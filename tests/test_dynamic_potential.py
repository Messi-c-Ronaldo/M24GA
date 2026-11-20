"""포텐 모드(mods/dynamic-potential) PC 쪽 계산 시험. 게임 없이 가짜 선수 자료로 돈다.

원래 Dynamic PA 0.9.5가 이 PC(내려받기 폴더)에 있으면, 같은 입력으로 원본 모델과 결과가 같은지도 본다.
"""
import copy
import importlib
import os
import random
import sys
import unittest
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, "mods", "dynamic-potential", "python")
sys.path.insert(0, os.path.join(ROOT, "pylib"))   # 코어 0.18.0: dpa, m24hist는 공용 라이브러리
sys.path.insert(0, PY)
import potential  # noqa: E402

ORIGINAL = os.path.join(os.path.expanduser("~"), "Downloads", "FM24_Dynamic_PA_v0.9.5", "app")
DUE = date(2035, 7, 1)


def fake_rows(seed=7, leagues=3, per_league=150):
    rnd = random.Random(seed)
    rows, uid = [], 1000
    for lg in range(1, leagues + 1):
        for team in range(per_league // 15):
            for _ in range(15):
                uid += 1
                age = rnd.randint(17, 34)
                pos = [rnd.randint(1, 12) for _ in range(15)]
                pos[rnd.randrange(15)] = 20
                ca = rnd.randint(60, 170)
                apps = rnd.randint(8, 38)
                rated = apps
                minutes = min(apps * 90, rnd.randint(apps * 40, apps * 90))
                rating = rnd.uniform(6.3, 7.8)
                goals, assists = rnd.randint(0, 20), rnd.randint(0, 12)
                shots = rnd.randint(goals, goals + 60)
                det = [rnd.randint(200, 1500), 0, rnd.randint(10, 80), 0, rnd.randint(10, 90), 0, rnd.randint(0, 60),
                       shots, rnd.randint(goals, shots), rnd.randint(0, 50), rnd.randint(0, 70), rnd.randint(0, shots * 30),
                       rnd.randint(0, 600), rnd.randint(0, 80), rnd.randint(0, 200), rnd.randint(50, 600), 0, 0,
                       rnd.randint(0, 80), 0]
                det[1], det[3], det[5], det[16] = det[0] * 8 // 10, det[2] // 2, det[4] // 2, det[15] // 3
                det[17], det[19] = det[11] * 9 // 10, det[18] // 3
                rows.append({"u": uid, "n": "선수%d" % uid, "b": "%d-03-15" % (DUE.year - age), "ca": ca,
                             "pa": min(200, ca + rnd.randint(0, 50)), "pos": pos,
                             "tr": [rnd.randint(1, 20), rnd.randint(1, 20), rnd.randint(1, 20), rnd.randint(1, 20), rnd.randint(1, 20)],
                             "lg": lg, "tm": "t%d-%d" % (lg, team), "tn": "팀%d" % team,
                             "s": [minutes, rated, round(rating * 10 * rated), apps - 3 if apps > 3 else apps, min(3, apps), goals, assists, min(goals, 2)],
                             "d": det})
    return rows


class DynamicPotential(unittest.TestCase):
    def test_same_input_same_result(self):
        a, sa = potential.evaluate(fake_rows(), DUE, {}, "save1")
        b, sb = potential.evaluate(fake_rows(), DUE, {}, "save1")
        self.assertEqual([(r["uid"], r["new"]) for r in a], [(r["uid"], r["new"]) for r in b])
        self.assertGreater(len(a), 100)
        self.assertGreater(sa["up"] + sa["down"], 0)

    def test_bounds_and_budget(self):
        res, sm = potential.evaluate(fake_rows(3), DUE, {}, "save2")
        for r in res:
            self.assertGreaterEqual(r["new"], r["ca"])
            self.assertLessEqual(r["new"], 200)
            self.assertTrue(r["why"])
        up = sum(max(0, r["delta"]) for r in res)
        down = sum(max(0, -r["delta"]) for r in res)
        self.assertLessEqual(up, down + int(0.25 * len(res)))

    def test_history_is_used(self):
        rows = fake_rows(5)
        res, _ = potential.evaluate(rows, DUE, {}, "s")
        hist = {uid: {str(DUE.year - 1): h} for uid, h in potential.history_entries(res).items()}
        res2, _ = potential.evaluate(rows, DUE, hist, "s")
        self.assertTrue(any("지난 시즌 1개 반영" in r["why"] for r in res2))

    def test_detail_checks(self):
        raw = [100, 120] + [0] * 18          # 패스 성공이 시도보다 많음 -> 둘 다 버림
        raw[11], raw[7] = 500, 3             # xG 5.00인데 슈팅 3개 -> xG 무리 버림
        out = potential.decode_detail(raw, 900, 1, "ST")
        self.assertNotIn("passes_attempted", out)
        self.assertNotIn("xg", out)
        self.assertIn("shots", out)
        self.assertEqual(potential.decode_detail(raw, 900, 1, "GK"), {})

    def test_due_for(self):
        self.assertEqual(potential.due_for(date(2035, 4, 27)), date(2034, 7, 1))
        self.assertEqual(potential.due_for(date(2035, 7, 1)), date(2035, 7, 1))
        self.assertEqual(potential.due_for(date(2035, 2, 1), 1, 15), date(2035, 1, 15))

    def test_injury_days_window(self):
        inj = [{"start": "2034-06-20", "total": 20}, {"start": "2034-06-20", "total": 20},   # 같은 부상은 한 번
               {"start": "2035-03-01", "total": 200}]                                       # 평가일(7/1) 넘는 부분은 뺀다
        self.assertEqual(potential.injury_days(inj, DUE), 9 + 122)   # 7/1~7/9, 3/1~6/30
        self.assertEqual(potential.injury_days(None, DUE), 0)

    def test_injury_effect(self):
        rows = fake_rows(13)
        long_inj = {str(r["u"]): [{"start": "2034-08-01", "total": 300}] for r in rows}
        a, sa = potential.evaluate(rows, DUE, {}, "save3", injuries={})
        b, sb = potential.evaluate(rows, DUE, {}, "save3", injuries=long_inj)
        c, _ = potential.evaluate(rows, DUE, {}, "save3", injuries=long_inj)
        self.assertEqual([(r["uid"], r["new"]) for r in b], [(r["uid"], r["new"]) for r in c])   # 같은 입력 같은 결과
        self.assertGreater(sb["injury"], 0)
        before = {r["uid"]: r for r in a}
        for r in b:
            self.assertGreaterEqual(r["new"], r["ca"])
            if r["event"] == "injury":
                if r["uid"] in before:
                    self.assertLessEqual(before[r["uid"]]["delta"], 0)        # 오른 선수는 안 건드림
                self.assertGreaterEqual(r["delta"], -3)
            elif r["uid"] in before:
                self.assertEqual(r["new"], before[r["uid"]]["new"])

    def test_savehist_merge(self):
        import m24hist as savehist
        mine = {"7": {"2034": {"dob": "2010-01-01", "percentile": 90, "poor": False, "ca": 100}}}
        prior = {"7": [{"year": 2034, "dob": "2010-01-01", "percentile": 10, "poor": True},
                       {"year": 2033, "dob": "2010-01-01", "percentile": 40, "poor": False}],
                 "8": [{"year": 2031, "dob": "2010-01-01", "percentile": 40, "poor": False}]}
        m = savehist.merge(mine, prior, DUE)
        self.assertEqual(m["7"]["2034"]["percentile"], 90)       # 모드 기록이 우선
        self.assertEqual(m["7"]["2033"]["percentile"], 40)       # 없는 해만 세이브 값
        self.assertEqual(m.get("8", {}), {})                     # 3년 넘은 해는 안 씀

    def test_half_check_scale(self):
        rows = fake_rows(17)
        full, _ = potential.evaluate(rows, DUE, {}, "s5")
        half, sm = potential.evaluate(rows, DUE, {}, "s5", scale=0.5)
        f = {r["uid"]: r for r in full}
        for r in half:
            self.assertEqual(r["delta"], max(r["ca"] - r["old"], int(f[r["uid"]]["delta"] * 0.5)))
        self.assertEqual(sm["scale"], 0.5)

    def test_cup_weight(self):
        rows = fake_rows(19)
        for r in rows:
            r["c"] = [900, 10, 720, 10, 0, 5, 2, 0]
        base, _ = potential.evaluate(rows, DUE, {}, "s6")
        zero, _ = potential.evaluate(rows, DUE, {}, "s6", cup_weight=0.0)
        self.assertEqual([(r["uid"], r["new"]) for r in base], [(r["uid"], r["new"]) for r in zero])   # 0이면 원래 모델 그대로
        more, _ = potential.evaluate(rows, DUE, {}, "s6", cup_weight=1.0)
        m = {r["uid"]: r for r in more}
        some = next(r for r in base if r["uid"] in m)
        self.assertGreater(m[some["uid"]]["minutes"], some["minutes"])

    def test_calendar_league_uses_saved_season(self):
        rows = fake_rows(23)
        players, totals, _ = potential.build(rows, DUE, {})
        saved = {}
        for p in players[:150]:                       # 한 리그 전체가 직전 시즌 보관 기록을 가진 것처럼
            t = dict(totals[p.uid])
            t.update(minutes=3000, rated=34, rating_sum=34 * 72, league=999, position=p.position, season_year=DUE.year - 1,
                     source_kind="saved_league_season", dob=p.dob)
            saved[str(p.uid)] = t
        res, sm = potential.evaluate(rows, DUE, {}, "s7", saved=saved)
        cal = [r for r in res if r.get("calendar")]
        self.assertGreater(len(cal), 50)
        self.assertTrue(all(r["minutes"] == 3000 for r in cal))
        self.assertTrue(all("직전 완료 시즌" in r["why"] for r in cal))
        self.assertEqual(sm["calendar"], len(cal))

    @unittest.skipUnless(os.path.isdir(ORIGINAL), "원래 Dynamic PA가 이 PC에 없음")
    def test_matches_original_dynamic_pa(self):
        rows = fake_rows(11)
        mine, _ = potential.evaluate(rows, DUE, {}, "save9")
        players, totals, hist = potential.build(rows, DUE, {})
        rules = dict(potential.dpa_rules.DEFAULTS)
        saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k in ("model", "rules", "model_v07", "league_strength",
                                                                           "scouting_metrics", "development_balance", "transfer_evaluation")}
        sys.path.insert(0, ORIGINAL)
        try:
            orig = importlib.import_module("model_v07")
            out = orig.proposals(players, copy.deepcopy(totals), DUE, hist, seed_context="save9", rules=rules)
        finally:
            sys.path.remove(ORIGINAL)
            for k in ("model", "rules", "model_v07", "league_strength", "scouting_metrics", "development_balance", "transfer_evaluation"):
                sys.modules.pop(k, None)
            sys.modules.update(saved)
        self.assertEqual([(r["uid"], r["new"]) for r in mine], [(x["uid"], x["new"]) for x in out])


if __name__ == "__main__":
    unittest.main()
