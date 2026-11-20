"""RTTI 표(tools/rtti.py)와 CLI explore 출력 시험 (M19). 게임 없이. fm.exe가 있으면 실제 파일로도 확인한다."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "loader"))
import rtti  # noqa: E402
import cli  # noqa: E402


class Demangle(unittest.TestCase):
    def test_names(self):
        self.assertEqual(rtti.demangle(".?AVACTUAL_PLAYER@db@@"), "db::ACTUAL_PLAYER")
        self.assertEqual(rtti.demangle(".?AVTRANSFER_VALUE_LABEL@@"), "TRANSFER_VALUE_LABEL")
        self.assertEqual(rtti.demangle(".?AUX@b@a@@"), "a::b::X")
        # 템플릿은 앞뒤만 뗀다
        self.assertEqual(rtti.demangle(".?AV?$MANUAL_SINGLETON@VX@@@sicore@@"), "?$MANUAL_SINGLETON@VX@@@sicore")


@unittest.skipUnless(os.path.exists(rtti.DEFAULT_EXE), "fm.exe 없음")
class RealExe(unittest.TestCase):
    """FM24 Epic 2026-10-24 빌드에서 코어가 쓰는 vtable이 기대한 클래스인지 (M19에서 확인한 값)."""

    @classmethod
    def setUpClass(cls):
        cls.data = rtti.load()

    def test_known_vtables(self):
        if os.path.getsize(rtti.DEFAULT_EXE) != 489128448:
            self.skipTest("다른 빌드")
        vt = self.data["vtables"]
        self.assertEqual(vt["0x5a4e958"]["name"], "db::ACTUAL_PLAYER")
        self.assertEqual(vt["0x5a4ee78"], {"name": "db::ACTUAL_PLAYER", "off": 0x278})   # 사람 데이터 객체 = 선수 +0x278
        self.assertEqual(vt["0x5a78848"]["name"], "db::TEAM")
        self.assertEqual(vt["0x5a51f38"]["name"], "db::CLUB")
        self.assertEqual(vt["0x5a6a388"], {"name": "db::HUMAN_NON_PLAYER", "off": 0x450})
        self.assertIn("db::PLAYER", self.data["classes"]["db::ACTUAL_PLAYER"]["bases"])
        self.assertGreater(len(self.data["classes"]), 10000)


class ExploreText(unittest.TestCase):
    def test_slot_lines(self):
        self.assertIn("-> db::TEAM", cli._slot_text({"off": 0x130, "hex": "00000000de960c00", "cls": "db::TEAM"}))
        self.assertIn("(+0x278 위치)", cli._slot_text({"off": 0, "hex": "0", "cls": "db::ACTUAL_PLAYER", "clsOff": 0x278}))
        self.assertIn("vtable db::CLUB", cli._slot_text({"off": 0, "hex": "0", "mod": "+0x5a51f38", "vtableOf": "db::CLUB"}))
        self.assertIn("RTTI 없음", cli._slot_text({"off": 8, "hex": "0", "ptr": True}))
        line = cli._slot_text({"off": 0x150, "hex": "07f37cb107f300ba", "i32": [133365946, 133397681],
                               "i16": [186, 2035, 31921, 2035], "date": ["2035-07-05", "2035-06-26"]})
        self.assertIn("날짜 2035-07-05, 2035-06-26", line)
        self.assertEqual(cli._slot_text({"off": 0x1d0, "error": "읽기 실패"}), "+0x1d0  읽기 실패")


class FindTools(unittest.TestCase):   # M21
    def test_parse_value(self):
        self.assertEqual(cli._parse_value("100..200", None), (100.0, 200.0))
        lo, hi = cli._parse_value("245억", None)                       # 245억 원 / 1664.7, 기본 오차 2%
        self.assertLess(lo, 14852187)
        self.assertGreater(hi, 14852187)                                # 화면 245억 = 실제 247.2억도 잡힌다
        self.assertEqual(cli._parse_value("1,000", None), (1000.0, 1000.0))
        self.assertEqual(cli._parse_value("10", 0.1), (9.0, 11.0))

    def test_kind_of(self):
        self.assertEqual(cli._kind_of("db::ACTUAL_PLAYER", []), "player")
        self.assertEqual(cli._kind_of("db::ACTUAL_PLAYER_AND_NON_PLAYER", ["db::ACTUAL_PLAYER"]), "player")
        self.assertIsNone(cli._kind_of("db::NATION", []))

    def test_opt(self):
        a = ["x", "--secs", "5", "--rw"]
        self.assertEqual(cli._opt(a, "--secs"), "5")
        self.assertTrue(cli._opt(a, "--rw", flag=True))
        self.assertEqual(a, ["x"])

    @unittest.skipUnless(os.path.exists(rtti.DEFAULT_EXE), "fm.exe 없음")
    def test_func_of(self):
        pe = rtti.PE(rtti.DEFAULT_EXE)
        if os.path.getsize(rtti.DEFAULT_EXE) != 489128448:
            self.skipTest("다른 빌드")
        self.assertEqual(pe.func_of(0x61ae80), (0x61ae70, 0x61bdd6))     # 소셜 패널 갱신 함수 (코어가 거는 곳)
        self.assertIsNone(pe.func_of(0x10))


if __name__ == "__main__":
    unittest.main()
