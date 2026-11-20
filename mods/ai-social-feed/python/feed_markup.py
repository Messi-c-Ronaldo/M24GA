# -*- coding: utf-8 -*-
"""
작성자: DeepSeek (Cline)

FM24 소셜 피드 본문의 **게임 마크업 ↔ AI용 문장** 변환 모듈 (순수 Python, 표준 라이브러리만).

게임/메모리는 건드리지 않는다. 입력은 문자열(`parse_feed_text`)과 `ParsedFeed`(`render_feed_text`)뿐이다.

마크업 형식 (2026-10-29_10번 문서에서 관찰된 사실)
--------------------------------------------------
    이름/팀 링크 : .<base64>.<표시 이름>.
    해시태그     : |c:hashtag|#<내용>|/c|      (여러 개는 공백으로 이어짐)
    기타 색상태그: |c:positive|, |c:negative|, |c:red| ... |/c|   → 건드리지 않고 보존

사용 예
-------
    parsed = parse_feed_text(orig)                  # 링크/해시태그를 떼어낸다
    ai     = parsed.body_template                   # AI에게 주는 원문 (예: "{T1} 팬들은 ...")
    new    = render_feed_text("{T1}{은/는} 팬들이 또 난리다.", parsed, keep_hashtags=True)

설계 메모
---------
- `entities[].kind`(team/person)는 base64 이진 데이터에서 확정하지 못하면 "unknown"이다.
  현재 확보된 실제 표본이 팀 링크 1개뿐이라(지시서 1절) 확정 근거가 없다 → 툴팁 낱말 휴리스틱만 사용.
  판정 근거 확장 지점: `KIND_TOOLTIP_WORDS`, `KIND_TYPE_IDS` (문서 3절 참고).
- 해시태그 덩어리는 **본문 끝에 연속으로 붙은 경우**만 `hashtags_raw`로 분리한다.
  문장 중간의 해시태그는 손상 방지를 위해 본문에 그대로 둔다(한계, `parse_feed_text` 참고).
- 왕복(parse → render) 시 원문과 **바이트 단위로 같아지도록** 링크 조각/공백 구분자를 원형 보존한다.
"""
from __future__ import annotations

import base64
import binascii
import dataclasses
import re
from typing import Dict, Iterable, List, Optional, Tuple

__all__ = [
    "Entity",
    "ParsedFeed",
    "parse_feed_text",
    "render_feed_text",
    "choose_particle",
    "jongseong_index",
    "GAME_PARTICLE_TOKENS",
    "HASHTAG_OPEN",
    "HASHTAG_CLOSE",
]

HASHTAG_OPEN = "|c:hashtag|"
HASHTAG_CLOSE = "|/c|"

MIN_B64_LEN = 16      # 이보다 짧으면 링크로 보지 않는다 (".의 ." 같은 오탐 방지)
MAX_NAME_LEN = 64     # 표시 이름 최대 길이 (마크업이 깨졌을 때 폭주 방지)
MAX_TOOLTIP_SEARCH = 640


# ---------------------------------------------------------------------------
# 자료 구조
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Entity:
    """링크 하나. `key`는 자리표시자(`{T1}` 등)에 그대로 쓰인다."""

    key: str
    name: str
    raw: str
    tooltip: str = ""
    kind: str = "unknown"          # "team" | "person" | "unknown"
    type_id: Optional[int] = None  # base64 앞 u32 (성격 미확인, 표본 비교용)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "raw": self.raw,
            "tooltip": self.tooltip,
            "kind": self.kind,
            "type_id": self.type_id,
        }


@dataclasses.dataclass
class ParsedFeed:
    """`parse_feed_text`의 반환값."""

    body_template: str = ""
    entities: List[Entity] = dataclasses.field(default_factory=list)
    hashtags_raw: str = ""
    hashtags_display: List[str] = dataclasses.field(default_factory=list)
    particles: Dict[str, str] = dataclasses.field(default_factory=dict)
    # 본문과 해시태그 덩어리 사이의 원래 공백(왕복 보존용). 없으면 "".
    hashtags_prefix: str = " "

    # 편의 접근자 ---------------------------------------------------------
    def entity_by_key(self) -> Dict[str, Entity]:
        return {e.key: e for e in self.entities}

    def entity_by_name(self) -> Dict[str, Entity]:
        out: Dict[str, Entity] = {}
        for e in self.entities:
            out.setdefault(e.name, e)
        return out

    def to_dict(self) -> dict:
        """지시서 2절의 dict 형태."""
        return {
            "body_template": self.body_template,
            "entities": [e.to_dict() for e in self.entities],
            "hashtags_raw": self.hashtags_raw,
            "hashtags_display": list(self.hashtags_display),
            "particles": dict(self.particles),
            "hashtags_prefix": self.hashtags_prefix,
        }


