# 출처: FM24 Dynamic PA v0.9.5 app/scouting_metrics.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Optional FM24 saved-season statistics. Missing is never a measured zero.

The 120-byte tail follows the validated 32-byte history header. Public FM24
24.4.2 field descriptions are hypotheses checked against record invariants.
This parser never reads/writes live memory. Its scores are bounded supplements.
"""
import math
import struct
from collections import defaultdict
from .model import percentile

FIELDS={'passes_attempted':8,'passes_completed':10,'tackles_attempted':12,
        'tackles_completed':14,'headers_attempted':16,'headers_won':18,
        'dribbles':20,'shots':26,'shots_on_target':28,'key_passes':54,
        'interceptions':60,'xg':72,'xa':74,'clearances':76,
        'progressive_passes':100,'pressures_attempted':102,
        'pressures_completed':104,'npxg':108,'crosses_attempted':112,
        'crosses_completed':114}
XG_FIELDS={'xg','xa','npxg'}
LABELS={'npxg':'비페널티 xG/90','xa':'기대 도움/90','key_passes':'키패스/90',
        'progressive_passes':'전진 패스/90','dribbles':'드리블/90',
        'tackles_completed':'태클 성공/90','interceptions':'가로채기/90',
        'headers_won':'헤더 성공/90','pass_pct':'패스 성공률','aerial_pct':'공중볼 성공률',
        'crosses_completed':'크로스 성공/90','pressures_completed':'압박 성공/90'}
# Direction/role is deliberately broad: no inferred on-pitch tactical role.
ROLE_WEIGHTS={
 'ST':{'npxg':.55,'xa':.20,'key_passes':.15,'dribbles':.10},
 'W':{'npxg':.20,'xa':.25,'key_passes':.20,'dribbles':.25,'crosses_completed':.10},
 'AM':{'npxg':.15,'xa':.30,'key_passes':.25,'progressive_passes':.20,'dribbles':.10},
 'CM':{'xa':.15,'key_passes':.20,'progressive_passes':.30,'pass_pct':.10,'interceptions':.15,'tackles_completed':.10},
 'DM':{'progressive_passes':.25,'pass_pct':.10,'interceptions':.35,'tackles_completed':.20,'headers_won':.10},
 'FB':{'xa':.15,'key_passes':.15,'progressive_passes':.20,'crosses_completed':.15,'interceptions':.20,'tackles_completed':.15},
 'CB':{'interceptions':.30,'tackles_completed':.15,'headers_won':.20,'aerial_pct':.15,'progressive_passes':.15,'pass_pct':.05},
 'GK':{}}

def decode(tail,minutes,goals,position):
    if len(tail)!=120 or minutes<=0 or not any(tail):return {},['상세 기록 없음']
    if position=='GK':return {},['골키퍼 상세 기록 의미 검증 전']
    raw={k:struct.unpack_from('<H',tail,o)[0] for k,o in FIELDS.items()}
    invalid=set();issues=[]
    for attempted,completed in [('passes_attempted','passes_completed'),('tackles_attempted','tackles_completed'),
        ('headers_attempted','headers_won'),('shots','shots_on_target'),
        ('crosses_attempted','crosses_completed'),('pressures_attempted','pressures_completed')]:
        if raw[completed]>raw[attempted]:invalid.update((attempted,completed));issues.append('횟수 관계 불일치: '+attempted)
    # Stored signed overperformance independently ties xG to the header's goals.
    over=struct.unpack_from('<h',tail,110)[0]
    if abs(goals*100-raw['xg']-over)>1 or raw['npxg']>raw['xg']:
        invalid.update(XG_FIELDS);issues.append('xG 관계 불일치')
    if raw['xg']>raw['shots']*100+1:
        invalid.update(XG_FIELDS);issues.append('xG 슈팅 한도 불일치')
    # Generous physical bounds reject bad decoding without guessing replacements.
    limits={'passes_attempted':200,'passes_completed':200,'key_passes':30,'progressive_passes':80,
            'dribbles':40,'tackles_attempted':45,'tackles_completed':45,'headers_attempted':65,
            'headers_won':65,'shots':35,'shots_on_target':35,'interceptions':45,
            'crosses_attempted':50,'crosses_completed':50,'clearances':50,
            'pressures_attempted':180,'pressures_completed':180}
    for key,limit in limits.items():
        if raw[key]>limit*minutes/90+10:invalid.add(key);issues.append('범위 불일치: '+key)
    values={key:{'value':value/(100 if key in XG_FIELDS else 1),'minutes':minutes}
            for key,value in raw.items() if key not in invalid}
    return values,issues

def combine(parts):
    out={}
    for part in parts:
        for key,item in part.get('advanced',{}).items():
            if key not in FIELDS:continue
            value=item.get('value');minutes=item.get('minutes')
            if not isinstance(value,(int,float)) or not isinstance(minutes,(int,float)) or not math.isfinite(value+minutes) or value<0 or minutes<=0:continue
            dest=out.setdefault(key,{'value':0.0,'minutes':0.0})
            dest['value']+=value;dest['minutes']+=minutes
    return out

def scaled(values,factor):
    return {k:{'value':v['value']*factor,'minutes':v['minutes']*factor} for k,v in values.items()}

def features(s):
    out={};minutes=s.get('minutes',0);data=s.get('advanced',{})
    if minutes<=0:return out
    valid={k:v for k,v in data.items() if .9*minutes<=v['minutes']<=minutes*1.001}
    for key,item in valid.items():out[key]=item['value']*90/item['minutes']
    for key,a,b in [('pass_pct','passes_attempted','passes_completed'),('aerial_pct','headers_attempted','headers_won')]:
        if a in valid and b in valid and abs(valid[a]['minutes']-valid[b]['minutes'])<.01 and valid[a]['value']>=30:
            out[key]=100*valid[b]['value']/valid[a]['value']
    return out

def distributions(rows,minimum):
    """All rows belong to one competition/category and position."""
    groups=defaultdict(list)
    for s in rows:
        for key,value in features(s).items():groups[key].append(value)
    return {key:sorted(values) for key,values in groups.items() if len(values)>=max(12,minimum)}

def adjust(s,position,base,dist,rules):
    values=features(s);weights=ROLE_WEIGHTS[position];used=[];delta=0;available=0
    if rules.get('advanced_weight',0)<=0:
        s.update(advanced_adjustment=0,advanced_metric_count=0,advanced_coverage=0,
                 advanced_used=[],advanced_status='상세 기록 보정 꺼짐',advanced_features={})
        return base
    for key,weight in weights.items():
        if key not in values or key not in dist:continue
        pct=percentile(dist[key],values[key]);available+=weight
        delta+=weight*(pct-base)
        used.append({'metric':key,'label':LABELS[key],'value':round(values[key],4),'percentile':round(pct,3),'peers':len(dist[key])})
    # Partial metric coverage reduces influence. No re-weighting sparse fields to 100%.
    correction=max(-rules['advanced_cap'],min(rules['advanced_cap'],rules['advanced_weight']*delta))
    correction*=min(1,s.get('minutes',0)/1200)
    s.update(advanced_adjustment=round(correction,4),advanced_metric_count=len(used),
             advanced_coverage=round(available,4),advanced_used=used,
             advanced_status='상세 기록 반영' if used else '기본 기록 평가 · 상세 자료 부족',
             advanced_features={key:round(value,4) for key,value in values.items()})
    return max(0,min(100,base+correction))

def development(age,position,ca_growth):
    # A gameplay stage, never biological maturity. High CA alone is not a veto.
    late=2 if position in ('GK','CB','DM') else 0
    if age<=18:return '유소년 성장기',1.0
    if age<=21:return '초기 성장기',.85
    if age<=24+late:
        growing=ca_growth is not None and ca_growth>=3
        return ('성장 지속' if growing else '성장 후기'),(.65 if growing else .45)
    if ca_growth is not None and ca_growth>=3:return '늦은 성장',.25
    return '성숙 단계',.10
