# -*- coding: utf-8 -*-
"""FM24 AI 소셜피드 모드: 문장 생성 모듈 (작성: Claude Sonnet)

게임/메모리를 건드리지 않는다. 입력은 글 원문(게임 마크업 포함)과 부모 글 문맥이고,
출력은 게임 마크업이 들어간 새 문장이다. 실패하면 None (호출자는 원문을 유지한다).

API 키: ~/.deepseek_key (한 줄). 로그나 코드에 키를 쓰지 않는다.
"""
import json
import os
import random
import re
import sys
import time
import urllib.request

# feed_markup.py는 이 폴더에 둔다 (11-08: logs 폴더 정리로 logs/tools 의존을 없앴다. 원본 개발본은 logs/AI소셜피드/tools)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feed_markup as fm  # noqa: E402

if not getattr(sys, "frozen", False):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as cfg  # noqa: E402  (API 주소/모델/비율/켜고 끄기 옵션은 모두 config.json에서 읽는다)
cfg.ensure_default_file()

SYSTEM = """너는 디시인사이드 해외축구 갤러리와 에펨코리아 축구 게시판에서 노는 눈치 빠른 축구 팬이다. 그 커뮤니티의 실제 댓글 말투로 쓴다.
말투 규칙:
- 반말. 짧고 자극적으로, 흥분하거나 비꼬거나 한탄한다. 1~2문장, 공백 포함 70자 이내.
- 초성 줄임말(ㄹㅇ, ㅇㅈ, ㅅㅂ, ㅠㅠ 등)은 거의 쓰지 말고 풀어 쓴 말로 표현한다. 댓글 열 개 중 한두 개만 쓴다.
- 개, 존나, 미쳤다, 실화냐, 레전드, 지렸다, 어이없네, 답없다, 말이 되냐, 소름, 환장하겠네, 가관이다, 눈물 난다 같은 표현과 인터넷 말투를 자연스럽게 섞는다. 매번 다른 표현을 쓰고, '폼 미쳤다'를 남발하지 않는다. 문장마다 시작과 끝 표현을 다르게 한다. 'ㅋ'은 한 글자도 쓰지 않는다.
- 감정을 과장한다 (극찬이면 호들갑, 실망이면 분노나 체념). 비꼬기와 드립도 좋다.
- 평점·골 같은 숫자는 꼭 필요할 때만 쓰고, 보통은 '폼 미쳤다', '요즘 최악' 같은 말로 바꿔 쓴다.
- 우승·수상·승리·칭찬 같은 좋은 소식에 억지로 비난이나 방출 얘기를 붙이지 않는다 (비꼬기는 라이벌 팬 관점일 때만).
- 원래 댓글의 내용 자체를 언급하거나 평가하지 않는다 (예: '그 얘기가 왜 나와' 금지). 새 댓글은 글 상황에 대한 반응이다.
- 뉴스 제목의 사정을 잘못 읽지 않는다. 예: '10명의 OO'는 퇴장으로 한 명이 적은 채 뛰었다는 뜻이다.
- 상황에 대한 욕설은 써도 된다 (ㅅㅂ, 좆같네, 지랄, 존나, 개같네). 가장 센 욕은 'ㅅㅂ'로만 쓰고 풀어 쓰지 않는다. 감정이 센 댓글(분노, 환호, 한탄)에서는 세 개 중 한 개꼴로 꼭 섞어 쓰고, 덤덤한 댓글은 욕 없이 쓴다.
- 선수·감독·보드진·다른 팬에 대한 거친 비난도 현실감 있게 써도 된다 (먹튀, 무능, 이딴 플레이 하려고 뛰냐, 감독 나가라, 보드진 일 안 하냐, 지랄하네, 쓰레기 같은 플레이 등). 열 개 중 두세 개 정도로, 플레이·결정·성과를 겨냥해서 쓴다.
- 인종·국적·지역·성별·장애·외모를 겨냥한 비하와 혐오, 성적 표현, 가족 욕, 신체 위해(다치길 바람, 죽어라 등)를 바라는 말은 절대 쓰지 않는다.
- 이모지, 해시태그, 따옴표는 쓰지 않는다.
이름 규칙:
- 이름은 반드시 자리표시자 {P1}, {T1} 등으로만 쓴다. 단, 게임 데이터에 나온 선수 이름(최다 득점자 등)은 그대로 써도 된다. 이름 뒤 조사는 {P1}{은/는}, {T1}{이/가}, {P1}{을/를}, {T1}{와/과}, {T1}{으로/로}, {P1}{이다/다} 처럼 조사 쌍으로 쓴다. 조사가 필요 없으면 자리표시자만 쓴다.
- 허용된 자리표시자 외의 이름이나 사실(점수, 날짜, 순위, 시간대 등)을 지어내지 않는다. 주어진 정보만 쓴다.
- '뉴스 기사 본문'이 있으면 그 사실(나이, 경력, 순위, 득점자, 이적료, 소문 내용 등)은 써도 된다. 본문에만 나오는 사람 이름은 그대로 써도 된다. 기사를 요약하지 말고, 팬이 기사에서 꽂힌 한 가지에 반응한다.
- '게임 데이터'는 참고용이다. 댓글 주제와 직접 맞을 때만 사실 하나를 자연스럽게 녹이고, 억지로 넣지 않는다. 국가대표·대회·수상 소식에는 클럽 시즌 기록을 끌어오지 않는다. 숫자는 게임 데이터에 있는 것만 쓴다. 포지션을 보고 판단한다(골키퍼에게 골 기록을 따지지 않는다). 경기 결과 글이면 가끔 팀 최다 득점자 같은 핵심 선수를 이름으로 언급한다 (예: 역시 OO가 해결해 준다, OO 없으면 어쩔 뻔했냐).
출력은 댓글 문장 하나뿐. 설명을 붙이지 않는다."""


# ---- 최근 표현 추적: 자주 나온 인터넷 표현은 "쓰지 말 것"으로 알려 주고, 그래도 쓰면 다시 만든다 ----
import collections
import threading

SLANG = ["ㅇㅈ", "ㅠㅠ", "ㄹㅇ", "ㅅㅂ", "답없", "폼 미쳤", "실화냐", "존나", "레전드", "지렸",
         "어이없", "미쳤다", "개꿀", "ㅡㅡ", "ㄷㄷ", "ㅎㅎ", "진짜 ", "솔직히", "ㅋ",
         # 상투 드립 (11-08: 1,495개 중 골대 3.7%, 축구화 2.7%, 호구 2.6%가 반복) -> 최근에 두 번 나오면 금지 목록에 올린다
         "골대", "축구화", "탁구", "연봉 반납", "발롱도르", "관중석", "죄인", "호구", "꼴값", "고집", "4-3-3"]
RECENT_N = 24            # 최근 이 개수의 출력만 본다
BAN_AT = 2               # 최근 N개 중 이만큼 이상 나온 표현은 금지
_recent = collections.deque(maxlen=RECENT_N)
_recent_lock = threading.Lock()


def _banned():
    with _recent_lock:
        txts = list(_recent)
    return [w for w in SLANG if w != "ㅋ" and sum(1 for t in txts if w in t) >= BAN_AT]


def _remember(text):
    with _recent_lock:
        _recent.append(text)


def _key():
    with open(cfg.data_path(cfg.get("api.key_file")), encoding="utf-8") as f:
        return f.read().strip()


def export_default_prompt():
    """내장 말투를 데이터 폴더의 system_prompt.default.txt로 내보낸다 (복사해서 고친 뒤 style.system_prompt_file에 이름을 적으면 대체됨)."""
    p = cfg.data_path("system_prompt.default.txt")
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p) or open(p, encoding="utf-8").read() != SYSTEM:
            with open(p, "w", encoding="utf-8") as f:
                f.write(SYSTEM)
    except OSError:
        pass


def get_system():
    """말투 지침 = (내장 또는 파일) + 설정에 따른 덧붙임. 설정이 바뀌면 다음 호출부터 반영된다."""
    base = SYSTEM
    pf = cfg.get("style.system_prompt_file")
    if pf:
        try:
            with open(cfg.data_path(pf), encoding="utf-8") as f:
                txt = f.read().strip()
            if txt:
                base = txt
        except OSError:
            pass                              # 파일이 없으면 내장 말투
    extra = []
    sw = cfg.get("style.swear")
    if sw == "mild":
        extra.append("[설정] 욕설과 센 비속어(ㅅㅂ, 좆같네, 지랄, 존나, 개같네 등)는 쓰지 않는다. '답없다', '미쳤다', '어이없네' 정도의 순한 표현으로 감정을 드러낸다. 위 욕설 규칙과 충돌하면 이 줄이 우선한다.")
    elif sw == "wild":
        extra.append(
            "[설정: 야생의 인터넷 모드] 새벽 3시 해외축구 갤러리 분위기다. 위 말투 규칙보다 훨씬 세게 쓴다. 이 줄이 위 욕설 비율 규칙보다 우선한다.\n"
            "- 댓글 열 개 중 일고여덟 개에 욕설이나 거친 말을 넣는다 (ㅅㅂ, 좆같네, 지랄하네, 개같네, 존나, 개못하네, 개노답, 꼴값, 미쳤냐, 쓰레기 같은 플레이 등). 덤덤한 소식에도 흥분하거나 비꼰다.\n"
            "- 개드립을 적극적으로 쓴다: 과장, 엉뚱한 비유와 밈, 비꼬는 칭찬, 자조, 라이벌 팬 조롱. 드립은 그 글에 나온 구체적인 상황(득점 장면, 이적료, 상대 팀, 날씨, 경기장 등)에서 매번 새로 만든다. "
            "예시 문구를 외워서 돌려 쓰지 않는다.\n"
            "- 거칠다는 것은 말투가 세다는 뜻이지 부정적이라는 뜻이 아니다. 이겼거나 잘나가는 팀 팬은 욕을 섞어서 환호하고 자랑한다.\n"
            "- 선수·감독·보드진에 대한 비난은 더 거칠어도 된다 (찐따, 호구, 개호구, 쫄보 같은 원색적인 말도 된다). 단, 플레이·태도·결정·성적·몸값을 겨냥하고, 키·몸매·얼굴 같은 신체는 놀리지 않는다 (키는 '공중볼을 다 진다'처럼 플레이로만 말한다).\n"
            "- 이 모드에서도 금지선은 그대로다: 인종·국적·지역·성별·장애·외모 비하, 성적 표현, 가족 욕, 다치거나 죽기를 바라는 말은 절대 쓰지 않는다. 장애를 빗댄 욕(병신, 애자 등)도 쓰지 않는다. 가장 센 욕은 'ㅅㅂ'로만 쓴다.")
    elif sw == "none":
        extra.append("[설정] 욕설, 비속어, 거친 비난(먹튀, 무능 같은 인신공격성 표현 포함)을 쓰지 않는다. 비판은 플레이와 결정에 대해 담백하게 말한다. 위 욕설·비난 규칙과 충돌하면 이 줄이 우선한다.")
    if cfg.get("style.allow_k"):
        extra.append("[설정] 'ㅋ'은 가끔(열 개 중 한두 개) 써도 된다. 위 'ㅋ' 금지 규칙은 이 줄로 대체한다.")
    ex = cfg.get("style.extra_instructions").strip()
    if ex:
        extra.append("[추가 지침] " + ex)
    # 토큰 절약 (38번 로그 이후): 요청마다 같던 규칙을 시스템 쪽 고정 블록으로 옮겼다.
    # DeepSeek은 앞부분이 같으면 캐시(입력 1/50 가격)라서, 글 내용 뒤에 붙던 고정 문구가 매번 비싸게 계산되던 걸 막는다.
    # 이 블록은 설정(욕설 모드)이 바뀔 때만 달라진다 -> 랜덤 요소를 넣지 말 것.
    extra.append(_request_rules())
    if sw == "wild":
        extra.append(WILD_TURN % "댓글마다")
    return base + "\n" + "\n".join(extra)


