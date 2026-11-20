# 출처: FM24 Dynamic PA v0.9.5 app/development_balance.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Small, evidence-gated PA revisions; parameters are gameplay choices.

No inferred historical CA, extra process scan, or second memory-write path.
The sparse ledger charges only actually applied rows and follows their undo state.
"""
from datetime import date

AGING_CAP = 10


def init_ledger(db):
    db.execute('''CREATE TABLE IF NOT EXISTS development_adjustments(
        career TEXT,event TEXT,uid INTEGER,dob TEXT,charge INTEGER NOT NULL,
        PRIMARY KEY(event,uid))''')
    db.execute('CREATE INDEX IF NOT EXISTS development_career ON development_adjustments(career)')


def aging_usage(db,career,today):
    return {(uid,dob):total for uid,dob,total in db.execute('''
        SELECT d.uid,d.dob,sum(d.charge) FROM development_adjustments d
        JOIN proposals p ON p.event=d.event AND p.uid=d.uid
        JOIN events e ON e.id=d.event
        WHERE d.career=? AND e.due<=? AND p.status='applied'
          AND e.status NOT IN ('undone','superseded','skipped')
        GROUP BY d.uid,d.dob''',(career,str(today)))}


def inherit_ledger(db,career,source_event,event):
    db.execute('''INSERT OR IGNORE INTO development_adjustments
        SELECT ?,?,uid,dob,charge FROM development_adjustments WHERE event=?''',
        (career,event,source_event))


def record_ledger(db,career,event,rows):
    db.executemany('INSERT INTO development_adjustments VALUES(?,?,?,?,?)',
        ((career,event,r['uid'],r['dob'],r['aging_extra_decline']) for r in rows
         if r.get('aging_extra_decline',0)>0))


def observed_rates(player,stats,today):
    """Three identity-matched snapshots, two roughly annual nonoverlapping gaps."""
    points=stats.get('development_ca_points',[])
    if len(points)!=3:return None
    try:
        days=[date.fromisoformat(x['date']) for x in points]
        ca=[x['ca'] for x in points]
        if any(x.get('dob')!=player.dob for x in points):return None
        if any(type(v) is not int or not 1<=v<=200 for v in ca):return None
        if days[-1]!=today or ca[-1]!=player.ca:return None
        gaps=[(b-a).days for a,b in zip(days,days[1:])]
        if any(not 300<=gap<=550 for gap in gaps) or sum(gaps)<700:return None
        return [(b-a)*365/gap for a,b,gap in zip(ca,ca[1:],gaps)]
    except (KeyError,TypeError,ValueError):return None


def adjust(player,stats,today,age,base_percentile,repeated_poor,coverage,
           performance_delta,rules,normal_cap):
    rates=observed_rates(player,stats,today)
    used=max(0,int(stats.get('aging_used_before',0)))
    info=dict(development_ca_points=stats.get('development_ca_points',[]),
              development_ca_annual_rates=None if rates is None else [round(v,3) for v in rates],
              development_check='장기 CA 관측 부족',stagnation_requested=0,aging_requested=0,
              development_extra_decline=0,aging_extra_decline=0,aging_used_before=used)
    if rates is None:return performance_delta,info
    info['development_check']='추가 하락 조건 미충족'
    if (coverage<.995 or stats['minutes']<stats['decline_minutes_required']
            or stats['rated']<stats['decline_rated_required']):
        info['development_check']='성적·출전 근거 부족';return performance_delta,info
    headroom=player.pa-player.ca
    requested=0;kind=None
    # One decimal prevents a leap-day interval turning a one-point annual change
    # into a different eligibility decision.
    rounded_rates=[round(v,1) for v in rates]
    if 19<=age<=24 and repeated_poor and max(rounded_rates)<=1:
        minimum=15 if age<=21 else 10
        if headroom>=minimum:
            if age<=21:requested=1+int(headroom>=30)+int(headroom>=50 and max(rounded_rates)<=0)
            else:requested=min(5,2+(age-22)+int(headroom>=40))
            kind='stagnation'
    end=rules['peak_windows'][player.position][1]
    if age>=end+2 and max(rounded_rates)<=-1:
        first=date.fromisoformat(stats['development_ca_points'][0]['date'])
        if player.age(first)>=end:
            if base_percentile>=50 or stats['raw_rating']>=7:
                info['development_check']='좋은 활약 · 노화 감점 유예'
            elif used>=AGING_CAP:
                info['development_check']='노화 추가 감점 누적 한도 도달'
            else:
                requested=2 if max(rounded_rates)<=-3 else 1;kind='aging'
    if not kind:return performance_delta,info
    requested=min(requested,round(normal_cap))
    if requested<=0:
        info['development_check']='일반 하락 상한 설정으로 추가 감점 없음'
        return performance_delta,info
    # Use the stronger explanation, not their sum. Charge only extra PA actually
    # removed beyond the existing non-positive performance result and CA floor.
    baseline=max(player.ca,player.pa+min(0,performance_delta))
    target=max(player.ca,min(player.pa+performance_delta,player.pa-requested))
    if kind=='aging':target=max(target,baseline-max(0,AGING_CAP-used))
    extra=max(0,baseline-target)
    info[kind+'_requested']=-requested
    info['development_extra_decline']=extra
    if kind=='aging':info['aging_extra_decline']=extra
    info['development_check']=('유망주 성장 정체' if kind=='stagnation' else '전성기 이후 CA 하락')+(' · 추가 감점' if extra else ' · 기존 부진 감점에 포함')
    return target-player.pa,info
