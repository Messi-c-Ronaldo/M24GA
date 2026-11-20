"""DynamicME 세부 값: 엔진 값 하나하나를 직접 정하는 편집 (E07).
덮어쓰기(overrides) = {항목 id: 값}. 빠른 조정(배율) 뒤에 마지막으로 적용돼요 (세부 값이 이긴다).
항목 id:
  phys:<키>                물리 값 (JSON 단위 그대로: 속도·킥 = m/s × 10000, 지연 = ms)
  w:<선발 방식>:<요인>       선발 가중치 (모든 버전 항목)
  m:<사건>:<구역>:<좌우>     모멘텀 점수
  rc:<계수 이름>            평점 계수 배율 (모든 역할·버전에 곱함, 1.0 = 그대로)
  rs:start                 평점 시작값 (6700 = 6.7점)
  re:<번호>:pos|neg         기대 결과 배율 (1000 = 1.0배)
  xg:<슛 종류>:intercept|<계수 이름>  xG 모델 절편·계수 (실제 값 = JSON ÷ 1e7, 모든 버전 항목에, E10)
  st:<폴더>:a|t:<번호>:min|max  전술 스타일 팀 지시(a)·성향(t) 범위 (E09). 스타일에 없는 번호를 정하면 새 항목으로 더해요
"""
import m24engine as E

PHYS_KO = {
    "very_slow_walk_speed": "아주 느린 걷기", "slow_walk_speed": "느린 걷기", "walk_speed": "걷기", "fast_walk_speed": "빠른 걷기",
    "slow_jog_speed": "느린 조깅", "jog_speed": "조깅", "moderate_jog_speed": "보통 조깅", "fast_jog_speed": "빠른 조깅",
    "run_speed": "달리기", "sprint_speed": "전력질주", "top_speed": "최고 속도", "base_top_speed": "기본 최고 속도",
    "theoretical_max_running_speed": "이론상 최대 달리기 속도",
    "soft_kick_speed": "아주 약한 킥", "soft_to_medium_kick_speed": "약한 킥", "medium_kick_speed": "보통 킥",
    "medium_to_moderate_kick_speed": "보통~중간 킥", "moderate_kick_speed": "중간 킥", "quite_hard_kick_speed": "꽤 강한 킥",
    "hard_kick_speed": "강한 킥", "very_hard_kick_speed": "아주 강한 킥", "basic_header_speed": "헤더 공 속도",
    "theoretical_min_diving_speed": "골키퍼 다이빙 속도 (최소)", "theoretical_max_diving_speed": "골키퍼 다이빙 속도 (최대)",
    "theoretical_min_acceleration": "가속 (최소)", "theoretical_max_acceleration": "가속 (최대)",
    "theoretical_min_diving_acceleration": "골키퍼 다이빙 가속 (최소)", "theoretical_max_diving_acceleration": "골키퍼 다이빙 가속 (최대)",
    "theoretical_min_deceleration": "감속 (최소)", "theoretical_max_deceleration": "감속 (최대)",
    "theoretical_max_turning_rate": "최대 회전 속도 (도/초)",
    "theoretical_max_potential_direction_change_walk": "걷기 방향 전환 (최대)", "theoretical_min_potential_direction_change_walk": "걷기 방향 전환 (최소)",
    "theoretical_max_potential_direction_change_jog": "조깅 방향 전환 (최대)", "theoretical_min_potential_direction_change_jog": "조깅 방향 전환 (최소)",
    "theoretical_max_potential_direction_change_run": "달리기 방향 전환 (최대)", "theoretical_min_potential_direction_change_run": "달리기 방향 전환 (최소)",
}
_DELAY_WORDS = [
    ("diving_header", "다이빙 헤더"), ("normal_header", "일반 헤더"), ("slide_tackle", "슬라이딩 태클"), ("ball_lunge", "공 향해 몸 뻗기"),
    ("block_tackle", "블록 태클"), ("deflect_ball", "공 굴절"), ("shoulder_charge", "어깨 싸움"),
    ("force_opponent_to_lose_ball", "몸으로 공 빼앗기"), ("shirt_tug", "유니폼 잡기"), ("obstruct", "진로 방해"),
    ("two_footed_tackle", "양발 태클"), ("foot_up_in_tackle", "발 들고 태클"), ("for_trip", "발 걸기"), ("push_opponen", "밀기"),
    ("violent_act", "폭력 행위"), ("celebrating_a_goal", "골 세리머니"),
    ("keeper_save_intentionally_drop_ball", "키퍼: 선방 뒤 일부러 공 떨어뜨리기"), ("keeper_save_dive_and_hold_ball", "키퍼: 다이빙해서 잡기"),
    ("keeper_save_dive_but_not_held", "키퍼: 다이빙했지만 못 잡음"), ("keeper_save_no_dive_hold_ball", "키퍼: 다이빙 없이 잡기"),
    ("keeper_save_no_dive_not_held", "키퍼: 다이빙 없이 못 잡음"), ("keeper_drop_ball_for_distribution", "키퍼: 배급하려 공 내려놓기"),
    ("keeper_save_with_outreached_foot", "키퍼: 발 뻗어 막기"), ("falling_down_before_injury", "다치기 전 넘어짐 (추가)"),
    ("player_stop_to_avoid_collision", "충돌 피하려 멈춤"), ("getting_injured", "부상"),
]


