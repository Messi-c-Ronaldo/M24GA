# -*- coding: utf-8 -*-
"""몸값 보정 기능 B: 활약 배율 계산 (게임 없이 시험할 수 있는 순수 계산). GPL-3.0-or-later

입력
  rows: 게임 쪽(mod.js)이 보낸 이번 시즌 리그 기록 [uid, 리그 UID, 포지션 무리(0~7), 출전 분, 평점 경기, 평점 합(x10), 생년월일, 내 팀(0/1), 이름, CA, 국가대표 [분, 평점 경기, 평점 합] 또는 None, A매치 통산 출전, 사람 번호(player.link)]
  prior: m24hist가 세이브 파일에서 읽은 지난 시즌 백분위 {uid 글자: [{year, dob, percentile(0~100), poor}]}
         year = 시즌이 끝난 해 (예: 2034/35 시즌 = 2035)
출력
  {uid: 배율}. 배율 = 1 + 세기 × (2 × 가중 백분위 − 1) × 확신도. 가중 백분위는 이번 시즌(출전 시간만큼)과 지난 두 시즌.
  모든 구단 선수에 똑같은 규칙 (내 선수만 올리면 돈벌이 수단이 됨, 몸값모드 V01 2절).
"""

# 게임 포지션 15칸(GK SW DL DC DR DM ML MC MR AML AMC AMR ST WBL WBR) -> 무리 (Dynamic PA와 같은 묶음)
POS_GROUP = (0, 1, 2, 1, 2, 3, 4, 5, 4, 4, 6, 4, 7, 2, 2)   # 0 GK 1 CB 2 FB 3 DM 4 W 5 CM 6 AM 7 ST
GROUP_KO = ("골키퍼", "중앙 수비", "측면 수비", "수비형 미드", "윙어", "중앙 미드", "공격형 미드", "스트라이커")

MIN_MINUTES = 270        # 이번 시즌 비교군에 들어가는 최소 출전 (3경기쯤)
MIN_RATED = 3
SHRINK = 5               # 평점 경기 수가 적으면 비교군 평균 쪽으로 당김 (경기 5개만큼)
MIN_PEERS = 8            # 리그·포지션 비교군이 이보다 작으면 리그 전체로
FULL_MINUTES = 1800      # 이번 시즌 무게가 꽉 차는 출전 시간 (20경기쯤)
W_CURRENT, W_LAST, W_BEFORE = 0.5, 0.35, 0.15
# 리그 수준 (V08): Dynamic PA league_strength와 같은 지표 = 리그 주전 평균 CA로 (평균 - 110) / 40, -1~1.
# 리그 전체를 올리거나 내리지는 않고(게임 몸값에 리그 명성이 이미 있음), 잘한 정도의 무게만 바꾼다:
#   잘함(d > 0): d × (1 + LEAGUE_K × 지표)  -> 약한 리그 1등은 덜 오름, 강한 리그 1등은 더 오름
#   못함(d < 0): d × (1 - LEAGUE_K × 지표)  -> 강한 리그에서 부진은 덜 내림
LEAGUE_K = 0.5
LEAGUE_MIN_SAMPLE = 30
CAPS_FULL = 50
# 커리어 영예 (V12): 수상(세이브 award_year_hist) + 우승(comp_history x 선수 시즌 기록). 최근 3시즌, 최근일수록 무게 큼
PLACE_W = {1: 1.0, 2: 0.5, 3: 0.25}
RECENT_W = (1.0, 0.7, 0.5)        # 마지막으로 끝난 시즌, 그 전, 그 전전
TROPHY_W = 0.8                   # 우승 하나 x 대회 크기 (0.1~1, trophy_prestige)
HONOURS_FULL = 3.0               # 점수가 이만큼이면 보너스가 꽉 참            # 국가대표 통산 보너스가 꽉 차는 A매치 출전 수 (V10)   # 이번 시즌 비교군(270분 이상) 선수가 이보다 적은 리그는 지표 0
MIN_WEIGHT = 0.1         # 무게 합이 이보다 작으면 배율 1 (기록 부족)
FULL_WEIGHT = 0.5        # 무게 합이 이만큼이면 확신도 1


def _percentiles(values):
    """[(key, value)] -> {key: 0~100 백분위 (같은 값은 평균 순위)}"""
    n = len(values)
    if n == 1:
        return {values[0][0]: 50.0}
    order = sorted(values, key=lambda kv: kv[1])
    out, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and order[j + 1][1] == order[i][1]:
            j += 1
        rank = (i + j) / 2.0
        for k in range(i, j + 1):
            out[order[k][0]] = 100.0 * rank / (n - 1)
        i = j + 1
    return out


