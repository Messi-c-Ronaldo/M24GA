// M24GA - 모드 등록·이벤트·동적 적재 (게임 쪽, Frida). GPL-3.0-or-later.
// core.js 앞에 붙는다. 게임 주소를 하나도 쓰지 않아서 게임 없이도 시험할 수 있다 (tests/test_modhost.py).
//
// 핫 리로드 (M09): 코어 스크립트는 한 번 올리면 그대로 두고, 모드만 m24gaLoadMod / m24gaUnloadMod로 올리고 내린다.
// 그래서 모드를 켜고 꺼도 코어의 데이터 표(클럽·사람 25만 개)가 사라지지 않는다.
// 모드를 내리면 그 모드가 api로 등록한 것(이벤트, 상태, 메시지 수신)을 모두 떼고, api.onUnload로 등록한 정리 함수를 부르고,
// 그 모드의 api를 죽인다(이후 api 호출은 아무 일도 안 함). 모드가 api를 거치지 않고 직접 건 Interceptor·타이머는 모드가 onUnload에서 치워야 한다.

// 훅은 코어만 건다. 같은 함수를 모드마다 걸면 꼬이므로 이벤트로 나눠 준다. 모드 오류는 모드 안에서 막는다.
var M24GA = { mods: [], on: { socialPanel: [], frame: [], dateChanged: [], saveLoaded: [], newsAdded: [], gameSaved: [], matchEnded: [] }, statusFns: {}, recvFns: {}, errs: {}, apis: {}, unloadFns: {},
  timers: {},                          // 모드 id -> api.every/after로 만든 타이머 (내릴 때 코어가 멈춘다)
  game: { date: null, save: null },    // 마지막으로 본 게임 날짜(해석한 값)와 세이브 {id, nonce}
  readGame: null,                      // core.js가 채운다: function () { return { date: u32 원값 또는 null, save: {id, nonce} 또는 null } }
  caps: {},                            // 모드 id -> 로더가 넘긴 그 모드의 기능 목록 (M14: 쓰기 API를 열지 정한다)
  settings: {}, settingsFns: {},       // 모드 id -> 설정 값 {key: 값} (password 형식은 제외), 바뀔 때 부를 함수 (M23)
  writers: {},                         // core.js가 채운다: { 'player.pa': { write(key, value, expect) -> {ok, before, after, name, error} } }
  writeTimes: {},                      // 모드 id -> 최근 1분의 쓰기 시각 (폭주 방지)
  prepareData: function (th) {} };     // prepareData는 core.js가 채운다

// ---- 게임 값 쓰기 (M14) ----
// 모드는 api.setPlayerPA 같은 이름 있는 쓰기만 쓴다. 코어가 확인한다: 기능 선언·허용(로더가 넘긴 caps), 세이브가 있는지,
// 값 범위, 폭주(1분 600번). 실제 쓰기와 대상 확인(같은 선수인지, CA보다 낮지 않은지)은 core.js의 writer가 한다.
// 쓸 때마다 로더에 {m24core: {t: 'write', ...}}를 보내 기록한다 (로더가 ~/m24ga_data/writes.jsonl에 남기고 되돌리기에 쓴다).
var M24_WRITE_CAP = { 'player.pa': 'write.player.pa' };
var M24_WRITE_MAX_PER_MIN = 600;
function m24gaWrite(id, field, key, value, opts) {
  opts = opts || {};
  var w = M24GA.writers[field];
  if (!w) {
    if (M24GA.fieldKind && M24GA.fieldKind(field)) return { ok: false, error: "'" + field + "'은 읽기만 되는 필드예요 (fields.json의 write가 safe인 필드만 쓸 수 있어요)" };
    if (!M24_WRITE_CAP[field]) return { ok: false, error: "모르는 필드 '" + field + "'" };
  }
  var cap = (w && w.cap) || M24_WRITE_CAP[field];   // 필드 등록부(M20)의 쓰기는 필드마다 기능을 갖고 온다 (기본 write.field)
  if ((M24GA.caps[id] || []).indexOf(cap) < 0 && !(opts.__py && cap === 'write.prop'))   // __py: Python 모드는 mods.py가 기능을 확인한 뒤 rpc propset으로 온다
    return { ok: false, error: "기능 '" + cap + "'을 mod.json capabilities에 선언하고 사용자 허용을 받아야 해요" };
  if (!w) return { ok: false, error: '이 게임 빌드에서는 ' + field + ' 쓰기를 지원하지 않아요' };
  if (typeof value !== 'number' || !isFinite(value) || (!w.float && value !== Math.floor(value))) return { ok: false, error: w.float ? '값은 숫자여야 해요' : '값은 정수여야 해요' };
  var g = m24gaReadGame();
  if (!g.save) return { ok: false, error: '세이브를 불러온 뒤에만 쓸 수 있어요' };
  var now = Date.now(), ts = (M24GA.writeTimes[id] || []).filter(function (t) { return now - t < 60000; });
  if (ts.length >= M24_WRITE_MAX_PER_MIN) { M24GA.writeTimes[id] = ts; return { ok: false, error: '쓰기가 너무 많아요 (1분에 ' + M24_WRITE_MAX_PER_MIN + '번까지)' }; }
  var r;
  try { r = w.write(key, value, opts.expect); } catch (e) { r = { ok: false, error: String(e) }; }
  if (r && r.ok && !r.same) {   // 값이 같아서 안 쓴 경우는 기록하지 않는다
    ts.push(now); M24GA.writeTimes[id] = ts;
    send({ m24core: { t: 'write', id: id, field: field, key: key, from: r.before, to: r.after, name: r.name || '',
      save: g.save, date: g.date && g.date.iso, reason: String(opts.reason || '').slice(0, 200) } });
  }
  return r;
}
// 속성 쓰기 (코어 0.42.0, 기능 write.prop, M71): 게임 set_property로 등록부 write.codes의 코드만. 화면 스레드에서 돌아서 Promise.
// 기록·되돌리기는 m24gaWrite와 같다 (필드 이름 = 'prop.<코드>', key = 대상의 dref 번호). tested 코드는 {tested: true}가 있어야 한다.
function m24gaSetProp(id, target, code, value, opts) {
  opts = opts || {};
  code = String(code || '');
  if (!M24GA.propKey || !M24GA.runOnUi) return Promise.resolve({ ok: false, error: '이 코어는 속성 쓰기를 지원하지 않아요' });
  var tier = M24GA.propWriteTier(code);
  if (!tier) return Promise.resolve({ ok: false, error: code + '는 쓰기가 확인된 코드가 아니에요 (api.propInfo(코드).writable)' });
  if (tier === 'tested' && opts.tested !== true) return Promise.resolve({ ok: false, error: code + '는 쓰기 시험만 한 코드예요. 쓰려면 {tested: true}를 주세요 (게임에서 결과를 꼭 확인하세요)' });
  if (typeof value === 'boolean') value = value ? 1 : 0;
  return M24GA.runOnUi(function () {
    var key = M24GA.propKey(target);
    if (key === null) return { ok: false, error: '대상을 찾지 못했거나 쓸 수 없는 대상이에요: ' + target };
    var r = m24gaWrite(id, 'prop.' + code, key, value, opts);
    if (r) { r.code = code; r.key = key; }
    return r;
  }).then(m24gaFix);
}
// 매치엔진 표 (코어 0.31.0, 기능 read.engine·write.engine, DynamicME E04)
function m24gaEngine(id, cap, fn) {
  if ((M24GA.caps[id] || []).indexOf(cap) < 0) return { ok: false, error: "기능 '" + cap + "'을 mod.json capabilities에 선언해야 해요" + (cap === 'write.engine' ? ' (사용자 허용 필요)' : '') };
  if (!M24GA.engineDump) return { ok: false, error: '이 코어는 매치엔진 표를 지원하지 않아요' };
  try { return fn(); } catch (e) { return { ok: false, error: String(e.message || e) }; }
}

