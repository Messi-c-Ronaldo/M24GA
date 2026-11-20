"""M24GA: 코어 + 켜진 모드들의 게임 쪽 JS를 Frida 스크립트 하나로 묶는다. GPL-3.0-or-later.

Frida 스크립트끼리는 변수를 공유하지 못하므로, 코어 API를 모드에 넘기려면 한 스크립트여야 한다 (M24GA M01 로그 3-1).
모드 코드는 registerMod(id, function (api) { ... }) 안에 들어가서 모드끼리 변수가 섞이지 않는다.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mods as modlib  # noqa: E402
import panels  # noqa: E402  (게임 안 패널 칸, M44)

ROOT = modlib.ROOT
CORE_JS = os.path.join(ROOT, "core", "core.js")
MODHOST_JS = os.path.join(ROOT, "core", "modhost.js")   # 모드 등록·동적 적재 (게임 주소 없음, core.js 앞에 붙는다)
CORE_DATA = modlib.DATA
FIELDS_JSON = os.path.join(ROOT, "core", "fields.json")   # 필드 등록부 (M20)
FUNCS_JSON = os.path.join(ROOT, "core", "functions.json")   # 함수 등록부 (M22)
PROPS_JSON = os.path.join(ROOT, "core", "properties.json")   # 속성 등록부 (M55, 코어 0.36.0)


def props_compact(reg):
    """속성 등록부의 짧은 판: { kinds: {종류: [클래스, 칸]}, block: [코드], p: {코드: [값 종류, 종류 비트]} }"""
    kinds = list(reg["kinds"])
    p = {}
    for c, v in reg["props"].items():
        if v.get("stale"):
            continue
        bits = 0
        for k in v["k"]:
            bits |= 1 << kinds.index(k)
        p[c] = [v["t"], bits]
    return {"kinds": {k: [reg["kinds"][k]["class"], reg["kinds"][k]["off"]] for k in kinds}, "block": sorted(reg.get("block", {})), "p": p}


def _js_path(p):
    return json.dumps(p.replace("\\", "/").rstrip("/") + "/")


def _inject(src, var, value, what):
    line = "var %s = %s;   // 로더가 넣은 값" % (var, value)   # 함수로 바꿔 넣는다 (값에 역슬래시가 있어도 그대로)
    out, n = re.subn(r"^var %s = .*$" % var, lambda _m: line, src, count=1, flags=re.M)
    if n != 1:
        raise RuntimeError("%s에서 'var %s =' 줄을 찾지 못했다" % (what, var))
    return out


def game_settings(m):
    """게임 쪽 JS에 보여 줄 모드 설정 {key: 값}: 파일 값(없으면 default)에서 password 형식을 뺀 것."""
    vals = modlib.load_settings(m)
    for s in m.manifest.get("settings") or []:
        if s.get("type") == "password":
            vals.pop(s["key"], None)
    return vals


def mod_source(m, settings=True):
    """모드 하나의 JS를 registerMod 호출로 감싼 문자열 (묶음의 한 조각). 문법 사전 검사에도 쓴다.
    settings=False: 설정 값을 뺀 것 (host가 '모드 코드가 바뀌었나'를 볼 때. 설정은 rpc로 따로 알리므로 바뀌어도 다시 올리지 않는다, 몸값모드 V08)"""
    src = m.read_text(m.manifest.get("js", "mod.js"))
    modlib.ensure_data(m)
    if re.search(r"^var DIR = ", src, flags=re.M):
        src = _inject(src, "DIR", _js_path(m.data_dir), m.id + "/mod.js")
    else:   # 모드가 DIR 줄을 안 적었으면 앞에 넣어 준다 (모드 데이터 폴더, 끝에 / 가 붙음)
        src = "var DIR = %s;\n%s" % (_js_path(m.data_dir), src)
    # 설정 값 (api.settings()): 비밀번호 형식은 게임 프로세스로 보내지 않는다. 앱에서 바뀌면 host.save_settings가 rpc로 알린다 (M23)
    meta = {"caps": list(m.caps), "settings": game_settings(m) if settings else None}   # 코어가 쓰기 같은 API를 이 모드에 열지 정한다 (M14). 권한이 없는 모드는 아예 올라가지 않는다
    return "registerMod(%s, function (api) {\n%s\n}, %s);" % (json.dumps(m.id), src, json.dumps(meta))


def build(mods_to_load=None, exe=None):
    """mods_to_load: Mod 목록, 또는 모드 id 목록(문자열), None이면 켜진 모드 전부.
    반환: (스크립트 문자열, 올린 모드 id 목록)"""
    if mods_to_load is None or any(isinstance(x, str) for x in mods_to_load):
        found, _ = modlib.scan()
        if mods_to_load is None:
            mods_to_load = modlib.active(found)
        else:
            ids = set(mods_to_load)
            mods_to_load = [m for m in found if m.id in ids and not m.problems]
    os.makedirs(CORE_DATA, exist_ok=True)
    with open(MODHOST_JS, encoding="utf-8") as f:
        host = f.read()
    pdir = panels.slot_dir_if_ready()   # M44: 게임 안 패널 칸 폴더 (칸 파일이 다 있을 때만)
    host = _inject(host, "M24_PANEL_DIR", _js_path(pdir) if pdir else "null", "modhost.js")
    host = _inject(host, "M24_PANEL_SLOTS", str(panels.SLOTS), "modhost.js")
    parts = [host]
    with open(CORE_JS, encoding="utf-8") as f:
        core = _inject(f.read(), "M24GA_DIR", _js_path(CORE_DATA), "core.js")
    with open(FIELDS_JSON, encoding="utf-8") as f:   # 필드 등록부 (M20): 한 줄 JSON으로 넣는다
        core = _inject(core, "M24_FIELDS", json.dumps(json.load(f), ensure_ascii=False, separators=(",", ":")), "core.js")
    with open(FUNCS_JSON, encoding="utf-8") as f:   # 함수 등록부 (M22)
        funcs = json.load(f)
    if exe:   # M57: 서명이 안 맞는 함수는 클래스 vtable 칸(vf)이나 서명 검색으로 다시 찾아 rva를 바꿔 넣는다 (코어는 서명을 다시 확인)
        import funcmap
        for name, rva in funcmap.relocated(funcs["functions"], exe).items():
            funcs["functions"][name] = dict(funcs["functions"][name], rva=rva, moved=True)
    core = _inject(core, "M24_FUNCS", json.dumps(funcs, ensure_ascii=False, separators=(",", ":")), "core.js")
    with open(PROPS_JSON, encoding="utf-8") as f:   # 속성 등록부 (M55): 짧은 판만
        core = _inject(core, "M24_PROPS", json.dumps(props_compact(json.load(f)), ensure_ascii=False, separators=(",", ":")), "core.js")
    parts.append(core)
    loaded = []
    for m in mods_to_load:
        parts.append(mod_source(m))
        loaded.append(m.id)
    parts.append("send('m24ga ready: ' + JSON.stringify(M24GA.mods));")
    return "\n".join(parts), loaded


if __name__ == "__main__":   # python loader/bundle.py out.js  -> 묶은 스크립트를 파일로 (검사용)
    src, ids = build()
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(CORE_DATA, "bundle.js")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print("bundle:", path, "mods:", ids, "lines:", src.count("\n") + 1)
