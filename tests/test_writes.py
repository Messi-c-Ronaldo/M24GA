"""게임 값 쓰기 기록과 되돌리기 시험 (M14): 호스트가 코어 알림을 writes.jsonl에 남기고, 지금 세이브의 것만 거꾸로 되돌리는지.
게임 없이 가짜 스크립트로 돈다. 임시 폴더만 쓴다."""
import json
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


class FakeExports:
    def __init__(self, values):
        self.values, self.calls = values, []

    def undowrite(self, field, key, frm, to):
        self.calls.append((field, key, frm, to))
        if self.values.get(key) != to:
            return {"ok": False, "error": "지금 값이 달라요"}
        self.values[key] = frm
        return {"ok": True, "before": to, "after": frm}


class FakeScript:
    def __init__(self, ex):
        self.exports_sync = ex


@unittest.skipIf(host is None, "frida 없음")
class Writes(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.saved = (modlib.DATA, host.LOG, dict(modlib.GAME), dict(host._cur))
        modlib.DATA = self.td
        host.LOG = os.path.join(self.td, "loader.log")
        modlib.GAME.update(date="2035-04-27", save={"id": 5117219, "nonce": 1})

    def tearDown(self):
        modlib.DATA, host.LOG, game, cur = self.saved
        modlib.GAME.clear(); modlib.GAME.update(game)
        host._cur.clear(); host._cur.update(cur)
        shutil.rmtree(self.td, ignore_errors=True)

    def notice(self, mod, key, frm, to, save=None, name="선수"):
        host._core_notice({"t": "write", "id": mod, "field": "player.pa", "key": key, "from": frm, "to": to, "name": name,
                           "save": save or {"id": 5117219, "nonce": 1}, "date": "2035-04-27", "reason": "시험"})

    def test_notice_is_logged(self):
        self.notice("pm", 7, 140, 150)
        self.notice("pm", 8, 100, 120)
        self.notice("other", 9, 90, 95)
        with open(os.path.join(self.td, "writes.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
        self.assertEqual([r["n"] for r in rows], [1, 2, 3])
        self.assertEqual((rows[0]["mod"], rows[0]["key"], rows[0]["from"], rows[0]["to"], rows[0]["reason"]), ("pm", 7, 140, 150, "시험"))
        log = host.write_log("pm")
        self.assertEqual([r["key"] for r in log], [8, 7])                       # 최근 것 먼저
        with open(host.LOG, encoding="utf-8") as f:
            self.assertIn("게임 값을 바꿨어요", f.read())

    def test_undo_current_save_in_reverse_and_cas(self):
        self.notice("pm", 7, 140, 150)
        self.notice("pm", 7, 150, 155)                                           # 같은 선수 두 번
        self.notice("pm", 8, 100, 120)
        self.notice("pm", 9, 60, 70, save={"id": 42, "nonce": 1})               # 다른 세이브: 되돌리지 않음
        self.notice("pm", 10, 80, 90)
        values = {7: 155, 8: 120, 10: 95}                                        # 10은 그 뒤 다른 것이 바꿈
        ex = FakeExports(values)
        host._cur["script"] = FakeScript(ex)
        r = host.undo_writes("pm")
        self.assertTrue(r["ok"])
        self.assertEqual(r["done"], 3)
        self.assertEqual([s["n"] for s in r["skipped"]], [5])
        self.assertEqual([c[1] for c in ex.calls], [10, 8, 7, 7])                # 최근 것부터
        self.assertEqual(values, {7: 140, 8: 100, 10: 95})                       # 7은 155→150→140 순서대로, 10은 안 건드림
        log = host.write_log("pm", 5117219)
        self.assertEqual(sorted(r["n"] for r in log if r["undone"]), [1, 2, 3])
        ex.calls.clear()
        r = host.undo_writes("pm")                                              # 두 번째: 이미 되돌린 것은 안 함
        self.assertEqual([c[1] for c in ex.calls], [10])

    def test_undo_needs_game(self):
        self.notice("pm", 7, 140, 150)
        host._cur["script"] = None
        self.assertFalse(host.undo_writes("pm")["ok"])
        modlib.GAME.update(save=None)
        host._cur["script"] = FakeScript(FakeExports({7: 150}))
        self.assertFalse(host.undo_writes("pm")["ok"])

    def test_nonce_mismatch_is_not_undone(self):
        self.notice("pm", 7, 140, 150, save={"id": 5117219, "nonce": 2})
        ex = FakeExports({7: 150})
        host._cur["script"] = FakeScript(ex)
        self.assertEqual(host.undo_writes("pm")["done"], 0)
        self.assertEqual(ex.calls, [])


if __name__ == "__main__":
    unittest.main()
