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
