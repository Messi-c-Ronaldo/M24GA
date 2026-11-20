# -*- coding: utf-8 -*-
"""게임에서 모은 선수 자료 -> Dynamic PA 모델(dpa/) 입력 -> 변화안 + 한국어 설명.

모델 계산은 dpa/(Dynamic PA 0.9.5, GPL-3.0)를 그대로 쓰고, 여기서는 입력을 원래와 같은 모양으로 만든다.
원래 프로그램과 다른 점 (P07 로그):
- 시즌 기록은 게임 메모리의 '리그' 블록 누적값 하나 (coverage 1.0). 원래 프로그램의 '현재 누적 기록' 방식과 같다.
- 상세 기록 검증에서 xG 초과 성과(+110) 관계 검사는 뺐다 (코어가 그 칸을 주지 않음). 나머지 관계·범위 검사는 같다.
- 과거 시즌 백분위·부진 여부·CA는 이 모드가 세이브별로 남긴 기록(history.json)에서 가져온다.
"""
import copy
import hashlib
import math
from datetime import date, timedelta

from dpa.model import Player
from dpa import model_v07, rules as dpa_rules

# 게임 포지션 15칸(GK SW DL DC DR DM ML MC MR AML AMC AMR ST WBL WBR) -> 모델 포지션 무리 (Dynamic PA fm24_profile.POSITIONS)
POS_GROUP = ('GK', 'CB', 'FB', 'CB', 'FB', 'DM', 'W', 'CM', 'W', 'W', 'AM', 'W', 'ST', 'FB', 'FB')
POS_KO = {'GK': '골키퍼', 'CB': '중앙 수비', 'FB': '측면 수비', 'DM': '수비형 미드', 'CM': '중앙 미드', 'AM': '공격형 미드', 'W': '윙어', 'ST': '스트라이커'}
DETAIL_FIELDS = ('passes_attempted', 'passes_completed', 'tackles_attempted', 'tackles_completed', 'headers_attempted', 'headers_won',
                 'dribbles', 'shots', 'shots_on_target', 'key_passes', 'interceptions', 'xg', 'xa', 'clearances',
                 'progressive_passes', 'pressures_attempted', 'pressures_completed', 'npxg', 'crosses_attempted', 'crosses_completed')
XG = {'xg', 'xa', 'npxg'}
LIMITS = {'passes_attempted': 200, 'passes_completed': 200, 'key_passes': 30, 'progressive_passes': 80, 'dribbles': 40,
          'tackles_attempted': 45, 'tackles_completed': 45, 'headers_attempted': 65, 'headers_won': 65, 'shots': 35,
          'shots_on_target': 35, 'interceptions': 45, 'crosses_attempted': 50, 'crosses_completed': 50, 'clearances': 50,
          'pressures_attempted': 180, 'pressures_completed': 180}
PAIRS = (('passes_attempted', 'passes_completed'), ('tackles_attempted', 'tackles_completed'), ('headers_attempted', 'headers_won'),
         ('shots', 'shots_on_target'), ('crosses_attempted', 'crosses_completed'), ('pressures_attempted', 'pressures_completed'))

REASON_KO = {
    'growth_gate_not_met': '오르기 조건(출전 시간·평점 경기 수·백분위 70) 미충족',
    'decline_not_supported': '부진 판정이 아니라 내리지 않음',
    'first_poor_period_limited': '첫 부진이라 하락 폭 제한',
    'three_poor_seasons': '3시즌 연속 부진 추가 하락',
    'short_minutes_growth_limited': '출전 1,600분 미만이라 상승 최대 +3',
    'detailed_pa_limit': '상세 기록 보정은 ±2까지',
    'growth_stagnation': '유망주 성장 정체',
    'aging_ca_decline': '전성기 이후 능력 하락',
    'limited_coverage_no_decline_or_rare_event': '기록이 부족해 하락·드문 사건 없음',
}


def decode_detail(raw, minutes, goals, position):
    """Dynamic PA scouting_metrics.decode와 같은 검사 (xG 초과 성과 검사만 뺌). raw = DETAIL_FIELDS 순서 정수"""
    if not raw or len(raw) != len(DETAIL_FIELDS) or minutes <= 0 or not any(raw) or position == 'GK':
        return {}
    v = dict(zip(DETAIL_FIELDS, raw))
    bad = set()
    for a, c in PAIRS:
        if v[c] > v[a]:
            bad.update((a, c))
    if v['npxg'] > v['xg'] or v['xg'] > v['shots'] * 100 + 1:
        bad.update(XG)
    for k, lim in LIMITS.items():
        if v[k] > lim * minutes / 90 + 10:
            bad.add(k)
    return {k: {'value': x / (100 if k in XG else 1), 'minutes': minutes} for k, x in v.items() if k not in bad}


