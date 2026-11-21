# -*- coding: utf-8 -*-
"""M24GA CLI: GUI 없이 모든 기능을 명령줄로 쓸 수 있는 도구. GPL-3.0-or-later.

AI 에이전트가 GUI(pywebview)를 조작하지 않고 직접 M24GA를 제어할 수 있다.
JSON 출력(--json)으로 프로그래밍 방식으로 파싱할 수 있다.

사용:
  python -X utf8 loader/cli.py <명령> [옵션]

명령 목록:
  상태 ──────────────────────────
  status              로더 상태 (켜짐/꺼짐, 게임 연결, 빌드, 모드 목록)
  mods                찾은 모드 목록과 상태
  mod <id>            모드 하나의 상세 정보

  켜기/끄기 ─────────────────────
  start [--now]       로더 시작 (게임을 기다렸다가 자동 연결, --now: 바로 데이터 표 만들기)
  stop                로더 끄기
  run [--now] [--once] [--check]  포그라운드에서 실행 (Ctrl+C로 종료, host.py의 콘솔 모드)

  모드 관리 ─────────────────────
  enable <id>         모드 켜기
  disable <id>        모드 끄기
  install <경로>      .24mod 파일 설치
  uninstall <id>      모드 삭제 (휴지통으로)
  reload <id>         모드의 게임 쪽 JS를 지금 파일로 다시 올리기 (핫 리로드)
  call <id> <함수> [인자...]  모드창처럼 모드 Python의 ui_<함수>(인자...)를 부르기 (인자는 JSON이면 JSON으로)
  grant <id>          위험 기능 권한 허용하고 켜기
  rescan              mods 폴더 다시 훑기

  설정 ──────────────────────────
  settings <id>       모드 설정 보기
  set <id> <key> <값> 모드 설정 바꾸기

  로그/보고 ─────────────────────
  log <id>            모드의 최근 로그
  log-clear <id>      모드 로그 지우기
  report <id>         AI에게 줄 모드 상태 보고서
  build-report        게임 빌드 진단 보고서 (Steam판 등 모르는 빌드)
  writes <id>         모드의 게임 값 쓰기 기록
  undo <id>           모드가 바꾼 값 되돌리기

  안전 모드 ─────────────────────
  safe                안전 모드 상태 확인
  safe-leave          안전 모드 끝내기

  게임 조사 (M19) ───────────────
  explore <대상> [시작] [크기]  게임 객체를 펼쳐 보기 (포인터는 클래스 이름과 함께). 대상: 0x주소 | player:<uid> |
                      person:<uid> | me | myclub, 뒤에 /+0x130 붙이면 그 칸의 포인터를 따라감
  classes <정규식>    fm.exe 클래스 이름 찾기 (RTTI, 게임 없이 됨)
  engine dump <표> [--out 파일]  매치엔진 표를 메모리에서 읽기 (weights|physics|momentum|ratings|styles|xg, E03·E09·E10)
  engine apply <팩> [--dry] / engine restore  엔진 팩 값을 게임 메모리에 바로 쓰기 / 원본으로 (재시작 없음)
  get <대상> <필드...> 필드 등록부의 칸 읽기 (필드 끝이 '.'이면 그 이름으로 시작하는 것 전부)
  fields [정규식]     필드 등록부 목록 (게임 없이 됨, docs/FIELDS.md)
  props <대상> [정규식] [--empty]  게임 속성 코드 값 전부 (대상: me | myteam | myclub | p123 | s45 | team:<번호> | player:<uid> | 0x주소, docs/PROPERTIES.md)
  prop-find <대상> <값>  값(숫자·글·날짜)이 든 속성 코드 찾기
  prop-info [정규식]  속성 등록부 목록 (게임 없이 됨)
  actions [정규식]    게임 액션(명령) 198개 목록 (id·클래스·문맥 키, 게임 없이 됨, docs/ACTIONS.md)
  find-field <대상>=<값> [...]  알려진 값으로 칸 찾기 (여러 대상이면 공통 칸 + fields.json 초안, 값: 숫자 | a..b | 180억)
  watch-write <대상> <칸> [크기]  그 칸에 쓰는 게임 코드 찾기 (하드웨어 감시, --secs/--max 뒤 자동 해제, show | stop)
  find-global <정규식>  전역 칸 중 그 클래스 객체를 가리키는 것 (싱글턴 찾기)
  find-objects <정규식>  그 클래스의 객체를 게임 메모리에서 찾기 (vtable 검색, --max, --secs)
  find-refs <대상>       그 주소를 가리키는 칸과 그 칸을 가진 객체 (거꾸로 따라가기)
  find-text <글>         화면 글을 들고 있는 객체 찾기 (글 -> 핸들 -> 주인)
  find-bytes <패턴>      바이트(16진수, ??) 또는 값 나열(--i32 11 15 ? 4, --u8/--i16/--f32 …)을 힙에서 찾기 (--align, --owner, --module)
  find-const <4글자>     실행 중인 fm.exe에서 4글자 상수(위젯 id·이벤트)가 쓰이는 곳
  play --days N          테스트용 자동 진행 (기본 규칙으로 메일·확인 창·면담 처리, 처음 보는 화면에서 멈춤)
  ui mail                열린 메일(제목·보낸 이·본문·답 버튼)과 메일 목록
  ui state [--watch 초]  게임 진행 상태 한 줄 (날짜·시각, 오른쪽 위 버튼, 진행 중, 팝업, 답할 메일)
  ui text|tree           게임 화면 읽기: 보이는 글 / 보이는 위젯 트리 (--all, --root, --depth, --max)
  act continue|click|reply|dialog|instant 게임 화면 조작 (reply = 메일 답, dialog = 확인 창, instant = 즉석 결과(스킨 무관)): 계속 진행 / 버튼 클릭 (0x주소 | id | 화면 글, --index, --partial, --yes), continue --wait [초]
  functions [정규식]  함수 등록부 목록 (게임 없이 됨, docs/FUNCTIONS.md)
  hooks               지금 걸린 끼어들기(모드별 호출 수·오류·시간)와 함수 서명 확인
  watch-call <함수|fm+0x주소>  함수를 잠깐 지켜보며 인자 정체·반환값·부른 곳 모으기 (--secs/--max 뒤 자동 해제, show | stop)
  기타 ──────────────────────────
  validate <경로>     모드 검사 (tools/m24.py validate와 같다)
  open-mods           모드 폴더 열기
  open-data <id>      모드 데이터 폴더 열기
  version             버전

전체 옵션:
  --json              JSON으로 출력 (AI 파싱용)
  --wait <초>         start 후 게임 연결까지 기다리기 (기본: 0 = 안 기다림)
"""
import contextlib
import io
import datetime
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import host  # noqa: E402
import mods as modlib  # noqa: E402
import validate as vlib  # noqa: E402
import control  # noqa: E402  (실행 중인 로더로 명령을 보내는 통로, M18)


# ═══════════════════════════════════════════════════
# 출력 도우미
# ═══════════════════════════════════════════════════
_json_mode = False


def out(obj):
    """결과를 출력한다. --json이면 JSON, 아니면 사람이 읽기 좋은 형태."""
    if _json_mode:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    elif isinstance(obj, str):
        print(obj)
    elif isinstance(obj, dict):
        _print_dict(obj)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                _print_dict(item)
                print()
            else:
                print(item)
    else:
        print(obj)


def _print_dict(d, indent=0):
    prefix = "  " * indent
    for k, v in d.items():
        if isinstance(v, dict):
            print("%s%s:" % (prefix, k))
            _print_dict(v, indent + 1)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            print("%s%s:" % (prefix, k))
            for item in v:
                _print_dict(item, indent + 1)
                print()
        elif isinstance(v, list):
            print("%s%s: %s" % (prefix, k, ", ".join(str(x) for x in v) if v else "(없음)"))
        else:
            print("%s%s: %s" % (prefix, k, v))


def err(msg):
    print("오류: %s" % msg, file=sys.stderr)
    return 1


def ok(msg=None, **extra):
    d = {"ok": True}
    if msg:
        d["message"] = msg
    d.update(extra)
    out(d)
    return 0


# ═══════════════════════════════════════════════════
# 명령들
# ═══════════════════════════════════════════════════

# ---- 상태 ----
def cmd_status(args):
    """로더 상태: 실행 여부, 게임 연결, 빌드, 모드 요약."""
    host.rescan()
    st = host.status()
    if _json_mode:
        out(st)
        return 0
    print("═══ M24GA 상태 ═══")
    print("로더:     %s" % ("켜짐" if st["running"] else "꺼짐"))
    print("단계:     %s" % st["phase"])
    if st.get("detail"):
        print("설명:     %s" % st["detail"])
    if st.get("build"):
        print("빌드:     %s" % st["build"])
    if st.get("pid"):
        print("게임 PID: %s" % st["pid"])
    g = st.get("game") or {}
    if g.get("date"):
        print("게임 날짜: %s" % g["date"])
    if g.get("save"):
        print("세이브:   id %s" % g["save"].get("id"))
    safe = st.get("hook", {})
    if safe:
        maps = "준비됨" if safe.get("mapsReady") else ("만드는 중" if safe.get("mapsStarted") else "대기")
        print("데이터표: %s" % maps)
        print("올린모드: %s" % (", ".join(safe.get("mods") or []) or "(없음)"))
    # 모드 요약
    mods = st.get("mods") or []
    if mods:
        print("\n─── 모드 (%d개) ───" % len(mods))
        for d in mods:
            label = host.STATE_LABEL.get(d.get("state"), d.get("state", "?"))
            flag = "●" if d["state"] == "running" else ("○" if d["state"] in ("ready", "off") else "✖")
            print("  %s %-24s %-8s  %s" % (flag, d["id"], d["version"], label))
    # 안전 모드
    si = host.safe_info()
    if si:
        print("\n⚠  안전 모드: 직전 게임이 비정상 종료(%s). safe-leave로 해제" % si.get("code"))
    if st.get("errors"):
        print("\n─── 오류 ───")
        for p, e in st["errors"]:
            print("  %s: %s" % (p, e))
    return 0


def cmd_mods(args):
    """찾은 모드 목록과 상태."""
    host.rescan()
    states = host.mod_states()
    if _json_mode:
        out(states)
        return 0
    if not states:
        print("모드가 없습니다. 모드 폴더: %s" % ", ".join(modlib.mod_dirs()))
        return 0
    print("─── 모드 목록 (%d개) ───" % len(states))
    print("%-24s %-8s %-12s %-10s %s" % ("ID", "버전", "상태", "종류", "이름"))
    print("-" * 80)
    for d in states:
        label = host.STATE_LABEL.get(d.get("state"), d.get("state", "?"))
        kind = "파일" if d["kind"] == "file" else "폴더"
        print("%-24s %-8s %-12s %-10s %s" % (d["id"], d["version"], label, kind, d["name"]))
        if d.get("problems"):
            for p in d["problems"]:
                print("  ✖ %s" % p)
        if d.get("auto_disabled"):
            print("  ⚠ 자동으로 꺼짐: %s" % d["auto_disabled"].get("reason", ""))
        if d.get("build_off"):
            print("  ⚠ 빌드 안 맞음: %s" % d["build_off"])
        if d.get("needs_perm"):
            print("  🔒 권한 필요: %s" % ", ".join(d["needs_perm"]))
    print("\n모드 폴더: %s" % ", ".join(modlib.mod_dirs()))
    return 0


def cmd_mod(args):
    """모드 하나의 상세 정보."""
    if not args:
        return err("모드 id를 지정하세요: cli.py mod <id>")
    mod_id = args[0]
    host.rescan()
    m = host.find_mod(mod_id)
    if not m:
        return err("모르는 모드: %s" % mod_id)
    d = m.info()
    d["settings"] = modlib.settings_view(m)
    d["data_dir"] = m.data_dir
    # 상태에서 추가 정보
    st = next((x for x in host.mod_states() if x["id"] == mod_id), {})
    d["state"] = st.get("state")
    d["state_label"] = host.STATE_LABEL.get(st.get("state"), st.get("state"))
    d["python_running"] = st.get("python_running", False)
    d["python_error"] = st.get("python_error")
    d["build_off"] = st.get("build_off")
    d["log_errors"] = st.get("log_errors", 0)
    out(d)
    return 0


# ---- 켜기/끄기 ----
def cmd_start(args):
    """로더 시작 (백그라운드 스레드)."""
    if host.running():
        return err("이미 실행 중입니다")
    now = "--now" in args
    host.rescan()
    host.check_last_crash()
    host.start(now=now)
    wait = 0
    for i, a in enumerate(args):
        if a == "--wait" and i + 1 < len(args):
            try:
                wait = int(args[i + 1])
            except ValueError:
                return err("--wait 뒤에 초(숫자)를 써 주세요")
    if wait > 0:
        if not _json_mode:
            print("로더를 시작했습니다. 게임 연결을 %d초 동안 기다립니다..." % wait)
        deadline = time.time() + wait
        while time.time() < deadline:
            st = host.status()
            if st["phase"] == "hooked":
                return ok("게임에 연결됐습니다", build=st.get("build"))
            if st["phase"] == "error":
                return err("오류: %s" % st.get("detail"))
            if st["phase"] == "unsupported":
                return err("지원하지 않는 게임 빌드")
            time.sleep(1)
        return ok("로더가 시작됐습니다 (아직 게임에 연결되지 않음)", phase=host.status()["phase"])
    return ok("로더를 시작했습니다", running=True)


