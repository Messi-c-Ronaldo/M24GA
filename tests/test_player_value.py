"""몸값 모드(mods/player-value) 기능 B 활약 배율 계산 시험 (pvperf). 게임 없이 가짜 기록으로 돈다."""
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "mods", "player-value", "python"))
import pvperf  # noqa: E402


def rows(seed=3, leagues=2, n=120):
    rnd = random.Random(seed)
    out, uid = [], 100
    for lg in range(1, leagues + 1):
        for _ in range(n):
            uid += 1
            rated = rnd.randint(0, 30)
            avg = rnd.uniform(6.2, 7.8)
            out.append([uid, lg, rnd.randint(0, 7), rated * 85, rated, int(round(avg * 10 * rated)), "2000-01-%02d" % (uid % 28 + 1), 0, ""])
    return out


class Perf(unittest.TestCase):
    def test_range_and_order(self):
        rs = rows()
        fs, s = pvperf.factors(rs, {}, 2036, 0.25)
        self.assertTrue(fs)
        self.assertTrue(all(0.75 <= f <= 1.25 for f in fs.values()))
        cur = pvperf.current_percentiles(rs)
        # 같은 출전에서 백분위가 높으면 배율도 높다
        full = [r for r in rs if r[3] >= pvperf.FULL_MINUTES and r[0] in fs]
        full.sort(key=lambda r: cur[r[0]][0])
        self.assertLessEqual(fs[full[0][0]], fs[full[-1][0]])
        self.assertEqual(s["strength"], 0.25)

    def test_little_data_is_neutral(self):
        # 출전이 조건보다 적고 지난 시즌이 없으면 배율이 없다 (1)
        rs = rows()
        fs, _ = pvperf.factors(rs, {}, 2036, 0.25)
        for r in rs:
            if r[3] < pvperf.MIN_MINUTES:
                self.assertNotIn(r[0], fs)

    def test_prior_seasons(self):
        # 이번 시즌 기록이 없어도 지난 두 시즌이 최고면 오르고, 생년월일이 다르면(다른 선수) 안 쓴다
        r = [9001, 1, 7, 0, 0, 0, "1999-05-05", 1, "가"]
        prior = {"9001": [{"year": 2035, "dob": "1999-05-05", "percentile": 99.0, "poor": False},
                          {"year": 2034, "dob": "1999-05-05", "percentile": 95.0, "poor": False}]}
        fs, s = pvperf.factors([r], prior, 2036, 0.3)
        self.assertGreater(fs[9001], 1.25)
        self.assertLessEqual(fs[9001], 1.3)
        self.assertEqual(s["with_last"], 1)
        prior["9001"][0]["dob"] = prior["9001"][1]["dob"] = "2001-01-01"
        fs, _ = pvperf.factors([r], prior, 2036, 0.3)
        self.assertNotIn(9001, fs)

    def test_league_strength(self):
        # V08: 같은 백분위라도 약한 리그(평균 CA 80)의 최고 선수는 강한 리그(평균 CA 150)의 최고 선수보다 덜 오른다. 끄면 같다
        rs = []
        for lg, ca in ((1, 80), (2, 150)):
            for k in range(40):
                rs.append([lg * 1000 + k, lg, 7, 2000, 25, 25 * (60 + k), "1990-01-01", 0, "", ca])
        weak, strong = 1039, 2039                 # 각 리그 평점 1등
        fs, s = pvperf.factors(rs, {}, 2036, 0.25)
        self.assertEqual(s["leagues"], 2)
        self.assertLess(fs[weak], fs[strong])
        self.assertLess(fs[weak], 1.25)
        fs2, _ = pvperf.factors(rs, {}, 2036, 0.25, league=False)
        self.assertEqual(fs2[weak], fs2[strong])
        # 꼴찌는 강한 리그 쪽이 덜 내려간다
        self.assertGreater(fs[2000], fs[1000])

    def test_intl(self):
        # 국가대표 경기가 좋으면 같은 리그 기록의 선수보다 백분위가 오른다. 비율 0이면 그대로
        rs = [[1000 + k, 1, 7, 2000, 25, 25 * (60 + k), "1990-01-01", 0, "", 120, None] for k in range(40)]
        rs[10][10] = [600, 6, 6 * 95]           # 중간 선수가 국가대표에서 평점 9.5
        base, _ = pvperf.factors(rs, {}, 2036, 0.25, league=False, intl=0.0)
        withi, s = pvperf.factors(rs, {}, 2036, 0.25, league=False, intl=1.0)
        self.assertGreater(withi[1010], base[1010])
        self.assertEqual(s["intl_players"], 1)
        zero, _ = pvperf.factors(rs, {}, 2036, 0.25, league=False, intl=0.0)
        self.assertEqual(zero, base)

    def test_caps_bonus(self):
        # A매치 통산 보너스: 50경기 이상이면 최대값, 활약 기록이 없어도 붙고, 0이면 없다
        rs = [[1, 1, 7, 0, 0, 0, "x", 0, "", 120, None, 80], [2, 1, 7, 0, 0, 0, "y", 0, "", 120, None, 25], [3, 1, 7, 0, 0, 0, "z", 0, "", 120, None, 0]]
        fs, s = pvperf.factors(rs, {}, 2036, 0.25, caps=0.05)
        self.assertEqual(fs[1], 1.05)
        self.assertEqual(fs[2], 1.025)
        self.assertNotIn(3, fs)
        self.assertEqual(s["caps_players"], 2)
        fs0, _ = pvperf.factors(rs, {}, 2036, 0.25, caps=0.0)
        self.assertEqual(fs0, {})

    def test_honours(self):
        # 수상(상 규모 x 순위 x 최근)과 우승이 있으면 영예 보너스, 없으면 없음, hcap 0이면 없음 (V12)
        recs = [(2035, 7, [(1, 900, 1), (2, 901, 1)]), (2034, 7, [(1, 900, 1)]), (2033, 7, [(1, 902, 1)])]
        prest = pvperf.award_prestige(recs, {900: 190, 901: 150, 902: 170})
        self.assertAlmostEqual(prest[7], min(1.0, ((190 + 190 + 170) / 3.0 - 110) / 60), places=3)
        by_link = {900: [(2035, 7, 1), (2034, 7, 1)], 901: [(2035, 7, 2)]}
        rs = [[1, 1, 7, 0, 0, 0, "x", 0, "", 150, None, 0, 900], [2, 1, 7, 0, 0, 0, "y", 0, "", 150, None, 0, 901],
              [3, 1, 7, 0, 0, 0, "z", 0, "", 150, None, 0, 903]]
        fs, s = pvperf.factors(rs, {}, 2036, 0.25, honours=(by_link, {3: [(2034, 51), (2034, 639)]}, prest), hcap=0.05)
        self.assertGreater(fs[1], fs[2])            # 1위 두 번 > 2위 한 번
        self.assertGreater(fs[3], 1.0)              # 우승 두 개
        self.assertEqual(s["honours_players"], 3)
        fs0, _ = pvperf.factors(rs, {}, 2036, 0.25, honours=(by_link, {}, prest), hcap=0.0)
        self.assertEqual(fs0, {})

    def test_trophy_prestige(self):
        # V14: 대회 크기 = 우승 멤버 평균 CA. 큰 대회 우승이 작은 대회 우승보다 점수가 크다
        wins = {u: [(2034, 639)] for u in range(1, 7)}
        wins.update({u: [(2034, 900)] for u in range(10, 16)})
        ca = {u: 180 for u in range(1, 7)}
        ca.update({u: 120 for u in range(10, 16)})
        tp = pvperf.trophy_prestige(wins, ca)
        self.assertGreater(tp[639], tp[900])
        big = pvperf.honours_score(None, 1, {}, wins, {}, 2036, tp)
        small = pvperf.honours_score(None, 10, {}, wins, {}, 2036, tp)
        self.assertGreater(big, small)

    def test_league_history_on_save(self):
        # V15: 실제 세이브가 있으면 바르셀로나(팀 1320)의 리그 성적이 이어지고 승점 = 3x승 + 무
        sys.path.insert(0, os.path.join(ROOT, "pylib"))
        import m24awards
        import m24hist
        path = m24hist.find_save(5117219)
        if not path:
            self.skipTest("테스트 세이브 없음")
        d = m24awards.parse_league_history(path)
        rows = d["by_team"].get(1320)
        if not rows:
            self.skipTest("다른 세이브")
        for r in rows[-5:]:
            self.assertEqual(r["pts"], 3 * r["won"] + r["drawn"])
            self.assertEqual(r["played"], r["won"] + r["drawn"] + r["lost"])

    def test_best_eleven_by_person(self):
        sys.path.insert(0, os.path.join(ROOT, "pylib"))
        import m24awards
        recs = [(2034, [(0, 5, 30, 0), (9, 45806, 33, 25), (12, 7, 3, 0)])]
        self.assertEqual(m24awards.best_eleven_by_person(recs)[45806], [(2034, 9)])
        self.assertNotIn(7, m24awards.best_eleven_by_person(recs))
        self.assertIn(7, m24awards.best_eleven_by_person(recs, starters_only=False))

    def test_m24awards_parse(self):
        # 공용 라이브러리 m24awards: 82바이트 기록 (연도, 상, 1~3위) 읽기 (가짜 바이트)
        import struct
        sys.path.insert(0, os.path.join(ROOT, "pylib"))
        import m24awards
        rec = struct.pack("<HH", 2035, 405) + struct.pack("<II", 45806, 679) + b"\0" * 18 + struct.pack("<II", 0xffffffff, 0xffffffff) + b"\0" * 18 + struct.pack("<II", 7, 1) + b"\0" * 18
        self.assertEqual(len(rec), 82)
        per = m24awards.by_person([(2035, 405, [(1, 45806, 679), (3, 7, 1)])])
        self.assertEqual(per[45806], [(2035, 405, 1)])
        self.assertEqual(per[7], [(2035, 405, 3)])
        rec = bytearray(b"\xff" * 55); rec[0:4] = struct.pack("<I", 51); rec[4:6] = struct.pack("<H", 2034)
        rec[8:12] = struct.pack("<I", 1320); rec[47:51] = struct.pack("<HH", 2033, 2034)   # V15: 시즌 시작 해는 끝부분
        cdt = bytes.fromhex("0301746d632e0300") + bytes(rec)
        self.assertEqual(m24awards.comp_winners(cdt), {(1320, 2033): [51]})

    def test_strength_clamped(self):
        prior = {"5": [{"year": 2035, "dob": "x", "percentile": 0.0}, {"year": 2034, "dob": "x", "percentile": 0.0}]}
        fs, s = pvperf.factors([[5, 1, 0, 0, 0, 0, "x", 0, ""]], prior, 2036, 5)
        self.assertEqual(s["strength"], 0.6)
        self.assertAlmostEqual(fs[5], 0.4, places=3)


if __name__ == "__main__":
    unittest.main()
