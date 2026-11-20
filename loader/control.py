"""M24GA 조종 통로 (M18): 실행 중인 로더(앱 또는 `cli.py run`)를 다른 CLI 호출이 조종한다. GPL-3.0-or-later.

CLI는 한 번 실행하고 끝나는 별도 프로세스라서, 그대로는 켜져 있는 앱의 로더(게임 연결, 모드 Python, 로그)에 닿지 않는다.
로더 쪽이 127.0.0.1에만 작은 HTTP 통로를 열고 포트와 무작위 토큰을 ~/m24ga_data/control.json에 적는다.
CLI는 그 파일이 있고 통로가 답하면 명령을 그쪽에서 실행하고 결과 글을 받아 그대로 출력한다.
- 이 PC 안에서만 (127.0.0.1), 토큰이 맞아야 실행 (같은 사용자의 데이터 폴더를 읽을 수 있어야 함)
- 통로가 실행하는 것은 cli.py의 명령뿐이다 (임의 코드 실행 없음)
"""
import json
import os
import secrets
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import mods as modlib

_srv = {"server": None}


def path():
    return os.path.join(modlib.DATA, "control.json")


def serve(dispatch):
    """통로를 연다. dispatch(argv) -> (종료 코드, 출력 글). 반환: 서버 (이미 열려 있으면 그것)."""
    if _srv["server"]:
        return _srv["server"]
    token = secrets.token_hex(16)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):   # 요청마다 콘솔에 찍지 않는다
            pass

        def do_POST(self):
            if self.headers.get("X-M24GA-Token") != token:
                self.send_response(403)
                self.end_headers()
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(n) or b"{}")
                argv = [str(a) for a in req.get("argv") or []]
                code, text = dispatch(argv)
            except Exception as e:  # noqa: BLE001
                code, text = 1, "오류: 통로에서 명령 실행 실패: %r\n" % e
            body = json.dumps({"code": code, "out": text}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _srv["server"] = server
    os.makedirs(modlib.DATA, exist_ok=True)
    with open(path(), "w", encoding="utf-8") as f:
        json.dump({"port": server.server_address[1], "token": token, "pid": os.getpid()}, f)
    return server


def stop():
    """통로를 닫고, 내가 쓴 control.json이면 지운다."""
    server = _srv["server"]
    _srv["server"] = None
    if server:
        server.shutdown()
        server.server_close()
    try:
        with open(path(), encoding="utf-8") as f:
            info = json.load(f)
        if info.get("pid") == os.getpid():
            os.remove(path())
    except (OSError, ValueError):
        pass


def call(argv, timeout=None):
    """실행 중인 로더의 통로에서 명령을 실행한다. 반환 (종료 코드, 출력 글), 통로가 없거나 답이 없으면 None."""
    try:
        with open(path(), encoding="utf-8") as f:
            info = json.load(f)
        if info.get("pid") == os.getpid():   # 나 자신이 통로를 연 프로세스 (cli run 안에서 부름)
            return None
        req = urllib.request.Request("http://127.0.0.1:%d/" % int(info["port"]),
                                     data=json.dumps({"argv": list(argv)}).encode("utf-8"),
                                     headers={"X-M24GA-Token": info["token"], "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        return int(d["code"]), d["out"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
