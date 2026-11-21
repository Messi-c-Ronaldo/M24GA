"""반자동 API 탐색 (M78, loader/apiscan.py) — 게임 없이 가짜 게임으로 검증 판정과 등록 규칙을 시험한다."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import apiscan  # noqa: E402


class FakeGame:
    """vsnap/vset만 흉내: 객체 하나의 스칼라 속성. mode에 따라 부작용을 낸다"""

    def __init__(self, mode="ok"):
        self.mode = mode
        self.props = {"Ctfc": 100, "Cwwb": 50, "Ceda": "2038-06-30"}
        self.cls, self.key = "db::CLUB", 50332768

    def __call__(self, argv):
        if argv[0] == "vsnap":
            return {"cls": self.cls, "top": "0x1", "key": self.key, "kind": "club", "props": dict(self.props)}
        code = argv[3]
        if "--value" not in argv:
            if code == "Zemp":
                return {"error": "오류: 스칼라가 아니에요 (empty)"}
            v = self.props[code]
            return {"t": "date", "before": 1, "beforeIso": v} if code == "Ceda" else {"t": "int", "before": v}
        val = json.loads(argv[argv.index("--value") + 1])
        if self.mode == "swap" and code == "Ctfc" and val != 100:
            self.cls = "db::OTHER"                 # 객체가 바뀜 (Ptyp 사고 흉내)
            return {"t": "int", "ok": 1, "before": 100, "after": 100}
        if self.mode == "linked" and code == "Ctfc":
            self.props["Cwwb"] = val * 3 - 250      # 다른 속성이 따라 바뀜 (파생 값: 100 -> 50, 101 -> 53)
        if self.mode == "sticky" and code == "Ctfc" and val != 100:
            self.props["Cwwb"] = 999                # 되돌려도 남는 부작용
        before = self.props[code]
        self.props[code] = val
        if code == "Ceda":
            return {"t": "date", "ok": 1, "before": 1, "after": 2, "beforeIso": before, "afterIso": val}
        return {"t": "int", "ok": 1, "before": before, "after": val}


class ApiScan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._saved = (apiscan.CAND, apiscan.VCONF, apiscan.PROPS, apiscan.FIELDS)
        apiscan.CAND = os.path.join(self.tmp, "candidates.json")
        apiscan.VCONF = os.path.join(self.tmp, "verify.json")
        apiscan.PROPS = os.path.join(self.tmp, "properties.json")
        apiscan.FIELDS = os.path.join(self.tmp, "fields.json")
        shutil.copy(os.path.join(ROOT, "core", "properties.json"), apiscan.PROPS)
        shutil.copy(os.path.join(ROOT, "core", "fields.json"), apiscan.FIELDS)

    def tearDown(self):
        apiscan.CAND, apiscan.VCONF, apiscan.PROPS, apiscan.FIELDS = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_test_saves(self):
        self.assertFalse(apiscan.save_allowed({"id": 1, "nonce": 1}))
        apiscan.add_test_save(1)
        self.assertTrue(apiscan.save_allowed({"id": 1, "nonce": 1}))
        self.assertFalse(apiscan.save_allowed(None))

    def test_add_and_ids(self):
        cid, new = apiscan.add("prop", "club", "시험", ["근거"], code="Ctfc")
        self.assertEqual((cid, new), ("prop:club:Ctfc", True))
        cid2, new2 = apiscan.add("prop", "club", "시험", ["근거2"], code="Ctfc")
        self.assertFalse(new2)
        self.assertEqual(apiscan.load()["candidates"][cid]["evidence"], ["근거", "근거2"])
        fid, _ = apiscan.add("field", "player", "시험", off="0x18", type_="i32", via=["0x340"])
        self.assertEqual(fid, "field:player:0x340/0x18:i32")
        with self.assertRaises(ValueError):
            apiscan.add("field", "player", "시험", off="0x18", type_="int")

    def _rt(self, mode, code="Ctfc"):
        cid, _ = apiscan.add("prop", "club", "시험", code=code)
        c = apiscan.load()["candidates"][cid]
        g = FakeGame(mode)
        res = apiscan.roundtrip(c, "myclub", g)
        return cid, res, g

    def test_roundtrip_ok(self):
        cid, res, g = self._rt("ok")
        self.assertTrue(res["ok"], res)
        self.assertEqual((res["before"], res["wrote"], res["restored"]), (100, 101, 100))
        self.assertEqual(res["linked"], [])
        self.assertEqual(apiscan.record(cid, res), "tested")

    def test_roundtrip_date(self):
        cid, res, g = self._rt("ok", "Ceda")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["wrote"], "2038-07-01")
        self.assertEqual(g.props["Ceda"], "2038-06-30")

    def test_roundtrip_linked_is_reported_not_failed(self):
        cid, res, g = self._rt("linked")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["linked"], ["Cwwb"])

    def test_roundtrip_detects_object_swap(self):
        cid, res, g = self._rt("swap")
        self.assertFalse(res["ok"])
        self.assertTrue(any("객체가 바뀌" in p for p in res["problems"]), res)
        self.assertEqual(apiscan.record(cid, res), "failed")

    def test_roundtrip_detects_leftover(self):
        cid, res, g = self._rt("sticky")
        self.assertFalse(res["ok"])
        self.assertTrue(any("되돌린 뒤에도" in p for p in res["problems"]), res)

    def test_untestable_is_skipped(self):
        cid, res, g = self._rt("ok", "Zemp")
        self.assertTrue(res.get("skip"))
        self.assertEqual(apiscan.record(cid, res), "new")

    def test_later_judgement(self):
        self.assertEqual(apiscan._judge(100, 101, 101), ("kept", True))
        self.assertEqual(apiscan._judge(100, 101, 100), ("reverted", False))
        self.assertEqual(apiscan._judge(100, 101, 105), ("drift", True))

    def test_promote_rules(self):
        import props_catalog
        doc = props_catalog.DOC
        props_catalog.DOC = os.path.join(self.tmp, "PROPERTIES.md")
        try:
            reg = json.load(open(apiscan.PROPS, encoding="utf-8"))
            code = next(c for c, e in reg["props"].items() if "club" in e["k"] and e["t"] == "int" and c not in reg["write"]["codes"] and c not in reg["write"]["deny"])
            cid, _ = apiscan.add("prop", "club", "시험", code=code)
            with self.assertRaises(ValueError):          # roundtrip 전
                apiscan.promote(cid, "tested")
            apiscan.record(cid, {"level": "roundtrip", "ok": True})
            with self.assertRaises(ValueError):          # safe는 day·save 필요
                apiscan.promote(cid, "safe", "뜻", [0, 10])
            apiscan.record(cid, {"level": "day", "ok": True})
            apiscan.record(cid, {"level": "save", "ok": True})
            self.assertEqual(apiscan.load()["candidates"][cid]["status"], "verified")
            f, n = apiscan.promote(cid, "safe", "시험 뜻", [0, 10])
            reg2 = json.load(open(apiscan.PROPS, encoding="utf-8"))
            self.assertEqual(reg2["write"]["codes"][code], {"w": "safe", "kinds": ["club"], "range": [0, 10]})
            self.assertTrue(reg2["props"][code]["ko"].startswith("시험 뜻"))
            # 금지 코드는 등록 안 됨
            cid2, _ = apiscan.add("prop", "player", "시험", code="Ptyp")
            apiscan.record(cid2, {"level": "roundtrip", "ok": True})
            with self.assertRaises(ValueError):
                apiscan.promote(cid2, "tested")
        finally:
            props_catalog.DOC = doc


if __name__ == "__main__":
    unittest.main()
