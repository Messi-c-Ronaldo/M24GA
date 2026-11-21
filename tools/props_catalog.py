"""속성 등록부 만들기 (M55, 작성: Claude)

게임 객체의 get_property(vtable+0x10)에 후보 코드를 모두 물어 본 조사 결과(scan_*.json)를 모아
core/properties.json을 만든다. 이미 있는 등록부의 뜻(ko)·확인(verified)은 그대로 둔다.

사용법:
  python -X utf8 tools/props_catalog.py <scan 폴더> [--out core/properties.json]
  python -X utf8 tools/props_catalog.py --docs        # docs/PROPERTIES.md만 다시 만들기

조사 결과 한 파일 = {name, cls, vt, props: {코드: [종류, 값 미리보기, 키 목록?]}} (조사 모드 m54-probe가 만든다).
등록부에는 게임 글(이름·값)을 넣지 않는다: 코드, 객체 종류, 값 종류, 묶음 키만.
"""
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "core", "properties.json")
DOC = os.path.join(ROOT, "docs", "PROPERTIES.md")

# 객체 종류: RTTI 클래스 이름 → 속성 부분의 위치(맨 위 객체에서 떨어진 칸). 빌드가 바뀌어도 클래스 이름은 그대로다.
KINDS = {
    "team": {"class": "db::TEAM", "off": 0, "ko": "팀 (구단의 1군·2군 등, 코어 clubs 표)"},
    "club": {"class": "db::CLUB", "off": 0, "ko": "구단"},
    "nation": {"class": "db::NATIONAL_TEAM", "off": 0, "ko": "국가대표팀"},
    "player": {"class": "db::ACTUAL_PLAYER", "off": 0x278, "ko": "선수 (코어 persons 표)"},
    "staff": {"class": "db::ACTUAL_NON_PLAYER", "off": 0xf8, "ko": "감독·스태프 (코어 staff 표)"},
    "human": {"class": "db::HUMAN_NON_PLAYER", "off": 0x450, "ko": "사람 감독 (myHuman())"},
    "comp": {"class": "db::COMP", "off": 0, "ko": "대회 (코어 comps 표)"},
    "award": {"class": "db::AWARD", "off": 0, "ko": "상 (코어 awards 표)"},
    # M58: 포인터로만 닿는 종류 (deref 표 없음)
    "country": {"class": "db::NATION", "off": 0, "ko": "국가 (축구협회 포함, 국가대표팀과 다름)"},
    "stadium": {"class": "db::STADIUM", "off": 0, "ko": "경기장"},
    "city": {"class": "db::CITY", "off": 0, "ko": "도시"},
    "continent": {"class": "db::CONTINENT", "off": 0, "ko": "대륙 (연맹)"},
    "media": {"class": "db::MEDIA_SOURCE", "off": 0, "ko": "언론사 (뉴스 +0x98)"},
    "contract": {"class": "db::FULL_CONTRACT", "off": 0, "ko": "계약 (사람 감독 +0x518 = 'myjob')"},
    "loan": {"class": "db::LOAN_CONTRACT", "off": 0, "ko": "임대 계약"},
    "injury": {"class": "db::INJURY", "off": 0, "ko": "부상 종류"},
}
CLASS_KIND = {v["class"]: k for k, v in KINDS.items()}
# 조사 결과의 값 종류 → 등록부 값 종류
TYPE_MAP = {"int": "int", "str": "str", "bool": "bool", "rec": "rec", "list": "list", "dbl": "num", "flt": "num", "cc": "int",
            "?50": "u32", "?fmdate::SI_DATE_TYPED_TRAITS": "date", "?sicore::RGBA_TYPED_TRAITS": "color",
            "?sicore::DATA_TYPED_TRAITS": "data", "empty": "empty"}
TYPES = ["int", "u32", "num", "bool", "str", "date", "color", "rec", "list", "data", "empty", "unknown"]