COUNTER_KEYS = ('minutes', 'rated', 'rating_sum', 'starts', 'subs', 'goals', 'assists', 'penalties')


def build(rows, due, history, saved=None, cup_weight=0.0):
    """rows: mod.js가 보낸 선수 자료. history: {uid: {year: {...}}} -> (players, totals, model_history)
    saved: 직전 시즌이 끝나 보관된 리그(달력형)의 선수 기록 {uid: totals} - 있으면 반 시즌 대신 그 1년치로 평가 (개선안 2)
    cup_weight: 0~1. 대륙컵·국가대표 기록을 이 비율만큼 리그 기록에 더함 (개선안 3, 0 = 원래 모델)"""
    saved = saved or {}
    players, totals, hist = [], {}, {}
    for r in rows:
        try:
            pos = r['pos']
            group = POS_GROUP[max(range(15), key=lambda i: pos[i])]
            prof, amb, det, wr, flair = r['tr']
            if None in (prof, amb, det, wr):
                continue
            minutes, rated, rsum, starts, subs, goals, assists, pens = r['s']
            p = Player(int(r['u']), r['n'], r['b'], group, int(r['ca']), int(r['pa']), int(r['lg']),
                       float(prof), float(amb), float(det), float(wr), {}, 0, None if flair is None else float(flair))
        except (KeyError, TypeError, ValueError):
            continue
        sv = saved.get(str(p.uid))
        if sv is not None and sv.get('dob') == p.dob and sv.get('position') and sv.get('league'):
            s = copy.deepcopy(sv)
            p = Player(p.uid, p.name, p.dob, s['position'], p.ca, p.pa, s['league'], p.professionalism, p.ambition,
                       p.determination, p.work_rate, {}, 0, p.flair)
            s.update(talent_age=p.age(due), ability_as_of=due.isoformat(), team_name=r.get('tn', ''), calendar=s.get('season_year'))
            mine = history.get(str(p.uid), {})
            prev = mine.get(str(due.year - 1))
            s['ca_growth'] = None
            hist[p.uid] = [dict(year=int(y), **h) for y, h in mine.items() if h.get('dob') == p.dob]
            players.append(p)
            totals[p.uid] = s
            continue
        if cup_weight > 0:
            extra = [x for x in (r.get('c'), r.get('i')) if x]
            if extra:
                base = [minutes, rated, rsum, starts, subs, goals, assists, pens]
                for x in extra:
                    base = [b + cup_weight * v for b, v in zip(base, x)]
                minutes, rated, rsum, starts, subs, goals, assists, pens = [int(round(v)) for v in base]
        adv = decode_detail(r.get('d'), minutes, goals, group)
        d = dict(zip(DETAIL_FIELDS, r.get('d') or [0] * len(DETAIL_FIELDS)))
        s = {'minutes': minutes, 'rated': rated, 'rating_sum': rsum, 'starts': starts, 'subs': subs, 'goals': goals,
             'assists': assists, 'penalties': pens, 'key_passes': d['key_passes'], 'tackles': d['tackles_completed'],
             'interceptions': d['interceptions'], 'headers': d['headers_won'], 'saves_proxy': 0,
             'quality': True, 'league': p.league, 'season_team': r.get('tm'), 'coverage': 1.0, 'ca_end': p.ca,
             'dob': p.dob, 'position': group, 'advanced': adv, 'source_kind': 'observed_july_window',
             'ability_as_of': due.isoformat(), 'team_name': r.get('tn', '')}
        mine = history.get(str(p.uid), {})
        prev = mine.get(str(due.year - 1))
        s['ca_growth'] = (p.ca - prev['ca']) if prev and prev.get('dob') == p.dob and isinstance(prev.get('ca'), int) else None
        hist[p.uid] = [dict(year=int(y), **h) for y, h in mine.items() if h.get('dob') == p.dob]
        players.append(p)
        totals[p.uid] = s
    return players, totals, hist


