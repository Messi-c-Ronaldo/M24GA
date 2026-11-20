# 출처: FM24 Dynamic PA v0.9.5 app/model.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Original gameplay model; coefficients are proposed settings, not SI formulas."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from collections import defaultdict
from bisect import bisect_left, bisect_right
import math
import hashlib

MODEL_VERSION='0.3.1-performance-gates'
MIN_UP_MINUTES=1600
MIN_UP_PERCENTILE=70
POOR_RATING_LIMIT=6.7
# Inclusive age limits, normal annual up/down caps, rare up/down ranges.
AGE_BANDS=((18,16,10,(20,30),(12,20)),(21,12,8,(16,24),(10,16)),
           (24,9,6,None,None),(29,6,5,None,None),(65,3,4,None,None))

def age_band(age):
    return next(b for b in AGE_BANDS if age<=b[0])

def stable_draw(context,today,p,label):
    payload=f'{MODEL_VERSION}|{context}|{today.year}|{p.uid}|{p.dob}|{label}'
    return int.from_bytes(hashlib.sha256(payload.encode('utf-8')).digest()[:8],'big')/2**64

COUNTERS = ('minutes','rated','rating_sum','starts','subs','goals','assists',
            'penalties','key_passes','tackles','interceptions','headers','saves_proxy')
PEAKS = {'GK':31,'CB':29,'FB':26,'DM':29,'CM':28,'AM':27,'W':27,'ST':28}

@dataclass
class Player:
    uid: int
    name: str
    dob: str
    position: str
    ca: int
    pa: int
    league: int
    professionalism: float
    ambition: float
    determination: float
    work_rate: float
    stats: dict = field(default_factory=dict)
    address: int = 0
    flair: float | None = None
    context: dict = field(default_factory=dict)

    def age(self, today):
        born = date.fromisoformat(self.dob)
        return today.year-born.year-((today.month,today.day)<(born.month,born.day))

def decode_date(raw):
    year, day = raw >> 16, raw & 0x1ff
    if not 1900 <= year <= 2300 or not 1 <= day <= 366:
        raise ValueError('Invalid FM date')
    result = date(year,1,1)+timedelta(days=day-1)
    if result.year != year:
        raise ValueError('Invalid leap day')
    return result

def season_start(d, month=7, day=1):
    anchor=date(d.year,month,day)
    return anchor if d>=anchor else date(d.year-1,month,day)

def age_factor(age,pos):
    peak=PEAKS[pos]
    points=[(14,1),(20,1.15),(peak-3,.85),(peak,.55),(peak+4,.15),(peak+8,0)]
    if age<=14:return 1.0
    for (a,x),(b,y) in zip(points,points[1:]):
        if age<=b:return x+(y-x)*(age-a)/(b-a)
    return 0.0

def counter_delta(old,new):
    """Only observed changes. A reset starts a new counter segment."""
    if any(k not in old or k not in new for k in COUNTERS):
        raise ValueError('Incomplete counters')
    reset=any(new[k]<old[k] for k in ('minutes','rated','rating_sum','starts','subs'))
    delta={k:(new[k] if reset else new[k]-old[k]) for k in COUNTERS}
    if any(v<0 for v in delta.values()):
        raise ValueError('Counters corrected or mixed; do not infer performance')
    return delta,reset

def percentile(sorted_values,x):
    return 100*(bisect_left(sorted_values,x)+bisect_right(sorted_values,x))/(2*len(sorted_values))

def talent_evidence(p,age):
    """A gameplay proxy, not an estimate of genetic talent or FM's hidden PA."""
    # Early established ability matters in every position. Flair is a smaller
    # optional bonus so low-flair defenders/GKs are not disqualified.
    expected=60+7*(max(14,min(24,age))-14)
    early=max(0,min(1,(p.ca-expected)/60))
    flair=0.0
    if p.flair is not None and math.isfinite(p.flair) and 1<=p.flair<=20:
        flair=max(0,(p.flair-10)/10)
    return .7*early+.3*flair

def event_chances(p,age,pct,minutes,pers):
    """No personality gate: high-performing, low-professionalism talents can break out."""
    talent=talent_evidence(p,age)
    if age>21:return talent,0.0,0.0
    up=0.0;down=0.0
    if pct>=85 and minutes>=1800:
        # 3..12% among qualifying players; performance and talent dominate.
        up=min(.12,.03+.05*talent+.025*(pct-85)/15+.015*(pers+1)/2)
    if pct<=15 and minutes>=900:
        down=min(.10,.02+.06*(1-pers)/2+.02*(15-pct)/15)
    return talent,up,down

