# -*- coding: utf-8 -*-
"""M24GA 공용 라이브러리 (pylib, 코어 0.18.0): 포텐 모드의 savehist.py를 옮김 (몸값모드 V06). 개선안 6: 과거 시즌을 세이브 파일(.fm)에서 읽어 첫 해부터 '최근 3시즌 가중'에 쓴다 (M24GA 새 코드).

과거 시즌 기록은 게임 메모리에 평소 없어서(P05) 원래 프로그램처럼 세이브 파일을 읽는다 (dpa/save_history.parse_save, 읽기 전용).
지난 2시즌의 리그 기록으로 그해 비교군 순위를 다시 매겨 {uid: [{year, dob, percentile, poor}]}를 만든다
= Dynamic PA history_store.HistoryStore.prior_rankings(rules가 있을 때)와 같은 계산.
한 번 읽은 결과는 세이브 폴더 savehist.json에 (파일 경로·크기·수정 시각·평가일) 열쇠로 남겨 다시 읽지 않는다.
"""
import glob
import json
import os
import pickle
import time
from dataclasses import replace
from datetime import date

from dpa.save_archive import SaveArchive
from dpa import save_history as H
from dpa.league_strength import profiles, for_player
from dpa.model_v07 import MIN_PEERS
from dpa import rules as dpa_rules


def save_dirs():
    home = os.path.expanduser("~")
    out = []
    for docs in ("Documents", os.path.join("OneDrive", "문서"), os.path.join("OneDrive", "Documents")):
        d = os.path.join(home, docs, "Sports Interactive", "Football Manager 2024", "games")
        if os.path.isdir(d):
            out.append(d)
    return out


class _NoCancel:
    def is_set(self):
        return False


def save_id_of(path):
    """세이브 파일 안의 세이브 ID (game_info.dat +34). 못 읽으면 None"""
    try:
        with SaveArchive(path, _NoCancel()) as a:
            info = a.small_member("game_info.dat")
        return int.from_bytes(info[34:38], "little") if len(info) >= 38 else None
    except Exception:       # 다른 형식·깨진 파일은 건너뜀
        return None


def find_save(save_id):
    """지금 세이브와 ID가 같은 .fm 중 가장 최근 것 (없으면 None)"""
    files = []
    for d in save_dirs():
        files += glob.glob(os.path.join(d, "*.fm"))
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        if save_id_of(f) == save_id:
            return f
    return None


ARCHIVED_MIN_PLAYERS = 40   # 직전 시즌 기록이 이만큼 이상 있는 리그 = 직전 시즌이 이미 끝나 보관된 리그 (달력형 리그)


def parse(path, due):
    """Dynamic PA parse_save와 같은 순서로 읽되, 보관 시즌 범위를 평가일 기준으로 정한다 (시험 미리보기도 직전 시즌을 보게)"""
    with SaveArchive(path, _NoCancel()) as a:
        lookup = {m.name: m for m in a.members}
        need = ("game_info.dat", "game_db.dat", "rgman/player_stats_hist_ls.dat", "player_stats_hist_dt.cmt")
        if any(x not in lookup for x in need):
            raise H.SaveError("세이브에 과거 시즌 기록 파일이 없어요")
        read = lambda n: b"".join(a.chunks(lookup[n]))
        info, db = read("game_info.dat"), read("game_db.dat")
        setup = H.read_setup(info, db)
        players, _, _ = H.player_records(db)
        from dpa.save_context import read_context
        metadata = read_context(db, players, lambda: None)
        del db
        dt = read("player_stats_hist_dt.cmt")
        lists, free, _ = H.history_lists(read("rgman/player_stats_hist_ls.dat"), dt)
        today = max(date.fromisoformat(setup["game_date"]), date(due.year, 7, 1))   # 보관 시즌 범위: 평가일 연도 기준 지난 3시즌
        by_uid, annual, _ = H.aggregate_history(players, lists, free, dt, today, lambda: None, metadata)
    return {"setup": setup, "players": by_uid, "seasons": annual}


def archived_current(seasons, due):
    """직전 시즌(평가일 연도-1)이 이미 보관된 리그의 선수 기록 {uid: totals} (달력형 리그 보정, 개선안 2)"""
    rows = seasons.get(due.year - 1, {})
    count = {}
    for t in rows.values():
        count[t.get("league")] = count.get(t.get("league"), 0) + 1
    leagues = {lg for lg, n in count.items() if lg and n >= ARCHIVED_MIN_PLAYERS}
    return {str(uid): t for uid, t in rows.items() if t.get("league") in leagues}, len(leagues)


