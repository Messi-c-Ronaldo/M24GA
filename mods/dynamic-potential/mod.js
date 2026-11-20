// 포텐 유동 변화: 게임 쪽 부분.
// 하는 일 두 가지 (Python이 ctx.post로 시킨다):
//  collect: 리그 기록이 있는 선수의 자료를 모아 Python에 보낸다. 1,000명씩 0.3초 간격 (게임을 오래 붙잡지 않게)
//  apply:   Python이 계산한 새 PA를 api.setPlayerPA로 쓴다. 초당 9명 (코어 한도 1분 600번 아래)
// 메모리는 직접 읽지 않고 코어 함수(read.player)만 쓴다.

var DETAIL_KEYS = ['passesAttempted', 'passesCompleted', 'tacklesAttempted', 'tacklesCompleted', 'headersAttempted', 'headersWon',
  'dribbles', 'shots', 'shotsOnTarget', 'keyPasses', 'interceptions', 'xg', 'xa', 'clearances',
  'progressivePasses', 'pressuresAttempted', 'pressuresCompleted', 'npxg', 'crossesAttempted', 'crossesCompleted'];
var MIN_MINUTES = 600, MIN_RATED = 5;   // 원래 모델에서 가장 낮은 출전 조건 (18세 이하 상승 600분·5경기). 이보다 적으면 평가·비교군에 안 들어간다
var job = null, applying = null, myCo = null;
function counters(x) { return x ? [x.minutes, x.rated, x.ratingSum, x.starts, x.subs, x.goals, x.assists, x.pens] : null; }

function row(uid, p, extra) {
  var s = playerSeason(p, 'league');
  if (!extra && (!s || s.minutes < MIN_MINUTES || s.rated < MIN_RATED)) return null;
  if (!s) s = { minutes: 0, rated: 0, ratingSum: 0, starts: 0, subs: 0, goals: 0, assists: 0, pens: 0 };
  var i = playerInfo(p), ps = playerPositions(p), tr = playerTraits(p), tm = playerTeam(p);
  if (!i || !ps || !tr || !i.dob) return null;
  if (!extra && (!tm || tm.compUid === null)) return null;
  if (!tm) tm = { compUid: 0, team: '', name: '', short: '' };
  var d = playerSeasonDetail(p, 'league'), det = null;
  if (d) det = DETAIL_KEYS.map(function (k) { return (k === 'xg' || k === 'xa' || k === 'npxg') ? Math.round(d[k] * 100) : d[k]; });
  return {
    u: uid, n: i.name, b: i.dob.iso, ca: i.ca, pa: i.pa,
    pos: ['GK', 'SW', 'DL', 'DC', 'DR', 'DM', 'ML', 'MC', 'MR', 'AML', 'AMC', 'AMR', 'ST', 'WBL', 'WBR'].map(function (c) { return ps[c]; }),
    tr: [tr.professionalism, tr.ambition, tr.determination, tr.workRate, tr.flair],
    lg: tm.compUid || 0, tm: String(tm.team), tn: tm.name || tm.short || '',
    s: counters(s), d: det, x: extra ? 1 : 0,
    c: counters(playerSeason(p, 'continental')), i: counters(playerSeason(p, 'international')),   // 개선안 3 (설정이 켜졌을 때만 Python이 씀)
    m: (myCo && tm.club && tm.club.equals(myCo)) ? 1 : 0                                         // 개선안 5: 내 팀
  };
}

function collect(id, extraList) {
  if (job) job.stop();
  var uids = playerUids(), i = 0, n = 0, buf = [], t0 = Date.now(), extra = {};
  (extraList || []).forEach(function (u) { extra[u] = true; });
  myCo = null; try { var me = myInfo(); if (me && me.co && !me.co.isNull()) myCo = me.co; } catch (e) {}
  api.log('자료 모으기 시작: 선수 ' + uids.length + '명');
  job = api.every(300, function () {
    var end = Math.min(uids.length, i + 1000);
    for (; i < end; i++) {
      var p = playerByUid(uids[i]); if (!p) continue;
      var r = null; try { r = row(uids[i], p, !!extra[uids[i]]); } catch (e) {}
      if (r) { buf.push(r); n++; }
      if (buf.length >= 500) { api.send({ t: 'rows', id: id, rows: buf }); buf = []; }
    }
    if (i >= uids.length) {
      job.stop(); job = null;
      if (buf.length) api.send({ t: 'rows', id: id, rows: buf });
      api.send({ t: 'done', id: id, n: n, total: uids.length, ms: Date.now() - t0 });
      api.log('자료 모으기 끝: ' + n + '명, ' + (Date.now() - t0) + 'ms');
    }
  });
}

