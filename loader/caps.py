"""M24GA 기능 등록부 (M10): core/capabilities.json 읽기, 모드 코드에서 쓰는 기능 찾기, 위험 등급. GPL-3.0-or-later.

모드는 mod.json "capabilities"에 쓰는 기능을 적는다. 로더와 validate는 mod.js에서 실제로 쓰는 기능도 찾아서
'선언 ∪ 찾은 것'을 그 모드의 기능으로 본다. 자동 허용이 아닌 위험 등급(pc, raw, hook, write)은 사용자가 허용해야 켜진다.
**샌드박스가 아니다:** 모드 JS는 코어와 같은 스크립트에서 돌고 Python은 PC에서 마음대로 돈다. 찾기는 글자 모양으로 하므로
일부러 숨기면 못 찾는다. 등록부의 목적은 (1) 사용자에게 무엇을 하는 모드인지 보여 주고 동의를 받는 것,
(2) 모드 제작자·AI에게 쓸 수 있는 기능과 이름을 정확히 알려 주는 것, (3) 게임 빌드별로 되는 기능을 알려 주는 것이다.
이 모듈은 mods.py에 의존하지 않는다 (mods.py, validate.py, tools/m24.py가 가져다 쓴다).
"""
import difflib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(ROOT, "core", "capabilities.json")
RISK_ORDER = ("read", "ui", "pc", "raw", "hook", "write")
_cache = {}


def registry():
    """{"core", "risks": {이름: {label, auto, desc}}, "capabilities": [...], "by_name": {이름: 항목}} (한 번 읽고 기억)."""
    if "reg" not in _cache:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            reg = json.load(f)
        for c in reg["capabilities"]:
            c["_re"] = [re.compile(p) for p in c.get("detect") or []]
        reg["by_name"] = {c["name"]: c for c in reg["capabilities"]}
        _cache["reg"] = reg
    return _cache["reg"]


def names():
    return [c["name"] for c in registry()["capabilities"]]


def risk_of(name):
    c = registry()["by_name"].get(name)
    return c["risk"] if c else None


def is_auto(name):
    """자동으로 허용되는 기능인가 (read, ui)."""
    r = risk_of(name)
    return bool(r and registry()["risks"][r]["auto"])


def closest(name):
    m = difflib.get_close_matches(name, names(), n=1, cutoff=0.5)
    return m[0] if m else None


def _code_lines(js):
    """주석을 뺀 줄들 (줄 번호, 글). 문자열 안의 // 는 드물어서 단순하게 자른다 (validate.at과 같은 규칙)."""
    out, block = [], False
    for n, ln in enumerate(js.splitlines(), 1):
        if block:
            if "*/" not in ln:
                continue
            ln, block = ln.split("*/", 1)[1], False
        while "/*" in ln:
            head, rest = ln.split("/*", 1)
            if "*/" in rest:
                ln = head + " " + rest.split("*/", 1)[1]
            else:
                ln, block = head, True
        out.append((n, ln.split("//")[0]))
    return out


FIELDS_PATH = os.path.join(ROOT, "core", "fields.json")
# getField(obj, '이름') / api.setField(obj, '이름', ...) / fieldInfo('이름'): 첫 인자 안에 괄호 한 겹(personOf(p))까지 허용
_FIELD_USE = re.compile(r"""\b(getField|api\.setField)\s*\((?:[^,()]|\([^()]*\))*,\s*['"]([\w.]+)['"]|\b(fieldInfo)\s*\(\s*['"]([\w.]+)['"]""")


def fields():
    """필드 등록부 core/fields.json {"kinds", "fields"} (한 번 읽고 기억)."""
    if "fields" not in _cache:
        with open(FIELDS_PATH, encoding="utf-8") as f:
            _cache["fields"] = json.load(f)
    return _cache["fields"]


FUNCS_PATH = os.path.join(ROOT, "core", "functions.json")
_HOOK_USE = re.compile(r"""\bapi\.hook\s*\(\s*['"]([\w.]+)['"]""")


def functions():
    """함수 등록부 core/functions.json {"functions"} (한 번 읽고 기억)."""
    if "funcs" not in _cache:
        with open(FUNCS_PATH, encoding="utf-8") as f:
            _cache["funcs"] = json.load(f)
    return _cache["funcs"]


