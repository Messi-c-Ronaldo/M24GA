# AGENTS.md: M24GA 저장소를 다루는 AI에게

M24GA는 FM24(Epic 빌드)에 모드를 붙이는 오픈소스(GPL-3.0-or-later) 로더예요. 이 파일은 **이 저장소 자체(로더)를 고치거나 이 저장소 안에서 모드를 만드는** AI를 위한 안내예요. 모드만 만든다면 [docs/AI_GUIDE.md](docs/AI_GUIDE.md)를 읽으세요.

## 먼저 읽을 것
- 모드를 만들 때: [docs/AI_GUIDE.md](docs/AI_GUIDE.md) → [docs/MODDING.md](docs/MODDING.md) → [examples/hello](examples/hello)
- 로더를 고칠 때: [README.md](README.md), `core/core.js`(게임 쪽 코어, 주석이 가장 정확해요), `loader/host.py`(게임 찾기·빌드 확인·스크립트 올리기), `loader/mods.py`(모드 찾기·설정·Python 실행), `loader/app.py`와 `loader/ui/`(앱 화면)

## 구성
```
core/core.js         게임 안 코어 (Frida). 훅은 코어만 걸고 이벤트로 모드에 나눠 줘요
loader/              Python 호스트 (host.py, mods.py, bundle.py, validate.py, caps.py, app.py, ui/, cli.py + control.py = CLI와 조종 통로)
builds/*.json        게임 빌드별 주소 서명 (안 맞으면 로더 전체가 멈춰요)
mods/ai-social-feed  포함된 모드 (동작 기준이 되는 실제 사례)
examples/hello       모드 예제 (설정 종류, 메시지, 모드창)
tools/m24.py         new / validate / pack
docs/                MODDING.md, AI_GUIDE.md, mod.schema.json, types/ (.d.ts, .pyi)
```

## 지켜야 할 것
- **게임 주소는 `builds/*.json`과 `core/core.js`에만** 둬요. 모드에 새 주소가 필요하면 모드의 `builds/`에 서명을 두고, 안 맞으면 그 모드만 꺼져요.
- 게임 객체를 읽는 코드는 객체를 먼저 확인하고(`lookup`, `checkObj`) `try/catch`로 감싸요. 확인 안 한 포인터로 가상 함수를 부르면 게임이 튕겨요.
- 동작이 같아야 하는 이전·리팩터링은 **검증 전후를 비교**해요 (소셜피드는 요청의 캐시 키·본문·ctx를 이전 세션과 비교하는 방법을 써요). 원본을 줄 범위로 잘라 옮기고 연결부만 새로 쓰세요.
- **API 키, 개인 경로, 추출한 게임 데이터(CSV, 덤프)는 커밋하지 마세요.** 개인 경로가 든 파일은 저장소 밖에 둬요.
- 코어를 바꾸면 `loader/mods.py`의 `CORE_VERSION`을 올리고(새 기능은 마이너), `docs/types/m24ga.d.ts`·`m24ga.pyi`와 `docs/MODDING.md`를 같이 고쳐요. 모드의 `core` 조건과 맞아야 해요.
- **코어에 모드용 기능(함수, 이벤트, 전역 이름)을 더하면 `core/capabilities.json`에 먼저 등록**하고(이름, 위험 등급, `uses`, `detect`, 예제), `python -X utf8 tools/m24.py caps`로 `docs/CAPABILITIES.md`와 스키마를 다시 만들어요. `tests/test_caps.py`가 d.ts와 등록부가 맞는지 확인해요.
- **새 게임 칸·함수를 등록하는 전체 절차는 `docs/EXTENDING.md`**예요 (칸 찾기 → 등록 → 확인 → 쓰기까지 열기, 함수 찾기 → 인자 확인 → 등록, 끝낼 때 할 일). 아래는 요약이에요.
- **게임 칸(필드)은 전용 함수를 만들지 말고 `core/fields.json`에 한 줄 등록**해요 (종류, `off`/`via`/`alt`, 형식, 뜻, `source`=근거 로그, `verified`). 쓰기(`write: safe`)는 쓰기 실기 확인(쓰기 → 게임에서 확인 → 되돌리기)을 한 칸만. 고친 뒤 `tools/m24.py caps`로 `docs/FIELDS.md`를 다시 만들고, 게임에서 `cli.py get player:<uid> <필드>`로 값을 확인해요. `tests/test_fields.py`가 형식을 검사해요. 칸 찾기는 `cli.py explore`·`classes` (M19), 객체 종류는 RTTI 클래스 이름으로 적어요.
- **게임 함수는 `core/functions.json`에 등록**해요 (rva = 함수 시작, `sig` = 시작+0x10의 16바이트(`tools/rtti.py`의 `PE`로 파일에서 읽기), args/argNames/ret, hook observe|modify, verified, source). modify는 인자 뜻을 확인한 함수만. `tests/test_functions.py`가 실제 fm.exe와 서명을 맞춰 봐요. 찾기: `cli.py watch-write`(칸에 쓰는 함수) → `watch-call`(인자·호출자) → REA 디컴파일.
- `loader/host.py`·`cli.py`를 고치면 **앱(pythonw)을 다시 켜야** CLI에 반영돼요 (CLI 명령이 앱 프로세스 안에서 돌아요). `core/*.js`·`fields.json`만 고쳤으면 `cli.py stop` → `cli.py start --now --wait 90`.
- 새 mod.json 항목이나 설정 종류를 추가하면 `loader/validate.py`, `docs/mod.schema.json`, `docs/MODDING.md`를 같이 고쳐요.
- **스킨·언어에 기대지 않기 (M35~M39):** 모드 로더는 모두가 써요. 기능은 게임 내부(메모리 객체, 등록부 함수·이벤트)로 만들고, 위젯 id·화면 글에 기대지 마세요. 위젯 id가 게임 코드에 있는지는 `cli.py find-const <4글자>`로 확인해요 (0곳 = 스킨 파일만 아는 이름, 예: `GCNT`·`MDSB`). 화면이 열려 있어야 되는 기능은 `core/capabilities.json`에 `"screen"`을 적어요. 글로 판단해야 하면 모르는 언어에서 **안전한 쪽으로 실패**하게 해요 (`uiLang()`이 'unknown'이면 위험으로). `tests/test_skin.py`가 확인해요.
- 한국어 주석과 한국어 사용자 문구를 써요. 사용자에게 보이는 글은 쉬운 말로 써요.

