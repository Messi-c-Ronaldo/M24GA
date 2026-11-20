// M24GA mod: AI 소셜피드 (게임 쪽). GPL-3.0-or-later.
// 로더가 이 파일을 registerMod('ai-social-feed', function (api) { ... }) 안에 넣는다. 코어 함수(getVal, collect용 표 등)는 그대로 보인다.
// 팬 댓글(this+0x1d8 in {2,4})만 교체한다. 캐시에 문장이 있으면 교체하고,
// 없으면 Python에 요청 메시지(api.send)를 보내고 '생성 중'을 띄운다. 실패/예외는 모두 원문 유지. (원래 fm24_ai_mod/hook.js)
// 7a단계부터 파일(cache.json, requests.jsonl, config.json)을 직접 읽고 쓰지 않고 메시지로 주고받는다:
//   Python -> JS: snap(캐시 묶음) / cfg(설정) / ready / res(결과 1건).  JS -> Python: hello(연결 직후) / req(요청 1건).

var DIR = '';   // 모드 데이터 폴더 (상태 표시용. 로더가 값을 넣는다)
var MAX_REQ = 600;           // 세션당 요청 상한 (비용 보호)

var cache = {};              // 키 -> 새 문장(문자열) 또는 null(실패)
var produced = {};           // 우리가 만든 문장 -> true (재진입 방지)
var requested = {};
var nReq = 0, nRepl = 0, nErr = 0;
var lastTitle = '', lastOfficial = '';
var threadTitle = {}, threadFirst = {};   // 스레드 객체 주소 -> 뉴스 제목/공식 글, 첫 팬 글
var PH = '문장 생성 중...';          // 아직 생성되지 않은 댓글에 표시
var pending = {};                   // 패널 주소 -> {k, o(원문), h(넣은 '생성 중' 문자열 핸들), t(시각)}
var lastTick = 0, nAuto = 0, tickSeen = false;
var PENDING_MAX_MS = 120000;        // 이보다 오래된 '생성 중' 패널은 버린다 (화면을 떠났을 가능성)

// 설정 (23번 로그): 켜기/끄기, 교체할 글 종류, 요청 상한, 기사 본문 사용. Python이 cfg 메시지로 알려 준다 (그 전에는 기본값).
var CFG = { enabled: true, types: [2, 4], maxReq: 600, useBody: true, autoRefresh: true };
var sentReq = {};                   // 키 -> 보낸 요청. Python이 아직 못 받았을 수 있어서 기억해 두었다가 답이 없는 것만 다시 보낸다
var linkReady = false;              // Python이 ready를 보낸 적이 있나 (= 메시지가 Python에 닿는다)

function sendReq(k) { api.send({ t: 'req', r: sentReq[k] }); }
function resendUnanswered() {       // Python은 이미 만들었거나 만드는 중인 키는 건너뛴다 (만든 것은 결과만 다시 보낸다)
  for (var k in sentReq) if (!(k in cache)) sendReq(k);
}
api.recv(function (m) {
  try {
    if (m.t === 'res') { cache[m.k] = m.v; if (m.v) produced[m.v] = true; }
    else if (m.t === 'snap') { for (var k in m.c) { cache[k] = m.c[k]; if (m.c[k]) produced[m.c[k]] = true; } }
    else if (m.t === 'cfg') {
      var wasOn = CFG.enabled, c = m.c;
      CFG.enabled = c.enabled !== false;
      if (Array.isArray(c.types)) CFG.types = c.types;
      if (typeof c.maxReq === 'number') CFG.maxReq = c.maxReq;
      CFG.autoRefresh = c.autoRefresh !== false;
      CFG.useBody = c.useBody !== false;
      if (CFG.enabled && !wasOn && linkReady) resendUnanswered();   // 꺼져 있는 동안 버려진 요청을 다시 보낸다
    }
    else if (m.t === 'ready') { linkReady = true; resendUnanswered(); }
  } catch (e) { nErr++; }
});
api.send({ t: 'hello' });           // Python이 아직 안 떠 있어도 호스트가 받아 두었다가 전달한다

