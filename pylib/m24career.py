# -*- coding: utf-8 -*-
"""M24GA 공용 라이브러리 (pylib, 코어 0.22.0): 세이브 파일(.fm)에서 사람별 경력 사건 기록 읽기 (읽기 전용). GPL-3.0-or-later

몸값모드 V17에서 형식을 확인했다 (홀란·사카·카마빙가·야말 기록을 실제 경력·게임 진행과 맞춤).

세이브 안의 person_record_history_ls.dat(목록) + person_record_history_dt.cmt(기록). 다른 *_hist 파일과 같은 _ls/_dt 형식.
목록 하나 = 사람 한 명(선수·스태프). 목록 번호는 게임 메모리의 사람 객체 +0x110 (코어 필드 player.recordList)이고,
사람 번호(player.link)와는 다르다 (홀란: 사람 45806, 목록 32192).

기록 하나 (42바이트):
  +0  u16 날짜: 하위 9비트 = 그해 몇째 날 (1월 1일 = 1), 상위 7비트는 뜻 미확인
  +2  u16 연도
  +4  u32 깃발 (종류마다 뜻이 다름, 0x80000000 = 우승·수상 같은 큰 일로 보임)
  +8, +12, +16, +20  u32 값 a, b, c, d (종류마다 뜻이 다름)
  +24 u8 종류 (아래 KINDS)
  +27 u32 팀 번호 (db::TEAM +0x8, 대표팀 포함), +31 u32 사람 번호, +35 u16 대회 번호, +37 u16 상 번호 (상 종류만),
  +38 u32 다른 팀 번호 (상 종류가 아닐 때). 빈 칸은 0xffffffff / 0xffff
"""
import datetime
import os
import pickle
import struct
import time

from dpa.save_archive import SaveArchive
import m24hist

WIDTH = 42
EMPTY = 0xffffffff
BASE = "person_record_history"

# 종류 번호 -> (이름, 설명, 화면·실제 경력과 맞춰 봤는지)
KINDS = {
    0: ("cup_final", "컵 대회 결승 (a: 1 우승 / 2 준우승; 깃발 0x2 우승, 0x4 준우승; a = 0인 기록은 뜻 미확인)", True),
    1: ("league_finish", "리그 시즌 결과 (깃발 0x2 우승, 0x4 상위권(2위·대륙 대회 진출로 보임), 0x8 승격, 0x40 강등; a = 순위는 게임 시작 전 기록에만)", True),
    30: ("award_week", "주간 상 (금주의 팀·선수; 상 번호, a = 연도)", True),
    31: ("award_month", "월간 상 (이달의 선수·유망주·감독; a = 월, b = 연도)", True),
    32: ("award_season", "시즌·연간 상 (득점왕·올해의 선수 등; c = 순위 1~3, a = 연도)", True),
    35: ("award_goal", "골 상 (이달의 골·대회 최고의 골 등)", True),
    38: ("award_year_nominee", "연간 상 후보 명단 (FIFA 올해의 선수 등, a = 연도; 수상 1~3위와 겹치는 건 1/3뿐이라 수상이 아님; b 뜻 미확인)", True),
    60: ("signed_player", "감독·스태프 기록: 선수 영입 (사람 = 선수, a = 이적료, 다른 팀 = 판 팀)", True),
    61: ("sold_player", "감독·스태프 기록: 선수 판매·방출 (사람 = 선수, a = 이적료, 다른 팀 = 산 팀)", True),
    62: ("transfer", "이적 (팀 = 떠난 팀, 다른 팀 = 새 팀, a = 이적료, d = 조건 포함 최대 이적료로 보임, c = 1 완전 이적)", True),
    63: ("left_club", "구단을 떠남: 계약 만료·방출 (팀 = 떠난 팀; 거의 다 바로 뒤에 떠난 팀 없는 이적(자유 이적)이 옴; b = 이유 번호, 2가 83%)", True),
    66: ("loan", "임대 (팀 = 임대 간 팀, 다른 팀 = 원소속 팀; 마지막 사건이 임대인 선수 98%가 지금 그 팀)", True),
    71: ("loan_end", "임대 끝 (팀 = 임대 갔던 팀; 마지막 사건이 임대 끝인 선수 95%가 그 팀을 떠나 있음)", True),
    113: ("record_broken", "개인 기록 경신 (사람 = 대개 본인, a = 기록 종류 번호 29~50, c = 값; 기록 종류 이름은 미확인)", False),
    122: ("debut", "데뷔전 (팀, 대회, 다른 팀 = 상대 팀)", True),
    123: ("first_goal", "첫 골 (팀, 대회, 다른 팀 = 상대 팀)", True),
}
AWARD_KINDS = (30, 31, 32, 35, 38)
_REC = struct.Struct("<HHIIIIIB2xIIHxI")   # 날짜, 연도, 깃발, a, b, c, d, 종류, (+25 2바이트), 팀, 사람, 대회, (+37), 다른 팀(+38)


