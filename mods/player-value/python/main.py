# -*- coding: utf-8 -*-
"""몸값 보정 (player-value) PC 쪽: 기능 B 활약 배율. GPL-3.0-or-later

흐름 (설정 perf_enabled가 켜졌을 때만)
  게임 날짜가 7일 넘게 지났거나 처음이거나 설정이 바뀌면 한 번:
    1) 지난 2시즌 백분위: 세이브 파일(.fm)을 m24hist(공용 pylib)로 읽음. 시즌마다 한 번만 (pv_prior.pkl, 세이브 ID + 시즌 열쇠)
    2) 게임 쪽에 collect -> 이번 시즌 리그 기록 rows
    3) pvperf.factors -> 게임 쪽에 factors (api.scale('player.value') 표에 넣음)
  꺼지면 게임 쪽에 clear.
세이브 폴더(ctx.save_dir())
  pv_prior.pkl  지난 시즌 백분위 캐시 / savehist.pkl  m24hist 자체 캐시 / perf.json  마지막 계산 요약과 내 팀 배율
"""
import json
import os
import pickle
import threading
import time
from datetime import date

import pvperf

_ctx = None
_lock = threading.Lock()
_op = None            # {"id", "rows", "started", "prior", "due_year", "strength", "key"}
_last = None          # 마지막으로 반영한 {"date", "save", "strength"}
_summary = None
_cleared = True
_seq = 0
_phase = ""


def _path(name):
    d = _ctx.save_dir() if _ctx else None
    return os.path.join(d, name) if d else None


def _write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    for i in range(10):   # Windows: 백신·색인이 잠깐 열고 있으면 PermissionError
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == 9:
                raise
            time.sleep(0.05 * (i + 1))


def _season_due(today):
    """이번 시즌이 끝나는 해의 7/1 (7월부터 새 시즌)"""
    return date(today.year + 1 if today.month >= 7 else today.year, 7, 1)


def _prior(save_id, due):
    """지난 2시즌 백분위. 지난 시즌은 바뀌지 않으므로 세이브 ID + 시즌으로만 캐시 (세이브할 때마다 다시 읽지 않게)"""
    cache = _path("pv_prior.pkl")
    key = [save_id, due.isoformat(), 1]
    try:
        with open(cache, "rb") as f:
            c = pickle.load(f)
        if c.get("key") == key:
            return c["prior"]
    except (OSError, ValueError, EOFError, pickle.UnpicklingError, AttributeError, ImportError):
        pass
    try:
        import m24hist                     # 공용 라이브러리 pylib (코어 0.18.0)
        from dpa import rules as dpa_rules
        prior, _, info = m24hist.load(save_id, due, dpa_rules.validate(dpa_rules.DEFAULTS), _path("savehist.pkl"), _ctx.log)
    except Exception as e:  # noqa: BLE001  세이브를 못 읽어도 이번 시즌 기록만으로 한다
        _ctx.log("지난 시즌을 읽지 못해 이번 시즌 기록만 써요: %r" % e)
        return {}
    if info:                               # 파일을 찾았을 때만 캐시 (없으면 다음에 다시 찾음)
        tmp = cache + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump({"key": key, "prior": prior}, f)
        os.replace(tmp, cache)
    return prior


def _num(v, default):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return default


def _honours(sid, due, latest=None):
    """수상(award_year_hist)과 우승(comp_history x 선수 시즌 기록) -> (수상 기록, {사람 번호: 수상}, {UID: 우승}). 못 읽으면 None.
    우승 계산은 game_db를 읽어 1분 안팎 -> 세이브 파일이 바뀔 때만 (m24awards 캐시)"""
    global _phase
    try:
        import m24awards                    # 공용 라이브러리 pylib (코어 0.19.0)
        _phase = "수상·우승 기록 읽는 중"
        aw = m24awards.load(sid, _path("pv_awards.pkl"), _ctx.log)
        extra = {}
        for comp, start, team in latest or ():   # V16: 게임 메모리의 최근 시즌 우승 (세이브 대회 기록에 아직 없음)
            extra.setdefault((team, start), []).append(comp)
        tr = m24awards.load_trophies(sid, due.year - 4, _path("pv_trophies.pkl"), _ctx.log, extra)
    except Exception as e:  # noqa: BLE001  영예 보너스만 빠지고 나머지는 한다
        _ctx.log("수상·우승 기록을 읽지 못해 영예 보너스는 빼요: %r" % e)
        return None
    if not aw:
        return None
    return aw["records"], m24awards.by_person(aw["records"]), (tr or {}).get("by_uid", {})


def _settings():
    st = _ctx.settings()
    try:
        s = float(st.get("perf_strength", 0.25))
    except (TypeError, ValueError):
        s = 0.25
    return bool(st.get("perf_enabled", False)), (max(0.05, min(0.6, s)), st.get("perf_league", True) is not False, _num(st.get("perf_intl"), 0.5), min(0.15, _num(st.get("perf_caps"), 0.05)), min(0.15, _num(st.get("perf_honours"), 0.05)))


