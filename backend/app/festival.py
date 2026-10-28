"""Deterministic teaching simulation; all quantities are fictional game units."""
from copy import deepcopy
import json
STAGES=['discovery','scope','workflow','build','mobile','hosting','review','recovery','request','release']
# option: credits, development-time units
COSTS={
'discovery':{'A':(8,2),'B':(12,2),'C':(0,0)},
'scope':{'A':(12,3),'B':(26,5),'C':(6,2)},
'workflow':{'A':(8,1),'B':(14,2),'C':(0,0)},
'build':{'A':(12,3),'B':(8,2),'C':(3,1)},
'mobile':{'A':(8,1),'B':(0,0),'C':(3,1)},
'hosting':{'A':(5,1),'B':(15,1),'C':(25,2)},
'review':{'A':(8,2),'B':(0,0),'C':(2,0)},
'recovery':{'A':(8,2),'B':(14,4),'C':(4,1)},
'request':{'A':(16,3),'B':(6,2),'C':(0,0)},
'release':{'A':(4,1),'B':(2,1),'C':(0,0)}}

def evaluate(choices, current='report'):
    pick={k:v[0] for k,v in choices.items() if k in STAGES and v}
    budget,remaining=100,20
    ledger=[]
    for key in STAGES:
        if key in pick:
            b,t=COSTS[key][pick[key]];budget-=b;remaining-=t
            ledger.append({'stage':key,'credits':b,'time':t,'reason':'Решение команды'})
    order=STAGES.index(current) if current in STAGES else (4 if current=='midpoint' else 10 if current in ['incident','report'] else -1)
    incident=order>=7 or current in ['incident','report']
    handover=order>=5 or current in ['incident','report']
    if handover and pick.get('workflow')=='C':
        budget-=6;remaining-=2;ledger.append({'stage':'handover','credits':6,'time':2,'reason':'Коллега недоступен: восстанавливаем инструкции'})
    core=pick.get('scope') in ['A','B'] and 'build' in pick
    prototype=pick.get('scope')=='C'
    checked=pick.get('build') in ['A','B'] or pick.get('review')=='A'
    capacity_bug=core and not checked
    late_bug=pick.get('review')=='C'
    mobile=pick.get('discovery')=='B' or pick.get('mobile') in ['A','C']
    backup=pick.get('hosting') in ['B','C']
    recovery=pick.get('recovery')
    offline=incident
    lost=None;downtime=None;recovery_text='Инцидент ещё не произошёл'
    if incident:
        recovery_text='Диск сервера отказал. Рабочая база недоступна.'
        if recovery:
            offline=False
            if recovery=='A' and backup:
                lost=1 if pick.get('hosting')=='B' else 0;downtime=2 if lost else 1
                recovery_text='Сервис восстановлен из независимой копии.'
            elif recovery=='B':
                lost=0 if backup and pick.get('hosting')=='C' else 1 if backup else 24
                downtime=4;recovery_text='Окружение собрано заново. Данные восстановлены только из доступных копий.'
            elif recovery=='C':
                lost=24;downtime=1;recovery_text='Чистая база запущена быстро. Старые записи не восстановлены.'
            else:
                offline=True;lost=24;downtime=4;recovery_text='Независимой копии нет: восстановить с неё нельзя.'
    notifications=pick.get('scope')=='B' or pick.get('request') in ['A','B']
    profiles=pick.get('scope')=='B' and pick.get('request')!='B'
    features=[{'name':'Запись и лимит мест','status':'не входит в прототип' if prototype else 'не собрано' if not core else 'ошибка сохранения' if late_bug else 'ошибка границы' if capacity_bug else 'работает'},
              {'name':'Список организатора','status':'работает' if core else 'не собрано'},
              {'name':'Телефон','status':'проверено' if mobile else 'не проверено'},
              {'name':'Уведомления','status':'готовы' if notifications and core else 'отложены'},
              {'name':'Профили','status':'готовы' if profiles and core else 'вне объёма'},
              {'name':'Позднее изменение','status':'дефект: подтверждение без сохранения' if late_bug else 'проверено' if pick.get('review')=='A' else 'отложено'}]
    issues=[]
    if budget<0:issues.append('Превышен бюджет')
    if remaining<0:issues.append('Превышен срок')
    if not core:issues.append('Рабочая регистрация не собрана')
    if capacity_bug:issues.append('Полное мероприятие принимает лишнего участника')
    if late_bug:issues.append('Поздняя правка подтверждает запись без сохранения')
    if offline:issues.append('Сервис не восстановлен')
    if incident and lost:issues.append(f'Потеряно записей: {lost} из 24')
    release=pick.get('release')
    hard=budget<0 or remaining<0 or not core or capacity_bug or late_bug or offline
    if release=='C':verdict='Показ прототипа' if prototype else 'Запуск отложен осознанно'
    elif hard:verdict='Заявленный запуск не готов'
    elif release=='B':verdict='Ограниченный пилот: предупредите об ограничениях'
    elif lost or not mobile:verdict='Запуск с ограничениями и обязательными действиями'
    else:verdict='Готово к учебному запуску'
    return dict(budget=budget,time=remaining,ledger=ledger,features=features,issues=issues,core=core,prototype=prototype,checked=checked,capacity_bug=capacity_bug,late_bug=late_bug,mobile=mobile,backup=backup,incident=incident,offline=offline,lost=lost,downtime=downtime,recovery_text=recovery_text,verdict=verdict,pick=pick)

