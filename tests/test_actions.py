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

    def test_ui(self):   # M65: 실행 쪽 전역 객체와 처리기 이벤트
        A = self.reg["actions"]
        ui = [e["ui"] for e in A.values() if "ui" in e]
        self.assertGreaterEqual(len(ui), 190)
        for u in ui:
            self.assertRegex(u["obj"], r"^0x[0-9a-f]+$")
            for ev in u["events"]:
                self.assertEqual(len(ev), 4)
        self.assertEqual(A["SUBS"]["ui"]["events"], ["stSU"])   # M65 실기: 구독
        self.assertEqual(A["USUB"]["ui"]["events"], ["stSU"])
        objs = [u["obj"] for u in ui]
        self.assertEqual(len(objs), len(set(objs)))   # 액션마다 다른 객체

    def test_compact(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "loader"))
        import bundle
        c = bundle.actions_compact(self.reg)
        self.assertEqual(c["SUBS"][0], "SUBSCRIBE_ACTION")
        self.assertGreater(c["SUBS"][1], 0)
        self.assertEqual(c["SUBS"][2], ["stSU"])
        self.assertEqual(c["PmcP"][3], ["pmcE"])   # M65: 누름 = 확인 창
        self.assertEqual(c["PmcP"][4], "pmcC")     # 확인 뒤 = 실기로 주장 바뀜
        self.assertTrue(c["Hres"][5])              # 처리기가 비어 있음 (사임은 다른 길)

    def test_docs(self):
        with open(os.path.join(ROOT, "docs", "ACTIONS.md"), encoding="utf-8") as f:
            doc = f.read()
        for aid in ("PGoH", "AtSo"):
            self.assertIn("`%s`" % aid, doc)


if __name__ == "__main__":
    unittest.main()