def hook_uses(js):
    """mod.js에서 api.hook('이름')으로 쓴 함수 [(줄 번호, 이름)]."""
    return [(n, m.group(1)) for n, code in _code_lines(js or "") for m in _HOOK_USE.finditer(code)]


def functions_markdown():
    """docs/FUNCTIONS.md 본문 (tools/m24.py caps가 쓴다)."""
    fr = functions()
    out = ["# M24GA 함수 목록 (코어 %s)" % registry()["core"], "",
           "> 이 파일은 `core/functions.json`에서 `python -X utf8 tools/m24.py caps`로 만들어요. 직접 고치지 마세요.", "",
           "게임 함수에 끼어들어요: `api.hook('이름', { before: function (ev) {}, after: function (ev) {} })` (기능 `hook.function`, 사용자 허용 필요). "
           "`ev.args`(형식대로 바꾼 인자), `ev.raw(i)`, `ev.caller`, `ev.tid`, `ev.data`(before → after), after에서 `ev.ret`. "
           "**끼어들기: modify**인 함수만 `ev.setArg(i, v)`(before) / `ev.setRet(v)`(after)로 바꿀 수 있어요. 콜백은 게임 스레드에서 불리니 짧게 하세요.",
           "코어는 함수마다 하나만 걸고 여러 모드에 나눠 줘요. 모드를 내리면 자동으로 떼요. 서명(`sig`)이 이 빌드와 다르면 걸지 않아요.",
           "새 함수는 `core/functions.json`에 한 줄 더하면 돼요 (찾는 법: CLI `watch-write`로 그 칸에 쓰는 함수, `watch-call`로 인자·호출자 관찰, REA 디컴파일). "
           "인자 뜻을 확인하지 못했으면 `verified: false`, 끼어들기는 `observe`로 두세요.", "",
           "빌드: %s" % fr.get("build", ""), "",
           "| 함수 | 위치 | 인자 → 반환 | 뜻 | 끼어들기 | 확인 |", "|---|---|---|---|---|---|"]
    for n, f in fr["functions"].items():
        args = ", ".join("%s%s" % (t, (" " + f["argNames"][i]) if f.get("argNames") and i < len(f["argNames"]) and f["argNames"][i] != "?" else "")
                         for i, t in enumerate(f.get("args") or []))
        if f.get("owner") == "core" and f.get("call"):
            how = "코어가 부름 (끼어들기 없음)"
        elif f.get("owner") == "core":
            how = "코어 전용 (`api.on('%s')`)" % f.get("event")
        else:
            how = "**modify**" if f.get("hook") == "modify" else "observe"
        out.append("| `%s` | fm+%s | (%s) → %s | %s | %s | %s |" % (n, f["rva"], args, f.get("ret", "void"), f.get("desc", ""), how,
                                                       ("✔ " if f.get("verified") else "미확인 ") + f.get("source", "")))
    if fr.get("gates"):
        out += ["", "## 게이트 (`api.gate`, 기능 `hook.gate`, 코어 0.15.0, 같은 칸 여러 개는 0.16.0)", "",
                "정해진 게임 함수(범위) 안에서만, 정해진 클래스의 가상 함수 칸이 다른 답(null/false)을 돌려줘요. 스레드마다 범위를 세서 다른 스레드는 원래 답을 받아요. "
                "코어가 범위 함수 서명, vtable 칸의 지금 값, 원래 함수 바이트를 모두 확인한 뒤에만 걸고, 모드를 내리면 원래대로 돌려요. 같은 칸에 게이트를 여러 개 걸면 사슬로 이어져서 각자 자기 범위에서만 답해요.", "",
                "| 게이트 | 범위 함수 | 바꾸는 칸 | 답 | 뜻 | 확인 |", "|---|---|---|---|---|---|"]
        for n, g in fr["gates"].items():
            out.append("| `%s` | fm+%s | `%s` vtable fm+%s +%s | %s | %s | %s |" % (n, g["scope"]["rva"], g.get("cls", "?"), g["vtable"], g["slot"], g.get("answer", "null"),
                                                                        g.get("desc", ""), ("✔ " if g.get("verified") else "미확인 ") + g.get("source", "")))
    return "\n".join(out) + "\n"