def _due_now():
    """지금 계산해야 하면 (오늘, 세이브 id, 세기), 아니면 None"""
    global _cleared
    g = _ctx.game()
    if not g or not g.get("date") or not g.get("save"):
        return None
    on, strength = _settings()
    if not on:
        if not _cleared:              # 표는 비우지 않는다: 게임 쪽이 표를 꺼 두고(enable false), 다시 켜면 그대로 쓴다
            _cleared = True
            _ctx.log("활약 배율 끔 (게임 계산에서 빠짐, 다시 켜면 마지막 배율로)")
        return None
    _cleared = False
    today = date.fromisoformat(g["date"])
    sid = g["save"]["id"]
    last = _last
    if last and last["save"] == sid and last["strength"] == strength and 0 <= (today - last["date"]).days < 7:
        return None
    return today, sid, strength


def _begin(today, sid, strength):
    global _op, _phase, _seq
    due = _season_due(today)
    _phase = "지난 시즌 읽는 중 (처음 한 번 1~2분)"
    prior = _prior(sid, due)
    _phase = "이번 시즌 기록 모으는 중"
    _seq += 1
    oid = "%d-%d" % (int(time.time()), _seq)
    with _lock:
        _op = {"id": oid, "rows": [], "started": time.time(), "prior": prior, "due_year": due.year, "strength": strength, "latest": [], "sid": sid, "due": due,
               "today": today, "save": sid}
    if not _ctx.post({"t": "collect", "id": oid}):
        with _lock:
            _op = None
        _phase = ""


def _finish(op):
    global _last, _summary, _cleared, _phase
    _phase = "계산 중"
    t0 = time.time()
    strength, league, intl, caps, hcap = op["strength"]
    hon = None
    honours = _honours(op["sid"], op["due"], op.get("latest")) if hcap > 0 else None
    if honours:
        recs, by_link, by_uid = honours
        ca = {r[12]: r[9] for r in op["rows"] if len(r) > 12 and r[12] is not None and r[9]}
        ca_uid = {r[0]: r[9] for r in op["rows"] if r[9]}
        hon = (by_link, by_uid, pvperf.award_prestige(recs, ca), pvperf.trophy_prestige(by_uid, ca_uid))
    fs, summary = pvperf.factors(op["rows"], op["prior"], op["due_year"], strength, league, intl, caps, hon, hcap)
    names = {r[0]: r[8] for r in op["rows"] if len(r) > 8 and r[7]}
    mine = sorted(([names[u], fs.get(u, 1.0)] for u in names), key=lambda x: -x[1])
    summary.update(date=op["today"].isoformat(), calc_s=round(time.time() - t0, 2), collect_s=round(t0 - op["started"], 1),
                   prior_players=len(op["prior"]), mine=mine[:40])
    items = sorted(fs.items())
    _ctx.post({"t": "clear"})
    for i in range(0, len(items), 2000):
        _ctx.post({"t": "factors", "id": op["id"], "rows": items[i:i + 2000], "last": i + 2000 >= len(items)})
    if not items:
        _ctx.post({"t": "factors", "id": op["id"], "rows": [], "last": True})
    _cleared = False
    _last = {"date": op["today"], "save": op["save"], "strength": op["strength"]}
    _summary = summary
    try:
        _write_json(_path("perf.json"), summary)
    except OSError as e:
        _ctx.log("perf.json을 쓰지 못함: %r" % e)
    _ctx.log("활약 배율: 선수 %d명 중 %d명 (오름 %d, 내림 %d), 이번 시즌 %d명 / 지난 시즌 %d명 / 그 전 %d명, 세기 ±%d%%, 리그 수준 %s, 국가대표 %d명(비율 %.1f), 통산 보너스 %d명(최대 +%d%%), 영예 보너스 %d명(최대 +%d%%)" % (
        summary["players"], summary["scaled"], summary["up"], summary["down"], summary["with_current"], summary["with_last"],
        summary["with_before"], round(summary["strength"] * 100), ("%d개 리그" % summary["leagues"]) if league else "끔", summary["intl_players"], intl, summary["caps_players"], round(caps * 100), summary["honours_players"], round(hcap * 100)))
    for n, f in mine[:5] + [m for m in mine[-3:] if m not in mine[:5]]:
        _ctx.log("내 팀: %s ×%.3f" % (n, f))
    _phase = ""


def run(ctx):
    global _ctx, _op, _last, _phase
    _ctx = ctx
    ctx.log("시작")
    last_check = 0
    while not ctx.stop.is_set():
        m = ctx.recv(0.5)
        if m is None:
            if time.time() - last_check > 5:
                last_check = time.time()
                if _op is None:
                    go = _due_now()
                    if go:
                        _begin(*go)
                elif time.time() - _op["started"] > 600:
                    ctx.log("이번 시즌 기록 모으기가 10분 넘게 끝나지 않아 멈춤")
                    with _lock:
                        _op = None
                    _phase = ""
            continue
        t = m.get("t") if isinstance(m, dict) else None
        if t == "reloaded":               # 게임 쪽이 다시 올라왔다 (표가 비었음) -> 다시 계산
            _last = None
            continue
        op = _op
        if not op or m.get("id") != op["id"]:
            continue
        if t == "latest":
            op["latest"].extend(m.get("rows") or [])
        elif t == "rows":
            op["rows"].extend(m.get("rows") or [])
        elif t == "done":
            with _lock:
                _op = None
            _finish(op)
    ctx.log("끝")


def status():
    on = _ctx is not None and _settings()[0]
    s = _summary or {}
    return {"활약_배율": ("켬" if on else "끔") + (" (%s)" % _phase if _phase else ""),
            "활약_배율_선수": s.get("scaled", 0), "활약_계산일": s.get("date")}
