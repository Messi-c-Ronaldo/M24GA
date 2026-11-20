"""fm.exe 정적 디스어셈블 도구 (작성: Claude)

사용법:
  python -X utf8 -I fmdis.py <pylib폴더> <fm.exe경로> <RVA> [<RVA> ...]

- RVA가 속한 함수를 PE 예외 테이블(.pdata)에서 찾아 함수 전체를 디스어셈블한다.
- call 대상은 함수 시작 RVA로 표시하고, RIP 상대 참조가 문자열을 가리키면 미리보기를 붙인다.
"""
import sys, struct, bisect

sys.path.insert(0, sys.argv[1])
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_RIP

pe = pefile.PE(sys.argv[2], fast_load=True)
pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXCEPTION"]])
data = pe.__data__
base = pe.OPTIONAL_HEADER.ImageBase

# .pdata: 함수 시작/끝 목록
exc = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
off = pe.get_offset_from_rva(exc.VirtualAddress)
funcs = []
for i in range(exc.Size // 12):
    s, e, _ = struct.unpack_from("<III", data, off + i * 12)
    funcs.append((s, e))
funcs.sort()
starts = [f[0] for f in funcs]


def func_of(rva):
    i = bisect.bisect_right(starts, rva) - 1
    if i >= 0 and funcs[i][0] <= rva < funcs[i][1]:
        return funcs[i]
    return None


def read_rva(rva, n):
    try:
        o = pe.get_offset_from_rva(rva)
    except Exception:
        return None
    return data[o:o + n]


def preview(rva):
    b = read_rva(rva, 160)
    if not b:
        return None
    end = b.find(b"\0")
    if end < 4:
        return None
    s = b[:end]
    try:
        t = s.decode("utf-8")
    except UnicodeDecodeError:
        return None
    printable = sum(1 for ch in t if ch.isprintable())
    return t if printable >= len(t) * 0.9 else None


def section_of(rva):
    for s in pe.sections:
        if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.Name.rstrip(b"\0").decode(errors="replace")
    return "?"


md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = True

for arg in sys.argv[3:]:
    rva = int(arg, 16)
    f = func_of(rva)
    if not f:
        print(f"## 0x{rva:x}: 함수 경계 없음")
        continue
    s, e = f
    code = read_rva(s, e - s)
    print(f"## func 0x{s:x}-0x{e:x} ({e - s} bytes, {section_of(s)})")
    calls = []
    for ins in md.disasm(code, base + s):
        r = ins.address - base
        note = ""
        if ins.mnemonic == "call" or ins.mnemonic.startswith("j"):
            for op in ins.operands:
                if op.type == X86_OP_IMM:
                    t = op.imm - base
                    tf = func_of(t)
                    if ins.mnemonic == "call":
                        note = f"  ; -> func 0x{tf[0]:x}" if tf else f"  ; -> 0x{t:x}"
                        calls.append(tf[0] if tf else t)
        for op in ins.operands:
            if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                t = ins.address + ins.size + op.mem.disp - base
                p = preview(t)
                note += f"  ; [0x{t:x} {section_of(t)}]" + (f' "{p[:70]}"' if p else "")
            elif op.type == X86_OP_IMM and ins.mnemonic == "mov" and op.size == 8 and op.imm > 0xFFFFFFFF:
                raw = struct.pack("<Q", op.imm & 0xFFFFFFFFFFFFFFFF)
                if all(32 <= c < 127 for c in raw):
                    note += f'  ; imm "{raw.decode()}"'
        print(f"  {r:08x}: {ins.mnemonic:6} {ins.op_str}{note}")
    print(f"  -- calls: {', '.join(f'0x{c:x}' for c in dict.fromkeys(calls))}\n")