def _delay_ko(k):
    name = next((ko for w, ko in _DELAY_WORDS if w in k), k)
    if k.endswith("_do"):
        name += " (하는 쪽)"
    elif k.endswith("_receive"):
        name += " (당하는 쪽)"
    return name


STYLE_KO = {"TEAM_PICKING_STYLE::TPS_FIRST_TEAM_PICKING": "1군 (가장 강한 선발)",
            "TEAM_PICKING_STYLE::TPS_SLIGHTLY_RESERVE_PICKING": "약간 로테이션",
            "TEAM_PICKING_STYLE::TPS_SEMI_RESERVE_PICKING": "반 로테이션",
            "TEAM_PICKING_STYLE::TPS_TOTAL_RESERVE_PICKING": "전면 로테이션 (2군)"}
FACTOR_KO = {
    "POSITION_ABILITY": "포지션 능력", "POSITION_ABILITY_IN_ROLE": "역할에서의 포지션 능력", "POSITION_TACTICAL_FAMILARITY": "전술 익숙함",
    "LOAN_TERMS": "임대 조건", "MATCH_RATING_TIME_ON": "출전 시간 대비 평점", "CONDITION": "컨디션", "ALLOWED_MINS": "허용 출전 시간 (넘으면 감점)",
    "CA": "현재 능력 (CA)", "PA": "잠재 능력 (PA)", "REPUTATION": "명성", "YOUNG_PLAYERS": "어린 선수", "MORALE": "사기",
    "TESTIMONIAL": "기념 경기", "FOOTBALL_PROMISES": "출전 약속", "BOOST_LOW_MATCH_FITNESS": "경기 감각 낮은 선수 기용",
    "CUP_KEEPER": "컵 대회 골키퍼", "PPMS": "선수 성향 (PPM)", "HUMAN_SELECTION": "사람 감독이 고른 선수",
    "TRIALIST_B_TEAM_PLAYERS": "입단 테스트·B팀 선수", "DECLARED_FOR_RESERVES": "2군 지정", "CAPTAINCY": "주장",
    "UNHAPPINESS": "불만", "INTERNATIONAL_CAPS": "A매치 경력", "CLUB_NATION_CHOICE_FACTORS": "구단·국가 선택 요인", "FORM": "폼",
    "AGREED_PLAYING_TIME": "계약 출전 시간", "PLAYING_SIDE_PREFERENCE": "선호하는 쪽 (발)", "MATCH_FITNESS": "경기 체력",
    "BOOST_SUBSTITUTE": "교체 선수 가산", "STAR_PLAYER": "스타 선수", "OLYMPIC_U23": "올림픽 U23", "REST_PROMISES": "휴식 약속 (감점)",
    "UPCOMING_SUSPENSION": "다가오는 출전 정지 (감점)", "NEED_MATCH_XP": "경기 경험이 필요한 선수", "DISLIKE_BY_NON_PLAYER": "스태프가 싫어함",
    "INTEGRATION": "팀 적응", "LAST_RATINGS": "최근 평점", "VIRTUAL": "가상 선수 (감점)", "EXTRA_ADJ": "추가 보정"}
