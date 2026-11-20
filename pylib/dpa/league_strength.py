# 출처: FM24 Dynamic PA v0.9.5 app/league_strength.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Transparent CA-based league proxy; no claimed SI reputation formula."""
from collections import defaultdict
from statistics import fmean

def profiles(players,totals):
    groups=defaultdict(list)
    for p in players:
        s=totals.get(p.uid)
        if not s or not s.get('quality'):continue
        ca=s.get('ca_end') if s.get('ca_end') is not None else p.ca
        if not 1<=ca<=200:continue
        from .transfer_evaluation import league_totals
        for part in league_totals(s).values():
            factor=part['comparison_factor']
            if part.get('minutes',0)*factor<900 or part.get('rated',0)*factor<10:continue
            key=(s.get('source_kind','observed_july_window'),part['league'])
            groups[key].append(ca)
    result={}
    for key,values in groups.items():
        if not key[1] or len(values)<40:continue
        center=fmean(values);index=max(-1,min(1,(center-110)/40))
        result[key]={'league_mean_ca':center,'league_sample':len(values),'league_strength_index':index,
                     'league_growth_weight':1+.20*index,'league_decline_weight':1-.25*index,
                     'poor_rating_limit':6.7-.12*max(0,index),
                     'strength_source':'arithmetic_mean_CA_of_season_regulars'}
    return result

def neutral():
    return {'league_mean_ca':None,'league_sample':0,'league_strength_index':0.0,
            'league_growth_weight':1.0,'league_decline_weight':1.0,'poor_rating_limit':6.7,
            'strength_source':'insufficient_data_neutral'}

def for_player(p,s,values):
    if s.get('segment_evaluation') and s.get('combined_league_profile'):
        return dict(s['combined_league_profile'])
    profile=values.get((s.get('source_kind','observed_july_window'),s.get('league',p.league)),neutral())
    return dict(profile)

def adjustment_factor(p,age,profile):
    center=profile['league_mean_ca']
    if age>23 or center is None or profile['league_strength_index']<=0:return 1.0
    return 1-.4*min(1,max(0,center-p.ca)/30)