def cmd_stop(args):
    """로더 끄기."""
    if not host.running():
        return ok("이미 꺼져 있습니다")
    host.stop()
    return ok("로더를 껐습니다")


def cmd_run(args):
    """포그라운드에서 실행 (host.py 콘솔 모드). Ctrl+C로 끈다. 다른 터미널의 CLI가 이 로더를 조종할 수 있게 통로를 연다."""
    control.serve(run_captured)
    try:
        return host.main(args)
    finally:
        control.stop()


# ---- 모드 관리 ----
def cmd_enable(args):
    """모드 켜기."""
    if not args:
        return err("모드 id를 지정하세요: cli.py enable <id>")
    mod_id = args[0]
    host.rescan()
    if not host.find_mod(mod_id):
        return err("모르는 모드: %s" % mod_id)
    host.set_enabled(mod_id, True)
    return ok("모드 %s를 켰습니다" % mod_id)


def cmd_disable(args):
    """모드 끄기."""
    if not args:
        return err("모드 id를 지정하세요: cli.py disable <id>")
    mod_id = args[0]
    host.rescan()
    if not host.find_mod(mod_id):
        return err("모르는 모드: %s" % mod_id)
    host.set_enabled(mod_id, False)
    return ok("모드 %s를 껐습니다" % mod_id)


def cmd_install(args):
    """모드 설치 (.24mod 파일)."""
    if not args:
        return err("파일 경로를 지정하세요: cli.py install <경로.24mod>")
    path = os.path.abspath(args[0])
    if not os.path.isfile(path):
        return err("파일을 찾을 수 없습니다: %s" % path)
    host.rescan()
    r = host.install_mod(path)
    if _json_mode:
        out(r)
    elif r.get("ok"):
        print("설치 완료: %s v%s" % (r.get("id"), r.get("version")))
        if r.get("replaced"):
            print("  옛 버전 v%s를 바꿨습니다" % r["replaced"])
        if r.get("restart_needed"):
            print("  ⚠ Python 부분은 앱을 다시 시작해야 적용됩니다")
    else:
        print("설치 안 함: %s" % r.get("error"))
        if r.get("report"):
            print(r["report"])
    return 0 if r.get("ok") else 1


def cmd_uninstall(args):
    """모드 삭제."""
    if not args:
        return err("모드 id를 지정하세요: cli.py uninstall <id>")
    mod_id = args[0]
    host.rescan()
    r = host.uninstall_mod(mod_id)
    if _json_mode:
        out(r)
    elif r.get("ok"):
        print("삭제 완료: %s → %s" % (mod_id, r.get("trash")))
    else:
        print("삭제 안 함: %s" % r.get("error"))
    return 0 if r.get("ok") else 1


def cmd_call(args):
    """모드창이 m24.call로 부르는 것과 같이 모드 Python의 ui_<함수>를 부른다 (개발·시험용)."""
    if len(args) < 2:
        return err("사용: cli.py call <모드 id> <함수> [인자...]  (예: call dynamic-potential state)")
    mod_id, name, rest = args[0], args[1], []
    for a in args[2:]:
        try:
            rest.append(json.loads(a))
        except ValueError:
            rest.append(a)
    r = host.mod_call(mod_id, name, rest)
    if not r.get("ok"):
        return err(r.get("error") or "실패")
    out(r.get("result"))
    return 0


def cmd_reload(args):
    """모드의 게임 쪽 JS를 다시 올리기 (핫 리로드)."""
    if not args:
        return err("모드 id를 지정하세요: cli.py reload <id>")
    mod_id = args[0]
    host.rescan()
    if not host.find_mod(mod_id):
        return err("모르는 모드: %s" % mod_id)
    if not host.running():
        return err("로더가 꺼져 있습니다. 먼저 start 해 주세요")
    done = host.reload_mod(mod_id)
    return ok("모드 %s를 다시 올렸습니다" % mod_id) if done else err("다시 올리지 못했습니다")


def cmd_grant(args):
    """위험 기능 권한 허용하고 모드 켜기."""
    if not args:
        return err("모드 id를 지정하세요: cli.py grant <id>")
    mod_id = args[0]
    host.rescan()
    m = host.find_mod(mod_id)
    if not m:
        return err("모르는 모드: %s" % mod_id)
    need = m.needs_permission()
    if not need:
        return ok("이미 모든 권한이 허용돼 있습니다", mod=mod_id)
    if not _json_mode:
        print("허용할 위험 기능: %s" % ", ".join(need))
    host.grant_permissions(mod_id)
    return ok("권한을 허용하고 모드 %s를 켰습니다" % mod_id, granted=need)


def cmd_rescan(args):
    """mods 폴더를 다시 훑는다."""
    ms = host.rescan()
    return ok("모드 %d개를 찾았습니다" % len(ms), count=len(ms))


# ---- 설정 ----
def cmd_settings(args):
    """모드 설정 보기."""
    if not args:
        return err("모드 id를 지정하세요: cli.py settings <id>")
    mod_id = args[0]
    host.rescan()
    m = host.find_mod(mod_id)
    if not m:
        return err("모르는 모드: %s" % mod_id)
    view = modlib.settings_view(m)
    if _json_mode:
        out(view)
        return 0
    specs = view.get("specs") or []
    vals = view.get("values") or {}
    is_set = view.get("set") or {}
    if not specs:
        print("이 모드에는 설정이 없습니다")
        return 0
    print("─── %s 설정 ───" % mod_id)
    for s in specs:
        key = s["key"]
        typ = s["type"]
        val = vals.get(key)
        if typ == "password":
            disp = "(설정됨)" if is_set.get(key) else "(비어 있음)"
        else:
            disp = val
        label = s.get("label") or key
        print("  %-20s = %-20s  [%s]%s" % (label, disp, typ, ("  %s" % s.get("help")) if s.get("help") else ""))
        if s.get("options"):
            opts = [o.get("label", o.get("value", o)) if isinstance(o, dict) else o for o in s["options"]]
            print("    선택지: %s" % ", ".join(str(x) for x in opts))
    print("\n설정 바꾸기: cli.py set %s <key> <값>" % mod_id)
    return 0


def cmd_set(args):
    """모드 설정 바꾸기."""
    if len(args) < 3:
        return err("사용법: cli.py set <mod_id> <key> <값>")
    mod_id, key = args[0], args[1]
    raw = args[2]
    # 값 파싱: true/false → bool, 정수/실수 → 숫자, 나머지 → 문자열
    if raw.lower() == "true":
        value = True
    elif raw.lower() == "false":
        value = False
    else:
        try:
            value = int(raw)
        except ValueError:
            try:
                value = float(raw)
            except ValueError:
                value = raw
    host.rescan()
    m = host.find_mod(mod_id)
    if not m:
        return err("모르는 모드: %s" % mod_id)
    errs = host.save_settings(m, {key: value})
    if errs:
        if _json_mode:
            out({"ok": False, "errors": errs})
        else:
            for k, e in errs.items():
                print("오류: %s: %s" % (k, e))
        return 1
    return ok("설정 저장: %s.%s = %s" % (mod_id, key, value))


# ---- 로그/보고 ----
def cmd_log(args):
    """모드의 최근 로그."""
    if not args:
        return err("모드 id를 지정하세요: cli.py log <id>")
    mod_id = args[0]
    since = 0
    for i, a in enumerate(args):
        if a == "--since" and i + 1 < len(args):
            since = int(args[i + 1])
    data = host.get_mod_log(mod_id, since)
    if _json_mode:
        out(data)
        return 0
    entries = data.get("entries") or []
    if not entries:
        print("(로그가 없습니다)")
        return 0
    print("─── %s 로그 (%d개) ───" % (mod_id, len(entries)))
    for e in entries:
        print(host.format_log_entry(e))
    print("\n마지막 번호: %d, 오류 %d개" % (data.get("last", 0), data.get("errors", 0)))
    return 0


def cmd_log_clear(args):
    """모드 로그 지우기."""
    if not args:
        return err("모드 id를 지정하세요: cli.py log-clear <id>")
    host.clear_mod_log(args[0])
    return ok("로그를 지웠습니다")


def cmd_report(args):
    """AI에게 줄 모드 상태 보고서."""
    if not args:
        return err("모드 id를 지정하세요: cli.py report <id>")
    mod_id = args[0]
    host.rescan()
    text = host.mod_report(mod_id)
    if not text:
        return err("모르는 모드: %s" % mod_id)
    if _json_mode:
        out({"report": text})
    else:
        print(text)
    return 0


def cmd_build_report(args):
    """게임 빌드 진단 보고서 (Steam판 등 모르는 빌드에서 어디가 다른지). 게임에 한 번 붙은 뒤에 만들 수 있어요."""
    text = host.build_report()
    if text is None:
        return err("아직 게임 빌드를 확인한 적이 없어요. 게임을 켜고 로더가 붙은 뒤에 다시 해 보세요 (cli.py start --now --wait 90).")
    host.save_build_report()
    if _json_mode:
        out({"report": text, "file": host.BUILD_REPORT})
    else:
        print(text)
    return 0


def cmd_writes(args):
    """모드의 게임 값 쓰기 기록."""
    if not args:
        return err("모드 id를 지정하세요: cli.py writes <id>")
    mod_id = args[0]
    rows = host.write_log(mod_id)
    if _json_mode:
        out(rows)
        return 0
    if not rows:
        print("쓰기 기록이 없습니다")
        return 0
    print("─── %s 쓰기 기록 (%d개) ───" % (mod_id, len(rows)))
    for r in rows:
        undo = " (되돌림)" if r.get("undone") else ""
        print("  #%d %s %s %s(%s): %s → %s%s%s" % (
            r.get("n", 0), r.get("time", ""), r.get("field", ""), r.get("name", ""),
            r.get("key", ""), r.get("from"), r.get("to"), undo,
            ("  이유: %s" % r["reason"]) if r.get("reason") else ""))
    return 0


def cmd_undo(args):
    """모드가 바꾼 값 되돌리기."""
    if not args:
        return err("모드 id를 지정하세요: cli.py undo <id>")
    mod_id = args[0]
    r = host.undo_writes(mod_id)
    if _json_mode:
        out(r)
    elif r.get("ok"):
        print("되돌리기 완료: %d개 되돌림" % r.get("done", 0))
        for s in r.get("skipped") or []:
            print("  건너뜀 #%d %s: %s" % (s.get("n", 0), s.get("name", ""), s.get("error", "")))
    else:
        print("되돌리기 안 됨: %s" % r.get("error"))
    return 0 if r.get("ok") else 1


# ---- 안전 모드 ----
def cmd_safe(args):
    """안전 모드 상태."""
    host.rescan()
    si = host.safe_info()
    if _json_mode:
        out(si or {"active": False})
        return 0
    if not si:
        print("안전 모드가 아닙니다")
        return 0
    print("⚠ 안전 모드")
    print("  직전 종료: %s (%s)" % (si.get("code"), si.get("time")))
    print("  올라가 있던 모드: %s" % ", ".join(si.get("mods") or []))
    if si.get("allowed"):
        print("  이번에 허용한 모드: %s" % ", ".join(si["allowed"]))
    print("\n해제: cli.py safe-leave")
    return 0


def cmd_safe_leave(args):
    """안전 모드 끝내기."""
    host.rescan()
    if host.leave_safe_mode():
        return ok("안전 모드를 끝냈습니다. 켜 둔 모드를 올립니다")
    return ok("안전 모드가 아닙니다")


# ---- 검사 ----
def cmd_validate(args):
    """모드 검사."""
    if not args:
        return err("모드 경로를 지정하세요: cli.py validate <경로>")
    path = os.path.abspath(args[0])
    if not os.path.exists(path):
        return err("경로를 찾을 수 없습니다: %s" % path)
    rep = vlib.validate(path)
    d = rep.to_dict()
    if _json_mode:
        out(d)
    else:
        print(vlib.format_text(rep))
    return 0 if d.get("ok") else 1


# ---- 폴더 ----
def cmd_open_mods(args):
    """모드 폴더 열기 (탐색기)."""
    os.makedirs(modlib.USER_MODS, exist_ok=True)
    if _json_mode:
        out({"path": modlib.USER_MODS})
    else:
        os.startfile(modlib.USER_MODS)  # noqa: S606
        print("모드 폴더: %s" % modlib.USER_MODS)
    return 0