EVENT_KO = {"CBE_END_SHOT_GONE_IN": "골", "CBE_END_SHOT_MISSED_TARGET": "슛 빗나감", "CBE_END_SHOT_HIT_WOODWORK": "골대",
            "CBE_END_SHOT_SAVED": "선방당한 슛", "CBE_END_SHOT_BLOCKED": "막힌 슛", "CBE_END_PASS_COMPLETED": "패스 성공", "CBE_TOUCH": "공 터치"}
ZONE_KO = {"FIRST_SIXTH": "자기 진영 맨 뒤", "SECOND_SIXTH": "자기 진영 뒤", "THIRD_SIXTH": "자기 진영 앞",
           "FOURTH_SIXTH": "상대 진영 앞", "FIVTH_SIXTH": "상대 진영 깊숙이", "FINAL_SIXTH": "상대 문전"}
THIRD_KO = {"LEFT_THIRD": "왼쪽", "CENTRAL_THIRD": "가운데", "RIGHT_THIRD": "오른쪽"}
COEF_KO = {
    "90min Adjuster": "기본 보정 (90분)", "Goals": "골", "Good Goal Adder": "좋은 골 추가", "Great Goal Adder": "멋진 골 추가",
    "Decisive Goal": "결승골", "Decisive Late Goal": "후반 막판 결승골", "Cumulative Goal Bonus": "여러 골 보너스",
    "Goals minus xG times 100 (only if negative)": "xG보다 적게 넣음 (감점)", "Assists": "도움", "Cumulative Assist Bonus": "여러 도움 보너스",
    "Shots": "슛", "Shots On Target": "유효 슛", "Penalties Scored": "PK 득점", "Penalties Missed": "PK 실축", "Key Passes": "키 패스",
    "Passes Completed": "패스 성공", "Passes Incomplete": "패스 실패", "Dribbles": "드리블", "Times Was Fouled": "파울 얻음",
    "Crosses Completed": "크로스 성공", "Crosses Incompleted": "크로스 실패", "Chances Created": "찬스 만듦", "Open Play xA": "필드 xA",
    "Tackles Won": "태클 성공", "Tackles Lost": "태클 실패", "Interceptions": "가로채기", "Fouls Committed": "파울 범함", "Blocks": "블록",
    "Clearances": "걷어내기", "Mistakes Leading to Goals": "실점으로 이어진 실수", "Possession Won": "공 탈취",
    "Aerial Duels Won": "공중볼 이김", "Aerial Duels Lost": "공중볼 짐", "Clean Sheet": "무실점", "Own Goal": "자책골", "Saves": "선방",
    "Good Saves Adder": "좋은 선방 추가", "Great Saves Adder": "멋진 선방 추가", "Penalties Saved Adder": "PK 선방",
    "Penalties Conceded": "PK 허용", "Keeper less than 5 shot boost": "키퍼: 슛 5개 미만 받은 경기", "Yellow Card": "경고",
    "Second Yellow Card": "두 번째 경고", "Red Card": "퇴장", "Shootout Scored": "승부차기 성공", "Shootout Missed": "승부차기 실축",
    "Shootout Saved": "승부차기 선방", "Shootout Winning Pen": "승부차기 결승골", "Shootout Saved Pen to Win": "승부차기 이기는 선방",
    "Shootout Missed Losing Pen": "승부차기 지는 실축", "Team Goals For": "팀 득점", "Team Goals Conceded": "팀 실점"}