class _NoCancel:
    def is_set(self):
        return False


def _opt(v, empty=EMPTY):
    return None if v == empty else v


def decode(raw):
    """기록 42바이트 -> dict. 공통: year, day(그해 몇째 날), date(datetime.date 또는 None), kind, kind_name, flags, a, b, c, d,
    team, person, comp, other_team(상 종류에서는 None), award(상 종류만). 종류별로 place / fee / from_team / to_team / opponent를 덧붙인다."""
    dc, year, flags, a, b, c, d, kind, team, person, comp, other = _REC.unpack_from(raw, 0)
    day = dc & 0x1ff
    try:
        dt = datetime.date(year, 1, 1) + datetime.timedelta(days=day - 1) if 1 <= day <= 366 and year > 1800 else None
    except (ValueError, OverflowError):
        dt = None
    r = {"year": year, "day": day, "date": dt, "kind": kind, "kind_name": KINDS.get(kind, ("unknown",))[0], "flags": flags,
         "a": a, "b": b, "c": c, "d": d, "team": _opt(team), "person": _opt(person), "comp": _opt(comp, 0xffff), "other_team": _opt(other)}
    if kind in AWARD_KINDS:
        r["award"] = struct.unpack_from("<H", raw, 37)[0]
        r["other_team"] = None
        if kind == 32:
            r["place"] = c if 1 <= c <= 3 else None
    elif kind == 0:
        r["place"] = a if a in (1, 2) else 1 if flags & 2 else 2 if flags & 4 else None
    elif kind == 1:
        r["place"] = a if 1 <= a < 100 else 1 if flags & 2 else None
        r["top"] = bool(flags & 6)
        r["promoted"] = bool(flags & 8)
        r["relegated"] = bool(flags & 0x40)
    elif kind in (60, 61, 62):
        r["fee"] = a
        if kind == 62:
            r["from_team"], r["to_team"], r["fee_max"] = _opt(team), _opt(other), d
    elif kind in (122, 123):
        r["opponent"] = _opt(other)
    elif kind == 66:
        r["loan_team"], r["parent_team"] = _opt(team), _opt(other)
    return r


def lists_of(ls):
    """_ls.dat -> [[기록 바이트 위치, ...] 목록마다] (dpa.save_history.history_lists와 같은 형식)"""
    at = 8
    free = struct.unpack_from("<I", ls, at)[0]
    at += 4 + 4 * free
    count = struct.unpack_from("<I", ls, at)[0]
    at += 4
    out = []
    for _ in range(count):
        n = struct.unpack_from("<I", ls, at)[0]
        at += 4
        prev, refs = 0, []
        for _ in range(n):
            enc = struct.unpack_from("<i", ls, at)[0]
            at += 4
            refs.append(enc + prev)
            prev = enc
        out.append(refs)
    return out


