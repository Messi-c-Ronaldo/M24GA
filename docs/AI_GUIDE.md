# M24GA AI 모딩 가이드

**한국어** | [English](en/AI_GUIDE.md)

이 문서는 **AI에게 모드를 시키는 사람**과 **모드를 만드는 AI** 둘 다를 위한 거예요. 참고서([MODDING.md](MODDING.md))보다 짧고, "무엇이 되고 안 되는지, 어떻게 틀리는지"에 집중해요.

코어 버전 **0.44.0** 기준이에요. 코어가 아직 0.x라서 함수 이름이 바뀔 수 있어요.

---

## 1. 사람에게: AI에게 이렇게 시키세요

아래를 AI(Claude Code, Cursor, ChatGPT 등)에게 붙여 넣고, `<...>` 부분만 채우세요. M24GA 폴더 위치가 다르면 경로를 바꾸세요.

**새 모드를 만들 때**
```
M24GA(FM24 모드 로더)용 모드를 만들어 줘.
1. C:\Program Files\Epic Games\M24GA\docs\AI_GUIDE.md 를 끝까지 읽어.
2. python -X utf8 "C:\Program Files\Epic Games\M24GA\tools\m24.py" new <모드id> --dir "<모드를 만들 폴더>" [--python] [--ui]
   로 뼈대를 만들고 거기서 시작해. (--python = PC 쪽 처리 필요, --ui = 앱 안 화면 필요)
3. 만들고 싶은 모드: <원하는 것을 자세히>
4. 코어에 없는 기능이 필요하면 지어내지 말고 "아직 없다"고 말해 줘.
5. 고친 뒤에는 매번 tools\m24.py validate 를 돌려서 오류를 0으로 만들고, 결과를 보여 줘.
```

**있는 모드를 고칠 때**
```
이 폴더의 M24GA 모드를 고쳐 줘. 먼저 이 폴더의 AGENTS.md 와 그 안에 적힌 AI_GUIDE.md 를 읽어.
고치고 싶은 것: <원하는 것>
고친 뒤에는 validate 를 돌려서 오류를 0으로 만들어.
```

**잘 안 될 때** 앱에서 모드를 열고 **로그 탭 → "AI에게 줄 보고서 복사"**를 누른 뒤 AI에게 붙여 넣으세요. 모드 상태, 자동으로 꺼진 이유, `validate` 결과, 최근 로그(오류 스택 포함)가 한 번에 들어 있어요. 이 보고서를 주고 "원인을 찾아서 고쳐 줘"라고 하면 돼요. (보고서에는 내 PC의 모드 폴더 경로가 들어 있어요.)

---

## 2. AI에게: 작업 규칙

1. **추측하지 마세요.** 이 문서, [`types/m24ga.d.ts`](types/m24ga.d.ts)(게임 쪽 JS), [`types/m24ga.pyi`](types/m24ga.pyi)(Python), [`examples/hello`](../examples/hello)에 없는 함수나 항목은 **없는 거예요.** 있을 것 같아서 쓰지 마세요.
2. **작게 만들고 매번 검사하세요.** 한 번에 다 쓰지 말고, 뼈대 → 읽기 → 화면/설정 → 다듬기 순서로 하고 단계마다 `validate`를 돌리세요.
3. **검사 출력을 믿고 고치세요.** `validate`의 `[오류]`는 위치와 "고치려면"이 같이 나와요. 오류가 0이 될 때까지 고치세요. 경고는 이유를 읽고 필요한 것만 고치세요.
4. **되지 않는 것을 요청받으면 정직하게 말하세요.** 4절의 "지금 없는 것"에 있으면 "코어에 아직 없어서 모드로는 못 한다"고 답하고, 가능한 대안을 제안하세요. 억지로 게임 메모리를 건드리는 코드를 쓰지 마세요.
5. **게임을 지키세요.** 게임 객체는 `lookup`으로 확인한 뒤에만 읽고, 게임 쪽 코드는 `try/catch`로 감싸고, 실패하면 **아무것도 바꾸지 않고** 넘어가세요. 잘못된 주소 하나로 게임이 튕겨요.
6. **쓰는 기능을 선언하세요.** [`CAPABILITIES.md`](CAPABILITIES.md)에서 필요한 기능의 이름을 찾아 `mod.json`의 `"capabilities"`에 적어요. 선언 없이 쓰면 `validate`가 오류를 내요. `read`/`ui` 등급은 그냥 켜지지만 `pc`(Python), `raw`(`ptr`, `.readU32` 같은 직접 읽기), `hook`(`Interceptor`), `write`(메모리 쓰기)는 **사용자가 앱에서 허용해야 켜져요.** 코어 함수로 되는 일은 코어 함수로 하세요.
7. **모르면 사용자에게 물어보세요.** 특히 "어느 화면의 어떤 글"을 바꾸고 싶은지가 불분명하면 먼저 물어보세요.