def current_percentiles(rows):
    """이번 시즌 리그 평점 -> {uid: (백분위, 출전 분)}. 리그·포지션 무리 안에서, 평점 경기가 적으면 비교군 평균 쪽으로 당김"""
    ok = [r for r in rows if r[3] >= MIN_MINUTES and r[4] >= MIN_RATED and r[1]]
    by_league = {}
    for r in ok:
        by_league.setdefault(r[1], []).append(r)
    def ranked(pool):
        mu = sum(r[5] for r in pool) / float(sum(r[4] for r in pool)) / 10.0   # 비교군 평균 평점
        return _percentiles([(r[0], (r[5] / 10.0 + SHRINK * mu) / (r[4] + SHRINK)) for r in pool])

    out = {}
    for rs in by_league.values():
        if len(rs) < MIN_PEERS:
            continue                          # 리그 전체도 너무 작으면 이번 시즌은 안 씀
        whole = None
        groups = {}
        for r in rs:
            groups.setdefault(r[2], []).append(r)
        for g in groups.values():
            if len(g) >= MIN_PEERS:
                pct = ranked(g)               # 같은 리그·같은 포지션 무리 안에서
            else:
                whole = whole or ranked(rs)   # 무리가 작으면 리그 전체와 비교
                pct = whole
            for r in g:
                out[r[0]] = (pct[r[0]], r[3])
    return out


def with_intl(rows, weight):
    """국가대표 경기를 리그 기록에 weight(0~1) 비율로 더한 새 줄 목록 (포텐 모드의 cup_weight와 같은 방식). 줄[10] = [출전 분, 평점 경기, 평점 합(x10)] 또는 None"""
    if weight <= 0:
        return rows
    out = []
    for r in rows:
        x = r[10] if len(r) > 10 else None
        if x and x[1] > 0:
            r = list(r)
            r[3] += int(round(weight * x[0]))
            r[4] += int(round(weight * x[1]))
            r[5] += int(round(weight * x[2]))
        out.append(r)
    return out


def league_index(rows):
    """{리그 UID: 지표 -1~1}. 이번 시즌 270분·3경기 이상 뛴 선수의 평균 CA (리그 하나의 평균만 쓰고 선수 개인 CA는 배율에 안 씀)"""
    cas = {}
    for r in rows:
        if len(r) > 9 and r[9] and r[1] and r[3] >= MIN_MINUTES and r[4] >= MIN_RATED:
            cas.setdefault(r[1], []).append(r[9])
    return {lg: max(-1.0, min(1.0, (sum(v) / float(len(v)) - 110.0) / 40.0)) for lg, v in cas.items() if len(v) >= LEAGUE_MIN_SAMPLE}


def award_prestige(records, ca_by_link):
    """{상 번호: 0.1~1}: 역대 1위 수상자 중 지금 선수 목록에 있는 사람의 평균 CA로 상의 규모를 잰다 ((평균 - 110) / 60).
    records = m24awards.parse의 [(연도, 상, [(순위, 사람, 팀)])]. 잰 수상자가 3명 미만인 상은 넣지 않음 (honours_score가 0.3으로 봄).
    상 이름 없이도 발롱도르급과 작은 리그 상을 나눈다"""
    cas = {}
    for _year, aid, places in records:
        for place, pid, _team in places:
            if place == 1 and pid in ca_by_link:
                cas.setdefault(aid, []).append(ca_by_link[pid])
    return {aid: max(0.1, min(1.0, (sum(v) / float(len(v)) - 110.0) / 60.0)) for aid, v in cas.items() if len(v) >= 3}


def trophy_prestige(trophies_by_uid, ca_by_uid):
    """{대회 번호: 0.1~1}: 그 대회 우승 멤버(우승 팀에서 270분 이상) 중 지금 선수들의 평균 CA로 대회 크기를 잰다 ((평균 - 110) / 60).
    잰 선수가 5명 미만이면 넣지 않음 (honours_score가 0.3으로 봄). 챔스 우승 멤버와 작은 컵 우승 멤버가 자연스럽게 나뉜다 (V14)"""
    cas = {}
    for uid, wins in trophies_by_uid.items():
        ca = ca_by_uid.get(uid)
        if not ca:
            continue
        for _year, comp in wins:
            cas.setdefault(comp, []).append(ca)
    return {c: max(0.1, min(1.0, (sum(v) / float(len(v)) - 110.0) / 60.0)) for c, v in cas.items() if len(v) >= 5}


