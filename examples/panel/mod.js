// 게임 안 패널 예제 (코어 0.23.0, 기능 ui.panel). 게임 값은 바꾸지 않는다.
// 설정 open 값을 바꿀 때마다 패널을 연다 (앱 설정 또는 CLI: python -X utf8 loader/cli.py set panel-example open 1).

var FORM = {
  title: 'M24GA 패널 예제',
  text: '게임 안 패널 시험이에요. 값을 고르고 적용을 눌러 보세요.',
  fields: [
    { id: 'club', type: 'text', label: '뛴 구단', value: 'FC 바르셀로나' },
    { id: 'year', type: 'number', label: '은퇴 해 (1970~2035)', min: 1970, max: 2035 },
    { id: 'intl', type: 'check', label: '국가대표 경력', value: true },
    { id: 'pos', type: 'select', label: '포지션', options: [{ value: 'GK', label: '골키퍼' }, { value: 'DF', label: '수비수' }, { value: 'MF', label: '미드필더' }, { value: 'FW', label: '공격수' }] },
    { type: 'label', label: '닫기 버튼은 코어가 늘 붙여요.' }
  ],
  buttons: [{ id: 'apply', label: '적용' }],
  closeLabel: '닫기'
};

var last = null, events = 0, cur = null;
function open() {
  if (!api.panel.available()) { api.log('게임 안 패널을 아직 못 써요 (패널 칸을 만든 뒤 게임을 다시 켜야 해요)'); return; }
  if (cur && cur.isOpen()) { api.log('이미 열려 있어요'); return; }
  cur = api.panel.open(FORM, function (ev) {
    events++;
    if (ev.kind === 'change') return;   // 글자마다 오니 로그는 생략
    api.log('패널 이벤트 ' + ev.id + ' (' + ev.kind + ')' + (ev.value !== undefined && ev.value !== null ? ' 값=' + JSON.stringify(ev.value) : '') + (ev.error ? ' ' + ev.error : ''));
    if (ev.id === 'apply') { last = ev.values(); api.log('적용: ' + JSON.stringify(last)); }
  });
  if (!cur.ok) api.log('열지 못했어요: ' + cur.error);
}

var seen = api.settings().open;
api.onSettings(function (s) {
  if (s.open === seen) return;
  seen = s.open;
  if (s.open < 0) { if (cur && cur.close) cur.close(); return; }   // 음수면 모드에서 닫기 (p.close())
  open();
});
api.status(function () { return { panelOpen: !!(cur && cur.isOpen && cur.isOpen()), panelEvents: events, lastApply: last }; });
api.log('올라왔어요. 패널 사용 가능: ' + api.panel.available());
