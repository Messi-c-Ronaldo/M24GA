// 필드·끼어들기 예제 모드: 게임 쪽 (Frida JS). 게임 값은 바꾸지 않고 읽기만 한다.
// 보여 주는 것: api.settings / api.onSettings (설정, 코어 0.12.0), findObj / getField (필드 등록부, docs/FIELDS.md),
// api.hook (함수 등록부, docs/FUNCTIONS.md), api.on('dateChanged'), api.every.

// 1) 설정: mod.json의 settings 값 (앱에서 바꾸면 onSettings가 불려요). 사용자 허용이 필요 없어요. 파일을 직접 읽지 않아요.
var cfg = api.settings();                         // { uid: 2002122126, watchValue: true }
api.onSettings(function (s) { cfg = s; setHook(cfg.watchValue); api.log('설정이 바뀌었어요: ' + JSON.stringify(s)); });

// 2) 필드 읽기: 객체를 찾고(findObj) 이름으로 읽는다(getField). 종류가 다른 객체거나 못 읽으면 null.
function describePlayer(uid) {
  var p = findObj('player', uid);                       // 선수 UID로 선수 객체 (없으면 null)
  if (!p) return '선수를 찾지 못했어요 (UID ' + uid + ')';
  var team = getField(p, 'player.team');                // ptr 필드: 소속 팀 객체
  var club = team ? getField(team, 'team.club') : null; // 팀의 클럽 객체
  return getField(p, 'player.name') + ' (' + (club ? getField(club, 'club.short') : '무소속') + ')' +
    ' CA ' + getField(p, 'player.ca') + ' / PA ' + getField(p, 'player.pa') +
    ', 요구 금액 ' + getField(p, 'player.askingPrice') +
    ', 리그 ' + getField(p, 'player.season.league.goals') + '골 ' + getField(p, 'player.season.league.assists') + '도움';
}

api.on('dateChanged', function (ev) {                   // 게임 날짜가 바뀔 때
  api.log(ev.to.iso + ' ' + describePlayer(cfg.uid));
});

// 3) 게임 함수에 끼어들기: 등록된 함수(player.updateAskingPrice)가 불리기 전후를 본다. 콜백은 게임 스레드라 짧게!
var calls = 0, hook = null;
function setHook(on) {
  if (on && !hook) {
    var h = api.hook('player.updateAskingPrice', {
      before: function (ev) { ev.data.t = Date.now(); },       // before에서 after로 값을 넘길 때는 ev.data
      after: function (ev) {
        calls++;
        api.log('요구 금액 일괄 계산 ' + calls + '번째: ' + (Date.now() - ev.data.t) + 'ms, 부른 곳 ' + ev.caller);
      }
    });
    if (h.ok) hook = h; else api.log('끼어들지 못했어요: ' + h.error);   // 모르는 함수, 서명이 다른 빌드 등
  } else if (!on && hook) { hook.stop(); hook = null; }      // 모드를 내리면 코어가 알아서 떼지만, 중간에 끄려면 stop()
}
setHook(cfg.watchValue);

// 4) 값 쓰기는 이 예제에서 하지 않는다. 쓰려면 mod.json에 "write.field"(PA는 "write.player.pa")를 더하고 사용자가 허용해야 한다:
//   var r = api.setField(findObj('player', uid), 'player.pa', 150, { expect: 149, reason: '이유' });  if (!r.ok) api.log(r.error);
// 쓸 수 있는 칸은 docs/FIELDS.md에서 '쓰기: safe'인 것뿐이다.

api.status(function () { return { watching: cfg.uid, askingPriceCalls: calls, hooked: !!hook }; });
api.log('올라왔어요. 지켜볼 선수 ' + cfg.uid + ': ' + describePlayer(cfg.uid));
