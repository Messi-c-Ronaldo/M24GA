# M24GA 넓히는 법: 새 게임 칸과 함수를 등록하기

모드가 쓸 수 있는 게임 값은 [`FIELDS.md`](FIELDS.md), 끼어들 수 있는 게임 함수는 [`FUNCTIONS.md`](FUNCTIONS.md)에 있는 것뿐이에요. 원하는 값이나 함수가 없으면 **코어에 전용 함수를 덧붙이지 말고 등록부(`core/fields.json`, `core/functions.json`)에 한 줄 더하세요.** 이 문서는 그 절차예요. 아래 명령은 모두 실제로 쓴 것이에요 (예시는 선수의 요구 금액을 찾은 과정).

준비: 게임을 켜고 세이브를 불러온 뒤 `python -X utf8 loader/cli.py start --now --wait 90`. 명령은 `m24cli`로 줄여 쓸 수 있어요 ([`CLI.md`](CLI.md)).

> **안전:** 읽기 도구(`explore`, `get`, `find-field`, `classes`, `watch-call`)는 게임을 바꾸지 않아요. **`watch-write`만 CPU 디버그 레지스터를 써서 게임이 튕길 수 있으니, 쓰기 전에 게임을 저장하세요.** 게임 값을 직접 쓰는 일(`api.setField`)은 칸을 확인하고 등록한 뒤에만 해요.

## A. 새 칸(필드) 등록하기

### 1. 어떤 객체에 있는 값인지 정하기

화면에서 원하는 값(예: 선수 화면의 "이적 시 요구 금액")이 보이는 대상을 둬요. 대상 이름은 `player:<UID>`, `person:<UID>`, `me`(사람 감독), `myclub`, `0x주소`, `fm+0x주소`(게임 전역)이고 뒤에 `/+0x130`을 붙이면 그 칸의 포인터를 따라가요.

```bash
m24cli explore player:2002122126 0x100 0x80    # 객체를 8바이트씩 펼치기. 포인터에는 클래스 이름이 붙어요
m24cli classes "TRANSFER|CONTRACT"             # 게임의 클래스 이름 찾기 (게임 없이 됨)
m24cli find-global "^GAME_UI$"                  # 하나뿐인 관리자 객체(싱글턴)가 있는 전역 칸
m24cli find-objects '^BUTTON$' --max 5           # 그 클래스의 객체들 (메모리 검색)
m24cli find-refs 0x1d5de7c0                      # 이 객체를 가리키는 칸과 그 주인 (거꾸로 따라가기)
m24cli find-text "서울 이랜드 FC"                 # 화면 글을 들고 있는 객체
m24cli ui tree --root 0x주소 --scan 0x400        # 화면 위젯과 그 안의 글 칸
```

### 2. 값으로 칸 찾기 (`find-field`)

화면 값을 **서로 다른 대상 둘 이상**에 대해 주세요. 한 대상만으로는 우연히 같은 숫자가 나와서, 여러 대상에서 같은 위치·형식인 칸만 믿을 수 있어요. 게임의 돈은 `N억`으로 쓰면 내부 단위로 바꿔 찾아요 (화면 값은 반올림돼 있어서 기본 오차 2%).

```bash
m24cli find-field player:2002122126=1480억 player:19302146=245억 --name player.askingPrice
#   모든 대상에서 같은 칸: +0x1d0 i32 (89100000, 14852187)
#   fields.json 초안: "player.askingPrice": {"kind": "player", "off": "0x1d0", ...}
```

- 후보가 많으면 대상을 더 늘리거나 값을 바꿔서(날짜를 진행한 뒤, 다른 선수) 다시 찾고 교차해요.
- 칸이 객체 안 다른 구조(포인터가 가리키는 곳)에 있으면 `via`(먼저 따라갈 포인터 칸들)가 초안에 나와요.
- 화면에 없는 값(숨은 성향 등)은 `explore`로 펼쳐 놓고 값이 다른 선수끼리 비교해서 찾아요.

### 3. 등록하기

`core/fields.json`의 `fields`에 한 줄 더해요. 초안의 `TODO`를 채우세요.

| 항목 | 뜻 |
|---|---|
| `kind` | 객체 종류 (`player` `team` `club` `human`). 없으면 `kinds`에 클래스 이름(RTTI)으로 먼저 더해요 |
| `off`, `via`, `alt` | 객체 맨 앞에서의 위치(16진 글), 먼저 따라갈 포인터 칸들, 하위 클래스마다 위치가 다를 때 `{"클래스": 위치 또는 null}` |
| `type` | `i8` `u8` `i16` `u16` `i32` `u32` `f32` `f64` `ptr`(+`to`) `date` `str` `strref` |
| `unit`, `desc` | 단위(`money`는 내부 돈 단위, 원 = ×1664.7), 뜻 (화면의 이름과 같게) |
| `source` | **근거** (어느 로그, 어느 화면 값과 맞춰 봤나) |
| `verified` | 화면·다른 값과 맞춰 봤으면 `true`, 아니면 `false` |
| `write` | 기본 `no`. 쓰기는 4절 |

