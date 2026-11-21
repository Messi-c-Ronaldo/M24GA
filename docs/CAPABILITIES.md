# M24GA 기능 목록 (코어 0.42.0)

> 이 파일은 `core/capabilities.json`에서 `python -X utf8 tools/m24.py caps`로 만들어요. 직접 고치지 마세요.

모드는 `mod.json`의 `"capabilities"`에 쓰는 기능의 이름을 적어요. 로더와 `validate`는 `mod.js`에서 실제로 쓰는 기능도 찾아내요.
**선언하지 않고 쓰면 `validate`가 오류를 내요.** 자동 허용이 아닌 등급은 사용자가 앱에서 허용해야 모드가 켜져요.

## 위험 등급

| 등급 | 뜻 | 허용 |
|---|---|---|
| `read` | 게임 데이터 읽기: 코어가 확인한 방법으로 게임 데이터를 읽어요. 게임을 바꾸지 않아요 | 자동 |
| `ui` | 게임 화면 글자 바꾸기: 게임 화면의 글자를 바꿔요. 세이브에는 남지 않아요 | 자동 |
| `pc` | PC에서 코드 실행: 이 PC에서 Python 코드나 파일 읽기·쓰기를 실행해요. 인터넷에 접속하거나 파일을 바꿀 수 있어요 | **사용자가 허용해야 함** |
| `raw` | 게임 메모리 직접 읽기·함수 호출: 코어를 거치지 않고 게임 메모리를 읽거나 게임 함수를 불러요. 잘못되면 게임이 튕길 수 있어요 | **사용자가 허용해야 함** |
| `hook` | 게임 함수 가로채기: 게임 함수에 직접 끼어들어요. 게임이 튕기거나 다른 모드와 꼬일 수 있어요 | **사용자가 허용해야 함** |
| `write` | 게임 값 쓰기: 게임 메모리의 값을 바꿔요. 세이브에 저장되면 되돌릴 수 없고 세이브가 망가질 수 있어요 | **사용자가 허용해야 함** |

## 기능

