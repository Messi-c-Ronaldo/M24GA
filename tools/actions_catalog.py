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
    ui = _ui_map(pe, data, code)
    byc = {e["class"]: aid for aid, e in acts.items()}
    for ucls, u in ui.items():
        aid = byc.get(ucls[:-3]) or byc.get(ucls.replace("_ACTION_ACTION_UI", "_ACTION"))
        if aid:
            acts[aid]["ui"] = u
    return {"$comment": "게임 액션(명령) 등록부 (M62). tools/actions_catalog.py가 fm.exe에서 만든다. 열쇠 = 4글자 액션 id. "
                        "class = RTTI 클래스(빌드가 바뀌어도 같음), protected = 확인 함수가 Denuvo 보호 구역(정적 분석 불가), "
                        "keys = 확인 함수가 읽는 문맥 묶음 키 후보. ui = 실행 쪽 전역 객체 *_ACTION_UI {obj: fm 안 주소, events: 처리기가 받는 이벤트} (M65, 코어 0.41.0 api.action).",
            "source": {"build": "FM24 Epic 24.4.2 (fm.exe 2026-10-24)", "count": len(acts), "ui": sum(1 for e in acts.values() if "ui" in e)},
            "context_keys": {"Pers": "대상 사람 {dref}", "Ttea": "팀 {dref}", "Hhum": "명령하는 사람 감독 {dref}", "SidT": "감독의 팀 {dref}",
                             "islc": "지역(이 PC) 감독인가", "objt": "화면의 대상 객체 {dref}"},
            "actions": dict(sorted(acts.items(), key=lambda kv: kv[1]["class"]))}


def _ui_map(pe, data, code):
    """실행 쪽 (M65): 액션마다 화면 쪽 처리 객체 *_ACTION_UI가 fm.exe 안 전역 객체로 하나씩 있다.
    등록 함수들이 `lea rax, [vtable]; mov [rip+객체], rax`로 vtable을 넣는다 -> 바이트로 찾는다 (capstone 필요 없음).
    처리기 = vtable [2] (this, 이벤트 4글자, 묶음, ACTIONS_EVENT_HANDLER). 처음 `cmp edx, imm32`들이 받는 이벤트."""
    IB = pe.image_base
    vts = {}
    for name, c in data["classes"].items():
        if name.endswith("ACTION_UI") and c.get("vtables"):
            vts[int(c["vtables"][0]["rva"], 16)] = name
    out = {}
    for a, b in code:
        a -= IB
        b -= IB
        o0 = pe.off(a)
        if o0 is None:
            continue
        m = pe.m
        i = m.find(b"\x48\x8d\x05", o0, o0 + (b - a))
        while i != -1:
            rva = a + (i - o0)
            t = rva + 7 + struct.unpack_from("<i", m, i + 3)[0]
            if t in vts and m[i + 7:i + 10] == b"\x48\x89\x05":
                obj = rva + 14 + struct.unpack_from("<i", m, i + 10)[0]
                s = funcmap._slots(pe, t, code)
                evs, e = [], {"obj": hex(obj)}
                if len(s) > 2:
                    h = s[2] - IB
                    ho = pe.off(h)
                    if ho is not None:
                        blob = m[ho:ho + 0x80]
                        if blob[:3] in (b"\x31\xc0\xc3", b"\x33\xc0\xc3"):   # xor eax, eax; ret = 처리기가 비었다 (화면 이동 LINK, 사임 등은 다른 길로 실행)
                            e["noop"] = True
                        j = blob.find(b"\x81\xfa")   # cmp edx, imm32
                        while j != -1 and j + 6 <= len(blob):
                            v = struct.unpack_from("<I", blob, j + 2)[0].to_bytes(4, "big")
                            if all(0x20 < c < 0x7f for c in v) and v.decode() not in evs:
                                evs.append(v.decode())
                            j = blob.find(b"\x81\xfa", j + 6)
                e["events"] = evs
                if len(s) > 1:   # 메뉴 항목을 만드는 [1]: 항목 묶음에 'evid'(누르면 보낼 이벤트)를 넣는 곳 = mov edx, 값; ...; mov edx, 'evid'
                    ck = _click_events(pe, s[1] - IB)
                    if ck:
                        e["click"] = ck
                        rest = [x for x in evs if x not in ck]
                        if len(ck) == 1 and len(evs) == 2 and len(rest) == 1:
                            e["confirm"] = rest[0]   # 누름 = 확인 창, 남은 하나 = 확인 뒤 실행 (PmcP pmcE -> pmcC, M65 실기)
                out[vts[t]] = e
            i = m.find(b"\x48\x8d\x05", i + 3, o0 + (b - a))
    return out


