"""M24GA 호스트: 게임 찾기 → 빌드 확인 → 코어+모드 묶음 올리기 → 모드 Python 부분 실행. GPL-3.0-or-later.

원래 fm24_ai_mod/launcher.py(소셜피드 24~25번 로그)를 모드 로더용으로 일반화했다 (M24GA M01~M03 로그).

콘솔 사용:
  python -X utf8 loader/host.py           게임을 기다렸다가 자동 연결 (게임 데이터 표는 소셜피드를 처음 볼 때 만든다)
  python -X utf8 loader/host.py --now     이미 세이브 안이면 바로 게임 데이터 표를 만든다
  python -X utf8 loader/host.py --check   연결해서 빌드만 확인하고 끝낸다 (스크립트를 올리지 않음)
  python -X utf8 loader/host.py --once    게임을 끄면 호스트도 끝낸다
  python -X utf8 loader/host.py --list    찾은 모드 목록만 보여 준다
  끝내기: Ctrl+C 또는 ~/m24ga_data/stop.flag 파일 만들기
앱(GUI)에서는 start() / stop() / status() / set_enabled() / reload_mod()를 쓴다.
모드를 켜고 끄면 apply_mods()가 코어 스크립트는 그대로 두고 모드만 내리고 올린다 (M09 핫 리로드, 데이터 표 유지).
기록: ~/m24ga_data/loader.log (게임 안 스크립트 메시지 포함). 모드 자체 기록은 각 모드 데이터 폴더.
"""
import collections
import glob
import hashlib
import itertools
import json
import os
import re
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mods as modlib  # noqa: E402

ROOT = modlib.ROOT
if not modlib.FROZEN:
    sys.path.insert(0, os.path.join(ROOT, "vendor"))   # frida 등은 저장소 vendor/에 (pip install --target vendor frida)

import frida  # noqa: E402

import buildreport  # noqa: E402  (빌드 진단 보고서, M48)
import bundle  # noqa: E402
import health  # noqa: E402
import savedata  # noqa: E402  (세이브별 모드 데이터, 코어 0.44.0)
import panels  # noqa: E402  (게임 안 패널 칸, M44)
import validate as vlib  # noqa: E402

GAME = "fm.exe"
ATTACH_DELAY = 20        # fm.exe가 뜬 뒤 이만큼 기다렸다가 연결 (Denuvo 초기화 중에는 붙지 않는다)
CHECK_RETRY_SEC = 180    # 서명이 안 맞으면 이 시간 동안 10초마다 다시 확인 (코드가 아직 풀리기 전일 수 있다)
STATUS_EVERY = 60        # 콘솔 상태 출력 간격(초)
BUILDS_DIR = os.path.join(ROOT, "builds")
LOG = os.path.join(modlib.DATA, "loader.log")
STOP = os.path.join(modlib.DATA, "stop.flag")

_stop = threading.Event()
_lock = threading.RLock()
_cur = {"session": None, "script": None, "build": None, "info": None, "pid": None, "last": None}   # last = 마지막 빌드 확인 {info, why, ok} (M48 진단 보고서용)
_threads = {"loop": None}
_mods = {"list": [], "errors": [], "loaded": [], "build_off": {}, "src": {}}   # build_off: {모드 id: 빌드가 안 맞는 이유}, src: {모드 id: 올린 JS의 해시}
_runners = {}            # 모드 id -> modlib.PyRunner
# 안전 모드 (M05): 직전 게임이 모드가 올라간 채로 튕겼으면 이번에는 모드를 끈 채 시작한다. allow = 사용자가 하나씩 켠 모드
_safe = {"active": False, "allow": set(), "code": None, "time": "", "mods": []}
# 단계: off / waiting / attaching / checking / hooked / unsupported / error
STATE = {"phase": "off", "detail": "", "build": None, "pid": None}
_console = {"on": False}