---

## 3. 파일 구성과 규칙

```
<모드폴더>/
  mod.json          이름, 버전, 설정 항목 (설정 화면은 여기서 자동으로 만들어져요)
  mod.js            게임 안에서 도는 JS (Frida). registerMod를 쓰지 않아요
  python/main.py    PC 쪽 (선택). run(ctx)와 ui_이름() 함수
  ui/index.html     앱 안 모드창 (선택). Python의 ui_이름()을 m24.call('이름')으로만 불러요
```

**mod.js (게임 쪽)**
- `api`와 `DIR`이 이미 있어요. `registerMod`, `require`, `import`, `document`, `window`, `fetch`는 못 써요.
- 변수는 **항상 `var`로 선언**해요 (`var` 없이 대입하면 코어나 다른 모드의 변수를 덮어써요).
- 로그는 `api.log('...')`. `console.log`는 안 보여요.
- 화면을 그리는 스레드에서 불리는 콜백(`socialPanel`, `frame`)은 **빨리 끝내요.** 느린 일은 Python에 `api.send`로 맡겨요.

**python/main.py (PC 쪽)**
- `def run(ctx):`를 만들고, `ctx.stop`이 켜질 때까지 일해요 (`while not ctx.stop.is_set():`). 끄면 15초 안에 끝나야 해요.
- 네트워크 호출(AI API 등), 파일 처리는 여기서 해요. 로그는 `ctx.log('...')`.
- 설정은 `ctx.settings()["키"]`. 호출할 때마다 파일에서 읽어서 사용자가 앱에서 바꾸면 바로 반영돼요.

**mod.json**
- 설정 항목 종류: `bool`, `int`, `number`, `text`, `password`, `select`. 자세한 건 [MODDING.md 3절](MODDING.md)과 [`mod.schema.json`](mod.schema.json).
- `mod.json` 맨 위에 `"$schema": "<mod.schema.json 경로>"`를 적으면 편집기가 자동완성과 오류 표시를 해 줘요 (새 모드 뼈대에는 이미 들어 있어요).

**ui/index.html (모드창)**
- 화면을 `m24.call('이름', 인자...)`로 Python의 `ui_이름(인자...)`에 물어서 그려요. `ui_` 함수 이름과 `m24.call('이름')`이 **정확히 같아야** 해요.
- 글자는 **`textContent`로만** 넣어요 (`innerHTML` 금지, 모드나 AI가 만든 글에 HTML이 있으면 실행돼요).
- 앱의 모양(`.card`, `.btn`, `.stat`, `.field` ...)은 로더가 자동으로 넣어 줘요.

---

## 4. 지금 되는 것 / 없는 것

**지금 되는 것** (코어 0.44.0, 이름과 등급은 [`CAPABILITIES.md`](CAPABILITIES.md))