class PersonRecords:
    """사람별 경력 기록. 목록 번호(player.recordList)로 꺼낸다. 기록은 꺼낼 때 푼다 (126만 개를 한꺼번에 dict로 만들지 않음)."""

    def __init__(self, lists, dt, file=None):
        self.lists, self.dt, self.file = lists, dt, file

    def __len__(self):
        return len(self.lists)

    def raw(self, list_idx):
        if not (0 <= list_idx < len(self.lists)):
            return []
        dt = self.dt
        return [dt[8 + off: 8 + off + WIDTH] for off in self.lists[list_idx] if 8 + off + WIDTH <= len(dt)]

    def of(self, list_idx, kinds=None):
        """목록 하나의 기록 -> [dict] (날짜 순). kinds: 종류 번호 모음이면 그것만"""
        out = [decode(b) for b in self.raw(list_idx) if kinds is None or b[24] in kinds]
        out.sort(key=lambda r: (r["year"], r["day"]))
        return out

    def transfers(self, list_idx):
        """이적 [(날짜 또는 None, 떠난 팀, 새 팀, 이적료)]"""
        return [(r["date"], r["from_team"], r["to_team"], r["fee"]) for r in self.of(list_idx, (62,))]

    def finals(self, list_idx):
        """컵 결승 [(연도, 대회, 팀, 순위 1/2)] (순위 모르는 기록은 뺌)"""
        return [(r["year"], r["comp"], r["team"], r["place"]) for r in self.of(list_idx, (0,)) if r["place"]]

    def league_finishes(self, list_idx):
        """리그 결과 [(연도, 대회, 팀, 순위 또는 None, 상위권, 승격, 강등)] (순위는 우승이거나 게임 시작 전 기록일 때만)"""
        return [(r["year"], r["comp"], r["team"], r["place"], r["top"], r["promoted"], r["relegated"]) for r in self.of(list_idx, (1,))]

    def loans(self, list_idx):
        """임대 [(날짜, 임대 간 팀, 원소속 팀)]"""
        return [(r["date"], r["loan_team"], r["parent_team"]) for r in self.of(list_idx, (66,))]

    def awards(self, list_idx):
        """상 [(연도, 종류 이름, 상 번호, 순위 또는 None)] (상 이름은 게임 쪽 awardInfo)"""
        return [(r["year"], r["kind_name"], r["award"], r.get("place")) for r in self.of(list_idx, AWARD_KINDS)]

    def iter_kind(self, kind):
        """모든 목록에서 한 종류만: (목록 번호, dict)"""
        dt = self.dt
        for li, offs in enumerate(self.lists):
            for off in offs:
                p = 8 + off
                if p + WIDTH <= len(dt) and dt[p + 24] == kind:
                    yield li, decode(dt[p: p + WIDTH])


def parse(path):
    """세이브 파일 경로 -> PersonRecords"""
    with SaveArchive(path, _NoCancel()) as a:
        lk = {m.name: m for m in a.members}
        ls_name = next((n for n in lk if n.endswith(BASE + "_ls.dat")), None)
        dt_name = next((n for n in lk if n.endswith(BASE + "_dt.cmt")), None)
        if not ls_name or not dt_name:
            raise ValueError("세이브에 사람 경력 기록 파일이 없어요")
        ls = b"".join(a.chunks(lk[ls_name]))
        dt = b"".join(a.chunks(lk[dt_name]))
    width = struct.unpack_from("<I", ls, len(ls) - 6)[0]
    if width != WIDTH:
        raise ValueError("사람 경력 기록 크기가 %d바이트예요 (알고 있는 형식은 %d)" % (width, WIDTH))
    return PersonRecords(lists_of(ls), dt, os.path.basename(path))


def load(save_id, cache_path=None, log=lambda m: None):
    """지금 세이브(ID)의 가장 최근 .fm -> PersonRecords 또는 None (파일 없음).
    cache_path를 주면 (파일 경로·크기·수정 시각)이 같을 때 다시 읽지 않는다."""
    path = m24hist.find_save(save_id)
    if not path:
        log("경력 기록: 세이브 ID %d인 .fm 파일을 찾지 못했어요" % save_id)
        return None
    st = os.stat(path)
    key = [os.path.abspath(path), st.st_size, int(st.st_mtime), 1]
    if cache_path:
        try:
            with open(cache_path, "rb") as f:
                c = pickle.load(f)
            if c.get("key") == key:
                return PersonRecords(c["lists"], c["dt"], c["file"])
        except (OSError, ValueError, EOFError, KeyError, pickle.UnpicklingError, AttributeError, ImportError):
            pass
    t0 = time.time()
    data = parse(path)
    if cache_path:
        tmp = cache_path + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump({"key": key, "lists": data.lists, "dt": data.dt, "file": data.file}, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, cache_path)
    log("경력 기록: %s에서 목록 %d개 (%.1f초)" % (data.file, len(data), time.time() - t0))
    return data
