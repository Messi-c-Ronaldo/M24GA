# M24GA 모드 만들기

M24GA는 FM24(Epic 빌드)에 모드를 붙이는 로더예요. 모드 하나는 **`.24mod` 파일 하나**이고(내용은 zip), 사용자는 이 파일을 모드 폴더에 넣고 M24GA 앱에서 켜고 설정해요.

이 문서는 모드를 만드는 사람을 위한 안내예요. 코어 버전은 **0.33.0**이고, `0.x`인 동안은 코어 함수의 이름과 모양이 바뀔 수 있어요 (바뀌면 `mod.json`의 `core` 조건으로 걸러져요).

가장 빠른 시작은 [`examples/hello/`](../examples/hello)를 복사해서 고쳐 보는 거예요. 설정 항목 종류, 모드창, Python 부분, 게임 쪽 JS가 한 번씩 다 들어 있어요.

**AI에게 시킨다면** [AI_GUIDE.md](AI_GUIDE.md)를 먼저 보세요. 되는 것/안 되는 것, 흔한 실수, AI에게 붙여 넣을 시작 프롬프트가 있어요.

**도구** (게임 없이 돌아가요):

| 명령 | 하는 일 |
|---|---|
| `python -X utf8 tools/m24.py new <id> [--python] [--ui] [--dir 폴더]` | 동작하는 모드 뼈대를 만들어요 (AI용 `AGENTS.md` 포함) |
| `python -X utf8 tools/m24.py validate <모드> [--json] [--strict]` | 문제를 위치·이유·고치는 법과 함께 알려 줘요 |
| `python -X utf8 tools/m24.py pack <모드폴더>` | 검사한 뒤 `.24mod`로 묶어요 |

편집기 지원: `mod.json`의 `"$schema"`에 [`mod.schema.json`](mod.schema.json)을 적으면 자동완성과 오류 표시, `mod.js` 맨 위에 `/// <reference path=".../docs/types/m24ga.d.ts" />`와 `// @ts-check`를 적으면 없는 함수나 틀린 인자가 바로 빨간 줄로 보여요 ([types/m24ga.d.ts](types/m24ga.d.ts), [types/m24ga.pyi](types/m24ga.pyi)). 새 모드 뼈대에는 둘 다 들어 있어요.

## 1. 모드 구조

```
my-mod-1.0.0.24mod   (zip)
  mod.json           필수. 모드 소개와 설정 항목
  mod.js             게임 안에서 도는 부분 (Frida JS). 필수
  python/main.py     PC에서 도는 부분 (AI 호출, 파일 처리 등). 선택
  ui/index.html      모드창 (앱 안에 뜨는 화면). 선택
  builds/*.json      이 모드만 쓰는 게임 주소 서명. 선택
```

- 모드 폴더는 `문서\M24GA\mods`예요 (앱의 "모드 폴더 열기" 버튼). 문서 폴더가 OneDrive로 옮겨져 있으면 그 안의 `M24GA\mods`예요.
- **개발할 때는 압축하지 않은 폴더**(안에 `mod.json`이 있는 폴더)를 모드 폴더에 그대로 두면 똑같이 인식돼요. 로더 저장소를 직접 받아 쓴다면 저장소의 `mods/`도 읽어요.
- 같은 `id`의 모드가 둘 이상 있으면 모두 켜지지 않고 앱에 충돌이 표시돼요.
- `.24mod`로 묶기: `python -X utf8 tools/pack_mod.py 모드폴더 [출력폴더]` → `<id>-<version>.24mod` (`__pycache__`와 숨김 파일은 빠져요).

## 2. mod.json

| 항목 | 설명 |
|---|---|
| `id` | **필수.** 소문자·숫자·`-`·`_`, 최대 64자. 설정·데이터 폴더 이름에 쓰이니 한 번 정하면 바꾸지 않아요 |
| `name`, `version` | **필수.** 앱에 보이는 이름과 버전 (`1.0.0` 형식 권장) |
| `description`, `author`, `license` | 앱의 정보 탭에 보여요 |
| `core` | 필요한 코어 버전. `">=0.2.0"`, `"==0.2.0"`, `"0.2.0"`(정확히 같음). `api.send/recv`와 `ctx.recv/post`를 쓰면 `>=0.2.0`, `api.onUnload/alive`를 쓰면 `>=0.3.0`이 필요해요. 안 맞으면 켤 수 없다고 표시돼요 |
| `js` | 게임 쪽 파일 이름 (기본 `mod.js`) |
| `python` | Python 진입 파일 (예: `python/main.py`). 없으면 Python 부분 없음 |
| `ui` | 모드창 HTML (예: `ui/index.html`). 없으면 모드창 탭이 비활성 |
| `default_enabled` | 처음 설치했을 때 켜질지 (기본 `true`). 켜짐 여부는 사용자가 바꾸면 `enabled.json`에 저장돼요 |
| `data_dir` | 모드 데이터 폴더 (기본 `~/m24ga_data/<id>`). `~`를 쓸 수 있어요 |
| `migrate_from` | 옛 데이터 폴더. 새 데이터 폴더가 비어 있으면 처음 켤 때 **한 번 복사**해 와요 (옛 폴더는 그대로 두고, 새 폴더에 내용이 있으면 아무것도 안 해요). 데이터 폴더 위치를 바꾼 모드가 쓰세요 |
| `capabilities` | (코어 0.4.0) 쓰는 기능 이름 목록. 목록과 뜻은 [`CAPABILITIES.md`](CAPABILITIES.md) (11절) |
| `settings_file` | 설정을 저장할 파일 이름 (기본 `settings.json`, 데이터 폴더 안) |
| `settings` | 설정 항목 목록 (3절) |
| `requires` | 필요한 Python 패키지 이름 목록. 없으면 앱에 경고만 보여요 (켜는 건 막지 않아요) |
| `events` | 쓰는 이벤트 목록 (참고용, 로더는 검사하지 않아요) |

## 3. 설정 (settings)

`settings`에 항목을 적으면 **앱의 설정 탭이 자동으로 만들어져요.** HTML을 쓸 필요가 없어요. 값은 `<데이터 폴더>/<settings_file>`에 저장되고, 모드를 새 버전으로 바꿔도 남아요.

```json
{"key": "style.swear", "type": "select", "label": "말투", "default": "normal", "group": "말투",
 "options": [{"value": "normal", "label": "기본"}, {"value": "wild", "label": "야생"}], "help": "설명 줄"}
```

- `key`: 점(`.`)이 있으면 파일 안에서 중첩돼요 (`style.swear` → `{"style": {"swear": ...}}`). 파일의 다른 항목은 건드리지 않아요.
- 공통: `label`(이름), `default`, `help`(회색 설명), `group`(카드 묶음 이름, 안 적으면 "설정").

| `type` | 화면 | 추가 항목 |
|---|---|---|
| `bool` | 스위치 | |
| `int` | 숫자 입력 | `min`, `max` |
| `number` | 숫자 입력, **`min`과 `max`가 둘 다 있으면 슬라이더** | `min`, `max`, `step`, `percent`(`true`면 0~1을 %로 보여 줘요) |
| `text` | 한 줄 입력 | `multiline`(여러 줄), `placeholder` |
| `password` | 가려진 입력. 값은 화면으로 보내지 않고 "저장돼 있어요"만 표시 | `placeholder` |
| `select` | 4개 이하는 분할 버튼, 그 이상은 드롭다운 | `options`: 문자열 목록 또는 `{"value", "label"}` 목록 |

범위를 벗어나거나 형식이 틀린 값은 저장되지 않고 이유가 토스트로 보여요. 파일에 없거나 틀린 값은 `default`로 읽혀요.

## 4. 게임 쪽 부분 (mod.js)

로더는 **코어 + 켜진 모드들**을 Frida 스크립트 **하나로 묶어서** 게임(`fm.exe`)에 올려요. 모드는 `registerMod('<id>', function (api) { /* mod.js */ })` 안에 들어가므로, `var`로 만든 변수는 그 모드 안에서만 보여요.

> 항상 `var`로 선언하세요. `var` 없이 대입하면 코어나 다른 모드의 전역 변수를 덮어써요.

### 로더가 넣어 주는 것