| 하고 싶은 것 | 방법 |
|---|---|
| 소셜피드의 글을 읽기 | `api.on('socialPanel', ev => ...)`의 `ev.text`, `ev.type` (0 제목, 2·4 팬 댓글, 3·5 공식 글) |
| 소셜피드의 글을 바꾸기 | `setStr(ev.dst, '새 글')` 후 `refreshPanel(ev.th)` (**화면 스레드의 콜백 안에서만**) |
| 글에 나온 클럽·선수·감독의 게임 데이터 읽기 | `linkIds(text)` → `lookup(clubs/persons/staff, idx, VT)` → `getVal` / `getInt` (5절의 필드표) |
| 선수의 현재 능력(CA)·잠재력(PA)·생년월일 | `playerInfo(playerOf(lookup(persons, idx, PERSON_VT)))` (모든 선수: `playerUids()` + `playerByUid`) |
| 선수의 이번 시즌 기록(대회별)·xG·포지션·성격·소속 리그 | `playerSeason(p, 'league')`, `playerSeasonDetail(p)`, `playerPositions(p)`/`playerPosition(p)`, `playerTraits(p)`, `playerTeam(p)` (p = `playerByUid(uid)`) |
| 선수 능력치 54개 (기술·정신·신체·GK·숨은 값·양발) | `getField(p, 'player.attr.crossing')` … (1~20, 목록 [`FIELDS.md`](FIELDS.md) `player.attr.*`), CLI `get player:<uid> player.attr.` |
| 선수 객체에서 속성(`getVal`) 읽기 | `getVal(personOf(p), 'PCRP')` (코어 0.9.0) |
| 등록된 게임 값을 이름으로 읽기 (몸값·시즌 기록·포지션·클럽 이름 …) | `getField(findObj('player', uid), 'player.askingPrice')` (코어 0.10.0, `read.field`, 목록 [`FIELDS.md`](FIELDS.md), CLI `fields`) |
| 쓰기가 확인된 게임 값 바꾸기 | `api.setField(obj, 'player.pa', 150, { expect: 149, reason })` (FIELDS.md의 **쓰기: safe**만, 그 칸의 쓰기 기능 + 사용자 허용, 기록·되돌리기) |
| 게임 함수가 불릴 때 알기 / 인자·반환값 보기 | `api.hook('player.updateAskingPrice', { before(ev), after(ev) })` (코어 0.11.0, `hook.function`, 목록 [`FUNCTIONS.md`](FUNCTIONS.md), CLI `functions`; modify 함수만 `ev.setArg`/`ev.setRet`) |
| 게임 객체가 무슨 클래스인지 | `className(obj)` → `'db::ACTUAL_PLAYER'`, `isA(obj, 'db::PERSON')`, `rttiInfo(obj)` (코어 0.9.0, `read.rtti`) |
| 소셜 패널의 스레드·지금 글·작성자 응원팀 | `panelThread(th)`, `panelText(th)`, `panelFanUid(th)`, 저장해 둔 패널 다시 찾기 `panelAt(addr, type)` |
| **아무 게임 값이나 4글자 속성 코드로 읽기** (팀·구단·선수·스태프·감독·대회·상·국가·경기장·계약…) | `api.prop('myteam', 'TpoN')`, `api.props('myclub', { re: '^Cc' })`, 링크 따라가기 `api.deref(v)`, Python `ctx.props('me')` (코어 0.36.0~0.39.0, `read.prop`, 등록부 2,300여 개 [`PROPERTIES.md`](PROPERTIES.md)). **코드를 모르면** 게임 화면에 보이는 값으로 `cli.py prop-find <대상> <값>`, 목록은 `cli.py prop-info <정규식>` |
| **속성 코드로 게임 값 바꾸기** (구단 잔고·예산·시설, 선수 CA·PA·명성·숨은 성향·사기, 팀·대회 명성…) | `api.setProp('myclub', 'Ctfc', 값, {reason})` → Promise, Python `ctx.set_prop` (코어 0.42.0, `write.prop`, 사용자 허용). 쓸 수 있는 코드는 [`PROPERTIES.md`](PROPERTIES.md) "쓰기" (safe 56개, tested 221개는 `{tested: true}`). 기록·되돌리기 됨 |
| **세이브마다 따로 두는 모드 자료** (활약 기록, 커리어 진행) | `api.saveData.get/set` (Python `ctx.save_data()`, 코어 0.44.0, `save.data`): 게임 저장 때 확정, 저장 없이 다시 불러오면 되돌림. `ctx.save_dir()`에 직접 쓰면 되돌림을 안 따라가요 |
| 경기 결과(점수), 뉴스의 관련 사람·팀 | `api.on('matchEnded', ev => ...)` (`ev.home/away/homeGoals/awayGoals`), `api.on('newsAdded', ev => ev.refs())` (코어 0.37.0, [`NEWS.md`](NEWS.md)) |
| 게임 명령(액션) 목록 — 관심 목록 넣기, 이적 제의, 휴가 … | [`ACTIONS.md`](ACTIONS.md), CLI `actions <정규식>`. 모드: `api.actionsFor(대상)` 지금 쓸 수 있는 명령 (read.action), `api.action(id, 대상, {event})` 실행 (game.action, 사용자 허용) — 코어 0.41.0 |
| 확인된 속성 코드 목록 | [`PROPERTIES.md`](PROPERTIES.md) (뜻 `ko`가 있는 것만 화면과 맞춰 봤어요. 나머지는 값을 직접 확인) |
| 선수 잠재력(PA) 바꾸기 | `api.setPlayerPA(uid, pa, { expect, reason })` (기능 `write.player.pa`, 사용자 허용 필요, 모든 쓰기가 기록되고 앱에서 되돌릴 수 있음, 결과의 `ok`·`error`를 꼭 확인) |
| 내 감독과 클럽 | `myInfo()` |
| 게임 날짜, 날짜가 바뀔 때 | `gameDate()`, `api.on('dateChanged', ev => ...)` (Python: `ctx.game()['date']`) |
| 세이브 구분, 세이브를 불러올 때 | `saveInfo()`, `api.on('saveLoaded', ...)`, Python `ctx.save_dir()` (세이브별 폴더) |
| 주기 작업 | `api.every(ms, fn)`, `api.after(ms, fn)` (모드를 끄면 자동으로 멈춤) |
| 팬이 응원하는 팀 | `fanClub(uid)` |
| 앱에 설정 화면 | `mod.json`의 `settings` (JS는 `api.settings()` / `api.onSettings(fn)`, Python은 `ctx.settings()`. 설정 파일을 직접 읽지 마세요) |
| 앱 안에 모드창 | `ui/index.html` + Python의 `ui_` 함수 |
| PC 쪽 처리 (인터넷 API, 파일) | `python/main.py`의 `run(ctx)` |
| 게임 쪽 ↔ PC 쪽 통신 | JS `api.send` / `api.recv` ↔ Python `ctx.recv` / `ctx.post` |
| 모드를 끌 때 정리 | `api.onUnload(fn)`: 직접 건 `Interceptor`·`setInterval`·바꾼 글자를 치워요. 끄고 켜도 게임 데이터 표는 그대로예요 |
| mod.js 고친 뒤 바로 적용 | 앱 정보 탭 **게임 쪽 다시 올리기** (게임 재시작 필요 없음. Python은 앱 재시작) |

