# -*- coding: utf-8 -*-
"""포텐 유동 변화: PC 쪽 부분.

흐름
  평가일(기본 7/1)이 지나면 한 번: 게임 쪽에 collect를 시켜 리그 기록을 받고 -> potential.evaluate -> 세이브 폴더에 저장
    -> 반영 방식이 auto면 바로 적용, preview면 모드창에서 사용자가 적용.
  모드창의 "지금 기록으로 미리보기"는 시험용: 오늘 날짜로 평가하고, 다음 해 평가에 쓰는 기록(history.json)에는 남기지 않는다.
세이브 폴더(ctx.save_dir())
  preview.json  마지막 평가 (요약, 모든 선수 결과, 적용 결과)
  history.json  {uid: {평가 연도: {dob, percentile, poor, ca}}} - 다음 해 '최근 3시즌 가중'과 CA 변화에 쓴다
  state.json    {"evaluated": [평가일 ...]} - 같은 평가일을 두 번 하지 않게
  injuries.json {uid: [{start, total, type, seen}]} - 게임 쪽 부상 훑기가 본 부상 (개선안 7)
  savehist.pkl  세이브 파일에서 읽은 지난 2시즌 백분위와 직전 보관 시즌 캐시 (개선안 6·2)
"""
import json
import os
import threading
import time
from datetime import date

import potential
import m24hist as savehist   # 코어 공용 라이브러리 pylib/ (코어 0.18.0, 몸값모드 V06에서 옮김)

