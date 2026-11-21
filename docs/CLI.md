# M24GA CLI 참고서

**한국어** | [English](en/CLI.md)

GUI(pywebview) 없이 M24GA의 모든 기능을 명령줄로 쓸 수 있어요. AI 에이전트가 모드를 개발·테스트할 때 GUI 조작 없이 바로 제어할 수 있어요.

코어 버전 **0.44.0** 기준이에요. 실행 중인 앱의 로더를 조종하는 통로는 `loader/control.py`예요.

---

## 실행

```bash
# 직접
python -X utf8 loader/cli.py <명령> [옵션]

# bat 파일 (M24GA 폴더에서)
m24cli <명령> [옵션]
```

## 실행 중인 M24GA와 연결 (조종 통로)

CLI는 한 번 실행하고 끝나는 별도 프로세스예요. 그래서 **앱(`start_m24ga.bat`)이나 `m24cli run`이 켜져 있으면 CLI는 명령을 그 로더로 보내서 실행**해요. 게임 연결, 모드 Python, 모드 로그, 쓰기 기록이 모두 그 로더에 있으니까요.

- 앱이나 `run`은 켜질 때 이 PC 안에서만 열리는 통로(127.0.0.1, 무작위 포트)를 열고, 포트와 무작위 토큰을 `~/m24ga_data/control.json`에 적어요. 닫히면 지워요.
- CLI는 그 파일이 있고 통로가 답하면 그쪽에서 실행한 결과를 그대로 출력해요. 통로가 실행하는 것은 이 CLI의 명령뿐이에요.
- **실행 중인 로더가 없으면** CLI 프로세스 안에서 실행해요. 이때 `start`, `stop`, `reload`, `log`, `undo`, `safe-leave`는 **그 명령이 끝나면 로더도 같이 끝나서** 의미가 없어요 (CLI가 참고 문구를 보여 줘요). 계속 켜 둘 로더는 앱이나 `m24cli run`(다른 터미널)으로 켜세요.
- 로더로 보내지 않고 항상 그 자리에서 하는 명령: `validate`, `version`, `run`, `watch`(대신 로더의 `status`를 물어봐요), `open-mods`, `open-data`.
- `--json` 결과에는 그 명령의 출력만 들어가요 (그사이 로더나 모드 Python이 찍은 글은 섞이지 않아요).

**AI 에이전트 추천 순서:** 사용자가 앱을 켜 두게 하고 → `m24cli status --json`으로 연결 확인 → `start --now --wait 60 --json`(꺼져 있으면) → `reload`/`log`/`report`로 개발. 화면 클릭(컴퓨터 조작) 없이 끝나서 토큰이 훨씬 적게 들어요.

## 전체 옵션

| 옵션 | 설명 |
|---|---|
| `--json` | 모든 명령에 붙일 수 있어요. JSON으로 출력돼서 프로그램이 파싱하기 좋아요 |
| `--help`, `-h` | 도움말 |

---

## 명령

### 상태

#### `status`
로더 상태: 실행 여부, 게임 연결, 빌드, 모드 요약.
```bash
m24cli status --json
```
JSON 출력 예:
```json
{
  "phase": "hooked",
  "running": true,
  "build": "fm24-epic-2026-10-24",
  "pid": 12345,
  "game": {"date": "2035-04-25", "save": {"id": 5117219, "nonce": 1}},
  "mods": [{"id": "ai-social-feed", "state": "running", ...}],
  "errors": []
}
```

#### `mods`
찾은 모드 목록과 상태. 모드마다 `state`가 있어요:
- `running`: 게임에 올라가 있음
- `ready`: 준비됨 (게임 대기)
- `off`: 꺼짐
- `build`: 이 게임 빌드와 안 맞음
- `problem`: 켤 수 없음 (mod.json 문제 등)
- `error`: Python 오류
- `auto_off`: 오류가 반복돼서 자동으로 꺼짐
- `safe`: 안전 모드라 올리지 않음
- `perm`: 권한 허용 필요

```bash
m24cli mods --json
```

#### `mod <id>`
모드 하나의 상세 정보 (설정 포함).
```bash
m24cli mod ai-social-feed --json
```

---

### 로더 제어

#### `start [--now] [--wait <초>]`
로더를 시작해요. 백그라운드 스레드로 게임을 기다렸다가 자동으로 연결해요.

| 옵션 | 설명 |
|---|---|
| `--now` | 게임이 이미 세이브 안이면 바로 데이터 표를 만들어요 |
| `--wait <초>` | 게임에 연결될 때까지 기다려요. AI에게 아주 유용해요 |

```bash
# AI 에이전트: 시작하고 60초 안에 연결되면 결과 받기
m24cli start --now --wait 60 --json
```

#### `stop`
로더 끄기. 스크립트를 내리고 모드 Python을 멈춰요.
```bash
m24cli stop --json
```

#### `run [--now] [--once] [--check]`
포그라운드에서 실행 (Ctrl+C로 끔). `host.py`의 콘솔 모드와 같아요.

| 옵션 | 설명 |
|---|---|
| `--now` | 바로 데이터 표 만들기 |
| `--once` | 게임을 한 번 끄면 로더도 끝남 |
| `--check` | 빌드만 확인하고 끝남 |

---

### 모드 관리

#### `enable <id>` / `disable <id>`
모드를 켜거나 꺼요. 로더가 실행 중이면 핫 리로드가 돼요.
```bash
m24cli enable ai-social-feed --json
m24cli disable ai-social-feed --json
```

#### `install <경로>`
`.24mod` 파일을 설치해요 (검사 → 복사 → 다시 훑기).
```bash
m24cli install "C:\path\to\my-mod.24mod" --json
```

#### `uninstall <id>`
모드를 삭제해요 (휴지통 폴더로 옮김). 설정과 데이터는 남아요.
```bash
m24cli uninstall my-mod --json
```

#### `call <id> <함수> [인자...]`

모드창이 `m24.call('<함수>', ...)`로 부르는 것과 같이 모드 Python의 `ui_<함수>(인자...)`를 불러요. 인자는 JSON으로 읽히면 JSON(숫자, 목록 등), 아니면 글자예요. 모드창 없이 모드를 시험할 때 써요.

```
m24cli call dynamic-potential state --json
m24cli call dynamic-potential rows up "" 20 --json
```

