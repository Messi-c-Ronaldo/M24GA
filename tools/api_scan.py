"""속성 setter 정적 후보 뽑기 (M78, 작성: Claude) — 반자동 API 탐색 1~2단계

속성 객체 vtable의 +0x18(set_property)과 기반 클래스들의 set_property를 디스어셈블해서, 코드 비교
(`cmp reg, imm32` 바로 뒤 je/jne)에 나오는 4글자 코드를 모은다 (M71 단계 0의 방법).
등록부(core/properties.json)에 있고 값 종류가 스칼라(int/u32/num/bool/date)인 코드만 남기고,
이미 write 등록부·deny에 있는 코드는 뺀다. 결과는 `cli.py cand import <결과>`로 후보 저장소에 넣는다.

사용:  python -X utf8 tools/api_scan.py --pylib <capstone 폴더> [--exe fm.exe] [--out scan.json] [--kinds club,player]
  - thunk(`sub/add rcx; jmp`)는 따라가고, Denuvo 가상 머신으로 가는 setter(대륙 등)는 건너뛴다.
  - 게임 파일은 읽기만 한다. 결과에 게임 글은 없다(4글자 코드뿐).
"""
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCALAR = {"int", "u32", "num", "bool", "date"}


def _arg(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1]
    return default


def main(argv):
    pylib = _arg(argv, "--pylib")
    if pylib:
        sys.path.insert(0, pylib)
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    except ImportError:
        print(__doc__)
        print("capstone이 없어요: --pylib <capstone 폴더> (tools/README.md)")
        return 2
    sys.path.insert(0, HERE)
    import rtti
    exe = _arg(argv, "--exe", rtti.DEFAULT_EXE)
    out = _arg(argv, "--out", os.path.join(os.path.expanduser("~"), "m24ga_data", "api_scan.json"))
    only = set((_arg(argv, "--kinds") or "").split(",")) - {""}
    pe = rtti.PE(exe)
    B = pe.image_base
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    D = rtti.load(exe)
    with open(os.path.join(ROOT, "core", "properties.json"), encoding="utf-8") as f:
        P = json.load(f)
    have = set(P.get("write", {}).get("codes", {})) | set(P.get("write", {}).get("deny", []))

    def q(rva):
        o = pe.off(rva)
        return None if o is None else struct.unpack_from("<Q", pe.m, o)[0]

    def follow(fn, depth=0):
        """짧은 thunk(jmp/call 한 번)는 따라간다"""
        o = pe.off(fn)
        if o is None or depth > 3:
            return fn
        fr = pe.func_of(fn)
        if fr and fr[1] - fr[0] > 120:
            return fn
        for i in list(md.disasm(pe.m[o:o + 40], B + fn))[:8]:
            if i.mnemonic in ("jmp", "call") and i.op_str.startswith("0x"):
                t = int(i.op_str, 16) - B
                if pe.func_of(t):
                    return follow(t, depth + 1)
                return None   # 함수 표에 없는 곳(Denuvo VM 등) -> 건너뜀
        return fn

    def codes(fn):
        if fn is None:
            return set()
        fr = pe.func_of(fn)
        if not fr or fr[1] - fr[0] <= 120:
            return set()
        o = pe.off(fr[0])
        ins = list(md.disasm(pe.m[o:o + fr[1] - fr[0]], B + fr[0]))
        got = set()
        for a, b in zip(ins, ins[1:]):
            if a.mnemonic == "cmp" and b.mnemonic in ("je", "jne"):
                m = re.search(r", (0x[0-9a-f]+)$", a.op_str)
                if m:
                    v = int(m.group(1), 16)
                    if v <= 0xffffffff:
                        s = struct.pack(">I", v)
                        if all(32 < c < 127 for c in s):
                            got.add(s.decode("latin-1"))
        return got

    vt_of = {}
    for vr, v in D["vtables"].items():
        vt_of.setdefault(v["name"], []).append((int(vr, 16), v["off"]))

    def setter_of(cls, off=0):
        for vr, o in vt_of.get(cls, []):
            if o == off:
                v = q(vr + 0x18)
                return follow(v - B) if v else None
        return None

    res = {"exe": os.path.basename(exe), "setters": {}, "codes": {}, "counts": {}}
    for kind, k in P["kinds"].items():
        if only and kind not in only:
            continue
        cl = D["classes"].get(k["class"])
        if not cl:
            continue
        fns = []
        for f in [setter_of(k["class"], k["off"])] + [setter_of(b) for b in (cl.get("bases") or [])]:
            if f and f not in fns:
                fns.append(f)
        allc = set()
        for f in fns:
            allc |= codes(f)
        props = {c for c, e in P["props"].items() if kind in e["k"] and e["t"] in SCALAR}
        cand = sorted(c for c in allc & props if c not in have)
        res["setters"][kind] = ",".join("0x%x" % f for f in fns)
        res["codes"][kind] = cand
        res["counts"][kind] = {"setterCodes": len(allc), "scalarInRegistry": len(allc & props), "new": len(cand)}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for kind, c in res["counts"].items():
        print("%-9s setter 코드 %4d, 등록부 스칼라 %4d, 새 후보 %4d" % (kind, c["setterCodes"], c["scalarInRegistry"], c["new"]))
    print("-> %s  (다음: python -X utf8 loader/cli.py cand import %s)" % (out, out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
