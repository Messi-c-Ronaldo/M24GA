# -*- coding: utf-8 -*-
"""M24GA 공용 라이브러리 (pylib, 코어 0.19.0): 세이브 파일(.fm)에서 해마다 주는 상의 역대 수상자 읽기 (읽기 전용). GPL-3.0-or-later

몸값모드 V12에서 형식을 확인했다 (게임 화면 '경력 업적'과 맞춤: 홀란 2034/35 유러피언 골든슈 1위, 라리가 득점왕 1위,
라리가 올해의 선수 2위, 챔스 골든 부츠 2위).

세이브 안의 award_year_hist_ls.dat(목록) + award_year_hist_dt.cmt(기록). 다른 *_hist 파일과 같은 _ls/_dt 형식 (dpa.save_history).
기록 하나 (보통 82바이트, 크기는 _ls 끝에 적혀 있음):
  +0  u16 연도 (시즌이 끝나는 해: 2034/35 시즌 = 2035)
  +2  u16 상 번호 (게임 db::AWARD 객체 +0x8의 번호와 같음)
  +4, +30, +56  1위·2위·3위 칸 (26바이트씩): +0 u32 수상자 사람 번호 (persons 표 번호 = 필드 player.link), +4 u32 팀 번호,
                나머지는 그때 기록으로 보임 (뜻 미확인). 빈 칸은 0xffffffff
사람 번호는 게임 메모리의 player.link와 같다 (홀란 45806).
"""
import os
import pickle
import struct
import time

from dpa.save_archive import SaveArchive
import m24hist

PLACE_OFFSETS = (4, 30, 56)
EMPTY = 0xffffffff


class _NoCancel:
    def is_set(self):
        return False