_ctx = None
_lock = threading.Lock()
_op = None          # 진행 중인 일: {"kind": "collect", "id", "rows", "due", "official", "started"} / {"kind": "apply", "id", "total", "done", "ok", "fail"}
_last_error = ""
_seq = 0
_phase = ""        # 모드창에 보여 줄 지금 단계 (과거 시즌 읽는 중 등)
_pending = None    # 요청된 평가 (run 스레드가 시작)


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def replace_retry(tmp, path, tries=10):
    """tmp -> path로 바꿔치기. Windows에서는 백신·검색 색인이 파일을 잠깐 열고 있으면 PermissionError가 난다
    (2026-11-13 injuries.json에서 실제로 남) -> 잠깐 기다렸다 다시 (최대 약 3초)."""
    for i in range(tries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(0.05 * (i + 1))


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    replace_retry(tmp, path)


def _path(name):
    d = _ctx.save_dir() if _ctx else None
    return os.path.join(d, name) if d else None


def _today():
    g = _ctx.game() if _ctx else None
    if not g or not g.get("date") or not g.get("save"):
        return None, None
    return date.fromisoformat(g["date"]), g["save"]


def _new_id():
    global _seq
    _seq += 1
    return "%d-%d" % (int(time.time()), _seq)


def _start_collect(due, official, kind="annual"):
    """평가를 요청한다. 실제 시작(세이브 파일 읽기 -> 게임 쪽 자료 모으기)은 run 스레드가 한다 (모드창 호출을 오래 붙잡지 않게).
    kind = annual(1년 평가) / half(반기 점검, 개선안 4). 이미 무언가 하는 중이면 False"""
    global _pending
    with _lock:
        if _op is not None or _pending is not None:
            return False
        _pending = {"due": due.isoformat(), "official": official, "kind": kind}
    return True


def _begin(req):
    """run 스레드: 과거 시즌(세이브 파일) -> 추가로 모을 선수(장기 부상, 달력형 리그) -> 게임 쪽 collect"""
    global _op, _last_error, _phase
    today, save = _today()
    if not save:
        _last_error = "세이브가 없어요"
        return
    due = date.fromisoformat(req["due"])
    st = _ctx.settings()
    prior, current, sh_info = {}, {}, None
    if st.get("use_save_history", True):
        _phase = "과거 시즌을 세이브 파일에서 읽는 중 (처음 한 번 1~2분)"
        try:
            prior, current, sh_info = savehist.load(save["id"], due, potential.dpa_rules.validate(potential.dpa_rules.DEFAULTS),
                                                    _path("savehist.pkl"), _ctx.log)
        except Exception as e:      # 세이브 파일을 못 읽어도 올해 기록만으로 평가는 한다
            _ctx.log("과거 시즌을 읽지 못했어요 (올해 기록만 씀): %s" % e)
    _phase = ""
    extra = set(int(u) for u in current)          # 달력형 리그: 올해 반 시즌 출전이 적어도 직전 1년 기록으로 평가
    if st.get("injury_effect", True) and req["kind"] == "annual":
        inj = _read(_path("injuries.json"), {})
        extra |= {int(u) for u, js in inj.items() if potential.injury_days(js, due) >= potential.INJURY_MIN_DAYS}
    with _lock:
        oid = _new_id()
        _op = {"kind": "collect", "id": oid, "rows": [], "due": req["due"], "official": req["official"], "eval": req["kind"],
               "started": time.time(), "prior": prior, "current": current, "sh_info": sh_info}
    if not _ctx.post({"t": "collect", "id": oid, "extra": sorted(extra)}):
        with _lock:
            _op = None
        _last_error = "게임에 붙어 있지 않아요"
        return
    _ctx.log("자료 모으기 시작 (%s, %s)" % ({"annual": "평가일", "half": "반기 점검"}[req["kind"]] if req["official"] else "시험 미리보기", due))


def _finish_collect(op):
    """자료가 다 왔다 -> 계산 -> 저장 -> (공식이고 auto면) 적용"""
    global _last_error, _phase
    today, save = _today()
    if not save:
        _last_error = "세이브가 없어요"
        return
    due = date.fromisoformat(op["due"])
    half = op.get("eval") == "half"
    hist = _read(_path("history.json"), {})
    st = _ctx.settings()
    t0 = time.time()
    model_hist = savehist.merge(hist, op["prior"], due) if op["prior"] else hist
    _phase = "계산 중"
    injuries = _read(_path("injuries.json"), {}) if st.get("injury_effect", True) and not half else None
    try:
        cup = float(st.get("cup_weight", 0) or 0)
        results, summary = potential.evaluate(op["rows"], due, model_hist, "save%d" % save["id"], st.get("rare_events", True), injuries,
                                              op["current"], max(0.0, min(1.0, cup)), 0.5 if half else 1.0)
    except Exception as e:      # 모델 오류는 기록하고 넘긴다 (run이 죽으면 모드가 다시 시작됨)
        _last_error = "계산 오류: %s" % e
        _ctx.log(_last_error)
        _phase = ""
        return
    _phase = ""
    sh = op.get("sh_info")
    summary["save_file"] = sh["file"] if sh else None
    summary.update(official=op["official"], kind=op.get("eval", "annual"), evaluated_on=today.isoformat() if today else None,
                   save=save["id"], created=time.strftime("%Y-%m-%d %H:%M:%S"), calc_s=round(time.time() - t0, 1),
                   collect_s=round(t0 - op["started"], 1))
    _write(_path("preview.json"), {"summary": summary, "results": results, "applied": {}})
    _ctx.log("평가 끝: 평가 %d명, 오름 %d, 내림 %d, 순변화 %+d, 과거 시즌 반영 %d명, 달력형 리그 %d명, 장기 부상 %d명 (%s)" % (
        summary["evaluated"], summary["up"], summary["down"], summary["net"], summary["history_players"], summary["calendar"],
        summary["injury"], ("반기 점검" if half else "평가일") if op["official"] else "시험"))
    for m in summary["mine"][:10]:                       # 개선안 5: 내 팀 변화는 로그에도
        _ctx.log("내 팀: %s %d → %d (%+d)" % (m["name"], m["old"], m["new"], m["delta"]))
    if op["official"]:
        if not half:
            for uid, h in potential.history_entries(results).items():
                hist.setdefault(uid, {})[str(due.year)] = h
            _write(_path("history.json"), hist)
        stt = _read(_path("state.json"), {"evaluated": []})
        stt["evaluated"] = sorted(set(stt["evaluated"]) | {("half:" if half else "") + op["due"]})
        _write(_path("state.json"), stt)
        if st.get("apply_mode") == "auto":
            _start_apply("all")


def _start_apply(which, uids=None):
    """preview.json의 바뀐 선수 중 아직 적용 안 한 것을 쓴다. which = all / up / down, uids를 주면 그 선수만"""
    global _op, _last_error
    pv = _read(_path("preview.json"), None)
    if not pv:
        _last_error = "미리보기가 없어요"
        return 0
    applied = pv.get("applied", {})
    items = []
    for r in pv["results"]:
        if r["delta"] == 0 or applied.get(str(r["uid"])) == r["new"]:
            continue
        if (which == "up" and r["delta"] < 0) or (which == "down" and r["delta"] > 0):
            continue
        if uids is not None and r["uid"] not in uids:
            continue
        items.append({"u": r["uid"], "v": r["new"], "e": r["old"],
                      "r": "포텐 %s %+d: %s" % (pv["summary"]["due"], r["delta"], r["why"])[:300]})
    if not items:
        return 0
    with _lock:
        if _op is not None:
            _last_error = "다른 작업 중이에요"
            return 0
        oid = _new_id()
        _op = {"kind": "apply", "id": oid, "total": len(items), "done": 0, "ok": 0, "fail": 0, "started": time.time()}
    if not _ctx.post({"t": "apply", "id": oid, "items": items}):
        with _lock:
            _op = None
        _last_error = "게임에 붙어 있지 않아요"
        return 0
    _ctx.log("적용 시작: %d명 (%s)" % (len(items), which))
    return len(items)


def _on_applied(results):
    pv = _read(_path("preview.json"), None)
    if not pv:
        return
    for r in results:
        if r.get("ok"):
            pv["applied"][str(r["u"])] = r.get("after")
    _write(_path("preview.json"), pv)


def _on_injuries(rows):
    path = _path("injuries.json")
    if not path or not rows:
        return
    inj = _read(path, {})
    today, _ = _today()
    keep_from = date(today.year - 2, 1, 1).isoformat() if today else "0000"
    for r in rows:
        lst = [j for j in inj.get(str(r["u"]), []) if j.get("start", "") >= keep_from and j.get("start") != r["start"]]
        lst.append({"start": r["start"], "total": r.get("total"), "type": r.get("type"), "seen": r.get("seen")})
        inj[str(r["u"])] = lst
    _write(path, inj)


def _on_checked(rows):
    """게임의 지금 PA로 적용 표시를 맞춘다 (앱에서 되돌린 선수는 '적용됨'에서 빠짐)"""
    pv = _read(_path("preview.json"), None)
    if not pv:
        return
    want = {str(r["uid"]): r["new"] for r in pv["results"] if r["delta"]}
    for uid, pa in rows:
        k = str(uid)
        if k not in want or pa is None:
            continue
        if pa == want[k]:
            pv["applied"][k] = pa
        else:
            pv["applied"].pop(k, None)
    _write(_path("preview.json"), pv)


def _check_due():
    """평가일이 지났고 이 세이브에서 아직 안 했으면 공식 평가를 시작"""
    today, save = _today()
    if not today:
        return
    st = _ctx.settings()
    try:
        due = potential.due_for(today, int(st.get("eval_month", 7)), int(st.get("eval_day", 1)))
    except ValueError:
        return
    if (today - due).days > 30:          # 평가일에서 한참 지나서 처음 켠 경우: 지난 시즌 기록이 이미 새 시즌으로 바뀌었을 수 있어서 자동으로는 안 한다
        return
    done = _read(_path("state.json"), {"evaluated": []})["evaluated"]
    if due.isoformat() not in done:
        _start_collect(due, True)
        return
    if st.get("half_check", False):              # 개선안 4: 평가일 6개월 뒤 한 번 더 (절반 크기)
        m = due.month + 6
        half = date(due.year + (m - 1) // 12, (m - 1) % 12 + 1, due.day)
        if half <= today and (today - half).days <= 30 and ("half:" + half.isoformat()) not in done:
            _start_collect(half, True, "half")


def run(ctx):
    global _ctx, _op, _pending
    _ctx = ctx
    ctx.log("시작 (모델 %s)" % potential.model_v07.MODEL_VERSION)
    last_check = 0
    while not ctx.stop.is_set():
        req = _pending
        if req is not None and _op is None:
            with _lock:
                _pending = None
            _begin(req)
        m = ctx.recv(0.5)
        if m is None:
            if time.time() - last_check > 5:
                last_check = time.time()
                if _op is None:
                    _check_due()
                elif _op["kind"] == "collect" and time.time() - _op["started"] > 900:
                    ctx.log("자료 모으기가 15분 넘게 끝나지 않아 멈춤")
                    with _lock:
                        _op = None
            continue
        t = m.get("t")
        if t == "injuries":
            _on_injuries(m.get("rows") or [])
            continue
        if t == "checked":
            _on_checked(m.get("rows") or [])
            continue
        op = _op
        if not op or m.get("id") != op["id"]:
            continue
        if t == "rows" and op["kind"] == "collect":
            op["rows"].extend(m.get("rows") or [])
        elif t == "done" and op["kind"] == "collect":
            with _lock:
                _op = None
            _finish_collect(op)
        elif t == "applied" and op["kind"] == "apply":
            res = m.get("results") or []
            op["done"] += len(res)
            op["ok"] += sum(1 for r in res if r.get("ok"))
            op["fail"] += sum(1 for r in res if not r.get("ok"))
            _on_applied(res)
        elif t == "applyDone" and op["kind"] == "apply":
            ctx.log("적용 끝: %d명 바꿈%s%s" % (op["ok"], (", 못 바꾼 선수 %d명" % op["fail"]) if op["fail"] else "", " (멈춤)" if m.get("stopped") else ""))
            with _lock:
                _op = None
    ctx.log("끝")


def status():
    op = _op
    return {"op": op["kind"] if op else None}


# ---- 모드창 ----
def ui_state():
    today, save = _today()
    pv = _read(_path("preview.json"), None) if save else None
    op = _op
    prog = {"kind": "prepare"} if (_pending is not None or (_phase and op is None)) else None
    if op and op["kind"] == "collect":
        prog = {"kind": "collect", "rows": len(op["rows"]), "s": int(time.time() - op["started"])}
    elif op and op["kind"] == "apply":
        prog = {"kind": "apply", "total": op["total"], "done": op["done"], "ok": op["ok"], "fail": op["fail"]}
    st = _ctx.settings() if _ctx else {}
    inj = _read(_path("injuries.json"), {}) if save else {}
    return {"date": today.isoformat() if today else None, "save": save, "op": prog, "error": _last_error, "phase": _phase,
            "injuries": len(inj),
            "mode": st.get("apply_mode"), "evalDay": "%d월 %d일" % (st.get("eval_month", 7), st.get("eval_day", 1)),
            "summary": pv["summary"] if pv else None, "applied": len(pv["applied"]) if pv else 0,
            "pending": sum(1 for r in pv["results"] if r["delta"] and pv["applied"].get(str(r["uid"])) != r["new"]) if pv else 0}


def ui_preview():
    """시험 미리보기: 오늘 날짜로 지금 리그 기록을 평가 (다음 해 기록에는 안 남김)"""
    today, save = _today()
    if not today:
        return {"ok": False, "error": "게임 세이브가 열려 있지 않아요"}
    return {"ok": _start_collect(today, False), "error": _last_error}


def ui_rows(kind="changed", query="", limit=300):
    pv = _read(_path("preview.json"), None)
    if not pv:
        return []
    q = (query or "").strip().lower()
    rows = pv["results"]
    if kind == "up":
        rows = [r for r in rows if r["delta"] > 0]
    elif kind == "down":
        rows = [r for r in rows if r["delta"] < 0]
    elif kind == "changed":
        rows = [r for r in rows if r["delta"]]
    elif kind == "mine":
        rows = [r for r in rows if r.get("mine")]
    if q:
        rows = [r for r in rows if q in r["name"].lower() or q in (r.get("team") or "").lower()]
    rows = sorted(rows, key=lambda r: (-abs(r["delta"]), -r["pct"]))[:max(1, min(2000, int(limit)))]
    ap = pv.get("applied", {})
    return [dict(r, applied=ap.get(str(r["uid"])) == r["new"] and r["delta"] != 0) for r in rows]


def ui_check():
    """바뀐 선수의 지금 PA를 게임에서 읽어 적용 표시를 맞춘다"""
    pv = _read(_path("preview.json"), None)
    if not pv:
        return False
    uids = [r["uid"] for r in pv["results"] if r["delta"]]
    for i in range(0, len(uids), 2000):
        _ctx.post({"t": "check", "id": "check", "uids": uids[i:i + 2000]})
    return True


def ui_apply(which="all", uids=None):
    """which = all / up / down. uids(선수 UID 목록)를 주면 그 선수만 (시험용)"""
    n = _start_apply(which if which in ("all", "up", "down") else "all", set(int(u) for u in uids) if uids else None)
    return {"ok": n > 0, "n": n, "error": _last_error if not n else ""}


def ui_stop():
    op = _op
    if op and op["kind"] == "apply":
        _ctx.post({"t": "stopApply", "id": op["id"]})
        return True
    return False