function apply(id, items) {
  if (applying) applying.stop();
  var k = 0, out = [];
  api.log('적용 시작: ' + items.length + '명');
  applying = api.every(1000, function () {
    for (var c = 0; c < 9 && k < items.length; c++, k++) {
      var it = items[k], r, p = playerByUid(it.u), now = p && playerInfo(p);
      if (now && now.pa === it.v) r = { ok: true, before: now.pa, after: now.pa, same: true };   // 이미 그 값 (다시 적용)
      else { try { r = api.setPlayerPA(it.u, it.v, { expect: it.e, reason: it.r }); } catch (e) { r = { ok: false, error: String(e) }; } }
      out.push({ u: it.u, ok: !!r.ok, before: r.before, after: r.after, error: r.error });
    }
    if (out.length >= 45 || k >= items.length) { api.send({ t: 'applied', id: id, results: out }); out = []; }
    if (k >= items.length) { applying.stop(); applying = null; api.send({ t: 'applyDone', id: id, n: items.length }); api.log('적용 끝: ' + items.length + '명'); }
  });
}

// 지금 PA 확인 (앱에서 되돌린 선수 찾기): [[uid, pa], ...]
function check(id, uids) {
  var out = [];
  uids.forEach(function (u) { var p = playerByUid(u), i = p && playerInfo(p); out.push([u, i ? i.pa : null]); });
  api.send({ t: 'checked', id: id, rows: out });
}

// 개선안 7: 부상 훑기. 선수 전체를 1,000명씩 1초 간격으로 계속 돈다 (한 바퀴 약 2분).
// 부상 중인 선수를 처음 보면(또는 다른 부상이면) 시작일(오늘 - 지난 일수)과 예상 전체 일수를 Python에 보낸다.
// 한 번만 봐도 시작일·예상 기간을 알 수 있어서, 한 바퀴보다 긴 부상(= 시즌 평가에 의미 있는 장기 부상)은 놓치지 않는다.
var injSeen = {}, injUids = null, injI = 0, injBuf = [];
function dayAdd(iso, n) { var d = new Date(iso + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
api.every(1000, function () {
  if (!mapsReady) return;
  var g = gameDate(); if (!g) return;
  if (!injUids || injI >= injUids.length) { injUids = playerUids(); injI = 0; }
  var end = Math.min(injUids.length, injI + 1000);
  for (; injI < end; injI++) {
    var u = injUids[injI], p = playerByUid(u); if (!p) continue;
    var r = null; try { r = playerInjury(p); } catch (e) {}
    if (!r || !r.injured || typeof r.daysSince !== 'number') continue;
    var start = dayAdd(g.iso, -r.daysSince), key = start + ':' + r.type;
    if (injSeen[u] === key) continue;
    injSeen[u] = key;
    injBuf.push({ u: u, start: start, total: r.expectedTotal, type: r.type, seen: g.iso });
  }
  if (injBuf.length && (injBuf.length >= 200 || injI >= injUids.length)) { api.send({ t: 'injuries', rows: injBuf }); injBuf = []; }
});

api.recv(function (m) {
  if (!m) return;
  if (m.t === 'collect') collect(m.id, m.extra);
  else if (m.t === 'check') check(m.id, m.uids || []);
  else if (m.t === 'apply') apply(m.id, m.items || []);
  else if (m.t === 'stopApply' && applying) { applying.stop(); applying = null; api.send({ t: 'applyDone', id: m.id, stopped: true }); }
});
api.status(function () { return { collecting: !!job, applying: !!applying }; });
api.onUnload(function () { if (job) job.stop(); if (applying) applying.stop(); });