def cmd_open_data(args):
    """모드 데이터 폴더 열기 (탐색기)."""
    if not args:
        return err("모드 id를 지정하세요: cli.py open-data <id>")
    host.rescan()
    m = host.find_mod(args[0])
    if not m:
        return err("모르는 모드: %s" % args[0])
    os.makedirs(m.data_dir, exist_ok=True)
    if _json_mode:
        out({"path": m.data_dir})
    else:
        os.startfile(m.data_dir)  # noqa: S606
        print("데이터 폴더: %s" % m.data_dir)
    return 0


def cmd_version(args):
    """버전."""
    out({"version": modlib.CORE_VERSION, "core": modlib.CORE_VERSION})
    return 0


# ---- watch: 상태를 주기적으로 출력 (AI 모니터링용) ----
def cmd_watch(args):
    """상태를 주기적으로 JSON으로 출력 (AI가 폴링하지 않아도 되게).
    --interval <초>  출력 간격 (기본 5초)
    --until <단계>   이 단계에 도달하면 멈춤 (hooked, error, unsupported 등)
    """
    interval = 5
    until = None
    for i, a in enumerate(args):
        if a == "--interval" and i + 1 < len(args):
            interval = max(1, int(args[i + 1]))
        elif a == "--until" and i + 1 < len(args):
            until = args[i + 1]
    try:
        while True:
            st = _status()
            line = json.dumps({"time": time.strftime("%H:%M:%S"), "phase": st["phase"],
                               "running": st["running"], "build": st.get("build"),
                               "game": st.get("game"), "mods_loaded": [m["id"] for m in st.get("mods") or [] if m.get("state") == "running"]},
                              ensure_ascii=False)
            print(line, flush=True)
            if until and st["phase"] == until:
                return 0
            time.sleep(interval)
    except KeyboardInterrupt:
        return 0


def _status():
    """상태: 실행 중인 로더가 있으면 그쪽 상태, 없으면 이 프로세스의 상태."""
    r = control.call(["status", "--json"])
    if r and r[0] == 0:
        try:
            return json.loads(r[1])
        except ValueError:
            pass
    return host.status()


# ═══════════════════════════════════════════════════
# 명령 등록
# ═══════════════════════════════════════════════════
# ---- 게임 조사 (M19) ----

def _slot_text(s):
    """explore 한 칸을 사람이 읽는 한 줄로."""
    if s.get("error"):
        return "+0x%03x  %s" % (s["off"], s["error"])
    parts = []
    if s.get("cls"):
        parts.append("-> %s%s" % (s["cls"], " (+0x%x 위치)" % s["clsOff"] if s.get("clsOff") else ""))
    elif s.get("vtableOf"):
        parts.append("vtable %s" % s["vtableOf"])
    elif s.get("mod"):
        parts.append("fm%s" % s["mod"])
    elif s.get("str"):
        parts.append("글 %r" % s["str"])
    elif s.get("ptr"):
        parts.append("-> (구조체, RTTI 없음)")
    else:
        a, b = s["i32"]
        parts.append("i32 %d, %d" % (a, b))
        if any(abs(x) < 400 for x in s["i16"]) and (abs(a) > 0xffff or abs(b) > 0xffff):
            parts.append("i16 %s" % ",".join(str(x) for x in s["i16"]))
        if s.get("f32"):
            parts.append("f32 %s" % ", ".join("NaN" if x is None else "%g" % x for x in s["f32"]))
        if s.get("date"):
            parts.append("날짜 %s" % ", ".join(d or "-" for d in s["date"]))
    if s.get("fields"):   # 필드 등록부에 있는 칸 (M20)
        parts.insert(0, "[%s]" % ", ".join(s["fields"]))
    return "+0x%03x  %s  %s" % (s["off"], s["hex"], "  ".join(parts))


def cmd_explore(args):
    """게임 객체를 8바이트씩 펼쳐 보인다. 포인터는 따라가서 클래스 이름(RTTI)을 붙인다."""
    if not args:
        return err("사용: cli.py explore <대상> [시작 칸] [크기]  (대상: 0x주소 | player:<uid> | person:<uid> | me | myclub, "
                   "뒤에 /+0x130 처럼 포인터 따라가기. 예: explore player:2002122126/+0x130 0 0x100)")
    frm = int(args[1], 16) if len(args) > 1 else 0
    size = int(args[2], 16) if len(args) > 2 else 0x200
    r = host.explore(args[0], frm, size)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    print("%s = %s  %s%s" % (r["path"], r["addr"], r["cls"] or "(RTTI 없음)",
                             " (객체 +0x%x 위치, 맨 앞 %s)" % (r["clsOff"], r["top"]) if r.get("clsOff") else ""))
    if r.get("bases"):
        print("  기반: " + " > ".join(r["bases"]))
    for s in r["slots"]:
        print("  " + _slot_text(s))
    return 0


def _engine_ctx():
    """(m24engine 모듈, 게임 설치 폴더, 원본 표, 메모리 표) — engine apply/restore/diff 공용."""
    sys.path.insert(0, os.path.join(HERE, "..", "pylib")) if os.path.join(HERE, "..", "pylib") not in sys.path else None
    import m24engine
    info = host._cur.get("info") or {}
    exe = info.get("path")
    if not exe:
        raise RuntimeError("게임에 연결돼 있지 않아요 (cli.py start --now --wait 60)")
    game = os.path.dirname(exe)
    orig = m24engine.load_game_original(game)
    mem = {}
    for t in ("weights", "physics", "momentum", "ratings"):
        r = host.rpc("enginedump", t)
        if not r or r.get("error"):
            raise RuntimeError("%s 읽기 실패: %s" % (t, (r or {}).get("error")))
        mem[t] = r
    mem["styles"] = host.rpc("enginedump", "styles")   # 첫 진행일 전에는 error (plan이 알림, E09)
    mem["xg"] = host.rpc("enginedump", "xg")   # E10
    return m24engine, game, orig, mem


def _engine_write_all(writes, force=False):
    done, errs, missing = 0, [], 0
    for t, spec in writes:
        r = host.rpc("enginewrite", t, spec, force)
        if not r or r.get("error"):
            errs.append("%s: %s" % (t, (r or {}).get("error")))
            if "진행 중" in str((r or {}).get("error")):
                break
        else:
            done += r.get("written", 0); missing += len(r.get("missing") or [])
    return done, errs, missing


def cmd_engine(args):
    """매치엔진 표 (DynamicME, E03): dump(읽기) / apply <팩 simatch 폴더> [--dry] / restore."""
    usage = ("사용: cli.py engine dump <weights|physics|momentum|ratings|styles|xg> [--out 파일]\n"
             "      cli.py engine apply <엔진 팩의 simatch 폴더> [--dry]   (게임 메모리에 바로, 재시작 없음)\n"
             "      cli.py engine restore                                 (원본 simatch.fmf 값으로)")
    if not args:
        return err(usage)
    if args[0] == "dump":
        if len(args) < 2:
            return err(usage)
        outp = None
        if "--out" in args:
            i = args.index("--out"); outp = args[i + 1] if i + 1 < len(args) else None
        r = host.rpc("enginedump", args[1])
        if not r or r.get("error"):
            return err((r or {}).get("error") or "실패")
        if outp:
            with open(outp, "w", encoding="utf8") as f:
                json.dump(r, f, ensure_ascii=False)
            return ok("저장했어요: %s" % outp)
        if _json_mode:
            out(r)
            return 0
        n = len(r.get("ints") or r.get("rows") or r.get("entries") or r.get("styles") or r.get("models") or [])
        print("%s: 매니저 %s, 항목 %d개 (전체는 --out 또는 --json)" % (r["table"], r["mgr"], n))
        return 0
    if args[0] in ("apply", "restore"):
        try:
            E, game, orig, mem = _engine_ctx()
        except Exception as e:  # noqa: BLE001
            return err(str(e))
        if args[0] == "apply":
            if len(args) < 2 or not os.path.isdir(args[1]):
                return err(usage)
            src = args[1]
            if os.path.isdir(os.path.join(src, "simatch")):
                src = os.path.join(src, "simatch")
            pack = {t: E.load_pack_table(src, t) for t in E.TABLE_FILES}
            writes, notes = E.plan(pack, orig, mem)
        else:
            writes, notes = E.restore_plan(orig, mem), [("info", "원본 simatch.fmf 값으로 되돌려요")]
        if "--dry" in args:
            if _json_mode:
                out({"writes": [(t, sorted(s.keys())) for t, s in writes], "notes": notes})
            else:
                for lv, msg in notes:
                    print("[%s] %s" % (lv, msg))
                print("쓸 곳: " + ", ".join("%s%s" % (t, "[%s]" % s["entry"] if "entry" in s else "") for t, s in writes))
            return 0
        done, errs, missing = _engine_write_all(writes)
        if "--dry" not in args:
            notes = notes + E.qme_sync(game, pack if args[0] == "apply" else {}, orig)[1]   # QME: 엔진 폴더 파일 (재시작 필요, E11)
        for lv, msg in notes:
            print("[%s] %s" % (lv, msg)) if not _json_mode else None
        if errs:
            return err("일부 실패: " + "; ".join(errs))
        return ok("썼어요: 칸 %d개 (없는 칸 %d)" % (done, missing), notes=notes)
    return err(usage)


def cmd_get(args):
    """필드 등록부의 칸 읽기 (M20). 여러 필드를 한 번에 줄 수 있다. 끝이 '.'이면 그 이름으로 시작하는 필드 전부."""
    if len(args) < 2:
        return err("사용: cli.py get <대상> <필드> [필드...]  (예: get player:2002122126 player.ca player.pa player.askingPrice, "
                   "get player:2002122126 player.season.league.)")
    import caps as caplib
    names = []
    for a in args[1:]:
        names += sorted(n for n in caplib.fields()["fields"] if n.startswith(a)) if a.endswith(".") else [a]
    res = []
    for n in names:
        r = host.getfield(args[0], n)
        if r and r.get("error"):
            return err(r["error"])
        res.append(r)
    if _json_mode:
        out(res)
        return 0
    if res:
        print("%s (%s)" % (res[0]["path"], res[0].get("cls") or "?"))
    for r in res:
        v = r["value"]
        print("  %-40s %s" % (r["name"], v["iso"] if isinstance(v, dict) and "iso" in v else json.dumps(v, ensure_ascii=False)))
    return 0


def _prop_names():
    """개발 PC에만 있는 속성 영어 이름표 (~/m24ga_data/prop_names.tsv, 게임 파일에서 뽑은 것이라 저장소에 없음)."""
    names = {}
    path = os.path.join(modlib.DATA, "prop_names.tsv")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "\t" in line:
                    c, n = line.rstrip("\n").split("\t", 1)
                    names[c] = n
    return names


def _prop_reg():
    with open(os.path.join(modlib.ROOT, "core", "properties.json"), encoding="utf-8") as f:
        return json.load(f)


def cmd_props(args):
    """게임 속성 코드 값 전부 (M55, 코어 0.36.0)."""
    empty = bool(_opt(args, "--empty", flag=True))
    if not args:
        return err("사용: cli.py props <대상> [정규식] [--empty]  (예: props myteam ^C, props p12345 Pc)")
    r = host.rpc("props", args[0], args[1] if len(args) > 1 else None, empty)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    reg, names = _prop_reg()["props"], _prop_names()
    print("%s %s (%s) — %d개, %dms" % (args[0], r["cls"], r["kind"], len(r["props"]), r["ms"]))
    for c, v in sorted(r["props"].items()):
        p = reg.get(c, {})
        label = p.get("ko") or names.get(c, "")
        print("  %s %-5s %-40s %s" % (c, p.get("t", "?"), json.dumps(v, ensure_ascii=False)[:120], label[:50]))
    return 0


def cmd_prop_find(args):
    """값으로 속성 코드 찾기 (M55)."""
    if len(args) < 2:
        return err("사용: cli.py prop-find <대상> <값>  (예: prop-find myteam 2038-06-30, prop-find me 47)")
    r = host.rpc("propfind", args[0], " ".join(args[1:]))
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    names = _prop_names()
    print("%s %s — %d곳" % (args[0], r["cls"], len(r["hits"])))
    for h in r["hits"]:
        print("  %-30s %-20s %s" % (h["path"], json.dumps(h["value"], ensure_ascii=False)[:20], names.get(h["code"], "")))
    return 0


def cmd_prop_info(args):
    """속성 등록부 목록 (게임 없이 됨)."""
    import re
    reg, names = _prop_reg(), _prop_names()
    rx = re.compile(args[0], re.I) if args else None
    rows = [(c, p) for c, p in reg["props"].items()
            if not rx or rx.search(c) or rx.search(p.get("ko", "")) or rx.search(names.get(c, ""))]
    if _json_mode:
        out(dict(rows))
        return 0
    for c, p in rows:
        print("  %s %-5s %-34s %s" % (c, p["t"], ",".join(p["k"]), p.get("ko") or names.get(c, "")))
    print("(%d개, 등록부 core/properties.json, 문서 docs/PROPERTIES.md)" % len(rows))
    return 0


