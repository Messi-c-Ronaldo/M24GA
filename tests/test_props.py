"""속성 등록부(core/properties.json) 형식 검사 (M55, 코어 0.36.0)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def load():
    with open(os.path.join(ROOT, "core", "properties.json"), encoding="utf-8") as f:
        return json.load(f)


class Props(unittest.TestCase):
    def setUp(self):
        self.reg = load()

    def test_kinds(self):
        for k, v in self.reg["kinds"].items():
            self.assertRegex(v["class"], r"^db::[A-Z_]+$", k)
            self.assertIsInstance(v["off"], int)
            self.assertTrue(v.get("ko"), k)

    def test_codes(self):
        kinds, types = set(self.reg["kinds"]), set(self.reg["types"])
        self.assertGreater(len(self.reg["props"]), 1000)
        for c, p in self.reg["props"].items():
            self.assertRegex(c, r"^[A-Za-z][A-Za-z0-9 ]{3}$", c)
            self.assertIn(p["t"], types, c)
            self.assertTrue(set(p["k"]) <= kinds, c)
            if not p.get("stale"):
                self.assertTrue(p["k"], c)
            for k in p.get("keys", []):
                self.assertIsInstance(k, str)
            if p.get("verified"):
                self.assertTrue(p.get("ko"), c)

    def test_block(self):
        for c, ks in self.reg["block"].items():
            self.assertRegex(c, r"^[A-Za-z][A-Za-z0-9 ]{3}$")
            self.assertTrue(set(ks) <= set(self.reg["kinds"]))

    def test_no_game_text(self):
        # 등록부에는 게임 글(영어 이름·값 미리보기)을 넣지 않는다
        for c, p in self.reg["props"].items():
            self.assertFalse({"name", "sample"} & set(p), c)

    def test_compact(self):
        import bundle
        cp = bundle.props_compact(self.reg)
        self.assertEqual(list(cp["kinds"]), list(self.reg["kinds"]))
        self.assertIn("CMli", cp["block"])
        t, bits = cp["p"]["TpoN"]
        self.assertEqual(t, "int")
        self.assertTrue(bits & 1)   # team

    def test_write(self):
        # 쓰기 등록부 (코어 0.42.0, M71): 종류·단계 형식, safe는 범위 필수, deny는 쓰기 목록에 없음, 스칼라 값 종류만
        w = self.reg["write"]
        kinds = set(self.reg["kinds"])
        self.assertIn("Ptyp", w["deny"])
        for c in ("DELE", "duni"):
            self.assertIn(c, w["deny"])
        nsafe = 0
        for c, e in w["codes"].items():
            self.assertIn(c, self.reg["props"], c)
            self.assertNotIn(c, w["deny"], c)
            self.assertIn(e["w"], ("safe", "tested"), c)
            self.assertTrue(e["kinds"] and set(e["kinds"]) <= kinds, c)
            self.assertIn(self.reg["props"][c]["t"], ("int", "u32", "num", "bool", "date"), c)
            if e["w"] == "safe":
                nsafe += 1
                self.assertEqual(len(e["range"]), 2, c)
                self.assertLess(e["range"][0], e["range"][1], c)
                self.assertTrue(self.reg["props"][c].get("ko"), "safe 코드는 뜻(ko)이 있어야 해요: " + c)
                for rel in ("gte", "lte"):
                    if rel in e:
                        self.assertIn(e[rel], w["codes"], c)
        self.assertGreaterEqual(nsafe, 20)

    def test_write_compact(self):
        import bundle
        cp = bundle.props_compact(self.reg)
        self.assertEqual(cp["w"]["PPAB"][0], "safe")
        self.assertEqual(cp["w"]["PPAB"][4], "PCAB")   # gte
        self.assertIn("Ptyp", cp["deny"])
        self.assertNotIn("Ptyp", cp["w"])

    def test_core_has_write(self):
        with open(os.path.join(ROOT, "core", "core.js"), encoding="utf-8") as f:
            core = f.read()
        with open(os.path.join(ROOT, "core", "modhost.js"), encoding="utf-8") as f:
            host = f.read()
        for s in ("function makePropWriter(", "add(0x18).readPointer()", "M24GA.propKey = propKey", "propset:"):
            self.assertIn(s, core)
        for s in ("function m24gaSetProp(", "function m24gaSetProps(", "setProp: function", "setProps: function", "w.ui && M24GA.runOnUi"):
            self.assertIn(s, host)

    def test_docs_fresh(self):
        import props_catalog
        with open(props_catalog.DOC, encoding="utf-8") as f:
            self.assertEqual(f.read(), props_catalog.docs(self.reg), "docs/PROPERTIES.md가 등록부와 다릅니다: tools/props_catalog.py --docs")

    def test_core_has_api(self):
        with open(os.path.join(ROOT, "core", "core.js"), encoding="utf-8") as f:
            core = f.read()
        self.assertIn("var M24_PROPS = ", core)
        for fn in ("function propGet(", "function propsAll(", "function propInfo(", "function propDeref("):
            self.assertIn(fn, core)


if __name__ == "__main__":
    unittest.main()
