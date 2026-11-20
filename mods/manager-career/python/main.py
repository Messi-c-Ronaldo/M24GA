"""감독 커리어 모드: PC 쪽. 세이브마다 적은 경력을 career.json에 보관한다. GPL-3.0-or-later.

게임 쪽(mod.js)이 보내는 메시지:
  {"t": "get", "save": "id:nonce"}            -> {"t": "career", "save": ..., "career": {...} 또는 None}
  {"t": "save", "save": "id:nonce", "career": {...}}  -> 저장 (이력은 history에 쌓음)
"""
import json
import os
import time

FILE = "career.json"


def _path(ctx):
    d = ctx.save_dir()
    return os.path.join(d, FILE) if d else None


def _load(ctx):
    p = _path(ctx)
    if not p or not os.path.isfile(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        ctx.log("career.json을 읽지 못했어요: %s" % e)
        return {}


def _save(ctx, data):
    p = _path(ctx)
    if not p:
        ctx.log("세이브 폴더를 몰라서 저장하지 못했어요 (세이브를 불러온 뒤 다시)")
        return False
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return True


def _ready(ctx, save):
    """PC 쪽이 아는 지금 세이브가 게임 쪽이 묻는 세이브("id:nonce")와 같은가."""
    if not ctx.save_dir():
        return False
    try:
        g = ctx.game() or {}
        s = g.get("save") or {}
        return save == "%s:%s" % (s.get("id"), s.get("nonce", 0))
    except Exception:  # noqa: BLE001
        return False


def run(ctx):
    ctx.log("시작")
    while not ctx.stop.is_set():
        m = ctx.recv(0.5)
        if not isinstance(m, dict):
            continue
        t = m.get("t")
        if t == "get":
            # 세이브를 막 불러온 직후에는 PC 쪽이 아직 그 세이브를 모를 수 있다 -> 준비 안 됨으로 답하고 게임 쪽이 다시 묻는다
            if not _ready(ctx, m.get("save")):
                ctx.post({"t": "career", "save": m.get("save"), "ready": False})
                continue
            data = _load(ctx)
            ctx.post({"t": "career", "save": m.get("save"), "ready": True, "career": data.get("career")})
        elif t == "save":
            data = _load(ctx)
            c = m.get("career") or {}
            hist = data.get("history", [])
            hist.append({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "career": c})
            data = {"save": m.get("save"), "career": c, "history": hist[-20:]}
            if _save(ctx, data):
                ctx.log("경력 저장: %s" % _path(ctx))
