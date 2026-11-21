"""기존 모드를 세이브별 모드 데이터로 옮긴 것 (M84): 포텐모드·감독 커리어가 예전 파일을 한 번 가져오고,
그 뒤에는 ctx.save_data만 쓰며, 저장 없이 다시 불러오면 되돌아가는지 — 가짜 ctx로."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "pylib"))
import savedata  # noqa: E402


class _SD:
    def __init__(self, store, mod):
        self.s, self.m = store, mod

    def get(self, k, d=None):
        return self.s.get(self.m, k, d)

    def set(self, k, v):
        ok, why = self.s.set(self.m, k, v)
        return {"ok": ok, "error": why}


class FakeCtx:
    def __init__(self, store, mod, save_dir):
        self.store, self.mod, self.dir = store, mod, save_dir
        self.logs = []

    def save_data(self):
        return _SD(self.store, self.mod)

    def save_dir(self):
        return self.dir

    def log(self, m):
        self.logs.append(m)

    def game(self):
        return {"save": self.store.save, "date": "2035-10-25"}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec.loader.exec_module(m)
    finally:
        sys.path.pop(0)
    return m


class ModSaveData(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = savedata.Store(os.path.join(self.tmp, "sd"))
        self.store.on_game({"id": 7, "nonce": 1})
        self.dir = os.path.join(self.tmp, "saves", "7")
        os.makedirs(self.dir)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _reload_unsaved(self):
        self.store.clock = lambda: 10 ** 9   # 저장 직후 아님
        self.store.on_game(None)
        self.store.on_game({"id": 7, "nonce": 2})

    def test_dynamic_potential(self):
        dp = _load(os.path.join(ROOT, "mods", "dynamic-potential", "python", "main.py"), "dp_main_test")
        dp._ctx = FakeCtx(self.store, "dynamic-potential", self.dir)
        with open(os.path.join(self.dir, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"evaluated": ["2035-07-01"]}, f)
        # 예전 파일을 한 번 가져온다
        self.assertEqual(dp._read(dp._path("state.json"), {}), {"evaluated": ["2035-07-01"]})
        self.assertEqual(self.store.get("dynamic-potential", "state"), {"evaluated": ["2035-07-01"]})
        self.store.on_saving()
        self.store.on_saved()
        # 그 뒤 쓰기는 파일이 아니라 save_data로
        dp._write(dp._path("state.json"), {"evaluated": ["2035-07-01", "2036-07-01"]})
        with open(os.path.join(self.dir, "state.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"evaluated": ["2035-07-01"]})
        self.assertEqual(dp._read(dp._path("state.json"), {}), {"evaluated": ["2035-07-01", "2036-07-01"]})
        # 저장 없이 다시 불러오면 되돌아감
        self._reload_unsaved()
        self.assertEqual(dp._read(dp._path("state.json"), {}), {"evaluated": ["2035-07-01"]})
        # 캐시 파일은 그대로 파일
        self.assertIsNone(dp.SD_KEYS.get("savehist.pkl"))

    def test_manager_career(self):
        mc = _load(os.path.join(ROOT, "mods", "manager-career", "python", "main.py"), "mc_main_test")
        ctx = FakeCtx(self.store, "manager-career", self.dir)
        with open(os.path.join(self.dir, "career.json"), "w", encoding="utf-8") as f:
            json.dump({"career": {"level": 8000}, "history": []}, f)
        self.assertEqual(mc._load(ctx)["career"], {"level": 8000})        # 예전 파일 가져옴
        self.store.on_saving()
        self.store.on_saved()
        self.assertTrue(mc._save(ctx, {"career": {"level": 3250}, "history": []}))
        self.assertEqual(mc._load(ctx)["career"], {"level": 3250})
        self._reload_unsaved()
        self.assertEqual(mc._load(ctx)["career"], {"level": 8000})        # 저장 안 한 변경은 되돌아감


if __name__ == "__main__":
    unittest.main()