### 4. 확인하기

```bash
python -X utf8 tools/m24.py caps                           # docs/FIELDS.md를 다시 만들어요
m24cli stop; m24cli start --now --wait 90                  # core/fields.json을 코어에 다시 넣어요
m24cli get player:2002122126 player.askingPrice            # 화면과 같은지
m24cli get player:19302146 player.askingPrice
python -X utf8 -m unittest tests.test_fields               # 형식 검사
```

여러 선수에서 기존 값과 같은지 대조하려면 읽기 전용 임시 모드를 만들어 모든 선수를 훑는 것이 가장 확실해요 (M20이 선수 119,449명으로 한 방법: `logs/M24GA/2026-11-08/m20_verify/`).

### 5. 쓰기까지 열 때 (`write: safe`)

**읽기로 충분히 확인한 칸만** 열어요. 게임이 그 값을 다른 곳에 따로 저장해 두면(예: 능력치 합계로 CA를 다시 계산) 쓴 값이 덮어쓰이거나 세이브가 어긋날 수 있어요. 쓰기 칸은 이렇게 적어요.

```json
"write": "safe", "range": [1, 200], "gte": "player.ca", "cap": "write.player.pa", "verified": true
```

- `range`(허용 범위), `gte`/`lte`(다른 필드와의 관계), `cap`(필요한 기능, 안 쓰면 `write.field`).
- 객체 종류에 `key`와 `check`가 있어야 해요 (되돌리기가 같은 객체를 다시 찾고, 쓰는 중에 객체가 바뀌지 않았는지 확인해요).
- **실기 확인 절차:** (1) 게임을 저장해 두고 (2) 임시 모드로 값을 한 번 쓰고 (3) 게임 화면에서 바뀐 것을 확인하고 (4) 앱 정보 탭이나 `m24cli undo <모드 id>`로 되돌려서 원래 값으로 돌아오는지 확인해요. 그리고 값이 **다음 날 되돌려지거나 다시 계산되는지**도 날짜를 진행해서 봐요.

## B. 새 함수 등록하기

### 1. 함수 찾기

가장 쉬운 길은 **그 값을 쓰는 코드를 잡는 것**이에요 (칸을 이미 등록했다면).

```bash
# 게임을 저장하세요! 그다음:
m24cli watch-write player:2002122126 0x1d0 4 --secs 300 --wait 300     # 그동안 게임에서 그 값이 바뀌게 하기 (날짜 진행 등)
#   fm+0x3701691 (함수 fm+0x3700780 +0xf11)  r14 -> db::ACTUAL_PLAYER  r15 -> db::CLUB  rbx -> db::FULL_CONTRACT
```

- 결과의 `함수 fm+0x…`가 **함수 시작(rva)**이에요. `r14 -> db::…`는 그 순간 레지스터가 가리킨 객체의 클래스예요. "호출 경로"로 부른 쪽 함수도 찾아 올라갈 수 있어요.
- 잡히는 곳이 한 곳이 아닐 수 있어요. 많이 잡히는 곳보다 **의미 있는 곳**(값을 계산하는 함수)을 고르세요.
- 함수 안을 읽으려면 REA(`fm.exe`를 열어 주소로 디컴파일)나 `python -X utf8 -I tools/fmdis.py ...`를 써요.

### 2. 인자와 호출자 알아내기 (`watch-call`)

```bash
m24cli watch-call fm+0x3700780 --secs 300 --wait 300     # 그동안 게임 진행
#   부른 곳: fm+0x372e8db   인자 0 (rcx): SHORTLIST_MANAGER   인자 3 (r9): 2035 ...
```

인자의 클래스 이름·정수와, 반환값, 부르는 곳, 한 번에 걸리는 시간을 알 수 있어요. **얼마나 자주 불리는지**도 중요해요 (매 프레임 불리는 함수에 느린 콜백을 달면 게임이 느려져요). 이건 디버그 레지스터를 쓰지 않아서 `watch-write`보다 안전해요.

### 3. 등록하기

`core/functions.json`의 `functions`에 더해요.

```json
"player.updateAskingPrice": {
  "rva": "0x3700780",
  "sig": {"off": "0x10", "hex": "01000066440f7fbc24a001000066440f"},
  "args": ["ptr", "ptr", "ptr", "ptr"],
  "argNames": ["SHORTLIST_MANAGER 객체", "?", "?", "?"],
  "ret": "void", "hook": "observe", "thread": "game",
  "desc": "...", "source": "M21 watch-write, M22 watch-call", "verified": false
}
```

