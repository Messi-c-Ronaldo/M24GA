// 감독 커리어 모드 0.6.0 (C03 1차판, C04 관계 읽기, C05 좋아하는/싫어하는 구단, C06 좋아하는/싫어하는 사람, C08 같은 이름 고르기, C09 게임 검색칸). GPL-3.0-or-later.
// 게임 안 창(api.panel, 코어 0.23.0)으로 내 감독의 선수 시절 경력을 받고,
// - 고른 '과거 선수 경력' 단계를 감독 칸 human.pastPlayingExperience(+0x410)에 쓴다 (api.setField, 기록·되돌리기).
//   게임은 이 값을 구단 면접 질문 계산에 쓴다 (C01). 명성은 바꾸지 않는다 (게임이 만들 때 이미 계산함).
// - 적은 경력(구단·기간·출전·골·A매치·포지션·좋아하는/싫어하는 구단)은 Python 부분이 세이브 폴더 career.json에 보관한다.
// - 적은 경력으로 추천한 단계와 고른 단계가 두 단계 이상 다르면 확인 창을 띄운다.

var LEVELS = [   // 게임의 7단계 = 값 (C01 실측). 0 = 없음
  { value: 2750, label: '조기 축구회 선수' },
  { value: 3250, label: '세미프로 축구 선수' },
  { value: 4500, label: '프로 축구 선수 (지역 수준)' },
  { value: 5250, label: '프로 축구 선수 (해당 지역에서 유명)' },
  { value: 6000, label: '프로 축구 선수 (국가에서 유명)' },
  { value: 7000, label: '국제 (대륙간 대회 수준)' },
  { value: 8000, label: '국제 (글로벌 수준)' }
];
var POS = [{ value: 'GK', label: '골키퍼' }, { value: 'DF', label: '수비수' }, { value: 'MF', label: '미드필더' }, { value: 'FW', label: '공격수' }];

var cfg = api.settings(), panelBusy = false, askTries = 0;
var career = null, careerSave = null, asked = {}, panel = null, confirm = null, pending = null, lastMsg = '';

function levelOf(v) { for (var i = LEVELS.length - 1; i >= 0; i--) if (v >= LEVELS[i].value) return i; return -1; }
function levelLabel(v) { var i = levelOf(v); return i < 0 ? '없음' : LEVELS[i].label; }
function me() { return myHuman(); }
function curLevel() { var h = me(); return h ? getField(h, 'human.pastPlayingExperience') : null; }
function saveKey() { var s = saveInfo(); return s ? s.id + ':' + s.nonce : null; }

// 적은 경력으로 단계 추천 (대충의 기준: A매치 → 국제, 클럽 출전 수 → 프로 단계)
function suggest(c) {
  var caps = c.caps || 0, apps = c.apps || 0;
  if (caps >= 40) return 8000;
  if (caps >= 5) return 7000;
  if (apps >= 300) return 6000;
  if (apps >= 150) return 5250;
  if (apps >= 50) return 4500;
  if (apps >= 1) return 3250;
  if (c.club1) return 2750;
  return null;
}

// 게임이 아는 좋아하는/싫어하는 구단 (코어 0.25.0 humanRelations, 읽기만)
function gameClubs(withRefs) {
  var out = { fav: [], disliked: [] };
  if (withRefs) { out.favRefs = []; out.dislikedRefs = []; }
  try {
    humanRelations(me()).forEach(function (r) {
      var k = r.kindName === 'favClub' ? 'fav' : r.kindName === 'dislikedClub' ? 'disliked' : null;
      if (!k || !r.name) return;
      out[k].push(r.name);
      if (withRefs) { var u = null; try { u = clubUid(r.target); } catch (e) {} if (u !== null) out[k + 'Refs'].push({ uid: u, name: r.name }); }
    });
  } catch (e) {}
  return out;
}
// 0.6.0 (코어 0.29.0): 구단·사람 칸은 게임 검색칸. 창에 "지금: …"으로 보일 값 (고른 것 > 적은 이름 > 게임에 있는 구단)
function nowClub(c, kind, field, refs) {
  var p = c.pick && c.pick[kind];
  if (p && p.uid !== undefined && p.name === c[field]) return { uid: p.uid, name: p.name };
  if (c[field] !== undefined) return c[field] ? { name: c[field] } : undefined;
  return refs && refs[0] ? refs[0] : undefined;
}
function nowPerson(c, kind, field) {
  var p = c.pick && c.pick[kind];
  if (p && p.ref && p.name === c[field]) return { ref: p.ref, name: p.name, label: p.label };
  return c[field] ? { name: c[field] } : undefined;
}
// 검색칸 값 -> 경력 기록. 고른 것 {name, ref|uid} / 치기만 한 글 {text} (이름으로 찾기, 같은 이름이면 고르는 창) / 없음(예전 것 유지)
function takePick(v, kind, field, c, prev) {
  if (!v) {
    if (prev && prev[field]) { c[field] = prev[field]; if (prev.pick && prev.pick[kind]) (c.pick = c.pick || {})[kind] = prev.pick[kind]; }
    return;
  }
  if (v.text !== undefined) { if (v.text) c[field] = v.text; return; }
  if (!v.name) return;
  c[field] = v.name;
  if (v.ref || (v.uid !== undefined && v.uid !== null)) (c.pick = c.pick || {})[kind] = { name: v.name, ref: v.ref, uid: v.uid, label: v.label || v.name };
}

