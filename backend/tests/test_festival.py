import json
from copy import deepcopy
from pathlib import Path
import pytest
from app.models import Scenario,Action
from app.engine import initial,apply
from app.festival import evaluate,STAGES
SC=Scenario.model_validate_json((Path(__file__).resolve().parents[2]/'scenarios/roadmap.json').read_text())
GOOD=dict(zip(STAGES,['A','A','A','B','B','B','B','A','C','B']))
def act(s,t,v=None):return apply(s,Action(type=t,value=v,revision=0),SC)
def finish(plan=GOOD):
 s=initial(SC)
 for key in STAGES:
  s=act(s,'jump',key);s=act(s,'choose',plan[key])
 return act(s,'jump','report')

def test_balanced_launch_and_backups():
 r=evaluate(finish()['choices'],'report')
 assert r['budget']==39 and r['time']==8 and r['lost']==1 and not r['offline']
 assert 'пилот' in r['verdict']
 no=deepcopy(GOOD);no.update(hosting='A',recovery='B')
 assert evaluate(finish(no)['choices'],'report')['lost']==24
 rep=deepcopy(GOOD);rep['hosting']='C'
 assert evaluate(finish(rep)['choices'],'report')['lost']==0

def test_unavailable_recovery_and_no_overspend():
 s=initial(SC);s=act(s,'jump','recovery')
 with pytest.raises(ValueError):act(s,'choose','A')
 # A costly expanded route cannot accept another unaffordable item.
 s=initial(SC)
 for stage,opt in [('discovery','B'),('scope','B'),('workflow','B'),('build','A'),('mobile','A'),('hosting','C')]:
  s=act(s,'jump',stage);s=act(s,'choose',opt)
 s=act(s,'jump','review')
 with pytest.raises(ValueError):act(s,'choose','A')
 assert evaluate(s['choices'],'review')['budget']==3

def test_counterfactual_original_preserved_and_rerated():
 s=finish();before=deepcopy(s['choices'])
 s=act(s,'whatif',json.dumps({'stage':'hosting','choice':'A'}))
 assert s['choices']==before and s['baseline']['choices']==before
 assert s['comparison']['report']['offline']
 assert s['comparison']['report']['lost']==24
 s=act(s,'whatif',json.dumps({'stage':'hosting','choice':'C'}))
 assert s['baseline']['choices']==before and s['comparison']['report']['lost']==0
 s=act(s,'clear_whatif');assert 'comparison' not in s and s['choices']==before

def test_demo_boundary_and_fix():
 s=initial(SC)
 for key,opt in [('scope','A'),('build','C')]:s=act(s,'jump',key);s=act(s,'choose',opt)
 for _ in range(4):s=act(s,'demo','register')
 assert s['demo']['count']==4
 s=act(s,'demo','register');assert s['demo']['count']==4
 s=act(s,'jump','review');s=act(s,'choose','A')
 for _ in range(4):s=act(s,'demo','register')
 assert s['demo']['count']==3
 s=act(s,'demo','test');assert all(x['passed'] for x in s['test_results'])
 s=act(s,'jump','incident');s=act(s,'demo','register');assert '503' in s['demo']['message']

def test_changed_history_invalidates_downstream_and_name():
 s=finish();s=act(s,'name','Кот и код');assert s['company_name']=='Кот и код'
 s=act(s,'jump','scope');s=act(s,'choose','C')
 assert set(s['choices'])=={'discovery','scope'}
 assert not evaluate(s['choices'],'scope')['core']

def test_session_api_snapshot_and_assessment_compatibility():
 from app.main import app
 from fastapi.testclient import TestClient
 c=TestClient(app);sid=c.post('/api/sessions',json={'scenario_id':SC.id}).json()['id']
 s=c.get('/api/sessions/'+sid).json();assert s['simulation']['budget']==100
 s=c.post('/api/sessions/'+sid+'/actions',json={'revision':0,'type':'name','value':'ФестЛаб'}).json()
 assert c.get('/api/sessions/'+sid).json()['state']['company_name']=='ФестЛаб'
 assert c.post('/api/sessions/'+sid+'/actions',json={'revision':s['revision'],'type':'whatif','value':'{}'}).status_code==422

def test_displayed_prices_match_authoritative_rules():
 raw=SC.model_dump();raw['slides'][1]['choices'][0]['effects']['Бюджет']=-1
 with pytest.raises(ValueError):Scenario.model_validate(raw)

def test_report_detail_and_counterfactual_does_not_modify_original_metrics():
 s=finish();s=act(s,'report_detail','open');assert s['report_details']
 metrics=deepcopy(s['metrics'])
 s=act(s,'whatif',json.dumps({'stage':'hosting','choice':'C'}))
 assert s['metrics']==metrics
 s=act(s,'report_detail','close');assert not s['report_details']

def test_entire_api_route_with_recovery_and_alternative():
 from app.main import app
 from fastapi.testclient import TestClient
 c=TestClient(app);sid=c.post('/api/sessions',json={'scenario_id':SC.id}).json()['id']
 s=c.get('/api/sessions/'+sid).json()
 for _ in range(30):
  current=s['state']['current']
  if current=='report':break
  if current in GOOD:
   response=c.post('/api/sessions/'+sid+'/actions',json={'revision':s['revision'],'type':'choose','value':GOOD[current]})
   assert response.status_code==200,response.text
   s=response.json()
  response=c.post('/api/sessions/'+sid+'/actions',json={'revision':s['revision'],'type':'next'})
  assert response.status_code==200,response.text
  s=response.json()
 assert s['state']['current']=='report' and s['simulation']['lost']==1
 response=c.post('/api/sessions/'+sid+'/actions',json={'revision':s['revision'],'type':'whatif','value':json.dumps({'stage':'hosting','choice':'C'})})
 assert response.status_code==200,response.text
 saved=c.get('/api/sessions/'+sid).json()
 assert saved['state']['comparison']['report']['lost']==0
 assert saved['simulation']['lost']==1