def cmd_actions(args):
    """게임 액션 등록부 목록 (M62, 게임 없이 됨)."""
    import re
    with open(os.path.join(modlib.ROOT, "core", "actions.json"), encoding="utf-8") as f:
        reg = json.load(f)
    rx = re.compile(args[0], re.I) if args else None
    rows = [(a, e) for a, e in reg["actions"].items() if not rx or rx.search(a) or rx.search(e["class"]) or rx.search(e["group"])]
    if _json_mode:
        out(dict(rows))
        return 0
    for a, e in rows:
        u = e.get("ui") or {}
        ev = "실행 없음" if not u else "실행 불가(빈 처리기)" if u.get("noop") else "실행:" + ",".join(u["events"] + [x for x in u.get("click", []) if x not in u["events"]]) + ("(확인 뒤 %s)" % u["confirm"] if u.get("confirm") else "")
        print("  %-5s %-62s %-8s %-22s %s" % (a, e["class"], "보호" if e["protected"] else "", ev, " ".join(e.get("keys", [])[:8])))
    print("(%d개, core/actions.json, docs/ACTIONS.md. 모드 API: api.actionsFor / api.action, 코어 0.41.0)" % len(rows))
    return 0


def cmd_fields(args):
    """필드 등록부 목록 (게임 없이 됨)."""
    import caps as caplib
    import re
    fr = caplib.fields()
    rx = re.compile(args[0], re.I) if args else None
    rows = [(n, f) for n, f in fr["fields"].items() if not rx or rx.search(n) or rx.search(f.get("desc", ""))]
    if _json_mode:
        out(dict(rows))
        return 0
    for n, f in rows:
        print("%-38s %-7s %-6s %s%s%s" % (n, f["type"], "safe" if f.get("write") == "safe" else "-",
                                       "" if f.get("verified") else "(미확인) ", f.get("desc", ""), (" [%s]" % f["unit"]) if f.get("unit") else ""))
    print("(%d개, 자세한 표는 docs/FIELDS.md)" % len(rows))
    return 0


# ---- 찾기 도구 (M21) ----
KRW_PER_UNIT = 1664.7   # 게임 내부 돈 단위 -> 원 (소셜피드 로그 34에서 화면과 맞춤)


def _opt(args, name, default=None, flag=False):
    """args에서 --name 값(또는 플래그)을 꺼낸다 (args를 고친다)."""
    if name not in args:
        return default
    i = args.index(name)
    if flag:
        del args[i]
        return True
    if i + 1 >= len(args):
        raise ValueError("%s 뒤에 값이 필요해요" % name)
    v = args[i + 1]
    del args[i:i + 2]
    return v


def _parse_value(text, tol):
    """'89100000' | '100..200' | '180억' | '1.2' -> (lo, hi). tol = 상대 오차 (억 단위는 기본 0.5%)."""
    t = text.replace(",", "").strip()
    if ".." in t:
        a, b = t.split("..", 1)
        return float(a), float(b)
    if t.endswith("억"):
        v = float(t[:-1]) * 1e8 / KRW_PER_UNIT
        tol = 0.02 if tol is None else tol   # 화면 몸값은 반올림·단위 깎기가 있어 2% (245억 화면 = 247.2억 실제)
    else:
        v = float(t)
        tol = tol or 0
    d = abs(v) * tol
    return v - d, v + d


def _kind_of(cls, bases):
    import caps as caplib
    for k, kd in caplib.fields()["kinds"].items():
        if cls == kd["cls"] or kd["cls"] in (bases or []):
            return k
    return None


def cmd_find_field(args):
    """알려진 값으로 칸 찾기. 대상을 여러 개 주면 모두에서 같은 위치·형식인 칸만 남기고 fields.json 줄 초안을 보여 준다."""
    args = list(args)
    try:
        types = _opt(args, "--type")
        tol = _opt(args, "--tol")
        size = _opt(args, "--size")
        shallow = _opt(args, "--shallow", flag=True)
        name = _opt(args, "--name")
        targets = []
        for a in args:
            if "=" not in a:
                raise ValueError("대상=값 형식이 아니에요: %s" % a)
            spec, val = a.rsplit("=", 1)
            lo, hi = _parse_value(val, float(tol) if tol else None)
            targets.append((spec, val, lo, hi))
    except ValueError as e:
        return err(str(e))
    if not targets:
        return err("사용: cli.py find-field <대상>=<값> [<대상>=<값> ...] [--type i32,f32] [--tol 0.01] [--size 0x800] [--shallow] [--name 필드이름]\n"
                   "  값: 89100000 | 100..200 | 180억 (게임 돈, 기본 오차 2%)\n"
                   "  예: find-field player:2002122126=1480억 player:19302146=245억 --type i32 --name player.askingPrice")
    results = []
    for spec, val, lo, hi in targets:
        tl = types.split(",") if types else (["i32", "u32", "f32", "f64"] if max(abs(lo), abs(hi)) > 65535 else ["i32", "u32", "i16", "u16", "u8", "f32", "f64"])
        r = host.rpc("findfield", spec, {"lo": lo, "hi": hi, "types": tl, "size": int(size, 16) if size else 0x800, "deep": not shallow})
        if not r or r.get("error"):
            return err((r or {}).get("error") or "실패")
        r["want"] = val
        results.append(r)

    def key(h):
        return ("/".join(h["via"]), h["off"], h["type"])
    common = None
    for r in results:
        ks = {key(h) for h in r["hits"]}
        common = ks if common is None else common & ks
    common = sorted(common or [], key=lambda k: (len(k[0]) > 0, int(k[1], 16), k[2]))
    kind = _kind_of(results[0]["cls"], results[0].get("bases"))
    drafts = []
    for via, off, typ in common[:5]:
        line = {"kind": kind or "?", "off": off, "type": typ, "desc": "TODO: 뜻", "source": "find-field %s" % time.strftime("%Y-%m-%d"),
                "verified": False, "write": "no"}
        if via:
            line = dict({"kind": line["kind"], "via": via.split("/")}, **{k: v for k, v in line.items() if k != "kind"})
        drafts.append({(name or "%s.TODO" % (kind or "x")): line})
    if _json_mode:
        out({"targets": [{"path": r["path"], "cls": r["cls"], "want": r["want"], "hits": len(r["hits"]), "truncated": r.get("truncated")} for r in results],
             "common": [{"via": k[0].split("/") if k[0] else [], "off": k[1], "type": k[2]} for k in common], "drafts": drafts})
        return 0
    for r in results:
        print("%s (%s) 값 %s: 맞는 칸 %d개%s" % (r["path"], r["cls"] or "RTTI 없음", r["want"], len(r["hits"]), " (400개에서 자름)" if r.get("truncated") else ""))
        if len(results) == 1:
            for h in r["hits"][:40]:
                print("  %s+%s %s = %s" % ("".join("+%s->" % x for x in h["via"]), h["off"], h["type"], h["value"]))
    if len(results) > 1:
        print("모든 대상에서 같은 칸: %d개" % len(common))
        for via, off, typ in common[:20]:
            vals = []
            for r in results:
                h = next(h for h in r["hits"] if key(h) == (via, off, typ))
                vals.append(str(h["value"]))
            print("  %s+%s %s  (%s)" % ("".join("+%s->" % x for x in via.split("/")) if via else "", off, typ, ", ".join(vals)))
    if drafts and len(results) > 1:
        print("fields.json 초안 (뜻·근거를 채우고 확인하면 verified: true):")
        print("  " + json.dumps(drafts[0], ensure_ascii=False)[1:-1])
    return 0


def _func_namer():
    """'fm+0x1234' -> 'fm+0x1234 (함수 fm+0x1200 +0x34)' (fm.exe 예외 테이블)."""
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    try:
        import rtti
        pe = rtti.PE(rtti.DEFAULT_EXE)
    except Exception:  # noqa: BLE001
        return lambda s: s

    def name(s):
        if not s.startswith("fm+0x"):
            return s
        rva = int(s[3:], 16)
        f = pe.func_of(rva)
        return "%s (함수 fm+0x%x +0x%x)" % (s, f[0], rva - f[0]) if f else s + " (함수 표에 없음: Denuvo 영역일 수 있음)"
    return name


def _print_watch(r):
    print("%s %s = %s, %d바이트, %s 감시, 스레드 %d개%s" % ("감시 중" if r["active"] else "끝남(%s)" % r["why"], r["path"], r["addr"], r["size"],
                                                       {"w": "쓰기", "rw": "읽기·쓰기"}.get(r["cond"], r["cond"]), r["threads"], ", 못 건 스레드 %d" % r["fails"] if r["fails"] else ""))
    print("  %.1f초, 잡힌 횟수 %d (자리 %d곳%s), 값 %s -> %s" % (r["secs"], r["total"], len(r["hits"]), ", 버림 %d" % r["dropped"] if r["dropped"] else "", r["before"], r["now"]))
    if not r["active"] and r.get("excSet"):
        print("  주의: 예외 처리기가 아직 남아 있어요%s. 게임을 저장하고, 로더를 끄기 전에 watch-write stop을 한 번 더 하세요" % (" (" + r["excErr"] + ")" if r.get("excErr") else ""))
    fn = _func_namer() if r["hits"] else None
    for h in r["hits"]:
        print("  [%d번] %s  (처음 %.1f초, 스레드 %d)" % (h["count"], fn(h["pc"]), h["first"] / 1000, h["tid"]))
        if h.get("values"):
            print("      값: %s" % ", ".join(str(v) for v in h["values"]))
        for rn, c in sorted(h.get("regs", {}).items()):
            print("      %s -> %s" % (rn, c))
        for i, a in enumerate(h.get("bt", [])[:8]):
            print("      %s %s" % ("호출 경로" if i == 0 else "         ", fn(a)))


def cmd_watch_write(args):
    """칸 하나에 하드웨어 감시를 걸어 그 칸에 쓰는 게임 코드를 찾는다. 자동으로 풀린다 (--max 번 / --secs 초)."""
    args = list(args)
    if args and args[0] in ("show", "stop"):
        r = host.rpc("watchreport" if args[0] == "show" else "watchstop")
        if not r or r.get("error"):
            return err((r or {}).get("error") or "실패")
        if _json_mode:
            out(r)
        else:
            _print_watch(r)
        return 0
    try:
        secs = int(_opt(args, "--secs", "60"))
        mx = int(_opt(args, "--max", "30"))
        wait = int(_opt(args, "--wait", "0"))
        rw = _opt(args, "--rw", flag=True)
    except ValueError as e:
        return err(str(e))
    if len(args) < 2:
        return err("사용: cli.py watch-write <대상> <칸> [크기 1|2|4|8] [--secs 60] [--max 30] [--wait 초] [--rw]\n"
                   "       cli.py watch-write show | stop\n"
                   "  예: watch-write player:2002122126 0x1d0 4 --secs 120 --wait 120   (그동안 게임에서 그 값이 바뀌게 하기)\n"
                   "      watch-write fm+0x631d5bc 0 4 --wait 60   (게임 날짜)\n"
                   "  주의: 디버그 레지스터를 써요. 게임이 튕길 수 있으니 저장하고 쓰세요")
    size = int(args[2]) if len(args) > 2 else 4
    r = host.rpc("watchstart", args[0], int(args[1], 16), size, "rw" if rw else "w", mx, secs)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if wait:
        if not _json_mode:
            print("감시를 걸었어요: %s (%d초 동안 기다려요. 게임에서 그 값이 바뀌게 해 주세요)" % (r["path"], wait), flush=True)
        end = time.time() + wait
        while time.time() < end:
            time.sleep(2)
            r = host.rpc("watchreport")
            if not r or r.get("error") or not r.get("active"):
                break
    if _json_mode:
        out(r)
    else:
        _print_watch(r)
    return 0


def _watch_wait_client(argv, cmd="watch-write"):
    """실행 중인 앱으로 watch-write를 보낼 때 --wait는 이 CLI 프로세스에서 기다린다 (M21: 앱 안에서 기다리면
    그동안 다른 CLI 명령, 특히 watch-write show/stop이 줄을 서서 막혔다)."""
    argv = list(argv)
    wait = int(_opt(argv, "--wait", "0"))
    r = control.call([cmd] + argv + ["--json"])
    if r is None or r[0] != 0:
        sys.stdout.write(r[1] if r else "오류: 앱에 보내지 못했어요\n")
        return r[0] if r else 1
    if not _json_mode:
        print("걸었어요 (%d초 동안 기다려요. 게임을 진행해 주세요. 다른 창에서 %s show / stop 가능)" % (wait, cmd), flush=True)
    end = time.time() + wait
    while time.time() < end:
        time.sleep(2)
        r = control.call([cmd, "show", "--json"])
        try:
            if r is None or not json.loads(r[1]).get("active"):
                break
        except ValueError:
            break
    r = control.call([cmd, "show"] + (["--json"] if _json_mode else []))
    sys.stdout.write(r[1] if r else "오류: 결과를 받지 못했어요\n")
    return r[0] if r else 1