# ---------------------------------------------------------------------------
# base64 링크 조각 해석
# ---------------------------------------------------------------------------

_B64_RE = re.compile(r"[A-Za-z0-9+/]{%d,}={0,2}" % MIN_B64_LEN)
# 표시 이름에 들어갈 수 없는 문자(마크업이 깨졌을 때 다음 구역으로 넘어가지 않게 한다)
_NAME_STOP = frozenset("|\n\r\t{}<>#")


def _decode_payload(b64_text: str) -> Optional[bytes]:
    """표준 알파벳 base64를 디코드. 실패하면 None."""
    if not b64_text or len(b64_text) % 4:
        return None
    try:
        return base64.b64decode(b64_text, validate=True)
    except (binascii.Error, ValueError):
        return None


def _decode_tooltip(payload: bytes) -> Tuple[str, Optional[int]]:
    """이진 데이터 끝의 [u32 길이][UTF-8 툴팁]을 찾는다.

    10번 문서 관찰: 툴팁 앞 4바이트가 툴팁 길이(u32 LE). 끝에서부터 정확히
    맞아떨어지는(off+4+len == len(payload)) 후보만 인정한다.
    """
    n = len(payload)
    for off in range(n - 5, max(-1, n - MAX_TOOLTIP_SEARCH), -1):
        length = int.from_bytes(payload[off:off + 4], "little")
        if length == 0 or off + 4 + length != n:
            continue
        try:
            text = payload[off + 4:].decode("utf-8")
        except UnicodeDecodeError:
            continue
        if not text or any(ord(ch) < 0x20 for ch in text):
            continue
        return text.replace("\x00", "").strip(), off
    return "", None


def _normalize_for_match(s: str) -> str:
    """툴팁/이름 대조용 정규화: 공백 제거, 소문자."""
    return "".join(ch for ch in s if not ch.isspace()).lower()


# 툴팁에 이 낱말이 있으면 종류를 추정한다(한국어 툴팁 기준, 확신도 낮음).
KIND_TOOLTIP_WORDS: Dict[str, Tuple[str, ...]] = {
    "person": ("선수", "감독", "코치", "인물", "스카우트", "회장", "구단주"),
    "team": ("클럽", "구단", "팀", "유소년"),
}

# base64 앞 u32 값 → kind. 실제 표본이 더 모이면 채운다(현재 비어 있음 = 판정 불가).
# 관찰값: 팀 링크 표본 1개(`AFC 아약스`)에서 type_id = 3.
KIND_TYPE_IDS: Dict[int, str] = {}


def _detect_kind(tooltip: str, type_id: Optional[int]) -> str:
    if type_id is not None and type_id in KIND_TYPE_IDS:
        return KIND_TYPE_IDS[type_id]
    if tooltip:
        if "프로필" in tooltip:      # "...의 프로필을 보려면 클릭하십시오." = 선수/스태프
            return "person"
        if type_id == 3 and tooltip.endswith("보려면 클릭하십시오."):
            return "team"            # 클럽/대회 등 (프로필 아님)
        for kind, words in KIND_TOOLTIP_WORDS.items():
            if any(w in tooltip for w in words):
                return kind
    return "unknown"