| 이름 | 등급 | 설명 | 코어 이름 | 빌드 |
|---|---|---|---|---|
| `event.socialPanel` | read | **소셜 패널 이벤트**: 소셜피드의 글 한 칸이 그려질 때 알림을 받아요. ev = { th, type, dst, text } _(화면 의존: 소셜 피드 화면)_ | `api.on('socialPanel', fn)` | 모두 |
| `event.frame` | read | **프레임 이벤트**: 화면 스레드의 프레임이 끝날 때마다(초당 약 20번) 불려요. 화면을 다시 그리는 일은 여기서 해요 | `api.on('frame', fn)` | 모두 |
| `event.dateChanged` | read | **게임 날짜 바뀜 이벤트**: 게임 날짜가 바뀌면(날짜 진행) 불려요. ev = { from, to, days } (from/to = {y, m, d, doy, iso}). 0.5초마다 확인하고 화면 스레드가 아니에요 | `api.on('dateChanged', fn)` | 모두 |
| `event.newsAdded` | read | **게임 뉴스가 생길 때**: 게임이 뉴스 하나를 넣을 때마다(하루 수백 번: 경기 보고, 이적, 부상, 언론 의견…) 불려요. ev = { cls(뉴스 종류 = 클래스 이름, 예: MATCH_REPORT_NEWS), flags, toInbox, team(받는 팀), mine(내 팀 앞), text() }. text()는 게임 본문 글(평문)을 만들어요. 비싸니 필요한 뉴스만, 콜백 안에서만 불러요 (콜백이 끝나면 ''). 게임 스레드에서 불리니 짧게 하고, 긴 일은 api.send로 Python에 넘기세요. 모드가 처음 구독할 때 코어가 끼어들어요 (코어 0.37.0) ev.id(뉴스 번호), ev.date('YYYY-MM-DD'), ev.refs() = 게임이 뉴스에 붙인 관련 기록 { people, teams, clubs, comps, refs:[dref] } (콜백 안에서만) | `api.on('newsAdded')` | 모두 |
| `event.gameSaved` | read | **게임 저장이 끝났을 때**: 게임 저장(Ctrl+S, 메뉴 저장)이 끝나 .fm 파일 쓰기가 마무리된 뒤 불려요. ev = { ms(저장에 걸린 시간), save({id, nonce}) }. 모드가 세이브별로 따로 적어 둔 기록을 이때 확정하면, 저장하지 않고 다시 불러온 경우와 구별할 수 있어요 | `api.on('gameSaved')` | 모두 |
| `event.matchEnded` | read | **경기가 끝났을 때 (점수)**: 경기 보고 뉴스가 나온 경기마다 한 번 불려요. ev = { home, away(팀 객체), homeGoals, awayGoals, comp(대회 객체 또는 null), stadium(0.39.0, 경기장 또는 null), mine(내 팀 경기), date('YYYY-MM-DD'), text()(경기 보고 본문) }. 게임이 보도하는 리그·대회의 경기만 오고(하루 수십~수백 경기), 승부차기·연장은 아직 구별하지 않아요. 게임 스레드라 짧게 | `api.on('matchEnded')` | 모두 |
| `event.saveLoaded` | read | **세이브 불러옴 이벤트**: 다른 세이브를 불러오면(또는 코어가 처음 세이브를 보면) 불려요. ev = { id, nonce, date }. 모드가 나중에 올라왔으면 이미 지나갔으니 처음에 saveInfo()로 확인하세요 | `api.on('saveLoaded', fn)` | 모두 |
| `read.data` | read | **클럽·선수·스태프 데이터 읽기**: 데이터 표(clubs, persons, staff)와 속성 읽기(4글자 코드). mapsReady가 true일 때 써요 (세이브를 불러오면 코어가 스스로 만들어요, 화면 무관. 예전 api.prepareData는 그대로 둠). (코어 0.26.0) clubByName('토트넘') = 정식/짧은 이름이 같은 구단(db::CLUB), clubUid(구단) / clubByUid(번호) = 구단 고유 번호. (코어 0.27.0) personByName('손흥민') = {person, ref:'p95264'\|'s…', many} 또는 null, 이름 색인을 처음 만드는 동안은 {pending:true} (뒤에서 30초쯤). personByRef(ref) / personRef(사람). (코어 0.28.0) personsByName('파울리뉴') = 같은 이름의 사람 모두 (최대 8명) [{person, ref, name, age, club, role:'player'\|'staff'}] 또는 색인을 만드는 동안 {pending:true}, personInfo(사람) = 같은 정보 하나 (club ''는 무소속). personByName 결과에 count(같은 이름 수) | `api.prepareData`, `mapsReady`, `uidReady`, `clubs`, `persons`, `staff`, `lookup`, `getVal`, `getInt`, `linkIds`, `personName`, `personForm`, `formText`, `personExtra`, `mainPosition`, `topPlayer`, `clubExtra`, `clubSituation`, `staffAttrs`, `decodeVal`, `CLUB_VT`, `PERSON_VT`, `STAFF_VT`, `CLUBOBJ_VT`, `NT_VT`, `isNT`, `EMPTY_VAL`, `clubObj`, `clubFullName`, `clubShortName`, `clubByName`, `clubByUid`, `clubUid`, `personByName`, `personByRef`, `personRef`, `personsByName`, `personInfo` | 모두 |
| `read.prop` | read | **게임 속성 코드 읽기**: 게임 화면이 쓰는 4글자 속성 코드로 팀·구단·국가대표·선수·스태프·사람 감독·대회·상(0.39.0부터 국가·경기장·도시·대륙·언론사·계약·임대·부상도)의 값을 읽어요. 등록부 core/properties.json(2,300여 개, 종류·값 형식)을 기준으로 api.prop(대상, 코드) / api.props(대상, {re, codes, empty}) / api.propInfo(코드) / api.deref({dref}). 대상은 객체 포인터 또는 'me'·'myteam'·'myclub'·'myjob'·'p123'·'s45'·'team:<번호>'·'comp:<번호>'. 날짜는 'YYYY-MM-DD', 다른 객체 링크는 {dref}. (코어 0.39.0) Python 모드: ctx.props(대상, 정규식) / ctx.prop(대상, 코드). (코어 0.40.0) api.leagueResults(대회 \| 'myleague') = 지난번 부른 뒤 끝난 리그 경기 결과 (보도 안 되는 경기 포함) | `api.prop`, `api.props`, `api.propInfo`, `api.deref`, `ctx.props`, `ctx.prop`, `api.leagueResults` | 모두 |
| `read.action` | read | **게임 명령(액션) 목록 읽기**: api.actionsFor(대상, {all})로 게임 메뉴가 그 대상(사람·팀·구단·대회, 'me'·'myteam'·'myclub'·{dref})에 보여 주는 명령을 읽어요. 게임 자신의 확인 함수를 불러서 화면 메뉴와 같은 판단이에요 (Promise [{id, cls, hidden, disabled, canRun, events, click, confirm, args}]). 목록: docs/ACTIONS.md. 게임을 바꾸지 않아요 Python 모드: ctx.actions_for(대상) | `api.actionsFor`, `ctx.actions_for` | 모두 |
| `read.news` | read | **뉴스 기사 본문 읽기**: 소셜피드 글이 달린 뉴스 기사의 본문(평문)을 읽어요 _(화면 의존: 소셜 피드 화면)_ | `newsBody` | 모두 |
| `read.me` | read | **내 감독·내 클럽**: 사용자 감독 이름과 맡은 클럽. (코어 0.24.0) myHuman() = 이 PC의 사람 감독 객체(db::HUMAN_NON_PLAYER, 소셜 화면 없이), humans() = 사람 감독 목록. 칸은 getField(myHuman(), 'human.…'). (코어 0.25.0) humanRelations(h) = 감독의 관계 목록 [{target, cls, kind, kindName(favClub·dislikedClub·favPerson·dislikedPerson), level, reason, name}] (읽기만) | `myInfo`, `myHuman`, `humans`, `humanRelations` | 모두 |
| `read.fan` | read | **팬 응원 클럽**: 댓글 작성자(팬)가 응원하는 클럽, 그 클럽 감독과 최근 성적 _(화면 의존: 소셜 피드 화면)_ | `fanClub`, `uidReady` | 모두 |
| `read.manager` | read | **클럽 감독**: 클럽의 지금 감독(임시 감독 포함)과 감독 능력치, 공석 여부 | `clubManagerObj`, `clubManager`, `clubManagerAttrs`, `vacant` | 모두 |
| `read.date` | read | **게임 날짜**: 지금 게임 날짜 {y, m, d, doy(연중 일수), iso}. 세이브를 안 불러왔으면 null. Python은 ctx.game()['date'] | `gameDate`, `ctx.game` | 모두 |
| `read.save` | read | **세이브 식별**: 지금 세이브 {id, nonce}. 세이브마다 따로 기록할 때 써요 (Python은 ctx.save_dir()가 세이브별 폴더를 줘요). 세이브가 없으면 null | `saveInfo`, `ctx.save_dir` | 모두 |
| `read.player` | read | **선수 능력·신원·시즌 기록·포지션·성격·소속**: 선수 객체에서 UID, 현재 능력(CA), 잠재력(PA), 생년월일, 이름을 읽어요. 글 링크로 찾은 사람(persons 표)은 playerOf(o)로 선수 객체를 얻어요. 선수 목록은 세이브가 바뀌면 다시 만들어요(0.3초). 코어 0.8.0부터: 이번 시즌 기록 대회별(playerSeason: club 합계/league/cup/continental/international), 상세 기록(playerSeasonDetail, xG 등), 포지션 숙련도(playerPositions, playerPosition), 성격(playerTraits: 야망·프로의식·결단력·활동량·창의성), 소속 팀·리그(playerTeam). 코어 0.8.1: 부상 상태와 부상 경향(playerInjury, 사람 표가 만들어진 뒤부터). 코어 0.9.0: 선수 객체 -> 사람 데이터 객체(personOf, getVal로 속성을 읽는 객체) | `playerOf`, `playerByUid`, `playerInfo`, `playerUids`, `personUid`, `playerSeason`, `playerSeasonDetail`, `playerPositions`, `playerPosition`, `playerTraits`, `playerTeam`, `playerInjury`, `personOf` | 모두 |
| `read.rtti` | read | **게임 객체의 클래스 이름**: fm.exe에 남은 클래스 정보(RTTI)로 아무 게임 객체의 클래스 이름과 상속을 읽어요. className(obj) -> 'db::ACTUAL_PLAYER' 같은 이름(없으면 null), rttiInfo(obj) -> {name, off, top, bases} (off = 이 vtable이 객체 안 어디 있는지, top = 객체 맨 앞), isA(obj, 'db::PERSON') -> 그 클래스이거나 물려받았나. 객체가 맞는지 확인할 때 vtable 주소 대신 이름으로 확인할 수 있어요. 클래스 목록은 CLI 'classes <정규식>', 객체 펼쳐 보기는 CLI 'explore' | `className`, `rttiInfo`, `isA` | 모두 |
| `read.field` | read | **필드 등록부로 게임 값 읽기**: core/fields.json에 등록된 칸을 이름으로 읽어요 (목록 docs/FIELDS.md). getField(obj, 'player.ca'), findObj('player', uid), fieldInfo('이름'), fieldNames('player.'). 객체 종류는 클래스 이름(RTTI)으로 확인해서 다른 종류의 객체면 null이에요. 새 칸은 fields.json에 한 줄 더하면 모든 모드가 써요 | `getField`, `findObj`, `fieldInfo`, `fieldNames` | 모두 |
| `read.panel` | read | **소셜 패널 도우미**: 패널 주소로 다시 찾기(panelAt), 지금 글과 글자 객체(panelText, panelTextHandle), 글자 칸(panelDst), 스레드(뉴스) 객체(panelThread), 작성자 응원 클럽 고유 ID(panelFanUid). 메모리를 직접 읽지 않고 소셜 패널을 다뤄요 _(화면 의존: 소셜 피드 화면)_ | `panelAt`, `panelDst`, `panelText`, `panelTextHandle`, `panelThread`, `panelFanUid` | 모두 |
| `ui.social.text` | ui | **소셜피드 글자 바꾸기**: 소셜 패널의 글자 칸을 새 글로 바꾸고 다시 그려요. refreshPanel은 화면 스레드(socialPanel/frame 콜백)에서만 _(화면 의존: 소셜 피드 화면)_ | `setStr`, `refreshPanel`, `uiTid` | 모두 |
| `ui.panel` | ui | **게임 안 패널 (FM 모양 대화상자)**: 양식(제목, 글, 입력칸·숫자·체크·드롭다운·글 칸, 버튼)을 적으면 코어가 게임의 대화상자로 띄우고, 버튼·값이 바뀔 때 알려 줘요. 스킨 파일을 쓰지 않아요 (FM 사용자 폴더의 패널 칸 파일, 로더가 게임보다 먼저 만듦). 세이브는 바꾸지 않아요. 처음 한 번은 게임을 다시 켜야 할 수 있어요 (api.panel.available()) (코어 0.29.0) 칸 종류 person·club = 게임 검색칸: 치는 대로 게임이 후보(이름·포지션/직업·구단)를 띄우고, 고르면 {id, kind:'pick', value:{type, ref\|uid, name, age, club, role, label}} 이벤트가 오고 창이 고른 것을 보이며 다시 그려져요. values()에서는 고른 것, 안 골랐으면 친 글 {text}, 둘 다 없으면 null. 칸 value에 {ref}나 {uid}를 주면 '지금: …'으로 보여요. select 칸도 value를 주면 그 항목이 골라진 채로 열려요 | `api.panel` | 모두 |
| `ui.inbox` | write | **게임 받은 편지함에 메일 넣기**: api.inbox.send({ title, body, from })로 게임 받은 편지함에 메일 한 통을 넣어요. 게임의 '감독끼리 보내는 메시지' 종류라 '보낸이의 말: 제목'으로 보이고, 보낸이는 사람(내 감독, 스태프, 선수: myHuman(), personByName(이름).person)이에요. 받는 사람은 내 감독(맡은 팀이 있어야 함). 세이브에 남고 되돌릴 수 없어서 사용자 허용이 필요하고 1분에 10통까지예요. 화면 스레드에서 넣고 Promise로 {ok, error}를 돌려줘요. 메일의 '응답' 버튼은 눌러도 아무 일도 일어나지 않아요 | `api.inbox` | 모두 |
| `game.action` | write | **게임 명령(액션) 실행**: api.action(id, 대상, {event, danger})로 게임 명령을 실행해요 (구독, 관심 목록, 구단에 요구 …). 게임이 그 대상에 그 명령을 보여 줄 때만, 게임이 만든 인자 그대로 화면 메뉴와 같은 처리기를 불러요. 세이브에 남고 되돌리기가 없어서(되돌리는 명령이 따로 있는 것도 있음) 사용자 허용이 필요하고 1분에 10번까지, 실행마다 로더 기록에 남아요. 사임·은퇴·휴가처럼 경력을 크게 바꾸는 명령은 {danger: true}가 있어야 해요. 확인 창을 거치는 명령(주장 지정 PmcP 등)은 확인 뒤 이벤트(pmcC처럼 …C)를 {event}로 주면 확인 창 없이 실행되고, 이런 명령은 게임이 다음 처리(하루 진행) 때 반영해요 (M65 실기). Promise {ok, error, handled}. 처리기가 빈 명령(화면 이동 LINK·사임 등 38개)은 이 길로 실행할 수 없어요. 이벤트가 여럿이면 {event}로 고르고, 등록부의 confirm(확인 뒤 이벤트)이 확인 창 없이 실행하는 쪽이에요. Python 모드: ctx.action(id, 대상, event=None, danger=False) | `api.action`, `ctx.action` | 모두 |
| `pc.python` | pc | **PC 쪽 Python 부분**: mod.json의 python 진입 파일을 이 PC에서 실행해요 (인터넷 API, 파일). 게임 쪽과는 api.send/recv ↔ ctx.recv/post로 이야기해요 | `mod.json python`, `api.send`, `api.recv` | 모두 |
| `pc.file` | pc | **게임 안에서 파일 읽기·쓰기**: Frida File로 파일을 직접 읽고 써요. 가능하면 Python 부분과 메시지를 쓰세요 | `File` | 모두 |
| `raw.read` | raw | **게임 메모리 직접 읽기**: 주소(ptr)를 직접 만들거나 .readPointer/.readU32 같은 읽기로 게임 메모리를 읽어요. 주소가 틀리면 예외가 나요 (코어 함수로 되는 일이면 코어 함수를 쓰세요) | `ptr()`, `NativePointer.read*`, `B`, `Memory.scan`, `Process` | 모두 |
| `raw.call` | raw | **게임 함수 직접 호출**: NativeFunction으로 게임 함수를 직접 불러요. 인자나 스레드가 틀리면 게임이 튕겨요 | `NativeFunction`, `NativeCallback` | 모두 |
| `hook.function` | hook | **게임 함수에 끼어들기 (함수 등록부)**: core/functions.json에 등록된 게임 함수에 api.hook('이름', {before, after})로 끼어들어요 (목록 docs/FUNCTIONS.md). 코어가 함수마다 하나만 걸고 서명을 확인하고, 모드를 내리면 자동으로 떼요. 인자와 반환값을 볼 수 있고, modify로 확인된 함수는 바꿀 수도 있어요 (ev.setArg/ev.setRet). 콜백은 게임 스레드에서 불려서 오래 걸리면 게임이 느려져요. raw.hook(Interceptor 직접)보다 안전해요 | `api.hook` | 모두 |
| `hook.gate` | hook | **게임 판단 바꾸기 (게이트 등록부)**: core/functions.json의 gates에 등록된 게이트를 켜요: 정해진 게임 함수 안에서만, 정해진 질문(예: '감독이 사람인가')에 다른 답을 해요. 코어가 서명·원래 값을 확인하고, 스레드마다 범위를 세고, 모드를 내리면 원래대로 돌려요. 게임 계산 결과가 바뀌고 세이브에 남을 수 있어요 (예: 몸값) | `api.gate` | 모두 |
| `read.player.value` | read | **선수 몸값(가치) 계산 읽기**: playerValue(p, club)로 게임의 선수 가치 함수를 불러 몸값(내부 돈 단위, 원화 = ×1664.7)과 단계별 이유 코드를 읽어요. club을 주면 그 구단이 평가하는 값(이적 제안에 쓰는 값). 게임이 진행 중이면 {error, busy}. 타이머(api.after/every)에서 부르세요 (frame·api.hook 콜백 안에서 부르면 게이트·배율이 빠진 값이 나와요) | `playerValue` | 모두 |
| `read.award` | read | **대회·상 이름과 정보**: 대회(리그·컵)와 상의 번호로 이름·짧은 이름·나라·대륙을 읽어요: compInfo(번호), awardInfo(번호), compIds(), awardIds(). 번호는 세이브 기록(Python 공용 라이브러리 m24awards의 상 번호·대회 번호)과 같아요. 세이브를 불러온 뒤 사람·구단 표와 함께 만들어져요. 코어 0.21.0: compLatest(번호) = 가장 최근에 끝난 시즌 결과 {start, end, winner, runnerUp, third} (팀 번호, 세이브에 아직 보관 안 된 시즌) | `compInfo`, `awardInfo`, `compIds`, `awardIds`, `compLatest` | 모두 |
| `hook.scale` | hook | **게임 계산 결과에 배율 곱하기 (배율 표)**: core/functions.json에서 scale이 있는 함수(예: player.value = 선수 가치)의 반환값에 객체별 배율을 곱해요: var s = api.scale('player.value'); s.set(선수, 1.2). 게임이 하루 수만 번 불러도 빠르게(네이티브 표) 처리하고, 결과는 게임 상한으로 잘라요. 함수 하나에 모드 하나. 게임 계산 결과가 바뀌고 세이브에 남을 수 있어요 (예: 요구 금액) | `api.scale` | 모두 |
| `raw.hook` | hook | **게임 함수 가로채기**: Interceptor로 게임 함수에 직접 끼어들어요. 코어가 이미 건 함수와 겹치면 꼬일 수 있어요. api.onUnload에서 떼야 해요 | `Interceptor` | 모두 |
| `write.player.pa` | write | **선수 잠재력(PA) 바꾸기**: api.setPlayerPA(uid, pa, {expect, reason})로 선수 PA를 바꿔요. 코어가 같은 선수인지·범위(1~200, CA 이상)·폭주(1분 600번)를 확인하고, 모든 쓰기를 기록해요. 앱 정보 탭에서 이 세이브에서 바꾼 값을 되돌릴 수 있어요. 게임을 저장하면 세이브 파일에 남아요. 코어 0.10.0부터 api.setField(obj, 'player.pa', ...)로도 쓸 수 있어요 (같은 확인·기록) | `api.setPlayerPA` | 모두 |
| `write.field` | write | **필드 등록부로 게임 값 쓰기**: fields.json에서 쓰기가 확인된 칸(write: safe)을 api.setField(obj, '이름', 값, {expect, reason})로 바꿔요. 코어가 객체 종류·범위·다른 필드와의 관계·쓰기 전후 신원을 확인하고, 모든 쓰기를 기록해요. 앱 정보 탭에서 이 세이브에서 바꾼 값을 되돌릴 수 있어요. 칸마다 다른 기능이 정해져 있으면(예: player.pa는 write.player.pa) 그 기능이 필요해요. 게임을 저장하면 세이브 파일에 남아요 | `api.setField` | 모두 |
| `write.prop` | write | **속성 코드로 게임 값 쓰기**: api.setProp(대상, '코드', 값, {expect, reason, tested})로 게임 속성 값을 게임 자신의 setter(속성 객체 vtable +0x18)로 바꿔요. 화면 메뉴처럼 게임 층이 먼저 처리하고 값 자르기·바뀜 알림도 게임이 해요. core/properties.json의 write.codes에 있는 코드만 되고(api.propInfo(코드).writable), safe(쓰기·화면·하루 진행·저장 뒤 다시 불러오기까지 확인한 29개: 구단 잔고·이적/주급/스카우트 예산·시설, 선수 CA·PA·명성·성격 일부·키·몸무게·사기·체력, 팀·대회 명성 …)는 그냥, tested(+1·되돌리기만 확인한 200개)는 {tested: true}가 있어야 해요. 정수·불리언·실수만 되고, 쓴 뒤 게임이 객체를 바꾸거나 다른 값으로 자르면 실패로 알려요(자른 경우는 원래 값으로 되돌림). 화면 스레드에서 돌아서 Promise {ok, before, after, code, key(대상 dref), error}. 1분 600번까지, 모든 쓰기를 기록하고 앱 정보 탭에서 이 세이브에서 바꾼 값을 되돌릴 수 있어요. 게임을 저장하면 세이브에 남아요. Python 모드: ctx.set_prop(대상, 코드, 값, expect=None, reason='', tested=False) | `api.setProp`, `ctx.set_prop` | 모두 |
| `write.relation` | write | **감독의 좋아하는/싫어하는 구단·사람 바꾸기**: api.setRelation(myHuman(), 'favClub'\|'dislikedClub'\|'favPerson'\|'dislikedPerson', 구단 또는 사람, 넣기/빼기, {reason})로 사람 감독의 좋아하는/싫어하는 구단·사람을 바꿔요 (사람은 코어 0.27.0, personByName으로 찾은 사람). 게임의 관계 더하기 함수를 쓰고, 빼기는 게임처럼 항목만 치워요. 모든 쓰기는 기록되고 앱에서 되돌릴 수 있어요. 세이브에 남아요 | `api.setRelation` | 모두 |
| `raw.write` | write | **게임 메모리 직접 쓰기**: 게임 메모리를 직접 바꿔요. 세이브에 저장되면 되돌릴 수 없어요. 코어의 안전한 쓰기 기능(백업·기록 포함)이 생기기 전까지는 이 방법뿐이에요 | `NativePointer.write*`, `Memory.protect`, `Memory.patchCode`, `Memory.copy` | 모두 |
| `read.engine` | read | **매치엔진 표 읽기**: api.engine.dump('weights'\|'physics'\|'momentum'\|'ratings'\|'styles'\|'xg')로 게임 메모리의 매치엔진 표(선발 가중치, 선수 물리, 모멘텀, 경기 평점, (코어 0.32.0) 전술 스타일, (코어 0.33.0) xG 모델 계수·절편)를 그대로 읽어요. 게임을 바꾸지 않아요. styles는 세이브를 불러온 뒤 첫 진행일부터 있어요 | `api.engine.dump` | 모두 |
| `write.engine` | write | **매치엔진 표 바꾸기**: api.engine.write(표, spec)로 게임 메모리의 매치엔진 표 값을 바꿔요 (재시작 없이 다음 선발·경기부터 반영). 이미 있는 칸에만 쓰고 (전술 스타일은 목록 전체를 바꾸고 칸이 늘면 버퍼를 새로 만들어요), 게임이 진행 중이면 쓰지 않아요. 세이브에는 남지 않아요 (게임을 다시 켜면 원본). 잘못된 값은 경기 결과를 이상하게 만들 수 있어요 | `api.engine.write` | 모두 |