EXPECT_KO = {"Exceed Significant with Win": "예상보다 훨씬 잘함 (승리)", "Exceed Significant with Draw": "예상보다 훨씬 잘함 (무승부)",
             "Exceed with Win": "예상보다 잘함 (승리)", "Exceed with Draw": "예상보다 잘함 (무승부)", "Exceed Same Result": "예상보다 잘함 (같은 결과)",
             "Neutral": "예상대로", "Deceed Significant with Loss": "예상보다 훨씬 못함 (패배)", "Deceed Significant with Draw": "예상보다 훨씬 못함 (무승부)",
             "Deceed with Loss": "예상보다 못함 (패배)", "Deceed with Draw": "예상보다 못함 (무승부)", "Deceed Same Result": "예상보다 못함 (같은 결과)"}

# 전술 스타일 (styles.xml 순서, 이름은 게임 한국어판)
TACTIC_STYLES = [("control_possession", "점유율 중시"), ("gegenpress", "게겐프레스"), ("tiki-taka", "티키타카"),
                 ("vertical_tiki-taka", "전진 티키타카"), ("wing_play", "측면 플레이"), ("route_one", "길게 차기"),
                 ("fluid_counter-attack", "유연한 역습"), ("direct_counter-attack", "빠른 역습"), ("catenaccio", "카테나치오"),
                 ("park_the_bus", "버스 세우기")]
# 팀 지시(attribute_template)와 성향(tendency_template) 번호 -> (원래 이름, 한국어). 원본 파일 주석에서 모음 (E09)
STYLE_ATTR = {0: ("ATTACKING", "공격 성향 (멘탈리티)"), 3: ("DIRECTNESS", "패스 직선성"), 10: ("CLOSING_DOWN", "압박 강도"),
              19: ("DEPTH", "수비 라인 깊이 (높을수록 내려섬)"), 20: ("FLUIDITY", "유동성"), 24: ("TEMPO", "템포"), 25: ("WIDTH", "공격 폭"),
              40: ("DIRTINESS_ALLOWANCE", "거친 태클 허용")}
STYLE_TEND = {21: ("NPT_TENDENCY_TO_USE_COUNTER_ATTACKING", "역습 활용"), 38: ("NPT_TENDENCY_TO_RELY_ON_SET_PIECES", "세트피스 의존"),
              75: ("NPT_TENDENCY_TO_ALLOW_CREATIVE_FREEDOM", "창의적 자유"), 76: ("NPT_TENDENCY_TO_MAN_MARK", "대인 마크"),
              77: ("NPT_TENDENCY_TO_HOLD_DEFENSIVE_LINE", "수비 라인 유지"), 80: ("NPT_TENDENCY_TO_USE_CROSSES", "크로스 활용"),
              81: ("NPT_TENDENCY_TO_LOOK_FOR_UNDERLAP", "언더래핑"), 82: ("NPT_TENDENCY_TO_LOOK_FOR_OVERLAP", "오버래핑"),
              84: ("NPT_TENDENCY_TO_WORK_BALL_INTO_BOX", "박스 안까지 공 몰고 가기"), 85: ("NPT_TENDENCY_TO_PLAY_OUT_OF_DEFENCE", "수비 진영부터 빌드업"),
              87: ("NPT_TENDENCY_TO_PREVENT_THE_CROSS", "크로스 막기"), 89: ("NPT_TENDENCY_TO_FOCUS_PLAY_DOWN_THE_FLANKS", "측면 위주 공격"),
              90: ("NPT_TENDENCY_TO_PRESS_INTENSELY", "강한 압박"), 91: ("NPT_TENDENCY_TO_COUNTERPRESS", "역압박 (카운터프레스)")}

XG_KO = {"regular": "일반 슛", "volleys": "발리", "headers": "헤더", "free_kicks": "직접 프리킥", "penalties": "페널티킥",
         "open_goal_regular": "빈 골문 슛", "open_goal_volleys": "빈 골문 발리", "open_goal_headers": "빈 골문 헤더",
         "obscured_regular": "시야 가린 슛", "obscured_volleys": "시야 가린 발리", "obscured_headers": "시야 가린 헤더"}
