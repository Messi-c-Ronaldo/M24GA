"""함수 등록부 주소 확인과 클래스 기반 찾기 (M57, 코어 0.38.0, 작성: Claude)

core/functions.json의 함수는 고정 rva + 16바이트 서명으로 찾는다. 게임 빌드가 바뀌어 서명이 안 맞으면,
가상 함수는 `vf: {class, off, index}`(클래스의 vtable 몇 번째 칸)로 다시 찾을 수 있다.
클래스 이름은 RTTI에서 오므로 빌드가 바뀌어도 그대로이고, vtable 칸 순서도 같은 소스면 그대로다.

- check(funcs, exe): 함수마다 {ok, rva, via('rva'|'vf'|None), error}. 서명이 다를 때만 RTTI 표(tools/rtti.py,
  ~/m24ga_data/rtti/ 캐시, 처음 30초)를 읽는다.
- vf_index(pe, data): 함수 VA -> [(클래스, vtable 안 칸 off, 번호)] (tools/func_vf.py가 vf를 채울 때).
게임 파일은 읽기만 한다.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
MAX_SLOTS = 1200


def _rtti():
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import rtti   # noqa: E402  (도구 폴더의 표준 라이브러리만 쓰는 RTTI 리더)
    return rtti


def _sig_ok(pe, rva, sig):
    if not sig:
        return True
    o = pe.off(rva + int(sig["off"], 16))
    if o is None:
        return False
    n = len(sig["hex"]) // 2
    return pe.m[o:o + n].hex() == sig["hex"].lower()


def _slots(pe, vt_rva, code):
    """vtable 칸들 (코드 구역을 가리키는 동안). code = [(시작 VA, 끝 VA)]"""
    out = []
    for i in range(MAX_SLOTS):
        o = pe.off(vt_rva + 8 * i)
        if o is None:
            break
        q = struct.unpack_from("<Q", pe.m, o)[0]
        if not any(a <= q < b for a, b in code):
            break
        out.append(q)
    return out


def _code_ranges(pe):
    # 실행 구역 = 섹션 특성의 실행 비트 (Denuvo 빌드는 이름이 뒤섞여서 이름으로 고르지 않는다)
    if getattr(pe, "_code", None) is None:
        m = pe.m
        h = struct.unpack_from("<I", m, 0x3C)[0]
        nsec, opt_size = struct.unpack_from("<H", m, h + 6)[0], struct.unpack_from("<H", m, h + 20)[0]
        sh, out = h + 24 + opt_size, []
        for i in range(nsec):
            vsize, va = struct.unpack_from("<II", m, sh + i * 40 + 8)
            ch = struct.unpack_from("<I", m, sh + i * 40 + 36)[0]
            if ch & 0x20000000:
                out.append((pe.image_base + va, pe.image_base + va + vsize))
        pe._code = out
    return pe._code


def vf_index(pe, data, want=None):
    """함수 VA -> [(클래스, off, 번호)]. want(VA 집합)를 주면 그것만 모은다."""
    code = _code_ranges(pe)
    idx = {}
    for vt, info in data["vtables"].items():
        for i, q in enumerate(_slots(pe, int(vt, 16), code)):
            if want is None or q in want:
                idx.setdefault(q, []).append((info["name"], info["off"], i))
    return idx


def owner(cands, data):
    """같은 함수가 상속으로 여러 클래스 vtable에 있으면, 기반 클래스에 같은 칸이 없는 클래스(처음 정의한 쪽)."""
    names = {c for c, _o, _i in cands}
    best = []
    for c, o, i in cands:
        bases = set((data["classes"].get(c) or {}).get("bases") or [])
        if not (bases & names):
            best.append((c, o, i))
    best = best or list(cands)
    best.sort(key=lambda x: (x[1], len(x[0]), x[0]))
    c, o, i = best[0]
    return {"class": c, "off": o, "index": i}


def resolve_vf(pe, data, vf):
    """vf {class, off, index} -> rva 또는 None"""
    cl = data["classes"].get(vf["class"])
    if not cl:
        return None
    code = _code_ranges(pe)
    for v in cl["vtables"]:
        if v["off"] != vf.get("off", 0):
            continue
        s = _slots(pe, int(v["rva"], 16), code)
        if vf["index"] < len(s):
            return s[vf["index"]] - pe.image_base
    return None


def check(funcs, exe, deep=True):
    """funcs = functions.json의 functions. 반환 {이름: {ok, rva, via, error}}. deep=False면 RTTI 표를 읽지 않는다."""
    pe = _rtti().PE(exe)
    res, data = {}, None
    for name, f in funcs.items():
        rva = int(f["rva"], 16)
        if _sig_ok(pe, rva, f.get("sig")):
            res[name] = {"ok": True, "rva": f["rva"], "via": "rva"}
            continue
        r = {"ok": False, "rva": None, "via": None, "error": "서명 다름"}
        if f.get("vf") and deep:
            if data is None:
                data = _rtti().load(exe)
            nr = resolve_vf(pe, data, f["vf"])
            if nr is None:
                r["error"] = "서명 다름, 클래스 %s를 이 빌드에서 못 찾음" % f["vf"]["class"]
            elif _sig_ok(pe, nr, f.get("sig")):
                r = {"ok": True, "rva": "0x%x" % nr, "via": "vf"}
            else:
                r["error"] = "서명 다름, 클래스 기반 주소 0x%x도 서명 다름" % nr
        elif f.get("vf"):
            r["error"] = "서명 다름 (클래스 기반 찾기 안 함)"
        res[name] = r
    return res


def relocated(funcs, exe):
    """bundle용: 서명이 다르지만 클래스 기반으로 찾은 함수의 새 rva {이름: '0x…'}. 실패해도 빈 dict."""
    try:
        res = check(funcs, exe)
    except Exception:   # noqa: BLE001  (파일을 못 읽어도 로더는 원래 rva로 돈다: 코어가 서명을 다시 확인한다)
        return {}
    return {n: r["rva"] for n, r in res.items() if r.get("via") == "vf"}


def summary(funcs, exe, deep):
    """빌드 진단 보고서용 한 줄들."""
    res = check(funcs, exe, deep)
    n = len(res)
    ok = sum(1 for r in res.values() if r["via"] == "rva")
    vf = sum(1 for r in res.values() if r["via"] == "vf")
    has_vf = sum(1 for f in funcs.values() if f.get("vf"))
    lines = ["함수 등록부: %d개 중 서명 맞음 %d개, 클래스 기반으로 찾음 %d개 (클래스 정보가 있는 함수 %d개)" % (n, ok, vf, has_vf)]
    bad = [k for k, r in res.items() if not r["ok"]]
    if bad:
        lines.append("못 찾은 함수: " + ", ".join(sorted(bad)[:30]) + (" …" if len(bad) > 30 else ""))
    return lines
