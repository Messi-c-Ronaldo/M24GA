"""게임 안 패널 (M44): 양식 -> 패널 XML 변환(core/modhost.js m24gaPanelXml)과 패널 칸 파일(loader/panels.py).

  python -X utf8 -W error::ResourceWarning -m unittest tests.test_panel
변환 시험은 frida로 빈 Python 프로세스에 modhost.js를 올려 돌린다 (frida가 없으면 건너뛴다).
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor"))
sys.path.insert(0, os.path.join(ROOT, "loader"))
try:
    import frida
except ImportError:      # pragma: no cover
    frida = None
import mods as modlib  # noqa: E402
import panels  # noqa: E402

HARNESS = "\nrpc.exports = { xml: function (form) { return m24gaPanelXml(form); }, slots: function () { return [M24_PANEL_DIR, M24_PANEL_SLOTS]; } };\n"

FORM = {
    "title": "감독 선수 경력 <&>",
    "text": "선수 시절을 골라 주세요",
    "fields": [
        {"id": "club", "type": "text", "label": "뛴 구단", "value": "Barcelona"},
        {"id": "from", "type": "number", "label": "입단 해", "min": 1970, "max": 2035},
        {"id": "intl", "type": "check", "label": "국가대표", "value": True},
        {"id": "pos", "type": "select", "label": "포지션", "options": [{"value": "GK", "label": "골키퍼"}, "DF", {"value": "MF"}]},
        {"type": "label", "label": "설명 \"따옴표\""},
    ],
    "buttons": [{"id": "ok2", "label": "적용"}],
}


@unittest.skipIf(frida is None, "frida 없음")
class PanelXml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        time.sleep(0.5)
        cls.session = frida.get_local_device().attach(cls.proc.pid)
        with open(os.path.join(ROOT, "core", "modhost.js"), encoding="utf-8") as f:
            cls.script = cls.session.create_script(f.read() + HARNESS)
        cls.script.load()
        cls.x = cls.script.exports_sync

    @classmethod
    def tearDownClass(cls):
        try:
            cls.script.unload()
            cls.session.detach()
        finally:
            cls.proc.kill()
            cls.proc.wait()

    def test_form_to_well_formed_xml(self):
        r = self.x.xml(FORM)
        self.assertTrue(r["ok"], r)
        root = ET.fromstring(r["xml"])            # 잘 짜인 XML이어야 한다 (잘못된 XML은 게임을 튕기게 할 수 있다)
        self.assertEqual(root.tag, "panel")
        self.assertEqual(root.find("string").get("value"), "감독 선수 경력 <&>")
        ids = [w.get("id") for w in root.iter("widget") if w.get("id")]
        self.assertEqual(len(ids), len(set(ids)))  # 위젯 id가 겹치지 않는다
        self.assertTrue(all(len(i) == 4 for i in ids if i != "ok"))   # 닫기 버튼은 게임 기본 XML처럼 'ok'
        self.assertEqual(set(r["widgets"]), {"club", "from", "intl", "pos", "ok2"})
        kinds = {v["id"]: v["kind"] for v in r["events"].values()}
        self.assertEqual(kinds, {"club": "change", "from": "change", "intl": "check", "pos": "select", "ok2": "button"})
        pos = [v for v in r["events"].values() if v["id"] == "pos"][0]
        self.assertEqual(pos["options"], ["GK", "DF", "MF"])
        num = [v for v in r["events"].values() if v["id"] == "from"][0]
        self.assertEqual(num["number"], {"min": 1970, "max": 2035})
        self.assertIsNotNone(root.find(".//widget[@id='ok']"))   # 닫기 버튼은 늘 있다 (빈 대화상자를 못 닫는 일 방지, M43)
        chk = root.find(".//widget[@id='%s']" % r["widgets"]["intl"])
        self.assertEqual(chk.get("selected"), "true")

    def test_person_club_search_boxes(self):
        # 코어 0.29.0 (C09): person/club 칸 = 게임 검색칸. ssro(고르면 화면 옮김)는 없어야 하고, 표 종류 1 = 사람, 3 = 구단
        r = self.x.xml({"fields": [
            {"id": "who", "type": "person", "label": "옛 동료", "value": {"ref": "p1", "name": "손흥민", "label": "손흥민 · 31세 · 토트넘 홋스퍼"}},
            {"id": "fav", "type": "club", "label": "좋아하는 구단"},
        ]})
        self.assertTrue(r["ok"], r)
        root = ET.fromstring(r["xml"])
        boxes = {w.get("id"): w for w in root.iter("widget") if w.get("class") == "db_record_search_box"}
        who, fav = boxes[r["widgets"]["who"]], boxes[r["widgets"]["fav"]]
        self.assertEqual((who.get("database_table_type"), fav.get("database_table_type")), ("1", "3"))
        for b in (who, fav):
            self.assertIsNone(b.get("ssro"))
            self.assertEqual(b.get("lpfi"), "widgets/predictive search list scout assignment")
        kinds = {v["id"]: (v["kind"], v.get("table")) for v in r["events"].values()}
        self.assertEqual(kinds, {"who": ("pick", "person"), "fav": ("pick", "club")})
        texts = [w.get("text") for w in root.iter("widget") if w.get("class") == "text"]
        self.assertIn("옛 동료  (지금: 손흥민 · 31세 · 토트넘 홋스퍼)", texts)   # 이름 줄에 붙인다 (창 높이)
        self.assertIn("좋아하는 구단", texts)

    def test_select_value_shows_choice(self):
        f = {"id": "lv", "type": "select", "label": "단계", "options": [{"value": 1, "label": "하나"}, {"value": 2, "label": "둘"}]}
        r = self.x.xml({"fields": [dict(f, value=2)]})
        root = ET.fromstring(r["xml"])
        self.assertEqual(root.find(".//widget[@class='popup_button']").get("text"), "둘")
        self.assertIn("단계", [w.get("text") for w in root.iter("widget") if w.get("class") == "text"])
        r2 = ET.fromstring(self.x.xml({"fields": [dict(f, value=9)]})["xml"])   # 없는 값이면 예전처럼 이름
        self.assertEqual(r2.find(".//widget[@class='popup_button']").get("text"), "단계")

    def test_event_codes_match_widget_numbers(self):
        r = self.x.xml(FORM)
        for ev, info in r["events"].items():
            self.assertEqual(ev[2:], r["widgets"][info["id"]][2:])

    def test_empty_form_still_has_close(self):
        r = self.x.xml({})
        self.assertTrue(r["ok"], r)
        self.assertIsNotNone(ET.fromstring(r["xml"]).find(".//widget[@id='ok']"))

    def test_errors(self):
        bad = [
            None,
            {"fields": [{"id": "a"}, {"id": "a"}]},                      # 겹치는 id
            {"fields": [{"id": "close"}]},                                # 코어가 쓰는 id
            {"fields": [{"id": "a", "type": "pick.club"}]},               # 아직 없는 종류
            {"fields": [{"id": "a b"}]},                                  # 이상한 id
            {"fields": [{"id": "s", "type": "select", "options": []}]},  # 빈 select
            {"fields": [{"id": "f%d" % i} for i in range(41)]},         # 너무 많음
            {"buttons": [{"id": "b%d" % i} for i in range(7)]},
        ]
        for form in bad:
            r = self.x.xml(form)
            self.assertFalse(r["ok"], form)
            self.assertTrue(r["error"])

    def test_control_chars_and_long_text_cut(self):
        r = self.x.xml({"title": "a\x01b" + "x" * 200, "text": "y" * 1000})
        self.assertTrue(r["ok"], r)
        root = ET.fromstring(r["xml"])
        self.assertEqual(len(root.find("string").get("value")), 80)

    def test_slot_vars_default(self):
        self.assertEqual(self.x.slots(), [None, 8])


class PanelSlots(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = modlib.documents_dir
        modlib.documents_dir = lambda: self.tmp.name

    def tearDown(self):
        modlib.documents_dir = self.old
        self.tmp.cleanup()

    def test_no_fm_folder_creates_nothing(self):
        r = panels.ensure_slots()
        self.assertFalse(r["ok"])
        self.assertTrue(r["error"])
        self.assertFalse(os.path.exists(panels.slot_dir()))
        self.assertIsNone(panels.slot_dir_if_ready())

    def test_ensure_then_ready_then_remove(self):
        os.makedirs(panels.fm_user_dir())
        other = os.path.join(panels.fm_user_dir(), "panels", "mine.xml")   # 사용자의 다른 패널은 건드리지 않는다
        os.makedirs(os.path.dirname(other))
        with open(other, "w") as f:
            f.write("<panel/>")
        r = panels.ensure_slots()
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["created"]), panels.SLOTS)
        self.assertEqual(panels.slot_dir_if_ready(), panels.slot_dir())
        ET.parse(panels.slot_file(1))                        # 처음 내용도 잘 짜인 XML
        self.assertEqual(panels.ensure_slots()["created"], [])   # 두 번째는 만들 것이 없다
        self.assertEqual(panels.game_path(3), "m24ga/slot03")
        self.assertEqual(panels.remove_slots(), panels.SLOTS)
        self.assertFalse(os.path.exists(panels.slot_dir()))
        self.assertTrue(os.path.exists(other))


if __name__ == "__main__":
    unittest.main()
