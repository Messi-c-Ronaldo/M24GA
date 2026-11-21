// M24GA - FM24 mod loader core (game side, Frida)
// Copyright (C) 2026 M24GA contributors. GPL-3.0-or-later (see LICENSE).
// 게임 데이터 읽기·주소록·화면 훅을 한 번만 걸고, registerMod로 올라온 모드들에 이벤트로 나눠 준다.
// 원래 fm24_ai_mod/hook.js의 공통 부분을 그대로 옮겼다 (M24GA M01 로그). 모드 코드는 registerMod(id, function (api) {...}) 안에 들어간다.

var M24GA_DIR = 'C:\\Users\\Public\\';   // 로더가 넣는 코어 데이터 폴더 (진단 기록용)
var DIR = M24GA_DIR;                      // 아래 dbg()가 쓴다
var B = Process.getModuleByName('fm.exe').base;
var assign = new NativeFunction(B.add(0x192ef30), 'void', ['pointer', 'pointer', 'int']);
var keep = [];
// 소셜 패널 (27번 로그): 패널 함수 0x61ae70은 인자가 this 하나. 화면 스레드에서만 부른다.
var PANEL_VT = B.add(0x56cc008);
var refreshPanel = new NativeFunction(B.add(0x61ae70), 'void', ['pointer']);
var uiTid = 0, coreErr = 0;

function hash64(s) {         // 두 개의 32비트 FNV-1a
  var h1 = 0x811c9dc5, h2 = 0x01000193 ^ s.length;
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i);
    h1 ^= c; h1 = Math.imul(h1, 0x01000193) >>> 0;
    h2 = (Math.imul(h2 ^ c, 0x85ebca6b) + i) >>> 0;
  }
  return ('00000000' + h1.toString(16)).slice(-8) + ('00000000' + h2.toString(16)).slice(-8);
}

function setStr(dst, str) {
  var buf = Memory.allocUtf8String(str);
  keep.push(buf); if (keep.length > 100) keep.shift();
  assign(dst, buf, -1);
}

// ---- 게임 상태 데이터 (작성: Claude Opus, 18번 로그) ----
// 링크 ID([3바이트 번호][종류]) -> 데이터 객체 -> 객체의 get_property(vtable+0x10)로 값 조회.
// 클럽 데이터 객체: vtable 0x5a78848, +0x8 = 클럽 번호, +0x30 = 클럽 객체(vtable 0x5a51f38, +0xc0 정식 이름)
// 사람 데이터 객체: vtable 0x5a4ee78, +0x8 = 사람 번호
var CLUB_VT = B.add(0x5a78848), CLUBOBJ_VT = B.add(0x5a51f38), PERSON_VT = B.add(0x5a4ee78);
// 국가대표팀 데이터 객체 (38번 로그): vtable fm+0x5a6cab8, 클럽과 같은 링크 종류(0x18)·같은 번호 체계(+8), 같은 속성(TMnR, Tomp, Tfrm…).
// +0x30은 클럽 객체가 아니라 다른 객체(fm+0x5a6cd98) -> 정식 이름·짧은 이름은 읽지 않는다. 표 clubs에 같이 넣는다 (호주 1120, 이란 94 등 1842개).
var NT_VT = B.add(0x5a6cab8);
function isNT(o) { try { return o.readPointer().equals(NT_VT); } catch (e) { return false; } }
// 감독·스태프 데이터 객체 (33번 로그): 선수가 아닌 사람은 vtable fm+0x5a4c358. 같은 사람 번호 체계(+8), 링크 종류 0x01.
var STAFF_VT = B.add(0x5a4c358), staff = {};
// 대회·상 표 (코어 0.20.0, 몸값모드 V14): 객체 +0x8 = 번호 (세이브의 comp_history·award_year_hist·선수 시즌 기록과 같은 번호)
var COMP_VT = B.add(0x5a54a38), AWARD_VT = B.add(0x5a511e8), comps = {}, awards = {};
// 값 묶음 종류 포인터는 실행마다 바뀐다 (2026-11-04 확인: 0x5c2298 -> 0x4c1f28).
// 패널 +0x1f8(빈 값 종류)을 기준으로 간격만 고정: 빈 값 +0, bool +0x10, int +0x20, cc +0x30, 실수 +0x70, 문자열 +0x80, list +0xa0, record +0xb0
var EMPTY_VAL = null, INT_T = null, VT = {}, TYPES_FROM = "";
function setTypes(e) {
  if (EMPTY_VAL) return;
  EMPTY_VAL = e; INT_T = e.add(0x20).toString();
  [[0x20, 'int'], [0x80, 'str'], [0x10, 'bool'], [0xb0, 'rec'], [0xa0, 'list'], [0x70, 'dbl'], [0x30, 'cc'], [0x60, 'flt']].forEach(function (x) { VT[e.add(x[0]).toString()] = x[1]; });
}
// 소셜 패널 없이 값 종류 표 찾기 (코어 0.8.1, P06 조사): 표는 힙에 있지만 fm.exe의 고정 칸들이 표 시작을 가리킨다.
// 표의 칸(16바이트)은 fm.exe 안 종류 정보를 가리키므로(빈 값 fm+0x5a0f1c8, int +0x20 -> fm+0x5a0f448, 문자열 +0x80 -> fm+0x5a0fbc8)
// 그걸로 검증하고, 맞을 때만 쓴다. 안 맞으면 예전처럼 소셜 패널(prepareData)을 기다린다.
var EV_SLOTS = [0x64278a0, 0x642fab0, 0x6437a08];
function typesOk(e) {
  try { return e.readPointer().equals(B.add(0x5a0f1c8)) && e.add(0x20).readPointer().equals(B.add(0x5a0f448)) && e.add(0x80).readPointer().equals(B.add(0x5a0fbc8)); } catch (x) { return false; }
}
function findTypes() {
  if (EMPTY_VAL) return true;
  for (var i = 0; i < EV_SLOTS.length; i++) {
    try { var e = B.add(EV_SLOTS[i]).readPointer(); if (!e.isNull() && typesOk(e)) { setTypes(e); TYPES_FROM = "fm+0x" + EV_SLOTS[i].toString(16); return true; } } catch (x) {}
  }
  return false;
}
if (!findTypes()) { var evTimer = setInterval(function () { if (findTypes()) clearInterval(evTimer); }, 1000); }
// 세이브가 열려 있으면 소셜 패널을 기다리지 않고 데이터 표(clubs, persons ...)를 만든다 (코어 0.8.1).
// 조건: 값 종류 표가 준비됐고, 세이브 root가 있고, 선수 목록이 1,000명 이상 (메인 메뉴에서는 만들지 않는다)
var autoMapsTimer = null;
function armAutoMaps() {   // C05: 메인 메뉴에서 만든 표를 버린 뒤에도 다시 지켜보게 함수로 (전에는 타이머가 한 번 꺼지면 피드 화면을 열 때까지 표가 비었다)
  if (autoMapsTimer) clearInterval(autoMapsTimer);
  autoMapsTimer = setInterval(function () {
    if (mapsStarted) { clearInterval(autoMapsTimer); autoMapsTimer = null; return; }
    try {
      if (!EMPTY_VAL || SAVE_ROOT.readPointer().isNull() || playerListKey().n < 1000) return;
      clearInterval(autoMapsTimer); autoMapsTimer = null; TYPES_FROM += ' +auto maps'; startMaps();
    } catch (e) {}
  }, 2000);
}
armAutoMaps();
// C05: 표를 만든 뒤 다른 세이브를 불러오면 표의 객체가 사라진다 -> 세이브가 바뀌면 다시 만든다
var mapsSaveKey = null;
setInterval(function () {
  try {
    var k = m24gaSaveKey(m24gaReadGame().save);
    if (mapsReady && k && mapsSaveKey && k !== mapsSaveKey) { mapsSaveKey = null; staleMaps('save changed'); }
  } catch (e) {}
}, 2000);
var clubs = {}, persons = {}, mapsReady = false;
// ---- 뉴스 기사 본문 (2026-11-04, 21번 로그) ----
// 본문 조립 함수 G = fm+0x263f220 (news, SIString* out, ctx, 1, 평문 여부). ctx = vtable fm+0x5a6a388 객체 중 +0x68에 감독 이름이 있는 것.
// 피드 패널의 +0x1b0 = 뉴스(스레드) 객체. 그 아래 댓글 패널도 같은 +0x1b0을 가진다.
var NEWS_CTX_VT = B.add(0x5a6a388), newsCtx = null, ctxCands = [];
var buildBody = new NativeFunction(B.add(0x263f220), 'pointer', ['pointer', 'pointer', 'pointer', 'uint8', 'uint8']);
var bodies = {};   // 뉴스 객체 주소 -> 본문(평문) 또는 ''
// 검증된 값만 쓴다 (18번 로그 7절): 연승/연패/무승/시즌 출전은 화면 상태에 따라 값이 달라져서 뺐다
var CLUB_FIELDS = [['Tomp', '_시즌 경기 수'], ['TpoN', '리그 순위'], ['Tlgs', '리그 득점'], ['Tlgc', '리그 실점'], ['Cmxp', '미디어 예상 순위'],
  ['Tnts', '이적 순지출(원)']];
var PERSON_FIELDS = [['Page', '나이'], ['PAap', '통산 출전'], ['PAcg', '통산 골'], ['PCRP', '명성']];
// 감독·스태프 (게임 스태프 프로필에서 보이는 값만. 1~20, 명성 0~10000)
var STAFF_FIELDS = [['Page', '나이'], ['Nptk', '전술 지식'], ['Npmm', '선수 관리'], ['Npde', '결단력'], ['Ncrr', '감독 명성']];
// 계약(직장) 객체 (36번 로그): +8 사람(스태프/선수 데이터 객체, 사람 감독은 기사 ctx 객체), +0x10 클럽 데이터, +0x1c 역할 (16 = 감독)
// 클럽 객체를 2군·유스가 같이 쓰므로 클럽 데이터(링크 번호)로 구분한다 -> 1군 감독만 정확히 나온다.
var JOB_VT = B.add(0x5667c88), ROLE_MANAGER = 16, mgrJobs = {}, vacant = {};
// ---- 사람 감독 목록 (코어 0.24.0, 감독커리어모드 C03) ----
// 전역 HUMAN_NON_PLAYER_MANAGER(fm+0x6365118) +0x18/+0x20 = 사람이 조종하는 감독(db::HUMAN_NON_PLAYER, 객체 시작) 포인터 목록.
// 소셜 패널(newsCtx)을 거치지 않아서 언제든 된다. 첫 번째 = 이 PC의 감독 (온라인 게임이 아니면 하나).
var HUMAN_MGR = B.add(0x6365118), HUMAN_VT = B.add(0x5a6a318);
function humans() {
  var out = [];
  try {
    var m = HUMAN_MGR.readPointer(); if (m.isNull() || className(m) !== 'HUMAN_NON_PLAYER_MANAGER') return out;
    var b = m.add(0x18).readPointer(), e = m.add(0x20).readPointer(), n = e.sub(b).toInt32() / 8;
    if (n < 0 || n > 16) return out;
    for (var i = 0; i < n; i++) { var h = b.add(8 * i).readPointer(); if (!h.isNull() && h.readPointer().equals(HUMAN_VT)) out.push(h); }
  } catch (x) {}
  return out;
}
function myHuman() { return humans()[0] || null; }
// 사람 감독의 관계 목록 (코어 0.25.0, 감독커리어모드 C04). 속성 Pfvc/Pdsc/Pfvp/Pdsp를 만드는 관계 조회(fm+0x21643c0)가 읽는 배열:
// 감독 +0x4d0 -> { 시작, 끝, 용량 }, 항목 16바이트 = { +0 대상(db::CLUB·db::NATION·사람), +0xa 이유(rrea), +0xb 종류, +0xc 정도(leve, 100 = 최대) }.
// 종류: 1 좋아하는 사람, 2 싫어하는 사람, 3 좋아하는 구단, 4 싫어하는 구단, 9 국가(뜻 미확인). 읽기만 한다 (더하는 게임 함수는 아직 모름).
var REL_KIND = { 1: 'favPerson', 2: 'dislikedPerson', 3: 'favClub', 4: 'dislikedClub' };
// ---- 구단 찾기 (코어 0.26.0, 감독커리어모드 C05) ----
// 코어의 clubs 표는 팀(db::TEAM) 표다: 팀 +0x30 = 구단(db::CLUB, team.club). 구단 고유 번호 = 팀의 속성 'duni' (uidToIdx 표).
function clubOfTeam(t) { try { return className(t) === 'db::TEAM' ? getField(t, 'team.club') : null; } catch (e) { return null; } }
function clubByName(name) {   // 정식 이름 또는 짧은 이름이 똑같은 구단 (db::CLUB). 없으면 null
  name = String(name || '').trim(); if (!name) return null;
  var lower = name.toLowerCase(), loose = null;
  for (var k in clubs) {
    var c = clubOfTeam(clubs[k]); if (!c) continue;
    var full = getField(c, 'club.name') || '', sh = getField(c, 'club.short') || '';
    if (full === name || sh === name) return c;
    if (!loose && (full.toLowerCase() === lower || sh.toLowerCase() === lower)) loose = c;
  }
  return loose;
}
function clubByUid(uid) { var i = uidToIdx[uid]; if (i === undefined) return null; var t = lookup(clubs, i, CLUB_VT); return t ? clubOfTeam(t) : null; }
function clubUid(club) {   // 구단 -> 고유 번호 (uidToIdx 표를 거꾸로). 표가 아직 없으면 null
  for (var u in uidToIdx) { var t = lookup(clubs, uidToIdx[u], CLUB_VT); if (t && clubOfTeam(t) && clubOfTeam(t).equals(club)) return +u; }
  return null;
}
// ---- 사람 찾기 (코어 0.27.0, 감독커리어모드 C06) ----
// 관계의 사람 대상 = 코어 persons 표(선수의 사람 데이터 부분, 선수 +0x278) 또는 staff 표(스태프) 객체. +8 = 표 번호.
// 이름으로 찾기는 17만 명이라 한 번에 하면 26초 걸려서(C06 실기), 이름 색인을 뒤에서 조금씩 만든다. 사람 참조 글 = 'p<번호>' / 's<번호>'.
var personIdx = null, personIdxFor = null, personIdxBusy = false;
function personNames(o) { try { var v = getVal(o, 'Pnam'); if (!v) return []; return [v.Pfln, v.Pcna, (v.Psna || '') + ' ' + (v.Pfna || ''), (v.Pfna || '') + ' ' + (v.Psna || '')].filter(function (s) { return s && s.trim(); }).map(function (s) { return s.trim().toLowerCase(); }); } catch (e) { return []; } }
function buildPersonIndex() {
  if (personIdxBusy || !mapsReady) return;
  personIdxBusy = true;
  var forMaps = persons, idx = {}, jobs = [['s', staff], ['p', persons]], ji = 0, keys = null, ki = 0;
  (function chunk() {
    if (forMaps !== persons) { personIdxBusy = false; setTimeout(buildPersonIndex, 1000); return; }   // 그사이 표가 바뀜 -> 새 표로 다시 (C08: 멈춘 채로 남던 것)
    var t0 = Date.now();
    while (Date.now() - t0 < 40) {
      if (!keys) { if (ji >= jobs.length) { personIdx = idx; personIdxFor = forMaps; personIdxBusy = false; send('person index ready ' + Object.keys(idx).length); return; } keys = Object.keys(jobs[ji][1]); ki = 0; }
      if (ki >= keys.length) { keys = null; ji++; continue; }
      var t = jobs[ji][0], k = keys[ki++], names = personNames(jobs[ji][1][k]);
      for (var n = 0; n < names.length; n++) { var l = idx[names[n]] || (idx[names[n]] = []); if (l.length < PERSON_IDX_MAX && l.indexOf(t + k) < 0) l.push(t + k); }
    }
    setTimeout(chunk, 5);   // 화면·게임 스레드를 오래 잡지 않게 조금씩
  })();
}
function personByRef(ref) {
  var m = /^([ps])(\d+)$/.exec(String(ref || '')); if (!m) return null;
  return m[1] === 's' ? lookup(staff, +m[2], STAFF_VT) : lookup(persons, +m[2], PERSON_VT);
}
function personRef(o) {
  try { var i = o.add(8).readU32(); if (staff[i] && staff[i].equals(o)) return 's' + i; if (persons[i] && persons[i].equals(o)) return 'p' + i; } catch (e) {}
  return null;
}
// 이름(전체 이름, 보통 이름, '성 이름', '이름 성')이 같은 사람. 반환 { person, ref, many } / null / { pending: true } (색인을 만드는 중)
function personByName(name) {
  name = String(name || '').trim().toLowerCase(); if (!name) return null;
  if (!mapsReady) return { pending: true };
  if (!personIdx || personIdxFor !== persons) { buildPersonIndex(); return { pending: true }; }
  var l = personIdx[name]; if (!l || !l.length) return null;
  var o = personByRef(l[0]); return o ? { person: o, ref: l[0], many: l.length > 1, count: l.length } : null;
}
// (코어 0.28.0, C08) 같은 이름의 사람을 모두 (이름 하나에 최대 PERSON_IDX_MAX명): 고르는 창에 쓸 나이·소속·선수/스태프와 함께.
// 반환 [{ person, ref, name, age, club, role }] (없으면 []) / { pending: true }
var PERSON_IDX_MAX = 8;
// 구단 번호(db::CLUB +8, 사람 속성 Pclb의 dref 0x03xxxxxx 아래 24비트) -> 구단. 팀 번호(clubs 표 열쇠)와 다르다 (C08: 손흥민 0x1b6 = 토트넘)
var clubIdxMap = null, clubIdxFor = null;
function clubByIndex(i) {
  if (clubIdxFor !== clubs) {
    clubIdxMap = {}; clubIdxFor = clubs;
    for (var k in clubs) { var c = clubOfTeam(clubs[k]); if (c) try { clubIdxMap[c.add(8).readU32()] = c; } catch (e) {} }
  }
  return clubIdxMap[i] || null;
}
function personInfo(o, ref) {
  var info = { person: o, ref: ref || personRef(o), name: null, age: null, club: null, role: null };
  try { info.name = getVal(o, 'Pfln') || null; } catch (e) {}
  try { var a = getVal(o, 'Page'); if (typeof a === 'number' && a > 0 && a < 120) info.age = a; } catch (e) {}
  try {   // Pclb = { dref: 0x03 + 팀 번호 }, 무소속은 0xff7fffff
    var c = getVal(o, 'Pclb');
    if (c && typeof c.dref === 'number' && (c.dref >>> 24) === 0x03) { var cl = clubByIndex(c.dref & 0xffffff); info.club = cl ? (getField(cl, 'club.name') || null) : null; }
    else if (c && typeof c.dref === 'number') info.club = '';   // 무소속
  } catch (e) {}
  if (info.ref) info.role = info.ref.charAt(0) === 's' ? 'staff' : 'player';
  return info;
}
function personsByName(name) {
  name = String(name || '').trim().toLowerCase(); if (!name) return [];
  if (!mapsReady) return { pending: true };
  if (!personIdx || personIdxFor !== persons) { buildPersonIndex(); return { pending: true }; }
  return (personIdx[name] || []).map(function (r) { var o = personByRef(r); return o ? personInfo(o, r) : null; }).filter(function (x) { return x; });
}
function humanRelations(h) {
  var out = [];
  try {
    h = h || myHuman(); if (!h || !h.readPointer().equals(HUMAN_VT)) return out;
    var v = h.add(0x4d0).readPointer(); if (v.isNull()) return out;
    var b = v.readPointer(), e = v.add(8).readPointer(), n = e.sub(b).toInt32() / 16;
    if (n < 0 || n > 512) return out;
    for (var i = 0; i < n; i++) {
      var it = b.add(16 * i), t = it.readPointer(), k = it.add(0xb).readU8(), cls = t.isNull() ? null : className(t);
      var r = { target: t, cls: cls, kind: k, kindName: REL_KIND[k] || null, level: it.add(0xc).readU8(), reason: it.add(0xa).readU8() };
      if (cls === 'db::CLUB') { try { r.name = getField(t, 'club.name'); } catch (x) {} }
      else if (it.add(0xa).readU8() === 3) { try { var pn = getVal(t, 'Pnam'); r.name = pn && (pn.Pfln || pn.Pcna) || null; r.ref = personRef(t); } catch (x) {} }   // 사람 (0.27.0)
      out.push(r);
    }
  } catch (x) {}
  return out;
}
// 관계 쓰기 (코어 0.26.0, 기능 write.relation). 값 글 = '<kindName>:<구단 고유 번호>' (예: 'dislikedClub:1708'), 없음 = ''.
// 더하기 = 게임의 일반 관계 더하기 person.relationAdd(fm+0x2164000, 감독 +0x478, 항목). 빼기 = 게임이 하는 것처럼 마지막 항목과 바꾸고 끝을 줄인다
// (메모리를 풀지 않는다). 화면 스레드에서만 (게임이 멈춘 화면의 패널 콜백 등).
var REL_KIND_NO = { favClub: 3, dislikedClub: 4, favPerson: 1, dislikedPerson: 2 };   // 1·2 사람은 0.27.0
var REL_OPPOSITE = { 1: 2, 2: 1, 3: 4, 4: 3 };
function relFind(h, club, kind) {
  var v = h.add(0x4d0).readPointer(); if (v.isNull()) return null;
  var b = v.readPointer(), e = v.add(8).readPointer(), n = e.sub(b).toInt32() / 16;
  for (var i = 0; i < n; i++) { var it = b.add(16 * i); if (it.readPointer().equals(club) && it.add(0xb).readU8() === kind) return { v: v, b: b, e: e, n: n, it: it }; }
  return null;
}
function relParse(s) {   // 'favClub:<구단 고유 번호>' / 'favPerson:<s|p><표 번호>'
  var m = /^(favClub|dislikedClub):(\d+)$/.exec(String(s || '')); if (m) return { kind: m[1], uid: +m[2] };
  m = /^(favPerson|dislikedPerson):([sp]\d+)$/.exec(String(s || '')); return m ? { kind: m[1], ref: m[2] } : null;
}
function relTarget(p) { return p.ref ? personByRef(p.ref) : clubByUid(p.uid); }
var REL_ADD = null;
function relationWriter() {
  return {
    cap: 'write.relation',
    // key = 감독 순번, value = 바꾼 뒤 상태 ('kind:uid' = 있게, '' = 없게), expect = 바꾸기 전 상태 (되돌리기에서 씀)
    write: function (key, value, expect) {
      // 화면 스레드가 아니면(로더의 되돌리기 등) 다음 프레임에 화면 스레드에서 하고 Promise로 결과를 준다 (rpc는 Promise를 기다린다)
      var self = this;
      if (uiTid && Process.getCurrentThreadId() !== uiTid) return runOnUi(function () { return self.write(key, value, expect); }).then(function (r) { return r && r.error && r.ok === undefined ? { ok: false, error: r.error } : r; });
      var h = findObj('human', key); if (!h) return { ok: false, error: '감독을 찾지 못했어요 (' + key + ')' };
      var who = getField(h, 'human.firstName') || '';
      var want = value ? relParse(value) : null, had = expect ? relParse(expect) : null;
      if (value && !want) return { ok: false, error: "관계 값은 'favClub:구단번호' 또는 'dislikedClub:구단번호'예요" };
      var p = want || had; if (!p) return { ok: false, error: '바꿀 관계가 없어요' };
      var club = relTarget(p); if (!club) return { ok: false, error: (p.ref ? '사람 ' + p.ref : '구단 번호 ' + p.uid) + '을(를) 찾지 못했어요 (데이터 표가 준비된 뒤 다시)' };
      var kind = REL_KIND_NO[p.kind], cur = relFind(h, club, kind);
      if (want) {   // 더하기
        if (cur) return { ok: true, same: true, before: value, after: value, name: who };
        var other = relFind(h, club, REL_OPPOSITE[kind]), what = p.ref ? '사람' : '구단';
        if (other) return { ok: false, error: '이 ' + what + '은 이미 ' + (kind === 3 || kind === 1 ? '싫어하는 ' : '좋아하는 ') + what + '이에요. 먼저 빼 주세요', before: '', name: who };
        if (!REL_ADD) { var st = funcCheck('person.relationAdd'); if (!st.ok) return { ok: false, error: st.error }; REL_ADD = new NativeFunction(st.addr, 'pointer', ['pointer', 'pointer', 'uint8']); }
        // 항목 {+8 이유(0 = 없음), +0xa 대상 종류(1 구단, 3 사람), +0xb 관계 종류, +0xc 정도, +0xd (구단 0x4e = 감독 만들기와 같게, 사람 0x4f = 선수들 사람 관계와 같게)} (C06에서 뜻 확인)
        var ent = Memory.alloc(16); ent.writePointer(club); ent.add(8).writeByteArray(p.ref ? [0, 0, 3, kind, 100, 0x4f, 0, 0xff] : [0, 0, 1, kind, 100, 0x4e, 0, 0xff]);
        var r = REL_ADD(h.add(0x478), ent, 0);
        var ok = !r.isNull() && !!relFind(h, club, kind);
        return { ok: ok, before: '', after: ok ? value : '', name: who, error: ok ? undefined : '게임이 관계를 넣지 않았어요' };
      }
      if (!cur) return { ok: true, same: true, before: '', after: '', name: who };   // 빼기: 이미 없음
      var last = cur.b.add(16 * (cur.n - 1));
      if (!cur.it.equals(last)) { var tmp = cur.it.readByteArray(16); cur.it.writeByteArray(last.readByteArray(16)); last.writeByteArray(tmp); }
      cur.v.add(8).writePointer(cur.e.sub(16));
      return { ok: true, before: expect, after: '', name: who };
    }
  };
}
M24GA.writers['human.relation'] = relationWriter();
// 모드가 부른다 (modhost m24gaRelation): 감독 h에 구단 club의 관계를 넣거나(on) 뺀다(off)
M24GA.relationKey = function (h, kindName, club, on) {
  if (!REL_KIND_NO[kindName]) return { error: "관계 종류는 'favClub', 'dislikedClub', 'favPerson', 'dislikedPerson'이에요" };
  var key = fieldKey(h, 'human'); if (key === null) return { error: '사람 감독 객체가 아니에요' };
  var id;
  if (/Person$/.test(kindName)) { id = club ? personRef(club) : null; if (id === null) return { error: '사람을 사람·스태프 표에서 찾지 못했어요 (personByName으로 찾은 사람을 넘기세요)' }; }
  else { id = club ? clubUid(club) : null; if (id === null) return { error: '구단 고유 번호를 찾지 못했어요 (데이터 표가 준비된 뒤 다시)' }; }
  var s = kindName + ':' + id;
  return { key: key, value: on ? s : '', expect: on ? '' : s };
};
function strAt(p) { try { var h = p.readPointer(); if (h.isNull()) return ''; h = h.readPointer(); var n = h.readU32(); return (n > 0 && n < 100) ? h.add(4).readUtf8String(n) : ''; } catch (e) { return ''; } }
// 지난 계약도 같은 vtable·역할·클럽으로 메모리에 남는다 (38번 로그 조사: 감독 계약 3044개, 클럽 2801개 중 147개 클럽에 계약 2~3개,
// 그중 146개는 정확히 하나만 현재). 사람 객체 +0xc8(현재 직장)이 이 계약을 가리킬 때만 현재 계약이다 (스태프·사람 감독 공통).
function isCurrentJob(j) { try { return j.add(8).readPointer().add(0xc8).readPointer().equals(j); } catch (e) { return false; } }
function jobManagerObj(idx, count) {   // 계약 표로 찾은 감독 (TMnR이 안 될 때 예비)
  var j = mgrJobs[idx];
  // 표에 없음: 세는 건 작성자 팀(fanClub)만 (글에 나온 팀은 국가대표팀처럼 원래 표에 없는 팀이 많다).
  // 표에 있었는데 지금은 아님(경질·이직): 어디서든 센다 -> 새 감독을 찾으러 다시 만든다.
  if (!j) { if (count) noteMiss('manager'); return null; }
  try {
    if (!j.readPointer().equals(JOB_VT) || j.add(0x1c).readU32() !== ROLE_MANAGER || !isCurrentJob(j)) { delete mgrJobs[idx]; vacant[idx] = true; noteMiss('manager'); return null; }   // 경질·이직 -> 새 감독을 찾을 때까지 공석
    var cd = j.add(0x10).readPointer();
    if (!cd.readPointer().equals(CLUB_VT) || cd.add(8).readU32() !== idx) { delete mgrJobs[idx]; noteMiss('manager'); return null; }
    var p = j.add(8).readPointer(), vt = p.readPointer();
    if (!vt.equals(STAFF_VT) && !vt.equals(NEWS_CTX_VT) && !vt.equals(PERSON_VT)) return null;
    var name = strAt(p.add(0x68));                   // 통칭 (사람 감독은 전체 이름 "윤라온")
    if (!name) { var first = strAt(p.add(0x58)), last = strAt(p.add(0x60)); name = last ? first + ' ' + last : first; }
    return name ? { name: name, obj: p } : null;
  } catch (e) { return null; }
}
function objName(p) { var n = strAt(p.add(0x68)); if (!n) { var f = strAt(p.add(0x58)), l = strAt(p.add(0x60)); n = l ? f + ' ' + l : f; } return n; }
// 팀 속성 TMnR (38번 로그) = 게임이 계산한 지금 팀 감독 {dref: 0x01xxxxxx 사람 ID}. 임시 감독도 여기 나온다
// (아스날: 1군 감독 계약 없음, TMnR = 사람 2555 애덤 버숄 = U21 수석코치이면서 1군 임시 감독. 사용자 확인).
// 계약 표의 현재 감독과 다르면 임시 감독(caretaker)이다.
var TMNR_OK = true;
function clubManagerObj(idx, count) {   // 클럽 데이터 링크 번호 -> {name, obj, caretaker} 또는 null
  if (TMNR_OK && EMPTY_VAL) {
    try {
      var cd = lookup(clubs, idx, CLUB_VT), r = cd ? getVal(cd, 'TMnR') : null;
      if (r && typeof r.dref === 'number' && (r.dref >>> 24) === 0x01) {
        var pidx = r.dref & 0xffffff, po = lookup(staff, pidx, STAFF_VT) || lookup(persons, pidx, PERSON_VT);
        if (po) {
          var jm = jobManagerObj(idx, false);
          var name = objName(po);
          if (name) return { name: name, obj: po, caretaker: !isNT(cd) && !(jm && jm.obj.equals(po)) };   // 대표팀 감독 계약은 +0xc8 현재 직장이 아니라서 비교 안 함
        }
        // 표에 없는 사람 (사람 감독 = 윤라온이거나 새로 생긴 스태프) -> 계약 표로
        var j2 = jobManagerObj(idx, false); if (j2) return j2;
        noteMiss('tmnr'); return null;
      }
    } catch (e) {}
  }
  return jobManagerObj(idx, count);
}
function clubManager(idx) { var m = clubManagerObj(idx); return m ? m.name : ''; }
// 감독 능력치 숫자 (37번 다음 작업 1): 스태프 데이터 객체일 때만. 사람 감독(기사 ctx 객체)·선수 겸 감독은 능력치가 없어 null.
// 숫자는 그대로 보내고 라벨은 Python _staff_notes가 붙인다. 숨은 성향은 '_숨_' 키 (Python이 설정으로 거른다).
function staffAttrs(obj) {
  var d = {};
  STAFF_FIELDS.forEach(function (f) { try { var v = getInt(obj, f[0]); if (v !== null && v > -1) d[f[1]] = v; } catch (x) {} });
  // 선호 포메이션 번호 (38번 로그: fm+0x1a0bd30 번호표). Nppf 1순위, Npsf 2순위 추정, Npaf/Npdf 공격·수비 추정
  [['Nppf', '_포메이션'], ['Npsf', '_포메이션2'], ['Npaf', '_포메이션_공'], ['Npdf', '_포메이션_수']].forEach(function (f) {
    try { var v = getInt(obj, f[0]); if (v !== null && v >= 0 && v <= 65) d[f[1]] = v; } catch (x) {}
  });
  [['Ntem', '기질'], ['Pcvy', '논란 성향'], ['Ploy', '충성심'], ['Pamb', '야망']].forEach(function (f) {
    try { var v = getInt(obj, f[0]); if (v !== null && v >= 1 && v <= 20) d['_숨_' + f[1]] = v; } catch (x) {}
  });
  return d;
}
function clubManagerAttrs(m) {
  if (!m || !EMPTY_VAL) return null;
  try { if (!m.obj.readPointer().equals(STAFF_VT)) return null; var d = staffAttrs(m.obj); return Object.keys(d).length ? d : null; } catch (e) { return null; }
}