function collectCtx(text) {   // 글에 나온 클럽/사람의 게임 데이터 (최대 4개)
  if (!mapsReady || !EMPTY_VAL) return null;
  var out = [];
  linkIds(text).slice(0, 6).forEach(function (e) {
    if (out.length >= 4) return;
    var obj = null, fields = null, kind = '';
    if (e.type === 0x18) { obj = lookup(clubs, e.idx, CLUB_VT); fields = CLUB_FIELDS; kind = '클럽'; }
    else if (e.type === 0x01) {
      obj = lookup(persons, e.idx, PERSON_VT); fields = PERSON_FIELDS; kind = '선수/인물';
      if (!obj) { obj = lookup(staff, e.idx, STAFF_VT); fields = STAFF_FIELDS; kind = '감독/스태프'; }   // 선수 표에 없으면 스태프
      if (!obj) noteMiss('person');   // 표를 만든 뒤 생긴 사람 (유스·새 스태프)
    }
    if (!obj) return;
    var d = { name: e.name, kind: kind };
    try {
      if (kind === '클럽' && isNT(obj)) d['_대표팀'] = true;
      else if (kind === '클럽') d.full = clubFullName(obj);   // 코어 도우미 (M13, 예전엔 +0x30 -> +0xc0을 직접 읽음)
    } catch (x) {}
    fields.forEach(function (f) { try { var v = getInt(obj, f[0]); if (v !== null && v > -1) d[f[1]] = v; } catch (x) {} });
    if (kind === '클럽') {
      clubExtra(obj, d); try { clubSituation(obj, d); } catch (x) {}
      try { var me = myInfo(), co = clubObj(obj); if (me && me.mgr && co && co.equals(me.co)) d['_내팀'] = me.mgr; } catch (x) {}
      try { var mg = clubManagerObj(e.idx); if (mg) { d['_감독'] = mg.name; if (mg.caretaker) d['_임시감독'] = true; var ma = clubManagerAttrs(mg); if (ma) d['_감독_d'] = ma; } else if (vacant[e.idx]) d['_감독공석'] = true; } catch (x) {}
    }
    if (kind === '선수/인물') {
      var pos = mainPosition(obj);
      if (pos) d['주 포지션'] = pos;
      if (pos === '골키퍼') delete d['통산 골'];    // 골키퍼 골 기록은 오해만 부른다
      try {
        var pf = personForm(obj);
        if (pf.avg !== undefined) { d['시즌 평균 평점'] = pf.avg; d['시즌 출전'] = pf.apps; if (pf.goals !== undefined && pos !== '골키퍼') d['시즌 골'] = pf.goals; }
        if (pf.recent) { d['최근 5경기 평점'] = pf.recent.join('/'); d['최근 5경기 평균'] = pf.recentAvg; }
        try { var ex = personExtra(obj); for (var ek in ex) d[ek] = ex[ek]; } catch (x) {}
      } catch (x) {}
    }
    if (kind === '감독/스태프') {
      try {   // 소속: Pclb {dref}. 0xff7fffff(-8388609)이면 무직 (경질된 감독, 감독 후보)
        var cl = getVal(obj, 'Pclb');
        if (cl && typeof cl.dref === 'number') d['무직'] = (cl.dref >>> 24) === 0xff;
      } catch (x) {}
      // 숨은 성향 (Python이 tokens.use_hidden_attributes로 거른다)
      var sa = staffAttrs(obj); for (var sk in sa) if (sk.charAt(0) === '_') d[sk] = sa[sk];   // 숨은 성향 + 포메이션 번호
    }
    out.push(d);
  });
  return out;
}

function panelStillOurs(addr, pd) {   // 아직 같은 패널이고, 우리가 넣은 '생성 중' 문자열을 그대로 갖고 있나 (코어 도우미, M13)
  var th = panelAt(addr, pd.type);
  return !!th && panelTextHandle(th) === pd.h && panelText(th) === PH;
}
function autoRefresh() {   // 화면 스레드에서만 불린다
  var now = Date.now();
  for (var addr in pending) {
    var pd = pending[addr];
    if (now - pd.t > PENDING_MAX_MS) { delete pending[addr]; continue; }
    if (!(pd.k in cache)) continue;                // 아직 생성 중
    if (!panelStillOurs(addr, pd)) { delete pending[addr]; continue; }
    var th = panelAt(addr), neu = cache[pd.k];
    delete pending[addr];
    if (!th) continue;
    try {
      setStr(panelDst(th), neu || pd.o);          // 실패면 원문 복구
      if (neu) { nRepl++; nAuto++; }
      refreshPanel(th);                            // 패널이 글을 다시 읽어 화면에 그린다
    } catch (e) { nErr++; }
  }
}

// 프레임마다 (화면 스레드, 원래 onFrameEnd): '생성 중' 패널이 있을 때만 다시 그린다
api.on('frame', function () {
  if (!CFG.enabled || !CFG.autoRefresh) return;
  var now = Date.now();
  if (now - lastTick < 400) return;
  lastTick = now;
  for (var k in pending) {                         // 기다리는 패널이 있을 때만
    if (!tickSeen) { tickSeen = true; send('auto refresh running on ui thread ' + uiTid); }
    try { autoRefresh(); } catch (e) { nErr++; send('auto refresh error ' + e); }
    break;
  }
});

