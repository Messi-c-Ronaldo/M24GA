# -*- coding: utf-8 -*-
"""FM24 AI 소셜피드 모드: 설정 모듈 (작성: Claude Sonnet, 23번 로그)

설정 파일: ~/m24ga_data/ai-social-feed/config.json  (환경변수 FM24_AI_DATA로 폴더 변경 가능)
- 없으면 기본값으로 만든다. 일부 항목만 적어도 되고, 빠진 항목과 잘못된 값(형식/범위)은 기본값을 쓴다.
- 파일을 고치면 1초 안에 반영된다 (생성기/브리지는 다시 시작할 필요 없음). hook.js는 2.5초마다 다시 읽는다.
- 나중에 설정 앱(GUI)이 이 모듈의 load/get/save를 그대로 쓴다.
"""
import copy
import json
import os
import threading
import time

DATA_DIR = os.environ.get("FM24_AI_DATA") or os.path.join(os.path.expanduser("~"), "m24ga_data", "ai-social-feed")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULTS = {
    "_설명": "이 파일을 고치면 바로 반영됩니다. 항목 설명은 logs/AI소셜피드/2026-11-04/2026-11-04_23_Claude_설정파일_앱설계.md 참고",
    "enabled": True,                      # False면 모드 전체 정지 (원문 그대로, 요청도 안 보냄)
    "api": {
        "url": "https://api.deepseek.com/chat/completions",
        "model": "deepseek-flash",
        "key_file": "~/.deepseek_key",    # API 키가 든 파일 (한 줄). 키는 이 설정 파일에 쓰지 않는다
        "timeout_sec": 40,
        "temperature": 1.1,
        "max_tokens": 200,
        "thinking": False,                # True면 추론을 켠다 (비용 몇 배, 느림). 켜면 max_tokens_thinking가 쓰인다
        "max_tokens_thinking": 2000,
        "concurrency": 6,                 # 동시에 보내는 요청 수 (브리지 시작 때 정해진다)
    },
    "tokens": {                           # 토큰/비용 관리
        "use_club_finances": True,        # 클럽 재정 상태(이적 예산, 잔고, 주급 초과)를 "큰손", "재정 적자" 같은 말로만 반영 (금액은 안 보냄)
        "use_hidden_attributes": False,   # 숨은 능력치(논란·충성심·야망·부상 경향)를 댓글에 반영. 스카우트해야 아는 정보라 플레이에 힌트가 될 수 있어 기본은 꺼 둠
        "use_article_body": True,         # 뉴스 기사 본문을 참고 (건당 약 +600 토큰)
        "article_body_max_chars": 1000,
        "game_data_rate": 0.35,           # 게임 데이터(순위, 폼 등)를 붙이는 비율 0~1
        "match_game_data_rate": 0.7,      # 클럽이 둘 이상 나오는 글(경기 결과 등)의 비율 0~1
        "player_mention_rate": 0.5,       # 핵심 선수 이름을 언급하게 하는 비율 0~1
        "sibling_hint": True,             # 같은 글 아래 이미 나온 댓글을 알려 주고 겹치면 다시 만든다
        "sibling_count": 6,
        "retries": 1,                     # 실패/금지 표현/겹침일 때 다시 만드는 횟수 (호출 수가 늘어남)
        "max_chars": 100,                 # 댓글 최대 길이 (해시태그 제외)
        "max_calls_per_session": 400,     # 브리지 한 번 실행당 호출 상한 (비용 보호)
        "batch_thread": True,             # 같은 글 아래 댓글을 한 번의 호출로 만든다 (토큰 절약 + 빠름)
        "batch_max": 6,                   # 한 번에 묶는 최대 댓글 수
        "batch_wait_ms": 800,             # 같은 글 요청을 모으려고 기다리는 시간
    },
    "style": {
        "swear": "normal",                # normal(기본) / mild(순한 말) / none(욕설 없음) / wild(야생의 인터넷: 욕설·개드립 최대, 금지선은 그대로)
        "allow_k": False,                 # ㅋ 허용 (False면 모델이 써도 지운다)
        "system_prompt_file": "",         # 비우면 내장 말투. 파일 이름(데이터 폴더 기준)을 적으면 그 파일로 대체
        "extra_instructions": "",         # 말투 지침 끝에 덧붙일 말 (예: 특정 팀 팬으로 말하게 하기)
    },
    "game": {
        "krw_per_unit": 1664.7,           # 게임 내부 금액 1 = 원화 얼마 (재정 화면과 맞춰 확인: 바르셀로나 영입 예산 184.52억 원 = 내부 11,084,149). 세이브마다 환율 설정이 다르면 고친다
    },
    "pricing": {                          # 비용 표시용 (100만 토큰당 달러). 기본은 deepseek-flash 피크 요금(보수적), 평시는 절반
        "input_hit_per_m": 0.006,
        "input_miss_per_m": 0.30,
        "output_per_m": 1.20,
    },
    "hook": {                             # 게임 안 hook.js가 읽는 항목
        "replace_types": [2, 4],          # 교체할 글 종류 (2·4 팬 댓글). 다른 종류는 아직 검증되지 않음
        "max_requests": 600,              # 게임 한 번 켤 때 요청 상한
        "auto_refresh": True,             # 문장이 준비되면 '생성 중' 댓글을 바로 바꿔 그린다 (다른 화면에 갔다 올 필요 없음)
    },
}