// 받은 편지함 메일 (코어 0.34.0, 기능 ui.inbox): 확인·횟수 제한 뒤 코어(화면 스레드)로. 세이브에 남아서 1분에 M24_INBOX_MAX_PER_MIN통까지
var M24_INBOX_MAX_PER_MIN = 10;
function m24gaInbox(id, o) {
  if ((M24GA.caps[id] || []).indexOf('ui.inbox') < 0) return Promise.resolve({ ok: false, error: "기능 'ui.inbox'를 mod.json capabilities에 선언하고 사용자 허용을 받아야 해요" });
  if (!M24GA.inboxSend) return Promise.resolve({ ok: false, error: '이 코어는 받은 편지함 메일을 지원하지 않아요' });
  if (!o || typeof o !== 'object') return Promise.resolve({ ok: false, error: '{ title, body, from }을 넘기세요' });
  var now = Date.now(), k = 'inbox:' + id, ts = (M24GA.writeTimes[k] || []).filter(function (t) { return now - t < 60000; });
  if (ts.length >= M24_INBOX_MAX_PER_MIN) { M24GA.writeTimes[k] = ts; return Promise.resolve({ ok: false, error: '메일이 너무 많아요 (1분에 ' + M24_INBOX_MAX_PER_MIN + '통까지)' }); }
  ts.push(now); M24GA.writeTimes[k] = ts;
  return M24GA.inboxSend(o).then(function (r) {
    if (r && r.ok) { var g = m24gaReadGame(); send({ m24core: { t: 'inbox', id: id, title: r.title, chars: r.chars, save: g.save, date: g.date && g.date.iso } }); }
    return r;
  });
}

// 게임 액션 (코어 0.41.0, M65): 읽기 read.action, 실행 game.action (세이브를 바꿈, 사용자 허용 + 1분에 M24_ACTION_MAX_PER_MIN번 + 로더 기록)
var M24_ACTION_MAX_PER_MIN = 10;
function m24gaFix(r) { return r && r.error !== undefined && r.ok === undefined && !Array.isArray(r) ? { ok: false, error: r.error } : r; }
function m24gaActionsFor(id, target, opts) {
  if ((M24GA.caps[id] || []).indexOf('read.action') < 0 && (M24GA.caps[id] || []).indexOf('game.action') < 0) return Promise.resolve({ ok: false, error: "기능 'read.action'을 mod.json capabilities에 선언하세요" });
  if (!M24GA.actionsFor) return Promise.resolve({ ok: false, error: '이 코어는 액션을 지원하지 않아요' });
  return M24GA.actionsFor(target, opts).then(m24gaFix);
}
function m24gaAction(id, aid, target, opts) {
  if ((M24GA.caps[id] || []).indexOf('game.action') < 0) return Promise.resolve({ ok: false, error: "기능 'game.action'을 mod.json capabilities에 선언하고 사용자 허용을 받아야 해요" });
  if (!M24GA.actionRun) return Promise.resolve({ ok: false, error: '이 코어는 액션 실행을 지원하지 않아요' });
  var now = Date.now(), k = 'action:' + id, ts = (M24GA.writeTimes[k] || []).filter(function (t) { return now - t < 60000; });
  if (ts.length >= M24_ACTION_MAX_PER_MIN) { M24GA.writeTimes[k] = ts; return Promise.resolve({ ok: false, error: '액션이 너무 많아요 (1분에 ' + M24_ACTION_MAX_PER_MIN + '번까지)' }); }
  ts.push(now); M24GA.writeTimes[k] = ts;
  return M24GA.actionRun(aid, target, opts).then(function (r) {
    r = m24gaFix(r);
    var g = m24gaReadGame();
    send({ m24core: { t: 'action', id: id, action: aid, cls: r && r.cls, event: r && r.event, target: r && r.target, ok: !!(r && r.ok), error: r && r.error, save: g.save, date: g.date && g.date.iso } });
    return r;
  });
}

// 관계 쓰기 (코어 0.26.0, 기능 write.relation): 감독 h에게 구단 club을 좋아하는/싫어하는 구단으로 넣거나(on=true) 뺀다.
// 확인·기록·되돌리기는 m24gaWrite와 같다 (값은 글 'favClub:구단번호' / '').
function m24gaRelation(id, h, kindName, club, on, opts) {
  opts = opts || {};
  if ((M24GA.caps[id] || []).indexOf('write.relation') < 0) return { ok: false, error: "기능 'write.relation'을 mod.json capabilities에 선언하고 사용자 허용을 받아야 해요" };
  var w = M24GA.writers['human.relation'];
  if (!w || !M24GA.relationKey) return { ok: false, error: '이 코어는 관계 쓰기를 지원하지 않아요' };
  var g = m24gaReadGame();
  if (!g.save) return { ok: false, error: '세이브를 불러온 뒤에만 쓸 수 있어요' };
  var now = Date.now(), ts = (M24GA.writeTimes[id] || []).filter(function (t) { return now - t < 60000; });
  if (ts.length >= M24_WRITE_MAX_PER_MIN) { M24GA.writeTimes[id] = ts; return { ok: false, error: '쓰기가 너무 많아요 (1분에 ' + M24_WRITE_MAX_PER_MIN + '번까지)' }; }
  var k;
  try { k = M24GA.relationKey(h, kindName, club, on !== false); } catch (e) { return { ok: false, error: String(e) }; }
  if (k.error) return { ok: false, error: k.error };
  var r;
  try { r = w.write(k.key, k.value, k.expect); } catch (e) { r = { ok: false, error: String(e) }; }
  if (r && r.ok && !r.same) {
    ts.push(now); M24GA.writeTimes[id] = ts;
    send({ m24core: { t: 'write', id: id, field: 'human.relation', key: k.key, from: k.expect, to: k.value, name: r.name || '',
      save: g.save, date: g.date && g.date.iso, reason: String(opts.reason || '').slice(0, 200) } });
  }
  return r;
}
// 되돌리기 (로더가 rpc로 부른다): 지금 값이 to일 때만 from으로 되돌린다 (그 뒤 게임이나 다른 모드가 바꾼 값은 덮어쓰지 않는다)
function m24gaUndoWrite(field, key, from, to) {
  var w = M24GA.writers[field];
  if (!w) return { ok: false, error: '쓰기 기능 없음: ' + field };
  var g = m24gaReadGame();
  if (!g.save) return { ok: false, error: '세이브가 없어요' };
  if (w.ui && M24GA.runOnUi) return M24GA.runOnUi(function () { return w.write(key, from, to); });   // 속성 쓰기(0.42.0)는 화면 스레드에서
  try { return w.write(key, from, to); } catch (e) { return { ok: false, error: String(e) }; }
}