#### `reload <id>`
모드의 게임 쪽 JS를 지금 파일로 다시 올려요. 코어와 데이터 표는 그대로 둬요 (핫 리로드).
```bash
# mod.js를 고친 뒤
m24cli reload my-mod --json
```

#### `grant <id>`
모드가 필요한 위험 기능(pc, raw, hook, write)을 허용하고 켜요.
```bash
m24cli grant my-mod --json
```

#### `rescan`
mods 폴더를 다시 훑어요. 로더가 켜져 있으면 바뀐 모드를 따라 Python과 스크립트도 맞춰요.
```bash
m24cli rescan --json
```

---

### 설정

#### `settings <id>`
모드 설정을 보여 줘요. JSON 모드에서는 `specs`(설정 항목 정의)와 `values`(현재 값)가 나와요.
```bash
m24cli settings ai-social-feed --json
```

#### `set <id> <key> <값>`
모드 설정을 바꿔요. 값은 자동으로 타입 변환돼요 (true/false → bool, 숫자 → int/float, 나머지 → 문자열).
```bash
m24cli set ai-social-feed api.model gpt-4o --json
m24cli set ai-social-feed api.key sk-xxxxx --json
m24cli set my-mod count 10 --json
m24cli set my-mod enabled true --json
```

---

### 로그와 보고

#### `log <id> [--since <번호>]`
모드의 최근 로그. `--since`를 주면 그 번호 이후의 것만 나와요.
```bash
m24cli log ai-social-feed --json
m24cli log ai-social-feed --since 42 --json
```

#### `log-clear <id>`
모드 로그를 지워요.

#### `report <id>`
**AI에게 줄 보고서**: 모드 상태, 자동으로 꺼진 이유, validate 결과, 최근 로그를 한 번에 모아요. 문제가 생겼을 때 이 출력을 AI에게 붙여 넣으면 돼요.
```bash
m24cli report ai-social-feed
```

#### `build-report`
**게임 빌드 진단 보고서**: 로더가 모르는 게임 빌드(예: Steam판)를 만났을 때 어디가 다른지 알려 줘요. 파일 크기, SHA-256, PE 빌드 시각, 버전 글자, 서명·vtable 칸별 기대값/실제값을 담고 개인 경로는 지워요. 게임에 한 번 붙은 뒤에 만들 수 있고, 빌드가 안 맞으면 로더가 `~/m24ga_data/build_report.txt`에 자동으로 저장해요. 앱 홈의 **빌드 진단 보고서 복사** 버튼도 같은 글이에요.
(코어 0.38.0) '함수 등록부' 절: 등록 함수의 서명이 이 빌드에서 맞는지, 안 맞으면 클래스 vtable 칸(`vf`)이나 서명 검색으로 다시 찾았는지 보여 줘요. 다시 찾은 함수는 로더가 그 주소로 올려요.
```bash
m24cli build-report
```

#### `writes <id>`
모드의 게임 값 쓰기 기록.

#### `undo <id>`
지금 세이브에서 모드가 바꾼 값을 되돌려요.

---

### 안전 모드

#### `safe`
안전 모드 상태 확인. 직전 게임이 비정상 종료됐으면 안전 모드가 켜져 있어요.

#### `safe-leave`
안전 모드를 끝내고 켜 둔 모드를 올려요.

---

### 게임 조사 (코어 0.9.0)

#### `explore <대상> [시작 칸] [크기]`
실행 중인 게임의 객체를 8바이트씩 펼쳐 보여요. 포인터는 따라가서 **클래스 이름**(RTTI)을 붙이고, 게임 글자 칸은 글로, 게임 날짜 칸은 날짜로 보여 줘요. 칸 번호와 크기는 16진수예요 (기본 0, 0x200, 최대 0x4000). 읽기만 해요.

| 대상 | 뜻 |
|---|---|
| `0x12345678` | 주소 |
| `player:<uid>` | 선수 객체 (`db::ACTUAL_PLAYER`) |
| `person:<uid>` | 그 선수의 사람 데이터 객체 (`personOf`, 선수 +0x278) |
| `me` | 내 감독 (`db::HUMAN_NON_PLAYER`) |
| `myclub` | 내 클럽 (`db::CLUB`) |
| 뒤에 `/+0x130` | 그 칸의 포인터를 따라가요 (여러 번 가능: `player:123/+0x130/+0x30`) |

```bash
m24cli explore player:2002122126 0x100 0x80
#   +0x130  00000000de960c00  -> db::TEAM
#   +0x150  07f37cb107f300ba  i32 ...  날짜 2035-07-05, 2035-06-26
m24cli explore "player:2002122126/+0x130" 0 0x40 --json
```

#### `get <대상> <필드> [필드...]` (코어 0.10.0)
필드 등록부([`FIELDS.md`](FIELDS.md))의 칸을 이름으로 읽어요. 대상은 `explore`와 같아요. 필드 이름 끝이 `.`이면 그 이름으로 시작하는 필드를 전부 읽어요.
```bash
m24cli get player:2002122126 player.name player.ca player.pa player.askingPrice
m24cli get player:2002122126 player.season.league.
m24cli get myclub club.name
```

#### `fields [정규식]` (코어 0.10.0)
필드 등록부 목록 (이름·형식·쓰기 가능 여부·뜻). 게임이 꺼져 있어도 돼요.

`explore`는 등록된 칸에 `[player.ca, player.pa(+2)]`처럼 필드 이름을 붙여 보여 줘요 (`(+2)`는 그 8바이트 칸 안에서 2바이트 뒤).

선수 능력치 54개는 `get player:<uid> player.attr.` (코어 0.39.0 이후 등록부, M60).

#### `props <대상> [정규식] [--empty]` (코어 0.36.0)
게임 속성 코드 값 전부 (등록부 `core/properties.json`, 문서 [PROPERTIES.md](PROPERTIES.md)). 대상: `me` · `myteam` · `myclub` · `myjob`(내 감독 계약) · 사람 참조 `p123`/`s45` · `team:<번호>` · `comp:<번호>` · `player:<uid>` · `0x주소`.
```bash
python -X utf8 loader/cli.py props myclub "^(Ccba|Ctfc|Cwwb)$"   # 잔고·이적 예산·주급 예산
python -X utf8 loader/cli.py props player:2002117436 "^P(ced|dob|cwg)$"
```
`~/m24ga_data/prop_names.tsv`(코드, 영어, 게임 언어, 표시 형식, 분류)가 있으면 이름도 같이 보여요 (예: `크로스 (Crossing) [능력치 · attribute_label]`). 이 표는 게임 글이라 저장소에 없어요. **각자 `python -X utf8 tools/prop_names.py --pylib <zstandard 폴더>`로 자기 게임 파일에서 만들어요** (1,655개, 첫 실행 2~3분, 언어는 `--lang`). 등록부 2,297개 중 약 900개가 이름을 가져요 (나머지는 게임 화면에 이름이 없는 내부 코드).

