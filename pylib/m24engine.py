"""FM24 매치엔진 표(simatch) 읽기·변환 (DynamicME, 작성: Claude, E03)

- .jsb(게임의 이진 JSON) 읽기·쓰기, 주석(//)·끝 쉼표가 섞인 엔진 팩 .json 읽기
- 게임 설치 폴더의 data/simatch.fmf(또는 data/simatch/ 폴더)에서 원본 표 읽기
- 엔진 팩 표를 "게임 메모리에 들어 있는 모습"으로 바꾸기 (코어 engineDump와 같은 모양)

메모리 배치 근거: logs/메치엔진조정모드 E02 2절·E03. 게임 코드가 아는 열쇠 이름만 쓴다
(모르는 이름은 게임도 무시하거나 0번으로 넣는다: E02 3절).
"""
import json
import os
import re
import struct

# ---------------------------------------------------------------- .jsb

def _rb(path):
    with open(path, "rb") as f:
        return f.read()


def _rt(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()



def jsb_loads(data):
    """게임 .jsb 바이트 -> 파이썬 값. 토큰 1바이트: 아래 4비트 종류, 위 4비트 짧은 크기/값."""
    pos = [0]

    def u8():
        v = data[pos[0]]; pos[0] += 1; return v

    def take(fmt, n):
        v = struct.unpack_from(fmt, data, pos[0])[0]; pos[0] += n; return v

    def size(hi):
        return hi - 1 if hi else take("<I", 4)

    def val():
        b = u8(); t = b & 0xF; hi = b >> 4
        if t == 0xA:
            o = {}
            for _ in range(size(hi)):
                n = u8(); k = data[pos[0]:pos[0] + n].decode("utf8"); pos[0] += n
                o[k] = val()
            return o
        if t == 0x9:
            return [val() for _ in range(size(hi))]
        if t == 0x8:
            n = size(hi); s = data[pos[0]:pos[0] + n].decode("utf8"); pos[0] += n; return s
        if t == 0x2:
            return hi - 8 if hi else take("<i", 4)
        if t == 0x4:
            return hi - 8 if hi else take("<I", 4)
        if t == 0x5:
            return hi - 8 if hi else take("<Q", 8)
        if t == 0x7:
            return float(hi - 1) if hi else take("<d", 8)
        if t == 0x0:
            return None
        raise ValueError("모르는 .jsb 토큰 %02x (위치 %d)" % (b, pos[0] - 1))

    v = val()
    if pos[0] != len(data):
        raise ValueError(".jsb 끝에 남는 바이트 %d" % (len(data) - pos[0]))
    return v


def _jsb_size(t, n, out):
    if n < 15:
        out.append(((n + 1) << 4) | t)
    else:
        out.append(t); out += struct.pack("<I", n)


def _jsb_enc(v, out):
    if isinstance(v, bool):
        raise ValueError("bool은 .jsb 형식을 아직 몰라요")
    if v is None:
        out.append(0)
    elif isinstance(v, dict):
        _jsb_size(0xA, len(v), out)
        for k in sorted(v, key=lambda s: s.encode("utf8")):   # 원본처럼 열쇠를 바이트 순서로
            kb = k.encode("utf8"); out.append(len(kb)); out += kb
            _jsb_enc(v[k], out)
    elif isinstance(v, list):
        _jsb_size(0x9, len(v), out)
        for x in v:
            _jsb_enc(x, out)
    elif isinstance(v, str):
        b = v.encode("utf8"); _jsb_size(0x8, len(b), out); out += b
    elif isinstance(v, int):
        if -7 <= v <= 7:
            out.append(((v + 8) << 4) | 0x2)
        elif -2 ** 31 <= v < 2 ** 31:
            out.append(0x2); out += struct.pack("<i", v)
        elif 0 <= v < 2 ** 32:
            out.append(0x4); out += struct.pack("<I", v)
        else:
            out.append(0x5); out += struct.pack("<Q", v)
    elif isinstance(v, float):
        if v == 0.0 or v == 1.0:   # 원본은 0.0(0x17)·1.0(0x27)만 짧게 쓴다
            out.append(((int(v) + 1) << 4) | 0x7)
        else:
            out.append(0x7); out += struct.pack("<d", v)
    else:
        raise ValueError("모르는 형식 %r" % type(v))


def jsb_dumps(v):
    out = bytearray(); _jsb_enc(v, out); return bytes(out)


def json_loads_loose(text):
    """엔진 팩 .json: // 주석, 끝 쉼표를 허용."""
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    text = re.sub(r'(?m)(?<!:)//[^\n"]*$', "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)

# ---------------------------------------------------------------- .fmf

_ZMAGIC = b"\x28\xb5\x2f\xfd"


def _unzstd(buf):
    try:
        from compression import zstd   # Python 3.14+
        mk = lambda: zstd.ZstdDecompressor()   # noqa: E731
    except ImportError:   # pragma: no cover
        import zstandard
        mk = lambda: zstandard.ZstdDecompressor().decompressobj()   # noqa: E731
    out = []
    while True:
        d = mk(); out.append(d.decompress(buf)); buf = d.unused_data
        if buf[:4] == _ZMAGIC:
            continue
        if buf[4:8] == _ZMAGIC:
            buf = buf[4:]; continue
        break
    return b"".join(out)


def fmf_files(path):
    """.fmf 묶음 -> {경로: 바이트}. 목차 = 마지막 zstd 조각 (M43 fmfx.py와 같은 형식)."""
    d = _rb(path)
    if d[2:6] != b"fmf.":
        raise ValueError("fmf 파일이 아니에요: %s" % path)
    index_off = struct.unpack_from("<Q", d, 9)[0]
    idx = _unzstd(d[d.find(_ZMAGIC, index_off):])
    p = [0]

    def u32():
        v = struct.unpack_from("<I", idx, p[0])[0]; p[0] += 4; return v

    def u64():
        v = struct.unpack_from("<Q", idx, p[0])[0]; p[0] += 8; return v

    def s():
        n = u32(); r = idx[p[0]:p[0] + n].decode("utf8", "replace"); p[0] += n; return r

    files = {}

    def walk(parent):
        name = s(); path_ = (parent + "/" + name) if parent else name
        for _ in range(u32()):
            fn = s(); ext = s(); off = u64(); cs = u64(); us = u64(); u64(); u64()   # ext는 점 포함
            files[path_ + "/" + fn + ext] = (off, cs, us)
        for _ in range(u32()):
            walk(path_)

    walk("")
    out = {}
    for k, (off, cs, us) in files.items():
        raw = d[26 + off:26 + off + cs]   # 자료는 머리(26바이트) 뒤부터
        out[k] = _unzstd(raw[4:]) if raw[4:8] == _ZMAGIC else raw   # 압축된 것은 앞 4바이트(크기) 뒤에 zstd
    return out


# 표 이름 -> simatch 안 파일 이름(확장자 빼고)
TABLE_FILES = {
    "weights": "weights",
    "physics": "physics/physical_constraints",
    "momentum": "momentum_weightings_data",
    "ratings": "player_ratings_data",
    "qme_stat": "qme_stat_relevant_attribute_data",
    "qme_dist": "qme_distribution_data",
    "styles": "tactics/styles",   # .xml (E09)
    "xg": "expected_goals/models",   # 폴더 (버전별 coefficient_output_*.jsb, E10)
}


def styles_parse(text):
    """tactics/styles.xml -> [{folder, code, attr [[번호, 최소, 최대]], tend [...], names {('a'|'t', 번호): 주석 이름}}] (파일 순서 = 게임 메모리 순서).
    게임 메모리에는 tactical_style_id가 있는 스타일만 있어요 (clean_slate 빼고 10개, E09)."""
    import re
    import xml.etree.ElementTree as ET
    root = ET.fromstring(text.lstrip("﻿"))
    out = []
    for st in root.findall("record"):
        if not st.get("tactical_style_id"):
            continue
        d = {"folder": st.get("folder"), "code": st.get("tactical_style_id"), "attr": [], "tend": []}
        for lst in st.findall("list"):
            key = {"attribute_template": "attr", "tendency_template": "tend"}.get(lst.get("id"))
            if not key:
                continue
            for r in lst.findall("record"):
                v = {i.get("id"): i.get("value") for i in r.findall("integer")}
                try:
                    d[key].append([int(r.get("id")), int(v["min"]), int(v["max"])])
                except (KeyError, TypeError, ValueError):
                    continue
        out.append(d)
    names = {}
    for sec, k in (("attribute_template", "a"), ("tendency_template", "t")):
        for blk in re.findall(r'<list id="%s">(.*?)</list>' % sec, text, re.S):
            for c, i in re.findall(r'<!--\s*([A-Z_0-9]+)\s*-->\s*<record id="(\d+)"', blk):
                names[(k, int(i))] = c
    return {"styles": out, "names": {"%s:%d" % k: v for k, v in names.items()}}


# xG 모델 (E10): expected_goals/models/<버전>/coefficient_output_<슛 종류>.jsb. 게임 메모리의 슛 종류 번호 순서
XG_TYPES = ["regular", "volleys", "headers", "free_kicks", "penalties", "open_goal_regular", "open_goal_volleys",
            "open_goal_headers", "obscured_regular", "obscured_volleys", "obscured_headers"]
XG_SCALE = 1e7   # JSON 정수 ÷ 1e7 = 메모리 f32
_XG_RE = r"(?:^|/)expected_goals/models/[^/]+/coefficient_output_([a-z_]+)\.(jsb|json)$"


def _loads_any(b, ext):
    """.jsb 칸에 JSON 글이 든 팩도 있어요 (BOM으로 시작). 둘 다 읽는다."""
    if ext == "jsb":
        try:
            return jsb_loads(b)
        except ValueError:
            pass
    return json_loads_loose(b.decode("utf-8-sig"))


def xg_collect(items):
    """[(경로, 바이트)] -> {"버전 해.릴리스.주.부": {슛 종류: {"intercept", "coefficients"}}} (파일 안 version_number 기준)."""
    import re
    out = {}
    for rel, b in items:
        m = re.search(_XG_RE, rel.replace("\\", "/"))
        if not m or m.group(1) not in XG_TYPES:
            continue
        try:
            o = _loads_any(b, m.group(2))
            v = o["version_number"]
            key = "%d.%d.%d.%d" % (v["version_year"], v["version_release"], v["version_major"], v["version_minor"])
            out.setdefault(key, {})[m.group(1)] = {"intercept": o["intercept"], "coefficients": dict(o["coefficients"])}
        except (KeyError, TypeError, ValueError):
            continue
    return out


def load_pack_table(simatch_dir, table):
    """엔진 팩 폴더(simatch/)에서 표 하나. 없으면 None.
    .jsb와 .json이 둘 다 있으면 .jsb를 쓴다 (게임 원본 형식. 빅토리 엔진 05처럼 둘의 값이 다른 팩이 있어요: pack_notes가 알림)."""
    if table == "xg":
        root = os.path.join(simatch_dir, "expected_goals", "models")
        items = []
        for dp, _, fn in os.walk(root):
            for f in fn:
                if f.startswith("coefficient_output_"):
                    full = os.path.join(dp, f)
                    items.append((os.path.relpath(full, simatch_dir), _rb(full)))
        return xg_collect(items) or None
    base = os.path.join(simatch_dir, *TABLE_FILES[table].split("/"))
    if table == "styles":
        return styles_parse(_rt(base + ".xml")) if os.path.exists(base + ".xml") else None
    if os.path.exists(base + ".jsb"):
        return jsb_loads(_rb(base + ".jsb"))
    if os.path.exists(base + ".json"):
        return json_loads_loose(_rt(base + ".json"))
    return None


def pack_notes(simatch_dir):
    """팩 폴더 자체의 문제: 같은 표가 .json과 .jsb로 둘 다 있고 값이 다를 때."""
    notes = []
    for t, f in TABLE_FILES.items():
        base = os.path.join(simatch_dir, *f.split("/"))
        if os.path.exists(base + ".jsb") and os.path.exists(base + ".json"):
            try:
                a = jsb_dumps(jsb_loads(_rb(base + ".jsb")))
                b = jsb_dumps(json_loads_loose(_rt(base + ".json")))
            except Exception:  # noqa: BLE001
                a, b = 0, 1
            if a != b:
                notes.append(("warn", "%s: .jsb와 .json이 둘 다 있고 값이 달라요. .jsb를 썼어요 (게임 원본 형식)" % f))
    return notes


_OTHER_NAMES = [("tactics/styles.xml", "전술 스타일 (AI 팀 지시 범위)"), ("tactics/", "AI 전술 프리셋"),
                ("expected_goals/", "xG 계수"), ("events/", "경기 해설·사건·소리"), ("physics/ball", "공 물리"),
                ("systems.cfg", "시스템 설정"), ("physics/config.xml", "물리 설정")]


def other_changes(simatch_dir, orig_files):
    """6개 표 밖에서 원본(fmf_files 결과)과 내용이 다른 파일 [(경로, 설명)]. 원본에 없는 새 파일은 뺀다(쓰이지 않음)."""
    okey = {}
    for k, b in orig_files.items():
        okey[os.path.splitext(k[len("simatch/"):])[0]] = (os.path.splitext(k)[1], b)
    skip = set(TABLE_FILES.values())
    out = []
    for dp, _, fn in os.walk(simatch_dir):
        for f in fn:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, simatch_dir).replace(os.sep, "/")
            base, ext = os.path.splitext(rel)
            if base in skip or base not in okey or ("expected_goals/models/" in rel and "/coefficient_output_" in rel):
                continue   # xG 계수는 이제 넣어요 (E10)
            oext, ob = okey[base]
            data = _rb(full)
            try:
                if ext in (".jsb", ".json") and oext in (".jsb", ".json"):
                    same = jsb_dumps(jsb_loads(data) if ext == ".jsb" else json_loads_loose(data.decode("utf-8-sig"))) ==                         jsb_dumps(jsb_loads(ob) if oext == ".jsb" else json_loads_loose(ob.decode("utf-8-sig")))
                else:
                    same = data == ob
            except Exception:  # noqa: BLE001
                same = False
            if not same:
                what = next((n for p, n in _OTHER_NAMES if rel.startswith(p)), "기타")
                out.append((rel, what))
    return sorted(out)


def load_game_original(game_dir):
    """게임 설치 폴더의 원본 표들 {표: 값}. data/simatch.fmf를 읽는다."""
    files = fmf_files(os.path.join(game_dir, "data", "simatch.fmf"))
    out = {}
    for t, f in TABLE_FILES.items():
        for ext in (".jsb", ".json", ".xml"):
            b = files.get("simatch/" + f + ext)
            if b is not None:
                out[t] = (styles_parse(b.decode("utf-8-sig")) if ext == ".xml" else
                          jsb_loads(b) if ext == ".jsb" else json_loads_loose(b.decode("utf-8-sig")))
                break
    out["xg"] = xg_collect(files.items())
    return out

# ---------------------------------------------------------------- 메모리 모양으로

# 선발 가중치: 선발 방식 4개와 요인 39개의 게임 순서 (소스 순서. 메모리 표와 대조해 확인, E03)
WEIGHT_STYLES = ["TEAM_PICKING_STYLE::TPS_FIRST_TEAM_PICKING", "TEAM_PICKING_STYLE::TPS_SLIGHTLY_RESERVE_PICKING",
                 "TEAM_PICKING_STYLE::TPS_SEMI_RESERVE_PICKING", "TEAM_PICKING_STYLE::TPS_TOTAL_RESERVE_PICKING"]
WEIGHT_FACTORS = [
    "POSITION_ABILITY", "POSITION_ABILITY_IN_ROLE", "POSITION_TACTICAL_FAMILARITY", "LOAN_TERMS", "MATCH_RATING_TIME_ON",
    "CONDITION", "ALLOWED_MINS", "CA", "PA", "REPUTATION", "YOUNG_PLAYERS", "MORALE", "TESTIMONIAL", "FOOTBALL_PROMISES",
    "BOOST_LOW_MATCH_FITNESS", "CUP_KEEPER", "PPMS", "HUMAN_SELECTION", "TRIALIST_B_TEAM_PLAYERS", "DECLARED_FOR_RESERVES",
    "CAPTAINCY", "UNHAPPINESS", "INTERNATIONAL_CAPS", "CLUB_NATION_CHOICE_FACTORS", "FORM", "AGREED_PLAYING_TIME",
    "PLAYING_SIDE_PREFERENCE", "MATCH_FITNESS", "BOOST_SUBSTITUTE", "STAR_PLAYER", "OLYMPIC_U23", "REST_PROMISES",
    "UPCOMING_SUSPENSION", "NEED_MATCH_XP", "DISLIKE_BY_NON_PLAYER", "INTEGRATION", "LAST_RATINGS", "VIRTUAL", "EXTRA_ADJ"]

# 물리: 항목 +0xc부터 f32 30개 (값 ÷ 배율), +0x84부터 i16 7개, 최소 지연 map 39개 (250ms 단위)
PHYS_SPEED = ["very_slow_walk_speed", "slow_walk_speed", "walk_speed", "fast_walk_speed", "slow_jog_speed", "jog_speed",
              "moderate_jog_speed", "fast_jog_speed", "run_speed", "sprint_speed", "top_speed", "base_top_speed",
              "theoretical_max_running_speed",
              "soft_kick_speed", "soft_to_medium_kick_speed", "medium_kick_speed", "medium_to_moderate_kick_speed",
              "moderate_kick_speed", "quite_hard_kick_speed", "hard_kick_speed", "very_hard_kick_speed",
              "basic_header_speed", "theoretical_min_diving_speed", "theoretical_max_diving_speed"]
PHYS_ACCEL = ["theoretical_min_acceleration", "theoretical_max_acceleration",
              "theoretical_min_diving_acceleration", "theoretical_max_diving_acceleration",
              "theoretical_min_deceleration", "theoretical_max_deceleration"]
PHYS_I16 = ["theoretical_max_turning_rate",
            "theoretical_max_potential_direction_change_walk", "theoretical_min_potential_direction_change_walk",
            "theoretical_max_potential_direction_change_jog", "theoretical_min_potential_direction_change_jog",
            "theoretical_max_potential_direction_change_run", "theoretical_min_potential_direction_change_run"]
PHYS_DELAYS = [
    "min_delay_for_diving_header", "min_delay_for_normal_header", "min_delay_for_slide_tackle_do",
    "min_delay_for_slide_tackle_receive", "min_delay_for_ball_lunge_do", "min_delay_for_ball_lunge_receive",
    "min_delay_for_block_tackle_do", "min_delay_for_block_tackle_receive", "min_delay_for_deflect_ball_do",
    "min_delay_for_deflect_ball_receive", "min_delay_for_shoulder_charge_do", "min_delay_for_shoulder_charge_receive",
    "min_delay_for_force_opponent_to_lose_ball_do", "min_delay_for_force_opponent_to_lose_ball_receive",
    "min_delay_for_shirt_tug_do", "min_delay_for_shirt_tug_receive", "min_delay_for_obstruct_do",
    "min_delay_for_obstruct_receive", "min_delay_for_two_footed_tackle_do", "min_delay_for_two_footed_tackle_receive",
    "min_delay_for_trip_do", "min_delay_for_trip_receive", "min_delay_for_foot_up_in_tackle_do",
    "min_delay_for_foot_up_in_tackle_receive", "min_delay_for_push_opponent_do", "min_delay_for_push_opponen_receive",
    "min_delay_for_violent_act_do", "min_delay_for_violent_act_receive", "min_delay_for_celebrating_a_goal",
    "min_delay_keeper_save_intentionally_drop_ball", "min_delay_keeper_save_dive_and_hold_ball",
    "min_delay_keeper_save_dive_but_not_held", "min_delay_keeper_save_no_dive_hold_ball",
    "min_delay_keeper_save_no_dive_not_held", "min_delay_keeper_drop_ball_for_distribution",
    "min_delay_keeper_save_with_outreached_foot", "min_extra_delay_for_falling_down_before_injury",
    "min_delay_for_player_stop_to_avoid_collision", "min_delay_for_getting_injured"]
PHYS_KNOWN = set(PHYS_SPEED + PHYS_ACCEL + PHYS_I16 + PHYS_DELAYS + ["speed_scaler", "acceleration_scaler", "min_me_version"])

# 모멘텀: 이름 -> 게임 번호 (정적 초기화 fm+0x1c6fff0, 메모리 대조 E03). 모르는 이름은 게임이 0으로 넣는다
MOM_EVENTS = {"CBE_END_SHOT_GONE_IN": 1, "CBE_END_SHOT_MISSED_TARGET": 2, "CBE_END_SHOT_HIT_WOODWORK": 3,
              "CBE_END_SHOT_SAVED": 4, "CBE_END_SHOT_BLOCKED": 5,   # 4·5는 원본 값이 같아 이름 순서로 정함 (확인 필요)
              "CBE_END_PASS_COMPLETED": 7, "CBE_TOUCH": 54}
MOM_ZONES = {"FIRST_SIXTH": 0, "SECOND_SIXTH": 1, "THIRD_SIXTH": 2, "FOURTH_SIXTH": 3, "FIVTH_SIXTH": 4, "FINAL_SIXTH": 5}
MOM_THIRDS = {"LEFT_THIRD": 0, "CENTRAL_THIRD": 1, "RIGHT_THIRD": 2}


def ver_tuple_me(v):
    """ME_VERSION / min_me_version / version 객체 -> (year, release, major, minor)."""
    g = lambda *ks: next((v[k] for k in ks if k in v), 0)   # noqa: E731
    return (g("ME_PACK_VERSION_YEAR", "version_year"), g("ME_PACK_VERSION_RELEASE", "version_release"),
            g("ME_PACK_VERSION_MAJOR", "version_major"), g("ME_PACK_VERSION_MINOR", "version_minor"))


def weights_entries(data):
    """WEIGHTS 배열 -> [(버전, [int ×156])] (파일 순서)."""
    out = []
    for e in data["WEIGHTS"]:
        ints = []
        for st in WEIGHT_STYLES:
            d = e[st]
            ints += [int(d["simatchshared::TSF_" + f]) for f in WEIGHT_FACTORS]
        out.append((ver_tuple_me(e["ME_VERSION"]), ints))
    return out


def physics_entries(data, base=None):
    """version_array -> [(버전, f32 30개, i16 7개, {지연 번호: 250ms 단위})] (파일 순서).
    팩에 없는 키는 게임처럼 원래 값을 둔다: base(원본 표)의 같은 버전 항목(없으면 첫 항목) 값을 쓴다 (E03 실기:
    명장엔진의 바뀐 이름 키는 원래 값이 남았다). 회전·방향 전환은 게임처럼 정수로 자른다 (168.75 -> 168)."""
    bases = {}
    if base:
        for b in base["version_array"]:
            bases[ver_tuple_me(b["min_me_version"])] = b
    first = base["version_array"][0] if base else {}
    out = []
    for e in data["version_array"]:
        v = ver_tuple_me(e["min_me_version"])
        b = bases.get(v, first)
        get = lambda k: e[k] if k in e else b[k]   # noqa: E731
        ss = float(e.get("speed_scaler", b.get("speed_scaler", 10000)))
        acs = float(e.get("acceleration_scaler", b.get("acceleration_scaler", 10000)))
        f = [get(k) / (ss if k in e or k not in b else float(b.get("speed_scaler", 10000))) for k in PHYS_SPEED]
        f += [get(k) / (acs if k in e or k not in b else float(b.get("acceleration_scaler", 10000))) for k in PHYS_ACCEL]
        s = [int(get(k)) for k in PHYS_I16]
        dl = {}
        for i, k in enumerate(PHYS_DELAYS):
            if k in e or k in b:
                dl[i] = int(get(k)) // 250 if k not in e else _delay_units(e[k])
        out.append((v, f, s, dl))
    return out


def _delay_units(ms):
    """최소 지연 ms -> 게임 250ms 단위 (규칙은 E03 명장엔진 대조로 확인)."""
    return int(round(ms / 250.0))


def momentum_rows(data, events=None):
    """values -> 메모리 줄 [(사건, 구역, 좌우, 점수)] 정렬. 모르는 이름은 게임처럼 0, 같은 칸이 또 나오면 처음 값 (E03 실기)."""
    events = events or MOM_EVENTS
    rows = {}
    for e in data["values"]:
        k = (events.get(e["CBE_EVENT_TYPE"], 0), MOM_ZONES.get(e["VERTICAL_ZONES"], 0), MOM_THIRDS.get(e["HORIZONTAL_THIRDS"], 0))
        rows.setdefault(k, int(e["MOMENTUM"]))
    return sorted(k + (v,) for k, v in rows.items())


def ratings_entries(data):
    """values -> [(버전, start, exp 22개, roles [[i16 ×52]])], 메모리처럼 새 버전부터."""
    out = []
    for e in data["values"]:
        exp = []
        for x in e["expected_score_data"]:
            exp += [x["positive_multiplier"] / 1000.0, x["negative_multiplier"] / 1000.0]
        # -30000 = 그 버전에 없는 계수 표시: 게임은 0으로 넣는다 (옛 항목 Open Play xA, 메모리 대조 E03)
        roles = [[0 if int(c["value"]) == -30000 else int(c["value"]) for c in r["coefficients"]] for r in e["role_data"]]
        out.append((ver_tuple_me(e["version"]), int(e["start_value"]), exp, roles))
    out.sort(key=lambda t: t[0], reverse=True)
    return out


# ---------------------------------------------------------------- 쓰기 계획 (팩 -> 코어 engineWrite)

def _newest(entries):
    return max(entries, key=lambda t: t[0])


def plan(pack, orig, mem):
    """엔진 팩을 지금 게임 메모리에 넣는 계획.
    pack/orig: {표: 값} (load_pack_table / load_game_original), 팩에 없는 표는 빼도 된다.
    mem: {표: engineDump 결과}. 반환 (writes [(표, spec)], notes [(수준, 글)])  수준 = info|warn|skip.
    원칙: 게임이 이미 가진 칸에만 쓴다. 팩이 최신 버전 항목을 지웠으면 게임이 고르는 항목에 팩의 유효 항목을 쓴다."""
    writes, notes = [], []
    if pack.get("weights"):
        pe = weights_entries(pack["weights"]); v, ints = _newest(pe)
        writes.append(("weights", {"entry": 0, "ints": ints}))
        ov = [x for x, _ in weights_entries(orig["weights"])]
        if v != max(ov):
            notes.append(("info", "선발 가중치: 팩이 최신 항목 %s를 지워서 %s 항목 값을 게임이 쓰는 칸에 넣어요" % (max(ov), v)))
    if pack.get("physics"):
        unknown = sorted({k for e in pack["physics"]["version_array"] for k in e} - PHYS_KNOWN)
        if unknown:
            notes.append(("warn", "물리: 게임이 모르는 키라 무시돼요 (게임도 안 읽음): " + ", ".join(unknown)))
        v, f, s, dl = _newest(physics_entries(pack["physics"], orig["physics"]))
        pe_ = max(pack["physics"]["version_array"], key=lambda e: ver_tuple_me(e["min_me_version"]))
        odd = [k for k in PHYS_DELAYS if k in pe_ and float(pe_[k]) % 250]
        if odd:
            notes.append(("warn", "물리: 최소 지연은 0.25초 단위로만 들어가요 (반올림, %d개): %s" % (len(odd), ", ".join(odd))))
        frac = [k for k in PHYS_I16 if k in pe_ and float(pe_[k]) != int(pe_[k])]
        if frac:
            notes.append(("warn", "물리: 회전·방향 전환은 정수만 들어가요 (소수점 버림): " + ", ".join(frac)))
        writes.append(("physics", {"entry": 0, "f32": f, "i16": s, "delays": [[k, x] for k, x in sorted(dl.items())]}))
    if pack.get("momentum"):
        bad = sorted({e[f] for e in pack["momentum"]["values"] for f, tbl in (("CBE_EVENT_TYPE", MOM_EVENTS), ("VERTICAL_ZONES", MOM_ZONES), ("HORIZONTAL_THIRDS", MOM_THIRDS)) if e[f] not in tbl})
        rows = momentum_rows(pack["momentum"])
        have = {tuple(r[:3]) for r in mem["momentum"]["rows"]}
        miss = [r for r in rows if tuple(r[:3]) not in have]
        absent = len(have - {tuple(r[:3]) for r in rows})
        if bad:
            notes.append(("warn", "모멘텀: 게임이 모르는 이름 %s → 게임이 그대로 읽으면 0번 구역(자기 진영 맨 뒤)으로 잘못 들어가요. 그 줄은 빼고 넣어요 (%d줄)" % (", ".join(bad), len(miss))))
        elif miss:
            notes.append(("skip", "모멘텀: 게임 표에 없는 칸 %d줄은 못 넣어요" % len(miss)))
        if absent:
            notes.append(("info", "모멘텀: 팩에 없는 칸 %d줄은 지금 값 그대로 둬요" % absent))
        writes.append(("momentum", {"rows": [list(r) for r in rows if tuple(r[:3]) in have]}))
    if pack.get("ratings"):
        # 메모리 항목 순서 = 원본 항목을 새 버전부터 정렬한 순서. 버전을 막은(255) 뒤에도 같은 칸을 찾도록 원본 버전으로 칸을 정한다
        pe = ratings_entries(pack["ratings"]); oe = ratings_entries(orig["ratings"]); mv = mem["ratings"]["entries"]
        newest = max(t[0] for t in pe)
        for i, m in enumerate(mv):
            if i >= len(oe):
                break
            ov = oe[i][0]
            hit = next((t for t in pe if t[0] == ov), None)
            if hit and len(hit[3]) == len(m["roles"]):
                writes.append(("ratings", {"entry": i, "ver": list(ov), "start": hit[1], "exp": hit[2], "roles": hit[3]}))
            elif hit:
                notes.append(("skip", "평점: %s 항목의 역할 수가 달라 못 넣어요 (팩 %d, 게임 %d)" % (ov, len(hit[3]), len(m["roles"]))))
            elif ov > newest:
                writes.append(("ratings", {"entry": i, "ver": [255, 255, 255, 255]}))   # 게임이 고르지 않게
                notes.append(("info", "평점: 팩이 지운 최신 항목 %s는 게임이 고르지 않게 막아요 → %s 항목이 쓰여요" % (ov, newest)))
            else:
                writes.append(("ratings", {"entry": i, "ver": list(ov)}))   # 팩에 없는 옛 항목: 원본 버전만 되살림
    if pack.get("xg"):
        w, n2 = xg_plan(pack["xg"], (mem or {}).get("xg"))
        writes += w
        notes += n2
    if pack.get("styles"):
        w, n2 = styles_plan(pack["styles"], (mem or {}).get("styles"))
        writes += w
        notes += n2
    notes += _unused_entry_notes(pack, orig)
    return writes, notes   # QME 두 표는 메모리 대신 엔진 폴더 파일로 (qme_sync, 재시작 필요, E11)


QME_TABLES = ("qme_stat", "qme_dist")


def simatch_folder(game_dir):
    """게임이 simatch.fmf 대신 읽는 엔진 폴더 data/simatch (있고 QME 파일이 있을 때만). E02: 폴더가 있으면 fmf 전체를 대신해요."""
    d = os.path.join(game_dir, "data", "simatch")
    ok = os.path.isdir(d) and any(os.path.exists(os.path.join(d, TABLE_FILES["qme_dist"] + e)) for e in (".jsb", ".json"))
    return d if ok else None


def qme_notes(pack, orig):
    """QME 표에서 게임이 모르는 이름 (원본에 없는 기록 종류·포지션·분포 종류). 게임은 그 항목을 버려요 (E11: 명장엔진이 기록 이름 3개를 바꿔 22개 중 20개만 들어감)."""
    notes = []
    st, dist = pack.get("qme_stat"), pack.get("qme_dist")
    known = {v["stat_type"] for v in orig["qme_stat"]["values"]}
    if st is not None:
        bad = sorted({v.get("stat_type") for v in st.get("values", [])} - known)
        if bad:
            notes.append(("warn", "QME 기록-능력치 표: 게임이 모르는 기록 이름 %s → 게임이 그 항목을 버려요 (원본 이름: %s)"
                          % (", ".join(map(str, bad)), ", ".join(sorted(known - {v.get("stat_type") for v in st.get("values", [])})))))
    if dist is not None:
        for f in ("stat_type", "position", "distribution_type"):
            k = {e[f] for e in orig["qme_dist"]}
            bad = sorted({e.get(f) for e in dist} - k, key=str)
            if bad:
                notes.append(("warn", "QME 분포 표: 게임이 모르는 %s %s → 그 줄은 버려져요" % (f, ", ".join(map(str, bad)))))
    return notes


def qme_sync(game_dir, target, orig):
    """QME 두 표(빠른 경기의 선수 기록 표): 표 모양이 팩마다 달라 메모리에 바로 못 쓴다.
    게임은 시작할 때 엔진 폴더에서 읽으므로, 그 폴더의 파일을 target(없으면 원본) 내용으로 맞춘다. 다음 게임 시작부터 적용.
    반환 (바꾼 파일 목록, notes)."""
    want = {t: (target or {}).get(t) if (target or {}).get(t) is not None else orig.get(t) for t in QME_TABLES}
    differs = any(want[t] is not None and orig.get(t) is not None and jsb_dumps(want[t]) != jsb_dumps(orig[t]) for t in QME_TABLES)
    d = simatch_folder(game_dir)
    if not d:
        return [], ([("skip", "QME(빠른 경기 선수 기록 표): 게임 폴더에 엔진 폴더(data\\simatch)가 없어 못 넣어요")] if differs else [])
    changed = []
    for t in QME_TABLES:
        if want[t] is None:
            continue
        base = os.path.join(d, *TABLE_FILES[t].split("/"))
        path = base + ".jsb" if os.path.exists(base + ".jsb") else base + ".json"
        data = jsb_dumps(want[t]) if path.endswith(".jsb") else json.dumps(want[t], ensure_ascii=False).encode("utf-8")
        try:
            cur = _rb(path)
        except OSError:
            cur = None
        if cur == data:
            continue
        if cur is not None and path.endswith(".json"):
            try:
                if json_loads_loose(cur.decode("utf-8-sig")) == want[t]:
                    continue
            except ValueError:
                pass
        with open(path, "wb") as f:
            f.write(data)
        changed.append(os.path.basename(path))
    notes = [("warn", "QME(빠른 경기 선수 기록 표): 엔진 폴더 파일을 %s 바꿨어요 (%s). **게임을 다시 켜야** 적용돼요"
              % ("팩 내용으로" if differs else "원본으로", ", ".join(changed)))] if changed else []
    return changed, notes


def _unused_entry_notes(pack, orig):
    """팩이 게임이 쓰지 않는 옛 버전 항목만 바꿨는지 알린다 (빅토리 엔진 06 BALANCED FIX가 물리 버전 0 항목만 고침, E05).
    게임은 경기 엔진 버전 이하 중 가장 새 항목을 쓴다 (FM24에서는 물리 22.6.0.2, 가중치 24 항목: E02 읽기 감시)."""
    notes = []
    for t, arr, vk in (("physics", "version_array", "min_me_version"), ("weights", "WEIGHTS", "ME_VERSION")):
        if not pack.get(t) or not orig.get(t):
            continue
        pe = {ver_tuple_me(e[vk]): e for e in pack[t][arr]}
        oe = {ver_tuple_me(e[vk]): e for e in orig[t][arr]}
        newest = max(pe)
        old = [v for v in pe if v != newest and v in oe and jsb_dumps(pe[v]) != jsb_dumps(oe[v])]
        if old:
            notes.append(("warn", "%s: 팩이 바꾼 옛 버전 항목 %s은 게임이 쓰지 않아요 (쓰이는 건 %s 항목). 그 변경은 효과가 없어요"
                          % ({"physics": "물리", "weights": "선발 가중치"}[t], ", ".join(".".join(map(str, v)) for v in old), ".".join(map(str, newest)))))
    return notes


STYLES_WAIT = "전술 스타일: 게임이 아직 불러오지 않았어요 (세이브를 불러온 뒤 첫 진행일에 불러와요). 불러오면 모드가 바로 넣어요"


def styles_plan(target, mem):
    """전술 스타일 쓰기 계획. target = styles_parse 결과, mem = engineDump('styles') (없거나 error면 기다림).
    메모리와 다른 스타일만 쓴다. 반환 (writes, notes)."""
    if not mem or mem.get("error") or not mem.get("styles"):
        return [], [("info", STYLES_WAIT)]
    have = {s["folder"]: s for s in mem["styles"]}
    out, notes, bad = [], [], []
    for s in target["styles"]:
        m = have.get(s["folder"])
        if not m:
            notes.append(("skip", "전술 스타일 %s: 게임 메모리에 없는 스타일이라 못 넣어요" % s["folder"]))
            continue
        spec = {"folder": s["folder"]}
        for k in ("attr", "tend"):
            rows = [[x & 0xff for x in r] for r in s[k] if all(-128 <= x <= 255 for x in r)]   # 메모리는 u8: -1 = 255 (원본 거친 태클 허용 -1)
            bad += [r for r in s[k] if not all(-128 <= x <= 255 for x in r)]
            if rows != [list(r) for r in m[k]]:
                spec[k] = rows
        if len(spec) > 1:
            out.append(spec)
    if bad:
        notes.append(("warn", "전술 스타일: -128~255 밖 값이 든 항목 %d개는 뺐어요" % len(bad)))
    return ([("styles", {"styles": out})] if out else []), notes


def _f32(x):
    import struct
    return struct.unpack("<f", struct.pack("<f", x))[0]


def xg_f32(v):
    """JSON 정수 -> 게임과 같은 f32: float(v) / float(1e7)을 f32로 (E10: 원본 110줄이 1비트도 안 다름. 배정밀도로 나누면 28줄이 1 ulp 다름)."""
    return _f32(_f32(v) / _f32(XG_SCALE))


def xg_plan(target, mem):
    """xG 쓰기 계획. target = xg_collect 결과, mem = engineDump('xg'). 메모리와 다른 값만, 계수 수가 같은 줄만."""
    if mem is None:
        return [], []   # 메모리를 안 읽은 호출 (시험 등)
    if mem.get("error"):
        return [], [("skip", "xG: 게임의 xG 표를 읽지 못했어요 (%s)" % mem.get("error"))]
    models, notes = [], []
    for m in mem.get("models", []):
        key = ".".join(map(str, m["ver"]))
        t = target.get(key)
        if not t:
            continue
        spec = {"ver": m["ver"], "coef": {}, "icpt": {}}
        for st, d in t.items():
            ti = str(XG_TYPES.index(st))
            if ti in m["icpt"]:
                v = xg_f32(d["intercept"])
                if v != m["icpt"][ti]:
                    spec["icpt"][ti] = v
            if ti in m["coef"]:
                vals = [xg_f32(d["coefficients"][k]) for k in sorted(d["coefficients"])]
                if len(vals) != len(m["coef"][ti]):
                    notes.append(("skip", "xG %s %s: 계수 수가 달라 못 넣어요 (팩 %d, 게임 %d)" % (key, st, len(vals), len(m["coef"][ti]))))
                elif vals != m["coef"][ti]:
                    spec["coef"][ti] = vals
        if spec["coef"] or spec["icpt"]:
            models.append(spec)
    return ([("xg", {"models": models})] if models else []), notes


def restore_plan(orig, mem):
    """원본(simatch.fmf)으로 되돌리는 계획 (평점 항목의 버전 번호도 되돌린다)."""
    return plan({t: orig.get(t) for t in ("weights", "physics", "momentum", "ratings", "styles", "xg")}, orig, mem)[0]