**게임을 조사할 때 (모드 코드가 아니라 개발 도구):** `cli.py explore player:<uid>`는 객체를 8바이트씩 펼쳐서 포인터가 가리키는 객체의 클래스 이름·글·날짜를 붙여 보여 줘요 (`/+0x130`으로 따라가기). `cli.py classes <정규식>`은 게임의 클래스 이름 1만여 개에서 찾아요. 찾은 칸은 `core/fields.json`에 한 줄 등록하면(확인 근거와 함께, 모르면 `verified: false`) 모든 모드가 `getField`로 읽어요. 등록 전에는 `raw.read`가 필요해요. `cli.py get player:<uid> player.season.league.`로 등록된 칸을 게임에서 바로 확인할 수 있어요. 새 칸은 `cli.py find-field <대상>=<화면 값> <다른 대상>=<값>`(공통 칸 + 등록 초안), 그 칸을 바꾸는 게임 함수는 `cli.py watch-write <대상> <칸>`으로 찾고 (M21, 게임을 저장하고), 그 함수의 인자·호출자는 `cli.py watch-call <함수|fm+0x주소>`로 봐요 (M22). 확인한 함수는 `core/functions.json`에 등록해요.

**등록부에 없는 값·함수가 필요하면** 모드에 전용 코드를 넣지 말고 등록부에 한 줄 더하는 절차를 따르세요: [`EXTENDING.md`](EXTENDING.md) (칸 찾기 → 등록 → 확인 → 쓰기까지 열기, 함수 찾기 → 인자 확인 → 등록).

