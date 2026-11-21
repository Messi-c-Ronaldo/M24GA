"""세이브별 모드 데이터 (코어 0.44.0, M82·M84, 작성: Claude) — api.saveData / ctx.save_data

모드 자료 = 세이브 id마다 확정본(디스크) + 작업본(메모리). 모드는 작업본을 읽고 쓴다.
  - 게임 저장이 끝나면(코어 'saved')      바뀐 키만 작업본 -> 확정본
                                          (~/m24ga_data/savedata/<세이브 id>/<모드 id>/<키>.json, 원자적 쓰기)
  - 다른 세이브를 불러오면                그 세이브의 확정본 -> 작업본
  - 같은 세이브를 다시 불러오면(저장 없이 nonce가 바뀜)  작업본을 버리고 확정본으로 되돌림
  - 저장하는 동안·직후의 nonce 변화(M53: 저장하면 nonce가 바뀜)는 되돌리지 않는다 (코어 'saving'·'saved')
같은 모드의 JS(api.saveData)와 Python(ctx.save_data)은 같은 자료를 본다. 다만 게임 쪽(JS) 거울에는
MIRROR_MAX 이하인 값만 보낸다 (포텐모드 부상 기록처럼 수 MB인 값은 PC 쪽 전용, JS에서는 없음).
게임 메모리는 건드리지 않는다.
"""
import json
import os
import threading
import time
import urllib.parse

DATA = os.path.join(os.path.expanduser("~"), "m24ga_data", "savedata")
KEY_MAX = 64 * 1024 * 1024      # 값 하나 (JSON 글자 수). 실제 세이브의 포텐모드 미리보기 13.8MB·부상 10.8MB (M84)
MOD_MAX = 128 * 1024 * 1024     # 모드 하나 합계
MIRROR_MAX = 256 * 1024         # 이보다 큰 값은 게임 쪽(JS) 거울에 보내지 않는다
SAVE_GRACE = 60.0               # 'saved' 뒤 이 시간 안의 nonce 변화는 저장에 따른 것으로 본다 (초)


def _fname(key):
    return urllib.parse.quote(key, safe="") + ".json"


def _key(fname):
    return urllib.parse.unquote(fname[:-5])