XG_COEF_KO = {"intercept": "기본값 (절편, 높을수록 xG가 커져요)", "fraction_of_goal_visible": "보이는 골문 비율",
              "normalised_distance_to_closest_occluding_player": "가장 가까운 방해 선수 거리", "normalised_distance_to_goal": "골문까지 거리",
              "normalised_height_of_ball": "공 높이", "normalised_players_between_shot_and_goal": "슛과 골문 사이 선수 수",
              "transformed_angle_from_player_facing_to_centre_of_goal": "몸 방향과 골문 중앙의 각도",
              "transformed_angle_from_shot_location_to_centre_of_goal": "슛 위치와 골문 중앙의 각도"}

SECTIONS = [
    {"id": "phys_speed", "label": "선수 물리 · 이동 속도 (13)", "hint": "값 ÷ 10000 = 초당 미터"},
    {"id": "phys_ball", "label": "선수 물리 · 킥·헤더·골키퍼 다이빙 (11)", "hint": "값 ÷ 10000 = 초당 미터"},
    {"id": "phys_accel", "label": "선수 물리 · 가속·감속 (6)", "hint": "값 ÷ 가속 배율(보통 10000)"},
    {"id": "phys_turn", "label": "선수 물리 · 회전·방향 전환 (7)", "hint": "정수"},
    {"id": "phys_delay", "label": "경합·반칙·골키퍼 최소 지연 (39)", "hint": "밀리초, 0.25초(250) 단위로 들어가요. 높이면 그 행동이 덜 자주"},
] + [{"id": "w_%d" % i, "label": "AI 선발 가중치 · %s (39)" % STYLE_KO[s], "hint": "높을수록 그 요인을 크게 따져요 (음수 = 감점)"}
     for i, s in enumerate(E.WEIGHT_STYLES)] + [
    {"id": "momentum", "label": "경기 흐름 (모멘텀) (48)", "hint": "사건이 일어난 구역별로 흐름을 바꾸는 크기"},
    {"id": "rating_coef", "label": "경기 평점 · 계수 배율 (52)", "hint": "모든 포지션 역할의 그 계수에 곱해요. 1.00 = 그대로"},
    {"id": "rating_misc", "label": "경기 평점 · 시작값·예상 결과 (23)", "hint": "시작값 6700 = 6.7점에서 시작. 예상 결과 배율 1000 = 1.0배"},
    {"id": "xg", "label": "xG 모델 · 슛 종류별 절편·계수 (77)",
     "hint": "슛이 골이 될 확률 모델 (로지스틱). 절편을 올리면 그 슛 종류가 더 잘 들어가요 (예: 직접 프리킥 -4.785 → -4.283)"},
] + [{"id": "st_" + f, "label": "전술 스타일 · %s (%d)" % (ko, 2 * (len(STYLE_ATTR) + len(STYLE_TEND))),
      "hint": "AI 감독이 이 스타일을 쓸 때 팀 지시·성향을 고르는 범위 (보통 1~20). '-'는 이 스타일에 없는 항목이에요: 값을 정하면 더해요"}
     for f, ko in TACTIC_STYLES]


def _style(t, folder):
    return next((s for s in ((t or {}).get("styles") or {}).get("styles", []) if s["folder"] == folder), None)


def _newest(arr, vk):
    return max(arr, key=lambda e: E.ver_tuple_me(e[vk]))


