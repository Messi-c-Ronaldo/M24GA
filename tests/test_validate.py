"""모드 검증기와 뼈대 생성 도구의 회귀 시험 (게임, frida, 인터넷 없이 돈다).

  python -X utf8 -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import m24  # noqa: E402
import validate as v  # noqa: E402


def write(folder, rel, text):
    p = os.path.join(folder, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def issues(rep, level=None):
    return [(i["where"], i["message"]) for i in rep.issues if level in (None, i["level"])]


class RealMods(unittest.TestCase):
    def test_bundled_mods_have_no_errors(self):
        for p in ("mods/ai-social-feed", "examples/hello", "examples/field-hook"):
            rep = v.validate(os.path.join(ROOT, p))
            self.assertEqual(rep.errors, [], "%s: %s" % (p, issues(rep, "error")))


class Scaffold(unittest.TestCase):
    def test_new_mod_variants_pass_validate(self):
        with tempfile.TemporaryDirectory() as td:
            for mid, flags in (("t-js", []), ("t-py", ["--python"]), ("t-ui", ["--ui"])):
                self.assertEqual(m24.main(["new", mid, "--dir", td] + flags), 0, mid)
                rep = v.validate(os.path.join(td, mid))
                self.assertEqual(rep.errors, [], "%s: %s" % (mid, issues(rep, "error")))
                self.assertEqual([i for i in rep.issues if i["level"] == "warning"], [], mid)
            self.assertTrue(os.path.exists(os.path.join(td, "t-ui", "ui", "index.html")))
            self.assertFalse(os.path.exists(os.path.join(td, "t-js", "python")))

    def test_new_rejects_bad_id_and_existing_folder(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(m24.main(["new", "Bad Id", "--dir", td]), 2)
            self.assertEqual(m24.main(["new", "ok-id", "--dir", td]), 0)
            self.assertEqual(m24.main(["new", "ok-id", "--dir", td]), 2)

    def test_pack_runs_validate_and_skips_agents_md(self):
        import zipfile
        with tempfile.TemporaryDirectory() as td:
            m24.main(["new", "pk", "--dir", td, "--python"])
            self.assertEqual(m24.main(["pack", os.path.join(td, "pk"), os.path.join(td, "out")]), 0)
            with zipfile.ZipFile(os.path.join(td, "out", "pk-0.1.0.24mod")) as z:
                names = z.namelist()
            self.assertIn("mod.json", names)
            self.assertNotIn("AGENTS.md", names)
            write(os.path.join(td, "pk"), "mod.json", "{ broken")
            self.assertEqual(m24.main(["pack", os.path.join(td, "pk"), os.path.join(td, "out2")]), 1)
            self.assertFalse(os.path.exists(os.path.join(td, "out2")))


class CatchesMistakes(unittest.TestCase):
    """AI가 흔히 하는 실수를 위치와 함께 잡아야 한다."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.td.name, "bad")
        manifest = {"id": "Bad Mod", "name": "x", "versoin": "1", "core": ">=9.0.0", "python": "python/mian.py", "ui": "ui/index.html",
                    "events": ["socialpanel"], "settings": [
                        {"key": "a", "type": "string", "label": "a", "default": "x"},
                        {"key": "b", "type": "int", "label": "b", "default": "3", "min": 5, "max": 1},
                        {"key": "c", "type": "select", "label": "c", "default": "z", "options": ["x", "y"]},
                        {"key": "a", "type": "text", "label": "dup", "default": ""},
                        {"key": "d", "type": "text", "label": "d", "default": ""}, {"key": "d.e", "type": "text", "label": "e", "default": ""}]}
        write(self.dir, "mod.json", json.dumps(manifest))
        write(self.dir, "mod.js", "registerMod('x', function (api) {\n  var x = document.body;\n  api.on('socialpanel', function () {});\n});\n")
        write(self.dir, "python/main.py", "def start(ctx):\n    pass\n")
        write(self.dir, "ui/index.html", "<script>m24.call('nothing'); el.innerHTML = 'x';</script>")
        self.rep = v.validate(self.dir)

    def tearDown(self):
        self.td.cleanup()

    def has(self, where, text):
        return any(where in w and text in m for w, m in issues(self.rep))

    def test_manifest_mistakes(self):
        for where, text in (("version", "필수"), ("id", "형식"), ("core", "필요한데"), ("python", "mian.py"), ("events", "socialpanel"),
                            ("settings[0]", "string"), ("settings[1]", "안 맞아요"), ("settings[1]", "min이 max보다"),
                            ("settings[2]", "options 안에 없어요"), ("settings[3]", "중복"), ("settings[5]", "겹쳐요")):
            self.assertTrue(self.has(where, text), (where, text, issues(self.rep)))
        self.assertTrue(any("versoin" in w and "version" in f["fix"] for w, f in [(i["where"], i) for i in self.rep.issues]), "오타 제안")

    def test_js_ui_mistakes(self):
        self.assertTrue(self.has("mod.js:1", "registerMod"))
        self.assertTrue(self.has("mod.js:2", "브라우저"))
        self.assertTrue(self.has("mod.js:3", "socialpanel"))
        self.assertTrue(self.has("ui/index.html", "nothing"))
        self.assertTrue(self.has("ui/index.html", "HTML로 넣으면"))

    def test_python_mistakes(self):
        with tempfile.TemporaryDirectory() as td:
            m24.main(["new", "py-bad", "--dir", td, "--ui"])
            d = os.path.join(td, "py-bad")
            write(d, "python/main.py", "import requests\n\ndef start(ctx):\n    pass\n")
            self.assertTrue(any("run(ctx)" in m for _, m in issues(v.validate(d), "error")))
            write(d, "python/main.py", "import requests\n\ndef run(ctx):\n    while True:\n        pass\n\ndef ui_other():\n    return 1\n")
            r = v.validate(d)
            self.assertTrue(any("ctx.stop" in m for _, m in issues(r, "warning")), issues(r))
            self.assertTrue(any("requests" in m for _, m in issues(r, "warning")), issues(r))
            self.assertTrue(any("ui_state" in m for _, m in issues(r, "error")), issues(r))   # 뼈대 모드창이 부르는 state가 없어짐


class HotReloadWarnings(unittest.TestCase):
    def test_raw_timer_without_onunload_warns_and_onunload_needs_core_030(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(m24.main(["new", "t-hr", "--dir", td]), 0)
            d = os.path.join(td, "t-hr")
            with open(os.path.join(d, "mod.js"), "a", encoding="utf-8") as f:
                f.write("var t = setInterval(function () {}, 1000);")
            msgs = [m for w, m in issues(v.validate(d), "warning")]
            self.assertTrue(any("api.onUnload가 없어요" in m for m in msgs), msgs)
            with open(os.path.join(d, "mod.js"), "a", encoding="utf-8") as f:
                f.write("api.onUnload(function () { clearInterval(t); });")
            msgs = [m for w, m in issues(v.validate(d), "warning")]
            self.assertFalse(any("api.onUnload가 없어요" in m for m in msgs), msgs)
            self.assertFalse(any("0.3.0부터" in m for m in msgs), msgs)    # 새로 만든 모드는 core가 >=0.3.0
            mj = os.path.join(d, "mod.json")
            with open(mj, encoding="utf-8") as f:
                m = json.load(f)
            m["core"] = ">=0.2.0"
            with open(mj, "w", encoding="utf-8") as f:
                json.dump(m, f)
            msgs = [m for w, m in issues(v.validate(d), "warning")]
            self.assertTrue(any("0.3.0부터" in m for m in msgs), msgs)


if __name__ == "__main__":
    unittest.main()