## 예제

**`event.socialPanel`**

```js
api.on('socialPanel', function (ev) { if (ev.type === 2) api.log(ev.text); });
```

**`event.frame`**

```js
var last = 0; api.on('frame', function () { if (Date.now() - last < 1000) return; last = Date.now(); /* 1초에 한 번 */ });
```

**`event.dateChanged`**

```js
api.on('dateChanged', function (ev) { if (ev.to.m !== ev.from.m) api.log('새 달: ' + ev.to.iso); });
```

**`event.newsAdded`**

```js
api.on('newsAdded', function (ev) { if (ev.mine && /MATCH/.test(ev.cls)) api.send({ news: ev.cls, text: ev.text() }); });
```

**`event.gameSaved`**

```js
api.on('gameSaved', function (ev) { api.send({ saved: ev.save, ms: ev.ms }); });
```

**`event.matchEnded`**

```js
api.on('matchEnded', function (ev) { if (ev.mine) api.log(api.prop(ev.home, 'Tnam').Tsna + ' ' + ev.homeGoals + '-' + ev.awayGoals + ' ' + api.prop(ev.away, 'Tnam').Tsna); });
```

**`event.saveLoaded`**

```js
api.on('saveLoaded', function (ev) { api.send({ t: 'save', id: ev.id }); });
```