def scan_link(text: str, start: int, limit: Optional[int] = None):
    """`text[start]`가 '.', 즉 링크 조각 시작일 때 해석한다.

    반환: (name, raw, tooltip, payload, end, type_id) 또는 None
      - `end`는 링크 **다음** 인덱스(마지막 '.' 바로 뒤).
    이름 끝 판정:
      1. base64를 풀어 얻은 툴팁 안에 후보 이름이 들어 있는 것 중 **가장 긴** 후보
      2. 없으면 "가장 가까운 '.'" 규칙(가장 짧은 후보)
    """
    if limit is None:
        limit = len(text)
    # 실제 게임 형식 (2026-10-29 Claude 확인): <base64><이름>
    # (이전 로그의 '.'은 터미널이 제어 문자를 점으로 표시한 것이었다)
    if start < len(text) and text[start] == "":
        sep = text.find("", start + 1, limit)
        if sep < 0:
            return None
        end = text.find("", sep + 1, limit)
        if end < 0 or end - sep - 1 > MAX_NAME_LEN or end == sep + 1:
            return None
        b64_text = text[start + 1:sep]
        if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", b64_text):
            return None
        payload = _decode_payload(b64_text + "=" * (-len(b64_text) % 4))
        if payload is None:
            return None
        tooltip, _ = _decode_tooltip(payload)
        type_id = int.from_bytes(payload[:4], "little") if len(payload) >= 4 else None
        return text[sep + 1:end], text[start:end + 1], tooltip, payload, end + 1, type_id
    if start >= len(text) or text[start] != ".":
        return None
    m = _B64_RE.match(text, start + 1, limit)
    if not m:
        return None
    b64_text = m.group(0)
    payload = _decode_payload(b64_text)
    if payload is None:
        return None
    dot = m.end()
    if dot >= limit or text[dot] != ".":
        return None

    name_start = dot + 1
    candidates: List[int] = []
    i = name_start
    while i < limit and (i - name_start) <= MAX_NAME_LEN:
        ch = text[i]
        if ch in _NAME_STOP:
            break
        if ch == "." and text[name_start:i].strip():
            candidates.append(i)
        i += 1
    if not candidates:
        return None

    tooltip, _ = _decode_tooltip(payload)
    chosen = None
    if tooltip:
        tip_norm = _normalize_for_match(tooltip)
        for pos in candidates:                      # 짧은 후보 → 긴 후보 순
            cand = text[name_start:pos]
            if _normalize_for_match(cand) in tip_norm:
                chosen = pos                        # 가장 긴 일치 후보를 남긴다
    if chosen is None:
        chosen = candidates[0]

    name = text[name_start:chosen]
    raw = text[start:chosen + 1]
    type_id = int.from_bytes(payload[:4], "little") if len(payload) >= 4 else None
    return name, raw, tooltip, payload, chosen + 1, type_id


# ---------------------------------------------------------------------------
# 해시태그 덩어리 분리
# ---------------------------------------------------------------------------

_HASHTAG_BLOCK_RE = re.compile(r"\|c:hashtag\|.*?\|/c\|", re.S)


def _hashtag_spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in _HASHTAG_BLOCK_RE.finditer(text)]


def _split_hashtags(text: str):
    """(body, prefix, raw, spans) 로 나눈다.

    - 본문 **끝**에 공백만 사이에 두고 연속된 해시태그 덩어리만 `raw`로 분리한다.
    - 끝이 아닌 해시태그는 `spans`에만 남고 본문에 그대로 보존된다(한계).
    """
    spans = _hashtag_spans(text)
    if not spans:
        return text, " ", "", []
    tail_end = spans[-1][1]
    if text[tail_end:].strip():
        return text, " ", "", spans        # 뒤에 본문이 더 있다 → 분리하지 않음

    run_start = spans[-1][0]
    run = [spans[-1]]
    for s, e in reversed(spans[:-1]):
        if text[e:run_start].strip() == "":
            run_start = s
            run.append((s, e))
        else:
            break
    run.reverse()

    body_raw = text[:run_start]
    body = body_raw.rstrip(" \t")
    prefix = body_raw[len(body):] or " "
    raw = text[run_start:tail_end]
    return body, prefix, raw, run


def _hashtag_display(block: str) -> str:
    """`|c:hashtag|#.<b64>.이름.|/c|` → `#이름`."""
    inner = block[len(HASHTAG_OPEN):-len(HASHTAG_CLOSE)].strip()
    if not inner.startswith("#"):
        return "#" + inner.lstrip("#")
    content = inner[1:].strip()
    if content[:1] in (".", ""):
        link = scan_link(content, 0)
        if link:
            return "#" + link[0]
    return "#" + content


# ---------------------------------------------------------------------------
# 링크 뒤 조사 추출 (AI 프롬프트 참고용)
# ---------------------------------------------------------------------------