function form() {
  var h = me(), cur = curLevel();
  var name = h ? ((getField(h, 'human.lastName') || '') + ' ' + (getField(h, 'human.firstName') || '')).trim() : '';
  var c = career || {}, g = gameClubs(true);
  function n(v) { return v === undefined || v === null ? undefined : v; }
  var rel = (g.fav.length ? ' 게임의 좋아하는 구단: ' + g.fav.join(', ') + '.' : '') + (g.disliked.length ? ' 싫어하는 구단: ' + g.disliked.join(', ') + '.' : '');
  return {
    title: '감독 선수 시절 경력',
    text: (name ? name + ' 감독의 ' : '') + '선수 시절을 적어 주세요. 지금 게임의 과거 선수 경력: ' + levelLabel(cur || 0) + '. 단계를 고르지 않으면 지금 단계를 그대로 둬요.' + rel,
    width: 640,
    fields: [
      { id: 'level', type: 'select', label: '과거 선수 경력 단계 (고르지 않으면 그대로)', options: LEVELS },
      { id: 'pos', type: 'select', label: '주 포지션', options: POS },
      { id: 'club1', type: 'text', label: '뛴 구단과 기간 1 (예: FC 서울 2005-2012)', value: n(c.club1) },
      { id: 'club2', type: 'text', label: '뛴 구단과 기간 2', value: n(c.club2) },
      { id: 'apps', type: 'number', label: '클럽 통산 출전 (0~1500)', min: 0, max: 1500, value: n(c.apps) },
      { id: 'goals', type: 'number', label: '클럽 통산 골 (0~1000)', min: 0, max: 1000, value: n(c.goals) },
      { id: 'caps', type: 'number', label: 'A매치 출전 (0~250)', min: 0, max: 250, value: n(c.caps) },
      { id: 'intlGoals', type: 'number', label: 'A매치 골 (0~200)', min: 0, max: 200, value: n(c.intlGoals) },
      { id: 'retired', type: 'number', label: '은퇴한 해 (1950~2040)', min: 1950, max: 2040, value: n(c.retired) },
      { id: 'favClub', type: 'club', label: '좋아하는 구단 (치면 후보가 떠요)', value: nowClub(c, 'favClub', 'favClub', g.favRefs) },
      { id: 'hateClub', type: 'club', label: '싫어하는 구단', value: nowClub(c, 'dislikedClub', 'hateClub', g.dislikedRefs) },
      { id: 'favPerson', type: 'person', label: '옛 동료·은사 (좋아하는 사람)', value: nowPerson(c, 'favPerson', 'favPerson') },
      { id: 'hatePerson', type: 'person', label: '사이가 나쁜 사람 (싫어하는 사람)', value: nowPerson(c, 'dislikedPerson', 'hatePerson') },
      { id: 'clearRel', type: 'check', label: '위 구단·사람 칸 모두 비우기 (모드가 넣은 것은 게임에서도 빼요)' }
    ],
    buttons: [{ id: 'save', label: '저장' }],
    closeLabel: '닫기'
  };
}

