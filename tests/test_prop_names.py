"""속성 이름표 도구(tools/prop_names.py)의 해석 로직 시험 (M67) — 게임 파일 없이 만든 작은 번역 파일로."""
import os
import struct
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import prop_names  # noqa: E402


def make_ltc(groups, keys, hi_flag=()):
    """groups = [[변형 글...]], keys = {번역 번호: 그룹 번호}. 머리 33바이트 + 문장 구역 + (개수, (번호, 위치)...) 표"""
    body = bytearray()
    starts = []
    for g in groups:
        starts.append(33 + len(body))
        body.append(len(g))
        for t in g:
            b = t.encode("utf-8")
            body += struct.pack("<I", len(b)) + b
    head = bytearray(33)
    head[0:2] = b"\x03\x01"
    head[2:6] = b"ctl."
    struct.pack_into("<I", head, 8, len(body) + 33 - 8)   # 문장 구역 끝 = 값 + 8
    table = struct.pack("<I", len(keys))
    for tid, g in keys.items():
        off = starts[g] - 8
        if tid in hi_flag:
            off |= 0x80000000
        table += struct.pack("<II", 0x10000000 | tid, off)
    return bytes(head) + bytes(body) + table


class PropNames(unittest.TestCase):
    def test_parse_ltc(self):
        buf = make_ltc([["크로스", "크로스(복수)"], ["나이"], ["사기"]], {227798: 0, 227770: 1, 227839: 2}, hi_flag=(227770,))
        got = prop_names.parse_ltc_buf(buf)
        self.assertEqual(got, {227798: "크로스", 227770: "나이", 227839: "사기"})   # 변형은 첫 문장, 위치 최상위 비트는 뗌

    def test_header(self):
        buf = bytearray(40)
        buf[2:6] = b"ctl."
        struct.pack_into("<I", buf, 16, 9)
        buf[20:29] = "한국어".encode("utf-8")
        self.assertEqual(prop_names.ltc_header(bytes(buf)), "한국어")
        self.assertIsNone(prop_names.ltc_header(b"\x00" * 40))


if __name__ == "__main__":
    unittest.main()