#### `prop-find <대상> <값>` (코어 0.36.0)
화면에 보이는 값(숫자·글·날짜 `2038-06-30`)이 어느 속성 코드에 있는지 찾아요 (묶음·목록 안까지). 뜻을 모르는 코드를 확인할 때.

#### `actions [정규식]` (M62)
게임 액션(명령) 198개 목록: 4글자 id, 클래스, 보호 구역 여부, 확인 함수가 읽는 문맥 키. 게임이 꺼져 있어도 돼요. 실행 이벤트도 보여요 (M65). 대상마다 쓸 수 있는 명령 읽기·실행은 모드 API `api.actionsFor`·`api.action`(코어 0.41.0)으로 해요 ([ACTIONS.md](ACTIONS.md)).

#### `cand` / `verify` / `promote` (M78, 반자동 API 탐색)
쓰기 후보를 모으고, 시험 세이브에서 자동으로 검증하고, 등록부에 올려요. 절차는 [`EXTENDING.md`](EXTENDING.md) D절.
```bash
m24cli cand testsave add                                  # 지금 세이브를 시험 세이브로 (검증 쓰기는 여기서만)
m24cli cand import ~/m24ga_data/api_scan.json             # tools/api_scan.py 결과
m24cli cand add prop contract Cabo                        # 손으로
m24cli verify prop:contract:Cabo contract:p45806          # roundtrip
m24cli verify --all "^prop:contract:" contract:p45806     # 여러 개
m24cli verify prop:contract:Cabo contract:p45806 --level day
m24cli verify prop:contract:Cabo contract:p45806 --level save   # -> 저장·다시 불러오기 -> verify resume
m24cli promote prop:contract:Cabo --tier tested
```
`vsnap <대상>`(정체성 + 스칼라 속성 전부)과 `vset <대상> prop|field …`(등록부 검사 없는 읽기·쓰기, 쓰기는 시험 세이브만)는 verify가 쓰는 낮은 단계 명령이에요.

#### `prop-info [정규식] [--writable]` (코어 0.36.0, 쓰기 표시 0.42.0)
속성 등록부 목록 (코드·값 종류·답하는 객체 종류·확인된 뜻). 게임이 꺼져 있어도 돼요.
코드마다 쓰기 단계를 붙여요: `[쓰기 safe 범위]`·`[쓰기 tested]`·`[쓰기 금지]`. `--writable`이면 `api.setProp`으로 쓸 수 있는 코드만 보여요 (쓰기는 모드에서만: 기능 `write.prop`).

화면 값과 코드 맞추기 팁: `ui text`는 위젯마다 4글자 코드를 보여 주는데, 숫자 위젯의 코드는 대개 그 값을 묻는 **속성 코드**예요 (예: 선수 프로필 `ATTRIBUTE_LABEL Pcro` = 크로스).

#### `find-field <대상>=<값> [<대상>=<값> ...]` (M21)
알려진 값으로 칸을 찾아요. 대상 객체(맨 앞부터 0x800바이트)와 그 안의 포인터가 가리키는 곳(각 0x400바이트)을 훑어요. **대상을 여러 개 주면 모두에서 같은 위치·형식인 칸만** 남기고 `fields.json`에 넣을 줄 초안을 보여 줘요. 읽기만 해요.

| 값 | 뜻 |
|---|---|
| `89100000` | 그 값 (`--tol 0.01`이면 ±1%) |
| `100..200` | 범위 |
| `1480억` | 게임 화면의 돈 (원 ÷ 1664.7 = 내부 단위, 기본 오차 2%: 화면 몸값은 반올림돼 있어요) |

옵션: `--type i32,f32` (기본: 큰 값은 i32·u32·f32·f64, 작은 값은 i8~u16도), `--size 0x1000`, `--shallow`(포인터 안 따라감), `--name player.askingPrice`(초안 이름).
```bash
m24cli find-field player:2002122126=1480억 player:19302146=245억 --name player.askingPrice
#   모든 대상에서 같은 칸: +0x1d0 i32 (89100000, 14852187)
#   "player.askingPrice": {"kind": "player", "off": "0x1d0", "type": "i32", ...}
```

#### `find-bytes <패턴> [--max 40] [--secs 20] [--align N] [--ctx 16] [--owner] [--module]` (코어 0.32.0, E09)

바이트 패턴을 게임 힙(쓰기 가능한 구역)에서 찾아요. 찾은 곳마다 앞뒤 바이트를 보여 주고, `--owner`면 앞쪽 0x800 안의 RTTI 객체(주인)를, `--module`이면 fm.exe 전역 구역도 훑어요.

```
m24cli find-bytes 0b ?? 0f              # 16진수, ?? = 아무 바이트
m24cli find-bytes --u8 0 11 15 19 4 8  # 값 나열 (--u8 --i8 --u16 --i16 --u32 --i32 --u64 --i64 --f32 --f64)
m24cli find-bytes --i32 11 ? 15 --align 4   # ? = 그 크기만큼 아무 값
```

전술 스타일 표(`styles.xml`)를 메모리에서 찾을 때 썼어요 (u8 세 개씩).

#### `find-const <4글자>` (M37)

실행 중인 `fm.exe` 모듈(코드 포함)에서 4글자 상수(위젯 id, 이벤트 코드)가 쓰이는 곳을 찾아요. **게임 코드가 그 이름을 직접 쓰는지** 확인할 때 써요: 0곳이면 스킨 파일만 아는 이름이라 스킨이 바꿀 수 있어요 (`GCNT`, `MDSB`, `ctnu`는 0곳. `INST`는 2곳). 디스크의 `fm.exe`는 일부가 암호화돼 있어 파일 검색보다 이쪽이 정확해요. `watch-call` 결과도 4글자처럼 보이는 정수 인자를 `'CONT'`처럼 글자로 보여 줘요.