def load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def build(scan_dir, old):
    scans = [load(p) for p in sorted(glob.glob(os.path.join(scan_dir, "scan_*.json")))]
    seen = collections.defaultdict(lambda: {"types": collections.Counter(), "kinds": set(), "keys": collections.Counter(),
                                            "bykind": collections.defaultdict(collections.Counter)})
    block, nobj = {}, collections.Counter()
    for s in scans:
        kind = CLASS_KIND.get(s["cls"])
        if not kind:
            continue
        nobj[kind] += 1
        for code, e in s["props"].items():
            if e[0] == "CRASH":
                block.setdefault(code, set()).add(kind)
                continue
            r = seen[code]
            r["kinds"].add(kind)
            r["types"][TYPE_MAP.get(e[0], "unknown")] += 1
            r["bykind"][kind][TYPE_MAP.get(e[0], "unknown")] += 1
            for k in (e[2] if len(e) > 2 and isinstance(e[2], list) else []):
                r["keys"][k] += 1
    oldp = (old or {}).get("props", {})
    props = {}
    for code in sorted(seen):
        r = seen[code]
        full = [t for t, _ in r["types"].most_common() if t != "empty"]
        p = {"t": full[0] if full else "empty", "k": sorted(r["kinds"], key=list(KINDS).index)}
        tk = {}
        for k, cnt in r["bykind"].items():   # 종류마다 값 종류가 다르면 따로 적는다 (예: Ccre 팀은 int, 구단은 rec)
            kt = [t for t, _ in cnt.most_common() if t != "empty"]
            if kt and kt[0] != p["t"]:
                tk[k] = kt[0]
        if tk:
            p["tk"] = dict(sorted(tk.items()))
        if r["keys"]:
            p["keys"] = sorted(r["keys"])
        o = oldp.get(code, {})
        for keep in ("ko", "unit", "verified", "note"):
            if keep in o:
                p[keep] = o[keep]
        props[code] = p
    for code, o in oldp.items():   # 이번 조사에 안 나온 코드도 뜻이 적혀 있으면 남긴다
        if code not in props and o.get("ko"):
            props[code] = dict(o, stale=True)
    return {
        "$comment": "게임 속성 코드 등록부 (코어 api.prop/props/propInfo, CLI props). tools/props_catalog.py가 만든다. "
                    "k = 답하는 객체 종류, t = 값 종류(empty = 조사한 객체에서는 늘 빈 값), keys = 묶음(rec)·목록(list) 항목의 키, "
                    "ko = 화면과 맞춰 본 뜻. 게임 글(이름·값)은 넣지 않는다.",
        "core": (old or {}).get("core", "0.36.0"),
        "source": {"build": "FM24 Epic 24.4.2 (fm.exe 2026-10-24)", "objects": dict(nobj), "method": "get_property 전수 조사 (M55)"},
        "kinds": KINDS,
        "types": TYPES,
        "block": {c: sorted(k) for c, k in sorted(block.items())},
        **({"write": old["write"]} if old and "write" in old else {}),   # 쓰기 확인 결과(M71)는 조사로 다시 만들지 않는다
        "props": props,
    }


