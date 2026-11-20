# -*- coding: utf-8 -*-
"""FM24 AI 소셜피드 모드: 요청 파일 감시 + 생성 + 캐시 저장 (작성: Claude Sonnet)

게임 안 hook.js가 requests.jsonl에 한 줄씩 요청을 쓰고, 이 프로그램이 읽어서 문장을 만든 뒤
cache.json(키 -> 새 문장, 실패는 null)에 저장한다. hook.js가 cache.json을 몇 초마다 다시 읽는다.

M24GA 7a단계: 로더가 켜면 main(link=ctx)로 불러서 요청·결과를 파일 대신 메시지(ctx.recv / ctx.post)로 주고받는다.
  JS -> Python: {"t":"hello"} (연결 직후), {"t":"req","r":{요청}}   Python -> JS: {"t":"snap","c":{키:문장}}, {"t":"cfg","c":{...}}, {"t":"ready"}, {"t":"res","k":키,"v":문장|null}
  받은 요청은 requests.jsonl에 기록만 한다 (예전 세션과 비교하는 용도). 직접 실행(link 없음)하면 예전처럼 requests.jsonl을 읽는다.

사용: python -X utf8 bridge.py [최대호출수=400]
종료: Ctrl+C 또는 ~/m24ga_data/ai-social-feed/stop.flag 파일 만들기
"""
import collections
import concurrent.futures as cf
import json
import os
import sys
import threading
import time

import ai_generator as g
import config as cfg


def max_calls():
    return MAX_CALLS_ARG if MAX_CALLS_ARG is not None else cfg.get("tokens.max_calls_per_session")

# 게임 프로세스는 Program Files 안에 쓸 수 없으므로 주고받는 파일은 사용자 폴더에 둔다
DATA = cfg.DATA_DIR
os.makedirs(DATA, exist_ok=True)
REQ = os.path.join(DATA, "requests.jsonl")
CACHE = os.path.join(DATA, "cache.json")
LOG = os.path.join(DATA, "bridge.log")
STOP = os.path.join(DATA, "stop.flag")
MAX_CALLS_ARG = None   # 직접 실행할 때 숫자 인자를 주면 그 값, 아니면 config tokens.max_calls_per_session
# 동시 요청 수는 config api.concurrency

LINK = None   # 로더가 준 메시지 채널(ctx). 없으면 파일 방식
lock = threading.Lock()
cache = {}
inflight = set()
calls = 0
# 앱 표시용: 이번 실행의 성공/실패 수와 토큰 합계(재시도 포함), 최근 생성 댓글
STATS = {"ok": 0, "fail": 0, "hit": 0, "miss": 0, "out": 0, "since": None}
RECENT = collections.deque(maxlen=50)


def cost_usd():
    """이번 실행 예상 비용 (config pricing, 100만 토큰당 달러)."""
    p = cfg.get("pricing")
    return (STATS["hit"] * p["input_hit_per_m"] + STATS["miss"] * p["input_miss_per_m"] + STATS["out"] * p["output_per_m"]) / 1e6


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_cache():
    global cache
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (FileNotFoundError, ValueError):
        cache = {}


def save_cache():
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=True)
    os.replace(tmp, CACHE)


def post(obj):
    if LINK:
        LINK.post(obj)


def cfg_msg():
    """게임 쪽이 쓰는 설정 (예전에는 JS가 config.json을 2.5초마다 읽었다)."""
    return {"enabled": bool(cfg.get("enabled")), "types": cfg.get("hook.replace_types"), "maxReq": cfg.get("hook.max_requests"),
            "autoRefresh": bool(cfg.get("hook.auto_refresh")), "useBody": bool(cfg.get("tokens.use_article_body"))}


def send_snapshot():
    """게임 쪽이 처음 연결하면 지금까지 만든 문장 전부와 설정을 보낸다."""
    with lock:
        items = list(cache.items())
    for i in range(0, len(items), 100):
        post({"t": "snap", "c": dict(items[i:i + 100])})
    post({"t": "cfg", "c": cfg_msg()})
    post({"t": "ready"})
    log("게임 연결: 캐시 %d개 전달" % len(items))


def log_request(req):
    with open(REQ, "a", encoding="utf-8") as f:
        f.write(json.dumps(req, ensure_ascii=False) + "\n")


