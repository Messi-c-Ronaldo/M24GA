"""기능 등록부와 권한 시험 (M10). 게임·frida 없이, 임시 폴더만 쓴다."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import caps  # noqa: E402
import m24  # noqa: E402
import mods as modlib  # noqa: E402
import validate as v  # noqa: E402

HELPERS = {"api", "DIR", "hash64", "dbg"}   # 기능이 아닌 기본 도구 (d.ts에는 있지만 등록부에 없어도 됨)


def msgs(rep, level):
    return [(i["where"], i["message"]) for i in rep.issues if i["level"] == level]


class Registry(unittest.TestCase):
    def test_entries_are_well_formed(self):
        reg = caps.registry()
        self.assertEqual(reg["core"], modlib.CORE_VERSION)
        seen = set()
        for c in reg["capabilities"]:
            self.assertNotIn(c["name"], seen)
            seen.add(c["name"])
            self.assertRegex(c["name"], r"^[a-z]+\.[A-Za-z.]+$")
            self.assertIn(c["risk"], caps.RISK_ORDER)
            for k in ("title", "desc", "uses", "builds", "example", "since"):
                self.assertTrue(c.get(k) is not None, (c["name"], k))
        self.assertEqual(set(reg["risks"]), set(caps.RISK_ORDER))
        self.assertEqual([k for k in caps.RISK_ORDER if reg["risks"][k]["auto"]], ["read", "ui"])

    def test_every_core_name_in_types_is_registered(self):
        with open(os.path.join(ROOT, "docs", "types", "m24ga.d.ts"), encoding="utf-8") as f:
            dts = f.read()
        declared = set(re.findall(r"^declare (?:const|let|function) (\w+)", dts, re.M))
        used = set()
        for c in caps.registry()["capabilities"]:
            for u in c["uses"]:
                used.update(re.findall(r"\w+", u))
        missing = sorted(declared - used - HELPERS)
        self.assertEqual(missing, [], "d.ts에 있는데 기능 등록부에 없는 이름 (core/capabilities.json uses에 넣으세요)")

    def test_generated_docs_are_up_to_date(self):
        stale = []
        for path, text in m24.caps_outputs().items():
            with open(path, encoding="utf-8") as f:
                if f.read() != text:
                    stale.append(path)
        self.assertEqual(stale, [], "python -X utf8 tools/m24.py caps 로 다시 만드세요")


class Detect(unittest.TestCase):
    def test_social_feed_declares_exactly_what_it_uses(self):
        m = modlib._load_one(os.path.join(ROOT, "mods", "ai-social-feed"))
        self.assertEqual(sorted(caps.declared(m.manifest)), sorted(caps.detect(m.js_text(), m.manifest)))

    def test_patterns(self):
        js = "\n".join([
            "// setStr(x) in a comment is ignored",
            "/* Interceptor.attach(a)",
            "   still comment */",
            "var o = lookup(clubs, 1, CLUB_VT);",
            "obj.add(0x202).writeS16(180);",
            "var p = ptr('0x10');",
            "api.on('frame', function () {});",
            "var f = new File(DIR + 'a', 'w');",
        ])
        d = caps.detect(js, {"python": "python/main.py"})
        self.assertEqual(sorted(d), ["event.frame", "pc.file", "pc.python", "raw.read", "raw.write", "read.data"])
        self.assertEqual(d["read.data"], 4)
        self.assertEqual(d["pc.python"], 0)
        self.assertNotIn("ui.social.text", d)
        self.assertNotIn("raw.hook", d)

    def test_effective_and_elevated(self):
        eff = caps.effective({"capabilities": ["read.me", "nope.x"]}, "setStr(a, 'b');")
        self.assertEqual(eff, ["read.me", "ui.social.text"])
        self.assertEqual(caps.elevated(["read.me", "pc.python", "raw.hook"]), ["pc.python", "raw.hook"])
        self.assertEqual(caps.unknown({"capabilities": ["read.me", "read.datas"]}), ["read.datas"])
        self.assertEqual(caps.closest("read.datas"), "read.data")

    def test_unsupported_build(self):
        reg = caps.registry()
        c = reg["by_name"]["read.news"]
        saved = c["builds"]
        c["builds"] = ["fm24-epic-OLD"]
        try:
            self.assertEqual(caps.unsupported(["read.news", "read.me"], "fm24-epic-NEW"), ["read.news"])
            self.assertEqual(caps.unsupported(["read.news"], "fm24-epic-OLD"), [])
            self.assertEqual(caps.unsupported(["read.news"], None), [])
        finally:
            c["builds"] = saved


class Permissions(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.saved = dict(USER_MODS=modlib.USER_MODS, DEV_MODS=modlib.DEV_MODS, DATA=modlib.DATA,
                          ENABLED_PATH=modlib.ENABLED_PATH, AUTO_PATH=modlib.AUTO_PATH)
        modlib.USER_MODS = os.path.join(self.td, "user")
        modlib.DEV_MODS = os.path.join(self.td, "dev")
        modlib.DATA = os.path.join(self.td, "data")
        modlib.ENABLED_PATH = os.path.join(modlib.DATA, "enabled.json")
        modlib.AUTO_PATH = os.path.join(modlib.DATA, "autodisabled.json")
        os.makedirs(modlib.DEV_MODS)

    def tearDown(self):
        for k, val in self.saved.items():
            setattr(modlib, k, val)
        shutil.rmtree(self.td, ignore_errors=True)

    def new(self, mid, *flags):
        self.assertEqual(m24.main(["new", mid, "--dir", modlib.DEV_MODS] + list(flags)), 0)

    def by_id(self):
        return {m.id: m for m in modlib.scan()[0]}

    def test_upgrade_grants_enabled_mods_once(self):
        self.new("p-on", "--python")
        self.new("p-off", "--python")
        self.new("plain")
        modlib.set_enabled("p-off", False)
        ms = self.by_id()                                       # 첫 scan이 권한 파일을 만든다
        self.assertEqual(modlib.granted("p-on"), ["pc.python"])
        self.assertEqual(modlib.granted("p-off"), [])           # 꺼져 있던 모드는 허용하지 않는다
        self.assertEqual(ms["p-on"].needs_permission(), [])
        self.assertEqual(ms["p-off"].needs_permission(), ["pc.python"])
        self.assertEqual(ms["plain"].needs_permission(), [])    # read/ui만 쓰면 묻지 않는다
        self.assertEqual(modlib.init_permissions(list(ms.values())), [])   # 두 번째는 아무것도 안 한다

    def test_new_mod_waits_for_permission(self):
        self.by_id()                                            # 권한 파일 생성 (모드 없음)
        self.new("p-new", "--python")
        ms = self.by_id()
        m = ms["p-new"]
        self.assertTrue(modlib.is_enabled(m))
        self.assertEqual(m.needs_permission(), ["pc.python"])
        self.assertEqual(modlib.active(list(ms.values())), [])  # 허용 전에는 켜지지 않는다
        info = m.info()
        self.assertEqual(info["needs_perm"], ["pc.python"])
        self.assertTrue(any(c["name"] == "pc.python" and not c["granted"] for c in info["caps"]))
        modlib.grant("p-new", ["pc.python"])
        ms = self.by_id()
        self.assertEqual([x.id for x in modlib.active(list(ms.values()))], ["p-new"])
        modlib.revoke("p-new")
        self.assertEqual(modlib.granted("p-new"), [])

    def test_update_that_adds_a_risky_capability_asks_again(self):
        self.by_id()
        self.new("p-up", "--python")
        modlib.grant("p-up", ["pc.python"])
        with open(os.path.join(modlib.DEV_MODS, "p-up", "mod.js"), "a", encoding="utf-8") as f:
            f.write("\nvar l = Interceptor.attach(ptr(1), {}); api.onUnload(function () { l.detach(); });\n")
        m = self.by_id()["p-up"]
        self.assertEqual(m.needs_permission(), ["raw.read", "raw.hook"])   # 위험 등급 순서 (raw < hook)

    def test_unknown_capability_is_a_problem(self):
        self.new("p-bad")
        mj = os.path.join(modlib.DEV_MODS, "p-bad", "mod.json")
        with open(mj, encoding="utf-8") as f:
            d = json.load(f)
        d["capabilities"].append("read.datas")
        with open(mj, "w", encoding="utf-8") as f:
            json.dump(d, f)
        m = self.by_id()["p-bad"]
        self.assertTrue(any("read.datas" in p and "read.data'" in p for p in m.problems), m.problems)


class Validate(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.assertEqual(m24.main(["new", "vc", "--dir", self.td]), 0)
        self.d = os.path.join(self.td, "vc")

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def set_caps(self, value):
        mj = os.path.join(self.d, "mod.json")
        with open(mj, encoding="utf-8") as f:
            d = json.load(f)
        if value is None:
            d.pop("capabilities", None)
        else:
            d["capabilities"] = value
        with open(mj, "w", encoding="utf-8") as f:
            json.dump(d, f)

    def add_js(self, text):
        with open(os.path.join(self.d, "mod.js"), "a", encoding="utf-8") as f:
            f.write("\n" + text + "\n")

    def test_scaffold_is_clean(self):
        rep = v.validate(self.d)
        self.assertEqual(msgs(rep, "error"), [])
        self.assertEqual(msgs(rep, "warning"), [])

    def test_used_but_not_declared_is_error_with_line(self):
        self.add_js("api.on('socialPanel', function (ev) { setStr(ev.dst, 'x'); });")
        errs = msgs(v.validate(self.d), "error")
        self.assertTrue(any("ui.social.text" in m and w.startswith("mod.js:") for w, m in errs), errs)

    def test_unknown_name_suggests(self):
        self.set_caps(["event.socialPanel", "ui.social.txt"])
        rep = v.validate(self.d)
        self.assertTrue(any("ui.social.txt" in m for w, m in msgs(rep, "error")))
        self.assertTrue(any("ui.social.text" in i["fix"] for i in rep.issues if i["level"] == "error"))

    def test_missing_field_is_warning_with_ready_list(self):
        self.set_caps(None)
        rep = v.validate(self.d)
        self.assertEqual(msgs(rep, "error"), [])
        fixes = [i["fix"] for i in rep.issues if i["level"] == "warning"]
        self.assertTrue(any('["event.socialPanel"]' in f for f in fixes), fixes)

    def test_elevated_is_reported(self):
        self.set_caps(["event.socialPanel", "raw.write"])
        self.add_js("ptr(1).writeU8(0);")
        rep = v.validate(self.d)
        errs = msgs(rep, "error")
        self.assertTrue(any("raw.read" in m for w, m in errs), errs)   # ptr( = raw.read도 선언해야 한다
        self.assertTrue(any("raw.write" in m for w, m in msgs(rep, "info")))

    def test_rtti_use_needs_declaration(self):   # 코어 0.9.0
        self.set_caps(["event.socialPanel"])
        self.add_js("var n = className(p); if (isA(p, 'db::PERSON')) api.log(n);")
        errs = msgs(self.v_validate(), "error")
        self.assertTrue(any("read.rtti" in m for w, m in errs), errs)
        self.set_caps(["event.socialPanel", "read.rtti"])
        self.assertEqual(msgs(self.v_validate(), "error"), [])

    def v_validate(self):
        return v.validate(self.d)


if __name__ == "__main__":
    unittest.main()
