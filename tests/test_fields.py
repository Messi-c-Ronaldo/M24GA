"""필드 등록부 시험 (M20): core/fields.json 형식, 기능 탐지, validate 규칙, FIELDS.md 최신. 게임 없이."""
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
import validate as v  # noqa: E402

TYPES = {"i8", "u8", "i16", "u16", "i32", "u32", "f32", "f64", "ptr", "date", "str", "strref"}
WRITABLE = {"i8", "u8", "i16", "u16", "i32", "u32", "f32", "f64"}
HEX = re.compile(r"^0x[0-9a-f]+$")


class Registry(unittest.TestCase):
    def setUp(self):
        self.fr = caps.fields()

    def test_kinds(self):
        for k, kd in self.fr["kinds"].items():
            self.assertTrue(kd.get("cls"), k)
            for ref in [kd.get("key"), kd.get("name")] + list(kd.get("check") or []):
                if ref:
                    self.assertIn(ref, self.fr["fields"], "%s: %s" % (k, ref))
                    self.assertEqual(self.fr["fields"][ref]["kind"], k, ref)

    def test_fields(self):
        capnames = set(caps.names())
        for n, f in self.fr["fields"].items():
            with self.subTest(field=n):
                self.assertRegex(n, r"^[a-z]+(\.[A-Za-z0-9]+)+$")
                self.assertIn(f["kind"], self.fr["kinds"])
                self.assertTrue(n.startswith(f["kind"] + "."), "필드 이름은 종류로 시작")
                self.assertIn(f["type"], TYPES)
                self.assertRegex(f["off"], HEX)
                for x in f.get("via") or []:
                    self.assertRegex(x, HEX)
                for c, o in (f.get("alt") or {}).items():
                    self.assertIn("::", c)
                    self.assertTrue(o is None or HEX.match(o))
                if f.get("to"):
                    self.assertIn(f["to"], self.fr["kinds"])
                    self.assertEqual(f["type"], "ptr")
                self.assertIn(f.get("write", "no"), ("no", "safe"))
                self.assertTrue(f.get("desc"))
                self.assertIn("verified", f)
                if f.get("write") == "safe":
                    self.assertIn(f["type"], WRITABLE)
                    if f.get("map"):   # 바꿔 읽는 칸(능력치 t20, M72)은 저장 값으로 쓴다: 저장 값 범위와 단위 설명이 있어야 한다 (되돌리기가 정확하게)
                        self.assertTrue(f.get("range"), "바꿔 읽는 칸의 쓰기는 저장 값 range가 필요하다")
                        self.assertIn("저장", f.get("unit", ""), "바꿔 읽는 칸은 unit에 저장 값 단위를 적는다")
                    self.assertIn(f.get("cap") or "write.field", capnames)
                    self.assertTrue(f.get("verified"), "쓰기는 확인된 칸만")
                    k = self.fr["kinds"][f["kind"]]
                    self.assertTrue(k.get("key") or k.get("find") == "human", "쓰기 칸의 종류는 key(또는 감독 순번 find: human)가 있어야 되돌릴 수 있다")
                for g in ("gte", "lte"):
                    if f.get(g):
                        self.assertIn(f[g], self.fr["fields"])

    def test_pa_matches_m14_rules(self):
        pa = self.fr["fields"]["player.pa"]
        self.assertEqual((pa["off"], pa["type"], pa["write"], pa["range"], pa["gte"], pa.get("cap")),
                         ("0x202", "i16", "safe", [1, 200], "player.ca", "write.player.pa"))
        self.assertEqual(self.fr["kinds"]["player"]["check"], ["player.uid", "player.dob"])

    def test_docs_up_to_date(self):
        path = os.path.join(ROOT, "docs", "FIELDS.md")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), caps.fields_markdown(), "python -X utf8 tools/m24.py caps 로 다시 만드세요")
        self.assertIn(path, m24.caps_outputs())


class Detect(unittest.TestCase):
    def test_field_uses(self):
        js = "var a = getField(personOf(p), 'player.ca');\nvar b = api.setField(p, \"player.pa\", 3);\nfieldInfo('club.name'); // getField(x, 'no.no')"
        self.assertEqual(caps.field_uses(js), [(1, "get", "player.ca"), (2, "set", "player.pa"), (3, "info", "club.name")])

    def test_set_field_needs_field_cap(self):
        found = caps.detect("api.setField(p, 'player.pa', 150);")
        self.assertIn("write.player.pa", found)
        self.assertNotIn("write.field", found)
        self.assertIn("read.field", caps.detect("var x = getField(p, 'player.ca');"))
        self.assertEqual(caps.field_cap("player.askingPrice"), None)


class Validate(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "mod.json"), "w", encoding="utf-8") as f:
            json.dump({"id": "ft", "name": "ft", "version": "1.0.0", "core": ">=0.10.0", "js": "mod.js",
                       "capabilities": ["read.field", "write.player.pa"]}, f)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def check(self, js):
        with open(os.path.join(self.d, "mod.js"), "w", encoding="utf-8") as f:
            f.write(js)
        return [(i["where"], i["message"], i["fix"]) for i in v.validate(self.d).issues if i["level"] == "error"]

    def test_known_fields_ok(self):
        self.assertEqual(self.check("var p = findObj('player', 1); api.log(getField(p, 'player.ca')); api.setField(p, 'player.pa', 150, {expect: 149});\n"), [])

    def test_unknown_field_suggests(self):
        errs = self.check("api.log(getField(p, 'player.askingprice'));\n")
        self.assertTrue(any("모르는 필드" in m and "player.askingPrice" in fx for w, m, fx in errs), errs)

    def test_readonly_field(self):
        errs = self.check("api.setField(p, 'player.ca', 150);\n")
        self.assertTrue(any("읽기만" in m for w, m, fx in errs), errs)


if __name__ == "__main__":
    unittest.main()
