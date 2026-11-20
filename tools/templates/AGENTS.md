# AGENTS.md: 이 모드를 고치는 AI에게

이 폴더는 **M24GA**(FM24 모드 로더)의 모드 하나예요. 코드를 고치기 전에 아래를 지키고, 모르는 것은 **지어내지 말고** 문서를 읽거나 사용자에게 물어보세요.

## 먼저 읽을 것
1. `{{ROOT}}\docs\AI_GUIDE.md`: 규칙, 할 수 있는 것/없는 것, 흔한 실수. **반드시 먼저 읽어요.**
2. `{{ROOT}}\docs\MODDING.md`: 자세한 참고서 (mod.json, 설정, api, Python, 모드창)
3. `{{ROOT}}\docs\CAPABILITIES.md`: 쓸 수 있는 **기능 목록과 이름**. 쓰는 기능은 `mod.json`의 `"capabilities"`에 적어요.
   게임 값 이름은 `{{ROOT}}\docs\FIELDS.md`(읽기·쓰기가 되는 칸), 끼어들 수 있는 게임 함수는 `{{ROOT}}\docs\FUNCTIONS.md`.
4. `{{ROOT}}\docs\types\m24ga.d.ts`(게임 쪽 JS)와 `m24ga.pyi`(Python): 쓸 수 있는 함수의 정확한 목록. **여기에 없는 함수는 없는 거예요.**
5. `{{ROOT}}\examples\hello\`(설정 종류, 메시지, 모드창)와 `{{ROOT}}\examples\field-hook\`(설정 읽기, 게임 값 읽기, 함수 끼어들기): 동작하는 예제

## 파일 구성
- `mod.json`: 이름, 버전, 설정 항목. 설정 화면은 여기서 자동으로 만들어져요.
- `mod.js`: **게임 안**에서 도는 JS (Frida). `registerMod`를 쓰지 않아요 (로더가 감싸 줘요).
- `python/main.py` (있으면): **PC 쪽**. `run(ctx)`와 `ui_이름()` 함수들.
- `ui/index.html` (있으면): 앱 안의 모드창. Python의 `ui_이름()`을 `m24.call('이름')`으로만 불러요.

## 꼭 지킬 규칙
- 변수는 항상 `var`로 선언해요. `var` 없이 대입하면 코어나 다른 모드의 전역 변수를 덮어써요.
- mod.js는 `require`, `import`, `document`, `window`, `fetch`를 못 써요. 네트워크와 파일 작업은 Python 쪽에서 해요.
- 로그는 `api.log('...')`(JS), `ctx.log('...')`(Python)로 남겨요. `console.log`는 안 보여요.
- **게임 값은 이름 있는 코어 기능으로만** 다뤄요: 읽기는 `getField(obj, '이름')`(FIELDS.md)와 코어 함수(`getVal`, `lookup`, `playerInfo` ...), 쓰기는 FIELDS.md에서 **쓰기: safe**인 칸만 `api.setField`(확인·기록·되돌리기가 코어에서 돼요), 게임 함수는 FUNCTIONS.md의 것만 `api.hook`. `ptr()`·`NativeFunction`·`Interceptor`·`.write*()`로 직접 건드리면 게임이 튕기거나 세이브가 망가질 수 있어요 (`raw.*` 기능, 사용자 허용 필요).
- **설정은 `api.settings()`로 읽어요** (바뀌면 `api.onSettings(fn)`). 설정 파일을 직접 읽지 마세요 (`pc.file` 허용이 필요해져요). Python은 `ctx.settings()`.
- 원하는 값·함수가 등록부에 없으면 지어내지 말고 "등록부에 없다"고 알려 주세요. 코어를 넓히는 절차는 `{{ROOT}}\docs\EXTENDING.md`.
- 게임 쪽 코드는 `try/catch`로 감싸고, 실패하면 아무것도 바꾸지 않고 넘어가요.
- JS와 Python의 메시지는 **유실될 수 있어요.** 연결 직후 `hello`를 보내 상태를 맞추고, 답이 없는 요청은 다시 보내요.
- 새 기능(코어 함수, 이벤트, `api.setField`·`api.hook`, Python 부분, `ptr`/`Interceptor` 같은 직접 접근)을 쓰면 `mod.json` `"capabilities"`에 그 이름을 더해요 (`validate`가 빠진 것을 오류로 알려 줘요). `pc`·`raw`·`hook`·`write` 등급은 사용자가 허용해야 켜지므로 꼭 필요할 때만 써요.
- 모드창은 모드가 만든 글자를 `textContent`로만 넣어요 (`innerHTML` 금지).
- `ui_` 함수 이름과 모드창의 `m24.call('이름')`을 항상 맞춰요.
- API 키 같은 비밀은 저장소/모드 파일에 넣지 않아요.

## 작업 순서
1. 코드를 고치고
2. **검사:** `python -X utf8 {{ROOT}}\tools\m24.py validate .` (오류는 위치와 고치는 법이 같이 나와요. 오류가 0이 될 때까지 고쳐요)
3. 모드 폴더(`문서\M24GA\mods`)에 두고 앱에서 **새로 고침**해서 켜요.
4. 안 되면 `~\m24ga_data\loader.log`의 마지막 줄들을 읽어요 (게임 쪽 메시지는 `game:`, Python은 `[모드id]`로 시작해요).
5. 끝나면 `python -X utf8 {{ROOT}}\tools\m24.py pack .`로 `.24mod` 파일을 만들어요.

## 지금 없는 것 (있다고 가정하지 마세요)
FIELDS.md에서 쓰기가 safe가 아닌 값 쓰기(CA, 능력치, 돈, 계약 ...), FUNCTIONS.md에 없는 함수 끼어들기, modify가 아닌 함수의 인자·반환값 바꾸기, 새 화면·버튼 만들기, `socialPanel`·`frame`·`dateChanged`·`saveLoaded` 말고 다른 이벤트. 사용자가 이런 것을 원하면 "코어에 아직 없다"고 알려 주세요.
