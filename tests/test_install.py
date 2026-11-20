"""데이터 폴더 이전, .24mod 설치·삭제·충돌의 시험 (임시 폴더에서만 돈다. 사용자 mods 폴더와 ~/m24ga_data는 건드리지 않는다).

  python -X utf8 -W error::ResourceWarning -m unittest discover -s tests
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import m24  # noqa: E402
import mods as modlib  # noqa: E402
import pack_mod  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Sandbox(unittest.TestCase):
    """modlib의 USER_MODS/DEV_MODS/DATA/TRASH를 임시 폴더로 바꿔 놓는다."""

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self._saved = (modlib.USER_MODS, modlib.DEV_MODS, modlib.DATA, modlib.TRASH, modlib.ENABLED_PATH, modlib.AUTO_PATH)
        modlib.USER_MODS = os.path.join(self.td, "user")
        modlib.DEV_MODS = os.path.join(self.td, "dev")
        modlib.DATA = os.path.join(self.td, "data")
        modlib.TRASH = os.path.join(modlib.DATA, "trash")
        modlib.ENABLED_PATH = os.path.join(modlib.DATA, "enabled.json")
        modlib.AUTO_PATH = os.path.join(modlib.DATA, "autodisabled.json")
        for d in (modlib.USER_MODS, modlib.DEV_MODS):
            os.makedirs(d)

    def tearDown(self):
        (modlib.USER_MODS, modlib.DEV_MODS, modlib.DATA, modlib.TRASH, modlib.ENABLED_PATH, modlib.AUTO_PATH) = self._saved
        shutil.rmtree(self.td, ignore_errors=True)

    def make_pack(self, mid, version="1.0.0", extra=None):
        """mod.json과 mod.js만 있는 .24mod를 만들어 경로를 돌려준다."""
        src = os.path.join(self.td, "src")
        shutil.rmtree(src, ignore_errors=True)
        os.makedirs(src)
        assert m24.main(["new", mid, "--dir", src]) == 0
        mj = os.path.join(src, mid, "mod.json")
        with open(mj, encoding="utf-8") as f:
            m = json.load(f)
        m["version"] = version
        m.update(extra or {})
        with open(mj, "w", encoding="utf-8") as f:
            json.dump(m, f)
        out = os.path.join(self.td, "out-" + version)
        os.makedirs(out, exist_ok=True)
        return pack_mod.pack(os.path.join(src, mid), out)[0]

    def mod_of(self, kind_path):
        return modlib._load_one(kind_path)


class Migrate(Sandbox):
    def folder_mod(self, extra):
        d = os.path.join(modlib.DEV_MODS, "m1")
        os.makedirs(d)
        with open(os.path.join(d, "mod.json"), "w", encoding="utf-8") as f:
            json.dump(dict({"id": "m1", "name": "M1", "version": "1.0.0"}, **extra), f)
        return modlib._load_one(d)

    def test_copies_once_and_keeps_old_folder(self):
        old = os.path.join(self.td, "oldhome")
        os.makedirs(os.path.join(old, "sub"))
        for rel, txt in (("config.json", '{"a": 1}'), ("sub/x.txt", "x"), ("stop.flag", ""), ("junk.tmp", "t")):
            with open(os.path.join(old, rel), "w") as f:
                f.write(txt)
        m = self.folder_mod({"migrate_from": old})
        note = modlib.ensure_data(m)
        self.assertIn("복사", note)
        new = m.data_dir
        self.assertEqual(read(os.path.join(new, "config.json")), '{"a": 1}')
        self.assertTrue(os.path.exists(os.path.join(new, "sub", "x.txt")))
        self.assertFalse(os.path.exists(os.path.join(new, "stop.flag")))      # 제외 대상
        self.assertFalse(os.path.exists(os.path.join(new, "junk.tmp")))
        self.assertTrue(os.path.exists(os.path.join(new, modlib.MIGRATED)))
        self.assertTrue(os.path.exists(os.path.join(old, "config.json")))     # 옛 폴더는 그대로
        self.assertFalse(os.path.exists(new + ".migrating"))
        # 두 번째는 아무것도 안 한다. 새 폴더에서 바꾼 내용을 옛 폴더가 덮어쓰지 않는다
        with open(os.path.join(new, "config.json"), "w") as f:
            f.write('{"a": 2}')
        self.assertIsNone(modlib.ensure_data(m))
        self.assertEqual(read(os.path.join(new, "config.json")), '{"a": 2}')

    def test_does_not_touch_nonempty_new_folder(self):
        old = os.path.join(self.td, "oldhome")
        os.makedirs(old)
        with open(os.path.join(old, "config.json"), "w") as f:
            f.write("old")
        m = self.folder_mod({"migrate_from": old})
        os.makedirs(m.data_dir)
        with open(os.path.join(m.data_dir, "mine.txt"), "w") as f:
            f.write("mine")
        self.assertIsNone(modlib.ensure_data(m))
        self.assertEqual(os.listdir(m.data_dir), ["mine.txt"])

    def test_missing_old_folder_just_makes_new(self):
        m = self.folder_mod({"migrate_from": os.path.join(self.td, "nope")})
        self.assertIsNone(modlib.ensure_data(m))
        self.assertTrue(os.path.isdir(m.data_dir))
        self.assertFalse(os.path.exists(os.path.join(m.data_dir, modlib.MIGRATED)))

    def test_same_folder_is_ignored(self):
        m = self.folder_mod({})
        m.manifest["migrate_from"] = m.data_dir
        self.assertIsNone(modlib.ensure_data(m))

    def test_real_social_feed_declares_migration(self):
        m = modlib._load_one(os.path.join(ROOT, "mods", "ai-social-feed"))
        self.assertEqual(m.manifest.get("migrate_from"), "~/fm24_ai_mod_data")
        self.assertNotIn("data_dir", m.manifest)
        self.assertEqual(os.path.normcase(m.data_dir), os.path.normcase(os.path.join(modlib.DATA, "ai-social-feed")))


class InstallRemove(Sandbox):
    def test_install_then_update_moves_old_to_trash(self):
        p1 = self.make_pack("inst-a", "1.0.0")
        r = modlib.install(p1)
        self.assertTrue(r["ok"], r)
        self.assertIsNone(r["replaced"])
        dst = os.path.join(modlib.USER_MODS, "inst-a.24mod")
        self.assertTrue(os.path.isfile(dst))
        self.assertEqual([m.id for m in modlib.scan()[0]], ["inst-a"])
        p2 = self.make_pack("inst-a", "1.1.0")
        r = modlib.install(p2)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["replaced"], "1.0.0")
        self.assertEqual(modlib.scan()[0][0].version, "1.1.0")
        self.assertEqual(len(os.listdir(modlib.TRASH)), 1)                    # 옛 버전이 남아 있다
        self.assertFalse(os.path.exists(dst + ".part"))

    def test_install_refuses_non_24mod_and_failing_validate(self):
        txt = os.path.join(self.td, "a.txt")
        with open(txt, "w"):
            pass
        self.assertFalse(modlib.install(txt)["ok"])
        bad = os.path.join(self.td, "bad.24mod")
        import zipfile
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("mod.json", json.dumps({"id": "bad-one", "name": "x", "version": "1.0.0"}))     # mod.js가 없다
        r = modlib.install(bad)
        self.assertFalse(r["ok"])
        self.assertIn("report", r)
        self.assertEqual(os.listdir(modlib.USER_MODS), [])

    def test_install_refuses_when_same_id_exists_elsewhere(self):
        d = os.path.join(modlib.DEV_MODS, "inst-b")
        self.assertEqual(m24.main(["new", "inst-b", "--dir", modlib.DEV_MODS]), 0)
        p = self.make_pack("inst-b")
        r = modlib.install(p)
        self.assertFalse(r["ok"])
        self.assertIn(d, r["error"])
        self.assertEqual(os.listdir(modlib.USER_MODS), [])

    def test_uninstall_moves_to_trash_and_keeps_data(self):
        modlib.install(self.make_pack("inst-c"))
        m = modlib.scan()[0][0]
        self.assertTrue(modlib.removable(m))
        os.makedirs(m.data_dir)
        r = modlib.uninstall(m)
        self.assertTrue(r["ok"], r)
        self.assertTrue(os.path.exists(r["trash"]))
        self.assertEqual(modlib.scan()[0], [])
        self.assertTrue(os.path.isdir(m.data_dir))                              # 데이터 폴더는 그대로

    def test_dev_folder_is_not_removable(self):
        self.assertEqual(m24.main(["new", "inst-d", "--dir", modlib.DEV_MODS]), 0)
        m = modlib.scan()[0][0]
        self.assertFalse(modlib.removable(m))
        r = modlib.uninstall(m)
        self.assertFalse(r["ok"])
        self.assertTrue(os.path.isdir(m.path))

    def test_duplicate_ids_report_conflicts_and_removable(self):
        self.assertEqual(m24.main(["new", "inst-e", "--dir", modlib.DEV_MODS]), 0)
        shutil.copyfile(self.make_pack("inst-e"), os.path.join(modlib.USER_MODS, "inst-e.24mod"))
        mods, _ = modlib.scan()
        self.assertEqual(len(mods), 2)
        for m in mods:
            self.assertTrue(any(p.startswith("같은 id") for p in m.problems))
            self.assertEqual(len(m.conflicts), 1)
            self.assertNotEqual(m.conflicts[0], m.path)
        info = {m.kind: m.info() for m in mods}
        self.assertTrue(info["file"]["removable"])
        self.assertFalse(info["dir"]["removable"])


if __name__ == "__main__":
    unittest.main()