def _dedupe_sentences(text):
    """같은 문장이 두 번 이상 나오면 처음 것만 남긴다."""
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    seen, out = set(), []
    for p in parts:
        k = p.strip()
        if k and k in seen:
            continue
        seen.add(k)
        out.append(p)
    return " ".join(out)


def _plain(text):
    """게임 마크업 → 사람이 읽는 글 ([이름] 형태 링크는 이름만)."""
    p = fm.parse_feed_text(text)
    out = p.body_template
    for e in p.entities:
        out = out.replace("{%s}" % e.key, e.name)
    return out


# 게임 데이터를 붙이는 비율은 config tokens.game_data_rate (기본 0.35: 매번 붙이면 모든 댓글이 기록 얘기만 한다)
# 클럽이 둘 이상 나오는 글(경기 결과 등)은 tokens.match_game_data_rate (기본 0.7: 전력 차 반응이 재미있다)


# ---- 순위 변동 (38번 로그) ----
# 게임의 순위 변동 속성 Lrps는 순위표 행 객체에 있는데 그 객체를 못 찾았다. 대신 클럽별 (치른 경기 수, 리그 순위)를
# 데이터 폴더 pos_history.json에 남겨 두고, 경기 수가 늘었을 때 직전 기록과 비교한다 (앱을 껐다 켜도 이어진다).
# 경기 수(Tomp)는 컵 대회도 포함 -> '최근 경기 사이 변동'. 경기 수가 줄면 새 시즌이라 처음부터.
_POS_PATH = os.path.join(cfg.DATA_DIR, "pos_history.json")
_pos_lock = threading.Lock()
_pos_hist = None


def _pos_change(d):
    """클럽 ctx -> (이전 순위, 지금 순위) 또는 None. 기록도 갱신한다."""
    global _pos_hist
    pos, omp = d.get("리그 순위"), d.get("_시즌 경기 수")
    key = d.get("full") or d.get("name")
    if not key or not isinstance(pos, int) or not isinstance(omp, int) or pos <= 0 or omp <= 0:
        return None
    with _pos_lock:
        if _pos_hist is None:
            try:
                with open(_POS_PATH, encoding="utf-8") as f:
                    _pos_hist = json.load(f)
            except Exception:  # noqa: BLE001
                _pos_hist = {}
        e = _pos_hist.get(key)
        changed = False
        if not e or omp < e.get("omp", 0):             # 처음 보거나 새 시즌
            e = {"omp": omp, "pos": pos}
            changed = True
        elif omp > e["omp"]:                             # 경기를 더 치렀다 -> 지금 기록이 '직전'이 된다
            e = {"omp": omp, "pos": pos, "prev_pos": e["pos"], "prev_omp": e["omp"]}
            changed = True
        elif pos != e["pos"]:                            # 같은 경기 수인데 순위만 바뀜 (다른 팀 경기 결과)
            e = dict(e, pos=pos)
            changed = True
        _pos_hist[key] = e
        if changed:
            try:
                tmp = _POS_PATH + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(_pos_hist, f, ensure_ascii=False)
                os.replace(tmp, _POS_PATH)
            except Exception:  # noqa: BLE001
                pass
        if "prev_pos" in e and e["prev_pos"] != pos:
            return e["prev_pos"], pos
    return None


def _pos_note(d):
    pc = _pos_change(d)
    if not pc:
        return None
    a, b = pc
    return "리그 순위 변동: %d위 → %d위 (%d계단 %s)" % (a, b, abs(a - b), "상승" if b < a else "하락")


def _form_seq_notes(seq):
    """hook의 _폼 (Tsof, [0]이 가장 최근. 3 승, 2·1 무, 0 패) -> 최근 흐름과 연속 기록 라벨 (38번 로그).
    목록 전체가 같은 결과면 그 이상일 수 있으니 '이상'을 붙인다."""
    if not isinstance(seq, list) or not seq:
        return []
    r = ["승" if x == 3 else "패" if x == 0 else "무" for x in seq]
    notes = ["최근 5경기 흐름(가장 최근부터): " + "-".join(r[:6])]

    def run(pred):
        n = 0
        for x in r:
            if not pred(x):
                break
            n += 1
        return n, ("%d경기 이상" % n if n == len(r) else "%d경기" % n)

    w, ws = run(lambda x: x == "승")
    l, ls = run(lambda x: x == "패")
    nw, nws = run(lambda x: x != "승")
    nl, nls = run(lambda x: x != "패")
    if w >= 2:
        notes.append(("%d연승 중" % w) if w < len(r) else "최근 %d경기 전승 (연승 중)" % w)
    elif l >= 2:
        notes.append(("%d연패 중" % l) if l < len(r) else "최근 %d경기 전패 (연패 중)" % l)
    if nw >= 3 and nw > l:
        notes.append(("%d경기째 무승" % nw) if nw < len(r) else "최근 %d경기 내내 무승" % nw)
    if nl >= 4 and nl > w:
        notes.append(("%d경기 무패" % nl) if nl < len(r) else "최근 %d경기 내내 무패" % nl)
    if r[0] == "패" and l == 1 and len(r) >= 4 and r[1:4].count("승") == 3:
        notes.append("연승 행진이 직전 경기에서 끊김")
    return notes


def _club_notes(d):
    """클럽 수치 -> 해석 라벨 (AI가 숫자만 보고 맥락을 놓치지 않게)."""
    notes = ["국가대표팀"] if d.get("_대표팀") else []   # 38번 로그: 대표팀도 클럽 표에 들어간다 (리그 순위·재정은 없음)
    pos, pred = d.get("리그 순위"), d.get("미디어 예상 순위")
    if pos and pred:
        if pred - pos >= 4:
            notes.append("시즌 전 예상(%d위)보다 훨씬 잘하는 중: 돌풍" % pred)
        elif pos - pred >= 4:
            notes.append("시즌 전 예상(%d위)보다 훨씬 못하는 중: 부진·몰락" % pred)
    form = next((v for k, v in d.items() if k.startswith("최근 ") and k.endswith("경기")), None)
    if form:
        w, dr, l = (int(x[:-1]) for x in form.split())
        if l == 0 and dr == 0 and w >= 4:
            notes.append("최근 전승 행진")
        elif w == 0:
            notes.append("최근 승리가 없음")
        elif l >= 3:
            notes.append("최근 부진")
    pn = _pos_note(d)
    if pn:
        notes.append(pn)
    notes += _form_seq_notes(d.get("_폼"))   # 38번 로그: Tfrm(화면 '최근 성적') 기준. Tsof로 했다가 틀려서 바꿨다
    if d.get("연패", 0) >= 3:
        notes.append("%d연패 중" % d["연패"])
    if d.get("연승", 0) >= 4:
        notes.append("%d연승 중" % d["연승"])
    if d.get("무승 경기 수", 0) >= 4:
        notes.append("%d경기째 무승" % d["무승 경기 수"])
    if d.get("무득점 경기 수", 0) >= 2:
        notes.append("%d경기째 무득점" % d["무득점 경기 수"])
    spend = d.get("이적 순지출(원)")
    if spend and spend >= 100_000_000_000:
        notes.append("이적료를 많이 쓴 팀")
    notes += _club_situation_notes(d)
    return notes


def _club_situation_notes(d):
    """클럽 사정 (34번 로그): 게임 내부 금액(×KRW_PER_UNIT = 원)을 말로만 바꾼다. 정확한 금액은 프롬프트에 넣지 않는다."""
    notes = []
    rate = cfg.get("game.krw_per_unit")
    age, tix, atm, sup = d.get("_c_평균나이"), d.get("_c_티켓"), d.get("_c_분위기"), d.get("_c_감독지지")
    if age is not None:
        if age >= 28.5:
            notes.append("노장 위주의 늙은 스쿼드")
        elif age <= 25.5:
            notes.append("젊은 선수 위주의 스쿼드")
    if tix is not None:
        if tix >= 55:
            notes.append("티켓값이 비싸기로 유명한 구단")
        elif tix <= 10:
            notes.append("티켓값이 싼 서민 구단")
    if atm is not None:
        if atm >= 7:
            notes.append("홈 경기장 분위기가 뜨겁기로 유명")
        elif atm <= 3:
            notes.append("경기장이 썰렁한 편")
    if sup is not None:
        if sup >= 7:
            notes.append("팬들의 감독 지지가 두터움")
        elif sup <= 3:
            notes.append("팬들이 감독을 못 믿는 분위기")
    if cfg.get("tokens.use_club_finances"):
        won = lambda k: d.get(k) * rate if d.get(k) is not None else None
        budget, bal, wage, wbud = won("_c_이적예산"), won("_c_잔고"), d.get("_c_주급"), d.get("_c_주급예산")
        if budget is not None:
            if budget >= 300_000_000_000:
                notes.append("이적 시장의 큰손 (이적 예산이 막대함)")
            elif budget <= 1_000_000_000:
                notes.append("이적 예산이 거의 바닥")
        if bal is not None:
            if bal <= -5_000_000_000:
                notes.append("재정 적자 상태 (구단 잔고가 마이너스)")
            elif bal >= 300_000_000_000:
                notes.append("금고가 두둑한 구단")
        if wage and wbud and wage >= wbud * 1.0:
            notes.append("주급 예산을 이미 초과해서 쓰는 중")
    return notes


