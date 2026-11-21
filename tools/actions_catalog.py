"""게임 액션(명령) 등록부 만들기 (M62, 작성: Claude)

FM24의 사용자 명령은 ACTION_BASE를 물려받은 클래스 198개다 (관심 목록에 넣기, 이적 제의, 휴가 …).
클래스마다 vtable이 3칸이다:
  [0] 정리, [1] 4글자 액션 id를 돌려주는 함수(mov eax, imm32; ret), [2] 대상·문맥을 받아 확인하는 함수
      (this, 출력, 대상 목록, 사람 감독, 문맥 묶음 {Pers, Ttea, Hhum, SidT, islc, objt …}) — 화면이 열릴 때 그 대상에 대해 불린다 (M62 실기).
이 도구는 fm.exe 파일만 읽어(실행하지 않음) core/actions.json과 docs/ACTIONS.md를 만든다.

사용법:
  python -X utf8 tools/actions_catalog.py [fm.exe] [--pylib <capstone 폴더>]
  --pylib가 있으면 [2] 함수가 읽는 4글자 문맥 키도 뽑는다 (capstone 필요).
"""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "loader"))
import funcmap  # noqa: E402
import rtti  # noqa: E402

REG = os.path.join(ROOT, "core", "actions.json")
DOC = os.path.join(ROOT, "docs", "ACTIONS.md")
OK = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ")

# 이름 앞부분 -> 묶음 (문서용)
GROUPS = [("ADD_", "목록에 넣기"), ("REMOVE_", "목록에서 빼기"), ("MOVE_", "옮기기"), ("OFFER_", "제의"), ("MAKE_", "정하기·제의"),
          ("ASK_", "요청·문의"), ("CHANGE_", "바꾸기"), ("CANCEL_", "취소"), ("COMPARE_", "비교"), ("CREATE_", "만들기"),
          ("SET_", "설정"), ("TRANSFER", "이적"), ("LOAN", "임대"), ("CONTRACT", "계약"), ("TRAINING", "훈련"), ("", "기타")]


def group_of(name):
    for p, g in GROUPS:
        if p and (name.startswith(p) or (not p.endswith("_") and p in name)):
            return g
    return "기타"


def build(exe, pylib=None):
    pe, data = rtti.PE(exe), rtti.load(exe)
    code = funcmap._code_ranges(pe)
    text = code[0]
    md = None
    if pylib:
        sys.path.insert(0, pylib)
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
    acts = {}
    for name, c in sorted(data["classes"].items()):
        if "ACTION_BASE" not in (c.get("bases") or []) or not c["vtables"]:
            continue
        vt = int(c["vtables"][0]["rva"], 16)
        s = funcmap._slots(pe, vt, code)
        if len(s) < 3:
            continue
        o = pe.off(s[1] - pe.image_base)
        b = pe.m[o:o + 6]
        if b[0] != 0xB8 or b[5] != 0xC3:   # mov eax, imm32; ret
            continue
        aid = b[1:5][::-1].decode("latin-1")
        chk = s[2] - pe.image_base
        o2 = pe.off(chk)
        tgt = chk
        if pe.m[o2] == 0xE9:   # jmp rel32 (보호 구역으로 가는 썽크)
            tgt = chk + 5 + struct.unpack_from("<i", pe.m, o2 + 1)[0]
        prot = not (text[0] <= tgt + pe.image_base < text[1])
        e = {"class": name, "group": group_of(name), "protected": prot}
        if md and not prot:
            e["keys"] = _keys(pe, md, chk)
        acts[aid] = e
    return {"$comment": "게임 액션(명령) 등록부 (M62). tools/actions_catalog.py가 fm.exe에서 만든다. 열쇠 = 4글자 액션 id. "
                        "class = RTTI 클래스(빌드가 바뀌어도 같음), protected = 확인 함수가 Denuvo 보호 구역(정적 분석 불가), "
                        "keys = 확인 함수가 읽는 문맥 묶음 키 후보. 실행 API는 아직 없음 (세이브를 바꾸는 명령이라 사용자 확인 뒤).",
            "source": {"build": "FM24 Epic 24.4.2 (fm.exe 2026-10-24)", "count": len(acts)},
            "context_keys": {"Pers": "대상 사람 {dref}", "Ttea": "팀 {dref}", "Hhum": "명령하는 사람 감독 {dref}", "SidT": "감독의 팀 {dref}",
                             "islc": "지역(이 PC) 감독인가", "objt": "화면의 대상 객체 {dref}"},
            "actions": dict(sorted(acts.items(), key=lambda kv: kv[1]["class"]))}


