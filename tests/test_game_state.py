"""게임 날짜·세이브의 Python 쪽 시험 (M12): 호스트가 코어 알림을 받아 ctx.game()/ctx.save_dir()로 넘기는지. 게임 없이 돈다."""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
import mods as modlib  # noqa: E402

try:
    import host  # noqa: E402
except ImportError:      # pragma: no cover
    host = None


class FakeMod:
    def __init__(self, data_dir):
        self.id, self.data_dir, self.manifest = "gm", data_dir, {}


@unittest.skipIf(host is None, "frida 없음")
class GameState(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.saved_log = host.LOG
        host.LOG = os.path.join(self.td, "loader.log")
        self.saved_game = dict(modlib.GAME)
        modlib.GAME.update(date=None, save=None)
        self.ctx = modlib.ModContext(FakeMod(os.path.join(self.td, "gm")), lambda m: None)

    def tearDown(self):
        host.LOG = self.saved_log
        modlib.GAME.clear()
        modlib.GAME.update(self.saved_game)
        shutil.rmtree(self.td, ignore_errors=True)

    def log_text(self):
        try:
            with open(host.LOG, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return ""

    def test_no_game(self):
        self.assertEqual(self.ctx.game(), {"date": None, "save": None})
        self.assertIsNone(self.ctx.save_dir())

    def test_notice_flows_to_ctx(self):
        host._core_notice({"t": "game", "date": "2035-04-25", "save": {"id": 5117219, "nonce": 1}})
        self.assertEqual(self.ctx.game(), {"date": "2035-04-25", "save": {"id": 5117219, "nonce": 1}})
        d = self.ctx.save_dir()
        self.assertTrue(os.path.isdir(d))
        self.assertTrue(d.replace("\\", "/").endswith("gm/saves/5117219"))
        self.assertIn("세이브 확인: id 5117219", self.log_text())
        # 날짜만 바뀌면 세이브 기록은 다시 남기지 않는다
        host._core_notice({"t": "game", "date": "2035-04-26", "save": {"id": 5117219, "nonce": 1}})
        self.assertEqual(self.ctx.game()["date"], "2035-04-26")
        self.assertEqual(self.log_text().count("세이브 확인"), 1)
        # ctx.game()은 복사본이다
        self.ctx.game()["save"]["id"] = 0
        self.assertEqual(modlib.GAME["save"]["id"], 5117219)

    def test_menu_and_unload_clear(self):
        host._core_notice({"t": "game", "date": "2035-04-25", "save": {"id": 1, "nonce": 1}})
        host._core_notice({"t": "game", "date": None, "save": None})
        self.assertIsNone(self.ctx.save_dir())
        self.assertIn("세이브 없음", self.log_text())
        host._core_notice({"t": "game", "date": "2035-04-25", "save": {"id": 1, "nonce": 1}})
        host._unload_script()               # 스크립트가 없어도 (게임에서 떨어짐) 상태를 비운다
        self.assertEqual(self.ctx.game(), {"date": None, "save": None})


if __name__ == "__main__":
    unittest.main()