#### `watch-write <대상> <칸> [크기]` (M21)
칸 하나(1·2·4·8바이트)에 **하드웨어 쓰기 감시**를 걸어 그 칸에 쓰는 게임 코드를 찾아요. 잡힐 때마다 코드 위치(`fm+0x…`와 그 함수의 시작), 호출 경로, 그때 레지스터가 가리키던 객체의 클래스(RTTI), 쓴 값을 모아요. `--max`번(기본 30) 잡거나 `--secs`초(기본 60, 최대 600)가 지나면 **스스로 풀려요.** 감시는 한 번에 하나.

- `--wait 초`: 그동안 기다렸다가 결과를 보여 줘요 (CLI 쪽에서 기다려서, 그동안 다른 창에서 `watch-write show`·`stop`을 쓸 수 있어요). 안 주면 바로 돌아오고 `watch-write show`로 봐요. `watch-write stop`은 지금 풀기.
- `--rw`: 읽기도 잡아요 (아주 자주 잡힐 수 있어요). **자주 읽히는 칸(엔진 표 등)에 쓰지 마세요**: 여러 스레드에서 순식간에 `--max`가 차요. 코어 0.29.1 전에는 이때 늦게 온 감시 예외로 게임이 튕겼어요 (E02). 0.29.1부터는 늦은 예외가 3초 동안 끊길 때까지 처리기를 내리지 않고 삼켜요 (`late`에 그 수). 결과의 `excSet`이 false가 된 뒤에 로더를 끄세요.
- 대상에 `fm+0x631d5bc`처럼 **게임 전역 칸**도 돼요 (`explore`·`get`도 같아요).
- **주의:** CPU 디버그 레지스터를 써요. 걸 때 있던 게임 스레드에만 걸려요 (그 뒤 생긴 스레드는 못 잡아요). 게임이 튕길 가능성이 있으니 **게임을 저장한 뒤** 쓰세요.
```bash
m24cli watch-write fm+0x631d5bc 0 4 --secs 120 --wait 120     # 그동안 게임에서 하루 진행 -> 날짜를 쓰는 코드
m24cli watch-write player:2002122126 0x1d0 4 --secs 300 --wait 300
```
찾은 함수는 REA(`fm.exe` 열기 → 주소로 디컴파일)나 `tools/fmdis.py`로 이어서 봐요.

#### `engine dump|apply|restore` (코어 0.30.0, DynamicME E03)
매치엔진 표(선발 가중치·물리·모멘텀·평점)를 **게임을 켠 채로, 재시작 없이** 읽고 바꿔요. 게임은 경기·선발 때 메모리 표를 그대로 읽어서 다음 선발·경기부터 반영돼요. 게임이 진행 중이면 쓰지 않아요 (경기 전 조정).
```bash
m24cli engine dump physics --out physics.json     # weights|physics|momentum|ratings|styles, 메모리 그대로 (읽기만)
m24cli engine apply "D:\받은것\(엔진이름)" --dry   # 엔진 팩(simatch 폴더) 미리보기: 무엇을 어디에 쓰는지, 경고
m24cli engine apply "D:\받은것\(엔진이름)"         # 게임 메모리에 바로
m24cli engine restore                              # 게임 설치 폴더의 simatch.fmf 원본 값으로
```
- 이미 있는 칸에만 써요 (할당 없음). 팩이 최신 버전 항목을 지웠으면 게임이 쓰는 칸에 팩의 유효 항목을 넣거나(가중치·물리), 지운 항목을 게임이 고르지 않게 막아요(평점).
- 게임이 모르는 키·구역 이름, 0.25초 단위가 아닌 지연, 소수 회전값은 경고로 알려요. 모양이 다른 표(QME 두 개)는 아직 못 넣어요.
- 변환·계획은 `pylib/m24engine.py`. 메모리는 세이브에 남지 않아요 (게임을 다시 켜면 원본).

#### `find-global <클래스 정규식> [최대]` (M24)
fm.exe의 전역 칸 중에서 그 클래스의 객체를 가리키는 것을 찾아요. 게임에 하나만 있는 관리자 객체(싱글턴)의 위치를 알아낼 때 써요. 1MB씩 읽고 8초 예산에서 멈춰요 (결과에 표시).
```bash
m24cli find-global "^(GAME_UI|GAME_SCREEN_MANAGER|SCREEN_CLIENT_MANAGER)$"
#   fm+0x63659c0 -> 0x1d2a82c0  GAME_UI
#   fm+0x63635b8 -> 0x45972c0   SCREEN_CLIENT_MANAGER
```

#### `find-objects <클래스 정규식> [--max 40] [--secs 20]` (M24)
그 클래스의 객체를 게임 메모리에서 찾아요 (객체 맨 앞의 vtable 값을 `Memory.scanSync`로 검색, 2.7GB를 5~10초). 정규식에 맞는 vtable이 24개를 넘으면 좁히라고 해요. 찾은 주소는 `explore`로 펼쳐요.
```bash
m24cli find-objects '^BUTTON$' --max 12
m24cli explore 0xbcb1f8d0 0 0x400
```

#### `find-refs <대상> [--max 40] [--secs 20] [--back 0x800]` (M25)
그 주소를 **가리키는 칸**을 힙과 fm.exe 전역에서 찾아요 (거꾸로 따라가기: 이 객체를 누가 들고 있나). 칸마다 앞쪽 `--back`바이트 안의 가장 가까운 RTTI 객체를 찾아 "클래스 +칸"으로 보여 줘요. 대상 이름은 `explore`와 같아요.
```bash
m24cli find-refs 0x1d5de7c0          # GAME_SCREEN_CLIENT를 들고 있는 것
#   0x15579f18  SCREEN_CLIENT_MANAGER::INTERNAL_DATA +0x18 ...   (화면 목록)
#   0x365ad28   sitoolkit::WIDGET +0x48 ...                       (위젯마다 자기 화면)
```

#### `find-text <화면 글> [--max 6] [--secs 40]` (M25)
화면에 보이는 글(UTF-8)을 메모리에서 찾고, 그 글을 가리키는 칸과 그 칸을 가리키는 칸(문자열 핸들)을 따라 **주인 객체**까지 올라가요. 게임 문자열은 `핸들 → 포인터 → {u32 길이, UTF-8}`이에요. 지워진 위젯의 흔적도 걸리니 부모가 있는지(+0x10) 확인하세요. 서식이 섞인 글(큰 뉴스 제목)은 안 잡힐 수 있어요.

