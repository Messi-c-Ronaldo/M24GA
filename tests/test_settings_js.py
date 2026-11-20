"""게임 쪽 JS의 설정 (M23): bundle.game_settings가 password 형식을 빼고 기본값을 채우는지, 묶음 meta에 들어가는지,
host.save_settings가 저장한 뒤 올라간 모드에 알리는지, validate가 core 조건을 확인하는지. 게임·frida 없이."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
import bundle  # noqa: E402
import host  # noqa: E402
import mods as modlib  # noqa: E402
import validate as v  # noqa: E402

MANIFEST = {"id": "sj", "name": "sj", "version": "1.0.0", "core": ">=0.12.0", "js": "mod.js", "capabilities": [],
            "settings": [{"key": "uid", "type": "int", "default": 7, "min": 1},
                         {"key": "on", "type": "bool", "default": True},
                         {"key": "api.key", "type": "password", "default": ""},
                         {"key": "api.model", "type": "text", "default": "m"}]}


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.mod_dir = os.path.join(self.td, "mods", "sj")
        os.makedirs(self.mod_dir)
        self.data = os.path.join(self.td, "data")
        self.old = modlib.DATA
        modlib.DATA = self.data
        self.write_manifest(MANIFEST)
        with open(os.path.join(self.mod_dir, "mod.js"), "w", encoding="utf-8") as f:
            f.write("var s = api.settings();\n")

    def tearDown(self):
        modlib.DATA = self.old
        shutil.rmtree(self.td, ignore_errors=True)

    def write_manifest(self, m):
        with open(os.path.join(self.mod_dir, "mod.json"), "w", encoding="utf-8") as f:
            json.dump(m, f)

    def mod(self):
        return modlib.Mod(self.mod_dir, "dir", json.load(open(os.path.join(self.mod_dir, "mod.json"), encoding="utf-8")))


class GameSettings(Sandbox):
    def test_password_left_out_defaults_filled(self):
        m = self.mod()
        modlib.save_settings(m, {"uid": 12, "api.key": "SECRET", "api.model": "x"})
        vals = bundle.game_settings(m)
        self.assertEqual(vals, {"uid": 12, "on": True, "api.model": "x"})          # 파일 값, 없는 건 default, 비밀번호는 없음
        self.assertNotIn("SECRET", json.dumps(vals))

    def test_meta_in_bundle(self):
        m = self.mod()
        src = bundle.mod_source(m)
        self.assertIn('"settings": {"uid": 7, "on": true, "api.model": "m"}', src)
        self.assertNotIn("api.key", src)


class SavePush(Sandbox):
    class FakeExports:
        def __init__(self):
            self.calls = []

        def setsettings(self, mid, vals):
            self.calls.append((mid, vals))

    class FakeScript:
        def __init__(self, ex):
            self.exports_sync = ex

    def test_push_after_save(self):
        m, ex = self.mod(), self.FakeExports()
        old = host._cur["script"]
        host._cur["script"] = self.FakeScript(ex)
        try:
            errs = host.save_settings(m, {"uid": 3, "api.key": "SECRET"})
            self.assertEqual(errs, {})
            self.assertEqual(ex.calls, [("sj", {"uid": 3, "on": True, "api.model": "m"})])
            errs = host.save_settings(m, {"uid": 0})                                # 범위 밖: 저장 안 됨 -> 알리지 않음
            self.assertIn("uid", errs)
            self.assertEqual(len(ex.calls), 1)
            host._cur["script"] = None
            self.assertEqual(host.save_settings(m, {"uid": 4}), {})                 # 게임에 안 붙어 있어도 저장은 된다
            self.assertEqual(modlib.load_settings(m)["uid"], 4)
        finally:
            host._cur["script"] = old


class RangeMessage(unittest.TestCase):
    def test_one_sided_range_reads_naturally(self):
        def bad(spec, v):
            try:
                modlib._coerce(spec, v)
            except ValueError as e:
                return str(e)
        self.assertEqual(bad({"type": "int", "min": 1}, 0), "1 이상")
        self.assertEqual(bad({"type": "int", "max": 5}, 6), "5 이하")
        self.assertEqual(bad({"type": "int", "min": 1, "max": 5}, 6), "범위 1~5")


class ValidateCore(Sandbox):
    def test_old_core_warns(self):
        m = dict(MANIFEST, core=">=0.11.0")
        self.write_manifest(m)
        w = [i["message"] for i in v.validate(self.mod_dir).issues if i["level"] == "warning"]
        self.assertTrue(any("api.settings" in x and "0.12.0" in x for x in w), w)
        self.write_manifest(MANIFEST)
        w = [i["message"] for i in v.validate(self.mod_dir).issues if i["level"] == "warning"]
        self.assertFalse(any("api.settings" in x for x in w), w)


if __name__ == "__main__":
    unittest.main()