**지금 없는 것** (있다고 가정하지 마세요. 요청받으면 "코어에 아직 없다"고 말하세요)
- FIELDS.md의 **쓰기: safe** 칸이나 PROPERTIES.md의 `safe`/`tested` 코드가 아닌 게임 값 쓰기 (다른 종류의 주급, 이적료, 경기 결과 ...)
- 새 게임 화면·버튼·메뉴 만들기
- 게임 계산 바꾸기 (경기 결과, 이적, 성장 ...)
- `socialPanel`, `frame`, `dateChanged`, `saveLoaded`, `newsAdded`, `matchEnded`, `gameSaved` 말고 다른 **이벤트** (경기 중 골·카드, 화면 전환 ...)
- 소셜피드가 아닌 화면(기자회견, 이적 화면 ...)의 글 읽기
- FUNCTIONS.md에 없는 게임 함수에 안전하게 끼어들기 (`Interceptor` 직접은 `raw.hook`, 정리·격리 없음), modify가 아닌 함수의 인자·반환값 바꾸기

---

## 5. 게임 데이터 읽기 치트시트

**순서:** `api.prepareData(ev.th)`(처음 한 번 표 만들기, 1~2분) → `mapsReady`가 `true`가 된 뒤 읽기.

```js
api.on('socialPanel', function (ev) {
  try {
    api.prepareData(ev.th);
    if (!mapsReady) return;                       // 표를 만드는 중이면 건너뛰어요
    linkIds(ev.text).forEach(function (e) {       // e = { name, type, idx }
      if (e.type === 0x18) {                      // 0x18 = 클럽, 0x01 = 사람
        var club = lookup(clubs, e.idx, CLUB_VT); // 항상 lookup으로 꺼내요 (같은 객체인지 확인해 줘요)
        if (!club) return;
        var rank = getInt(club, 'TpoN');          // 리그 순위. 없으면 null
        if (rank !== null) api.log(e.name + ' 순위 ' + rank);
      }
    });
  } catch (x) { /* 실패하면 아무것도 바꾸지 않아요 */ }
});
```

**알려진 필드 코드** (소셜피드 모드 작업에서 확인한 것만. 다른 코드는 모르는 거예요)

| 대상 | 코드 | 뜻 |
|---|---|---|
| 클럽 | `Tomp` | 시즌 경기 수 |
| 클럽 | `TpoN` | 리그 순위 |
| 클럽 | `Tlgs` / `Tlgc` | 리그 득점 / 실점 |
| 클럽 | `Cmxp` | 미디어 예상 순위 |
| 클럽 | `Tnts` | 이적 순지출 (게임 내부 금액) |
| 클럽 | `Tfrm` | 최근 경기 결과 배열 (값 0~3, 마지막이 가장 최근. `fanClub()`가 뒤집어서 [0]이 최근) |
| 선수/인물 | `Page` | 나이 |
| 선수/인물 | `PAap` / `PAcg` | 통산 출전 / 통산 골 |
| 선수/인물 | `PCRP` | 명성 |
| 선수/인물 | `Pnam` | 이름 객체 (`.Pfna`가 통칭, `personName()`이 대신 해 줘요) |
| 감독/스태프 | `Page`, `Nptk`, `Npmm`, `Npde`, `Ncrr` | 나이, 전술 지식, 선수 관리, 결단력, 감독 명성 |

