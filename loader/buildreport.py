"""M24GA 빌드 진단 보고서 (M48): 로더가 모르는 게임 빌드(예: Steam판)를 만났을 때, 어디가 다른지 알려 주는 글을 만든다. GPL-3.0-or-later.

사용자가 이 글을 이슈나 채팅에 붙여 넣으면 개발자가 그 빌드를 지원할 수 있다.
- 개인 경로는 지운다 (사용자 폴더 -> ~).
- 게임 파일 내용은 넣지 않는다: 크기, SHA-256, 빌드 시각, 버전 글자, 서명 칸의 16바이트만.
"""
import datetime
import hashlib
import mmap
import os
import re
import struct
import sys

_VER_RX = re.compile(rb"\d{2}\.\d{1,2}\.\d{1,2}\+\d{5,9}")
_STORE_FILES = ("epic.txt", "steam_api64.dll", "EOSSDK-Win64-Shipping.dll", "steam_appid.txt")


def _clean(text, extra=()):
    """개인 경로를 지운다."""
    home = os.path.expanduser("~")
    for h in (home, home.replace("\\", "/")) + tuple(extra):
        if h and len(h) > 3:
            text = text.replace(h, "~")
    return text


def file_facts(exe):
    """게임 파일에서 읽을 수 있는 사실 (크기, SHA-256, PE 빌드 시각, 버전 글자, 같은 폴더의 스토어 관련 파일)."""
    f = {}
    try:
        f["size"] = os.path.getsize(exe)
        with open(exe, "rb") as fh:
            head = fh.read(4096)
            pe = struct.unpack_from("<I", head, 0x3C)[0]
            ts = struct.unpack_from("<I", head, pe + 8)[0]
            f["pe_time"] = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            h = hashlib.sha256()
            fh.seek(0)
            while True:
                b = fh.read(8 << 20)
                if not b:
                    break
                h.update(b)
            f["sha256"] = h.hexdigest()
            with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as m:
                f["versions"] = sorted({x.decode() for x in _VER_RX.findall(m)})[:5]
    except Exception as e:  # noqa: BLE001
        f["error"] = repr(e)
    d = os.path.dirname(exe)
    f["store_files"] = [n for n in _STORE_FILES if os.path.exists(os.path.join(d, n))]
    return f


def build_text(info, why, builds, core_version, mod_off=None, mod_rows=None, with_file=True, func_lines=None):
    """보고서 글. info = host.read_signature 결과, builds = 알려진 빌드 목록."""
    L = []
    L.append("# M24GA 빌드 진단 보고서")
    L.append("")
    L.append("- 로더 코어 %s, Python %s, 시각 %s" % (core_version, sys.version.split()[0], datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    try:
        import frida
        L.append("- frida %s" % frida.__version__)
    except Exception:  # noqa: BLE001
        pass
    L.append("- 결과: %s" % _clean(why or "?"))
    L.append("")
    exe = (info or {}).get("path")
    L.append("## 게임 파일")
    L.append("- 모듈 크기(메모리): %s" % (info or {}).get("size"))
    if exe and with_file:
        f = file_facts(exe)
        L.append("- 파일 크기: %s" % f.get("size"))
        L.append("- PE 빌드 시각: %s" % f.get("pe_time"))
        L.append("- 버전 글자: %s" % (", ".join(f.get("versions") or []) or "못 찾음"))
        L.append("- SHA-256: %s" % f.get("sha256"))
        L.append("- 게임 폴더의 스토어 관련 파일: %s" % (", ".join(f.get("store_files") or []) or "없음"))
        if f.get("error"):
            L.append("- (읽기 오류: %s)" % f["error"])
    else:
        L.append("- (게임 파일 경로를 못 읽음)")
    L.append("")
    L.append("## 알려진 빌드와 비교")
    for b in builds:
        L.append("### %s" % b.get("name"))
        if b.get("module_size"):
            ok = (info or {}).get("size") == b["module_size"]
            L.append("- 모듈 크기: 기대 %s / 실제 %s %s" % (b["module_size"], (info or {}).get("size"), "맞음" if ok else "다름"))
        rows = list((b.get("sig") or {}).items()) + list((b.get("hook_guard") or {}).items())
        bad = 0
        for o, v in rows:
            got = ((info or {}).get("sig") or {}).get(o)
            if got != v:
                bad += 1
                L.append("- 서명 %s 다름: 기대 %s / 실제 %s" % (o, v, got))
        for o, v in (b.get("vt") or {}).items():
            got = ((info or {}).get("vt") or {}).get(o)
            if got != v:
                bad += 1
                L.append("- vtable %s 다름: 기대 %s / 실제 %s" % (o, v, got))
        L.append("- 서명·vtable %d칸 중 다른 것 %d칸" % (len(rows) + len(b.get("vt") or {}), bad))
    L.append("")
    if func_lines:   # M57: 함수 등록부 서명 + 클래스 기반 찾기 (loader/funcmap.py)
        L.append("## 함수 등록부")
        for line in func_lines:
            L.append("- " + line)
        L.append("")
    if mod_off:
        L.append("## 이 빌드에서 꺼진 모드")
        for mid, w in sorted(mod_off.items()):
            L.append("- %s: %s" % (mid, _clean(w)))
        L.append("")
    if mod_rows:
        L.append("## 모드")
        for r in mod_rows:
            L.append("- %s %s (%s)" % (r.get("id"), r.get("version"), r.get("state")))
        L.append("")
    return _clean("\n".join(L), extra=(os.path.dirname(exe) if exe else "",)) + "\n"