#### `ui text` / `ui tree` (M25, AI 플레이 "보는 눈")
**지금 게임 화면을 글로** 읽어요. 스크린샷 없이 AI가 화면을 알 수 있게 하는 명령이에요. 읽기만 해요 (100~500ms).
- `ui text`: 글이 있는 **보이는** 위젯만, 화면 순서대로. 줄마다 `글  [클래스 id 주소 @가운데x,y]`이고, 스크롤해야 보이는 것은 `화면 밖`이 붙어요. 체크박스는 앞에 `☑`/`☐`, 팝업·대화 상자 안의 위젯은 `팝업`이 붙고, 팝업이 떠 있으면 마지막 줄에 `팝업 떠 있음`이 나와요 (M27).
- `ui tree`: 보이는 위젯 트리 전체 (클래스, id, 자식 수, 플래그, 위치·크기, 글). `--all`이면 숨은 것도 (`숨음`).
- `--json`: 노드마다 `checked`(체크박스), `modal`(팝업 안), 결과에 `modal`(팝업이 떠 있나).
- 옵션: `--root 0x주소`(그 위젯 아래만), `--depth 40`, `--max 3000`, `--scan 0x400`(조사용: 위젯 몸 안의 모든 글 칸), `--json`.
```bash
m24cli ui text
#   수신함  [TEXT sect 0xc501a790 @319,33]
#   35/7/2  [TEXT dtam 0xc501b410 @...]
#   알-이티하드, 비니시우스 주니오르에 대해 제의  [TEXT titl 0xffbfb720 @...]
#   바르셀로나  [TEAM_BUTTON Ttea 0x10b121800 @1684,591]
#   114  [LEAGUE_POINTS_TEXT LOpo 0xf0eaf930 @1849,591]
```
어떻게 읽는지 (M25): `fm+0x63635b8`(SCREEN_CLIENT_MANAGER) → `+0x68` → `+0x18` 화면 목록 → `GAME_SCREEN_CLIENT` → `+0x58` 뿌리 컨테이너 → 자식 배열(`+0x100`/`+0x108`). 위젯 `+0x5c` id 4글자, `+0x60` x·y·너비·높이(실수, 게임 창 픽셀), `+0x78` 플래그(0x2 = 보임, 부모가 숨으면 자식도 숨음; 체크박스는 0x10 = 체크됨). 팝업은 뿌리 아래 `modl` 컨테이너 → `MODAL_SHEET` 가지에 붙어요. 글은 위젯 안의 `MULTI_LINE_STRING`(또는 그것을 물려받은 `CLICKABLE_TEXT`) `+0x98` 줄 목록이에요. 아이콘·그림만 있는 위젯과, 데이터에서 그때그때 그리는 일부 위젯(최근 결과의 팀 이름 등)은 글이 안 나와요.

알아 둘 것 (M27, 선수단·전술·팝업 대조):
- 긴 목록은 **보이는 행만 위젯으로 있어요.** 스크롤하면 기존 행 위젯이 자리를 옮기고 새 행이 생겨요. 목록 전체를 보려면 스크롤하며 여러 번 읽으세요.
- 화면을 연 **직후**에는 배치가 덜 끝나 위치가 어긋나거나 글이 빠질 수 있어요. 잠깐 기다리거나 두 번 읽어 같은지 보세요.
- 표는 칸 위젯의 id가 열 제목(`COLUMN_HEADING`)의 id와 같아요 (예: 이름 칸과 "이름" 제목이 둘 다 `Pnms`). 같은 y끼리 묶으면 행이 돼요.

#### `ui state [--watch 초]` (M30, AI 플레이 "기다리기")
게임 진행 상태 한 줄: `2035-07-02 월 10:30  버튼:진행하기 [진행 중] [팝업] [답할 메일]  화면:수신함`. 날짜는 전역 `fm+0x631d5bc`(상위 16비트 연도, 하위 9비트 연중 일수, 그 위 비트가 시각 — 진행 중에 0x200씩 오름), 버튼은 오른쪽 위 `GCNT`(계속 계열) 또는 `MDSB`(답변 요망), 진행 중은 게임의 `CONTINUE_MANAGER`(전역 `fm+0x6364ea0`) `+0xc0` 값으로 판정해요 (스킨 무관, 코어 0.12.1. 진행 화면 `GAME_PROCESSING_PANEL_CONTAINER`가 보여도 진행 중). `--watch 초`는 바뀔 때마다 한 줄 (CLI 쪽에서 0.25초마다). `--json`이면 `raw`(날짜 원값)까지.

#### `play --days N [--manual] [--steps 400] [--quiet] [--json]` (M32, 테스트용 자동 진행)
**모드를 시험할 때 게임을 N일 진행**하는 명령이에요. 판단 없는 기본 규칙으로 돌아요 (테스트 세이브용).
- **기본 = 휴가 (M38, 스킨·메일 종류 무관):** `act holiday --until 목표날짜`로 휴가를 가요. 휴가 동안 수석코치가 경기·메일·행정을 처리하고 목표 날짜에 돌아와요. 휴가가 중간에 끝나면(확인 창 등) 창을 `예`로 닫고 다시 가요 (4번까지). 휴가로 못 끝내면 아래 단계별 진행으로 넘어가요. 실기: 8/19 → 8/24 134초, 리그 경기 포함.
- `--manual`: 휴가를 쓰지 않고 아래 단계별 진행만 (화면 규칙, 직접 메일에 답하고 경기 날 처리. 메일·면담 처리를 시험할 때).
- 답할 메일 → 열어서(`MDSB`) 제목에 기자·회견·제안한·제의·임대를 원하는이 있으면 `no`, 아니면 `yes` (`act reply --yes --all`, 그 종류 버튼이 없으면 반대 종류). 여러 제의 메일은 아직 안 처리한 줄만 차례로.
- 확인 창 → `예`. 선수 면담 → 첫 번째 답. 면담·회의의 다음 버튼(`nxbt`/`endB`)은 계속처럼.
- **경기 날**: 팀 선발 화면이면 `빠른 선발`[`askp`](부상 선수 빼고 자동) → `즉석 결과`. 스킨에 `즉석 결과`[`INST`] 버튼이 있으면 그걸, **없으면 `act instant`**(게임 내부 이벤트, 스킨 무관). 결과 창은 `act dialog`가 닫기(`clos`)로 닫아요. 경기를 직접 보게 되면(실시간 경기 화면) 시계가 멈췄을 때만 `IMBu`(일시정지/재개 토글)를 한 번 눌러요.
- **진행 중 판정 (스킨 무관):** 코어가 `CONTINUE_MANAGER`에서 읽어요 (`ui state --json`의 `busy`, 상태가 바뀔 때마다 느는 `seq`). `act continue`도 진행 중이면 누르지 않아요 (누르면 일시정지라서).
- 진행 중에는 누르지 않고 기다려요. 멈춤 조건: 목표 날짜 도착(성공, 종료 코드 0) / **처음 보는 화면**(계속 버튼 없음) / 같은 상태 8번 넘게 반복 / 같은 메일에 6번 / 단계 수 한도. 멈추면 지금 상태와 화면 글을 보여 줘요.
- 기다리는 반복은 CLI 쪽에서 돌아요. 모든 조작은 `act_log.jsonl`에.
```bash
m24cli play --days 3
#   경기 날: 빠른 선발
#   계속(즉석 결과) 1.7초 -> 2035-07-18 수 12:00 선수명단 제출하기
#   ...
#   목표 날짜 도착: 2035-07-18 -> 2035-07-21 (154초)
```

