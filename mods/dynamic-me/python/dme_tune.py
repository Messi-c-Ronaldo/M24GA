"""DynamicME 실시간 조정: 사람이 알아보는 조절값(배율) -> 엔진 표(JSON 모양)를 고친 사본.
기준 표(원본 또는 고른 팩)에 배율을 곱한다. 모든 버전 항목에 똑같이 곱해서, 게임이 어느 항목을 쓰든 같게 바뀐다.
기본 조절값(level basic)과 고급 조절값(level adv)은 겹쳐서 곱해진다 (예: 이동 속도 × 전력질주)."""
import copy
import math

import m24engine as E

_SP = E.PHYS_SPEED
_D = lambda *names: [k for k in E.PHYS_DELAYS if any(n in k for n in names)]   # noqa: E731

# 조절값: key, label, group, level, min, max, help, 대상 하나 이상
#   physics: 물리 키(속도·킥·가속·회전, 지연 포함)   weights: 선발 요인   ratings: 평점 계수 이름
#   rating_expect: 기대 이상/이하 결과 배율(1000에서 벗어난 만큼)   momentum: True(전부) 또는 사건 이름 목록
#   xg: 슛 종류 목록 (절편에 ln(배율)을 더함 = 골이 될 승산(odds)을 배율만큼. 확률이 낮은 슛은 거의 그대로 배율만큼)
#   styles: {"attr": [팀 지시 번호], "tend": [성향 번호]} 모든 AI 전술 스타일의 그 범위(최소·최대)에 배율 (0~20으로 자름)
_XG_OPEN = ["regular", "volleys", "headers", "open_goal_regular", "open_goal_volleys", "open_goal_headers",
            "obscured_regular", "obscured_volleys", "obscured_headers"]