**`read.data`**

```js
var o = lookup(clubs, idx, CLUB_VT); if (o) api.log('리그 순위 ' + getInt(o, 'TpoN'));
```

**`read.prop`**

```js
var rank = api.prop('myteam', 'TpoN'); var opp = api.deref(api.prop('myteam', 'Topp')); if (opp) api.log('상대 순위 ' + api.prop(opp, 'TpoN'));
```

**`read.action`**

```js
api.actionsFor(player).then(function (L) { api.log(L.map(function (a) { return a.id; }).join(' ')); });
```

**`read.news`**

```js
var body = newsBody(ev.th.add(0x1b0).readPointer());
```

**`read.me`**

```js
var me = myInfo(); if (me) api.log(me.mgr + ' / ' + me.club);
```

**`read.fan`**

```js
var f = fanClub(salo); if (f.name) api.log(f.name + ' 팬');
```

**`read.manager`**

```js
var m = clubManagerObj(idx); if (m) api.log(m.name + (m.caretaker ? ' (임시)' : ''));
```

**`read.date`**

```js
var d = gameDate(); if (d && d.m === 7) api.log('여름 이적 시장');
```

**`read.save`**

```js
var s = saveInfo(); if (s) api.log('세이브 ' + s.id);
```

**`read.player`**