- `DIR`: 모드 데이터 폴더 (끝에 `/` 포함, 예: `C:/Users/me/m24ga_data/my-mod/`). `var DIR = ...;` 줄을 적어도 되고(로더가 값을 바꿔 넣어요) 안 적어도 돼요.
- 게임 프로세스는 `Program Files` 안에 파일을 쓸 수 없으니, 주고받는 파일은 `DIR` 안에 두세요. Frida의 `File`을 써요 (`File.readAllText(path)`, `new File(path, 'a')`).

### api

| 함수 | 설명 |
|---|---|
| `api.on('socialPanel', fn)` | 소셜 패널(소셜피드 글 한 칸)이 그려질 때. `fn(ev)`, `ev = { th, type, dst, text }`: `th` 패널 객체 주소, `type` 글 종류 (0 뉴스 제목, 2·4 팬 댓글, 3·5 공식 글), `dst` 글자 칸 주소, `text` 지금 글. 화면을 그리는 스레드에서 불려요 |
| `api.on('frame', fn)` | 화면 스레드의 매 프레임이 끝난 직후 (초당 약 20번). **오래 걸리는 일은 하지 마세요.** 간격은 모드가 직접 조절해요 (`Date.now()`로) |
| `api.on('dateChanged', fn)` | (코어 0.5.0) 게임 날짜가 바뀔 때. `ev = { from, to, days }`, 날짜는 `{ y, m, d, doy, iso }`. 코어가 0.5초마다 확인해요 (화면 스레드 아님) |
| `api.on('newsAdded', fn)` | (코어 0.35.0, 기능 `event.newsAdded`) 게임이 뉴스를 넣을 때마다 (하루 수백 번: 경기 보고·이적·부상·언론 의견…). `ev = { cls, flags, toInbox, team, mine, text() }`. `cls` = 뉴스 종류(클래스 이름), `mine` = 내 팀 앞, `text()` = 게임 본문 글(평문, 비싸니 필요한 것만, 콜백 안에서만). 게임 스레드라 짧게 하고 긴 일은 `api.send`로 Python에. 모드가 `api.inbox.send`로 넣은 메일에는 안 와요. (코어 0.37.0) `ev.id`(뉴스 번호), `ev.date`('YYYY-MM-DD'), `ev.refs()` = 관련 기록 `{ people, teams, clubs, comps, refs }` (게임이 뉴스에 붙인 사람·팀·대회 객체, 콜백 안에서만) |
| `api.on('matchEnded', fn)` | (코어 0.37.0, 기능 `event.matchEnded`) 경기가 끝나 경기 보고 뉴스가 나올 때 경기마다 한 번. `ev = { home, away, homeGoals, awayGoals, comp, stadium, mine, date, text() }`. 팀·대회는 객체라 `api.prop(ev.home, 'Tnam').Tsna`(팀 짧은 이름), `api.prop(ev.comp, 'cnam')`(대회 이름)처럼 읽어요. 게임이 보도하는 리그·대회의 경기만 오고, 승부차기는 아직 구별하지 않아요  자세히: [NEWS.md](NEWS.md) |
| `api.on('gameSaved', fn)` | (코어 0.35.0, 기능 `event.gameSaved`) 게임 저장이 끝난 뒤 (.fm 파일 쓰기 완료). `ev = { ms, save }`. 세이브별 모드 기록을 이때 확정하면 '저장 안 하고 다시 불러오기'와 구별돼요 |
| `api.on('saveLoaded', fn)` | (코어 0.5.0) 다른 세이브를 불러왔을 때. `ev = { id, nonce, date }`. 모드가 그 뒤에 올라왔으면 이미 지나갔으니 처음에 `saveInfo()`로 확인하세요 |
| `api.every(ms, fn)` / `api.after(ms, fn)` | (코어 0.5.0) 타이머 (최소 50ms). 반환값의 `stop()`으로 멈추고, **모드를 내리면 코어가 알아서 멈춰요** (`setInterval`을 직접 쓰지 마세요). 화면 스레드 아님 |
| `api.setPlayerPA(uid, pa, opts)` | (코어 0.7.0, 기능 `write.player.pa`, **사용자 허용 필요**) 선수 잠재력을 바꿔요 (아래 "게임 값 쓰기") |
| `api.hook(name, { before, after })` | (코어 0.11.0, 기능 `hook.function`, **사용자 허용 필요**) 함수 등록부의 게임 함수에 끼어들어요 (아래 "게임 함수 끼어들기", 목록 [`FUNCTIONS.md`](FUNCTIONS.md)) |
| `api.gate(name, on?)` | (코어 0.15.0, 기능 `hook.gate`, 사용자 허용 필요) 등록된 게이트를 켜요: 정해진 게임 함수 안에서만 정해진 질문에 다른 답을 해요 (예: 몸값 계산의 '감독이 사람인가'). 같은 칸에 게이트 여러 개를 함께 걸 수 있어요 (0.16.0). 반환 `{ ok, set(on), stats(), stop() }`. 목록은 [`FUNCTIONS.md`](FUNCTIONS.md) '게이트' |
| `api.scale(name)` | (코어 0.17.0, 기능 `hook.scale`, 사용자 허용 필요) 등록부에서 scale이 있는 함수(예: `player.value` = 선수 가치)의 반환값에 객체별 배율을 곱해요: `s.set(선수, 1.2)`. 네이티브 표라 하루 수만 번 불려도 빨라요. 게임 상한으로 잘라요. 함수 하나에 모드 하나. 반환 `{ ok, set, get, clear, enable, stats, stop }` |
| `api.setField(obj, name, value, opts)` | (코어 0.10.0, 기능 `write.field` 또는 그 필드의 기능, **사용자 허용 필요**) 필드 등록부에서 쓰기가 확인된 칸을 바꿔요 (아래 "게임 값 쓰기", 목록 [`FIELDS.md`](FIELDS.md)) |
| `api.setProp(대상, 코드, 값, opts)` | (코어 0.42.0, 기능 `write.prop`, **사용자 허용 필요**) 속성 코드 값을 게임 자신의 setter로 바꿔요 → Promise `{ok, before, after, code, key, error}` (아래 "속성 코드로 쓰기", 목록 [`PROPERTIES.md`](PROPERTIES.md) "쓰기") |
| `api.settings()` / `api.onSettings(fn)` | (코어 0.12.0) 이 모드의 설정 값 `{key: 값}` (mod.json `settings`, 없으면 `default`, **비밀번호 형식은 빠져요**)와, 앱에서 설정이 바뀔 때 새 값으로 불리는 함수. 사용자 허용이 필요 없어요. 설정 파일을 직접 읽지 마세요 (`pc.file` 허용이 필요해져요). Python은 `ctx.settings()` |
| `api.status(fn)` | `fn()`이 돌려주는 객체가 로더 상태(`rpc status`)에 합쳐져요 |
| `api.prepareData(th)` | 게임 데이터 표(클럽·선수·스태프 주소록)를 만들기 시작하고 값 종류를 얻어요. 소셜 패널 안에서 한 번 부르면 돼요. 표는 1~2분 걸려요. 준비되면 전역 `mapsReady`가 `true` |
| `api.log(msg)` | 로더 기록(`~/m24ga_data/loader.log`)에 `game: [<id>] msg`로 남아요 |
| `api.send(obj)` | 이 모드의 **Python 부분**으로 메시지를 보내요 (`ctx.recv()`로 받아요). `obj`는 JSON으로 바꿀 수 있어야 해요 |
| `api.onUnload(fn)` | (코어 0.3.0) 모드를 내릴 때(끄기, 새 버전 설치, 다시 올리기) 불려요. `api`로 등록한 것은 코어가 알아서 떼지만, 모드가 **직접 건** `Interceptor.attach`, `setInterval`/`setTimeout`, 바꿔 둔 화면 글자는 여기서 치우세요. 안에서 `api.log/send`는 돼요 |
| `api.alive()` | (코어 0.3.0) 아직 올라가 있으면 `true`. 내린 뒤 남은 타이머 등에서 확인하세요 (내린 뒤 `api` 호출은 아무 일도 안 해요) |
| `api.recv(fn)` | Python의 `ctx.post(obj)`로 온 메시지를 받아요. `fn(obj)` 하나만 등록할 수 있고(나중 것이 앞의 것을 바꿔요), 게임의 다른 스레드에서 불려요 (JS는 한 번에 하나씩만 돌아서 모드 변수는 안전해요) |

