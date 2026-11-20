// 몸값 보정 (player-value) 0.4.2 — 게임 쪽 (Frida JS). GPL-3.0-or-later
// 기능 A (FM24 버그 수정): 사람 감독 구단의 선수는 구단 스쿼드 계획에 따른 할증 두 가지를 못 받는다 (몸값모드 V03, V05 로그):
//  1) 핵심 선수 할증 (선수 가치 계산의 이유 코드 11): 언제나 (요구 금액, 화면 몸값)
//  2) 파는 구단 계획 할증 (이유 코드 21, ×1.5): 다른 구단이 그 선수를 평가할 때 (AI 이적 제안 금액)
//  두 함수 모두 구단 감독에게 '사람이냐'를 묻고 사람이면 건너뛴다. 코어 게이트가 그 함수들 안에서만 '사람 아님'으로 답한다.
// 기능 B (활약 배율, 기본 꺼짐): Python이 지난 2시즌(세이브 파일)과 이번 시즌 리그 평점으로 선수마다 배율을 계산하면
//  코어 배율 표(api.scale('player.value'))에 넣는다. 모든 구단 선수에 똑같은 규칙 (몸값모드 V06).
var GATES = ['valuation.squadPremiumHumanAsAi', 'valuation.sellerPlanHumanAsAi'];
var on = api.settings().squad_premium !== false;
var gs = GATES.map(function (n) {
  var g = api.gate(n, on);
  if (!g.ok) api.log('게이트를 켜지 못했어요 (' + n + '): ' + g.error);
  return g;
});
api.log('구단 계획 할증 ' + (on ? '켬' : '끔') + ' (내 구단 선수도 AI 구단 규칙으로), 게이트 ' + gs.filter(function (g) { return g.ok; }).length + '/' + gs.length);

// ---- 기능 B: 활약 배율 ----
var perfOn = api.settings().perf_enabled === true;
var sc = null;          // api.scale 손잡이 (켜졌을 때만 건다)
function scaleOn(want) {
  if (want && !sc) {
    sc = api.scale('player.value');
    if (!sc.ok) { api.log('배율 표를 걸지 못했어요: ' + sc.error); sc = null; return; }
  }
  if (sc) sc.enable(want);
}
scaleOn(perfOn);
// 게임 쪽이 새로 올라오면 표가 비어 있다 -> Python이 다시 계산하게 알린다. 올라가는 순간 보낸 메시지는 사라질 수 있어서(V06),
// 켜져 있는데 표가 비어 있는 동안 15초마다 다시 알린다 (Python은 계산 중이면 무시)
api.every(15000, function () { if (perfOn && put === 0 && !feed && !job && !queue.length) api.send({ t: 'reloaded' }); });