def rankings(players, totals, today, min_peers=20, shrink_small=False):
    """totals keyed by UID, with observed counters, dominant league and quality flag."""
    cohorts=defaultdict(list)
    candidates={}
    for p in players:
        s=totals.get(p.uid)
        if not s or not s.get('quality',True) or s['minutes']<900 or s['rated']<10:
            continue
        if not (1<=p.ca<=p.pa<=200) or not 14<=p.age(today)<=60:
            continue
        if any(not math.isfinite(x) or not 1<=x<=20 for x in
               (p.professionalism,p.ambition,p.determination,p.work_rate)):
            continue
        league=s.get('league',p.league)
        if not league:continue
        rating=s['rating_sum']/10/s['rated']
        if not 1<=rating<=10:continue
        per90=90/s['minutes']
        if p.position=='ST': metric=(max(0,s['goals']-s['penalties'])+.6*s['assists'])*per90
        elif p.position in ('AM','W'):
            metric=(s['goals']+s['assists']+(.12*s['key_passes'] if s.get('advanced_available',True) else 0))*per90
        elif not s.get('advanced_available',True):metric=None
        elif p.position in ('CM','DM'):metric=(.15*s['key_passes']+.1*s['interceptions']+.05*s['tackles'])*per90
        elif p.position in ('CB','FB'):metric=(.1*s['interceptions']+.05*s['headers']+.05*s['tackles'])*per90
        else:metric=None # no unreliable GK save proxy; use rating within GK cohort
        c=(league,p.position,s.get('source_kind','observed_july_window'),s.get('advanced_available',True))
        candidates[p.uid]=(p,s,rating,metric,c)
        cohorts[c].append(p.uid)
    ranked={}
    for cohort,uids in cohorts.items():
        threshold=min_peers.get(cohort[1],12) if isinstance(min_peers,dict) else min_peers
        if len(uids)<threshold:continue
        ratings=sorted(candidates[u][2] for u in uids)
        metrics=sorted(candidates[u][3] for u in uids if candidates[u][3] is not None)
        abilities=sorted(candidates[u][0].ca for u in uids)
        median_ca=abilities[len(abilities)//2]
        for uid in uids:
            p,s,r,m,_=candidates[uid]
            pct=percentile(ratings,r)
            if m is not None:pct=.7*pct+.3*percentile(metrics,m)
            # A player far above their peers must outperform more to earn a higher ceiling.
            if s.get('historical_ca_available',True):
                pct=max(0,min(100,pct-max(0,p.ca-median_ca-10)*.6))
            if shrink_small and len(uids)<20:
                pct=50+(pct-50)*math.sqrt(len(uids)/20)
            ranked[uid]=(p,s,r,pct,len(uids))
    return ranked

def proposals(players, totals, today, previous=None, min_peers=20, seed_context=''):
    previous=previous or {};output=[]
    for uid,(p,s,r,pct,cohort_size) in rankings(players,totals,today,min_peers).items():
        previous_pct=previous.get(uid,50)
        score=.7*(pct-50)/50+.3*(previous_pct-50)/50
        score=math.copysign(max(0,abs(score)-.15)/.85,score)
        confidence=min(1,s['minutes']/1800)
        pers=(.5*p.professionalism+.25*p.ambition+.2*p.determination+.05*p.work_rate-10.5)/9.5
        age=p.age(today)
        talent,up_chance,down_chance=event_chances(p,age,pct,s['minutes'],pers)
        if r>=POOR_RATING_LIMIT:down_chance=0.0
        _,cap_up,cap_down,rare_up,rare_down=age_band(age)
        reason='performance'
        if score>0:
            highpa=1 if p.pa<170 else max(.2,(200-p.pa)/30)
            raw=cap_up*score*confidence*age_factor(age,p.position)*(1+.15*pers)*highpa*(1+.20*talent)
        else:
            raw=cap_down*score*confidence*(1-.25*pers)
        delta=int(math.copysign(math.floor(abs(raw)+.5),raw))
        if delta>0 and (s['minutes']<MIN_UP_MINUTES or pct<MIN_UP_PERCENTILE):
            delta=0;reason='growth_sample_or_percentile'
        elif delta<0 and r>=POOR_RATING_LIMIT:
            delta=0;reason='rating_protects_from_decline'
        delta=max(-cap_down,min(cap_up,delta));event='normal';probability=0.0
        # One reproducible draw per save/branch, year and identity. Re-running
        # or reordering the list never rerolls the outcome.
        if up_chance:
            probability=up_chance
            if stable_draw(seed_context,today,p,'event')<probability:
                lo,hi=rare_up
                delta=lo+int(stable_draw(seed_context,today,p,'magnitude')*(hi-lo+1));event='breakout'
        elif down_chance:
            probability=down_chance
            if stable_draw(seed_context,today,p,'event')<probability:
                lo,hi=rare_down
                delta=-(lo+int(stable_draw(seed_context,today,p,'magnitude')*(hi-lo+1)));event='setback'
        new=max(p.ca,min(200,p.pa+delta))
        output.append({'uid':uid,'dob':p.dob,'name':p.name,'old':p.pa,'new':new,
                       'percentile':round(pct,3),'minutes':s['minutes'],'rating':round(r,2),
                       'position':p.position,'age':age,'cohort_size':cohort_size,
                       'event':event,'event_probability':round(probability,4),
                       'requested_delta':delta,'model_version':MODEL_VERSION,
                       'talent_evidence':round(talent,4),'flair':p.flair,'evaluation_reason':reason})
    # Limit aggregate net growth, without raising any player's PA to compensate.
    regular=[r for r in output if r['event']=='normal']
    positive=sum(max(0,r['new']-r['old']) for r in regular)
    negative=sum(max(0,r['old']-r['new']) for r in regular)
    budget=negative+math.floor(.5*len(regular))
    if positive>budget:
        gains=[(r,(r['new']-r['old'])*budget/positive) for r in regular if r['new']>r['old']]
        for r,exact in gains:r['new']=r['old']+math.floor(exact)
        left=budget-sum(r['new']-r['old'] for r,_ in gains)
        for r,exact in sorted(gains,key=lambda t: (-(t[1]%1),t[0]['uid']))[:left]:r['new']+=1
    return sorted(output,key=lambda r:r['uid'])