def honours_score(link, uid, awards_by_link, trophies_by_uid, prestige, due_year, tprestige=None):
    """최근 3시즌 수상·우승 점수. 수상 연도 = 시즌이 끝난 해, 우승 연도 = 시즌 시작 해"""
    sc = 0.0
    for year, aid, place in awards_by_link.get(link, ()) if link is not None else ():
        back = (due_year - 1) - year                 # 0 = 마지막으로 끝난 시즌
        if 0 <= back < len(RECENT_W):
            sc += PLACE_W.get(place, 0) * RECENT_W[back] * prestige.get(aid, 0.3)
    for year, comp in trophies_by_uid.get(uid, ()):
        back = (due_year - 2) - year
        if 0 <= back < len(RECENT_W):
            sc += TROPHY_W * RECENT_W[back] * (tprestige or {}).get(comp, 0.3)
    return sc


def factors(rows, prior, due_year, strength, league=True, intl=0.0, caps=0.0, honours=None, hcap=0.0):
    """-> ({uid: 배율}, 요약). due_year = 이번 시즌이 끝나는 해 (예: 2035/36 시즌 = 2036). league: 리그 수준으로 무게 조절 (V08)"""
    strength = max(0.0, min(0.6, float(strength)))
    lix = league_index(rows) if league else {}     # 리그 수준은 리그 기록만으로
    intl = max(0.0, min(1.0, float(intl)))
    cur = current_percentiles(with_intl(rows, intl))
    dob = {r[0]: r[6] for r in rows}
    caps = max(0.0, min(0.15, float(caps)))
    hcap = max(0.0, min(0.15, float(hcap)))
    awards_by_link, trophies_by_uid, prestige = (honours or ({}, {}, {}))[:3]
    tprestige = honours[3] if honours and len(honours) > 3 else None
    out, used = {}, {"current": 0, "last": 0, "before": 0, "caps": 0, "honours": 0}
    for r in rows:
        uid = r[0]
        parts = []
        if uid in cur:
            pct, mins = cur[uid]
            parts.append((W_CURRENT * min(1.0, mins / float(FULL_MINUTES)), pct))
            used["current"] += 1
        for h in prior.get(str(uid), ()):
            if h.get("dob") != dob.get(uid):
                continue                     # 다른 선수가 같은 UID를 쓰는 경우 (새로 만든 선수 등)
            if h.get("year") == due_year - 1:
                parts.append((W_LAST, float(h["percentile"])))
                used["last"] += 1
            elif h.get("year") == due_year - 2:
                parts.append((W_BEFORE, float(h["percentile"])))
                used["before"] += 1
        w = sum(p[0] for p in parts)
        cb = caps * min(1.0, (r[11] if len(r) > 11 and r[11] else 0) / float(CAPS_FULL))   # 국가대표 통산 보너스 (활약과 따로)
        if cb > 0:
            used["caps"] += 1
        if hcap > 0:                                   # 커리어 영예 보너스 (수상·우승, V12)
            hs = honours_score(r[12] if len(r) > 12 else None, uid, awards_by_link, trophies_by_uid, prestige, due_year, tprestige)
            if hs > 0:
                used["honours"] += 1
                cb = (1.0 + cb) * (1.0 + hcap * min(1.0, hs / HONOURS_FULL)) - 1.0
        if w < MIN_WEIGHT:
            if cb > 0:
                out[uid] = round(1.0 + cb, 3)
            continue
        p = sum(a * b for a, b in parts) / w / 100.0
        conf = min(1.0, w / FULL_WEIGHT)
        d = 2.0 * p - 1.0
        k = lix.get(r[1], 0.0)          # 지금 리그 기준 (지난 시즌 리그는 세이브 기록에 없어서 지금 리그로 봄)
        d = max(-1.0, min(1.0, d * (1.0 + LEAGUE_K * k) if d > 0 else d * (1.0 - LEAGUE_K * k)))
        f = 1.0 + strength * d * conf
        f = round(max(1.0 - strength, min(1.0 + strength, f)) * (1.0 + cb), 3)
        if f != 1.0:
            out[uid] = f
    summary = {"players": len(rows), "scaled": len(out), "up": sum(1 for f in out.values() if f > 1), "down": sum(1 for f in out.values() if f < 1),
               "with_current": used["current"], "with_last": used["last"], "with_before": used["before"], "strength": strength,
               "intl": intl, "caps": caps, "caps_players": used["caps"], "honours_players": used["honours"], "hcap": hcap, "intl_players": sum(1 for r in rows if len(r) > 10 and r[10] and r[10][1] > 0), "leagues": len(lix), "league_top": sorted(lix.items(), key=lambda kv: -kv[1])[:5]}
    return out, summary