def _form_notes(avg, apps, recent_avg, recent):
    """시즌 평균과 최근 5경기 평점으로 폼 해석 라벨."""
    notes = []
    if avg is not None and apps and apps >= 5:
        if avg < 6.6:
            notes.append("시즌 내내 부진 (팬들이 팔라고 할 만함)")
        elif avg >= 7.4:
            notes.append("시즌 에이스급 활약")
    if avg is not None and recent_avg is not None and apps and apps >= 5:
        if recent_avg - avg >= 0.4:
            notes.append("최근 폼이 확 올라옴")
        elif avg - recent_avg >= 0.4:
            notes.append("최근 폼이 확 떨어짐 (벤치로 보내라, 팔아라 소리 나올 만함)")
    if recent and min(recent) <= 6.0:
        notes.append("최근 5경기 중 평점 %s짜리 최악의 경기가 있음" % min(recent))
    if recent and max(recent) >= 9.0:
        notes.append("최근 5경기 중 평점 %s짜리 인생 경기가 있음" % max(recent))
    return notes


def _person_notes(d):
    notes = []
    rec = [float(x) for x in str(d.get("최근 5경기 평점", "")).split("/") if x]
    notes += _form_notes(d.get("시즌 평균 평점"), d.get("시즌 출전"), d.get("최근 5경기 평균"), rec)
    rep, age = d.get("명성"), d.get("나이")
    if rep is not None:
        notes.append("월드클래스" if rep >= 8000 else "정상급" if rep >= 6500 else "준수한 선수" if rep >= 4500 else "무명")
    if age is not None:
        if age <= 21:
            notes.append("유망주")
        elif age >= 32:
            notes.append("베테랑")
    apps = d.get("이번 시즌 출전")
    if apps is not None and apps <= 3:
        notes.append("이번 시즌 거의 못 뛰는 중")
    keeper = d.get("주 포지션") == "골키퍼"
    # xG 대비 득점: 시즌 골과 xG의 차이 (경기 수가 어느 정도 쌓였을 때만)
    xg, goals, xgn = d.get("xG"), d.get("시즌 골"), d.get("xG 기준 경기") or 0
    if xg is not None and goals is not None and xgn >= 10 and not keeper:
        if goals - xg >= 3:
            notes.append("xG(%.1f)보다 골을 훨씬 많이 넣는 중: 결정력 폭발" % xg)
        elif xg - goals >= 3:
            notes.append("xG(%.1f)에 비해 골이 모자람: 좋은 찬스를 계속 날리는 중" % xg)
    yc, rc = d.get("시즌 경고"), d.get("시즌 퇴장")
    if yc is not None and yc >= 7:
        notes.append("경고를 %d개나 받은 거친 선수" % yc)
    if rc:
        notes.append("이번 시즌 퇴장 %d회" % rc)
    caps, ig = d.get("국가대표 출전"), d.get("국가대표 골")
    if caps and caps >= 50:
        notes.append("국가대표 주전급 (A매치 %d경기%s)" % (caps, ", %d골" % ig if ig and not keeper else ""))
    elif caps and caps >= 1:
        notes.append("국가대표 경험 있음 (A매치 %d경기)" % caps)
    mor = d.get("사기")
    if mor is not None:
        if mor >= 17:
            notes.append("사기가 하늘을 찌름")
        elif mor <= 7:
            notes.append("사기가 바닥 (불만이 쌓인 상태)")
    # 숨은 능력치 (스카우트해야 아는 정보 = 플레이에 힌트가 된다): 설정에서 켠 경우만
    if cfg.get("tokens.use_hidden_attributes"):
        h = lambda k: d.get("_숨_" + k)
        if h("논란 성향") is not None and h("논란 성향") >= 15:
            notes.append("구설수가 잦은 문제아 성향")
        if h("충성심") is not None:
            if h("충성심") >= 16:
                notes.append("의리 있는 원클럽맨 타입")
            elif h("충성심") <= 6:
                notes.append("더 좋은 조건이면 바로 떠날 타입")
        if h("야망") is not None and h("야망") >= 16:
            notes.append("야망이 커서 큰 팀을 노리는 타입")
        if h("부상 경향") is not None and h("부상 경향") >= 15:
            notes.append("부상이 잦은 유리몸")
    return notes


# 포메이션 번호표 (38번 로그): fm+0x1a0bd30(번호, 출력, 꼬리말 여부)를 게임에서 직접 불러 받은 한국어 이름.
# 빈 번호(1, 13, 17, 48, 49, 62)는 게임에서도 빈 문자열. 0·65 = '임의'(선호 없음).
# 4번은 함수가 "4-1-2-3 DM 넓게"를 내지만 감독 프로필 화면은 "4-3-3 DM 넓게"로 보인다 (사용자 확인: 과르디올라 Nppf=4)
FORMATIONS = {
    2: "5-3-2 WB", 3: "4-4-2", 4: "4-3-3 DM 넓게", 5: "4-2-4 넓게", 6: "3-5-2", 7: "4-4-2 다이아몬드형 좁게",
    8: "4-5-1", 9: "3-4-3", 10: "3-4-1-2", 11: "3-4-2-1", 12: "4-3-2-1 좁게", 14: "4-3-1-2 좁게",
    15: "5-4-1 다이아몬드형 WB", 16: "4-4-1-1", 18: "4-2-3-1 좁게", 19: "4-1-3-1-1 DM 좁게", 20: "4-1-3-2 DM 좁게",
    21: "4-2-3-1 넓게", 22: "4-2-2-2 DM", 23: "4-2-1-3 DM 넓게", 24: "4-2-2-2 DM 좁게", 25: "3-1-3-1-2 DM",
    26: "4-1-2-3 좁게", 27: "4-3-2-1 DM 좁게", 28: "4-2-4 DM 넓게", 29: "4-2-3-1 DM 넓게", 30: "5-1-2-2 DM WB",
    31: "3-4-2-1 DM", 32: "4-1-4-1 DM", 33: "4-4-1-1 2DM", 34: "3-2-3-2 DM", 35: "3-4-3 DM 넓게", 36: "4-3-3 좁게",
    37: "4-2-4", 38: "5-4-1", 39: "4-1-2-3 좁게", 40: "4-2-3-1 DM 좁게", 41: "5-2-1-2 WB", 42: "5-1-2-2 DM 좁게",
    43: "2-3-5", 44: "2-4-4", 45: "3-2-5", 46: "3-3-4", 47: "5-2-3 좁게", 50: "4-1-4-1 DM 비대칭 AML",
    51: "4-2-4-0 DM 넓게", 52: "4-1-3-2 DM", 53: "4-1-4-1 DM 비대칭 AML", 54: "4-2-3-1 DM", 55: "4-2-3-1-0 DM",
    56: "5-1-3-1 DM WB", 57: "5-2-2-1 DM", 58: "5-2-2-1-0 DM", 59: "5-2-2-1 WB", 60: "3-1-4-2 DM", 61: "5-2-3 WB 넓게",
    63: "3-4-3 DM 좁게", 64: "5-2-1-2 DM WB",
}
# 게임 이름은 팬이 쓰는 말과 다르다 (예: 4-1-2-3 DM 넓게 = 흔히 4-3-3). 팬 말투로 부를 이름.
_FORMATION_FAN = {4: "4-3-3", 23: "4-3-3", 26: "4-3-3", 39: "4-3-3", 36: "4-3-3", 7: "다이아몬드 4-4-2",
                  51: "제로톱", 55: "제로톱", 58: "제로톱"}


def _formation_note(d):
    """감독 선호 포메이션 → '선호 포메이션 4-3-3 (게임 표기 4-1-2-3 DM 넓게), 스리백' 같은 한 줄. 없으면 None."""
    n = d.get("_포메이션") if isinstance(d, dict) else None
    name = FORMATIONS.get(n)
    if not name:
        return None
    fan = _FORMATION_FAN.get(n) or name.split(" ")[0]
    back = "스리백" if name[0] == "3" else "파이브백(백5)" if name[0] == "5" else ""
    s = "선호 포메이션 %s" % fan + (" (게임 표기 %s)" % name if fan != name else "")
    return s + (", " + back + " 쓰는 감독" if back else "")


def _staff_notes(d):
    """감독·스태프 (33번 로그): 전술 지식·선수 관리·결단력(1~20), 명성(0~10000), 무직 여부 + 숨은 성향(설정)."""
    notes = []
    tk, mm, de, rep = d.get("전술 지식"), d.get("선수 관리"), d.get("결단력"), d.get("감독 명성")
    if rep is not None:
        notes.append("세계적인 명장" if rep >= 9000 else "이름 있는 감독" if rep >= 7000 else "중견 감독" if rep >= 5000 else "무명 감독")
    if tk is not None:
        if tk >= 17:
            notes.append("전술 천재 소리 듣는 전술가")
        elif tk <= 8:
            notes.append("전술 이해도가 떨어진다는 평")
    if mm is not None:
        if mm >= 17:
            notes.append("선수단 장악력·라커룸 관리 최고")
        elif mm <= 8:
            notes.append("선수단 관리를 못한다는 평 (라커룸 불화 걱정)")
    if de is not None and de >= 18:
        notes.append("승부욕·결단력이 강함")
    fm = _formation_note(d)
    if fm:
        notes.append(fm)
    if d.get("무직"):
        notes.append("현재 무직 (다음 행선지를 찾는 감독 후보)")
    age = d.get("나이")
    if age is not None:
        if age <= 40:
            notes.append("젊은 감독")
        elif age >= 62:
            notes.append("노장 감독")
    if cfg.get("tokens.use_hidden_attributes"):
        h = lambda k: d.get("_숨_" + k)
        if h("기질") is not None and h("기질") <= 5:
            notes.append("다혈질 (터치라인에서 폭발하는 타입)")
        if h("논란 성향") is not None and h("논란 성향") >= 15:
            notes.append("인터뷰마다 구설수")
        if h("야망") is not None and h("야망") >= 17:
            notes.append("야망이 커서 더 큰 팀을 노림")
        if h("충성심") is not None and h("충성심") <= 6:
            notes.append("좋은 제안 오면 바로 떠날 타입")
    return notes


