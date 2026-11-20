# 출처: FM24 Dynamic PA v0.9.5 app/model_v07.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Auditable gameplay model. Parameters are design choices, not empirical forecasts."""
from datetime import date
import math
import hashlib
from .rules import rankings,validate,DEFAULTS,rules_id
from .league_strength import profiles,for_player,adjustment_factor

MODEL_VERSION='0.9.4-development-balance'
NET_GROWTH_BUDGET=.25
WEIGHTS=(.6,.3,.1)
MIN_PEERS={'GK':8,'CB':12,'FB':12,'DM':12,'CM':12,'AM':12,'W':12,'ST':12}
PEAK_WINDOWS={'GK':(29,33),'CB':(27,31),'FB':(24,28),'DM':(27,31),
              'CM':(26,30),'AM':(25,29),'W':(23,27),'ST':(26,30)}
CAP_KNOTS=((14,16,10),(18,16,10),(21,12,8),(24,9,6),(29,6,5),(35,3,4),(60,1,2))
RARE_KNOTS=((14,20,30),(18,20,30),(21,16,24),(25,8,14),(29,4,8),(33,2,4),(37,0,0))

def interpolate(age,knots,column=1):
    if age<=knots[0][0]:return knots[0][column]
    for a,b in zip(knots,knots[1:]):
        if age<=b[0]:return a[column]+(b[column]-a[column])*(age-a[0])/(b[0]-a[0])
    return knots[-1][column]

def age_factor(age,position,rules=None):
    rules=rules or DEFAULTS;start,end=rules['peak_windows'][position]
    effective=start if start<=age<=end else age
    return interpolate(effective,rules['age_factors'])*interpolate(age,((14,1),(end,1),(end+4,.65),(end+8,.35),(65,.2)))

def high_pa_factor(pa,knots=None):
    return interpolate(pa,knots or DEFAULTS['soft_barrier'])

def headroom_factor(ca,pa):
    return interpolate(max(0,pa-ca),((0,1),(15,1),(35,.65),(70,.25),(199,.15)))

def talent(p,age,s,pct):
    # No unverified attribute offsets: known position, CA, observed CA trend,
    # performance and optional Flair. These are evidence proxies, not genes.
    ability_age=s.get('talent_age',age)
    center=sum(PEAK_WINDOWS[p.position])/2
    expected=60+7*(max(14,min(24,ability_age))-14)-max(0,center-27)*2
    ability=s.get('ca_end') if s.get('ca_end') is not None else p.ca
    early=max(0,min(1,(ability-expected)/60))
    change=s.get('ca_growth')
    growth=None if change is None else max(0,min(1,change/12))
    creative=p.position in ('ST','AM','W','CM')
    role=max(0,min(1,(pct-50)/50))
    if creative and p.flair is not None:role=max(0,min(1,(p.flair-10)/10))
    numerator=.55*early+.10*role;denominator=.65
    if growth is not None:numerator+=.35*growth;denominator+=.35
    return numerator/denominator,change

def draw(context,due,p,label):
    # Keep event draws stable across the median-to-mean league change.
    data=f'0.7.0-configurable-seasons|{context}|{due.isoformat()}|{p.uid}|{p.dob}|{label}'
    return int.from_bytes(hashlib.sha256(data.encode()).digest()[:8],'big')/2**64

def breakout_probability(age,pct,minutes,pers,talent_score,pa,coverage,knots=None,minimum_minutes=1800,minimum_percentile=85):
    if pct<minimum_percentile or minutes<minimum_minutes or coverage<.995:return 0.0
    age_weight=interpolate(age,((14,1),(21,1),(25,.45),(29,.12),(33,.03),(37,0)))
    base=min(.12,.03+.05*talent_score+.025*(pct-85)/15+.015*(pers+1)/2)
    return base*age_weight*high_pa_factor(pa,knots)