function openPanel(why, kind) {
  if (panelBusy) return;   // 여는 중이거나 열려 있으면 또 열지 않는다 (0.2.0)
  if (!api.panel.available()) { note('게임 안 창을 아직 못 써요 (패널 칸을 만든 뒤 게임을 다시 켜야 해요)'); return; }
  if (!me()) { note('감독을 찾지 못했어요 (세이브를 불러온 뒤 다시)'); return; }
  openWhy = kind || 'user';
  panel = api.panel.open(form(), onPanel);
  panelBusy = !!panel.ok;
  if (!panel.ok) note('창을 열지 못했어요: ' + panel.error);
  else api.log('경력 창을 열어요 (' + why + ')');
}

var openedAt = 0, openWhy = '', autoRetry = 0;
function onPanel(ev) {
  if (ev.id === 'open') openedAt = Date.now();
  if (ev.id === 'close' || ev.id === 'error') panelBusy = false;
  // 세이브를 불러오는 중에 연 창은 화면이 바뀌며 바로 닫힌다 (C05 실기). 자동으로 연 창이 4초 안에 닫히면 5초 뒤 다시 (2번까지)
  if (ev.id === 'close' && openWhy === 'auto' && Date.now() - openedAt < 4000 && autoRetry < 2) { autoRetry++; api.after(5000, function () { if (!career) openPanel('다시 (불러오는 중에 닫힘)', 'auto'); }); }
  if (ev.id === 'error') { note('창을 못 열었어요: ' + ev.error); if (/진행 중/.test(ev.error || '')) api.after(5000, function () { openPanel('다시'); }); return; }
  if (ev.id !== 'save') return;
  var v = ev.values(), c = {};
  ['pos', 'club1', 'club2', 'apps', 'goals', 'caps', 'intlGoals', 'retired'].forEach(function (k) {
    if (v[k] !== null && v[k] !== undefined && v[k] !== '') c[k] = v[k];
  });
  if (!v.clearRel) {   // 0.6.0: 검색칸
    takePick(v.favClub, 'favClub', 'favClub', c, career);
    takePick(v.hateClub, 'dislikedClub', 'hateClub', c, career);
    takePick(v.favPerson, 'favPerson', 'favPerson', c, career);
    takePick(v.hatePerson, 'dislikedPerson', 'hatePerson', c, career);
  } else { c.favClub = ''; c.hateClub = ''; }   // 빈 글 = 게임 구단도 창에 다시 채우지 않음
  var chosen = (v.level !== null && v.level !== undefined) ? v.level : curLevel();
  var sug = suggest(c);
  c.level = chosen; c.suggested = sug;
  panel.close();
  if (sug !== null && chosen && Math.abs(levelOf(sug) - levelOf(chosen)) >= 2) {
    pending = c;
    confirm = api.panel.open({
      title: '경력과 단계가 달라 보여요',
      text: '적은 경력(클럽 ' + (c.apps || 0) + '경기, A매치 ' + (c.caps || 0) + '경기)으로는 "' + levelLabel(sug) + '"가 맞아 보여요. 고른 단계는 "' + levelLabel(chosen) + '"예요.',
      buttons: [{ id: 'useSug', label: '추천 단계로' }, { id: 'keep', label: '고른 대로' }],
      closeLabel: '취소'
    }, function (e2) {
      if (e2.id === 'useSug' && pending) { pending.level = pending.suggested; finish(pending); pending = null; confirm.close(); }
      else if (e2.id === 'keep' && pending) { finish(pending); pending = null; confirm.close(); }
    });
    if (!confirm.ok) finish(c);
    return;
  }
  finish(c);
}

function finish(c) {
  var h = me(), before = curLevel(), wrote = null;
  if (cfg.apply_level && h && c.level && c.level !== before) {
    var r = api.setField(h, 'human.pastPlayingExperience', c.level, { expect: before, reason: '감독 커리어: 선수 시절 경력 → ' + levelLabel(c.level) });
    wrote = r.ok ? (r.same ? '같음' : before + ' → ' + r.after) : ('실패: ' + r.error);
  }
  c.appliedLevel = curLevel();
  var rel = cfg.apply_clubs ? applyRelations(c) : null;   // 0.3.0 구단, 0.4.0 사람을 게임에
  c.gameClubs = gameClubs();   // 0.2.0: 저장할 때 게임이 아는 좋아하는/싫어하는 구단도 함께 남김
  if (rel) wrote = (wrote ? wrote + ', ' : '') + rel;
  c.savedAt = (gameDate() || {}).iso || null;
  career = c; careerSave = saveKey();
  api.send({ t: 'save', save: careerSave, career: c });
  note('저장했어요. 과거 선수 경력 ' + levelLabel(c.appliedLevel) + (wrote ? ' (' + wrote + ')' : ''));
  if ((c.relAmbig || []).length) api.after(800, function () { if (career === c) askPick(c); });   // 경력 창이 닫힌 뒤
}

