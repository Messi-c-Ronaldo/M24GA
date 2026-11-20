"""host.apply_mods 시험 (M09 핫 리로드): 가짜 세션·스크립트로 '코어는 그대로, 바뀐 모드만 내리고 올리는지' 본다.
게임·frida 연결 없이 돈다. 임시 폴더만 쓴다.
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import m24  # noqa: E402
import mods as modlib  # noqa: E402

try:
    import host  # noqa: E402  (frida가 없으면 import 실패)
except ImportError:      # pragma: no cover
    host = None


class FakeExports:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail or {}

    def loadmod(self, mid, src):
        self.calls.append(("load", mid))
        if mid in self.fail:
            return {"ok": False, "error": self.fail[mid]}
        return {"ok": True}

    def unloadmod(self, mid):
        self.calls.append(("unload", mid))
        return True


class FakeScript:
    def __init__(self, exports):
        self.exports_sync = exports


class FakeSession:
    def __init__(self):
        self.compiled = []

    def compile_script(self, src):
        self.compiled.append(src)
        if "SYNTAX_ERROR_HERE" in src:
            raise RuntimeError("Script(line 3): SyntaxError: unexpected token")


@unittest.skipIf(host is None, "frida 없음")
class ApplyMods(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.saved = dict(USER_MODS=modlib.USER_MODS, DEV_MODS=modlib.DEV_MODS, DATA=modlib.DATA, ENABLED_PATH=modlib.ENABLED_PATH,
                          AUTO_PATH=modlib.AUTO_PATH, CACHE_DIR=modlib.CACHE_DIR)
        modlib.USER_MODS = os.path.join(self.td, "user")
        modlib.DEV_MODS = os.path.join(self.td, "dev")
        modlib.DATA = os.path.join(self.td, "data")
        modlib.ENABLED_PATH = os.path.join(modlib.DATA, "enabled.json")
        modlib.AUTO_PATH = os.path.join(modlib.DATA, "autodisabled.json")
        modlib.CACHE_DIR = os.path.join(modlib.DATA, "cache")
        os.makedirs(modlib.USER_MODS)
        os.makedirs(modlib.DEV_MODS)
        self.saved_host = (host.LOG, dict(host._cur), dict(host._mods), host.health.session_set_mods, host.match_mods)
        host.LOG = os.path.join(self.td, "loader.log")
        host.health.session_set_mods = lambda *a, **k: None
        host.match_mods = lambda info, build, mods: {}
        for mid in ("ma", "mb"):
            self.assertEqual(m24.main(["new", mid, "--dir", modlib.DEV_MODS]), 0)
        self.ex = FakeExports()
        host._cur.update(session=FakeSession(), script=FakeScript(self.ex), build="test", info={})
        host._mods.update(list=[], errors=[], loaded=[], build_off={}, src={})
        host._mods["list"], _ = modlib.scan()

    def tearDown(self):
        host.LOG, cur, mods, host.health.session_set_mods, host.match_mods = self.saved_host
        host._cur.clear(); host._cur.update(cur)
        host._mods.clear(); host._mods.update(mods)
        for k, v in self.saved.items():
            setattr(modlib, k, v)
        shutil.rmtree(self.td, ignore_errors=True)

    def rescan(self):
        host._mods["list"], _ = modlib.scan()

    def test_first_apply_loads_all_then_nothing(self):
        self.assertTrue(host.apply_mods())
        self.assertEqual(sorted(self.ex.calls), [("load", "ma"), ("load", "mb")])
        self.assertEqual(sorted(host._mods["loaded"]), ["ma", "mb"])
        self.ex.calls.clear()
        self.assertFalse(host.apply_mods())                  # 바뀐 게 없으면 아무것도 안 한다
        self.assertEqual(self.ex.calls, [])

    def test_disable_unloads_only_that_mod(self):
        host.apply_mods()
        self.ex.calls.clear()
        modlib.set_enabled("ma", False)
        self.assertTrue(host.apply_mods())
        self.assertEqual(self.ex.calls, [("unload", "ma")])
        self.assertEqual(host._mods["loaded"], ["mb"])
        modlib.set_enabled("ma", True)
        self.ex.calls.clear()
        host.apply_mods()
        self.assertEqual(self.ex.calls, [("load", "ma")])

    def test_changed_js_is_reloaded_alone(self):
        host.apply_mods()
        self.ex.calls.clear()
        with open(os.path.join(modlib.DEV_MODS, "mb", "mod.js"), "a", encoding="utf-8") as f:
            f.write("\napi.log('바뀜');\n")
        self.rescan()
        host.apply_mods()
        self.assertEqual(self.ex.calls, [("load", "mb")])   # 같은 id를 다시 올리면 코어가 옛 것을 먼저 내린다
        self.assertEqual(sorted(host._mods["loaded"]), ["ma", "mb"])

    def test_force_reload(self):
        host.apply_mods()
        self.ex.calls.clear()
        host.apply_mods(force=("ma",))
        self.assertEqual(self.ex.calls, [("load", "ma")])

    def test_syntax_error_is_auto_disabled_without_touching_core(self):
        host.apply_mods()
        self.ex.calls.clear()
        with open(os.path.join(modlib.DEV_MODS, "ma", "mod.js"), "a", encoding="utf-8") as f:
            f.write("\nSYNTAX_ERROR_HERE\n")
        self.rescan()
        host.apply_mods()
        self.assertIn("ma", modlib.auto_disabled())
        self.assertEqual(self.ex.calls, [("unload", "ma")])  # 틀린 새 코드는 안 올리고, 올라가 있던 것은 내린다
        self.assertEqual(host._mods["loaded"], ["mb"])

    def test_load_failure_is_not_marked_loaded(self):
        self.ex.fail["mb"] = "init boom"
        host.apply_mods()
        self.assertEqual(host._mods["loaded"], ["ma"])
        self.assertNotIn("mb", host._mods["src"])

    def test_rpc_error_falls_back_to_full_reload(self):
        class Broken(FakeExports):
            def loadmod(self, mid, src):
                raise RuntimeError("unable to find method 'loadmod'")
        host._cur["script"] = FakeScript(Broken())
        called = []
        saved = host.reload
        host.reload = lambda start_maps=None: called.append(True) or True
        try:
            self.assertTrue(host.apply_mods())
        finally:
            host.reload = saved
        self.assertEqual(called, [True])

    def test_no_script_does_nothing(self):
        host._cur["script"] = None
        self.assertFalse(host.apply_mods())


if __name__ == "__main__":
    unittest.main()