def docs(reg):
    P = reg["props"]
    L = ["# 게임 속성 코드", "",
         "> 이 문서는 `python -X utf8 tools/props_catalog.py --docs`가 `core/properties.json`에서 만들어요. 고치려면 등록부의 `ko`를 고치세요.", "",
         "게임 화면(스킨)은 `get_property=\"Tpos\"`처럼 **4글자 속성 코드**로 값을 물어요. 게임 객체마다 답하는 코드가 정해져 있고, "
         "M24GA는 그 목록을 전부 조사해 등록부(`core/properties.json`)로 만들었어요 (코어 0.36.0, 기능 `read.prop`).", "",
         "```js",
         "api.prop('myteam', 'TpoN')          // 리그 순위 (정수)",
         "api.props('myteam', { re: '^Cc' })  // {코드: 값} — 그 객체가 답하는 코드 중 정규식에 맞는 것",
         "api.propInfo('Pced')                // { code, t: 'date', k: ['player', ...], ko }",
         "api.deref(api.prop('myteam', 'Topp')) // {dref} → 객체 (사람·팀·구단·대회)",
         "```", "",
         "- 대상: 객체 포인터(어느 칸을 가리켜도 됨) 또는 `'me'`(내 감독) · `'myteam'` · `'myclub'` · `'myjob'`(내 감독 계약) · 사람 참조 `'p123'`/`'s45'` · 사람의 계약 `'contract:p123'`/`'contract:s45'`/`'contract:me'` (M74).",
         "- 값 종류: `int` 정수, `u32` 부호 없는 정수, `num` 실수, `bool`, `str` 글, `date` 날짜(`'2038-06-30'`, 빈 날짜는 null), "
         "`color` 색(`'#rrggbbaa'`), `rec` 묶음(`{키: 값}`), `list` 목록, `data` 내부 자료(null), `empty` 조사한 객체에서는 늘 빈 값.",
         "- `{dref: 번호}` = 다른 게임 객체 링크. 위 8비트가 종류예요: `0x01` 사람, `0x03` 구단, `0x18` 팀, `0x19` 대회 (`api.deref`). 국가·경기장 등 나머지 종류는 링크로 못 따라가고, 다른 객체가 가리키는 포인터로만 닿아요 (예: `matchEnded`의 `ev.stadium`).",
         "- 값은 **게임 화면이 보여 주는 값 그대로**예요. 뜻(ko)을 적은 것만 화면과 맞춰 봤어요. 나머지는 이름을 보고 짐작해서 쓰되, 직접 확인하세요.",
         "- 이름은 게임 파일(`properties.fmf` + 번역 파일)에만 있어서 저장소에 넣지 않았어요. `python -X utf8 tools/prop_names.py`가 자기 게임 파일에서 `~/m24ga_data/prop_names.tsv`(코드, 영어, 게임 언어, 표시 형식, 분류)를 만들고, 있으면 CLI `props`·`prop-info`가 이름·표시 형식을 같이 보여 줘요.", ""]
    if reg.get("block"):
        L += ["**부르지 않는 코드** (게임 안에서 접근 오류): " + ", ".join("`%s`" % c for c in reg["block"]), ""]
    L += ["## 객체 종류", "", "| 종류 | 게임 클래스 | 코드 수 | 뜻 |", "|---|---|---|---|"]
    for k, v in reg["kinds"].items():
        n = sum(1 for p in P.values() if k in p["k"])
        L.append("| `%s` | `%s` (+0x%x) | %d | %s |" % (k, v["class"], v["off"], n, v["ko"]))
    L += ["", "## 화면과 맞춰 본 코드", "", "| 코드 | 종류 | 값 | 뜻 |", "|---|---|---|---|"]
    for c, p in P.items():
        if p.get("ko"):
            L.append("| `%s` | %s | %s | %s%s |" % (c, ", ".join(p["k"]) or "-", p["t"], p["ko"], (" (" + p["unit"] + ")") if p.get("unit") else ""))
    W = reg.get("write", {})
    if W.get("codes"):
        safe = [(c, e) for c, e in W["codes"].items() if e["w"] == "safe"]
        tested = [(c, e) for c, e in W["codes"].items() if e["w"] == "tested"]
        L += ["", "## 쓰기 (코어 0.42.0, 기능 `write.prop`)", "",
              "`api.setProp(대상, '코드', 값, {expect, reason})` → Promise `{ok, before, after, code, key, error}` (Python `ctx.set_prop`). "
              "게임 자신의 setter(속성 객체 vtable +0x18)를 화면 스레드에서 불러요. 정수·불리언·실수만 되고, 기록되고 앱에서 되돌릴 수 있어요.", "",
              "- **safe** (%d개): 쓰기 → 화면 → 하루 진행 → 저장 뒤 다시 불러오기까지 확인했어요 (M71)." % len(safe),
              "- **tested** (%d개): setter가 받고 +1·되돌리기만 확인했어요. `{tested: true}`를 줘야 써지고, 게임에서 결과를 꼭 확인하세요." % len(tested),
              "- **쓰지 않는 코드**: " + ", ".join("`%s`" % c for c in W.get("deny", [])) + " (`Ptyp`는 사람 종류를 바꿔서 게임이 객체를 새로 만들어요).", "",
              "| 코드 | 종류 | 범위 | 뜻 |", "|---|---|---|---|"]
        for c, e in safe:
            r = e.get("range")
            extra = (" (≥ %s)" % e["gte"]) if e.get("gte") else (" (≤ %s)" % e["lte"]) if e.get("lte") else ""
            L.append("| `%s` | %s | %s%s | %s |" % (c, ", ".join(e["kinds"]), ("%s~%s" % (r[0], r[1])) if r else "-", extra, P.get(c, {}).get("ko", "")))
        by = collections.defaultdict(list)
        for c, e in tested:
            for k in e["kinds"]:
                by[k].append("`%s`" % c)
        L += ["", "<details><summary><b>tested 코드</b> (종류별)</summary>", ""]
        L += ["- **%s** (%d): %s" % (k, len(v), " ".join(v)) for k, v in by.items()]
        L += ["", "</details>"]
    L += ["", "## 전체 목록 (종류별)", "", "값 종류 뒤 `{…}`는 묶음·목록 항목의 키예요.", ""]
    for k in reg["kinds"]:
        codes = [c for c, p in P.items() if k in p["k"]]
        L += ["<details><summary><b>%s</b> — %d개</summary>" % (k, len(codes)), ""]
        by = collections.defaultdict(list)
        for c in codes:
            p = P[c]
            keys = [k for k in p.get("keys", []) if k.isprintable()]   # 제어 문자 키(Chol 등)는 문서에서 뺀다
            by[p["t"]].append("`%s`%s" % (c, ("{" + ",".join(keys[:6]) + ("…" if len(keys) > 6 else "") + "}") if keys else ""))
        for t in reg["types"]:
            if by.get(t):
                L.append("- **%s** (%d): %s" % (t, len(by[t]), " ".join(by[t])))
        L += ["", "</details>", ""]
    return "\n".join(L) + "\n"