// ---- 게임 날짜와 세이브 (M12) ----
// 날짜 원값 u32: 상위 16비트 = 연도, 하위 9비트 = 연중 일수(1~366). (FM24 Dynamic PA의 해석, 이 빌드에서 2035-04-25로 실측 확인)
function m24gaPad(n) { return n < 10 ? '0' + n : '' + n; }
function m24gaDecodeDate(raw) {
  if (typeof raw !== 'number') return null;
  var y = raw >>> 16, doy = raw & 0x1ff;
  if (y < 1900 || y > 2300 || doy < 1 || doy > 366) return null;
  var dt = new Date(Date.UTC(y, 0, doy));
  if (dt.getUTCFullYear() !== y) return null;          // 윤년이 아닌 해의 366일
  var m = dt.getUTCMonth() + 1, d = dt.getUTCDate();
  return { y: y, m: m, d: d, doy: doy, iso: y + '-' + m24gaPad(m) + '-' + m24gaPad(d) };
}
function m24gaDaysBetween(a, b) { return Math.round((Date.UTC(b.y, b.m - 1, b.d) - Date.UTC(a.y, a.m - 1, a.d)) / 86400000); }
function m24gaReadGame() {
  if (!M24GA.readGame) return { date: null, save: null };
  var r;
  try { r = M24GA.readGame() || {}; } catch (e) { return { date: null, save: null }; }
  var s = r.save && r.save.id ? { id: r.save.id >>> 0, nonce: (r.save.nonce || 0) >>> 0 } : null;
  return { date: m24gaDecodeDate(r.date), save: s };
}
// 모드가 부르는 전역 함수: 지금 게임 날짜 {y, m, d, doy, iso} (세이브를 안 불러왔으면 null), 지금 세이브 {id, nonce} (없으면 null)
function gameDate() { return m24gaReadGame().date; }
function saveInfo() { return m24gaReadGame().save; }
function m24gaSaveKey(s) { return s ? s.id + ':' + s.nonce : null; }
// 0.5초마다 날짜와 세이브를 본다 (게임 함수를 가로채지 않는다). 바뀌면 이벤트를 내고 로더에도 알린다.
// 이 콜백은 화면 스레드가 아니다: 화면 글자를 바꾸는 일은 frame/socialPanel에서 한다.
function m24gaPollGame() {
  var now = m24gaReadGame(), g = M24GA.game;
  if (m24gaSaveKey(now.save) !== m24gaSaveKey(g.save)) {     // 다른 세이브를 불러옴 (또는 처음 봄 / 메인 메뉴로 나감)
    g.save = now.save; g.date = now.date;
    send({ m24core: { t: 'game', date: now.date && now.date.iso, save: now.save } });
    if (now.save) m24gaEmit('saveLoaded', { id: now.save.id, nonce: now.save.nonce, date: now.date });
    return;
  }
  if (!now.date) return;
  if (!g.date) { g.date = now.date; send({ m24core: { t: 'game', date: now.date.iso, save: now.save } }); return; }
  if (now.date.iso !== g.date.iso) {
    var from = g.date;
    g.date = now.date;
    send({ m24core: { t: 'game', date: now.date.iso, save: now.save } });
    m24gaEmit('dateChanged', { from: from, to: now.date, days: m24gaDaysBetween(from, now.date) });
  }
}
var M24_POLL_MS = 500;
setInterval(m24gaPollGame, M24_POLL_MS);

