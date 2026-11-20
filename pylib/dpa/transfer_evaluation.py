# 출처: FM24 Dynamic PA v0.9.5 app/transfer_evaluation.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Compare each league separately, then combine one player's evidence by minutes.

Segment counts remain additive and annualized exactly once. Participation gates
apply to the whole period. A short stint is a query against established peers,
not an extra peer or an independent PA award. Unknown comparison data is neutral.
"""
from collections import defaultdict
from datetime import date
from statistics import median
import math

COUNTS=('minutes','rated','rating_sum','starts','subs','goals','assists','penalties')

def segments(s):
    if s.get('segments') is not None:return s['segments']
    return [dict(**{k:s.get(k,0) for k in COUNTS},league=s.get('league',0),
                 season_team=s.get('season_team'),season_year=s.get('season_year'),position=s.get('position'))]

def league_totals(s):
    groups={}
    for part in segments(s):
        key=part.get('league',0)
        if not key:continue
        if key not in groups:groups[key]=dict.fromkeys(COUNTS,0);groups[key].update(league=key,teams=set(),years=set())
        g=groups[key]
        for name in COUNTS:g[name]+=part.get(name,0)
        g.setdefault('_parts',[]).append(part)
        g['teams'].add(part.get('season_team'))
        if isinstance(part.get('season_year'),int):g['years'].add(part['season_year'])
    for g in groups.values():
        from .scouting_metrics import combine
        g['advanced']=combine(g.pop('_parts'))
        g['season_team']=next(iter(g['teams'])) if len(g['teams'])==1 else None
        period_years=s.get('normalization_years',1) or 1
        g['league_years']=len(g['years']) or period_years
        g['comparison_factor']=period_years/g['league_years']
    return groups

def rank_segments(players,totals,today,min_peers,shrink_small,rules):
    from .rules import participation,team_context
    from .model import percentile
    from .league_strength import profiles,neutral,adjustment_factor
    from dataclasses import replace

    # All readable players contribute their actual per-league stints to the
    # comparison pool. Missing total-period evidence never becomes a PA penalty.
    context={};pool=defaultdict(list);requirements={};valid={}
    for p in players:
        s=totals.get(p.uid)
        if not s or not s.get('quality'):continue
        age=p.age(date.fromisoformat(s.get('ability_as_of',str(today))))
        if not 1<=p.ca<=p.pa<=200 or not 14<=age<=65:continue
        required=participation(age,rules);requirements[p.uid]=required
        if s.get('minutes',0)<min(required['growth_minutes_required'],required['decline_minutes_required']) or s.get('rated',0)<min(required['growth_rated_required'],required['decline_rated_required']):continue
        valid[p.uid]=p
        for league,part in league_totals(s).items():
            if part['minutes']<=0:continue
            rating=part['rating_sum']/10/part['rated'] if part['rated'] else None
            if rating is not None and not 1<=rating<=10:continue
            # A full season in each of three leagues is not three short spells:
            # compare each league over its own active seasons, but combine with
            # its share of the whole interval's minutes.
            item=dict(s,**{k:part[k]*part['comparison_factor'] for k in COUNTS},
                      league=league,season_team=part['season_team'],weight_minutes=part['minutes'],
                      league_years=part['league_years'])
            from .scouting_metrics import scaled
            item['advanced']=scaled(part.get('advanced',{}),part['comparison_factor'])
            item.pop('segments',None);item.pop('combined_league_profile',None);item.pop('segment_evaluation',None)
            context[(p.uid,league)]=item;pool[league].append(replace(p,league=league))

    # Per-league team correction. Multiple clubs in a league have no single
    # team comparison; their league performance is still retained.
    teams={}
    for league,people in pool.items():
        part_totals={p.uid:context[p.uid,league] for p in people}
        for uid,value in team_context(people,part_totals).items():teams[uid,league]=value
    cohorts=defaultdict(list)
    for (uid,league),part in context.items():
        p=valid[uid];required=requirements[uid]
        raw=part['rating_sum']/10/part['rated'] if part['rated'] else None;team=teams.get((uid,league));correction=0
        if team:correction=max(-rules['team_rating_cap'],min(rules['team_rating_cap'],(team['league_peer_rating']-team['team_peer_rating'])*rules['team_rating_weight']))
        adjusted=max(1,min(10,raw+correction)) if raw is not None else None;production=max(0,part['goals']-part['penalties'])+part['assists']
        part.update(raw_rating=raw,adjusted_rating=adjusted,team_rating_adjustment=correction,
                    team_comparison_available=bool(team),team_peer_rating=team['team_peer_rating'] if team else None,
                    team_peer_sample=team['team_peer_sample'] if team else 0,production=production,rate=production*90/part['minutes'])
        if part['minutes']>=min(required['growth_minutes_required'],required['decline_minutes_required']) and part['rated']>=min(required['growth_rated_required'],required['decline_rated_required']):
            cohorts[league,p.position].append((p,part))
    # Cached distributions avoid re-sorting a league for every transfer player.
    distributions={}
    for key,rows in cohorts.items():
        distributions[key]=(sorted(s['adjusted_rating'] for _,s in rows),sorted(s['rate'] for _,s in rows),
                            sorted(s['production'] for _,s in rows),median(p.ca for p,_ in rows),len(rows))
    from .scouting_metrics import distributions as metric_distributions,adjust
    detailed={key:metric_distributions([s for _,s in rows],min_peers[key[1]]) for key,rows in cohorts.items()}
    strength=profiles(players,totals);output={}
    for uid,p in valid.items():
        s=totals[uid];parts=[(league,context[uid,league]) for league in sorted(league_totals(s)) if (uid,league) in context]
        total_minutes=s['minutes'];known_minutes=sum(part['weight_minutes'] for _,part in parts)
        if known_minutes<=0:continue
        # Records with missing/invalid rated stints are not silently dropped or
        # allowed to inflate the weights of the remaining stints.
        if not math.isclose(known_minutes,total_minutes,rel_tol=1e-9,abs_tol=1e-6):continue
        details=[];pct_sum=correction_sum=ca_sum=ca_adjust=0.0
        profile_sum={k:0.0 for k in ('league_strength_index','league_growth_weight','league_decline_weight','poor_rating_limit','adaptation')}
        mean_sum=0.0;all_mean=True;all_team=True;peer_rating_sum=0.0;samples=[];team_samples=[];compared=0.0
        for league,part in parts:
            weight=part['weight_minutes']/total_minutes;dist=distributions.get((league,p.position));peers=dist[4] if dist else 0
            rw=rules['rating_weights'][p.position];pct=50.0;base_pct=50.0;adjustment=0.0;center=None;reliability=0.0
            if dist and peers>=min_peers[p.position] and part['rated']>0:
                ratings,rates,production,center,_=dist
                adjustment=max(-rules['ca_adjustment_cap'],min(rules['ca_adjustment_cap'],(center-p.ca)*rules['ca_adjustment']))
                pct=rw*percentile(ratings,part['adjusted_rating'])+(1-rw)*(.5*percentile(rates,part['rate'])+.5*percentile(production,part['production']))
                base_pct=max(0,min(100,pct+adjustment))
                pct=adjust(part,p.position,base_pct,detailed.get((league,p.position),{}),rules)
                if shrink_small and peers<20:
                    pct=50+(pct-50)*math.sqrt(peers/20);base_pct=50+(base_pct-50)*math.sqrt(peers/20)
                req=requirements[uid]
                reliability=min(1,part['minutes']/min(req['growth_minutes_required'],req['decline_minutes_required']),part['rated']/min(req['growth_rated_required'],req['decline_rated_required']))
                pct=50+(pct-50)*reliability;base_pct=50+(base_pct-50)*reliability;compared+=weight
            profile=dict(strength.get((s.get('source_kind','observed_july_window'),league),neutral()))
            index=profile['league_strength_index']
            profile['league_growth_weight']=1+index*((rules['league_growth_max']-1) if index>=0 else (1-rules['league_growth_min']))
            profile['poor_rating_limit']=rules['poor_rating']-.12*max(0,index)
            profile['adaptation']=adjustment_factor(p,s.get('talent_age',p.age(today)),profile)
            for name in profile_sum:profile_sum[name]+=weight*profile[name]
            if profile['league_mean_ca'] is None:all_mean=False
            else:mean_sum+=weight*profile['league_mean_ca']
            pct_sum+=weight*pct;correction_sum+=weight*part['team_rating_adjustment']
            ca_sum+=weight*(center if center is not None else p.ca);ca_adjust+=weight*adjustment
            samples.append(peers)
            if part['team_comparison_available']:
                peer_rating_sum+=weight*part['team_peer_rating'];team_samples.append(part['team_peer_sample'])
            else:all_team=False
            details.append(dict(league=league,minutes=part['weight_minutes'],comparison_minutes=part['minutes'],
                                league_seasons=part['league_years'],rated=part['rated'],weight=weight,
                                percentile=pct,cohort_size=peers,short_stint_reliability=reliability,
                                league_mean_ca=profile['league_mean_ca'],league_sample=profile['league_sample'],
                                league_growth_weight=profile['league_growth_weight'],league_decline_weight=profile['league_decline_weight'],
                                advanced_adjustment=pct-base_pct,advanced_used=part.get('advanced_used',[])))
        # Keep standard non-transfer eligibility: an unsupported ordinary cohort
        # remains omitted. Transfers stay visible, with neutral unsupported legs.
        if len(parts)==1 and samples[0]<min_peers[p.position]:continue
        from .scouting_metrics import features
        s.update(advanced_adjustment=sum(d['weight']*d.get('advanced_adjustment',0) for d in details),
                 advanced_metric_count=len({m['metric'] for d in details for m in d.get('advanced_used',[])}),
                 advanced_used=[dict(m,league=d['league']) for d in details for m in d.get('advanced_used',[])],
                 advanced_features={k:round(v,4) for k,v in features(s).items()})
        s['advanced_status']='상세 기록 반영' if s['advanced_metric_count'] else '기본 기록 평가 · 상세 자료 부족'
        s['base_percentile']=pct_sum-s['advanced_adjustment']
        s.update(requirements[uid]);production=max(0,s['goals']-s.get('penalties',0))+s['assists']
        s.update(raw_rating=s['rating_sum']/10/s['rated'],team_rating_adjustment=correction_sum,
                 team_comparison_available=all_team,team_peer_rating=peer_rating_sum if all_team else None,
                 team_peer_sample=min(team_samples) if all_team else 0,ca_peer_median=ca_sum,
                 ca_percentile_adjustment=ca_adjust,rating_weight=rules['rating_weights'][p.position],
                 goals_assists_per90=production*90/s['minutes'],goals_assists_total=production,
                 segment_evaluation=True,league_count=len(parts),segment_count=len(segments(s)),
                 transfer_included=len(parts)>1 or s.get('transfer_included',False),
                 comparison_coverage=compared,league_breakdown=details,
                 combined_league_profile={**{k:v for k,v in profile_sum.items() if k!='adaptation'},
                    'league_mean_ca':mean_sum if all_mean else None,'league_sample':min(d['league_sample'] for d in details),
                    'strength_source':'minutes_weighted_per_league_CA_profiles'},
                 combined_adaptation=profile_sum['adaptation'])
        output[uid]=(p,s,max(1,min(10,s['raw_rating']+correction_sum)),pct_sum,min(samples))
    return output