def explain(x, team, calendar=None):
    """개선안 1: 선수별 한국어 설명"""
    d = x['new'] - x['old']
    pct = x['percentile']
    rank = ('상위 %d%%' % max(1, round(100 - pct))) if pct >= 50 else ('하위 %d%%' % max(1, round(pct)))
    head = '%s %d명 중 %s, 평점 %.2f, %s분' % (POS_KO.get(x['position'], x['position']), x['cohort_size'], rank,
                                          x['rating'], format(x['minutes'], ','))
    parts = []
    if calendar:
        parts.append('직전 완료 시즌(%s) 1년 기록' % calendar)
    if x['event'] == 'breakout':
        parts.append('급성장')
    elif x['event'] == 'setback':
        parts.append('큰 하락')
    for code in (x.get('evaluation_reason') or '').split(';'):
        if code in REASON_KO:
            parts.append(REASON_KO[code])
    if x.get('budget_reduction'):
        parts.append('전체 균형으로 %d 줄임' % x['budget_reduction'])
    if d > 0 and x.get('pa_growth_factor', 1) < 1:
        parts.append('높은 PA라 덜 오름(×%.2f)' % x['pa_growth_factor'])
    if d > 0 and x.get('headroom_growth_factor', 1) < 1:
        parts.append('PA-CA 여유가 커서 덜 오름(×%.2f)' % x['headroom_growth_factor'])
    if x.get('poor'):
        parts.append('부진 판정')
    if x.get('history_periods', 1) > 1:
        parts.append('지난 시즌 %d개 반영' % (x['history_periods'] - 1))
    return head + (' → %+d' % d if d else ' → 그대로') + (' (' + ', '.join(parts) + ')' if parts else '')


INJURY_MIN_DAYS = 120   # 평가 기간(1년)에 이만큼 이상 다쳐 있었으면 장기 부상