# 긴 것부터 검사한다("이랑" > "이").
KNOWN_PARTICLES: Tuple[str, ...] = (
    "으로서", "으로써", "에서는", "에게서", "이라고", "이라는", "이라도",
    "이랑", "이나", "이든", "이란", "이라", "이여", "이야", "이지",
    "으로", "에서", "에게", "에겐", "부터", "까지", "보다", "처럼", "마다",
    "조차", "마저", "이든", "밖에",
    "은", "는", "이", "가", "을", "를", "와", "과", "의", "에", "도", "만",
    "로", "랑", "나", "든", "란", "라", "야", "여", "께", "써",
)


def _extract_particle(text: str, pos: int) -> str:
    """`pos` 위치에서 시작하는 조사를 찾는다. 없으면 빈 문자열."""
    for p in KNOWN_PARTICLES:
        if text.startswith(p, pos):
            # 조사 뒤가 글자(한글/영숫자)면 낱말의 일부일 수 있으므로 제외
            nxt = text[pos + len(p):pos + len(p) + 1]
            if nxt and (nxt.isalnum()):
                continue
            return p
    return ""


# ---------------------------------------------------------------------------
# 게임 템플릿의 조사 토큰 (ko_ltc_social.csv 통계 조사 결과, 기록 문서 4절)
# ---------------------------------------------------------------------------
# 이름 토큰 뒤에 붙는 `{r}` 같은 표기. 게임이 이름 받침에 맞는 조사를 골라 넣는다.
# 값 = 이 모듈의 choose_particle()이 받는 "조사 쌍".
GAME_PARTICLE_TOKENS = {
    "{r}": "이/가",      # 32,159회. "팀1이 6경기를 치렀지만" / "그가 경질될" (확신 높음)
    "{s}": "은/는",      # 44,326회. "{s}커녕"(은커녕) / "팀은 벌써 12경기를 패해서" (확신 높음)
    "{f}": "을/를",      # 17,753회. "클럽이 그를 감독으로 선임" / "팀을 상대로" (확신 높음)
    "{d}": "와/과",      # 12,782회. "팀1과 팀2 간의" / "{d}의" (확신 높음)
    "{h}": "으로/로",    #  6,583회. "{h} 승리한 경기" / "{h} 이적하는" (확신 높음)
}
# 그 밖에 {an}(영문 'a/an' 관사, 미번역 문장에서만 96회), {S}(2회, 의미 미확인)가 있다.


# ---------------------------------------------------------------------------
# 파싱
# ---------------------------------------------------------------------------

def parse_feed_text(text: str) -> ParsedFeed:
    """게임 본문 → (자리표시자 본문, 개체 목록, 해시태그).

    마크업이 없는 일반 문장도 오류 없이 처리한다(entities 빈 목록).
    """
    if not isinstance(text, str):
        raise TypeError("parse_feed_text: str 이 필요합니다")
    if not text:
        return ParsedFeed(body_template="")

    body, prefix, tags_raw, spans = _split_hashtags(text)
    stray_spans = [(s, e) for (s, e) in spans if s < len(body)]

    parsed = ParsedFeed(body_template="", hashtags_raw=tags_raw, hashtags_prefix=prefix)
    by_name: Dict[str, Entity] = {}
    counters = {"T": 0, "P": 0, "E": 0}
    out: List[str] = []

    def key_for(name: str, kind: str) -> str:
        ent = by_name.get(name)
        if ent is not None:
            return ent.key
        prefix_letter = {"team": "T", "person": "P"}.get(kind, "E")
        counters[prefix_letter] += 1
        key = "%s%d" % (prefix_letter, counters[prefix_letter])
        return key

    i = 0
    span_idx = 0
    while i < len(body):
        while span_idx < len(stray_spans) and stray_spans[span_idx][1] <= i:
            span_idx += 1
        if span_idx < len(stray_spans) and stray_spans[span_idx][0] == i:
            s, e = stray_spans[span_idx]
            out.append(body[s:e])          # 중간 해시태그는 원형 그대로 둔다(한계)
            i = e
            span_idx += 1
            continue

        limit = stray_spans[span_idx][0] if span_idx < len(stray_spans) else len(body)
        if body[i] in (".", ""):
            link = scan_link(body, i, limit)
            if link is not None:
                name, raw, tooltip, _payload, end, type_id = link
                kind = _detect_kind(tooltip, type_id)
                ent = by_name.get(name)
                if ent is None:
                    key = key_for(name, kind)
                    ent = Entity(key=key, name=name, raw=raw, tooltip=tooltip,
                                 kind=kind, type_id=type_id)
                    by_name[name] = ent
                    parsed.entities.append(ent)
                out.append("{%s}" % ent.key)
                if ent.key not in parsed.particles:
                    particle = _extract_particle(body, end)
                    if particle:
                        parsed.particles[ent.key] = particle
                i = end
                continue

        out.append(body[i])
        i += 1

    parsed.body_template = "".join(out)
    if tags_raw:
        parsed.hashtags_display = [_hashtag_display(b)
                                   for b in re.findall(r"\|c:hashtag\|.*?\|/c\|",
                                                       tags_raw, re.S)]
    return parsed