def parse(path):
    """세이브 파일 -> {"records": [(연도, 상 번호, [(순위, 사람 번호, 팀 번호), ...])], "width": 기록 크기}"""
    with SaveArchive(path, _NoCancel()) as a:
        lk = {m.name: m for m in a.members}
        if "award_year_hist_ls.dat" not in lk or "award_year_hist_dt.cmt" not in lk:
            raise ValueError("세이브에 수상 기록 파일이 없어요")
        ls = b"".join(a.chunks(lk["award_year_hist_ls.dat"]))
        dt = b"".join(a.chunks(lk["award_year_hist_dt.cmt"]))
    if dt[:4] != b"\x03\x01tm" or ls[:4] != b"\x03\x01ta":
        raise ValueError("수상 기록 형식이 달라요")
    width = struct.unpack_from("<I", ls, len(ls) - 6)[0]
    if width < 60 or (len(dt) - 8) % width:
        raise ValueError("수상 기록 크기가 이상해요 (%d)" % width)
    out = []
    for k in range((len(dt) - 8) // width):
        r = dt[8 + k * width: 8 + (k + 1) * width]
        year, aid = struct.unpack_from("<HH", r, 0)
        places = []
        for place, off in enumerate(PLACE_OFFSETS, 1):
            pid, team = struct.unpack_from("<II", r, off)
            if pid != EMPTY:
                places.append((place, pid, team))
        out.append((year, aid, places))
    return {"records": out, "width": width}


def by_person(records):
    """[(연도, 상, [(순위, 사람, 팀)])] -> {사람 번호: [(연도, 상 번호, 순위)]}"""
    per = {}
    for year, aid, places in records:
        for place, pid, _team in places:
            per.setdefault(pid, []).append((year, aid, place))
    return per


# ---- 대회 우승 (몸값모드 V12) ----
# comp_history_ls.dat / comp_history_dt.cmt: 기록 55바이트 = +0 u32 대회 번호, +4 u16 결정된 달력 해 (V15: 시즌 시작 해 아님),
#   +8 u32 우승 팀 번호, +12 준우승, +16 3위 (팀 번호 = 게임 db::TEAM 객체 +0x8, 바르셀로나 1군 1320), +47 u16 시즌 시작 해, +49 끝 해.
# 선수 쪽: player_stats_hist (dpa가 읽는 시즌별 선수 기록) = 기록마다 +1 u32 팀, +5 u16 리그, +11 u16 시즌 시작 해, +15 u16 출전 분,
#   +31 종류 (1 리그, 0·2·3 컵·대륙컵 등으로 보임). 선수 -> 기록 목록은 game_db의 선수 기록(dpa player_records의 history_ref).
# 선수의 우승 = 그 시즌 그 팀에서 MIN_TROPHY_MINUTES 이상 뛰었고 그 팀이 우승한 대회 (FM 경력 업적과 같은 기준으로 보임).
COMP_WIDTH = 55
MIN_TROPHY_MINUTES = 270


def comp_winners(cdt):
    """comp_history_dt -> {(팀 번호, 시즌 시작 해): [대회 번호, ...]}.
    V15: 기록 +4의 연도는 '결정된 달력 해'(라리가 2033/34 = 2034, 8월 UEFA 슈퍼컵 2034/35 = 2034)라서,
    선수 시즌 기록(시작 해)과 맞추려면 기록 끝의 시즌 시작 해(+47 u16, 다음 +49 끝 해)를 쓴다.
    주의: 가장 최근에 끝난 시즌(예: 2035-09 기준 2034/35 리그)은 아직 이 파일에 없을 수 있다 (게임이 나중에 보관)."""
    out = {}
    for k in range((len(cdt) - 8) // COMP_WIDTH):
        p = 8 + k * COMP_WIDTH
        comp = struct.unpack_from("<I", cdt, p)[0]
        start = struct.unpack_from("<H", cdt, p + 47)[0]
        team = struct.unpack_from("<I", cdt, p + 8)[0]
        if team != EMPTY:
            out.setdefault((team, start), []).append(comp)
    return out


def parse_trophies(path, since_year, extra_wins=None):
    """세이브 파일 -> {"by_uid": {선수 UID: [(시즌 시작 해, 대회 번호)]}, "winners": 우승 기록 수, "players": 선수 수}.
    since_year 이후 시즌만 (오래 걸림: game_db 선수 기록을 읽어서 1분 안팎)"""
    from dpa import save_history as H
    with SaveArchive(path, _NoCancel()) as a:
        lk = {m.name: m for m in a.members}
        rd = lambda n: b"".join(a.chunks(lk[n]))
        need = ("game_db.dat", "player_stats_hist_dt.cmt", "rgman/player_stats_hist_ls.dat", "comp_history_dt.cmt")
        if any(n not in lk for n in need):
            raise ValueError("세이브에 우승 계산에 필요한 파일이 없어요")
        db = rd("game_db.dat")
        players, _, _ = H.player_records(db)
        del db
        sdt = rd("player_stats_hist_dt.cmt")
        lists, free, _ = H.history_lists(rd("rgman/player_stats_hist_ls.dat"), sdt)
        cdt = rd("comp_history_dt.cmt")
    wins = comp_winners(cdt)
    for key, comps in (extra_wins or {}).items():   # V16: 게임 메모리(compLatest)의 최근 시즌 우승 {(팀, 시작 해): [대회]}
        lst = wins.setdefault(tuple(key), [])
        for c in comps:
            if c not in lst:
                lst.append(c)
    # V15: 대회 기록에 아직 보관되지 않은 최근 시즌 리그 우승은 팀 순위 기록(tc_league_history, 1위)으로 채운다 (컵은 못 채움)
    try:
        for team, rows in parse_league_history(path)["by_team"].items():
            for r in rows:
                if r["pos"] == 1:
                    lst = wins.setdefault((team, r["year"] - 1), [])
                    if r["comp"] not in lst:
                        lst.append(r["comp"])
    except ValueError:
        pass
    by_uid = {}
    for row in players:
        ref = row["history_ref"]
        if ref >= len(lists) or ref in free:
            continue
        mins = {}
        for off in lists[ref]:
            p = 8 + off
            if p + 32 > len(sdt):
                continue
            year = struct.unpack_from("<H", sdt, p + 11)[0]
            if year < since_year:
                continue
            team = struct.unpack_from("<I", sdt, p + 1)[0]
            mins[(team, year)] = mins.get((team, year), 0) + struct.unpack_from("<H", sdt, p + 15)[0]
        got = []
        for (team, year), m in mins.items():
            if m >= MIN_TROPHY_MINUTES:
                got += [(year, c) for c in wins.get((team, year), ())]
        if got:
            by_uid[row["player"].uid] = sorted(set(got))
    return {"by_uid": by_uid, "winners": sum(len(v) for v in wins.values()), "players": len(players)}


def load_trophies(save_id, since_year, cache_path=None, log=lambda m: None, extra_wins=None):
    """parse_trophies + 캐시 (파일 경로·크기·수정 시각·since_year가 같으면 다시 읽지 않음). 파일이 없으면 None"""
    path = m24hist.find_save(save_id)
    if not path:
        return None
    st = os.stat(path)
    extra_sig = sorted((list(k), sorted(v)) for k, v in (extra_wins or {}).items())
    key = [os.path.abspath(path), st.st_size, int(st.st_mtime), since_year, 3, extra_sig]   # 3 = V16 최근 시즌 우승 포함
    if cache_path:
        try:
            with open(cache_path, "rb") as f:
                c = pickle.load(f)
            if c.get("key") == key:
                return c["data"]
        except (OSError, ValueError, EOFError, pickle.UnpicklingError, AttributeError, ImportError):
            pass
    t0 = time.time()
    log("우승 기록: %s 읽는 중 (1분 안팎)" % os.path.basename(path))
    data = parse_trophies(path, since_year, extra_wins)
    if cache_path:
        tmp = cache_path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump({"key": key, "data": data}, f)
        os.replace(tmp, cache_path)
    log("우승 기록: 선수 %d명이 %d시즌 이후 우승 (%.0f초)" % (len(data["by_uid"]), since_year, time.time() - t0))
    return data


# ---- 구단·대표팀 시즌 베스트 일레븐 (몸값모드 V14) ----
# tc_best_eleven_history_ls.dat / _dt.cmt: 목록 = 팀 컨테이너(구단·국가대표)마다 (목록 -> 팀 번호는 best_eleven_teams, V15),
#   기록 509바이트 = +0 u16 시즌 시작 해 (2034 = 2034/35, 화면 "바르셀로나 시즌별 베스트 일레븐에 선정 2035/6/4"),
#   +2부터 27바이트 칸 18개 (0~10 선발 11명, 11~17 교체로 보임): +0 u32 사람 번호(player.link), +4 u16 경기, +6 u16 골,
#   +8 u16 평점 관련 값(뜻 미확인), 나머지 포지션 플래그. 끝 21바이트는 포메이션·포지션 목록으로 보임.
BEST11_SLOTS = 18
BEST11_SLOT = 27


def parse_best_elevens(path):
    """세이브 파일 -> [(시즌 시작 해, [(칸 0~17, 사람 번호, 경기, 골)], 목록 번호)] (목록 = 구단·대표팀, best_eleven_teams로 팀 번호)"""
    with SaveArchive(path, _NoCancel()) as a:
        lk = {m.name: m for m in a.members}
        if "tc_best_eleven_history_ls.dat" not in lk or "tc_best_eleven_history_dt.cmt" not in lk:
            raise ValueError("세이브에 베스트 일레븐 기록 파일이 없어요")
        ls = b"".join(a.chunks(lk["tc_best_eleven_history_ls.dat"]))
        dt = b"".join(a.chunks(lk["tc_best_eleven_history_dt.cmt"]))
    width = struct.unpack_from("<I", ls, len(ls) - 6)[0]
    if width < 2 + BEST11_SLOTS * BEST11_SLOT or (len(dt) - 8) % width:
        raise ValueError("베스트 일레븐 기록 크기가 이상해요 (%d)" % width)
    owner = {off: li for li, refs in enumerate(_lists_of(ls)) for off in refs}
    out = []
    for k in range((len(dt) - 8) // width):
        p = 8 + k * width
        year = struct.unpack_from("<H", dt, p)[0]
        slots = []
        for s in range(BEST11_SLOTS):
            pid, apps, goals = struct.unpack_from("<IHH", dt, p + 2 + s * BEST11_SLOT)
            if pid != EMPTY:
                slots.append((s, pid, apps, goals))
        out.append((year, slots, owner.get(k * width)))
    return out


def best_eleven_teams(path, records=None):
    """베스트 일레븐 목록 번호 -> 팀 번호 (db::TEAM +0x8): 선발 11명이 그 시즌 가장 오래 뛴 팀으로 다수결 (V15).
    선수 시즌 기록과 game_db 선수 기록(dpa player_records, entity_id = 사람 번호 player.link)을 읽어서 1분 안팎.
    반환 {목록 번호: 팀 번호}. 대표팀 목록은 클럽 팀이 섞여 표가 갈리면 빠진다"""
    from dpa import save_history as H
    records = records if records is not None else parse_best_elevens(path)
    with SaveArchive(path, _NoCancel()) as a:
        lk = {m.name: m for m in a.members}
        rd = lambda n: b"".join(a.chunks(lk[n]))
        db = rd("game_db.dat")
        players, _, _ = H.player_records(db)
        del db
        sdt = rd("player_stats_hist_dt.cmt")
        lists, free, _ = H.history_lists(rd("rgman/player_stats_hist_ls.dat"), sdt)
    ref_of = {row["entity_id"]: row["history_ref"] for row in players}
    team_cache = {}

    def team_of(link, year):
        key = (link, year)
        if key in team_cache:
            return team_cache[key]
        ref, best = ref_of.get(link), None
        if ref is not None and ref < len(lists) and ref not in free:
            mins = {}
            for off in lists[ref]:
                q = 8 + off
                if q + 32 <= len(sdt) and struct.unpack_from("<H", sdt, q + 11)[0] == year:
                    t = struct.unpack_from("<I", sdt, q + 1)[0]
                    mins[t] = mins.get(t, 0) + struct.unpack_from("<H", sdt, q + 15)[0]
            if mins:
                best = max(mins.items(), key=lambda kv: kv[1])[0]
        team_cache[key] = best
        return best

    votes = {}
    for year, slots, li in records:
        if li is None:
            continue
        for s, pid, _apps, _goals in slots:
            if s <= 10:
                t = team_of(pid, year)
                if t is not None and t != EMPTY:
                    v = votes.setdefault(li, {})
                    v[t] = v.get(t, 0) + 1
    out = {}
    for li, v in votes.items():
        team, n = max(v.items(), key=lambda kv: kv[1])
        if n * 2 >= sum(v.values()):
            out[li] = team
    return out


def best_eleven_by_person(records, starters_only=True):
    """[(해, [(칸, 사람, 경기, 골)])] -> {사람 번호: [(시즌 시작 해, 칸)]} (starters_only면 칸 0~10만)"""
    per = {}
    for rec in records:
        year, slots = rec[0], rec[1]
        for s, pid, _apps, _goals in slots:
            if not starters_only or s <= 10:
                per.setdefault(pid, []).append((year, s))
    return per


# ---- 팀 시즌 리그 성적 (몸값모드 V15) ----
# tc_league_history_ls.dat / _dt.cmt: 목록 = 팀마다 (목록 번호는 파일마다 다르다), 기록 24바이트:
#   +0 u16 시즌이 끝나는 해 (2035 = 2034/35, comp_history +4와 같은 방식), +2 u16 대회 번호, +4 u8 순위(0 = 1위), +5 u8 팀 수, +12 u8 경기, +14 u8 승, +15 u8 무, +16 u16 패,
#   +18 u16 득점, +20 u16 실점, +22 u16 승점 (2034/35 라리가로 확인: 1위 36승 2무 0패 196득 20실 110점 = 바르셀로나).
# 목록 -> 팀 번호(db::TEAM +0x8): 대회 기록(comp_history)의 1·2·3위 팀과 같은 (대회, 시즌, 순위)를 가진 목록끼리 표결.
LEAGUE_WIDTH = 24


def _lists_of(ls):
    """_ls.dat -> [[기록 바이트 위치, ...] 목록마다] (dpa.save_history.history_lists와 같은 형식, 크기 검사는 안 함)"""
    at = 8
    free = struct.unpack_from("<I", ls, at)[0]
    at += 4 + 4 * free
    count = struct.unpack_from("<I", ls, at)[0]
    at += 4
    out = []
    for _ in range(count):
        n = struct.unpack_from("<I", ls, at)[0]
        at += 4
        prev, refs = 0, []
        for _ in range(n):
            enc = struct.unpack_from("<i", ls, at)[0]
            at += 4
            refs.append(enc + prev)
            prev = enc
        out.append(refs)
    return out


def _comp_places(cdt):
    """comp_history -> {(대회, 시즌 시작 해): [1위 팀, 2위 팀, 3위 팀]}"""
    out = {}
    for k in range((len(cdt) - 8) // COMP_WIDTH):
        p = 8 + k * COMP_WIDTH
        comp, year = struct.unpack_from("<IH", cdt, p)
        out[(comp, year)] = list(struct.unpack_from("<III", cdt, p + 8))
    return out


def parse_league_history(path):
    """세이브 파일 -> {"by_team": {팀 번호: [{year(끝나는 해), comp, pos(1=1위), teams, played, won, drawn, lost, gf, ga, pts}]},
    "unmapped": 팀을 못 정한 목록 수, "lists": 목록 수}. 팀은 그 목록이 리그 1~3위를 한 적이 있어야 정해진다"""
    with SaveArchive(path, _NoCancel()) as a:
        lk = {m.name: m for m in a.members}
        need = ("tc_league_history_ls.dat", "tc_league_history_dt.cmt", "comp_history_dt.cmt")
        if any(n not in lk for n in need):
            raise ValueError("세이브에 리그 성적 기록 파일이 없어요")
        rd = lambda n: b"".join(a.chunks(lk[n]))
        ls, dt, cdt = rd("tc_league_history_ls.dat"), rd("tc_league_history_dt.cmt"), rd("comp_history_dt.cmt")
    places = _comp_places(cdt)
    by_list = {}
    for li, refs in enumerate(_lists_of(ls)):
        rows = []
        for off in refs:
            p = 8 + off
            if p + LEAGUE_WIDTH > len(dt):
                continue
            year, comp, pos, teams = struct.unpack_from("<HHBB", dt, p)
            played, _x, won, drawn = struct.unpack_from("<BBBB", dt, p + 12)
            lost, gf, ga, pts = struct.unpack_from("<HHHH", dt, p + 16)
            rows.append({"year": year, "comp": comp, "pos": pos + 1, "teams": teams, "played": played, "won": won,
                         "drawn": drawn, "lost": lost, "gf": gf, "ga": ga, "pts": pts})
        if rows:
            by_list[li] = rows
    by_team, unmapped = {}, 0
    for li, rows in by_list.items():
        votes = {}
        for r in rows:
            if r["pos"] <= 3:
                t = places.get((r["comp"], r["year"]), [EMPTY] * 3)[r["pos"] - 1]
                if t != EMPTY:
                    votes[t] = votes.get(t, 0) + 1
        if not votes:
            unmapped += 1
            continue
        team, n = max(votes.items(), key=lambda kv: kv[1])
        if n * 2 < sum(votes.values()):          # 표가 갈리면 버림
            unmapped += 1
            continue
        by_team.setdefault(team, []).extend(sorted(rows, key=lambda r: r["year"]))
    return {"by_team": by_team, "unmapped": unmapped, "lists": len(by_list)}


def load(save_id, cache_path=None, log=lambda m: None):
    """지금 세이브(ID)의 가장 최근 .fm에서 수상 기록 -> {"records", "width", "file"} 또는 None (파일 없음).
    cache_path를 주면 (파일 경로·크기·수정 시각)이 같을 때 다시 읽지 않는다."""
    path = m24hist.find_save(save_id)
    if not path:
        log("수상 기록: 세이브 ID %d인 .fm 파일을 찾지 못했어요" % save_id)
        return None
    st = os.stat(path)
    key = [os.path.abspath(path), st.st_size, int(st.st_mtime), 1]
    if cache_path:
        try:
            with open(cache_path, "rb") as f:
                c = pickle.load(f)
            if c.get("key") == key:
                return c["data"]
        except (OSError, ValueError, EOFError, pickle.UnpicklingError, AttributeError, ImportError):
            pass
    t0 = time.time()
    data = parse(path)
    data["file"] = os.path.basename(path)
    if cache_path:
        tmp = cache_path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump({"key": key, "data": data}, f)
        os.replace(tmp, cache_path)
    log("수상 기록: %s에서 %d개 (%.1f초)" % (data["file"], len(data["records"]), time.time() - t0))
    return data
