"""게임 액션 등록부(core/actions.json) 형식 검사 (M62)."""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Actions(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "core", "actions.json"), encoding="utf-8") as f:
            self.reg = json.load(f)

    def test_shape(self):
        A = self.reg["actions"]
        self.assertGreaterEqual(len(A), 190)
        classes = set()
        for aid, e in A.items():
            self.assertEqual(len(aid), 4, aid)
            self.assertRegex(e["class"], r"^[A-Z0-9_]+$")
            self.assertIsInstance(e["protected"], bool)
            for k in e.get("keys", []):
                self.assertEqual(len(k), 4)
            classes.add(e["class"])
        self.assertEqual(len(classes), len(A))   # 클래스 하나 = id 하나

    def test_known(self):
        A = self.reg["actions"]
        self.assertEqual(A["PGoH"]["class"], "GO_ON_HOLIDAY_ACTION")   # M38 휴가
        self.assertEqual(A["AtSo"]["class"], "ADD_PLAYERS_TO_SHORTLIST_ACTION")

    def test_docs(self):
        with open(os.path.join(ROOT, "docs", "ACTIONS.md"), encoding="utf-8") as f:
            doc = f.read()
        for aid in ("PGoH", "AtSo"):
            self.assertIn("`%s`" % aid, doc)


if __name__ == "__main__":
    unittest.main()