def _set(phase, detail=""):
    STATE["phase"], STATE["detail"] = phase, detail


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    if _console["on"]:
        print(line, flush=True)
    os.makedirs(modlib.DATA, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    m = _ID_PREFIX.match(msg)           # "[모드id] ..."로 시작하면 그 모드의 Python 기록 (ctx.log, Python 오류와 스택)
    if m and m.group(1) in _known_ids():
        mod_log(m.group(1), msg[m.end():], "python")


# ---- 모드별 로그 (M06): 모드 상세의 로그 탭 ----
# 모드마다 최근 500개를 메모리에 모은다. JS(api.log, 코어가 알린 오류), Python(ctx.log, 오류 스택), 로더(켬/끔, 자동으로 꺼짐 ...).
# 앱을 다시 켜면 비워진다 (전체 기록은 loader.log).
_ID_PREFIX = re.compile(r"^\[([a-z0-9][a-z0-9_-]*)\] ")
_ERR_RE = re.compile(r"Traceback|오류|[Ee]rror|예외|실패|failed|Exception")
_WARN_RE = re.compile(r"경고|[Ww]arning|WARN")
_MODLOG_MAX = 500
_mod_logs = {}
_mod_log_lock = threading.Lock()
_log_seq = itertools.count(1)


def _known_ids():
    return {m.id for m in _mods["list"]} | set(_runners)


def _level(text):
    return "error" if _ERR_RE.search(text) else ("warn" if _WARN_RE.search(text) else "info")


def mod_log(mod_id, msg, src="loader", lvl=None):
    """모드의 로그 탭에 한 줄(여러 줄도 한 항목) 남긴다. src = js / python / loader, lvl = info / warn / error (없으면 글에서 짐작)."""
    e = {"n": next(_log_seq), "t": time.strftime("%H:%M:%S"), "src": src, "lvl": lvl or _level(str(msg)), "msg": str(msg).rstrip()[:4000]}
    with _mod_log_lock:
        _mod_logs.setdefault(mod_id, collections.deque(maxlen=_MODLOG_MAX)).append(e)


def get_mod_log(mod_id, since=0):
    """since(마지막으로 받은 번호)보다 새 항목들. last = 지금 마지막 번호, errors = 보관 중인 오류 개수."""
    with _mod_log_lock:
        d = list(_mod_logs.get(mod_id, ()))
    return {"entries": [e for e in d if e["n"] > since], "last": d[-1]["n"] if d else since, "errors": sum(e["lvl"] == "error" for e in d)}


def clear_mod_log(mod_id):
    with _mod_log_lock:
        _mod_logs.pop(mod_id, None)


def _log_errors(mod_id):
    with _mod_log_lock:
        return sum(e["lvl"] == "error" for e in _mod_logs.get(mod_id, ()))


def _stopping():
    if os.path.exists(STOP):
        _stop.set()
    return _stop.is_set()


# ---- 모드 ----
def rescan():
    """mods 폴더를 다시 훑는다. 로더가 켜져 있으면 바뀐 모드(새로 생김/없어짐)를 따라 Python과 스크립트도 맞춘다."""
    with _lock:
        _mods["list"], _mods["errors"] = modlib.scan()
        for p, e in _mods["errors"]:
            log("모드 오류: %s: %s" % (p, e))
        for m in _mods["list"]:
            for pr in m.problems:
                log("모드 %s 켤 수 없음: %s" % (m.id, pr))
            for w in m.warnings:
                log("모드 %s 경고: %s" % (m.id, w))
    if running():
        _sync()
    return _mods["list"]


def _sync():
    """실행 중에 모드 목록이 바뀌었을 때(파일을 넣거나 지움): 없어진 모드의 Python을 멈추고, 새 모드를 시작하고, 스크립트를 다시 올린다."""
    for mid in [x for x in _runners if not find_mod(x)]:
        _runners.pop(mid).stop()
        log("모드 %s 파일이 없어져서 멈춤" % mid)
    _start_python()
    with _lock:
        if _cur["script"]:
            apply_mods()     # 켜진 모드가 바뀌었거나 모드 JS가 바뀐 것만 내리고 올린다 (코어와 데이터 표는 그대로)


def find_mod(mod_id):
    return next((m for m in _mods["list"] if m.id == mod_id), None)


def _wanted():
    """켜져 있고 문제없고 자동으로 꺼지지 않은 모드 (빌드 확인 전). 안전 모드면 사용자가 하나씩 켠 것만."""
    w = modlib.active(_mods["list"])
    if _safe["active"]:
        w = [m for m in w if m.id in _safe["allow"]]
    return w


def _python_fatal(mod_id, reason):
    """모드의 Python 부분이 반복해서 오류로 멈췄다: 자동으로 끄고 기록한다."""
    if modlib.auto_disable(mod_id, reason, "python"):
        log("모드 %s를 자동으로 껐습니다 (Python): %s" % (mod_id, reason))
        mod_log(mod_id, "자동으로 껐어요 (Python): %s" % reason, "loader", "error")


def _prepare_data(m):
    """모드 데이터 폴더 준비 (옛 폴더에서 복사해 와야 하면 한 번 복사하고 기록)."""
    try:
        note = modlib.ensure_data(m)
    except OSError as e:
        log("모드 %s 데이터 폴더 준비 실패: %s" % (m.id, e))
        mod_log(m.id, "데이터 폴더를 준비하지 못했어요: %s" % e, "loader", "error")
        return
    if note:
        log("모드 %s: %s" % (m.id, note))
        mod_log(m.id, note, "loader", "info")


def _start_python():
    for m in _wanted():
        _prepare_data(m)
        r = _runners.get(m.id)
        if r is None or (r.mod is not m and not r.running()):   # 다시 훑어 Mod 객체가 바뀌었으면 새 실행기 (돌고 있는 건 그대로)
            r = _runners[m.id] = modlib.PyRunner(m, log, post_to_game, _python_fatal)
        if not r.running():
            r.start()
            if r.running():
                mod_log(m.id, "Python 부분을 시작했어요", "loader", "info")


def _stop_python(mod_id=None):
    for mid in list(_runners):
        if mod_id is None or mid == mod_id:
            _runners[mid].stop()


# ---- 빌드 확인 ----
def load_builds():
    out = []
    for p in sorted(glob.glob(os.path.join(BUILDS_DIR, "*.json"))):
        with open(p, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


SIG_JS = """
var m = Process.getModuleByName('fm.exe'), B = m.base, req = %s;
function hx(off, n) {
  var b = new Uint8Array(B.add(off).readByteArray(n)), s = '';
  for (var i = 0; i < b.length; i++) s += ('0' + b[i].toString(16)).slice(-2);
  return s;
}
var out = { size: m.size, path: m.path, sig: {}, vt: {} };
req.sig.forEach(function (o) { try { out.sig[o] = hx(parseInt(o), 16); } catch (e) { out.sig[o] = 'ERR'; } });
req.vt.forEach(function (o) { try { out.vt[o] = B.add(parseInt(o)).readPointer().sub(B).toString(16); } catch (e) { out.vt[o] = 'ERR'; } });
send(out);
"""


def _mod_entries(build, mods_list):
    """{모드 id: [{"sig", "vt"}, ...]} - 빌드 파일 "mods" 구역 + 모드 안 builds/*.json 중 이 빌드 것."""
    out = {}
    for mid, e in (build.get("mods") or {}).items():
        out.setdefault(mid, []).append(e)
    for m in mods_list:
        for e in m.build_entries():
            if e.get("build") == build["name"]:
                out.setdefault(m.id, []).append(e)
    return out


def read_signature(session, builds, mods_list):
    sig, vt = set(), set()
    for b in builds:
        sig |= set(b["sig"]) | set(b.get("hook_guard") or {})
        vt |= set(b["vt"])
        for es in _mod_entries(b, mods_list).values():
            for e in es:
                sig |= set(e.get("sig") or {})
                vt |= set(e.get("vt") or {})
    res = {}
    sc = session.create_script(SIG_JS % json.dumps({"sig": sorted(sig), "vt": sorted(vt)}))
    sc.on("message", lambda m, d: res.update(m.get("payload") or {"error": m}))
    sc.load()
    sc.unload()
    return res


def _bad(info, e):
    bad = [o for o, v in (e.get("sig") or {}).items() if info["sig"].get(o) != v]
    bad += ["vt " + o for o, v in (e.get("vt") or {}).items() if info["vt"].get(o) != v]
    return bad


def match_build(info, builds):
    """(빌드 dict 또는 None, 이유)"""
    if "error" in info:
        return None, "서명 읽기 실패: %s" % info["error"]
    reasons = []
    for b in builds:
        bad = _bad(info, b)
        if b.get("module_size") and info.get("size") != b["module_size"]:
            bad.append("module_size %s" % info.get("size"))
        if not bad:
            for o, v in (b.get("hook_guard") or {}).items():
                if info["sig"].get(o) != v:   # 훅 자리가 원래 바이트와 다르면 다른 도구가 이미 훅을 올린 상태
                    return None, "다른 도구가 이미 훅을 올려 둔 것 같다 (%s가 원래 바이트가 아님). 그쪽을 먼저 내려 주세요." % o
            return b, "ok"
        reasons.append("%s: 다름 %s" % (b["name"], ", ".join(bad)))
    return None, "; ".join(reasons) or "지원 빌드 목록이 비어 있음"


def match_mods(info, build, mods_list):
    """{모드 id: 이유} - 모드 전용 주소가 이 빌드와 안 맞는 모드. 전용 주소가 없는 모드는 통과."""
    entries = _mod_entries(build, mods_list)
    off = {}
    for m in mods_list:
        own = any(e.get("build") for e in m.build_entries())
        es = entries.get(m.id)
        if not es:
            if own:
                off[m.id] = "이 게임 빌드(%s)용 주소가 없음" % build["name"]
            continue
        bads = [_bad(info, e) for e in es]
        if all(bads):
            off[m.id] = "모드 주소가 다름: " + ", ".join(bads[0])
    for m in mods_list:      # 기능 등록부 (M10): 모드가 쓰는 기능이 이 빌드에서 안 되면 끈다
        un = modlib.caps.unsupported(m.caps, build.get("name"))
        if un and m.id not in off:
            off[m.id] = "이 게임 빌드(%s)에서 지원하지 않는 기능: %s" % (build.get("name"), ", ".join(un))
    return off


# ---- 게임 안 스크립트 ----
_postlock = threading.Lock()


def post_to_game(mod_id, obj):
    """모드 Python -> 그 모드 JS (api.recv). 스크립트가 안 올라가 있거나 끊겼으면 False."""
    sc = _cur["script"]
    if not sc:
        return False
    try:
        with _postlock:
            sc.post({"type": "m24ga", "m": mod_id, "d": obj})
        return True
    except Exception:  # noqa: BLE001  (연결 끊김, 스크립트 내려가는 중 등)
        return False


def _clean_stack(msg):
    """JS 스택에서 Frida 내부 줄(/frida/runtime/..., (native))을 뺀다. 모드 코드의 줄만 남겨 로그와 AI 보고서를 짧게 한다."""
    return "\n".join(ln for ln in str(msg).splitlines() if "/frida/runtime/" not in ln and "(native)" not in ln)


def _core_notice(n):
    """코어가 보낸 모드 오류 알림: error는 기록만, disabled(오류 반복)/loadfail(로드 실패)은 그 모드를 자동으로 끈다."""
    t, mid = n.get("t"), n.get("id")
    where, msg = n.get("where"), _clean_stack(n.get("msg", ""))
    if t == "error":
        log("game: [%s] %s 오류: %s" % (mid, where, msg.splitlines()[0] if msg else ""))
        mod_log(mid, "%s 오류: %s" % (where, msg), "js", "error")
    elif t == "write":                    # 모드가 게임 값을 바꿈 (M14, modhost.js m24gaWrite)
        _write_notice(n)
    elif t == "inbox":                    # 모드가 받은 편지함에 메일을 넣음 (코어 0.34.0, modhost.js m24gaInbox)
        mod_log(mid, "받은 편지함 메일: '%s' (본문 %s자, 게임 날짜 %s)" % (n.get("title", ""), n.get("chars", 0), n.get("date") or "-"), "loader")
    elif t == "action":                   # 모드가 게임 액션을 실행함 (코어 0.41.0, modhost.js m24gaAction)
        what = "%s %s (대상 dref %s, 이벤트 %s)" % (n.get("action"), n.get("cls") or "", n.get("target"), n.get("event"))
        mod_log(mid, ("게임 액션 실행: " + what + ", 게임 날짜 %s" % (n.get("date") or "-")) if n.get("ok") else ("게임 액션 거절: %s: %s" % (n.get("action"), n.get("error"))), "loader")
    elif t == "game":                     # 게임 날짜·세이브가 바뀜 (M12, modhost.js m24gaPollGame)
        _game_notice(n.get("date"), n.get("save"))
        _sd_game(n.get("save"))
    elif t == "saving":                   # 게임 저장 시작 (코어 0.44.0): 이 동안의 nonce 변화는 되돌리지 않는다
        savedata.STORE.on_saving()
    elif t == "saved":                    # 게임 저장 끝: 모드 데이터 작업본 -> 확정본
        k = savedata.STORE.on_saved(n.get("save"))
        if k:
            log("모드 데이터 확정 (세이브 %s): 모드 %d개" % ((n.get("save") or {}).get("id"), k))
    elif t == "sd":                       # 모드 JS가 api.saveData.set/del
        okk, why = savedata.STORE.set(mid, n.get("k"), n.get("v"), bool(n.get("del")), n.get("save"))
        if not okk:
            mod_log(mid, "세이브 데이터 쓰기 거절: %s" % why, "loader", "error")
    elif t in ("disabled", "loadfail"):
        what = "mod.js를 불러오지 못함" if t == "loadfail" else "게임 쪽 코드가 5초에 25번 넘게 오류(%s)" % where
        reason = "%s: %s" % (what, msg.splitlines()[0] if msg else "")
        if t == "loadfail":
            mod_log(mid, "올라가다 예외: %s" % msg, "js", "error")
        if modlib.auto_disable(mid, reason, "js"):
            log("모드 %s를 자동으로 껐습니다 (JS): %s" % (mid, reason))
            mod_log(mid, "자동으로 껐어요 (JS): %s" % reason, "loader", "error")
            threading.Thread(target=_stop_python, args=(mid,), daemon=True).start()   # 메시지 스레드를 막지 않게


def on_message(m, data):
    if m.get("type") == "send":
        p = m.get("payload")
        if isinstance(p, dict) and "m24" in p:       # 모드 JS -> 모드 Python (api.send)
            r = _runners.get(p["m24"])
            if r:
                r.deliver(p.get("d"))
            return
        if isinstance(p, dict) and "m24core" in p:   # 코어가 모드의 오류를 알려 줌 (core.js m24gaModError / registerMod)
            _core_notice(p["m24core"])
            return
        if isinstance(p, str):                       # 게임 쪽 글: "[모드id] ..."(api.log), "mod loaded: id", "mod load failed: id ..."
            mm = _ID_PREFIX.match(p)
            if mm and mm.group(1) in _known_ids():
                mod_log(mm.group(1), p[mm.end():], "js")
            else:
                mm = re.match(r"^mod loaded: (\S+)$", p)
                if mm:
                    mod_log(mm.group(1), "게임 쪽 부분이 올라갔어요", "js", "info")
        log("game: %s" % p)
    elif m.get("type") == "error":
        log("game 오류: %s" % (m.get("stack") or m.get("description")))


def _targets(session):
    """지금 게임에 올라가 있어야 할 모드와 그 JS 조각: [(Mod, src)]. 빌드가 안 맞는 모드는 빼고(build_off에 기록),
    모드마다 문법만 먼저 검사해서 틀린 모드는 자동으로 끈다 (모드 하나의 문법 오류가 코어와 다른 모드를 막지 않게). _lock 안에서."""
    wanted = _wanted()
    _mods["build_off"] = match_mods(_cur["info"], _cur["build"], wanted)
    for mid, why in _mods["build_off"].items():
        if mid not in _mods["loaded"]:
            log("모드 %s는 이 빌드에서 끕니다: %s" % (mid, why))
            mod_log(mid, "이 게임 빌드에서는 올리지 않아요: %s" % why, "loader", "warn")
    out = []
    for m in wanted:
        if m.id in _mods["build_off"]:
            continue
        _prepare_data(m)
        src = bundle.mod_source(m)
        try:
            session.compile_script(src)
        except Exception as e:  # noqa: BLE001
            reason = "mod.js 문법 오류: %s" % str(e).splitlines()[0][:200]
            if modlib.auto_disable(m.id, reason, "js"):
                log("모드 %s를 자동으로 껐습니다 (올리기 전 검사): %s" % (m.id, reason))
                mod_log(m.id, "자동으로 껐어요 (올리기 전 검사): %s" % reason, "loader", "error")
            _stop_python(m.id)
            continue
        out.append((m, src))
    return out


def _src_hash(src):
    return hashlib.sha1(src.encode("utf-8")).hexdigest()


def _load_script():
    """코어 + 지금 켜진 모드로 묶음을 만들어 올린다 (_lock 안에서). 게임에 처음 붙을 때와 reload()에서만 쓴다.
    모드를 켜고 끌 때는 apply_mods()가 코어를 그대로 두고 모드만 바꾼다 (M09 핫 리로드)."""
    session = _cur["session"]
    targets = _targets(session)
    src, loaded = bundle.build([m for m, _ in targets], exe=((_cur.get("last") or {}).get("info") or {}).get("path"))
    script = session.create_script(src)
    script.on("message", on_message)
    # load() 도중에 모드 JS가 보낸 hello에 모드 Python이 바로 답하므로, 올리기 전에 등록해 둔다 (안 그러면 post_to_game이 그 답을 버린다)
    _cur["script"] = script
    savedata.STORE.need_push = True   # 새 코어에는 모드 데이터 거울이 없다 -> 다음 'game' 알림 때 다시 보냄
    try:
        script.load()
    except Exception:
        _cur["script"] = None
        raise
    _mods["loaded"] = loaded
    _mods["src"] = {m.id: _src_hash(bundle.mod_source(m, settings=False)) for m, js in targets}   # apply_mods와 같은 열쇠 (설정 값 뺌, V08)
    health.session_set_mods(STATE.get("pid"), loaded, _safe["active"])   # 게임이 튕기면 어떤 모드가 올라가 있었는지 알기 위해
    log("스크립트 올림: 코어 + %s%s" % (", ".join(loaded) or "모드 없음", " (안전 모드)" if _safe["active"] else ""))
    for mid in loaded:
        mod_log(mid, "게임에 올렸어요 (코어 %s)%s" % (modlib.CORE_VERSION, ", 안전 모드" if _safe["active"] else ""), "loader", "info")


def apply_mods(force=()):
    """켜진 모드 목록이나 모드 코드가 바뀌었을 때: **코어 스크립트와 데이터 표는 그대로 두고** 모드만 내리고 올린다 (M09 핫 리로드).
    - 꺼진 모드: 게임 쪽 부분을 내린다 (등록한 이벤트·상태·메시지 수신을 떼고 api.onUnload를 부른다)
    - 새로 켠 모드, JS가 바뀐 모드(새 버전 설치, 개발 폴더에서 고침), force에 든 모드: 다시 올린다
    코어가 동적 적재를 모르거나(옛 코어) rpc가 실패하면 예전처럼 스크립트를 통째로 다시 올린다. 반환: 무언가 했으면 True."""
    with _lock:
        sc, session = _cur["script"], _cur["session"]
        if not sc or not session or not _cur["build"]:
            return False
        targets = _targets(session)
        want = {m.id: src for m, src in targets}
        changed = False
        try:
            x = sc.exports_sync
            for mid in [i for i in _mods["loaded"] if i not in want]:
                x.unloadmod(mid)
                _mods["loaded"].remove(mid)
                _mods["src"].pop(mid, None)
                log("모드 %s의 게임 쪽 부분을 내렸습니다 (코어와 데이터 표는 그대로)" % mid)
                mod_log(mid, "게임 쪽 부분을 내렸어요", "loader", "info")
                changed = True
            for m, src in targets:
                h = _src_hash(bundle.mod_source(m, settings=False))   # 설정 값은 빼고 본다 (설정은 save_settings가 rpc로 알림, V08)
                if m.id in _mods["loaded"] and _mods["src"].get(m.id) == h and m.id not in force:
                    continue
                again = m.id in _mods["loaded"]
                r = x.loadmod(m.id, src) or {}
                changed = True
                if r.get("ok"):
                    if not again:
                        _mods["loaded"].append(m.id)
                    _mods["src"][m.id] = h
                    log("모드 %s를 게임에 %s (코어와 데이터 표는 그대로)" % (m.id, "다시 올렸습니다" if again else "올렸습니다"))
                    mod_log(m.id, "게임에 %s (코어 %s, 데이터 표는 그대로)" % ("다시 올렸어요" if again else "올렸어요", modlib.CORE_VERSION), "loader", "info")
                else:   # init에서 던졌으면 코어가 loadfail을 알려 자동으로 꺼진다
                    if again:
                        _mods["loaded"].remove(m.id)
                    _mods["src"].pop(m.id, None)
                    log("모드 %s를 올리지 못했습니다: %s" % (m.id, r.get("error")))
                    mod_log(m.id, "게임에 올리지 못했어요: %s" % _clean_stack(r.get("error", "")), "js", "error")
        except Exception as e:  # noqa: BLE001  (옛 코어라 loadmod가 없음, 스크립트가 죽음 등)
            log("모드만 바꾸지 못해서 스크립트를 통째로 다시 올립니다: %r" % e)
            return reload()
        if changed:
            health.session_set_mods(STATE.get("pid"), list(_mods["loaded"]), _safe["active"])
        return changed


def reload_mod(mod_id):
    """모드 하나의 게임 쪽 부분을 지금 파일 내용으로 다시 올린다 (개발용 핫 리로드). 반환: 했으면 True."""
    if not running() or not find_mod(mod_id):
        return False
    rescan()
    return apply_mods(force=(mod_id,))


# ---- 게임 값 쓰기 기록과 되돌리기 (M14) ----
# ~/m24ga_data/writes.jsonl 한 줄 = 쓰기 한 번 {n, time, mod, field, key, name, from, to, save:{id,nonce}, date, reason}
# 되돌린 것은 {undo: n, time, ok, error} 줄을 더한다 (원래 줄은 고치지 않는다).
_wlock = threading.Lock()


def _writes_path():
    return os.path.join(modlib.DATA, "writes.jsonl")


def _append_write(rec):
    with _wlock:
        os.makedirs(modlib.DATA, exist_ok=True)
        with open(_writes_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _read_writes():
    try:
        with open(_writes_path(), encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]
    except (OSError, ValueError):
        return []


def _write_notice(n):
    rows = _read_writes()
    rec = {"n": 1 + max([r.get("n", 0) for r in rows] or [0]), "time": time.strftime("%Y-%m-%d %H:%M:%S"), "mod": n.get("id"),
           "field": n.get("field"), "key": n.get("key"), "name": n.get("name", ""), "from": n.get("from"), "to": n.get("to"),
           "save": n.get("save"), "date": n.get("date"), "reason": n.get("reason", "")}
    _append_write(rec)
    msg = "게임 값을 바꿨어요: %s %s(%s) %s → %s%s" % (rec["field"], rec["name"] or "", rec["key"], rec["from"], rec["to"],
                                                ("  (이유: %s)" % rec["reason"]) if rec["reason"] else "")
    log("모드 %s %s" % (rec["mod"], msg))
    mod_log(rec["mod"], msg, "loader", "warn")


def write_log(mod_id=None, save_id=None):
    """쓰기 기록 (최근 것 먼저). 되돌린 것은 undone=True. save_id를 주면 그 세이브의 것만."""
    rows = _read_writes()
    undone = {r["undo"]: r for r in rows if "undo" in r and r.get("ok")}
    out = []
    for r in rows:
        if "undo" in r:
            continue
        if mod_id and r.get("mod") != mod_id:
            continue
        if save_id is not None and (r.get("save") or {}).get("id") != save_id:
            continue
        out.append(dict(r, undone=r["n"] in undone))
    return out[::-1]


def undo_writes(mod_id):
    """지금 세이브에서 그 모드가 바꾼 값을 최근 것부터 되돌린다. 지금 값이 모드가 쓴 값일 때만 되돌린다.
    반환 {ok, done, skipped:[{n, name, error}], error}."""
    save = modlib.GAME.get("save")
    sc = _cur["script"]
    if not sc or not save:
        return {"ok": False, "error": "게임에 붙어 있고 세이브를 불러온 상태에서만 되돌릴 수 있어요"}
    todo = [r for r in write_log(mod_id, save.get("id")) if not r["undone"] and (r.get("save") or {}).get("nonce") == save.get("nonce")]
    done, skipped = 0, []
    for r in todo:                     # write_log는 최근 것이 먼저
        try:
            res = sc.exports_sync.undowrite(r["field"], r["key"], r["from"], r["to"]) or {}
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": repr(e)}
        _append_write({"undo": r["n"], "time": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": bool(res.get("ok")), "error": res.get("error")})
        if res.get("ok"):
            done += 1
        else:
            skipped.append({"n": r["n"], "name": r.get("name"), "error": res.get("error")})
    log("모드 %s 쓰기 되돌리기: %d개 되돌림, %d개 건너뜀" % (mod_id, done, len(skipped)))
    mod_log(mod_id, "바꾼 값 되돌리기: %d개 되돌림%s" % (done, (", %d개는 지금 값이 달라서 건너뜀" % len(skipped)) if skipped else ""), "loader", "info")
    return {"ok": True, "done": done, "skipped": skipped}


def _game_notice(date, save):
    """코어가 알린 게임 날짜·세이브를 기억한다 (모드 Python의 ctx.game(), 앱 홈 표시)."""
    old = modlib.GAME.get("save")
    modlib.GAME.update(date=date, save=save if isinstance(save, dict) else None)
    if (old or {}).get("id") != (save or {}).get("id") or (old or {}).get("nonce") != (save or {}).get("nonce"):
        if save:
            log("세이브 확인: id %s, nonce %s, 게임 날짜 %s" % (save.get("id"), save.get("nonce"), date))
        else:
            log("세이브 없음 (메인 메뉴 등)")


def _sd_game(save):
    """세이브가 바뀌면 모드 데이터 작업본을 정하고 게임 쪽 거울을 다시 보낸다 (코어 0.44.0)"""
    act = savedata.STORE.on_game(save)
    if act == "load":
        snap = savedata.STORE.snapshot()
        post_to_game("__sd", dict(op="load", **snap))
        if snap["save"]:
            log("모드 데이터 불러옴 (세이브 %s, nonce %s): 모드 %d개" % (snap["save"].get("id"), snap["save"].get("nonce"), len(snap["all"])))


def sd_set_from_python(mod_id, key, value=None, delete=False):
    """ctx.save_data().set/delete -> 작업본 + 게임 쪽 거울"""
    okk, why = savedata.STORE.set(mod_id, key, value, delete)
    if okk:   # 큰 값(MIRROR_MAX 넘음)은 PC 쪽 전용: 게임 쪽 거울에서는 지운다
        big = not delete and not savedata.STORE.mirrorable(mod_id, key)
        post_to_game("__sd", {"op": "set", "id": mod_id, "k": key, "v": None if (delete or big) else value, "del": bool(delete or big)})
    return okk, why


modlib.SD["set"] = sd_set_from_python
modlib.SD["get"] = savedata.STORE.get


def _unload_script():
    sc = _cur["script"]
    _cur["script"] = None
    modlib.GAME.update(date=None, save=None)
    if sc:
        try:   # 감시(watch-write)의 예외 처리기가 남은 채 내리면 frida-agent가 튕긴다 (M21, 0xc0000409). 먼저 푼다
            r = sc.exports_sync.prepareunload()
            if r and r.get("watch"):
                log("스크립트를 내리기 전에 메모리 감시를 풀었어요")
        except Exception:  # noqa: BLE001
            pass
        try:
            sc.unload()
        except Exception:  # noqa: BLE001
            pass
        log("스크립트 내림")


def reload(start_maps=None):
    """켜진 모드 목록이 바뀌었을 때: 스크립트를 내렸다가 다시 묶어 올린다 (게임 재시작 불필요, 데이터 표는 다시 만든다).
    start_maps=None이면 이전 스크립트가 표를 만들기 시작했을 때만 바로 다시 만든다."""
    with _lock:
        if not _cur["session"] or not _cur["build"]:
            return False
        if start_maps is None:
            st = hook_status() or {}
            start_maps = bool(st.get("mapsStarted"))
        _unload_script()
        _load_script()
        if start_maps:
            _cur["script"].exports_sync.startmaps()
            log("게임 데이터 표 다시 만들기 시작")
    return True


def grant_permissions(mod_id):
    """모드가 필요한 위험 기능을 모두 허용하고 켠다 (앱의 '허용하고 켜기')."""
    m = find_mod(mod_id)
    if not m:
        return False
    need = m.needs_permission()
    if need:
        modlib.grant(mod_id, need)
        log("모드 %s 권한 허용: %s" % (mod_id, ", ".join(need)))
        mod_log(mod_id, "사용자가 권한을 허용했어요: %s" % ", ".join(need), "loader", "info")
    set_enabled(mod_id, True)
    return True


def set_enabled(mod_id, on):
    """GUI의 켜고 끄기. 실행 중이면 그 모드의 Python 부분을 켜거나 끄고 스크립트를 다시 올린다."""
    modlib.set_enabled(mod_id, on)
    if on and modlib.clear_auto_disabled(mod_id):     # 오류로 자동으로 꺼졌던 모드를 사용자가 다시 켰다
        log("모드 %s의 자동 꺼짐 기록을 지웠습니다" % mod_id)
        mod_log(mod_id, "자동으로 꺼진 기록을 지우고 다시 켰어요", "loader", "info")
    if _safe["active"]:                               # 안전 모드에서는 켠 모드만 하나씩 올린다 (어느 모드가 문제인지 찾기)
        (_safe["allow"].add if on else _safe["allow"].discard)(mod_id)
    log("모드 %s %s" % (mod_id, "켬" if on else "끔"))
    mod_log(mod_id, "사용자가 %s" % ("켰어요" if on else "껐어요"), "loader", "info")
    if not running():
        return
    if on:
        _start_python()
    else:
        _stop_python(mod_id)
    apply_mods()


def install_mod(path):
    """.24mod 파일 설치 (검사 -> mods 폴더에 복사 -> 다시 훑기). 반환은 modlib.install과 같고 restart_needed가 더해진다."""
    with _lock:
        r = modlib.install(path, _mods["list"])
        if not r["ok"]:
            log("모드 설치 안 함: %s (%s)" % (path, r["error"]))
            return r
        log("모드 설치: %s %s%s" % (r["id"], r["version"], (" (옛 버전 %s를 바꿈)" % r["replaced"]) if r["replaced"] else ""))
        had_python = r["id"] in _runners
        was_loaded = r["id"] in _mods["loaded"]
        rescan()
        mod_log(r["id"], "설치했어요 (v%s)%s" % (r["version"], (", 옛 버전 v%s를 바꿨어요" % r["replaced"]) if r["replaced"] else ""), "loader", "info")
        r["restart_needed"] = False
        if r["replaced"] and running():
            if had_python:
                r["restart_needed"] = True       # 돌고 있는 Python 코드는 import된 채라 새 버전으로 바꾸려면 앱을 다시 켜야 한다
                log("모드 %s: 새 버전의 Python 부분은 앱을 다시 켜면 적용됩니다" % r["id"])
            elif was_loaded:
                apply_mods()
    return r


def uninstall_mod(mod_id):
    """설치한 .24mod를 지운다 (휴지통 폴더로 옮김). 켜져 있으면 Python을 멈추고 게임 쪽도 내린다. 데이터 폴더와 설정은 남긴다."""
    with _lock:
        m = find_mod(mod_id)
        if not m:
            return {"ok": False, "error": "모르는 모드"}
        if mod_id in _runners and not modlib.removable(m):
            return {"ok": False, "error": "개발 폴더 모드나 mods 폴더 밖의 모드는 앱에서 지우지 않아요. 직접 지워 주세요: %s" % m.path}
        if mod_id in _runners:
            _runners.pop(mod_id).stop()
        r = modlib.uninstall(m)
        if not r["ok"]:
            log("모드 삭제 안 함: %s (%s)" % (mod_id, r["error"]))
            return r
        modlib.clear_auto_disabled(mod_id)
        modlib.revoke(mod_id)          # 같은 id로 다른 모드를 깔았을 때 옛 허용이 넘어가지 않게
        log("모드 삭제: %s -> %s" % (mod_id, r["trash"]))
        mod_log(mod_id, "삭제했어요 (파일은 %s 로 옮겼어요)" % r["trash"], "loader", "info")
        rescan()
    return r


def _apply_pending_crash():
    """직전 게임이 모드가 올라간 채 튕겼으면 안전 모드를 건다 (한 번만. 걸면 그 기록은 확인한 것으로 친다)."""
    c = health.pending_crash()
    if not c:
        return False
    _safe.update(active=True, allow=set(), code=c["code"], time=c["time"], mods=list(c["mods"]))
    health.acknowledge_crash()
    log("직전 게임이 비정상 종료됐습니다 (%s, %s). 올라가 있던 모드: %s -> 이번에는 모드를 끈 채 시작합니다 (안전 모드)" % (
        health.code_text(c["code"]), c["time"], ", ".join(c["mods"])))
    for mid in c["mods"]:
        mod_log(mid, "직전 게임이 비정상 종료됐을 때(%s, %s) 올라가 있었어요. 안전 모드라 이번에는 올리지 않아요" % (health.code_text(c["code"]), c["time"]), "loader", "warn")
    return True


def check_last_crash():
    """앱이나 로더를 시작할 때: 직전 게임이 튕겼는지 확인해서 안전 모드를 건다. 걸었으면 True."""
    return _apply_pending_crash()


def leave_safe_mode():
    """안전 모드를 끝내고 켜 둔 모드를 모두 올린다."""
    if not _safe["active"]:
        return False
    _safe.update(active=False, allow=set())
    log("안전 모드를 끝냅니다: 켜 둔 모드를 올립니다")
    if running():
        _start_python()
        apply_mods()
    return True


def safe_info():
    """GUI용: 안전 모드 상태 (없으면 None)."""
    if not _safe["active"]:
        return None
    names = {m.id: m.name for m in _mods["list"]}
    return {"code": health.code_text(_safe["code"]), "time": _safe["time"], "mods": [names.get(i, i) for i in _safe["mods"]],
            "allowed": sorted(_safe["allow"])}


def run_session(pid, now=False, check_only=False, console=False):
    """연결해서 스크립트를 올리고, 게임이 꺼지거나 멈추라고 할 때까지 기다린다. 반환: 'exited' / 'stopped' / 'unsupported' / 'checked'"""
    _set("checking", "게임 버전 확인 중")
    session = frida.get_local_device().attach(pid)
    watch = health.ProcWatch(pid)         # 게임이 끝난 뒤 종료 코드를 읽어 튕겼는지 알기 위해
    detached = threading.Event()
    session.on("detached", lambda reason, crash=None: (log("연결 끊김: %s" % reason), detached.set()))
    _cur["session"] = session
    builds = load_builds()
    t0 = time.time()
    while True:
        info = read_signature(session, builds, _wanted())
        build, why = match_build(info, builds)
        if build or time.time() - t0 > CHECK_RETRY_SEC or _stopping() or detached.is_set() or check_only:
            break
        log("버전 확인 대기 (%s) - 10초 뒤 다시" % why)
        time.sleep(10)
    log("fm.exe: %s, 모듈 크기 %s" % (info.get("path"), info.get("size")))
    _cur["last"] = {"info": info, "why": why, "ok": bool(build)}
    if info.get("path"):
        modlib.GAME_DIR["dir"] = os.path.dirname(info["path"])   # 모드 ctx.game_dir() (코어 0.31.0)
    if not build:
        log("지원하지 않는 게임 빌드라 스크립트를 올리지 않습니다: %s" % why)
        _set("unsupported", why)
        try:
            p = save_build_report()
            log("빌드 진단 보고서를 저장했습니다: %s (앱의 '빌드 진단 보고서' 또는 cli.py build-report)" % p)
        except Exception as e:  # noqa: BLE001
            log("빌드 진단 보고서 저장 실패: %r" % e)
        try:
            session.detach()
        except frida.InvalidOperationError:
            pass
        _cur["session"] = None
        watch.close()
        return "unsupported"
    log("지원 빌드 확인: %s" % build["name"])
    STATE["build"] = build["name"]
    if check_only:
        off = match_mods(info, build, _wanted())
        for mid, w in off.items():
            log("모드 %s: %s" % (mid, w))
        session.detach()
        _cur["session"] = None
        watch.close()
        return "checked"
    with _lock:
        _cur["build"], _cur["info"] = build, info
        _load_script()
    _set("hooked")
    if now:
        _cur["script"].exports_sync.startmaps()
        log("게임 데이터 표 만들기 시작 (1~2분)")
    else:
        log("스크립트 로드 완료. 소셜피드를 처음 열 때 게임 데이터 표를 만든다 (1~2분)")
    last = time.time()
    while not detached.is_set() and not _stopping():
        time.sleep(0.5)
        if console and time.time() - last >= STATUS_EVERY:
            last = time.time()
            st = hook_status()
            if st:
                log("상태: %s" % json.dumps(st, ensure_ascii=False))
    if _stop.is_set():
        unload()
        watch.close()
        health.session_end(None, "loader-stopped")      # 우리가 먼저 껐으니 게임이 튕겼는지는 모른다
        return "stopped"
    with _lock:
        _cur.update(script=None, session=None, build=None, info=None)
    code = watch.wait_code(5.0)                          # 게임이 끝났다: 종료 코드로 튕겼는지 확인
    watch.close()
    s = health.session_end(code, "game-exit")
    if health.is_crash(code):
        log("게임이 비정상 종료했습니다 (종료 코드 %s)" % health.code_text(code))
        if _apply_pending_crash():     # 로더는 계속 켜져 있으니 다음 게임 시작에 대비해 바로 안전 모드를 건다
            _stop_python()
    else:
        log("게임 종료 (종료 코드 %s)" % health.code_text(code))
    return "exited"


BUILD_REPORT = os.path.join(modlib.DATA, "build_report.txt")


def build_report():
    """마지막으로 확인한 게임 빌드의 진단 보고서 글. 아직 게임에 붙은 적이 없으면 None."""
    last = _cur["last"]
    if not last:
        return None
    build = _cur["build"]
    off = _mods["build_off"] if build else None
    rows = [{"id": m.id, "version": m.manifest.get("version"), "state": (_mods["build_off"].get(m.id) and "빌드 안 맞음") or "ok"} for m in _mods["list"]] if build else None
    return buildreport.build_text(last["info"], last["why"], load_builds(), modlib.CORE_VERSION, off, rows, func_lines=_func_lines(last["info"]))


def _func_lines(info):
    """M57: 함수 등록부 서명 확인 + 클래스 기반 찾기. RTTI 표 캐시가 있을 때만 클래스 기반까지 (없으면 처음 30초 걸려서)."""
    exe = (info or {}).get("path")
    if not exe or not os.path.exists(exe):
        return None
    try:
        import funcmap
        rtti = funcmap._rtti()
        deep = os.path.exists(rtti.cache_path(os.path.getsize(exe)))
        with open(bundle.FUNCS_JSON, encoding="utf-8") as f:
            funcs = json.load(f)["functions"]
        lines = funcmap.summary(funcs, exe, deep)
        if not deep:
            lines.append("클래스 기반 찾기는 RTTI 표가 있어야 해요 (cli.py classes . 한 번 실행 → 다시 보고서)")
        return lines
    except Exception as e:  # noqa: BLE001
        return ["확인 실패: %r" % e]


def save_build_report():
    text = build_report()
    if text is None:
        return None
    os.makedirs(modlib.DATA, exist_ok=True)
    with open(BUILD_REPORT, "w", encoding="utf-8") as f:
        f.write(text)
    return BUILD_REPORT


def hook_status():
    sc = _cur["script"]
    if not sc:
        return None
    try:
        return sc.exports_sync.status()
    except Exception:  # noqa: BLE001  (게임이 막 꺼진 경우, 다시 올리는 중 등)
        return None


def explore(spec, frm=0, size=0x200):
    """게임 객체 탐색 (M19, CLI explore): 코어 rpc explore를 부른다. 게임에 안 붙어 있으면 오류 dict."""
    sc = _cur["script"]
    if not sc:
        return {"error": "게임에 연결돼 있지 않아요 (cli.py start --now --wait 60)"}
    try:
        return sc.exports_sync.explore(spec, frm, size)
    except Exception as e:  # noqa: BLE001
        return {"error": "탐색 실패: %s" % e}


def save_settings(mod, changes):
    """모드 설정 저장(modlib.save_settings) + 게임에 올라가 있는 모드의 JS에 새 값 알리기 (api.onSettings, M23).
    반환은 modlib.save_settings와 같다 (검사에 걸린 {key: 이유})."""
    errs = modlib.save_settings(mod, changes)
    if len(errs) < len(changes) and _cur["script"]:
        try:
            _cur["script"].exports_sync.setsettings(mod.id, bundle.game_settings(mod))
        except Exception:  # noqa: BLE001  (게임이 막 꺼졌거나 모드가 안 올라가 있음: 다음에 올릴 때 새 값이 들어간다)
            pass
    return errs


def rpc(name, *args):
    """코어 rpc 하나 부르기 (M21 개발 도구용). 게임에 안 붙어 있거나 실패하면 {"error"}."""
    sc = _cur["script"]
    if not sc:
        return {"error": "게임에 연결돼 있지 않아요 (cli.py start --now --wait 60)"}
    try:
        return getattr(sc.exports_sync, name)(*args)
    except Exception as e:  # noqa: BLE001
        return {"error": "%s 실패: %s" % (name, e)}


modlib.RPC["fn"] = lambda name, *args: rpc(name, *args) if name in ("props", "actionsfor", "actionrun", "propset", "propsset") else {"error": "모드가 부를 수 없는 rpc: %s" % name}   # ctx.props (코어 0.39.0), ctx.actions_for / ctx.action (0.41.0), ctx.set_prop (0.42.0)


def getfield(spec, name):
    """필드 하나 읽기 (M20, CLI get): 코어 rpc getfield."""
    sc = _cur["script"]
    if not sc:
        return {"error": "게임에 연결돼 있지 않아요 (cli.py start --now --wait 60)"}
    try:
        return sc.exports_sync.getfield(spec, name)
    except Exception as e:  # noqa: BLE001
        return {"error": "읽기 실패: %s" % e}


def unload():
    with _lock:
        se = _cur["session"]
        _unload_script()
        _cur.update(session=None, build=None, info=None)
        if se:
            try:
                se.detach()
            except Exception:  # noqa: BLE001
                pass


def find_pid():
    for p in frida.get_local_device().enumerate_processes():
        if p.name.lower() == GAME:
            return p.pid
    return None


def alive(pid):
    return any(p.pid == pid for p in frida.get_local_device().enumerate_processes())


def run_loop(now=False, check_only=False, once=False, console=False):
    """게임을 기다렸다가 붙는 반복. 멈추라고 하거나(_stop) once/check일 때 끝난다."""
    waiting_logged = False
    if not check_only:   # M44: 게임 안 패널 칸 파일. 게임이 켜질 때 목록을 읽으므로 게임보다 먼저 만들어 둔다
        pr = panels.ensure_slots()
        if pr["created"]:
            log("게임 안 패널 칸을 만들었어요 (%s)%s" % (pr["dir"], ". 게임이 이미 켜져 있으면 다시 켜야 게임 안 패널을 쓸 수 있어요" if find_pid() else ""))
        elif not pr["ok"]:
            log("게임 안 패널 칸을 만들지 못했어요: %s" % pr["error"])
    while not _stopping():
        pid = find_pid()
        STATE["pid"] = pid
        if not pid:
            if check_only:
                log("fm.exe가 실행 중이 아닙니다")
                return 1
            if not waiting_logged:
                log("fm.exe 실행을 기다립니다")
                waiting_logged = True
            _set("waiting", "게임을 기다리는 중")
            time.sleep(2)
            continue
        just_started = waiting_logged
        waiting_logged = False
        started = time.time()
        if just_started:
            log("fm.exe 발견 (pid %d). %d초 뒤 연결" % (pid, ATTACH_DELAY))
            while time.time() - started < ATTACH_DELAY and not _stopping() and alive(pid):
                _set("attaching", "게임이 켜졌어요. %d초 뒤 연결" % max(0, int(ATTACH_DELAY - (time.time() - started))))
                time.sleep(1)
        if _stopping() or not alive(pid):
            continue
        r = run_session(pid, now=now, check_only=check_only, console=console)
        if r in ("checked", "stopped"):
            return 0
        now = False
        if r == "unsupported":
            log("게임이 꺼질 때까지 기다립니다")
        while alive(pid) and not _stopping():
            time.sleep(2)
        if once:
            return 0
        log("게임 종료. 다음 실행을 기다립니다")
    return 0


# ---- 앱용 ----
def running():
    t = _threads["loop"]
    return bool(t and t.is_alive())


def start(now=None):
    """켜기: 모드를 다시 훑고, 켜진 모드의 Python 부분을 실행하고, 게임을 기다렸다가 붙는다.
    now=None이면 게임이 이미 켜져 있을 때 바로 표를 만든다."""
    if running():
        return
    _stop.clear()
    if os.path.exists(STOP):
        os.remove(STOP)
    log("M24GA 시작 (코어 %s)" % modlib.CORE_VERSION)
    rescan()
    check_last_crash()
    if now is None:
        now = find_pid() is not None
    _set("waiting", "시작하는 중")
    _start_python()

    def loop():
        try:
            run_loop(now=now)
        except Exception as e:  # noqa: BLE001
            log("호스트 오류: %r" % e)
            _set("error", str(e)[:200])
            unload()
            return
        _set("off")

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    _threads["loop"] = t


def stop():
    """끄기: 스크립트를 내리고 모드 Python 부분을 멈춘다."""
    _stop.set()
    t = _threads["loop"]
    if t:
        t.join(15)
    _threads["loop"] = None
    _stop_python()
    unload()
    if STATE["phase"] != "error":
        _set("off")


def mod_states():
    """GUI 모드 목록용: 모드마다 info + 상태(running/off/build/problem/error)."""
    hook = _mods["loaded"] if _cur["script"] else []
    out = []
    for m in _mods["list"]:
        d = m.info()
        r = _runners.get(m.id)
        d["python_running"] = bool(r and r.running())
        d["python_error"] = r.error if r else None
        d["build_off"] = _mods["build_off"].get(m.id) if _cur["build"] else None
        d["log_errors"] = _log_errors(m.id)
        held = _safe["active"] and d["enabled"] and m.id not in _safe["allow"] and not d["auto_disabled"]
        if m.problems:
            d["state"] = "problem"
        elif d["auto_disabled"]:           # 오류가 반복돼서 자동으로 꺼짐 (스위치로 다시 켜면 기록이 지워진다)
            d["state"], d["enabled"] = "auto_off", False
        elif held:                         # 안전 모드: 켜 둔 모드지만 이번에는 올리지 않음 (스위치를 켜면 이 모드만 올린다)
            d["state"], d["enabled"] = "safe", False
        elif not d["enabled"]:
            d["state"] = "off"
        elif d["needs_perm"]:              # 켜 두었지만 위험 기능(pc, raw, hook, write)을 아직 허용하지 않음 (M10)
            d["state"] = "perm"
        elif d["build_off"]:
            d["state"] = "build"
        elif d["python_error"]:
            d["state"] = "error"
        elif m.id in hook:
            d["state"] = "running"
        else:
            d["state"] = "ready"
        out.append(d)
    return out


STATE_LABEL = {"running": "실행 중", "ready": "준비됨(게임 대기)", "off": "꺼짐", "build": "이 게임 빌드와 안 맞음", "problem": "켤 수 없음",
               "error": "Python 오류", "auto_off": "오류가 반복돼서 자동으로 꺼짐", "safe": "안전 모드라 올리지 않음",
               "perm": "권한 허용 필요"}
SRC_LABEL = {"js": "JS", "python": "PY", "loader": "로더"}
LVL_LABEL = {"error": "[오류]", "warn": "[경고]", "info": ""}


def format_log_entry(e):
    return "[%s][%s]%s %s" % (e["t"], SRC_LABEL.get(e["src"], e["src"]), LVL_LABEL.get(e["lvl"], ""), e["msg"])


def mod_report(mod_id, lines=60):
    """AI에게 붙여 넣을 모드 상태 보고서: 상태, 자동으로 꺼진 이유, 검사 결과, 최근 로그."""
    m = find_mod(mod_id)
    if not m:
        return ""
    st = next((x for x in mod_states() if x["id"] == mod_id), {})
    out = ["# M24GA 모드 상태 보고", "",
           "AI에게: 아래는 사용자의 M24GA 모드 상태예요. 먼저 M24GA의 docs/AI_GUIDE.md를 읽고 원인을 찾아 고쳐 주세요. "
           "코어에 없는 기능이 필요하면 지어내지 말고 없다고 말해 주세요. 고친 뒤에는 tools/m24.py validate를 돌려 보세요.", "",
           "## 모드",
           "- 이름: %s (id: %s, 버전 %s)" % (m.name, m.id, m.version),
           "- 위치: %s (%s)" % (m.path, ".24mod 파일" if m.kind == "file" else "개발 폴더"),
           "- 상태: %s" % STATE_LABEL.get(st.get("state"), st.get("state")),
           "- 코어 버전: %s / 모드가 요구하는 코어: %s" % (modlib.CORE_VERSION, m.manifest.get("core") or "없음"),
           "- 게임 빌드: %s / 로더 상태: %s" % (STATE.get("build") or "연결 안 됨", STATE.get("phase"))]
    ad = st.get("auto_disabled")
    if ad:
        out.append("- 자동으로 꺼짐 (%s, %s): %s" % (ad.get("time"), "Python 부분" if ad.get("source") == "python" else "게임 쪽 코드", ad.get("reason")))
    if st.get("build_off"):
        out.append("- 이 게임 빌드에서 꺼 둠: %s" % st["build_off"])
    if st.get("python_error"):
        out.append("- Python 오류: %s" % st["python_error"])
    for p in m.problems:
        out.append("- 켤 수 없는 이유: %s" % p)
    out.append("- 기능 (mod.json capabilities%s): %s" % ("" if "capabilities" in m.manifest else " 선언 없음, 코드에서 찾음",
                                                       ", ".join(m.caps) or "없음"))
    if m.needs_permission():
        out.append("- 사용자가 아직 허용하지 않은 기능: %s" % ", ".join(m.needs_permission()))
    if _safe["active"]:
        out.append("- 안전 모드: 직전 게임이 비정상 종료돼서(%s) 모드를 끈 채 시작함" % health.code_text(_safe["code"]))
    try:
        rep = vlib.validate(m.path)
        txt = vlib.format_text(rep).splitlines()
        out += ["", "## 검사 결과 (tools/m24.py validate)"] + txt[:60] + (["... (%d줄 더)" % (len(txt) - 60)] if len(txt) > 60 else [])
    except Exception as e:  # noqa: BLE001
        out += ["", "## 검사 결과", "검사하지 못함: %r" % e]
    with _mod_log_lock:
        entries = list(_mod_logs.get(mod_id, ()))[-lines:]
    out += ["", "## 최근 로그 (마지막 %d개, 앱을 켠 뒤의 기록)" % len(entries)]
    out += [format_log_entry(e) for e in entries] or ["(아직 기록이 없어요)"]
    return "\n".join(out)


def mod_call(mod_id, name, args):
    """모드창 → 모드 Python의 ui_<name>(*args). 반환: {"ok": True, "result": ..} / {"ok": False, "error": ..}"""
    r = _runners.get(mod_id)
    if not r or not r.running():
        return {"ok": False, "error": "모드가 실행 중이 아니에요. 홈에서 M24GA를 켜 주세요"}
    try:
        return {"ok": True, "result": r.call_ui(name, args)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}


def mod_status(mod_id):
    """모드 Python 부분의 status() 결과 (없으면 None)."""
    r = _runners.get(mod_id)
    return r.status() if r else None


def status():
    st = dict(STATE)
    st["running"] = running()
    st["hook"] = hook_status()
    st["mods"] = mod_states()
    st["errors"] = [[p, e] for p, e in _mods["errors"]]
    st["game"] = dict(modlib.GAME)
    return st


def main(argv):
    _console["on"] = True
    if "--list" in argv:
        rescan()
        print("mods 폴더:", modlib.mod_dirs())
        for d in mod_states():
            print("%-20s %-8s %-8s %s" % (d["id"], d["version"], d["state"], d["path"]))
        return 0
    now, check_only, once = "--now" in argv, "--check" in argv, "--once" in argv
    if os.path.exists(STOP):
        os.remove(STOP)
    log("M24GA 시작 (코어 %s, 콘솔)" % modlib.CORE_VERSION)
    rescan()
    if not check_only:
        check_last_crash()
        _start_python()
    try:
        return run_loop(now=now, check_only=check_only, once=once, console=True)
    except KeyboardInterrupt:
        log("Ctrl+C - 종료합니다")
    finally:
        _stop.set()
        _stop_python()
        unload()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
