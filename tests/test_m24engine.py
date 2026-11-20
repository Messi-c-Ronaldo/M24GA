"""pylib/m24engine.py 시험 (DynamicME, E03): .jsb 읽기·쓰기, 엔진 팩 계획.
게임이 설치돼 있으면 원본 simatch.fmf의 표가 바이트까지 같게 되돌아오는지도 본다."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pylib"))
import m24engine as E  # noqa: E402

GAME = r"C:\Program Files\Epic Games\FootballManager24"
HAS_GAME = os.path.exists(os.path.join(GAME, "data", "simatch.fmf"))


class Jsb(unittest.TestCase):
    def test_roundtrip_values(self):
        v = {"b": [0, 1, -7, 7, 8, -8, 2 ** 31 - 1, 2 ** 32 - 1, 2 ** 40, 0.0, 1.0, 12.0, 0.25],
             "a": "x" * 20, "s": "short", "o": {str(i): i for i in range(20)}, "n": None}
        b = E.jsb_dumps(v)
        self.assertEqual(E.jsb_loads(b), v)
        self.assertEqual(b[0], 0x6A)   # 객체, 항목 5개

    def test_inline_rules(self):
        self.assertEqual(E.jsb_dumps(0), bytes([0x82]))
        self.assertEqual(E.jsb_dumps(8), bytes([0x02, 8, 0, 0, 0]))
        self.assertEqual(E.jsb_dumps(0.0), bytes([0x17]))
        self.assertEqual(E.jsb_dumps(1.0), bytes([0x27]))
        self.assertEqual(E.jsb_dumps(12.0)[0], 0x07)

    def test_loose_json(self):
        t = '{\n  // 주석\n  "a": 1, // 끝 주석\n  "b": [1, 2,],\n}'
        self.assertEqual(E.json_loads_loose(t), {"a": 1, "b": [1, 2]})


@unittest.skipUnless(HAS_GAME, "게임이 설치돼 있지 않음")
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = E.fmf_files(os.path.join(GAME, "data", "simatch.fmf"))
        cls.orig = E.load_game_original(GAME)

    def test_all_jsb_roundtrip(self):
        n = 0
        for k, b in self.files.items():
            if k.endswith(".jsb"):
                self.assertEqual(E.jsb_dumps(E.jsb_loads(b)), b, k); n += 1
        self.assertGreater(n, 10)

    def test_shapes(self):
        w = E.weights_entries(self.orig["weights"])
        self.assertTrue(all(len(ints) == 156 for _, ints in w))
        p = E.physics_entries(self.orig["physics"], self.orig["physics"])
        self.assertEqual(len(p[0][1]), 30); self.assertEqual(len(p[0][2]), 7); self.assertEqual(len(p[0][3]), 39)
        self.assertEqual(len(E.momentum_rows(self.orig["momentum"])), 48)
        r = E.ratings_entries(self.orig["ratings"])
        self.assertEqual([t[0] for t in r], sorted([t[0] for t in r], reverse=True))

    def test_plan_original_is_clean(self):
        mem = {"momentum": {"rows": [list(x) for x in E.momentum_rows(self.orig["momentum"])]},
               "ratings": {"entries": [{"ver": list(v), "roles": roles} for v, _, _, roles in E.ratings_entries(self.orig["ratings"])]}}
        writes, notes = E.plan(self.orig, self.orig, mem)
        self.assertEqual([lv for lv, _ in notes if lv in ("warn", "skip")], [])
        self.assertEqual({t for t, _ in writes}, {"weights", "physics", "momentum", "ratings"})

    def test_styles_original(self):
        st = self.orig["styles"]["styles"]
        self.assertEqual(len(st), 10)                       # clean_slate(스타일 id 없음)는 빼요: 게임 메모리도 10개
        self.assertEqual(st[0]["folder"], "control_possession")
        self.assertEqual(st[0]["attr"][0], [0, 11, 15])
        self.assertIn([40, -1, -1], st[1]["attr"])           # 거친 태클 허용 -1 = 메모리 255

    def test_styles_plan(self):
        import copy
        mem = {"styles": [{"folder": s["folder"], "attr": [[x & 0xff for x in r] for r in s["attr"]],
                           "tend": [[x & 0xff for x in r] for r in s["tend"]]} for s in self.orig["styles"]["styles"]]}
        self.assertEqual(E.styles_plan(self.orig["styles"], mem), ([], []))   # 원본 = 메모리: 쓸 것 없음 (-1 = 255)
        pk = copy.deepcopy(self.orig["styles"])
        pk["styles"][0]["attr"][0][2] = 17
        pk["styles"][0]["tend"].append([75, 13, 19])
        pk["styles"][1]["tend"].append([76, -5, 300])        # 범위 밖 → 뺌
        w, notes = E.styles_plan(pk, mem)
        self.assertEqual(len(w), 1)
        specs = w[0][1]["styles"]
        self.assertEqual([s["folder"] for s in specs], ["control_possession"])
        self.assertEqual(specs[0]["attr"][0], [0, 11, 17])
        self.assertEqual(specs[0]["tend"][-1], [75, 13, 19])
        self.assertEqual(sorted(specs[0]), ["attr", "folder", "tend"])
        self.assertEqual([lv for lv, _ in notes], ["warn"])
        w, notes = E.styles_plan(pk, {"error": "아직 없어요"})
        self.assertEqual((w, notes), ([], [("info", E.STYLES_WAIT)]))

    def test_xg(self):
        import copy
        xg = self.orig["xg"]
        self.assertEqual(sorted(xg), ["0.0.0.0", "23.1.1.9", "23.7.0.5", "23.9.9.1", "24.1.2.3"])
        self.assertEqual(len(xg["24.1.2.3"]), 11)
        # 메모리 모양 (engineDump 'xg'): 계수 = 이름 abc 순서 f32, 절편 f32
        mem = {"models": [{"ver": [int(x) for x in v.split(".")],
                           "coef": {str(E.XG_TYPES.index(st)): [E.xg_f32(d["coefficients"][k]) for k in sorted(d["coefficients"])] for st, d in t.items()},
                           "icpt": {str(E.XG_TYPES.index(st)): E.xg_f32(d["intercept"]) for st, d in t.items()}} for v, t in xg.items()]}
        self.assertEqual(E.xg_plan(xg, mem), ([], []))
        pk = copy.deepcopy(xg)
        pk["24.1.2.3"]["free_kicks"]["intercept"] = -42825701       # 빅토리 엔진 04·06·07
        pk["24.1.2.3"]["headers"]["coefficients"]["extra"] = 1        # 계수 수가 다르면 뺌
        w, notes = E.xg_plan(pk, mem)
        self.assertEqual(w, [("xg", {"models": [{"ver": [24, 1, 2, 3], "coef": {}, "icpt": {"3": E.xg_f32(-42825701)}}]})])
        self.assertEqual([lv for lv, _ in notes], ["skip"])
        # .jsb 칸에 JSON 글이 든 팩도 읽어요
        b = '﻿{"intercept": 5, "coefficients": {"a": 1}, "version_number": {"version_year": 24, "version_release": 1, "version_major": 2, "version_minor": 3}}'.encode("utf-8")
        self.assertEqual(E.xg_collect([("simatch/expected_goals/models/24_1_2_3/coefficient_output_penalties.jsb", b)]),
                         {"24.1.2.3": {"penalties": {"intercept": 5, "coefficients": {"a": 1}}}})

    def test_qme_sync(self):
        import copy, tempfile
        with tempfile.TemporaryDirectory() as g:
            self.assertEqual(E.qme_sync(g, {}, self.orig), ([], []))            # 폴더 없음, 원본 그대로: 할 일 없음
            pk = copy.deepcopy({t: self.orig[t] for t in E.QME_TABLES})
            pk["qme_stat"]["values"][0]["relevant_attributes"].append("stamina")
            self.assertEqual([lv for lv, _ in E.qme_sync(g, pk, self.orig)[1]], ["skip"])
            d = os.path.join(g, "data", "simatch"); os.makedirs(d)
            for t in E.QME_TABLES:
                with open(os.path.join(d, E.TABLE_FILES[t] + ".jsb"), "wb") as f:
                    f.write(E.jsb_dumps(self.orig[t]))
            ch, notes = E.qme_sync(g, pk, self.orig)
            self.assertEqual(ch, ["qme_stat_relevant_attribute_data.jsb"])
            self.assertEqual(E.jsb_loads(open(os.path.join(d, "qme_stat_relevant_attribute_data.jsb"), "rb").read()), pk["qme_stat"])
            self.assertEqual(E.qme_sync(g, pk, self.orig), ([], []))            # 이미 같음
            self.assertEqual(E.qme_sync(g, {}, self.orig)[0], ["qme_stat_relevant_attribute_data.jsb"])   # 원본으로
            self.assertEqual(open(os.path.join(d, "qme_stat_relevant_attribute_data.jsb"), "rb").read(), E.jsb_dumps(self.orig["qme_stat"]))

    def test_plan_flags_unknown_names(self):
        import copy
        pk = copy.deepcopy(self.orig)
        pk["momentum"]["values"][0]["VERTICAL_ZONES"] = "FINAL_FIVTH"
        pk["physics"]["version_array"][0]["min_turning_rate"] = 65
        mem = {"momentum": {"rows": [list(x) for x in E.momentum_rows(self.orig["momentum"])]},
               "ratings": {"entries": [{"ver": list(v), "roles": roles} for v, _, _, roles in E.ratings_entries(self.orig["ratings"])]}}
        _, notes = E.plan({"momentum": pk["momentum"], "physics": pk["physics"]}, self.orig, mem)
        txt = " ".join(m for _, m in notes)
        self.assertIn("FINAL_FIVTH", txt); self.assertIn("min_turning_rate", txt)


if __name__ == "__main__":
    unittest.main()


class FindBytes(unittest.TestCase):
    """cli.py find-bytes 패턴 만들기 (E09)."""
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(HERE, "..", "loader"))
        import cli
        cls.f = staticmethod(cli.find_bytes_pattern)

    def test_patterns(self):
        self.assertEqual(self.f(["0b", "??", "0F10"]), "0b ?? 0f 10")
        self.assertEqual(self.f(["--i32", "11", "?", "-1"]), "0b 00 00 00 ?? ?? ?? ?? ff ff ff ff")
        self.assertEqual(self.f(["--u8", "0", "11", "15"]), "00 0b 0f")
        self.assertEqual(self.f(["--f32", "1.0"]), "00 00 80 3f")
        with self.assertRaises(ValueError):
            self.f(["zz"])