**모드를 켜고 끌 때 (핫 리로드, 코어 0.3.0):** 앱에서 모드를 켜고 끄거나 새 버전을 설치하면, 로더는 **코어 스크립트와 게임 데이터 표는 그대로 두고 그 모드만** 내리고 올려요 (예전에는 스크립트 전체를 다시 올려서 표를 1분 반 동안 다시 만들었어요). 개발 폴더 모드는 `mod.js`를 고친 뒤 앱 정보 탭의 **게임 쪽 다시 올리기**를 누르면 게임을 다시 켜지 않고 바로 적용돼요 (모드 폴더에서 **새로 고침**을 눌러도 바뀐 모드만 다시 올라가요). 다시 올라온 모드는 변수가 새로 시작하므로, Python과 상태를 맞추는 `hello`를 올라올 때마다 보내세요. Python 부분은 앱을 다시 켜야 새 코드가 적용돼요.

모드 콜백에서 난 오류는 코어가 `try/catch`로 막아서 **다른 모드와 게임은 멈추지 않아요.** 그래도 게임 메모리를 읽는 코드는 직접 `try/catch`로 감싸고, 실패하면 아무것도 안 바꾸고 넘어가세요.

### 코어 함수 (모드에서 그대로 쓸 수 있어요)

- **선수 능력·신원 (코어 0.6.0, `read.player`):** `playerOf(o)`(사람 데이터 객체 → 선수 객체, 선수가 아니면 `null`), `playerByUid(uid)`, `playerInfo(p)` → `{ uid, ca, pa, dob, name }`(CA·PA 1~200), `playerUids()`(모든 선수 UID), `personUid(o)`(고유 ID), `personOf(p)`(코어 0.9.0, 선수 객체 → 사람 데이터 객체: `getVal`로 속성을 읽는 객체). 소셜 패널이 그려지기 전에도 돼요.
- **대회·상 정보 (코어 0.20.0, `read.award`):** `compInfo(번호)` → `{ idx, uid, name, short, nation, continent }`, `awardInfo(번호)` → `{ idx, name, short, comp, nation, continent }` (comp = 그 상이 딸린 대회 번호, 나라·대륙은 이름), `compIds()`, `awardIds()`. 코어 0.21.0: `compLatest(번호)` → `{ comp, start, end, winner, runnerUp, third }` (가장 최근에 끝난 시즌, 팀 번호 = db::TEAM +0x8; 세이브 대회 기록에 아직 보관 안 된 시즌이라 m24awards 우승 계산에 `extra_wins`로 넘겨요). 번호는 세이브 기록(Python `m24awards`의 상·대회 번호)과 같아서, Python이 번호를 보내면 게임 쪽에서 이름을 붙일 수 있어요. 표는 세이브를 불러온 뒤 만들어져요 (없으면 `null`).
- **선수 몸값 (코어 0.17.0, `read.player.value`):** `playerValue(p, club?)` → `{ value, reasons: [{code, a, b}], club }` (내부 돈 단위, 원화 = ×1664.7). 게임의 가치 함수를 그대로 불러요 (게이트·배율 표가 들어간 값). club을 주면 그 구단이 평가하는 값(이적 제안). 게임이 진행 중이면 `{ error, busy }`. **타이머(`api.after/every`)에서** 부르세요: `frame`·`api.hook` 콜백 안에서 부르면 게이트·배율이 빠진 값이 나와요. 이유 코드 뜻은 [`FUNCTIONS.md`](FUNCTIONS.md) `player.value`.
- **필드 등록부 (코어 0.10.0, `read.field`):** `getField(obj, 'player.askingPrice')`, `findObj('player', uid)`, `fieldInfo(name)`, `fieldNames('player.season.league.')`. [`core/fields.json`](../core/fields.json)에 등록된 칸을 이름으로 읽어요 (목록 [`FIELDS.md`](FIELDS.md)). 객체 종류를 클래스 이름으로 확인해서 다른 종류면 `null`이에요. 전용 함수(`playerInfo` 등)에 없는 칸도 여기 있으면 읽을 수 있고, **새 칸은 `fields.json`에 한 줄 더하면** 모든 모드가 써요.
- **객체의 클래스 이름 (코어 0.9.0, `read.rtti`):** `className(obj)` → `'db::ACTUAL_PLAYER'`(없으면 `null`), `isA(obj, 'db::PERSON')`, `rttiInfo(obj)` → `{ name, off, top, bases }`. fm.exe에 남은 클래스 정보(RTTI)를 읽어요. 객체 종류를 vtable 주소 대신 이름으로 확인할 수 있어요. 게임 조사는 CLI `explore`·`classes`([`CLI.md`](CLI.md)).
- **선수 시즌 기록·포지션·성격·소속 (코어 0.8.0, `read.player`):** `playerSeason(p, kind)` → `{ apps, starts, subs, minutes, rated, ratingSum, avg, goals, assists, pens }` (kind: `'club'` 클럽 공식전 합계(기본) · `'league'` · `'cup'` · `'continental'` · `'international'`), `playerSeasonDetail(p, kind)` → `{ xg, xa, npxg, shots, keyPasses, ... }` (게임 속성과 맞춰 본 건 xG뿐), `playerPositions(p)` → `{ GK: 1, DC: 20, ... }`(1~20), `playerPosition(p)` → `{ code, level }`, `playerTraits(p)` → `{ ambition, professionalism, determination, workRate, flair }`(1~20), `playerTeam(p)` → `{ team, club, name, short, compUid }`, `playerInjury(p)` → `{ injured, proneness, type, daysSince, remainMin, remainMax }`(코어 0.8.1, 사람 표가 만들어진 뒤부터). 모두 선수 객체(`playerByUid`/`playerOf`)를 받아요.
- **소셜 패널 도우미 (코어 0.6.0, `read.panel`):** `panelAt(addr, type)`(주소 문자열로 패널 다시 찾기), `panelText(th)`, `panelTextHandle(th)`, `panelDst(th)`, `panelThread(th)`, `panelFanUid(th)`. 클럽 이름은 `clubFullName(cd)`, `clubShortName(cd)`, `clubObj(cd)` (`read.data`). 이 도우미로 되는 일에 `ptr()`·`.readU32()` 같은 직접 읽기(`raw.read`, 사용자 허용 필요)를 쓰지 마세요.
- **속성 코드:** `getVal`/`getInt`에 쓰는 4글자 코드 중 확인된 것은 [`PROPERTIES.md`](PROPERTIES.md)에 있어요.
- **게임 날짜·세이브 (코어 0.5.0):** `gameDate()` → `{ y, m, d, doy, iso }` 또는 `null`(세이브 없음), `saveInfo()` → `{ id, nonce }` 또는 `null`. 세이브마다 따로 기록할 것은 Python의 `ctx.save_dir()`에 두세요.

코어 전역 함수는 한 스크립트 안이라 이름만 써서 부르면 돼요. 자세한 동작은 `core/core.js`의 주석이 가장 정확해요. 주로 쓰는 것:

| 이름 | 하는 일 |
|---|---|
| `getVal(obj, '4글자')`, `getInt(obj, code)` | 게임 데이터 객체의 속성 읽기 (예: `getVal(club, 'Tfrm')`). 객체가 클럽/사람 데이터 객체가 아니면 예외를 던져 게임이 튕기는 걸 막아요 |
| `lookup(map, idx, vt)` | 주소록에서 번호로 객체를 꺼내고 아직 같은 객체인지 확인. 없으면 `null` |
| `clubs`, `persons`, `staff` | 주소록 (번호 → 객체 주소). `mapsReady` 뒤에 쓸 수 있어요 |
| `linkIds(text)` | 글 속 링크를 `[{name, type, idx}]`로 풀어요 |
| `newsBody(news)` | 뉴스 기사 본문 (실패하면 `''`) |
| `myInfo()` | 내 감독 이름과 클럽 `{mgr, co, club, full}` (무직이면 `mgr`만, 못 구하면 `null`) |
| `fanClub(uid)` | 팬 고유 ID → 응원 팀 `{uid, name, full, mine}` |
| `clubManagerObj(idx)`, `personName(id)`, `personForm`, `topPlayer`, `clubExtra`, `clubSituation`, `mainPosition` | 감독·이름·폼·핵심 선수·클럽 정보 읽기 |
| `setStr(dst, str)` | 소셜 패널의 글자 칸을 새 글로 바꾸기 |
| `refreshPanel(th)` | 패널을 다시 그리기. **화면 스레드에서만** (`socialPanel`·`frame` 콜백 안) |
| `hash64(s)`, `dbg(msg)`, `B`(fm.exe 기준 주소), `uiTid`(화면 스레드 번호) | 도우미 |