#### 언어 (M39)
- 위험 버튼 보호(`--yes`)와 이적·계약 메일 판단은 한국어·영어 단어로 해요. 다른 언어로 게임을 하면 단어를 못 알아보니, 코어가 화면 글로 언어를 짐작해서(`ui state --json`의 `lang`: ko / en / unknown) **모르는 언어면 짧은 행동 버튼과 모든 메일 답을 위험으로 봐요** (`--yes`가 있어야 눌러요). `play`는 원래 `--yes`로 답해서 그대로 돼요.

#### `act holiday [--days N | --until YYYY-MM-DD] [--accept-offers]` (M38, 휴가 — 스킨 무관)
- 휴가를 가요 (기본 7일). 화면을 쓰지 않고 휴가 창(`GO_ON_HOLIDAY_DIALOG`)의 `휴가 떠나기`가 부르는 함수(등록부 `ui.holidayStart`, fm+0x7a19a50)를 화면 스레드에서 직접 불러요. 게임은 서버에 `'GOHL'` 메시지를 보내고 휴가를 시작해요.
- 옵션: 창의 기본값과 같은 **모든 제의 거절 + 현재 전술 사용 + 날짜에 복귀** (비트 `0x242`). `--accept-offers`는 요구 금액에 맞는 제의만 수락(`0x4`). 감독직 지원 안 함.
- 휴가 중에는 `ui state`의 `kind`가 `-6`, `busy`가 true예요. 이때 `act continue`는 하지 않아요 (계속 버튼이 휴가 취소라서).
- 진행 중이거나 팝업이 떠 있으면 하지 않아요.

#### `act instant [--index N]` (M33, 즉석 결과 — 스킨 무관)
경기 날 **팀 선발 화면에서** 경기를 보지 않고 결과만 내요. 기본 스킨처럼 `즉석 결과` 버튼이 없어도 돼요.
- 원리: 스킨의 `즉석 결과`(id `INST`) 버튼은 결국 `CLIENT_TACTIC`(경기 전 전술 객체)의 이벤트 처리기(+0x38 부분 vtable +0x28 = 등록부 `match.clientTacticEvent`, fm+0x223200)에 `'INST'` 이벤트를 보내요. 이 처리기가 즉석 결과 함수(fm+0x277b10, 이 경로에서만 불림)를 불러요. `act instant`는 메모리에서 `CLIENT_TACTIC`을 찾아 같은 이벤트를 화면 스레드에서 보내요 (처리기 주소가 등록부 서명과 맞을 때만).
- `CLIENT_TACTIC`은 **경기 전 팀 선발 화면에 있을 때만** 있어요 (실시간 경기·하프타임에는 0개). 없으면 `none`으로 실패해요. 검색에 5~10초.
- 실기 (M33, 오리지널 스킨): 7/24 마르세유 친선 경기 → 12:00에서 13:45로 바로, 결과 창 "1 - 2" (득점자·평점).

#### `ui mail` / `act reply [ybut|xbut|yes|no|버튼 글] [--yes]` (M31, 메일 읽고 답하기)
- `ui mail`: 수신함에 열린 메일을 구조로 — 제목(`nwhd`), 보낸 이(`snob`/`sjob`), 본문(`etxt`), 세부 글(금액·조건 …), 메일 안 버튼(`ybut` 확인류, `xbut` 거절·취소류, `업무` 위임 메뉴, 링크), **답 필요** 여부, **이적·계약 관련** 여부, 왼쪽 메일 목록(시각·보낸 이·제목). 목록 위 도구 버튼은 빼요.
- `act reply`: **열린 메일 안의 버튼만** 눌러요 (기본 `ybut`). 메일 제목·본문에 이적·계약·제의·임대·영입·판매·방출·해고·입찰·협상(`core.js` `MAIL_DANGER`)이 있으면 `--yes`가 필요해요. 버튼 글 위험 판정(`ACT_DANGER`) 대신 메일 내용으로 판단해요.
- 답 버튼 종류(`kind`)는 id(`ybut`/`xbut`) 또는 글로 정해요: `yes` = 확인·수락·제의 수락·참석, `no` = 거절·취소·제의 거절. 이적 제의 메일은 `제의 수락`[`set `] / `요구 사항 제안`[`sgtm`] / `제의 거절`[`disc`]이라 `act reply yes|no`가 편해요.
- 답할 메일 처리 순서: `ui state`에 `[답할 메일]` → `act continue`(답변 요망 상태에서는 답할 메일을 열어요, M37) → `ui mail` → `act reply yes|no [--yes]` → (확인 창이 뜨면) `act dialog yes|no`.
- `act dialog [yes|no|버튼 글] [--yes]`: 떠 있는 **팝업(확인 창)**의 예/아니요. 질문(`ques`)도 돌려줘요. 예: "슈테판 히츠스페르거에 대한 제의를 거절하겠습니까?" → `예`[`yes `] / `아니요`[`no  `] (옵션 라디오 버튼은 `act click`).
- 선수 면담(일대일 대화) 같은 화면: 질문 `qusl`, 답 버튼 `answ`(여러 개, 위에 `gptl` 어조: 승낙·약속·설득·주장·위협), 반응 `ReaT`(우려함 → 고무됨 …). 답은 `act click <answ 주소>`, 끝나면 오른쪽 위 `nxbt`("요약" → "미팅 떠나기")를 `act continue`로.
- 아직 안 되는 것: 왼쪽 목록에서 **특정 메일을 골라 열기** (줄 `NEWS_ITEM_LIST_WIDGET`는 버튼이 아니라 클릭 경로를 아직 못 찾음). 안 읽은 메일은 `act continue`("다음 읽기")로 차례로 열려요.
```bash
m24cli ui mail
#   ■ Vinci, AC 밀란과의 계약에 합의
#     보낸 이: 요나스 볼트 (풋볼 디렉터)
#     ... 버튼: 추가 금액, 업무, 확인 [ybut], 연기, 취소 [xbut] ...
#     (답 필요, 이적·계약 관련 (act reply에 --yes 필요))
m24cli act reply ybut --yes
```

