from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Choice(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    label: str = Field(min_length=1, max_length=500)
    feedback: str = ''
    correct: bool | None = None
    next: str | None = None
    effects: dict[str, float] = Field(default_factory=dict)

class Notes(Model):
    talk: list[str] = Field(default_factory=list)
    activity: list[str] = Field(default_factory=list)
    important: str = ''
    short: str = ''

class Slide(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    title: str = Field(min_length=1, max_length=200)
    section: str
    layout: Literal['title','cards','choice','code','board','flow','break','summary'] = 'cards'
    minutes: int = Field(default=3,ge=0,le=120)
    body: list[str] = Field(default_factory=list, max_length=8)
    code: str | None = None
    reveal: list[str] = Field(default_factory=list)
    choices: list[Choice] = Field(default_factory=list, max_length=8)
    selection_limit: int = Field(default=1,ge=1,le=8)
    columns: dict[str,list[str]] = Field(default_factory=dict)
    next: str | None = None
    notes: Notes = Field(default_factory=Notes)

class Scenario(Model):
    schema_version: Literal[1] = 1
    simulation: Literal['festival-v1'] | None = None
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,63}$')
    title: str = Field(min_length=1,max_length=200)
    subtitle: str = ''
    description: str = ''
    start: str
    metrics: dict[str,float] = Field(default_factory=dict)
    slides: list[Slide] = Field(min_length=1,max_length=200)

    @model_validator(mode='after')
    def graph(self):
        ids = {s.id for s in self.slides}
        if len(ids)!=len(self.slides): raise ValueError('Duplicate slide ids')
        if self.start not in ids: raise ValueError('Unknown start slide')
        for s in self.slides:
            if len({c.id for c in s.choices}) != len(s.choices): raise ValueError('Duplicate choice ids')
            if s.selection_limit>1 and any(c.next for c in s.choices): raise ValueError('Multiple choices cannot have branch targets')
            for target in [s.next]+[c.next for c in s.choices]:
                if target is not None and target not in ids: raise ValueError('Unknown transition: '+target)
            for c in s.choices:
                if not set(c.effects)<=set(self.metrics): raise ValueError('Unknown metric')
        if self.simulation:
            from .festival import COSTS
            by_id={s.id:s for s in self.slides}
            if not set(COSTS)<=set(by_id):raise ValueError('Missing festival stages')
            for key,options in COSTS.items():
                if {c.id for c in by_id[key].choices}!=set(options):raise ValueError('Festival options must match rule pack')
                for c in by_id[key].choices:
                    b,t=options[c.id]
                    if c.effects!={'Бюджет':-b,'Время':-t}:raise ValueError('Displayed festival prices must match rules')
        return self

class NewSession(Model):
    scenario_id: str

class Action(Model):
    revision: int
    type: Literal['next','back','reveal','choose','jump','timer','reset','move','name','demo','whatif','clear_whatif','report_detail']
    value: str | None = None