// ---- 타이머 (M12): api.every / api.after. 모드를 내리면 코어가 멈춘다 ----
function m24gaTimer(id, ms, fn, repeat) {
  ms = Math.max(50, +ms || 0);
  var list = M24GA.timers[id] || (M24GA.timers[id] = []), h = null;
  var t = { stop: function () {
    if (h === null) return;
    (repeat ? clearInterval : clearTimeout)(h); h = null;
    var i = list.indexOf(t); if (i >= 0) list.splice(i, 1);
  } };
  h = (repeat ? setInterval : setTimeout)(function () {
    if (!repeat) t.stop();
    if (m24gaOff(id)) return;
    try { fn(); } catch (e) { m24gaModError(id, repeat ? 'every' : 'after', e); }
  }, ms);
  list.push(t);
  return t;
}
// 모드 오류 감시 (M05): 모드 콜백이 던진 오류를 센다. 5초 안에 25번을 넘으면 그 모드의 콜백을 더 이상 부르지 않고 로더에 알린다
// (게임과 다른 모드를 지킨다. 로더는 그 모드를 자동으로 끄고 기록한다). 처음 몇 개의 오류는 로더 기록에 남긴다.
var M24_ERR_MAX = 25, M24_ERR_WINDOW = 5000;
function m24gaModError(id, where, e) {
  var st = M24GA.errs[id] || (M24GA.errs[id] = { n: 0, t0: 0, total: 0, off: false });
  var now = Date.now();
  if (now - st.t0 > M24_ERR_WINDOW) { st.t0 = now; st.n = 0; }
  st.n++; st.total++;
  var msg = String((e && e.stack) || e).slice(0, 400);
  if (st.n <= 3) send({ m24core: { t: 'error', id: id, where: where, msg: msg } });
  if (st.n >= M24_ERR_MAX && !st.off) { st.off = true; send({ m24core: { t: 'disabled', id: id, where: where, msg: msg } }); }
}
function m24gaOff(id) { var st = M24GA.errs[id]; return !!(st && st.off); }
// 모드 <-> 모드 Python 메시지 (7a단계): api.send(obj)는 호스트가 그 모드의 Python 수신함(ctx.recv)에 넣고,
// Python의 ctx.post(obj)는 api.recv(fn)로 온다. 코어가 recv를 하나만 걸어 두고 모드 id로 나눠 준다.
function m24gaRecv() {
  recv('m24ga', function (msg) {
    try { var f = M24GA.recvFns[msg.m]; if (f && !m24gaOff(msg.m)) f(msg.d); } catch (e) { m24gaModError(msg.m, 'recv', e); }
    m24gaRecv();   // recv는 한 번만 받으므로 다시 건다
  });
}
m24gaRecv();
function m24gaEmit(ev, arg) {
  var hs = M24GA.on[ev];
  for (var i = 0; i < hs.length; i++) {
    if (m24gaOff(hs[i].id)) continue;
    try { hs[i].fn(arg); } catch (e) { m24gaModError(hs[i].id, ev, e); }
  }
}
// ---- 게임 함수 끼어들기 (M22, 기능 hook.function): 함수 등록부(core/functions.json)의 함수에 모드가 before/after를 건다 ----
// 코어(core.js)가 함수마다 Interceptor를 하나만 걸고(M24GA.hookInstall/hookRelease), 여기서 모드들에게 나눠 준다.
// 모드 콜백 오류는 그 모드 안에서 막고(m24gaModError, 반복되면 그 모드만 꺼짐), 모드를 내리면 그 모드의 끼어들기를 모두 뗀다.
// 마지막 모드가 떼면 코어가 Interceptor를 푼다. 콜백은 게임 스레드에서 불리므로 짧게 해야 한다 (걸린 시간을 센다).
M24GA.hooks = {};            // 함수 이름 -> [{ id, before, after, calls, errs, ms }]
M24GA.hookInstall = null;    // core.js가 채운다: function (name) -> { ok, error }
M24GA.hookRelease = null;    // core.js가 채운다: function (name)
M24GA.funcInfo = null;       // core.js가 채운다: function (name) -> 등록부 항목 또는 null
// ---- 게이트 (코어 0.15.0, 기능 hook.gate): 등록된 게이트를 모드가 켠다. 여러 모드가 같은 게이트를 쓰면 하나라도 켜면 켜짐 ----
M24GA.gateUsers = {};        // 게이트 이름 -> { 모드 id: 켬 여부 }
function m24gaGateApply(name) {
  var u = M24GA.gateUsers[name] || {}, ids = Object.keys(u);
  if (!ids.length) { delete M24GA.gateUsers[name]; if (M24GA.gateRelease) M24GA.gateRelease(name); return; }
  if (M24GA.gateSet) M24GA.gateSet(name, ids.some(function (k) { return u[k]; }));
}
function m24gaGateAdd(id, name, on) {
  if (!M24GA.gateInstall) return { ok: false, error: '이 코어는 게이트를 지원하지 않아요' };
  var r = M24GA.gateInstall(name); if (!r || !r.ok) return { ok: false, error: (r && r.error) || '걸지 못했어요' };
  (M24GA.gateUsers[name] = M24GA.gateUsers[name] || {})[id] = on !== false;
  m24gaGateApply(name);
  return { ok: true,
    set: function (v) { if (M24GA.gateUsers[name] && id in M24GA.gateUsers[name]) { M24GA.gateUsers[name][id] = !!v; m24gaGateApply(name); } },
    stats: function () { return M24GA.gateStats ? M24GA.gateStats(name) : null; },
    stop: function () { if (M24GA.gateUsers[name]) { delete M24GA.gateUsers[name][id]; m24gaGateApply(name); } } };
}
// ---- 배율 표 (코어 0.17.0, 기능 hook.scale): 등록부의 scale 함수 반환값에 객체별 배율. 함수 하나에 모드 하나 ----
M24GA.scaleOwners = {};      // 함수 이름 -> 모드 id
function m24gaScaleAdd(id, name) {
  if (!M24GA.scaleInstall) return { ok: false, error: '이 코어는 배율 표를 지원하지 않아요' };
  var r = M24GA.scaleInstall(name, id); if (!r || !r.ok) return { ok: false, error: (r && r.error) || '걸지 못했어요' };
  M24GA.scaleOwners[name] = id;
  function mine() { return M24GA.scaleOwners[name] === id; }
  return { ok: true,
    // 배율 하나: obj = 열쇠 객체(예: 선수), factor = 곱할 수 (1이면 그대로). 반환 true/false (표가 꽉 차면 false)
    set: function (obj, factor) { return mine() ? M24GA.scaleSet(name, obj, factor) : false; },
    get: function (obj) { return mine() ? M24GA.scaleGet(name, obj) : 1; },
    clear: function () { if (mine()) M24GA.scaleClear(name); },          // 모든 배율을 1로
    enable: function (on) { if (mine()) M24GA.scaleEnable(name, on !== false); },
    stats: function () { return M24GA.scaleStats ? M24GA.scaleStats(name) : null; },   // { calls, changed, entries, on }
    stop: function () { if (mine()) { delete M24GA.scaleOwners[name]; M24GA.scaleRelease(name); } } };
}
function m24gaScaleForget(id) { for (var n in M24GA.scaleOwners) if (M24GA.scaleOwners[n] === id) { delete M24GA.scaleOwners[n]; if (M24GA.scaleRelease) M24GA.scaleRelease(n); } }
function m24gaGateForget(id) { for (var n in M24GA.gateUsers) { if (id in M24GA.gateUsers[n]) { delete M24GA.gateUsers[n][id]; m24gaGateApply(n); } } }
function m24gaHookAdd(id, name, h) {
  var info = M24GA.funcInfo ? M24GA.funcInfo(name) : null;
  if (!info) return { ok: false, error: "모르는 함수 '" + name + "' (docs/FUNCTIONS.md, CLI functions)" };
  if (info.owner === 'core') return { ok: false, error: "'" + name + "'은 코어가 이미 걸어 둔 함수예요. api.on('" + (info.event || '?') + "')을 쓰세요" };
  if (!h || (typeof h.before !== 'function' && typeof h.after !== 'function')) return { ok: false, error: 'before나 after 함수가 필요해요' };
  var list = M24GA.hooks[name] || (M24GA.hooks[name] = []);
  if (!list.length) {
    var r = M24GA.hookInstall ? M24GA.hookInstall(name) : { ok: false, error: '이 코어는 끼어들기를 지원하지 않아요' };
    if (!r || !r.ok) return { ok: false, error: (r && r.error) || '걸지 못했어요' };
  }
  var e = { id: id, before: h.before, after: h.after, calls: 0, errs: 0, ms: 0 };
  list.push(e);
  return { ok: true, stop: function () { m24gaHookRemove(name, e); } };
}
function m24gaHookRemove(name, e) {
  var list = M24GA.hooks[name]; if (!list) return;
  var i = list.indexOf(e); if (i < 0) return;
  list.splice(i, 1);
  if (!list.length && M24GA.hookRelease) { try { M24GA.hookRelease(name); } catch (x) {} }
}
// core.js의 Interceptor가 부른다. phase = 'before' | 'after'. ev는 한 번의 호출 동안 before와 after가 같은 객체를 받는다 (ev.data에 넘길 값을 둔다)
function m24gaHookCall(name, phase, ev) {
  var list = M24GA.hooks[name]; if (!list || !list.length) return;
  var copy = list.slice();
  for (var i = 0; i < copy.length; i++) {
    var e = copy[i], fn = e[phase];
    if (typeof fn !== 'function' || m24gaOff(e.id)) continue;
    var t = Date.now();
    ev.mod = e.id;
    try { fn(ev); } catch (x) { e.errs++; m24gaModError(e.id, 'hook ' + name + ' ' + phase, x); }
    e.ms += Date.now() - t; if (phase === 'before' || typeof e.before !== 'function') e.calls++;
  }
  ev.mod = null;
}
function m24gaHookForget(id) {
  for (var name in M24GA.hooks) {
    M24GA.hooks[name].filter(function (e) { return e.id === id; }).forEach(function (e) { m24gaHookRemove(name, e); });
  }
}
function m24gaHookStats() {
  var out = {};
  for (var name in M24GA.hooks) out[name] = M24GA.hooks[name].map(function (e) { return { mod: e.id, calls: e.calls, errs: e.errs, ms: e.ms }; });
  return out;
}