#### `act continue` / `act click <대상>` (M28, AI 플레이 "아는 손")
게임 화면을 **직접 조작**해요. 마우스 좌표를 찍지 않고 게임 내부의 버튼 동작을 **화면 스레드(`onFrameEnd`, `fm+0x1049430`)**에서 바로 실행해서 창이 가려져 있거나 해상도가 달라도 똑같이 동작해요.
- `act continue`: 오른쪽 위 버튼(`GCNT`: 계속/소셜 피드/수신함/다음 읽기 = 스페이스바)을 눌러 진행해요. 그 버튼이 없는 화면에서는 등록부 함수 `ui.continueGlobal`(전역 `CONT` 이벤트, **서명이 맞을 때만**)을 불러요.
  - **스킨 무관 (M37, 코어 0.13.0):** 버튼 위젯을 누르지 않고 게임의 `CONTINUE_MANAGER`(전역 `fm+0x6364ea0`)에 `'CONT'` 이벤트를 보내요 (`ui.continueHandler` = 게임의 `handle_continue_game_action`). 게임이 지금 종류에 따라 알아서 해요: 진행 / 다음 읽기 / 수신함 / **답할 메일 열기**(답변 요망). 버튼 id `GCNT`/`MDSB`는 스킨 파일이 정한 이름이라(게임 코드에 없음) 글 표시에만 써요. id를 바꾼 스킨을 흉내 낸 시험에서 이틀 자동 진행 확인.
  - 종류는 `ui state --json`의 `kind`/`kindName` (`ui.continueKind`): `-1` continue(진행하기·소셜 피드·주요 일정 등), `-8` nextUnread(다음 읽기), `-19` inbox(수신함), `-14` needReply(답변 요망), `-3`/`-4` processing.
  - **안 하는 경우:** 팝업이 떠 있을 때, 게임이 진행 중일 때(`busy`), **계속 버튼이 없는 화면**(면담 질문 중, 경기 … `noButton`. 그래도 하려면 `--force`). 단계형 화면(면담 `nxbt`, 경기 전 `IMBu`)에서는 그 다음 버튼을 눌러요.
- `act continue --wait [초]` (M30, 기본 60초): 계속을 누른 뒤 **게임이 다시 입력을 기다릴 때까지** 기다려요. 멈춤 = 진행 화면이 안 보이고, 상태(날짜·시각, 오른쪽 위 버튼, 팝업, 답할 메일, 화면 제목)가 바뀐 뒤 1초 동안 그대로. 결과는 전/후 상태와 다음에 할 일 (답할 메일 → `act click MDSB`, 팝업 → `ui text`). `--json`이면 거친 단계(`steps`)와 진행 화면을 봤는지도. 기다리는 반복은 CLI 쪽에서 돌아요 (앱 통로를 붙잡지 않음).
  - 실기 (M30): `진행하기` 10:30 → 진행 중 14초 → 12:30 `다음 읽기`. `다음 읽기` → 1.6초 → `답변 요망`.
- `act click <대상> [--index N] [--partial] [--yes] [--behind]`: 보이는 버튼 위젯을 찾아 클릭해요.
  - 대상: `0x주소` | 4글자 `id`(예: `TeSq`, `GCNT`, `MDSB`, `FiBn`, `anLB`) | 화면에 보이는 글(예: `선수단`, `전술`, `조건`, `분석`).
  - 글 위젯 주소를 주면 그 위젯을 품은 `BUTTON`(자신 또는 조상)을 눌러요. **자식 쪽으로는 찾지 않아요** (버튼이 아니고 버튼 안에도 없으면 실패).
  - 모든 `BUTTON`과 하위 클래스(`CHECK_BOX`, `RADIO_BUTTON`, `POPUP_BUTTON`, `sitoolkit::TOGGLE_BUTTON`, `sitoolkit::WIDGET_POPUP_BUTTON`, `SIDEBAR_LABEL`, `ICON_BUTTON` 등)가 공통으로 물려받는 가상 클릭 핸들러 `vtable[+0x140](widget, event)`를 불러요.
  - **안전장치 (M29):**
    - 글은 **똑같이 맞아야** 해요. 일부만 맞는 버튼은 후보만 보여 주고 누르지 않아요 → `--partial`.
    - 맞는 버튼이 **여러 개면 누르지 않고** 후보 목록을 보여 줘요 → `--index N`으로 고르기.
    - **팝업이 떠 있으면 팝업 안 버튼만** 눌러요. 팝업을 연 버튼으로 다시 닫을 때처럼 밖을 눌러야 하면 `--behind`.
    - 세이브를 바꿀 수 있는 **짧은 버튼 글**(15글자 이하에 제의·계약·수락·거절·해고·방출·판매·임대·서명·입찰 … 이 들어감, `core.js`의 `ACT_DANGER`)은 `--yes`가 있어야 눌러요. 긴 글(뉴스 제목)은 열어 보기라 제외.
    - 자기와 **부모가 모두 보이는** 버튼만 눌러요.