> 이 목록은 아직 "코어 안 전역 함수를 그대로 노출"한 것이에요. 이름과 모양은 `0.x`에서 `api.*`로 정리될 수 있어요. 새 게임 주소가 필요한 기능은 코어가 아니라 모드의 `builds/`에 서명을 두는 걸 권장해요 (6절).

### 매치엔진 표 (코어 0.31.0, 기능 `read.engine`·`write.engine`)

- `api.engine.dump(표)`: 게임 메모리의 매치엔진 표를 그대로 읽어요. 표는 `'weights'`(선발 가중치), `'physics'`(선수 물리), `'momentum'`(경기 흐름), `'ratings'`(경기 평점), (코어 0.32.0) `'styles'`(전술 스타일: AI 감독이 스타일별로 팀 지시·성향을 고르는 범위, `tactics/styles.xml`)이에요.
- `styles`는 게임이 세이브를 불러온 뒤 **첫 진행일에** 불러와요. 그 전에는 `{error}`이고, 언어를 바꾸면 다시 불러와요 (`key`가 바뀜).
- (코어 0.33.0) `'xg'`: xG 모델(`expected_goals/models`)의 버전별·슛 종류별 계수와 절편 (f32 = JSON ÷ 1e7). `spec = {models: [{ver, coef?, icpt?}]}`는 있는 줄에만, 계수 수가 같을 때만 써요. `spec = {styles: [{folder, attr?, tend?}]}`는 그 스타일의 목록 전체를 바꾸고, 칸이 늘면 코어가 게임이 나중에 해제할 수 있는 버퍼를 새로 만들어요.
- `api.engine.write(표, spec)`: 이미 있는 칸에만 써요. 게임이 진행 중이면 `{error}`를 돌려줘요. 다음 선발·경기부터 반영되고, 세이브에는 남지 않아요.
- 무엇을 쓸지는 Python에서 `pylib/m24engine.py`로 정해요. 엔진 팩(.json/.jsb) 읽기, 원본 `simatch.fmf` 읽기(`load_game_original(ctx.game_dir())`), `plan(팩, 원본, 메모리)` → 쓰기 목록과 경고를 줘요.
- 실제 예는 `mods/dynamic-me`예요. JS는 읽기·쓰기만 하고 Python이 계획을 만들어요.

### 게임 속성 읽기 (코어 0.36.0, 기능 `read.prop`)

게임 화면이 값을 물을 때 쓰는 **4글자 속성 코드**를 모드도 그대로 써요. 코어가 게임 객체 16종류(팀·구단·국가대표·선수·스태프·사람 감독·대회·상, 0.39.0부터 국가·경기장·도시·대륙·언론사·계약·임대·부상)에 코드를 전부 물어 본 등록부(`core/properties.json`, 2,300여 개)를 갖고 있어요. 목록과 뜻은 [PROPERTIES.md](PROPERTIES.md).

```js
// mod.json "capabilities": ["read.prop"]
var rank = api.prop('myteam', 'TpoN');                 // 리그 순위
var money = api.props('myclub', { re: '^Cc' });        // 구단 재정 코드들 {코드: 값}
var opp = api.deref(api.prop('myteam', 'Topp'));       // 다음 경기 상대 팀 객체
if (opp) api.log('다음 상대 순위 ' + api.prop(opp, 'TpoN'));
api.log(JSON.stringify(api.propInfo('Pced')));         // { code: 'Pced', t: 'date', k: ['player','staff','human'] }
```

- 대상: 객체 포인터(선수 객체의 어느 칸이든 됨) 또는 `'me'`, `'myteam'`, `'myclub'`, `'myjob'`(내 감독 계약), 사람 참조 `'p123'`/`'s45'`, `'team:<번호>'`, `'comp:<번호>'`.
- 값: 정수, 실수, 글, `true/false`, 날짜 `'2038-06-30'`, 색 `'#rrggbbaa'`, 묶음 `{키: 값}`, 목록 `[...]`. 다른 객체는 `{dref: 번호}` → `api.deref`.
- 읽기만 해요. 게임 화면이 보여 주는 값이라 안전하지만, 등록부에 뜻(`ko`)이 없는 코드는 값의 뜻을 직접 확인하세요.
- (코어 0.40.0) **리그 경기 결과**: `api.leagueResults('myleague')` = 지난번 부른 뒤 끝난 리그 경기 `[{home, away, homeGoals, awayGoals, date}]` (보도 안 되는 경기 포함, [NEWS.md](NEWS.md)).
- (코어 0.41.0) **게임 명령(액션)**: `api.actionsFor(대상)` = 게임 메뉴가 그 대상에 보여 주는 명령 목록 (기능 `read.action`), `api.action('SUBS', 대상)` = 실행 (기능 `game.action`, 세이브를 바꿔서 사용자 허용, 1분에 10번, 로더 기록). 게임이 보여 주는 명령만, 게임이 만든 인자 그대로 실행해요. 확인 창을 거치는 명령(주장 지정 `PmcP`)은 확인 뒤 이벤트(등록부 `confirm`)를 주면 돼요 (`{event: 'pmcC'}`, 다음 날 처리 때 반영). 처리기가 빈 명령(화면 이동 LINK·사임 등, `canRun: false`)은 실행할 수 없어요. 대상: 사람·팀·구단·대회. Python 모드: `ctx.actions_for(대상)` / `ctx.action(id, 대상, event=None)`. 목록·이벤트: [ACTIONS.md](ACTIONS.md).
- Python 쪽에서도 돼요 (코어 0.39.0): `ctx.props('myclub', '^Cc')`, `ctx.prop('myteam', 'TpoN')`. JS가 `api.send`로 보낸 객체 주소(`String(ptr)`)도 대상이 돼요. AI 프롬프트에 넣을 값을 Python에서 바로 모을 때 편해요.
- 개발할 때: `cli.py props myteam ^T` (값 전부), `cli.py prop-find me 2038-06-30` (값으로 코드 찾기), `cli.py prop-info 순위` (게임 없이 목록).
- 한 번에 1,000개쯤 읽는 `api.props(대상)`은 0.5~1초 걸려요. `re`나 `codes`로 좁혀 쓰세요.

### 받은 편지함 메일 (코어 0.34.0, 기능 `ui.inbox`)

게임 받은 편지함에 메일 한 통을 넣어요. 게임의 "감독끼리 보내는 메시지" 종류라 목록에 **"보낸이의 말: 제목"** 으로 보여요.

```js
// mod.json "capabilities": ["ui.inbox", "read.me"]  (세이브에 남아서 사용자 허용이 필요해요)
var p = personByName('자우메 무닐');                       // 보낸이: 스태프·선수도 돼요 (없으면 내 감독)
api.inbox.send({ title: '이번 주 몸 상태 보고', body: '감독님, 부상 위험이 높은 선수는 없습니다.', from: p && p.person })
  .then(function (r) { if (!r.ok) api.log('메일 실패: ' + r.error); });
```

- 받는 사람은 내 감독이에요. 감독이 팀을 맡고 있어야 해요 (무직이면 `{ok: false}`).
- 제목 200자, 본문 8000자까지. 1분에 10통까지.
- **세이브에 남고 되돌릴 수 없어요.** 저장하면 다시 불러와도 그대로 있어요. 사용자는 게임에서 메일을 지울 수 있어요.
- 보낸 기록은 앱의 모드 로그에 남아요.
- 메일의 "응답" 버튼은 눌러도 아무 일도 일어나지 않아요 (온라인 게임용 기능).
- 화면 스레드에서 넣어요. 어느 스레드에서 불러도 되고, 결과는 Promise로 와요.

### 게임 안 패널 (코어 0.23.0, 기능 `ui.panel`)

게임 안에 FM 모양 대화상자를 띄워 사용자에게 고르게 하거나 알려 줄 때 써요. 모드는 게임 패널 XML을 쓰지 않고 **양식**만 적어요. 코어가 XML을 만들어 FM 사용자 폴더의 패널 칸(`문서\Sports Interactive\Football Manager 2024\panels\m24ga\slot01~08.xml`)에 쓰고, 게임의 일반 대화상자로 띄워요. 스킨 파일을 쓰지 않아서 어떤 스킨에서든 같아요.