# 숫자 범위 (넘으면 기본값)
RANGES = {
    "api.timeout_sec": (5, 300), "api.temperature": (0, 2), "api.max_tokens": (30, 4000), "api.max_tokens_thinking": (200, 8000),
    "tokens.article_body_max_chars": (100, 5000), "tokens.game_data_rate": (0, 1), "tokens.match_game_data_rate": (0, 1),
    "tokens.player_mention_rate": (0, 1), "tokens.sibling_count": (1, 20), "tokens.retries": (0, 3),
    "tokens.max_chars": (20, 300), "tokens.max_calls_per_session": (1, 100000), "hook.max_requests": (1, 100000),
    "game.krw_per_unit": (1, 100000), "tokens.batch_max": (1, 10), "tokens.batch_wait_ms": (0, 5000), "api.concurrency": (1, 16),
    "pricing.input_hit_per_m": (0, 100), "pricing.input_miss_per_m": (0, 100), "pricing.output_per_m": (0, 100),
}
CHOICES = {"style.swear": ("normal", "mild", "none", "wild")}

_lock = threading.Lock()
_cache = {"mtime": None, "checked": 0.0, "cfg": None, "warn": []}


def _merge(base, user, path, warn):
    out = {}
    for k, dv in base.items():
        full = path + k
        if k not in user:
            out[k] = copy.deepcopy(dv)
            continue
        uv = user[k]
        if isinstance(dv, dict):
            out[k] = _merge(dv, uv, full + ".", warn) if isinstance(uv, dict) else copy.deepcopy(dv)
            if not isinstance(uv, dict):
                warn.append("%s: 객체여야 함 -> 기본값" % full)
        elif isinstance(dv, bool):
            if isinstance(uv, bool):
                out[k] = uv
            else:
                out[k] = dv
                warn.append("%s: true/false여야 함 -> 기본값" % full)
        elif isinstance(dv, (int, float)):
            ok = isinstance(uv, (int, float)) and not isinstance(uv, bool)
            lo, hi = RANGES.get(full, (None, None))
            if ok and (lo is None or lo <= uv <= hi):
                out[k] = uv
            else:
                out[k] = dv
                warn.append("%s: 숫자 범위 밖 또는 형식 오류 -> 기본값" % full)
        elif isinstance(dv, str):
            if isinstance(uv, str) and (full not in CHOICES or uv in CHOICES[full]):
                out[k] = uv
            else:
                out[k] = dv
                warn.append("%s: 문자열/허용 값 오류 -> 기본값" % full)
        elif isinstance(dv, list):
            if isinstance(uv, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in uv):
                out[k] = uv
            else:
                out[k] = dv
                warn.append("%s: 정수 목록이어야 함 -> 기본값" % full)
        else:
            out[k] = uv
    for k, uv in user.items():            # 모르는 항목은 그대로 둔다 (미래 항목, 사용자 메모)
        if k not in base:
            out[k] = uv
    return out


def load(force=False):
    """현재 설정(dict). 파일이 바뀌었을 때만 다시 읽는다 (1초에 한 번만 확인)."""
    now = time.time()
    with _lock:
        if not force and _cache["cfg"] is not None and now - _cache["checked"] < 1.0:
            return _cache["cfg"]
        _cache["checked"] = now
        try:
            mt = os.path.getmtime(CONFIG_PATH)
        except OSError:
            mt = None
        if not force and _cache["cfg"] is not None and mt == _cache["mtime"]:
            return _cache["cfg"]
        warn = []
        user = {}
        if mt is not None:
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    user = json.load(f)
                if not isinstance(user, dict):
                    warn.append("최상위가 객체가 아님 -> 전부 기본값")
                    user = {}
            except (ValueError, OSError) as e:
                warn.append("config.json 읽기 실패(%s) -> 이전/기본값" % type(e).__name__)
                if _cache["cfg"] is not None:     # 편집 중이라 깨진 파일이면 직전 설정을 유지
                    _cache["warn"] = warn
                    return _cache["cfg"]
                user = {}
        _cache["cfg"] = _merge(DEFAULTS, user, "", warn)
        _cache["mtime"] = mt
        _cache["warn"] = warn
        return _cache["cfg"]


def warnings():
    load()
    return list(_cache["warn"])


def get(path):
    """get('tokens.use_article_body')"""
    v = load()
    for part in path.split("."):
        v = v[part]
    return v


def data_path(name):
    """데이터 폴더 기준 경로 (절대 경로면 그대로)."""
    name = os.path.expanduser(name)
    return name if os.path.isabs(name) else os.path.join(DATA_DIR, name)


def save(changes):
    """설정 일부를 바꿔 저장한다. changes는 {'tokens': {'use_article_body': False}} 처럼 중첩 dict. (GUI용)"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cur = json.load(f)
    except (OSError, ValueError):
        cur = {}

    def upd(dst, src):
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                upd(dst[k], v)
            else:
                dst[k] = v
    upd(cur, changes)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)
    return load(force=True)


def ensure_default_file():
    """config.json이 없으면 기본값으로 만든다."""
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULTS, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    ensure_default_file()
    load(force=True)
    print(json.dumps(load(), ensure_ascii=False, indent=2))
    for w in warnings():
        print("경고:", w)
