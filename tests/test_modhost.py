"""core/modhost.js 시험: 게임 없이 frida로 빈 Python 프로세스에 붙여 모드를 올리고 내린다 (핫 리로드, M09).

  python -X utf8 -W error::ResourceWarning -m unittest discover -s tests
frida가 없으면 건너뛴다.
"""
import json
import os
import subprocess
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor"))
try:
    import frida
except ImportError:      # pragma: no cover
    frida = None

# 시험용: modhost.js 뒤에 붙이는 부분 (게임 코어 대신 이벤트를 쏘고 상태를 본다)
HARNESS = """
rpc.exports = {
  load: function (id, src) { return m24gaLoadMod(id, src); },
  unload: function (id) { return m24gaUnloadMod(id); },
  mods: function () { return M24GA.mods; },
  emit: function (ev, arg) { m24gaEmit(ev, arg); return true; },
  counts: function () { var o = {}; for (var ev in M24GA.on) o[ev] = M24GA.on[ev].length; o.status = Object.keys(M24GA.statusFns).length; o.recv = Object.keys(M24GA.recvFns).length; return o; },
  status: function () { var s = {}; for (var id in M24GA.statusFns) { var m = M24GA.statusFns[id](); for (var k in m) s[k] = m[k]; } return s; },
  fakeWriter: function () {
    M24GA_VALS = { 7: 140 };
    M24GA.writers['player.pa'] = { write: function (k, v, expect) {
      if (!(k in M24GA_VALS)) return { ok: false, error: 'no player' };
      var cur = M24GA_VALS[k];
      if (expect !== undefined && expect !== null && cur !== expect) return { ok: false, error: 'expect', before: cur };
      if (cur === v) return { ok: true, before: cur, after: cur, same: true, name: 'P' + k };
      M24GA_VALS[k] = v; return { ok: true, before: cur, after: v, name: 'P' + k };
    } };
    return true;
  },
  fakeField: function () {   // 필드 등록부 쓰기 시험 (M20): x.f = 실수 필드(기능 write.field), x.ro = 읽기만
    M24GA_VALS = { 7: 0 };
    M24GA.writers['x.f'] = { cap: 'write.field', float: true, write: function (k, v, expect) {
      var cur = M24GA_VALS[k]; if (cur === v) return { ok: true, before: cur, after: cur, same: true }; M24GA_VALS[k] = v; return { ok: true, before: cur, after: v, name: 'X' + k }; } };
    M24GA.fieldKind = function (n) { return { 'x.f': 'x', 'x.ro': 'x' }[n] || null; };
    M24GA.fieldKey = function (obj, kind) { return 7; };
    return true;
  },
  fakeHooks: function () {   // 함수 끼어들기 시험 (M22): f.x = 모드용, f.core = 코어 전용
    M24GA_HK = { install: 0, release: 0 };
    M24GA.funcInfo = function (n) { return { 'f.x': { hook: 'observe' }, 'f.core': { owner: 'core', event: 'frame' } }[n] || null; };
    M24GA.hookInstall = function (n) { M24GA_HK.install++; return { ok: true }; };
    M24GA.hookRelease = function (n) { M24GA_HK.release++; };
    return true;
  },
  fire: function (n) { var ev = { name: n, args: [1], data: {} }; m24gaHookCall(n, 'before', ev); ev.ret = 7; m24gaHookCall(n, 'after', ev); return ev.data; },
  hk: function () { return { hk: M24GA_HK, n: (M24GA.hooks['f.x'] || []).length, stats: m24gaHookStats() }; },
  setSettings: function (id, v) { return m24gaSetSettings(id, v); },
  vals: function () { return M24GA_VALS; },
  setRate: function (n) { M24_WRITE_MAX_PER_MIN = n; return true; },
  undo: function (f, k, from, to) { return m24gaUndoWrite(f, k, from, to); },
  setGame: function (raw, sid, nonce) { M24GA_FAKE = { date: raw, save: sid ? { id: sid, nonce: nonce } : null }; M24GA.readGame = function () { return M24GA_FAKE; }; return true; },
  poll: function () { m24gaPollGame(); return M24GA.game; },
  decode: function (raw) { return m24gaDecodeDate(raw); },
  liveDate: function () { return [gameDate(), saveInfo()]; },
  timers: function () { var n = 0; for (var k in M24GA.timers) n += M24GA.timers[k].length; return n; },
  callStale: function () { M24GA_STALE.log('stale'); M24GA_STALE.send({ x: 1 }); M24GA_STALE.on('frame', function () {}); return M24GA_STALE.alive(); }
};
var M24GA_STALE = null, M24GA_FAKE = null, M24GA_VALS = {}, M24GA_HK = {};
"""


