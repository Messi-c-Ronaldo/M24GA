"""빌드 진단 보고서 (M48): 다른 칸이 보이고, 개인 경로가 지워지는지."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loader"))
import buildreport  # noqa: E402

BUILD = {"name": "T", "module_size": 100, "sig": {"0x10": "aa", "0x20": "bb"}, "vt": {"0x30": "0x1"}, "hook_guard": {"0x40": "cc"}}


class BuildReport(unittest.TestCase):
    def test_diff_shown(self):
        info = {"size": 200, "path": os.path.join(os.path.expanduser("~"), "game", "fm.exe"),
                "sig": {"0x10": "aa", "0x20": "XX", "0x40": "cc"}, "vt": {"0x30": "0x2"}}
        t = buildreport.build_text(info, "다름", [BUILD], "9.9.9", with_file=False)
        self.assertIn("서명 0x20 다름: 기대 bb / 실제 XX", t)
        self.assertIn("vtable 0x30 다름", t)
        self.assertIn("모듈 크기: 기대 100 / 실제 200 다름", t)
        self.assertIn("4칸 중 다른 것 2칸", t)
        self.assertNotIn("서명 0x10", t)

    def test_no_personal_path(self):
        home = os.path.expanduser("~")
        t = buildreport.build_text({"size": 1, "path": os.path.join(home, "x", "fm.exe"), "sig": {}, "vt": {}},
                                   "이유 " + home, [BUILD], "9.9.9", with_file=False)
        self.assertNotIn(home, t)

    def test_error_info(self):
        t = buildreport.build_text({"error": 1}, "읽기 실패", [BUILD], "9.9.9", with_file=False)
        self.assertIn("읽기 실패", t)


if __name__ == "__main__":
    unittest.main()
