# 출처: FM24 Dynamic PA v0.9.5 app/rules.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Validated, content-addressed gameplay settings. Frozen plans keep their rules."""
import hashlib,json,math
from datetime import date
from copy import deepcopy
from .model import percentile
from collections import defaultdict
from statistics import median

DEFAULTS={'advanced_weight':.25,'advanced_cap':8,'youth_rare_setbacks':True,'schema':1,'growth_minutes':1600,'decline_minutes':1200,'rated_games':10,
 'growth_percentile':70,'poor_percentile':35,'poor_rating':6.7,
 'rating_weights':{'GK':1.0,'CB':.90,'FB':.85,'DM':.85,'CM':.75,'AM':.65,'W':.65,'ST':.60},
 'ca_adjustment':.3,'ca_adjustment_cap':12,'normal_decline_cap':5,'normal_growth_cap':16,
 'league_growth_min':.65,'league_growth_max':1.30,'net_growth_budget':.25,
 'soft_barrier':[[1,1.0],[150,1.0],[160,.60],[170,.45],[180,.30],[190,.10],[200,0.0]],
 'age_factors':[[14,1.4],[18,1.4],[21,1.3],[24,1.2],[27,1.05],[30,.95],[65,.8]],
 'peak_windows':{'GK':[29,33],'CB':[27,31],'FB':[24,28],'DM':[27,31],'CM':[26,30],'AM':[25,29],'W':[23,27],'ST':[26,30]},
 'rare_events':True,'rare_setbacks':False,'team_rating_weight':.35,'team_rating_cap':.15,'three_poor_extra':1}

BOUNDS={'advanced_weight':(0,.4),'advanced_cap':(0,12),'growth_minutes':(300,9000),'decline_minutes':(300,9000),'rated_games':(1,100),
 'growth_percentile':(50,99),'poor_percentile':(1,49),'poor_rating':(1,10),
 'ca_adjustment':(0,1),'ca_adjustment_cap':(0,25),'normal_decline_cap':(0,20),
 'normal_growth_cap':(0,40),'league_growth_min':(.1,1),'league_growth_max':(1,2),
 'net_growth_budget':(0,2),'three_poor_extra':(0,5),'team_rating_weight':(0,1),'team_rating_cap':(0,.3)}
EFFECTS={'advanced_weight':'포지션별 상세 기록의 보정 강도입니다. 0은 미사용, 기본 0.25. 누락된 지표 비중은 자동으로 줄어듭니다.',
 'advanced_cap':'상세 기록이 바꿀 수 있는 백분위의 최대 폭입니다. 기본 ±8점. PA 증가량이 아닙니다.',
 'growth_minutes':'성인 기준입니다. 18세 이하 ×0.375, 19~21세 ×0.5625, 22~24세 ×0.75 (최저 300분). 높이면 상승 조건이 엄격해집니다.',
 'decline_minutes':'성인 기준입니다. 18세 이하 ×1.5, 19~21세 ×1.25. 높이면 하락에 더 많은 출전을 요구합니다.',
 'rated_games':'성인 기준입니다. 유망주 상승은 적은 경기 수를 허용하고 하락은 더 많은 경기 수를 요구합니다. 최저 5경기를 사용합니다.',
 'growth_percentile':'높일수록 상승 조건이 엄격해지고, 낮추면 상승 자격이 넓어집니다.',
 'poor_percentile':'높일수록 부진 판정 대상이 넓어집니다. 다른 부진 조건도 충족해야 합니다.',
 'poor_rating':'높일수록 실제 평점에 의한 부진 기준이 엄격해져 하락 대상이 늘 수 있습니다.',
 'ca_adjustment':'높일수록 같은 포지션 비교군보다 CA가 낮은 선수의 활약을 더 우대합니다.',
 'ca_adjustment_cap':'높일수록 CA 차이로 보정할 수 있는 백분위 폭이 넓어집니다.',
 'normal_decline_cap':'높일수록 일반 하락의 최대 폭이 커집니다. 드문 하락 사건은 별도입니다.',
 'normal_growth_cap':'높일수록 일반 상승의 최대 폭이 커집니다. 나이별 한도도 함께 적용합니다.',
 'league_growth_min':'높일수록 평균 CA가 낮은 리그의 상승 억제가 약해집니다. 1이면 하위 리그 감쇠가 없습니다.',
 'league_growth_max':'높일수록 평균 CA가 높은 리그의 상승 보너스가 커집니다. 1이면 상위 리그 가산이 없습니다.',
 'net_growth_budget':'높일수록 전체 순상승 허용량이 커집니다. 0은 전체 합계의 순상승을 막으며 개별 상승을 모두 막지는 않습니다.',
 'three_poor_extra':'높일수록 확인된 3시즌 연속 부진의 추가 하락이 커집니다. 0이면 추가 감점이 없습니다.',
 'team_rating_weight':'높일수록 소속팀의 평균 평점이 평가에 미치는 영향을 더 보정합니다. 팀 비교 자료가 있을 때만 사용합니다.',
 'team_rating_cap':'팀 환경으로 보정할 수 있는 평점 폭입니다. 0이면 팀 평점 보정이 없습니다.'}