def cmd_find_global(args):
    """fm.exe 전역 칸 중 이름이 정규식에 맞는 클래스의 객체를 가리키는 것 (싱글턴 찾기, M24)."""
    if not args:
        return err("사용: cli.py find-global <클래스 정규식> [최대 개수]  (예: find-global '^GAME_UI$')")
    r = host.rpc("findglobals", args[0], int(args[1]) if len(args) > 1 else 30)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    for h in r["hits"]:
        print("  %s -> %s  %s" % (h["at"], h["obj"], h["cls"]))
    print("(%d개, 포인터 %d개 확인, %dms%s)" % (len(r["hits"]), r["seen"], r["ms"], ", 시간 예산에서 멈춤" if r.get("partial") else ""))
    return 0


def cmd_find_objects(args):
    """이름이 정규식에 맞는 클래스의 객체를 게임 메모리에서 찾는다 (vtable 검색, M24). 클래스는 정확히 맞추는 것을 권장 (예: '^BUTTON$')."""
    args = list(args)
    try:
        mx = int(_opt(args, "--max", "40"))
        secs = int(_opt(args, "--secs", "20"))
    except ValueError as e:
        return err(str(e))
    if not args:
        return err("사용: cli.py find-objects <클래스 정규식> [--max 40] [--secs 20]  (예: find-objects '^MAKE_OFFER_TO_PLAYER_ACTION$')")
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import rtti
    import re
    rx = re.compile(args[0])
    vts = [v["rva"] for n, c in rtti.load()["classes"].items() if rx.search(n) for v in c["vtables"] if not v["off"]]   # 객체 맨 앞의 vtable만
    if not vts:
        return err("맞는 클래스가 없어요 (cli.py classes로 이름 확인)")
    if len(vts) > 24:
        return err("맞는 클래스가 너무 많아요 (%d개 vtable). 정규식을 좁히세요" % len(vts))
    r = host.rpc("findobjects", vts, mx, secs * 1000)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    for h in r["hits"]:
        print("  %s  %s" % (h["obj"], h["cls"]))
    print("(%d개, %dMB 훑음, %dms%s)" % (len(r["hits"]), r["scannedMB"], r["ms"], ", 시간 예산에서 멈춤" if r.get("partial") else ""))
    return 0


_FB_TYPES = {"--u8": "<B", "--i8": "<b", "--u16": "<H", "--i16": "<h", "--u32": "<I", "--i32": "<i",
             "--u64": "<Q", "--i64": "<q", "--f32": "<f", "--f64": "<d"}


def find_bytes_pattern(args):
    """find-bytes 인자 -> Frida 패턴 문자열 ('0b ?? 0f'). 값 형식이 없으면 16진수 그대로 (?? = 아무 바이트).
    값 형식: --i32 11 15 ? 4  (? = 그 크기만큼 아무 바이트)."""
    import struct
    fmt = None
    for k in _FB_TYPES:
        if k in args:
            fmt = _FB_TYPES[k]
            args.remove(k)
            break
    if fmt is None:
        toks = " ".join(args).replace(",", " ").split()
        out = []
        for t in toks:
            t = t.lower()
            if t in ("?", "??"):
                out.append("??")
                continue
            if len(t) % 2 or any(c not in "0123456789abcdef" for c in t):
                raise ValueError("16진수가 아니에요: %s" % t)
            out += [t[i:i + 2] for i in range(0, len(t), 2)]
        if not out:
            raise ValueError("패턴이 비었어요")
        return " ".join(out)
    size = struct.calcsize(fmt)
    out = []
    for t in " ".join(args).replace(",", " ").split():
        if t in ("?", "??"):
            out += ["??"] * size
            continue
        v = float(t) if fmt in ("<f", "<d") else int(t, 0)
        out += ["%02x" % b for b in struct.pack(fmt, v)]
    if not out:
        raise ValueError("값이 없어요")
    return " ".join(out)


def cmd_find_bytes(args):
    """바이트 패턴이나 값 나열을 게임 힙에서 찾는다 (E09). 찾은 곳의 앞뒤 바이트와 (--owner) 주인 객체."""
    args = list(args)
    try:
        opt = {"max": int(_opt(args, "--max", "40")), "budget": int(_opt(args, "--secs", "20")) * 1000,
               "align": int(_opt(args, "--align", "1"), 0), "ctx": int(_opt(args, "--ctx", "16"), 0),
               "module": bool(_opt(args, "--module", flag=True)), "owner": bool(_opt(args, "--owner", flag=True))}
        if not args:
            raise ValueError("사용: cli.py find-bytes <16진수 ?? …> | --i32 11 15 ? 4  [--u8|--i16|--u32|--f32|--f64 …] "
                             "[--max 40] [--secs 20] [--align 4] [--ctx 16] [--module] [--owner]")
        pat = find_bytes_pattern(args)
    except ValueError as e:
        return err(str(e))
    r = host.rpc("findbytes", pat, opt)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    print("패턴: %s" % r["pat"])
    for h in r["hits"]:
        hold = h.get("holder")
        print("  %s%s" % (h["at"], "  [%s %s+%s]" % (hold["cls"], hold["owner"], hold["off"]) if hold else ""))
        if h.get("ctx"):
            print("      %s: %s" % (h["ctxAt"], h["ctx"]))
    print("(%d곳, %dMB 훑음, %dms%s)" % (len(r["hits"]), r["scannedMB"], r["ms"],
                                       ", 시간 예산에서 멈춤" if r.get("partial") else (", 최대 개수에서 멈춤" if r.get("truncated") else "")))
    return 0


def cmd_find_refs(args):
    """어떤 주소(explore와 같은 대상 이름)를 가리키는 칸을 힙·전역에서 찾는다. 칸마다 그 칸을 가진 객체의 클래스와 위치 (M25)."""
    args = list(args)
    try:
        mx = int(_opt(args, "--max", "40"))
        secs = int(_opt(args, "--secs", "20"))
        back = int(_opt(args, "--back", "0x800"), 0)
    except ValueError as e:
        return err(str(e))
    if not args:
        return err("사용: cli.py find-refs <대상> [--max 40] [--secs 20] [--back 0x800]  (예: find-refs 0x1d5de7c0)")
    r = host.rpc("findrefs", args[0], mx, secs * 1000, back)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    for h in r["hits"]:
        print("  %s  %s" % (h["at"], ("%s +%s  (객체 %s)" % (h["cls"], h["off"], h["owner"])) if h.get("cls") else "(RTTI 객체 밖)"))
    print("(%d개, %dMB 훑음, %dms%s)" % (len(r["hits"]), r["scannedMB"], r["ms"], ", 시간 예산에서 멈춤" if r.get("partial") else ""))
    return 0


def cmd_find_const(args):
    """find-const <4글자> [--max 60]: 실행 중인 fm.exe 모듈에서 4글자 상수가 있는 곳 (M37). 게임 코드가 그 id를 직접 쓰는지 확인할 때."""
    args = list(args)
    mx = int(_opt(args, "--max", "60"))
    if not args or not 1 <= len(args[0]) <= 4:
        return err("사용: cli.py find-const <4글자> [--max 60]")
    r = host.rpc("findconst", args[0], mx)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    for h in r["hits"]:
        print("  %s  %s" % (h["at"], h["prot"]))
    print("('%s' %d곳%s, %dms)" % (r["code"], len(r["hits"]), " 이상" if r.get("truncated") else "", r["ms"]))
    return 0


def cmd_find_text(args):
    """화면 글이 메모리 어디에 있고 어느 객체가 들고 있나 (M25). 글 -> 길이 칸을 가리키는 칸 -> 핸들 칸 -> 주인 객체"""
    args = list(args)
    try:
        mx = int(_opt(args, "--max", "6"))
        secs = int(_opt(args, "--secs", "40"))
    except ValueError as e:
        return err(str(e))
    if not args:
        return err("사용: cli.py find-text <화면 글> [--max 6] [--secs 40]")
    r = host.rpc("findtext", args[0], mx, secs * 1000)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0

    def hold(h):
        return "%s +%s (객체 %s)" % (h["cls"], h["off"], h["owner"]) if h else "(RTTI 객체 밖)"
    for h in r["hits"]:
        print("글 %s 길이 %s: %s%s" % (h["str"], h.get("len"), (h.get("full") or "")[:80], "  [" + h["note"] + "]" if h.get("note") else ""))
        for x in h.get("refs", []):
            print("   <- %s  %s" % (x["at"], hold(x.get("holder"))))
            for y in x.get("handles", []):
                print("      <- %s  %s" % (y["at"], hold(y.get("holder"))))
    print("(%dms%s)" % (r["ms"], ", 시간 예산에서 멈춤" if r.get("partial") else ""))
    return 0