def _strength_line(clubs, key_of):
    """두 클럽 이상이면 리그 순위로 전력 비교. 같은 리그가 아닐 수 있어 순위가 둘 다 있을 때만."""
    ranked = [d for d in clubs if d.get("리그 순위") and d.get("_시즌 경기 수") != 0]
    if len(ranked) < 2:
        return None
    ranked.sort(key=lambda d: d["리그 순위"])
    strong, weak = ranked[0], ranked[-1]
    if weak["리그 순위"] - strong["리그 순위"] < 5:
        return "전력 비교: 비슷한 전력 (%s %d위, %s %d위)" % (
            key_of(strong), strong["리그 순위"], key_of(weak), weak["리그 순위"])
    return ("전력 비교: %s(%d위)가 강팀, %s(%d위)가 약팀. 원래 댓글과 글을 보고 약팀이 이겼거나 비겼으면 이변으로, "
            "강팀이 졌으면 굴욕으로 반응한다 (단, 퇴장·부상 같은 사정이 뉴스에 있으면 그 사정을 짚는다)" % (key_of(strong), strong["리그 순위"], key_of(weak), weak["리그 순위"]))


def _data_rate(ctx):
    clubs = [d for d in ctx or [] if d.get("kind") == "클럽"]
    return cfg.get("tokens.match_game_data_rate" if len(clubs) >= 2 else "tokens.game_data_rate")


def _ctx_lines(ctx, parsed, force=False):
    """hook.js가 게임 함수로 읽은 클럽/선수 데이터 -> 프롬프트 줄. 이름은 자리표시자로 바꿔 보여 준다.
    force=True면 비율 판정 없이 넣는다 (묶음 생성: 데이터는 한 번 넣고 '몇 개만 인용'으로 비율을 맞춘다)."""
    if not ctx:
        return []
    clubs = [d for d in ctx if d.get("kind") == "클럽"]
    if not force and random.random() > _data_rate(ctx):
        return []
    keys = {e.name: e.key for e in parsed.entities}

    def key_of(d):
        name = d.get("name", "")
        return "{%s}" % keys[name] if name in keys else name

    out = ["게임 데이터 (실제 게임 수치, 이 안의 사실만 인용 가능):"]
    for d in ctx:
        if d.get("kind") == "클럽" and d.get("_시즌 경기 수") == 0:   # 시즌 전이면 순위·득실이 의미 없다
            d = {k: v for k, v in d.items() if k not in ("리그 순위", "리그 득점", "리그 실점", "최근 5경기", "_폼")}
        # 명성(0~10000)·사기(0~20)는 게임 내부 수치라 숫자 대신 라벨(월드클래스, 사기 바닥 등)만 준다 (38번 로그: "명성 9400짜리" 댓글)
        # 토큰 절약: 라벨로 이미 설명되는 원시 값은 뺀다 (이적 순지출 -> '이적료를 많이 쓴 팀', 미디어 예상 순위 -> 돌풍/부진,
        # 최근 N경기 합계 -> '최근 5경기 흐름')
        skip = {"name", "kind", "full", "xG 기준 경기", "명성", "사기", "이적 순지출(원)", "미디어 예상 순위"}
        facts = ["%s %s" % (k, v) for k, v in d.items()
                 if k not in skip and not k.startswith("_") and not (d.get("_폼") and k.startswith("최근 ") and k.endswith("경기"))]
        if d.get("주 포지션") == "골키퍼":
            facts = [f for f in facts if not f.startswith("xG ")]
        if d.get("kind") == "감독/스태프":   # 능력치 숫자(1~20)는 팬이 말할 정보가 아니다 -> 해석 라벨만 (나이만 남김)
            facts = [f for f in facts if f.startswith("나이 ")]
        notes = (_club_notes(d) if d.get("kind") == "클럽" else
                 _staff_notes(d) if d.get("kind") == "감독/스태프" else _person_notes(d))
        if d.get("_내팀"):   # 36번 로그: 플레이어가 감독인 팀
            notes = list(notes or []) + ["게임 플레이어 팀 (감독 %s)" % d["_내팀"]]
        if facts:
            out.append("  %s (%s%s): %s%s" % (key_of(d), d.get("kind", ""), ", " + d["full"] if d.get("full") else "",
                                              ", ".join(facts), (" → " + ", ".join(notes)) if notes else ""))
    for d in clubs:
        shown = 0
        for k, f in (d.get("_ids") or {}).items():
            if not k.startswith("_form_") or not isinstance(f, dict) or f.get("avg") is None:
                continue
            notes = _form_notes(f.get("avg"), f.get("apps"), f.get("recentAvg"), f.get("recent"))
            if not notes or shown >= 2:   # 토큰 절약: 할 말(폼 라벨)이 있는 선수만, 팀당 2명
                continue
            shown += 1
            name = k[len("_form_"):]
            txt = "시즌 평균 평점 %s(%s경기%s)" % (f["avg"], f.get("apps"), (", %s골" % f["goals"]) if f.get("goals") is not None else "")
            if f.get("recentAvg") is not None:
                txt += ", 최근 5경기 평균 %s" % f.get("recentAvg")
            out.append("  %s의 핵심 선수 %s: %s → %s" % (key_of(d), name, txt, ", ".join(notes)))
    s = _strength_line(clubs, key_of)
    if s:
        out.append("  " + s)
    return out if len(out) > 1 else []


# 핵심 선수 이름을 언급하게 하는 비율은 config tokens.player_mention_rate (기본 0.5)


def _mentionable_players(ctx, parsed, parent_text):
    """뉴스 제목이나 댓글 본문에 나온 팀의 핵심 선수만 "이름(소속)" 목록으로. 해시태그에만 나온 팀은 뺀다."""
    shown = set(e.name for e in parsed.entities)
    parent_plain = _plain(parent_text) if parent_text else ""
    out = []
    for d in ctx or []:
        if d.get("kind") != "클럽":
            continue
        club = d.get("name", "")
        if club not in shown and club not in parent_plain:
            continue
        for n in (d.get("_ids") or {}):
            if not n.startswith("_form_"):
                out.append("%s(%s 소속)" % (n, club))
    return list(dict.fromkeys(out))   # 게임 데이터가 붙은 댓글 중 핵심 선수 이름을 꼭 넣게 하는 비율


def _situation_note(text):
    """뉴스 제목에서 모델이 자주 거꾸로 읽는 표현을 풀어서 알려 준다."""
    m = re.search(r"(\d+)명의 ", _plain(text))
    if m and int(m.group(1)) < 11:
        return ("주의: 'N명의 팀'은 퇴장으로 %s명만 뛰어 수적으로 불리했다는 뜻이다. "
                "'%s명으로도', '%s명이 뛰고도'처럼 유리한 조건인 것처럼 쓰면 틀린다. 불리했던 사정을 전제로 쓴다." % ((m.group(1),) * 3))
    return None


# 같은 글 아래 댓글들이 같은 말을 반복하지 않게, 댓글마다 관점을 하나씩 무작위로 준다.
# 예전에는 14개 중 9개가 비판·한탄이라 전승 중인 팀 팬에게도 '전술 탓'이 자주 뽑혔다 (사용자 지적, 11-08).
# -> 긍정·부정·중립으로 나누고 작성자 팀 분위기(_mood)에 맞는 쪽에서만 뽑는다.
ANGLES_POS = ["과하게 흥분한 응원", "선수 찬양 (득점자, 폼 오른 선수)", "감독·전술 칭찬", "우승·순위 설레발",
              "상대 팀이나 라이벌 조롱", "다음 상대 깔보기", "이 기세면 뭐든 된다는 허세"]
ANGLES_NEG = ["심판 판정 탓", "감독 전술·교체 탓", "특정 선수(또는 수비진·공격진) 탓", "체념하고 자조", "다음 경기 걱정",
              "보드진·이적 정책 탓", "옛날이 그립다는 한탄",
              "부진한 선수 팔아라·벤치로 보내라 (게임 데이터에 부진·폼 하락 표시가 있을 때)"]
ANGLES_NEU = ["상대 팀을 인정하고 칭찬", "비꼬기와 드립", "냉정한 분석가 말투", "라이벌 팬처럼 조롱",
              "폼 오른 선수 칭찬 (게임 데이터에 폼 상승 표시가 있을 때)", "기사 속 사소한 디테일에 꽂힘"]
ANGLES = ANGLES_POS + ANGLES_NEG + ANGLES_NEU


def _mood(seq):
    """최근 경기 목록([0]이 최근, 3 승 / 2·1 무 / 0 패) -> ('good'|'bad'|None, 설명)."""
    if not isinstance(seq, list) or len(seq) < 3:
        return None, ""
    r = seq[:5]
    w, l = sum(1 for x in r if x == 3), sum(1 for x in r if x == 0)
    d = len(r) - w - l
    ws = next((i for i, x in enumerate(r) if x != 3), len(r))
    ls = next((i for i, x in enumerate(r) if x != 0), len(r))
    rec = "최근 %d경기 %d승 %d무 %d패" % (len(r), w, d, l)
    if w >= 4 or ws >= 3:
        return "good", rec
    if l >= 3 or ls >= 2 or w == 0:
        return "bad", rec
    return None, rec


def _mood_tag(fan):
    """작성자 줄에 붙일 팀 분위기 (hook fan.form)."""
    m, rec = _mood(fan.get("form") if isinstance(fan, dict) else None)
    if not rec:
        return None, ""
    return m, " [팀 분위기 %s: %s]" % ({"good": "최고", "bad": "바닥"}.get(m, "보통"), rec)