- 모든 `act`는 `~/m24ga_data/act_log.jsonl`에 한 줄씩 남아요 (시각, 명령, 대상, 성공/실패, 누른 버튼 글, `--yes` 여부). AI가 무엇을 눌렀는지 나중에 볼 수 있어요.
- `--json`이면 실패해도 후보(`matches`)·`needConfirm`·`needReply`가 담긴 결과를 줘요 (종료 코드 1).
- **주의:** 게임을 진행하거나 상태를 바꾸는 조작을 하기 전에는 **게임을 먼저 저장**하세요.
```bash
m24cli act click 선수단
#   클릭함: SIDEBAR_LABEL TeSq 0x10ae27f10 "선수단"
m24cli act click FiBn
#   클릭함: sitoolkit::WIDGET_POPUP_BUTTON FiBn 0x117efb160 "조건"
m24cli act click anLB
#   클릭함: CHECK_BOX anLB 0xe5c21560 "분석" -> ☑
m24cli act continue
#   계속 진행 실행함 (버튼: 소셜 피드)
m24cli act click 수신함
#   오류: '수신함' 버튼이 2개예요. --index로 하나를 고르세요 (누르지 않았어요)
#     #0 수신함  [MENUBAR_ICON_BUTTON Pibx 0xe3bd6c20]
#     #1 수신함  [SIDEBAR_LABEL Pibx 0x10e390110]
m24cli act continue        # 답할 메일이 있을 때
#   계속 진행 실행함 (답변 요망)   <- 답할 메일을 열어요 (M37부터 거부하지 않음)
```

#### `functions [정규식]` (코어 0.11.0)
함수 등록부 목록 (위치, 인자 → 반환, 끼어들기 observe/modify/코어 전용). 게임이 꺼져 있어도 돼요. 자세한 표는 [`FUNCTIONS.md`](FUNCTIONS.md).

#### `hooks` (코어 0.11.0)
지금 걸린 끼어들기(함수별 모드, 호출 수, 오류, 걸린 시간)와 등록부 함수의 **서명 확인** 결과 (이 빌드와 다르면 그 함수는 걸리지 않아요).

#### `watch-call <함수 이름 | fm+0x주소>` (M22)
함수 하나를 잠깐 지켜보며 **앞 4개 인자의 정체**(RTTI 클래스·정수·주소), 반환값, 부른 곳을 모아요. 인자 뜻을 모르는 함수를 등록하기 전에 써요. `--max`번(300) 또는 `--secs`초(30, 최대 600) 뒤 스스로 풀려요. `--wait`는 CLI 쪽에서 기다려요, `show`/`stop`. 디버그 레지스터를 쓰지 않아요 (코어가 평소 쓰는 Interceptor). 주소를 줄 때는 **함수 시작**이어야 해요 (`watch-write` 결과의 "함수 fm+0x…").
```bash
m24cli watch-call player.updateAskingPrice --secs 300 --wait 300   # 그동안 게임 진행
#   호출 2번, 부른 곳 fm+0x372e8db, 인자 0 (rcx): SHORTLIST_MANAGER ×2 ...
```

#### `classes <정규식>`
fm.exe의 클래스 이름(1만여 개)에서 찾아요. vtable 주소(RVA)와 물려받은 클래스도 보여 줘요. **게임이 꺼져 있어도 돼요** (처음 한 번 `tools/rtti.py`가 표를 만들어 `~/m24ga_data/rtti/`에 저장, 6초쯤).
```bash
m24cli classes "TRANSFER_VALUE|ASKING_PRICE"
```

### 기타

#### `validate <경로>`
모드 검사 (`tools/m24.py validate`와 같아요).
```bash
m24cli validate mods/my-mod --json
```

#### `watch [--interval <초>] [--until <단계>]`
상태를 주기적으로 JSON 한 줄씩 출력해요. AI가 폴링하지 않아도 돼요.

| 옵션 | 설명 |
|---|---|
| `--interval <초>` | 출력 간격 (기본 5초) |
| `--until <단계>` | 이 단계에 도달하면 멈춤 (`hooked`, `error`, `unsupported` 등) |

```bash
# 게임에 연결될 때까지 감시
m24cli watch --until hooked
```

출력 예 (한 줄씩):
```json
{"time": "16:30:05", "phase": "waiting", "running": true, "build": null, "game": {}, "mods_loaded": []}
{"time": "16:30:10", "phase": "attaching", "running": true, "build": null, "game": {}, "mods_loaded": []}
{"time": "16:30:35", "phase": "hooked", "running": true, "build": "fm24-epic-2026-10-24", "game": {"date": "2035-04-25"}, "mods_loaded": ["ai-social-feed"]}
```

#### `version`
코어 버전.

#### `open-mods` / `open-data <id>`
탐색기에서 폴더를 열어요. `--json`이면 경로만 출력해요.

---

## AI 에이전트 워크플로

### 모드 개발 사이클

```bash
# 1. 뼈대 만들기
python -X utf8 tools/m24.py new my-mod --python --ui

# 2. 코드 작성 (AI가 파일을 편집)

# 3. 검사
python -X utf8 loader/cli.py validate mods/my-mod --json

# 4. 로더 시작 & 게임 연결 대기
python -X utf8 loader/cli.py start --now --wait 60 --json

# 5. 코드 수정 후 핫 리로드
python -X utf8 loader/cli.py reload my-mod --json

# 6. 로그 확인
python -X utf8 loader/cli.py log my-mod --json

# 7. 문제가 있으면 보고서
python -X utf8 loader/cli.py report my-mod
```

### 설정 변경

```bash
python -X utf8 loader/cli.py settings ai-social-feed --json
python -X utf8 loader/cli.py set ai-social-feed api.key sk-xxx --json
```

### 상태 감시

```bash
# 게임에 붙을 때까지 기다리기 (Ctrl+C로 중단)
python -X utf8 loader/cli.py watch --until hooked
```

---

## GUI(`app.py`)와의 차이

CLI는 `app.py`의 `Api` 클래스와 같은 `host.py`/`mods.py` 함수를 불러요 (앱이 켜져 있으면 위의 통로로 앱 안에서). **기능 차이는 두 가지**뿐이에요:

1. **파일 선택 창** — GUI에서는 대화상자로 `.24mod`를 고르지만 CLI에서는 경로를 직접 줘요 (`install <경로>`)
2. **모드창** — GUI에서만 보이는 iframe 안의 모드 UI는 CLI에서 렌더링하지 않아요

그 외에는 같아요. CLI만 쓸 때는 pywebview가 없어도 돼요 (frida는 필요해요).
