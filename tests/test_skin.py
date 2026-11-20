"""스킨·언어 의존 막기 (M39): 모드 API와 모드 코드는 스킨이 정한 위젯 id에 기대지 않는다."""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 실행 중인 fm.exe에 없는 id (find-const 0곳) = 스킨 파일이 정한 이름 (M37)
SKIN_ONLY_IDS = ("GCNT", "MDSB", "endB", "snob", "ctnu")


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf8") as f:
        return f.read()


class Skin(unittest.TestCase):
    def test_mod_side_has_no_skin_ids(self):
        # 모드 API(modhost.js)와 모드·예제 코드에는 스킨 id가 없어야 한다
        files = [("core", "modhost.js")]
        for top in ("mods", "examples"):
            for dp, _, fs in os.walk(os.path.join(ROOT, top)):
                files += [(os.path.relpath(os.path.join(dp, f), ROOT),) for f in fs if f.endswith((".js", ".py"))]
        for f in files:
            text = read(*f)
            for sid in SKIN_ONLY_IDS:
                self.assertNotRegex(text, r"['\"]%s['\"]" % sid, "%s가 스킨 id %s를 써요" % (os.path.join(*f), sid))

    def test_core_continue_uses_internal_event(self):
        # act continue는 버튼이 아니라 게임 내부 계속 이벤트가 먼저다 (버튼 클릭은 예비)
        core = read("core", "core.js")
        i = core.index("var cs = contSend();")
        j = core.index("fireBtn(ptr(gcnt.addr)")
        self.assertLess(i, j)

    def test_screen_capabilities_marked(self):
        # 소셜 피드 화면에 기대는 기능은 screen 표시가 있어야 한다
        caps = json.loads(read("core", "capabilities.json"))["capabilities"]
        panel = re.compile(r"socialPanel|panelAt|panelText|refreshPanel|newsBody|fanClub")
        for c in caps:
            if any(panel.search(u) for u in c.get("uses", [])):
                self.assertTrue(c.get("screen"), "%s는 화면 의존 기능인데 screen 표시가 없어요" % c["name"])

    def test_unknown_language_fails_closed(self):
        # 모르는 언어면 위험 판정이 '위험'으로 (--yes 필요)
        core = read("core", "core.js")
        self.assertIn("uiLang() === 'unknown'", core)
        self.assertIn("mail.lang === 'unknown'", core)


if __name__ == "__main__":
    unittest.main()