// 이번 시즌 리그 기록 모으기: 1,000명씩 0.3초 간격 (게임을 오래 붙잡지 않게, 포텐 모드와 같은 방식)
// 줄 = [uid, 리그 UID, 포지션 무리 0~7, 출전 분, 평점 경기, 평점 합(x10), 생년월일, 내 팀 0/1, 이름(내 팀만), CA(리그 평균에만 씀), 국가대표 [분, 평점 경기, 평점 합] 또는 null, A매치 통산 출전, 사람 번호(player.link, 수상 기록 열쇠)]
var POS = ['GK', 'SW', 'DL', 'DC', 'DR', 'DM', 'ML', 'MC', 'MR', 'AML', 'AMC', 'AMR', 'ST', 'WBL', 'WBR'];
var POS_GROUP = [0, 1, 2, 1, 2, 3, 4, 5, 4, 4, 6, 4, 7, 2, 2];
var job = null, feed = null;
function row(uid, p, myCo) {
  var tm = playerTeam(p); if (!tm || !tm.club) return null;
  var i = playerInfo(p); if (!i || !i.dob) return null;
  var s = playerSeason(p, 'league') || { minutes: 0, rated: 0, ratingSum: 0 };
  var ps = playerPositions(p), g = 0, best = -1;
  if (ps) POS.forEach(function (c, k) { if ((ps[c] || 0) > best) { best = ps[c] || 0; g = POS_GROUP[k]; } });
  var mine = (myCo && tm.club.equals(myCo)) ? 1 : 0;
  var it = playerSeason(p, 'international');   // 이번 시즌 국가대표 기록
  return [uid, tm.compUid || 0, g, s.minutes, s.rated, s.ratingSum, i.dob.iso, mine, mine ? i.name : '', i.ca, (it && it.rated > 0) ? [it.minutes, it.rated, it.ratingSum] : null, getField(p, 'player.intlCaps') || 0, getField(p, 'player.link')];
}
var waitMaps = null;
function collect(id) {
  if (job) job.stop();
  if (waitMaps) { waitMaps.stop(); waitMaps = null; }
  // 대회 표는 사람·구단 표와 함께 세이브를 불러온 뒤 만들어진다 (앱 시작 직후엔 비어 있음) -> 최대 2분 기다림 (V16)
  var t0w = Date.now();
  if (!compIds().length) {
    waitMaps = api.every(2000, function () {
      if (compIds().length || Date.now() - t0w > 120000) { waitMaps.stop(); waitMaps = null; collectNow(id); }
    });
    return;
  }
  collectNow(id);
}
function collectNow(id) {
  // V16: 대회마다 가장 최근에 끝난 시즌 우승 팀 (세이브 대회 기록에 아직 없는 시즌, 코어 compLatest) -> Python 우승 계산에 더함
  try {
    var lat = [];
    compIds().forEach(function (ci) { var r = compLatest(ci); if (r && r.winner !== null) lat.push([ci, r.start, r.winner]); });
    for (var li = 0; li < lat.length; li += 2000) api.send({ t: 'latest', id: id, rows: lat.slice(li, li + 2000) });
    api.log('최근 시즌 우승 ' + lat.length + '개 대회');
  } catch (e) { api.log('최근 시즌 우승을 못 읽었어요: ' + e); }
  var uids = playerUids(), k = 0, buf = [], t0 = Date.now(), n = 0, myCo = null;
  try { var me = myInfo(); if (me && me.co && !me.co.isNull()) myCo = me.co; } catch (e) {}
  job = api.every(300, function () {
    if (!myCo) { try { var me2 = myInfo(); if (me2 && me2.co && !me2.co.isNull()) myCo = me2.co; } catch (e) {} }   // 앱 시작 직후엔 아직 없을 수 있음 (V08)
    var end = Math.min(uids.length, k + 1000);
    for (; k < end; k++) {
      var p = playerByUid(uids[k]); if (!p) continue;
      var r = null; try { r = row(uids[k], p, myCo); } catch (e) {}
      if (r) { buf.push(r); n++; }
      if (buf.length >= 500) { api.send({ t: 'rows', id: id, rows: buf }); buf = []; }
    }
    if (k >= uids.length) {
      job.stop(); job = null;
      if (buf.length) api.send({ t: 'rows', id: id, rows: buf });
      api.send({ t: 'done', id: id, n: n });
      api.log('이번 시즌 기록 모으기 끝: ' + n + '명, ' + (Date.now() - t0) + 'ms');
    }
  });
}
// 배율 넣기: 받은 줄을 쌓아 두고 2,000명씩 0.2초 간격
var queue = [], put = 0;
function feedStart() {
  if (feed) return;
  feed = api.every(200, function () {
    if (!sc) { queue = []; }
    var end = Math.min(queue.length, 2000);
    for (var j = 0; j < end; j++) { var p = playerByUid(queue[j][0]); if (p && sc.set(p, queue[j][1])) put++; }
    queue = queue.slice(end);
    if (!queue.length) { feed.stop(); feed = null; }
  });
}
api.recv(function (m) {
  if (!m || !m.t) return;
  if (m.t === 'collect') collect(m.id);
  else if (m.t === 'clear') { queue = []; put = 0; if (sc) sc.clear(); }
  else if (m.t === 'factors') {
    if (!perfOn) return;
    scaleOn(true);
    queue = queue.concat(m.rows || []);
    feedStart();
    if (m.last) api.log('활약 배율 받음: ' + (put + queue.length) + '명');
  }
});

api.onSettings(function (s) {
  on = s.squad_premium !== false;
  gs.forEach(function (g) { if (g.ok) g.set(on); });
  perfOn = s.perf_enabled === true;
  scaleOn(perfOn);
  api.log('구단 계획 할증 ' + (on ? '켬' : '끔') + ', 활약 배율 ' + (perfOn ? '켬' : '끔'));
});

// 앱 상태 표시: 할증 함수가 불린 횟수 / AI처럼 답한 횟수 (게이트마다), 활약 배율
api.status(function () {
  var a = gs[0].ok ? gs[0].stats() : null, b = gs[1].ok ? gs[1].stats() : null, c = sc ? sc.stats() : null;
  return {
    '몸값_할증': a || b ? (on ? '켬' : '끔') : '오류',
    '몸값_핵심할증_검사': a ? a.scope : '오류', '몸값_핵심할증_AI처럼': a ? a.answered : '오류',
    '몸값_파는쪽할증_검사': b ? b.scope : '오류', '몸값_파는쪽할증_AI처럼': b ? b.answered : '오류',
    '몸값_활약배율': perfOn ? (c ? '켬 ' + put + '명, 바꾼 계산 ' + c.changed : '켬 (표 없음)') : '끔'
  };
});
api.onUnload(function () { if (job) job.stop(); if (feed) feed.stop(); if (waitMaps) waitMaps.stop(); });