def _angles(moods, k):
    """작성자들 분위기에 맞는 관점 후보 k개. 좋은 팀만 있으면 비판 관점을 빼고, 나쁜 팀만 있으면 설레발을 뺀다."""
    good, bad = "good" in moods, "bad" in moods
    pool = (ANGLES_POS + ANGLES_NEU) if good and not bad else (ANGLES_NEG + ANGLES_NEU) if bad and not good else ANGLES
    return random.sample(pool, min(len(pool), k))


def link_known_players(text, ctx):
    """AI 문장에 나온 핵심 선수 이름(게임 데이터)을 게임 형식 링크로 바꾼다. 기존 링크·해시태그 안은 건드리지 않는다."""
    ids = {}
    for d in ctx or []:
        ids.update({k: v for k, v in (d.get("_ids") or {}).items() if not k.startswith("_form_")})
    if not ids:
        return text
    tag = text.find(fm.HASHTAG_OPEN)
    body, tail = (text, "") if tag < 0 else (text[:tag], text[tag:])
    parts = re.split(r"(\x01[^\x01\x02]*\x02[^\x01]*\x01)", body)
    done = set()
    for i in range(0, len(parts), 2):          # 짝수 칸 = 링크가 아닌 일반 글자
        for name, dref in ids.items():
            if name in done:
                continue
            shown = name if name in parts[i] else None
            last = name.split()[-1] if " " in name else None
            if shown is None and last and len(last) >= 2 and last in parts[i]:
                shown = last                         # AI가 성만 쓴 경우 (예: 아딩그라)
            if shown is None:
                continue
            try:
                parts[i] = parts[i].replace(shown, fm.make_person_link(shown, int(dref)), 1)
                done.add(name)
            except ValueError:
                pass
    return "".join(parts) + tail


# 기사 본문 사용/최대 글자 수는 config tokens.use_article_body / article_body_max_chars (비용: 약 +600 토큰, 같은 뉴스 댓글끼리는 캐시 적중)

# ---- 같은 글 아래 댓글끼리 겹침 방지 (2026-11-04, 22번 로그) ----
# 같은 부모 글 아래 이미 만든 댓글을 프롬프트에 알려 주고, 시작 표현이 같으면 다시 만든다.
# 겹침을 보려면 같은 글의 댓글을 동시에 만들면 안 되므로 thread_lock()으로 글별로 차례로 만든다.
# 글당 기억하는 댓글 수는 config tokens.sibling_count, 끄기는 tokens.sibling_hint
SIB_KEYS = 400           # 기억하는 글 수 (넘으면 오래된 것부터 버림)
OPEN_LEN = 4             # 시작 이 글자 수가 같으면 겹친 것으로 본다
_siblings = collections.OrderedDict()
_thread_locks = {}
_sib_lock = threading.Lock()


def _tkey(parent_text):
    return (parent_text or "")[:300]


def thread_lock(parent_text):
    k = _tkey(parent_text)
    with _sib_lock:
        return _thread_locks.setdefault(k, threading.Lock())


def _sibs(parent_text):
    if not cfg.get("tokens.sibling_hint"):
        return []                              # 끄면 프롬프트 줄도, 겹침 검사도 없다
    with _sib_lock:
        return list(_siblings.get(_tkey(parent_text), []))[-cfg.get("tokens.sibling_count"):]


def _add_sib(parent_text, plain):
    if not cfg.get("tokens.sibling_hint"):
        return
    k = _tkey(parent_text)
    with _sib_lock:
        lst = _siblings.setdefault(k, [])
        lst.append(plain)
        del lst[:-20]                          # 설정 최댓값(20)까지만 쌓고, 쓸 때 sibling_count로 자른다
        _siblings.move_to_end(k)
        while len(_siblings) > SIB_KEYS:
            old, _ = _siblings.popitem(last=False)
            _thread_locks.pop(old, None)


def _norm_open(t):
    return re.sub(r"[\s{}\d,.!?~…]", "", re.sub(r"\{[^{}]*\}", "", t))[:OPEN_LEN]


SHARE_LEN = 5            # 다른 댓글과 이 글자 수 이상 똑같은 구절이 있으면 겹친 것으로 본다 (6이면 '바르샤가 전승 달리는'/'바르샤 전승 달리는데'를 놓쳤다)


def _squash(t):
    return re.sub(r"[\s{}\d,.!?~…\-]", "", re.sub(r"\{[^{}]*\}", "", t))


def _dup_open(text, sibs):
    """시작 5글자가 같거나, 6글자 이상 똑같은 구절이 이미 나온 댓글에 있으면 True."""
    o = _norm_open(text)
    if o and any(_norm_open(s) == o for s in sibs):
        return True
    a = _squash(text)
    for s in sibs:
        b = _squash(s)
        if any(a[i:i + SHARE_LEN] in b for i in range(max(0, len(a) - SHARE_LEN + 1))):
            return True
    return False


# ---- 작성자 응원 클럽 (32번 로그): 댓글 레코드의 Salo(클럽 고유 ID) -> hook이 클럽 이름으로 바꿔 보낸다 ----
FAN_RULE = ("작성자 응원 팀 규칙: 작성자가 응원하는 팀이 글의 주인공이면 '우리 팀' 입장(기쁨, 분노, 한탄)으로, "
            "글에 나온 상대 팀이나 라이벌이면 그 팀 팬 입장(견제, 조롱, 남 일이라는 태도)으로, 글과 상관없는 팀이면 제3자 시선으로 쓴다. "
            "작성자 팀이 글에 나오지 않으면 그 팀이 영입하거나 이득을 보는 것처럼 쓰지 않는다 ('우리 팀 일'로 만들지 않는다). "
            "그때는 글에 나온 팀들을 구경하는 시선이고, 라이벌 팀의 손해는 반기고 이득은 배아파한다. "
            "원래 댓글의 감정(좋겠다, 싫다, 루머다)은 작성자 팀 입장에서 다시 해석한다. "
            "작성자 팀 이름이나 '우리 팀', '우리 애들' 같은 말은 그대로 써도 된다.")


def _fan_name(fan):
    if not isinstance(fan, dict):
        return None
    return fan.get("name") or fan.get("full")


# ---- 내 감독·내 클럽 (36번 로그): 게임 플레이어가 감독인 클럽과 감독 이름 ----
def _me(fan):
    """hook이 fan에 붙여 보낸 플레이어 정보 -> (감독 이름, 클럽 짧은 이름) 또는 (None, None)"""
    if not isinstance(fan, dict) or not fan.get("me_mgr"):
        return None, None
    return fan["me_mgr"], fan.get("me_club")


def _mine_note(fan):
    """작성자가 플레이어 클럽 팬일 때 붙는 한 줄. 아니면 ''."""
    mgr, club = _me(fan)
    if not mgr or not fan.get("mine"):
        return ""
    return ("이 작성자는 게임 플레이어가 감독인 %s의 팬이고, 우리 감독 이름은 %s. 글이 우리 팀 경기·선수·이적·감독 얘기일 때만 "
            "가끔 감독을 '%s', '%s 감독', '우리 감독' 등으로 불러 반응한다 (성적이 좋으면 칭찬·찬양, 나쁘면 전술·선발·교체 탓). "
            "글과 상관없으면 감독을 꺼내지 않는다. 감독 이름은 자리표시자 없이 그대로 써도 된다."
            % (club or "우리 팀", mgr, mgr, mgr[1:] if len(mgr) == 3 else mgr))


VACANT_NOTE = "감독 공석 (정식 감독 없이 시즌 중, 팬은 새 감독 선임을 기다리거나 구단 운영을 탓함)"


MGR_RULE = ("감독 언급 규칙: 글이 그 팀 경기·성적·선수·이적 얘기일 때만, 댓글 열 개 중 한 개 정도로 드물게 감독을 이름으로 부른다 "
            "(잘하면 칭찬·찬양, 못하면 전술·선발·교체 탓이나 경질 타령, 남의 팀 감독이면 비꼬거나 견제). "
            "글과 상관없으면 감독을 꺼내지 않는다. 감독 이름은 자리표시자 없이 그대로 써도 된다. "
            "선호 포메이션은 글이 전술·경기 내용일 때만, 스무 개 중 한 개 정도로 아주 드물게 쓴다. '○○ 고집' 같은 틀을 반복하지 않는다. "
            "'게임 표기'는 참고용이니 그대로 옮기지 않는다.")


def _mgr_with_label(name, attrs, caretaker=False):
    """감독 이름 + 성향 라벨 (37번 다음 작업 1). attrs = hook의 staffAttrs 숫자. 사람 감독은 attrs가 없어 이름만.
    라벨은 많아야 3개 (명성 → 전술 → 관리 순으로 _staff_notes가 낸다)."""
    if caretaker:   # 38번 로그: 정식 감독 없이 임시로 맡은 사람 (TMnR과 계약 표가 다름)
        name = "%s (임시 감독, 정식 감독 아님)" % name
    if not isinstance(attrs, dict) or not attrs:
        return name
    fm = _formation_note(attrs)
    keep_fm = fm and random.random() < FORMATION_RATE   # 11-08: 포메이션 언급이 너무 잦아서 (8%, '4-3-3 고집' 반복) 가끔만 알려 준다
    notes = [x for x in _staff_notes(attrs) if x != fm][:3] + ([fm] if keep_fm else [])
    return "%s (%s)" % (name, ", ".join(notes)) if notes else name


FORMATION_RATE = 0.3


def _in_article(team, parent_text, body, ctx):
    """작성자 팀이 이 글에 나오나 (글 제목·본문·링크된 클럽). 안 나오면 그 팀 감독 얘기를 꺼낼 일이 없다."""
    if not team:
        return False
    if any(d.get("kind") == "클럽" and d.get("name") == team for d in ctx or []):
        return True
    return team in ((_plain(parent_text) if parent_text else "") + " " + (body or ""))


def _own_mgr_note(fan, parent_text=None, body=None, ctx=None):
    """플레이어 팀이 아닌 팬: 자기 팀 감독 이름 + 성향 라벨 (hook이 계약 객체에서 읽은 1군 감독).
    11-08: 감독 언급이 24%나 돼서, 작성자 팀이 글에 나올 때만 알려 준다."""
    if not isinstance(fan, dict) or fan.get("mine"):
        return ""
    if not _in_article(_fan_name(fan), parent_text, body, ctx):
        return ""
    if fan.get("mgr_vacant") and not fan.get("mgr"):   # 38번 로그: 지난 감독 계약만 있고 현재 감독이 없음
        return "이 작성자 팀(%s): %s." % (_fan_name(fan) or "작성자 팀", VACANT_NOTE)
    if not fan.get("mgr"):
        return ""
    return "이 작성자 팀(%s) 감독: %s." % (_fan_name(fan) or "작성자 팀", _mgr_with_label(fan["mgr"], fan.get("mgr_d"), fan.get("mgr_caretaker")))


