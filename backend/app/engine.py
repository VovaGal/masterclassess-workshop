from copy import deepcopy
import time, json
from .models import Scenario, Action
from .festival import handle, evaluate, STAGES, COSTS

def initial(scenario: Scenario):
    return dict(current=scenario.start, revealed=False, boards={}, choices={}, metrics=scenario.metrics.copy(), history=[], timer_end=None, timer_remaining=60)

def apply(state, action: Action, scenario: Scenario):
    s=deepcopy(state)
    slides={x.id:x for x in scenario.slides}
    slide=slides[s['current']]
    if not scenario.simulation and action.type in ['name','demo','whatif','clear_whatif','report_detail']:raise ValueError('Команда доступна только в симуляции')
    if action.type=='reset': return initial(scenario)
    if action.type=='back':
        if s['history']: return s['history'].pop() | {'history':s['history']}
        return s
    if scenario.simulation:
        result=handle(s,action,scenario)
        if result is not None:return result
        if action.type=='choose':
            # A changed earlier decision invalidates later commitments.
            if slide.id in STAGES:
                for later in STAGES[STAGES.index(slide.id)+1:]:s['choices'].pop(later,None)
            s.pop('baseline',None);s.pop('comparison',None);s['demo']={'count':0,'message':''};s.pop('test_results',None)
            trial=deepcopy(s['choices']);trial[slide.id]=[action.value]
            if slide.id not in COSTS or action.value not in COSTS[slide.id]:raise ValueError('Unknown choice')
            if slide.id=='recovery' and action.value=='A' and not evaluate(trial,slide.id)['backup']:raise ValueError('Нужна независимая резервная копия. Выберите другой способ восстановления.')
            projection=evaluate(trial,slide.id)
            if projection['budget']<0 or projection['time']<0:raise ValueError('Недостаточно ресурсов. Сократите объём или пересмотрите более раннее решение.')
        if action.type=='next' and slide.choices and not s['choices'].get(slide.id):raise ValueError('Сначала примите решение')
    if action.type=='move':
        try: move=json.loads(action.value or '{}'); source=move['source']; card=move['card']; target=move['target']
        except (ValueError,KeyError,TypeError): raise ValueError('Invalid board move')
        columns=s.setdefault('boards',{}).setdefault(slide.id,deepcopy(slide.columns))
        if source not in columns or target not in columns or card not in columns[source]: raise ValueError('Unknown board item')
        columns[source].remove(card);columns[target].append(card)
    elif action.type=='reveal': s['revealed']=not s['revealed']
    elif action.type=='choose':
        if action.value not in {c.id for c in slide.choices}: raise ValueError('Unknown choice')
        selected=s['choices'].get(slide.id,[])
        if action.value in selected: selected.remove(action.value)
        elif slide.selection_limit==1: selected=[action.value]
        elif len(selected)<slide.selection_limit: selected.append(action.value)
        else: raise ValueError('Selection limit reached')
        s['choices'][slide.id]=selected
        s['metrics']=scenario.metrics.copy()
        for sid,chosen in s['choices'].items():
            for c in slides[sid].choices:
                if c.id in chosen:
                    for key,delta in c.effects.items(): s['metrics'][key]+=delta
    elif action.type in ('next','jump'):
        target=action.value if action.type=='jump' else slide.next
        if action.type=='next':
            for c in slide.choices:
                if c.id in s['choices'].get(slide.id,[]) and c.next: target=c.next
            if target is None:
                idx=next(i for i,x in enumerate(scenario.slides) if x.id==slide.id)
                if idx+1==len(scenario.slides): return s
                target=scenario.slides[idx+1].id
        if target not in slides: raise ValueError('Unknown slide')
        history=s.pop('history')
        history.append(deepcopy(s))
        s['history']=history[-300:]
        s.update(current=target,revealed=False,timer_end=None,timer_remaining=60)
    elif action.type=='timer':
        if action.value=='toggle':
            if s['timer_end']:
                s['timer_remaining']=max(0,s['timer_end']-time.time());s['timer_end']=None
            else: s['timer_end']=time.time()+s['timer_remaining']
        elif action.value in ['60','90','120','600']:
            s['timer_remaining']=int(action.value);s['timer_end']=None
        else: raise ValueError('Invalid timer command')
    if scenario.simulation:
        totals=evaluate(s['choices'],s['current']);s['metrics']={'Бюджет':totals['budget'],'Время':totals['time']}
    return s