// 소셜 패널이 그려질 때 (원래 645~716의 패널별 처리)
api.on('socialPanel', function (ev) {
  var th = ev.th, type = ev.type, dst = ev.dst, s = ev.text;
  try {
    if (!CFG.enabled) {                            // 모드 꺼짐: 아무것도 바꾸지 않고, 남아 있는 '생성 중' 표시만 원문으로 되돌린다
      var pd0 = pending[th.toString()];
      if (s === PH && pd0) { setStr(dst, pd0.o); delete pending[th.toString()]; }
      return;
    }
    api.prepareData(th);                           // 처음 한 번만 표를 만들고 값 종류를 얻는다 (원래 startMaps + setTypes)
    var thread = panelThread(th), tk = thread.toString();
    // 부모 글은 스레드 객체별로 기억한다 (29번 이후 수정): "마지막으로 본 제목"을 쓰면 뉴스 카드 없이
    // 팬 글로 시작하는 스레드가 바로 위 스레드의 제목을 부모로 받아 엉뚱한 팀 얘기를 했다.
    if (type === 0) {
      lastTitle = s; lastOfficial = '';
      threadTitle[tk] = s;
      if (CFG.useBody && mapsReady && !thread.isNull()) { try { newsBody(thread); } catch (x) {} }
      return;
    }
    if (type === 3 || type === 5) { lastOfficial = s; threadTitle[tk] = s; return; }
    if (CFG.types.indexOf(type) < 0) return;
    if (!(tk in threadFirst) && s !== PH) threadFirst[tk] = s;   // 뉴스 카드 없는 스레드는 첫 팬 글이 부모
    var addr = th.toString();
    if (s === PH) {                                // 이미 '생성 중' 표시 중인 패널
      var pd = pending[addr];
      if (!pd) return;
      var c0 = cache[pd.k];
      if (c0) { setStr(dst, c0); nRepl++; delete pending[addr]; }
      else if (pd.k in cache) { setStr(dst, pd.o); delete pending[addr]; }   // 생성 실패 -> 원문 복구
      return;
    }
    if (produced[s]) return;                       // 이미 우리가 넣은 문장
    // 캐시 키 = 원문 + 부모 글 (30번 로그). 게임은 같은 원문("진짜면 좋겠다!" 등)을 여러 기사에 다시 쓰고,
    // 공유(리포스트)로 다른 기사 아래에 다시 보여 준다. 원문만으로 찾으면 다른 기사용 AI 댓글이 붙는다.
    var parent = threadTitle[tk] || (threadFirst[tk] !== s ? threadFirst[tk] : '') || '';
    // 작성자 응원 클럽(고유 ID). 같은 기사·같은 원문이라도 맨시티 팬 그룹과 바르셀로나 팬 그룹은 다르게 쓴다 (32번 로그)
    var salo = 0;
    salo = panelFanUid(th);
    var key = hash64(s + '\u0001' + parent + '\u0001' + salo);
    if (key in cache) {
      var neu = cache[key];
      if (!neu) return;                            // 생성 실패 기록 -> 원문 유지
      setStr(dst, neu);
      nRepl++;
    } else {
      if (!mapsReady || !uidReady) return;        // 게임 데이터 표·클럽 고유 ID 표가 준비되기 전에는 원문 유지
      if (!requested[key] && nReq < CFG.maxReq) {
        requested[key] = true; nReq++;
        var ctx = null;
        try { ctx = collectCtx(s + ' ' + parent); } catch (x) {}   // 글 + 그 스레드의 부모만
        var body = bodies[tk] || '';   // 뉴스 카드가 먼저 그려졌을 때만 있다 (모르는 객체에 본문 함수를 부르지 않는다)
        var fan = salo ? fanClub(salo) : {};
        try { var me = myInfo(); if (me && me.mgr) { fan.me_mgr = me.mgr; if (me.club) fan.me_club = me.club; } } catch (x) {}
        sentReq[key] = { k: key, o: s, t: type, p: parent, th: tk, b: body, ctx: ctx, fan: fan };
        sendReq(key);
      }
      if (requested[key]) {
        setStr(dst, PH);
        pending[addr] = { k: key, o: s, h: panelTextHandle(th), t: Date.now(), type: type };
      }
    }
  } catch (e) { nErr++; }
});

api.status(function () {
  return { enabled: CFG.enabled, replaced: nRepl, requested: nReq, errs: nErr, cached: Object.keys(cache).length, dir: DIR,
    autoRefreshed: nAuto, pending: Object.keys(pending).length, linked: linkReady };
});