def handle(s,a,scenario):
    """Return updated state for simulation-only commands; None delegates navigation."""
    if a.type=='report_detail':
        s['report_details']=a.value=='open';return s
    if a.type=='name':
        value=(a.value or '').strip()
        if not 1<=len(value)<=45:raise ValueError('Название: от 1 до 45 символов')
        s['company_name']=value;return s
    if a.type=='demo':
        result=evaluate(s['choices'],s['current'])
        if a.value=='reset':s['demo']={'count':0,'message':'Демонстрация сброшена'};return s
        if a.value=='test':
            s['test_results']=[{'name':'Есть место','passed':result['core'] and not result['offline'] and not result['late_bug']}, {'name':'Мест нет','passed':result['core'] and result['checked'] and not result['offline'] and not result['late_bug']}, {'name':'Запись сохраняется','passed':result['core'] and not result['late_bug'] and not result['offline']}];return s
        demo=s.setdefault('demo',{'count':0,'message':''})
        if result['offline']:demo['message']='503 · сервис недоступен'
        elif not result['core']:demo['message']='Это прототип: настоящая запись ещё не реализована'
        elif a.value=='duplicate':demo['message']='Повторная запись отклонена' if demo['count'] else 'Сначала запишите первого гостя'
        elif a.value=='register':
            if demo['count']>=(4 if result['capacity_bug'] else 3):demo['message']='Мест нет: запись отклонена'
            elif result['late_bug']:demo['message']='Показали успех, но запись не сохранилась — дефект поздней правки'
            else:demo['count']+=1;demo['message']='Гость записан'+(' · ОШИБКА: превышена вместимость!' if demo['count']>3 else '')
        else:raise ValueError('Unknown demo command')
        return s
    if a.type=='whatif':
        if s['current']!='report' or len([k for k in STAGES if s['choices'].get(k)])!=10:raise ValueError('Сначала завершите все десять решений и откройте отчёт')
        try:payload=json.loads(a.value or '{}');stage=payload['stage'];choice=payload['choice']
        except (ValueError,KeyError,TypeError):raise ValueError('Неверный формат альтернативы')
        if stage not in COSTS or choice not in COSTS[stage]:raise ValueError('Неизвестная альтернатива')
        if 'baseline' not in s:s['baseline']={'choices':deepcopy(s['choices']),'report':evaluate(s['choices'],'report')}
        variant=deepcopy(s['baseline']['choices']);variant[stage]=[choice]
        s['comparison']={'stage':stage,'choice':choice,'report':evaluate(variant,'report'),'choices':variant};return s
    if a.type=='clear_whatif':s.pop('comparison',None);return s
    return None
