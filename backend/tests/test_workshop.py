import os,tempfile,json
from pathlib import Path
os.environ['WORKSHOP_DATA']=tempfile.mkdtemp()
from fastapi.testclient import TestClient
from app.main import app
from app.models import Scenario,Action
from app.engine import initial,apply
client=TestClient(app)
ROOT=Path(__file__).resolve().parents[2]

def test_complete_workshop_and_persistence():
    catalog=client.get('/api/scenarios').json();assert catalog[0]['slides']==29
    sid=client.post('/api/sessions',json={'scenario_id':'toolkit-interactive-v3'}).json()['id']
    s=client.get('/api/sessions/'+sid).json()
    for idx in range(28):
        s=client.post('/api/sessions/'+sid+'/actions',json={'revision':s['revision'],'type':'next'}).json()
    assert s['state']['current']=='s29'
    assert client.get('/api/sessions/'+sid).json()['state']==s['state']
    stale=client.post('/api/sessions/'+sid+'/actions',json={'revision':0,'type':'reset'})
    assert stale.status_code==409
    assert client.post('/api/sessions/'+sid+'/actions',json={'revision':s['revision'],'type':'jump','value':'missing'}).status_code==422

def test_branching_and_undo_no_double_effects():
    scenario=Scenario.model_validate_json((ROOT/'docs/scenario-example.json').read_text())
    s=initial(scenario)
    def act(kind,value=None):
        nonlocal s
        s=apply(s,Action(type=kind,value=value,revision=0),scenario)
    act('choose','A');assert s['metrics']['Условный бюджет']==8
    act('next');assert s['current']=='checked'
    act('back');assert s['current']=='start'
    act('choose','B');assert s['metrics']['Условный бюджет']==10
    act('next');assert s['current']=='finish'
    act('reset');assert s==initial(scenario)

def test_import_validation_and_snapshot():
    raw=json.loads((ROOT/'docs/scenario-example.json').read_text())
    raw['slides'][0]['choices'][0]['next']='missing'
    assert client.post('/api/scenarios',json=raw).status_code==422
    raw=json.loads((ROOT/'docs/scenario-example.json').read_text())
    assert client.post('/api/scenarios',json=raw).status_code==201
    assert client.post('/api/scenarios',json=raw).status_code==409
    sid=client.post('/api/sessions',json={'scenario_id':raw['id']}).json()['id']
    assert client.get('/api/sessions/'+sid).json()['scenario']['id']==raw['id']

def test_multiple_selection_order_and_timer():
    scenario=Scenario.model_validate_json((ROOT/'scenarios/toolkit.json').read_text())
    s=initial(scenario)
    for kind,value in [('jump','s26'),('choose','C'),('choose','A'),('choose','B')]:
        s=apply(s,Action(type=kind,value=value,revision=0),scenario)
    assert s['choices']['s26']==['C','A','B']
    import pytest
    with pytest.raises(ValueError):apply(s,Action(type='choose',value='F',revision=0),scenario)
    s=apply(s,Action(type='timer',value='90',revision=0),scenario)
    s=apply(s,Action(type='timer',value='toggle',revision=0),scenario)
    assert s['timer_end'] is not None
    s=apply(s,Action(type='timer',value='toggle',revision=0),scenario)
    assert 89<s['timer_remaining']<=90

def test_static_build_and_schema():
    response=client.get('/')
    assert response.status_code==200 and 'МТУСИ' in response.text
    import re
    for src in re.findall(r'(?:src|href)="(/assets/[^"]+)"',response.text):
        assert client.get(src).status_code==200
    assert client.get('/api/schema').json()['properties']['schema_version']
    assert client.get('/api/sessions/does-not-exist').status_code==404

def test_every_slide_content():
    s=Scenario.model_validate_json((ROOT/'scenarios/toolkit.json').read_text())
    assert len(s.slides)==29
    assert sum(x.minutes for x in s.slides if x.layout!='break')==90
    assert all(x.notes.talk for x in s.slides)
    assert len([x for x in s.slides if x.code])==2
    # Verify the teaching example and correction against expected boundary cases.
    snippets=[x.code for x in s.slides if x.code]
    env={};exec(snippets[0],env);assert env['can_register'](10,10) is True
    exec(snippets[1],env);assert env['can_register'](10,10) is False
    assert env['can_register'](9,10) is True

def test_board_move_and_undo():
    scenario=Scenario.model_validate_json((ROOT/'scenarios/toolkit.json').read_text())
    s=apply(initial(scenario),Action(type='jump',value='s08',revision=0),scenario)
    command=json.dumps({'source':'В работе','target':'На проверке','card':'Запись на мероприятие'})
    s=apply(s,Action(type='move',value=command,revision=0),scenario)
    assert 'Запись на мероприятие' in s['boards']['s08']['На проверке']
    s=apply(s,Action(type='next',revision=0),scenario)
    s=apply(s,Action(type='back',revision=0),scenario)
    assert 'Запись на мероприятие' in s['boards']['s08']['На проверке']

def test_interactive_v2_feedback_and_persistence():
    scenario=Scenario.model_validate_json((ROOT/'scenarios/toolkit.json').read_text())
    assert sum(bool(s.choices) for s in scenario.slides)>=15
    for slide in scenario.slides:
        if slide.choices:
            assert all(c.feedback for c in slide.choices)
            assert len(set(c.feedback for c in slide.choices))==len(slide.choices)
    state=initial(scenario)
    state=apply(state,Action(type='jump',value='s04',revision=0),scenario)
    state=apply(state,Action(type='choose',value='B',revision=0),scenario)
    state=apply(state,Action(type='next',revision=0),scenario)
    assert state['choices']['s04']==['B']
    assert scenario.slides[-1].title=='Ваш следующий проект'

def test_answer_assessment_and_substantial_notes():
    s=Scenario.model_validate_json((ROOT/'scenarios/toolkit.json').read_text())
    for slide in s.slides:
        assert len(' '.join(slide.notes.talk))>(300 if slide.layout=='break' else 500)
        if slide.choices:
            assert all(c.correct is not None for c in slide.choices)
            assert any(c.correct for c in slide.choices)
    assert [c.correct for c in s.slides[16].choices]==[True,False]
    assert all(c.correct for c in s.slides[17].choices)
    # Existing scenarios without assessment remain loadable.
    older=Scenario.model_validate_json((ROOT/'docs/scenario-example.json').read_text())
    assert older.slides[0].choices[0].correct is None
    sid=client.post('/api/sessions',json={'scenario_id':s.id}).json()['id']
    loaded=client.get('/api/sessions/'+sid).json()
    assert loaded['scenario']['slides'][16]['choices'][0]['correct'] is True
