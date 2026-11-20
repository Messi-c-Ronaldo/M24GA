"""함수 등록부에 클래스 기반 주소(vf)를 채우고 확인한다 (M57, 작성: Claude)

사용법:
  python -X utf8 tools/func_vf.py fill [fm.exe]     가상 함수인 등록 함수에 vf {class, off, index}를 채운다 (core/functions.json)
  python -X utf8 tools/func_vf.py check [fm.exe]    서명 확인 + 클래스 기반 찾기 결과 (빌드 진단과 같은 계산)

vf = 이 함수가 처음 정의된 클래스(기반 클래스에 같은 칸이 없는 쪽)의 vtable(객체 안 off)의 index번째 칸.
게임이 빌드가 바뀌어 rva·서명이 안 맞을 때 로더가 이 길로 새 주소를 찾는다 (loader/funcmap.py).
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "loader"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import funcmap  # noqa: E402
import rtti  # noqa: E402

FUNCS = os.path.join(ROOT, "core", "functions.json")


def load():
    with open(FUNCS, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=collections.OrderedDict)


def fill(exe):
    reg = load()
    funcs = reg["functions"]
    pe, data = rtti.PE(exe), rtti.load(exe)
    # 서명 16바이트가 코드에서 한 곳이 아니면, 같은 자리에서 시작하는 더 긴 검색용 바이트(find)를 둔다 (빌드가 바뀌면 서명 검색에 씀)
    for name, f in funcs.items():
        sig = f.get("sig")
        if not sig:
            continue
        f.pop("find", None)
        if funcmap.count_hits(pe, bytes.fromhex(sig["hex"])) == 1:
            continue
        o = pe.off(int(f["rva"], 16) + int(sig["off"], 16))
        for n in (24, 32, 48, 64, 96):
            pat = pe.m[o:o + n]
            if funcmap.count_hits(pe, pat) == 1:
                funcs[name] = collections.OrderedDict((k, v) for k, v in list(f.items()) + [("find", {"off": sig["off"], "hex": pat.hex()})])
                print("  %-24s 검색용 바이트 %d" % (name, n))
                break
        else:
            print("  %-24s 96바이트로도 한 곳이 아님" % name)
    want = {pe.image_base + int(f["rva"], 16): n for n, f in funcs.items()}
    idx = funcmap.vf_index(pe, data, set(want))
    n = 0
    for va, name in want.items():
        cands = idx.get(va)
        f = funcs[name]
        if not cands:
            f.pop("vf", None)
            continue
        vf = funcmap.owner(cands, data)
        if funcmap.resolve_vf(pe, data, vf) != va - pe.image_base:   # 거꾸로 찾아 같은 주소인지
            print("  %s: 클래스 기반 주소가 달라 건너뜀 (%s)" % (name, vf))
            continue
        new = collections.OrderedDict()
        for k, v in f.items():   # vf는 sig 바로 뒤에
            new[k] = v
            if k == "sig":
                new["vf"] = vf
        if "vf" not in new:
            new["vf"] = vf
        funcs[name] = new
        n += 1
        print("  %-24s %s +0x%x [%d] (후보 %d)" % (name, vf["class"], vf["off"], vf["index"], len(cands)))
    with open(FUNCS, "w", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False, indent=2) + "\n")
    print("가상 함수 %d개 / 등록 함수 %d개 -> %s" % (n, len(funcs), FUNCS))


def check(exe):
    funcs = load()["functions"]
    res = funcmap.check(funcs, exe)
    for n, r in res.items():
        print("  %-24s %-4s %s %s" % (n, r["via"] or "-", r["rva"] or "", r.get("error", "")))
    print("\n".join(funcmap.summary(funcs, exe, True)))


def main(argv):
    if not argv or argv[0] not in ("fill", "check"):
        print(__doc__)
        return 2
    exe = argv[1] if len(argv) > 1 else rtti.DEFAULT_EXE
    (fill if argv[0] == "fill" else check)(exe)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