function ptrPat(p) { var s = [], v = p; for (var i = 0; i < 8; i++) { s.push(('0' + v.and(0xff).toString(16)).slice(-2)); v = v.shr(8); } return s.join(' '); }
// 새 표에 모은 뒤 끝나면 한 번에 바꿔 끼운다 -> 다시 만드는 동안(refresh)에도 예전 표로 계속 댓글을 만든다 (38번 로그)
var building = false, lastBuild = 0;
function buildMaps(refresh) {
  building = true;
  var ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: true }).filter(function (r) { return r.size < 0x40000000; });
  var nClubs = {}, nPersons = {}, nStaff = {}, nJobs = {}, nOld = {}, nComps = {}, nAwards = {}, cands = [];
  var jobs = [[NEWS_CTX_VT, 'ctx', false], [CLUB_VT, nClubs, true], [NT_VT, nClubs, false], [PERSON_VT, nPersons, false], [STAFF_VT, nStaff, false], [JOB_VT, 'jobs', false], [COMP_VT, nComps, false], [AWARD_VT, nAwards, false]], ji = 0;
  (function nextJob() {
    if (ji === 1 && !newsCtx) { ctxCands = cands; pickCtx(); }
    if (ji >= jobs.length) {
      building = false;
      if (Object.keys(nClubs).length < 1000) {   // 메인 메뉴 등 세이브가 없을 때 만든 표 -> 버리고 다음 피드 패널 때 다시
        if (!refresh) { mapsStarted = false; armAutoMaps(); }   // 세이브가 열리면 자동으로 다시 (C05)
        send('maps too small (clubs=' + Object.keys(nClubs).length + '), retry when a save is open');
        return;
      }
      var counts = [nClubs, nPersons, nStaff, nJobs].map(function (m) { return Object.keys(m).length; }).join('/');
      REFRESH_GAP = (refresh && counts === lastCounts) ? Math.min(REFRESH_GAP * 2, 120 * 60 * 1000) : GAP0;
      lastCounts = counts;
      var nVac = {}; for (var vk in nOld) if (!(vk in nJobs)) nVac[vk] = true;   // 지난 감독 계약만 있고 현재 감독이 없는 클럽 = 공석
      clubs = nClubs; persons = nPersons; staff = nStaff; mgrJobs = nJobs; vacant = nVac; comps = nComps; awards = nAwards; misses = 0; lastBuild = Date.now();
      mapsReady = true; try { mapsSaveKey = m24gaSaveKey(m24gaReadGame().save); } catch (e) {}
      send((refresh ? 'maps refreshed' : 'maps ready') + ' clubs=' + Object.keys(clubs).length + ' persons=' + Object.keys(persons).length + ' staff=' + Object.keys(staff).length + ' managers=' + Object.keys(mgrJobs).length + ' comps=' + Object.keys(comps).length + ' awards=' + Object.keys(awards).length + ' vacant=' + Object.keys(vacant).length + ' newsCtx=' + newsCtx);
      buildUidMap();
      setTimeout(function () { try { playerMapNow(); } catch (e) {} }, 0);   // 선수 표도 미리 (0.3초, M13)
      return;
    }
    var job = jobs[ji++], pat = ptrPat(job[0]), idx = 0;
    (function next() {
      if (idx >= ranges.length) return setTimeout(nextJob, 0);
      var r = ranges[idx++];
      Memory.scan(r.base, r.size, pat, {
        onMatch: function (a) {
          if (a.and(7).toInt32() !== 0) return;
          try {
            if (job[1] === 'ctx') { cands.push(a); return; }
            if (job[1] === 'jobs') {   // 계약 중 역할 16(감독)만: 클럽 데이터 링크 번호 -> 계약 객체
              if (a.add(0x1c).readU32() !== ROLE_MANAGER) return;
              var cd = a.add(0x10).readPointer();
              if (!cd.readPointer().equals(CLUB_VT)) return;
              if (isCurrentJob(a)) nJobs[cd.add(8).readU32()] = a; else nOld[cd.add(8).readU32()] = true;   // 지난 계약(경질·이직)은 공석 판단에만
              return;
            }
            if (job[2] && !a.add(0x30).readPointer().readPointer().equals(CLUBOBJ_VT)) return;
            job[1][a.add(8).readU32()] = a;
          } catch (e) {}
        },
        onError: function () {}, onComplete: function () { setTimeout(next, 0); }
      });
    })();
  })();
}
// ---- 시즌이 바뀌며 생기는 사람 (38번 로그) ----
// 매 시즌 은퇴·신규 생성(유스, 새 스태프)과 감독 경질·부임이 있다. 표는 한 번 만들면 그대로라 새 사람·새 계약이 빠진다.
// 표에 없는 사람·감독 계약이 MISS_LIMIT번 나오면, 마지막으로 만든 지 REFRESH_GAP이 지났을 때 뒤에서 표를 다시 만든다.
// 다시 만들어도 새로 찾은 게 없으면(빈 감독 자리 등 원래 없는 것) 간격을 두 배로 늘린다 (20분 → 최대 2시간).
var misses = 0, MISS_LIMIT = 5, GAP0 = 20 * 60 * 1000, REFRESH_GAP = GAP0, lastCounts = '';
function noteMiss(why) {
  misses++;
  if (!mapsReady || building || misses < MISS_LIMIT || Date.now() - lastBuild < REFRESH_GAP) return;
  send('maps refresh (' + why + ', misses=' + misses + ')');
  buildMaps(true);
}
// ---- 표 만들기 시점과 오래된 객체 보호 (24번 로그) ----
// 표는 피드 패널이 처음 그려질 때 만든다 (= 세이브가 불러와진 뒤). 실행기를 메인 메뉴에서 미리 켜 둬도 된다.
// 다른 세이브를 불러오면 예전 객체가 사라진다 -> 쓰기 전에 vtable/번호를 확인하고, 다르면 표를 다시 만든다.
var MEND = B.add(Process.getModuleByName('fm.exe').size);
var mapsStarted = false;
function startMaps() { if (mapsStarted) return; mapsStarted = true; send('maps building'); buildMaps(); }
function staleMaps(why) {
  if (!mapsReady) return;
  mapsReady = false; clubs = {}; persons = {}; staff = {}; mgrJobs = {}; vacant = {}; comps = {}; awards = {}; newsCtx = null; ctxCands = []; bodies = {};
  uidToIdx = {}; uidReady = false;
  send('maps stale (' + why + '), rebuilding');
  buildMaps();
}
// ---- 댓글 작성자의 응원 클럽 (32번 로그) ----
// 댓글 패널 +0x1c8 레코드의 Salo = 작성자(팬 계정)가 응원하는 클럽의 고유 ID(duni).
// 클럽 데이터 객체의 속성 'duni'(고유 ID)와 같다 (맨시티 679, 바르셀로나 1708, 레알 1736, 엘체 1707 확인).
// 링크 번호(클럽 데이터 객체 +8)와는 다른 번호 체계라 고유 ID -> 클럽 번호 표를 따로 만든다.
var uidToIdx = {}, uidReady = false;
function buildUidMap() {
  var src = clubs, ids = Object.keys(src), i = 0, buf = Memory.alloc(0x40), DUNI = 0x64756e69, nu = {};   // 'duni'
  var fn = new NativeFunction(CLUB_VT.add(0x10).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer']);
  var fnNT = new NativeFunction(NT_VT.add(0x10).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer']);
  (function chunk() {
    if (src !== clubs) return;   // 그사이 표가 다시 만들어졌다 -> 새 표에서 다시 시작한 호출이 있다
    if (!EMPTY_VAL) return setTimeout(chunk, 500);
    var end = Math.min(ids.length, i + 3000);
    for (; i < end; i++) {
      try {
        var o = src[ids[i]];
        buf.writePointer(EMPTY_VAL);
        if (!(isNT(o) ? fnNT : fn)(o, DUNI, buf)) continue;
        var tp = buf.readPointer();
        if (tp.equals(EMPTY_VAL.add(0x20)) || tp.equals(EMPTY_VAL.add(0x30))) nu[buf.add(8).readU32()] = +ids[i];
      } catch (e) {}
    }
    if (i < ids.length) return setTimeout(chunk, 0);
    uidToIdx = nu; uidReady = true;
    send('club uid map ready ' + Object.keys(uidToIdx).length);
  })();
}
function fanClub(uid) {   // 고유 ID -> {uid, name(짧은 이름), full, mine(내 클럽 팬)}
  var f = { uid: uid };
  if (!uidReady || !(uid in uidToIdx)) return f;
  try {
    var o = lookup(clubs, uidToIdx[uid], CLUB_VT); if (!o || isNT(o)) return f;
    var co = o.add(0x30).readPointer();
    var full = co.add(0xc0).readPointer(), sh = co.add(0xc8).readPointer();
    f.full = full.add(4).readUtf8String(full.readU32());
    f.name = sh.add(4).readUtf8String(sh.readU32());
    var me = myInfo();
    if (me && co.equals(me.co)) f.mine = true;
    var mg = clubManagerObj(uidToIdx[uid], true);   // 작성자 팀 감독 + 능력치 (사람 감독이면 이름만)
    if (mg) { f.mgr = mg.name; if (mg.caretaker) f.mgr_caretaker = true; var ma = clubManagerAttrs(mg); if (ma) f.mgr_d = ma; }
    else if (vacant[uidToIdx[uid]]) f.mgr_vacant = true;
    // 작성자 팀 최근 5경기 (39번 이후, 부정 편향 수정): Tfrm 뒤집기 = [0]이 가장 최근. Python이 '팀 분위기'로 바꿔 감정 방향을 맞춘다
    try { var fr = getVal(o, 'Tfrm'); if (fr && fr.length && fr.every(function (x) { return x >= 0 && x <= 3; })) f.form = fr.slice().reverse(); } catch (x) {}
  } catch (e) {}
  return f;
}
// ---- 내 감독·내 클럽 (36번 로그) ----
// 기사 ctx 객체(newsCtx) = 사람 감독 객체: +0x68 감독 이름(윤라온), +0x58 이름, +0x60 성.
// +0xc8 = 현재 직장 객체 (vtable fm+0x5667c88, +8 = 감독 객체 자신, +0x10 = 맡은 클럽의 클럽 데이터).
// 주의: +0x138은 맡은 팀이 아니다 (바르셀로나 감독인데 맨시티 = 프로필의 좋아하는 클럽으로 보임). +0x80은 경력 목록으로 보임.
// 사람 감독은 인물·스태프 표에서 이름으로 찾을 수 없다 (Pnam이 비어 있음) -> ctx에서 바로 읽는다. 클럽을 옮겨도 따라가도록 매번 읽는다.
function myInfo() {
  if (!newsCtx) return null;
  try {
    if (!newsCtx.readPointer().equals(NEWS_CTX_VT)) return null;
    var h = newsCtx.add(0x68).readPointer().readPointer(), n = h.readU32();
    var mgr = (n > 0 && n < 100) ? h.add(4).readUtf8String(n) : '';
    var co = ptr(0), job = newsCtx.add(0xc8).readPointer();
    if (!job.isNull() && job.readPointer().equals(JOB_VT) && job.add(8).readPointer().equals(newsCtx)) {
      var cd = job.add(0x10).readPointer();
      if (!cd.isNull() && cd.readPointer().equals(CLUB_VT)) co = cd.add(0x30).readPointer();
    }
    if (co.isNull() || !co.readPointer().equals(CLUBOBJ_VT)) return mgr ? { mgr: mgr, co: ptr(0) } : null;   // 무직이면 이름만
    var sh = co.add(0xc8).readPointer(), full = co.add(0xc0).readPointer();
    return { mgr: mgr, co: co, club: sh.add(4).readUtf8String(sh.readU32()), full: full.add(4).readUtf8String(full.readU32()) };
  } catch (e) { return null; }
}
// ---- 선수 객체 (M13, read.player) ----
// 선수 배열: fm+0x642EDD0(시작)/+0x642EDD8(끝)의 포인터 목록. 객체 종류 둘 (FM24 Dynamic PA v0.9.5 레이아웃, M11·M13에서 이 빌드로 실측):
//   선수 vtable fm+0x5a4e958: UID +0x284, 생년월일 +0x2BC / 선수 겸 비선수 vtable fm+0x5c7e798: UID +0x374, 생년월일 +0x3AC
//   공통: CA +0x200, PA +0x202 (int16), 이름 핸들 +0x2D0 (선수 종류에서 확인)
// 사람 데이터 객체(persons 표)와의 연결 (M13 조사): 선수 종류의 +0x280 = 사람 링크 번호(= 사람 데이터 객체 +8, 표본 400/400),
// 그리고 사람 데이터 객체의 속성 'duni'(고유 ID) = 선수 UID (400/400). '선수 겸 비선수' 종류는 persons/staff 표에 없다 (데이터 객체 종류가 다름).
// 링크 번호 연결은 속성 함수(EMPTY_VAL)가 필요 없어서 소셜 패널이 그려지기 전에도 된다. UID·번호 표는 0.3초에 만든다.
var PLAYER_LIST = B.add(0x642EDD0), PLAYER_VT = B.add(0x5a4e958), PLAYER2_VT = B.add(0x5c7e798);
var playerMap = null, playerByIdx = {}, playerMapKey = '';
function playerLayout(p) {
  var vt = p.readPointer();
  if (vt.equals(PLAYER_VT)) return { uid: 0x284, dob: 0x2BC, name: 0x2D0, idx: 0x280 };
  if (vt.equals(PLAYER2_VT)) return { uid: 0x374, dob: 0x3AC, name: null, idx: null };
  return null;
}
function playerListKey() {
  var s = PLAYER_LIST.readPointer(), e = PLAYER_LIST.add(8).readPointer();
  return { s: s, n: (s.isNull() || e.isNull()) ? 0 : e.sub(s).toInt32() / 8, key: s + ':' + e + ':' + m24gaSaveKey(M24GA.game.save) };
}
function buildPlayerMap() {
  var r = playerListKey(), m = {}, bi = {};
  for (var i = 0; i < r.n; i++) {
    try {
      var p = r.s.add(i * 8).readPointer(), L = playerLayout(p); if (!L) continue;
      m[p.add(L.uid).readU32()] = p;
      if (L.idx) bi[p.add(L.idx).readU32()] = p;
    } catch (e) {}
  }
  playerMap = m; playerByIdx = bi; playerMapKey = r.key;
  return m;
}
function playerMapNow() {   // 선수 목록이 바뀌었거나(다른 세이브, 새 선수) 처음이면 다시 만든다
  var k; try { k = playerListKey().key; } catch (e) { return {}; }
  if (!playerMap || k !== playerMapKey) buildPlayerMap();
  return playerMap;
}
function playerOk(p, uid) { try { var L = playerLayout(p); return !!L && p.add(L.uid).readU32() === uid; } catch (e) { return false; } }
// 선수 UID -> 선수 객체 (없으면 null). 표의 객체가 바뀌었으면 한 번 다시 만든다
function playerByUid(uid) {
  uid = uid >>> 0;
  var p = playerMapNow()[uid];
  if (p && playerOk(p, uid)) return p;
  if (p) { buildPlayerMap(); p = playerMap[uid]; return p && playerOk(p, uid) ? p : null; }
  return null;
}
// 사람 데이터 객체(persons 표, lookup으로 꺼낸 것)의 고유 ID (= 선수 UID). 없으면 null
function personUid(o) { try { var u = getVal(o, 'duni'); return typeof u === 'number' ? u >>> 0 : null; } catch (e) { return null; } }
// 사람 데이터 객체 -> 선수 객체 (선수가 아니면 null). 링크 번호로 먼저 찾고(속성 함수 없이), 안 되면 고유 ID로
function playerOf(o) {
  try {
    var idx = o.add(8).readU32(), p = (playerMapNow(), playerByIdx[idx]);
    if (p && playerLayout(p) && p.add(0x280).readU32() === idx) return p;
  } catch (e) {}
  if (!EMPTY_VAL) return null;
  var u = personUid(o); return u === null ? null : playerByUid(u);
}
// 선수 객체 -> { uid, ca, pa, dob: {y,m,d,doy,iso}, name } (못 읽으면 null). CA·PA는 1~200 (PA가 음수면 범위로 지정된 잠재력)
function playerInfo(p) {
  try {
    var L = playerLayout(p); if (!L) return null;
    return { uid: p.add(L.uid).readU32(), ca: p.add(0x200).readS16(), pa: p.add(0x202).readS16(),
      dob: m24gaDecodeDate(p.add(L.dob).readU32()), name: L.name ? strAt(p.add(L.name)) : '' };
  } catch (e) { return null; }
}
// 지금 세이브의 모든 선수 UID (전체를 훑는 모드용. 12만 개라 자주 부르지 마세요)
function playerUids() { return Object.keys(playerMapNow()).map(Number); }

// ---- 선수 시즌 기록·포지션·성격·소속 (코어 0.8.0, read.player) — 포텐모드 P03에서 이 빌드로 실측 ----
// 시즌 기록: 선수 +0x108 -> 묶음, 묶음 +대회칸 -> 블록. 블록 머리(32바이트): +0 상세 기록(120바이트) 포인터, +8 평점 합(u16, ×10),
//   +10 출전 분(u16), +12 선발, +13 교체, +14 평점 받은 경기, +15 골, +16 도움, +19 PK 골 (u8).
//   대회칸: +0x28 리그, +0x30 국내 컵, +0x38 대륙컵, +0x40 국가대표, +0x48 클럽 공식전 합계 (리그+컵+대륙컵).
//   합계 블록이 게임 속성 Poav·Pgls와 896/896, 상세 기록 +72(xG)가 PoxG와 423/423 일치. 범위 검사는 Dynamic PA 0.9.5(GPL-3.0)와 같다.
var SEASON_SLOTS = { league: 0x28, cup: 0x30, continental: 0x38, international: 0x40, club: 0x48 };
// 상세 기록 칸 (Dynamic PA scouting_metrics.FIELDS, u16. xg·xa·npxg는 ÷100). 이 빌드에서 맞춰 본 건 xg뿐
var SEASON_DETAIL = { passesAttempted: 8, passesCompleted: 10, tacklesAttempted: 12, tacklesCompleted: 14, headersAttempted: 16, headersWon: 18,
  dribbles: 20, shots: 26, shotsOnTarget: 28, keyPasses: 54, interceptions: 60, xg: 72, xa: 74, clearances: 76,
  progressivePasses: 100, pressuresAttempted: 102, pressuresCompleted: 104, npxg: 108, crossesAttempted: 112, crossesCompleted: 114 };
function seasonBlock(p, kind) {
  var off = SEASON_SLOTS[kind || 'club']; if (off === undefined) return null;
  var c = p.add(0x108).readPointer(); if (c.isNull()) return null;
  var b = c.add(off).readPointer(); return b.isNull() ? null : b;
}
// 선수 객체 -> 이번 시즌 기록 { apps, starts, subs, minutes, rated, ratingSum, avg, goals, assists, pens }. 기록이 없거나 이상하면 null
function playerSeason(p, kind) {
  try {
    if (!playerLayout(p)) return null;
    var b = seasonBlock(p, kind); if (!b) return null;
    var h = b.readByteArray(32), u = new Uint8Array(h);
    var sum = u[8] | (u[9] << 8), min = u[10] | (u[11] << 8), st = u[12], sb = u[13], rated = u[14], apps = st + sb;
    if (apps > 160 || rated > apps || min > apps * 130 || min > 12000) return null;
    if ((rated === 0 && sum !== 0) || (rated && (sum < 10 * rated || sum > 100 * rated))) return null;
    return { apps: apps, starts: st, subs: sb, minutes: min, rated: rated, ratingSum: sum,
      avg: rated ? Math.round(sum * 10 / rated) / 100 : null, goals: u[15], assists: u[16], pens: u[19] };
  } catch (e) { return null; }
}
// 선수 객체 -> 이번 시즌 상세 기록 { xg, xa, npxg, shots, keyPasses, ... } (값이 모두 0이거나 못 읽으면 null)
function playerSeasonDetail(p, kind) {
  try {
    if (!playerLayout(p)) return null;
    var b = seasonBlock(p, kind); if (!b) return null;
    var a = b.readPointer(); if (a.isNull()) return null;
    var out = {}, any = false;
    for (var k in SEASON_DETAIL) {
      var v = a.add(SEASON_DETAIL[k]).readU16(); if (v) any = true;
      out[k] = (k === 'xg' || k === 'xa' || k === 'npxg') ? v / 100 : v;
    }
    return any ? out : null;
  } catch (e) { return null; }
}
// 포지션 숙련도: 선수 +0x208부터 15바이트 (1~20). 순서는 Dynamic PA POSITIONS, 게임 속성 Pgoa·Pdce… 와 칸별 일치
var POSITION_CODES = ['GK', 'SW', 'DL', 'DC', 'DR', 'DM', 'ML', 'MC', 'MR', 'AML', 'AMC', 'AMR', 'ST', 'WBL', 'WBR'];
function playerPositions(p) {   // { GK: 1, DC: 20, ... } (못 읽으면 null)
  try {
    if (!playerLayout(p)) return null;
    var u = new Uint8Array(p.add(0x208).readByteArray(15)), out = {};
    for (var i = 0; i < 15; i++) { if (u[i] > 20) return null; out[POSITION_CODES[i]] = u[i]; }
    return out;
  } catch (e) { return null; }
}
function playerPosition(p) {    // 가장 숙련된 포지션 { code, level } (같으면 앞 순서)
  var ps = playerPositions(p); if (!ps) return null;
  var best = null;
  POSITION_CODES.forEach(function (c) { if (!best || ps[c] > best.level) best = { code: c, level: ps[c] }; });
  return best;
}
// 성격 (1~20): 야망·프로의식은 사람 부분(선수 종류 +0x2F1/+0x2F4, 선수 겸 비선수 +0xF0),
// 결단력·활동량·창의성은 선수 부분 +0x24A/+0x234/+0x231에 1~100으로 있어 (v+2)/5로 1~20에 맞춘다
function playerTraits(p) {
  try {
    var vt = p.readPointer(), sh;
    if (vt.equals(PLAYER_VT)) sh = 0; else if (vt.equals(PLAYER2_VT)) sh = 0xF0; else return null;
    function t20(off) { var v = p.add(off).readU8(); return (v >= 1 && v <= 100) ? Math.max(1, Math.floor((v + 2) / 5)) : null; }
    function r20(off) { var v = p.add(off).readU8(); return (v >= 1 && v <= 20) ? v : null; }
    return { ambition: r20(0x2F1 + sh), professionalism: r20(0x2F4 + sh), determination: t20(0x24A), workRate: t20(0x234), flair: t20(0x231) };
  } catch (e) { return null; }
}
// 부상 (코어 0.8.1): 사람 데이터 객체의 속성 'injr'(부상 중이면 값이 찬 객체, 아니면 {})과 'Pipr'(부상 경향 1~20). 속성 함수(EMPTY_VAL)는 코어 0.8.1부터 붙자마자 준비된다(findTypes).
// 사람 표(persons)가 다 만들어지기 전(시작 후 1~2분)에는 null. P05에서 실측(그로브너: 4/14 발목 부상, 4/27 기준 지난 13일 = tios, 남은 5~11일 = PPMi/PPMa)
function playerInjury(p) {
  try {
    if (!EMPTY_VAL || !playerLayout(p)) return null;
    var o = lookup(persons, p.add(0x280).readU32(), PERSON_VT); if (!o) return null;
    var pr = getVal(o, 'Pipr'), v = getVal(o, 'injr');
    var out = { injured: false, proneness: typeof pr === 'number' && pr >= 1 && pr <= 20 ? pr : null };
    if (v && typeof v === 'object' && typeof v.injr === 'number') {
      out.injured = true; out.type = v.injr; out.category = v.inCa; out.daysSince = v.tios; out.remainMin = v.PPMi; out.remainMax = v.PPMa; out.expectedTotal = v.iito;
    }
    return out;
  } catch (e) { return null; }
}
// 소속: 선수 +0x130 팀 -> +0x30 클럽 객체, +0x50 대회 -> +0xC 대회 UID. 팀이 없으면 null, 대회가 없으면 compUid null
function playerTeam(p) {
  try {
    if (!playerLayout(p)) return null;
    var t = p.add(0x130).readPointer(); if (t.isNull()) return null;
    var co = t.add(0x30).readPointer(), cm = t.add(0x50).readPointer(), ok = false;
    try { ok = !co.isNull() && co.readPointer().equals(CLUBOBJ_VT); } catch (e) {}
    var cu = null; try { if (!cm.isNull()) cu = cm.add(0xC).readU32(); } catch (e) {}
    return { team: t, club: ok ? co : null, name: ok ? clubNameAt(co, 0xc0) : '', short: ok ? clubNameAt(co, 0xc8) : '', compUid: cu };
  } catch (e) { return null; }
}

// 선수 객체 -> 사람 데이터 객체(persons 표의 객체, getVal로 속성을 읽는 것). M19 RTTI로 확인: 사람 데이터 객체는 따로 있는 게 아니라
// db::ACTUAL_PLAYER의 +0x278 위치(db::PLAYER 기반 부분, vtable PERSON_VT)다. 그래서 선수 +0x280 = 사람 데이터 객체 +8 = 링크 번호였다.
function personOf(p) {
  try { if (!playerLayout(p)) return null; var o = p.add(0x278); return o.readPointer().equals(PERSON_VT) ? o : null; } catch (e) { return null; }
}

// ---- 객체 지도 (M19, read.rtti): fm.exe에 남은 MSVC RTTI로 아무 게임 객체의 클래스 이름·상속을 읽는다 ----
// vtable[-1] -> CompleteObjectLocator { u32 sig(=1), u32 offset(이 vtable이 객체 안 어디에 있나), u32 cdOffset, u32 TypeDescriptor RVA,
// u32 ClassHierarchyDescriptor RVA, u32 자기 RVA }. TypeDescriptor +0x10 = ".?AVname@ns@@". vtable마다 한 번만 읽고 기억한다.
// 오프라인 표(전체 클래스·vtable 목록, 찾기)는 tools/rtti.py.
var RTTI = {};   // vtable 주소 문자열 -> { name, off, bases } 또는 null
function rttiDemangle(raw) {
  var s = raw.replace(/^\.\?A[VU]/, '').replace(/@@$/, '');
  return (s.indexOf('?') >= 0 || s.indexOf('$') >= 0) ? s : s.split('@').reverse().join('::');
}
function inModule(p) { return p.compare(B) >= 0 && p.compare(MEND) < 0; }
function rttiOfVt(vt) {
  var k = vt.toString();
  if (k in RTTI) return RTTI[k];
  var r = null;
  try {
    if (inModule(vt)) {
      var col = vt.sub(8).readPointer();
      if (inModule(col) && col.readU32() === 1 && col.add(20).readU32() === (col.sub(B).toInt32() >>> 0)) {
        var raw = B.add(col.add(12).readU32()).add(16).readCString();
        if (raw && /^\.\?A[VU]/.test(raw)) {
          var bases = [], seen = {}, chd = B.add(col.add(16).readU32()), n = chd.add(8).readU32(), arr = B.add(chd.add(12).readU32());
          for (var i = 1; i < n && i < 64; i++) {
            var bn = rttiDemangle(B.add(B.add(arr.add(4 * i).readU32()).readU32()).add(16).readCString() || '');
            if (bn && !seen[bn]) { seen[bn] = 1; bases.push(bn); }
          }
          r = { name: rttiDemangle(raw), off: col.add(4).readU32(), bases: bases };
        }
      }
    }
  } catch (e) { r = null; }
  RTTI[k] = r;
  return r;
}
// 객체 -> { name, off, top, bases } (vtable이 없거나 RTTI가 없으면 null). off는 이 vtable이 객체 안 어디 있는지, top = 객체 맨 앞 주소
function rttiInfo(obj) {
  try {
    obj = ptr(obj); if (obj.isNull()) return null;
    var r = rttiOfVt(obj.readPointer()); if (!r) return null;
    return { name: r.name, off: r.off, top: obj.sub(r.off), bases: r.bases };
  } catch (e) { return null; }
}
function className(obj) { var r = rttiInfo(obj); return r ? r.name : null; }
// 이 클래스이거나 이 클래스를 물려받았나 (이름은 'db::ACTUAL_PLAYER'처럼 이름공간까지)
function isA(obj, name) { var r = rttiInfo(obj); return !!r && (r.name === name || r.bases.indexOf(name) >= 0); }

// ---- 탐색 (M19, 개발 도구: CLI explore가 rpc로 부른다. 모드 API가 아님) ----
// 대상 글: '0x1234...' 주소, 'player:<uid>', 'person:<uid>'(선수의 사람 데이터 객체), 'me'(내 감독 객체), 'myclub'(내 클럽 객체),
// 뒤에 '/+0x130'처럼 붙이면 그 칸의 포인터를 따라간다 (여러 번 가능, '/+0x130/+0x30').
function exploreResolve(spec) {
  var parts = String(spec).split('/'), head = parts.shift().trim(), p = null, m;
  if (/^0x[0-9a-f]+$/i.test(head)) p = ptr(head);
  else if ((m = /^fm\+0x([0-9a-f]+)$/i.exec(head))) p = B.add(parseInt(m[1], 16));   // 게임 전역 칸 (예: fm+0x631d5bc 게임 날짜)
  else if ((m = /^player:(\d+)$/.exec(head))) p = playerByUid(+m[1]);
  else if ((m = /^person:(\d+)$/.exec(head))) { var pl = playerByUid(+m[1]); p = pl && personOf(pl); }
  else if (head === 'me') { var mi = myInfo(); p = (newsCtx && mi) ? newsCtx : myHuman(); }   // 소셜 화면을 안 열었으면 감독 객체 (C03)
  else if ((m = /^human(?::(\d+))?$/.exec(head))) p = humans()[+(m[1] || 0)] || null;
  else if (head === 'myclub') { var mc = myInfo(); p = mc && !mc.co.isNull() ? mc.co : null; }
  if (!p) return { error: '대상을 찾지 못했어요: ' + head };
  var path = head;
  for (var i = 0; i < parts.length; i++) {
    var off = parseInt(parts[i].replace(/^\+/, ''), 16);
    if (isNaN(off)) return { error: '칸 글이 틀렸어요: ' + parts[i] };
    try { p = p.add(off).readPointer(); } catch (e) { return { error: path + ' +0x' + off.toString(16) + '을 읽지 못했어요' }; }
    path += '/+0x' + off.toString(16);
    if (p.isNull()) return { error: path + '는 빈 포인터예요' };
  }
  return { p: p, path: path };
}
function exploreSlot(base, off) {
  var a = base.add(off), s = { off: off };
  var lo = a.readU32(), hi = a.add(4).readU32();
  s.hex = ('0000000' + hi.toString(16)).slice(-8) + ('0000000' + lo.toString(16)).slice(-8);
  s.i32 = [a.readS32(), a.add(4).readS32()];
  s.i16 = [a.readS16(), a.add(2).readS16(), a.add(4).readS16(), a.add(6).readS16()];
  var f0 = a.readFloat(), f1 = a.add(4).readFloat();
  if ((Math.abs(f0) > 1e-4 && Math.abs(f0) < 1e9) || (Math.abs(f1) > 1e-4 && Math.abs(f1) < 1e9)) s.f32 = [+f0.toPrecision(6), +f1.toPrecision(6)];
  [lo, hi].forEach(function (w, i) {   // 게임 날짜 u32 (상위 16비트 연도, 하위 9비트 연중 일수)
    var y = w >>> 16, d = w & 0x1ff;
    if (y >= 1900 && y <= 2200 && d >= 1 && d <= 366) { var dd = m24gaDecodeDate(w); if (dd) (s.date = s.date || [])[i] = dd.iso; }
  });
  if (hi < 0x8000 && (hi > 0 || lo >= 0x10000) && (lo & 7) === 0) {   // 사용자 영역 포인터처럼 보이면 따라가 본다 (이 게임의 힙은 4GB 아래에도 있다)
    var p = ptr('0x' + s.hex);
    try {
      if (inModule(p)) { s.mod = '+0x' + p.sub(B).toString(16); var vr = rttiOfVt(p); if (vr) s.vtableOf = vr.name; }
      else {
        p.readU8();
        var r = rttiInfo(p);
        if (r) { s.cls = r.name; if (r.off) s.clsOff = r.off; }
        else { var str = strAt(a); if (str) s.str = str; else s.ptr = true; }
      }
    } catch (e) {}
  }
  return s;
}
// find-global (M24, 개발 도구): fm.exe의 쓰기 가능한 전역 구역에서, 이름이 rx에 맞는 클래스의 객체를 가리키는 칸을 찾는다.
// 싱글턴(GAME_UI, GAME_SCREEN_MANAGER ...)의 전역 위치를 찾을 때 쓴다. 한 번에 1MB씩 읽고 시간 예산을 둔다 (게임을 오래 붙잡지 않게).
function findGlobals(pattern, max) {
  var rx = new RegExp(pattern), hits = [], t0 = Date.now(), seen = 0;
  var mod = Process.getModuleByName('fm.exe');
  var ranges = mod.enumerateRanges('rw-');
  for (var ri = 0; ri < ranges.length && hits.length < (max || 30); ri++) {
    var r = ranges[ri];
    for (var off = 0; off < r.size && hits.length < (max || 30); off += 0x100000) {
      var n = Math.min(0x100000, r.size - off), buf;
      try { buf = r.base.add(off).readByteArray(n); } catch (e) { continue; }
      var dv = new DataView(buf);
      for (var o = 0; o + 8 <= n; o += 8) {
        var lo = dv.getUint32(o, true), hi = dv.getUint32(o + 4, true);
        if (hi >= 0x8000 || (hi === 0 && lo < 0x10000) || (lo & 7)) continue;
        var p = ptr('0x' + hi.toString(16) + ('0000000' + lo.toString(16)).slice(-8));
        if (inModule(p)) continue;
        seen++;
        var info = null;
        try { var vt = p.readPointer(); if (inModule(vt)) { var rr = rttiOfVt(vt); if (rr && rx.test(rr.name)) info = rr; } } catch (e) {}
        if (info) hits.push({ at: 'fm+0x' + r.base.add(off + o).sub(B).toString(16), obj: p.toString(), cls: info.name + (info.off ? '@+0x' + info.off.toString(16) : '') });
      }
      if (Date.now() - t0 > 8000) return { hits: hits, seen: seen, ms: Date.now() - t0, partial: true };
    }
  }
  return { hits: hits, seen: seen, ms: Date.now() - t0 };
}

// find-objects (M24, 개발 도구): vtable 주소(RVA 목록, CLI가 tools/rtti.py 표에서 넘김)를 담은 칸을 게임 힙에서 찾는다 = 그 클래스의 객체들.
// Memory.scanSync(네이티브)로 쓰기 가능한 구역을 훑는다. 모듈 안과 1GB 넘는 구역은 뺀다. max개 또는 시간 예산에서 멈춘다.
function findObjects(rvas, max, budgetMs) {
  max = max || 50; budgetMs = budgetMs || 20000;
  var t0 = Date.now(), hits = [], scanned = 0;
  var pats = rvas.map(function (r) {
    var v = B.add(parseInt(r, 16)), s = [];
    for (var i = 0; i < 8; i++) { s.push(('0' + v.shr(8 * i).and(0xff).toInt32().toString(16)).slice(-2)); }
    return { rva: r, pat: s.join(' ') };
  });
  var ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: false })
    .filter(function (r) { return r.size < 0x40000000 && !inModule(r.base); });
  for (var i = 0; i < ranges.length && hits.length < max; i++) {
    for (var k = 0; k < pats.length && hits.length < max; k++) {
      var res; try { res = Memory.scanSync(ranges[i].base, ranges[i].size, pats[k].pat); } catch (e) { continue; }
      for (var j = 0; j < res.length && hits.length < max; j++) {
        var a = res[j].address; if (a.and(7).toInt32() !== 0) continue;
        var r = rttiInfo(a); if (!r) continue;
        hits.push({ obj: a.toString(), top: r.top.toString(), cls: r.name + (r.off ? '@+0x' + r.off.toString(16) : '') });
      }
    }
    scanned += ranges[i].size;
    if (Date.now() - t0 > budgetMs) return { hits: hits, scannedMB: Math.round(scanned / 1048576), ms: Date.now() - t0, partial: true, ranges: ranges.length, at: i };
  }
  return { hits: hits, scannedMB: Math.round(scanned / 1048576), ms: Date.now() - t0, ranges: ranges.length };
}

// find-refs (M25, 개발 도구): 어떤 주소를 가리키는 8바이트 칸을 찾는다 (거꾸로 따라가기: 이 객체를 누가 들고 있나).
// 힙과 fm.exe 전역 구역을 훑는다. 찾은 칸마다 앞쪽 back바이트 안에서 가장 가까운 RTTI 객체를 찾아 "클래스 +칸"으로 알려 준다.
function findRefs(spec, max, budgetMs, back) {
  var t = exploreResolve(spec); if (t.error) return t;
  max = max || 40; budgetMs = budgetMs || 20000; back = back || 0x800;
  var v = t.p, s = [];
  for (var i = 0; i < 8; i++) s.push(('0' + v.shr(8 * i).and(0xff).toInt32().toString(16)).slice(-2));
  var pat = s.join(' '), t0 = Date.now(), hits = [], scanned = 0;
  var ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: false }).filter(function (r) { return r.size < 0x40000000; });
  for (var ri = 0; ri < ranges.length && hits.length < max; ri++) {
    var res; try { res = Memory.scanSync(ranges[ri].base, ranges[ri].size, pat); } catch (e) { continue; }
    for (var j = 0; j < res.length && hits.length < max; j++) {
      var a = res[j].address; if (a.and(7).toInt32() !== 0) continue;
      var h = { at: inModule(a) ? 'fm+0x' + a.sub(B).toString(16) : a.toString() };
      for (var o = 0; o <= back; o += 8) {
        var q = a.sub(o); if (q.compare(ranges[ri].base) < 0) break;
        var r = null; try { r = rttiInfo(q); } catch (e) {}
        if (r) { h.owner = r.top.toString(); h.cls = r.name; h.off = '0x' + a.sub(r.top).toString(16); break; }
      }
      hits.push(h);
    }
    scanned += ranges[ri].size;
    if (Date.now() - t0 > budgetMs) return { target: v.toString(), hits: hits, scannedMB: Math.round(scanned / 1048576), ms: Date.now() - t0, partial: true };
  }
  return { target: v.toString(), hits: hits, scannedMB: Math.round(scanned / 1048576), ms: Date.now() - t0 };
}

// find-text (M25, 개발 도구): 화면 글(UTF-8)이 메모리 어디에 있고 누가 들고 있나.
// 게임 문자열 = 핸들 -> 포인터 -> {u32 길이, UTF-8}. 글을 찾고 -> 길이 칸을 가리키는 칸 -> 그 칸을 가리키는 칸(핸들)의 주인 객체까지 올라간다.
function scanAll(pat, max, budgetMs, t0) {
  var out = [], ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: false }).filter(function (r) { return r.size < 0x40000000; });
  for (var i = 0; i < ranges.length && out.length < max; i++) {
    var res; try { res = Memory.scanSync(ranges[i].base, ranges[i].size, pat); } catch (e) { continue; }
    for (var j = 0; j < res.length && out.length < max; j++) out.push({ a: res[j].address, base: ranges[i].base });
    if (Date.now() - t0 > budgetMs) break;
  }
  return out;
}
function ptrPat(v) { var s = []; for (var i = 0; i < 8; i++) s.push(('0' + v.shr(8 * i).and(0xff).toInt32().toString(16)).slice(-2)); return s.join(' '); }
function ownerOf(a, base, back) {
  for (var o = 0; o <= back; o += 8) {
    var q = a.sub(o); if (q.compare(base) < 0) break;
    var r = null; try { r = rttiInfo(q); } catch (e) {}
    if (r) return { owner: r.top.toString(), cls: r.name, off: '0x' + a.sub(r.top).toString(16) };
  }
  return null;
}
function findText(text, max, budgetMs) {
  max = max || 10; budgetMs = budgetMs || 40000;
  var t0 = Date.now(), bytes = [], u = unescape(encodeURIComponent(text));
  for (var i = 0; i < u.length; i++) bytes.push(('0' + u.charCodeAt(i).toString(16)).slice(-2));
  var hits = scanAll(bytes.join(' '), 50, budgetMs, t0), out = [];
  for (var k = 0; k < hits.length && out.length < max && Date.now() - t0 < budgetMs; k++) {
    var h = hits[k].a, lenp = h.sub(4), item = { str: h.toString() };
    try { var n = lenp.readU32(); item.len = n; item.full = h.readUtf8String(Math.min(n, 300)); if (n < u.length || n > 4000) { item.note = '길이 칸 아님'; out.push(item); continue; } } catch (e) { continue; }
    var r1 = scanAll(ptrPat(lenp), 4, budgetMs, t0);
    item.refs = r1.map(function (x) {
      var o = { at: x.a.toString() }, ow = ownerOf(x.a, x.base, 0x400); if (ow) o.holder = ow;
      var r2 = scanAll(ptrPat(x.a), 4, budgetMs, t0);
      o.handles = r2.map(function (y) { var z = { at: y.a.toString() }, w = ownerOf(y.a, y.base, 0x800); if (w) z.holder = w; return z; });
      return o;
    });
    out.push(item);
  }
  return { hits: out, ms: Date.now() - t0, partial: Date.now() - t0 >= budgetMs };
}

