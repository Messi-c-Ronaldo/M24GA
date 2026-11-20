"""함수 등록부의 클래스 기반 주소(vf)와 다시 찾기 (M57, 코어 0.38.0)."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import funcmap  # noqa: E402
import rtti  # noqa: E402

EXE = rtti.DEFAULT_EXE


def funcs():
    with open(os.path.join(ROOT, "core", "functions.json"), encoding="utf-8") as f:
        return json.load(f)["functions"]


class Format(unittest.TestCase):
    def test_vf_shape(self):
        n = 0
        for name, f in funcs().items():
            vf = f.get("vf")
            if vf is None:
                continue
            n += 1
            self.assertEqual(set(vf), {"class", "off", "index"}, name)
            self.assertIsInstance(vf["class"], str)
            self.assertGreaterEqual(vf["index"], 0)
            self.assertGreaterEqual(vf["off"], 0)
        self.assertGreater(n, 0)

    def test_owner_prefers_base(self):
        data = {"classes": {"A": {"bases": []}, "B": {"bases": ["A"]}}}
        self.assertEqual(funcmap.owner([("B", 0, 3), ("A", 0, 3)], data), {"class": "A", "off": 0, "index": 3})


@unittest.skipUnless(os.path.exists(EXE), "fm.exe 없음")
class Game(unittest.TestCase):
    def test_all_signatures(self):
        res = funcmap.check(funcs(), EXE, deep=False)
        self.assertEqual([n for n, r in res.items() if not r["ok"]], [])

    def test_relocate_moved_virtuals(self):
        f = copy.deepcopy(funcs())
        moved = [n for n, x in f.items() if x.get("vf")][:3]
        want = {n: f[n]["rva"] for n in moved}
        for n in moved:
            f[n]["rva"] = hex(int(f[n]["rva"], 16) + 0x40)   # 빌드가 바뀐 척
        self.assertEqual(funcmap.relocated(f, EXE), want)


if __name__ == "__main__":
    unittest.main()