function note(m) { lastMsg = m; api.log(m); }

// ---- 좋아하는/싫어하는 구단·사람을 게임에 (0.3.0 구단, 0.4.0 사람, 코어 0.27.0 api.setRelation) ----
// 모드가 넣은 관계만 c.modRel = [{kind, id, name}]로 기억한다 (id = 구단 고유 번호 또는 사람 참조 'p123'/'s45').
// 감독 만들 때 고른 구단은 건드리지 않는다. 다음에 다른 것을 적으면 이전에 모드가 넣은 것을 빼고 새로 넣는다.
// 화면 스레드(패널 콜백·frame)에서만 부른다.
var REL_FIELDS = [['favClub', 'favClub'], ['dislikedClub', 'hateClub'], ['favPerson', 'favPerson'], ['dislikedPerson', 'hatePerson']];
function isPersonKind(k) { return /Person$/.test(k); }
function relId(p) { return p.id !== undefined ? p.id : p.uid; }   // 0.3.0 기록은 uid
function relTargetOf(kind, id) { return isPersonKind(kind) ? personByRef(id) : clubByUid(id); }
function relWord(kind) { return { favClub: '좋아하는 구단', dislikedClub: '싫어하는 구단', favPerson: '좋아하는 사람', dislikedPerson: '싫어하는 사람' }[kind]; }
// 0.5.0 (코어 0.28.0): 같은 이름이 여럿이면 고르는 창을 띄우고, 고른 사람을 c.pick[종류] = {name, ref}로 기억한다 (이름이 바뀌면 다시 고름)
function wantedRel(c) {
  var out = [], miss = [], ambig = [], pending = false;
  REL_FIELDS.forEach(function (f) {
    var name = c[f[1]]; if (!name) return;
    if (isPersonKind(f[0])) {
      var pk = c.pick && c.pick[f[0]], pt = pk && pk.name === name ? personByRef(pk.ref) : null;
      if (pt) { out.push({ kind: f[0], id: pk.ref, name: pk.label || name, target: pt }); return; }
      var r = personByName(name);
      if (r && r.pending) { pending = true; return; }
      if (!r) { miss.push(name); return; }
      if (r.many) { ambig.push({ kind: f[0], name: name }); return; }
      out.push({ kind: f[0], id: r.ref, name: name, target: r.person });
    } else {
      var cp = c.pick && c.pick[f[0]];   // 0.6.0: 검색칸에서 고른 구단
      var club = (cp && cp.uid !== undefined && cp.uid !== null && cp.name === name) ? clubByUid(cp.uid) : null;
      club = club || clubByName(name);
      if (!club) { miss.push(name); return; }
      out.push({ kind: f[0], id: clubUid(club), name: getField(club, 'club.name'), target: club });
    }
  });
  return { list: out, miss: miss, ambig: ambig, pending: pending };
}
function personLabel(p) {
  var bits = [p.name || '?'];
  if (p.age) bits.push(p.age + '세');
  bits.push(p.club ? p.club : '무소속');
  return bits.join(' · ') + (p.role === 'staff' ? ' (스태프)' : p.role === 'player' ? ' (선수)' : '');
}
// 고를 사람이 남아 있으면 하나씩 창을 띄운다. 고르면 c.pick에 적고 다시 반영·저장
var picker = null;
function askPick(c) {
  if (picker || !c || !(c.relAmbig || []).length) return;
  var a = c.relAmbig[0], cands = personsByName(a.name);
  if (!cands || cands.pending || cands.length < 2) { c.relAmbig.shift(); return askPick(c); }
  var opts = cands.map(function (p) { return { value: p.ref, label: personLabel(p) }; }), picked = false;
  picker = api.panel.open({
    title: '같은 이름이 여럿이에요',
    text: relWord(a.kind) + '으로 적은 "' + a.name + '"이(가) 게임에 ' + cands.length + '명 있어요' + (cands.length >= 8 ? ' (8명까지만 보여요)' : '') + '. 누구인지 골라 주세요.',
    width: 560,
    fields: [{ id: 'who', type: 'select', label: '사람', options: opts }],
    buttons: [{ id: 'pick', label: '이 사람으로' }],
    closeLabel: '나중에'
  }, function (ev) {
    if (ev.id === 'close' || ev.id === 'error') {
      picker = null;
      if (ev.id === 'error') note('고르는 창을 못 열었어요: ' + ev.error);
      else if (picked) api.after(500, function () { askPick(c); });   // 고른 뒤 닫힘 -> 남은 이름. '나중에'로 닫으면 다음 저장 때 다시 물음
      return;
    }
    if (ev.id !== 'pick') return;
    var ref = ev.values().who;
    if (!ref) { note('사람을 골라 주세요'); return; }
    var got = cands.filter(function (p) { return p.ref === ref; })[0];
    c.pick = c.pick || {};
    c.pick[a.kind] = { name: a.name, ref: ref, label: got ? personLabel(got) : a.name };
    c.relAmbig.shift(); picked = true;
    picker.close();
    var msg = applyRelations(c);
    c.gameClubs = gameClubs();
    api.send({ t: 'save', save: careerSave, career: c });
    note('골랐어요: ' + c.pick[a.kind].label + (msg ? ' (' + msg + ')' : ''));
  });
  if (!picker.ok) { note('고르는 창을 열지 못했어요: ' + picker.error); picker = null; }
}
function applyRelations(c) {
  var h = me(); if (!h) return null;
  var any = REL_FIELDS.some(function (f) { return c[f[1]]; }) || ((career && career.modRel) || []).length;
  if (!any) return null;
  if (!mapsReady) { c.relApplyPending = true; return '구단·사람 표를 만드는 중이라 잠시 뒤 반영해요'; }
  var w = wantedRel(c);
  if (w.pending) { c.relApplyPending = true; return '사람 이름 색인을 만드는 중이라 (30초쯤) 잠시 뒤 반영해요'; }
  delete c.relApplyPending;
  var prev = (career && career.modRel) || [], done = [], msgs = [];
  c.relAmbig = w.ambig;
  prev.forEach(function (p) {   // 이전에 넣은 것 중 이번에 없는 것은 뺀다
    if (w.list.some(function (x) { return x.kind === p.kind && x.id === relId(p); })) return;
    if (w.ambig.some(function (a) { return a.kind === p.kind; })) { done.push(p); return; }   // 고르기 전까지는 예전 사람을 그대로 둔다
    var t = relTargetOf(p.kind, relId(p)); if (!t) return;
    var r = api.setRelation(h, p.kind, t, false, { reason: '감독 커리어: 적은 ' + relWord(p.kind) + '이(가) 바뀜' });
    if (r.ok && !r.same) msgs.push('뺌 ' + p.name);
  });
  w.list.forEach(function (x) {
    if (x.id === null) { msgs.push(x.name + ' 번호 없음'); return; }
    var r = api.setRelation(h, x.kind, x.target, true, { reason: '감독 커리어: 선수 시절 ' + relWord(x.kind) });
    var mine = prev.some(function (p) { return p.kind === x.kind && relId(p) === x.id; });
    if (r.ok) {
      // 새로 넣었거나 예전에 모드가 넣은 것만 기억한다. 원래 게임에 있던 것(감독 만들기에서 고른 구단)은 기억하지 않아서 나중에 빼지 않는다
      if (!r.same || mine) done.push({ kind: x.kind, id: x.id, name: x.name });
      if (!r.same) msgs.push(relWord(x.kind) + ' ' + x.name);
    } else msgs.push(x.name + ' 실패: ' + r.error);
  });
  c.modRel = done;
  if (w.ambig.length) msgs.push('같은 이름이 여럿이라 골라 주세요: ' + w.ambig.map(function (a) { return a.name; }).join(', '));
  if (w.miss.length) msgs.push('못 찾음: ' + w.miss.join(', ') + ' (구단은 정식/짧은 이름, 사람은 게임에 나오는 이름 그대로)');
  return msgs.length ? msgs.join(', ') : null;
}
// 불러올 때 보관된 관계가 게임에 없으면 다시 넣는다 (저장 안 하고 끈 경우). 화면 스레드에서 해야 해서 다음 프레임에
var relPending = false, relTick = 0;
api.on('frame', function () {
  if (++relTick % 20) return;   // 1초에 한 번쯤만 본다
  if (career && career.relApplyPending && cfg.apply_clubs && mapsReady) {   // 저장할 때 표·색인이 없어서 미뤄 둔 반영
    var msg = applyRelations(career);
    if (!career.relApplyPending) {
      career.gameClubs = gameClubs();
      api.send({ t: 'save', save: careerSave, career: career });
      if (msg) note('구단·사람 반영: ' + msg);
      if ((career.relAmbig || []).length) askPick(career);
    }
  }
  if (!relPending || !mapsReady) return;   // 구단 표가 준비될 때까지 기다린다
  relPending = false;
  var h = me(); if (!h || !career || !cfg.apply_clubs) return;
  (career.modRel || []).forEach(function (p) {
    var t = relTargetOf(p.kind, relId(p)); if (!t) return;
    var r = api.setRelation(h, p.kind, t, true, { reason: '감독 커리어: 보관된 ' + relWord(p.kind) + ' 다시 반영' });
    if (r.ok && !r.same) note('보관된 ' + relWord(p.kind) + '을(를) 다시 반영했어요: ' + p.name);
  });
});