# ---------------------------------------------------------------------------
# 조사 선택 (받침 판정)
# ---------------------------------------------------------------------------

# 받침 인덱스: (코드포인트 - 0xAC00) % 28. 0 = 받침 없음, 8 = ㄹ.
_JONG_NONE = 0
_JONG_RIEUL = 8

# 끝 글자가 영문/숫자일 때 "읽는 소리"의 받침 인덱스 (지시서 2절).
_READING_JONG: Dict[str, int] = {
    # 숫자
    "0": 21, "1": 8, "2": 0, "3": 16, "4": 0, "5": 0,
    "6": 1, "7": 8, "8": 8, "9": 0,
    # 영문 (A 에이 … Z 제트)
    "A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0, "G": 0, "H": 0,
    "I": 0, "J": 0, "K": 0, "L": 8, "M": 16, "N": 4, "O": 0, "P": 0,
    "Q": 0, "R": 8, "S": 0, "T": 0, "U": 0, "V": 0, "W": 0, "X": 0,
    "Y": 0, "Z": 0,
    # 기호
    # (F=에프, %=퍼센트, +=플러스 → 받침 없음. 2026-10-29 Claude 검토에서 정정)
    "&": 4, "%": 0, "+": 0,
}

# 이름 끝에서 무시하는 문자(괄호/따옴표/문장부호/공백).
_TRAILING_IGNORE = " \t\u00a0.,!?~…·:;'\"”’)]}>」』】^"