```js
if (!api.panel.available()) api.log('게임 안 패널을 아직 못 써요 (게임을 다시 켜 주세요)');
var p = api.panel.open({
  title: '감독 선수 경력', text: '선수 시절을 골라 주세요',
  fields: [
    { id: 'club', type: 'text', label: '뛴 구단' },
    { id: 'year', type: 'number', label: '은퇴 해', min: 1970, max: 2035 },
    { id: 'intl', type: 'check', label: '국가대표', value: true },
    { id: 'pos', type: 'select', label: '포지션', options: [{ value: 'GK', label: '골키퍼' }, { value: 'FW', label: '공격수' }] },
    { type: 'label', label: '안내 글 한 줄' }
  ],
  buttons: [{ id: 'apply', label: '적용' }]      // 닫기 버튼은 코어가 늘 붙여요 (closeLabel로 글 바꾸기)
}, function (ev) {                                // 화면 스레드에서 불려요. 짧게!
  if (ev.id === 'apply') api.log(JSON.stringify(ev.values()));   // { club, year, intl, pos }
  if (ev.id === 'close') api.log('닫힘');
});
if (!p.ok) api.log(p.error);
```

- 이벤트 `ev.id`: 칸·버튼 id, 또는 `'open'`(뜸), `'close'`(닫힘), `'error'`(못 띄움, `ev.error`). `ev.kind`: `button`·`change`(글자마다)·`check`·`select`. `ev.value` = 그 칸의 지금 값.
- 값: `p.get(id)`, `p.values()`. number는 숫자(범위 밖이면 null), select는 options의 value, check는 true/false.
- **사람·구단 검색칸 (코어 0.29.0):** 칸 종류 `person`·`club`은 게임 자체 검색칸이에요. 치는 대로 게임이 후보(이름·포지션/직업·구단)를 띄우고, 고르면 `ev.kind === 'pick'`, `ev.value = { type, ref | uid, name, age, club, role, label }`이 오고 창이 "지금: …"을 보이며 다시 그려져요 (다른 칸 값은 그대로). `values()`에서는 고른 것, 안 골랐으면 친 글 `{ text }`, 둘 다 없으면 null. 칸 `value`에 `{ ref }`(사람)나 `{ uid }`(구단)를 주면 처음부터 "지금: …"으로 보여요. 고른 뒤 다시 그리지 않으려면 양식에 `refreshOnPick: false`. select 칸도 `value`를 주면 그 항목이 골라진 채 열려요.
  ```js
  { id: 'mentor', type: 'person', label: '은사', value: { ref: 'p95264' } },
  { id: 'fav', type: 'club', label: '좋아하는 구단' }
  ```
- `p.close()`로 닫아요. 모드를 내리면 코어가 그 모드의 패널을 닫아요. 한 번에 8개까지.
- 게임이 진행 중일 때는 열지 않아요 (`error`). 멈춘 화면에서 열어요.
- **처음 한 번:** 로더가 패널 칸 파일을 처음 만든 뒤에는 게임을 다시 켜야 해요 (게임이 켤 때 파일 목록을 읽어요). `api.panel.available()`이 false면 이 경우예요.
- 예제: `examples/panel`.
### 게임 안 JS ↔ Python 메시지 (코어 0.2.0부터)

JS와 Python은 파일 대신 **메시지**로 주고받아요. 폴링도, 파일 잠금도 필요 없어요.

```js
// mod.js
api.recv(function (m) { if (m.t === 'answer') use(m.text); });
api.send({ t: 'question', q: '...' });
```
```python
# python/main.py
def run(ctx):
    while not ctx.stop.is_set():
        m = ctx.recv(0.5)                      # 0.5초 기다려서 하나 받기 (없으면 None)
        if m and m.get("t") == "question":
            ctx.post({"t": "answer", "text": "..."})
```

- `ctx.recv(timeout=0)`: 0이면 기다리지 않고, 숫자면 그 초만큼, `None`이면 올 때까지 기다려요. 수신함은 2만 개까지이고 넘치면 가장 오래된 것부터 버려요.
- `ctx.post(obj)`는 게임에 안 붙어 있거나 스크립트가 내려가 있으면 `False`를 돌려주고 **그 메시지는 버려져요**. 그래서 **메시지가 유실될 수 있다고 생각하고** 설계하세요.
  - 게임 쪽이 로드되면 먼저 `hello` 같은 메시지를 보내서 Python이 필요한 상태(캐시, 설정)를 한꺼번에 보내게 하세요. 모드를 켜고 끌 때마다 스크립트가 다시 올라가므로 이 순서는 매번 일어나요.
  - JS가 보낸 요청에 답이 없으면 JS가 기억해 뒀다가 Python이 "준비됨"을 알릴 때 다시 보내세요. Python은 같은 요청을 두 번 받아도 괜찮게 만드세요 (소셜피드는 요청마다 키가 있어서 이미 만든 키는 결과만 다시 보내고, 만드는 중인 키는 건너뛰어요).
  - Python이 아직 안 떠 있을 때 JS가 보낸 메시지는 호스트가 수신함에 쌓아 두었다가 Python이 시작하면 줄 수 있어요 (Python 시작 순서는 로더가 JS 스크립트를 올리기 전이에요).
- 소셜피드 모드가 쓰는 메시지는 `mods/ai-social-feed`의 `mod.js`와 `python/bridge.py`(`main` 위쪽 주석)에 있어요. 처음 설계할 때 참고하세요.

## 5. PC 쪽 부분 (Python)

`mod.json`의 `python`이 가리키는 파일에 `run(ctx)`를 두면, 로더가 **모드를 켤 때 스레드로** 불러요 (로더가 게임을 기다리는 동안에도 돌아요).

```python
def run(ctx):
    ctx.log("시작")
    while not ctx.stop.wait(1.0):     # 멈추라고 하면 바로 빠져나오세요
        ...                           # 할 일

def status():                          # 선택. 앱이 모드 상태를 물을 때
    return {"ticks": 1}

def ui_hello(name):                    # 선택. 모드창에서 m24.call('hello', '이름')
    return "안녕, " + name
```