// Python 부분: 세이브별 career.json 읽기·쓰기
var handled = {};
api.recv(function (m) {
  if (!m || m.t !== 'career') return;
  if (m.save !== saveKey() || handled[m.save]) return;
  if (m.ready === false) { if (askTries++ < 15) api.after(2000, askCareer); return; }   // PC 쪽이 아직 이 세이브를 모름 -> 다시 묻기 (0.2.0)
  handled[m.save] = true;
  career = m.career || null; careerSave = m.save;
  if (career) {
    api.log('보관된 경력을 읽었어요 (' + (career.club1 || '구단 없음') + ', 단계 ' + levelLabel(career.appliedLevel || 0) + ')');
    reapply();
    relPending = true;   // 0.3.0: 보관된 구단·사람도 (다음 프레임에)
  } else if (cfg.auto_open && !asked[m.save]) {
    asked[m.save] = true;
    api.after(3000, function () { if (!career && saveKey() === m.save) openPanel('이 세이브에 적은 경력이 없어요', 'auto'); });   // 그사이 경력을 읽었으면 열지 않는다
  }
});
// 경력 원본은 모드가 보관한다 (M42): 단계를 반영한 뒤 게임을 저장하지 않고 껐으면 세이브의 값이 예전 것이다 -> 불러올 때 다시 반영
function reapply() {
  var h = me(), cur = curLevel(), want = career && career.appliedLevel;
  if (!cfg.apply_level || !h || !want || cur === null || cur === want) return;
  var r = api.setField(h, 'human.pastPlayingExperience', want, { expect: cur, reason: '감독 커리어: 보관된 경력 다시 반영 (' + levelLabel(want) + ')' });
  note(r.ok ? '보관된 단계를 다시 반영했어요: ' + levelLabel(cur) + ' → ' + levelLabel(want) + ' (게임을 저장하면 남아요)' : '보관된 단계를 반영하지 못했어요: ' + r.error);
}
function askCareer() { var k = saveKey(); if (k && !handled[k]) api.send({ t: 'get', save: k }); }
api.on('saveLoaded', function () { career = null; handled = {}; askTries = 0; askCareer(); });

var seen = cfg.open;
api.onSettings(function (s) { cfg = s; if (s.open !== seen) { seen = s.open; openPanel('설정'); } });
api.status(function () {
  var cur = curLevel();
  return { 과거선수경력: cur === null ? '-' : levelLabel(cur) + ' (' + cur + ')', 적은경력: career ? (career.club1 || '-') + (career.apps ? ', ' + career.apps + '경기' : '') : '없음', 게임좋아하는구단: gameClubs().fav.join(', ') || '-', 마지막: lastMsg };
});
askCareer();
api.log('올라왔어요. 창 사용 가능: ' + api.panel.available());