def cmd_ui(args):
    """게임 화면 읽기 (M25, AI 플레이 A단계 "보는 눈").
    ui text  : 지금 보이는 글이 있는 위젯만 (AI가 읽기 좋은 형식)
    ui tree  : 보이는 위젯 트리 전체 (--all이면 숨은 것도)
    옵션: --depth 40 --max 3000 --root 0x주소 --all --scan 0x400(조사용: 몸 안의 글 칸)"""
    args = list(args)
    sub = args.pop(0) if args else "text"
    if sub == "state":
        return _ui_state(args)
    if sub == "mail":
        return _ui_mail(args)
    if sub not in ("tree", "text"):
        return err("사용: cli.py ui text|tree [--depth 40] [--max 3000] [--root 0x주소] [--all] [--scan 0x400]")
    try:
        opts = {"depth": int(_opt(args, "--depth", "40")), "max": int(_opt(args, "--max", "3000")),
                "scan": int(_opt(args, "--scan", "0"), 0)}
        root = _opt(args, "--root", "")
    except ValueError as e:
        return err(str(e))
    if "--all" in args:
        opts["all"] = True
    if sub == "text":
        opts["textOnly"] = True
    if root:
        opts["root"] = root
    r = host.rpc("uitree", opts)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    for n in r["nodes"]:
        txt = " / ".join(t.replace("\n", "⏎") for t in n.get("text", []))
        mark = {True: "☑ ", False: "☐ "}.get(n.get("checked"), "")   # 체크박스 상태 (M27)
        if sub == "text":
            rc = n.get("rect")
            at = (" @%d,%d" % (rc[0] + rc[2] // 2, rc[1] + rc[3] // 2)) if rc else ""   # 가운데 좌표 (게임 창 픽셀)
            print("%s%s  [%s%s %s%s%s%s]" % (mark, txt, n["cls"], (" " + n["id"]) if n.get("id") else "", n["addr"], at,
                                            " 화면 밖" if n.get("off") else "", " 팝업" if n.get("modal") else ""))
            continue
        extra = []
        if n.get("id"):
            extra.append("id=" + n["id"])
        if n.get("kids"):
            extra.append("자식 %d" % n["kids"])
        extra.append("f=" + n.get("flags", "?"))
        if n.get("rect"):
            extra.append("(%d,%d %dx%d)" % tuple(n["rect"]))
        if n.get("hidden"):
            extra.append("숨음")
        if mark:
            extra.append(mark.strip())
        line = "%s%s %s  %s" % ("  " * n["d"], n["cls"], n["addr"], " ".join(extra))
        if txt:
            line += '  "%s"' % txt
        if n.get("str"):
            line += "  " + " | ".join(n["str"])
        print(line)
    print("(위젯 %d개, 숨어서 뺀 가지 %d개, %dms%s%s)" % (len(r["nodes"]), r.get("hidden", 0), r["ms"],
                                                  ", 팝업 떠 있음" if r.get("modal") else "", ", 최대 개수에서 멈춤" if r.get("truncated") else ""))
    return 0


def _state_line(s):
    return "%s %s  버튼:%s%s%s%s  화면:%s" % (
        s.get("date") or "?", s.get("clock") or "", s.get("button") or s.get("kindName") or "-",
        " [진행 중]" if s.get("processing") else "", " [팝업]" if s.get("modal") else "",
        " [답할 메일]" if s.get("needReply") else "", (s.get("title") or "?") + ((" > " + s["item"].replace("\n", " ")[:40]) if s.get("item") else ""))


def _jcall(argv, remote):
    """명령 하나를 JSON으로 실행해 (코드, dict). remote면 실행 중인 앱으로 보낸다 (기다리는 반복은 CLI 쪽에서 돌리려고, M30)."""
    global _json_mode
    if remote:
        r = control.call(list(argv) + ["--json"])
        if r is None:
            return 1, {"error": "앱에 보내지 못했어요"}
        code, text = r
    else:
        saved = _json_mode
        try:
            code, text = run_captured(list(argv) + ["--json"])
        finally:
            _json_mode = saved
    try:
        return code, json.loads(text)
    except ValueError:
        return code, {"error": text.strip()}


def _state_key(s):
    return (s.get("raw"), s.get("button"), s.get("processing"), s.get("modal"), s.get("needReply"), s.get("title"), s.get("item"), s.get("itemAddr"), s.get("itemBody"))


def _ui_state(args, remote=False):
    """ui state [--watch 초]: 게임 진행 상태 한 줄 (날짜·시각, 오른쪽 위 버튼, 진행 중, 팝업, 답할 메일, 화면 제목). --watch는 바뀔 때마다 (M30)"""
    try:
        watch = float(_opt(args, "--watch", "0"))
    except ValueError as e:
        return err(str(e))
    if not watch:
        s = host.rpc("uistate")
        if not s or s.get("error"):
            return err((s or {}).get("error") or "실패")
        if _json_mode:
            out(s)
        else:
            print(_state_line(s))
        return 0
    end, last = time.time() + watch, None
    while time.time() < end:
        code, s = _jcall(["ui", "state"], remote)
        if code == 0 and s and not s.get("error"):
            k = _state_key(s)
            if k != last:
                print("%s  %s  (raw %x)" % (time.strftime("%H:%M:%S"), _state_line(s), s.get("raw") or 0), flush=True)
                last = k
        time.sleep(0.25)
    return 0


def _continue_wait(args, remote=False):
    """act continue --wait [초]: 계속을 누르고, 게임이 멈춰서 사람(AI)의 입력을 기다릴 때까지 기다린다 (M30, D단계).
    멈춤 = 진행 화면이 안 보이고, 상태(날짜 원값·버튼·팝업·답할 메일·화면)가 바뀐 뒤 1초 동안 그대로."""
    args = list(args)
    secs = 60.0
    if "--wait" in args:
        i = args.index("--wait")
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            try:
                secs = float(args[i + 1])
            except ValueError:
                return err("--wait 뒤에는 초(숫자)를 적어요")
    res = _continue_and_wait(secs, remote, ["--force"] if "--force" in args else [])
    if not res.get("ok"):
        if _json_mode:
            out(res)
            return 1
        return err(res.get("error") or "실패")
    before, s, r = res["before"], res["after"], {"label": res.get("label")}
    if _json_mode:
        out(res)
        return 0
    print("계속 (%s) -> %.1f초%s" % (r.get("label") or "계속", res["secs"], ", 시간 초과" if res["timeout"] else ""))
    print("  전: %s" % _state_line(before))
    print("  후: %s" % _state_line(s))
    if s.get("needReply"):
        print("  다음: 답할 메일이 있어요 (act continue로 열고 ui mail, act reply)")
    elif s.get("modal"):
        print("  다음: 팝업이 떠 있어요 (ui text)")
    return 0


def _continue_and_wait(secs, remote, extra=(), action=None):
    """계속(또는 action 명령)을 누르고 멈출 때까지 기다린 결과 dict (출력 없음). _continue_wait와 play가 쓴다 (M32)."""
    code, before = _jcall(["ui", "state"], remote)
    if code != 0 or before.get("error"):
        return {"ok": False, "error": before.get("error") or "상태를 읽지 못했어요"}
    code, r = _jcall(list(action) if action else ["act", "continue"] + list(extra), remote)
    if action and code == 0 and not r.get("label"):
        r["label"] = " / ".join(r.get("text") or []) or r.get("id")
    if code != 0 or r.get("error"):
        return {"ok": False, "error": r.get("error") or "실패", "before": before, "act": r}
    t0, last, stable_since, saw_proc, s, steps = time.time(), None, None, False, before, []
    while time.time() - t0 < secs:
        time.sleep(0.3)
        c, s2 = _jcall(["ui", "state"], remote)
        if c != 0 or s2.get("error"):
            continue
        s = s2
        saw_proc = saw_proc or bool(s.get("processing"))
        k = _state_key(s)
        if k != last:
            steps.append({"t": round(time.time() - t0, 1), "state": _state_line(s)})
            last, stable_since = k, time.time()
        changed = _state_key(s)[:1] != _state_key(before)[:1] or s.get("button") != before.get("button") or \
            s.get("needReply") or s.get("modal") or s.get("title") != before.get("title") or _state_key(s)[6:] != _state_key(before)[6:]
        if changed and not s.get("processing") and time.time() - stable_since >= 1.0:
            break
        if not saw_proc and not s.get("processing") and time.time() - t0 >= 3.0 and time.time() - stable_since >= 3.0:
            break   # M31: 진행 화면 없이 3초 그대로 = 즉시 끝나는 조작(메일 넘기기 등)인데 눈에 띄는 변화가 없음
    else:
        steps.append({"t": round(time.time() - t0, 1), "state": "시간 초과 (%d초)" % secs})
    return {"ok": True, "before": before, "after": s, "secs": round(time.time() - t0, 1), "processing_seen": saw_proc,
            "timeout": time.time() - t0 >= secs, "label": r.get("label"), "steps": steps}


def _ui_mail(args):
    """ui mail: 열린 메일(제목, 보낸 이, 본문, 세부 글, 답 버튼)과 왼쪽 메일 목록 (M31)."""
    r = host.rpc("uimail")
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    m = r["mail"]
    print("■ %s" % (m.get("title") or "(제목 없음)"))
    if m.get("from"):
        print("  보낸 이: %s %s" % (m["from"], m.get("fromJob") or ""))
    if m.get("body"):
        print("  " + m["body"].replace("\n\n", "\n").strip().replace("\n", "\n  "))
    for t in m.get("texts") or []:
        print("  · " + t.replace("\n", " / "))
    if m.get("buttons"):
        print("  버튼: " + ", ".join("%s%s" % (b.get("text") or "?", (" [%s]" % b["id"]) if b.get("id") else "") for b in m["buttons"]))
    flags = []
    if m.get("needReply"):
        flags.append("답 필요")
    if m.get("risky"):
        flags.append("이적·계약 관련 (act reply에 --yes 필요)")
    if flags:
        print("  (" + ", ".join(flags) + ")")
    if r.get("list"):
        print("─ 메일 목록 (%d)" % len(r["list"]))
        for x in r["list"]:
            print("  %s  %s — %s" % (x.get("time") or "", x.get("from") or "", x.get("title") or ""))
    return 0


def _open_reply_mail(remote):
    """'답변 요망'(MDSB) 버튼으로 답할 메일을 연다. 스킨마다 MDSB 개수·위치가 달라서(기존 스킨 2개, 오리지널 1개 등)
    --index를 가정하지 않고, 후보가 여러 개면 화면 아래쪽(목록 줄이 아니라 메일 쪽 도구)부터 시도한다 (M33)."""
    c, r = _jcall(["act", "continue"], remote)   # M37: 답변 요망 상태의 계속 = 답할 메일 열기 (게임 내부 이벤트, 버튼 id 불필요)
    if c == 0:
        return r
    c, r = _jcall(["act", "click", "MDSB"], remote)
    if c == 0:
        return r
    cands = r.get("matches") or []
    for m in sorted(cands, key=lambda x: (x.get("rect") or [0, 0])[1], reverse=True):
        c, r = _jcall(["act", "click", m["addr"]], remote)
        if c == 0:
            return r
    return r


PLAY_CONT_KINDS = (-1, -8, -19)   # ui.continueKind: 진행하기 / 다음 읽기 / 수신함 (코어 CONT_KINDS와 같음, M37)
PLAY_NO = ("기자", "회견", "제안한", "제의", "임대를 원하는")   # 기본 규칙: 우리 선수에 대한 제의·기자회견은 거절, 나머지는 확인


def _play(args, remote=False):
    """play --days N [--steps 400] [--quiet]: 테스트용 자동 진행 (M32). 판단 없는 기본 규칙으로 날짜를 넘긴다.
    답할 메일 -> 열어서 기본 규칙(기자회견·우리 선수 제의는 no, 나머지 yes), 확인 창 -> 예, 면담 -> 첫 답,
    그 밖 -> act continue --wait. 처음 보는 화면(계속 버튼 없음)에서는 멈추고 화면 글을 보여 준다. 모든 조작은 act_log.jsonl에."""
    args = list(args)
    try:
        days = int(_opt(args, "--days", "1"))
        steps = int(_opt(args, "--steps", "400"))
    except ValueError as e:
        return err(str(e))
    quiet = bool(_opt(args, "--quiet", flag=True))
    import datetime

    def say(*a):
        if not quiet and not _json_mode:
            print(*a, flush=True)
    code, s = _jcall(["ui", "state"], remote)
    if code != 0 or s.get("error") or not s.get("date"):
        return err(s.get("error") or "게임 날짜를 읽지 못했어요 (세이브를 불러왔나요?)")
    start = datetime.date.fromisoformat(s["date"])
    goal = start + datetime.timedelta(days=days)
    say("시작 %s %s, 목표 %s" % (s["date"], s.get("clock") or "", goal.isoformat()))
    if not _opt(args, "--manual", flag=True):   # M38: 기본은 휴가 (스킨·메일 종류 무관). 안 되면 아래 단계별 진행으로
        t0 = time.time()
        ok, stop, log, s = _play_holiday(goal, remote, say)
        if ok:
            return _play_report(True, stop, start, goal, s, t0, log, remote)
        say("  휴가로 끝내지 못함 (%s) -> 단계별 진행으로" % stop)
    log, stop, t0, seen, picked, match_steps = [], None, time.time(), {}, None, 0
    last_clk, clk_since, last_resume, instant_tried, registered = None, time.time(), 0.0, None, None
    for i in range(steps):
        code, s = _jcall(["ui", "state"], remote)
        if code != 0 or s.get("error"):
            stop = "상태를 읽지 못함: %s" % s.get("error")
            break
        if s.get("date") and datetime.date.fromisoformat(s["date"]) >= goal and (s.get("buttonId") == "GCNT" or (not s.get("button") and s.get("kind") in PLAY_CONT_KINDS)) and not s.get("modal"):
            stop = "목표 날짜 도착"
            break
        if s.get("modal"):
            c, r = _jcall(["act", "dialog", "yes", "--yes"], remote)
            log.append(("dialog", r.get("question"), c == 0))
            say("  확인 창: %s -> 예%s" % (r.get("question") or "", "" if c == 0 else " 실패: " + str(r.get("error"))))
            if c != 0:
                stop = "확인 창을 처리하지 못함"
                break
            time.sleep(0.8)
            continue
        c, tr = _jcall(["ui", "tree"], remote)
        answ = [n for n in tr.get("nodes") or [] if n.get("id") == "answ"]
        if answ:
            c, r = _jcall(["act", "click", answ[0]["addr"]], remote)
            log.append(("meeting", "/".join(answ[0].get("text") or [])[:40], c == 0))
            say("  면담 답: %s" % "/".join(answ[0].get("text") or [])[:50].replace("\n", " "))
            time.sleep(1.5)
            continue
        idsr = {n.get("id"): n for n in tr.get("nodes") or [] if n.get("id")}
        if "aspb" in idsr and "cspa" in idsr and registered != (s.get("date"), s.get("clock")):   # M33: 대회 선수 등록 화면 -> 자동 선발 + 선수 명단 확정 (확인 창은 위에서)
            registered = (s.get("date"), s.get("clock"))
            _jcall(["act", "click", idsr["aspb"]["addr"]], remote)
            time.sleep(1.0)
            c, r = _jcall(["act", "click", idsr["cspa"]["addr"]], remote)
            log.append(("register", s.get("date"), c == 0))
            say("  선수 등록: 자동 선발 + 확정%s" % ("" if c == 0 else " 실패: " + str(r.get("error"))))
            time.sleep(1.0)
            continue
        if s.get("needReply"):
            _open_reply_mail(remote)
            time.sleep(0.8)
            c, m = _jcall(["ui", "mail"], remote)
            title = (m.get("mail") or {}).get("title") or "?"
            choice = "no" if any(w in title for w in PLAY_NO) else "yes"
            c, r = _jcall(["act", "reply", choice, "--yes", "--all"], remote)
            if c != 0 and r.get("none"):   # 그 종류 버튼이 없으면 반대 종류로 (예: 거절 버튼 없는 메일)
                other = "yes" if choice == "no" else "no"
                c, r = _jcall(["act", "reply", other, "--yes", "--all"], remote)
                choice = other
            log.append(("mail", title, choice, c == 0))
            if len(log) >= 6 and all(x[0] == "mail" and x[1] == title for x in log[-6:]):
                stop = "같은 메일에 6번 답해도 그대로: %s" % title   # M32: 무한 반복 방지 (여러 제의 메일은 줄마다 한 번씩이라 여유를 둠)
                break
            say("  메일: %s -> %s%s" % (title, choice, "" if c == 0 else " 실패: " + str(r.get("error"))))
            if c != 0:
                stop = "메일에 답하지 못함: %s" % title
                break
            time.sleep(0.8)
            continue
        ids0 = {n.get("id"): n for n in tr.get("nodes") or [] if n.get("id")}
        if not s.get("button") and "Mclk" in ids0 and "IMBu" in ids0:   # 실시간 경기 화면: 시계 Mclk, 진행 버튼 IMBu(글 없음) 반복 (M33)
            # IMBu는 경기 화면에서 '일시정지/재개' 토글이다 (사용자 확인). 시계가 멈춰 있을 때만 한 번 눌러 재개하고, 그 뒤는 누르지 않고 기다린다.
            clk = "/".join(ids0["Mclk"].get("text") or [])
            match_steps += 1
            if match_steps > 600:
                stop = "경기가 오래 지나도 안 끝남 (마지막 시계 %s)" % clk
                break
            if clk != last_clk:
                last_clk, clk_since = clk, time.time()
            elif time.time() - clk_since >= 4.0 and time.time() - last_resume >= 8.0:
                c, r = _jcall(["act", "click", ids0["IMBu"]["addr"]], remote)   # 멈춘 시계 = 일시정지 -> 재개 한 번
                last_resume = time.time()
                say("  경기 시계 %s에서 멈춤 -> 재개" % clk)
            elif match_steps % 25 == 1:
                say("  경기 진행 중 %s" % clk)
            time.sleep(1.0)
            continue
        if not s.get("button") and s.get("kind") not in PLAY_CONT_KINDS:   # 버튼 id를 못 찾아도 게임이 계속 가능한 종류라면 진행 (M37)
            stop = "처음 보는 화면 (계속 버튼 없음)"
            break
        if s.get("processing"):   # 아직 진행 중 (이전 계속이 덜 끝남) -> 누르지 않고 기다림
            time.sleep(1.0)
            continue
        sig = (s.get("date"), s.get("clock"), s.get("button"), s.get("item"))   # M32: 같은 상태가 계속 반복되면 멈춤 (선수명단 제출 무한 반복 사고)
        seen[sig] = seen.get(sig, 0) + 1
        if seen[sig] > 8:
            stop = "같은 상태가 8번 넘게 반복됨: %s" % _state_line(s)
            break
        ids = {n.get("id"): n for n in tr.get("nodes") or [] if n.get("id")}
        action = None
        if "askp" in ids and picked != s.get("date"):   # 경기 날 팀 선발: 빠른 선발(부상 선수 빼고 자동) 먼저
            c, r = _jcall(["act", "click", ids["askp"]["addr"]], remote)
            picked = s.get("date")
            log.append(("quickpick", s.get("date"), c == 0))
            say("  경기 날: 빠른 선발%s" % ("" if c == 0 else " 실패: " + str(r.get("error"))))
            time.sleep(1.0)
            continue
        if "INST" in ids:   # 즉석 결과 (경기를 보지 않고 결과만)
            action = ["act", "click", ids["INST"]["addr"]]
        elif "askp" in ids and instant_tried != s.get("date"):   # M33: 즉석 결과 버튼이 없는 스킨 -> 게임 내부 이벤트로 즉석 결과
            instant_tried = s.get("date")
            action = ["act", "instant"]
        r = _continue_and_wait(180, remote, action=action)
        if not r.get("ok"):
            if (r.get("act") or {}).get("busy"):
                time.sleep(1.0)
                continue
            stop = "계속 실패: %s" % r.get("error")
            break
        a = r.get("after") or {}
        if r.get("timeout"):
            stop = "계속 후 180초 동안 멈추지 않음"
            break
        say("  계속(%s) %.1f초 -> %s %s %s" % (r.get("label"), r.get("secs") or 0, a.get("date"), a.get("clock") or "", a.get("button") or ""))
    else:
        stop = "단계 수 한도(%d)" % steps
    code, s = _jcall(["ui", "state"], remote)
    return _play_report(stop == "목표 날짜 도착", stop, start, goal, s, t0, log, remote)


def _play_report(ok, stop, start, goal, s, t0, log, remote):
    res = {"ok": ok, "stop": stop, "start": start.isoformat(), "goal": goal.isoformat(), "now": s,
           "secs": round(time.time() - t0, 1), "log": log}
    if _json_mode:
        out(res)
        return 0 if res["ok"] else 1
    print("%s: %s -> %s (%.0f초)" % (stop, start.isoformat(), s.get("date"), res["secs"]))
    if not res["ok"]:
        print("지금: " + _state_line(s))
        c, t = (control.call(["ui", "text"]) if remote else run_captured(["ui", "text"]))
        print("\n".join(t.splitlines()[:30]))
    return 0 if res["ok"] else 1


def _play_holiday(goal, remote, say, tries=4):
    """휴가로 goal 날짜까지 (M38). 휴가 동안 수석코치가 경기·메일을 처리한다. 휴가가 중간에 끝나면(중요한 일) 확인 창을 닫고 다시 간다.
    돌려줌: (성공, 이유, 기록, 마지막 상태)"""
    import datetime
    log, s = [], {}
    for attempt in range(tries):
        busy_wait = time.time()
        while True:   # 진행 중이면 멈출 때까지 기다림
            c, s = _jcall(["ui", "state"], remote)
            if c == 0 and not s.get("busy") and not s.get("processing"):
                break
            if time.time() - busy_wait > 120:
                return False, "진행이 120초 동안 안 멈춤", log, s
            time.sleep(1.0)
        if s.get("date") and datetime.date.fromisoformat(s["date"]) >= goal:
            return True, "목표 날짜 도착", log, s
        if s.get("modal"):
            c, r = _jcall(["act", "dialog", "yes", "--yes"], remote)
            log.append(("dialog", r.get("question"), c == 0))
            say("  확인 창: %s -> %s" % (r.get("question") or "", "예" if c == 0 else "실패: " + str(r.get("error"))))
            if c != 0:
                return False, "확인 창을 닫지 못함", log, s
            time.sleep(1.0)
            continue
        c, r = _jcall(["act", "holiday", "--until", goal.isoformat()], remote)
        log.append(("holiday", s.get("date"), c == 0))
        if c != 0:
            return False, "휴가 시작 실패: %s" % r.get("error"), log, s
        say("  휴가: %s -> %s" % (s.get("date"), goal.isoformat()))
        days = (goal - datetime.date.fromisoformat(s["date"])).days
        end, started, quiet_since, last_date = time.time() + 120 + 60 * days, False, None, None
        while time.time() < end:
            time.sleep(1.5)
            c, s = _jcall(["ui", "state"], remote)
            if c != 0:
                continue
            if s.get("date") != last_date:
                last_date = s.get("date")
                say("    %s %s" % (s.get("date"), s.get("clock") or ""))
            if s.get("busy") or s.get("kind") == -6:
                started, quiet_since = True, None
                continue
            quiet_since = quiet_since or time.time()
            if (started and time.time() - quiet_since >= 2) or time.time() - quiet_since >= 8:
                break   # 휴가가 끝남 (또는 시작되지 않음)
        else:
            return False, "휴가가 %d초 안에 안 끝남" % (120 + 60 * days), log, s
    return False, "휴가를 %d번 다시 가도 목표에 못 감" % tries, log, s


def cmd_play(args):
    return err("play는 CLI 쪽에서 돌아요: python -X utf8 loader/cli.py play --days 7")


def cmd_act(args):
    """게임 화면 조작 (M28 "아는 손", M29 안전장치). 모든 조작은 화면 스레드(onFrameEnd)에서 돈다.
    act continue                       : 오른쪽 위 버튼 진행 (계속/소셜 피드/수신함/다음 읽기 = 스페이스바). 팝업이 떠 있으면 안 함
    act click <대상> [--index N] [--partial] [--yes]
        대상: 0x주소 | 4글자 id | 화면 글(똑같은 글). 버튼이 여러 개면 누르지 않고 후보를 보여 줌 (--index로 고르기).
        --partial: 글 일부만 맞아도 됨. --yes: 세이브를 바꿀 수 있는 짧은 버튼(제의·계약·수락·해고 …)도 누름.
        팝업이 떠 있으면 팝업 안 버튼만 (--behind: 팝업을 연 버튼으로 닫을 때처럼 밖도). 모든 조작은 ~/m24ga_data/act_log.jsonl에 남는다."""
    args = list(args)
    sub = args.pop(0) if args else ""
    usage = "사용: cli.py act continue\n       cli.py act click <0x주소 | id | 화면 글> [--index N] [--partial] [--yes]"
    usage += "\n       cli.py act reply [ybut | xbut | yes | no | 버튼 글] [--yes]   (열린 메일에 답하기, M31)"
    usage += "\n       cli.py act dialog [yes | no | 버튼 글] [--yes]               (떠 있는 확인 창, M31)"
    usage += "\n       cli.py act holiday [--days N | --until YYYY-MM-DD] [--accept-offers]   (휴가, M38)"
    if sub not in ("continue", "click", "reply", "dialog", "instant", "holiday"):
        return err(usage)
    try:
        idx = _opt(args, "--index", None)
        idx = int(idx) if idx is not None else None
    except ValueError as e:
        return err(str(e))
    partial = bool(_opt(args, "--partial", flag=True))
    confirm = bool(_opt(args, "--yes", flag=True))
    behind = bool(_opt(args, "--behind", flag=True))
    if sub == "click" and not args:
        return err("사용: cli.py act click <0x주소 | id | 화면 글> [--index N] [--partial] [--yes]")
    force = bool(_opt(args, "--force", flag=True))
    opts = {"cmd": sub}
    if sub == "continue" and force:
        opts["force"] = True
    if sub == "continue" and confirm:
        opts["confirm"] = True
    all_ = bool(_opt(args, "--all", flag=True))
    if sub == "reply":
        opts.update({"target": " ".join(args) or "ybut", "confirm": confirm})
        if all_:
            opts["all"] = True
    if sub == "dialog":
        opts.update({"target": " ".join(args) or "yes", "confirm": confirm})
    if sub == "instant":   # M33: 즉석 결과 (스킨 버튼 없이). CLIENT_TACTIC vtable을 RTTI 표에서 찾아 넘긴다
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
        import rtti
        cl = rtti.load()["classes"].get("CLIENT_TACTIC") or {}
        vts = [v["rva"] for v in cl.get("vtables", []) if not v["off"]]
        if not vts:
            return err("CLIENT_TACTIC 클래스를 찾지 못했어요 (rtti 표)")
        opts["vt"] = vts[0]
        if idx is not None:
            opts["index"] = idx
    if sub == "holiday":   # M38: 휴가 (게임 내부 호출, 스킨 무관). 기본: 7일, 모든 제의 거절, 현재 전술
        import datetime
        days, until = _opt(args, "--days", None), _opt(args, "--until", None)
        st = host.rpc("uistate") or {}
        if not st.get("date"):
            return err("게임 날짜를 읽지 못했어요 (세이브를 불러왔나요?)")
        try:
            today = datetime.date.fromisoformat(st["date"])
            target = datetime.date.fromisoformat(until) if until else today + datetime.timedelta(days=int(days or 7))
        except ValueError as e:
            return err(str(e))
        if target <= today:
            return err("복귀 날짜는 오늘(%s) 뒤여야 해요" % today)
        flags = 0x242
        if _opt(args, "--accept-offers", flag=True):
            flags = (flags & ~0x2) | 0x4   # 요구 금액에 맞는 제의는 수락
        opts.update({"date": (target.year << 16) | target.timetuple().tm_yday, "flags": flags})
    if sub == "click":
        opts.update({"target": " ".join(args), "partial": partial, "confirm": confirm})
        if behind:
            opts["behind"] = True
        if idx is not None:
            opts["index"] = idx
    r = host.rpc("uiact", opts)
    _act_log(opts, r)
    if _json_mode:
        out(r or {"error": "실패"})
        return 1 if (not r or r.get("error")) else 0
    if not r or r.get("error"):
        msg = (r or {}).get("error") or "실패"
        for m in (r or {}).get("matches") or []:
            msg += "\n  #%d %s  [%s%s %s]" % (m["index"], m.get("text") or "", m.get("cls") or "", (" " + m["id"]) if m.get("id") else "", m["addr"])
        bl = (r or {}).get("buttons")
        if bl:
            msg += "\n  메일 버튼: " + ", ".join("%s%s" % (b.get("text") or "?", (" [%s]" % b["id"]) if b.get("id") else "") for b in bl)
        return err(msg)
    if sub == "instant":
        print("즉석 결과 실행함 (CLIENT_TACTIC %s%s)" % (r.get("obj"), ", 처리됨" if r.get("handled") else ""))
        return 0
    if sub == "dialog":
        print("팝업 '%s' -> %s" % (r.get("question") or "", " / ".join(r.get("text") or []) or r.get("id") or r["addr"]))
        return 0
    if sub == "reply":
        print("답함: '%s' -> %s" % (r.get("mail") or "", " / ".join(r.get("text") or []) or r.get("id") or r["addr"]))
        return 0
    if sub == "holiday":
        print("휴가 시작: %s까지 (옵션 %s). 진행은 ui state로 보세요" % ((r.get("date") or {}).get("iso"), r.get("flags")))
        return 0
    if sub == "continue":
        print("계속 진행 실행함%s" % (" (%s)" % r["label"] if r.get("label") else ""))
        return 0
    mark = {True: " -> ☑", False: " -> ☐"}.get(r.get("checked"), "")
    txt = ' "%s"' % " / ".join(r["text"]) if r.get("text") else ""
    print("클릭함: %s%s %s%s%s" % (r["cls"], (" " + r["id"]) if r.get("id") else "", r["addr"], txt, mark))
    return 0


def _act_log(opts, r):
    """act 기록 한 줄 (M29): 언제, 무엇을, 결과. AI가 무엇을 눌렀는지 사용자가 나중에 볼 수 있게."""
    try:
        r = r or {}
        row = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "cmd": opts.get("cmd"), "target": opts.get("target"),
               "ok": bool(r.get("ok")), "error": r.get("error"), "cls": r.get("cls"), "id": r.get("id"),
               "text": r.get("text") or r.get("label"), "confirm": opts.get("confirm", False)}
        os.makedirs(modlib.DATA, exist_ok=True)
        with open(os.path.join(modlib.DATA, "act_log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---- 함수 등록부 (M22) ----

def cmd_functions(args):
    """함수 등록부 목록 (게임 없이 됨)."""
    import caps as caplib
    import re
    fr = caplib.functions()["functions"]
    rx = re.compile(args[0], re.I) if args else None
    rows = [(n, f) for n, f in fr.items() if not rx or rx.search(n) or rx.search(f.get("desc", ""))]
    if _json_mode:
        out(dict(rows))
        return 0
    for n, f in rows:
        how = "코어(%s)" % f.get("event") if f.get("owner") == "core" else f.get("hook", "observe")
        print("%-28s fm+%-10s (%s) -> %s  %-9s %s%s" % (n, f["rva"], ", ".join(f.get("args") or []), f.get("ret", "void"), how,
                                                     "" if f.get("verified") else "(미확인) ", f.get("desc", "")))
    print("(%d개, 자세한 표는 docs/FUNCTIONS.md)" % len(rows))
    return 0


def cmd_hooks(args):
    """지금 걸린 끼어들기(모드별 호출 수·오류·걸린 시간)와 함수 서명 확인 결과."""
    r = host.rpc("hooks")
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if _json_mode:
        out(r)
        return 0
    print("서명 확인: " + ", ".join("%s %s" % (n, "ok" if v == "ok" else "X (%s)" % v) for n, v in r["check"].items()))
    if not r["hooks"]:
        print("걸린 끼어들기 없음")
    for n, lst in r["hooks"].items():
        print("%s%s" % (n, "" if n in r["installed"] else " (풀림)"))
        for e in lst:
            print("  %-24s 호출 %d, 오류 %d, 걸린 시간 %dms" % (e["mod"], e["calls"], e["errs"], e["ms"]))
    return 0


def _print_wcall(r):
    print("%s %s (%s), %.1f초, 호출 %d번" % ("지켜보는 중" if r["active"] else "끝남(%s)" % r["why"], r["name"], r["addr"], r["secs"], r["total"]))
    if not r["total"]:
        return
    fn = _func_namer()
    print("  부른 곳: " + "; ".join("%s ×%d" % (fn(c), k) for c, k in r["callers"][:5]))
    for i, a in enumerate(r["args"]):
        print("  인자 %d (%s): %s" % (i, ["rcx", "rdx", "r8", "r9"][i], ", ".join("%s ×%d" % (k, v) for k, v in a)))
    print("  반환: " + ", ".join("%s ×%d" % (k, v) for k, v in r["ret"]))
    for s in r["samples"][:6]:
        print("    예: (%s) -> %s  [%s]" % (", ".join(s["args"]), s.get("ret"), s["caller"]))


def cmd_watch_call(args):
    """게임 함수 하나를 잠깐 지켜보며 인자 정체·반환값·부른 곳을 모은다 (함수를 등록하기 전에 인자 뜻 알아내기)."""
    args = list(args)
    if args and args[0] in ("show", "stop"):
        r = host.rpc("wcallreport" if args[0] == "show" else "wcallstop")
        if not r or r.get("error"):
            return err((r or {}).get("error") or "실패")
        out(r) if _json_mode else _print_wcall(r)
        return 0
    try:
        secs = int(_opt(args, "--secs", "30"))
        mx = int(_opt(args, "--max", "300"))
        wait = int(_opt(args, "--wait", "0"))
    except ValueError as e:
        return err(str(e))
    if not args:
        return err("사용: cli.py watch-call <함수 이름 | fm+0x주소> [--secs 30] [--max 300] [--wait 초]\n       cli.py watch-call show | stop\n"
                   "  예: watch-call player.updateAskingPrice --secs 120 --wait 120   (그동안 게임 진행)")
    r = host.rpc("wcallstart", args[0], secs, mx)
    if not r or r.get("error"):
        return err((r or {}).get("error") or "실패")
    if wait:
        end = time.time() + wait
        while time.time() < end:
            time.sleep(2)
            r = host.rpc("wcallreport")
            if not r or r.get("error") or not r.get("active"):
                break
    out(r) if _json_mode else _print_wcall(r)
    return 0


def cmd_classes(args):
    """fm.exe RTTI 클래스 찾기 (tools/rtti.py, 게임 없이 됨)."""
    if not args:
        return err("사용: cli.py classes <정규식>  (예: classes 'TRANSFER.*VALUE')")
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import rtti  # noqa: E402
    import re
    data = rtti.load()
    rx = re.compile(args[0], re.I)
    hits = {n: c for n, c in data["classes"].items() if rx.search(n)}
    if _json_mode:
        out(hits)
        return 0
    for n in sorted(hits):
        c = hits[n]
        vts = ",".join(v["rva"] + ("@+0x%x" % v["off"] if v["off"] else "") for v in c["vtables"]) or "-"
        bases = []
        for b in c["bases"] or []:
            if b not in bases:
                bases.append(b)
        print("%s  vt=%s  기반: %s" % (n, vts, " > ".join(bases) or "-"))
    print("(%d개)" % len(hits))
    return 0


COMMANDS = {
    "status": cmd_status,
    "mods": cmd_mods,
    "mod": cmd_mod,
    "start": cmd_start,
    "stop": cmd_stop,
    "run": cmd_run,
    "enable": cmd_enable,
    "disable": cmd_disable,
    "install": cmd_install,
    "uninstall": cmd_uninstall,
    "reload": cmd_reload,
    "call": cmd_call,
    "grant": cmd_grant,
    "rescan": cmd_rescan,
    "settings": cmd_settings,
    "set": cmd_set,
    "log": cmd_log,
    "log-clear": cmd_log_clear,
    "report": cmd_report,
    "build-report": cmd_build_report,
    "writes": cmd_writes,
    "undo": cmd_undo,
    "safe": cmd_safe,
    "safe-leave": cmd_safe_leave,
    "validate": cmd_validate,
    "open-mods": cmd_open_mods,
    "open-data": cmd_open_data,
    "version": cmd_version,
    "watch": cmd_watch,
    "explore": cmd_explore,
    "engine": cmd_engine,
    "classes": cmd_classes,
    "get": cmd_get,
    "fields": cmd_fields,
    "props": cmd_props,
    "prop-find": cmd_prop_find,
    "prop-info": cmd_prop_info,
    "actions": cmd_actions,
    "find-field": cmd_find_field,
    "watch-write": cmd_watch_write,
    "functions": cmd_functions,
    "hooks": cmd_hooks,
    "watch-call": cmd_watch_call,
    "find-global": cmd_find_global,
    "find-objects": cmd_find_objects,
    "find-refs": cmd_find_refs,
    "find-bytes": cmd_find_bytes,
    "ui": cmd_ui,
    "act": cmd_act,
    "find-text": cmd_find_text,
    "find-const": cmd_find_const,
    "play": cmd_play,
}

# host.py의 기존 CLI 옵션도 지원 (호환성)
ALIASES = {
    "--list": "mods",
    "--check": "run --check",
    "--now": "run --now",
    "--once": "run --once",
}


def usage():
    print(__doc__)
    return 0


# 실행 중인 로더로 보내지 않고 이 프로세스에서 하는 명령 (로더 상태와 상관없음, 또는 오래 도는 명령)
LOCAL_ONLY = {"validate", "version", "run", "watch", "open-mods", "open-data", "classes", "fields", "functions"}
# 실행 중인 로더가 없으면 이 프로세스 안에서만 의미가 있는 명령 (명령이 끝나면 로더도 끝난다)
NEEDS_LOADER = {"start", "stop", "reload", "log", "log-clear", "undo", "safe-leave"}
_run_lock = threading.Lock()


def run_captured(argv):
    """통로(control.py)가 부른다: 이 프로세스(앱 또는 cli run)에서 명령을 실행하고 출력 글을 돌려준다."""
    with _run_lock:
        buf = io.StringIO()
        out_, err_ = _ThreadOnly(buf, sys.stdout), _ThreadOnly(buf, sys.stderr)
        with contextlib.redirect_stdout(out_), contextlib.redirect_stderr(err_):
            try:
                code = main(list(argv), local=True)
            except SystemExit as e:  # noqa: PERF203
                code = int(e.code or 0)
        return code, buf.getvalue()


class _ThreadOnly:
    """명령을 실행하는 스레드의 출력만 모은다. 그사이 다른 스레드(로더, 모드 Python)가 찍는 글은 원래 출력으로 보낸다
    (안 그러면 --json 결과 앞에 다른 글이 섞여 AI가 JSON을 못 읽는다)."""

    def __init__(self, buf, orig):
        self.buf, self.orig, self.owner = buf, orig, threading.get_ident()

    def write(self, s):
        if threading.get_ident() == self.owner:
            return self.buf.write(s)
        if self.orig is not None:
            try:
                return self.orig.write(s)
            except (OSError, ValueError):
                pass
        return len(s)

    def flush(self):
        if self.orig is not None and threading.get_ident() != self.owner:
            try:
                self.orig.flush()
            except (OSError, ValueError):
                pass


def main(argv=None, local=False):
    """local=True: 통로에서 불림 (다시 보내지 않고 이 프로세스에서 실행, 콘솔 설정을 건드리지 않음)."""
    global _json_mode
    argv = argv if argv is not None else sys.argv[1:]
    argv = list(argv)

    # 전역 옵션 추출 (부를 때마다 새로 정한다: 통로에서는 한 프로세스가 여러 명령을 받는다)
    _json_mode = "--json" in argv
    if _json_mode:
        argv.remove("--json")
    if "--help" in argv or "-h" in argv:
        return usage()
    if not argv:
        return usage()

    cmd = argv[0]

    # 별명 처리
    if cmd in ALIASES:
        parts = ALIASES[cmd].split()
        cmd = parts[0]
        argv = parts + argv[1:]
    else:
        argv = argv[1:]

    fn = COMMANDS.get(cmd)
    if not fn:
        return err("모르는 명령: %s\n\n도움말: python -X utf8 loader/cli.py --help" % cmd)
    if not local and cmd in ("watch-write", "watch-call") and "--wait" in argv and control.call(["version"]) is not None:
        return _watch_wait_client(argv, cmd)
    # M30: 기다리는 반복은 CLI 쪽에서 (앱 안에서 기다리면 조종 통로가 막혀서 그동안 act가 줄을 선다)
    if not local and cmd == "ui" and argv[:1] == ["state"] and "--watch" in argv:
        return _ui_state(argv[1:], remote=control.call(["version"]) is not None)
    if not local and cmd == "play":
        return _play(argv, remote=control.call(["version"]) is not None)
    if not local and cmd == "act" and argv[:1] == ["continue"] and "--wait" in argv:
        return _continue_wait(argv[1:], remote=control.call(["version"]) is not None)
    if not local and cmd not in LOCAL_ONLY:
        r = control.call([cmd] + argv + (["--json"] if _json_mode else []))
        if r is not None:                   # 앱이나 cli run이 켜져 있다: 그 로더에서 실행한 결과
            sys.stdout.write(r[1])
            return r[0]
        if cmd in NEEDS_LOADER:
            print("참고: 실행 중인 M24GA(앱 또는 'cli.py run')가 없어서 이 프로세스 안에서만 실행해요. "
                  "이 명령이 끝나면 로더도 끝나요.", file=sys.stderr)
    if not local:
        host._console["on"] = not _json_mode   # JSON 모드가 아니면 host.py의 콘솔 로그를 켠다
    return fn(argv)


if __name__ == "__main__":
    sys.exit(main())