def proposals(players,totals,due,history=None,seed_context='',rules=None):
    rules=validate(rules or DEFAULTS);rid=rules_id(rules);seed_context+='|'+rid
    history=history or {};result=[];league_profiles=profiles(players,totals)
    for uid,(p,s,r,pct,peers) in rankings(players,totals,due,min_peers=MIN_PEERS,shrink_small=True,rules=rules).items():
        prior=[h for h in history.get(uid,[]) if h.get('dob')==p.dob]
        prior_by_year={int(h['year']):h for h in prior}
        observations=[(WEIGHTS[0],pct)]
        for back,weight in ((1,.3),(2,.1)):
            if due.year-back in prior_by_year:
                observations.append((weight,prior_by_year[due.year-back]['percentile']))
        weighted=sum(w*v for w,v in observations)/sum(w for w,_ in observations)
        score=(weighted-50)/50
        score=math.copysign(max(0,abs(score)-.15)/.85,score)
        base_pct=s.get('base_percentile',pct)
        base_weighted=(sum(w*v for w,v in observations)-WEIGHTS[0]*pct+WEIGHTS[0]*base_pct)/sum(w for w,_ in observations)
        base_score=(base_weighted-50)/50
        base_score=math.copysign(max(0,abs(base_score)-.15)/.85,base_score)
        coverage=max(0,min(1,s.get('season_confidence',0) if s.get('coverage') is None else s.get('coverage',0)))
        coverage*=s.get('comparison_coverage',1)
        confidence=min(1,s['minutes']/2400)*coverage
        pers=(.5*p.professionalism+.25*p.ambition+.2*p.determination+.05*p.work_rate-10.5)/9.5
        age=p.age(date.fromisoformat(s.get('ability_as_of',str(due))));t,ca_growth=talent(p,age,s,pct)
        from .scouting_metrics import development
        stage,maturity=development(age,p.position,ca_growth)
        context_known=not s.get('context_v090') or s.get('competition_class_known',False)
        rare_minutes=1200 if age<=21 else 1800
        rare_percentile=90 if age<=21 else 85
        cap_up=min(rules['normal_growth_cap'],interpolate(age,CAP_KNOTS,1));cap_down=min(rules['normal_decline_cap'],interpolate(age,CAP_KNOTS,2))
        league=for_player(p,s,league_profiles)
        strength=league['league_strength_index']
        if not s.get('segment_evaluation'):
            league['league_growth_weight']=1+strength*((rules['league_growth_max']-1) if strength>=0 else (1-rules['league_growth_min']))
            league['poor_rating_limit']=rules['poor_rating']-.12*max(0,strength)
        adaptation=s['combined_adaptation'] if s.get('segment_evaluation') else adjustment_factor(p,s.get('talent_age',age),league)
        team_poor=not s['team_comparison_available'] or s['raw_rating']<s['team_peer_rating']-.1
        poor=s['minutes']>=s['decline_minutes_required'] and s['rated']>=s['decline_rated_required'] and s['raw_rating']<league['poor_rating_limit'] and base_pct<rules['poor_percentile'] and team_poor
        prior_poor=sum(bool(prior_by_year.get(due.year-back,{}).get('poor')) for back in (1,2))
        repeated_poor=poor and prior_poor>=1
        reasons=[]
        if not context_known:reasons.append('competition_class_unknown_no_extremes')
        if s.get('advanced_metric_count',0):reasons.append('position_metrics_used')
        if s.get('transfer_included'):reasons.append('transfer_minutes_weighted')
        if s.get('comparison_coverage',1)<.995:reasons.append('transfer_comparison_incomplete')
        def ordinary(current_pct,current_score,talent_score):
            local_reasons=[]
            if current_score>0:
                # Minutes/percentile weighting is continuous after the common
                # 900-minute/10-rated-game reliability gate in rankings().
                evidence=min(1,max(0,(current_pct-55)/25))
                raw=cap_up*current_score*confidence*age_factor(age,p.position,rules)*(1+.15*pers)
                raw*=high_pa_factor(p.pa,rules['soft_barrier'])*headroom_factor(p.ca,p.pa)*(1+.2*talent_score)*evidence*league['league_growth_weight']
            else:
                raw=cap_down*current_score*confidence*(1-.25*pers)*league['league_decline_weight']*adaptation
                if not poor or coverage<.995:
                    raw=0;local_reasons.append('decline_not_supported')
                elif not repeated_poor:
                    raw=max(-1 if age<=21 else -2,raw);local_reasons.append('first_poor_period_limited')
            if current_score>0 and (s['minutes']<s['growth_minutes_required'] or s['rated']<s['growth_rated_required'] or base_pct<rules['growth_percentile']):raw=0;local_reasons.append('growth_gate_not_met')
            if poor and prior_poor>=2 and coverage>=.995:raw-=rules['three_poor_extra'];local_reasons.append('three_poor_seasons')
            return raw,local_reasons
        raw,ordinary_reasons=ordinary(pct,score,t);reasons.extend(ordinary_reasons)
        base_t,_=talent(p,age,s,base_pct)
        base_raw,_=ordinary(base_pct,base_score,base_t)
        performance_raw=raw
        delta=int(math.copysign(math.floor(abs(raw)+.5),raw))
        delta=max(-round(cap_down),min(round(cap_up),delta))
        rare_pct=base_pct
        base_delta=max(-round(cap_down),min(round(cap_up),int(math.copysign(math.floor(abs(base_raw)+.5),base_raw))))
        detailed_delta=max(base_delta-2,min(base_delta+2,delta))
        if detailed_delta!=delta:reasons.append('detailed_pa_limit')
        delta=detailed_delta
        advanced_pa_adjustment=delta-base_delta
        event='normal';probability=min(.12,breakout_probability(age,rare_pct,s['minutes'],pers,base_t,p.pa,coverage,rules['soft_barrier'],rare_minutes,rare_percentile)*league['league_growth_weight']*maturity) if context_known else 0
        if rules['rare_events'] and s['minutes']>=max(rare_minutes,s['growth_minutes_required']) and s['rated']>=max(10,s['growth_rated_required']) and base_pct>=rules['growth_percentile'] and probability and draw(seed_context,due,p,'event')<probability:
            lo=interpolate(age,RARE_KNOTS,1);hi=interpolate(age,RARE_KNOTS,2)
            magnitude=lo+(hi-lo)*draw(seed_context,due,p,'magnitude')
            rare=round(magnitude*high_pa_factor(p.pa,rules['soft_barrier'])*max(.4,headroom_factor(p.ca,p.pa)))
            delta=max(delta,rare);event='breakout' if rare>0 else 'normal'
        elif context_known and ((rules['rare_setbacks'] and age>21) or (rules['youth_rare_setbacks'] and age<=21)) and repeated_poor and coverage>=.995 and base_pct<=10:
            probability=(.015+.025*(1-pers)/2+.015*(10-base_pct)/10)*interpolate(age,((14,1),(21,1),(25,.45),(29,.12),(35,0)))*min(1,league['league_decline_weight']*adaptation)
            if draw(seed_context,due,p,'setback')<probability:
                delta=-round(interpolate(age,((14,12),(18,12),(21,10),(25,6),(29,3),(35,0)))
                            *(1+.5*draw(seed_context,due,p,'magnitude'))*min(1,league['league_decline_weight']*adaptation))
                event='setback'
        if coverage<.995:reasons.append('limited_coverage_no_decline_or_rare_event')
        if s['minutes']<rules['growth_minutes'] and delta>0 and event!='breakout':
            delta=min(delta,3);reasons.append('short_minutes_growth_limited')
        if not context_known and event!='normal':raise AssertionError('Unclassified competition cannot trigger extreme events')
        from .development_balance import adjust as adjust_development
        delta,development_info=adjust_development(p,s,date.fromisoformat(s.get('ability_as_of',str(due))),
            age,base_pct,repeated_poor,coverage,delta,rules,cap_down)
        if development_info['development_extra_decline']:
            reasons.append('growth_stagnation' if development_info['stagnation_requested'] else 'aging_ca_decline')
        new=max(p.ca,min(200,p.pa+delta))
        result.append(dict(advanced_pa_adjustment=advanced_pa_adjustment,development_stage=stage,development_factor=maturity,performance_raw=round(performance_raw,4),
            **development_info,
            normal_up_limit=round(cap_up,2),normal_down_limit=round(cap_down,2),pa_growth_factor=round(high_pa_factor(p.pa,rules['soft_barrier']),4),headroom_growth_factor=round(headroom_factor(p.ca,p.pa),4),
            **{k:s.get(k) for k in ('current_team','current_league','current_league_country','nationality','evaluated_team','evaluated_league','league_country','competition_class','competition_classes','competition_class_known','evaluated_team_ids','evaluated_teams','evaluated_leagues','evaluated_countries','advanced_adjustment','advanced_metric_count','advanced_status','advanced_features','advanced_used')},
            uid=uid,dob=p.dob,name=p.name,old=p.pa,new=new,percentile=round(pct,3),
            **{k:s.get(k) for k in ('normalization_years','normalization_factor','observed_minutes','observed_rated','observed_goals','observed_assists','evidence_period_start','evidence_period_end','league_count','segment_count','transfer_included','comparison_coverage','league_breakdown')},
            minutes=s['minutes'],rating=round(s['raw_rating'],2),adjusted_rating=round(r,3),position=p.position,age=age,cohort_size=peers,
            **{k:s[k] for k in ('growth_minutes_required','decline_minutes_required','growth_rated_required','decline_rated_required')},
            event=event,event_probability=round(probability,5),requested_delta=delta,talent_evidence=round(t,4),
            flair=p.flair,model_version=MODEL_VERSION,evaluation_reason=';'.join(reasons) or 'performance',
            weighted_percentile=round(weighted,3),history_periods=len(observations),poor=poor,
            repeated_poor=repeated_poor,ca_growth=ca_growth,headroom=p.pa-p.ca,coverage=None if s.get('coverage') is None else round(coverage,5),
            evidence_confidence=round(coverage,5),source_kind=s.get('source_kind','observed_july_window'),
            season_year=s.get('season_year'),exact_july_window=s.get('exact_july_window',True),
            ability_as_of=s.get('ability_as_of'),historical_ca_available=s.get('historical_ca_available',True),
            ruleset_id=rid,ca=p.ca,ca_peer_median=s.get('ca_peer_median'),ca_percentile_adjustment=s.get('ca_percentile_adjustment'),rating_weight=s.get('rating_weight'),goals=s['goals'],assists=s['assists'],goals_assists_per90=s.get('goals_assists_per90'),injury_adjustment=None,injury_data_available=False,team_comparison_available=s['team_comparison_available'],team_peer_rating=s['team_peer_rating'],team_peer_sample=s['team_peer_sample'],team_rating_adjustment=s['team_rating_adjustment'],ca_trend_source=s.get('ca_trend_source'),ca_baseline_date=s.get('ca_baseline_date'),ca_trend_days=s.get('ca_trend_days'),competition_scope='league_only',budget_reduction=0,adaptation_decline_weight=round(adaptation,4),**league))
    # Include rare events. Never manufacture negative changes to fund growth.
    positive=sum(max(0,x['new']-x['old']) for x in result)
    # New stagnation/aging deductions cannot fund extra growth for other players.
    negative=sum(max(0,x['old']-x['new']-x['development_extra_decline']) for x in result)
    budget=negative+math.floor(rules['net_growth_budget']*len(result))
    if positive>budget:
        gains=[(x,(x['new']-x['old'])*budget/positive,x['new']) for x in result if x['new']>x['old']]
        for x,amount,_ in gains:x['new']=x['old']+math.floor(amount)
        left=budget-sum(x['new']-x['old'] for x,_,_ in gains)
        for x,_,_ in sorted(gains,key=lambda v:(-(v[1]%1),v[0]['uid']))[:left]:x['new']+=1
        for x,_,original in gains:x['budget_reduction']=original-x['new']
    return sorted(result,key=lambda x:x['uid'])