- `ctx.id`, `ctx.data_dir`(데이터 폴더), `ctx.stop`(`threading.Event`), `ctx.log(msg)`(loader.log에 `[<id>] msg`), `ctx.settings()`(설정 값 dict, 호출할 때마다 파일에서 읽어요), `ctx.game()`(코어 0.5.0, `{"date": "2035-04-25", "save": {"id", "nonce"}}`, 게임에 안 붙었으면 None), `ctx.save_dir()`(코어 0.5.0, 지금 세이브 전용 폴더 `<데이터 폴더>/saves/<세이브 id>/`, 세이브가 없으면 None). `ctx.game_dir()`(코어 0.31.0, 붙은 게임의 설치 폴더 = fm.exe 폴더, 원본 게임 자료를 읽을 때).
- 모드를 끄거나 로더를 멈추면 `ctx.stop`이 켜져요. **15초 안에 끝내세요.** `run`이 예외를 던지면 로더가 2초 뒤 **다시 시작**하고, 60초 안에 3번 실패하면 모드를 **자동으로 꺼요** (10절). 그래서 일시적인 오류(네트워크 등)는 `run` 안에서 직접 잡아서 처리하는 게 좋아요. 사용자 설정이 빠져서 못 도는 경우(API 키가 없는 경우 등)에는 예외를 던지지 말고 `ctx.stop.wait(2.0)`로 기다리세요 (소셜피드가 이렇게 해요).
- 같은 폴더의 다른 `.py` 파일은 그냥 `import`해요 (진입 파일이 있는 폴더가 `sys.path`에 들어가요). `.24mod`는 켤 때 `~/m24ga_data/cache/<id>-<version>/`에 **진입 파일이 있는 폴더(`python/`)만** 풀리고, zip이 바뀌었을 때만 다시 풀려요.
- 모드끼리 **모듈 이름이 겹치면**(예: 두 모드에 다 `config.py`) 나중에 켜는 모드가 막혀요. 이름에 모드 이름을 넣거나 패키지(폴더) 안에 넣으세요.
- 순수 Python 라이브러리는 `python/` 안에 같이 넣어 오세요. 배포용 exe에는 흔한 패키지만 들어가요. 없으면 `requires`로 알리세요.
- **공용 라이브러리 `pylib/` (코어 0.18.0):** 여러 모드가 같이 쓰는 라이브러리는 M24GA의 `pylib/`에 있고, 로더가 `sys.path` 끝에 넣어요 (모드 자기 모듈이 먼저). 지금 있는 것: `dpa`(FM24 Dynamic PA 0.9.5 모델·세이브 파일 읽기, GPL-3.0, 고치지 마세요), `m24hist`(세이브 파일에서 지난 2시즌 리그 기록 → 비교군 백분위, 캐시: `m24hist.load(save_id, 평가일, dpa.rules.validate(dpa.rules.DEFAULTS), 캐시 경로, ctx.log)` → `(prior, current, info)`). 쓰는 모드는 `core`를 `>=0.18.0`으로. 코어 0.19.0: `m24awards`(세이브의 상 역대 수상자와 대회 우승: `m24awards.load(save_id, 캐시)` → 기록 `[(연도, 상 번호, [(순위, 사람 번호, 팀 번호)])]`, `by_person(기록)` → `{사람 번호(player.link): [(연도, 상, 순위)]}`, `load_trophies(save_id, 시작 해, 캐시)` → `{"by_uid": {선수 UID: [(시즌 시작 해, 대회 번호)]}}`, 1분 안팎; 코어 0.20.0: `parse_best_elevens(경로)` → `[(시즌 시작 해, [(칸, 사람 번호, 경기, 골)], 목록 번호)]`, `best_eleven_teams(경로, 기록)` → `{목록 번호: 팀 번호}` (1분 안팎), `best_eleven_by_person(기록)` → `{사람 번호: [(해, 칸)]}` (구단·대표팀 시즌 베스트 일레븐). `parse_league_history(경로)` → `{"by_team": {팀 번호(db::TEAM +0x8): [{year(끝나는 해), comp, pos, teams, played, won, drawn, lost, gf, ga, pts}]}}` (팀 시즌 리그 성적, 리그 1~3위를 한 적 있는 팀만 이어짐). 연도: 수상·리그 성적은 끝나는 해, 우승·베스트 일레븐·선수 시즌 기록은 시작 해. 상·대회 번호의 이름은 게임 쪽 `awardInfo`/`compInfo`). 코어 0.22.0: `m24career`(사람별 경력 사건 기록: `m24career.load(save_id, 캐시)` → 기록 묶음, `.of(목록 번호, 종류)` → `[{year, date, kind, kind_name, team, person, comp, other_team, award, place, fee, …}]`, `.transfers(번호)` → `[(날짜, 떠난 팀, 새 팀, 이적료)]`, `.finals` 컵 결승, `.loans` 임대, `.league_finishes` 리그 결과(승격·강등), `.awards` 주간·월간·시즌 상, `.iter_kind(종류)` 전체에서 한 종류. 목록 번호는 게임 쪽 필드 `player.recordList` (사람 번호와 달라요), 종류 뜻은 `m24career.KINDS`, 1초 안팎). 출처는 `pylib/NOTICE.md`.
- **API 키 같은 비밀은 설정 파일에 쓰지 않는 걸 권장해요.** `password` 항목은 화면으로 값이 안 나가지만 파일에는 그대로 저장돼요. 소셜피드는 키를 따로 파일(`~/.deepseek_key`)에 두고 설정에는 파일 경로만 둬요.

## 6. 게임 빌드와 주소

게임이 업데이트되면 코드 주소가 바뀌어요. 그래서 로더는 올리기 전에 실행 중인 `fm.exe`의 코드 바이트와 값을 **서명**과 비교해요.

- 코어 주소는 로더의 `builds/*.json`이 가지고 있어요. 안 맞으면 **로더 전체**가 아무것도 올리지 않아요.
- 모드가 코어에 없는 주소를 쓴다면 모드 안에 `builds/<빌드>.json`을 넣어요. **안 맞으면 그 모드만** 꺼져요 (앱에 "이 게임 빌드에서 꺼 뒀어요"가 표시돼요).

```json
{"build": "FM24 Epic, fm.exe 2026-10-24 빌드",
 "sig": {"0x61ae80": "0100004889ce31d2e85362b00084c00f"},
 "vt":  {"0x56cc008": "64c350"}}
```

- `build`: 코어 빌드 파일의 `name`과 같은 글자. 모드 안 `builds/`에 `build`가 있는 서명이 하나라도 있는데 지금 빌드 것이 없으면 그 모드는 꺼져요.
- `sig`: `fm.exe` 기준 오프셋 → 그 자리 16바이트(소문자 16진수). `vt`: 오프셋의 포인터 값에서 `fm.exe` 기준 주소를 뺀 값 (16진수).
- 함수 안쪽을 `Interceptor`로 후킹하는 자리는 후킹이 덮어쓰기 전의 바이트와 비교하거나, 후킹보다 16바이트 뒤를 서명으로 쓰세요.

## 7. 모드창 (ui)

`ui`에 적은 HTML이 앱의 **모드창 탭** 안에 떠요. 보안을 위해 `sandbox="allow-scripts"` iframe 안에서 돌아서, 앱 화면이나 파일, 다른 모드에 직접 접근할 수 없어요. 모드와 통신하는 길은 하나뿐이에요.

```js
const r = await m24.call('greet', '민수');   // → 모드 Python의 ui_greet('민수')
m24.toast('저장했어요');                      // 앱 아래에 토스트
```

- `m24.call(이름, ...인자)`는 모드 Python의 `ui_<이름>(*인자)`를 불러요 (`[a-z][a-z0-9_]*`만, 이름 앞에 `ui_`가 붙은 함수만 불려요). 인자와 결과는 JSON으로 오가요. 예외는 `Error`로 와요.
- 모드의 Python 부분이 돌고 있을 때만 열려요 (모드가 꺼져 있거나 로더가 꺼져 있으면 안내 문구가 보여요). 켜지는 순간 자동으로 열려요.
- 로더가 **테마 CSS**를 넣어 줘요. 색은 변수예요: `--bg --card --blue --text --text2 --text3 --line --grey --red --amber ...`. 자주 쓰는 클래스: `.card`, `.card.list`, `.row`(`.name` `.hint` `.val`), `.stats`/`.stat`(`.label` `.value`), `.btn`(`.primary` `.ghost` `.grey` `.wide`), `.field`(입력 줄), `.switch`, `.seg`, `.pill`, `.badge`, `.sec-title`, `.empty`, `.cmt`. 전부 `loader/ui/theme.css`에 있어요.
- **모드가 만든 글자는 `textContent`로만 넣으세요** (`innerHTML`로 넣으면 글 속 HTML이 그대로 실행돼요).
- 글꼴(Pretendard)은 인터넷에서 불러오고, 없으면 맑은 고딕을 써요. 다른 외부 주소는 가급적 쓰지 마세요.

## 8. 사용자 데이터 위치

```
~/m24ga_data/
  enabled.json              {모드 id: true/false}
  loader.log                로더와 게임 안 스크립트 기록
  cache/<id>-<version>/     .24mod 안 Python 부분을 푼 곳
  <모드 id>/                모드 데이터 폴더 (settings.json 등)
  trash/                    앱에서 지우거나 새 버전으로 바꾼 .24mod (되살리려면 mods 폴더로 옮기세요)
문서\M24GA\mods\            .24mod 파일을 넣는 곳
```

## 9. 만들고 확인하는 순서

1. `python -X utf8 tools/m24.py new <id>`로 뼈대를 만들어요 (또는 `examples/hello`를 복사해서 `id`부터 바꿔요).
1b. `python -X utf8 tools/m24.py validate <폴더>`로 검사해요 (오류가 0이 될 때까지).
2. 폴더째로 모드 폴더에 넣고 앱에서 **새로 고침** (`.24mod`는 앱 왼쪽 아래 **모드 설치** 버튼으로 고르면 검사 후 설치돼요. 같은 id가 있으면 새 버전으로 바꾸고 옛 파일은 `trash/`로 가요. 지우려면 모드의 정보 탭 **모드 삭제**, 개발 폴더 모드는 앱이 지우지 않아요) → 모드가 목록에 나와요. `mod.json` 오류는 앱 홈 화면(빨간 알림)과 `loader.log`에 나와요.
3. 터미널로 확인할 수 있어요 (저장소 루트에서):
   - `python -X utf8 loader/host.py --list`: 찾은 모드와 상태
   - `python -X utf8 loader/host.py --check`: 게임에 붙어 빌드만 확인
   - `python -X utf8 loader/bundle.py out.js` 후 `node --check out.js`: 묶음 JS 문법 검사