def participation(age,rules):
    growth=.375 if age<=18 else .5625 if age<=21 else .75 if age<=24 else 1
    decline=1.5 if age<=18 else 1.25 if age<=21 else 1
    rated_up=.5 if age<=18 else .7 if age<=21 else .8 if age<=24 else 1
    rated_down=1.5 if age<=18 else 1.2 if age<=21 else 1
    return dict(growth_minutes_required=max(300,math.ceil(rules['growth_minutes']*growth)),
                decline_minutes_required=math.ceil(rules['decline_minutes']*decline),
                growth_rated_required=max(5,math.ceil(rules['rated_games']*rated_up)),
                decline_rated_required=max(5,math.ceil(rules['rated_games']*rated_down)))

def validate(value):
    if isinstance(value,dict):
        value=dict(value)
        for key in ('advanced_weight','advanced_cap','youth_rare_setbacks'):value.setdefault(key,DEFAULTS[key])
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS):raise ValueError('평가 기준 키를 추가·삭제할 수 없습니다. 기본 형식을 사용하세요.')
    r=deepcopy(value)
    for key,(low,high) in BOUNDS.items():
        x=r[key]
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not low<=x<=high:raise ValueError(f'{key}: {low} ~ {high} 범위가 필요합니다.')
    if r['schema']!=1 or type(r['rare_events']) is not bool or type(r['rare_setbacks']) is not bool or type(r['youth_rare_setbacks']) is not bool:raise ValueError('기준 형식 오류')
    if r['league_growth_min']>1 or r['league_growth_max']<1:raise ValueError('리그 배율은 중립값 1을 포함해야 합니다.')
    if not isinstance(r['rating_weights'],dict) or set(r['rating_weights'])!=set(DEFAULTS['rating_weights']):raise ValueError('포지션 비중 키 오류')
    for x in r['rating_weights'].values():
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1:raise ValueError('평점 비중: 0 ~ 1')
    knots=r['soft_barrier']
    if not isinstance(knots,list) or not 2<=len(knots)<=30:raise ValueError('Soft Barrier 형식 오류')
    previous=0;weight=1.0
    for item in knots:
        if not isinstance(item,list) or len(item)!=2:raise ValueError('Soft Barrier는 [PA, 배율] 목록입니다.')
        pa,v=item
        if type(pa) is not int or not previous<pa<=200 or isinstance(v,bool) or not isinstance(v,(int,float)) or not 0<=v<=weight:raise ValueError('Soft Barrier는 PA 증가·배율 감소 순서여야 합니다.')
        previous=pa;weight=v
    if knots[0][0]!=1 or knots[-1]!=[200,0]:raise ValueError('Soft Barrier 양 끝은 [1, 배율], [200, 0]이어야 합니다.')
    previous=0
    if not isinstance(r['age_factors'],list) or not 2<=len(r['age_factors'])<=40:raise ValueError('나이 보정 형식 오류')
    for item in r['age_factors']:
        if not isinstance(item,list) or len(item)!=2:raise ValueError('나이 보정은 [나이, 배율] 목록입니다.')
        age,v=item
        if type(age) is not int or not previous<age<=65 or not isinstance(v,(int,float)) or not 0<=v<=2:raise ValueError('나이 보정 범위 오류')
        previous=age
    if r['age_factors'][0][0]!=14 or r['age_factors'][-1][0]!=65:raise ValueError('나이 보정은 14~65세 범위가 필요합니다.')
    if not isinstance(r['peak_windows'],dict) or set(r['peak_windows'])!=set(DEFAULTS['peak_windows']):raise ValueError('포지션별 전성기 형식 오류')
    for window in r['peak_windows'].values():
        if not isinstance(window,list) or len(window)!=2 or any(type(x) is not int for x in window) or not 18<=window[0]<window[1]<=45:raise ValueError('전성기는 18~45세 사이의 시작·끝 나이로 입력하세요.')
    return r

