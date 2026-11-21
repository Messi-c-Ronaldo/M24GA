"""세이브별 모드 데이터 (M82, loader/savedata.py) — 게임 없이 세이브 흐름을 흉내 낸다."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
import savedata  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class SaveData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.clock = Clock()
        self.s = savedata.Store(self.tmp, self.clock)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def load(self, sid, nonce):
        return self.s.on_game({"id": sid, "nonce": nonce})

    def test_save_commits_and_reload_reverts(self):
        self.assertEqual(self.load(7, 1), "load")
        self.assertEqual(self.s.set("m", "a", 1), (True, None))
        self.s.on_saving()
        self.clock.t += 15
        self.assertIsNone(self.load(7, 2))            # 저장 중 nonce 변화 -> 이어서 (되돌리지 않음)
        self.assertEqual(self.s.on_saved({"id": 7, "nonce": 2}), 1)
        self.assertEqual(json.load(open(os.path.join(self.tmp, "7", "m.json"), encoding="utf-8")), {"a": 1})
        self.s.set("m", "a", 2)                        # 저장 뒤 바꿈
        self.clock.t += 300
        self.assertEqual(self.load(7, 3), "load")      # 저장 없이 다시 불러옴 -> 확정본으로
        self.assertEqual(self.s.get("m", "a"), 1)

    def test_nonce_change_right_after_saved_is_kept(self):
        self.load(7, 1)
        self.s.set("m", "a", 1)
        self.s.on_saving()
        self.s.on_saved({"id": 7, "nonce": 1})        # 'saved'가 nonce 변화보다 먼저 와도
        self.clock.t += 5
        self.assertIsNone(self.load(7, 2))
        self.assertEqual(self.s.get("m", "a"), 1)

    def test_other_save_is_separate(self):
        self.load(7, 1)
        self.s.set("m", "a", 1)
        self.s.on_saving()
        self.s.on_saved()
        self.clock.t += 300
        self.assertEqual(self.load(8, 1), "load")
        self.assertIsNone(self.s.get("m", "a"))
        self.s.set("m", "a", 99)
        self.clock.t += 300
        self.load(7, 5)
        self.assertEqual(self.s.get("m", "a"), 1)      # 8번에서 쓴 것은 저장 안 해서 사라지고 7번은 확정본

    def test_unsaved_changes_dropped_on_menu(self):
        self.load(7, 1)
        self.s.set("m", "a", 1)
        self.assertEqual(self.s.on_game(None), "load")
        self.assertEqual(self.s.set("m", "a", 2)[0], False)   # 세이브 없으면 못 씀

    def test_delete_and_limits(self):
        self.load(7, 1)
        self.s.set("m", "a", 1)
        self.s.set("m", "a", delete=True)
        self.assertIsNone(self.s.get("m", "a"))
        self.assertFalse(self.s.set("m", "x", object())[0])
        self.assertFalse(self.s.set("m", "", 1)[0])
        self.assertFalse(self.s.set("m", "big", "x" * (savedata.MAX_BYTES + 1))[0])
        self.assertFalse(self.s.set("m", "a", 1, save={"id": 8})[0])   # 다른 세이브 자료

    def test_need_push_after_script_reload(self):
        self.assertEqual(self.load(7, 1), "load")
        self.assertIsNone(self.load(7, 1))
        self.s.need_push = True                        # 스크립트를 새로 올림
        self.assertEqual(self.load(7, 1), "load")
        snap = self.s.snapshot()
        self.assertEqual(snap["save"], {"id": 7, "nonce": 1})

    def test_core_and_host_wired(self):
        core = open(os.path.join(ROOT, "core", "core.js"), encoding="utf-8").read()
        host = open(os.path.join(ROOT, "core", "modhost.js"), encoding="utf-8").read()
        py = open(os.path.join(ROOT, "loader", "host.py"), encoding="utf-8").read()
        self.assertIn("t: 'saving'", core)
        self.assertIn("t: 'saved'", core)
        self.assertIn("saveData:", host)
        self.assertIn("'__sd'", host)
        self.assertIn("savedata.STORE", py)


if __name__ == "__main__":
    unittest.main()
