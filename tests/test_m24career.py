"""공용 라이브러리 m24career (사람별 경력 사건 기록 person_record_history) 시험. 게임·세이브 없이 가짜 바이트로 돈다."""
import datetime
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pylib"))
import m24career  # noqa: E402

FF = 0xffffffff


def rec(year, day, kind, flags=0, a=0, b=0, c=0, d=0, team=FF, person=FF, comp=0xffff, b37=0, other=FF):
    r = struct.pack("<HHIIIIIB2xIIHBI", day | (13 << 9), year, flags, a, b, c, d, kind, team, person, comp, b37, other)
    assert len(r) == m24career.WIDTH
    return r


def ls_bytes(lists):
    """_ls.dat 만들기: 머리 8바이트, 지운 기록 0개, 목록 수, 목록마다 (개수, 차이 인코딩 위치), 끝에 기록 크기"""
    out = bytearray(bytes.fromhex("03017461642e0400")) + struct.pack("<II", 0, len(lists))
    for offs in lists:
        out += struct.pack("<I", len(offs))
        prev = 0
        for o in offs:
            out += struct.pack("<i", o - prev)
            prev = o - prev
    return bytes(out) + struct.pack("<IH", m24career.WIDTH, 0)


class Career(unittest.TestCase):
    def test_decode_transfer(self):
        # 야말 2031-07-04 맨시티(515) -> 바르셀로나(1320), 3억 (실기 V17)
        r = m24career.decode(rec(2031, 185, 62, a=300000000, b=2, c=1, d=300000000, team=515, other=1320))
        self.assertEqual(r["kind_name"], "transfer")
        self.assertEqual(r["date"], datetime.date(2031, 7, 4))
        self.assertEqual((r["from_team"], r["to_team"], r["fee"]), (515, 1320, 300000000))
        self.assertIsNone(r["person"])

    def test_decode_cup_league_award(self):
        cup = m24career.decode(rec(2021, 192, 0, flags=0x80000004, a=2, team=596, comp=635))   # 사카 유로 2020 준우승
        self.assertEqual((cup["place"], cup["comp"], cup["team"]), (2, 635, 596))
        lg = m24career.decode(rec(2016, 1, 1, flags=0x40, a=FF, team=1008, comp=622))           # 홀란 브륀 강등
        self.assertTrue(lg["relegated"])
        self.assertIsNone(lg["place"])
        lg = m24career.decode(rec(2035, 147, 1, flags=0x80000002, a=FF, b=FF, team=1320, comp=51))
        self.assertEqual(lg["place"], 1)
        aw = m24career.decode(rec(2035, 150, 32, flags=0x80000000, a=2035, b=1, c=1, team=1320, b37=405 & 0xff, other=405 >> 8))
        self.assertEqual((aw["award"], aw["place"], aw["other_team"]), (405, 1, None))
        ln = m24career.decode(rec(2030, 36, 66, team=4110, person=318405, other=6473))           # 임대 (V18: 98%가 지금 임대 팀)
        self.assertEqual((ln["loan_team"], ln["parent_team"]), (4110, 6473))
        db = m24career.decode(rec(2018, 333, 122, team=439, comp=641, other=7096))               # 사카 데뷔
        self.assertEqual((db["date"], db["opponent"]), (datetime.date(2018, 11, 29), 7096))

    def test_lists_and_helpers(self):
        recs = [rec(2035, 182, 62, c=1, team=439, other=1320), rec(2020, 214, 0, flags=0x80000002, a=1, team=439, comp=664),
                rec(2025, 32, 31, a=2, b=2025, team=515, comp=7, b37=12, other=0)]
        dt = bytes.fromhex("0301746d632e0600") + b"".join(recs)
        lists = [[0, 2 * m24career.WIDTH], [], [m24career.WIDTH]]
        self.assertEqual(m24career.lists_of(ls_bytes(lists)), lists)
        pr = m24career.PersonRecords(lists, dt)
        self.assertEqual([r["year"] for r in pr.of(0)], [2025, 2035])   # 날짜 순
        self.assertEqual(pr.transfers(0), [(datetime.date(2035, 7, 1), 439, 1320, 0)])
        self.assertEqual(pr.finals(2), [(2020, 664, 439, 1)])
        self.assertEqual(pr.awards(0), [(2025, "award_month", 12, None)])
        self.assertEqual(pr.of(1), [])
        self.assertEqual(pr.of(99), [])
        self.assertEqual([li for li, _ in pr.iter_kind(62)], [0])


if __name__ == "__main__":
    unittest.main()
