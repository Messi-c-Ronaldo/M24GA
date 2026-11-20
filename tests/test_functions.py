"""함수 등록부 시험 (M22): core/functions.json 형식, 실제 fm.exe 서명, validate 규칙, FUNCTIONS.md 최신. 게임 없이."""
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
import rtti  # noqa: E402
import validate as v  # noqa: E402

HEX = re.compile(r"^0x[0-9a-f]+$")
ARG = {"ptr", "i32", "u32", "i64", "bool"}


class Registry(unittest.TestCase):
    def setUp(self):
        self.fr = caps.functions()["functions"]

    def test_entries(self):
        for n, f in self.fr.items():
            with self.subTest(fn=n):
                self.assertRegex(n, r"^[a-z]+(\.[A-Za-z0-9]+)+$")
                self.assertRegex(f["rva"], HEX)
                for t in f.get("args") or []:
                    self.assertIn(t, ARG)
                if f.get("argNames"):
                    self.assertEqual(len(f["argNames"]), len(f["args"]))
                self.assertIn(f.get("ret", "void"), ARG | {"void"})
                self.assertTrue(f.get("desc"))
                self.assertIn("verified", f)
                if f.get("owner") == "core" and f.get("call"):
                    self.assertNotIn("hook", f, "코어가 부르기만 하는 함수 (M29)")
                elif f.get("owner") == "core":
                    self.assertIn(f.get("event"), ("socialPanel", "frame", "dateChanged", "saveLoaded", "panel"))   # panel = 게임 안 패널 (M45, api.panel로 나눠 줌)
                else:
                    self.assertIn(f.get("hook", "observe"), ("observe", "modify"))
                    if f.get("hook") == "modify":
                        self.assertTrue(f.get("verified"), "바꾸기는 인자 뜻을 확인한 함수만")
                if f.get("scale"):   # V06 (코어 0.17.0): api.scale 대상 = int 반환, 열쇠 인자가 포인터, 확인된 modify 함수
                    sc = f["scale"]
                    self.assertEqual(f.get("ret"), "i32")
                    self.assertEqual(f.get("hook"), "modify")
                    self.assertEqual(f["args"][sc["key"]], "ptr")
                    self.assertLess(sc["min"], sc["max"])
                if f.get("sig"):
                    self.assertRegex(f["sig"]["off"], HEX)
                    self.assertRegex(f["sig"]["hex"], r"^([0-9a-f]{2})+$")
                    self.assertGreaterEqual(int(f["sig"]["off"], 16), 0x10, "앞 16바이트는 후킹이 덮어쓴다")

    def test_act_danger_words(self):
        # M29: act click이 --yes 없이 누르지 않는 버튼 글 (core.js ACT_DANGER, 15글자 이하만). JS 정규식을 그대로 꺼내 Python re로 확인
        import re
        src = open(os.path.join(ROOT, "core", "core.js"), encoding="utf-8").read()
        m = re.search(r"var ACT_DANGER = /(.+)/i;", src)
        rx = re.compile(m.group(1), re.I)

        def danger(t):
            return len(t) <= 15 and bool(rx.search(t))
        for t in ("제의 수락", "계약 제의", "거절", "선수 방출", "해고", "Accept Offer", "임대 제의하기"):
            self.assertTrue(danger(t), t)
        for t in ("선수단", "확인", "계속", "답변 요망", "모두 읽음으로 표시", "알-이티하드, 비니시우스 주니오르에 대해 제의"):
            self.assertFalse(danger(t), t)

    @unittest.skipUnless(os.path.exists(rtti.DEFAULT_EXE), "fm.exe 없음")
    def test_signatures_match_exe(self):
        if os.path.getsize(rtti.DEFAULT_EXE) != 489128448:
            self.skipTest("다른 빌드")
        pe = rtti.PE(rtti.DEFAULT_EXE)
        for n, f in self.fr.items():
            with self.subTest(fn=n):
                rva = int(f["rva"], 16)
                self.assertEqual(pe.func_of(rva)[0], rva, "함수 시작이어야 한다")
                o = pe.off(rva + int(f["sig"]["off"], 16))
                self.assertEqual(pe.m[o:o + len(f["sig"]["hex"]) // 2].hex(), f["sig"]["hex"])

    def test_gates(self):
        # 몸값모드 V03 (코어 0.15.0): 게이트 = 범위 함수(시작 + 서명) + vtable 칸 + 원래 함수 바이트. 실제 fm.exe에서 칸이 원래 함수를 가리켜야 한다
        gates = caps.functions().get("gates") or {}
        self.assertIn("valuation.squadPremiumHumanAsAi", gates)
        self.assertIn("valuation.sellerPlanHumanAsAi", gates)   # V05: 같은 칸 두 번째 게이트 (코어 0.16.0)
        same_build = os.path.getsize(rtti.DEFAULT_EXE) == 489128448
        pe = rtti.PE(rtti.DEFAULT_EXE) if same_build else None
        for n, g in gates.items():
            with self.subTest(gate=n):
                self.assertRegex(n, r"^[a-z]+(\.[A-Za-z0-9]+)+$")
                for k in ("desc", "source"):
                    self.assertTrue(g.get(k))
                self.assertIn("verified", g)
                self.assertIn(g.get("answer", "null"), ("null", "false"))
                for h in (g["scope"]["rva"], g["vtable"], g["slot"], g["impl"]["rva"], g["scope"]["sig"]["off"]):
                    self.assertRegex(h, HEX)
                self.assertGreaterEqual(int(g["scope"]["sig"]["off"], 16), 0x10, "앞 16바이트는 Interceptor가 덮어쓴다")
                if not pe:
                    continue
                rva = int(g["scope"]["rva"], 16)
                self.assertEqual(pe.func_of(rva)[0], rva, "범위는 함수 시작이어야 한다")
                o = pe.off(rva + int(g["scope"]["sig"]["off"], 16))
                self.assertEqual(pe.m[o:o + len(g["scope"]["sig"]["hex"]) // 2].hex(), g["scope"]["sig"]["hex"])
                o = pe.off(int(g["impl"]["rva"], 16))
                self.assertEqual(pe.m[o:o + len(g["impl"]["hex"]) // 2].hex(), g["impl"]["hex"])
                o = pe.off(int(g["vtable"], 16) + int(g["slot"], 16))
                self.assertEqual(int.from_bytes(pe.m[o:o + 8], "little") - 0x140000000, int(g["impl"]["rva"], 16), "vtable 칸이 원래 함수를 가리켜야 한다")

    def test_docs_up_to_date(self):
        path = os.path.join(ROOT, "docs", "FUNCTIONS.md")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), caps.functions_markdown(), "python -X utf8 tools/m24.py caps 로 다시 만드세요")
        self.assertIn(path, m24.caps_outputs())


class Validate(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "mod.json"), "w", encoding="utf-8") as f:
            json.dump({"id": "fn", "name": "fn", "version": "1.0.0", "core": ">=0.11.0", "js": "mod.js", "capabilities": ["hook.function"]}, f)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def issues(self, js, level):
        with open(os.path.join(self.d, "mod.js"), "w", encoding="utf-8") as f:
            f.write(js)
        return [i["message"] + " / " + i["fix"] for i in v.validate(self.d).issues if i["level"] == level]

    def test_ok(self):
        self.assertEqual(self.issues("api.hook('player.updateAskingPrice', { after: function (ev) { api.log(ev.caller); } });\n", "error"), [])

    def test_unknown_and_core(self):
        errs = self.issues("api.hook('player.updateAskingprice', {});\napi.hook('ui.frameTick', {});\n", "error")
        self.assertTrue(any("모르는 함수" in e and "player.updateAskingPrice" in e for e in errs), errs)
        self.assertTrue(any("api.on('frame'" in e for e in errs), errs)

    def test_set_on_observe_warns(self):
        w = self.issues("api.hook('player.updateAskingPrice', { after: function (ev) { ev.setRet(1); } });\n", "warning")
        self.assertTrue(any("보기만" in x for x in w), w)

    def test_detect(self):
        self.assertIn("hook.function", caps.detect("api.hook('x', {});"))


if __name__ == "__main__":
    unittest.main()
