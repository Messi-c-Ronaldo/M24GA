# -*- coding: utf-8 -*-
"""fm.exe의 MSVC RTTI(클래스 이름 정보)를 읽어 vtable ↔ 클래스 이름 ↔ 상속 표를 만든다. GPL-3.0-or-later.

게임 파일은 읽기만 한다. 결과는 게임에서 뽑은 데이터라 저장소가 아니라 ~/m24ga_data/rtti/ 에 캐시한다.
패키지 설치 없이 표준 라이브러리만 쓴다.

사용:
  python -X utf8 tools/rtti.py build [fm.exe 경로]      표 만들기 (캐시, 30초 안팎)
  python -X utf8 tools/rtti.py find <정규식> [--json]    클래스 이름 찾기 (vtable RVA, 기반 클래스)
  python -X utf8 tools/rtti.py vt <RVA> [--json]         vtable RVA(예: 0x5a4e958)의 클래스
  python -X utf8 tools/rtti.py stats                     요약

x64 MSVC RTTI 구조 (모두 RVA):
  vtable[-1] -> CompleteObjectLocator { u32 signature(=1), u32 offset(이 vtable의 객체 안 위치), u32 cdOffset,
                                        u32 pTypeDescriptor, u32 pClassHierarchyDescriptor, u32 pSelf(=자기 RVA) }
  TypeDescriptor { void* vftable, void* spare, char name[] (".?AVname@ns@@") }
  ClassHierarchyDescriptor { u32 sig, u32 attributes, u32 numBaseClasses, u32 pBaseClassArray }
  BaseClassArray[i] -> BaseClassDescriptor { u32 pTypeDescriptor, u32 numContainedBases, i32 mdisp, i32 pdisp, i32 vdisp, u32 attr, u32 pCHD }
"""
import json
import mmap
import os
import re
import struct
import sys
import time

DEFAULT_EXE = r"C:\Program Files\Epic Games\FootballManager24\fm.exe"
CACHE_DIR = os.path.join(os.path.expanduser("~"), "m24ga_data", "rtti")


def demangle(raw):
    """'.?AVACTUAL_PLAYER@db@@' -> 'db::ACTUAL_PLAYER'. 템플릿(?$)처럼 단순하지 않은 이름은 앞뒤만 떼고 그대로."""
    s = raw
    for p in (".?AV", ".?AU"):
        if s.startswith(p):
            s = s[len(p):]
            break
    if s.endswith("@@"):
        s = s[:-2]
    if "?" in s or "$" in s:
        return s
    return "::".join(reversed(s.split("@")))


class PE:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.m = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        m = self.m
        pe = struct.unpack_from("<I", m, 0x3C)[0]
        if m[pe:pe + 4] != b"PE\0\0":
            raise ValueError("PE 파일이 아니에요")
        nsec = struct.unpack_from("<H", m, pe + 6)[0]
        opt_size = struct.unpack_from("<H", m, pe + 20)[0]
        opt = pe + 24
        if struct.unpack_from("<H", m, opt)[0] != 0x20B:
            raise ValueError("64비트(PE32+)가 아니에요")
        self.image_base = struct.unpack_from("<Q", m, opt + 24)[0]
        self.sections = []
        sh = opt + opt_size
        for i in range(nsec):
            o = sh + i * 40
            name = m[o:o + 8].rstrip(b"\0").decode("latin-1")
            vsize, va, rsize, raw = struct.unpack_from("<IIII", m, o + 8)
            self.sections.append((name, va, max(vsize, rsize), raw, rsize))

    def off(self, rva):
        for _n, va, vs, raw, rs in self.sections:
            if va <= rva < va + vs:
                d = rva - va
                return raw + d if d < rs else None
        return None

    def u32(self, rva):
        o = self.off(rva)
        return None if o is None else struct.unpack_from("<I", self.m, o)[0]

    def cstr(self, rva, n=512):
        o = self.off(rva)
        if o is None:
            return None
        e = self.m.find(b"\0", o, o + n)
        return self.m[o:e].decode("latin-1") if e > o else None

    def func_of(self, rva):
        """rva가 든 함수의 (시작 RVA, 끝 RVA) — PE 예외 테이블(.pdata, 데이터 디렉터리 3)의 RUNTIME_FUNCTION. 없으면 None."""
        if not hasattr(self, "_pdata"):
            m = self.m
            pe = struct.unpack_from("<I", m, 0x3C)[0]
            rva_p, size = struct.unpack_from("<II", m, pe + 24 + 112 + 3 * 8)
            o = self.off(rva_p)
            self._pdata = [] if o is None else [x[:2] for x in struct.iter_unpack("<III", m[o:o + size - size % 12])]
        lo, hi = 0, len(self._pdata) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            b, e = self._pdata[mid]
            if rva < b:
                hi = mid - 1
            elif rva >= e:
                lo = mid + 1
            else:
                return b, e
        return None

    def data_sections(self):
        # Denuvo 빌드는 섹션 이름이 뒤섞여 있다 (진짜 .rdata는 '.idata'라는 이름, '.rdata'는 0x200바이트 가짜).
        # 그래서 이름 대신 크기로 고른다: 200MB 넘는 구역(Denuvo 가상 머신 '.arch')만 뺀다.
        return [s for s in self.sections if s[4] < 200 * 1024 * 1024]


