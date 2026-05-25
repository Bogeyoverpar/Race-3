
from dataclasses import dataclass, field
from pathlib import Path
import csv
@dataclass(frozen=True)
class Driver:
    driver_id:str; name:str; team:str; manufacturer:str; car_number:str
    speed:int; consistency:int; aggression:int; qualifying:int; pit_crew:int; tire_saving:int
@dataclass(frozen=True)
class Race:
    race_id:str; name:str; track:str; track_type:str; laps:int; stage_1_end:int; stage_2_end:int; chaos:int
@dataclass
class RunningCar:
    driver:Driver; position:int; qualifying_position:int; score:float=0
    stage_points:int=0; bonus_points:int=0; laps_led:int=0; cautions_involved:int=0
    crashed_out:bool=False; damage_status:str='RUNNING'; pit_stops:int=0; penalties:int=0
@dataclass
class RaceEvent:
    event_type:str; lap:int; title:str; message:str; requires_decision:bool=False
    options:list[str]=field(default_factory=list); data:dict=field(default_factory=dict)
def _to_int(v,d=0):
    try: return int(v)
    except Exception: return d
def load_drivers(path:Path):
    out=[]
    with path.open(newline='', encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            out.append(Driver(r['driver_id'],r['name'],r['team'],r['manufacturer'],r['car_number'],_to_int(r['speed']),_to_int(r['consistency']),_to_int(r['aggression']),_to_int(r['qualifying']),_to_int(r['pit_crew']),_to_int(r['tire_saving'])))
    return out
def load_schedule(path:Path):
    out=[]
    with path.open(newline='', encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            out.append(Race(r['race_id'],r['name'],r['track'],r['track_type'],_to_int(r['laps'],10),_to_int(r['stage_1_end'],3),_to_int(r['stage_2_end'],6),_to_int(r['chaos'],5)))
    return out