function m24gaForget(id) {   // 모드가 api로 등록한 것을 모두 뗀다
  for (var ev in M24GA.on) M24GA.on[ev] = M24GA.on[ev].filter(function (h) { return h.id !== id; });
  delete M24GA.statusFns[id]; delete M24GA.recvFns[id]; delete M24GA.unloadFns[id]; delete M24GA.settings[id]; delete M24GA.settingsFns[id];
  (M24GA.timers[id] || []).slice().forEach(function (t) { t.stop(); });
  delete M24GA.timers[id];
  m24gaHookForget(id);   // (M22) 이 모드의 게임 함수 끼어들기
  m24gaGateForget(id);   // (V03) 이 모드가 켠 게이트
  m24gaScaleForget(id);  // (V06) 이 모드의 배율 표
  if (M24GA.panelCloseMod) { try { M24GA.panelCloseMod(id); } catch (e) {} }   // (M45) 이 모드의 게임 안 패널
  M24GA.mods = M24GA.mods.filter(function (x) { return x !== id; });
}
function registerMod(id, init, meta) {   // meta = { caps: [이 모드의 기능] } (로더가 넣는다, M14)
  var alive = true, talk = true;   // alive: 등록 가능, talk: log/send 가능 (내리는 중 onUnload 안에서는 talk만)
  var api = {
    id: id,
    on: function (ev, fn) { if (!M24GA.on[ev]) throw new Error('unknown event ' + ev); if (alive) { M24GA.on[ev].push({ id: id, fn: fn }); if (M24GA.eventHook) M24GA.eventHook(ev); } },   // 코어 0.35.0: newsAdded·gameSaved는 처음 구독할 때 코어가 끼어든다
    status: function (fn) { if (alive) M24GA.statusFns[id] = fn; },
    // (코어 0.12.0) 이 모드의 설정 값 {key: 값} (mod.json settings, 파일에 없으면 default, 비밀번호 형식은 빠져요). 부를 때마다 새 복사본.
    // 사용자 허용이 필요 없어요. 앱에서 설정을 바꾸면 onSettings 함수가 새 값으로 불려요 (한 모드에 하나, 게임 스레드가 아닐 수 있어요)
    settings: function () { var s = M24GA.settings[id] || {}, o = {}; for (var k in s) o[k] = s[k]; return o; },
    onSettings: function (fn) { if (alive) M24GA.settingsFns[id] = fn; },
    // 데이터 표 준비: 세이브가 불러와진 뒤(첫 소셜 패널) 한 번 표를 만들고, 패널에서 값 종류를 얻는다
    prepareData: function (th) { if (alive) M24GA.prepareData(th); },
    log: function (m) { if (talk) send('[' + id + '] ' + m); },
    send: function (d) { if (talk) send({ m24: id, d: d }); },
    recv: function (fn) { if (alive) M24GA.recvFns[id] = fn; },
    // 모드를 내릴 때(끄기, 새 버전으로 바꾸기) 불린다. 모드가 직접 건 Interceptor·타이머·바꿔 둔 화면 글자를 여기서 치운다
    onUnload: function (fn) { if (alive) (M24GA.unloadFns[id] = M24GA.unloadFns[id] || []).push(fn); },
    alive: function () { return alive; },
    // (코어 0.5.0) ms마다 fn을 부른다 / ms 뒤 한 번 부른다. 반환값의 stop()으로 멈춘다. 모드를 내리면 코어가 알아서 멈춘다.
    // 최소 50ms. 화면 스레드가 아니다 (화면 글자를 바꾸는 일은 frame/socialPanel에서)
    every: function (ms, fn) { return alive ? m24gaTimer(id, ms, fn, true) : { stop: function () {} }; },
    after: function (ms, fn) { return alive ? m24gaTimer(id, ms, fn, false) : { stop: function () {} }; },
    // (코어 0.7.0, 기능 write.player.pa) 선수 잠재력(PA)을 바꾼다. uid = 선수 UID, pa = 1~200 정수(CA보다 낮을 수 없음).
    // opts.expect: 지금 PA가 이 값일 때만 쓴다, opts.reason: 기록에 남길 이유. 반환 {ok, before, after, name, error}. 모든 쓰기는 기록되고 앱에서 되돌릴 수 있다
    setPlayerPA: function (uid, pa, opts) { return alive ? m24gaWrite(id, 'player.pa', uid >>> 0, pa, opts) : { ok: false, error: '내려간 모드' }; },
    // (코어 0.10.0, 기능 write.field 또는 필드의 cap) 필드 등록부의 write: safe 필드를 쓴다. obj = 게임 객체(또는 그 종류의 key, 예: 선수 UID).
    // 확인·기록·되돌리기는 setPlayerPA와 같다. 반환 {ok, before, after, name, error}
    // (코어 0.11.0, 기능 hook.function, 사용자 허용 필요) 함수 등록부의 게임 함수에 끼어든다: api.hook('이름', { before: function (ev) {}, after: function (ev) {} }).
    // ev.args(형식대로 바꾼 인자), ev.raw(i), ev.caller('fm+0x...'), ev.tid, ev.data(before->after로 넘길 칸), after에서 ev.ret.
    // hook이 modify인 함수만 ev.setArg(i, v) / ev.setRet(v). 반환 { ok, stop(), error }. 모드를 내리면 코어가 알아서 뗀다. 콜백은 게임 스레드라 짧게
    hook: function (name, h) { return alive ? m24gaHookAdd(id, name, h) : { ok: false, error: '내려간 모드' }; },
    // (코어 0.15.0, 기능 hook.gate, 사용자 허용 필요) 함수 등록부의 게이트를 켠다: api.gate('valuation.squadPremiumHumanAsAi').
    // 반환 { ok, error, set(켬/끔), stats() -> { scope, inScope, answered, on }, stop() }. 모드를 내리면 코어가 알아서 푼다
    gate: function (name, on) { return alive ? m24gaGateAdd(id, name, on) : { ok: false, error: '내려간 모드' }; },
    // (코어 0.17.0, 기능 hook.scale, 사용자 허용 필요) 등록부에서 scale이 있는 함수(예: 'player.value')의 반환값에 객체별 배율을 곱한다.
    // 반환 { ok, error, set(obj, factor), get(obj), clear(), enable(on), stats() -> { calls, changed, entries, on }, stop() }. 게임 상한으로 자른다. 모드를 내리면 코어가 푼다
    scale: function (name) { return alive ? m24gaScaleAdd(id, name) : { ok: false, error: '내려간 모드' }; },
    // (코어 0.23.0, 기능 ui.panel) 게임 안에 FM 모양 대화상자를 띄운다 (M45). form = 양식 (docs/MODDING.md "게임 안 패널"),
    // cb(ev) = 이벤트: ev.id(칸·버튼 id 또는 'open'·'close'·'error'), ev.kind, ev.value, ev.values(), ev.panel. 화면 스레드에서 불리니 짧게.
    // 반환 { ok, error, slot, isOpen(), get(id), values(), close() }. 모드를 내리면 코어가 닫는다. panel.available()로 쓸 수 있는지 먼저 본다
    // (코어 0.26.0, 기능 write.relation) 감독 h의 좋아하는/싫어하는 구단: api.setRelation(myHuman(), 'dislikedClub', clubByName('토트넘'), true, {reason}).
    // on=false면 뺀다. 화면 스레드(패널 콜백·frame)에서만. 반환 {ok, same, error}. 기록되고 앱에서 되돌릴 수 있다
    setRelation: function (h, kindName, club, on, opts) { return alive ? m24gaRelation(id, h, kindName, club, on, opts) : { ok: false, error: '내려간 모드' }; },
    // (코어 0.31.0, 기능 read.engine / write.engine) 매치엔진 표 (DynamicME). 표 = 'weights'|'physics'|'momentum'|'ratings'|'styles'(코어 0.32.0)|'xg'(코어 0.33.0).
    // dump(표) -> 메모리 그대로 (engineDump 모양), write(표, spec) -> {ok, written, missing, error}. 있는 칸에만 쓰고, 게임이 진행 중이면 거절.
    // 메모리 값은 세이브에 남지 않아요 (게임을 다시 켜면 원본). 쓰기 계획은 Python pylib/m24engine.py plan()으로 만들어요
    engine: {
      dump: function (name) { return alive ? m24gaEngine(id, 'read.engine', function () { return M24GA.engineDump(name); }) : { error: '내려간 모드' }; },
      write: function (name, spec) { return alive ? m24gaEngine(id, 'write.engine', function () { return M24GA.engineWrite(name, spec, false); }) : { ok: false, error: '내려간 모드' }; }
    },
    // (코어 0.34.0, 기능 ui.inbox) 게임 받은 편지함에 메일 한 통: api.inbox.send({ title, body, from }) -> Promise {ok, error}.
    // from = 사람 객체(myHuman(), personByName(이름).person 등, 없으면 내 감독). '보낸이의 말: 제목'으로 보이고 세이브에 남아요 (되돌리기 없음)
    inbox: {
      send: function (o) { return alive ? m24gaInbox(id, o) : Promise.resolve({ ok: false, error: '내려간 모드' }); },
      available: function () { return !!M24GA.inboxSend; }
    },
    // (코어 0.36.0, 기능 read.prop) 게임 속성 코드 읽기 (등록부 core/properties.json, docs/PROPERTIES.md).
    // 대상 = 객체 포인터(어느 칸이든) 또는 'me' | 'myteam' | 'myclub' | 'myjob'(내 감독 계약) | 'p123'/'s45'(사람 참조) | 'team:<번호>' | 'comp:<번호>'.
    // prop -> 값 / null(빈 값) / undefined(답하지 않는 코드). 모르는 객체·막은 코드는 예외. props(대상, {re, codes, empty}) -> {코드: 값}
    prop: function (obj, code) { return M24GA.propGet(obj, code); },
    props: function (obj, opts) { return M24GA.propsAll(obj, opts); },
    propInfo: function (code) { return M24GA.propInfo(code); },
    deref: function (d) { return M24GA.propDeref(d); },
    // (코어 0.40.0, 기능 read.prop) 리그 경기 결과 (보도 안 되는 경기 포함): 대회 객체 또는 'myleague'. 지난번 부른 뒤 끝난 경기 [{home, away, homeGoals, awayGoals, date, fixture, comp}].
    // 처음 부르면 기준만 잡고 []. dateChanged마다 부르면 그날 경기가 나와요
    leagueResults: function (comp) { return M24GA.leagueResults(comp); },
    // (코어 0.41.0) 게임 액션 (docs/ACTIONS.md). 화면 스레드에서 돌아 Promise를 돌려줘요.
    // actionsFor(대상, {all}) -> [{id, cls, hidden, disabled, canRun, events, args}] (기능 read.action): 게임 메뉴가 그 대상에 보여 주는 명령
    // action(id, 대상, {event, danger}) -> {ok, error, handled} (기능 game.action, 세이브를 바꿈): 게임이 보여 주는 명령일 때만 그 인자 그대로 실행
    actionsFor: function (target, opts) { return alive ? m24gaActionsFor(id, target, opts) : Promise.resolve({ ok: false, error: '내려간 모드' }); },
    action: function (aid, target, opts) { return alive ? m24gaAction(id, aid, target, opts) : Promise.resolve({ ok: false, error: '내려간 모드' }); },   // {dref} -> 객체 (사람·구단·팀·대회), 모르면 null
    panel: {
      open: function (form, cb) { return alive ? m24gaPanelOpen(id, form, cb) : { ok: false, error: '내려간 모드' }; },
      available: function () { return !!(M24GA.panelAvailable && M24GA.panelAvailable()); }
    },
    // setProp(대상, '코드', 값, {expect, reason, tested}) -> Promise {ok, before, after, code, key, error} (기능 write.prop, 코어 0.42.0)
    setProp: function (target, code, value, opts) { return alive ? m24gaSetProp(id, target, code, value, opts) : Promise.resolve({ ok: false, error: '내려간 모드' }); },
    setField: function (obj, name, value, opts) {
      if (!alive) return { ok: false, error: '내려간 모드' };
      var kind = M24GA.fieldKind ? M24GA.fieldKind(name) : null;
      if (!kind) return { ok: false, error: "모르는 필드 '" + name + "' (fieldNames()로 목록을 보세요)" };
      var key = (obj && typeof obj.add === 'function') ? M24GA.fieldKey(obj, kind) : obj;
      if (key === null || key === undefined) return { ok: false, error: "객체가 '" + kind + "' 종류가 아니에요" };
      return m24gaWrite(id, name, key, value, opts);
    }
  };
  api._close = function () { alive = false; };
  api._kill = function () { alive = false; talk = false; };
  M24GA.apis[id] = api;
  M24GA.caps[id] = (meta && meta.caps) || [];
  M24GA.settings[id] = (meta && meta.settings) || {};
  delete M24GA.errs[id];   // 다시 올리는 모드는 오류 횟수를 새로 센다
  try { init(api); M24GA.mods.push(id); send('mod loaded: ' + id); return true; }
  catch (e) {
    send('mod load failed: ' + id + ' ' + (e.stack || e));
    m24gaForget(id); api._kill(); delete M24GA.apis[id];   // 로드하다 만 모드가 등록해 둔 것을 거둔다
    send({ m24core: { t: 'loadfail', id: id, where: 'init', msg: String((e && e.stack) || e).slice(0, 400) } });
    return false;
  }
}
// 모드 하나를 내린다. 반환: 내렸으면 true, 올라가 있지 않았으면 false
function m24gaUnloadMod(id) {
  var api = M24GA.apis[id];
  if (!api) return false;
  var fns = M24GA.unloadFns[id] || [];
  m24gaForget(id);
  api._close();             // 새로 등록은 못 하지만 정리 함수 안에서 log/send는 된다
  delete M24GA.apis[id];
  for (var i = 0; i < fns.length; i++) { try { fns[i](); } catch (e) { m24gaModError(id, 'unload', e); } }
  api._kill();
  send('mod unloaded: ' + id);
  return true;
}
// 모드 하나를 (다시) 올린다. src = 로더가 만든 'registerMod("id", function (api) { ... });' 한 조각.
// 같은 id가 올라가 있으면 먼저 내린다. 반환 {ok, error}: 문법 오류면 ok=false, init에서 던지면 코어가 loadfail을 알리고 ok=false
// 앱에서 설정이 바뀌면 로더가 부른다 (rpc setsettings): 값을 바꾸고 모드의 onSettings를 부른다
function m24gaSetSettings(id, vals) {
  if (!M24GA.apis[id]) return false;
  M24GA.settings[id] = vals || {};
  var f = M24GA.settingsFns[id];
  if (f && !m24gaOff(id)) { var o = {}; for (var k in M24GA.settings[id]) o[k] = M24GA.settings[id][k]; try { f(o); } catch (e) { m24gaModError(id, 'onSettings', e); } }
  return true;
}
function m24gaLoadMod(id, src) {
  m24gaUnloadMod(id);
  var before = M24GA.apis[id];
  try { (0, eval)(src); }   // 전역에서 평가한다 (모드 코드가 코어 전역 함수·표를 그대로 본다)
  catch (e) { return { ok: false, error: String((e && e.stack) || e).slice(0, 400) }; }
  var ok = M24GA.mods.indexOf(id) >= 0 && M24GA.apis[id] !== before;
  return ok ? { ok: true } : { ok: false, error: 'registerMod(' + id + ')가 불리지 않았거나 init에서 실패' };
}