def prior(path, due, rules, cancel=lambda: None):
    """세이브 파일 -> ({uid: [{year, dob, percentile, poor}]}, 직전 보관 시즌 {uid: totals}, 정보)"""
    result = parse(path, due)
    seasons, players = result["seasons"], list(result["players"].values())
    out = {}
    for back in (2, 3):
        year = due.year - back
        rows = seasons.get(year, {})
        eligible = [replace(p, position=rows[p.uid]["position"], league=rows[p.uid]["league"])
                    for p in players if p.uid in rows and rows[p.uid]["dob"] == p.dob]
        strengths = profiles(eligible, rows)
        ranked = dpa_rules.rankings(eligible, rows, date(year + 1, 7, 1), min_peers=MIN_PEERS, shrink_small=True, rules=rules)
        for uid, (p, s, r, pct, peers) in ranked.items():
            league = for_player(p, s, strengths)
            poor = (s["minutes"] >= s["decline_minutes_required"] and s["rated"] >= s["decline_rated_required"]
                    and s.get("comparison_coverage", 1) >= .995
                    and s["raw_rating"] < (league["poor_rating_limit"] if s.get("segment_evaluation")
                                           else rules["poor_rating"] - .12 * max(0, league["league_strength_index"]))
                    and s.get("base_percentile", pct) < rules["poor_percentile"]
                    and (not s["team_comparison_available"] or s["raw_rating"] < s["team_peer_rating"] - .1))
            out.setdefault(str(uid), []).append({"year": year + 1, "dob": p.dob, "percentile": round(pct, 3), "poor": bool(poor)})
    current, n_leagues = archived_current(seasons, due)
    info = {"file": os.path.basename(path), "game_date": result["setup"]["game_date"],
            "season_counts": {str(k): len(v) for k, v in seasons.items() if k in (due.year - 2, due.year - 3)},
            "players": sum(1 for v in out.values() if v), "archived_leagues": n_leagues, "archived_players": len(current)}
    return out, current, info


def load(save_id, due, rules, cache_path, log=lambda m: None):
    """캐시가 맞으면 캐시, 아니면 세이브 파일을 읽는다 -> (prior, current, info). 세이브 파일이 없으면 ({}, {}, None).
    캐시는 cache_path(.pkl): 보관 시즌 기록에 집합(set) 같은 JSON이 아닌 값이 있어 pickle로 남긴다 (모드 자신이 쓴 파일만 읽음)"""
    path = find_save(save_id)
    if not path:
        log("과거 시즌: 세이브 ID %d인 .fm 파일을 찾지 못해 올해 기록만 써요" % save_id)
        return {}, {}, None
    st = os.stat(path)
    key = [os.path.abspath(path), st.st_size, int(st.st_mtime), due.isoformat(), 2]
    try:
        with open(cache_path, "rb") as f:
            c = pickle.load(f)
        if c.get("key") == key:
            return c["prior"], c["current"], c["info"]
    except (OSError, ValueError, EOFError, pickle.UnpicklingError, AttributeError, ImportError):
        pass
    log("과거 시즌: %s 읽는 중 (1~2분)" % os.path.basename(path))
    out, current, info = prior(path, due, rules)
    tmp = cache_path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump({"key": key, "prior": out, "current": current, "info": info}, f)
    for i in range(10):   # Windows: 다른 프로그램이 잠깐 열고 있으면 PermissionError -> 잠깐 기다렸다 다시 (main.replace_retry와 같음)
        try:
            os.replace(tmp, cache_path)
            break
        except PermissionError:
            if i == 9:
                raise
            time.sleep(0.05 * (i + 1))
    log("과거 시즌: %d명 (%s), 직전 시즌이 끝난 리그(달력형) %d개 %d명" % (
        info["players"], ", ".join("%s 시즌 %d명" % kv for kv in sorted(info["season_counts"].items())),
        info["archived_leagues"], info["archived_players"]))
    return out, current, info


def merge(history, prior_rows, due):
    """모드가 직접 남긴 기록(history.json)이 우선. 없는 연도만 세이브 파일 값으로 채운다 -> history.json과 같은 모양"""
    merged = {uid: dict(years) for uid, years in history.items()}
    for uid, rows in prior_rows.items():
        mine = merged.setdefault(uid, {})
        for h in rows:
            y = str(h["year"])
            if y not in mine and int(y) in (due.year - 1, due.year - 2):
                mine[y] = {"dob": h["dob"], "percentile": h["percentile"], "poor": h["poor"], "source": "save"}
    return merged
