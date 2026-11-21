"""반자동 게임 API 탐색 (M78, 작성: Claude): 후보 저장소 -> 자동 검증 -> 등록.

후보(candidate) = 아직 등록부에 없는 쓰기 후보 하나.
  - kind 'prop'  : 속성 코드를 게임 setter(vtable +0x18)로 쓰는 것. {code}
  - kind 'field' : 객체 맨 앞(+via 포인터들) + 칸에 메모리로 쓰는 것. {off, type, via?, viaCls?}
  공통: obj(객체 종류 이름), source(어디서 왔는지), evidence(근거 글 목록), tests{단계: 결과}, status
저장: ~/m24ga_data/candidates.json (개발 PC 자료, 저장소에 넣지 않음)

검증 단계 (verify):
  roundtrip : 쓰기(+1 / 반전 / +1일) -> 다시 읽기 -> 되돌리기. 쓰기 전후 스냅숏(정체성 + 같은 객체의 스칼라 속성 전부)을 비교해
              객체가 바뀌었거나(Ptyp 사고, M71) 되돌린 뒤 다른 값이 남으면 실패. 같이 바뀐 다른 속성은 'linked'로 기록 (사람이 판단).
  day       : 쓰고 하루 진행 -> 쓴 값 그대로(kept) 또는 쓴 값에서 움직임(drift)이면 통과, 원래 값으로 돌아갔으면(reverted) 실패 -> 되돌리기
  save      : 쓰고 '저장 -> 다시 불러오기'를 기다림 (verify resume) -> 같은 판단 -> 되돌리기
시험 세이브에서만 쓴다: ~/m24ga_data/verify.json의 test_saves에 지금 세이브 id가 있어야 한다.
등록 (promote): roundtrip 통과면 tested, day+save까지 통과면 safe로 core/properties.json(write) 또는 core/fields.json에 쓴다.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(os.path.expanduser("~"), "m24ga_data")
CAND = os.path.join(DATA, "candidates.json")
VCONF = os.path.join(DATA, "verify.json")
PROPS = os.path.join(ROOT, "core", "properties.json")
FIELDS = os.path.join(ROOT, "core", "fields.json")
TYPES = ("i8", "u8", "i16", "u16", "i32", "u32", "f32", "f64")
INT_RANGE = {"i8": (-128, 127), "u8": (0, 255), "i16": (-32768, 32767), "u16": (0, 65535), "i32": (-2 ** 31, 2 ** 31 - 1), "u32": (0, 2 ** 32 - 1)}


# ---- 저장소 ----
def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load():
    return _load(CAND, {"candidates": {}, "pending": None})


def store(db):
    _save(CAND, db)


def test_saves():
    return [int(x) for x in _load(VCONF, {}).get("test_saves", [])]


def add_test_save(sid):
    c = _load(VCONF, {})
    ts = set(int(x) for x in c.get("test_saves", []))
    ts.add(int(sid))
    c["test_saves"] = sorted(ts)
    _save(VCONF, c)
    return c["test_saves"]


def save_allowed(save):
    """지금 세이브가 시험 세이브인지 (쓰기 허락). save = {id, nonce} 또는 None"""
    return bool(save) and save.get("id") in test_saves()


def cand_id(kind, obj, key):
    return "%s:%s:%s" % (kind, obj, key)


def add(kind, obj, source, evidence=None, code=None, off=None, type_=None, via=None, via_cls=None):
    if kind == "prop":
        if not code or len(code) != 4:
            raise ValueError("속성 코드는 4글자예요")
        cid = cand_id("prop", obj, code)
        c = {"kind": "prop", "obj": obj, "code": code}
    elif kind == "field":
        if type_ not in TYPES:
            raise ValueError("형식은 %s 중 하나예요" % "/".join(TYPES))
        off = "0x%x" % int(off, 16)
        via = [("0x%x" % int(v, 16)) for v in (via or [])]
        cid = cand_id("field", obj, "/".join(via + [off]) + ":" + type_)
        c = {"kind": "field", "obj": obj, "off": off, "type": type_, "via": via}
        if via_cls:
            c["viaCls"] = via_cls
    else:
        raise ValueError("kind는 prop 또는 field")
    db = load()
    old = db["candidates"].get(cid)
    if old:   # 이미 있으면 근거만 더한다
        old["evidence"] = sorted(set(old.get("evidence", [])) | set(evidence or []))
        store(db)
        return cid, False
    c.update(source=source, evidence=list(evidence or []), tests={}, status="new", added=_now())
    db["candidates"][cid] = c
    store(db)
    return cid, True


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---- 검증 ----
def _vset_args(c, target, value=None):
    """앱 쪽 vset 명령 인자"""
    if c["kind"] == "prop":
        a = ["vset", target, "prop", c["code"]]
    else:
        a = ["vset", target, "field", c["off"], "--type", c["type"]]
        if c.get("via"):
            a += ["--via", ",".join(c["via"])]
    if value is not None:
        a += ["--value", json.dumps(value)]
    return a


def _next_value(r, c):
    """쓰기 시험 값: 정수 +1(끝이면 -1) / 불리언 반전 / 날짜 +1일 / 실수 +1"""
    t, v = r.get("t"), r.get("before")
    if t == "bool":
        return 0 if v else 1
    if t == "date":
        iso = r.get("beforeIso")
        if not iso:
            raise ValueError("빈 날짜는 시험할 수 없어요")
        d = datetime.date.fromisoformat(iso) + datetime.timedelta(days=1)
        return d.isoformat()
    if t in ("flt", "dbl", "f32", "f64"):
        return round(v + 1.0, 3)
    lo, hi = INT_RANGE.get(c.get("type") or {"int": "i32", "cc": "u32", "u32": "u32"}.get(t, "i32"), (-2 ** 31, 2 ** 31 - 1))
    return v + 1 if v + 1 <= hi else v - 1


def _same(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-3 * max(1.0, abs(float(b)))
        except (TypeError, ValueError):
            return False
    return a == b


def _val(r, c):
    """vset 결과에서 비교할 값 (날짜는 글)"""
    return r.get("afterIso") or r.get("after") if r.get("t") == "date" else r.get("after")


def _diff(p0, p1, skip):
    out = {}
    for k in set(p0) | set(p1):
        if k == skip:
            continue
        if not _same(p0.get(k), p1.get(k)) and not (p0.get(k) is None and p1.get(k) is None):
            out[k] = [p0.get(k), p1.get(k)]
    return out


def _ident(s):
    return [s.get("cls"), s.get("top"), s.get("key")]


def roundtrip(c, target, call):
    """call(argv) -> dict (앱 쪽 명령을 JSON으로)"""
    res = {"level": "roundtrip", "target": target, "time": _now()}
    s0 = call(["vsnap", target])
    if s0.get("error"):
        return dict(res, ok=False, error=s0["error"])
    r0 = call(_vset_args(c, target))
    if r0.get("error"):
        skip = any(w in r0["error"] for w in ("스칼라가 아니에요", "답하지 않아요"))   # 이 대상에서는 시험할 수 없음 (다른 대상에서 다시)
        return dict(res, ok=False, error=r0["error"], skip=skip)
    res.update(kindSeen=s0.get("kind"), cls=s0.get("cls"), t=r0.get("t"))
    if c["kind"] == "field" and c.get("viaCls") and r0.get("viaCls") != c["viaCls"]:
        return dict(res, ok=False, error="따라간 객체가 %s가 아니에요 (%s)" % (c["viaCls"], r0.get("viaCls")))
    before = r0.get("beforeIso") if r0.get("t") == "date" else r0.get("before")
    try:
        new = _next_value(r0, c)
    except ValueError as e:
        return dict(res, ok=False, error=str(e), skip=True)
    w = call(_vset_args(c, target, new))
    s1 = call(["vsnap", target])
    back = call(_vset_args(c, target, before))
    s2 = call(["vsnap", target])
    skip = c.get("code")
    res.update(before=before, wrote=new, after=_val(w, c), restored=_val(back, c), setterOk=w.get("ok"))
    problems = []
    if w.get("error") or back.get("error"):
        problems.append("쓰기 오류: %s" % (w.get("error") or back.get("error")))
    if not _same(_val(w, c), new):
        problems.append("쓴 값이 읽히지 않아요 (%s)" % _val(w, c))
    if not _same(_val(back, c), before):
        problems.append("되돌리기가 안 됐어요 (%s)" % _val(back, c))
    if _ident(s1) != _ident(s0) or _ident(s2) != _ident(s0):
        problems.append("쓰는 중에 객체가 바뀌었어요 %s -> %s" % (_ident(s0), _ident(s1)))
    left = _diff(s0.get("props", {}), s2.get("props", {}), skip)
    if left:
        problems.append("되돌린 뒤에도 다른 속성이 달라요: %s" % ", ".join(sorted(left)[:8]))
    res["linked"] = sorted(_diff(s0.get("props", {}), s1.get("props", {}), skip))
    res["ok"] = not problems
    if problems:
        res["problems"] = problems
    return res


def _judge(before, wrote, now):
    if _same(now, wrote):
        return "kept", True
    if _same(now, before):
        return "reverted", False
    return "drift", True


def write_for_later(c, target, call, level, save):
    """day/save 단계 준비: 값을 쓰고 기다릴 정보를 돌려준다"""
    r0 = call(_vset_args(c, target))
    if r0.get("error"):
        return {"ok": False, "error": r0["error"]}
    before = r0.get("beforeIso") if r0.get("t") == "date" else r0.get("before")
    new = _next_value(r0, c)
    w = call(_vset_args(c, target, new))
    if not _same(_val(w, c), new):
        call(_vset_args(c, target, before))
        return {"ok": False, "error": "쓴 값이 읽히지 않아요"}
    s = call(["vsnap", target])
    return {"ok": True, "level": level, "target": target, "before": before, "wrote": new, "save": save,
            "ident": [s.get("cls"), s.get("key")], "time": _now()}


def finish_later(c, p, call, save):
    """day/save 단계 끝: 지금 값을 보고 판단한 뒤 원래 값으로 되돌린다"""
    r = call(_vset_args(c, p["target"]))
    s = call(["vsnap", p["target"]])
    res = {"level": p["level"], "target": p["target"], "time": _now(), "before": p["before"], "wrote": p["wrote"]}
    if r.get("error"):
        return dict(res, ok=False, error=r["error"])
    now = r.get("beforeIso") if r.get("t") == "date" else r.get("before")
    how, ok = _judge(p["before"], p["wrote"], now)
    res.update(now=now, result=how)
    problems = []
    if not ok:
        problems.append("게임이 원래 값으로 되돌렸어요 (파생 값일 수 있어요)")
    if [s.get("cls"), s.get("key")] != p["ident"]:
        problems.append("객체가 바뀌었어요 %s -> %s" % (p["ident"], [s.get("cls"), s.get("key")]))
    if p["level"] == "save" and (save or {}).get("nonce") == (p.get("save") or {}).get("nonce"):
        problems.append("세이브를 다시 불러오지 않은 것 같아요 (nonce 그대로)")
    back = call(_vset_args(c, p["target"], p["before"]))
    res["restored"] = _val(back, c)
    res["ok"] = not problems
    if problems:
        res["problems"] = problems
    return res


def record(cid, res):
    db = load()
    c = db["candidates"][cid]
    if res.get("skip"):   # 시험할 수 없었음: 기록만 남기고 상태는 그대로 (다른 대상에서 다시)
        c.setdefault("skipped", []).append({"target": res.get("target"), "error": res.get("error"), "time": res.get("time")})
        store(db)
        return c["status"]
    c["tests"][res["level"]] = res
    t = c["tests"]
    if not all(v.get("ok") for v in t.values()):
        c["status"] = "failed"
    elif all(t.get(k, {}).get("ok") for k in ("roundtrip", "day", "save")):
        c["status"] = "verified"
    elif t.get("roundtrip", {}).get("ok"):
        c["status"] = "tested"
    store(db)
    return c["status"]


# ---- 등록 ----
def promote(cid, tier, ko=None, rng=None, name=None, gte=None, lte=None):
    """후보를 등록부에 쓴다. 반환 (등록부 파일, 이름)."""
    db = load()
    c = db["candidates"].get(cid)
    if not c:
        raise ValueError("모르는 후보: %s" % cid)
    t = c.get("tests", {})
    if not t.get("roundtrip", {}).get("ok"):
        raise ValueError("roundtrip 검증을 통과해야 등록할 수 있어요")
    if tier == "safe" and not (t.get("day", {}).get("ok") and t.get("save", {}).get("ok")):
        raise ValueError("safe는 day·save 검증까지 통과해야 해요 (지금: %s)" % ", ".join("%s=%s" % (k, v.get("ok")) for k, v in t.items()))
    if tier == "safe" and not rng:
        raise ValueError("safe는 --range 최소 최대가 필요해요")
    src = "M78 verify %s (%s)" % (", ".join("%s %s" % (k, v.get("result") or ("ok" if v.get("ok") else "x")) for k, v in sorted(t.items())), c.get("source", ""))
    if c["kind"] == "prop":
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import props_catalog as pc   # noqa: E402
        reg = pc.load(PROPS)
        if c["code"] not in reg["props"]:
            raise ValueError("등록부에 없는 코드예요: %s" % c["code"])
        if c["code"] in reg.get("write", {}).get("deny", []):
            raise ValueError("쓰기 금지 코드예요: %s" % c["code"])
        w = reg.setdefault("write", {"$comment": "", "deny": [], "codes": {}})["codes"]
        e = w.get(c["code"], {"kinds": []})
        e["w"] = tier
        e["kinds"] = sorted(set(e.get("kinds", [])) | {c["obj"]})
        if rng:
            e["range"] = rng
        for k, v in (("gte", gte), ("lte", lte)):
            if v:
                e[k] = v
        w[c["code"]] = {k: e[k] for k in ("w", "kinds", "range", "gte", "lte") if k in e}
        p = reg["props"][c["code"]]
        seen = {"int": "int", "cc": "u32", "u32": "u32", "bool": "bool", "date": "date", "flt": "num", "dbl": "num"}.get(t["roundtrip"].get("t"))
        if p.get("t") in ("empty", "unknown") and seen:   # 전수 조사 때 빈 값이었던 코드: 검증에서 본 값 종류로 (M78 Cabo)
            p["t"] = seen
        if ko and not p.get("ko"):
            p["ko"] = ko + " (M78 등록)"
        if tier == "safe" and not p.get("ko"):
            raise ValueError("safe 코드는 뜻(--ko)이 필요해요")
        pc.save(reg, PROPS)
        with open(pc.DOC, "w", encoding="utf-8") as f:
            f.write(pc.docs(reg))
        out = (PROPS, c["code"])
    else:
        if not name or not re.match(r"^[a-z]+(\.[A-Za-z0-9]+)+$", name):
            raise ValueError("필드는 --name 종류.이름 형식이 필요해요 (예: player.contract.bonus)")
        if not ko:
            raise ValueError("필드는 --ko 뜻이 필요해요")
        with open(FIELDS, encoding="utf-8") as f:
            reg = json.load(f)
        if c["obj"] not in reg["kinds"]:
            raise ValueError("필드 종류에 없는 객체예요: %s (fields.json kinds: %s)" % (c["obj"], ", ".join(reg["kinds"])))
        if name in reg["fields"]:
            raise ValueError("이미 있는 필드예요: %s" % name)
        f = {"kind": c["obj"]}
        if c.get("via"):
            f["via"] = c["via"]
        f.update(off=c["off"], type=c["type"])
        if c.get("viaCls"):
            f["viaCls"] = c["viaCls"]
        if rng:
            f["range"] = rng
        f.update(desc=ko, source=src, verified=True, write="safe" if tier == "safe" else "no")
        reg["fields"][name] = f
        with open(FIELDS, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False, indent=2) + "\n")
        out = (FIELDS, name)
    subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "m24.py"), "caps"], capture_output=True)
    c["status"] = "promoted-" + tier
    c["promoted"] = {"file": os.path.basename(out[0]), "name": out[1], "time": _now()}
    store(db)
    return out


# ---- 정적 후보 가져오기 ----
def import_scan(path, source="setter 정적 분석"):
    """tools/api_scan.py 결과 {종류: [코드]} -> prop 후보 (이미 write 등록부에 있는 코드는 뺀다). 반환 (더함, 이미 있음, 뺌)"""
    with open(path, encoding="utf-8") as f:
        scan = json.load(f)
    reg = _load(PROPS, {})
    have = set(reg.get("write", {}).get("codes", {})) | set(reg.get("write", {}).get("deny", []))
    added = dup = skipped = 0
    for kind, codes in scan.get("codes", {}).items():
        for code in codes:
            if code in have:
                skipped += 1
                continue
            _, new = add("prop", kind, source, ["setter %s가 코드 비교 (%s)" % (scan.get("setters", {}).get(kind, "?"), scan.get("exe", ""))], code=code)
            added += new
            dup += (not new)
    return added, dup, skipped
