# -*- coding: utf-8 -*-
"""Hello 예제 모드: Python 부분.

로더가 run(ctx)를 스레드로 부른다. ctx.stop이 켜지면(모드를 끄거나 로더를 멈출 때) 빨리 끝내야 한다.
이름이 ui_로 시작하는 함수는 모드창(ui/index.html)이 m24.call('이름', ...)으로 부를 수 있다.
설정은 ctx.settings()로 읽는다 (GUI에서 바꾸면 다음 호출부터 바로 반영된다).
"""
import time

_ctx = None
_started = None
_ticks = 0


def run(ctx):
    global _ctx, _started, _ticks
    _ctx, _started, _ticks = ctx, time.time(), 0
    ctx.log("시작. 데이터 폴더 %s, 설정 %s" % (ctx.data_dir, ctx.settings()))
    while not ctx.stop.wait(1.0):   # 1초마다 깨어나되, 멈추라고 하면 바로 끝낸다
        _ticks += 1
    ctx.log("끝")


def status():
    """선택 사항. 로더가 모드 상태를 물을 때 부른다."""
    return {"ticks": _ticks}


def _greeting(name):
    s = _ctx.settings()
    word = {"plain": s["greeting"], "polite": s["greeting"] + "하세요", "casual": s["greeting"] + "~"}[s["tone"]]
    out = " ".join([word] * int(s["repeat"])) + (", " + name if name else "")
    return out + ("!" if s["shout"] else "")


# ---- 모드창이 부르는 함수 ----
def ui_state():
    return {"ticks": _ticks, "up": int(time.time() - _started) if _started else 0, "mood": _ctx.settings()["mood"]}


def ui_greet(name):
    return _greeting((name or "").strip()[:30])