4. 게임에서 확인하고, 다 되면 `tools/pack_mod.py`로 `.24mod`를 만들어요.
5. 게임 데이터를 읽는 모드는 **읽기부터** 만드세요. 게임 메모리를 쓰는 기능은 아직 코어 API가 없어요 (나중에 `mod.json`에 쓰기 선언을 요구할 예정이에요).

## 10. 안전장치: 자동으로 꺼짐과 안전 모드

모드가 말썽을 부려도 게임과 다른 모드를 지키도록 로더가 알아서 막아요. 모드 제작자는 이런 일이 생길 수 있다는 것만 알면 돼요.

| 상황 | 로더가 하는 일 |
|---|---|
| `mod.js`에 **문법 오류** | 올리기 전에 모드마다 문법만 검사해서 그 모드만 빼고 올려요. 코어와 다른 모드는 그대로 동작해요 |
| `mod.js`가 **올라가다 예외** (로드 실패) | 그 모드가 등록해 둔 것을 모두 거두고 자동으로 꺼요 |
| 게임 쪽 콜백(`socialPanel`, `frame`, `api.recv`)이 **5초에 25번 넘게 예외** | 코어가 그 모드의 콜백 호출을 멈추고(게임과 다른 모드는 영향 없음) 자동으로 꺼요 |
| Python `run(ctx)`가 **60초 안에 3번 예외로 끝남** | 두 번까지는 2초 뒤 다시 시작하고, 3번째에 자동으로 꺼요 |
| 게임이 **튕김** (종료 코드가 `0xC...`, 예: `0xC0000005`) 그때 모드가 올라가 있었음 | 다음 시작 때 **안전 모드**: 모드를 올리지 않고 시작해요. 앱 홈에 안내가 나오고, 모드를 **하나씩 켜 보며** 원인을 찾을 수 있어요. 문제가 없다고 보면 "안전 모드 끝내고 모드 모두 켜기" |

- 자동으로 꺼진 모드는 앱에서 **"자동으로 꺼짐"**으로 표시되고 이유와 시각이 나와요. 사용자가 스위치나 **다시 켜기** 버튼으로 켜면 기록이 지워지고 다시 시도해요. 기록은 `~/m24ga_data/autodisabled.json`이에요.
- 안전 모드는 게임이 튕긴 **한 번만** 걸려요. 튕긴 기록은 `~/m24ga_data/session.json`, `crashes.json`에 있어요. 종료 코드를 알 수 없는 경우(로더를 먼저 끈 경우 등)나, 모드가 한 번도 안 올라간 상태에서 튕긴 경우에는 걸지 않아요 (모드 탓이 아니니까요).
- 게임이 튕기는 원인이 모드가 아니라 코어나 게임 자체일 수도 있어요. 안전 모드에서도 튕기면 모드 탓이 아니에요.

### 모드별 로그 탭

앱에서 모드를 열면 **로그 탭**이 있어요. 그 모드의 기록을 시각, 출처(**JS** = `api.log`와 게임 쪽 오류, **PY** = `ctx.log`와 Python 오류와 스택, **로더** = 켜고 끔, 자동으로 꺼짐 등)와 함께 보여 줘요. 오류가 있으면 탭에 빨간 개수가 떠요. `오류만`으로 걸러 보고, `로그 복사`, `지우기`를 쓸 수 있어요. 최근 500개를 앱을 켠 동안만 보관해요 (전체 기록은 `~/m24ga_data/loader.log`). 문제가 있는 모드(자동으로 꺼짐, Python 오류)는 로그 탭이 먼저 열려요.

**`AI에게 줄 보고서 복사`**: 모드 상태, 자동으로 꺼진 이유, `validate` 결과, 최근 로그를 한 번에 복사해요. AI에게 붙여 넣고 원인을 찾아 고치게 하세요.

### 게임 값 쓰기 (코어 0.7.0, 필드 등록부 0.10.0)

쓸 수 있는 값은 [`FIELDS.md`](FIELDS.md)에서 **쓰기: safe**인 칸이에요 (선수 잠재력(PA), 감독 과거 경력 값, **선수 능력치 54개** `player.attr.*`(코어 0.42.0, M72): 능력치는 **저장 값 1~100**으로 써요 = 화면 값 × 5. 읽기 `getField`는 화면 값 1~20). `api.setField(obj, '이름', value, { expect, reason })` → `{ ok, before, after, name, error }`. `obj`는 게임 객체 또는 그 종류의 key(선수는 UID)예요. PA는 예전처럼 `api.setPlayerPA(uid, pa, { expect, reason })`로도 써요 (같은 확인·기록).

- 칸마다 필요한 기능이 있어요 (기본 `write.field`, PA는 `write.player.pa`). `mod.json`에 선언해야 하고, 사용자가 앱에서 허용해야 모드가 켜져요. 선언하지 않은 모드가 부르면 `ok: false`예요. `validate`는 없는 필드 이름과 읽기만 되는 칸 쓰기를 오류로 알려 줘요.
- 코어가 확인하는 것: 세이브를 불러왔는지, 같은 객체인지(종류의 key와 `check` 칸이 쓰기 전후 그대로인지, 선수는 UID·생년월일), 형식 범위와 칸의 `range`(PA 1~200), `gte`/`lte`(PA는 **CA보다 낮지 않게**), 정수 칸에는 정수만, `expect`를 줬다면 지금 값이 그 값인지, 모드마다 1분에 600번 이하인지. 하나라도 안 맞으면 쓰지 않고 이유를 `error`로 돌려줘요.
- 모든 쓰기는 `~/m24ga_data/writes.jsonl`에 기록되고(모드, 선수, 전→후, 세이브, 게임 날짜, `reason`), 모드 로그 탭에도 남아요. 앱의 모드 정보 탭에 **게임 값 쓰기 기록**과 **이 세이브에서 이 모드가 바꾼 값 되돌리기** 버튼이 있어요. 되돌리기는 최근 것부터, **지금 값이 모드가 쓴 값일 때만** 되돌려요 (그 뒤 게임이나 다른 모드가 바꾼 값은 건드리지 않아요).
- **게임을 저장하면 바꾼 값이 세이브 파일에 남아요.** 되돌린 뒤에는 다시 저장해야 해요. 중요한 세이브는 미리 복사해 두라고 사용자에게 안내하세요.
- 사람 데이터 객체에서 UID는 `personUid(o)` 또는 `playerInfo(playerOf(o)).uid`로 얻어요.

> 등록부에 없는 값이나 함수가 필요하면 [`EXTENDING.md`](EXTENDING.md)의 절차대로 `core/fields.json` / `core/functions.json`에 한 줄 더해요.

### 세이브별 모드 데이터 (코어 0.44.0, M82)

세이브마다 따로 두는 모드 자료(선수별 기록, 커리어 진행 등)는 `api.saveData`에 두세요. 기능 `save.data`를 선언해요 (허용 필요 없음).

```js
if (api.saveData.ready()) {
  var wins = api.saveData.get('wins', 0);
  api.saveData.set('wins', wins + 1);
}
```

- **게임을 저장할 때 확정**돼요 (`~/m24ga_data/savedata/<세이브 id>/<모드 id>/<키>.json`, 바뀐 키만).
- **저장하지 않고 같은 세이브를 다시 불러오면** 마지막 저장 때 값으로, **다른 세이브를 불러오면** 그 세이브의 값으로 돌아가요. 세이브를 되돌려도 모드 기록과 게임이 어긋나지 않아요.
- 값은 JSON으로 저장할 수 있는 것만, 값 하나 64MB·모드당 128MB까지. 키는 1~200자 글. **256KB가 넘는 값은 PC 쪽(Python) 전용**이에요 (JS `get`에서는 없음): 큰 기록은 Python에서 다루세요.
- `ready()`는 세이브를 불러와 자료가 준비됐을 때 true. 세이브를 바꾸면 `saveLoaded` 이벤트 뒤에 자료가 바뀌어요.
- 같은 모드의 Python은 `ctx.save_data().get/set/delete/keys/all`로 같은 자료를 봐요.
- 예전처럼 `ctx.save_dir()`(세이브별 폴더)에 직접 쓰는 자료는 저장·되돌리기를 따라가지 않아요. 되돌림이 중요한 자료는 saveData로 옮기세요.

### 속성 코드로 쓰기 (코어 0.42.0, M71)

