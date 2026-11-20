"""mods/dynamic-me 시험 (E04): 조절값 정리·적용."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pylib"))
sys.path.insert(0, os.path.join(HERE, "..", "mods", "dynamic-me", "python"))
import m24engine as E  # noqa: E402
import dme_tune as T  # noqa: E402
import dme_detail as D  # noqa: E402

GAME = r"C:\Program Files\Epic Games\FootballManager24"
HAS_GAME = os.path.exists(os.path.join(GAME, "data", "simatch.fmf"))


class Tune(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(T.clean({"speed": 1.0, "accel": "1.1", "nope": 2, "w_ca": 99}), {"accel": 1.1, "w_ca": 2.0})

    def test_knob_keys_exist(self):
        for k in T.KNOBS:
            self.assertIn(k["level"], ("basic", "adv"))
            for f in k.get("weights") or []:
                self.assertIn(f, E.WEIGHT_FACTORS, k["key"])
            for f in k.get("physics") or []:
                self.assertIn(f, E.PHYS_KNOWN, k["key"])
            if isinstance(k.get("momentum"), list):
                for f in k["momentum"]:
                    self.assertIn(f, E.MOM_EVENTS, k["key"])
            for f in k.get("xg") or []:
                self.assertIn(f, E.XG_TYPES, k["key"])
            for i in (k.get("styles") or {}).get("attr", []):
                self.assertIn(i, D.STYLE_ATTR, k["key"])
            for i in (k.get("styles") or {}).get("tend", []):
                self.assertIn(i, D.STYLE_TEND, k["key"])

    def test_delays_in_one_group(self):
        seen = {}
        for k in T.KNOBS:
            for f in k.get("physics") or []:
                if f in E.PHYS_DELAYS:
                    self.assertNotIn(f, seen, "%s: %s와 겹침" % (f, seen.get(f)))
                    seen[f] = k["key"]
        self.assertEqual(sorted(seen), sorted(E.PHYS_DELAYS))


@unittest.skipUnless(HAS_GAME, "게임이 설치돼 있지 않음")
class TuneOnOriginal(unittest.TestCase):
    def test_apply_does_not_touch_base(self):
        orig = E.load_game_original(GAME)
        before = E.jsb_dumps(orig["physics"])
        t = T.apply(orig, {"speed": 1.1, "w_ca": 1.5, "turn": 1.2, "momentum": 2})
        self.assertEqual(E.jsb_dumps(orig["physics"]), before)
        e0, t0 = orig["physics"]["version_array"][0], t["physics"]["version_array"][0]
        self.assertAlmostEqual(t0["top_speed"], e0["top_speed"] * 1.1)
        self.assertIsInstance(t0["theoretical_max_turning_rate"], int)
        st = "TEAM_PICKING_STYLE::TPS_FIRST_TEAM_PICKING"
        self.assertEqual(t["weights"]["WEIGHTS"][0][st]["simatchshared::TSF_CA"],
                         round(orig["weights"]["WEIGHTS"][0][st]["simatchshared::TSF_CA"] * 1.5))
        self.assertIs(T.apply(orig, {}), orig)

    def test_xg_and_style_knobs(self):
        import math
        orig = E.load_game_original(GAME)
        t = T.apply(orig, {"xg_fk": 2.0, "xg_open": 1.5, "xg_pen": 0.5, "st_press": 1.2, "st_attack": 0.5})
        v = "24.1.2.3"

        def diff(st):
            return t["xg"][v][st]["intercept"] - orig["xg"][v][st]["intercept"]
        self.assertEqual(diff("free_kicks"), round(math.log(2.0) * E.XG_SCALE))      # 승산 2배 = 절편 + ln2
        self.assertEqual(diff("regular"), round(math.log(1.5) * E.XG_SCALE))
        self.assertEqual(diff("penalties"), round(math.log(0.5) * E.XG_SCALE))
        cp, co = D._style(t, "control_possession"), D._style(orig, "control_possession")
        self.assertEqual([r for r in cp["attr"] if r[0] == 10], [[10, 18, 20]])       # 압박 15~19 x1.2, 20으로 자름
        self.assertEqual([r for r in cp["attr"] if r[0] == 0], [[0, 6, 8]])           # 공격 11~15 x0.5
        self.assertEqual([r for r in cp["tend"] if r[0] == 90], [[90, 12, 20]])
        self.assertEqual([r for r in cp["attr"] if r[0] == 24], [r for r in co["attr"] if r[0] == 24])   # 템포는 안 건드림
        self.assertEqual(co["attr"][0], [0, 11, 15])                                  # 원본은 그대로
        self.assertEqual(T.apply(orig, {"xg_fk": 1.0}), orig)                          # 1.0은 아무것도 안 함

    def test_rating_names_exist(self):
        orig = E.load_game_original(GAME)
        names = {c["name"] for e in orig["ratings"]["values"] for r in e["role_data"] for c in r["coefficients"]}
        for k in T.KNOBS:
            for n in k.get("ratings") or []:
                self.assertIn(n, names, k["key"])
        t = T.apply(orig, {"r_goal": 2, "d_keeper": 0.5, "r_expect": 0})
        e = max(t["ratings"]["values"], key=lambda e: E.ver_tuple_me(e["version"]))
        self.assertTrue(all(x["positive_multiplier"] == 1000 for x in e["expected_score_data"]))
        pe = t["physics"]["version_array"][0]
        self.assertEqual(pe["min_delay_keeper_save_dive_and_hold_ball"] % 250, 0)


@unittest.skipUnless(HAS_GAME, "게임이 설치돼 있지 않음")
class Detail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig = E.load_game_original(GAME)

    def test_every_section_has_items_with_names(self):
        total = 0
        for sec in D.SECTIONS:
            items = D.items(sec["id"], self.orig, self.orig)
            self.assertTrue(items, sec["id"])
            for it in items:
                if not sec["id"].startswith("st_"):   # 전술 스타일은 그 스타일에 없는 항목(원본 None)도 보여 줘요 (정하면 더함)
                    self.assertIsNotNone(it["orig"], it["id"])
                self.assertNotEqual(it["label"], it["key"], "한국어 이름 없음: " + it["id"])
            total += len(items)
        self.assertEqual(total, 13 + 11 + 6 + 7 + 39 + 39 * 4 + 48 + 52 + 23 + 77 + 10 * 44)

    def test_style_sections(self):
        folders = [s["folder"] for s in self.orig["styles"]["styles"]]
        self.assertEqual(folders, [f for f, _ in D.TACTIC_STYLES])
        items = D.items("st_control_possession", self.orig, self.orig)
        have = [it for it in items if it["orig"] is not None]
        self.assertEqual(len(have), 2 * (7 + 4))   # 원본 점유율 중시: 팀 지시 7, 성향 4
        self.assertEqual(items[0]["id"], "st:control_possession:a:0:min")
        self.assertEqual((items[0]["orig"], items[1]["orig"]), (11, 15))
        # 원본 주석에 있는 번호는 모두 한국어 이름이 있어요
        for k in self.orig["styles"]["names"]:
            kind, i = k.split(":")
            self.assertIn(int(i), D.STYLE_ATTR if kind == "a" else D.STYLE_TEND, k)

    def test_style_overrides(self):
        t = D.apply(self.orig, {"st:control_possession:a:0:max": 18, "st:control_possession:t:38:min": 3,
                                "st:control_possession:t:38:max": 9, "st:park_the_bus:t:75:max": 12})
        cp = D._style(t, "control_possession")
        self.assertEqual(cp["attr"][0], [0, 11, 18])
        self.assertEqual(cp["tend"][-1], [38, 3, 9])               # 없던 항목은 끝에 더함
        self.assertEqual(D._style(t, "park_the_bus")["tend"][-1], [75, 12, 12])   # 한쪽만 정하면 둘 다 그 값
        self.assertEqual(D._style(self.orig, "control_possession")["attr"][0], [0, 11, 15])   # 원본은 그대로

    def test_apply_overrides(self):
        ov = {"phys:top_speed": 90000, "phys:min_delay_for_trip_do": 610, "phys:theoretical_max_turning_rate": 190.7,
              "w:0:CA": 250, "m:CBE_END_SHOT_GONE_IN:FINAL_SIXTH:CENTRAL_THIRD": 77, "rc:Goals": 1.5, "rs:start": 6500,
              "re:0:pos": 1300}
        t = D.apply(self.orig, ov)
        pe = t["physics"]["version_array"][0]
        self.assertEqual(pe["top_speed"], 90000)
        self.assertEqual(pe["min_delay_for_trip_do"], 500)   # 250 단위
        self.assertEqual(pe["theoretical_max_turning_rate"], 191)
        self.assertEqual(t["weights"]["WEIGHTS"][0]["TEAM_PICKING_STYLE::TPS_FIRST_TEAM_PICKING"]["simatchshared::TSF_CA"], 250)
        rows = {r[:3]: r[3] for r in E.momentum_rows(t["momentum"])}
        self.assertEqual(rows[(1, 5, 1)], 77)
        e = max(t["ratings"]["values"], key=lambda e: E.ver_tuple_me(e["version"]))
        eo = max(self.orig["ratings"]["values"], key=lambda e: E.ver_tuple_me(e["version"]))
        self.assertEqual(e["role_data"][0]["coefficients"][1]["value"], round(eo["role_data"][0]["coefficients"][1]["value"] * 1.5))
        self.assertEqual(e["start_value"], 6500)
        self.assertEqual(e["expected_score_data"][0]["positive_multiplier"], 1300)
        self.assertNotEqual(self.orig["physics"]["version_array"][0]["top_speed"], 90000)   # 원본은 그대로


@unittest.skipUnless(HAS_GAME, "게임이 설치돼 있지 않음")
class ModBackend(unittest.TestCase):
    """모드 Python 쪽 새 기능 (E12): zip 팩, 프리셋, 검색, 대표 값."""
    @classmethod
    def setUpClass(cls):
        import json
        import tempfile
        import zipfile
        import importlib.util
        spec = importlib.util.spec_from_file_location("dme_main", os.path.join(HERE, "..", "mods", "dynamic-me", "python", "main.py"))
        M = importlib.util.module_from_spec(spec)   # 다른 모드의 main과 이름이 겹치지 않게 파일에서 직접
        spec.loader.exec_module(M)
        cls.M, cls.json = M, json
        cls.tmp = tempfile.mkdtemp()
        tmp = cls.tmp

        class Ctx:
            data_dir = os.path.join(tmp, "data")

            def game_dir(self):
                return GAME

            def settings(self):
                return {"packs_dir": os.path.join(tmp, "packs")}
        M._ctx = Ctx()
        os.makedirs(os.path.join(tmp, "packs"))
        cls.orig = E.load_game_original(GAME)
        pk = json.loads(json.dumps(cls.orig["physics"]))
        for e in pk["version_array"]:
            e["top_speed"] = 99000
        cls.pk = pk
        cls.zip = os.path.join(tmp, "packs", "테스트.zip")
        with zipfile.ZipFile(cls.zip, "w") as z:
            z.writestr("simatch/physics/physical_constraints.json", json.dumps(pk))
            z.writestr("../evil.json", "{}")
            z.writestr("simatch/events/commentary.wav", "x")

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_zip_pack(self):
        M = self.M
        self.assertEqual(M.ui_packs()["packs"][0]["name"], "테스트 (zip)")
        sd = M._simatch_dir(self.zip)
        self.assertEqual(sorted(os.listdir(os.path.join(sd, "physics"))), ["physical_constraints.json"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "evil.json")))          # ../ 항목은 안 풂
        self.assertFalse(os.path.exists(os.path.join(sd, "events", "commentary.wav")))  # 표 파일만 풂
        pack, _ = M._load_pack(self.zip)
        self.assertEqual([t for t, v in pack.items() if v is not None], ["physics"])
        self.assertEqual(M._simatch_dir(self.zip), sd)                                   # 다시 안 풂
        hl = M._highlights(self.orig, dict(self.orig, physics=self.pk))
        self.assertEqual((hl[0]["orig"], hl[0]["new"]), (8.941, 9.9))

    def test_presets(self):
        M = self.M
        M._save_state({"pack": None, "tune": {}, "detail": {}})
        with self.assertRaises(RuntimeError):
            M.ui_preset_save("빈 설정")                                                  # 조정이 없으면 저장 안 함
        M._save_state({"pack": {"path": "x", "name": "x"}, "tune": {"speed": 1.1}, "detail": {"phys:top_speed": 95000}})
        r = M.ui_preset_save("내 설정 (1)")
        data = self.json.load(open(r["path"], encoding="utf8"))
        self.assertEqual(sorted(data), ["detail", "format", "tune", "version"])           # 팩 경로·원본 값은 없음
        self.assertEqual(M.ui_presets()["presets"], [{"name": "내 설정 (1)", "tune": 1, "detail": 1}])
        self.assertEqual(M._preset_name("../../x"), "x")                                 # 경로 문자는 걸러냄
        bad = os.path.join(self.tmp, "bad.json")
        with open(bad, "w") as f:
            f.write('{"a": 1}')
        with self.assertRaises(RuntimeError):
            M.ui_preset_import(bad)
        M.ui_preset_delete("내 설정 (1)")
        self.assertEqual(M.ui_presets()["presets"], [])

    def test_search(self):
        M = self.M
        M._save_state({"pack": None, "tune": {}, "detail": {}})
        r = M.ui_search("프리킥")
        self.assertTrue(any(x["id"] == "xg:free_kicks:intercept" for x in r))
        self.assertTrue(all("section" in x for x in r))
        self.assertEqual(M.ui_search(""), [])
        self.assertLessEqual(len(M.ui_search("최소")), 80)


if __name__ == "__main__":
    unittest.main()