값이 `null`이면 그 객체에 없는 속성이에요. 에러가 아니라 정상이니 건너뛰세요. 코드 의미를 모르면 **추측해서 읽지 말고** 사용자에게 알려 주세요.

---

## 6. 자주 쓰는 패턴

**PC 쪽에서 무거운 일(AI 호출 등)을 하고 결과를 게임 쪽에 돌려주기**

```js
// mod.js
var results = {}, sent = {};
api.recv(function (m) {
  if (m.t === 'res') results[m.k] = m.v;
  if (m.t === 'ready') { for (var k in sent) if (!(k in results)) api.send({ t: 'req', k: k, text: sent[k] }); }   // 답 없는 요청 다시 보내기
});
function ask(k, text) { sent[k] = text; api.send({ t: 'req', k: k, text: text }); }
api.send({ t: 'hello' });                          // 연결 직후, Python이 ready로 답해요
```
```python
# python/main.py
def run(ctx):
    while not ctx.stop.is_set():
        m = ctx.recv(0.5)
        if m is None:
            continue
        if m.get("t") == "hello":
            ctx.post({"t": "ready"})
        elif m.get("t") == "req":
            ctx.post({"t": "res", "k": m["k"], "v": "결과: " + m["text"]})   # 여기서 AI API 등을 불러요
```

핵심: 메시지는 **유실될 수 있어요** (게임이 안 붙어 있거나 스크립트가 다시 올라가면 버려져요). 그래서 `hello` → `ready` 핸드셰이크로 상태를 맞추고, 답이 없는 요청은 다시 보내고, Python은 같은 요청을 두 번 받아도 괜찮게 만드세요. 실제 사용 예는 `mods/ai-social-feed`예요.

**설정 값을 게임 쪽 JS가 쓰기**: 설정 파일은 Python이 읽어요 (`ctx.settings()`). JS는 파일을 읽지 않고, Python이 `ctx.post({"t": "cfg", ...})`로 보내 주게 하세요. 값이 바뀔 때마다 보내면 앱에서 바꾼 설정이 바로 반영돼요.

---

## 7. 흔한 실수와 증상

| 증상 | 원인 | 해결 |
|---|---|---|
| 모드가 앱 목록에 없다 | `mod.json`이 없거나 JSON 문법 오류, 폴더 위치가 틀림 | `validate`, 모드 폴더(`문서\M24GA\mods`)에 있는지, 앱에서 **새로 고침** |
| "켤 수 없음" | `mod.json` 오류(필수 항목, 파일 없음, core 조건) | 앱 홈의 빨간 알림 또는 모드 정보 탭, `validate` |
| 켰는데 게임에서 아무 일도 없다 | 로더가 꺼져 있다 / 게임이 아직 안 붙었다 / 표를 만드는 중 | 홈의 큰 버튼, `loader.log`, `mapsReady` 확인. **이미 그려진 소셜 글은 화면을 나갔다 다시 들어와야** 바뀌어요 |
| 모드창에 "아직 실행 중이 아니에요" | Python 부분이 안 돌고 있다 | 로더를 켜기, `loader.log`에서 `[모드id] Python 오류` 찾기 |
| 모드창에서 `ui_... 함수가 없음` | `m24.call('이름')`과 `def ui_이름`이 다름 | 이름을 맞추기 (`validate`가 잡아 줘요) |
| 모드가 켜자마자 "Python 오류" | `run(ctx)` 없음, import 실패, 예외 | `loader.log`의 스택 |
| 앱에 "자동으로 꺼짐" + 이유 | 로더가 오류 반복을 감지해 껐다: 문법 오류, 로드 중 예외, 5초에 25번 넘는 콜백 예외, Python이 60초에 3번 예외 | 이유 문구와 `loader.log`의 스택을 읽고 고친 뒤 **다시 켜기**. 모든 콜백을 `try/catch`로 감싸고, 설정이 빠져서 못 도는 건 예외 대신 `ctx.stop.wait(2.0)`로 기다리기 |
| 게임이 튕긴 뒤 모드가 하나도 안 올라온다 | **안전 모드** (게임이 모드가 올라간 채 튕겼다) | 앱 홈 안내를 읽고 모드를 하나씩 켜서 원인 찾기. 코드는 `lookup`으로 확인한 객체만 읽는지 점검 |
| 모드를 끄고 켠 뒤 이미 열려 있던 화면의 글이 그대로다 | 코어 0.3.0부터 표는 그대로지만, 다시 올라온 모드는 그 뒤에 그려지는 글부터 바꿔요 | 그 화면을 나갔다 다시 열기. 앱 M24GA를 처음 켤 때만 표를 1~2분 만들어요 |
| 모드를 끄고 켰는데 Interceptor·타이머가 두 번 돈다 | 모드가 직접 건 것은 코어가 모르니 내릴 때 남아요 | `api.onUnload(fn)`에서 `listener.detach()`, `clearInterval(t)` 하기 (`validate`가 경고해요) |
| 설정을 바꿔도 JS가 모른다 | JS는 설정 파일을 안 읽어요 | Python이 `ctx.post`로 보내기 (6절) |
| 메시지가 안 온다 | `ctx.post`가 `False` (게임이 안 붙어 있음), 또는 유실 | `hello`/`ready`와 재전송 패턴 |
| 게임이 튕겼다 | 확인 안 한 객체를 읽음, 원시 메모리 접근 | `lookup`으로만 꺼내고 `try/catch`, 원시 접근 금지 |
| "지원하지 않는 게임 버전" | 게임이 업데이트돼서 코어 주소가 안 맞음 | 코어 업데이트를 기다리기 (모드 문제가 아니에요) |

