"""안전장치 시험: 게임 종료 코드 판별, 세션 기록과 안전 모드, 자동으로 끈 모드, Python 감독, 올리기 전 문법 검사.
게임은 필요 없다 (종료 코드는 시험용 하위 프로세스로, 문법 검사는 그 프로세스에 frida를 붙여서 확인한다).

  python -X utf8 -m unittest discover -s tests -v
"""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "vendor"))
import health  # noqa: E402
import host  # noqa: E402
import m24  # noqa: E402
import mods as modlib  # noqa: E402


class Isolated(unittest.TestCase):
    """~/m24ga_data의 실제 기록을 건드리지 않도록 경로를 임시 폴더로 바꾼다."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        t = self.td.name
        self._saved = (health.SESSION_PATH, health.CRASH_LOG, modlib.AUTO_PATH, modlib.ENABLED_PATH, host.LOG, modlib.mod_dirs, modlib.DATA)
        health.SESSION_PATH, health.CRASH_LOG = os.path.join(t, "session.json"), os.path.join(t, "crashes.json")
        modlib.AUTO_PATH, modlib.ENABLED_PATH = os.path.join(t, "auto.json"), os.path.join(t, "enabled.json")
        host.LOG = os.path.join(t, "loader.log")
        modlib.DATA = t
        self.mods_dir = os.path.join(t, "mods")
        os.makedirs(self.mods_dir)
        modlib.mod_dirs = lambda: [self.mods_dir]
        host._safe.update(active=False, allow=set(), code=None, time="", mods=[])
        host._mods.update(list=[], errors=[], loaded=[], build_off={})

    def tearDown(self):
        (health.SESSION_PATH, health.CRASH_LOG, modlib.AUTO_PATH, modlib.ENABLED_PATH, host.LOG, modlib.mod_dirs, modlib.DATA) = self._saved
        host._safe.update(active=False, allow=set(), code=None, time="", mods=[])
        host._mods.update(list=[], errors=[], loaded=[], build_off={})
        self.td.cleanup()

    def new_mod(self, mid, *flags):
        self.assertEqual(m24.main(["new", mid, "--dir", self.mods_dir] + list(flags)), 0)
        return os.path.join(self.mods_dir, mid)


class ExitCodes(unittest.TestCase):
    def test_is_crash(self):
        for code in (0xC0000005, 0xC0000409, 0xC00000FD, 0xC0000374):
            self.assertTrue(health.is_crash(code), hex(code))
        for code in (0, 1, 2, 259, 0x40010004, None):
            self.assertFalse(health.is_crash(code), str(code))

    def test_procwatch_reads_real_exit_codes(self):
        for code, crash in ((0, False), (1, False), (0xC0000005, True)):
            # os._exit은 0xC0000005 같은 큰 값을 못 받아서 Windows API로 직접 끝낸다
            p = subprocess.Popen([sys.executable, "-c", "import ctypes,time; time.sleep(0.6); ctypes.windll.kernel32.ExitProcess(%d)" % code])
            w = health.ProcWatch(p.pid)
            try:
                self.assertIsNone(w.exit_code(), "아직 살아 있으면 None")
                got = w.wait_code(10)
                self.assertEqual(got, code)
                self.assertEqual(health.is_crash(got), crash)
            finally:
                w.close()
                p.wait()

    def test_procwatch_unknown_pid(self):
        w = health.ProcWatch(0x7FFFFFF0)
        self.assertIsNone(w.exit_code())
        self.assertIsNone(w.wait_code(0.2))


class SessionRecords(Isolated):
    def test_crash_with_mods_is_pending_until_acknowledged(self):
        health.session_set_mods(100, ["a"], False)
        health.session_end(0xC0000005, "game-exit")
        c = health.pending_crash()
        self.assertEqual(c["mods"], ["a"])
        self.assertEqual(c["code"], 0xC0000005)
        health.acknowledge_crash()
        self.assertIsNone(health.pending_crash())
        self.assertEqual(len(modlib._read_json(health.CRASH_LOG, [])), 1)

    def test_no_pending_without_mods_or_without_crash(self):
        health.session_set_mods(100, [], False)
        health.session_end(0xC0000005, "game-exit")
        self.assertIsNone(health.pending_crash(), "모드가 한 번도 안 올라갔으면 모드 탓이 아니다")
        health.session_set_mods(101, ["a"], False)
        health.session_end(0, "game-exit")
        self.assertIsNone(health.pending_crash())
        health.session_set_mods(102, ["a"], False)
        health.session_end(None, "loader-stopped")
        self.assertIsNone(health.pending_crash(), "종료 코드를 모르면 안전 모드를 걸지 않는다")

    def test_mods_that_were_loaded_earlier_in_the_session_count(self):
        health.session_set_mods(100, ["a"], False)
        health.session_set_mods(100, [], False)      # 도중에 끔
        health.session_set_mods(100, ["b"], False)
        health.session_end(0xC0000005, "game-exit")
        self.assertEqual(health.pending_crash()["mods"], ["a", "b"])

    def test_new_game_starts_new_session(self):
        health.session_set_mods(100, ["a"], False)
        health.session_end(0xC0000005, "game-exit")
        health.session_set_mods(200, [], False)       # 다음 게임
        self.assertIsNone(health.pending_crash())


class AutoDisabled(Isolated):
    def test_store_and_active_filter(self):
        d = self.new_mod("m-one")
        self.new_mod("m-two")
        host.rescan()
        self.assertEqual(sorted(m.id for m in modlib.active(host._mods["list"])), ["m-one", "m-two"])
        self.assertTrue(modlib.auto_disable("m-one", "테스트", "js"))
        self.assertFalse(modlib.auto_disable("m-one", "또", "js"), "같은 모드는 한 번만 기록")
        self.assertEqual([m.id for m in modlib.active(host._mods["list"])], ["m-two"])
        st = {s["id"]: s for s in host.mod_states()}
        self.assertEqual(st["m-one"]["state"], "auto_off")
        self.assertFalse(st["m-one"]["enabled"])
        self.assertEqual(st["m-one"]["auto_disabled"]["reason"], "테스트")
        host.set_enabled("m-one", True)               # 사용자가 다시 켜면 기록이 지워진다
        self.assertEqual(modlib.auto_disabled(), {})
        self.assertEqual(sorted(m.id for m in modlib.active(host._mods["list"])), ["m-one", "m-two"])
        self.assertTrue(os.path.isdir(d))


class PythonSupervisor(Isolated):
    def make(self, mid, code):
        d = self.new_mod(mid, "--python")
        with open(os.path.join(d, "python", "main.py"), "w", encoding="utf-8") as f:
            f.write(code)
        mod = modlib._load_one(d)
        logs, fatal = [], []
        r = modlib.PyRunner(mod, logs.append, None, lambda i, reason: fatal.append((i, reason)))
        r.RESTART_WAIT = 0.05
        return r, logs, fatal

    def join(self, r, sec=5):
        t = time.time()
        while r.running() and time.time() - t < sec:
            time.sleep(0.02)

    def test_repeated_failure_disables_after_three(self):
        r, logs, fatal = self.make("sv-fail", "COUNT = []\ndef run(ctx):\n    COUNT.append(1)\n    raise ValueError('boom')\n")
        r.start()
        self.join(r)
        self.assertFalse(r.running())
        self.assertEqual(len(fatal), 1, logs)
        self.assertIn("boom", fatal[0][1])
        self.assertEqual(sum("다시 시작합니다" in x for x in logs), 2, "3번째 실패에서는 다시 시작하지 않는다")

    def test_recovers_after_one_failure(self):
        r, logs, fatal = self.make("sv-ok", "N = [0]\ndef run(ctx):\n    N[0] += 1\n    if N[0] == 1:\n        raise ValueError('once')\n    ctx.stop.wait(30)\n")
        r.start()
        t = time.time()
        while time.time() - t < 5 and not any("다시 시작합니다" in x for x in logs):
            time.sleep(0.02)
        time.sleep(0.3)
        self.assertTrue(r.running(), "한 번 실패한 뒤 다시 시작해서 계속 돈다")
        self.assertEqual(fatal, [])
        r.stop()
        self.assertFalse(r.running())

    def test_normal_return_is_not_an_error(self):
        r, logs, fatal = self.make("sv-done", "def run(ctx):\n    return\n")
        r.start()
        self.join(r)
        self.assertEqual(fatal, [])

    def test_stop_during_backoff(self):
        r, logs, fatal = self.make("sv-stop", "def run(ctx):\n    raise ValueError('x')\n")
        r.RESTART_WAIT = 30
        r.start()
        time.sleep(0.3)
        t = time.time()
        r.stop(timeout=5)
        self.assertLess(time.time() - t, 3, "대기 중에도 멈추라고 하면 바로 끝난다")
        self.assertFalse(r.running())


class SafeModeLogic(Isolated):
    def setUp(self):
        super().setUp()
        self.new_mod("sm-a")
        self.new_mod("sm-b")
        host.rescan()

    def test_enter_allow_one_by_one_and_leave(self):
        health.session_set_mods(100, ["sm-a", "sm-b"], False)
        health.session_end(0xC0000005, "game-exit")
        self.assertTrue(host.check_last_crash())
        self.assertFalse(host.check_last_crash(), "한 번만 걸린다")
        self.assertEqual(host._wanted(), [])
        info = host.safe_info()
        self.assertEqual(info["code"], "0xC0000005")
        self.assertEqual(sorted(info["mods"]), ["sm-a", "sm-b"])
        st = {s["id"]: s["state"] for s in host.mod_states()}
        self.assertEqual(st, {"sm-a": "safe", "sm-b": "safe"})
        host.set_enabled("sm-a", True)                 # 하나만 켜 본다
        self.assertEqual([m.id for m in host._wanted()], ["sm-a"])
        st = {s["id"]: s["state"] for s in host.mod_states()}
        self.assertEqual(st["sm-b"], "safe")
        self.assertNotEqual(st["sm-a"], "safe")
        host.leave_safe_mode()
        self.assertIsNone(host.safe_info())
        self.assertEqual(sorted(m.id for m in host._wanted()), ["sm-a", "sm-b"])

    def test_no_safe_mode_after_normal_exit(self):
        health.session_set_mods(100, ["sm-a"], False)
        health.session_end(0, "game-exit")
        self.assertFalse(host.check_last_crash())
        self.assertEqual(len(host._wanted()), 2)


class ModLogs(Isolated):
    """모드별 로그 탭의 수집·분류·보고서."""

    def setUp(self):
        super().setUp()
        host._mod_logs.clear()
        self.new_mod("lg-a", "--python")
        host.rescan()

    def tearDown(self):
        host._mod_logs.clear()
        super().tearDown()

    def msgs(self, mid="lg-a", since=0):
        return [(e["src"], e["lvl"], e["msg"]) for e in host.get_mod_log(mid, since)["entries"]]

    def test_python_lines_are_attributed_by_prefix(self):
        host.log("[lg-a] 안녕")                          # ctx.log가 보내는 모양
        host.log("[lg-a] Python 오류(1회째): ValueError('x')\nTraceback (most recent call last):\n  boom")
        host.log("[other-mod] 모르는 모드의 글")           # 모르는 id는 모으지 않는다
        host.log("일반 로더 글")
        got = self.msgs()
        self.assertEqual([g[:2] for g in got], [("python", "info"), ("python", "error")])
        self.assertIn("Traceback", got[1][2], "스택이 한 항목에 같이 들어간다")
        self.assertEqual(self.msgs("other-mod"), [])

    def test_js_messages_from_game(self):
        host.on_message({"type": "send", "payload": "[lg-a] 게임 쪽 api.log"}, None)
        host.on_message({"type": "send", "payload": "mod loaded: lg-a"}, None)
        host.on_message({"type": "send", "payload": {"m24core": {"t": "error", "id": "lg-a", "where": "frame", "msg": "TypeError: x is undefined\n    at f"}}}, None)
        got = self.msgs()
        self.assertEqual([g[:2] for g in got], [("js", "info"), ("js", "info"), ("js", "error")])
        self.assertIn("at f", got[2][2], "오류는 스택까지 남긴다")

    def test_frida_internal_stack_lines_are_dropped(self):
        stack = "Error: boom\n    at f (/script2.js:1:1)\n    at complete (/frida/runtime/message-dispatcher.js:115:15)\n    at forEach (native)"
        host.on_message({"type": "send", "payload": {"m24core": {"t": "error", "id": "lg-a", "where": "recv", "msg": stack}}}, None)
        msg = self.msgs()[-1][2]
        self.assertIn("at f (/script2.js:1:1)", msg)
        self.assertNotIn("/frida/runtime/", msg)
        self.assertNotIn("(native)", msg)

    def test_auto_disable_is_logged_as_error(self):
        host.on_message({"type": "send", "payload": {"m24core": {"t": "disabled", "id": "lg-a", "where": "recv", "msg": "Error: boom 24"}}}, None)
        got = self.msgs()
        self.assertTrue(any(l == "error" and "자동으로 껐어요" in m for _, l, m in got), got)
        self.assertEqual(host.mod_states()[0]["log_errors"], 1)

    def test_paging_clear_and_ring_buffer(self):
        for i in range(host._MODLOG_MAX + 30):
            host.mod_log("lg-a", "line %d" % i, "loader", "info")
        r = host.get_mod_log("lg-a", 0)
        self.assertEqual(len(r["entries"]), host._MODLOG_MAX)
        self.assertEqual(r["entries"][-1]["msg"], "line %d" % (host._MODLOG_MAX + 29))
        self.assertEqual(host.get_mod_log("lg-a", r["last"])["entries"], [], "이미 받은 건 다시 안 준다")
        host.mod_log("lg-a", "새 글", "loader")
        self.assertEqual([e["msg"] for e in host.get_mod_log("lg-a", r["last"])["entries"]], ["새 글"])
        host.clear_mod_log("lg-a")
        self.assertEqual(host.get_mod_log("lg-a", 0)["entries"], [])

    def test_levels(self):
        for text, lvl in (("정상", "info"), ("경고: 뭔가", "warn"), ("Python 오류", "error"), ("Traceback x", "error"), ("job failed", "error")):
            self.assertEqual(host._level(text), lvl, text)

    def test_report_contains_state_validation_and_log(self):
        host.mod_log("lg-a", "마지막으로 본 로그 줄", "js", "error")
        modlib.auto_disable("lg-a", "테스트 이유", "js")
        rep = host.mod_report("lg-a")
        for needle in ("M24GA 모드 상태 보고", "AI_GUIDE.md", "lg-a", "자동으로 꺼짐", "테스트 이유", "검사 결과", "결과: 통과", "마지막으로 본 로그 줄", "[JS][오류]"):
            self.assertIn(needle, rep)
        self.assertEqual(host.mod_report("없는-모드"), "")


class SyntaxPrecheck(Isolated):
    """host._load_script가 쓰는 session.compile_script가 문법 오류를 실제로 거부하는지 (frida를 시험용 프로세스에 붙여 확인)."""

    def test_compile_script_rejects_syntax_errors_only(self):
        import frida
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"])
        try:
            time.sleep(0.5)
            try:
                session = frida.get_local_device().attach(proc.pid)
            except Exception as e:  # noqa: BLE001
                self.skipTest("frida를 붙일 수 없음: %r" % e)
            try:
                d = self.new_mod("sx-ok")
                good = modlib._load_one(d)
                import bundle
                session.compile_script(bundle.mod_source(good))        # 문법이 맞으면 통과 (registerMod가 없어도 문법만 본다)
                with open(os.path.join(d, "mod.js"), "a", encoding="utf-8") as f:
                    f.write("\nfunction broken( {\n")
                with self.assertRaises(Exception) as cm:
                    session.compile_script(bundle.mod_source(modlib._load_one(d)))
                self.assertTrue(str(cm.exception).strip())
            finally:
                session.detach()
        finally:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    unittest.main()