def field_uses(js):
    """mod.js에서 이름으로 쓴 필드 [(줄 번호, 'get'|'set'|'info', 필드 이름)]."""
    out = []
    for n, code in _code_lines(js or ""):
        for m in _FIELD_USE.finditer(code):
            fn, name = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            out.append((n, "set" if fn == "api.setField" else ("info" if fn == "fieldInfo" else "get"), name))
    return out


def field_cap(name):
    """그 필드를 쓰는 데 필요한 기능 (write: safe가 아니면 None)."""
    f = fields()["fields"].get(name)
    return (f.get("cap") or "write.field") if f and f.get("write") == "safe" else None


def detect(js, manifest=None):
    """mod.js 글(과 mod.json)에서 쓰는 기능을 찾는다. 반환 {기능 이름: 처음 나온 줄 번호(mod.json이면 0)}."""
    found = {}
    lines = _code_lines(js or "")
    for c in registry()["capabilities"]:
        for n, code in lines:
            if any(r.search(code) for r in c["_re"]):
                found[c["name"]] = n
                break
    for n, how, name in field_uses(js):   # api.setField는 필드마다 필요한 기능이 다르다 (M20)
        cap = field_cap(name) if how == "set" else None
        if cap and cap not in found:
            found[cap] = n
    if manifest and manifest.get("python"):
        found["pc.python"] = 0
    return found


def declared(manifest):
    v = manifest.get("capabilities")
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def effective(manifest, js):
    """그 모드의 기능 = 선언한 것(알려진 이름만) ∪ 코드에서 찾은 것. 위험 등급 순서로 정렬."""
    known = registry()["by_name"]
    out = {x for x in declared(manifest) if x in known} | set(detect(js, manifest))
    return sorted(out, key=lambda x: (RISK_ORDER.index(known[x]["risk"]), x))


def unknown(manifest):
    known = registry()["by_name"]
    return [x for x in declared(manifest) if x not in known]


def elevated(cap_names):
    """사용자 허용이 필요한 기능만."""
    return [x for x in cap_names if not is_auto(x)]


def unsupported(cap_names, build_name):
    """이 게임 빌드에서 지원하지 않는 기능 (빌드 이름을 모르면 빈 목록)."""
    if not build_name:
        return []
    by = registry()["by_name"]
    return [x for x in cap_names if x in by and "*" not in by[x]["builds"] and build_name not in by[x]["builds"]]


def describe(cap_names, granted=()):
    """GUI·보고서용 [{name, title, risk, risk_label, auto, granted, desc}]."""
    reg = registry()
    out = []
    for x in cap_names:
        c = reg["by_name"].get(x)
        if not c:
            continue
        r = reg["risks"][c["risk"]]
        out.append({"name": x, "title": c["title"], "risk": c["risk"], "risk_label": r["label"], "auto": r["auto"],
                    "granted": r["auto"] or x in granted, "desc": c["desc"]})
    return out