// ---- 게임 안 패널 양식 -> 패널 XML (M44, 코어 0.23.0 준비) ----
// 모드는 게임 패널 XML을 직접 쓰지 않고 "양식"만 적는다. 코어가 이 함수로 XML을 만들어 FM 사용자 폴더의 패널 칸
// (panels/m24ga/slotNN.xml, 로더가 게임을 켜기 전에 만들어 둠)에 쓰고 게임의 일반 대화상자로 띄운다 (M43).
// 같은 양식을 앱 창으로 그릴 수도 있다. 게임 주소를 쓰지 않아서 게임 없이 시험한다 (tests/test_panel.py).
//   form = { title, text?, fields: [{ id, type: 'text'|'number'|'check'|'select'|'label'|'person'|'club', label, value?, options?: [{value, label}] }],
//            person/club 칸(코어 0.29.0)의 value = 지금 고른 것 { ref | uid, name, label? } (창에 "지금: …"으로 보임). refreshOnPick: false면 고른 뒤 창을 다시 그리지 않음
//            buttons: [{ id, label }] }   (닫기 버튼은 코어가 늘 붙인다: id 'close')
// 반환 { ok, xml, widgets: {필드 id: 위젯 4글자}, events: {이벤트 4글자: {id, kind}} } 또는 { ok: false, error }
var M24_PANEL_LIMITS = { fields: 40, buttons: 6, text: 400, label: 80, options: 60 };
var M24_PANEL_DIR = null;   // 로더가 넣는다: FM 사용자 폴더의 panels/m24ga/ (없으면 null = 게임 안 패널을 못 씀)
var M24_PANEL_SLOTS = 8;    // 패널 칸 수 (slot01~slot08). loader/panels.py의 SLOTS와 같아야 한다
function m24gaXmlEsc(s) {
  return String(s === undefined || s === null ? '' : s).replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&apos;');
}
function m24gaPanelOpen(id, form, cb) {
  if ((M24GA.caps[id] || []).indexOf('ui.panel') < 0) return { ok: false, error: "기능 'ui.panel'을 mod.json capabilities에 선언해야 해요" };
  if (!M24GA.panelOpen) return { ok: false, error: '이 코어는 게임 안 패널을 지원하지 않아요' };
  try { return M24GA.panelOpen(id, form, cb); } catch (e) { return { ok: false, error: String(e.message || e) }; }
}
function m24gaHex2(n) { return ('0' + n.toString(16)).slice(-2); }
function m24gaPanelXml(form) {
  if (!form || typeof form !== 'object') return { ok: false, error: '양식은 객체여야 해요' };
  var L = M24_PANEL_LIMITS, fields = form.fields || [], buttons = form.buttons || [];
  if (!Array.isArray(fields) || !Array.isArray(buttons)) return { ok: false, error: 'fields와 buttons는 배열이어야 해요' };
  if (fields.length > L.fields) return { ok: false, error: '칸은 ' + L.fields + '개까지예요' };
  if (buttons.length > L.buttons) return { ok: false, error: '버튼은 ' + L.buttons + '개까지예요' };
  var seen = { close: 1 }, widgets = {}, events = {}, n = 0, body = [];
  function cut(s, max) {   // 제어 문자를 먼저 지우고 자른다
    s = String(s === undefined || s === null ? '' : s).replace(/[\x00-\x08\x0b\x0c\x0e-\x1f]/g, '');
    return s.length > max ? s.slice(0, max) : s;
  }
  function newIds(id, kind) {
    if (typeof id !== 'string' || !/^[A-Za-z0-9_.-]{1,40}$/.test(id)) throw new Error("id '" + id + "'는 영문·숫자·_.- 1~40자여야 해요");
    if (seen[id]) throw new Error("id '" + id + "'가 겹쳐요 ('close'는 코어가 써요)");
    seen[id] = 1;
    var w = 'mw' + m24gaHex2(n), e = 'me' + m24gaHex2(n); n++;
    widgets[id] = w; events[e] = { id: id, kind: kind };
    return { w: w, e: e };
  }
  try {
    body.push('\t<string id="title" value="' + m24gaXmlEsc(cut(form.title || 'M24GA', L.label)) + '"/>');
    body.push('\t<attachment_group class="vertical_arrange_autosize" vertical_gap="10"/>');
    body.push('\t<layout class="centre_in_parent_attachment"/>');
    if (form.text) body.push('\t<widget class="text" auto_size="vertical" multiline="true" text="' + m24gaXmlEsc(cut(form.text, L.text)) + '"/>');
    fields.forEach(function (f) {
      if (!f || typeof f !== 'object') throw new Error('칸은 객체여야 해요');
      var t = f.type || 'text', label = m24gaXmlEsc(cut(f.label, L.label));
      if (t === 'label') {
        var lid = f.id ? newIds(f.id, 'label') : null;
        body.push('\t<widget class="text"' + (lid ? ' id="' + lid.w + '"' : '') + ' auto_size="vertical" multiline="true" text="' + m24gaXmlEsc(cut(f.value !== undefined ? f.value : f.label, L.text)) + '"/>');
      } else if (t === 'text' || t === 'number') {
        var a = newIds(f.id, 'change');
        if (label) body.push('\t<widget class="text" auto_size="vertical" text="' + label + '"/>');
        body.push('\t<widget class="edit_box" id="' + a.w + '" height="28"' + (f.value !== undefined ? ' text="' + m24gaXmlEsc(cut(f.value, L.text)) + '"' : '') + '>');
        body.push('\t\t<record id="changed_event"><flags id="event_id" value="' + a.e + '"/></record>');
        body.push('\t</widget>');
      } else if (t === 'check') {
        var c = newIds(f.id, 'check');
        body.push('\t<widget class="check_box" id="' + c.w + '" click_event="' + c.e + '" height="25"' + (f.value ? ' selected="true"' : '') + ' text="' + label + '"/>');
      } else if (t === 'select') {
        var opts = f.options || [];
        if (!Array.isArray(opts) || !opts.length) throw new Error("select 칸 '" + f.id + "'에 options가 없어요");
        if (opts.length > L.options) throw new Error('select 항목은 ' + L.options + '개까지예요');
        var s = newIds(f.id, 'select');
        // (코어 0.29.0) value가 있으면 그 항목 이름을 단추 글로 (게임 단추의 value 속성은 글을 바꾸지 않는다, C09 실기). 이름 칸은 위에 따로
        var cur = null;
        if (f.value !== undefined && f.value !== null) opts.forEach(function (o) { var v = (o && typeof o === 'object') ? o.value : o; if (cur === null && v === f.value) cur = (o && typeof o === 'object') ? (o.label !== undefined ? o.label : o.value) : o; });
        if (cur !== null && label) body.push('\t<widget class="text" auto_size="vertical" text="' + label + '"/>');
        body.push('\t<widget class="popup_button" id="' + s.w + '" select_event="' + s.e + '" height="28" text="' + (cur !== null ? m24gaXmlEsc(cut(cur, L.label)) : label) + '">');
        body.push('\t\t<list id="items">');
        opts.forEach(function (o, i) {
          var v = (o && typeof o === 'object') ? o.value : o, nm = (o && typeof o === 'object') ? (o.label !== undefined ? o.label : o.value) : o;
          body.push('\t\t\t<record value="' + (i + 1) + '" name="' + m24gaXmlEsc(cut(nm, L.label)) + '"/>');
          s.opts = s.opts || []; s.opts.push(v);
        });
        body.push('\t\t</list>');
        body.push('\t</widget>');
        events[s.e].options = s.opts;
      } else if (t === 'person' || t === 'club') {
        // (코어 0.29.0, C09) 게임의 검색칸(db_record_search_box): 치는 대로 게임이 사람/구단 후보를 띄우고, 고르면 코어가 'pick' 이벤트로 알린다.
        // 줄 모양은 게임 파일(widgets/search box scout assignment, predictive search list scout assignment). ssro를 빼서 고를 때 화면이 옮겨 가지 않는다
        var k2 = newIds(f.id, 'pick');
        events[k2.e].table = t;
        // 지금 고른 것은 이름 줄 끝에 붙인다 (창 높이를 늘리지 않게). 이름이 없으면 따로 한 줄
        var now = (f.value && typeof f.value === 'object') ? (f.value.label || f.value.name) : null;
        var nowTxt = now ? (f.nowLabel !== undefined ? f.nowLabel : '지금: ') + now : '';
        if (label || nowTxt) body.push('\t<widget class="text" auto_size="vertical" text="' + m24gaXmlEsc(cut(label && nowTxt ? cut(f.label, L.label) + '  (' + nowTxt + ')' : (label ? cut(f.label, L.label) : nowTxt), L.label * 2)) + '"/>');
        body.push('\t<widget class="db_record_search_box" id="' + k2.w + '" height="30" SRnk="false" file="widgets/search box scout assignment" database_table_type="' + (t === 'person' ? 1 : 3) +
          '" dfol="true" lpfi="widgets/predictive search list scout assignment" lpmw="500"/>');
      } else throw new Error("모르는 칸 종류 '" + t + "' (text, number, check, select, label, person, club)");
      if (t === 'number') { events[widgets[f.id] && ('me' + widgets[f.id].slice(2))].number = { min: f.min, max: f.max }; }
    });
    body.push('\t<container>');
    body.push('\t\t<attachment_group class="button_arrangement_right"/>');
    buttons.forEach(function (b) {
      if (!b || typeof b !== 'object') throw new Error('버튼은 객체여야 해요');
      var k = newIds(b.id, 'button');
      body.push('\t\t<widget class="button" id="' + k.w + '" click_event="' + k.e + '" auto_size="all" text="' + m24gaXmlEsc(cut(b.label || b.id, L.label)) + '"/>');
    });
    body.push('\t\t<widget class="primary_icon_tick_button" id="ok" text="' + m24gaXmlEsc(cut(form.closeLabel || 'OK', L.label)) + '"/>');
    body.push('\t</container>');
  } catch (e) { return { ok: false, error: String(e.message || e) }; }
  var xml = '<panel width="' + Math.max(320, Math.min(900, form.width | 0 || 560)) + '">\n' + body.join('\n') + '\n</panel>\n';
  return { ok: true, xml: xml, widgets: widgets, events: events };
}