def injury_days(injuries, due):
    """평가 기간 [due-1년, due) 안에 부상으로 빠진 일수. injuries = [{start, total, ...}] (같은 시작일은 한 번)"""
    lo, hi = date(due.year - 1, due.month, due.day), due
    seen, days = set(), 0
    for j in injuries or []:
        try:
            a = date.fromisoformat(j["start"])
            n = int(j.get("total") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if a in seen or n <= 0:
            continue
        seen.add(a)
        b = a + timedelta(days=n)
        days += max(0, (min(b, hi) - max(a, lo)).days)
    return days


def _draw(seed, due, uid, dob, label):
    data = "m24ga-injury-1|%s|%s|%d|%s|%s" % (seed, due.isoformat(), uid, dob, label)
    return int.from_bytes(hashlib.sha256(data.encode()).digest()[:8], "big") / 2 ** 64


def injury_effect(results, rows, injuries, due, seed):
    """개선안 7 (M24GA 새 규칙, 원래 모델에 없음): 평가 기간에 120일 이상 다친 선수는 작은 확률로 PA -1~-3.
    - 확률 8%(120일) ~ 20%(1년 내내). 같은 세이브·평가일·선수면 결과가 항상 같다.
    - 크기: 21세 이하 -1, 22~27세 -1~-2, 28세 이상 -1~-3. CA 아래로는 안 내린다.
    - 원래 모델에서 오른 선수는 건드리지 않고, 이미 내린 선수는 더 큰 하락 한 쪽만 (더하지 않음).
    - 전체 예산(오름 상한) 계산 뒤에 하므로 이 하락이 다른 선수의 오름을 늘리지 않는다."""
    by_uid = {r["uid"]: r for r in results}
    added = 0
    for raw in rows:
        uid = int(raw["u"])
        days = injury_days(injuries.get(str(uid)), due)
        if days < INJURY_MIN_DAYS:
            continue
        r = by_uid.get(uid)
        if r and r["delta"] > 0:
            continue
        prob = min(.20, .08 + .12 * (days - INJURY_MIN_DAYS) / (365 - INJURY_MIN_DAYS))
        if _draw(seed, due, uid, raw["b"], "event") >= prob:
            if r:
                r["injury_days"] = days
            continue
        born = date.fromisoformat(raw["b"])
        age = due.year - born.year - ((due.month, due.day) < (born.month, born.day))
        top = 1 if age <= 21 else 2 if age <= 27 else 3
        mag = 1 + int(_draw(seed, due, uid, raw["b"], "magnitude") * top)
        if r is None:
            minutes, rated, rsum, _, _, goals, assists, _ = raw["s"]
            r = {"uid": uid, "name": raw["n"], "dob": raw["b"], "age": age, "pos": POS_GROUP[max(range(15), key=lambda i: raw["pos"][i])],
                 "team": raw.get("tn", ""), "league": raw.get("lg", 0), "ca": int(raw["ca"]), "old": int(raw["pa"]), "new": int(raw["pa"]),
                 "delta": 0, "pct": 0.0, "rating": round(rsum / 10 / rated, 2) if rated else 0.0, "minutes": minutes,
                 "goals": goals, "assists": assists, "event": "normal", "poor": False, "ranked": False, "why": ""}
            results.append(r)
            by_uid[uid] = r
            added += 1
        new = max(r["ca"], min(r["new"], r["old"] - mag))
        if new >= r["new"]:
            continue
        r["new"], r["delta"], r["event"], r["injury_days"] = new, new - r["old"], "injury", days
        note = "평가 기간 부상 %d일 → 장기 부상 %+d" % (days, new - r["old"])
        r["why"] = (r["why"] + " · " + note) if r["why"] else note
    return added


def evaluate(rows, due, history, seed, rare_events=True, injuries=None, saved=None, cup_weight=0.0, scale=1.0):
    """-> (results, summary). results는 평가된 모든 선수 (바뀌지 않은 선수 포함). injuries를 주면 장기 부상 규칙도.
    scale < 1이면 반기 점검(개선안 4): 변화량을 그만큼 줄인다 (0쪽으로 버림), 장기 부상·드문 사건 크기도 같이"""
    rules = dict(dpa_rules.DEFAULTS)
    rules['rare_events'] = bool(rare_events)
    players, totals, hist = build(rows, due, history, saved, cup_weight)
    mine_uids = {int(r['u']) for r in rows if r.get('m')}
    out = model_v07.proposals(players, totals, due, hist, seed_context=seed, rules=rules)
    results = []
    for x in out:
        s = totals[x['uid']]
        results.append({'uid': x['uid'], 'name': x['name'], 'dob': x['dob'], 'age': x['age'], 'pos': x['position'],
                        'team': s.get('team_name', ''), 'league': s['league'], 'ca': x['ca'], 'old': x['old'], 'new': x['new'],
                        'delta': x['new'] - x['old'], 'pct': x['percentile'], 'rating': x['rating'], 'minutes': x['minutes'],
                        'goals': x['goals'], 'assists': x['assists'], 'event': x['event'], 'poor': bool(x['poor']),
                        'ranked': True, 'mine': x['uid'] in mine_uids, 'calendar': s.get('calendar'),
                        'why': explain(x, s.get('team_name', ''), s.get('calendar'))})
    injury_only = injury_effect(results, rows, injuries, due, seed) if injuries is not None else 0
    for r in results:
        r.setdefault('mine', r['uid'] in mine_uids)
        if scale < 1 and r['delta']:
            d = int(r['delta'] * scale)                 # 0쪽으로 버림
            r['new'] = max(r['ca'], min(200, r['old'] + d))
            r['delta'] = r['new'] - r['old']
            r['why'] += ' · 반기 점검이라 절반 → %+d' % r['delta']
    summary = {'due': due.isoformat(), 'collected': len(rows), 'evaluated': len(results),
               'up': sum(r['delta'] > 0 for r in results), 'down': sum(r['delta'] < 0 for r in results),
               'breakout': sum(r['event'] == 'breakout' for r in results), 'setback': sum(r['event'] == 'setback' for r in results),
               'injury': sum(r['event'] == 'injury' for r in results), 'injury_only': injury_only,
               'calendar': sum(1 for r in results if r.get('calendar')), 'scale': scale, 'cup_weight': cup_weight,
               'mine': [{k: r[k] for k in ('name', 'pos', 'age', 'old', 'new', 'delta', 'event', 'why')}
                        for r in sorted(results, key=lambda r: -abs(r['delta'])) if r.get('mine') and r['delta']][:30],
               'highlights': [{k: r[k] for k in ('name', 'team', 'age', 'old', 'new', 'delta', 'event')}
                              for r in sorted(results, key=lambda r: -r['delta']) if r['event'] == 'breakout'][:10],
               'history_players': sum(1 for x in history.values() if any(int(y) in (due.year - 1, due.year - 2) for y in x)),
               'net': sum(r['delta'] for r in results), 'model': model_v07.MODEL_VERSION}
    return results, summary


def history_entries(results):
    """다음 해 평가에 쓸 기록: {uid: {dob, percentile, poor, ca}}"""
    return {str(r['uid']): {'dob': r['dob'], 'percentile': r['pct'], 'poor': r['poor'], 'ca': r['ca']} for r in results if r.get('ranked', True)}


def due_for(today, month=7, day=1):
    """오늘 기준 이번 평가일 (원래 모델의 season_start와 같음)"""
    anchor = date(today.year, month, day)
    return anchor if today >= anchor else date(today.year - 1, month, day)
