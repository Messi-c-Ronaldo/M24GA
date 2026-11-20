// DynamicME 게임 쪽: 코어 api.engine으로 엔진 표를 읽고 쓰기만 한다. 무엇을 쓸지는 Python(python/main.py)이 정한다.
// 메시지: Python -> {t:'dump', id} / {t:'write', id, writes:[[표, spec], ...]}
//         JS -> {t:'hello'} / {t:'dump', id, tables} / {t:'written', id, ok, results} / {t:'styles_ready', key}
//         Python -> {t:'styles_done', key} (그 스타일 불러오기를 처리함)
var TABLES = ['weights', 'physics', 'momentum', 'ratings', 'styles', 'xg'];   // styles: 첫 진행일 전에는 error (아직 안 불러옴)

function dumpAll() {
  var r = {};
  TABLES.forEach(function (t) { r[t] = api.engine.dump(t); });
  return r;
}

api.recv(function (m) {
  if (!m || !m.t) return;
  if (m.t === 'dump') {
    api.send({ t: 'dump', id: m.id, tables: dumpAll() });
  } else if (m.t === 'styles_done') {
    stylesDone = m.key;
  } else if (m.t === 'write') {
    var res = [], ok = true;
    for (var i = 0; i < m.writes.length; i++) {
      var w = m.writes[i], r = api.engine.write(w[0], w[1]);
      res.push(r);
      if (!r || r.error) {
        ok = false;
        if (String(r && r.error).indexOf('진행 중') >= 0) break;   // 게임이 진행 중: 나머지도 안 됨
      }
    }
    api.send({ t: 'written', id: m.id, ok: ok, results: res });
  }
});

// 전술 스타일은 게임이 첫 진행일에(또는 언어를 바꾸면 다시) 불러온다 (E09). 새로 불러온 것을 보면 Python에 알려 다시 넣게 한다.
// Python이 끝냈다고(styles_done) 할 때까지 10초마다 다시 알린다 (게임이 진행 중이라 못 쓴 경우).
var stylesDone = null;
api.every(10000, function () {
  var r = api.engine.dump('styles');
  if (!r || r.error || !r.key || r.key === stylesDone) return;
  api.send({ t: 'styles_ready', key: r.key });
});

api.send({ t: 'hello' });
api.log('DynamicME 게임 쪽 준비');
