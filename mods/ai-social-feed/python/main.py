# -*- coding: utf-8 -*-
"""AI 소셜피드 모드의 Python 진입점 (M24GA). GPL-3.0-or-later.

로더가 run(ctx)를 스레드로 부른다. 하는 일은 예전 fm24_ai_mod/launcher.py가 브리지를 켜던 부분과 같다:
설정 파일 확인 → API 키 확인 → bridge.main(게임 쪽 메시지 처리 + AI 생성 + 캐시 저장).
bridge.py, ai_generator.py, config.py, feed_markup.py는 fm24_ai_mod에서 그대로 옮겼다.
"""
import json
import os
import urllib.request

# 모드창(ui_*)이 모드가 켜지기 전/후 어느 쪽에서 불러도 같은 데이터 폴더를 쓰도록 config.py를 불러오기 전에 정한다
os.environ.setdefault("FM24_AI_DATA", os.path.expanduser("~/m24ga_data/ai-social-feed"))


def run(ctx):
    os.environ["FM24_AI_DATA"] = ctx.data_dir      # config.py가 처음 import될 때 이 폴더를 쓴다
    import bridge
    import config as cfg
    cfg.ensure_default_file()
    for w in cfg.warnings():
        ctx.log("config 경고: " + w)
    warned = False
    while not os.path.exists(cfg.data_path(cfg.get("api.key_file"))):
        # 키가 없다고 예외로 죽으면 모드창에서 키를 넣을 수도 없고(Python이 안 돎), 반복 오류로 자동으로 꺼진다. 키가 생길 때까지 기다린다
        if not warned:
            ctx.log("API 키 파일이 없습니다: %s (모드창에서 키를 넣어 주세요. 넣으면 바로 시작해요)" % cfg.data_path(cfg.get("api.key_file")))
            warned = True
        if ctx.stop.wait(2.0):
            return
    bridge.main(stop_event=ctx.stop, link=ctx)   # 요청·결과는 메시지로 (7a단계). link를 안 주면 예전 파일 방식


def status():
    """GUI 표시용: 이번 실행의 생성 수, 토큰, 예상 비용, 최근 댓글 수."""
    import sys
    bridge = sys.modules.get("bridge")
    if not bridge:
        return None
    s = bridge.STATS
    return {"made": s["ok"], "failed": s["fail"], "tokens": s["hit"] + s["miss"] + s["out"],
            "cost": round(bridge.cost_usd(), 4), "recent": len(bridge.RECENT)}


def recent(n=30):
    import sys
    bridge = sys.modules.get("bridge")
    return list(bridge.RECENT)[:n] if bridge else []


# ---- 모드창이 부르는 함수 (이름 앞에 ui_ 가 붙은 것만 밖에서 부를 수 있다) ----
def _key_path():
    import config as cfg
    return cfg.data_path(cfg.get("api.key_file"))


def ui_state():
    import bridge
    import config as cfg
    s = bridge.STATS
    return {"made": s["ok"], "failed": s["fail"], "tokens": s["hit"] + s["miss"] + s["out"], "cost": round(bridge.cost_usd(), 4),
            "keySet": os.path.exists(_key_path()), "model": cfg.get("api.model")}


def ui_recent(n=30):
    import bridge
    return list(bridge.RECENT)[:int(n)]


def ui_set_key(key):
    key = (key or "").strip()
    if len(key) < 10 or " " in key:
        return {"ok": False, "error": "키 형식이 이상해요"}
    p = _key_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(key)
    return {"ok": True}


def ui_test_api():
    """키가 맞는지 잔액 조회로 확인한다 (DeepSeek만). 다른 제공자는 키 존재만 확인."""
    import config as cfg
    if not os.path.exists(_key_path()):
        return {"ok": False, "error": "API 키가 없어요"}
    if "api.deepseek.com" not in cfg.get("api.url"):
        return {"ok": True, "balance": None, "note": "잔액 조회는 DeepSeek만 지원해요"}
    try:
        with open(_key_path(), encoding="utf-8") as f:
            key = f.read().strip()
        req = urllib.request.Request("https://api.deepseek.com/user/balance", headers={"Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.load(r)
        infos = d.get("balance_infos") or []
        usd = next((b for b in infos if b.get("currency") == "USD"), infos[0] if infos else {})
        return {"ok": True, "balance": usd.get("total_balance"), "currency": usd.get("currency", ""), "available": d.get("is_available")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "키가 맞지 않아요 (HTTP %d)" % e.code if e.code in (401, 403) else "HTTP %d" % e.code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "연결 실패: %s" % type(e).__name__}