def mod_src(mid, body, caps=None, settings=None):
    meta = {} if caps is None else {"caps": caps}
    if settings is not None:
        meta["settings"] = settings
    tail = (", " + json.dumps(meta)) if meta else ""
    return "registerMod(%s, function (api) {\n%s\n}%s);" % (json.dumps(mid), body, tail)


COUNTER = """
var n = 0;
api.on('frame', function () { n++; });
api.status(function () { return { %(k)s: n }; });
api.recv(function (m) { api.send({ echo: m }); });
api.onUnload(function () { api.log('bye'); globalThis.UNLOADED_%(v)s = (globalThis.UNLOADED_%(v)s || 0) + 1; });
api.log('hello ' + n);
"""


@unittest.skipIf(frida is None, "frida 없음")
class ModHost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        time.sleep(0.5)
        cls.session = frida.get_local_device().attach(cls.proc.pid)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.session.detach()
        finally:
            cls.proc.kill()
            cls.proc.wait()

    def setUp(self):
        with open(os.path.join(ROOT, "core", "modhost.js"), encoding="utf-8") as f:
            src = f.read()
        self.msgs, self.lock = [], threading.Lock()
        self.script = self.session.create_script(src + HARNESS)
        self.script.on("message", self._on)
        self.script.load()
        self.x = self.script.exports_sync

    def tearDown(self):
        self.script.unload()

    def _on(self, m, data):
        with self.lock:
            self.msgs.append(m.get("payload") if m["type"] == "send" else ("ERROR", m.get("description")))

    def wait_for(self, pred, timeout=3.0):
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                hit = [m for m in self.msgs if pred(m)]
            if hit:
                return hit
            time.sleep(0.02)
        self.fail("메시지가 안 옴. 받은 것: %r" % self.msgs)

    def test_load_emit_unload_and_reload(self):
        r = self.x.load("a", mod_src("a", COUNTER % {"k": "na", "v": "a"}))
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.x.mods(), ["a"])
        for _ in range(3):
            self.x.emit("frame", None)
        self.assertEqual(self.x.status()["na"], 3)
        self.wait_for(lambda m: m == "[a] hello 0")
        # 메시지: 호스트 -> 모드 recv -> api.send
        self.script.post({"type": "m24ga", "m": "a", "d": {"q": 1}})
        self.wait_for(lambda m: isinstance(m, dict) and m.get("m24") == "a" and m["d"] == {"echo": {"q": 1}})
        # 내리기: 등록한 것이 모두 떨어지고 onUnload가 불린다
        self.assertTrue(self.x.unload("a"))
        self.wait_for(lambda m: m == "[a] bye")
        self.wait_for(lambda m: m == "mod unloaded: a")
        self.assertEqual(self.x.mods(), [])
        self.assertEqual(self.x.counts(), {"socialPanel": 0, "frame": 0, "dateChanged": 0, "saveLoaded": 0, "status": 0, "recv": 0})
        self.assertFalse(self.x.unload("a"))          # 두 번 내려도 괜찮다
        # 다시 올리면 상태가 새로 시작한다 (모드 JS의 변수는 새로)
        self.assertTrue(self.x.load("a", mod_src("a", COUNTER % {"k": "na", "v": "a"}))["ok"])
        self.x.emit("frame", None)
        self.assertEqual(self.x.status()["na"], 1)

    def test_load_same_id_replaces_old_version(self):
        self.x.load("a", mod_src("a", COUNTER % {"k": "v1", "v": "a"}))
        r = self.x.load("a", mod_src("a", COUNTER % {"k": "v2", "v": "a"}))
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.x.mods(), ["a"])
        self.assertEqual(self.x.counts()["frame"], 1)      # 옛 버전의 핸들러가 남지 않는다
        st = self.x.status()
        self.assertIn("v2", st)
        self.assertNotIn("v1", st)
        self.wait_for(lambda m: m == "[a] bye")             # 옛 버전의 onUnload가 불렸다

    def test_other_mods_untouched(self):
        self.x.load("a", mod_src("a", COUNTER % {"k": "na", "v": "a"}))
        self.x.load("b", mod_src("b", COUNTER % {"k": "nb", "v": "b"}))
        self.x.unload("a")
        self.x.emit("frame", None)
        self.assertEqual(self.x.mods(), ["b"])
        self.assertEqual(self.x.status(), {"nb": 1})

    def test_dead_api_does_nothing(self):
        self.x.load("a", mod_src("a", "M24GA_STALE = api;"))
        self.x.unload("a")
        with self.lock:
            self.msgs.clear()
        self.assertFalse(self.x.call_stale())
        time.sleep(0.2)
        with self.lock:
            self.assertEqual([m for m in self.msgs if m == "[a] stale" or (isinstance(m, dict) and m.get("m24"))], [])
        self.assertEqual(self.x.counts()["frame"], 0)

    def test_syntax_error_and_init_throw(self):
        r = self.x.load("bad", "registerMod('bad', function (api) { var = ; });")
        self.assertFalse(r["ok"])
        self.assertIn("SyntaxError", r["error"])
        r = self.x.load("boom", mod_src("boom", "api.on('frame', function () {}); throw new Error('init boom');"))
        self.assertFalse(r["ok"])
        self.wait_for(lambda m: isinstance(m, dict) and m.get("m24core", {}).get("t") == "loadfail")
        self.assertEqual(self.x.mods(), [])
        self.assertEqual(self.x.counts()["frame"], 0)       # 하다 만 등록을 거뒀다

    def test_error_watch_then_reload_resets(self):
        self.x.load("e", mod_src("e", "api.on('frame', function () { throw new Error('x'); });"))
        for _ in range(30):
            self.x.emit("frame", None)
        self.wait_for(lambda m: isinstance(m, dict) and m.get("m24core", {}).get("t") == "disabled")
        # 같은 id를 다시 올리면 오류 횟수가 새로 시작해서 콜백이 다시 불린다
        self.x.load("e", mod_src("e", "var n = 0; api.on('frame', function () { n++; }); api.status(function () { return { ne: n }; });"))
        self.x.emit("frame", None)
        self.assertEqual(self.x.status()["ne"], 1)

    # ---- M12: 타이머, 게임 날짜·세이브 ----
    def test_every_after_and_cleanup_on_unload(self):
        body = """
var ticks = 0, once = 0;
api.every(50, function () { ticks++; });
api.after(60, function () { once++; });
var s = api.every(50, function () {}); s.stop();
api.status(function () { return { ticks: ticks, once: once }; });
"""
        self.assertTrue(self.x.load("t", mod_src("t", body))["ok"])
        time.sleep(0.5)
        st = self.x.status()
        self.assertGreaterEqual(st["ticks"], 4)
        self.assertEqual(st["once"], 1)
        self.assertEqual(self.x.timers(), 1)            # 멈춘 것과 끝난 after는 빠지고 every 하나만 남음
        self.x.unload("t")
        self.assertEqual(self.x.timers(), 0)            # 내리면 코어가 멈춘다

    def test_timer_errors_go_to_error_watch(self):
        self.x.load("te", mod_src("te", "api.every(50, function () { throw new Error('tick'); });"))
        self.wait_for(lambda m: isinstance(m, dict) and m.get("m24core", {}).get("t") == "error" and m["m24core"]["where"] == "every")

    def test_decode_date(self):
        d = self.x.decode(133399155)                    # 실측값: 2035-04-25 (M11 0절)
        self.assertEqual((d["y"], d["m"], d["d"], d["doy"], d["iso"]), (2035, 4, 25, 115, "2035-04-25"))
        self.assertEqual(self.x.decode((2024 << 16) | 366)["iso"], "2024-12-31")   # 윤년 366일
        self.assertIsNone(self.x.decode((2025 << 16) | 366))                         # 평년 366일은 없음
        self.assertIsNone(self.x.decode(0))
        self.assertIsNone(self.x.decode(None))

    def test_poll_emits_save_and_date_events(self):
        body = """
var log = [];
api.on('saveLoaded', function (ev) { log.push('save ' + ev.id + ' ' + (ev.date && ev.date.iso)); });
api.on('dateChanged', function (ev) { log.push('date ' + ev.from.iso + '>' + ev.to.iso + ' ' + ev.days); });
api.status(function () { return { log: log }; });
"""
        self.x.load("g", mod_src("g", body))
        day = lambda y, doy: (y << 16) | doy
        self.x.set_game(0, 0, 0)                        # 메인 메뉴: 세이브 없음
        self.x.poll()
        self.x.set_game(day(2035, 115), 5117219, 1)     # 세이브 불러옴
        self.x.poll()
        self.x.poll()                                   # 그대로면 아무 일 없음
        self.x.set_game(day(2035, 117), 5117219, 1)     # 이틀 진행
        self.x.poll()
        self.x.set_game(day(2036, 1), 5117219, 1)       # 해 넘김
        self.x.poll()
        self.x.set_game(day(2026, 200), 42, 7)          # 다른 세이브 (날짜 이벤트는 안 나감)
        self.x.poll()
        self.assertEqual(self.x.status()["log"], [
            "save 5117219 2035-04-25", "date 2035-04-25>2035-04-27 2", "date 2035-04-27>2036-01-01 249", "save 42 2026-07-19"])
        live = self.x.live_date()
        self.assertEqual(live[0]["iso"], "2026-07-19")
        self.assertEqual(live[1], {"id": 42, "nonce": 7})
        self.wait_for(lambda m: isinstance(m, dict) and m.get("m24core", {}).get("t") == "game" and m["m24core"]["save"] == {"id": 42, "nonce": 7})


    # ---- M14: 게임 값 쓰기 ----
    WRITER_MOD = """
var res = [];
api.recv(function (m) { res.push(api.setPlayerPA(m.uid, m.pa, m.opts)); });
api.status(function () { return { res: res }; });
"""

    def _ask(self, mid, uid, pa, opts=None):
        self.script.post({"type": "m24ga", "m": mid, "d": {"uid": uid, "pa": pa, "opts": opts or {}}})
        time.sleep(0.15)
        return self.x.status()["res"][-1]

    def test_write_needs_capability_and_save(self):
        self.x.fake_writer()
        self.x.load("nw", mod_src("nw", self.WRITER_MOD, ["read.data"]))      # 쓰기 기능 선언·허용 없음
        r = self._ask("nw", 7, 150)
        self.assertFalse(r["ok"])
        self.assertIn("write.player.pa", r["error"])
        self.x.load("w", mod_src("w", self.WRITER_MOD, ["write.player.pa"]))
        self.x.set_game(0, 0, 0)                                                 # 세이브 없음
        r = self._ask("w", 7, 150)
        self.assertFalse(r["ok"])
        self.assertIn("세이브", r["error"])
        self.assertEqual(self.x.vals()["7"], 140)

    def test_write_logs_and_undo(self):
        self.x.fake_writer()
        self.x.set_game((2035 << 16) | 117, 5117219, 1)
        self.x.load("w", mod_src("w", self.WRITER_MOD, ["write.player.pa"]))
        self.assertFalse(self._ask("w", 7, 150.5)["ok"])                          # 정수만
        self.assertFalse(self._ask("w", 7, 150, {"expect": 139})["ok"])           # 예상 값과 다름
        r = self._ask("w", 7, 150, {"expect": 140, "reason": "시험"})
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["before"], r["after"]), (140, 150))
        n = self.wait_for(lambda m: isinstance(m, dict) and m.get("m24core", {}).get("t") == "write")[0]["m24core"]
        self.assertEqual((n["id"], n["field"], n["key"], n["from"], n["to"], n["reason"], n["date"]), ("w", "player.pa", 7, 140, 150, "시험", "2035-04-27"))
        self.assertEqual(n["save"], {"id": 5117219, "nonce": 1})
        with self.lock:
            self.msgs.clear()
        self.assertTrue(self._ask("w", 7, 150)["ok"])                            # 같은 값: 기록 안 함
        time.sleep(0.2)
        with self.lock:
            self.assertFalse(any(isinstance(m, dict) and m.get("m24core", {}).get("t") == "write" for m in self.msgs))
        self.assertFalse(self.x.undo("player.pa", 7, 140, 151)["ok"])            # 지금 값(150)이 쓴 값과 다르면 안 되돌림
        self.assertTrue(self.x.undo("player.pa", 7, 140, 150)["ok"])
        self.assertEqual(self.x.vals()["7"], 140)

    def test_write_rate_limit(self):
        self.x.fake_writer()
        self.x.set_game((2035 << 16) | 117, 1, 1)
        self.x.set_rate(3)
        self.x.load("w", mod_src("w", self.WRITER_MOD, ["write.player.pa"]))
        oks = [self._ask("w", 7, 141 + i)["ok"] for i in range(4)]
        self.assertEqual(oks, [True, True, True, False])
        self.assertIn("너무 많아요", self.x.status()["res"][-1]["error"])

    # ---- 모드 설정 (M23): api.settings() 복사본, 앱에서 바뀌면 onSettings, 내리면 사라짐 ----
    SET_MOD = """
var got = [];
api.onSettings(function (s) { got.push(s); });
api.status(function () { var s = api.settings(); s.zz = 1; return { now: api.settings(), got: got, mutated: s.zz }; });
"""

    def test_settings(self):
        self.x.load("s1", mod_src("s1", self.SET_MOD, [], {"uid": 5, "on": True}))
        st = self.x.status()
        self.assertEqual(st["now"], {"uid": 5, "on": True})
        self.assertNotIn("zz", st["now"])                                  # 부를 때마다 새 복사본이라 고쳐도 원본은 그대로
        self.assertTrue(self.x.set_settings("s1", {"uid": 9, "on": False}))
        st = self.x.status()
        self.assertEqual((st["now"], st["got"]), ({"uid": 9, "on": False}, [{"uid": 9, "on": False}]))
        self.assertFalse(self.x.set_settings("nope", {}))                  # 올라가 있지 않은 모드
        self.x.load("s2", mod_src("s2", "api.status(function () { return { s2: api.settings() }; });", []))   # 설정을 안 넘긴 모드
        self.assertEqual(self.x.status()["s2"], {})
        self.x.unload("s1")
        self.assertFalse(self.x.set_settings("s1", {"uid": 1}))

    # ---- 게임 함수 끼어들기 (M22): 코어는 함수마다 한 번만 걸고, 모드들에 나눠 주고, 마지막 모드가 떼면 푼다 ----
    HOOK_MOD = """
var r = api.hook('f.x', { before: function (ev) { ev.data[api.id + 'b'] = ev.args[0]; }, after: function (ev) { ev.data[api.id + 'a'] = ev.ret; } });
var bad = api.hook('f.nope', { before: function () {} }), core = api.hook('f.core', { before: function () {} });
api.status(function () { var o = {}; o[api.id] = { ok: r.ok, bad: bad.error, core: core.error }; return o; });
"""
    BOOM_MOD = "api.hook('f.x', { before: function (ev) { throw new Error('boom'); } });"

    def test_hooks(self):
        self.x.fake_hooks()
        self.x.load("h1", mod_src("h1", self.HOOK_MOD, ["hook.function"]))
        self.x.load("h2", mod_src("h2", self.HOOK_MOD, ["hook.function"]))
        st = self.x.status()
        self.assertTrue(st["h1"]["ok"])
        self.assertIn("모르는 함수", st["h1"]["bad"])
        self.assertIn("api.on('frame')", st["h1"]["core"])
        self.assertEqual(self.x.hk()["hk"]["install"], 1)                 # 두 모드여도 한 번만 건다
        self.x.load("boom", mod_src("boom", self.BOOM_MOD, ["hook.function"]))
        d = self.x.fire("f.x")
        self.assertEqual((d["h1b"], d["h1a"], d["h2b"], d["h2a"]), (1, 7, 1, 7))   # 한 모드가 오류를 내도 다른 모드는 받는다
        stats = {e["mod"]: e for e in self.x.hk()["stats"]["f.x"]}
        self.assertEqual(stats["boom"]["errs"], 1)
        self.assertEqual(stats["h1"]["calls"], 1)
        self.x.unload("h1"); self.x.unload("boom")
        self.assertEqual(self.x.hk()["hk"]["release"], 0)                 # h2가 남아 있다
        self.x.unload("h2")
        self.assertEqual((self.x.hk()["n"], self.x.hk()["hk"]["release"]), (0, 1))   # 마지막 모드가 내려가면 푼다

    # ---- 필드 등록부 쓰기 (M20): api.setField는 필드의 쓰기 함수가 가진 기능(cap)을 요구하고, 실수 필드는 실수를 받는다 ----
    FIELD_MOD = """
var res = [];
api.recv(function (m) { res.push(api.setField(m.obj, m.name, m.v, m.opts)); });
api.status(function () { return { res: res }; });
"""

    def _set(self, mid, obj, name, v, opts=None):
        self.script.post({"type": "m24ga", "m": mid, "d": {"obj": obj, "name": name, "v": v, "opts": opts or {}}})
        time.sleep(0.15)
        return self.x.status()["res"][-1]

    def test_set_field(self):
        self.x.fake_field()
        self.x.set_game((2035 << 16) | 117, 1, 1)
        self.x.load("nf", mod_src("nf", self.FIELD_MOD, ["read.field"]))           # write.field 없음
        r = self._set("nf", 7, "x.f", 1.5)
        self.assertFalse(r["ok"])
        self.assertIn("write.field", r["error"])
        self.x.load("f", mod_src("f", self.FIELD_MOD, ["read.field", "write.field"]))
        self.assertIn("읽기만", self._set("f", 7, "x.ro", 1)["error"])
        self.assertIn("모르는 필드", self._set("f", 7, "zz", 1)["error"])
        r = self._set("f", 7, "x.f", 1.5, {"reason": "시험"})                        # 실수 필드라 1.5도 된다
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.x.vals()["7"], 1.5)
        self.assertFalse(self._set("f", 7, "x.f", "a")["ok"])   # 숫자가 아니면 거부



if __name__ == "__main__":
    unittest.main()