def rules_id(r):return hashlib.sha256(json.dumps(validate(r),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]

def load(path):
    if not path.exists():return deepcopy(DEFAULTS)
    value=json.loads(path.read_text(encoding='utf-8'))
    # Only newly introduced optional settings are filled. Existing choices stay intact.
    if isinstance(value,dict):
        for key in ('rare_setbacks','team_rating_weight','team_rating_cap','advanced_weight','advanced_cap','youth_rare_setbacks'):
            if key not in value:value[key]=DEFAULTS[key]
    return validate(value)

def team_context(players,totals):
    teams=defaultdict(list);leagues=defaultdict(list)
    for p in players:
        s=totals.get(p.uid)
        if not s or not s.get('quality') or s.get('minutes',0)<900 or s.get('rated',0)<10:continue
        league=s.get('league');team=s.get('season_team');rating=s['rating_sum']/10/s['rated']
        if not league or not 1<=rating<=10:continue
        leagues[league].append(rating)
        if team is not None:teams[(league,team)].append((p.uid,rating))
    output={}
    for p in players:
        s=totals.get(p.uid)
        if not s:continue
        league=s.get('league');team=s.get('season_team');peers=[r for uid,r in teams.get((league,team),[]) if uid!=p.uid]
        if team is None or len(peers)<8 or len(leagues[league])<40:continue
        output[p.uid]=dict(team_peer_rating=sum(peers)/len(peers),team_peer_sample=len(peers),
                           league_peer_rating=sum(leagues[league])/len(leagues[league]))
    return output

def rankings(players,totals,today,min_peers,shrink_small=True,rules=None):
    from .transfer_evaluation import segments,rank_segments
    if any(s.get('context_v090') or len({part['league'] for part in segments(s)})>1 for s in totals.values()):
        return rank_segments(players,totals,today,min_peers,shrink_small,validate(rules or DEFAULTS))
    return single_rankings(players,totals,today,min_peers,shrink_small,rules)

def single_rankings(players,totals,today,min_peers,shrink_small=True,rules=None):
    r=validate(rules or DEFAULTS);groups=defaultdict(list);team_values=team_context(players,totals)
    for p in players:
        s=totals.get(p.uid)
        if not s or not s.get('quality'):continue
        age=p.age(date.fromisoformat(s.get('ability_as_of',str(today))))
        required=participation(age,r)
        if s['minutes']<min(required['growth_minutes_required'],required['decline_minutes_required']) or s['rated']<min(required['growth_rated_required'],required['decline_rated_required']):continue
        if not 1<=p.ca<=p.pa<=200 or not 14<=age<=65:continue
        s.update(required)
        league=s.get('league',0);rating=s['rating_sum']/10/s['rated']
        if not league or not 1<=rating<=10:continue
        team=team_values.get(p.uid);correction=0
        if team:correction=max(-r['team_rating_cap'],min(r['team_rating_cap'],(team['league_peer_rating']-team['team_peer_rating'])*r['team_rating_weight']))
        adjusted=max(1,min(10,rating+correction))
        s.update(raw_rating=rating,team_rating_adjustment=correction,team_comparison_available=bool(team),
                 team_peer_rating=team['team_peer_rating'] if team else None,team_peer_sample=team['team_peer_sample'] if team else 0)
        production=max(0,s['goals']-s.get('penalties',0))+s['assists']
        groups[(league,p.position)].append((p,s,adjusted,production*90/s['minutes'],production))
    output={}
    for (_,position),rows in groups.items():
        if len(rows)<min_peers[position]:continue
        ratings=sorted(x[2] for x in rows);rates=sorted(x[3] for x in rows);totals_sorted=sorted(x[4] for x in rows);ca=median(x[0].ca for x in rows)
        from .scouting_metrics import distributions,adjust
        detailed=distributions([row[1] for row in rows],min_peers[position])
        for p,s,rating,rate,total in rows:
            rw=r['rating_weights'][position]
            pct=rw*percentile(ratings,rating)+(1-rw)*(.5*percentile(rates,rate)+.5*percentile(totals_sorted,total))
            adjustment=max(-r['ca_adjustment_cap'],min(r['ca_adjustment_cap'],(ca-p.ca)*r['ca_adjustment']))
            # Present-day CA proxy, never presented as historical CA.
            base_pct=max(0,min(100,pct+adjustment));pct=adjust(s,position,base_pct,detailed,r)
            if shrink_small and len(rows)<20:
                pct=50+(pct-50)*math.sqrt(len(rows)/20);base_pct=50+(base_pct-50)*math.sqrt(len(rows)/20)
            s.update(base_percentile=base_pct,advanced_adjustment=pct-base_pct)
            s.update(ca_peer_median=ca,ca_percentile_adjustment=adjustment,rating_weight=rw,goals_assists_per90=rate,goals_assists_total=total)
            output[p.uid]=(p,s,rating,pct,len(rows))
    return output