// find-bytes (E09, 개발 도구): 바이트 패턴(16진수, ?? = 아무 바이트)을 힙(rw-)에서 찾는다. opt.module이면 fm.exe 쓰기 구역(전역)도.
// 찾은 곳마다 앞뒤 바이트(ctx)와, opt.owner면 앞쪽 0x800 안의 RTTI 객체(주인)를 알려 준다. 정렬(opt.align)이 안 맞는 곳은 뺀다.
function findBytes(pat, opt) {
  opt = opt || {};
  var max = opt.max || 40, budgetMs = opt.budget || 20000, align = opt.align || 1, ctx = opt.ctx || 16;
  var t0 = Date.now(), hits = [], scanned = 0, total = 0;
  var ranges = Process.enumerateRanges({ protection: 'rw-', coalesce: false })
    .filter(function (r) { return r.size < 0x40000000 && (opt.module || !inModule(r.base)); });
  for (var i = 0; i < ranges.length && hits.length < max; i++) {
    var res; try { res = Memory.scanSync(ranges[i].base, ranges[i].size, pat); } catch (e) { continue; }
    for (var j = 0; j < res.length && hits.length < max; j++) {
      var a = res[j].address; if (align > 1 && a.and(align - 1).toInt32() !== 0) continue;
      total++;
      var h = { at: inModule(a) ? 'fm+0x' + a.sub(B).toString(16) : a.toString() };
      try { var s = a.sub(ctx).compare(ranges[i].base) < 0 ? a : a.sub(ctx); h.ctxAt = s.toString(); h.ctx = hexOf(s, Math.min(ctx * 3, ranges[i].base.add(ranges[i].size).sub(s).toInt32())); } catch (e) {}
      if (opt.owner) { var ow = ownerOf(a, ranges[i].base, 0x800); if (ow) h.holder = ow; }
      hits.push(h);
    }
    scanned += ranges[i].size;
    if (Date.now() - t0 > budgetMs) return { pat: pat, hits: hits, scannedMB: Math.round(scanned / 1048576), ms: Date.now() - t0, partial: true, ranges: ranges.length, at: i };
  }
  return { pat: pat, hits: hits, scannedMB: Math.round(scanned / 1048576), ms: Date.now() - t0, ranges: ranges.length, truncated: hits.length >= max };
}
function hexOf(p, n) { var b = new Uint8Array(p.readByteArray(n)), s = []; for (var i = 0; i < b.length; i++) s.push(('0' + b[i].toString(16)).slice(-2)); return s.join(' '); }

// find-const (M37, 개발 도구): 실행 중인 fm.exe 모듈(코드 포함) 안에서 4글자 상수(예: 위젯 id 'GCNT', 이벤트 'CONT')가 쓰이는 곳을 찾는다.
// 디스크의 fm.exe는 일부가 암호화돼 있어(Denuvo) 파일 검색으로는 안 나오는 상수가 있다. 값은 u32 리틀엔디언(메모리에는 글자가 거꾸로).
function findConst(code, max) {
  max = max || 60;
  var pat = []; for (var i = 3; i >= 0; i--) pat.push(('0' + (i < code.length ? code.charCodeAt(i) : 32).toString(16)).slice(-2));
  var hits = [], t0 = Date.now(), ranges = Process.getModuleByName('fm.exe').enumerateRanges('r--');
  for (var ri = 0; ri < ranges.length && hits.length < max; ri++) {
    var res; try { res = Memory.scanSync(ranges[ri].base, ranges[ri].size, pat.join(' ')); } catch (e) { continue; }
    for (var j = 0; j < res.length && hits.length < max; j++) hits.push({ at: 'fm+0x' + res[j].address.sub(B).toString(16), prot: ranges[ri].protection });
  }
  return { code: code, hits: hits, ms: Date.now() - t0, truncated: hits.length >= max };
}

// ---- 화면 위젯 트리 (M25: AI가 FM을 플레이 A단계 "보는 눈") ----
// fm+0x63635b8 SCREEN_CLIENT_MANAGER -> +0x68 INTERNAL_DATA -> +0x18 화면 목록(시작/끝) -> GAME_SCREEN_CLIENT -> +0x58 뿌리 CONTAINER.
// 위젯: +0x10 부모, +0x48 화면, +0x5c id 4글자, +0x70 WIDGET_FLAGS. CONTAINER: +0x100/+0x108 자식 포인터 배열.
var UI_SCM = 0x63635b8;
function uiClients() {
  var out = [];
  try {
    var idata = B.add(UI_SCM).readPointer().add(0x68).readPointer();
    var b = idata.add(0x18).readPointer(), e = idata.add(0x20).readPointer();
    for (var a = b; a.compare(e) < 0 && out.length < 16; a = a.add(8)) { var c = a.readPointer(); if (isA(c, 'SCREEN_CLIENT')) out.push(c); }
  } catch (x) {}
  return out;
}
function fourcc(v) { var s = ''; for (var i = 3; i >= 0; i--) { var ch = (v >>> (8 * i)) & 0xff; s += (ch >= 32 && ch < 127) ? String.fromCharCode(ch) : '?'; } return s; }
function uiKids(w) {
  var out = [];
  try {
    if (!isA(w, 'sitoolkit::CONTAINER')) return out;
    var b = w.add(0x100).readPointer(), e = w.add(0x108).readPointer(), n = e.sub(b).toInt32() / 8;
    if (n < 0 || n > 4096) return out;
    for (var i = 0; i < n; i++) out.push(b.add(8 * i).readPointer());
  } catch (x) {}
  return out;
}
// 화면 글자: sitoolkit::MULTI_LINE_STRING (위젯 몸 안에 박혀 있거나 포인터) +0x98/+0xa0 = 줄 목록 시작/끝, 칸마다 문자열 핸들.
// CLICKABLE_TEXT(TEXT 위젯 +0x100), EDITABLE_TEXT도 MULTI_LINE_STRING을 물려받아 같은 칸을 쓴다.
var MLS_VTS = {};
function isMlsVt(v) {
  if (!inModule(v)) return false;
  var k = v.toString();
  if (!(k in MLS_VTS)) {
    var r = rttiOfVt(v);
    MLS_VTS[k] = !!r && r.off === 0 && (r.name === 'sitoolkit::MULTI_LINE_STRING' || r.bases.indexOf('sitoolkit::MULTI_LINE_STRING') >= 0);
  }
  return MLS_VTS[k];
}
function mlsLines(m) {
  var out = [];
  try {
    var b = m.add(0x98).readPointer(), e = m.add(0xa0).readPointer(), n = e.sub(b).toInt32() / 8;
    if (n <= 0 || n > 200) return out;
    for (var i = 0; i < n; i++) { var s = strAt(b.add(8 * i)); if (s) out.push(s); }
  } catch (x) {}
  return out;
}
// 클래스마다 글 객체 위치를 배운다: 처음 몇 개는 몸 전체를 훑고(UI_FULL번), 그다음부터는 배운 위치만 본다 (트리 한 번에 위젯 수천 개).
var UI_TEXT_OFFS = {}, UI_FULL = 4;
function uiText(w, cls) {
  var out = [], scr = null, L = cls ? (UI_TEXT_OFFS[cls] = UI_TEXT_OFFS[cls] || { n: 0, offs: {} }) : null;
  var full = !L || L.n < UI_FULL, list = [];
  if (full) { for (var o = 0x60; o < 0x600; o += 8) list.push(o); if (L) L.n++; }
  else list = Object.keys(L.offs).map(Number);
  try { scr = w.add(0x48).readPointer(); } catch (x) {}
  for (var i = 0; i < list.length; i++) {
    var o = list[i], v; try { v = w.add(o).readPointer(); } catch (x) { break; }
    if (full && scr && o > 0x80 && v.equals(scr)) break;   // 다음 위젯의 +0x48(화면)이 나오면 이 위젯 몸이 끝난 것 (옆 위젯 글을 읽지 않게)
    var m = null;
    if (isMlsVt(v)) m = w.add(o);
    else if (!inModule(v) && v.compare(ptr(0x10000)) > 0 && v.and(7).toInt32() === 0) { try { if (isMlsVt(v.readPointer())) m = v; } catch (x) {} }
    if (m) {
      if (L) L.offs[o] = 1;
      var t = mlsLines(m).join('\n'); if (t && out.indexOf(t) < 0) out.push(t);
    }
  }
  return out;
}
function uiStrings(w, from, to) {   // 위젯 몸 안의 글 칸 (조사용)
  var out = [];
  for (var o = from; o < to; o += 8) { var s = strAt(w.add(o)); if (s) out.push('+0x' + o.toString(16) + '=' + s); }
  return out;
}
function uiTree(opts) {
  opts = opts || {};
  var maxDepth = opts.depth || 12, maxNodes = opts.max || 400, scan = opts.scan || 0, t0 = Date.now();
  var roots = opts.root ? [ptr(opts.root)] : uiClients().map(function (c) { return c.add(0x58).readPointer(); });
  var nodes = [], hidden = 0, all = !!opts.all, textOnly = !!opts.textOnly;
  var modal = false;
  var DIALOG_BTN_IDS = { yes: 1, no: 1, ok: 1, clos: 1, canc: 1 };
  function walk(w, d, pvis, inModal, inHover) {
    if (nodes.length >= maxNodes) return;
    var r = rttiInfo(w); if (!r) return;
    var flags = 0; try { flags = w.add(0x78).readU32(); } catch (x) {}
    var vis = pvis && (flags & 2) !== 0;   // WIDGET_FLAGS 0x2 = 보임 (M25: 배경 10개 중 보이는 1개만 켜짐). 부모가 숨으면 자식도 숨음
    if (!vis && !all) { hidden++; return; }
    var n = { d: d, addr: w.toString(), cls: r.name };
    if (!vis) n.hidden = true;
    try { var id = w.add(0x5c).readU32(); if (id && id !== 0x4e554c4c) n.id = fourcc(id); } catch (x) {}
    n.flags = flags.toString(16);
    try { n.rect = [0x60, 0x64, 0x68, 0x6c].map(function (o) { return Math.round(w.add(o).readFloat()); }); } catch (x) {}   // 게임 창 기준 x, y, 너비, 높이 (M25 스크린샷과 대조)
    // M32: 버튼이 하나도 없는 팝업(마우스를 올리면 뜨는 정보 툴팁 '대략적인 가격' 등)은 팝업으로 세지 않는다
    // M39: 마우스를 올리면 뜨는 정보 팝업(MODAL_POPUP_PANEL, 예: 순위표)은 버튼이 있어도 대화 상자가 아니다 -> 예/아니요/확인/닫기/취소 버튼만 센다
    if (inModal) { n.modal = true; if (vis && r.name !== 'MODAL_SHEET' && (r.name === 'BUTTON' || r.bases.indexOf('BUTTON') >= 0) && (!inHover || DIALOG_BTN_IDS[(n.id || '').trim()])) modal = true; }   // 'modl' 가지 아래 = 팝업·대화 상자 (M27: 조건 팝업으로 확인). MODAL_SHEET 빈 틀만 남고 안쪽 메뉴가 숨은 상태는 제외
    if (r.name === 'CHECK_BOX' || r.bases.indexOf('CHECK_BOX') >= 0) n.checked = (flags & 0x10) !== 0;   // M27: 0x10 = 체크됨 (조건 팝업 21개 대조)
    if (scan) n.str = uiStrings(w, 0x60, scan);
    var tx = uiText(w, r.name); if (tx.length) n.text = tx;
    var kids = uiKids(w); if (kids.length) n.kids = kids.length;
    if (!textOnly || n.text) nodes.push(n);
    if (d < maxDepth) for (var i = 0; i < kids.length; i++) walk(kids[i], d + 1, vis, inModal || n.id === 'modl', inHover || r.name === 'sitoolkit::MODAL_POPUP_PANEL');
  }
  roots.forEach(function (rt) { walk(rt, 0, true, false, false); });
  var screen = null;
  try { screen = [0x68, 0x6c].map(function (o) { return Math.round(roots[0].add(o).readFloat()); }); } catch (x) {}   // 뿌리 컨테이너 크기 = 게임 창
  if (screen) nodes.forEach(function (n) {   // 가운데가 창 밖이면 스크롤해야 보이는 것
    if (!n.rect) return;
    var cx = n.rect[0] + n.rect[2] / 2, cy = n.rect[1] + n.rect[3] / 2;
    if (cx < 0 || cy < 0 || cx > screen[0] || cy > screen[1]) n.off = true;
  });
  return { clients: uiClients().map(String), screen: screen, nodes: nodes, hidden: hidden, modal: modal, ms: Date.now() - t0, truncated: nodes.length >= maxNodes };
}

// ---- 진행 상태 (M30: AI 플레이 D단계 "기다리기") ----
// 날짜 원값(fm+0x631d5bc: 상위 16비트 연도, 하위 9비트 연중 일수, 그 위 비트 = 시각), 진행 화면, 오른쪽 위 버튼(GCNT/MDSB), 팝업, 화면 제목·시각.
function uiState() {
  var t0 = Date.now(), tr = uiTree({ depth: 30, max: 3000 }), st = { modal: !!tr.modal, processing: false, button: null, buttonId: null, needReply: false, title: null, clock: null };
  try { var raw = M24GA.readGame ? (M24GA.readGame() || {}).date : null; st.raw = raw >>> 0; var dd = m24gaDecodeDate(raw); st.date = dd ? dd.iso : null; } catch (x) {}
  for (var i = 0; i < tr.nodes.length; i++) {
    var n = tr.nodes[i], tx = (n.text || []).join(' / ');
    if (n.cls === 'GAME_PROCESSING_PANEL_CONTAINER' || n.cls === 'GAME_PROCESSING_PANEL') st.processing = true;   // 보이는 것만 트리에 있음
    if (!st.button && (n.id === 'GCNT' || n.id === 'MDSB')) { st.button = tx || null; st.buttonId = n.id; if (n.id === 'MDSB') st.needReply = true; }
    if (!st.next && (n.id === 'nxbt' || n.id === 'endB' || n.id === 'IMBu')) { st.next = tx || null; st.nextId = n.id; }   // IMBu: 경기 직전 '라커룸' (M33)   // M31: 면담 nxbt('요약','미팅 떠나기'), 스탭 회의 endB('미팅 종료')   // M31: 단계형 화면(면담 …)의 다음 버튼 ('요약' -> '미팅 떠나기')
    if (!st.title && n.id === 'sect') st.title = tx;
    if (!st.item && n.id === 'nwhd') { st.item = tx; st.itemAddr = n.addr; }   // M31: 열린 메일·뉴스 제목 ("다음 읽기"는 이것만 바뀐다)
    if (!st.itemBody && n.id === 'etxt') st.itemBody = tx.slice(0, 80);       // 같은 제목 메일이 이어질 때 구분
    if (n.id === 'dytm') st.clock = tx;
    if (n.id === 'dtam' && !st.screenDate) st.screenDate = tx;
  }
  if (!st.button && st.next) { st.button = st.next; st.buttonId = st.nextId; }
  var busy = gameBusy(); st.busy = busy; if (busy) st.processing = true;   // M36: 진행 화면이 안 보이는 스킨에서도 (CONTINUE_MANAGER)
  try { st.seq = contMgr().add(0xde).readU16(); } catch (x) {}
  try { st.lang = uiLang(); } catch (x) {}
  st.kind = contKind; st.kindName = contKind === null ? null : contKindName(contKind);
  // M37: 버튼 id(MDSB) 없이도. 단, 단계형 화면(면담·스탭 회의: 다음 버튼만 보임)은 그 화면 자체가 답하는 중이라 제외
  if (contKind === CONT_NEED_REPLY && !(st.nextId && st.buttonId === st.nextId)) st.needReply = true;
  // M33: 스킨이 id를 바꿨거나 뺀 경우를 알려 준다 (알 수 없는 스킨에서 조용히 틀리지 않게). 게임 날짜는 메모리에서 읽으므로 이것과 무관.
  var seenIds = {}; tr.nodes.forEach(function (n) { if (n.id) seenIds[n.id] = 1; });
  st.skinOk = contKind !== null || !!(seenIds.GCNT || seenIds.MDSB || seenIds.nxbt || seenIds.endB || seenIds.IMBu || st.modal || !tr.nodes.length);
  if (!st.skinOk) st.note = "계속 버튼(GCNT/MDSB/nxbt/endB)을 못 찾았어요. 처음 보는 화면이거나 스킨이 버튼 id를 바꿨을 수 있어요 (ui text로 확인)";
  st.ms = Date.now() - t0;
  return st;
}

// ---- 메일 (M31: 수신함 메일 읽기와 답하기) ----
// NEWS_ITEM_PANEL(id nitp) 안: 왼쪽 목록 = NEWS_ITEM_LIST_WIDGET 줄들 (catw 보낸 이, time, hdlw 제목),
// 오른쪽 = 열린 메일 (nwhd 제목, snob/sjob 보낸 이, etxt 본문, 그 밖의 글, 버튼: ybut 확인류 / xbut 거절·취소류 / 업무 위임 메뉴 …)
var MAIL_DANGER = /이적|계약|제의|제안|임대|영입|판매|방출|해고|입찰|협상|transfer|contract|offer|loan|bid/i;
// 답 버튼 종류: id(ybut/xbut) 또는 글. 이적 제의 메일은 '제의 수락'[set ] / '제의 거절'[disc] / '요구 사항 제안'[sgtm] (M31 실기)
var MAIL_YES = /^(확인|수락|제의 수락|참석|기자 ?회견 참석|동의|예|accept|confirm|ok|yes)$/i, MAIL_NO = /^(거절|취소|제의 거절|거부|아니요|reject|decline|cancel|no)$/i;
function mailBtnKind(n, tx) {
  if (n.id === 'ybut' || n.id === 'accw' || MAIL_YES.test(tx || '')) return 'yes';   // accw/canw: 여러 제의 메일의 줄별 수락/거절 아이콘 (M32)
  if (n.id === 'xbut' || n.id === 'canw' || MAIL_NO.test(tx || '')) return 'no';
  return n.cls.indexOf('POPUP') >= 0 ? 'menu' : 'other';
}
function uiMail() {
  var tr = uiTree({ depth: 40, max: 3000 }), nodes = tr.nodes, i, p = -1;
  // 스킨마다 NEWS_ITEM_PANEL이 목록까지 감쌀 수도(기존 스킨), 본문만 감쌀 수도(오리지널 스킨) 있다 (M33). 그래서 범위를 INBOX_PANEL(없으면 NEWS_ITEM_PANEL)로 잡고,
  // 목록은 NEWS_ITEM_PANEL '밖'의 NEWS_ITEM_LIST_WIDGET, 본문은 NEWS_ITEM_PANEL '안'이라는 구조로 나눈다 (위치 비교 안 함).
  var nip = -1;
  for (i = 0; i < nodes.length; i++) { if (nodes[i].cls === 'INBOX_PANEL' && p < 0) p = i; if (nodes[i].cls === 'NEWS_ITEM_PANEL' && nip < 0) nip = i; }
  if (p < 0) p = nip;
  if (p < 0) return { error: '열린 메일 화면이 없어요 (수신함에서 메일을 여세요: act click Pibx / act continue)' };
  var pd = nodes[p].d, list = [], row = null, rowD = -1, mail = { texts: [], buttons: [] }, end = p + 1, listRight = 0, rowStatus = null;
  while (end < nodes.length && nodes[end].d > pd) end++;
  var nipEnd = -1, nipD = nip >= 0 ? nodes[nip].d : -1;
  if (nip >= 0) { nipEnd = nip + 1; while (nipEnd < nodes.length && nodes[nipEnd].d > nipD) nipEnd++; }
  for (i = p + 1; i < end; i++) {
    var n = nodes[i], tx = (n.text || []).join('\n');
    if (row && n.d <= rowD) row = null;
    var inNip = nip >= 0 && i > nip && i < nipEnd;
    if (n.cls === 'NEWS_ITEM_LIST_WIDGET' && (!inNip || nodes[nip].cls === n.cls)) { row = { addr: n.addr, rect: n.rect }; rowD = n.d; list.push(row); if (n.rect) listRight = Math.max(listRight, n.rect[0] + n.rect[2]); continue; }
    if (row) {
      if (n.id === 'catw') row.from = tx; else if (n.id === 'time') row.time = tx; else if (n.id === 'hdlw') row.title = tx;
      continue;
    }
    if (n.modal) continue;
    // 본문 쪽인지: NEWS_ITEM_PANEL이 목록을 감싸는 스킨(기존)에서는 목록 오른쪽 경계로, 본문만 감싸는 스킨(오리지널)에서는 NEWS_ITEM_PANEL 안인지로 가른다
    var wraps = nip >= 0 && nodes.some(function (q, qi) { return qi > nip && qi < nipEnd && q.cls === 'NEWS_ITEM_LIST_WIDGET'; });
    var left = wraps ? (listRight && n.rect && n.rect[0] < listRight - 4) : !inNip;
    if (n.id === 'nwhd') mail.title = tx;
    else if (n.id === 'snob') mail.from = tx;
    else if (n.id === 'sjob') mail.fromJob = tx;
    else if (n.id === 'etxt') mail.body = tx;
    else if (left) continue;
    else if (n.id === 'Stts') { rowStatus = tx; mail.texts.push(tx); }   // M32: 여러 제의 메일의 줄 상태 ('이적 - 만든 제안' / '이적 - 거절')
    else if (isA(ptr(n.addr), 'BUTTON')) mail.buttons.push({ addr: n.addr, id: n.id || null, text: tx || null, cls: n.cls, kind: mailBtnKind(n, tx), row: rowStatus });
    else if (tx) mail.texts.push(tx);
  }
  var st = uiState();
  mail.needReply = !!st.needReply || mail.buttons.some(function (b) { return b.kind === 'yes' || b.kind === 'no'; });
  mail.lang = uiLang();
  mail.risky = MAIL_DANGER.test((mail.title || '') + ' ' + (mail.body || '')) || mail.lang === 'unknown';   // M39: 모르는 언어면 모든 메일을 위험으로 (--yes 필요)
  return { mail: mail, list: list, state: st, modal: tr.modal };
}