def _ctx_mgr_note(ctx, fan, parent_text):
    """글에 나온 팀들의 감독 (작성자 팀은 따로 알려 주므로 뺀다). 플레이어 팀은 '게임 플레이어'로 표시."""
    own = _fan_name(fan) if isinstance(fan, dict) else None
    me_mgr, me_club = _me(fan)
    items, seen = [], set()
    for d in ctx or []:
        if d.get("kind") != "클럽":
            continue
        name = d.get("name", "")
        mgr = d.get("_감독") or d.get("_내팀")
        if name in seen or name == own:
            continue
        if not mgr:
            if d.get("_감독공석"):
                seen.add(name)
                items.append("%s 감독 공석" % name)
            continue
        seen.add(name)
        items.append("%s %s" % (name, "%s (게임 플레이어)" % mgr if d.get("_내팀") else _mgr_with_label(mgr, d.get("_감독_d"), d.get("_임시감독"))))
    # 글이 플레이어 팀 얘기인데 링크가 없어 ctx에 없을 때
    if me_mgr and me_club and me_club != own and me_club not in seen and parent_text and me_club in _plain(parent_text):
        items.append("%s %s (게임 플레이어)" % (me_club, me_mgr))
    return ("글에 나온 팀 감독: " + ", ".join(items) + ".") if items else ""


MOOD_RULE = ("감정 방향 규칙: 작성자 줄의 '팀 분위기'를 따른다. '최고'(연승, 거의 전승)면 그 팀 팬은 기쁨·자랑·선수와 감독 찬양·우승 설레발·상대 조롱으로 쓰고, "
             "자기 팀 감독·전술·선수를 비판하거나 경질·방출을 말하지 않는다. 원래 댓글이 불만이어도 '이겼으니 됐고 이거 하나만 아쉽다' 정도로 가볍게 바꾼다. "
             "'바닥'(연패, 무승)이면 분노·한탄·비판을 써도 된다. '보통'이거나 표시가 없으면 글 내용과 원래 댓글을 따른다. "
             "욕설 모드가 세도 같다: 욕은 칭찬과 흥분에도 쓴다 (존나 잘하네, ㅅㅂ 미쳤다, 개사기네). 거칠게 쓰라는 것이지 부정적으로 쓰라는 것이 아니다.")
AGE_RULE = ("사실 규칙: 이 게임은 현실보다 몇 년 뒤 시점이다. 실존 선수·감독이라도 나이·소속·기록·경력은 네 기억과 다르니 "
            "주어진 정보(게임 데이터, 등장 인물 나이, 기사 본문, 글)에만 근거한다. 나이 정보가 없으면 '몇 살', '10대', '노장' 같은 나이 표현을 쓰지 않는다.")
STOCK_RULE = ("상투 드립 금지: 너무 많이 써서 식상해진 표현은 쓰지 않는다 - 골대가 MVP·골대가 더 잘 뛴다, 축구화 벗고 탁구, 연봉 반납, "
              "발롱도르 줘라, 내가 뛰어도 낫다, 응원하는 내가 죄인·병, 관중석에서 뛰어도, 박물관에 모셔라. 드립은 매번 그 글의 상황에서 새로 만든다.")


BATCH_RULE = ("묶음 요청 규칙: 팬 댓글 여러 개를 한 번에 새로 쓸 때는 서로 다른 사람이 쓴 것처럼 시작 표현, 소재, 관점, 말투가 모두 달라야 한다. "
              "무난하고 일반적인 반응(예: '깔끔했다', '앞으로가 기대된다')은 피하고, 댓글마다 기사 본문·게임 데이터·원래 댓글에서 "
              "서로 다른 구체적인 사실 하나씩(나이, 경기 수, 득점 시간, 판정, 순위, 이적료 등)을 집어서 반응한다. "
              "하나씩 따로 쓸 때만큼 자극적으로 쓴다 (말투 강도는 위 지침 그대로). 각 댓글에는 그 댓글 전용 자리표시자만 쓴다. "
              "감독 언급은 묶음 전체에서 많아야 1개 (없어도 된다).")


def _request_rules():
    return "[요청 처리 규칙] 요청에 해당하는 정보가 있을 때만 적용한다.\n- " + "\n- ".join((FAN_RULE, MOOD_RULE, MGR_RULE, BATCH_RULE, STOCK_RULE, AGE_RULE))


def build_user_prompt(parsed, comment_type=None, parent_text=None, ctx=None, body=None, fan=None):
    lines = []
    if parent_text:
        lines.append("이 댓글이 달린 글(뉴스/공식 계정): " + _plain(parent_text))
    else:
        lines.append("이 댓글이 달린 글: (알 수 없음)")
    if body and cfg.get("tokens.use_article_body"):   # 같은 뉴스의 댓글끼리 앞부분이 같아야 캐시가 먹으니 제목 바로 뒤에 둔다
        mx = cfg.get("tokens.article_body_max_chars")
        body = _dedupe_sentences(body)   # 토큰 절약: 경기 기사에 같은 문장(VAR 판정 등)이 여러 번 나온다
        b = body if len(body) <= mx else body[:mx] + "…"
        lines.append("뉴스 기사 본문 (사실 확인용. 그대로 베끼지 말고, 팬이 기사를 읽고 꽂힌 한 가지에만 반응한다): " + b.replace("\n", " "))
    if parsed.entities:
        lines.append("사용할 수 있는 자리표시자:")
        for e in parsed.entities:
            kind = {"team": "팀/대회", "person": "선수/인물"}.get(e.kind, "개체")
            tip = ("  (" + e.tooltip.replace("를 보려면 클릭하십시오.", "").replace("의 프로필을 보려면 클릭하십시오.", "") + ")") if e.tooltip else ""
            lines.append("  {%s} = %s [%s]%s" % (e.key, e.name, kind, tip))
    else:
        lines.append("사용할 수 있는 자리표시자: 없음 (이름을 쓰지 말 것)")
    ban = _banned()
    if ban:
        lines.append("최근 너무 많이 쓴 표현이라 이번에는 절대 쓰지 말 것: " + ", ".join(b.strip() for b in ban))
    lines.append("게임이 원래 만든 댓글(참고용, 같은 의미와 분위기로 새로 쓸 것): " + parsed.body_template)
    fn = _fan_name(fan)
    if fn:
        lines.append("이 댓글 작성자: %s 팬%s (작성자 응원 팀 규칙·감정 방향 규칙 적용)." % (fn, _mood_tag(fan)[1]))
    mine_note = _mine_note(fan) if isinstance(fan, dict) and _in_article(fan.get("me_club"), parent_text, body, ctx) else ""
    extras = [x for x in (mine_note, _own_mgr_note(fan, parent_text, body, ctx), _ctx_mgr_note(ctx, fan, parent_text)) if x]
    if extras:
        lines.extend(extras)   # 감독 언급 규칙은 시스템 쪽 [요청 처리 규칙]
    ctx_lines = _ctx_lines(ctx, parsed)
    lines.extend(ctx_lines)
    if not ctx_lines:
        al = _ages_line(ctx, parsed)
        if al:
            lines.append(al)
    names = _mentionable_players(ctx, parsed, parent_text)
    if ctx_lines and names and random.random() < cfg.get("tokens.player_mention_rate"):
        lines.append("이번 댓글에는 다음 핵심 선수 중 한 명을 이름 그대로 꼭 언급한다: %s "
                     "(예: 역시 OO가 해결해 준다, OO 없으면 어쩔 뻔했냐, OO 요즘 왜 이러냐)" % ", ".join(names))
    note = _situation_note((parent_text or "") + " " + parsed.body_template)
    if note:
        lines.append(note)
    sibs = _sibs(parent_text)
    if sibs:
        lines.append("같은 글 아래 이미 달린 다른 댓글들 (시작 표현, 소재, 관점이 이것들과 겹치면 안 된다. 다른 사람이 쓴 것처럼 완전히 다르게 쓴다):\n" +
                     "\n".join("- " + s for s in sibs))
    lines.append("관점 후보: " + " / ".join(_angles([_mood_tag(fan)[0]], 3)) +
                 " (글 상황과 원래 댓글에 어울리는 것 하나만 골라 쓰고, 어울리는 게 없으면 무시한다)")
    if cfg.get("style.swear") == "wild":   # 시스템에만 두면 약해서 짧게 한 번 더 (전문은 시스템 쪽)
        lines.append(WILD_SHORT % "이 댓글에")
    lines.append("새 댓글 한 문장을 써라.")
    return "\n".join(lines)


WILD_SHORT = "야생 모드: %s 욕설이나 개드립을 반드시 하나 이상 (시스템 지침의 야생 모드 그대로)."
# 야생 모드: 말투 지침 끝 한 줄만으로는 약해서, 요청마다 직접 한 번 더 시킨다 (전문은 시스템 쪽, 요청엔 WILD_SHORT)
WILD_TURN = ("야생의 인터넷 모드: %s 욕설(ㅅㅂ, 좆같네, 지랄, 개같네, 존나 등)이나 개드립을 반드시 하나 이상 넣는다. "
             "개드립 유형: 과장, 밈·비유, 비꼬는 칭찬, 자조, 태도·플레이를 찌르는 원색적인 말. 그 글의 구체적인 상황에서 새로 만들고 상투 드립 금지 목록은 쓰지 않는다. "
             "욕과 드립의 방향(환호냐 분노냐)은 감정 방향 규칙(팀 분위기)을 따른다. "
             "금지선(혐오·비하·성적 표현·가족 욕·위해)은 그대로 지킨다.")