def items(section, base, orig):
    """세부 값 목록. base/orig = {표: JSON} (기준 = 팩 또는 원본, 빠른 조정 전). 반환 [{id, label, base, orig, kind}]"""
    out = []
    if section.startswith("phys_"):
        pb, po = _newest(base["physics"]["version_array"], "min_me_version"), _newest(orig["physics"]["version_array"], "min_me_version")
        keys = {"phys_speed": E.PHYS_SPEED[:13], "phys_ball": E.PHYS_SPEED[13:], "phys_accel": E.PHYS_ACCEL,
                "phys_turn": E.PHYS_I16, "phys_delay": E.PHYS_DELAYS}[section]
        for k in keys:
            ko = PHYS_KO.get(k) or _delay_ko(k)
            out.append({"id": "phys:" + k, "label": ko, "key": k, "base": pb.get(k, po.get(k)), "orig": po.get(k),
                        "kind": "int" if k in E.PHYS_I16 or k in E.PHYS_DELAYS else "num"})
    elif section.startswith("w_"):
        st = E.WEIGHT_STYLES[int(section[2:])]
        wb, wo = _newest(base["weights"]["WEIGHTS"], "ME_VERSION"), _newest(orig["weights"]["WEIGHTS"], "ME_VERSION")
        for f in E.WEIGHT_FACTORS:
            k = "simatchshared::TSF_" + f
            out.append({"id": "w:%s:%s" % (section[2:], f), "label": FACTOR_KO.get(f, f), "key": f,
                        "base": wb.get(st, {}).get(k), "orig": wo.get(st, {}).get(k), "kind": "int"})
    elif section == "momentum":
        def rows(t):
            return {(e["CBE_EVENT_TYPE"], e["VERTICAL_ZONES"], e["HORIZONTAL_THIRDS"]): e["MOMENTUM"] for e in t["momentum"]["values"]}
        rb, ro = rows(base), rows(orig)
        for k in sorted(ro, key=lambda k: (list(EVENT_KO).index(k[0]) if k[0] in EVENT_KO else 99, list(ZONE_KO).index(k[1]), list(THIRD_KO).index(k[2]))):
            out.append({"id": "m:%s:%s:%s" % k, "label": "%s · %s %s" % (EVENT_KO.get(k[0], k[0]), ZONE_KO[k[1]], THIRD_KO[k[2]]),
                        "key": "/".join(k), "base": rb.get(k, ro[k]), "orig": ro[k], "kind": "int"})
    elif section == "rating_coef":
        e = _newest(orig["ratings"]["values"], "version")
        for c in e["role_data"][0]["coefficients"]:
            out.append({"id": "rc:" + c["name"], "label": COEF_KO.get(c["name"], c["name"]), "key": c["name"],
                        "base": 1.0, "orig": 1.0, "kind": "mul"})
    elif section == "rating_misc":
        eb, eo = _newest(base["ratings"]["values"], "version"), _newest(orig["ratings"]["values"], "version")
        out.append({"id": "rs:start", "label": "시작 평점 (6700 = 6.7)", "key": "start_value", "base": eb["start_value"], "orig": eo["start_value"], "kind": "int"})
        for i, (xb, xo) in enumerate(zip(eb["expected_score_data"], eo["expected_score_data"])):
            nm = EXPECT_KO.get(xo["name"], xo["name"])
            out.append({"id": "re:%d:pos" % i, "label": nm + " · 올림 배율", "key": xo["name"], "base": xb["positive_multiplier"], "orig": xo["positive_multiplier"], "kind": "int"})
            out.append({"id": "re:%d:neg" % i, "label": nm + " · 깎음 배율", "key": xo["name"], "base": xb["negative_multiplier"], "orig": xo["negative_multiplier"], "kind": "int"})
    elif section == "xg":
        def newest(t):
            x = (t or {}).get("xg") or {}
            return x[max(x, key=lambda v: tuple(map(int, v.split("."))))] if x else {}
        nb, no = newest(base), newest(orig)
        for st in E.XG_TYPES:
            o, b = no.get(st), nb.get(st) or no.get(st)
            if not o:
                continue
            for k in ["intercept"] + sorted(o["coefficients"]):
                ov = o["intercept"] if k == "intercept" else o["coefficients"][k]
                bv = (b["intercept"] if k == "intercept" else b["coefficients"].get(k, ov))
                out.append({"id": "xg:%s:%s" % (st, k), "label": "%s · %s" % (XG_KO[st], XG_COEF_KO.get(k, k)), "key": k,
                            "base": bv / E.XG_SCALE, "orig": ov / E.XG_SCALE, "kind": "num"})
    elif section.startswith("st_"):
        folder = section[3:]
        sb, so = _style(base, folder) or {"attr": [], "tend": []}, _style(orig, folder) or {"attr": [], "tend": []}
        for k, names, word in (("a", STYLE_ATTR, "팀 지시"), ("t", STYLE_TEND, "성향")):
            key = "attr" if k == "a" else "tend"
            rb, ro = {r[0]: r for r in sb[key]}, {r[0]: r for r in so[key]}
            ids = [i for i in names if i in rb or i in ro] + [i for i in names if i not in rb and i not in ro] +                   sorted(i for i in set(rb) | set(ro) if i not in names)
            for i in ids:
                en, ko = names.get(i, ("#%d" % i, "%s %d번" % (word, i)))
                for j, side in ((1, "min"), (2, "max")):
                    out.append({"id": "st:%s:%s:%d:%s" % (folder, k, i, side), "label": "%s · %s" % (ko, "최소" if j == 1 else "최대"),
                                "key": en, "base": rb[i][j] if i in rb else None, "orig": ro[i][j] if i in ro else None, "kind": "int"})
    return out