class Store:
    def __init__(self, root=None, clock=time.time):
        self.root = root or DATA
        self.clock = clock
        self.lock = threading.RLock()
        self.save = None           # 지금 세이브 {id, nonce}
        self.work = {}             # 모드 id -> {키: 값} (작업본)
        self.sizes = {}            # 모드 id -> {키: JSON 글자 수}
        self.dirty = set()         # 확정본과 다른 (모드, 키)
        self.saving_since = None   # 'saving' 받은 시각
        self.saved_at = None       # 마지막 'saved' 시각
        self.need_push = True      # 게임 쪽 거울을 다시 보내야 함 (스크립트를 새로 올렸을 때)

    # ---- 디스크 ----
    def _dir(self, sid, mod=None):
        d = os.path.join(self.root, str(int(sid)))
        return os.path.join(d, mod) if mod else d

    def _read_committed(self, sid):
        work, sizes = {}, {}
        d = self._dir(sid)
        if not os.path.isdir(d):
            return work, sizes
        for mod in os.listdir(d):
            md = os.path.join(d, mod)
            if not os.path.isdir(md):
                continue
            for n in os.listdir(md):
                if not n.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(md, n), encoding="utf-8") as f:
                        text = f.read()
                    work.setdefault(mod, {})[_key(n)] = json.loads(text)
                    sizes.setdefault(mod, {})[_key(n)] = len(text)
                except (OSError, ValueError):
                    pass
        return work, sizes

    def _write(self, sid, mod, key, value):
        md = self._dir(sid, mod)
        os.makedirs(md, exist_ok=True)
        p = os.path.join(md, _fname(key))
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False)
        for i in range(10):   # Windows: 백신·색인이 잠깐 열고 있으면 PermissionError
            try:
                os.replace(tmp, p)
                return
            except PermissionError:
                if i == 9:
                    raise
                time.sleep(0.05 * (i + 1))

    def _remove(self, sid, mod, key):
        try:
            os.remove(os.path.join(self._dir(sid, mod), _fname(key)))
        except OSError:
            pass

    # ---- 게임 쪽 알림 ----
    def on_game(self, save):
        """코어 'game' 알림의 세이브. 반환 'load'면 작업본이 바뀌었으니 게임 쪽 거울을 다시 보내야 한다 (None이면 그대로)."""
        with self.lock:
            save = save if isinstance(save, dict) and save.get("id") else None
            old = self.save
            if not save:
                changed = old is not None or self.work
                self.save, self.work, self.sizes, self.dirty = None, {}, {}, set()
                return "load" if (changed or self.need_push) else None
            same_id = old is not None and old.get("id") == save.get("id")
            if same_id and old.get("nonce") == save.get("nonce"):
                return self._pushed() if self.need_push else None
            if same_id and self._saving_now():        # 저장 때문에 nonce가 바뀜 -> 이어서
                self.save = dict(save)
                return self._pushed() if self.need_push else None
            # 다른 세이브를 불러옴, 또는 같은 세이브를 저장 없이 다시 불러옴 -> 확정본으로
            self.save = dict(save)
            self.work, self.sizes = self._read_committed(save["id"])
            self.dirty = set()
            self.saving_since = None
            return self._pushed()

    def _pushed(self):
        self.need_push = False
        return "load"

    def _saving_now(self):
        now = self.clock()
        if self.saving_since is not None and now - self.saving_since < 600:
            return True
        return self.saved_at is not None and now - self.saved_at < SAVE_GRACE

    def on_saving(self):
        with self.lock:
            self.saving_since = self.clock()

    def on_saved(self, save=None):
        """게임 저장 끝: 바뀐 키만 확정본으로. 반환 확정한 모드 수"""
        with self.lock:
            if isinstance(save, dict) and save.get("id"):
                if self.save and self.save.get("id") == save["id"]:
                    self.save = dict(save)
            self.saving_since = None
            self.saved_at = self.clock()
            if not self.save:
                return 0
            mods = set()
            for mod, key in sorted(self.dirty):
                if key in self.work.get(mod, {}):
                    self._write(self.save["id"], mod, key, self.work[mod][key])
                else:
                    self._remove(self.save["id"], mod, key)
                mods.add(mod)
            self.dirty = set()
            return len(mods)

    # ---- 모드 쪽 ----
    def set(self, mod, key, value=None, delete=False, save=None):
        """작업본 바꾸기. 반환 (ok, 오류). save를 주면 지금 세이브와 같을 때만."""
        with self.lock:
            if not self.save:
                return False, "세이브를 불러온 뒤에만 쓸 수 있어요"
            if save and save.get("id") != self.save.get("id"):
                return False, "다른 세이브의 자료라 버렸어요"
            if not isinstance(key, str) or not key or len(key) > 200:
                return False, "키는 1~200자 글이어야 해요"
            d = self.work.setdefault(mod, {})
            sz = self.sizes.setdefault(mod, {})
            if delete:
                d.pop(key, None)
                sz.pop(key, None)
            else:
                try:
                    n = len(json.dumps(value, ensure_ascii=False))
                except (TypeError, ValueError):
                    return False, "JSON으로 저장할 수 있는 값만 돼요"
                if n > KEY_MAX:
                    return False, "값 하나가 64MB를 넘어요"
                if sum(sz.values()) - sz.get(key, 0) + n > MOD_MAX:
                    return False, "모드 자료가 128MB를 넘어요"
                d[key] = value
                sz[key] = n
            self.dirty.add((mod, key))
            return True, None

    def get(self, mod, key=None, default=None):
        """작업본의 복사본 (고쳐도 set하기 전에는 바뀌지 않음)"""
        with self.lock:
            d = self.work.get(mod, {})
            if key is None:
                return json.loads(json.dumps(d))
            return json.loads(json.dumps(d[key])) if key in d else default

    def mirrorable(self, mod, key):
        with self.lock:
            return self.sizes.get(mod, {}).get(key, 0) <= MIRROR_MAX

    def snapshot(self):
        """게임 쪽 거울로 보낼 것: {save, all: {모드: {키: 값}}} — MIRROR_MAX 이하인 값만"""
        with self.lock:
            out = {}
            for mod, d in self.work.items():
                small = {k: v for k, v in d.items() if self.sizes.get(mod, {}).get(k, 0) <= MIRROR_MAX}
                if small:
                    out[mod] = small
            return {"save": self.save, "all": json.loads(json.dumps(out))}


STORE = Store()
