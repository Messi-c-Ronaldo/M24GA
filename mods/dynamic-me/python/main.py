"""DynamicME PC 쪽 (작성: Claude, E04).

- 엔진 팩·조절값 -> pylib/m24engine.plan() -> 게임 쪽 JS(api.engine.write)로 쓰기
- 원본 = 게임 설치 폴더의 data/simatch.fmf (ctx.game_dir()). 파일은 바꾸지 않는다
- 상태(state.json): {"pack": {"path", "name"} 또는 None, "tune": {조절값}} — 게임에 붙을 때 다시 넣는다 (설정 reapply)
"""
import json
import os
import threading

import m24engine as E
import dme_tune as T
import dme_detail as D

TABLES = ("weights", "physics", "momentum", "ratings")
STYLES = "styles"   # 전술 스타일: 게임이 첫 진행일에 불러와서, 없을 수 있어요 (E09)
XG = "xg"           # xG 모델 계수·절편 (E10)
EXTRA = (STYLES, XG)

_ctx = None
_lock = threading.Lock()
_waiters = {}
_seq = [0]
_orig = {"dir": None, "tables": None, "files": None}
_last = {"result": None, "notes": [], "busy": False}


# ---------------------------------------------------------------- 게임과 주고받기

def _request(msg, timeout=30.0):
    """게임 쪽 JS에 요청 하나 보내고 답을 기다린다 (run 루프가 답을 전해 준다)."""
    with _lock:
        _seq[0] += 1
        mid = _seq[0]
        slot = {"ev": threading.Event(), "res": None}
        _waiters[mid] = slot
    msg = dict(msg, id=mid)
    if not _ctx.post(msg):
        _waiters.pop(mid, None)
        raise RuntimeError("게임에 연결돼 있지 않아요 (게임을 켜고 세이브를 불러온 뒤 다시)")
    if not slot["ev"].wait(timeout):
        _waiters.pop(mid, None)
        raise RuntimeError("게임이 답하지 않아요")
    _waiters.pop(mid, None)
    return slot["res"]


def _dump():
    r = _request({"t": "dump"})
    tables = (r or {}).get("tables") or {}
    for t in TABLES:
        x = tables.get(t)
        if not x or x.get("error"):
            raise RuntimeError("%s 표를 읽지 못했어요: %s" % (t, (x or {}).get("error")))
    return tables   # styles는 error일 수 있어요 (아직 안 불러옴): plan이 알림을 붙이고 나중에 넣어요


def _write(writes):
    r = _request({"t": "write", "writes": writes}, timeout=60.0)
    errs = [x.get("error") for x in (r or {}).get("results") or [] if x and x.get("error")]
    n = sum((x or {}).get("written", 0) for x in (r or {}).get("results") or [])
    if errs:
        raise RuntimeError(errs[0])
    return n


# ---------------------------------------------------------------- 원본, 팩, 상태

def _original():
    gd = _ctx.game_dir()
    if not gd:
        raise RuntimeError("게임 설치 폴더를 아직 몰라요 (게임에 한 번 붙은 뒤 다시)")
    if not os.path.isfile(os.path.join(gd, "data", "simatch.fmf")):
        raise RuntimeError("게임 원본 엔진 파일이 없어요: %s\n엔진을 설치하면서 simatch.fmf를 지우거나 이름을 바꿨다면 원래대로 돌려 주세요 "
                           "(Steam: 속성 > 설치된 파일 > 무결성 검사, Epic: 라이브러리 > ... > 관리 > 확인). "
                           "data\\simatch 폴더는 그대로 둬도 돼요." % os.path.join(gd, "data", "simatch.fmf"))
    if _orig["dir"] != gd or _orig["tables"] is None:
        _orig["tables"] = E.load_game_original(gd)
        _orig["files"] = E.fmf_files(os.path.join(gd, "data", "simatch.fmf"))
        _orig["dir"] = gd
    return _orig["tables"]


def _packs_dir():
    d = (_ctx.settings().get("packs_dir") or "").strip()
    if not d:
        d = os.path.join(_documents_dir(), "M24GA", "engines")
    os.makedirs(d, exist_ok=True)
    return d


