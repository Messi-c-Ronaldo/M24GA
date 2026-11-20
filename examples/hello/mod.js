// Hello 예제 모드: 게임 쪽 (Frida JS).
// 로더가 이 파일을 registerMod('hello-example', function (api) { ... }) 안에 넣어서 올린다.
// 그래서 var는 이 모드 안에서만 보이고, 코어의 전역 함수(getVal, lookup, setStr 등)는 그대로 쓸 수 있다.
// 'var DIR = ...' 줄을 적지 않아도 로더가 모드 데이터 폴더(DIR, 끝에 / 포함)를 앞에 넣어 준다.

var seen = 0, byType = {};

api.log('게임 쪽 부분이 올라왔어요. 데이터 폴더: ' + DIR);   // loader.log에 "game: [hello-example] ..."로 남는다

// (화면 의존 기능, M39) 소셜 피드 화면에서 패널이 하나 그려질 때마다 코어가 알려 준다. 그 화면이 안 열리면(스킨·사용자에 따라) 안 불린다.
// 모드의 핵심 기능은 dateChanged·saveLoaded·api.every처럼 화면과 무관한 것으로 만들고, 화면 기능은 덤으로 쓰세요.
// (예제는 세기만 하고 화면은 건드리지 않는다)
// ev = { th: 패널 객체 주소, type: 글 종류(2·4 = 팬 댓글), dst: 글자 칸 주소, text: 지금 글 }
api.on('socialPanel', function (ev) {
  seen++;
  byType[ev.type] = (byType[ev.type] || 0) + 1;
  if (seen % 100 === 0) api.log('소셜 패널 ' + seen + '개째: ' + JSON.stringify(byType));
});

// (코어 0.5.0) 게임 날짜가 바뀔 때마다. ev.from / ev.to = { y, m, d, doy, iso }, ev.days = 며칠 지났는지
api.on('dateChanged', function (ev) {
  if (ev.to.m !== ev.from.m) api.log('새 달이 됐어요: ' + ev.to.iso);
});

// (코어 0.5.0) 타이머: 1분마다. 모드를 끄면 코어가 알아서 멈춘다 (setInterval을 직접 쓰지 않는다)
api.every(60000, function () {
  var d = gameDate(), s = saveInfo();
  if (d) api.log('게임 날짜 ' + d.iso + (s ? ', 세이브 ' + s.id : ''));
});

// 코어의 rpc status에 합쳐진다 (콘솔판 host.py가 60초마다 기록하는 상태에 보인다)
api.status(function () { return { helloSeen: seen }; });