def _keys(pe, md, rva):
    from capstone.x86 import X86_OP_IMM
    f = pe.func_of(rva)
    if not f:
        return []
    o = pe.off(f[0])
    ks = []
    for i in md.disasm(pe.m[o:o + min(f[1] - f[0], 0x8000)], pe.image_base + f[0]):
        if i.mnemonic in ("cmp", "mov") and len(i.operands) == 2 and i.operands[1].type == X86_OP_IMM:
            v = i.operands[1].imm & 0xFFFFFFFF
            bb = v.to_bytes(4, "big")
            if v >= 0x41000000 and all(c in OK for c in bb) and chr(bb[0]).isalpha() and bb.decode() not in ks:
                ks.append(bb.decode())
    return ks


def docs(reg):
    A = reg["actions"]
    L = ["# 게임 액션(명령) 목록", "",
         "> `python -X utf8 tools/actions_catalog.py`가 `core/actions.json`에서 만들어요. 직접 고치지 마세요.", "",
         "FM24에서 사용자가 하는 명령(관심 목록에 넣기, 이적 제의, 계약 제의, 휴가 …)은 게임 안에서 **액션 객체 %d개**예요. "
         "M24GA는 그 목록을 등록부로 만들어 뒀어요. **모드가 액션을 실행하는 API는 아직 없어요** (세이브를 바꾸는 명령이라 안전 장치를 먼저 만들어야 해요)." % len(A), "",
         "- 액션 id = 4글자 (예: `PGoH` 휴가, `AtSo` 관심 목록에 넣기, `offr` 이적 제의).",
         "- 화면이 열릴 때 게임은 액션마다 '이 대상에 대해' 확인 함수를 불러요. 넘기는 문맥 묶음: " +
         ", ".join("`%s` %s" % kv for kv in reg["context_keys"].items()) + ".",
         "- `protected` = 확인 함수가 Denuvo 보호 구역이라 정적으로 못 읽은 것. `keys` = 확인 함수가 읽는 키 후보.",
         "- CLI: `cli.py actions [정규식]` (게임 없이 됨).", ""]
    by = {}
    for aid, e in A.items():
        by.setdefault(e["group"], []).append((aid, e))
    for g in sorted(by, key=lambda x: (x == "기타", x)):
        L += ["## %s (%d)" % (g, len(by[g])), "", "| id | 클래스 | 보호 | 문맥 키 |", "|---|---|---|---|"]
        for aid, e in sorted(by[g], key=lambda x: x[1]["class"]):
            L.append("| `%s` | `%s` | %s | %s |" % (aid.replace("|", "\\|"), e["class"], "예" if e["protected"] else "", " ".join("`%s`" % k for k in e.get("keys", [])[:10])))
        L.append("")
    return "\n".join(L) + "\n"


def main(argv):
    pylib = argv[argv.index("--pylib") + 1] if "--pylib" in argv else None
    args = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or argv[i - 1] != "--pylib")]
    exe = args[0] if args else rtti.DEFAULT_EXE
    reg = build(exe, pylib)
    with open(REG, "w", encoding="utf-8") as f:
        head = {k: v for k, v in reg.items() if k != "actions"}
        txt = json.dumps(head, ensure_ascii=False, indent=1)[:-2]
        rows = ['  %s: %s' % (json.dumps(k), json.dumps(v, ensure_ascii=False, separators=(",", ":"))) for k, v in reg["actions"].items()]
        f.write(txt + ',\n "actions": {\n' + ",\n".join(rows) + "\n }\n}\n")
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(docs(reg))
    print("액션 %d개 -> %s, %s" % (len(reg["actions"]), REG, DOC))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