def _documents_dir():
    """문서 폴더 (OneDrive로 옮겨져 있어도 실제 위치)."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
            return buf.value
    except (AttributeError, OSError):
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


_ZIP_EXT = (".json", ".jsb", ".xml", ".cfg")   # 엔진 표만 푼다 (해설 소리 같은 큰 파일은 안 풂)
_ZIP_MAX_FILE = 64 * 1024 * 1024
_ZIP_MAX_TOTAL = 256 * 1024 * 1024


def _zip_dir(zpath):
    """zip 팩을 모드 데이터 폴더 아래(zips/<해시>)에 풀고 그 폴더를 돌려준다 (같은 zip은 다시 안 풂). 경로를 벗어나는 항목은 건너뛴다."""
    import hashlib
    import shutil
    import zipfile
    st = os.stat(zpath)
    key = hashlib.sha1(("%s|%d|%d" % (os.path.abspath(zpath), st.st_size, int(st.st_mtime))).encode("utf8")).hexdigest()[:12]
    dest = os.path.join(_ctx.data_dir, "zips", key)
    if os.path.exists(os.path.join(dest, ".ok")):
        return dest
    tmp = dest + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    root = os.path.realpath(tmp)
    total = 0
    with zipfile.ZipFile(zpath) as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.lower().endswith(_ZIP_EXT):
                continue
            target = os.path.realpath(os.path.join(tmp, info.filename))
            if not target.startswith(root + os.sep):
                continue   # ../ 로 밖을 가리키는 항목
            if info.file_size > _ZIP_MAX_FILE or total + info.file_size > _ZIP_MAX_TOTAL:
                raise RuntimeError("zip이 너무 커요 (엔진 표 파일만 %d MB까지 풀어요)" % (_ZIP_MAX_TOTAL // 1048576))
            total += info.file_size
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    with open(os.path.join(tmp, ".ok"), "w") as f:
        f.write("ok")
    shutil.rmtree(dest, ignore_errors=True)
    os.rename(tmp, dest)
    return dest


def _simatch_dir(path):
    """팩 경로 -> 엔진 파일이 든 폴더 (simatch 폴더가 안에 있으면 그것). .zip이면 풀어서."""
    path = os.path.abspath(os.path.expanduser(path.strip().strip('"')))
    if path.lower().endswith(".zip") and os.path.isfile(path):
        path = _zip_dir(path)
    for cand in (os.path.join(path, "simatch"), path):
        if os.path.isdir(cand) and any(os.path.exists(os.path.join(cand, *E.TABLE_FILES[t].split("/")) + ext)
                                       for t in E.TABLE_FILES for ext in (".json", ".jsb")):
            return cand
    return None


def _load_pack(path):
    sd = _simatch_dir(path)
    if not sd:
        raise RuntimeError("엔진 파일(weights, physics 등)이 든 simatch 폴더를 찾지 못했어요: %s" % path)
    return {t: E.load_pack_table(sd, t) for t in E.TABLE_FILES}, sd


def _state_path():
    return os.path.join(_ctx.data_dir, "state.json")


def _state():
    try:
        with open(_state_path(), encoding="utf8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        s = {}
    return {"pack": s.get("pack"), "tune": T.clean(s.get("tune")), "detail": D.clean(s.get("detail"))}


def _save_state(s):
    os.makedirs(_ctx.data_dir, exist_ok=True)
    with open(_state_path(), "w", encoding="utf8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


def _base(state):
    """상태의 기준 표: 고른 팩(팩에 없는 표는 원본), 조정 전. 반환 (기준, 원본)."""
    orig = _original()
    base = {t: orig.get(t) for t in TABLES + EXTRA}
    if state.get("pack"):
        pack, _ = _load_pack(state["pack"]["path"])
        for t in TABLES + EXTRA:
            if pack.get(t) is not None:
                base[t] = pack[t]
        for t in ("qme_stat", "qme_dist"):
            base[t] = pack.get(t)
    return base, orig


def _target(state):
    """상태 -> 게임에 넣을 전체 표: 기준 → 빠른 조정(배율) → 세부 값(덮어쓰기)."""
    base, orig = _base(state)
    return D.apply(T.apply(base, state.get("tune")), state.get("detail")), orig


def _apply_state(state):
    """상태를 게임 메모리에 넣는다. 반환 (쓴 칸 수, notes)."""
    tables, orig = _target(state)
    mem = _dump()
    writes, notes = E.plan(tables, orig, mem)
    n = _write(writes)
    _, qn = E.qme_sync(_ctx.game_dir(), tables, orig)   # QME는 엔진 폴더 파일로 (재시작 필요, E11)
    return n, notes + qn


def _diff_counts(a, b):
    """두 표 묶음(원본, 대상)의 게임이 쓰는 항목 기준 바뀐 값 수."""
    out = {}
    try:
        wa, wb = E.weights_entries(a["weights"]), E.weights_entries(b["weights"])
        out["선발 가중치"] = sum(x != y for x, y in zip(max(wa)[1], max(wb)[1]))
    except Exception:  # noqa: BLE001
        pass
    try:
        pa = max(E.physics_entries(a["physics"], a["physics"]), key=lambda t: t[0])
        pb = max(E.physics_entries(b["physics"], a["physics"]), key=lambda t: t[0])
        out["선수 물리"] = (sum(abs(x - y) > 1e-6 for x, y in zip(pa[1], pb[1])) + sum(x != y for x, y in zip(pa[2], pb[2]))
                         + sum(pa[3].get(k) != pb[3].get(k) for k in set(pa[3]) | set(pb[3])))
    except Exception:  # noqa: BLE001
        pass
    try:
        ma = {r[:3]: r[3] for r in E.momentum_rows(a["momentum"])}
        mb = {r[:3]: r[3] for r in E.momentum_rows(b["momentum"])}
        out["모멘텀"] = sum(ma.get(k) != mb.get(k) for k in set(ma) | set(mb))
    except Exception:  # noqa: BLE001
        pass
    try:
        ra = {t[0]: t for t in E.ratings_entries(a["ratings"])}
        rb = {t[0]: t for t in E.ratings_entries(b["ratings"])}
        n = 0
        for v in set(ra) | set(rb):
            x, y = ra.get(v), rb.get(v)
            if not x or not y:
                n += 1
                continue
            n += sum(p != q for r1, r2 in zip(x[3], y[3]) for p, q in zip(r1, r2)) + (x[1] != y[1])
        out["경기 평점"] = n
    except Exception:  # noqa: BLE001
        pass
    try:
        out["xG 모델"] = xg_diff(a.get(XG), b.get(XG))
    except Exception:  # noqa: BLE001
        pass
    try:
        out["전술 스타일"] = styles_diff(a.get(STYLES), b.get(STYLES))
    except Exception:  # noqa: BLE001
        pass
    return out


def xg_diff(a, b):
    """두 xg_collect 결과의 바뀐 값 수 (절편·계수 하나하나)."""
    if not a or not b:
        return 0
    n = 0
    for v, types in b.items():
        for st, d in types.items():
            o = (a.get(v) or {}).get(st)
            if not o:
                continue
            n += (o["intercept"] != d["intercept"]) + sum(o["coefficients"].get(k) != x for k, x in d["coefficients"].items())
    return n


def _highlights(orig, full):
    """미리보기용 대표 값 비교: 원본 -> 팩 (달라진 것만)."""
    out = []
    try:
        po = D._newest(orig["physics"]["version_array"], "min_me_version")
        pn = D._newest(full["physics"]["version_array"], "min_me_version")
        for k, label in (("top_speed", "최고 속도"), ("sprint_speed", "전력질주 속도"), ("hard_kick_speed", "강한 킥 세기"), ("basic_header_speed", "헤더 공 속도")):
            if k in po and k in pn and abs(po[k] - pn[k]) > 1e-9:
                out.append({"label": label + " (m/s)", "orig": round(po[k] / 1e4, 3), "new": round(pn[k] / 1e4, 3)})
    except Exception:  # noqa: BLE001
        pass
    try:
        def fk(t):
            x = (t or {}).get("xg") or {}
            return x[max(x, key=lambda v: tuple(map(int, v.split("."))))]["free_kicks"]["intercept"] / E.XG_SCALE
        a, b = fk(orig), fk(full)
        if abs(a - b) > 1e-6:
            out.append({"label": "직접 프리킥 xG 절편", "orig": round(a, 3), "new": round(b, 3)})
    except Exception:  # noqa: BLE001
        pass
    return out


def styles_diff(a, b):
    """두 styles_parse 결과의 바뀐 칸 수 (최소·최대 하나하나, 새 항목은 2칸)."""
    if not a or not b:
        return 0
    n = 0
    sa = {s["folder"]: s for s in a["styles"]}
    for s in b["styles"]:
        o = sa.get(s["folder"]) or {"attr": [], "tend": []}
        for k in ("attr", "tend"):
            om = {r[0]: r for r in o[k]}
            bm = {r[0]: r for r in s[k]}
            for i in set(om) | set(bm):
                x, y = om.get(i), bm.get(i)
                n += 2 if not x or not y else (x[1] != y[1]) + (x[2] != y[2])
    return n


# ---------------------------------------------------------------- 모드창 (m24.call)

def ui_status():
    s = _state()
    g = _ctx.game() if _ctx else None
    return {"connected": bool(g), "date": (g or {}).get("date"), "pack": s.get("pack"), "tune": s.get("tune"), "detail": s.get("detail"),
            "last": _last, "packs_dir": _packs_dir() if _ctx else None}


def ui_knobs():
    return [{k: v for k, v in d.items() if k in ("key", "label", "group", "level", "min", "max", "help")} for d in T.KNOBS]


def ui_packs():
    root = _packs_dir()
    out = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p) and _simatch_dir(p):
            out.append({"name": name, "path": p})
        elif os.path.isfile(p) and name.lower().endswith(".zip"):
            out.append({"name": name[:-4] + " (zip)", "path": p})
    return {"dir": root, "packs": out}


def ui_preview(path):
    pack, sd = _load_pack(path)
    orig = _original()
    full = {t: (pack.get(t) if pack.get(t) is not None else orig.get(t)) for t in TABLES + EXTRA}
    full.update({t: pack.get(t) for t in ("qme_stat", "qme_dist")})
    mem = _dump()
    writes, notes = E.plan(full, orig, mem)
    notes = E.pack_notes(sd) + notes
    notes += E.qme_notes(pack, orig)
    if any(pack.get(t) is not None and E.jsb_dumps(pack[t]) != E.jsb_dumps(orig[t]) for t in E.QME_TABLES):
        notes.append(("warn" if E.simatch_folder(_ctx.game_dir()) else "skip",
                      "QME(빠른 경기 선수 기록 표): 표 모양이 달라 엔진 폴더 파일로 넣어요. 적용 뒤 게임을 다시 켜야 반영돼요"
                      if E.simatch_folder(_ctx.game_dir()) else "QME(빠른 경기 선수 기록 표): 게임 폴더에 엔진 폴더(data\\simatch)가 없어 못 넣어요"))
    other = E.other_changes(sd, _orig["files"])
    if other:
        kinds = {}
        for rel, what in other:
            kinds.setdefault(what, []).append(rel)
        for what, rels in kinds.items():
            notes.append(("skip", "%s: 아직 못 넣어요 (%s)" % (what, ", ".join(rels[:3]) + (" 외 %d개" % (len(rels) - 3) if len(rels) > 3 else ""))))
    return {"folder": sd, "tables": [t for t in E.TABLE_FILES if pack.get(t) is not None],
            "changes": _diff_counts(orig, full), "highlights": _highlights(orig, full), "notes": notes, "writes": len(writes)}


def _run_apply(state, what):
    _last["busy"] = True
    try:
        n, notes = _apply_state(state)
        _save_state(state)
        _last.update(result="%s: 칸 %d개를 썼어요" % (what, n), notes=notes)
        _ctx.log("%s (칸 %d개)" % (what, n))
        return {"ok": True, "written": n, "notes": notes}
    finally:
        _last["busy"] = False


def ui_apply(path):
    s = _state()
    sd = _simatch_dir(path)
    if not sd:
        raise RuntimeError("엔진 파일이 든 폴더가 아니에요: %s" % path)
    if path.strip().strip('"').lower().endswith(".zip"):
        name = os.path.splitext(os.path.basename(path.strip().strip('"')))[0]
    else:
        name = os.path.basename(os.path.dirname(sd)) if os.path.basename(sd).lower() == "simatch" else os.path.basename(sd)
    s["pack"] = {"path": path, "name": name}
    return _run_apply(s, "엔진 팩 적용 '%s'" % name)


def ui_tune(tune):
    s = _state()
    s["tune"] = T.clean(tune)
    return _run_apply(s, "조정 적용 (%d개)" % len(s["tune"]))


# ---------------------------------------------------------------- 프리셋 (내가 바꾼 숫자만 담은 작은 파일: 빠른 조정 + 세부 값)
# 게임 원본이 든 엔진 팩이 아니라 내가 고른 숫자만 들어서, 파일로 주고받아도 원본 재배포가 아니에요. 팩은 담지 않아요 (경로가 PC마다 달라서).

PRESET_FORMAT = "dynamic-me-preset"


def _presets_dir():
    d = os.path.join(_ctx.data_dir, "presets")
    os.makedirs(d, exist_ok=True)
    return d


def _preset_name(name):
    n = "".join(c for c in str(name or "").strip() if c.isalnum() or c in " -_()")[:40].strip()
    if not n:
        raise RuntimeError("프리셋 이름을 넣어 주세요 (글자·숫자·공백·-_()만 써요)")
    return n


def _preset_load(path):
    with open(path, encoding="utf8") as f:
        d = json.load(f)
    if not isinstance(d, dict) or d.get("format") != PRESET_FORMAT:
        raise RuntimeError("DynamicME 프리셋 파일이 아니에요")
    return {"tune": T.clean(d.get("tune")), "detail": D.clean(d.get("detail"))}


def ui_presets():
    root = _presets_dir()
    out = []
    for f in sorted(os.listdir(root)):
        if f.lower().endswith(".json"):
            try:
                x = _preset_load(os.path.join(root, f))
            except (OSError, ValueError, RuntimeError):
                continue
            out.append({"name": f[:-5], "tune": len(x["tune"]), "detail": len(x["detail"])})
    return {"dir": root, "presets": out}


def ui_preset_save(name):
    s = _state()
    if not s["tune"] and not s["detail"]:
        raise RuntimeError("저장할 조정이 없어요 (빠른 조정이나 세부 값을 먼저 적용해 주세요)")
    n = _preset_name(name)
    path = os.path.join(_presets_dir(), n + ".json")
    with open(path, "w", encoding="utf8") as f:
        json.dump({"format": PRESET_FORMAT, "version": 1, "tune": s["tune"], "detail": s["detail"]}, f, ensure_ascii=False, indent=1)
    return {"ok": True, "name": n, "path": path}


def ui_preset_apply(name):
    x = _preset_load(os.path.join(_presets_dir(), _preset_name(name) + ".json"))
    s = _state()
    s["tune"], s["detail"] = x["tune"], x["detail"]   # 팩은 그대로 둔다
    return _run_apply(s, "프리셋 '%s' 적용 (조정 %d, 세부 값 %d)" % (name, len(x["tune"]), len(x["detail"])))


def ui_preset_delete(name):
    path = os.path.join(_presets_dir(), _preset_name(name) + ".json")
    if os.path.exists(path):
        os.remove(path)
    return {"ok": True}


def ui_preset_import(path):
    """다른 사람이 준 프리셋 파일을 내 프리셋 목록에 넣는다."""
    src = os.path.abspath(os.path.expanduser(str(path).strip().strip('"')))
    x = _preset_load(src)
    n = _preset_name(os.path.splitext(os.path.basename(src))[0])
    dest = os.path.join(_presets_dir(), n + ".json")
    with open(dest, "w", encoding="utf8") as f:
        json.dump({"format": PRESET_FORMAT, "version": 1, "tune": x["tune"], "detail": x["detail"]}, f, ensure_ascii=False, indent=1)
    return {"ok": True, "name": n}


def ui_search(q):
    """세부 값 전체에서 이름·키에 q가 든 항목 (최대 80개). 묶음을 펼치지 않고 바로 값을 넣게."""
    q = str(q or "").strip().lower()
    if not q:
        return []
    base, orig = _base(_state())
    out = []
    for sec in D.SECTIONS:
        for it in D.items(sec["id"], base, orig):
            if q in it["label"].lower() or q in str(it["key"]).lower():
                out.append(dict(it, section=sec["label"]))
                if len(out) >= 80:
                    return out
    return out


def ui_sections():
    """세부 값 묶음 + 묶음마다 항목 id (모드창이 접힌 묶음에도 바꾼 개수를 보이게)."""
    base, orig = _base(_state())
    return [dict(sec, ids=[it["id"] for it in D.items(sec["id"], base, orig)]) for sec in D.SECTIONS]


def ui_detail(section):
    base, orig = _base(_state())
    return D.items(section, base, orig)


def ui_detail_set(detail):
    s = _state()
    s["detail"] = D.clean(detail)
    return _run_apply(s, "세부 값 적용 (%d개)" % len(s["detail"]))


def ui_restore():
    s = {"pack": None, "tune": {}, "detail": {}}
    return _run_apply(s, "원본으로")


def ui_unpack():
    """팩만 빼고 조정은 남긴다."""
    s = _state()
    s["pack"] = None
    return _run_apply(s, "팩 빼기")


# ---------------------------------------------------------------- 루프

def _reapply_later():
    def go():
        try:
            s = _state()
            if not s.get("pack") and not s.get("tune") and not s.get("detail"):
                return
            if not _ctx.settings().get("reapply", True):
                _ctx.log("다시 적용 꺼 둠: 게임은 원본 엔진이에요")
                return
            n, _ = _apply_state(s)
            _last.update(result="게임에 붙어서 다시 적용: 칸 %d개" % n)
            _ctx.log("다시 적용했어요 (칸 %d개, 팩 %s, 조정 %d개)" % (n, (s.get("pack") or {}).get("name"), len(s.get("tune") or {})))
        except Exception as e:  # noqa: BLE001
            _last.update(result="다시 적용 실패: %s" % e)
            _ctx.log("다시 적용 실패: %s" % e)
    threading.Thread(target=go, daemon=True).start()


def _styles_ready(key):
    """게임이 전술 스타일을 (다시) 불러왔다: 상태의 스타일만 다시 넣는다. 끝나면 JS에 styles_done (실패하면 JS가 다시 알림)."""
    def go():
        try:
            s = _state()
            if (s.get("pack") or s.get("tune") or s.get("detail")) and _ctx.settings().get("reapply", True):
                tables, _ = _target(s)
                w, notes = E.styles_plan(tables.get(STYLES), _dump().get(STYLES))
                if any(lvl == "info" and txt == E.STYLES_WAIT for lvl, txt in notes):
                    return
                n = _write(w) if w else 0
                if n:
                    _last.update(result="전술 스타일을 불러와서 넣었어요: 칸 %d개" % n)
                    _ctx.log("전술 스타일 넣음 (칸 %d개)" % n)
            _ctx.post({"t": "styles_done", "key": key})
        except Exception as e:  # noqa: BLE001
            if "진행 중" not in str(e):   # 게임이 하루를 처리하는 중이면 조용히 10초 뒤 다시 (JS가 다시 알림)
                _ctx.log("전술 스타일을 아직 못 넣었어요 (다시 해요): %s" % e)
    threading.Thread(target=go, daemon=True).start()


def run(ctx):
    global _ctx
    _ctx = ctx
    ctx.log("시작")
    while not ctx.stop.is_set():
        m = ctx.recv(0.5)
        if not m:
            continue
        t = m.get("t")
        if t in ("dump", "written"):
            slot = _waiters.get(m.get("id"))
            if slot:
                slot["res"] = m
                slot["ev"].set()
        elif t == "hello":
            _reapply_later()
        elif t == "styles_ready":
            _styles_ready(m.get("key"))


def status():
    s = _state() if _ctx else {}
    return {"팩": (s.get("pack") or {}).get("name") or "원본", "조정": len(s.get("tune") or {}), "세부 값": len(s.get("detail") or {})}