```js
var o = lookup(persons, idx, PERSON_VT), p = o && playerOf(o), i = p && playerInfo(p); if (i) api.log(i.name + ' CA ' + i.ca + ' / PA ' + i.pa); var s = p && playerSeason(p, 'league'); if (s) api.log('리그 ' + s.apps + '경기 평점 ' + s.avg + ' ' + s.goals + '골');
```

**`read.rtti`**

```js
var p = playerByUid(uid); if (p && isA(p, 'db::PLAYER')) api.log(className(p));   // db::ACTUAL_PLAYER
```

**`read.field`**

```js
var p = findObj('player', uid); if (p) api.log(getField(p, 'player.name') + ' 요구 금액 ' + getField(p, 'player.askingPrice'));
```

**`read.panel`**

```js
api.on('socialPanel', function (ev) { var f = fanClub(panelFanUid(ev.th)); if (f.name) api.log(f.name + ' 팬의 글'); });
```

**`ui.social.text`**

```js
api.on('socialPanel', function (ev) { if (ev.type === 2) setStr(ev.dst, '바꾼 글'); });
```

**`ui.panel`**

```js
var p = api.panel.open({ title: '경력', fields: [{ id: 'club', type: 'text', label: '뛴 구단' }], buttons: [{ id: 'apply', label: '적용' }] }, function (ev) { if (ev.id === 'apply') api.log(JSON.stringify(ev.values())); });
```