`api.prop`으로 읽는 4글자 코드 중 쓰기가 확인된 것은 `api.setProp`으로 바꿀 수 있어요. 메모리 칸을 직접 고치지 않고 **게임 자신의 setter**(화면 편집과 같은 길)를 불러서, 게임이 값 자르기·바뀜 알림을 처리해요.

```js
api.setProp('myclub', 'Ctfc', 300000000, { reason: '이사회 추가 예산' }).then(function (r) {
  if (!r.ok) api.log('실패: ' + r.error); else api.log('이적 예산 ' + r.before + ' -> ' + r.after);
});
api.propInfo('PCAB').writable   // 'safe' | 'tested' | 'deny' | false
```

- 쓸 수 있는 코드: [`PROPERTIES.md`](PROPERTIES.md)의 "쓰기" 절. **safe** 56개(재정·시설·선수 CA/PA/명성/숨은 성향/키·몸무게·사기·경기 감각, 팀·대회 명성 등)는 그냥, **tested**(+1·되돌리기만 확인)는 `{ tested: true }`를 줘야 써져요.
- 대상: `api.prop`과 같아요(`'me'`·`'myteam'`·`'myclub'`·객체·`'p123'`). 기록 열쇠는 대상의 dref라서 게임을 다시 불러와도 되돌리기가 돼요.
- 정수·불리언·실수·날짜가 돼요. 날짜 코드는 `'YYYY-MM-DD'`로 쓰고, 결과 `before`/`after`도 날짜 글이에요.
- **계약**: 대상 `'contract:p123'`(선수) · `'contract:s45'`(스태프의 지금 구단 계약) · `'contract:me'`(= `'myjob'`, 내 감독)로 계약 속성(만료일 `Ceda` 등)을 읽고 써요 (M74). 주급은 setter가 받지 않아서 필드 `player.contract.wage` · `staff.contract.wage` · `human.contract.wage`를 `api.setField`로 써요 (내부 단위, 속성 `Cwwa`와 같음).
- 여러 개를 한 번에: `api.setProps('myclub', { Ctfc: 3e8, Cwwb: 9000000 }, { reason })` → Promise `{ok, results, error, rolledBack}`. 하나라도 실패하면 앞에서 바꾼 것을 거꾸로 되돌려요 (되돌림도 기록돼요). Python `ctx.set_props(대상, {코드: 값})`.
- 범위(`range`)와 관계(PA는 CA 이상, CA는 PA 이하)를 확인하고, 게임이 값을 다르게 자르면 원래 값으로 되돌리고 `ok: false`예요. 쓰는 중에 게임이 객체를 바꾸면(사람 종류 `Ptyp` 같은 코드, 등록부에서 막음) 실패로 알려요.
- 화면 스레드에서 돌아서 Promise예요. 기록·되돌리기·1분 600번 제한은 `setField`와 같아요. **저장하면 세이브에 남아요.**
- Python 모드: `ctx.set_prop('myclub', 'Ctfc', 300000000, reason='...')` (기능 `write.prop` 선언).

### 게임 함수 끼어들기 (코어 0.11.0)

[`core/functions.json`](../core/functions.json)에 등록된 게임 함수(목록 [`FUNCTIONS.md`](FUNCTIONS.md))에 끼어들어요. 기능 `hook.function`을 선언하고 사용자 허용을 받아야 해요.

```js
var h = api.hook('player.updateAskingPrice', {
  before: function (ev) { ev.data.t = Date.now(); },                       // 함수가 불리기 직전
  after: function (ev) { api.log((Date.now() - ev.data.t) + 'ms, 부른 곳 ' + ev.caller); }   // 함수가 끝난 직후
});
if (!h.ok) api.log(h.error);   // 모르는 함수, 코어 전용 함수, 서명이 이 빌드와 다름
```

- `ev.args`(functions.json의 `args` 형식대로 바꾼 인자), `ev.raw(i)`(원래 포인터, 등록된 것보다 뒤 인자도), `ev.caller`(`'fm+0x...'`), `ev.tid`, `ev.data`(before → after로 넘길 칸), after에서 `ev.ret`.
- **끼어들기: modify**로 확인된 함수만 `ev.setArg(i, v)`(before) / `ev.setRet(v)`(after)로 바꿀 수 있어요. observe 함수에서 부르면 오류예요 (`validate`가 경고해요).
- 코어가 함수마다 **하나만** 걸고 여러 모드에 나눠 줘요. 한 모드의 콜백 오류는 그 모드 안에서 막히고(반복되면 그 모드만 꺼짐), 모드를 내리면 자동으로 떼요. 마지막 모드가 떼면 후킹도 풀려요. `h.stop()`으로 직접 뗄 수도 있어요.
- 콜백은 **게임 스레드**에서 불려요. 오래 걸리면 게임이 느려지니 짧게 하고, 무거운 일은 `api.send`로 Python에 넘기세요. CLI `hooks`로 모드별 호출 수·오류·걸린 시간을 봐요.
- 코어가 이미 걸어 둔 함수(`owner: core`, 예: 매 프레임)는 걸 수 없어요. `api.on('frame')` 같은 이벤트를 쓰세요.
- 등록되지 않은 함수에 직접 `Interceptor`를 거는 것(`raw.hook`)은 여전히 되지만 서명 확인·정리·오류 격리가 없어요. 찾은 함수는 functions.json에 등록해서 쓰세요 (찾는 법: CLI `watch-write`·`watch-call`, [`CLI.md`](CLI.md)).

## 11. 기능 등록부와 권한 (코어 0.4.0)

코어가 모드에 열어 주는 기능은 [`core/capabilities.json`](../core/capabilities.json)에 하나씩 등록돼 있어요 (사람용 목록: [`CAPABILITIES.md`](CAPABILITIES.md)). 기능마다 이름, **위험 등급**, 지원하는 게임 빌드가 있어요.

- 모드는 `mod.json`에 쓰는 기능을 적어요: `"capabilities": ["event.socialPanel", "read.data", "ui.social.text"]`.
- `validate`는 `mod.js`에서 실제로 쓰는 기능을 찾아서 **선언하지 않고 쓰면 오류**, 모르는 이름이면 오류(비슷한 이름 제안), `capabilities`가 아예 없으면 경고(넣을 목록을 알려 줌)를 내요.
- 로더는 **선언한 것과 코드에서 찾은 것을 합쳐서** 그 모드의 기능으로 봐요.
  - `read`(읽기), `ui`(화면 글자): 그냥 켜져요.
  - `pc`(Python 부분, 파일), `raw`(`ptr`, `.readU32` 같은 직접 읽기, `NativeFunction`), `hook`(`Interceptor`), `write`(메모리 쓰기): **사용자가 앱에서 허용해야 켜져요.** 허용 전에는 "권한 필요"로 표시되고 정보 탭에 무엇을 하는 기능인지 나와요. 새 버전이 위험 기능을 더 쓰면 다시 물어요.
  - 기능이 지금 게임 빌드에서 안 되면 그 모드만 "이 게임 빌드와 안 맞음"으로 꺼져요 (어떤 기능이 문제인지 같이 나와요).
- 허용 기록은 `~/m24ga_data/permissions.json`이에요. 앱에서 모드를 지우면 그 모드의 허용도 지워져요. 0.4.0으로 처음 올렸을 때는 그때 켜 둔 모드의 기능을 허용한 것으로 한 번 기록해요 (쓰던 모드가 갑자기 꺼지지 않게).
- **이건 샌드박스가 아니에요.** 모드 JS는 코어와 같은 스크립트에서 돌고, Python은 PC에서 그대로 돌아요. 기능 찾기는 글자 모양으로 하므로 일부러 숨기면 못 찾아요. 목적은 사용자에게 알리고 동의를 받는 것, 모드 제작자와 AI에게 쓸 수 있는 기능을 정확히 알려 주는 것이에요.
- 코어에 새 기능이 생기면 등록부에 먼저 추가돼요. 등록부에 없는 기능은 코어에 없는 거예요.

## 12. 신뢰와 라이선스

- 모드는 게임 메모리와 사용자 PC에서 **임의 코드를 실행**해요. 출처를 아는 모드만 설치하세요. 모드를 배포한다면 무엇을 하는지 설명에 적어 주세요.
- M24GA 코어는 **GPL-3.0-or-later**예요. 모드가 코어 코드와 한 스크립트에서 함께 돌기 때문에, 모드도 GPL 호환 라이선스를 쓰는 걸 권장해요. (법률 조언은 아니에요. 확실하지 않으면 라이선스를 직접 확인하세요.)