def work(req):
    parent = req.get("p") or None
    with g.thread_lock(parent):      # 같은 글의 댓글은 차례로 만들어야 서로 겹침을 볼 수 있다
        out, info = g.generate(req["o"], req.get("t"), parent, ctx=req.get("ctx"), body=req.get("b") or None, fan=req.get("fan"))
    finish(req, out, info, info.get("tries", 1))


def work_batch(reqs):
    """같은 글의 요청 여러 개를 한 번에 (28번 로그). 검사에 걸린 것만 하나씩 다시 만든다."""
    parent = reqs[0].get("p") or None
    body = next((r.get("b") for r in reqs if r.get("b")), None)
    with g.thread_lock(parent):
        try:
            res = g.generate_batch(reqs, parent, body)
        except Exception as e:  # noqa: BLE001
            log("batch 오류: %r" % e)
            res = [(None, {"error": "batch exc", "usage": {}, "sec": 0}) for _ in reqs]
        redo = []
        for i, (req, (out, info)) in enumerate(zip(reqs, res)):
            if out:
                finish(req, out, info, 1 if i == 0 else 0, tag="B%d" % len(reqs))
            else:
                redo.append((req, info))
        if len(redo) == len(reqs):           # 묶음 호출 자체가 실패: 호출 1회는 첫 요청 몫으로 센다
            redo[0][1]["_api_counted"] = True
        for req, binfo in redo:
            out, info = g.generate(req["o"], req.get("t"), parent, ctx=req.get("ctx"), body=req.get("b") or None, fan=req.get("fan"))
            if binfo.get("usage_sum") and not binfo.get("_merged"):
                for k2, v2 in binfo["usage_sum"].items():     # 묶음 호출 토큰이 실패한 첫 항목에 있으면 합친다
                    info.setdefault("usage_sum", {})[k2] = info.get("usage_sum", {}).get(k2, 0) + v2
            info["error"] = info.get("error") or None
            finish(req, out, info, info.get("tries", 1) + (1 if binfo.get("_api_counted") else 0),
                   tag="R(" + str(binfo.get("error")) + ")")


def finish(req, out, info, n_api, tag=""):
    global calls
    k = req["k"]
    u = info.get("usage_sum") or info.get("usage") or {}
    with lock:
        calls += n_api
        cache[k] = out            # 실패면 None -> 다시 시도하지 않는다
        save_cache()
        inflight.discard(k)
        STATS["ok" if out else "fail"] += 1
        STATS["hit"] += u.get("prompt_cache_hit_tokens", 0)
        STATS["miss"] += u.get("prompt_cache_miss_tokens", u.get("prompt_tokens", 0) - u.get("prompt_cache_hit_tokens", 0))
        STATS["out"] += u.get("completion_tokens", 0)
        if out:
            try:
                RECENT.appendleft({"t": time.strftime("%H:%M"), "new": g._plain(out), "old": g._plain(req["o"]),
                                   "parent": g._plain(req.get("p") or "")[:80], "body": bool(req.get("b"))})
            except Exception:  # noqa: BLE001
                pass
    post({"t": "res", "k": k, "v": out})
    ok = "OK " if out else "FAIL"
    # hit/miss/out = 캐시 적중 입력 / 미적중 입력 / 출력 토큰 (토큰 절약 확인용)
    log("%s %s %ss tok=%s hit=%s miss=%s out=%s err=%s ctx=%d body=%d | %s -> %s" % (
        ok, tag, info.get("sec"), u.get("total_tokens"), u.get("prompt_cache_hit_tokens"),
        u.get("prompt_cache_miss_tokens"), u.get("completion_tokens"), info.get("error"),
        len(req.get("ctx") or []), len(req.get("b") or ""),
        g._plain(req["o"])[:40], (g._plain(out)[:60] if out else "")))