def fields_markdown():
    """docs/FIELDS.md 본문 (tools/m24.py caps가 쓴다)."""
    fr = fields()
    out = ["# M24GA 필드 목록 (코어 %s)" % registry()["core"], "",
           "> 이 파일은 `core/fields.json`에서 `python -X utf8 tools/m24.py caps`로 만들어요. 직접 고치지 마세요.", "",
           "게임 객체의 칸을 이름으로 읽어요: `getField(obj, '이름')` (기능 `read.field`). 쓰기가 확인된 칸(**쓰기: safe**)은 "
           "`api.setField(obj, '이름', 값, { expect, reason })`로 바꿀 수 있어요 (그 칸의 쓰기 기능, 사용자 허용 필요, 모든 쓰기가 기록되고 앱에서 되돌릴 수 있어요).",
           "객체는 `findObj('player', uid)`, `playerByUid(uid)`, `myInfo().co` 같은 코어 함수로 얻어요. 객체 종류는 클래스 이름(RTTI)으로 확인해서, 종류가 다른 객체를 넘기면 `null`이에요.",
           "새 칸을 찾으면 `core/fields.json`에 한 줄 더하면 돼요 (찾는 법: CLI `explore`, [`CLI.md`](CLI.md)). 확인하지 못한 칸은 `verified: false`로 두세요.", "",
           "빌드: %s" % fr.get("build", ""), ""]
    out += ["## 객체 종류", "", "| 종류 | 클래스 | 설명 |", "|---|---|---|"]
    for k, v in fr["kinds"].items():
        out.append("| `%s` (%s) | `%s` | %s |" % (k, v.get("label", ""), v["cls"], v.get("desc", "")))
    for k in fr["kinds"]:
        rows = [(n, f) for n, f in fr["fields"].items() if f["kind"] == k]
        if not rows:
            continue
        out += ["", "## %s (`%s`)" % (fr["kinds"][k].get("label", k), k), "",
                "| 필드 | 위치 | 형식 | 뜻 | 쓰기 | 확인 |", "|---|---|---|---|---|---|"]
        for n, f in rows:
            pos = " → ".join(["+" + x for x in f.get("via") or []] + ["+" + f["off"]])
            if f.get("alt"):
                pos += " (" + ", ".join("%s: %s" % (c.split("::")[-1], "+" + o if o else "없음") for c, o in f["alt"].items()) + ")"
            typ = f["type"] + (" → `%s`" % f["to"] if f.get("to") else "") + (" (%s)" % f["map"] if f.get("map") else "")
            w = "**safe**" if f.get("write") == "safe" else "-"
            if f.get("write") == "safe":
                extra = [x for x in (("범위 %s~%s" % tuple(f["range"])) if f.get("range") else "", ("≥ `%s`" % f["gte"]) if f.get("gte") else "",
                                     ("≤ `%s`" % f["lte"]) if f.get("lte") else "", "기능 `%s`" % (f.get("cap") or "write.field")) if x]
                w += " (" + ", ".join(extra) + ")"
            out.append("| `%s` | %s | %s | %s%s | %s | %s |" % (n, pos, typ, f.get("desc", ""), (" [%s]" % f["unit"]) if f.get("unit") else "", w,
                                                       ("✔ " if f.get("verified") else "미확인 ") + f.get("source", "")))
    return "\n".join(out) + "\n"


def markdown():
    """docs/CAPABILITIES.md 본문 (tools/m24.py caps가 쓴다)."""
    reg = registry()
    out = ["# M24GA 기능 목록 (코어 %s)" % reg["core"], "",
           "> 이 파일은 `core/capabilities.json`에서 `python -X utf8 tools/m24.py caps`로 만들어요. 직접 고치지 마세요.", "",
           "모드는 `mod.json`의 `\"capabilities\"`에 쓰는 기능의 이름을 적어요. 로더와 `validate`는 `mod.js`에서 실제로 쓰는 기능도 찾아내요.",
           "**선언하지 않고 쓰면 `validate`가 오류를 내요.** 자동 허용이 아닌 등급은 사용자가 앱에서 허용해야 모드가 켜져요.",
           "", "## 위험 등급", "", "| 등급 | 뜻 | 허용 |", "|---|---|---|"]
    for k in RISK_ORDER:
        r = reg["risks"][k]
        out.append("| `%s` | %s: %s | %s |" % (k, r["label"], r["desc"], "자동" if r["auto"] else "**사용자가 허용해야 함**"))
    out += ["", "## 기능", "", "| 이름 | 등급 | 설명 | 코어 이름 | 빌드 |", "|---|---|---|---|---|"]
    for c in reg["capabilities"]:
        out.append("| `%s` | %s | **%s**: %s%s | %s | %s |" % (c["name"], c["risk"], c["title"], c["desc"].replace("|", "\\|"),
                                                       (" _(화면 의존: %s)_" % c["screen"]) if c.get("screen") else "",
                                                       ", ".join("`%s`" % u.replace("|", "\\|") for u in c["uses"]),
                                                       "모두" if "*" in c["builds"] else ", ".join(c["builds"])))
    out += ["", "## 예제", ""]
    for c in reg["capabilities"]:
        out += ["**`%s`**" % c["name"], "", "```js" if not c["example"].startswith('"') else "```json", c["example"], "```", ""]
    out += ["## 이 목록에 없는 것", "",
            "게임 값을 **안전하게** 쓰는 기능(백업·쓰기 기록 포함), 새 이벤트(날짜 진행, 경기 결과, 세이브 로드), 새 화면 요소는 아직 없어요.",
            "`raw.*`로 직접 할 수는 있지만 게임이 튕기거나 세이브가 망가질 수 있어요. 새 기능을 코어에 넣으면 이 목록에 먼저 추가해요.", ""]
    return "\n".join(out)