**`ui.inbox`**

```js
api.inbox.send({ title: '경기 뒤 기자 질문', body: '오늘 승리의 열쇠는 무엇이었나요?', from: myHuman() }).then(function (r) { if (!r.ok) api.log(r.error); });
```

**`game.action`**

```js
api.action('SUBS', player).then(function (r) { if (!r.ok) api.log(r.error); });
```

**`pc.python`**

```json
"python": "python/main.py"
```

**`pc.file`**

```js
var f = new File(DIR + 'out.txt', 'w'); f.write('...'); f.close();
```

**`raw.read`**

```js
var n = ev.th.add(0x1d8).readU32();
```

**`raw.call`**

```js
var f = new NativeFunction(B.add(0x123456), 'void', ['pointer']);
```

**`hook.function`**

```js
api.hook('player.updateAskingPrice', { after: function (ev) { api.log('요구 금액 계산 ' + ev.caller); } });
```

**`hook.gate`**

```js
var g = api.gate('valuation.squadPremiumHumanAsAi'); if (g.ok) api.status(function () { return g.stats(); });
```

**`read.player.value`**

```js
api.after(500, function () { var p = playerByUid(uid), r = playerValue(p); if (r && !r.error) api.log('가치 ' + r.value + ' 원화 ' + Math.round(r.value * 1664.7)); });
```

