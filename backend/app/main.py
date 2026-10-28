import json, os, sqlite3, uuid
from pathlib import Path
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .models import Scenario, NewSession, Action
from .engine import initial, apply
from .festival import evaluate

ROOT=Path(__file__).resolve().parents[2]
DATA=Path(os.getenv('WORKSHOP_DATA',str(ROOT/'data')))
DATA.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='MTUCI Workshop Studio',version='1.0.0')

@contextmanager
def db():
    con=sqlite3.connect(DATA/'workshops.sqlite3',timeout=10)
    con.row_factory=sqlite3.Row
    try: yield con;con.commit()
    except Exception: con.rollback();raise
    finally: con.close()

with db() as con:
    con.execute('CREATE TABLE IF NOT EXISTS scenarios (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, scenario TEXT NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP)')
    for p in (ROOT/'scenarios').glob('*.json'):
        scenario=Scenario.model_validate_json(p.read_text(encoding='utf-8'))
        con.execute('INSERT OR IGNORE INTO scenarios VALUES (?,?)',(scenario.id,scenario.model_dump_json()))

@app.get('/api/health')
def health(): return {'status':'ok'}

@app.get('/api/scenarios')
def scenarios():
    with db() as con: rows=con.execute('SELECT body FROM scenarios').fetchall()
    return [dict(id=s['id'],title=s['title'],subtitle=s['subtitle'],description=s['description'],slides=len(s['slides']),minutes=sum(x['minutes'] for x in s['slides'] if x['layout']!='break')) for r in rows for s in [json.loads(r['body'])]]

@app.get('/api/scenarios/{scenario_id}')
def scenario_get(scenario_id:str):
    with db() as con: row=con.execute('SELECT body FROM scenarios WHERE id=?',(scenario_id,)).fetchone()
    if not row: raise HTTPException(404,'Scenario not found')
    return json.loads(row['body'])

@app.post('/api/scenarios',status_code=201)
async def scenario_import(request:Request):
    raw=await request.body()
    if len(raw)>2_000_000: raise HTTPException(413,'Scenario exceeds 2 MB')
    try: s=Scenario.model_validate_json(raw)
    except ValueError as e: raise HTTPException(422,str(e))
    with db() as con:
        if con.execute('SELECT 1 FROM scenarios WHERE id=?',(s.id,)).fetchone(): raise HTTPException(409,'This scenario ID already exists. Change id to import a new version.')
        con.execute('INSERT INTO scenarios VALUES (?,?)',(s.id,s.model_dump_json()))
    return {'id':s.id}

@app.get('/api/schema')
def schema(): return Scenario.model_json_schema()

@app.post('/api/sessions',status_code=201)
def create_session(body:NewSession):
    s=Scenario.model_validate(scenario_get(body.scenario_id));sid=uuid.uuid4().hex
    with db() as con: con.execute('INSERT INTO sessions(id,scenario,state) VALUES (?,?,?)',(sid,s.model_dump_json(),json.dumps(initial(s))))
    return {'id':sid}

@app.get('/api/sessions')
def list_sessions():
    with db() as con: rows=con.execute('SELECT * FROM sessions ORDER BY created DESC,rowid DESC LIMIT 30').fetchall()
    return [dict(id=r['id'],title=json.loads(r['scenario'])['title'],created=r['created'],current=json.loads(r['state'])['current']) for r in rows]

@app.get('/api/sessions/{sid}')
def session_get(sid:str):
    with db() as con: row=con.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
    if not row: raise HTTPException(404,'Session not found')
    scenario=json.loads(row['scenario']);state=json.loads(row['state'])
    return dict(id=sid,scenario=scenario,state=state,revision=row['revision'],simulation=evaluate(state['choices'],state['current']) if scenario.get('simulation') else None)

@app.post('/api/sessions/{sid}/actions')
def action(sid:str,a:Action):
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
        if not row: raise HTTPException(404,'Session not found')
        if row['revision']!=a.revision: raise HTTPException(409,'State changed. Please retry.')
        try: state=apply(json.loads(row['state']),a,Scenario.model_validate_json(row['scenario']))
        except ValueError as e: raise HTTPException(422,str(e))
        con.execute('UPDATE sessions SET state=?,revision=revision+1 WHERE id=?',(json.dumps(state),sid))
    return session_get(sid)

DIST=ROOT/'frontend'/'dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/')
    def index(): return FileResponse(DIST/'index.html')