def jongseong_index(word: str) -> Optional[int]:
    """마지막 글자의 받침 인덱스. 판정 불가면 None.

    - 한글 음절: 분해해서 계산
    - 영문/숫자/일부 기호: 읽는 소리 표 사용 (대소문자 무시)
    - 끝의 괄호·공백·문장부호는 무시
    """
    if not word:
        return None
    s = word.rstrip(_TRAILING_IGNORE)
    if not s:
        return None
    ch = s[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28
    if "\u3131" <= ch <= "\u318E":       # 낱자 자모는 판정하지 않는다
        return None
    up = ch.upper()
    if up in _READING_JONG:
        return _READING_JONG[up]
    return None


def _split_pair_raw(pair: str) -> Tuple[str, str]:
    """`"은/는"` 또는 `"은(는)"` → ("은", "는")."""
    pair = pair.strip()
    if not pair:
        raise ValueError("조사 쌍이 비었습니다")
    if "/" in pair:
        left, right = pair.split("/", 1)
    else:
        m = re.match(r"^(.*?)\s*\((.*)\)$", pair)
        if not m:
            raise ValueError("조사 쌍 형식이 아닙니다: {%s}" % pair)
        left, right = m.group(1), m.group(2)
    left, right = left.strip(), right.strip()
    if not left or not right:
        raise ValueError("조사 쌍 형식이 아닙니다: {%s}" % pair)
    return left, right


# 조사 쌍에서 "받침 뒤" 형태를 알려 주는 표.
# 주의: 쌍의 **순서가 일정하지 않다** — 은/는·을/를·이/가 는 앞쪽이 받침 뒤 형태지만
#       와/과 는 반대(과 가 받침 뒤)다. 그래서 순서에 의존하지 않고 표로 찾는다.
_PAIR_WITH_FINAL: Dict[frozenset, str] = {
    frozenset(("은", "는")): "은",
    frozenset(("이", "가")): "이",
    frozenset(("을", "를")): "을",
    frozenset(("와", "과")): "과",
    frozenset(("으로", "로")): "으로",
    frozenset(("이다", "다")): "이다",
    frozenset(("아", "야")): "아",
    frozenset(("이랑", "랑")): "이랑",
    frozenset(("이나", "나")): "이나",
    frozenset(("이든", "든")): "이든",
    frozenset(("이란", "란")): "이란",
    frozenset(("이야", "야")): "이야",
    frozenset(("이지", "지")): "이지",
    frozenset(("이여", "여")): "이여",
    frozenset(("이오", "오")): "이오",
    frozenset(("으로서", "로서")): "으로서",
    frozenset(("으로써", "로써")): "으로써",
    frozenset(("으로부터", "로부터")): "으로부터",
}


def _pair_forms(pair: str) -> Tuple[str, str]:
    """조사 쌍 → (받침 뒤 형태, 받침 없을 때 형태)."""
    first, second = _split_pair_raw(pair)
    if first == second:
        return first, second
    with_final = _PAIR_WITH_FINAL.get(frozenset((first, second)))
    if with_final is None:
        # 표에 없으면 "긴 쪽이 받침 뒤 형태"로 추정(으로/로·이다/다 계열). 아니면 앞쪽.
        if first.endswith(second):
            with_final = first
        elif second.endswith(first):
            with_final = second
        else:
            with_final = first
    without_final = second if with_final == first else first
    return with_final, without_final


def choose_particle(name: str, pair: str) -> str:
    """이름의 마지막 글자 받침으로 조사를 고른다.

    `pair` 예: "은/는", "이/가", "을/를", "와/과", "으로/로", "이다/다", "아/야", "이랑/랑"

    규칙
    - 받침 있음 → 받침 뒤 형태, 없음 → 받침 없을 때 형태
    - "으로/로": 받침이 없거나 ㄹ이면 "로"
    - 판정 불가(기호 등)면 받침 없음으로 취급
    """
    with_final, without_final = _pair_forms(pair)
    jong = jongseong_index(name)
    if jong is None:
        return without_final
    if with_final == "으로" and without_final == "로":
        return without_final if jong in (_JONG_NONE, _JONG_RIEUL) else with_final
    return with_final if jong != _JONG_NONE else without_final


# ---------------------------------------------------------------------------
# 렌더링 (AI 문장 → 게임 본문)
# ---------------------------------------------------------------------------

_BRACE_RE = re.compile(r"\{([^{}]*)\}")
_PLACEHOLDER_RE = re.compile(r"^[A-Za-z]{1,3}[0-9]+$")
_GAME_MARKUP_RE = re.compile(r"\|c:|\|/c\||\[%")


def render_feed_text(ai_text: str, parsed: ParsedFeed, keep_hashtags: bool = True) -> str:
    """AI 문장 → 게임 본문.

    `ai_text` 규칙: 자리표시자(`{T1}`)와 조사 쌍(`{T1}{은/는}`)만 쓴다.
    - 모르는 자리표시자, 짝이 안 맞는 중괄호, `|c:`/`[%` 같은 게임 마크업이 있으면 ValueError
      (모드가 원문으로 되돌리는 신호로 쓴다)
    - 줄바꿈은 공백으로 바꾼다
    """
    if not isinstance(ai_text, str):
        raise TypeError("render_feed_text: ai_text 는 str 이어야 합니다")
    if not isinstance(parsed, ParsedFeed):
        raise TypeError("render_feed_text: parsed 는 ParsedFeed 여야 합니다")

    text = ai_text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    bad = _GAME_MARKUP_RE.search(text)
    if bad:
        raise ValueError("AI 문장에 게임 마크업이 있습니다: %r" % bad.group(0))

    stripped = _BRACE_RE.sub("", text)
    if "{" in stripped or "}" in stripped:
        raise ValueError("중괄호 짝이 맞지 않습니다")

    by_key = parsed.entity_by_key()
    out: List[str] = []
    pos = 0
    last_key: Optional[str] = None
    last_end: Optional[int] = None

    for m in _BRACE_RE.finditer(text):
        out.append(text[pos:m.start()])
        token = m.group(1).strip()
        if "/" in token or "(" in token:
            if last_key is None or last_end != m.start():
                raise ValueError("{A/B} 조사 쌍은 자리표시자 바로 뒤에만 올 수 있습니다: {%s}"
                                 % token)
            out.append(choose_particle(by_key[last_key].name, token))
            last_key, last_end = None, None
        else:
            if not _PLACEHOLDER_RE.match(token):
                raise ValueError("알 수 없는 중괄호 표기: {%s}" % token)
            if token not in by_key:
                raise ValueError("모르는 자리표시자: {%s}" % token)
            out.append(by_key[token].raw)
            last_key, last_end = token, m.end()
        pos = m.end()
    out.append(text[pos:])

    result = "".join(out)
    if keep_hashtags and parsed.hashtags_raw:
        sep = parsed.hashtags_prefix
        if not sep:
            sep = " "
        result = result + sep + parsed.hashtags_raw
    return result


# ---------------------------------------------------------------------------
# 사람 링크 만들기 (작성: Claude Opus, 18번 로그)
# ---------------------------------------------------------------------------
# 게임의 사람 링크 payload 구조 (빌리 길모어 링크를 바이트 단위로 재현해 확인):
#   [3]"eklc" 01 0a [3]"tjbo" 01 0a [1]"ferd" 01 01 <ID> "dive" 01 02 "KNIL" "gtve" 01 02 "worb" "xnoc" 01 0a
#   [3]"tjbo" 01 0a [1]"ferd" 01 01 <ID> "dive" 01 02 "ATEG" "gtve" 01 02 "worb" "tnih" 01 1a [len u32][툴팁 UTF-8]
#   <ID> = 번호 3바이트 LE + 종류 1바이트 (사람 0x01)
# 빌리 길모어 링크의 앞부분(툴팁 길이 직전까지). ID 자리는 "ferd 01 01" 바로 뒤 4바이트 두 곳.
_LINK_TEMPLATE = bytes.fromhex(
    "03000000656b6c63010a03000000746a626f010a0100000066657264010162 0f0101646976650102"
    "4b4e494c677476650102776f7262786e6f63010a03000000746a626f010a01000000666572640101"
    "620f0101646976650102415445476774766501027776f7262746e6968011a".replace(" ", "").replace("027776f72", "02776f72"))
_ID_POS = [i + 6 for i in range(len(_LINK_TEMPLATE)) if _LINK_TEMPLATE[i:i + 6] == b"ferd"]


def make_person_link(name: str, dref: int) -> str:
    """사람 ID(0x01xxxxxx)와 표시 이름으로 게임과 같은 형식의 링크 조각을 만든다."""
    if (dref >> 24) != 0x01:
        raise ValueError("사람 ID가 아닙니다: %x" % dref)
    idb = dref.to_bytes(4, "little")
    tip = ("%s의 프로필을 보려면 클릭하십시오." % name).encode("utf-8")
    body = bytearray(_LINK_TEMPLATE)
    for pos in _ID_POS:
        body[pos:pos + 4] = idb
    payload = bytes(body) + len(tip).to_bytes(4, "little") + tip
    return "" + base64.b64encode(payload).decode("ascii") + "" + name + ""


# ---------------------------------------------------------------------------
# 간단한 자체 점검 (python feed_markup.py)
# ---------------------------------------------------------------------------

_REAL_SAMPLE = (
    ".AwAAAGVrbGMBCgMAAAB0amJvAQoBAAAAZmVyZAEBAwMAGGRpdmUBAktOSUxndHZlAQJ3b3JieG5vYwEK"
    "AwAAAHRqYm8BCgEAAABmZXJkAQEDAwAYZGl2ZQECQVRFR2d0dmUBAndvcmJ0bmloARouAAAAQUZDIOyV"
    "hOyVveyKpOulvCDrs7TroKTrqbQg7YG066at7ZWY7Iut7Iuc7JikLg==.아약스."
)


def _demo() -> None:  # pragma: no cover - 수동 확인용
    other = _REAL_SAMPLE.replace("아약스", "빌리길모어")
    sample = (_REAL_SAMPLE + "의 팬들은 이제 이 정도로 멘탈 터지지 않는다. (한숨) "
              "|c:hashtag|#%s|/c| |c:hashtag|#ESP|/c|" % other)
    parsed = parse_feed_text(sample)
    print("body_template :", parsed.body_template)
    print("entities      :", [(e.key, e.name, e.kind) for e in parsed.entities])
    print("hashtags_raw  :", parsed.hashtags_raw[:48].replace("\n", " "), "...")
    print("display       :", parsed.hashtags_display)
    print("particles     :", parsed.particles)
    print("roundtrip ok  :", render_feed_text(parsed.body_template, parsed) == sample)
    ai = "{%s}{은/는} 팬들이 또 난리다." % parsed.entities[0].key
    print("ai render     :", render_feed_text(ai, parsed, False))


if __name__ == "__main__":  # pragma: no cover
    _demo()