KNOBS = [
    # ---- 기본
    {"key": "speed", "label": "선수 이동 속도", "group": "선수 움직임", "level": "basic", "min": 0.80, "max": 1.20,
     "help": "걷기부터 전력질주·최고 속도까지 한꺼번에 곱해요. 1.05 = 5% 빠르게", "physics": _SP[:13]},
    {"key": "accel", "label": "가속·감속", "group": "선수 움직임", "level": "basic", "min": 0.70, "max": 1.30,
     "help": "출발·멈춤이 얼마나 빠른지예요 (다이빙 가속 포함)", "physics": E.PHYS_ACCEL},
    {"key": "turn", "label": "방향 전환·회전", "group": "선수 움직임", "level": "basic", "min": 0.70, "max": 1.30,
     "help": "드리블·수비에서 몸을 돌리는 정도예요 (정수로 들어가요)", "physics": E.PHYS_I16},
    {"key": "kick", "label": "슛·패스 세기", "group": "공", "level": "basic", "min": 0.80, "max": 1.20,
     "help": "약한 패스부터 강슛까지 공 속도를 곱해요", "physics": _SP[13:21]},
    {"key": "header", "label": "헤더 세기", "group": "공", "level": "basic", "min": 0.70, "max": 1.30,
     "help": "헤더로 보내는 공의 속도예요", "physics": ["basic_header_speed"]},
    {"key": "w_ca", "label": "선발에서 능력(CA) 비중", "group": "AI 선발 성향", "level": "basic", "min": 0.0, "max": 2.0,
     "help": "AI 감독이 선발을 고를 때 현재 능력을 얼마나 따지는지예요", "weights": ["CA"]},
    {"key": "w_condition", "label": "선발에서 컨디션 비중", "group": "AI 선발 성향", "level": "basic", "min": 0.0, "max": 2.0,
     "help": "지친 선수를 쉬게 하는 정도예요 (높이면 로테이션이 늘어요)", "weights": ["CONDITION", "MATCH_FITNESS"]},
    {"key": "w_form", "label": "선발에서 폼·최근 평점 비중", "group": "AI 선발 성향", "level": "basic", "min": 0.0, "max": 2.0,
     "help": "요즘 잘하는 선수를 쓰는 정도예요", "weights": ["FORM", "LAST_RATINGS"]},
    {"key": "w_reputation", "label": "선발에서 명성·스타 비중", "group": "AI 선발 성향", "level": "basic", "min": 0.0, "max": 2.0,
     "help": "이름값 있는 선수를 쓰는 정도예요", "weights": ["REPUTATION", "STAR_PLAYER"]},
    {"key": "w_young", "label": "유망주 기용", "group": "AI 선발 성향", "level": "basic", "min": 0.0, "max": 3.0,
     "help": "어린 선수·PA 높은 선수를 쓰는 정도예요", "weights": ["YOUNG_PLAYERS", "PA"]},
    {"key": "momentum", "label": "경기 흐름(모멘텀) 변화 크기", "group": "경기 흐름", "level": "basic", "min": 0.5, "max": 2.0,
     "help": "슛·골·패스 같은 사건이 경기 흐름을 얼마나 크게 바꾸는지예요", "momentum": True},
    {"key": "xg_open", "label": "필드 슛 골 확률", "group": "골 확률 (xG)", "level": "basic", "min": 0.5, "max": 2.0,
     "help": "필드골(일반 슛·발리·헤더, 빈 골문·시야 가림 포함)이 들어갈 가능성이에요. 1.20 = 가능성 약 20% 증가", "xg": _XG_OPEN},
    {"key": "xg_fk", "label": "직접 프리킥 골 확률", "group": "골 확률 (xG)", "level": "basic", "min": 0.3, "max": 3.0,
     "help": "직접 프리킥이 골이 될 가능성이에요. 2.00 = 가능성 약 2배", "xg": ["free_kicks"]},
    {"key": "st_attack", "label": "AI 공격 성향", "group": "AI 전술 성향", "level": "basic", "min": 0.5, "max": 1.5,
     "help": "AI 감독이 고르는 공격 성향(멘탈리티)을 모든 전술 스타일에서 곱해요. 높이면 AI 팀이 더 공격적이에요", "styles": {"attr": [0]}},
    {"key": "st_press", "label": "AI 압박", "group": "AI 전술 성향", "level": "basic", "min": 0.5, "max": 1.5,
     "help": "압박 강도와 강한 압박·역압박 성향이에요. 높이면 AI 팀이 앞에서부터 강하게 압박해요", "styles": {"attr": [10], "tend": [90, 91]}},
    {"key": "st_tempo", "label": "AI 템포", "group": "AI 전술 성향", "level": "basic", "min": 0.5, "max": 1.5,
     "help": "AI 팀의 경기 속도(템포)예요", "styles": {"attr": [24]}},

    # ---- 고급: 선수 움직임
    {"key": "a_walkjog", "label": "걷기·조깅 속도", "group": "고급 · 선수 움직임", "level": "adv", "min": 0.80, "max": 1.20,
     "help": "공 없이 자리 잡을 때의 속도예요", "physics": _SP[:8]},
    {"key": "a_sprint", "label": "달리기·전력질주·최고 속도", "group": "고급 · 선수 움직임", "level": "adv", "min": 0.80, "max": 1.20,
     "help": "역습·침투 때의 속도예요", "physics": _SP[8:13]},
    {"key": "a_accel", "label": "가속", "group": "고급 · 선수 움직임", "level": "adv", "min": 0.70, "max": 1.30,
     "help": "출발하는 빠르기예요", "physics": ["theoretical_min_acceleration", "theoretical_max_acceleration"]},
    {"key": "a_decel", "label": "감속", "group": "고급 · 선수 움직임", "level": "adv", "min": 0.70, "max": 1.30,
     "help": "멈추는 빠르기예요", "physics": ["theoretical_min_deceleration", "theoretical_max_deceleration"]},
    {"key": "a_gkdive", "label": "골키퍼 다이빙 속도·가속", "group": "고급 · 선수 움직임", "level": "adv", "min": 0.80, "max": 1.25,
     "help": "몸을 날리는 선방의 빠르기예요", "physics": ["theoretical_min_diving_speed", "theoretical_max_diving_speed",
                                                     "theoretical_min_diving_acceleration", "theoretical_max_diving_acceleration"]},
    {"key": "a_turnrate", "label": "최대 회전 속도", "group": "고급 · 선수 움직임", "level": "adv", "min": 0.70, "max": 1.30,
     "help": "제자리에서 몸을 돌리는 최대 빠르기예요", "physics": ["theoretical_max_turning_rate"]},
    {"key": "a_dirchange", "label": "방향 전환 (걷기·조깅·달리기)", "group": "고급 · 선수 움직임", "level": "adv", "min": 0.70, "max": 1.30,
     "help": "움직이면서 방향을 꺾는 정도예요. 높이면 드리블이 날카로워져요", "physics": E.PHYS_I16[1:]},
    # ---- 고급: 공
    {"key": "a_kick_short", "label": "짧은 패스 세기", "group": "고급 · 공", "level": "adv", "min": 0.80, "max": 1.20,
     "help": "약한 패스·짧은 연결", "physics": _SP[13:16]},
    {"key": "a_kick_mid", "label": "중간 패스·크로스 세기", "group": "고급 · 공", "level": "adv", "min": 0.80, "max": 1.20,
     "help": "중거리 패스·크로스·프리킥 일부", "physics": _SP[16:18]},
    {"key": "a_kick_hard", "label": "강한 슛·롱볼 세기", "group": "고급 · 공", "level": "adv", "min": 0.80, "max": 1.20,
     "help": "중거리슛·강슛·롱볼. 너무 높이면 골대·중거리 골이 늘 수 있어요", "physics": _SP[18:21]},
    # ---- 고급: 경합·반칙 (최소 지연, 높이면 덜 자주)
    {"key": "d_tackle_do", "label": "태클 다시 시도까지 간격", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "슬라이딩·블록·런지·양발·발 들기 태클을 한 뒤 다시 하기까지의 최소 시간이에요 (0.25초 단위)",
     "physics": _D("slide_tackle_do", "block_tackle_do", "ball_lunge_do", "two_footed_tackle_do", "foot_up_in_tackle_do")},
    {"key": "d_tackle_recv", "label": "태클 당한 뒤 회복 시간", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "태클을 당한 선수가 다시 움직이기까지예요",
     "physics": _D("slide_tackle_receive", "block_tackle_receive", "ball_lunge_receive", "two_footed_tackle_receive", "foot_up_in_tackle_receive")},
    {"key": "d_contact", "label": "몸싸움 간격 (어깨·밀기·공 뺏기·막기·유니폼)", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "몸싸움 행동을 하거나 당한 뒤의 최소 시간이에요",
     "physics": _D("shoulder_charge", "push_opponen", "force_opponent", "obstruct", "shirt_tug")},
    {"key": "d_violent", "label": "거친 행동·걸기 간격", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "폭력 행위·발 걸기의 최소 시간이에요", "physics": _D("violent_act", "for_trip")},
    {"key": "d_header", "label": "헤더 간격 (다이빙·일반)", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "헤더를 다시 하기까지의 최소 시간이에요", "physics": _D("diving_header", "normal_header")},
    {"key": "d_keeper", "label": "골키퍼 동작 지연", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "선방 뒤 공 잡기·떨어뜨리기·배급까지의 시간이에요. 낮추면 빠른 배급·연속 선방", "physics": _D("keeper_")},
    {"key": "d_injury", "label": "부상·넘어짐 지연", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "다치거나 넘어진 뒤의 시간이에요", "physics": _D("getting_injured", "falling_down")},
    {"key": "d_misc", "label": "기타 지연 (공 굴절·충돌 피하기·골 세리머니)", "group": "고급 · 경합·반칙 (높이면 덜 자주)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "공이 맞고 굴절된 뒤, 부딪히지 않으려 멈추는 시간, 골 뒤 세리머니예요", "physics": _D("deflect_ball", "player_stop", "celebrating")},
    # ---- 고급: AI 선발 요인
    {"key": "w_position", "label": "포지션 능력 비중", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "그 자리·역할에 맞는 선수를 쓰는 정도예요", "weights": ["POSITION_ABILITY", "POSITION_ABILITY_IN_ROLE"]},
    {"key": "w_familiar", "label": "전술 익숙함 비중", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "전술에 익숙한 선수를 쓰는 정도예요", "weights": ["POSITION_TACTICAL_FAMILARITY"]},
    {"key": "w_morale", "label": "사기·불만 비중", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "사기·불만을 따지는 정도예요", "weights": ["MORALE", "UNHAPPINESS"]},
    {"key": "w_promises", "label": "출전 약속·계약 출전 시간", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "약속한 출전·계약 조건을 지키는 정도예요", "weights": ["FOOTBALL_PROMISES", "AGREED_PLAYING_TIME", "LOAN_TERMS"]},
    {"key": "w_rest", "label": "휴식 약속·출전 제한", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "쉬게 해 주겠다는 약속, 출전 시간 제한을 지키는 정도예요 (원래 음수 값)", "weights": ["REST_PROMISES", "ALLOWED_MINS"]},
    {"key": "w_ppms", "label": "선수 성향(PPM) 비중", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 3.0,
     "help": "선수 고유 플레이 성향을 따지는 정도예요", "weights": ["PPMS"]},
    {"key": "w_cup", "label": "컵 대회 키퍼·2군 지정", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "컵 대회용 골키퍼, 2군으로 지정한 선수를 따르는 정도예요", "weights": ["CUP_KEEPER", "DECLARED_FOR_RESERVES"]},
    {"key": "w_misc", "label": "주장·국가대표·발 방향", "group": "고급 · AI 선발", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "주장, A매치 경력, 선호하는 쪽을 따지는 정도예요", "weights": ["CAPTAINCY", "INTERNATIONAL_CAPS", "PLAYING_SIDE_PREFERENCE"]},
    # ---- 고급: 경기 평점 (계수 배율, 모든 역할)
    {"key": "r_goal", "label": "평점: 득점", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "골·결승골·멋진 골·PK 골이 평점을 올리는 크기예요",
     "ratings": ["Goals", "Good Goal Adder", "Great Goal Adder", "Decisive Goal", "Decisive Late Goal", "Cumulative Goal Bonus", "Penalties Scored"]},
    {"key": "r_assist", "label": "평점: 도움·찬스", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "도움·키 패스·찬스 만들기", "ratings": ["Assists", "Cumulative Assist Bonus", "Key Passes", "Chances Created", "Open Play xA"]},
    {"key": "r_shot", "label": "평점: 슈팅", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "슛·유효 슛", "ratings": ["Shots", "Shots On Target"]},
    {"key": "r_pass", "label": "평점: 패스·크로스·드리블", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "패스·크로스 성공과 실패, 드리블, 파울 얻기",
     "ratings": ["Passes Completed", "Passes Incomplete", "Crosses Completed", "Crosses Incompleted", "Dribbles", "Times Was Fouled"]},
    {"key": "r_def", "label": "평점: 수비", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "태클·가로채기·블록·걷어내기·공 탈취·공중볼",
     "ratings": ["Tackles Won", "Tackles Lost", "Interceptions", "Blocks", "Clearances", "Possession Won", "Aerial Duels Won", "Aerial Duels Lost"]},
    {"key": "r_gk", "label": "평점: 골키퍼", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "선방·PK 선방·무실점·슛을 적게 받은 경기",
     "ratings": ["Saves", "Good Saves Adder", "Great Saves Adder", "Penalties Saved Adder", "Keeper less than 5 shot boost", "Clean Sheet"]},
    {"key": "r_bad", "label": "평점: 실수·카드·반칙", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "실점 실수·자책골·파울·PK 허용·경고·퇴장·PK 실축이 평점을 깎는 크기예요",
     "ratings": ["Mistakes Leading to Goals", "Own Goal", "Fouls Committed", "Penalties Conceded", "Yellow Card",
                 "Second Yellow Card", "Red Card", "Penalties Missed", "Goals minus xG times 100 (only if negative)"]},
    {"key": "r_team", "label": "평점: 팀 득실", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "팀 득점·실점이 모든 선수 평점에 주는 영향이에요", "ratings": ["Team Goals For", "Team Goals Conceded"]},
    {"key": "r_expect", "label": "평점: 예상보다 잘하고 못한 결과", "group": "고급 · 경기 평점", "level": "adv", "min": 0.0, "max": 2.0,
     "help": "약팀이 이기거나 강팀이 질 때 더하고 빼는 배율이에요", "rating_expect": True},
    # ---- 고급: 골 확률·AI 전술
    {"key": "xg_pen", "label": "페널티킥 골 확률", "group": "고급 · 골 확률 (xG)", "level": "adv", "min": 0.5, "max": 2.0,
     "help": "페널티킥이 들어갈 가능성이에요", "xg": ["penalties"]},
    {"key": "st_direct", "label": "AI 패스 직선성", "group": "고급 · AI 전술 성향", "level": "adv", "min": 0.5, "max": 1.5,
     "help": "높이면 AI 팀이 짧게 이어가기보다 앞으로 곧장 질러요", "styles": {"attr": [3]}},
    {"key": "st_width", "label": "AI 공격 폭", "group": "고급 · AI 전술 성향", "level": "adv", "min": 0.5, "max": 1.5,
     "help": "높이면 AI 팀이 측면을 넓게 써요", "styles": {"attr": [25]}},
    {"key": "st_fluid", "label": "AI 유동성", "group": "고급 · AI 전술 성향", "level": "adv", "min": 0.5, "max": 1.5,
     "help": "높이면 AI 팀 선수들이 자리를 자유롭게 바꿔요", "styles": {"attr": [20]}},
    # ---- 고급: 모멘텀 사건별
    {"key": "m_goal", "label": "모멘텀: 골", "group": "고급 · 경기 흐름", "level": "adv", "min": 0.0, "max": 3.0,
     "help": "골이 흐름을 바꾸는 크기예요", "momentum": ["CBE_END_SHOT_GONE_IN"]},
    {"key": "m_shot", "label": "모멘텀: 골이 아닌 슛", "group": "고급 · 경기 흐름", "level": "adv", "min": 0.0, "max": 3.0,
     "help": "빗나감·골대·선방·막힘", "momentum": ["CBE_END_SHOT_MISSED_TARGET", "CBE_END_SHOT_HIT_WOODWORK", "CBE_END_SHOT_SAVED", "CBE_END_SHOT_BLOCKED"]},
    {"key": "m_play", "label": "모멘텀: 패스·터치", "group": "고급 · 경기 흐름", "level": "adv", "min": 0.0, "max": 3.0,
     "help": "상대 진영에서 패스 성공·공 터치", "momentum": ["CBE_END_PASS_COMPLETED", "CBE_TOUCH"]},
]
KNOB_KEYS = {k["key"]: k for k in KNOBS}


def clean(tune):
    """조절값 dict 정리: 아는 키만, 범위 안으로, 1.0(바꾸지 않음)은 뺀다."""
    out = {}
    for k, v in (tune or {}).items():
        d = KNOB_KEYS.get(k)
        if not d:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        v = min(max(v, d["min"]), d["max"])
        if abs(v - 1.0) > 1e-9:
            out[k] = round(v, 3)
    return out


def _mul_phys(e, k, f):
    if k not in e:
        return
    if k in E.PHYS_I16:
        e[k] = int(round(float(e[k]) * f))
    elif k in E.PHYS_DELAYS:
        e[k] = int(round(float(e[k]) * f / 250.0)) * 250   # 게임은 0.25초 단위
    else:
        e[k] = e[k] * f


def apply(tables, tune):
    """tables = {표: JSON 값} (원본이나 팩). 배율을 곱한 사본을 돌려준다 (원본은 그대로)."""
    tune = clean(tune)
    if not tune:
        return tables
    t = {k: copy.deepcopy(v) for k, v in tables.items()}
    for key, f in tune.items():
        d = KNOB_KEYS[key]
        if d.get("physics") and t.get("physics"):
            for e in t["physics"]["version_array"]:
                for k in d["physics"]:
                    _mul_phys(e, k, f)
        if d.get("weights") and t.get("weights"):
            for e in t["weights"]["WEIGHTS"]:
                for st in E.WEIGHT_STYLES:
                    for k in d["weights"]:
                        kk = "simatchshared::TSF_" + k
                        if kk in e.get(st, {}):
                            e[st][kk] = int(round(e[st][kk] * f))
        if d.get("ratings") and t.get("ratings"):
            names = set(d["ratings"])
            for e in t["ratings"]["values"]:
                for r in e["role_data"]:
                    for c in r["coefficients"]:
                        if c["name"] in names and int(c["value"]) != -30000:
                            c["value"] = int(round(c["value"] * f))
        if d.get("rating_expect") and t.get("ratings"):
            for e in t["ratings"]["values"]:
                for x in e["expected_score_data"]:
                    for k in ("positive_multiplier", "negative_multiplier"):
                        x[k] = int(round(1000 + (x[k] - 1000) * f))
        if d.get("momentum") and t.get("momentum"):
            names = None if d["momentum"] is True else set(d["momentum"])
            for e in t["momentum"]["values"]:
                if names is None or e["CBE_EVENT_TYPE"] in names:
                    e["MOMENTUM"] = int(round(e["MOMENTUM"] * f))
        if d.get("xg") and t.get("xg"):
            add = int(round(math.log(f) * E.XG_SCALE))
            for types in t["xg"].values():
                for st in d["xg"]:
                    if st in types:
                        types[st]["intercept"] += add
        if d.get("styles") and t.get("styles"):
            for st in t["styles"]["styles"]:
                for kind, ids in (("attr", d["styles"].get("attr", [])), ("tend", d["styles"].get("tend", []))):
                    for row in st[kind]:
                        if row[0] in ids:
                            row[1] = min(20, max(0, int(round(row[1] * f))))
                            row[2] = min(20, max(0, int(round(row[2] * f))))
    return t