def call_api(system, user, max_tokens=None, json_mode=False):
    think = cfg.get("api.thinking")
    req_body = {
        "model": cfg.get("api.model"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": cfg.get("api.temperature"),
        # 추론을 끄면 ~1초, 토큰 1/10. 켜면 추론이 먼저 나와서 max_tokens가 작으면 문장 전에 잘리므로 크게 쓴다
        "max_tokens": cfg.get("api.max_tokens_thinking") if think else (max_tokens or cfg.get("api.max_tokens")),
        "stream": False,
        "thinking": {"type": "enabled" if think else "disabled"},
    }
    if json_mode:
        req_body["response_format"] = {"type": "json_object"}
    body = json.dumps(req_body).encode("utf-8")
    req = urllib.request.Request(cfg.get("api.url"), data=body, headers={
        "Authorization": "Bearer " + _key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=cfg.get("api.timeout_sec")) as r:
        d = json.load(r)
    return d["choices"][0]["message"]["content"].strip(), d.get("usage", {})


_PAIR_OF = {"은": "은/는", "는": "은/는", "이": "이/가", "가": "이/가", "을": "을/를", "를": "을/를",
            "와": "와/과", "과": "와/과", "으로": "으로/로", "로": "으로/로"}
_BARE_PARTICLE = re.compile(r"(\{[A-Za-z]{1,3}[0-9]+\})(으로|은|는|이|가|을|를|와|과|로)(?=[\s,.?!~…]|$)")


def fix_bare_particles(text):
    """AI가 {T1}이 처럼 조사를 직접 붙이면 {T1}{이/가} 쌍으로 바꿔 받침에 맞게 고른다."""
    return _BARE_PARTICLE.sub(lambda m: m.group(1) + "{" + _PAIR_OF[m.group(2)] + "}", text)


# 어떤 말투 모드에서도 쓰지 않는 표현 (장애·외모·성별·출신 비하, 가족 욕). 나오면 그 댓글을 버리고 다시 만든다.
_FORBIDDEN = re.compile(r"병신|븅신|빙신|애자|장애인|정신병자|난쟁이|돼지\s*새끼|흑형|짱깨|쪽바리|홍어|김치녀|된장녀|니\s*애미|느금|니\s*엄마|니\s*애비|부모\s*욕|죽어라|뒤져라|디져라|다쳐라")


def has_forbidden(text):
    return bool(_FORBIDDEN.search(re.sub(r"\{[^{}]*\}", "", text)))


# ---- 나이 할루시네이션 막기 (11-08, 사용자 지적) ----
# 게임은 2034년인데 실존 선수(라민 야말 27세)를 AI가 현실 기억으로 "열여섯 살"이라고 썼다.
# 댓글에 나온 나이가 게임 데이터 나이나 기사·글에 나온 숫자와 안 맞으면 버리고 다시 만든다.
_KO_TENS = {"열": 10, "스물": 20, "서른": 30, "마흔": 40, "쉰": 50}
_KO_ONES = {"한": 1, "하나": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9}
_AGE_RE = re.compile(r"(\d{1,2})\s*(?:살|세(?![가-힣]))|(?:(열|스물|서른|마흔|쉰)\s*)?(한|두|세|네|다섯|여섯|일곱|여덟|아홉)?\s*살")


def _ages_in(text):
    out = []
    for m in _AGE_RE.finditer(re.sub(r"\{[^{}]*\}", "", text)):
        if m.group(1):
            out.append(int(m.group(1)))
        elif m.group(2) or m.group(3):
            out.append(_KO_TENS.get(m.group(2), 0) + _KO_ONES.get(m.group(3), 0))
    return out


def _known_ages(ctx, *texts):
    """허용되는 나이: 게임 데이터의 나이 + 기사·글에 나온 10~49 숫자 (생일 기사 '16번째 생일' 등) 주변 ±1."""
    ok = set()
    for d in ctx or []:
        if isinstance(d.get("나이"), int):
            ok.add(d["나이"])
    for t in texts:
        for n in re.findall(r"\d{1,2}", t or ""):
            n = int(n)
            if 10 <= n <= 49:
                ok.update((n - 1, n, n + 1))
    return ok


def bad_age(text, ctx, *texts):
    """댓글의 '몇 살'이 근거 없는 나이면 True."""
    ages = [a for a in _ages_in(text) if 10 <= a <= 49]
    if not ages:
        return False
    ok = _known_ages(ctx, *texts)
    return any(a not in ok for a in ages)


def _ages_line(ctx, parsed):
    """데이터 비율 판정에 걸려 게임 데이터가 빠져도 등장 인물 나이는 알려 준다 (짧다)."""
    keys = {e.name: e.key for e in parsed.entities}
    items = []
    for d in ctx or []:
        if d.get("kind") in ("선수/인물", "감독/스태프") and isinstance(d.get("나이"), int):
            n = d.get("name", "")
            items.append("%s %d세" % ("{%s}" % keys[n] if n in keys else n, d["나이"]))
    return ("등장 인물 나이 (게임 속 현재): " + ", ".join(items)) if items else None


def clean(ai_text):
    t = ai_text.strip().strip('"“”\'')
    t = re.sub(r"씨발|시발|씨바|씨팔|시팔|씨빨", "ㅅㅂ", t)   # 가장 센 욕은 초성으로 순화
    if not cfg.get("style.allow_k"):
        t = re.sub(r"ㅋ+", "", t)      # 모델이 금지해도 ㅋ을 쓰면 지운다
    t = re.sub(r"\s+", " ", t).strip()
    return t


def generate(original, comment_type=None, parent_text=None, retries=None, ctx=None, body=None, fan=None):
    """원문(게임 마크업) → 새 문장(게임 마크업) 또는 None.

    반환: (새 문장 또는 None, 정보 dict)
    """
    info = {"tries": 0, "error": None, "usage": {}, "ai_raw": None, "sec": 0.0}
    if retries is None:
        retries = cfg.get("tokens.retries")
    system = get_system()
    max_chars = cfg.get("tokens.max_chars")
    try:
        parsed = fm.parse_feed_text(original)
    except Exception as e:  # noqa: BLE001
        info["error"] = "parse: %r" % e
        return None, info
    if "\x01" not in parsed.body_template and parsed.body_template == "":
        info["error"] = "empty"
        return None, info
    user = build_user_prompt(parsed, comment_type, parent_text, ctx, body, fan)
    t0 = time.time()
    for _ in range(retries + 1):
        info["tries"] += 1
        try:
            raw, usage = call_api(system, user)
        except Exception as e:  # noqa: BLE001
            info["error"] = "api: %s %s" % (type(e).__name__, str(e)[:100])
            continue
        info["usage"] = usage
        s = info.setdefault("usage_sum", {})          # 재시도까지 합친 토큰 (비용 계산용)
        for uk, uv in usage.items():
            if isinstance(uv, (int, float)):
                s[uk] = s.get(uk, 0) + uv
        info["ai_raw"] = raw
        text = fix_bare_particles(clean(raw))
        if not text or len(re.sub(r"\{[^{}]*\}", "X", text)) > max_chars:
            info["error"] = "length"
            continue
        if re.search(r"[\u4e00-\u9fff\u3040-\u30ff]", text):   # DeepSeek이 가끔 한자를 섞는다
            info["error"] = "cjk"
            continue
        if has_forbidden(text):                    # 금지선을 넘는 표현 -> 버리고 다시
            info["error"] = "forbidden"
            continue
        if bad_age(text, ctx, body, _plain(parent_text) if parent_text else "", parsed.body_template):
            info["error"] = "age"                   # 근거 없는 나이 (실존 선수 현실 나이 등)
            user = build_user_prompt(parsed, comment_type, parent_text, ctx, body, fan) + \
                "\n방금 쓴 '%s'의 나이는 근거가 없다. 주어진 나이만 쓰거나 나이를 빼고 다시 써라." % text
            continue
        used = [b for b in _banned() if b in text]
        if used and _ < retries:
            info["error"] = "banned: " + ",".join(used)
            user = build_user_prompt(parsed, comment_type, parent_text, ctx, body, fan)
            continue
        if _dup_open(text, _sibs(parent_text)) and _ < retries:
            info["error"] = "dup_open"
            user = build_user_prompt(parsed, comment_type, parent_text, ctx, body, fan) + \
                "\n방금 쓴 '%s'는 같은 글의 다른 댓글과 시작이 겹쳐서 버렸다. 시작 표현과 관점을 완전히 바꿔서 다시 써라." % text
            continue
        try:
            out = link_known_players(fm.render_feed_text(text, parsed, keep_hashtags=True), ctx)
        except ValueError as e:
            info["error"] = "validate: %s" % e
            continue
        info["error"] = None
        info["sec"] = round(time.time() - t0, 2)
        _remember(text)
        try:
            _add_sib(parent_text, _plain(out))
        except Exception:  # noqa: BLE001
            pass
        return out, info
    info["sec"] = round(time.time() - t0, 2)
    return None, info


# ---- 같은 글 댓글을 한 번에 생성 (28번 로그) ----
# 제목·본문·게임 데이터·안내를 한 번만 보내서 토큰을 아끼고, 호출 한 번으로 여러 댓글을 받는다.
# 댓글마다 자리표시자 번호가 따로라서 댓글 1은 {aP1}, 댓글 2는 {bP1}처럼 앞글자를 붙여 보내고, 받은 뒤 되돌린다.
# 검사(길이, 한자, 겹침, 렌더링)에 걸린 댓글만 호출한 쪽이 generate()로 하나씩 다시 만든다.
_LET = "abcdefghij"


class _Keyed:
    def __init__(self, entities):
        self.entities = entities


class _Ent:
    def __init__(self, name, key):
        self.name, self.key = name, key


def _ns(text, keys, letter):
    """text 안의 {P1} 같은 자리표시자를 {aP1}로 (조사 쌍 {은/는}은 그대로)."""
    for k in sorted(keys, key=len, reverse=True):
        text = text.replace("{%s}" % k, "{%s%s}" % (letter, k))
    return text


def _unns(text, letter):
    """{aP1} -> {P1}. 다른 댓글 글자({bP1})가 섞여 있으면 그대로 남아 렌더링 검사에서 걸린다."""
    return re.sub(r"\{%s([A-Za-z]{1,3}[0-9]+)\}" % letter, r"{\1}", text)


def build_batch_prompt(parsed_list, parent_text, ctx_list, body, fans=None):
    lines = []
    if parent_text:
        lines.append("이 댓글들이 달린 글(뉴스/공식 계정): " + _plain(parent_text))
    if body and cfg.get("tokens.use_article_body"):
        mx = cfg.get("tokens.article_body_max_chars")
        body = _dedupe_sentences(body)   # 토큰 절약: 경기 기사에 같은 문장(VAR 판정 등)이 여러 번 나온다
        b = body if len(body) <= mx else body[:mx] + "…"
        lines.append("뉴스 기사 본문 (사실 확인용. 그대로 베끼지 말고, 팬이 기사를 읽고 꽂힌 한 가지에만 반응한다): " + b.replace("\n", " "))
    n = len(parsed_list)
    lines.append("아래 팬 댓글 %d개를 각각 새로 써라 (묶음 요청 규칙)." % n)
    merged_ents, seen_names = [], set()
    any_fan = False
    mgr_labels = {}
    moods = []
    all_ctx_b = [d for c in ctx_list for d in (c or [])]
    for i, p in enumerate(parsed_list):
        L = _LET[i]
        lines.append("댓글 %d" % (i + 1))
        if p.entities:
            parts = []
            for e in p.entities:
                kind = {"team": "팀/대회", "person": "선수/인물"}.get(e.kind, "개체")
                parts.append("{%s%s} = %s [%s]" % (L, e.key, e.name, kind))
                if e.name not in seen_names:
                    seen_names.add(e.name)
                    merged_ents.append(_Ent(e.name, L + e.key))
            lines.append("  쓸 수 있는 자리표시자 (이 댓글 전용): " + ", ".join(parts))
        else:
            lines.append("  쓸 수 있는 자리표시자: 없음 (이름을 쓰지 말 것)")
        lines.append("  원래 댓글 (같은 의미와 분위기로 새로 쓸 것): " + _ns(p.body_template, [e.key for e in p.entities], L))
        fan_i = (fans or [None] * n)[i]
        fn = _fan_name(fan_i)
        if fn:
            mine_i = isinstance(fan_i, dict) and fan_i.get("mine")
            mgr_i = (fan_i.get("me_mgr") if mine_i else fan_i.get("mgr")) if isinstance(fan_i, dict) else None
            if not _in_article(fn, parent_text, body, all_ctx_b):   # 11-08: 글에 안 나오는 팀이면 감독 얘기 재료를 주지 않는다
                mgr_i = None
            if mgr_i and not mine_i:   # 토큰 절약: 댓글마다 라벨 전문을 반복하지 않고 아래에 한 번만
                mgr_labels.setdefault(mgr_i, _mgr_with_label(fan_i["mgr"], fan_i.get("mgr_d"), fan_i.get("mgr_caretaker")))
                if fan_i.get("mgr_caretaker"):
                    mgr_i += " (임시 감독)"
            if not mgr_i and not mine_i and isinstance(fan_i, dict) and fan_i.get("mgr_vacant") and _in_article(fn, parent_text, body, all_ctx_b):
                mgr_i = "없음 (" + VACANT_NOTE + ")"
            mood_i, tag_i = _mood_tag(fan_i)
            moods.append(mood_i)
            lines.append("  작성자: %s 팬%s%s%s" % (fn, " (게임 플레이어 팀 팬)" if mine_i else "",
                                                  ", 자기 팀 감독 %s" % mgr_i if mgr_i else "", tag_i))
            any_fan = True
    if any_fan:
        lines.append("작성자 응원 팀 규칙·감정 방향 규칙 적용.")
    # 감독 (36번 로그): 작성자 팀 감독은 댓글마다 위에, 글에 나온 팀 감독과 규칙은 한 번만
    all_ctx = [d for c in ctx_list for d in (c or [])]
    fans_d = [f for f in (fans or []) if isinstance(f, dict)]
    mine_fan = next((f for f in fans_d if f.get("mine") and f.get("me_mgr")), None)
    any_me = next((f for f in fans_d if f.get("me_mgr")), {})
    ctx_note = _ctx_mgr_note(all_ctx, {"me_mgr": any_me.get("me_mgr"), "me_club": any_me.get("me_club")}, parent_text)
    if mine_fan and _in_article(mine_fan.get("me_club"), parent_text, body, all_ctx):
        lines.append(_mine_note(mine_fan).replace("이 작성자는", "'게임 플레이어 팀 팬' 작성자는"))
    if ctx_note:
        lines.append(ctx_note)
    own = [v for k, v in mgr_labels.items() if not (ctx_note and k in ctx_note)]   # 글에 나온 팀 감독 줄에 이미 있으면 뺀다
    if own:
        lines.append("작성자 팀 감독 정보: " + "; ".join(own) + ".")
    if ctx_note or own or any(f.get("mine") for f in fans_d):
        lines.append("감독 언급 규칙 적용 (묶음 전체 많아야 1개).")
    merged_ctx, seen = [], set()           # 게임 데이터는 합쳐서 한 번만
    for ctx in ctx_list:
        for d in ctx or []:
            k = (d.get("kind"), d.get("name"))
            if k not in seen:
                seen.add(k)
                merged_ctx.append(d)
    keyed = _Keyed(merged_ents)
    # 비율 판정을 묶음 전체에 한 번 하면 "전부 붙거나 전부 안 붙거나"가 된다 (이적 기사 댓글이 스탯을 하나도 언급하지 않았다).
    # 데이터는 항상 한 번 넣고, 비율만큼의 댓글에만 인용하게 한다.
    ctx_lines = _ctx_lines(merged_ctx, keyed, force=True)
    lines.extend(ctx_lines)
    if ctx_lines:
        k = sum(1 for _ in range(n) if random.random() < _data_rate(merged_ctx))
        if k == 0:
            lines.append("이번에는 게임 데이터를 인용하지 않는다 (참고만 한다).")
        else:
            lines.append("게임 데이터의 사실(나이, 통산·시즌 기록, 평점, 최근 폼, 순위 등)은 댓글 %d개에만 하나씩 자연스럽게 녹인다 "
                         "(댓글마다 다른 사실). 나머지 댓글은 데이터 없이 쓴다." % k)
    names = _mentionable_players(merged_ctx, keyed, parent_text)
    if ctx_lines and names and random.random() < cfg.get("tokens.player_mention_rate"):
        lines.append("댓글 중 하나에는 다음 핵심 선수 중 한 명을 이름 그대로 언급한다: %s" % ", ".join(names))
    note = _situation_note((parent_text or "") + " " + " ".join(p.body_template for p in parsed_list))
    if note:
        lines.append(note)
    ban = _banned()
    if ban:
        lines.append("최근 너무 많이 쓴 표현이라 쓰지 말 것: " + ", ".join(b.strip() for b in ban))
    sibs = _sibs(parent_text)
    if sibs:
        lines.append("같은 글 아래 이미 달린 다른 댓글들 (이것들과도 겹치면 안 된다):\n" + "\n".join("- " + s for s in sibs))
    lines.append("관점 후보 (댓글마다 다른 것을 고르거나, 어울리지 않으면 무시): " + " / ".join(_angles(moods, n + 2)))
    if cfg.get("style.swear") == "wild":
        lines.append(WILD_SHORT % "댓글마다")
    lines.append('출력: JSON 객체 하나로만 답한다. 형식: {"1": "댓글 1의 새 문장", "2": "댓글 2의 새 문장"}.')
    return "\n".join(lines)


def generate_batch(items, parent_text=None, body=None):
    """items: [{'o': 원문, 't': 종류, 'ctx': ...}] (같은 부모 글). 반환: [(새 문장 또는 None, info)] (items 순서).
    None인 항목은 호출한 쪽이 generate()로 하나씩 다시 만든다. 토큰은 첫 항목 info에만 넣는다."""
    t0 = time.time()
    res = [(None, {"tries": 1, "error": "batch", "usage": {}, "sec": 0.0, "batch": len(items)}) for _ in items]
    parsed = []
    for it in items:
        try:
            parsed.append(fm.parse_feed_text(it["o"]))
        except Exception:  # noqa: BLE001
            parsed.append(None)
    idx = [i for i, p in enumerate(parsed) if p is not None and p.body_template][:len(_LET)]
    if not idx:
        return res
    user = build_batch_prompt([parsed[i] for i in idx], parent_text, [items[i].get("ctx") for i in idx], body,
                              [items[i].get("fan") for i in idx])
    try:
        raw, usage = call_api(get_system(), user, max_tokens=80 * len(idx) + 60, json_mode=True)
    except Exception as e:  # noqa: BLE001
        res[0][1]["error"] = "api: %s %s" % (type(e).__name__, str(e)[:100])
        return res
    res[0][1]["usage"] = usage
    res[0][1]["usage_sum"] = {k: v for k, v in usage.items() if isinstance(v, (int, float))}
    try:
        data = json.loads(raw)
    except ValueError:
        res[0][1]["error"] = "batch json"
        return res
    max_chars = cfg.get("tokens.max_chars")
    made = []
    for j, i in enumerate(idx):
        info = res[i][1]
        L = _LET[j]
        t = data.get(str(j + 1))
        if not isinstance(t, str):
            info["error"] = "batch missing"
            continue
        text = fix_bare_particles(_unns(clean(t), L))
        if not text or len(re.sub(r"\{[^{}]*\}", "X", text)) > max_chars:
            info["error"] = "length"
            continue
        if re.search(r"[一-鿿぀-ヿ]", text):
            info["error"] = "cjk"
            continue
        if has_forbidden(text):
            info["error"] = "forbidden"
            continue
        if bad_age(text, items[i].get("ctx"), body, _plain(parent_text) if parent_text else "", parsed[i].body_template):
            info["error"] = "age"   # 단일 생성으로 다시
            continue
        if _dup_open(text, _sibs(parent_text) + made):
            info["error"] = "dup_open"
            continue
        try:
            out = link_known_players(fm.render_feed_text(text, parsed[i], keep_hashtags=True), items[i].get("ctx"))
        except ValueError as e:
            info["error"] = "validate: %s" % e
            continue
        info["error"] = None
        _remember(text)
        p_out = _plain(out)
        made.append(p_out)
        try:
            _add_sib(parent_text, p_out)
        except Exception:  # noqa: BLE001
            pass
        res[i] = (out, info)
    sec = round(time.time() - t0, 2)
    for _, info in res:
        info["sec"] = sec
    return res