---

## 8. 디버깅 순서

1. `python -X utf8 tools\m24.py validate <모드폴더>`: 구조 오류는 대부분 여기서 잡혀요.
2. 앱에서 **새로 고침** → 모드를 켜기 → 로더를 켜기.
3. 앱에서 그 모드를 열고 **로그 탭**을 보세요 (오류가 있으면 탭에 빨간 개수가 떠요. "오류만"으로 걸러 볼 수 있어요). 전체 기록은 `~\m24ga_data\loader.log`예요: `game: ...` = 게임 쪽 JS(`api.log`와 오류), `[모드id] ...` = Python(`ctx.log`와 오류).
4. 한 번에 하나만 바꾸고 다시 확인하세요.
5. **AI 에이전트는 화면 대신 CLI로 확인하세요** ([`CLI.md`](CLI.md)): 사용자가 앱을 켜 두면 `python -X utf8 loader\cli.py status --json`(연결·게임 날짜), `rescan`/`enable <id>`(새 모드 올리기), `reload <id>`(mod.js 고친 뒤 바로 반영), `log <id> --json`, `report <id>`가 앱의 로더에서 실행돼요.
6. (선택) `mod.js` 맨 위의 `// @ts-check`와 `/// <reference ...m24ga.d.ts />`가 있으면 VS Code에서 없는 함수나 틀린 인자를 바로 빨간 줄로 보여 줘요.

---

## 9. 안전

- 모드는 게임 메모리와 사용자 PC에서 코드를 실행해요. **출처를 모르는 모드를 설치하지 마세요.** AI가 만든 코드도 읽어 보고 켜세요.
- 앱은 모드를 켜기 전에 위험한 기능(PC에서 코드 실행, 메모리 직접 읽기·쓰기, 함수 가로채기)을 **사용자에게 보여 주고 허용을 받아요.** 이건 안내와 동의 장치이지 샌드박스가 아니에요: 코드를 숨기면 못 찾을 수 있으니 믿을 수 있는 모드만 허용하세요.
- 게임 값 쓰기(`api.setProp`, `api.setField`, `api.setPlayerPA`, `api.action`)는 게임을 저장하면 세이브에 남아요. **세이브를 먼저 백업**하고, 반자동 탐색(`verify`)은 **시험 세이브에서만** 쓰세요.
- API 키는 모드 파일에 넣지 말고, 키는 별도 파일에 두고 설정에는 경로만 두세요 (`mods/ai-social-feed` 방식).