def save(reg, path):
    """코드 하나 = 한 줄 (diff 보기 좋게)."""
    head = {k: v for k, v in reg.items() if k not in ("props", "write")}
    txt = json.dumps(head, ensure_ascii=False, indent=1)[:-2]
    one = lambda p: json.dumps(p, ensure_ascii=False, separators=(",", ":"))
    if "write" in reg:   # 쓰기 등록부(M71)도 코드 하나 = 한 줄
        w = reg["write"]
        txt += ',\n "write": {\n  "$comment": %s,\n  "deny": %s,\n  "codes": {\n%s\n  }\n }' % (
            json.dumps(w["$comment"], ensure_ascii=False), one(w["deny"]),
            ",\n".join('   %s: %s' % (json.dumps(c), one(e)) for c, e in w["codes"].items()))
    rows = ['  %s: %s' % (json.dumps(c), one(p)) for c, p in reg["props"].items()]
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt + ',\n "props": {\n' + ",\n".join(rows) + "\n }\n}\n")


def main(argv):
    if "--docs" in argv:
        reg = load(REG)
        save(reg, REG)
    else:
        if not argv or argv[0].startswith("--"):
            print(__doc__)
            return 2
        out = argv[argv.index("--out") + 1] if "--out" in argv else REG
        reg = build(argv[0], load(out))
        save(reg, out)
        print("등록부: %d개 코드, 막은 코드 %d개 -> %s" % (len(reg["props"]), len(reg["block"]), out))
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(docs(reg))
    print("문서: %s" % DOC)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
