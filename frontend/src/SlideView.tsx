import {useLayoutEffect,useRef,useState} from 'react';
import {FestivalView} from './FestivalView';
import type {Session} from './types';
export function SlideView({session,onChoose,onMove,onAction,readonly=false}:{session:Session;onChoose:(id:string)=>void;onMove?:(value:string)=>void;onAction?:(type:string,value?:string)=>void;readonly?:boolean}){
 const viewport=useRef<HTMLDivElement>(null),[scale,setScale]=useState(1);
 useLayoutEffect(()=>{const el=viewport.current!;const resize=()=>setScale(Math.min(el.clientWidth/1600,el.clientHeight/900));resize();const observer=new ResizeObserver(resize);observer.observe(el);return()=>observer.disconnect()},[]);
 const {scenario,state}=session,slide=scenario.slides.find(s=>s.id===state.current)!;
 const selected=state.choices[slide.id]||[],index=scenario.slides.indexOf(slide),chosen=selected.map(id=>slide.choices.find(c=>c.id===id)!).filter(Boolean);
 const columns=state.boards?.[slide.id]||slide.columns;
 const boardCards=Object.values(columns).flat(),done=Object.entries(columns).at(-1)?.[1].length||0;
 const decisionHistory=[...new Map(scenario.slides.filter(s=>state.choices[s.id]?.length&&s.id!==slide.id).map(s=>[s.section,s])).values()];
 const wrong=chosen.filter(c=>c.correct===false);
 const right=chosen.filter(c=>c.correct===true);
 const recommended=right.length?right:slide.choices.filter(c=>c.correct===true).slice(0,1);
 const ungraded=chosen.filter(c=>c.correct==null);
 const answerCards=[...wrong,...recommended,...ungraded];
 if(scenario.simulation==='festival-v1'&&session.simulation)return <FestivalView session={session} scale={scale} viewport={viewport} onChoose={onChoose} onAction={onAction||(()=>{})} readonly={readonly}/>;
 return <div className="ws-viewport" ref={viewport}><section className={'ws-canvas ws-layout-'+slide.layout+(state.revealed?' ws-revealed':'')} style={{transform:`translate(-50%,-50%) scale(${scale})`}}>
 <header className="ws-header"><span>МТУСИ <small>/ МАСТЕРСКАЯ ПРОЕКТОВ</small></span><span>{slide.section}</span><span>{index+1} / {scenario.slides.length}</span></header>
 <main className="ws-content"><div className="ws-eyebrow">{state.revealed?'РАЗБОР РЕШЕНИЯ':slide.layout==='break'?'ПЕРЕРЫВ':slide.choices.length?'РЕШЕНИЕ ЗА ВАМИ':'РАЗБИРАЕМ КЕЙС'}</div><h1>{slide.title}</h1>
 {state.revealed?<div className="ws-results">
 {chosen.length===0&&slide.choices.length>0&&<p className="ws-unanswered">Ответ ещё не выбран. Вернитесь к заданию и отметьте решение команды.</p>}
 <div className={'ws-verdicts '+(answerCards.length>2?'ws-verdicts-many':'')}>
 {answerCards.map(c=><article key={c.id} className={c.correct===false?'ws-incorrect':c.correct===true?'ws-correct':'ws-neutral'}>
 <small>{c.correct===false?'✕ ВЫ ВЫБРАЛИ · ЗДЕСЬ ОШИБКА':c.correct===true?(selected.includes(c.id)?'✓ ВЫ ВЫБРАЛИ · ВЕРНО':'✓ ПОДХОДЯЩЕЕ РЕШЕНИЕ'):'ВАШ ВАРИАНТ · ОБСУДИМ'}</small>
 <h2>{c.id}. {c.label}</h2><p>{c.feedback}</p></article>)}
 </div>
 <div className="ws-takeaway">{slide.reveal.map((t,i)=><p key={i}>{t}</p>)}</div>
 </div>:<>
 {slide.layout==='flow'?<div className="ws-timeline">{slide.body.map((t,i)=><div key={i}><span>{i+1}</span><h2>{t}</h2>{i<slide.body.length-1&&<b className="ws-arrow">→</b>}</div>)}</div>:<div className="ws-body">{(slide.layout==='summary'?['Вот решения, которые вы приняли. Что из этого вы оставите для следующего проекта?']:slide.body).map((t,i)=><p key={i}>{t}</p>)}</div>}
 {slide.code&&<pre className="ws-code"><small>PYTHON · ПРОЧИТАЙТЕ УСЛОВИЕ</small><code>{slide.code}</code></pre>}
 {slide.layout==='board'&&<><div className="ws-board">{Object.entries(columns).map(([title,cards])=><div className={cards.length>2?'ws-packed':''} key={title}><h2>{title} <small>{cards.length}</small></h2>{cards.map(c=><div className="ws-task" key={c}><strong>{c}</strong>{!readonly&&<select aria-label={'Переместить: '+c} value={title} onChange={e=>onMove?.(JSON.stringify({source:title,card:c,target:e.target.value}))}>{Object.keys(columns).map(k=><option key={k}>{k}</option>)}</select>}</div>)}</div>)}</div><div className="ws-board-status">Проверено и готово: <b>{done} из {boardCards.length}</b><span>{done===boardCards.length?'Всё перемещено в «Готово». Какие проверки это подтверждают?':'Код написан? Перед «Готово» ещё нужна проверка.'}</span></div></>}
 {slide.layout==='summary'&&<div className="ws-history">{decisionHistory.slice(-6).map(s=><article key={s.id}><small>{s.section}</small><p>{s.selection_limit>1?'Ваш порядок действий: '+state.choices[s.id].join(' → '):state.choices[s.id].map(id=>s.choices.find(c=>c.id===id)?.label).join(' → ')}</p></article>)}{!decisionHistory.length&&<p>Пока нет сохранённых решений. Вернитесь к одному кейсу и выберите действие вместе.</p>}</div>}
 {slide.choices.length>0&&<><div className={'ws-choices ws-count-'+slide.choices.length}>{slide.choices.map(c=><button key={c.id} disabled={readonly} className={selected.includes(c.id)?'ws-selected':''} aria-pressed={selected.includes(c.id)} onClick={()=>onChoose(c.id)}><b>{c.id}</b><span>{c.label}</span>{selected.includes(c.id)&&<em>✓ {slide.selection_limit>1?selected.indexOf(c.id)+1:''}</em>}</button>)}</div>
 {chosen.length>0?<div className="ws-live-result" role="status"><b>{slide.selection_limit>1?`Порядок: ${selected.join(' → ')} · ${selected.length}/${slide.selection_limit}`:'Выбор команды принят'}</b><p>{slide.selection_limit>1?'Расположите действия по порядку, затем откройте разбор.':'Откройте разбор, чтобы проверить решение и сравнить объяснения.'}</p></div>:<p className="ws-instruction">{slide.selection_limit>1?`Выберите ${slide.selection_limit} действия по порядку.`:'Обсудите в команде и проголосуйте руками. Ведущий отмечает ваш ответ.'}</p>}
 </>}
 {scenario.id.startsWith('toolkit-')&&slide.id==='s29'&&<div className="ws-exit"><b>30 секунд — соседу. Затем 3 ответа — всему залу.</b><p>Например: «Попробую Git: мы постоянно теряем версии файлов».</p></div>}
 </>}
 {Object.keys(state.metrics).length>0&&<div className="ws-metrics">{Object.entries(state.metrics).map(([k,v])=><span key={k}>{k}: <b>{v}</b></span>)}</div>}
 </main><footer className="ws-footer"><span>{state.revealed?'Сравните с другим вариантом: что изменится?':'Сначала обсудите. Затем проверьте своё решение.'}</span><div><i style={{width:`${(index+1)/scenario.slides.length*100}%`}}/></div></footer>
 </section></div>
}