def build(exe):
    t0 = time.time()
    pe = PE(exe)
    m = pe.m
    # 1) CompleteObjectLocator 찾기: signature 1, pSelf == 자기 RVA, TypeDescriptor 이름이 .?AV/.?AU
    cols = {}
    for name, va, vs, raw, rs in pe.data_sections():
        buf = m[raw:raw + rs]
        for mt in re.finditer(rb"\x01\x00\x00\x00", buf):
            o = mt.start()
            if o & 3 or o + 24 > rs:
                continue
            sig, offset, cdoff, ptd, pchd, pself = struct.unpack_from("<IIIIII", buf, o)
            if pself != va + o:
                continue
            nm = pe.cstr(ptd + 16)
            if not nm or not (nm.startswith(".?AV") or nm.startswith(".?AU")):
                continue
            cols[va + o] = (offset, ptd, pchd, nm)
    # 2) vtable: 데이터 구역에서 COL의 절대 주소를 담은 8바이트 칸 -> 그 다음 칸이 vtable 시작
    want = {pe.image_base + r: r for r in cols}
    vtables = {}
    for name, va, vs, raw, rs in pe.data_sections():
        for i, (q,) in enumerate(struct.iter_unpack("<Q", m[raw:raw + (rs & ~7)])):
            r = want.get(q)
            if r is not None:
                vtables[va + i * 8 + 8] = r
    # 3) 클래스별 기반 클래스 (ClassHierarchyDescriptor)
    classes = {}
    for colr, (offset, ptd, pchd, raw_name) in cols.items():
        cname = demangle(raw_name)
        c = classes.setdefault(cname, {"raw": raw_name, "vtables": [], "bases": None})
        if c["bases"] is None:
            n, arr = pe.u32(pchd + 8), pe.u32(pchd + 12)
            bases = []
            if n and arr and n < 256:
                for k in range(1, n):   # 0번은 자기 자신
                    bcd = pe.u32(arr + 4 * k)
                    btd = bcd and pe.u32(bcd)
                    bn = btd and pe.cstr(btd + 16)
                    if bn:
                        bases.append(demangle(bn))
            c["bases"] = bases
    for vt, colr in vtables.items():
        offset, ptd, pchd, raw_name = cols[colr]
        classes[demangle(raw_name)]["vtables"].append({"rva": "0x%x" % vt, "off": offset})
    by_vt = {"0x%x" % vt: {"name": demangle(cols[c][3]), "off": cols[c][0]} for vt, c in vtables.items()}
    out = {"exe": exe, "exe_size": os.path.getsize(exe), "image_base": "0x%x" % pe.image_base,
           "made": time.strftime("%Y-%m-%d %H:%M:%S"), "cols": len(cols), "vtables": by_vt, "classes": classes}
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = cache_path(out["exe_size"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    return out, path, time.time() - t0


def cache_path(size):
    return os.path.join(CACHE_DIR, "fm-%d.json" % size)


def load(exe=DEFAULT_EXE):
    p = cache_path(os.path.getsize(exe))
    if not os.path.exists(p):
        out, p, _ = build(exe)
        return out
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "build":
        exe = argv[1] if len(argv) > 1 else DEFAULT_EXE
        out, path, dt = build(exe)
        print("클래스 %d개, vtable %d개, COL %d개 (%.1f초) -> %s" % (len(out["classes"]), len(out["vtables"]), out["cols"], dt, path))
        return 0
    data = load()
    if cmd == "stats":
        cl = data["classes"]
        ns = {}
        for n in cl:
            k = n.split("::")[0] if "::" in n else "(전역)"
            ns[k] = ns.get(k, 0) + 1
        print("클래스 %d개, vtable %d개, 만든 때 %s" % (len(cl), len(data["vtables"]), data["made"]))
        print("이름공간 상위: " + ", ".join("%s %d" % kv for kv in sorted(ns.items(), key=lambda kv: -kv[1])[:20]))
        return 0
    if cmd == "find" and len(argv) > 1:
        rx = re.compile(argv[1], re.I)
        hits = {n: c for n, c in data["classes"].items() if rx.search(n)}
        if as_json:
            print(json.dumps(hits, ensure_ascii=False, indent=1))
        else:
            for n in sorted(hits):
                c = hits[n]
                print("%s  vt=%s  bases=%s" % (n, ",".join(v["rva"] + ("" if not v["off"] else "@+0x%x" % v["off"]) for v in c["vtables"]) or "-",
                                             " > ".join(c["bases"] or []) or "-"))
            print("(%d개)" % len(hits))
        return 0
    if cmd == "vt" and len(argv) > 1:
        key = "0x%x" % int(argv[1], 16)
        v = data["vtables"].get(key)
        if v:
            v = dict(v, bases=data["classes"][v["name"]]["bases"])
        print(json.dumps(v, ensure_ascii=False) if as_json else (v and "%s (객체 +0x%x 위치의 vtable) 기반: %s" % (v["name"], v["off"], " > ".join(v["bases"]) or "-") or "없음"))
        return 0 if v else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