**`read.award`**

```js
var a = awardInfo(405); if (a) api.log(a.name + ' (' + (a.continent || a.nation || '세계') + ')');
```

**`hook.scale`**

```js
var s = api.scale('player.value'); if (s.ok) { s.set(playerByUid(uid), 1.2); api.status(function () { return s.stats(); }); }
```

**`raw.hook`**

```js
var l = Interceptor.attach(B.add(0x123456), { onEnter: function (a) {} }); api.onUnload(function () { l.detach(); });
```

**`write.player.pa`**

```js
var p = playerByUid(uid), i = p && playerInfo(p); if (i && i.pa < 200) api.setPlayerPA(uid, i.pa + 1, { expect: i.pa, reason: '이달의 활약' });
```

**`write.field`**

```js
var r = api.setField(findObj('player', uid), 'player.pa', 150, { expect: 149, reason: '활약' }); if (!r.ok) api.log(r.error);
```

**`write.prop`**

```js
api.setProp('myclub', 'Ctfc', 300000000, { reason: '이사회 추가 예산' }).then(function (r) { if (!r.ok) api.log(r.error); });
```

**`write.relation`**

```js
var r = api.setRelation(myHuman(), 'dislikedClub', clubByName('토트넘'), true, { reason: '선수 시절 라이벌' }); if (!r.ok) api.log(r.error);
```

**`raw.write`**

```js
obj.add(0x202).writeS16(180);   // 예: 포텐 (실제 주소는 역분석 필요)
```

**`read.engine`**

```js
var w = api.engine.dump('weights'); if (!w.error) api.log('1군 CA 가중치 ' + w.ints[7]);
```

**`write.engine`**

```js
var r = api.engine.write('weights', { entry: 0, ints: ints156 }); if (!r.ok) api.log(r.error);
```

## 이 목록에 없는 것

게임 값을 **안전하게** 쓰는 기능(백업·쓰기 기록 포함), 새 이벤트(날짜 진행, 경기 결과, 세이브 로드), 새 화면 요소는 아직 없어요.
`raw.*`로 직접 할 수는 있지만 게임이 튕기거나 세이브가 망가질 수 있어요. 새 기능을 코어에 넣으면 이 목록에 먼저 추가해요.