## 확인하는 법
- 기능 등록부 문서가 최신인지: `python -X utf8 tools/m24.py caps --check`
- 구조 검사: `python -X utf8 tools/m24.py validate mods/ai-social-feed` (오류 0이어야 해요. 경고는 이유를 읽고 판단해요)
- 묶음 JS 문법: `python -X utf8 loader/bundle.py out.js` 후 `node --check out.js`
- 모드 목록: `python -X utf8 loader/host.py --list`, 게임에 붙어 빌드만 확인: `--check`
- 타입 정의가 맞는지: `tsc --noEmit --allowJs --checkJs <mod.js>` (mod.js에 `/// <reference path=".../m24ga.d.ts" />`)
- 게임에 붙여 보는 실기 검증은 사용자가 게임을 켜 둔 상태에서만 해요. 앱은 `pythonw -X utf8 loader\app.py [--on]`.
- **AI 에이전트는 GUI 대신 CLI를 쓰세요**: `python -X utf8 loader/cli.py <명령> --json`. GUI 조작(pywebview 클릭)이 필요 없어요.
  - 앱이나 `cli.py run`이 켜져 있으면 CLI 명령은 **그 로더로 전달돼요** (`loader/control.py`, `~/m24ga_data/control.json`). 꺼져 있으면 CLI 프로세스 안에서만 돌고 명령이 끝나면 로더도 끝나요.
  - 로더 시작: `cli.py start --now --wait 60 --json` (60초 안에 게임에 붙으면 결과를 돌려 줘요)
  - 모드 켜기/끄기: `cli.py enable <id> --json` / `cli.py disable <id> --json`
  - 상태 확인: `cli.py status --json` (JSON으로 모든 정보)
  - 모드 핫 리로드: `cli.py reload <id> --json` (mod.js를 고친 뒤 바로 반영)
  - 모드 보고서: `cli.py report <id>` (오류 진단용 전체 보고서)
  - 상태 감시: `cli.py watch --until hooked --json` (게임에 붙을 때까지 JSON 스트림)
  - 전체 명령: `cli.py --help`
- 화면 조작이 필요하면 앱 창을 `pythonw` 프로세스로 지정해요 (창 제목 "M24GA"는 편집기 창에도 들어 있어요).

## 쓰는 도구의 함정
- 셸 heredoc 안의 파이썬 코드에 `"\n"`이 있으면 줄바꿈으로 풀려 문법 오류가 나요. `\n`이나 정규식이 든 코드는 파일 편집 도구로 쓰거나 파일로 만들어 실행하세요.
- 앱(pythonw)을 켠 직후에는 **조종 통로가 열릴 때까지(`~/m24ga_data/control.json` 시각이 바뀔 때까지) 기다린 뒤** CLI 명령을 보내요. 그 전에 `start`를 보내면 로더가 CLI 프로세스 안에서 따로 올라갔다 내려가요 (M43: 이 때문에 게임이 튕겼고, 코어 0.22.1에서 게이트 칸 되돌리기를 고쳤지만 로더 두 개가 겹치는 일 자체를 피하세요).
- PowerShell `Set-Content -Encoding UTF8`은 BOM을 붙여요 (로더는 BOM을 읽지만, 다른 도구는 못 읽을 수 있어요).