- `rva`는 **함수 시작**이어야 해요 (`tests/test_functions.py`가 예외 테이블로 확인해요).
- `sig`는 **`fm.exe` 파일에서** 함수 시작 + 0x10의 16바이트예요 (후킹이 덮어쓰는 앞 16바이트를 피해요). 다른 빌드에서는 이게 안 맞아서 코어가 그 함수에 걸지 않아요.
- (코어 0.38.0) **가상 함수면 `vf: {class, off, index}`**(그 클래스 vtable의 몇 번째 칸)를 `python -X utf8 tools/func_vf.py fill`로 채워요. 빌드가 바뀌어 rva·서명이 안 맞으면 로더가 RTTI 클래스 이름으로 vtable을 찾아 같은 칸의 함수를 다시 확인해 써요 (`loader/funcmap.py`, 빌드 진단 보고서의 '함수 등록부' 절). 서명 16바이트가 코드 안 여러 곳에 있으면 같은 `fill`이 더 긴 검색용 바이트 `find`를 둬요. 비가상 함수는 이 바이트를 코드에서 검색해(딱 한 곳 + 함수 시작이어야) 다시 찾아요. 확인: `tools/func_vf.py check`.
  ```python
  python -X utf8 -c "import sys; sys.path.insert(0,'tools'); import rtti; pe=rtti.PE(rtti.DEFAULT_EXE); o=pe.off(0x3700780+0x10); print(pe.m[o:o+16].hex())"
  ```
- `hook`은 `observe`(보기만)로 시작해요. **`modify`(인자·반환값 바꾸기)는 인자 뜻을 모두 확인하고 `verified: true`일 때만** 쓰세요.
- 코어가 이미 걸어 둔 함수는 `"owner": "core", "event": "..."`로 적어요 (모드는 `api.on`을 써요).

### 4. 확인하기

```bash
python -X utf8 tools/m24.py caps          # docs/FUNCTIONS.md
python -X utf8 -m unittest tests.test_functions
m24cli stop; m24cli start --now --wait 90
m24cli hooks                              # 서명 확인: 이 빌드와 맞으면 ok
```

그다음 임시 모드에서 `api.hook('이름', { before, after })`로 걸어 `m24cli log <모드 id>`와 `m24cli hooks`(호출 수·오류·걸린 시간)를 확인해요 (M22의 시험 모드: `logs/M24GA/2026-11-09/m22_hook/`).

## 스킨·언어와 무관하게 (M35~M39)

- 사용자마다 스킨과 게임 언어가 달라요. **위젯 id나 화면 글 대신 게임 내부를 쓰세요**: 데이터는 객체·필드, 동작은 등록부 함수·이벤트 (예: 계속 = `ui.continueHandler`에 `'CONT'`, 휴가 = `ui.holidayStart`, 즉석 결과 = `match.clientTacticEvent`에 `'INST'`).
- 버튼이 하는 일을 내부에서 찾는 순서: 버튼의 4글자 id를 `find-const`로 확인 → 게임 코드에 있으면 그 상수를 쓰는 함수를 디스어셈블 → 없으면(스킨 이름) 버튼을 누르는 동안 `watch-call fm+0x1053920`(이벤트 보내기, 4글자 코드가 글자로 보임)이나 그 창의 이벤트 처리기(vtable +0x28)를 읽어요. 보호 구역(Denuvo)이라 못 읽으면 사용자에게 그 화면을 한 번 열어 달라고 하고 창 쪽 처리기를 읽어요 (M38 휴가).
- 화면이 열려 있어야 되는 기능은 `capabilities.json`에 `"screen": "화면 이름"`을 적어요 (문서에 '화면 의존'으로 표시).

## C. 끝내기

1. `python -X utf8 -W error::ResourceWarning -m unittest discover -s tests` — 전부 통과
2. 코어가 바뀌었으면 `loader/mods.py`의 `CORE_VERSION`을 올려요 (등록부만 더했으면 보통 마이너). `core/capabilities.json`의 `core`도 같이.
3. 로그(`logs/M24GA/YYYY-MM-DD/MNN_...md`)에 **무엇을 어떻게 확인했는지**(화면 값, 몇 명에서 대조, 쓰기·되돌리기 실기) 적어요. 등록부의 `source`가 그 로그를 가리키게 해요.
4. 함정: 임시 모드는 끝나면 지워요 (모드 폴더, `permissions.json`, `enabled.json`, 쓰기 기록의 시험 줄).