def _click_events(pe, rva):
    """메뉴 항목을 만드는 함수에서 'evid' 키 바로 앞에 실은 4글자 값 (바이트 검색). 보호 구역(jmp)이면 []."""
    o = pe.off(rva)
    if o is None or pe.m[o] == 0xE9:
        return []
    f = pe.func_of(rva)
    end = o + ((f[1] - f[0]) if f else 0x800)
    m, out = pe.m, []
    k = m.find(b"\xba\x64\x69\x76\x65", o, end)   # mov edx, 'evid'
    while k != -1:
        j = m.rfind(b"\xba", max(o, k - 0x40), k)   # 그 앞의 mov edx, imm32
        while j != -1:
            v = struct.unpack_from("<I", m, j + 1)[0].to_bytes(4, "big")
            if v != b"evid" and all(0x20 < c < 0x7f for c in v):
                if v.decode() not in out:
                    out.append(v.decode())
                break
            j = m.rfind(b"\xba", max(o, k - 0x40), j)
        k = m.find(b"\xba\x64\x69\x76\x65", k + 5, end)
    return out


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


def _ev_cell(u):
    if not u:
        return "-"
    if u.get("noop"):
        return "실행 불가"
    evs = list(u["events"]) + [x for x in u.get("click", []) if x not in u["events"]]
    out = []
    for x in evs:
        t = "`%s`" % x
        if x in u.get("click", []):
            t = "**%s**" % t
        if x == u.get("confirm"):
            t += " ✔"
        out.append(t)
    return " ".join(out)


def docs(reg):
    A = reg["actions"]
    L = ["# 게임 액션(명령) 목록", "",
         "> `python -X utf8 tools/actions_catalog.py`가 `core/actions.json`에서 만들어요. 직접 고치지 마세요.", "",
         "FM24에서 사용자가 하는 명령(관심 목록에 넣기, 이적 제의, 계약 제의, 휴가 …)은 게임 안에서 **액션 객체 %d개**예요. "
         "M24GA는 그 목록을 등록부로 만들어 뒀어요. 모드는 (코어 0.41.0) `api.actionsFor(대상)`으로 게임 메뉴가 그 대상에 보여 주는 명령을 읽고 "
         "(기능 `read.action`), `api.action(id, 대상, {event})`로 실행해요 (기능 `game.action`, 세이브를 바꿔서 사용자 허용·기록)." % len(A), "",
         "- 액션 id = 4글자 (예: `PGoH` 휴가, `AtSo` 관심 목록에 넣기, `offr` 이적 제의).",
         "- 화면이 열릴 때 게임은 액션마다 '이 대상에 대해' 확인 함수를 불러요. 넘기는 문맥 묶음: " +
         ", ".join("`%s` %s" % kv for kv in reg["context_keys"].items()) + ".",
         "- `protected` = 확인 함수가 Denuvo 보호 구역이라 정적으로 못 읽은 것. `keys` = 확인 함수가 읽는 키 후보.",
         "- `실행 이벤트` = 실행 쪽 처리기(*_ACTION_UI)가 받는 이벤트. **굵게** = 메뉴를 누를 때 보내는 이벤트(`click`, 확인 창·화면을 여는 단계가 많아요), ✔ = 확인 뒤 이벤트(`confirm`, 확인 창 없이 실행). 하나면 `api.action`에서 생략, 여럿이면 `{event}`로 골라요. `실행 불가` = 처리기가 비어 있어 이 길로 실행할 수 없는 명령 (화면 이동 LINK, 사임 등), '-' = 실행 객체 없음.",
         "- 실기 확인 (M65): `SUBS` 구독 / `USUB` 구독 취소 = 바로 반영. 리더십 훈련 코스(`Ablc`)는 화면 메뉴로 확인. 주장 지정 `PmcP`는 누름 `pmcE`(확인 창, 모드에서 부르면 창이 안 뜸)가 아니라 확인 뒤 `pmcC`를 주면 실행되고 다음 날 처리 때 반영 (주장 바뀜 → 되돌림 확인). 다른 `confirm`은 같은 꼴(이벤트 2개 중 누름이 아닌 쪽)이라 적은 것이고 실기는 아직이에요.",
         "- CLI: `cli.py actions [정규식]` (게임 없이 됨).", ""]
    by = {}
    for aid, e in A.items():
        by.setdefault(e["group"], []).append((aid, e))
    for g in sorted(by, key=lambda x: (x == "기타", x)):
        L += ["## %s (%d)" % (g, len(by[g])), "", "| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |", "|---|---|---|---|---|"]
        for aid, e in sorted(by[g], key=lambda x: x[1]["class"]):
            ev = _ev_cell(e.get("ui"))
            L.append("| `%s` | `%s` | %s | %s | %s |" % (aid.replace("|", "\\|"), e["class"], "예" if e["protected"] else "", " ".join("`%s`" % k for k in e.get("keys", [])[:10]), ev))
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
