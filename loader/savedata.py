"""세이브별 모드 데이터 (코어 0.44.0, M82, 작성: Claude) — api.saveData / ctx.save_data

모드 자료 = 세이브 id마다 확정본(디스크) + 작업본(메모리). 모드는 작업본을 읽고 쓴다.
  - 게임 저장이 끝나면(코어 'saved')      작업본 -> 확정본 (~/m24ga_data/savedata/<세이브 id>/<모드 id>.json, 원자적 쓰기)
  - 다른 세이브를 불러오면                그 세이브의 확정본 -> 작업본
  - 같은 세이브를 다시 불러오면(저장 없이 nonce가 바뀜)  작업본을 버리고 확정본으로 되돌림
  - 저장하는 동안·직후의 nonce 변화(M53: 저장하면 nonce가 바뀜)는 되돌리지 않는다 (코어 'saving'·'saved')
같은 모드의 JS(api.saveData)와 Python(ctx.save_data)은 같은 자료를 본다. 게임 메모리는 건드리지 않는다.
"""
import json
import os
import threading
import time

DATA = os.path.join(os.path.expanduser("~"), "m24ga_data", "savedata")
MAX_BYTES = 1024 * 1024        # 모드 하나의 자료 크기 제한 (JSON 글자 수)
SAVE_GRACE = 60.0              # 'saved' 뒤 이 시간 안의 nonce 변화는 저장에 따른 것으로 본다 (초)


class Store:
    def __init__(self, root=None, clock=time.time):
        self.root = root or DATA
        self.clock = clock
        self.lock = threading.RLock()
        self.save = None           # 지금 세이브 {id, nonce}
        self.work = {}             # 모드 id -> {키: 값} (작업본)
        self.dirty = set()         # 확정본과 다른 모드
        self.saving_since = None   # 'saving' 받은 시각
        self.saved_at = None       # 마지막 'saved' 시각
        self.need_push = True      # 게임 쪽 거울을 다시 보내야 함 (스크립트를 새로 올렸을 때)

    # ---- 디스크 ----
    def _dir(self, sid):
        return os.path.join(self.root, str(int(sid)))

    def _read_committed(self, sid):
        out = {}
        d = self._dir(sid)
        if not os.path.isdir(d):
            return out
        for n in os.listdir(d):
            if n.endswith(".json"):
                try:
                    with open(os.path.join(d, n), encoding="utf-8") as f:
                        v = json.load(f)
                    if isinstance(v, dict):
                        out[n[:-5]] = v
                except (OSError, ValueError):
                    pass
        return out

    def _write(self, sid, mod, data):
        d = self._dir(sid)
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, mod + ".json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, p)

    # ---- 게임 쪽 알림 ----
    def on_game(self, save):
        """코어 'game' 알림의 세이브. 반환 'load'면 작업본이 바뀌었으니 게임 쪽 거울을 다시 보내야 한다 (None이면 그대로)."""
        with self.lock:
            save = save if isinstance(save, dict) and save.get("id") else None
            old = self.save
            if not save:
                changed = old is not None or self.work
                self.save, self.work, self.dirty = None, {}, set()
                return "load" if (changed or self.need_push) else None
            same_id = old is not None and old.get("id") == save.get("id")
            if same_id and old.get("nonce") == save.get("nonce"):
                return self._pushed() if self.need_push else None
            if same_id and self._saving_now():        # 저장 때문에 nonce가 바뀜 -> 이어서
                self.save = dict(save)
                return self._pushed() if self.need_push else None
            # 다른 세이브를 불러옴, 또는 같은 세이브를 저장 없이 다시 불러옴 -> 확정본으로
            self.save = dict(save)
            self.work = self._read_committed(save["id"])
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
        """게임 저장 끝: 작업본을 확정본으로. 반환 확정한 모드 수"""
        with self.lock:
            if isinstance(save, dict) and save.get("id"):
                if self.save and self.save.get("id") == save["id"]:
                    self.save = dict(save)
            self.saving_since = None
            self.saved_at = self.clock()
            if not self.save:
                return 0
            n = 0
            for mod in sorted(self.dirty):
                self._write(self.save["id"], mod, self.work.get(mod, {}))
                n += 1
            self.dirty = set()
            return n

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
            d = dict(self.work.get(mod, {}))
            if delete:
                d.pop(key, None)
            else:
                try:
                    json.dumps(value)
                except (TypeError, ValueError):
                    return False, "JSON으로 저장할 수 있는 값만 돼요"
                d[key] = value
            if len(json.dumps(d, ensure_ascii=False)) > MAX_BYTES:
                return False, "모드 자료가 1MB를 넘어요"
            self.work[mod] = d
            self.dirty.add(mod)
            return True, None

    def get(self, mod, key=None, default=None):
        with self.lock:
            d = self.work.get(mod, {})
            if key is None:
                return json.loads(json.dumps(d))
            return json.loads(json.dumps(d[key])) if key in d else default

    def snapshot(self):
        """게임 쪽 거울로 보낼 것: {save, all: {모드: 자료}}"""
        with self.lock:
            return {"save": self.save, "all": json.loads(json.dumps(self.work))}


STORE = Store()