def main(stop_event=None, link=None):
    """stop_event(threading.Event)가 있으면 실행기가 멈출 수 있다. 없으면 stop.flag 파일로 멈춘다.
    link(ModContext)가 있으면 요청·결과를 메시지로 주고받는다 (없으면 requests.jsonl / cache.json 파일)."""
    global calls, LINK
    LINK = link
    if not link and os.path.exists(STOP):
        os.remove(STOP)
    calls = 0
    STATS.update(ok=0, fail=0, hit=0, miss=0, out=0, since=time.time())
    load_cache()
    g.export_default_prompt()
    log("bridge start, cache=%d, max_calls=%d" % (len(cache), max_calls()))
    for w in cfg.warnings():
        log("config 경고: " + w)
    pos = 0
    workers = cfg.get("api.concurrency")
    pool = cf.ThreadPoolExecutor(max_workers=workers)
    log("동시 요청 %d개, 같은 글 묶기 %s" % (workers, "켜짐" if cfg.get("tokens.batch_thread") else "꺼짐"))
    groups = {}                               # 부모 글 -> {"reqs": [...], "t0": 처음 받은 시각, "last": 마지막으로 받은 시각}
    buf = b""

    def handle(req):
        """요청 하나: 이미 있으면(캐시/처리 중) 건너뛰고, 아니면 같은 글끼리 모으거나 바로 만든다."""
        k = req.get("k")
        with lock:
            if k and k in cache:
                known = True
            elif not k or k in inflight:
                return
            else:
                known = False
                inflight.add(k)
        if known:                             # 이미 만든 문장: 게임이 요청을 다시 보냈으면 결과만 다시 알려 준다
            post({"t": "res", "k": k, "v": cache[k]})
            return
        if LINK:
            log_request(req)
        if cfg.get("tokens.batch_thread") and req.get("p"):
            # 묶는 기준: 스레드 객체 + 부모 글 (다른 스레드가 한 묶음에 섞이지 않게)
            gr = groups.setdefault((req.get("th"), req["p"]), {"reqs": [], "t0": time.time(), "last": 0})
            gr["reqs"].append(req)
            gr["last"] = time.time()
        else:
            pool.submit(work, req)

    last_cfg = None
    while not (stop_event and stop_event.is_set()) and (link or not os.path.exists(STOP)):
        if calls >= max_calls():
            log("max calls reached, stop")
            break
        enabled = cfg.get("enabled")
        if LINK:
            c = cfg_msg()
            if c != last_cfg:                 # 설정이 바뀌면 게임 쪽에 알린다 (꺼져 있어도 알려야 다시 켤 수 있다)
                last_cfg = c
                post({"t": "cfg", "c": c})
            while True:
                m = LINK.recv(0)
                if m is None:
                    break
                if not isinstance(m, dict):
                    continue
                if m.get("t") == "hello":
                    send_snapshot()
                elif m.get("t") == "req" and enabled and isinstance(m.get("r"), dict):
                    handle(m["r"])
        if not enabled:                     # 꺼진 동안은 요청을 처리하지 않는다 (파일 방식은 켜면 그때부터 이어서 처리, 메시지 방식은 게임이 다시 보낸다)
            time.sleep(1.0 if not LINK else 0.3)
            continue
        if not LINK:
            try:
                with open(REQ, "rb") as f:
                    f.seek(pos)
                    chunk = f.read()
            except FileNotFoundError:
                chunk = b""
            if chunk:
                buf += chunk
                pos += len(chunk)
                *lines, buf = buf.split(b"\n")
                for ln in lines:
                    if not ln.strip():
                        continue
                    try:
                        req = json.loads(ln.decode("utf-8"))
                    except ValueError:
                        continue
                    handle(req)
        # 모은 묶음 내보내기: 처음 받은 뒤 batch_wait_ms가 지났고 잠깐 새 요청이 없거나, 최대 개수가 찼을 때
        wait = cfg.get("tokens.batch_wait_ms") / 1000.0
        bmax = cfg.get("tokens.batch_max")
        now = time.time()
        for p in list(groups):
            gr = groups[p]
            if len(gr["reqs"]) >= bmax or (now - gr["t0"] >= wait and now - gr["last"] >= min(0.3, wait)):
                del groups[p]
                rs = gr["reqs"]
                for i in range(0, len(rs), bmax):
                    chunk_reqs = rs[i:i + bmax]
                    if len(chunk_reqs) == 1:
                        pool.submit(work, chunk_reqs[0])
                    else:
                        pool.submit(work_batch, chunk_reqs)
        time.sleep(0.2)
    for gr in groups.values():               # 멈출 때 남은 요청은 다음 실행에서 다시 들어오도록 inflight만 푼다
        for r in gr["reqs"]:
            inflight.discard(r["k"])
    pool.shutdown(wait=True)
    log("bridge end, calls=%d" % calls)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        MAX_CALLS_ARG = int(sys.argv[1])
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted")