// ---- 화면 조작 (M28: AI가 FM을 플레이 B단계 "아는 손" — 계속 진행과 버튼 클릭) ----
// 모든 조작은 화면 스레드(onFrameEnd)에서 돌려 레이아웃·그리기와 겹치지 않게 한다.
var uiQueue = [], fnCont = null;
function runOnUi(fn) {
  if (!tickInstalled) installTick();
  if (!tickInstalled) return Promise.resolve({ error: '화면 스레드 훅이 아직 안 걸렸어요' });
  return new Promise(function (resolve) {
    var done = false, timer = setTimeout(function () { if (!done) { done = true; resolve({ error: '화면 스레드가 응답하지 않아요' }); } }, 3000);
    uiQueue.push(function () {
      if (done) return;
      done = true; clearTimeout(timer);
      try { resolve(fn()); } catch (e) { resolve({ error: String(e.message || e) }); }
    });
  });
}
// M29 안전장치: 세이브를 바꿀 수 있는 짧은 버튼 글(행동 버튼)은 confirm(--yes)이 있어야 누른다. 긴 글(뉴스 제목 등)은 열어 보기라 제외.
var ACT_DANGER = /제의|제안|계약|해고|방출|판매|매각|이적 ?명단|임대|사임|삭제|수락|거절|서명|입찰|지불|협상|은퇴|퇴단|offer|contract|sack|release|sell|resign|delete|accept|reject|sign|bid|negotiat/i;
// M39: 위 단어 목록은 한국어·영어뿐이다. 다른 언어로 게임을 하면 위험 버튼을 못 알아본다 -> 화면 글로 언어를 짐작해서,
// 모르는 언어면 짧은 버튼 글(행동 버튼) 전부를 위험으로 본다 (안전한 쪽으로 실패: --yes가 필요할 뿐 동작은 됨). 30초마다 다시 짐작.
var UI_LANG = null, UI_LANG_AT = 0;
var LANG_EN = /\b(Continue|Inbox|Home|Squad|Tactics|Schedule|Club|Transfers|Scouting|Training|Finances|News|Back|Next|Save|Options|Done|Confirm|Cancel|Close)\b/;
function uiLang() {
  if (UI_LANG && Date.now() - UI_LANG_AT < 30000) return UI_LANG;
  var tr = uiTree({ depth: 20, max: 600, textOnly: true }), ko = 0, en = 0, other = 0;
  tr.nodes.forEach(function (n) {
    var t = (n.text || []).join(' ');
    if (/[\uac00-\ud7a3]/.test(t)) ko++;
    else if (LANG_EN.test(t)) en++;
    else if (/[^\x00-\x7f]/.test(t.replace(/[0-9\s.,:;\/()\-–—'"%€£$]/g, ''))) other++;
  });
  UI_LANG = ko >= 3 ? 'ko' : (en >= 3 && en > other ? 'en' : (tr.nodes.length ? 'unknown' : (UI_LANG || 'unknown')));
  UI_LANG_AT = Date.now();
  return UI_LANG;
}
function actDanger(texts) {
  var short = (texts || []).filter(function (t) { return t && t.length <= 15; });
  if (short.some(function (t) { return ACT_DANGER.test(t); })) return true;
  return short.length > 0 && uiLang() === 'unknown';   // 모르는 언어: 행동 버튼은 모두 --yes
}
function uiVisibleChain(w) {   // 자기와 조상 모두 보임(+0x78 & 2)인가
  for (var p = w, k = 0; p && !p.isNull() && k < 64; k++) {
    if (!isA(p, 'sitoolkit::WIDGET')) break;   // 뿌리 컨테이너의 부모는 GAME_SCREEN_CLIENT (위젯 아님, +0x78은 플래그가 아님)
    var f; try { f = p.add(0x78).readU32(); } catch (x) { return false; }
    if ((f & 2) === 0) return false;
    try { p = p.add(0x10).readPointer(); } catch (x) { return false; }
  }
  return true;
}
function fireBtn(w, opts) {
  opts = opts || {};
  var r = rttiInfo(w);
  if (!r || (r.name !== 'BUTTON' && r.bases.indexOf('BUTTON') < 0)) return { error: '버튼 위젯이 아니에요 (' + (r ? r.name : '알 수 없음') + ')' };
  if (!uiVisibleChain(w)) return { error: '숨어 있는 버튼이에요 (자기나 부모가 안 보임)' };
  var id = null, tx = uiText(w, r.name);
  if (opts.label && tx.indexOf(opts.label) < 0) tx = tx.concat([opts.label]);
  try { var iv = w.add(0x5c).readU32(); if (iv && iv !== 0x4e554c4c) id = fourcc(iv); } catch (x) {}
  if (!opts.confirm && actDanger(tx)) return { error: "'" + tx.join(' / ') + "'은 세이브를 바꿀 수 있는 버튼이라 누르지 않았어요. 정말 누르려면 --yes", needConfirm: true, addr: w.toString(), cls: r.name, id: id, text: tx };
  var dummy = Memory.alloc(0x40);   // 빈 이벤트 기록 (포인터 3개 + u32 2개 = 0)
  var fnClick = new NativeFunction(w.readPointer().add(0x140).readPointer(), 'uint8', ['pointer', 'pointer']);
  var ret = fnClick(w, dummy);
  var out = { ok: true, action: 'click', addr: w.toString(), cls: r.name, id: id, text: tx, handled: !!ret };
  if (r.name === 'CHECK_BOX' || r.bases.indexOf('CHECK_BOX') >= 0) out.checked = (w.add(0x78).readU32() & 0x10) !== 0;
  return out;
}
function btnOf(w) {   // 그 위젯 자신 또는 조상(5단계까지) 중 BUTTON. 자식 쪽으로는 내려가지 않는다 (M29: 엉뚱한 자식 버튼을 누르지 않게)
  for (var p = w, k = 0; p && !p.isNull() && k < 5; k++) {
    if (isA(p, 'BUTTON')) return p;
    try { p = p.add(0x10).readPointer(); } catch (x) { break; }
  }
  return null;
}
// M33: 즉석 결과를 스킨과 상관없이. 스킨의 '즉석 결과'(id INST) 버튼은 결국 CLIENT_TACTIC 이벤트 처리기에 'INST'를 보낸다
// (fm+0x223200 = CLIENT_TACTIC +0x38 부분의 vtable +0x28. 'INST' -> fm+0x277b10 즉석 결과, 이 경로에서만 불림).
// CLIENT_TACTIC은 경기 전 팀 선발 화면에 있을 때만 메모리에 있다 (실시간 경기 중에는 0개였음). vt = CLI가 RTTI 표에서 넘긴 CLIENT_TACTIC vtable RVA.
var EV_INST = 0x494e5354;
function uiInstant(opts) {
  var st = funcCheck('match.clientTacticEvent');
  if (!st.ok) return { error: '즉석 결과를 쓸 수 없어요: ' + st.error };
  if (!opts.vt) return { error: 'CLIENT_TACTIC vtable을 받지 못했어요 (CLI가 넘겨야 함)' };
  var f = findObjects([opts.vt], 8, 20000), objs = [];
  (f.hits || []).forEach(function (h) { var p = ptr(h.obj); if (className(p) === 'CLIENT_TACTIC') objs.push(p); });
  if (!objs.length) return { error: '경기 전 팀 선발 상태가 아니에요 (CLIENT_TACTIC 없음). 경기 날 팀 선발 화면에서 쓰세요', none: true };
  if (objs.length > 1 && opts.index == null) return { error: 'CLIENT_TACTIC이 ' + objs.length + '개예요 (--index로 고르기)', objs: objs.map(String) };
  var obj = objs[opts.index || 0], sub = obj.add(0x38);
  var fn = sub.readPointer().add(0x28).readPointer();
  if (!fn.equals(st.addr)) return { error: '이벤트 처리기가 예상과 달라요 (' + fn + ' != ' + st.addr + ')' };
  return runOnUi(function () {
    var call = new NativeFunction(st.addr, 'uint8', ['pointer', 'uint32', 'pointer']);
    var rec = Memory.alloc(0x40);
    var ret = call(sub, EV_INST, rec);
    return { ok: true, action: 'instant', obj: obj.toString(), handled: !!ret, count: objs.length };
  });
}
function uiAct(opts) {
  opts = opts || {};
  if (opts.cmd === 'instant') return uiInstant(opts);
  if (opts.cmd === 'holiday') return holidayStart(opts);
  return runOnUi(function () {
    if (opts.cmd === 'continue') {
      var tr = uiTree({ depth: 25, max: 1500 }), gcnt = null;
      if (tr.modal) return { error: '팝업이 떠 있어서 계속하지 않았어요. 팝업을 먼저 닫으세요 (ui text로 확인)' };
      // M32: 진행 중에는 누르지 않는다 (진행 중 GCNT는 '진행 중' = 멈추기 버튼일 수 있음. play가 기다리지 않고 다시 누른 일이 있음)
      if (gameBusy() || tr.nodes.some(function (n) { return n.cls === 'GAME_PROCESSING_PANEL_CONTAINER' || n.cls === 'GAME_PROCESSING_PANEL'; })) return { error: '게임이 진행 중이에요. 끝날 때까지 기다리세요 (ui state)', busy: true };
      var mdsb = null, nxbt = null;
      for (var i = 0; i < tr.nodes.length; i++) {
        if (tr.nodes[i].id === 'GCNT' && !gcnt) gcnt = tr.nodes[i];
        if (tr.nodes[i].id === 'MDSB' && !mdsb) mdsb = tr.nodes[i];
        if ((tr.nodes[i].id === 'nxbt' || tr.nodes[i].id === 'endB' || tr.nodes[i].id === 'IMBu') && !nxbt) nxbt = tr.nodes[i];   // 단계형 화면의 다음/끝 버튼
      }
      if (!gcnt && !mdsb && nxbt) {   // M31: 면담 등 단계형 화면의 다음 버튼. 위험 글(제의 …)이면 --yes 필요 (fireBtn 검사)
        var rn = fireBtn(ptr(nxbt.addr), { confirm: !!opts.confirm });
        if (rn.error) return rn;
        return { ok: true, action: 'continue', label: (nxbt.text || []).join(' / ') || null, addr: nxbt.addr, via: nxbt.id };
      }
      // M37: 계속은 버튼을 누르지 않고 게임 내부 계속 이벤트로 (스킨이 버튼 id를 바꿔도 됨). 게임이 종류에 따라 알아서 한다:
      // 진행 / 다음 읽기 / 수신함 / 답할 메일 열기(답변 요망). 버튼 글은 보이면 기록용으로만 쓴다.
      var btn = gcnt || mdsb, kind = null;
      try { var km = contMgr(), ks = funcCheck('ui.continueKind'); if (km && ks.ok) { if (!fnContKind) fnContKind = new NativeFunction(ks.addr, 'int', ['pointer']); kind = contKind = fnContKind(km); } } catch (x) {}
      if (!btn && !opts.force) {
        // 계속 버튼이 안 보이는 화면(선수 면담, 경기 등)에서는 하지 않는다 (M31). 단, 스킨이 id를 바꿔서 못 찾은 것일 수 있다:
        // 숨은 것까지 봐도 GCNT/MDSB가 아예 없고 제목줄(TITLEBAR_PANEL, 게임 코드 클래스)이 보이면 계속할 수 있는 화면으로 본다
        var idsExist = uiTree({ depth: 25, max: 6000, all: true }).nodes.some(function (n) { return n.id === 'GCNT' || n.id === 'MDSB'; });
        var titlebar = tr.nodes.some(function (n) { return n.cls === 'TITLEBAR_PANEL'; });
        if (idsExist || !titlebar) return { error: '계속 버튼이 없는 화면이에요 (면담·경기 등). ui text로 보고 그 화면에서 할 일을 하세요 (그래도 계속하려면 --force)', noButton: true };
      }
      var label = btn ? ((btn.text || []).join(' / ') || null) : (kind !== null ? contKindName(kind) : null);
      var cs = contSend();
      if (!cs.error) return { ok: true, action: 'continue', label: label, addr: btn ? btn.addr : null, via: 'ui.continueHandler', kind: kind, needReply: kind === CONT_NEED_REPLY || undefined };
      if (gcnt) {   // 내부 이벤트를 못 쓰면(다른 빌드 등) 예전처럼 버튼으로
        var r0 = fireBtn(ptr(gcnt.addr), { confirm: true });
        if (r0.error) return r0;
        return { ok: true, action: 'continue', label: label, addr: gcnt.addr, via: 'GCNT' };
      }
      return { error: '계속하지 못했어요: ' + cs.error };
    }
    if (opts.cmd === 'dialog') {   // M31: 떠 있는 팝업(확인 대화 상자)의 예/아니요. 팝업 안 버튼만
      var td = uiTree({ depth: 40, max: 3000 });
      if (!td.modal) return { error: '떠 있는 팝업이 없어요' };
      var wantK = String(opts.target || 'yes').trim(), qs = [], cands = [];
      td.nodes.forEach(function (n) {
        if (!n.modal) return;
        var tx = (n.text || []).join(' / ');
        if (n.id === 'ques' && tx) qs.push(tx);
        if (!isA(ptr(n.addr), 'BUTTON') || n.cls.indexOf('RADIO') >= 0 || n.cls.indexOf('CHECK') >= 0) return;
        var k = (n.id || '').trim() === 'yes' ? 'yes' : (n.id || '').trim() === 'no' ? 'no' : mailBtnKind(n, tx);
        if (k === wantK || tx === wantK || n.id === wantK) cands.push({ addr: n.addr, id: n.id || null, text: tx, kind: k });
      });
      if (!cands.length && wantK === 'yes') {   // M33: 예 버튼이 없는 알림 팝업(즉석 결과 결과 창 등)은 닫기(clos)·확인(ok)으로
        td.nodes.forEach(function (n) {
          if (!n.modal || !isA(ptr(n.addr), 'BUTTON')) return;
          var id = (n.id || '').trim(), tx = (n.text || []).join(' / ');
          if (id === 'clos' || id === 'ok' || /^(닫기|close|ok)$/i.test(tx)) cands.push({ addr: n.addr, id: n.id || null, text: tx, kind: 'close' });
        });
      }
      if (cands.length !== 1) return { error: "팝업에서 '" + wantK + "' 버튼을 하나로 못 정했어요 (" + cands.length + '개)', question: qs.join(' / '), buttons: cands };
      var rd = fireBtn(ptr(cands[0].addr), { confirm: !!opts.confirm || wantK === 'no', label: cands[0].text });
      if (!rd.error) { rd.action = 'dialog'; rd.question = qs.join(' / ') || null; }
      return rd;
    }
    if (opts.cmd === 'reply') {   // M31: 열린 메일 안의 버튼만. 이적·계약 같은 메일(MAIL_DANGER)은 --yes
      var m = uiMail(); if (m.error) return m;
      if (m.modal) return { error: '팝업이 떠 있어요. 팝업을 먼저 닫으세요' };
      var want = String(opts.target || 'ybut').trim();
      var bs = m.mail.buttons.filter(function (b) { return b.id === want || b.text === want || (want === 'yes' && b.kind === 'yes') || (want === 'no' && b.kind === 'no'); });
      if (opts.all) bs = bs.filter(function (b) { return !(b.row && /거절|수락|철회|완료|reject|accept|withdraw/i.test(b.row)); });   // M32: 이미 처리된 제의 줄은 건너뜀
      if (!bs.length) return { error: "메일에 '" + want + "' 버튼이 없어요", buttons: m.mail.buttons, none: true };
      if (bs.length > 1 && !opts.all) return { error: "메일에 '" + want + "' 버튼이 " + bs.length + '개예요 (id로 고르거나 --all로 첫 번째부터: 한 번에 하나씩 누름)', buttons: bs, many: true };
      if (m.mail.risky && !opts.confirm) return { error: "'" + (m.mail.title || '') + "'은 이적·계약 관련 메일이라 답하지 않았어요. 정말 답하려면 --yes", needConfirm: true, mail: m.mail.title, button: bs[0] };
      var rr = fireBtn(ptr(bs[0].addr), { confirm: true, label: bs[0].text });
      if (!rr.error) { rr.action = 'reply'; rr.mail = m.mail.title || null; }
      return rr;
    }
    if (opts.cmd === 'click') {
      var target = String(opts.target || '').trim(), idx = opts.index;
      if (!target) return { error: '클릭할 대상을 적어 주세요' };
      var tr2 = uiTree({ depth: 40, max: 3000 });
      if (/^0x[0-9a-f]+$/i.test(target)) {
        var bw = btnOf(ptr(target));
        if (!bw) return { error: target + '은 버튼도 아니고 버튼 안에 있지도 않아요' };
        if (tr2.modal && !opts.behind && !tr2.nodes.some(function (n) { return n.modal && n.addr === bw.toString(); })) return { error: '팝업이 떠 있어서 팝업 밖 버튼은 누르지 않았어요 (팝업을 연 버튼으로 닫을 때는 --behind)' };
        return fireBtn(bw, { confirm: opts.confirm });
      }
      var exact = [], part = [];
      tr2.nodes.forEach(function (n) {
        if (tr2.modal && !n.modal && !opts.behind) return;   // 팝업이 떠 있으면 팝업 안만 (사람도 뒤의 버튼은 못 누름). --behind면 밖도 (팝업을 연 버튼으로 닫기)
        var b = btnOf(ptr(n.addr)); if (!b) return;
        var tx = (n.text || []).join(' / ');
        var isExact = n.id === target || tx === target || (n.text || []).indexOf(target) >= 0;
        var isPart = !isExact && tx && tx.indexOf(target) >= 0;
        if (!isExact && !isPart) return;
        var list = isExact ? exact : part, bAddr = b.toString();
        if (!list.some(function (h) { return h.btn.toString() === bAddr; })) list.push({ btn: b, node: n, text: tx });
      });
      var pick = exact.length ? exact : (opts.partial ? part : []);
      var cand = function (l) { return l.map(function (h, j) { return { index: j, addr: h.btn.toString(), id: h.node.id || null, text: h.text || null, rect: h.node.rect || null, cls: className(h.btn) }; }); };
      if (!pick.length) {
        if (part.length) return { error: "'" + target + "'와 똑같은 버튼은 없어요. 일부만 맞는 버튼이 " + part.length + "개 있어요 (--partial로 고르기)", matches: cand(part) };
        return { error: "화면에서 '" + target + "' 버튼을 찾지 못했어요" + (tr2.modal && !opts.behind ? ' (팝업이 떠 있어서 팝업 안만 찾았어요. 밖 버튼은 --behind)' : '') };
      }
      if (pick.length > 1 && idx == null) return { error: "'" + target + "' 버튼이 " + pick.length + '개예요. --index로 하나를 고르세요 (누르지 않았어요)', matches: cand(pick) };
      idx = idx || 0;
      if (idx < 0 || idx >= pick.length) return { error: '순번이 범위를 벗어났어요 (0~' + (pick.length - 1) + ')', matches: cand(pick) };
      var res = fireBtn(pick[idx].btn, { confirm: opts.confirm, label: pick[idx].text });
      if (pick.length > 1) res.matches = cand(pick);
      return res;
    }
    return { error: '모르는 조작: ' + opts.cmd };
  });
}

function exploreObj(spec, from, size) {
  var t = exploreResolve(spec); if (t.error) return t;
  from = from || 0; size = Math.min(size || 0x400, 0x4000);
  var r = rttiInfo(t.p), out = { path: t.path, addr: t.p.toString(), cls: r ? r.name : null, clsOff: r ? r.off : null, top: r ? r.top.toString() : null,
    bases: r ? r.bases : null, from: from, slots: [] };
  var fm = r ? fieldsAt(r) : {}, base = r ? r.off : 0;   // 등록된 필드 이름 붙이기 (필드 위치는 객체 맨 앞 기준)
  for (var o = from; o < from + size; o += 8) {
    var sl;
    try { sl = exploreSlot(t.p, o); } catch (e) { out.slots.push({ off: o, error: '읽기 실패' }); break; }
    for (var k = 0; k < 8; k++) { var names = fm[base + o + k]; if (names) (sl.fields = sl.fields || []).push.apply(sl.fields, names.map(function (n) { return k ? n + '(+' + k + ')' : n; })); }
    out.slots.push(sl);
  }
  return out;
}

// ---- 찾기 도구 (M21, 개발 도구: CLI find-field / watch-write가 rpc로 부른다. 모드 API가 아님) ----
// find-field: 객체(맨 앞부터 size바이트)와, 그 안의 포인터가 가리키는 곳(깊이 1, 각 0x400바이트)에서 값이 [lo, hi]인 칸을 찾는다.
// 메모리는 한 번에 읽어 DataView로 훑는다 (칸마다 read를 부르면 느리다).
var FIND_TYPES = { i8: [1, 'getInt8'], u8: [1, 'getUint8'], i16: [2, 'getInt16'], u16: [2, 'getUint16'], i32: [4, 'getInt32'], u32: [4, 'getUint32'],
  f32: [4, 'getFloat32'], f64: [8, 'getFloat64'] };
function findIn(base, size, q, via, hits) {
  var buf; try { buf = base.readByteArray(size); } catch (e) { return false; }
  if (!buf) return false;
  var dv = new DataView(buf);
  q.types.forEach(function (t) {
    var w = FIND_TYPES[t][0], fn = FIND_TYPES[t][1];
    for (var o = 0; o + w <= size; o += (w >= 4 ? 4 : w)) {   // 4바이트 이상은 4바이트 정렬만 본다
      var v = dv[fn](o, true);
      if (v >= q.lo && v <= q.hi && v === v) { hits.push({ via: via, off: '0x' + o.toString(16), type: t, value: v }); if (hits.length > 400) return; }
    }
  });
  return true;
}
function findField(spec, q) {
  var t = exploreResolve(spec); if (t.error) return t;
  var r = rttiInfo(t.p), base = r ? r.top : t.p, size = Math.min(q.size || 0x800, 0x4000), hits = [];
  findIn(base, size, q, [], hits);
  if (q.deep) {
    var seen = {};
    for (var o = 0; o + 8 <= size; o += 8) {
      try {
        var p = base.add(o).readPointer();
        if (p.isNull() || p.and(7).toInt32() !== 0 || p.compare(ptr('0x10000')) < 0 || p.compare(ptr('0x800000000000')) >= 0 || inModule(p) || seen[p]) continue;
        seen[p] = 1;
        findIn(p, 0x400, q, ['0x' + o.toString(16)], hits);
      } catch (e) {}
      if (hits.length > 400) break;
    }
  }
  return { path: t.path, cls: r ? r.name : null, bases: r ? r.bases : null, top: base.toString(), hits: hits, truncated: hits.length > 400 };
}

// watch-write: 칸 하나에 하드웨어 감시(디버그 레지스터)를 건다. 걸 때 있던 게임 스레드 전부에 건다 (그 뒤 생긴 스레드는 안 잡힌다).
// 값을 쓴 명령 뒤에서 예외가 나면 위치·호출 경로·레지스터가 가리키는 객체의 클래스를 모으고 계속 실행한다.
// max번 잡거나 secs초가 지나면 스스로 푼다. 우리 감시가 아닌 예외는 건드리지 않는다 (false를 돌려 게임에 넘김).
var WATCH = null, EXC_SET = false, WATCH_LATE = 0, WATCH_LATE_AT = 0, WATCH_UNSET_ERR = 0;
function watchHandler(d) {
  var w = WATCH;
  if (d.type !== 'single-step' && d.type !== 'breakpoint') return false;
  // 감시를 푼 뒤에도 감시 예외가 늦게 올 수 있다 (E02 실기 2번 튕김, 0x80000004): 자주 읽히는 칸(엔진 표)에 --rw를 걸면
  // 디버그 레지스터가 어떤 스레드에서는 바로 안 지워져 계속 잡힌다. 처리기가 남아 있는 동안(=excRelease가 조용해졌다고
  // 확인하기 전까지)은 single-step을 삼킨다.
  if (!w) { if (d.type === 'single-step' && watchLast) { WATCH_LATE++; WATCH_LATE_AT = Date.now(); return true; } return false; }
  try {
    var pc = d.context.pc, k = inModule(pc) ? 'fm+0x' + pc.sub(B).toString(16) : pc.toString();
    var h = w.hits[k];
    if (!h) {
      if (Object.keys(w.hits).length >= 40) { w.dropped++; return true; }
      var regs = {};
      ['rcx', 'rdx', 'rbx', 'rsi', 'rdi', 'r8', 'r9', 'r12', 'r13', 'r14', 'r15', 'rax'].forEach(function (rn) {
        try { var v = d.context[rn]; if (!v || inModule(v)) return; var ri = rttiInfo(v); if (ri) regs[rn] = ri.name + (ri.off ? '@+0x' + ri.off.toString(16) : '') + (v.equals(w.obj) ? ' (감시 객체)' : ''); } catch (e) {}
      });
      var bt = [];
      try { bt = Thread.backtrace(d.context, Backtracer.FUZZY).slice(0, 10).map(function (a) { return inModule(a) ? 'fm+0x' + a.sub(B).toString(16) : a.toString(); }); } catch (e) {}
      h = w.hits[k] = { pc: k, count: 0, first: Date.now() - w.t0, tid: Process.getCurrentThreadId(), regs: regs, bt: bt, values: [] };
    }
    if (w.full) { WATCH_LATE++; return true; }
    h.count++; w.total++;
    if (h.values.length < 8) { try { h.values.push(w.read()); } catch (e) {} }
    // 예외 처리기 안(게임 스레드)에서 풀면 그 스레드의 디버그 레지스터가 안 지워졌다 (E02: 늦은 예외 54,597번).
    // 그래서 여기서는 표시만 하고, 푸는 일은 JS 스레드(setTimeout)에서 한다
    if (w.total >= w.max && !w.full) { w.full = true; setTimeout(function () { if (WATCH === w) watchStop('최대 횟수'); }, 0); }
  } catch (e) { w.errs = (w.errs || 0) + 1; }
  return true;
}
function watchStart(spec, off, size, cond, max, secs) {
  if (WATCH) return { error: '이미 감시 중이에요 (watch-write stop)' };
  var t = exploreResolve(spec); if (t.error) return t;
  size = size || 4; if ([1, 2, 4, 8].indexOf(size) < 0) return { error: '크기는 1, 2, 4, 8 중 하나' };
  var a = t.p.add(off || 0);
  if (a.and(size - 1).toInt32() !== 0) return { error: '주소가 크기(' + size + ')에 맞게 정렬돼 있지 않아요: ' + a };
  var rd = { 1: 'readU8', 2: 'readU16', 4: 'readU32', 8: 'readU64' }[size];
  if (!EXC_SET) { Process.setExceptionHandler(watchHandler); EXC_SET = true; }
  var w = { addr: a, obj: t.p, path: t.path + '+0x' + (off || 0).toString(16), size: size, cond: cond || 'w', max: max || 30, t0: Date.now(),
    hits: {}, total: 0, dropped: 0, threads: [], fails: 0, before: null, read: function () { var v = a[rd](); return typeof v === 'number' ? v : v.toString(); } };
  try { w.before = w.read(); } catch (e) { return { error: '그 주소를 읽지 못했어요: ' + a }; }
  WATCH = w;
  Process.enumerateThreads().forEach(function (th) {
    try { th.setHardwareWatchpoint(0, a, size, w.cond); w.threads.push(th.id); } catch (e) { w.fails++; w.failMsg = String(e.message || e); }
  });
  if (!w.threads.length) { WATCH = null; return { error: '감시를 걸지 못했어요: ' + (w.failMsg || '스레드 없음') }; }
  w.timer = setTimeout(function () { watchStop('시간 끝'); }, Math.min(secs || 60, 600) * 1000);
  return watchReport();
}
function watchStop(why) {
  var w = WATCH; if (!w) return null;
  watchLast = w;   // WATCH를 비우기 전에: 그 사이에 오는 늦은 예외도 처리기가 삼키도록 (watchLast가 있어야 삼킨다)
  WATCH = null; w.why = why || '멈춤'; w.t1 = Date.now();
  try { clearTimeout(w.timer); } catch (e) {}
  WATCH_LATE_AT = Date.now();
  Process.enumerateThreads().forEach(function (th) { if (w.threads.indexOf(th.id) >= 0) { try { th.unsetHardwareWatchpoint(0); } catch (e) {} } });
  excRelease();
  watchLast = w;
  return w;
}
var watchLast = null;
// 예외 처리기를 감시가 끝나면 바로 푼다. 처리기가 남은 채 스크립트를 내리면 frida-agent가 0xc0000409로 게임을 튕겼다 (M21 실기).
// 처리기는 "조용해진 뒤에만" 내린다: 1초마다 감시했던 스레드의 디버그 레지스터를 다시 지우고, 늦은 감시 예외가
// 3초 동안 한 번도 없을 때만 처리기를 내린다. 계속 오면 내리지 않고 기다린다 (내리면 게임이 튕기니까).
// 예외 처리기 안에서 자기 자신을 풀지 않도록 setTimeout으로 JS 스레드에서 한다.
var EXC_RELEASE_T = null;
function excRelease() {
  if (!EXC_SET || EXC_RELEASE_T) return;
  var tick = function () {
    EXC_RELEASE_T = null;
    if (WATCH || !EXC_SET) return;
    var last = watchLast;
    if (last) Process.enumerateThreads().forEach(function (th) { if (last.threads.indexOf(th.id) >= 0) { try { th.unsetHardwareWatchpoint(0); } catch (e) { WATCH_UNSET_ERR++; } } });
    if (Date.now() - WATCH_LATE_AT < 3000) { EXC_RELEASE_T = setTimeout(tick, 1000); return; }
    try { Process.setExceptionHandler(null); EXC_SET = false; } catch (e) { EXC_ERR = String(e.message || e); }
  };
  EXC_RELEASE_T = setTimeout(tick, 1000);
}
var EXC_ERR = null;
function watchReport() {
  var w = WATCH || watchLast; if (!w) return { error: '감시 기록이 없어요' };
  var now; try { now = w.read(); } catch (e) { now = null; }
  return { active: w === WATCH, why: w.why || null, excSet: EXC_SET, excErr: EXC_ERR, path: w.path, addr: w.addr.toString(), size: w.size, cond: w.cond, threads: w.threads.length, fails: w.fails,
    secs: Math.round(((w.t1 || Date.now()) - w.t0) / 100) / 10, total: w.total, dropped: w.dropped, before: w.before, now: now, errs: w.errs || 0, late: WATCH_LATE, unsetErrs: WATCH_UNSET_ERR,
    hits: Object.keys(w.hits).map(function (k) { return w.hits[k]; }).sort(function (x, y) { return y.count - x.count; }) };
}

// ---- 매치엔진 표 (DynamicME, E02~E03) ----
// simatch 매니저 싱글턴(정적 칸)과 그 안 표의 배치. 게임은 경기·선발 때 이 메모리 표를 그대로 읽는다 (E02 읽기 감시).
// engineDump는 읽기만 한다. 배치 근거: logs/메치엔진조정모드 E02 2절, E03.
var ENGINE_TABLES = {
  weights:  { g: 0x6374be0, cls: 'MATCH_WEIGHTS_PROVIDER' },        // +0x8/+0x10 int32 배열 (버전 × 선발 방식 4 × 요인 39)
  physics:  { g: 0x6428810, cls: 'PHYSICAL_CONSTRAINTS_MANAGER' },  // +0x8/+0x10 항목 포인터 배열 (새 버전부터)
  momentum: { g: 0x637b8b0, cls: 'MATCH_MOMENTUM_MANAGER' },        // +0x8/+0x10 8바이트 줄
  ratings:  { g: 0x64287f0, cls: 'MATCH_PLAYER_RATINGS_MANAGER' },  // +0x8/+0x10 0x88바이트 항목 (새 버전부터)
  styles:   { g: 0x6365628, cls: 'TACTIC_LOADER' },                 // +0x8/+0x10 전술 스타일 포인터 (tactics/styles.xml 순서, E09)
  xg:       { g: 0x64287d0, cls: 'simatchshared::STATS_MANAGER' }   // xG 모델 (expected_goals/models, E10)
};
// xG 모델 (E10): STATS_MANAGER +0x20 계수, +0x38 절편 = 모델 버전 항목 vector (0x20바이트: +0 버전 4바이트 [부·릴리스·주·해] 거꾸로, +8 줄 vector).
//   계수 줄 0x20바이트: +0 u8 슛 종류, +8 vector<f32> (계수 이름 abc 순서, 값 = JSON ÷ 1e7)
//   절편 줄 0x10바이트: +0 u8 슛 종류, +4 f32, +8 f32, +0xc f32 절편 (JSON ÷ 1e7)
// 경기 시뮬레이션 스레드가 슛마다 읽는다 (fm+0x4386fa0, E10 읽기 감시).
function xgVer(p) { return [p.add(3).readU8(), p.add(2).readU8(), p.add(1).readU8(), p.readU8()]; }   // [해, 릴리스, 주, 부] = 폴더 이름 순서
function xgModels(mgr) {
  var cv = engineVec(mgr.add(0x18)), iv = engineVec(mgr.add(0x30)), out = [], i, j;
  for (i = 0; i < cv.n; i += 0x20) {
    var e = cv.b.add(i), rows = engineVec(e), m = { ver: xgVer(e), coef: {}, icpt: {}, coefAt: {}, icptAt: {} };
    for (j = 0; j < rows.n; j += 0x20) { var r = rows.b.add(j), fv = engineVec(r), fl = []; for (var k = 0; k < fv.n; k += 4) fl.push(fv.b.add(k).readFloat()); m.coef[r.readU8()] = fl; m.coefAt[r.readU8()] = fv.b; }
    out.push(m);
  }
  for (i = 0; i < iv.n; i += 0x20) {
    var e2 = iv.b.add(i), v2 = xgVer(e2).join('.'), m2 = out.filter(function (x) { return x.ver.join('.') === v2; })[0], rows2 = engineVec(e2);
    if (!m2) { m2 = { ver: xgVer(e2), coef: {}, icpt: {}, coefAt: {}, icptAt: {} }; out.push(m2); }
    for (j = 0; j < rows2.n; j += 0x10) { var r2 = rows2.b.add(j); m2.icpt[r2.readU8()] = r2.add(0xc).readFloat(); m2.icptAt[r2.readU8()] = r2.add(0xc); }
  }
  return out;
}
// 전술 스타일 (E09): TACTIC_LOADER는 AI가 처음 전술을 쓸 때(세이브를 불러온 뒤 첫 진행일) 만들어지고 styles.xml을 읽는다. 그 전에는 '아직 없어요'.
// 스타일 S: +0x20 attribute_template, +0x38 tendency_template = vector<{u8 id, u8 min, u8 max}> (begin/end/cap), +0xb0 폴더 이름(글 핸들), +0xc8 4글자 코드.
// 게임은 하루 처리 때 이 표를 읽는다 (fm+0x47e77d0, E09 읽기 감시). 언어가 바뀌면 다시 읽는다 (fm+0x4b33dd0: +0x68 언어 비교 -> fm+0x1c25360 비우기 -> fm+0x1c229c0 읽기).
// 이 vector는 크기별 풀 할당자(G = [fm+0x63634e8])를 쓴다: 해제 때 (cap - begin)바이트가 풀 표(G+0x18, 크기 0..개수-1) 밖이면 ucrtbase free(ptr - G+0x30)를 부른다.
// 그래서 칸을 늘릴 때는 풀 표보다 큰 버퍼를 ucrtbase malloc으로 만들고 옛 버퍼는 그대로 둔다 (해제하지 않음, 수십 바이트). 게임이 나중에 해제해도 짝이 맞다.
var STYLE_POOL = 0x63634e8, STYLE_VECS = { attr: 0x20, tend: 0x38 };
var styleMalloc = null;
function styleStr(h) { if (h.isNull()) return null; var n = h.readU32(); return n > 0 && n < 256 ? h.add(4).readUtf8String(n) : null; }
function styleTriples(S, off) { var v = engineVec(S.add(off - 8)), o = []; for (var i = 0; i + 3 <= v.n; i += 3) o.push([v.b.add(i).readU8(), v.b.add(i + 1).readU8(), v.b.add(i + 2).readU8()]); return o; }
function styleVecSet(S, off, list) {
  var p = S.add(off), b = p.readPointer(), cap = p.add(0x10).readPointer().sub(b).toInt32(), need = list.length * 3, i, grown = false;
  for (i = 0; i < list.length; i++) {
    var t = list[i]; if (!t || t.length !== 3) throw new Error('스타일 칸은 [번호, 최소, 최대]');
    for (var k = 0; k < 3; k++) if (!(t[k] >= 0 && t[k] <= 255) || t[k] !== Math.floor(t[k])) throw new Error('스타일 값은 0~255 정수: ' + JSON.stringify(t));
  }
  if (need > cap) {
    var G = B.add(STYLE_POOL).readPointer(), cnt = G.add(0x20).readPointer().sub(G.add(0x18).readPointer()).toInt32() / 8;
    if (G.add(0x30).readU32() !== 0) throw new Error('스타일 할당자 머리 크기가 0이 아니에요 (다른 빌드?)');
    var C = Math.ceil(Math.max(need, G.add(0x34).readU8() ? cnt : 0, 48) / 3) * 3;
    if (!styleMalloc) styleMalloc = new NativeFunction(Process.getModuleByName('ucrtbase.dll').getExportByName('malloc'), 'pointer', ['size_t']);
    var nb = styleMalloc(C); if (nb.isNull()) throw new Error('메모리를 못 얻었어요');
    for (i = 0; i < C; i++) nb.add(i).writeU8(0);
    b = nb; grown = true; cap = C;
  }
  for (i = 0; i < list.length; i++) { b.add(i * 3).writeU8(list[i][0]); b.add(i * 3 + 1).writeU8(list[i][1]); b.add(i * 3 + 2).writeU8(list[i][2]); }
  if (grown) { p.writePointer(b); p.add(0x10).writePointer(b.add(cap)); }   // 새 버퍼를 다 채운 뒤 begin/cap/end를 바꾼다
  p.add(8).writePointer(b.add(need));
  return grown;
}
function engineMgr(name) {
  var t = ENGINE_TABLES[name]; if (!t) throw new Error('모르는 엔진 표: ' + name);
  var p = B.add(t.g).readPointer();
  if (p.isNull()) throw new Error(name + ' 매니저가 아직 없어요');
  var cn = className(p) || '';
  if (cn.indexOf(t.cls) < 0) throw new Error(name + ' 매니저 클래스가 달라요: ' + cn);
  return p;
}
function engineVec(p) { var b = p.add(8).readPointer(), e = p.add(0x10).readPointer(); return { b: b, e: e, n: e.sub(b).toInt32() }; }
function engineVer(p) { return [p.readU8(), p.add(1).readU8(), p.add(2).readU8(), p.add(3).readU8()]; }   // year, release, major, minor
function engineMapWalk(head, out) {   // MSVC std::map<i32,i32>: 노드 +0 왼쪽 +8 부모 +0x10 오른쪽 +0x19 isnil, 열쇠 +0x1c, 값 +0x20
  var root = head.add(8).readPointer(), guard = 0;
  (function walk(n) {
    if (n.isNull() || n.equals(head) || n.add(0x19).readU8() || ++guard > 4096) return;
    walk(n.readPointer()); out.push([n.add(0x1c).readU16(), n.add(0x20).readS32()]); walk(n.add(0x10).readPointer());
  })(root);
  return out;
}
function engineDump(name) {
  var p = engineMgr(name), v = engineVec(p), i, j, r = { table: name, mgr: p.toString(), vec: v.b.toString() };
  if (name === 'weights') {
    r.ints = []; for (i = 0; i < v.n; i += 4) r.ints.push(v.b.add(i).readS32());
  } else if (name === 'momentum') {
    r.rows = []; for (i = 0; i < v.n; i += 8) { var q = v.b.add(i); r.rows.push([q.readU8(), q.add(1).readU8(), q.add(2).readU8(), q.add(4).readS32()]); }
  } else if (name === 'physics') {
    r.entries = [];
    for (i = 0; i < v.n; i += 8) {
      var en = v.b.add(i).readPointer(), f = [], s = [];
      for (j = 0xc; j < 0x84; j += 4) f.push(en.add(j).readFloat());
      for (j = 0x84; j < 0x92; j += 2) s.push(en.add(j).readS16());
      r.entries.push({ addr: en.toString(), ver: engineVer(en.add(4)), f32: f, i16: s, delayCount: en.add(0xa0).readU32(), delays: engineMapWalk(en.add(0x98).readPointer(), []) });
    }
  } else if (name === 'ratings') {
    r.entries = [];
    for (i = 0; i < v.n; i += 0x88) {
      var e2 = v.b.add(i), rv = engineVec(e2.sub(8)), roles = [], exp = [];   // 항목 +0/+8 = 역할 계수 배열 begin/end
      for (j = 0; j < rv.n; j += 0x68) { var c = []; for (var k = 0; k < 0x68; k += 2) c.push(rv.b.add(j + k).readS16()); roles.push(c); }
      for (j = 0x28; j < 0x80; j += 4) exp.push(e2.add(j).readFloat());
      r.entries.push({ addr: e2.toString(), ver: engineVer(e2.add(0x84)), start: e2.add(0x80).readS32(), lookupCount: e2.add(0x20).readU32(), exp: exp, roles: roles });
    }
  } else if (name === 'styles') {
    r.styles = [];
    for (i = 0; i < v.n; i += 8) {
      var S = v.b.add(i).readPointer();
      r.styles.push({ addr: S.toString(), folder: styleStr(S.add(0xb0).readPointer()), code: fourcc(S.add(0xc8).readU32()),
        attr: styleTriples(S, STYLE_VECS.attr), tend: styleTriples(S, STYLE_VECS.tend) });
    }
    r.key = r.styles.map(function (s) { return s.addr; }).join(',');   // 바뀌면 게임이 스타일을 다시 읽은 것
  } else if (name === 'xg') {
    r.models = xgModels(p).map(function (m) { return { ver: m.ver, coef: m.coef, icpt: m.icpt }; });
  }
  return r;
}

// engineWrite: 이미 있는 칸에만 쓴다 (줄·역할 수가 다르면 거절, 할당 없음). 게임이 진행 중이면 거절 (경기 전 조정만, E01 5-1).
// spec 모양 = engineDump 결과의 일부:
//   weights  { entry, ints[156] }                      항목 entry(0 = 게임이 쓰는 새 버전)의 int 156개
//   physics  { entry, f32[30]?, i16[7]?, delays[[열쇠, 조각]]? }  지연은 map에 있는 열쇠만
//   momentum { rows[[사건, 구역, 좌우, 점수]] }         메모리에 있는 줄의 점수만 (없는 줄은 missing으로 돌려줌)
//   ratings  { entry, ver[4]?, start?, exp[22]?, roles[[52]]? }  ver로 게임이 고르는 항목을 바꿀 수 있다
//   styles   { styles: [{ folder, attr?[[번호, 최소, 최대]], tend?[...] }] }  스타일의 목록 전체를 이 내용으로 (칸이 늘면 버퍼를 새로 만듦, E09)
//   xg       { models: [{ ver[4], coef?{슛 종류: [f32...]}, icpt?{슛 종류: f32} }] }  있는 줄만, 계수 수가 같을 때만 (E10)
function engineWrite(name, spec, force) {
  if (!force && gameBusy() === true) return { error: '게임이 진행 중이라 쓰지 않았어요 (진행을 멈춘 뒤 다시)' };
  var p = engineMgr(name), v = engineVec(p), n = 0, i, j, missing = [];
  if (name === 'weights') {
    var per = 156 * 4, wb = v.b.add(spec.entry * per);
    if (spec.ints.length !== 156 || (spec.entry + 1) * per > v.n) return { error: 'weights 모양이 달라요' };
    for (i = 0; i < 156; i++) { wb.add(i * 4).writeS32(spec.ints[i]); n++; }
  } else if (name === 'physics') {
    if ((spec.entry + 1) * 8 > v.n) return { error: 'physics 항목이 없어요: ' + spec.entry };
    var en = v.b.add(spec.entry * 8).readPointer();
    if (spec.f32) { if (spec.f32.length !== 30) return { error: 'physics f32는 30개' }; for (i = 0; i < 30; i++) { en.add(0xc + i * 4).writeFloat(spec.f32[i]); n++; } }
    if (spec.i16) { if (spec.i16.length !== 7) return { error: 'physics i16은 7개' }; for (i = 0; i < 7; i++) { en.add(0x84 + i * 2).writeS16(spec.i16[i]); n++; } }
    if (spec.delays) {
      var head = en.add(0x98).readPointer(), nodes = {};
      (function walk(x, d) {
        if (x.isNull() || x.equals(head) || x.add(0x19).readU8() || d > 64) return;
        walk(x.readPointer(), d + 1); nodes[x.add(0x1c).readU16()] = x; walk(x.add(0x10).readPointer(), d + 1);
      })(head.add(8).readPointer(), 0);
      spec.delays.forEach(function (kv) { var x = nodes[kv[0]]; if (x) { x.add(0x20).writeS32(kv[1]); n++; } else missing.push(kv[0]); });
    }
  } else if (name === 'momentum') {
    var at = {};
    for (i = 0; i < v.n; i += 8) { var q = v.b.add(i); at[q.readU8() + ',' + q.add(1).readU8() + ',' + q.add(2).readU8()] = q; }
    spec.rows.forEach(function (r) { var q = at[r[0] + ',' + r[1] + ',' + r[2]]; if (q) { q.add(4).writeS32(r[3]); n++; } else missing.push(r); });
  } else if (name === 'ratings') {
    if ((spec.entry + 1) * 0x88 > v.n) return { error: 'ratings 항목이 없어요: ' + spec.entry };
    var e2 = v.b.add(spec.entry * 0x88), rv = engineVec(e2.sub(8));
    if (spec.roles) {
      if (spec.roles.length * 0x68 !== rv.n) return { error: 'ratings 역할 수가 달라요: 메모리 ' + (rv.n / 0x68) + ', 쓸 것 ' + spec.roles.length };
      for (i = 0; i < spec.roles.length; i++) { if (spec.roles[i].length !== 52) return { error: '역할 계수는 52개' }; }
      for (i = 0; i < spec.roles.length; i++) for (j = 0; j < 52; j++) { rv.b.add(i * 0x68 + j * 2).writeS16(spec.roles[i][j]); n++; }
    }
    if (spec.exp) { if (spec.exp.length !== 22) return { error: 'exp는 22개' }; for (i = 0; i < 22; i++) { e2.add(0x28 + i * 4).writeFloat(spec.exp[i]); n++; } }
    if (spec.start != null) { e2.add(0x80).writeS32(spec.start); n++; }
    if (spec.ver) { for (i = 0; i < 4; i++) e2.add(0x84 + i).writeU8(spec.ver[i]); n++; }
  } else if (name === 'styles') {
    var byFolder = {}, grown = 0;
    for (i = 0; i < v.n; i += 8) { var S = v.b.add(i).readPointer(), f = styleStr(S.add(0xb0).readPointer()); if (f) byFolder[f] = S; }
    for (i = 0; i < (spec.styles || []).length; i++) {
      var st = spec.styles[i], S2 = byFolder[st.folder];
      if (!S2) { missing.push(st.folder); continue; }
      try {
        for (var key in STYLE_VECS) if (st[key]) { if (styleVecSet(S2, STYLE_VECS[key], st[key])) grown++; n += st[key].length; }
      } catch (e) { return { error: st.folder + ': ' + e.message, written: n }; }
    }
    return { ok: true, table: name, written: n, missing: missing, grown: grown };
  } else if (name === 'xg') {
    var models = xgModels(p);
    (spec.models || []).forEach(function (sm) {
      var m = models.filter(function (x) { return x.ver.join('.') === sm.ver.join('.'); })[0];
      if (!m) { missing.push(sm.ver.join('.')); return; }
      Object.keys(sm.coef || {}).forEach(function (t) {
        var at = m.coefAt[t], vals = sm.coef[t];
        if (!at || vals.length !== m.coef[t].length) { missing.push(sm.ver.join('.') + ' 계수 ' + t); return; }
        for (var q = 0; q < vals.length; q++) { at.add(q * 4).writeFloat(vals[q]); n++; }
      });
      Object.keys(sm.icpt || {}).forEach(function (t) {
        if (!m.icptAt[t]) { missing.push(sm.ver.join('.') + ' 절편 ' + t); return; }
        m.icptAt[t].writeFloat(sm.icpt[t]); n++;
      });
    });
  } else return { error: '모르는 표: ' + name };
  return { ok: true, table: name, written: n, missing: missing };
}

M24GA.engineDump = engineDump;
M24GA.engineWrite = engineWrite;

// ---- 함수 등록부 (M22, hook.function): core/functions.json의 함수에 코어가 Interceptor를 하나씩 걸고 modhost.js가 모드들에 나눠 준다 ----
var M24_FUNCS = { functions: {} };   // 로더가 core/functions.json을 넣는다
var FUNC_STATE = {};                 // 이름 -> { ok, error, addr } (서명 확인 결과, 한 번만)
var HOOK_LISTENERS = {};             // 이름 -> Interceptor listener
function funcInfo(name) { return M24_FUNCS.functions[name] || null; }
function funcNames(prefix) { return Object.keys(M24_FUNCS.functions).filter(function (n) { return !prefix || n.indexOf(prefix) === 0; }); }
function funcCheck(name) {
  if (FUNC_STATE[name]) return FUNC_STATE[name];
  var f = funcInfo(name), st;
  if (!f) st = { ok: false, error: "모르는 함수 '" + name + "'" };
  else {
    var addr = B.add(parseInt(f.rva, 16));
    st = { ok: true, addr: addr };
    if (f.sig) {
      try {
        var u = new Uint8Array(addr.add(parseInt(f.sig.off, 16)).readByteArray(f.sig.hex.length / 2)), hex = '';
        for (var i = 0; i < u.length; i++) hex += ('0' + u[i].toString(16)).slice(-2);
        if (hex !== f.sig.hex.toLowerCase()) st = { ok: false, error: name + '의 서명이 이 게임 빌드와 달라요 (다른 빌드이거나 다른 도구가 바꿨어요)' };
      } catch (e) { st = { ok: false, error: name + '의 서명을 읽지 못했어요' }; }
    }
  }
  FUNC_STATE[name] = st;
  return st;
}
var ARG_CONV = {
  ptr: function (p) { return p; }, i32: function (p) { return p.toInt32(); }, u32: function (p) { return p.toInt32() >>> 0; },
  i64: function (p) { return p.toString(); }, bool: function (p) { return (p.toInt32() & 0xff) !== 0; }
};
function convRet(t, r) { return ARG_CONV[t] ? ARG_CONV[t](r) : r; }
M24GA.funcInfo = funcInfo;
M24GA.hookInstall = function (name) {
  var f = funcInfo(name), st = funcCheck(name);
  if (!st.ok) return st;
  if (HOOK_LISTENERS[name]) return { ok: true };
  var types = f.args || [], modify = f.hook === 'modify';
  try {
    HOOK_LISTENERS[name] = Interceptor.attach(st.addr, {
      onEnter: function (args) {
        var list = M24GA.hooks[name]; if (!list || !list.length) return;
        var ra = this.returnAddress, ev = { name: name, args: [], tid: this.threadId, data: {}, ret: undefined,
          caller: inModule(ra) ? 'fm+0x' + ra.sub(B).toString(16) : ra.toString(),
          raw: function (i) { return args[i]; } };
        for (var i = 0; i < types.length; i++) { try { ev.args.push(ARG_CONV[types[i]] ? ARG_CONV[types[i]](args[i]) : args[i]); } catch (e) { ev.args.push(null); } }
        ev.setArg = modify ? function (i, v) { args[i] = (typeof v === 'object' && v && v.add) ? v : ptr(v); } : function () { throw new Error(name + '은 보기만 되는 함수예요 (hook: observe)'); };
        ev.setRet = function () { throw new Error('setRet은 after에서만 써요'); };
        this.m24ev = ev;
        m24gaHookCall(name, 'before', ev);
      },
      onLeave: function (retval) {
        var ev = this.m24ev; if (!ev) return;
        ev.ret = f.ret && f.ret !== 'void' ? convRet(f.ret, retval) : undefined;
        ev.setArg = function () { throw new Error('setArg는 before에서만 써요'); };
        ev.setRet = modify ? function (v) { retval.replace((typeof v === 'object' && v && v.add) ? v : ptr(v)); ev.ret = v; } : function () { throw new Error(name + '은 보기만 되는 함수예요 (hook: observe)'); };
        m24gaHookCall(name, 'after', ev);
      }
    });
  } catch (e) { return { ok: false, error: name + '에 걸지 못했어요: ' + (e.message || e) }; }
  send(name + ' 끼어들기 걸음');
  return { ok: true };
};
M24GA.hookRelease = function (name) {
  var l = HOOK_LISTENERS[name]; if (!l) return;
  try { l.detach(); } catch (e) {}
  delete HOOK_LISTENERS[name];
  send(name + ' 끼어들기 풂');
};

// ---- 게이트 (코어 0.15.0, 몸값모드 V03, 기능 hook.gate) ----
// "함수 X 안에서만, 클래스 Z의 가상 함수 칸 Y가 null(또는 false)을 돌려준다". core/functions.json의 gates에 등록한 것만 쓴다.
// 범위는 스레드마다 센다 (Windows TLS): 다른 스레드가 같은 칸을 부르면 원래 답을 받는다 (전역 깃발로 하면 다른 곳이 튕겼다, V03 실험).
// 범위 함수에는 CModule Interceptor(빠름), 칸은 vtable 한 칸만 바꾼다 (그 클래스 객체에만 영향). 켜기 전에 범위 함수 서명·칸의 지금 값·원래 함수 바이트를 모두 확인한다.
var GATES = {};   // 이름 -> { cm, lis, slotAddr, impl, stats, on, users }
var GATE_LINK = {};   // 게이트 함수 주소 -> { prev, impl, live }: 칸 사슬. 풀린 게이트도 남는다 (메모리에 남아 아래로 넘기기만 함)
function gateBelow(p) { var l; while ((l = GATE_LINK[p.toString()]) && !l.live) p = l.prev; return p; }   // 풀린 게이트를 건너뛴 실제 아래
var K32 = null;
// M43: 게이트로 바꾼 칸을 게임 프로세스의 환경 변수(M24GA_GATE_SLOTS = "칸=게이트;...")에 적어 둔다.
// 스크립트 메모리는 내려가면 사라지지만 환경 변수는 프로세스에 남는다. 다음 스크립트는 칸 값이 이 기록과 똑같을 때만
// "이전 M24GA가 정리 못 한 흔적"으로 보고 되돌린다 (다른 도구가 건 칸은 기록에 없으니 건드리지 않는다).
var GATE_ENV = 'M24GA_GATE_SLOTS', ENVF = null;
function envFns() {
  if (!ENVF) {
    var k = Process.getModuleByName('kernel32.dll');
    ENVF = { get: new NativeFunction(k.getExportByName('GetEnvironmentVariableW'), 'uint32', ['pointer', 'pointer', 'uint32']),
      set: new NativeFunction(k.getExportByName('SetEnvironmentVariableW'), 'int', ['pointer', 'pointer']) };
  }
  return ENVF;
}
function gateMarks() {
  try {
    var f = envFns(), nm = Memory.allocUtf16String(GATE_ENV), buf = Memory.alloc(8192), n = f.get(nm, buf, 4096);
    var out = {}; if (!n || n >= 4096) return out;
    buf.readUtf16String(n).split(';').forEach(function (kv) { var p = kv.split('='); if (p.length === 2) out[p[0]] = p[1]; });
    return out;
  } catch (e) { return {}; }
}
function gateMarkSet(slot, gate) {   // gate = null이면 지운다
  try {
    var m = gateMarks(), k = slot.toString();
    if (gate) m[k] = gate.toString(); else delete m[k];
    var s = Object.keys(m).map(function (x) { return x + '=' + m[x]; }).join(';');
    envFns().set(Memory.allocUtf16String(GATE_ENV), s ? Memory.allocUtf16String(s) : ptr(0));
  } catch (e) {}
}
function gateStale(slot, cur) { return gateMarks()[slot.toString()] === cur.toString(); }
function gateInfo(name) { return (M24_FUNCS.gates || {})[name] || null; }
function hexAt(addr, n) { var u = new Uint8Array(addr.readByteArray(n)), h = ''; for (var i = 0; i < u.length; i++) h += ('0' + u[i].toString(16)).slice(-2); return h; }
function gateInstall(name) {
  if (GATES[name]) return { ok: true };
  var g = gateInfo(name);
  if (!g) return { ok: false, error: "모르는 게이트 '" + name + "' (docs/FUNCTIONS.md)" };
  try {
    var scope = B.add(parseInt(g.scope.rva, 16)), slot = B.add(parseInt(g.vtable, 16) + parseInt(g.slot, 16)), impl = B.add(parseInt(g.impl.rva, 16));
    if (hexAt(scope.add(parseInt(g.scope.sig.off, 16)), g.scope.sig.hex.length / 2) !== g.scope.sig.hex) return { ok: false, error: name + ': 범위 함수 서명이 이 게임 빌드와 달라요' };
    if (hexAt(impl, g.impl.hex.length / 2) !== g.impl.hex) return { ok: false, error: name + ': 원래 함수 바이트가 이 게임 빌드와 달라요' };
    // 같은 칸에 게이트를 여러 개 걸 수 있다 (0.16.0, 몸값모드 V05): 칸이 원래 함수이거나 우리 게이트(같은 원래 함수)면 그 위에 잇는다
    var cur = slot.readPointer(), link = GATE_LINK[cur.toString()];
    if (link && !link.live) {   // 맨 위가 풀린 게이트면 실제 아래로 칸을 정리한 뒤 잇는다
      cur = gateBelow(cur);
      Memory.protect(slot, 8, 'rw-'); slot.writePointer(cur); Memory.protect(slot, 8, 'r--');
      link = GATE_LINK[cur.toString()];
    }
    if (!cur.equals(impl) && !link && !inModule(cur) && gateStale(slot, cur)) {
      // M43: 이전 M24GA 스크립트가 정리하지 못하고 내려가서(로더 프로세스가 죽음 등) 칸이 사라진 게이트 코드를 가리킨 채 남은 경우.
      // 그대로 두면 게임이 그 칸을 부를 때 튕긴다. 원래 함수(impl, 위에서 바이트 확인함)로 되돌린 뒤 정상적으로 잇는다.
      Memory.protect(slot, 8, 'rw-'); slot.writePointer(impl); Memory.protect(slot, 8, 'r--');
      send(name + ': 이전 스크립트가 남긴 vtable 칸을 원래 함수로 되돌렸어요 (' + cur + ')');
      cur = impl;
    }
    if (!(cur.equals(impl) || (link && link.impl.equals(impl)))) return { ok: false, error: name + ': vtable 칸이 원래 함수가 아니에요 (다른 도구가 바꿨을 수 있어요)' };
    if (!K32) {
      var k = Process.getModuleByName('kernel32.dll');
      K32 = { TlsAlloc: new NativeFunction(k.getExportByName('TlsAlloc'), 'uint32', []), TlsGetValue: k.getExportByName('TlsGetValue'), TlsSetValue: k.getExportByName('TlsSetValue') };
    }
    var idx = Memory.alloc(8), st = Memory.alloc(64), en = Memory.alloc(8);
    idx.writeU32(K32.TlsAlloc()); en.writeU32(1);
    var ans = g.answer === 'false' ? '(void *)0' : '(void *)0';
    var cm = new CModule([
      '#include <gum/guminterceptor.h>',
      'extern void * TlsGetValue(unsigned int i);',
      'extern int TlsSetValue(unsigned int i, void * v);',
      'extern volatile unsigned int tlsIndex;',
      'extern volatile int enabled;',
      'extern volatile long long stats[4];',
      'extern void * orig(void * self);',
      'void onEnter(GumInvocationContext * ic) { long long d = (long long) TlsGetValue(tlsIndex); TlsSetValue(tlsIndex, (void *) (d + 1)); stats[0]++; }',
      'void onLeave(GumInvocationContext * ic) { long long d = (long long) TlsGetValue(tlsIndex); if (d > 0) TlsSetValue(tlsIndex, (void *) (d - 1)); }',
      'void * gate(void * self) { if (TlsGetValue(tlsIndex)) { stats[1]++; if (enabled) { stats[2]++; return ' + ans + '; } } return orig(self); }'
    ].join('\n'), { TlsGetValue: K32.TlsGetValue, TlsSetValue: K32.TlsSetValue, tlsIndex: idx, enabled: en, stats: st, orig: cur });
    var lis = Interceptor.attach(scope, cm);
    Memory.protect(slot, 8, 'rw-'); slot.writePointer(cm.gate); Memory.protect(slot, 8, 'r--');
    gateMarkSet(slot, cm.gate);   // M43: 칸 = 이 게이트라고 프로세스에 적어 둔다 (스크립트가 정리 못 하고 내려가도 다음에 고칠 수 있게)
    GATES[name] ={ cm: cm, lis: lis, slot: slot, impl: impl, prev: cur, st: st, en: en, idx: idx };
    GATE_LINK[cm.gate.toString()] = { prev: cur, impl: impl, live: true };
    send(name + ' 게이트 걸음');
    return { ok: true };
  } catch (e) { return { ok: false, error: name + ' 게이트를 걸지 못했어요: ' + (e.message || e) }; }
}
function gateRelease(name) {
  var x = GATES[name]; if (!x) return;
  try { x.en.writeU32(0); } catch (e) {}   // 먼저 끈다: 칸 사슬 가운데에 남아도 그냥 아래로 넘긴다
  // 맨 위면 바로 아래(원래 함수 또는 먼저 건 게이트)로 되돌린다. 위에 다른 게이트가 있으면 사슬에 남아 넘기기만 한다
  var lk = GATE_LINK[x.cm.gate.toString()]; if (lk) lk.live = false;
  try { if (x.slot.readPointer().equals(x.cm.gate)) { Memory.protect(x.slot, 8, 'rw-'); x.slot.writePointer(gateBelow(x.prev)); Memory.protect(x.slot, 8, 'r--'); } } catch (e) {}
  try { var now = x.slot.readPointer(); if (GATE_LINK[now.toString()] && GATE_LINK[now.toString()].live) gateMarkSet(x.slot, now); else gateMarkSet(x.slot, null); } catch (e) {}   // M43 기록도 맞춘다
  try { x.lis.detach(); } catch (e) {}
  delete GATES[name];   // CModule(x.cm)은 지우지 않는다: 그 순간 칸을 부르던 다른 스레드가 있을 수 있고, 사슬에 남을 수도 있어서 코드가 메모리에 남아 있게 둔다
  send(name + ' 게이트 풂');
}
function gateStats(name) {
  var x = GATES[name]; if (!x) return null;
  return { scope: Number(x.st.readS64()), inScope: Number(x.st.add(8).readS64()), answered: Number(x.st.add(16).readS64()), on: x.en.readU32() === 1 };
}
M24GA.gateInstall = gateInstall;
M24GA.gateRelease = gateRelease;
M24GA.gateStats = gateStats;
M24GA.gateSet = function (name, on) { var x = GATES[name]; if (x) x.en.writeU32(on ? 1 : 0); };

// ---- 배율 표 (코어 0.17.0, 몸값모드 V06, 기능 hook.scale) ----
// 등록부에서 "scale"이 있는 함수(예: player.value)의 반환값(int)에 객체별 배율을 곱한다. 열쇠 = 인자 scale.key(예: 선수 객체).
// 하루 수만 번 불리는 함수라 JS 콜백 대신 CModule + 네이티브 해시표(열린 주소, 2^18칸)로 한다. 배율이 없거나 1이면 그대로, 반환이 0 이하면 그대로.
// 결과는 등록부의 min~max(게임 상한)로 자른다. 표는 JS가 CModule 함수(tset/tclear)로 쓰고 게임 스레드가 읽는다 (열쇠를 마지막에 써서 반쯤 쓴 칸을 안 읽게).
// 함수 하나에 표 하나, 한 모드만 쓴다 (둘째 모드는 오류).
var SCALES = {};   // 함수 이름 -> { cm, lis, st, en, owner, tset, tclear, n }
var SCALE_CAP_BITS = 18;
function scaleInstall(name, owner) {
  if (SCALES[name]) return SCALES[name].owner === owner ? { ok: true } : { ok: false, error: name + ' 배율 표는 다른 모드(' + SCALES[name].owner + ')가 쓰고 있어요' };
  var f = funcInfo(name), st = funcCheck(name);
  if (!st.ok) return st;
  if (!f.scale || f.ret !== 'i32') return { ok: false, error: name + '은 배율을 곱할 수 있게 등록된 함수가 아니에요' };
  try {
    var cap = 1 << SCALE_CAP_BITS, tbl = Memory.alloc(cap * 16), stats = Memory.alloc(32), en = Memory.alloc(8), lim = Memory.alloc(8);
    en.writeU32(1); lim.writeS32(f.scale.min | 0); lim.add(4).writeS32(f.scale.max | 0);
    var cm = new CModule([
      '#include <gum/guminterceptor.h>',
      'typedef struct { unsigned long long k; float f; unsigned int pad; } E;',
      'extern E tbl[];',
      'extern volatile long long stats[4];',
      'extern volatile int enabled;',
      'extern volatile int lim[2];',
      '#define CAP ' + cap,
      '#define SHIFT ' + (64 - SCALE_CAP_BITS),
      'static unsigned int slot(unsigned long long k) { return (unsigned int) (((k >> 4) * 0x9E3779B97F4A7C15ULL) >> SHIFT); }',
      'static float find(unsigned long long k) { unsigned int i = slot(k); for (int n = 0; n < 128; n++) { unsigned long long kk = tbl[i].k; if (kk == k) return tbl[i].f; if (!kk) return 0; i = (i + 1) & (CAP - 1); } return 0; }',
      'int tset(unsigned long long k, float f) { unsigned int i = slot(k); for (int n = 0; n < 128; n++) { if (tbl[i].k == k) { tbl[i].f = f; return 1; } if (!tbl[i].k) { tbl[i].f = f; tbl[i].k = k; return 2; } i = (i + 1) & (CAP - 1); } return 0; }',
      'void tclear(void) { for (int i = 0; i < CAP; i++) { tbl[i].f = 1.0f; } }',
      'float tget(unsigned long long k) { float f = find(k); return f > 0.0f ? f : 1.0f; }',
      'void onEnter(GumInvocationContext * ic) { void ** d = GUM_IC_GET_INVOCATION_DATA(ic, void *); *d = gum_invocation_context_get_nth_argument(ic, ' + (f.scale.key | 0) + '); stats[0]++; }',
      'void onLeave(GumInvocationContext * ic) {',
      '  if (!enabled) return;',
      '  void ** d = GUM_IC_GET_INVOCATION_DATA(ic, void *);',
      '  float m = find((unsigned long long) *d);',
      '  if (m <= 0.0f || m == 1.0f) return;',
      '  int r = (int) (long long) gum_invocation_context_get_return_value(ic);',
      '  if (r <= 0) return;',
      '  double v = (double) r * (double) m;',
      '  if (v > (double) lim[1]) v = (double) lim[1];',
      '  if (v < (double) lim[0]) v = (double) lim[0];',
      '  stats[1]++;',
      '  gum_invocation_context_replace_return_value(ic, (gpointer) (long long) (int) v);',
      '}'
    ].join('\n'), { tbl: tbl, stats: stats, enabled: en, lim: lim });
    var lis = Interceptor.attach(st.addr, cm);
    SCALES[name] = { cm: cm, lis: lis, st: stats, en: en, owner: owner, n: 0, tbl: tbl,
      tset: new NativeFunction(cm.tset, 'int', ['uint64', 'float']), tclear: new NativeFunction(cm.tclear, 'void', []),
      tget: new NativeFunction(cm.tget, 'float', ['uint64']) };
    send(name + ' 배율 표 걸음 (' + owner + ')');
    return { ok: true };
  } catch (e) { return { ok: false, error: name + ' 배율 표를 걸지 못했어요: ' + (e.message || e) }; }
}
function scaleRelease(name) {
  var x = SCALES[name]; if (!x) return;
  try { x.en.writeU32(0); } catch (e) {}
  try { x.lis.detach(); } catch (e) {}
  delete SCALES[name];   // CModule·표 메모리는 남긴다 (그 순간 onLeave 안에 있는 스레드가 있을 수 있어서)
  send(name + ' 배율 표 풂');
}
function scaleSet(name, obj, factor) {
  var x = SCALES[name]; if (!x) return false;
  if (!obj || obj.isNull()) return false;
  var f = Number(factor); if (!isFinite(f) || f <= 0) f = 1;
  var r = x.tset(uint64(obj.toString()), f);
  if (r === 2) x.n++;
  return r !== 0;
}
function scaleGet(name, obj) {   // 표에 있는 배율 (없으면 1)
  var x = SCALES[name]; if (!x || !obj || obj.isNull()) return 1;
  return x.tget(uint64(obj.toString()));
}
function scaleStats(name) {
  var x = SCALES[name]; if (!x) return null;
  return { calls: Number(x.st.readS64()), changed: Number(x.st.add(8).readS64()), entries: x.n, on: x.en.readU32() === 1 };
}
M24GA.scaleInstall = scaleInstall;
M24GA.scaleRelease = scaleRelease;
M24GA.scaleSet = scaleSet;
M24GA.scaleGet = scaleGet;
M24GA.scaleClear = function (name) { var x = SCALES[name]; if (x) x.tclear(); };
M24GA.scaleEnable = function (name, on) { var x = SCALES[name]; if (x) x.en.writeU32(on ? 1 : 0); };
M24GA.scaleStats = scaleStats;

// ---- 대회·상 정보 (코어 0.20.0, 기능 read.award, 몸값모드 V14) ----
// 번호(객체 +0x8) -> 이름·나라·대륙. 번호는 세이브 기록(pylib m24awards: 상 번호, 대회 번호)과 같다. 표는 세이브를 불러온 뒤 사람·구단 표와 함께 만든다.
// 이름 칸: db::COMP +0x40 정식 / +0x48 짧은, db::AWARD +0x30 / +0x38 (포인터 -> {u32 길이, UTF-8}).
function strDirect(p) { try { var h = p.readPointer(); if (h.isNull()) return ''; var n = h.readU32(); return (n > 0 && n < 200) ? h.add(4).readUtf8String(n) : ''; } catch (e) { return ''; } }
function vtIs(o, vt) { try { return o.readPointer().equals(vt); } catch (e) { return false; } }
function ptrIdx(o, vt) { try { var q = o.readPointer(); return (!q.isNull() && vtIs(q, vt)) ? q.add(8).readU32() : null; } catch (e) { return null; } }
function refName(o, cls) {
  try { var q = o.readPointer(); if (q.isNull()) return null; var r = rttiInfo(q); if (!r || r.name !== cls) return null; return strDirect(q.add(0x40)) || strDirect(q.add(0x30)) || null; } catch (e) { return null; }
}
function compInfo(idx) {
  var o = comps[idx >>> 0]; if (!o || !vtIs(o, COMP_VT) || o.add(8).readU32() !== (idx >>> 0)) return null;
  return { idx: idx >>> 0, uid: o.add(0xc).readU32(), name: strDirect(o.add(0x40)), short: strDirect(o.add(0x48)),
    nation: refName(o.add(0x60), 'db::NATION'), continent: refName(o.add(0x58), 'db::CONTINENT') };
}
function awardInfo(idx) {
  var o = awards[idx >>> 0]; if (!o || !vtIs(o, AWARD_VT) || o.add(8).readU32() !== (idx >>> 0)) return null;
  return { idx: idx >>> 0, name: strDirect(o.add(0x30)), short: strDirect(o.add(0x38)), comp: ptrIdx(o.add(0x58), COMP_VT),
    nation: refName(o.add(0x60), 'db::NATION'), continent: refName(o.add(0x50), 'db::CONTINENT') };
}
function compIds() { return Object.keys(comps).map(Number); }
// 대회 +0xa8 -> 가장 최근에 끝난 시즌 결과 (세이브 comp_history에 아직 보관 안 된 것, 몸값모드 V16):
//   +0x0 대회(자기 자신), +0x8 우승 팀, +0x10 준우승, +0x18 3위 (db::TEAM, +0x8 = 팀 번호), +0x58 u16 시즌 시작 해, +0x5a 끝 해.
//   2034/35 챔스(639) 우승 1320 바르셀로나 / 준우승 515, 라리가(51) 1320 / 1335 / 1361로 확인.
function compLatest(idx) {
  var o = comps[idx >>> 0]; if (!o || !vtIs(o, COMP_VT)) return null;
  try {
    var e = o.add(0xa8).readPointer(); if (e.isNull() || !e.readPointer().equals(o)) return null;
    var team = function (k) { var q = e.add(k).readPointer(); return (!q.isNull() && rttiInfo(q) && rttiInfo(q).name === 'db::TEAM') ? q.add(8).readU32() : null; };
    var start = e.add(0x58).readU16(), end = e.add(0x5a).readU16();
    if (start < 1900 || start > 2300 || end < start || end > start + 1) return null;
    return { comp: idx >>> 0, start: start, end: end, winner: team(0x8), runnerUp: team(0x10), third: team(0x18) };
  } catch (e2) { return null; }
}
function awardIds() { return Object.keys(awards).map(Number); }

// ---- 선수 가치 읽기 (코어 0.17.0, 기능 read.player.value) ----
// 게임의 가치 함수(player.value)를 이유 기록기와 함께 부른다: { value, reasons: [{code, a, b}], club } (내부 돈 단위, 원화 = ×1664.7).
// club = 평가하는 구단 객체(없으면 구단 없이 = 요구 금액 계산과 같음). 게이트·배율 표가 걸려 있으면 그것까지 들어간 값 (게임이 보는 값).
// 게임이 진행 중이면(CONTINUE_MANAGER 바쁨) 부르지 않는다. 타이머(api.after/every)에서 부를 것: Interceptor 콜백(frame, api.hook) 안에서
// 부르면 Frida가 안쪽 Interceptor(게이트·배율)를 건너뛰어 다른 값이 나온다 (몸값모드 V03).
var PV = null;
function playerValue(p, club) {
  if (!p) return null;
  var st = funcCheck('player.value'); if (!st.ok) return { error: st.error };
  if (gameBusy()) return { error: '게임이 진행 중이에요. 멈춘 뒤에 읽으세요', busy: true };
  if (!PV) {
    PV = { fn: new NativeFunction(st.addr, 'int', ['pointer', 'pointer', 'int', 'uint32', 'pointer', 'pointer']), vec: Memory.alloc(24), buf: Memory.alloc(12 * 256) };
  }
  PV.vec.writePointer(PV.buf); PV.vec.add(8).writePointer(PV.buf); PV.vec.add(16).writePointer(PV.buf.add(12 * 256));   // 넉넉한 버퍼: 게임이 다시 할당하지 않게
  var v;
  try { v = PV.fn(p, club || ptr(0), -1, 0x20, PV.vec, ptr(0)); } catch (e) { return { error: '가치 계산을 부르지 못했어요: ' + (e.message || e) }; }
  var end = PV.vec.add(8).readPointer(), out = [];
  if (!PV.vec.readPointer().equals(PV.buf)) return { value: v, reasons: null, club: club ? club.toString() : null };   // 다시 할당됐으면 이유는 버림 (게임 힙)
  for (var a = PV.buf; a.compare(end) < 0 && out.length < 256; a = a.add(12)) out.push({ code: a.readU32(), a: a.add(4).readS32(), b: a.add(8).readS32() });
  return { value: v, reasons: out, club: club ? club.toString() : null };
}

// ---- watch-call (M22, 개발 도구: CLI가 rpc로 부른다) ----
// 함수 하나를 잠깐 지켜보며 앞 4개 인자의 정체(RTTI 클래스·정수), 반환값, 부른 곳을 모은다. 인자 뜻을 모르는 함수를 등록할 때 쓴다.
// max번 또는 secs초 뒤 스스로 푼다. 등록부 이름 또는 fm+0x... 주소 (주소는 함수 시작이어야 한다).
var WCALL = null, wcallLast = null;
function argDesc(p) {
  try {
    if (p.isNull()) return '0';
    var r = (p.compare(ptr('0x10000')) > 0 && p.compare(ptr('0x800000000000')) < 0 && !inModule(p)) ? rttiInfo(p) : null;
    if (r) return r.name + (r.off ? '@+0x' + r.off.toString(16) : '');
    if (inModule(p)) return 'fm+0x' + p.sub(B).toString(16);
    if (p.compare(ptr('0x100000000')) < 0) {   // M37: 4글자 코드처럼 보이는 정수는 글자로 ('CONT') -> 이벤트 종류별로 세어진다
      var u = p.toUInt32(), cs = '', okc = u > 0x20202020;
      for (var ci = 3; ci >= 0 && okc; ci--) { var ch = (u >>> (8 * ci)) & 0xff; if (ch < 32 || ch > 126) okc = false; else cs += String.fromCharCode(ch); }
      if (okc && /[A-Za-z]{2}/.test(cs)) return "'" + cs + "'";
    }
    var v = p.toInt32(); return (p.compare(ptr('0x100000000')) < 0) ? String(v) : p.toString();
  } catch (e) { return p.toString(); }
}
function wcallStart(target, secs, max) {
  if (WCALL) return { error: '이미 지켜보는 중이에요 (watch-call stop)' };
  var addr, name = target, m;
  if ((m = /^fm\+0x([0-9a-f]+)$/i.exec(target))) addr = B.add(parseInt(m[1], 16));
  else { var st = funcCheck(target); if (!st.ok) return { error: st.error }; addr = st.addr; }
  var w = { name: name, addr: addr, t0: Date.now(), max: max || 300, total: 0, callers: {}, samples: [], argKinds: [{}, {}, {}, {}], retKinds: {} };
  try {
    w.l = Interceptor.attach(addr, {
      onEnter: function (args) {
        if (WCALL !== w) return;
        var ra = this.returnAddress, c = inModule(ra) ? 'fm+0x' + ra.sub(B).toString(16) : ra.toString(), a = [];
        for (var i = 0; i < 4; i++) { var d = argDesc(args[i]); a.push(d); var k = /^[\d-]+$/.test(d) ? '(정수)' : d.replace(/^0x[0-9a-f]+$/, '(주소)'); w.argKinds[i][k] = (w.argKinds[i][k] || 0) + 1; }
        w.callers[c] = (w.callers[c] || 0) + 1;
        this.wcs = (w.samples.length < 12) ? { caller: c, args: a, tid: this.threadId } : null;
        w.total++;
      },
      onLeave: function (retval) {
        if (WCALL !== w) return;
        var d = argDesc(retval), k = /^[\d-]+$/.test(d) ? '(정수)' : d.replace(/^0x[0-9a-f]+$/, '(주소)');
        w.retKinds[k] = (w.retKinds[k] || 0) + 1;
        if (this.wcs) { this.wcs.ret = d; w.samples.push(this.wcs); }
        if (w.total >= w.max) setTimeout(function () { wcallStop('최대 횟수'); }, 0);
      }
    });
  } catch (e) { return { error: '걸지 못했어요: ' + (e.message || e) }; }
  WCALL = w;
  w.timer = setTimeout(function () { wcallStop('시간 끝'); }, Math.min(secs || 30, 600) * 1000);
  return wcallReport();
}
function wcallStop(why) {
  var w = WCALL; if (!w) return;
  WCALL = null; w.why = why; w.t1 = Date.now();
  try { clearTimeout(w.timer); } catch (e) {}
  try { w.l.detach(); } catch (e) {}
  wcallLast = w;
}
function wcallReport() {
  var w = WCALL || wcallLast; if (!w) return { error: '기록이 없어요' };
  function top(o) { return Object.keys(o).map(function (k) { return [k, o[k]]; }).sort(function (a, b) { return b[1] - a[1]; }).slice(0, 8); }
  return { active: w === WCALL, why: w.why || null, name: w.name, addr: 'fm+0x' + w.addr.sub(B).toString(16), secs: Math.round(((w.t1 || Date.now()) - w.t0) / 100) / 10,
    total: w.total, callers: top(w.callers), args: w.argKinds.map(top), ret: top(w.retKinds), samples: w.samples };
}

// ---- 필드 등록부 (M20, read.field / write.field): core/fields.json의 칸을 이름으로 읽고 쓴다 ----
// 모드마다 전용 읽기·쓰기 함수를 만들지 않고, 확인한 칸을 fields.json에 한 줄 더하면 모든 모드가 getField/api.setField로 쓴다.
// 객체 종류는 RTTI 클래스 이름으로 확인한다 (vtable 주소를 필드마다 적지 않음). 안쪽 위치(사람 데이터 객체 = 선수 +0x278)를 넘겨도 맨 앞으로 맞춘다.
var M24_FIELDS = { kinds: {}, fields: {} };   // 로더가 core/fields.json을 넣는다
var FIELD_SIZE = { i8: 1, u8: 1, i16: 2, u16: 2, i32: 4, u32: 4, f32: 4, f64: 8, ptr: 8, date: 4, str: 8, strref: 8 };
function fieldInfo(name) { return M24_FIELDS.fields[name] || null; }
function fieldNames(prefix) { return Object.keys(M24_FIELDS.fields).filter(function (n) { return !prefix || n.indexOf(prefix) === 0; }); }
function kindMatches(r, kind) { return !!r && !!kind && (r.name === kind.cls || r.bases.indexOf(kind.cls) >= 0); }
// 필드가 있는 주소 (객체가 그 종류가 아니거나, 이 하위 클래스에는 없는 칸이거나, 따라갈 포인터가 비었으면 null)
function fieldAddr(obj, f) {
  var r = rttiInfo(obj), kind = M24_FIELDS.kinds[f.kind];
  if (!kindMatches(r, kind)) return null;
  var off = f.off;
  if (f.alt && Object.prototype.hasOwnProperty.call(f.alt, r.name)) { off = f.alt[r.name]; if (off === null) return null; }
  var base = r.top;
  for (var i = 0; f.via && i < f.via.length; i++) { base = base.add(parseInt(f.via[i], 16)).readPointer(); if (base.isNull()) return null; }
  return base.add(parseInt(off, 16));
}
function fieldRead(a, f) {
  switch (f.type) {
    case 'i8': return a.readS8(); case 'u8': return a.readU8();
    case 'i16': return a.readS16(); case 'u16': return a.readU16();
    case 'i32': return a.readS32(); case 'u32': return a.readU32();
    case 'f32': return a.readFloat(); case 'f64': return a.readDouble();
    case 'ptr': { var p = a.readPointer(); return p.isNull() ? null : p; }
    case 'date': return m24gaDecodeDate(a.readU32());
    case 'str': { var h = a.readPointer(); if (h.isNull()) return ''; var n = h.readU32(); return (n > 0 && n < 400) ? h.add(4).readUtf8String(n) : ''; }
    case 'strref': return strAt(a);
  }
  throw new Error('모르는 형식 ' + f.type);
}
function fieldMap(v, f) {
  if (f.map === 't20') return (typeof v === 'number' && v >= 1 && v <= 100) ? Math.max(1, Math.floor((v + 2) / 5)) : null;
  return v;
}
// 객체의 필드 값 (못 읽으면 null). date는 {y, m, d, doy, iso}, ptr은 포인터(빈 포인터는 null), str·strref는 글
function getField(obj, name) {
  var f = M24_FIELDS.fields[name]; if (!f) throw new Error("모르는 필드 '" + name + "' (fieldNames()로 목록을 보세요)");
  try { var a = fieldAddr(obj, f); return a ? fieldMap(fieldRead(a, f), f) : null; } catch (e) { return null; }
}
// 종류와 key로 객체 찾기: findObj('player', uid). find 방법이 없는 종류는 주소 글('0x...')을 받아 종류를 확인한다
function findObj(kindName, key) {
  var kind = M24_FIELDS.kinds[kindName]; if (!kind) return null;
  var o = null;
  if (kind.find === 'player') o = playerByUid(Number(key) >>> 0);
  else if (kind.find === 'human' && (typeof key === 'number' || /^\d+$/.test(String(key)))) o = humans()[Number(key)] || null;   // 0 = 이 PC의 감독
  else if (typeof key === 'string' && /^0x[0-9a-f]+$/i.test(key)) o = ptr(key);
  return o && kindMatches(rttiInfo(o), kind) ? (rttiInfo(o).top) : null;
}
// 객체 -> 그 종류의 key 값 (기록·되돌리기에 쓴다). key 필드가 없는 종류는 맨 앞 주소 글
function fieldKey(obj, kindName) {
  var kind = M24_FIELDS.kinds[kindName], r = rttiInfo(obj); if (!kindMatches(r, kind)) return null;
  if (kind.find === 'human') { var hs = humans(); for (var i = 0; i < hs.length; i++) if (hs[i].equals(r.top)) return i; return null; }   // 감독 순번 (주소는 게임을 다시 켜면 바뀐다)
  return kind.key ? getField(obj, kind.key) : r.top.toString();
}
function fieldWrite(a, f, v) {
  switch (f.type) {
    case 'i8': a.writeS8(v); break; case 'u8': a.writeU8(v); break;
    case 'i16': a.writeS16(v); break; case 'u16': a.writeU16(v); break;
    case 'i32': a.writeS32(v); break; case 'u32': a.writeU32(v); break;
    case 'f32': a.writeFloat(v); break; case 'f64': a.writeDouble(v); break;
    default: throw new Error(f.type + ' 형식은 쓸 수 없어요');
  }
}
var FIELD_INT_RANGE = { i8: [-128, 127], u8: [0, 255], i16: [-32768, 32767], u16: [0, 65535], i32: [-2147483648, 2147483647], u32: [0, 4294967295] };
// write: 'safe' 필드마다 쓰기 함수를 만든다 (modhost.js m24gaWrite가 기능·세이브·폭주를 확인한 뒤 부른다, 되돌리기도 같은 함수).
// 확인: 객체를 key로 다시 찾음, 형식 범위, range, gte/lte(다른 필드), expect(지금 값), check 필드가 쓰기 전후 그대로인지, 쓴 값을 다시 읽어 확인
function makeFieldWriter(name, f) {
  var kind = M24_FIELDS.kinds[f.kind], label = f.desc ? f.desc.split(' (')[0] : name;
  return {
    cap: f.cap || 'write.field', float: f.type === 'f32' || f.type === 'f64',
    write: function (key, value, expect) {
      var o = findObj(f.kind, key);
      if (!o) return { ok: false, error: (kind ? kind.label : f.kind) + '을(를) 찾지 못했어요 (' + key + ')' };
      if (kind.key && getField(o, kind.key) !== key) return { ok: false, error: '객체가 맞지 않아요' };
      var a = fieldAddr(o, f); if (!a) return { ok: false, error: '이 객체에는 ' + name + ' 칸이 없어요' };
      var who = kind.name ? getField(o, kind.name) || '' : '', cur = fieldRead(a, f);
      var bad = function (msg) { return { ok: false, error: msg, before: cur, name: who }; };
      var ir = FIELD_INT_RANGE[f.type];
      if (ir && (value < ir[0] || value > ir[1])) return bad(name + ' 형식(' + f.type + ') 범위를 벗어나요');
      if (f.range && (value < f.range[0] || value > f.range[1])) return bad(label + '은(는) ' + f.range[0] + '~' + f.range[1] + '이어야 해요');
      if (f.gte) { var lo = getField(o, f.gte); if (typeof lo === 'number' && value < lo) return bad(label + '은(는) 지금 ' + (fieldInfo(f.gte).desc || f.gte).split(' (')[0] + '(' + lo + ')보다 낮을 수 없어요'); }
      if (f.lte) { var hi = getField(o, f.lte); if (typeof hi === 'number' && value > hi) return bad(label + '은(는) 지금 ' + (fieldInfo(f.lte).desc || f.lte).split(' (')[0] + '(' + hi + ')보다 높을 수 없어요'); }
      if (expect !== undefined && expect !== null && cur !== expect) return bad('지금 ' + label + '(' + cur + ')가 예상(' + expect + ')과 달라요');
      if (cur === value) return { ok: true, before: cur, after: cur, name: who, same: true };
      var chk = (kind.check || []).map(function (c) { return JSON.stringify(getField(o, c)); });
      fieldWrite(a, f, value);
      var after = fieldRead(a, f);
      var moved = (kind.check || []).some(function (c, i) { return JSON.stringify(getField(o, c)) !== chk[i]; });
      if (moved) return { ok: false, error: '쓰는 중에 객체가 바뀌었어요', before: cur, after: after, name: who };
      var same = f.type === 'f32' ? Math.abs(after - value) < 1e-3 * Math.max(1, Math.abs(value)) : after === value;
      return { ok: same, before: cur, after: after, name: who, error: same ? undefined : '쓴 값이 확인되지 않아요' };
    }
  };
}
function installFieldWriters() {
  for (var n in M24_FIELDS.fields) { var f = M24_FIELDS.fields[n]; if (f.write === 'safe') M24GA.writers[n] = makeFieldWriter(n, f); }
}
installFieldWriters();   // player.pa(M14의 setPlayerPA)도 여기서 만든다: 범위 1~200, CA 이상, UID·생년월일 확인
M24GA.fieldKey = fieldKey;
M24GA.fieldKind = function (name) { var f = M24_FIELDS.fields[name]; return f ? f.kind : null; };
// explore가 칸에 필드 이름을 붙이게: 객체 종류에 맞는 필드(via 없는 것) -> { 맨 앞에서의 위치: [이름] }
function fieldsAt(r) {
  var m = {};
  for (var n in M24_FIELDS.fields) {
    var f = M24_FIELDS.fields[n]; if (f.via || !kindMatches(r, M24_FIELDS.kinds[f.kind])) continue;
    var off = f.off; if (f.alt && Object.prototype.hasOwnProperty.call(f.alt, r.name)) off = f.alt[r.name];
    if (off === null) continue;
    off = parseInt(off, 16); (m[off] = m[off] || []).push(n);
  }
  return m;
}

// ---- 소셜 패널 도우미 (M13, read.panel): 모드가 패널 메모리를 직접 읽지 않게 ----
// 패널 객체: vtable PANEL_VT, +0x1d8 글 종류, +0x1f0 글자 핸들, +0x1b0 스레드(뉴스) 객체, +0x1c8/+0x1d0 작성자 레코드(Salo = 응원 클럽 고유 ID)
function panelAt(addr, type) {   // 주소 문자열(th.toString()) -> 아직 소셜 패널이면 그 객체 (type을 주면 글 종류도 같아야), 아니면 null
  try {
    var th = ptr(addr);
    if (!th.readPointer().equals(PANEL_VT)) return null;
    if (type !== undefined && type !== null && th.add(0x1d8).readU32() !== type) return null;
    return th;
  } catch (e) { return null; }
}
function panelDst(th) { return th.add(0x1f0); }   // 글자 칸 (setStr의 첫 인자, 이벤트의 ev.dst와 같다)
function panelText(th) {   // 지금 패널 글 ('' = 비어 있음, null = 못 읽음)
  try { var h = th.add(0x1f0).readPointer(); if (h.isNull()) return ''; var n = h.readU32(); return (n > 0 && n <= 4000) ? h.add(4).readUtf8String(n) : ''; } catch (e) { return null; }
}
function panelTextHandle(th) { try { return th.add(0x1f0).readPointer().toString(); } catch (e) { return null; } }   // 지금 글자 객체의 주소 (같은 글자인지 비교용)
function panelThread(th) { try { return th.add(0x1b0).readPointer(); } catch (e) { return null; } }        // 스레드(뉴스) 객체: newsBody(), 같은 글 묶기 키
function panelFanUid(th) {   // 댓글 작성자가 응원하는 클럽의 고유 ID (fanClub에 넘긴다). 없으면 0
  try { var r = decodeVal(th.add(0x1c8).readPointer(), th.add(0x1d0), 0); return r && typeof r.Salo === 'number' ? r.Salo : 0; } catch (e) { return 0; }
}
// 클럽 데이터 객체(clubs 표) -> 클럽 객체 / 정식 이름 / 짧은 이름. 대표팀은 클럽 객체가 없어서 null / ''
function clubObj(cd) { try { var co = cd.add(0x30).readPointer(); return co.readPointer().equals(CLUBOBJ_VT) ? co : null; } catch (e) { return null; } }
function clubNameAt(co, off) { try { var h = co.add(off).readPointer(); var n = h.readU32(); return (n > 0 && n < 200) ? h.add(4).readUtf8String(n) : ''; } catch (e) { return ''; } }
function clubFullName(cd) { var co = clubObj(cd); return co ? clubNameAt(co, 0xc0) : ''; }
function clubShortName(cd) { var co = clubObj(cd); return co ? clubNameAt(co, 0xc8) : ''; }

function lookup(map, idx, vt) {   // 표에서 꺼낸 객체가 아직 같은 객체인지 확인
  idx = Number(idx) >>> 0;   // Object.keys(표)는 글자 번호를 준다. 글자로 비교하면 멀쩡한 항목을 지워 버렸다 (몸값모드 V01)
  var o = map[idx];
  if (!o) return null;
  try {
    // 클럽이 사라졌으면 다른 세이브 -> 전부 다시. 사람만 사라졌으면 은퇴 등 -> 그 항목만 빼고 다시 만들기 후보 (38번 로그)
    var ov = o.readPointer(), vok = ov.equals(vt) || (map === clubs && ov.equals(NT_VT));   // 클럽 표에는 대표팀 객체도 있다
    if (!vok || o.add(8).readU32() !== idx) {
      if (map === clubs) { if (!vok) staleMaps('vtable'); return null; }
      delete map[idx]; noteMiss('gone'); return null;
    }
  } catch (e) { if (map === clubs) staleMaps('read'); else { delete map[idx]; noteMiss('gone'); } return null; }
  return o;
}
function pickCtx() {   // +0x68 -> 문자열 핸들 포인터 -> 감독 이름이 있는 후보
  ctxCands.forEach(function (a) {
    if (newsCtx) return;
    try { var h = a.add(0x68).readPointer().readPointer(), n = h.readU32(); if (n > 0 && n < 100 && h.add(4).readUtf8String(n).length) newsCtx = a; } catch (e) {}
  });
}
function stripMarkup(s) {   // 링크 -> 이름, 해시태그 제거
  return s.replace(/\x01[^\x02\x01]*\x02([^\x01]*)\x01/g, '$1').replace(/\|c:hashtag\|[^|]*\|\/c\|/g, '').replace(/[\x00-\x09\x0b-\x1f]/g, '');
}
function newsBody(news) {   // 실패하면 '' (본문이 없어도 댓글 생성은 그대로)
  var k = news.toString();
  if (k in bodies) return bodies[k];
  bodies[k] = '';
  if (!newsCtx) return '';
  try {
    if (!newsCtx.readPointer().equals(NEWS_CTX_VT)) { staleMaps('ctx'); return ''; }
    var nv = news.readPointer();                       // 뉴스 객체의 vtable이 fm.exe 안이어야 가상 함수를 부른다
    if (nv.compare(B) < 0 || nv.compare(MEND) >= 0) return '';
  } catch (e) { return ''; }
  [1, 0].some(function (plain) {   // 평문 모드가 빈 값인 기사가 있어서 마크업 모드로 한 번 더
    try {
      var o = Memory.alloc(0x10); o.writePointer(ptr(0));
      buildBody(news, o, newsCtx, 1, plain);
      var h = o.readPointer(); if (h.isNull()) return false;
      var n = h.readU32(); if (n <= 0 || n > 40000) return false;
      var s = stripMarkup(h.add(4).readUtf8String(n)).trim();
      if (s.length < 10) return false;
      bodies[k] = s.length > 1500 ? s.substr(0, 1500) : s;
      return true;
    } catch (e) { return false; }
  });
  return bodies[k];
}
// buildMaps()는 startMaps()가 부른다 (세이브가 열려 있으면 코어가 스스로, 아니면 첫 패널이 그려질 때)

var B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
function b64bytes(s) {
  var out = [], buf = 0, bits = 0;
  for (var i = 0; i < s.length; i++) {
    var v = B64.indexOf(s[i]); if (v < 0) continue;
    buf = (buf << 6) | v; bits += 6;
    if (bits >= 8) { bits -= 8; out.push((buf >> bits) & 255); }
  }
  return out;
}
function linkIds(text) {   // [{name, type, idx}]
  var re = /\x01([A-Za-z0-9+\/=]+)\x02([^\x01]*)\x01/g, m, res = [], seen = {};
  while ((m = re.exec(text)) !== null) {
    var b = b64bytes(m[1]);
    for (var i = 0; i + 9 < b.length; i++) {
      if (b[i] === 0x66 && b[i + 1] === 0x65 && b[i + 2] === 0x72 && b[i + 3] === 0x64) {   // 'ferd'
        var idx = b[i + 6] | (b[i + 7] << 8) | (b[i + 8] << 16), t = b[i + 9];
        var k = t + ':' + idx;
        if (!seen[k]) { seen[k] = 1; res.push({ name: m[2], type: t, idx: idx }); }
        break;
      }
    }
  }
  return res;
}
function getInt(obj, code) {
  var fn = new NativeFunction(checkObj(obj).add(0x10).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer']);
  var buf = Memory.alloc(0x40); buf.writePointer(EMPTY_VAL);
  var c = ((code.charCodeAt(0) << 24) | (code.charCodeAt(1) << 16) | (code.charCodeAt(2) << 8) | code.charCodeAt(3)) >>> 0;
  if (!fn(obj, c, buf) || buf.readPointer().toString() !== INT_T) return null;
  return buf.add(8).readS32();
}
// 포지션 숙련도(1~20) 중 가장 높은 것을 주 포지션으로 본다. 선수가 아닌 인물(감독 등)은 모두 낮아서 null
var POS_FIELDS = [['Pgoa', '골키퍼'], ['Pdce', '중앙 수비수'], ['Pdls', '왼쪽 풀백'], ['Pdrs', '오른쪽 풀백'],
  ['Pwbl', '왼쪽 윙백'], ['Pwbr', '오른쪽 윙백'], ['Pdmc', '수비형 미드필더'], ['Pmce', '중앙 미드필더'],
  ['Pmls', '왼쪽 미드필더'], ['Pmrs', '오른쪽 미드필더'], ['Pamc', '공격형 미드필더'], ['Paml', '왼쪽 윙어'],
  ['Pamr', '오른쪽 윙어'], ['Pace', '스트라이커']];
function mainPosition(obj) {
  var best = null, bv = 14;
  POS_FIELDS.forEach(function (f) { try { var v = getInt(obj, f[0]); if (v !== null && v > bv) { bv = v; best = f[1]; } } catch (x) {} });
  return best;
}

// ---- 묶음 값 해석: 결과 값 [종류 포인터][값 8바이트]
//   record(0x5c2348) = [begin][end] 안에 16바이트 [4글자 키][값 포인터]
//   list(0x5c2338)   = [begin][end] 안에 값 포인터(8바이트)
//   실수(0x5c2308) = double, 정수(0x5c22b8), 문자열(0x5c2318) = SIString 핸들
// (종류 표 VT는 위 setTypes가 채운다)
function cc4(v) { return String.fromCharCode((v >>> 24) & 255, (v >>> 16) & 255, (v >>> 8) & 255, v & 255); }
function decodeVal(tp, vbuf, depth) {
  var t = VT[tp.toString()];
  if (t === 'int') return vbuf.readS32();
  if (t === 'dbl') return Math.round(vbuf.readDouble() * 100) / 100;
  if (t === 'bool') return (vbuf.readU8() & 1) === 1;
  if (t === 'cc') return vbuf.readU32();   // 국가대표 출전·골(Piap/Pigl)처럼 정수인데 다른 종류 번호를 쓰는 값
  if (t === 'flt') return Math.round(vbuf.readFloat() * 100) / 100;   // 32비트 실수 (스쿼드 평균 나이 Cvag 등)
  if (t === 'str') {   // 빈 문자열 항목은 핸들이 잘못된 값일 수 있다 (이름 묶음의 Psna 등)
    try { var p = vbuf.readPointer(), n = p.readU32(); return n > 0 && n < 400 ? p.add(4).readUtf8String(n) : ''; } catch (x) { return ''; }
  }
  if (!t) { var et = extType(tp); return et ? decodeExt(et, vbuf) : null; }   // 코어 0.36.0: 날짜·색·u32 (묶음·목록 안에서도)
  if (depth > 3) return null;
  if (t === 'rec') {   // 항목 하나가 실패해도 나머지는 살린다
    var v = vbuf.readPointer(), b = v.readPointer(), n2 = v.add(8).readPointer().sub(b).toInt32() / 16, o = {};
    for (var i = 0; i < n2 && i < 80; i++) {
      try { var ent = b.add(i * 16), vv = ent.add(8).readPointer(); o[cc4(ent.readU32())] = decodeVal(vv.readPointer(), vv.add(8), depth + 1); } catch (x) {}
    }
    return o;
  }
  if (t === 'list') {
    var l = vbuf.readPointer(), lb = l.readPointer(), n3 = l.add(8).readPointer().sub(lb).toInt32() / 8, a = [];
    for (var j = 0; j < n3 && j < 60; j++) {
      try { var vp = lb.add(j * 8).readPointer(); a.push(vp.isNull() ? null : decodeVal(vp.readPointer(), vp.add(8), depth + 1)); } catch (x) { a.push(null); }
    }
    return a;
  }
  return null;
}
function checkObj(obj) {   // 클럽/사람 데이터 객체가 아니면 가상 함수를 부르지 않는다 (튕김 방지)
  var vt = obj.readPointer();
  if (!vt.equals(CLUB_VT) && !vt.equals(NT_VT) && !vt.equals(PERSON_VT) && !vt.equals(STAFF_VT)) {
    var tg = propTarget(obj);   // 코어 0.36.0: 속성 등록부의 종류(구단·대회·상·사람 감독)도 허용. 속성 부분 자체여야 한다
    if (!tg || !tg.p.equals(obj)) throw new Error('not a data object');
  }
  return vt;
}
function getVal(obj, code) {
  var fn = new NativeFunction(checkObj(obj).add(0x10).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer']);
  var buf = Memory.alloc(0x40); buf.writePointer(EMPTY_VAL);
  var c = ((code.charCodeAt(0) << 24) | (code.charCodeAt(1) << 16) | (code.charCodeAt(2) << 8) | code.charCodeAt(3)) >>> 0;
  if (!fn(obj, c, buf)) return null;
  return decodeVal(buf.readPointer(), buf.add(8), 0);
}

// ---- 속성 등록부 (코어 0.36.0, M55) ----
// 게임 객체의 get_property(vtable+0x10)에 후보 코드를 모두 물어 본 결과 = core/properties.json (tools/props_catalog.py).
// 종류(kind)는 RTTI 클래스 이름 + 속성 부분의 칸(선수 +0x278, 스태프 +0xf8, 사람 감독 +0x450)이라 객체의 어느 칸 포인터를 줘도 된다.
// 로더가 짧은 판을 넣는다: { kinds: {종류: [클래스, 칸]}, block: [부르면 접근 오류 나는 코드], p: {코드: [값 종류, 종류 비트]} }
var M24_PROPS = { kinds: {}, block: [], p: {} };   // 로더가 core/properties.json을 넣는다
var PROP_KIND_NAMES = null, PROP_BY_CLASS = {}, PROP_BLOCK = {}, PROP_SUB = {};
function propsInit() {
  if (PROP_KIND_NAMES) return;
  PROP_KIND_NAMES = Object.keys(M24_PROPS.kinds);
  PROP_KIND_NAMES.forEach(function (k, i) { var v = M24_PROPS.kinds[k]; PROP_BY_CLASS[v[0]] = { kind: k, off: v[1], bit: 1 << i }; });
  (M24_PROPS.block || []).forEach(function (c) { PROP_BLOCK[c] = true; });
}
function code4(code) { return ((code.charCodeAt(0) << 24) | (code.charCodeAt(1) << 16) | (code.charCodeAt(2) << 8) | code.charCodeAt(3)) >>> 0; }
// 객체(어느 칸이든) -> { p: 속성 부분, kind, bit } 또는 null. 클래스·칸·vtable(+0x10 함수가 fm.exe 안)을 모두 확인한다
function propTarget(obj) {
  propsInit();
  var r = rttiInfo(obj); if (!r) return null;
  var k = PROP_BY_CLASS[r.name]; if (!k) return null;
  var p = r.top.add(k.off);
  try {
    var vt = p.readPointer(), key = vt.toString();
    if (!(key in PROP_SUB)) {
      var vr = rttiOfVt(vt), f = vt.add(0x10).readPointer();
      PROP_SUB[key] = !!vr && vr.name === r.name && vr.off === k.off && inModule(f);
    }
    return PROP_SUB[key] ? { p: p, kind: k.kind, bit: k.bit } : null;
  } catch (e) { return null; }
}
// 대상 글 -> 객체: 'me'(내 감독), 'myteam', 'myclub', 'myjob'(내 감독 계약), 사람 참조 'p123'/'s45', 'team:<번호>', 'comp:<번호>', '0x주소', 또는 포인터
function propResolve(o) {
  if (o && typeof o.add === 'function') return o;
  var s = String(o || ''), m;
  if (s === 'me') return myHuman();
  if (s === 'myteam') return myTeamObj();
  if (s === 'myclub') { var t = myTeamObj(); return t ? clubOfTeam(t) : null; }
  if (s === 'myjob') { var h = myHuman(); if (!h) return null; var j = h.add(0x518).readPointer(); return j.isNull() ? null : j; }   // 내 감독 계약 (db::FULL_CONTRACT)
  if (/^[ps]\d+$/.test(s)) return personByRef(s);
  if ((m = /^team:(\d+)$/.exec(s))) return lookup(clubs, +m[1], CLUB_VT);
  if ((m = /^comp:(\d+)$/.exec(s))) return lookup(comps, +m[1], COMP_VT);
  if (/^0x[0-9a-f]+$/i.test(s)) return ptr(s);
  return null;
}
// 값 종류 확장 (VT 표에 없는 것): 종류 포인터의 클래스 이름으로 가린다 (실행마다 주소가 바뀜)
var EXT_T = {};
function extType(tp) {
  var k = tp.toString(); if (k in EXT_T) return EXT_T[k];
  var t = null;
  try {
    if (EMPTY_VAL && tp.equals(EMPTY_VAL)) t = 'empty';
    else if (EMPTY_VAL && tp.equals(EMPTY_VAL.add(0x50))) t = 'u32';
    else { var n = className(tp) || ''; t = /SI_DATE/.test(n) ? 'date' : /RGBA/.test(n) ? 'color' : /DATA_TYPED/.test(n) ? 'data' : null; }
  } catch (e) {}
  return (EXT_T[k] = t);
}
// 속성 날짜 u32: 연도 = >>>17, 연중 일수(1~366) = (>>>8)&0x1ff, 아래 8비트는 다른 뜻. 1900-01-01 = 빈 날짜 (M55: 계약 만료 2038 181일 = 6월 30일)
function propDate(u) {
  var y = u >>> 17, d = (u >>> 8) & 0x1ff;
  if (y <= 1900) return null;
  var dd = m24gaDecodeDate((y << 16) | d); return dd ? dd.iso : null;
}
function decodeExt(t, vbuf) {
  if (t === 'u32') return vbuf.readU32();
  if (t === 'date') return propDate(vbuf.readU32());
  if (t === 'color') { var a = new Uint8Array(vbuf.readByteArray(4)), s = '#'; for (var i = 0; i < 4; i++) s += ('0' + a[i].toString(16)).slice(-2); return s; }
  return null;   // empty, data(내부 자료)
}
// 속성 하나 읽기. 반환: 값 / null(빈 값) / undefined(이 객체가 답하지 않는 코드). 모르는 객체·막은 코드는 예외
function propGet(obj, code) {
  code = String(code || '');
  if (code.length !== 4) throw new Error('속성 코드는 4글자예요: ' + code);
  if (PROP_BLOCK[code] || (propsInit(), PROP_BLOCK[code])) throw new Error('이 코드는 게임 안에서 접근 오류가 나서 막았어요: ' + code);
  var o = propResolve(obj); if (!o) throw new Error('대상을 찾지 못했어요: ' + obj);
  var tg = propTarget(o); if (!tg) throw new Error('속성을 읽을 수 없는 객체예요 (' + (className(o) || '?') + ')');
  if (!EMPTY_VAL) throw new Error('값 종류 표가 아직 없어요 (세이브를 불러온 뒤에 써요)');
  var fn = new NativeFunction(tg.p.readPointer().add(0x10).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer']);
  var buf = Memory.alloc(0x40); buf.writePointer(EMPTY_VAL);
  if (!fn(tg.p, code4(code), buf)) return undefined;
  var tp = buf.readPointer();
  if (VT[tp.toString()]) return decodeVal(tp, buf.add(8), 0);
  return decodeExt(extType(tp), buf.add(8));
}
// 객체가 답하는 코드(등록부 기준) 전부: { 코드: 값 }. opts = { re: 정규식 글, codes: [코드], empty: 빈 값도 넣기 }
function propsAll(obj, opts) {
  opts = opts || {};
  var o = propResolve(obj); if (!o) throw new Error('대상을 찾지 못했어요: ' + obj);
  var tg = propTarget(o); if (!tg) throw new Error('속성을 읽을 수 없는 객체예요 (' + (className(o) || '?') + ')');
  var rx = opts.re ? new RegExp(opts.re) : null, list = opts.codes || Object.keys(M24_PROPS.p), out = {};
  list.forEach(function (c) {
    var e = M24_PROPS.p[c]; if (!e || !(e[1] & tg.bit) || PROP_BLOCK[c] || (rx && !rx.test(c))) return;
    var v; try { v = propGet(o, c); } catch (x) { return; }
    if (v === undefined || ((v === null || v === '') && !opts.empty)) return;
    out[c] = v;
  });
  return out;
}
function propInfo(code) {
  propsInit();
  var e = M24_PROPS.p[code]; if (!e) return null;
  var w = (M24_PROPS.w || {})[code], out = { code: code, t: e[0], k: PROP_KIND_NAMES.filter(function (k, i) { return e[1] & (1 << i); }), blocked: !!PROP_BLOCK[code] };
  out.writable = w ? w[0] : ((M24_PROPS.deny || []).indexOf(code) >= 0 ? 'deny' : false);   // 코어 0.42.0: 'safe' | 'tested' | 'deny' | false
  if (w) { out.writeKinds = PROP_KIND_NAMES.filter(function (k, i) { return w[1] & (1 << i); }); if (w[2] !== null) out.range = [w[2], w[3]]; }
  return out;
}
// ---- 속성 쓰기 (코어 0.42.0, M71) ----
// 게임 자신의 set_property(속성 객체 vtable +0x18, get_property 바로 다음 칸)를 부른다. 게임 층(GAME_CLUB 등)이 먼저 처리하고,
// 값 자르기·바뀜 알림도 게임이 한다. 값 버퍼는 get_property가 채운 것의 값 종류 포인터(정적 표)를 그대로 쓰고 값 칸만 바꾼다
// (스칼라만: 정수·불리언·실수. 묶음·목록·글·링크는 힙 구조라 흉내 내지 않는다, M66). 등록부 write.codes에 있는 코드만,
// deny(Ptyp 등: 사람 종류를 바꾸면 게임이 객체를 새로 만든다, M71 3절)는 절대 안 쓴다. 화면 스레드에서만 부른다 (runOnUi).
var PROP_SCALAR = { int: 'i', cc: 'u', u32: 'u', bool: 'b', flt: 'f', dbl: 'd' };
function propRaw(p, code) {   // -> { t, tp, v } (스칼라가 아니면 t만)
  var g = new NativeFunction(p.readPointer().add(0x10).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer']);
  var buf = Memory.alloc(0x40); buf.writePointer(EMPTY_VAL);
  if (!g(p, code4(code), buf)) return null;
  var tp = buf.readPointer(), t = VT[tp.toString()] || extType(tp), s = PROP_SCALAR[t], b = buf.add(8);
  var v = s === 'i' ? b.readS32() : s === 'u' ? b.readU32() : s === 'b' ? (b.readU8() & 1) : s === 'f' ? b.readFloat() : s === 'd' ? b.readDouble() : undefined;
  return { t: t, tp: tp, v: v };
}
function propSetRaw(p, code, r, x) {
  var s = new NativeFunction(p.readPointer().add(0x18).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer']);
  var b = Memory.alloc(0x40), k = PROP_SCALAR[r.t]; b.writePointer(r.tp); b.add(8).writeU64(0);
  if (k === 'i') b.add(8).writeS32(x); else if (k === 'u') b.add(8).writeU32(x >>> 0); else if (k === 'b') b.add(8).writeU8(x ? 1 : 0);
  else if (k === 'f') b.add(8).writeFloat(x); else b.add(8).writeDouble(x);
  return s(p, code4(code), b);
}
// 객체 -> 쓰기 열쇠 (dref 번호: 세이브를 다시 불러와도 같다 -> 기록·되돌리기에 쓴다)
function propKey(obj) {
  var o = propResolve(obj); if (!o) return null;
  var d = propGet(o, 'dref'); d = d && d.dref;
  return typeof d === 'number' && propDeref(d) ? d >>> 0 : null;
}
function makePropWriter(code) {
  var w = M24_PROPS.w[code];
  return {
    cap: 'write.prop', float: !!(M24_PROPS.p[code] && M24_PROPS.p[code][0] === 'num'), ui: true, prop: true,   // num = 실수 (위도·경기장 크기 등)
    write: function (key, value, expect) {
      if ((M24_PROPS.deny || []).indexOf(code) >= 0) return { ok: false, error: code + '는 쓰면 안 되는 코드예요' };
      var o = propDeref(key); if (!o) return { ok: false, error: '대상을 찾지 못했어요 (dref ' + key + ')' };
      var tg = propTarget(o); if (!tg) return { ok: false, error: '속성 객체가 아니에요' };
      if (!(w[1] & tg.bit)) return { ok: false, error: code + '는 ' + tg.kind + '에 쓰기가 확인되지 않았어요' };
      var r = propRaw(tg.p, code); if (!r) return { ok: false, error: '이 객체가 ' + code + '에 답하지 않아요' };
      if (!PROP_SCALAR[r.t]) return { ok: false, error: code + ' 값 종류(' + r.t + ')는 쓸 수 없어요 (정수·불리언·실수만)' };
      var cur = r.v, bad = function (m) { return { ok: false, error: m, before: cur }; };
      if (typeof value === 'boolean') value = value ? 1 : 0;
      if (typeof value !== 'number' || !isFinite(value)) return bad('값은 숫자여야 해요');
      if (PROP_SCALAR[r.t] !== 'f' && PROP_SCALAR[r.t] !== 'd' && value !== Math.floor(value)) return bad('값은 정수여야 해요');
      if (r.t === 'bool' && value !== 0 && value !== 1) return bad('불리언은 true/false(1/0)예요');
      if (w[2] !== null && (value < w[2] || value > w[3])) return bad(code + '는 ' + w[2] + '~' + w[3] + '이어야 해요');
      if (w[4]) { var lo = propGet(o, w[4]); if (typeof lo === 'number' && value < lo) return bad(code + '는 지금 ' + w[4] + '(' + lo + ')보다 낮을 수 없어요'); }
      if (w[5]) { var hi = propGet(o, w[5]); if (typeof hi === 'number' && value > hi) return bad(code + '는 지금 ' + w[5] + '(' + hi + ')보다 높을 수 없어요'); }
      if (expect !== undefined && expect !== null && cur !== expect) return bad('지금 ' + code + '(' + cur + ')가 예상(' + expect + ')과 달라요');
      if (cur === value) return { ok: true, before: cur, after: cur, same: true };
      var cls0 = className(rttiInfo(o).top), ok = propSetRaw(tg.p, code, r, value), r1 = propRaw(tg.p, code), cls1 = className(rttiInfo(o).top);
      if (cls1 !== cls0 || propDeref(key) === null || !ptr(propDeref(key)).equals(o))
        return { ok: false, before: cur, error: '쓰는 중에 게임이 객체를 바꿨어요 (' + cls0 + ' -> ' + cls1 + '). 이 쓰기는 되돌릴 수 없어요' };
      var after = r1 ? r1.v : undefined;
      var same = (PROP_SCALAR[r.t] === 'f' || PROP_SCALAR[r.t] === 'd') ? Math.abs(after - value) < 1e-3 * Math.max(1, Math.abs(value)) : after === value;
      if (!ok || !same) {   // 게임이 거절했거나 다른 값으로 바꿨다 -> 원래 값으로 되돌린다
        if (after !== cur) propSetRaw(tg.p, code, r, cur);
        return { ok: false, before: cur, after: after, error: !ok ? '게임이 이 값을 받지 않았어요' : '게임이 값을 ' + after + '(으)로 바꿔서 되돌렸어요' };
      }
      return { ok: true, before: cur, after: after };
    }
  };
}
function installPropWriters() {
  for (var c in (M24_PROPS.w || {})) M24GA.writers['prop.' + c] = makePropWriter(c);
}
installPropWriters();
M24GA.propKey = propKey;
M24GA.propWriteTier = function (code) { var w = (M24_PROPS.w || {})[code]; return w ? w[0] : null; };
M24GA.runOnUi = runOnUi;
// {dref: 번호} 또는 번호 -> 게임 객체. 위 8비트 = 종류: 0x01 사람, 0x03 구단, 0x18 팀(국가대표 포함), 0x19 대회. 모르는 종류·없는 번호는 null
function propDeref(d) {
  if (d && typeof d === 'object') d = d.dref;
  if (typeof d !== 'number') return null;
  var kind = d >>> 24, i = d & 0xffffff;
  if (kind === 0x01) {
    var hs = humans();   // 사람 감독은 staff 표에 없다: 사람 부분(+0x450) +8 번호로 맞춘다
    for (var h = 0; h < hs.length; h++) { try { if (hs[h].add(0x458).readU32() === i) return hs[h]; } catch (e) {} }
    return lookup(staff, i, STAFF_VT) || lookup(persons, i, PERSON_VT);
  }
  if (kind === 0x03) return clubByIndex(i);
  if (kind === 0x18) return lookup(clubs, i, CLUB_VT);
  if (kind === 0x19) return lookup(comps, i, COMP_VT);
  return null;
}
M24GA.propGet = propGet; M24GA.propsAll = propsAll; M24GA.propInfo = propInfo; M24GA.propDeref = propDeref;   // 모드 api.prop/props/propInfo/deref

// ---- 리그 경기 결과 (코어 0.40.0, M63) ----
// 보도 안 되는 경기도: 리그(대회 속성 actm = 참가 팀)의 팀마다 다음 경기(Tnef: 경기 번호 FRfr, home, away, 날짜)와
// 누적 리그 기록(Tomp 경기 수, Tlgs 득점, Tlgc 실점)을 기억해 두고, 다음에 부를 때 경기 수가 늘었으면 늘어난 득점·실점 = 그 경기 점수.
// 홈 팀 기준으로 한 번만 낸다. 처음 부르면 기준만 잡고 []. 하루에 두 경기를 하거나 기록이 리그 밖(컵)이면 맞지 않을 수 있어 건너뜀.
var LEAGUE_SNAP = {};
function leagueTeamSnap(t) {
  var nf = propGet(t, 'Tnef') || {}, f = nf.FRfr && nf.FRfr.dref;
  return { omp: propGet(t, 'Tomp'), gs: propGet(t, 'Tlgs'), gc: propGet(t, 'Tlgc'), fx: f || null,
    home: nf.home && nf.home.dref, away: nf.away && nf.away.dref, date: nf.fxdt || null, comp: nf.comp && nf.comp.dref };
}
function leagueResults(compSpec) {
  var c = compSpec === 'myleague' ? propDeref(propGet('myteam', 'Cdiv')) : propResolve(compSpec);
  if (!c || className(c) !== 'db::COMP') throw new Error('리그(대회)를 찾지 못했어요: ' + compSpec);
  var key = c.add(8).readU32(), cdref = (0x19000000 | key) >>> 0, teams = (propGet(c, 'actm') || []).map(function (x) { return x && x.dref; }).filter(Boolean);
  var now = {}, prev = LEAGUE_SNAP[key], out = [], seen = {};
  teams.forEach(function (d) { var t = propDeref(d); if (t) { try { now[d] = leagueTeamSnap(t); } catch (e) {} } });
  if (prev) {
    teams.forEach(function (d) {
      var a = prev[d], b = now[d]; if (!a || !b || !a.fx || a.home !== d || a.comp !== cdref) return;   // 홈 팀 쪽, 이 리그 경기만
      if (b.omp !== a.omp + 1 || b.fx === a.fx) return;
      var o = a.away, oa = prev[o], ob = now[o]; if (!oa || !ob || ob.omp !== oa.omp + 1 || oa.fx !== a.fx || seen[a.fx]) return;
      var hg = b.gs - a.gs, ag = b.gc - a.gc;
      if (hg !== ob.gc - oa.gc || ag !== ob.gs - oa.gs || hg < 0 || ag < 0) return;   // 양쪽 기록이 맞을 때만
      seen[a.fx] = 1;
      out.push({ home: propDeref(d), away: propDeref(o), homeGoals: hg, awayGoals: ag, date: a.date, fixture: a.fx, comp: c });
    });
  }
  LEAGUE_SNAP[key] = now;
  return out;
}
M24GA.leagueResults = leagueResults;

// ---- 게임 액션 (코어 0.41.0, M65) ----
// 사용자 명령(관심 목록에 넣기, 구독, 이적 제의 …) = ACTION_BASE 클래스 198개 (core/actions.json, M62).
// 읽기: ACTIONS_MANAGER(fm+0x6363570이 가리킴)의 action.query(대상 목록, 감독, 결과, 문맥, 'NULL')가 액션마다 확인 함수를 불러
//   [id][결과 묶음]을 채운다. 결과 묶음 hidn = 메뉴에서 숨김, 나머지 칸 = 실행할 때 쓰는 인자 (화면 메뉴와 같은 판단).
// 실행: 액션마다 fm.exe 안 전역 객체 *_ACTION_UI가 있고 vtable [2] = 처리기 (this, 이벤트 4글자, 결과 묶음, ACTIONS_EVENT_HANDLER).
//   메뉴를 누르면 게임도 이 처리기를 부른다 (M65 실기: 리더십 훈련 코스). 넷째 인자 = 전역 fm+0x63635b0.
// 대상 목록·문맥은 게임 함수로만 만든다: {dref} 묶음 값 = rec.init + rec.set('dref', 정수) + rec.toValue(게임 풀의 참조 횟수 있는 묶음).
// M65 교훈: Frida 메모리로 묶음 값을 흉내 내면 게임 복사본이 그걸 같이 가리키다 나중에(다음 날 처리) 정리하면서 튕겼다 (덤프: 화면 스레드, fm+0x1977be0 근처).
// 대상 목록 벡터의 항목(게임 힙, 0x20바이트씩)은 정리 함수를 몰라 남긴다.
var M24_ACTIONS = {};   // 로더가 넣는다: {id: [클래스, 실행 객체 rva | 0, [처리기 이벤트], [누름 이벤트], 확인 뒤 이벤트 | '', 처리기가 비었나]}
var ACT_MGR_SLOT = 0x6363570, ACT_DIR_SLOT = 0x63635b0, ACT_FN = null;
var ACT_FN_NAMES = ['action.query', 'val.types', 'val.listInit', 'val.listPush', 'rec.init', 'rec.set', 'rec.toValue', 'ui.eventFree'];
function actFns() {
  if (ACT_FN) return ACT_FN;
  var a = {};
  for (var i = 0; i < ACT_FN_NAMES.length; i++) { var st = funcCheck(ACT_FN_NAMES[i]); if (!st.ok) throw new Error(st.error); a[ACT_FN_NAMES[i]] = st.addr; }
  ACT_FN = {
    query: new NativeFunction(a['action.query'], 'void', ['pointer', 'pointer', 'pointer', 'pointer', 'pointer', 'uint32']),
    types: new NativeFunction(a['val.types'], 'pointer', []),
    listInit: new NativeFunction(a['val.listInit'], 'pointer', ['pointer']),
    push: new NativeFunction(a['val.listPush'], 'void', ['pointer', 'pointer']),
    recInit: new NativeFunction(a['rec.init'], 'pointer', ['pointer']),
    recSet: new NativeFunction(a['rec.set'], 'void', ['pointer', 'uint32', 'pointer']),
    toValue: new NativeFunction(a['rec.toValue'], 'void', ['pointer', 'pointer']),
    recFree: new NativeFunction(a['ui.eventFree'], 'void', ['pointer'])
  };
  return ACT_FN;
}
function actGlobal(slot, cls) {   // 전역 칸이 가리키는 객체, 클래스가 맞을 때만 (다른 빌드에서 엉뚱한 곳을 부르지 않게)
  var o = B.add(slot).readPointer();
  if (o.isNull() || className(o) !== cls) throw new Error(cls + '를 찾지 못했어요 (이 게임 빌드에서는 액션을 쓸 수 없어요)');
  return o;
}
// 객체·대상 글 -> dref 번호 (0x01 사람, 0x03 구단, 0x18 팀, 0x19 대회). {dref} 또는 번호는 그대로
function actDref(spec) {
  if (spec && typeof spec === 'object' && typeof spec.dref === 'number') return spec.dref >>> 0;
  if (typeof spec === 'number') return spec >>> 0;
  var o = propResolve(spec); if (!o) throw new Error('대상을 찾지 못했어요: ' + spec);
  var tg = propTarget(o); if (!tg) throw new Error('액션 대상이 될 수 없는 객체예요');
  var id = function (p) { return p.add(8).readU32() & 0xffffff; };
  if (tg.kind === 'human') return (0x01000000 | (tg.p.add(8).readU32() & 0xffffff)) >>> 0;   // 사람 부분 +0x450의 +8 = 감독 번호 (propDeref와 같음)
  if (tg.kind === 'player' || tg.kind === 'staff') return (0x01000000 | id(tg.p)) >>> 0;
  if (tg.kind === 'team' || tg.kind === 'nation') return (0x18000000 | id(tg.p)) >>> 0;
  if (tg.kind === 'comp') return (0x19000000 | id(tg.p)) >>> 0;
  if (tg.kind === 'club') return (0x03000000 | id(tg.p)) >>> 0;   // propDeref의 clubByIndex와 같은 번호 (구단 +8)
  throw new Error("'" + tg.kind + "' 종류는 아직 액션 대상으로 못 써요 (사람·팀·구단·대회만)");
}
function actDrefVal(F, d) {   // {dref: n} 묶음 값 (게임 것). 다 쓰면 actRelease
  var vec = Memory.alloc(0x20); F.recInit(vec);
  var iv = Memory.alloc(16); iv.writePointer(EMPTY_VAL.add(0x20)); iv.add(8).writeU64(d >>> 0);   // 정수 값은 안에 바로 든다 (복사됨)
  F.recSet(vec, code4('dref'), iv);
  var v = Memory.alloc(16); v.writePointer(EMPTY_VAL); v.add(8).writeU64(0);   // 빈 값에서 시작
  F.toValue(v, vec); F.recFree(vec);
  return v;
}
function actRelease(v) {   // 값 정리 = 종류 객체의 가상 함수 +0x10 (게임 코드와 같음)
  try { var t = v.readPointer(); new NativeFunction(t.readPointer().add(0x10).readPointer(), 'void', ['pointer', 'pointer'])(t, v); } catch (e) {}
}
function actDrefMe() { var h = humans()[0]; if (!h) throw new Error('사람 감독을 찾지 못했어요'); return { obj: h, d: (0x01000000 | (h.add(0x458).readU32() & 0xffffff)) >>> 0 }; }
// 화면 메뉴가 넘기는 것과 같은 문맥 {Pers, Ttea, Hhum, SidT, islc, objt}
function actContext(d) {
  var me = actDrefMe(), myt = null, kind = d >>> 24, c = { Hhum: me.d, islc: true, objt: d };
  try { myt = actDref('myteam'); c.SidT = myt; } catch (e) {}
  if (kind === 0x01) { c.Pers = d; var o = propDeref(d), t = null; try { t = o && propGet(o, 'Pcte'); } catch (e) {} c.Ttea = (t && t.dref) || myt; }
  else if (kind === 0x18) c.Ttea = d;
  else if (myt) c.Ttea = myt;
  if (kind === 0x03) c.Cclu = d;   // 구단 화면 문맥 (M65: 구단 결과 묶음에 Cclu)
  return { me: me, c: c };
}
// 게임에 묻기: fn(결과 [{id, val 포인터}])를 결과가 살아 있는 동안 부른다
function actQuery(d, filter, fn) {
  var F = actFns(), mgr = actGlobal(ACT_MGR_SLOT, 'ACTIONS_MANAGER'), x = actContext(d), T = F.types(), frees = [];
  var list = Memory.alloc(0x20); F.listInit(list);
  var tv = actDrefVal(F, d); F.push(list, tv); actRelease(tv);
  var ctx = Memory.alloc(0x20); F.recInit(ctx);
  Object.keys(x.c).forEach(function (k) {
    var v = x.c[k];
    if (v === true || v === false) { var b = Memory.alloc(16); b.writePointer(T.add(0x18)); b.add(8).writeU64(v ? 1 : 0); F.recSet(ctx, code4(k), b); }
    else { var dv = actDrefVal(F, v); F.recSet(ctx, code4(k), dv); actRelease(dv); }
  });
  var out = Memory.alloc(0x20); F.recInit(out);
  try {
    F.query(mgr, list, x.me.obj, out, ctx, filter ? code4(filter) : 0x4e554c4c);
    var b0 = out.readPointer(), n = b0.isNull() ? 0 : out.add(8).readPointer().sub(b0).toInt32() / 16, L = [];
    for (var i = 0; i < n && i < 400; i++) { var ent = b0.add(16 * i); L.push({ id: cc4(ent.readU32()), val: ent.add(8).readPointer() }); }
    return fn(L, ctx);
  } finally { F.recFree(out); F.recFree(ctx); }   // 둘 다 M65 조사 모드에서 정리해도 됐다
}
function actDecode(vp) { try { return decodeVal(vp.readPointer(), vp.add(8), 0); } catch (e) { return null; } }
// 대상에 지금 쓸 수 있는 액션 (화면 메뉴와 같은 판단). opts.all = 숨은 것도
function actionsFor(spec, opts) {
  opts = opts || {};
  var d = actDref(spec);
  return actQuery(d, null, function (L) {
    var out = [];
    L.forEach(function (e) {
      var r = actDecode(e.val), hid = !r || r.hidn !== false;
      if (hid && !opts.all) return;
      var a = {}; if (r) Object.keys(r).forEach(function (k) { if (k !== 'hidn' && k !== 'disa') a[k] = r[k]; });
      var m = M24_ACTIONS[e.id] || [];
      out.push({ id: e.id, cls: m[0] || null, hidden: hid, disabled: !!(r && r.disa), canRun: !!m[1] && !m[5], events: m[2] || [], click: m[3] || [], confirm: m[4] || null, args: a });
    });
    return out;
  });
}
var ACT_DANGER_CLS = /RESIGN|RETIRE|KICK|BAN_USER|FORCE_|CHANGE_HUMAN_TEAM|TERMINATION|HOLIDAY|ADD_MANAGER|ADD_AI_MANAGER|ADD_MULTIPLE_AI_MANAGER|KEEP_RETIRED/;
// 액션 실행: 게임이 그 대상에 보여 주는 액션일 때만, 그 결과 묶음 그대로 처리기에. opts.event = 이벤트 4글자 (처리기가 받는 것이 하나면 생략)
function actionRun(id, spec, opts) {
  opts = opts || {};
  var m = M24_ACTIONS[id];
  if (!m) throw new Error("모르는 액션 '" + id + "' (docs/ACTIONS.md)");
  if (!m[1]) throw new Error("'" + id + "'는 실행 객체를 못 찾은 액션이에요");
  if (m[5]) throw new Error("'" + id + "'는 실행 처리기가 비어 있어요 (화면 이동·사임처럼 게임이 다른 길로 실행하는 명령, docs/ACTIONS.md)");
  if (ACT_DANGER_CLS.test(m[0]) && opts.danger !== true) throw new Error("'" + id + "'(" + m[0] + ")는 감독 경력을 크게 바꾸는 액션이라 { danger: true }가 있어야 해요");
  var known = m[2].concat(m[3].filter(function (x) { return m[2].indexOf(x) < 0; }));   // 처리기 이벤트 + 누름 이벤트
  var ev = opts.event || (known.length === 1 ? known[0] : null);
  if (!ev) throw new Error("'" + id + "'는 이벤트를 골라야 해요 (opts.event): " + (known.join(', ') || '알려진 이벤트 없음') +
    (m[4] ? " — 확인 창 없이 실행하려면 확인 뒤 이벤트 '" + m[4] + "'" : '') + (m[3].length ? " (메뉴를 누를 때: " + m[3].join(', ') + ", 확인 창·화면을 여는 단계는 모드에서 부르면 창이 안 떠요)" : ''));
  if (known.length && known.indexOf(ev) < 0) throw new Error("'" + id + "'가 받는 이벤트가 아니에요: " + ev + " (" + known.join(', ') + ")");
  var ui = B.add(m[1]), ucls = className(ui);
  if (!ucls || ucls.indexOf('ACTION_UI') < 0) throw new Error("'" + id + "'의 실행 객체가 이 빌드와 맞지 않아요");
  var dir = actGlobal(ACT_DIR_SLOT, 'action_ui::ACTIONS_EVENT_HANDLER'), d = actDref(spec);
  return actQuery(d, id, function (L) {
    var e = null; L.forEach(function (x) { if (x.id === id) e = x; });
    var r = e && actDecode(e.val);
    if (!r || r.hidn !== false) return { ok: false, error: "게임이 이 대상에 '" + id + "'를 보여 주지 않아요 (지금 쓸 수 없음)" };
    if (r.disa) return { ok: false, error: "게임 메뉴에서 '" + id + "'가 흐리게(못 누름) 나와요" };
    var h = new NativeFunction(ui.readPointer().add(0x10).readPointer(), 'uint8', ['pointer', 'uint32', 'pointer', 'pointer']);
    var ret = h(ui, code4(ev), e.val.add(8).readPointer(), dir);
    return { ok: true, id: id, cls: m[0], event: ev, target: d, handled: ret !== 0 };
  });
}
M24GA.actionsFor = function (spec, opts) { return runOnUi(function () { return actionsFor(spec, opts); }); };
M24GA.actionRun = function (id, spec, opts) { return runOnUi(function () { return actionRun(id, spec, opts); }); };
var dbgLines = [], dbgFile = null;
function dbg(msg) {   // 진단 기록 (처음 40줄만)
  if (dbgLines.length >= 40) return;
  dbgLines.push(msg);
  try { if (!dbgFile) dbgFile = new File(DIR + 'hook_debug.txt', 'w'); dbgFile.write(msg + '\n'); dbgFile.flush(); } catch (x) {}
}
function personName(dref) {   // 사람 ID(0x01xxxxxx) -> 이름
  if (!dref || (dref >>> 24) !== 0x01) { dbg('personName bad dref ' + dref); return null; }
  var o = lookup(persons, dref & 0xffffff, PERSON_VT);
  if (!o) { dbg('personName no obj idx ' + (dref & 0xffffff).toString(16) + ' persons=' + Object.keys(persons).length); return null; }
  var n = getVal(o, 'Pnam');
  return n && n.Pfna ? n.Pfna : null;
}
// 선수 폼: Poav = {valu 시즌 평균 평점, numb 출전}, Pgls = {valu 시즌 골}, Pfrm = {Prat 최근 평균, Pgls 최근 골, Pfrm [최근 5경기 평점]}
// 기록·성향 (31번 로그): 카드, xG, 국가대표, 사기 + 숨은 능력치(논란·충성심·야망·부상 경향).
// 숨은 능력치 사용 여부는 Python이 설정(tokens.use_hidden_attributes)으로 정한다. 여기서는 읽기만 한다.
function personExtra(o) {
  var x = {};
  function rec(code) { try { var r = getVal(o, code); return r && typeof r === 'object' && r.numb > 0 ? r : null; } catch (e) { return null; } }
  var yc = rec('Poyc'), rc = rec('Porc'), xg = rec('PoxG');
  if (yc) x['시즌 경고'] = yc.valu;
  if (rc) x['시즌 퇴장'] = rc.valu;
  if (xg) { x['xG'] = xg.valu; x['xG 기준 경기'] = xg.numb; }
  try { var cp = getVal(o, 'Piap'); if (typeof cp === 'number' && cp > 0 && cp < 400) x['국가대표 출전'] = cp; } catch (e) {}
  try { var cg = getVal(o, 'Pigl'); if (typeof cg === 'number' && cg >= 0 && cg < 200) x['국가대표 골'] = cg; } catch (e) {}
  try { var m = getInt(o, 'Pmor'); if (m !== null && m >= 0 && m <= 20) x['사기'] = m; } catch (e) {}
  [['Pcvy', '논란 성향'], ['Ploy', '충성심'], ['Pamb', '야망'], ['Pipr', '부상 경향']].forEach(function (f) {
    try { var v = getInt(o, f[0]); if (v !== null && v >= 1 && v <= 20) x['_숨_' + f[1]] = v; } catch (e) {}
  });
  return x;
}
function personForm(o) {
  var f = {};
  try { var a = getVal(o, 'Poav'); if (a && a.numb > 0) { f.avg = a.valu; f.apps = a.numb; } } catch (x) {}
  try { var g = getVal(o, 'Pgls'); if (g && g.numb > 0) f.goals = g.valu; } catch (x) {}
  try { var r = getVal(o, 'Pfrm'); if (r && r.Pfrm && r.Pfrm.length) { f.recent = r.Pfrm; f.recentAvg = r.Prat; f.recentGoals = r.Pgls; } } catch (x) {}
  return f;
}
function formText(f) {   // "시즌 평균 8.02(26경기, 34골), 최근 5경기 8.6/7.3/7.8/10/8.1(평균 8.36)"
  var t = [];
  if (f.avg !== undefined) t.push('시즌 평균 평점 ' + f.avg + '(' + f.apps + '경기' + (f.goals !== undefined ? ', ' + f.goals + '골' : '') + ')');
  if (f.recent) t.push('최근 5경기 평점 ' + f.recent.join('/') + '(평균 ' + f.recentAvg + ')');
  return t.join(', ');
}

function topPlayer(obj, code, ids) {   // Tstg/Tsma/Tsar -> "이름 (값)", ids[이름] = 사람 ID (링크 만들기용)
  var r = getVal(obj, code);
  if (!r || !r.plys || !r.plys.length || !r.plys[0]) return null;
  var name = personName(r.plys[0].dref);
  if (!name) return null;
  ids[name] = r.plys[0].dref >>> 0;
  try {
    var po = lookup(persons, r.plys[0].dref & 0xffffff, PERSON_VT);
    if (po && !ids['_form_' + name]) ids['_form_' + name] = personForm(po);   // 숫자 그대로 (해석은 Python)
  } catch (x) {}
  return name + ' (' + r.valu + ')';
}
// 클럽 사정 (34번 로그): 돈·나이·분위기. 금액은 게임 내부 단위 그대로 `_c_` 키로 보내고 Python이 원화(×1664.7)로 환산해 말로만 바꾼다.
function clubSituation(obj, d) {
  [['Ctfc', '_c_이적예산'], ['Ccba', '_c_잔고'], ['Ccww', '_c_주급'], ['Cwwb', '_c_주급예산'], ['ccca', '_c_분위기'], ['ccms', '_c_감독지지']].forEach(function (f) {
    try { var v = getInt(obj, f[0]); if (v !== null) d[f[1]] = v; } catch (x) {}
  });
  try { var a = getVal(obj, 'Cvag'); if (typeof a === 'number' && a > 15 && a < 45) d['_c_평균나이'] = a; } catch (x) {}
  try { var t = getVal(obj, 'Ctpr'); if (typeof t === 'number' && t > 0 && t < 5000) d['_c_티켓'] = t; } catch (x) {}
}
function clubExtra(obj, d) {
  // 폼 (38번 로그, 6순위): Tfrm = 게임 화면 '최근 성적'(구단 분위기·순위표)과 같은 5경기. **[0]이 가장 오래된 것, 끝이 가장 최근**.
  // 3 승, 2·1 무, 0 패. 사용자 스크린샷과 대조: 맨시티 [2,0,3,3,3] = "무패승승승", 브렌트포드 [0,0,0,1,0] = "패패패무패".
  // 끝이 최근인 근거: 아스날이 브렌트포드를 이긴 직후 아스날 [0,3,0,0,3], 브렌트포드 [...,0] (앞이 최근이면 아스날이 진 셈).
  // Tsof는 화면과 맞지 않고 실행 중에 뒤에 덧붙는 등 정체를 모른다 (처음엔 Tsof를 썼다가 '맨시티 5연승' 오류). 쓰지 않는다.
  // Twir/Tlir/Tgww 같은 연속 기록 속성도 엉터리 (릴: 연승 1·연패 1·무승 1 동시).
  try {   // 다음 상대 (Topp = 다음 경기 Tnef의 상대 팀) + 그 팀 리그 순위
    var op = getVal(obj, 'Topp');
    if (op && typeof op.dref === 'number' && (op.dref >>> 24) === 0x18) {
      var oo = lookup(clubs, op.dref & 0xffffff, CLUB_VT);
      if (oo) {
        var osh = oo.add(0x30).readPointer().add(0xc8).readPointer(), on = osh.add(4).readUtf8String(osh.readU32());
        var opos = null; try { opos = getInt(oo, 'TpoN'); } catch (x) {}
        if (on) d['다음 상대'] = on + (opos && opos > 0 ? ' (리그 ' + opos + '위)' : '');
      }
    }
  } catch (x) {}
  try {
    var f = getVal(obj, 'Tfrm');
    if (f && f.length && f.every(function (x) { return x >= 0 && x <= 3; })) {
      d['_폼'] = f.slice().reverse();   // Python은 [0]이 가장 최근인 순서로 받는다
      var w = 0, dr = 0, l = 0;
      f.forEach(function (x) { if (x === 3) w++; else if (x === 1 || x === 2) dr++; else if (x === 0) l++; });   // 무승부는 1(0-0)·2 둘 다 (예전엔 2를 빠뜨렸다)
      d['최근 ' + f.length + '경기'] = w + '승 ' + dr + '무 ' + l + '패';
    }
  } catch (x) {}
  [['Tstg', '팀 최다 득점자(골)'], ['Tsma', '팀 도움 1위(도움)'], ['Tsar', '팀 최고 평점 선수(평점)']].forEach(function (f) {
    try { d._ids = d._ids || {}; var t = topPlayer(obj, f[0], d._ids); if (t) d[f[1]] = t; else dbg(d.name + ' ' + f[0] + ' -> null ' + JSON.stringify(getVal(obj, f[0]))); } catch (x) { dbg(d.name + ' ' + f[0] + ' EXC ' + x); }
  });
}

// ---- 모드 등록과 이벤트: core/modhost.js (이 파일 앞에 붙는다) ----
// 게임 날짜·세이브 (M12, M11 0절에서 이 빌드로 실측): 날짜 u32 = fm+0x631D5BC, 세이브 root 포인터 = fm+0x63659C0 (+0x90 id, +0xA0 nonce).
// 주소 출처: FM24 Dynamic PA v0.9.5(GPL-3.0)의 24.4.2 레이아웃. 해석과 변화 감지는 modhost.js가 한다.
var GAME_DATE = B.add(0x631D5BC), SAVE_ROOT = B.add(0x63659C0);
// M36: "진행 중" 판정을 스킨과 무관하게. 진행 화면(GAME_PROCESSING_PANEL)은 스킨에 따라 안 보일 수 있다 (M33).
// 게임의 CONTINUE_MANAGER(싱글턴, fm+0x6364ea0)가 계속 버튼 상태를 들고 있다. +0xc0(u8) = 진행 중 (기본 스킨 실측: 쉬는 상태
// 진행하기·다음 읽기·수신함·답변 요망 모두 0, 진행 중 1. +0xc2·+0xc9도 같이 1). +0xde(u16) = 상태가 바뀔 때마다 1씩 느는 번호, +0xe4 = 게임 날짜 원값.
var CONT_MGR = B.add(0x6364ea0);
function contMgr() { try { var m = CONT_MGR.readPointer(); return (!m.isNull() && className(m) === 'CONTINUE_MANAGER') ? m : null; } catch (e) { return null; } }
// M37: 계속 버튼의 종류. 게임은 상태가 바뀔 때마다 ui.continueKind(CONTINUE_MANAGER)로 종류 번호를 계산해 전역 속성 'cont'로 알린다
// (스킨은 그 속성으로 버튼을 그린다). 코어도 같은 함수를 화면 스레드에서 불러 지금 종류를 얻는다 -> 버튼 id(GCNT/MDSB)에 기대지 않는다.
// (Interceptor로 지켜보는 방식은 안 됨: 우리 콜백 안에서 부른 호출은 Frida가 다시 잡지 않는다)
var contKind = null, fnContKind = null;
function contRefresh() {   // Promise -> 종류 번호 (못 구하면 null 또는 { error })
  var st = funcCheck('ui.continueKind'), m = contMgr();
  if (!st.ok || !m) return Promise.resolve(null);
  return runOnUi(function () {
    if (!fnContKind) fnContKind = new NativeFunction(st.addr, 'int', ['pointer']);
    var mm = contMgr(); if (!mm) return null;
    contKind = fnContKind(mm); return contKind;
  });
}
// M37: 계속을 스킨과 무관하게. CONTINUE_MANAGER의 이벤트 처리기에 'CONT'를 보낸다 = 게임의 handle_continue_game_action
// (계속 버튼이 하는 일 그대로: 종류에 따라 진행 / 다음 읽기 / 수신함 / 답할 메일 열기). 화면 스레드에서만 부른다.
// 종류 번호 (ui.continueKind 반환값, 기본 스킨 실측): -1 진행하기, -8 다음 읽기, -19 수신함, -14 답변 요망, -3 진행 중 (+0xc0), -4 진행 중 (+0xc2)
var CONT_NEED_REPLY = -14, CONT_KINDS = { '-1': 'continue', '-8': 'nextUnread', '-19': 'inbox', '-14': 'needReply', '-3': 'processing', '-4': 'processing' };
function contKindName(k) { return CONT_KINDS[String(k)] || ('other(' + k + ')'); }
var EV_CONT = 0x434f4e54;
function contSend() {
  var h = funcCheck('ui.continueHandler'), en = funcCheck('ui.eventNew'), ef = funcCheck('ui.eventFree'), m = contMgr();
  if (!h.ok) return { error: h.error }; if (!en.ok) return { error: en.error }; if (!ef.ok) return { error: ef.error };
  if (!m) return { error: 'CONTINUE_MANAGER를 찾지 못했어요 (세이브를 불러왔나요?)' };
  var sub = m.add(8), fn = sub.readPointer().add(0x28).readPointer();
  if (!fn.equals(h.addr)) return { error: '계속 이벤트 처리기가 예상과 달라요 (' + fn + ')' };
  var ev = Memory.alloc(0x80);
  new NativeFunction(en.addr, 'pointer', ['pointer', 'uint32', 'uint32'])(ev, EV_CONT, 0);
  var ret = new NativeFunction(h.addr, 'uint8', ['pointer', 'uint32', 'pointer'])(sub, EV_CONT, ev);
  new NativeFunction(ef.addr, 'void', ['pointer'])(ev);
  return { ok: true, handled: !!ret };
}
// M38: 휴가 (스킨 무관). 휴가 창의 '휴가 떠나기'가 부르는 ui.holidayStart(CONTINUE_MANAGER, 고정 값, 옵션, &복귀 날짜, 감독직 지원)를 직접 부른다.
// 옵션 비트 (fm+0x6f19700에서 체크 상자별로): 0x2 모든 제의 거절, 0x4 요구 금액 맞으면 수락, 0x1000 모든 제의 수락, 0x4000 방출 대상만,
// 0x40 현재 전술 사용, 0x80 현재 선발 명단, 0x200 날짜에 복귀, 0x10000 며칠 뒤 복귀, 0x20000 무기한. 기본 = 0x242 (거절·현재 전술·날짜에 복귀, 창의 기본값과 같음)
var HOLIDAY_FIXED = 0x642fad8;
function holidayStart(opts) {
  var st = funcCheck('ui.holidayStart'); if (!st.ok) return Promise.resolve({ error: '휴가를 쓸 수 없어요: ' + st.error });
  if (!opts.date) return Promise.resolve({ error: '복귀 날짜가 없어요' });
  return runOnUi(function () {
    var m = contMgr(); if (!m) return { error: 'CONTINUE_MANAGER를 찾지 못했어요 (세이브를 불러왔나요?)' };
    if (gameBusy()) return { error: '게임이 진행 중이에요. 멈춘 뒤에 하세요', busy: true };
    if (uiTree({ depth: 25, max: 1500 }).modal) return { error: '팝업이 떠 있어요. 먼저 닫으세요' };
    var d = Memory.alloc(8); d.writeU32(opts.date >>> 0);
    var flags = (opts.flags == null ? 0x242 : opts.flags) >>> 0;
    new NativeFunction(st.addr, 'void', ['pointer', 'pointer', 'uint32', 'pointer', 'int32'])(m, B.add(HOLIDAY_FIXED), flags, d, -1);
    return { ok: true, action: 'holiday', date: m24gaDecodeDate(opts.date >>> 0), flags: '0x' + flags.toString(16) };
  });
}
function gameBusy() { var m = contMgr(); if (!m) return null; try { return m.add(0xc0).readU8() !== 0; } catch (e) { return null; } }   // null = 알 수 없음
M24GA.readGame = function () {
  var save = null;
  try { var r = SAVE_ROOT.readPointer(); if (!r.isNull()) save = { id: r.add(0x90).readU32(), nonce: r.add(0xA0).readU32() }; } catch (e) {}
  return { date: GAME_DATE.readU32(), save: save };
};
M24GA.prepareData = function (th) { startMaps(); try { var e = th.add(0x1f8).readPointer(); if (!EMPTY_VAL) { if (!typesOk(e)) dbg("빈 값 종류 표 검증 실패 " + e); TYPES_FROM = "panel"; } setTypes(e); } catch (x) {} };

// 화면 스레드의 메인 루프는 매 프레임 전역 앱 객체(fm+0x6365198)의 가상 함수 [vt+0x18] = fm+0x1049430을 부른다 (초당 약 20번).
// 그 함수가 끝난 직후 = 프레임과 프레임 사이라서, 여기서 다시 그리면 레이아웃 계산 중간에 끼어들지 않는다.
// (처음에는 PeekMessageW를 썼는데, 그건 메시지 스레드라 패널을 그리는 화면 스레드와 달랐다)
var APP_GLOBAL = B.add(0x6365198), APP_VT = B.add(0x5601d58), tickInstalled = false;
function onFrameEnd() {
  var tid = Process.getCurrentThreadId();
  if (!uiTid) { uiTid = tid; send('ui thread ' + tid); }   // 소셜 패널을 열기 전에도 첫 프레임에서 화면 스레드 번호를 잡는다 (M28)
  else if (tid !== uiTid) return;                          // 화면 스레드에서만
  while (uiQueue.length) { try { (uiQueue.shift())(); } catch (e) { coreErr++; } }
  if (M24GA.on.frame.length) m24gaEmit('frame', null);
}
function installTick() {
  if (tickInstalled) return;
  try {
    var app = APP_GLOBAL.readPointer();
    if (app.isNull() || !app.readPointer().equals(APP_VT)) return;   // 아직 없거나 예상과 다르면 자동 갱신 없이 동작
    Interceptor.attach(app.readPointer().add(0x18).readPointer(), { onLeave: onFrameEnd });
    tickInstalled = true;
    send('auto refresh installed');
  } catch (e) { send('auto refresh install failed ' + e); tickInstalled = true; }
}
installTick();

// 소셜 패널 훅 (원래 645~657): 공통 처리 뒤 글자가 있는 패널만 모드에 넘긴다
Interceptor.attach(B.add(0x61ae70), { onEnter: function (a) {
  try {
    var th = a[0];
    var tid = Process.getCurrentThreadId();        // 패널을 그리는 스레드 = 화면 스레드
    if (tid !== uiTid) { uiTid = tid; send('ui thread ' + tid); }
    if (!tickInstalled) installTick();
    var type = th.add(0x1d8).readU32();
    var dst = th.add(0x1f0);
    var p = dst.readPointer();
    if (p.isNull()) return;
    var len = p.readU32();
    if (len === 0 || len > 4000) return;
    m24gaEmit('socialPanel', { th: th, type: type, dst: dst, text: p.add(4).readUtf8String(len) });
  } catch (e) { coreErr++; }
}});

// ---- 받은 편지함 메일 (코어 0.34.0, M51·M52, 기능 ui.inbox) ----
// 게임의 '감독끼리 보내는 메시지'(HUMAN_MESSAGE_NEWS)를 만들어 게임이 평소 뉴스를 넣는 함수(news.add)에 넘긴다 (news.add가 사본을 가져간다).
// 받은 편지함에 '보낸이의 말: 제목'으로 보이고 저장·불러오기·진행 뒤에도 남는다 (M51 실기). 보낸이는 아무 사람(사람 감독·스태프·선수)의
// PERSON 부분(객체 시작 + [[시작+8]+4] + 8: 사람 감독 +0x450, 스태프 +0xf8). 사람 객체 자체를 넣으면 게임 함수가 접근 오류를 낸다.
// 글은 게임 할당기(str.alloc)로 만든다: Frida 메모리는 로더를 끄면 사라져서 게임이 나중에 글을 읽다 튕긴다.
// 받는 사람 = 내 감독이 맡은 팀(human.job +0x10)의 감독 = 나. 무직이면 넣지 못한다. 메일의 '응답' 버튼은 싱글에서 보내도 아무 일 없다 (M52 실기).
// 온라인 전용 fm+0x3491790(접속 감독 모두에게)은 싱글에서 부르면 접근 오류라 쓰지 않는다.
var INBOX_FN = null, NEWS_MGR = B.add(0x63651c0), HUMAN_MSG_VT = B.add(0x5ac0d78), INBOX_TITLE_MAX = 200, INBOX_BODY_MAX = 8000;
var INBOX_FN_NAMES = ['news.itemInit', 'news.itemFree', 'news.humanMsgFill', 'news.add', 'str.alloc', 'str.free'];
function inboxFns() {
  if (INBOX_FN) return INBOX_FN;
  var a = {};
  for (var i = 0; i < INBOX_FN_NAMES.length; i++) { var st = funcCheck(INBOX_FN_NAMES[i]); if (!st.ok) return { error: st.error }; a[INBOX_FN_NAMES[i]] = st.addr; }
  INBOX_FN = {
    init: new NativeFunction(a['news.itemInit'], 'void', ['pointer']),
    free: new NativeFunction(a['news.itemFree'], 'void', ['pointer']),
    fill: new NativeFunction(a['news.humanMsgFill'], 'void', ['pointer', 'pointer', 'pointer', 'pointer']),
    add: new NativeFunction(a['news.add'], 'int', ['pointer', 'pointer', 'pointer', 'uint32']),
    alloc: new NativeFunction(a['str.alloc'], 'pointer', ['uint32', 'uint32']),
    strFree: new NativeFunction(a['str.free'], 'void', ['pointer'])
  };
  return INBOX_FN;
}
// 게임 할당기로 참조 계수 문자열을 만든다: 블록 [계수 u32][길이 u32][UTF-8][0], 반환 = 글 칸에 넣는 주소(블록+4), 계수 1 = 우리 몫
function gameStrNew(F, s) {
  var b = utf8Bytes(s), n = b.byteLength, blk = F.alloc(0x108, n);
  if (blk.isNull()) throw new Error('게임 할당기가 글 자리를 주지 않았어요');
  blk.writeU32(1); blk.add(4).writeU32(n); if (n) blk.add(8).writeByteArray(b); blk.add(8 + n).writeU8(0);
  return blk.add(4);
}
function gameStrRelease(F, p) { var c = p.sub(4), v = c.readU32() - 1; c.writeU32(v); if (v === 0) F.strFree(c); }
// 사람 객체(어느 부분을 가리켜도) -> 그 사람의 PERSON 부분 (보낸이 칸에 넣는 것). 사람이 아니면 null
function personPart(p) {
  try {
    var info = rttiInfo(p); if (!info) return null;
    if (info.name !== 'db::PERSON' && (info.bases || []).indexOf('db::PERSON') < 0) return null;
    var top = info.top, off = top.add(8).readPointer().add(4).readS32();
    if (off <= 0 || off > 0x4000) return null;
    var s = top.add(off + 8), si = rttiInfo(s);
    return (si && si.top.equals(top)) ? s : null;
  } catch (e) { return null; }
}
function myTeamObj() {
  try { var h = myHuman(); if (!h) return null; var j = h.add(0x518).readPointer(); if (j.isNull()) return null; var t = j.add(0x10).readPointer(); return className(t) === 'db::TEAM' ? t : null; } catch (e) { return null; }
}
// 화면 스레드에서 메일 하나를 넣는다. o = { title, body, from(사람 객체, 없으면 내 감독) } -> { ok, error? }
function inboxSendNow(o) {
  var F = inboxFns(); if (F.error) return { ok: false, error: F.error };
  var title = String(o.title || '').trim().slice(0, INBOX_TITLE_MAX), body = String(o.body || '').slice(0, INBOX_BODY_MAX);
  if (!title) return { ok: false, error: '제목(title)이 비었어요' };
  var mgr = NEWS_MGR.readPointer();
  if (mgr.isNull() || className(mgr) !== 'NEWS_MANAGER') return { ok: false, error: '세이브를 불러온 뒤에만 넣을 수 있어요' };
  var team = myTeamObj(); if (!team) return { ok: false, error: '감독이 맡은 팀이 없어요 (무직이면 받은 편지함에 넣지 못해요)' };
  var from = (o.from === undefined || o.from === null || o.from === 'me') ? myHuman() : o.from;
  var snd = from ? personPart(from) : null;
  if (!snd) return { ok: false, error: '보낸이(from)는 사람 객체여야 해요 (myHuman(), personByName(이름).person 등)' };
  var n = Memory.alloc(0x400);
  F.init(n); n.writePointer(HUMAN_MSG_VT);
  if (className(n) !== 'HUMAN_MESSAGE_NEWS') { F.free(n); return { ok: false, error: '이 게임 빌드에서는 메시지 종류(HUMAN_MESSAGE_NEWS)를 찾지 못했어요' }; }
  var t = gameStrNew(F, title), b = gameStrNew(F, body), slot = Memory.alloc(16), ret;
  slot.writePointer(t); slot.add(8).writePointer(b);
  try {
    F.fill(n, snd, slot, slot.add(8));
    n.add(0xa0).writeU32(GAME_DATE.readU32());
    ret = F.add(mgr, n, team, 1);
  } finally { F.free(n); gameStrRelease(F, t); gameStrRelease(F, b); }
  return { ok: true, ret: ret, title: title, chars: body.length };
}
// ---- 이벤트 newsAdded·gameSaved (코어 0.35.0, M53, 기능 event.newsAdded·event.gameSaved) ----
// newsAdded: 게임이 뉴스 하나를 넣을 때마다 (news.add, 하루 수백 번: 경기 보고·이적·부상·언론 의견…). 모드가 처음 구독할 때 끼어든다.
//   ev = { cls(뉴스 클래스 이름), flags, toInbox(flags&7), team(받는 팀, 없으면 null), mine(내 팀 앞), text() }. text()는 게임의 본문 글(평문)을
//   만든다 (비싸서 필요한 것만, 콜백 안에서만 됨). 받는 사람의 PERSON 부분(= NEWS_CTX)을 글 문맥으로 쓴다.
//   모드가 api.inbox.send로 넣은 메일은 화면 스레드 콜백 안에서 부르므로 Frida가 끼어들기를 건너뛰어 이 이벤트가 안 온다 (되먹임 없음).
//   (코어 0.37.0) ev.id(뉴스 번호), ev.date('YYYY-MM-DD'), ev.refs() = 관련 기록 { people, teams, clubs, comps, refs:[dref] } (콜백 안에서만).
// matchEnded (코어 0.37.0): 경기 보고 뉴스가 나온 경기마다 한 번. ev = { home, away(팀), homeGoals, awayGoals, comp, stadium(0.39.0), mine, date, text() }
// gameSaved: 게임 저장(save.write)이 끝난 뒤 (파일 쓰기 완료). ev = { ms(걸린 시간), save }.
var EVENT_HOOKS = {};
function newsPlainText(n) {
  var ctx = personPart(myHuman()); if (!ctx || !ctx.readPointer().equals(NEWS_CTX_VT)) return '';
  var nv = n.readPointer(); if (nv.compare(B) < 0 || nv.compare(MEND) >= 0) return '';
  var o = Memory.alloc(0x10); o.writePointer(ptr(0));
  buildBody(n, o, ctx, 1, 1);
  var h = o.readPointer(); if (h.isNull()) return '';
  var len = h.readU32(), s = (len > 0 && len < 40000) ? stripMarkup(h.add(4).readUtf8String(len)).trim() : '';
  // 만든 글의 참조는 놓지 않는다 (newsBody와 같음, 짧은 글이 조금 남을 뿐: 잘못 놓으면 나중에 튕길 수 있다)
  return s;
}
// (코어 0.37.0, M56) 뉴스의 관련 기록: 게임 함수 news.related(fm+0x26402d0)가 {dref} 값 목록을 만든다 (항목 첫 u32 = dref).
// 반환 { people, teams, clubs, comps, refs: [dref] }. 게임이 만든 목록 메모리는 놓지 않는다 (부를 때만 조금 남음 -> 필요할 때만)
var NEWS_REL_FN = null;
function newsRefs(n) {
  if (!NEWS_REL_FN) { var st = funcCheck('news.related'); if (!st.ok) return { error: st.error }; NEWS_REL_FN = new NativeFunction(st.addr, 'uint32', ['pointer', 'pointer']); }
  var v = Memory.alloc(0x20), out = { people: [], teams: [], clubs: [], comps: [], refs: [] };
  var cnt = NEWS_REL_FN(n, v), b = v.readPointer();
  if (b.isNull()) return out;
  var m = Math.min(cnt, v.add(8).readPointer().sub(b).toInt32() / 8, 64);
  for (var i = 0; i < m; i++) {
    var it = b.add(8 * i).readPointer(); if (it.isNull()) continue;
    var d = it.readU32() >>> 0; out.refs.push(d);
    var o = propDeref(d), k = d >>> 24; if (!o) continue;
    if (k === 0x01) out.people.push(o); else if (k === 0x18) out.teams.push(o); else if (k === 0x03) out.clubs.push(o); else if (k === 0x19) out.comps.push(o);
  }
  return out;
}
// 뉴스 날짜(+0xa0, 게임 날짜 형식). 게임이 사본에 날짜를 넣는 뉴스(이적 등)는 1900 -> 지금 게임 날짜
function newsDate(n) { var d = null; try { d = m24gaDecodeDate(n.add(0xa0).readU32()); } catch (e) {} if (!d || d.y <= 1900) d = M24GA.game && M24GA.game.date; return d ? d.iso : null; }
// 경기 보고 뉴스(MATCH_REPORT_NEWS, 경기마다 두 팀 쪽에서 하나씩, M56): +0xe0 이쪽 팀, +0xe8 상대, +0x100 대회, +0x108 경기장,
// +0x180 이쪽 골, +0x181 상대 골, +0x1d2 1 = 이쪽이 홈 / 2 = 원정. 홈 쪽 보고서에서만 matchEnded를 낸다 (한 경기에 한 번).
// 보고서가 나오는 경기만 (게임이 보도하는 리그·대회). 승부차기·연장 구분은 아직 없음
function matchFromReport(n) {
  if (className(n) !== 'MATCH_REPORT_NEWS') return null;
  var side = n.add(0x1d2).readU8(); if (side !== 1 && side !== 2) return null;
  var a = n.add(0xe0).readPointer(), b = n.add(0xe8).readPointer();
  if (className(a) !== 'db::TEAM' && className(a) !== 'db::NATIONAL_TEAM') return null;
  if (className(b) !== 'db::TEAM' && className(b) !== 'db::NATIONAL_TEAM') return null;
  var ga = n.add(0x180).readU8(), gb = n.add(0x181).readU8(); if (ga > 40 || gb > 40) return null;
  var comp = n.add(0x100).readPointer(); if (className(comp) !== 'db::COMP') comp = null;
  var st = n.add(0x108).readPointer(); if (className(st) !== 'db::STADIUM') st = null;
  return side === 1 ? { home: a, away: b, homeGoals: ga, awayGoals: gb, comp: comp, stadium: st, homeSide: true } : { home: b, away: a, homeGoals: gb, awayGoals: ga, comp: comp, stadium: st, homeSide: false };
}
function newsAddedEmit(n, t, f) {
  var cls = className(n); if (!cls) return;
  var myT = myTeamObj(), live = true, cache = null, refs = null;
  if (M24GA.on.newsAdded.length) {
    var ev = { cls: cls, flags: f, toInbox: (f & 7) !== 0, team: t.isNull() ? null : t, mine: !!(myT && !t.isNull() && t.equals(myT)),
      id: n.add(0xa8).readU32(), date: newsDate(n),
      text: function () { if (!live) return ''; if (cache === null) { try { cache = newsPlainText(n); } catch (e) { cache = ''; } } return cache; },
      refs: function () { if (!live) return null; if (refs === null) { try { refs = newsRefs(n); } catch (e) { refs = { error: String(e) }; } } return refs; } };
    m24gaEmit('newsAdded', ev);
  }
  if (M24GA.on.matchEnded.length && cls === 'MATCH_REPORT_NEWS') {
    var m = null; try { m = matchFromReport(n); } catch (e) {}
    if (m && m.homeSide) {
      var mine = !!(myT && (m.home.equals(myT) || m.away.equals(myT)));
      m24gaEmit('matchEnded', { home: m.home, away: m.away, homeGoals: m.homeGoals, awayGoals: m.awayGoals, comp: m.comp, stadium: m.stadium, mine: mine, date: newsDate(n),
        text: function () { if (!live) return ''; if (cache === null) { try { cache = newsPlainText(n); } catch (e) { cache = ''; } } return cache; } });
    }
  }
  live = false;
}
M24GA.eventHook = function (ev) {
  if (EVENT_HOOKS[ev]) return true;
  var st;
  if (ev === 'newsAdded' || ev === 'matchEnded') {   // 둘 다 news.add 끼어들기 하나를 같이 쓴다
    if (EVENT_HOOKS.newsAdded || EVENT_HOOKS.matchEnded) { EVENT_HOOKS[ev] = EVENT_HOOKS.newsAdded || EVENT_HOOKS.matchEnded; return true; }
    st = funcCheck('news.add'); if (!st.ok) { coreErr++; return false; }
    EVENT_HOOKS[ev] = Interceptor.attach(st.addr, {
      onEnter: function (a) { if (!M24GA.on.newsAdded.length && !M24GA.on.matchEnded.length) return; this.go = true; this.n = a[1]; this.t = a[2]; this.f = a[3].toUInt32(); },
      onLeave: function () { if (!this.go) return; try { newsAddedEmit(this.n, this.t, this.f); } catch (e) { coreErr++; } }
    });
  } else if (ev === 'gameSaved') {
    st = funcCheck('save.write'); if (!st.ok) { coreErr++; return false; }
    EVENT_HOOKS[ev] = Interceptor.attach(st.addr, {
      onEnter: function () { this.t0 = Date.now(); },
      onLeave: function () { if (!M24GA.on.gameSaved.length) return; var g = {}; try { g = M24GA.readGame() || {}; } catch (e) {}
        try { m24gaEmit('gameSaved', { ms: Date.now() - this.t0, save: g.save || null }); } catch (e) { coreErr++; } }
    });
  } else return false;
  return true;
};

M24GA.inboxSend = function (o) { return runOnUi(function () { return inboxSendNow(o || {}); }).then(function (r) { return r && r.error && r.ok === undefined ? { ok: false, error: r.error } : r; }); };

// ---- 게임 안 패널 (코어 0.23.0, M45, 기능 ui.panel) ----
// 모드의 양식 -> m24gaPanelXml(modhost.js) -> FM 사용자 폴더의 패널 칸(panels/m24ga/slotNN.xml, 로더가 게임보다 먼저 만듦, loader/panels.py)에
// 쓰기 -> 게임의 일반 대화상자(sitoolkit::DIALOG)로 띄우기. 게임은 띄울 때 파일을 다시 읽는다 (M43 실기). 파일 읽기 함수에 끼어들지 않는다.
// 이벤트: 안쪽 위젯 이벤트가 부모로 올라와 DIALOG 처리기(ui.dialogHandler)를 지난다 -> 우리 대화상자 것만 모드로 (패널이 열려 있을 때만 건다).
// 닫기·열기는 늘 화면 스레드의 다음 프레임(runOnUi)에서 한다 (게임이 이벤트를 처리하는 도중에 대화상자를 없애지 않게).
var PANEL_FN = null, PANEL_SLOT = {}, PANEL_HOOK = null;
var EV_CANC = 0x63616e63, EV_KILL = 0x6b696c6c, FOURCC_FILE = 0x66696c65;
var PANEL_FN_NAMES = ['ui.strFromC', 'ui.strFree', 'ui.recordWith', 'ui.eventFree', 'ui.eventNew', 'ui.dialogClass', 'ui.widgetCreate', 'ui.widgetSetOwner', 'ui.dialogShow', 'ui.dialogHandler'];
function panelFns() {
  if (PANEL_FN) return PANEL_FN;
  var a = {};
  for (var i = 0; i < PANEL_FN_NAMES.length; i++) { var st = funcCheck(PANEL_FN_NAMES[i]); if (!st.ok) return { error: st.error }; a[PANEL_FN_NAMES[i]] = st.addr; }
  PANEL_FN = {
    strFromC: new NativeFunction(a['ui.strFromC'], 'pointer', ['pointer', 'pointer']),
    strFree: new NativeFunction(a['ui.strFree'], 'void', ['pointer']),
    recordWith: new NativeFunction(a['ui.recordWith'], 'pointer', ['pointer', 'uint32', 'pointer']),
    recFree: new NativeFunction(a['ui.eventFree'], 'void', ['pointer']),
    eventNew: new NativeFunction(a['ui.eventNew'], 'pointer', ['pointer', 'uint32', 'uint32']),
    dialogClass: new NativeFunction(a['ui.dialogClass'], 'pointer', []),
    create: new NativeFunction(a['ui.widgetCreate'], 'pointer', ['pointer', 'pointer', 'pointer', 'pointer']),
    setOwner: new NativeFunction(a['ui.widgetSetOwner'], 'void', ['pointer', 'pointer']),
    show: new NativeFunction(a['ui.dialogShow'], 'void', ['pointer', 'uint8', 'uint8']),
    handler: a['ui.dialogHandler']
  };
  return PANEL_FN;
}
function panelSlotName(i) { return 'slot' + ('0' + i).slice(-2); }
function panelReady() {
  if (!M24_PANEL_DIR) return { ok: false, error: '게임 안 패널 칸이 없어요 (로더가 FM 사용자 폴더에 만든 뒤 게임을 다시 켜야 해요)' };
  var F = panelFns(); if (F.error) return { ok: false, error: F.error };
  return { ok: true };
}
function utf8Bytes(s) { var p = Memory.allocUtf8String(s), n = 0; while (p.add(n).readU8() !== 0) n++; return p.readByteArray(n); }
// 칸 파일 쓰기: Frida File은 한글 경로(예: OneDrive\문서)를 못 열어서 Windows 유니코드 API(CreateFileW)로 쓴다 (M45 실기)
var W32F = null;
function panelWriteSlot(i, xml) {
  if (!W32F) {
    var k = Process.getModuleByName('kernel32.dll');
    W32F = { open: new NativeFunction(k.getExportByName('CreateFileW'), 'pointer', ['pointer', 'uint32', 'uint32', 'pointer', 'uint32', 'uint32', 'pointer']),
      write: new NativeFunction(k.getExportByName('WriteFile'), 'int', ['pointer', 'pointer', 'uint32', 'pointer', 'pointer']),
      close: new NativeFunction(k.getExportByName('CloseHandle'), 'int', ['pointer']),
      err: new NativeFunction(k.getExportByName('GetLastError'), 'uint32', []) };
  }
  var path = (M24_PANEL_DIR + panelSlotName(i) + '.xml').replace(/\//g, '\\');
  var h = W32F.open(Memory.allocUtf16String(path), 0x40000000, 0, ptr(0), 2, 0x80, ptr(0));   // GENERIC_WRITE, CREATE_ALWAYS, NORMAL
  if (h.equals(ptr(-1))) throw new Error('CreateFileW 실패 ' + W32F.err() + ' (' + path + ')');
  try {
    var bytes = utf8Bytes(xml), buf = Memory.alloc(bytes.byteLength + 1), done = Memory.alloc(4);
    buf.writeByteArray(bytes);
    if (!W32F.write(h, buf, bytes.byteLength, done, ptr(0)) || done.readU32() !== bytes.byteLength) throw new Error('WriteFile 실패 ' + W32F.err());
  } finally { W32F.close(h); }
}
function panelByDlg(d) { for (var k in PANEL_SLOT) { var p = PANEL_SLOT[k]; if (p.dlg && p.dlg.equals(d)) return p; } return null; }
function panelHookOn() {
  if (PANEL_HOOK) return;
  PANEL_HOOK = Interceptor.attach(PANEL_FN.handler, { onEnter: function (a) {
    if (!Object.keys(PANEL_SLOT).length) return;
    var p = panelByDlg(a[0]); if (!p) return;
    try { panelEvent(p, a[1].toUInt32()); } catch (e) { coreErr++; }
  } });
}
function panelHookOffIfIdle() {
  pickHooksOffIfIdle();
  if (PANEL_HOOK && !Object.keys(PANEL_SLOT).length) setTimeout(function () { if (PANEL_HOOK && !Object.keys(PANEL_SLOT).length) { PANEL_HOOK.detach(); PANEL_HOOK = null; } }, 0);
}
function panelCall(p, ev) {   // 모드 콜백 (모드 오류는 모드 안에서)
  if (!p.cb || m24gaOff(p.mod)) return;
  ev.panel = p.handle; ev.values = function () { return panelValues(p); };
  try { p.cb(ev); } catch (e) { m24gaModError(p.mod, 'panel ' + (ev.id || ev.kind), e); }
}
function panelEvent(p, code) {
  if (code === EV_KILL) {   // 대화상자가 닫혀 없어진다 (확인 버튼, canc, 화면 바뀜)
    if (p.refreshing && p.next) {   // 다시 그리기: 같은 칸·같은 손잡이로 새 양식을 띄운다 (모드에는 닫힘을 알리지 않음)
      var nx = p.next; p.refreshing = false; p.next = null; p.dlg = null; p.state = 'opening';
      try { panelWriteSlot(p.slot, nx.xml); } catch (e) { p.state = 'closed'; delete PANEL_SLOT[p.slot]; panelCall(p, { id: 'close', kind: 'close' }); panelHookOffIfIdle(); return; }
      p.events = nx.events; p.fields = panelFields(p.form, nx);
      panelShow(p, true);
      return;
    }
    p.state = 'closed'; p.dlg = null; delete PANEL_SLOT[p.slot];
    panelCall(p, { id: 'close', kind: 'close' });
    panelHookOffIfIdle();
    return;
  }
  var info = p.events[fourcc(code)]; if (!info) return;
  if (info.kind === 'select') {   // 드롭다운은 이벤트 때 아직 고른 글이 안 바뀌어 있다 (M45 실기) -> 다음 프레임에 값과 함께
    runOnUi(function () { if (p.state === 'open') panelCall(p, { id: info.id, kind: info.kind, value: panelValue(p, info.id) }); });
    return;
  }
  panelCall(p, { id: info.id, kind: info.kind, value: info.kind === 'button' ? null : panelValue(p, info.id) });
}
function panelFind(p, wid) {   // 대화상자 안에서 위젯 id(4글자)로 찾기
  if (!p.dlg) return null;
  var code = 0; for (var i = 0; i < 4; i++) code = ((code << 8) | wid.charCodeAt(i)) >>> 0;
  var stack = [[p.dlg, 0]];
  while (stack.length) {
    var x = stack.pop(), w = x[0];
    try { if (w.add(0x5c).readU32() === code) return w; } catch (e) { continue; }
    if (x[1] < 12) uiKids(w).forEach(function (k) { stack.push([k, x[1] + 1]); });
  }
  return null;
}
function panelValue(p, fid) {
  var f = p.fields[fid]; if (!f) return null;
  if (f.kind === 'pick') {   // 고른 것 > (안 골랐으면) 친 글 { text } > null
    if (p.picks[fid]) return pickOut(p.picks[fid]);
    var tx = p.state === 'open' ? pickBoxText(p, f) : '';
    return tx ? { text: tx } : (p.prefill && p.prefill[fid]) || null;
  }
  if (p.state !== 'open') return null;
  var w = panelFind(p, f.w); if (!w) return null;
  try {
    if (f.kind === 'check') return (w.add(0x78).readU32() & 0x10) !== 0;
    var t = uiText(w, className(w)).join('');
    if (f.kind === 'select') { var i = f.labels.indexOf(t); return i >= 0 ? f.options[i] : null; }
    if (f.type === 'number') { var v = parseFloat(String(t).replace(/,/g, '')); if (!isFinite(v)) return null; if (f.min !== undefined && v < f.min) return null; if (f.max !== undefined && v > f.max) return null; return v; }
    return t;
  } catch (e) { return null; }
}
function pickBoxText(p, f) {   // 검색칸 안 글 칸(EDIT_BOX)의 글
  try {
    var w = panelFind(p, f.w); if (!w) return '';
    var stack = [[w, 0]];
    while (stack.length) { var x = stack.pop(); if (className(x[0]) === 'EDIT_BOX') return uiText(x[0], 'EDIT_BOX').join('').trim(); if (x[1] < 4) uiKids(x[0]).forEach(function (k) { stack.push([k, x[1] + 1]); }); }
  } catch (e) {}
  return '';
}
function panelValues(p) { var o = {}; for (var k in p.fields) if (p.fields[k].kind !== 'button' && p.fields[k].kind !== 'label') o[k] = panelValue(p, k); return o; }
function panelSendClose(p) {   // 화면 스레드에서: 'canc' 이벤트를 대화상자 전달 함수(vtable +0x20)로 (M43 실기: 닫힘)
  if (!p.dlg || className(p.dlg) !== 'sitoolkit::DIALOG') return false;
  var F = PANEL_FN, ev = Memory.alloc(0x40);
  F.eventNew(ev, EV_CANC, 0);
  var r = new NativeFunction(p.dlg.readPointer().add(0x20).readPointer(), 'uint8', ['pointer', 'pointer'])(p.dlg, ev);
  F.recFree(ev);
  return !!r;
}
function panelClose(p, tries) {
  if (p.state === 'closed') return;
  if (p.state === 'opening') { p.closeAfterOpen = true; return; }
  tries = tries || 0;
  // 대화상자가 여러 개면 게임은 맨 위 것의 'canc'만 처리한다 (C04 실기: 둘을 한 프레임에 닫으면 하나가 남음) -> 남았으면 다음 프레임에 다시 (5번까지)
  runOnUi(function () {
    if (p.state !== 'open') return;
    var d = p.dlg;   // 다시 그린 새 대화상자는 닫지 않게 (코어 0.29.0)
    panelSendClose(p);
    if (tries < 5) setTimeout(function () { if (p.state === 'open' && p.dlg && d && p.dlg.equals(d)) panelClose(p, tries + 1); }, 150);
  });
}
// 모드가 부른다 (modhost m24gaPanelOpen을 거쳐). form = 양식 (m24gaPanelXml), cb(ev) = 이벤트 콜백.
// ev = { id: 필드·버튼 id 또는 'open'·'close'·'error', kind, value, values(), panel }. 반환 손잡이 { ok, error, slot, isOpen(), get(id), values(), close() }
function panelFields(form, x) {
  var fields = {};
  (form.fields || []).forEach(function (f) {
    if (!f || !f.id || !x.widgets[f.id]) return;
    var ev = x.events['me' + x.widgets[f.id].slice(2)] || {};
    fields[f.id] = { w: x.widgets[f.id], kind: ev.kind || 'label', type: f.type || 'text', min: f.min, max: f.max, table: ev.table,
      options: ev.options || [], labels: (f.options || []).map(function (o) { return String((o && typeof o === 'object') ? (o.label !== undefined ? o.label : o.value) : o); }) };
  });
  return fields;
}
function panelHasPick(p) { for (var k in p.fields) if (p.fields[k].kind === 'pick') return true; return false; }
function panelOpen(mod, form, cb) {
  var rd = panelReady(); if (!rd.ok) return rd;
  var x = m24gaPanelXml(form); if (!x.ok) return x;
  var slot = 0; for (var i = 1; i <= M24_PANEL_SLOTS; i++) if (!PANEL_SLOT[i]) { slot = i; break; }
  if (!slot) return { ok: false, error: '열린 게임 안 패널이 너무 많아요 (' + M24_PANEL_SLOTS + '개까지)' };
  var fields = panelFields(form, x), picks = {}, prefill = {};
  for (var fk in fields) if (fields[fk].kind === 'pick') {
    if (!pickHooksReady()) return { ok: false, error: '사람·구단 검색칸을 못 써요 (이 게임 빌드에서 검색칸 함수를 찾지 못함)' };
    var fv = (form.fields || []).filter(function (f) { return f && f.id === fk; })[0].value;   // 이미 고른 것 { ref | uid }
    var pre = fv && typeof fv === 'object' ? pickResolve(fields[fk].table, fv) : null;
    if (pre) picks[fk] = pre;
    else if (fv && typeof fv === 'object') prefill[fk] = fv;   // 표가 아직 없어서 못 찾으면 받은 값 그대로 돌려준다
  }
  try { panelWriteSlot(slot, x.xml); } catch (e) { return { ok: false, error: '패널 칸 파일을 쓰지 못했어요: ' + (e.message || e) }; }
  var p = { slot: slot, mod: mod, cb: typeof cb === 'function' ? cb : null, state: 'opening', dlg: null, events: x.events, fields: fields, form: form, picks: picks, prefill: prefill };
  p.handle = { ok: true, slot: slot,
    isOpen: function () { return p.state === 'open'; },
    get: function (fid) { return panelValue(p, fid); },
    values: function () { return panelValues(p); },
    close: function () { p.refreshing = false; panelClose(p); } };
  PANEL_SLOT[slot] = p;
  panelShow(p, false);
  return p.handle;
}
// 대화상자를 만들어 띄운다 (처음 열 때와 다시 그릴 때). quiet = 다시 그리기 (모드에 'open'을 다시 보내지 않음)
function panelShow(p, quiet) {
  var slot = p.slot;
  function fail(msg) { if (PANEL_SLOT[slot] === p) delete PANEL_SLOT[slot]; p.state = 'closed'; panelCall(p, { id: 'error', kind: 'error', error: msg }); panelHookOffIfIdle(); }
  runOnUi(function () {
    if (p.state !== 'opening') return;
    var stage = 'start';
    try {
    if (gameBusy()) return fail('게임이 진행 중이라 패널을 열지 않았어요 (멈춘 뒤 다시)');
    var F = PANEL_FN, cl = uiClients()[0]; if (!cl) return fail('게임 화면을 찾지 못했어요');
    var root = cl.add(0x58).readPointer();
    var str = Memory.alloc(0x20), rec = Memory.alloc(0x40), cpath = Memory.allocUtf8String('m24ga/' + panelSlotName(slot));
    stage = 'strFromC'; F.strFromC(str, cpath);
    stage = 'recordWith'; F.recordWith(rec, FOURCC_FILE, str);
    stage = 'create'; var dlg = F.create(cl, ptr(0), F.dialogClass(), rec);
    stage = 'free'; F.recFree(rec);   // 문자열(str)은 속성 묶음이 가져가므로 따로 놓지 않는다 (놓으면 0번지 접근, M45 실기. 게임 코드 fm+0xae71d0도 같음)
    if (dlg.isNull() || className(dlg) !== 'sitoolkit::DIALOG') return fail('대화상자를 만들지 못했어요');
    stage = 'hook'; panelHookOn(); if (panelHasPick(p)) pickHooksOn();
    stage = 'setOwner'; F.setOwner(dlg, root);
    p.dlg = dlg;
    stage = 'show'; F.show(dlg, 1, 1);
    } catch (e) { return fail('패널을 여는 중 오류 (' + stage + '): ' + (e.message || e)); }
    runOnUi(function () {   // 다음 프레임에 확인: 우리 파일을 읽었으면 닫기 버튼('ok')이 있다. 없으면 빈 틀이니 닫는다 (M43)
      if (p.state !== 'opening') return;
      if (!findOk(dlg)) { p.state = 'open'; panelSendClose(p); return fail('패널 파일을 게임이 읽지 못했어요 (게임을 켠 뒤 칸 파일이 생겼으면 게임을 다시 켜 주세요)'); }
      p.state = 'open';
      if (!quiet) panelCall(p, { id: 'open', kind: 'open' });
      if (p.closeAfterOpen) panelSendClose(p);
    });
  }).then(function (r) { if (r && r.error && p.state === 'opening') fail(r.error); });
}
// ---- 사람·구단 검색칸 (코어 0.29.0, C09) ----
// 게임 검색칸(DB_RECORD_SEARCH_BOX)은 칠 때마다 'SeRq'(검색 요청)를 받는다 -> 지금 쓰는 칸을 기억한다.
// 후보 목록(GAME_PREDICTIVE_SEARCH_LIST)에서 고르면 'itsl'이 오고, 이벤트 기록 slct.item(+0x68)에 고른 줄의 ID(dref)가 있다
// (사람 0x01xxxxxx = persons/staff 번호, 구단 0x03xxxxxx = 구단 번호). 맨 위 머리 줄은 'NULL'이라 무시한다. 둘 다 읽기만 하는 걸기.
// 우리 창의 칸이 아니면(게임 자체 검색창) 아무것도 하지 않는다.
var EV_SERQ = 0x53655271, EV_ITSL = 0x6974736c, PICK_HOOK = null, PICK_ACTIVE = null;
function pickHooksReady() { return funcCheck('ui.searchBoxHandler').ok && funcCheck('ui.searchListHandler').ok; }
function pickHooksOn() {
  if (PICK_HOOK || !pickHooksReady()) return;
  PICK_HOOK = [
    Interceptor.attach(funcCheck('ui.searchBoxHandler').addr, { onEnter: function (a) { if (a[1].toUInt32() === EV_SERQ) PICK_ACTIVE = a[0]; } }),
    Interceptor.attach(funcCheck('ui.searchListHandler').addr, { onEnter: function (a) { if (a[1].toUInt32() === EV_ITSL) { try { pickSelected(a[2]); } catch (e) { coreErr++; } } } })
  ];
}
function pickHooksOffIfIdle() {
  if (!PICK_HOOK) return;
  for (var k in PANEL_SLOT) if (panelHasPick(PANEL_SLOT[k])) return;
  var h = PICK_HOOK; PICK_HOOK = null; PICK_ACTIVE = null;
  setTimeout(function () { h.forEach(function (x) { try { x.detach(); } catch (e) {} }); }, 0);
}
function evRecGet(rec, key) {   // sicore 기록 [시작][끝] 안 16바이트 [4글자 키][값 포인터] -> 값 포인터 (값 = [종류][내용 8바이트])
  var b = rec.readPointer(), e = rec.add(8).readPointer(), n = e.sub(b).toInt32() / 16;
  if (n < 0 || n > 64) return null;
  for (var i = 0; i < n; i++) { var ent = b.add(16 * i); if (fourcc(ent.readU32()) === key) return ent.add(8).readPointer(); }
  return null;
}
function pickResolve(table, x) {   // 고른 것 -> 정보. x = dref 숫자 또는 { ref } / { uid }
  if (table === 'person') {
    var o = null;
    if (typeof x === 'number') { if ((x >>> 24) !== 0x01) return null; var ix = x & 0xffffff; o = lookup(staff, ix, STAFF_VT) || lookup(persons, ix, PERSON_VT); }
    else if (x && x.ref) o = personByRef(x.ref);
    if (!o) return null;
    var inf = personInfo(o); inf.type = 'person'; return inf;
  }
  var c = null;
  if (typeof x === 'number') { if ((x >>> 24) !== 0x03) return null; c = clubByIndex(x & 0xffffff); }
  else if (x && x.uid !== undefined) c = clubByUid(x.uid);
  if (!c) return null;
  return { type: 'club', club: c, uid: clubUid(c), name: getField(c, 'club.name') || null };
}
function pickOut(i) { var o = {}; for (var k in i) o[k] = i[k]; o.label = i.type === 'person' ? [i.name, i.age ? i.age + '세' : null, i.club || (i.club === '' ? '무소속' : null)].filter(function (s) { return s; }).join(' · ') : i.name; return o; }
function pickSelected(ev) {
  if (!PICK_ACTIVE) return;
  var hit = null;
  for (var k in PANEL_SLOT) {
    var p = PANEL_SLOT[k]; if (p.state !== 'open') continue;
    for (var fid in p.fields) { var f = p.fields[fid]; if (f.kind !== 'pick') continue; var w = panelFind(p, f.w); if (w && w.equals(PICK_ACTIVE)) { hit = { p: p, fid: fid, f: f }; break; } }
    if (hit) break;
  }
  if (!hit) return;   // 게임 자체 검색칸
  var slct = evRecGet(ev, 'slct'); if (!slct) return;
  var item = evRecGet(slct.add(8).readPointer(), 'item'); if (!item) return;
  var dref = item.add(8).readPointer().add(0x68).readU32() >>> 0;
  var info = pickResolve(hit.f.table, dref); if (!info) return;   // 머리 줄('NULL') 등
  hit.p.picks[hit.fid] = info;
  var P = hit.p;
  runOnUi(function () {
    if (P.state !== 'open') return;
    panelCall(P, { id: hit.fid, kind: 'pick', value: pickOut(info) });
    if (P.form.refreshOnPick !== false && P.state === 'open') panelRefresh(P);
  });
}
// 고른 것을 창에 보이려고 같은 칸에 다시 그린다 (게임 검색칸 글을 바꾸는 함수를 몰라서). 다른 칸의 지금 값은 그대로 옮긴다
function panelRefresh(p) {
  if (p.state !== 'open') return;
  var vals = panelValues(p);
  var form = {}; for (var k in p.form) form[k] = p.form[k];
  form.fields = (p.form.fields || []).map(function (f) {
    var g = {}; for (var k2 in f) g[k2] = f[k2];
    if (!f || !f.id || !(f.id in p.fields)) return g;
    var fk = p.fields[f.id];
    if (fk.kind === 'pick') { if (p.picks[f.id]) g.value = pickOut(p.picks[f.id]); }
    else if (fk.kind !== 'button' && fk.kind !== 'label') { var v = vals[f.id]; if (v !== null && v !== undefined) g.value = v; }
    return g;
  });
  var x = m24gaPanelXml(form); if (!x.ok) return;
  p.form = form; p.next = x; p.refreshing = true;
  panelClose(p);
}
function findOk(dlg) {   // 닫기 버튼(id 'ok')이 있는가 = 우리 파일을 읽었는가 (없는 경로면 버튼 없는 빈 틀이 뜬다, M43)
  var stack = [[dlg, 0]];
  while (stack.length) {
    var x = stack.pop(), w = x[0], id = 0;
    try { id = w.add(0x5c).readU32(); } catch (e) { continue; }
    if ((id >>> 16) === 0x6f6b) return true;   // 'ok..'
    if (x[1] < 12) uiKids(x[0]).forEach(function (k) { stack.push([k, x[1] + 1]); });
  }
  return false;
}
M24GA.panelOpen = panelOpen;
M24GA.panelAvailable = function () { return panelReady().ok; };
M24GA.panelCloseMod = function (mod) {   // 모드를 내릴 때: 콜백을 끊고 그 모드의 패널을 닫는다
  for (var k in PANEL_SLOT) { var p = PANEL_SLOT[k]; if (p.mod === mod) { p.cb = null; panelClose(p); } }
};
M24GA.panelStats = function () { var o = []; for (var k in PANEL_SLOT) o.push({ slot: +k, mod: PANEL_SLOT[k].mod, state: PANEL_SLOT[k].state }); return { ready: panelReady(), open: o, hooked: !!PANEL_HOOK }; };

// 스크립트를 내리기 직전 정리 (M21 prepareunload, M43 dispose): 감시·예외 처리기 해제, 게이트 vtable 칸 되돌리기, 배율 표 풀기
function m24gaPrepareUnload() {
  var had = !!WATCH; watchStop('스크립트 내림'); wcallStop('스크립트 내림');
  // 처리기를 바로 내려야 하니, 감시했던 스레드의 디버그 레지스터를 한 번 더 지운다 (E02). 늦은 예외가 아직 오는 중이면 위험 → CLI는 excSet이 false가 된 뒤 끄라고 안내한다
  if (watchLast) Process.enumerateThreads().forEach(function (th) { if (watchLast.threads.indexOf(th.id) >= 0) { try { th.unsetHardwareWatchpoint(0); } catch (e) {} } });
  Object.keys(GATES).forEach(gateRelease);   // V03: vtable 칸을 원래대로
  Object.keys(SCALES).forEach(scaleRelease);   // V06: 배율 표 Interceptor
  if (EXC_SET) { try { Process.setExceptionHandler(null); EXC_SET = false; } catch (e) { EXC_ERR = String(e.message || e); } }
  return { watch: had, excSet: EXC_SET, excErr: EXC_ERR };
}
rpc.exports = {
  status: function () {   // 로더 표시용. 모드가 api.status로 낸 값을 합친다 (예전 키 이름 그대로)
    var s = { mods: M24GA.mods, mapsStarted: mapsStarted, mapsReady: mapsReady, clubs: Object.keys(clubs).length,
      persons: Object.keys(persons).length, newsCtx: !!newsCtx, bodies: Object.keys(bodies).length, uiTid: uiTid, coreErrs: coreErr, types: TYPES_FROM,
      gameDate: M24GA.game.date && M24GA.game.date.iso, save: M24GA.game.save };
    for (var id in M24GA.statusFns) { try { var m = M24GA.statusFns[id](); for (var k in m) s[k] = m[k]; } catch (e) {} }
    return s;
  },
  startmaps: function () { startMaps(); return true; },   // 이미 세이브 안에 있을 때 바로 표를 만들게 한다
  // 핫 리로드 (M09): 코어와 데이터 표는 그대로 두고 모드만 올리고 내린다
  loadmod: function (id, src) { return m24gaLoadMod(id, src); },
  undowrite: function (field, key, from, to) { return m24gaUndoWrite(field, key, from, to); },   // 쓰기 되돌리기 (M14)
  unloadmod: function (id) { return m24gaUnloadMod(id); },
  setsettings: function (id, vals) { return m24gaSetSettings(id, vals); },   // 앱에서 모드 설정이 바뀜 (M23)
  explore: function (spec, from, size) { return exploreObj(spec, from, size); },   // 객체 탐색 (M19, CLI explore)
  enginedump: function (name) { try { return engineDump(name); } catch (e) { return { error: String(e.message || e) }; } },   // 매치엔진 표 읽기 (E03, CLI engine dump)
  enginewrite: function (name, spec, force) { try { return engineWrite(name, spec, force); } catch (e) { return { error: String(e.message || e) }; } },   // 매치엔진 표 쓰기 (E03, CLI engine apply)
  getfield: function (spec, name) {   // CLI get (M20)
    var t = exploreResolve(spec); if (t.error) return t;
    try { var v = getField(t.p, name); return { path: t.path, name: name, value: (v && v.add) ? v.toString() : v, cls: className(t.p) }; } catch (e) { return { error: String(e.message || e) }; }
  },
  // (코어 0.41.0) Python 모드 ctx.actions_for / ctx.action. 확인·횟수 제한·기록은 Python(mods.py)이 한다
  actionsfor: function (spec, opts) { return M24GA.actionsFor(spec, opts || {}); },
  // (코어 0.42.0) Python 모드 ctx.set_prop. 기능(write.prop) 확인은 mods.py가 하고, 범위·기록·되돌리기·1분 제한은 m24gaWrite가 한다
  propset: function (id, spec, code, value, opts) { opts = opts || {}; opts.__py = true; return m24gaSetProp(String(id), spec, code, value, opts); },
  actionrun: function (id, spec, opts) { return M24GA.actionRun(id, spec, opts || {}).then(function (r) { return r && r.error !== undefined && r.ok === undefined ? { ok: false, error: r.error } : r; }); },
  props: function (spec, re, empty) {   // CLI props (M55): 대상이 답하는 속성 전부
    try {
      var o = propResolve(spec); if (!o) { var t = exploreResolve(spec); if (t.error) return t; o = t.p; }
      var tg = propTarget(o); if (!tg) return { error: '속성을 읽을 수 없는 객체예요 (' + (className(o) || '?') + ')' };
      var t0 = Date.now(), v = propsAll(o, { re: re || null, empty: !!empty });
      return { obj: o.toString(), cls: className(o), kind: tg.kind, ms: Date.now() - t0, props: JSON.parse(JSON.stringify(v)) };
    } catch (e) { return { error: String(e.message || e) }; }
  },
  propfind: function (spec, want) {   // CLI prop-find (M55): 값(숫자·글·날짜)이 들어 있는 속성 코드 찾기 (묶음·목록 안까지)
    try {
      var o = propResolve(spec); if (!o) { var t = exploreResolve(spec); if (t.error) return t; o = t.p; }
      var all = propsAll(o, {}), hits = [], w = String(want).toLowerCase();
      (function walk(v, path) {
        if (hits.length >= 200) return;
        if (v && typeof v === 'object') { for (var k in v) walk(v[k], path + (Array.isArray(v) ? '[' + k + ']' : '.' + k)); return; }
        var s = String(v).toLowerCase();
        if (s === w || (typeof v === 'string' && w.length >= 3 && s.indexOf(w) >= 0)) hits.push({ path: path, value: v });
      })(all, '');
      return { obj: o.toString(), cls: className(o), hits: hits.map(function (h) { return { code: h.path.slice(1, 5), path: h.path.slice(1), value: h.value }; }) };
    } catch (e) { return { error: String(e.message || e) }; }
  },
  findglobals: function (pattern, max) { return findGlobals(pattern, max); },   // CLI find-global (M24)
  findobjects: function (rvas, max, budget) { return findObjects(rvas, max, budget); },   // CLI find-objects (M24)
  findbytes: function (pat, opt) { return findBytes(pat, opt); },   // CLI find-bytes (E09)
  findrefs: function (spec, max, budget, back) { return findRefs(spec, max, budget, back); },   // CLI find-refs (M25)
  uitree: function (opts) { return uiTree(opts); },   // CLI ui tree (M25)
  uiact: function (opts) { return uiAct(opts); },     // CLI act (M28)
  uistate: function () { return contRefresh().then(function (r) { var st = uiState(); if (r && r.error) st.kindError = r.error; return st; }); },         // CLI ui state, act continue --wait (M30)
  uimail: function () { return uiMail(); },           // CLI ui mail, act reply (M31)
  findconst: function (code, max) { return findConst(code, max); },   // CLI find-const (M37)
  findtext: function (text, max, budget) { return findText(text, max, budget); },   // CLI find-text (M25)
  findfield: function (spec, q) { return findField(spec, q); },             // CLI find-field (M21)
  watchstart: function (spec, off, size, cond, max, secs) { return watchStart(spec, off, size, cond, max, secs); },   // CLI watch-write (M21)
  watchreport: function () { return watchReport(); },
  wcallstart: function (target, secs, max) { return wcallStart(target, secs, max); },   // CLI watch-call (M22)
  wcallreport: function () { return wcallReport(); },
  wcallstop: function () { wcallStop('사용자가 멈춤'); return wcallReport(); },
  gates: function () { var o = {}; for (var n in (M24_FUNCS.gates || {})) o[n] = GATES[n] ? gateStats(n) : null; return o; },   // CLI hooks (V03 게이트)
  hooks: function () {   // CLI hooks (M22): 걸린 끼어들기와 함수 서명 확인
    var chk = {}; funcNames().forEach(function (n) { var st = funcCheck(n); chk[n] = st.ok ? 'ok' : st.error; });
    return { hooks: m24gaHookStats(), installed: Object.keys(HOOK_LISTENERS), check: chk };
  },
  watchstop: function () { watchStop('사용자가 멈춤'); return watchReport(); },
  // 로더가 스크립트를 내리기 직전에 부른다 (M21): 감시를 풀고 예외 처리기를 지금 바로 해제한다
  prepareunload: m24gaPrepareUnload,
  // M43: Frida가 스크립트를 내리기 직전에 스스로 부른다 (로더 프로세스가 죽거나 연결이 끊겨 내려갈 때도).
  // prepareunload를 못 부른 채 내려가면 게이트가 바꾼 vtable 칸이 사라진 CModule 코드를 가리킨 채 남아 게임이 튕겼다 (0xC0000005).
  dispose: function () { try { m24gaPrepareUnload(); } catch (e) {} },
  rtti: function (addr) { var r = rttiInfo(addr); return r ? { name: r.name, off: r.off, top: r.top.toString(), bases: r.bases } : null; },
  mods: function () { return M24GA.mods; }
};