def clean(ov):
    """덮어쓰기 정리: 숫자로 바꿀 수 없는 것 버림."""
    out = {}
    for k, v in (ov or {}).items():
        if not isinstance(k, str) or ":" not in k:
            continue
        try:
            out[k] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def apply(tables, ov):
    """빠른 조정까지 끝난 표(사본)에 세부 값을 덮어쓴다. tables는 이미 사본이어야 한다 (dme_tune.apply 결과나 deepcopy)."""
    import copy
    ov = clean(ov)
    if not ov:
        return tables
    t = {k: copy.deepcopy(v) for k, v in tables.items()}
    for k, v in ov.items():
        kind, rest = k.split(":", 1)
        if kind == "phys" and t.get("physics"):
            for e in t["physics"]["version_array"]:
                if rest in E.PHYS_I16:
                    e[rest] = int(round(v))
                elif rest in E.PHYS_DELAYS:
                    e[rest] = int(round(v / 250.0)) * 250
                else:
                    e[rest] = v
        elif kind == "w" and t.get("weights"):
            si, f = rest.split(":", 1)
            st = E.WEIGHT_STYLES[int(si)]
            for e in t["weights"]["WEIGHTS"]:
                if st in e:
                    e[st]["simatchshared::TSF_" + f] = int(round(v))
        elif kind == "m" and t.get("momentum"):
            ev, zn, th = rest.split(":")
            hit = False
            for e in t["momentum"]["values"]:
                if (e["CBE_EVENT_TYPE"], e["VERTICAL_ZONES"], e["HORIZONTAL_THIRDS"]) == (ev, zn, th):
                    e["MOMENTUM"] = int(round(v)); hit = True
            if not hit:
                t["momentum"]["values"].append({"CBE_EVENT_TYPE": ev, "VERTICAL_ZONES": zn, "HORIZONTAL_THIRDS": th, "MOMENTUM": int(round(v))})
        elif kind == "rc" and t.get("ratings"):
            for e in t["ratings"]["values"]:
                for r in e["role_data"]:
                    for c in r["coefficients"]:
                        if c["name"] == rest and int(c["value"]) != -30000:
                            c["value"] = int(round(c["value"] * v))
        elif kind == "rs" and t.get("ratings"):
            for e in t["ratings"]["values"]:
                e["start_value"] = int(round(v))
        elif kind == "xg" and t.get("xg"):
            st, k = rest.split(":", 1)
            for types in t["xg"].values():
                d = types.get(st)
                if not d:
                    continue
                if k == "intercept":
                    d["intercept"] = int(round(v * E.XG_SCALE))
                elif k in d["coefficients"]:
                    d["coefficients"][k] = int(round(v * E.XG_SCALE))
        elif kind == "st" and t.get("styles"):
            folder, k, i, side = rest.rsplit(":", 3)
            st = _style(t, folder)
            if st:
                rows = st["attr" if k == "a" else "tend"]
                row = next((r for r in rows if r[0] == int(i)), None)
                val = max(-1, min(255, int(round(v))))   # -1 = 쓰지 않음 (원본 거친 태클 허용), 메모리에는 255
                if row is None:
                    rows.append([int(i), val, val])
                else:
                    row[1 if side == "min" else 2] = val
        elif kind == "re" and t.get("ratings"):
            i, side = rest.split(":")
            for e in t["ratings"]["values"]:
                x = e["expected_score_data"][int(i)]
                x["positive_multiplier" if side == "pos" else "negative_multiplier"] = int(round(v))
    return t
