# 게임 뉴스 (코어 0.37.0)

FM24는 하루에 뉴스를 수백~수천 개 만들어요 (경기 보고, 이적, 부상, 언론 의견…). 뉴스 하나는 `db::NEWS_ITEM`을 물려받은 클래스 객체이고, 종류가 645개쯤 있어요 (`cli.py classes NEWS`). M24GA는 게임이 뉴스를 넣는 함수(`news.add`)에 끼어들어 모드에 이벤트로 나눠 줘요.

## 이벤트

```js
// mod.json "capabilities": ["event.newsAdded", "event.matchEnded", "read.prop"]
api.on('newsAdded', function (ev) {
  if (ev.cls !== 'INJURY_INJURED_NEWS') return;
  var r = ev.refs();                                  // 게임이 뉴스에 붙인 관련 기록
  api.log(ev.date + ' 부상: ' + r.people.map(function (p) { return api.prop(p, 'Pfln'); }).join(', '));
});
api.on('matchEnded', function (ev) {
  if (!ev.mine) return;
  api.log(api.prop(ev.home, 'Tnam').Tsna + ' ' + ev.homeGoals + '-' + ev.awayGoals + ' ' + api.prop(ev.away, 'Tnam').Tsna);
});
```

| 이벤트 | ev |
|---|---|
| `newsAdded` | `cls` 뉴스 종류, `flags`, `toInbox`(받은 편지함에 감), `team`(받는 팀), `mine`(내 팀 앞), `id` 뉴스 번호(사본에서 매기는 뉴스는 0), `date` 'YYYY-MM-DD', `text()` 본문 평문, `refs()` = `{ people, teams, clubs, comps, refs: [dref] }` |
| `matchEnded` | `home`, `away`(팀), `homeGoals`, `awayGoals`, `comp`(대회 또는 null), `mine`, `date`, `text()`(경기 보고 본문) |

- 이벤트는 게임 스레드에서 와요. 짧게 처리하고, 긴 일(AI 호출 등)은 `api.send`로 Python에 넘기세요.
- `text()`와 `refs()`는 **콜백 안에서만** 돼요 (뉴스 객체는 콜백이 끝나면 사라져요). 비싸니 필요한 뉴스에만 부르세요.
- 모드가 `api.inbox.send`로 넣은 메일에는 이벤트가 오지 않아요 (되먹임 없음).

## 관련 기록 (`refs`)

게임 함수 `news.related`(가상 함수 +0x168)가 뉴스마다 관련 기록 목록을 만들어요. 항목은 `{dref}` 값이고, 위 8비트가 종류예요.

| dref 종류 | 뜻 | `refs()`의 칸 |
|---|---|---|
| `0x01` | 사람 (선수·스태프·사람 감독) | `people` |
| `0x18` | 팀 (국가대표 포함) | `teams` |
| `0x03` | 구단 | `clubs` |
| `0x19` | 대회 | `comps` |
| 그 밖 (`0x15` 경기 관련 등) | 아직 객체로 못 바꿈 | `refs`에 번호만 |

실기 예 (M56): 부상 = 사람·팀·대회, 이적 완료·계약 합의 = 사람·팀(·대회), 경기 보고 = 팀 2·대회·`0x15`, 기자회견 요약 = 사람 여럿·팀·대회.

## 경기 보고 (`MATCH_REPORT_NEWS`)

경기마다 두 팀 쪽에서 하나씩 나와요 (같은 경기, 관점만 다름). `matchEnded`는 홈 쪽 보고서에서 한 번만 내요.

| 칸 | 뜻 |
|---|---|
| `+0xd8` | 이쪽 구단 (db::CLUB) |
| `+0xe0` / `+0xe8` | 이쪽 팀 / 상대 팀 |
| `+0x100` / `+0x108` | 대회 / 경기장 |
| `+0x180` / `+0x181` | 이쪽 골 / 상대 골 (u8) |
| `+0x1d2` | 1 = 이쪽이 홈, 2 = 원정 |

- 게임이 보도하는 리그·대회의 경기만 보고서가 나와요 (사흘에 수십 경기). 모든 경기 결과가 필요하면 아직 방법이 없어요 (AI 경기 처리 함수 `fm+0x34632a0`은 점수 칸을 못 찾음, M53).
- 승부차기·연장은 아직 구별하지 않아요.

## 자주 나오는 뉴스 종류

M53·M56 실기(하루 약 700개)에서 많이 본 것:

| 종류 | 뜻 |
|---|---|
| `MATCH_REPORT_NEWS` | 경기 보고 (경기마다 2개) |
| `MOM_SUMMARY_NEWS` | 경기 최우수 선수 요약 ("○○를 상대로 3-1 승리") |
| `PRE_MATCH_ODDS_NEWS` / `PRE_MATCH_DANGER_PLAYER_NEWS` / `PRE_MATCH_ATTENDANCE_NEWS` | 경기 전 배당 / 경계 대상 / 관중 |
| `INJURY_INJURED_NEWS` | 부상 |
| `RED_CARD_BAN_NEWS` | 퇴장 징계 |
| `TRANSFER_COMPLETED_NEWS` / `TRANSFER_OFFER_NEWS` / `FUTURE_TRANSFER_NEWS` | 이적 완료 / 제의 / 미래 이적 |
| `CONTRACT_DECISION_NEWS` / `TRANSFER_CONTRACT_DECISION_NEWS` | 계약 합의 |
| `PRESS_CONFERENCE_SUMMARY_NEWS` | 기자회견 요약 |
| `SOCIAL_TEAM_SELECTION_NEWS` / `SOCIAL_POLL_NEWS` | 소셜 피드 (선발 반응, 투표) |
| `AWARD_NEWS` / `BUILDUP_HYPE_AWARD_NEWS` | 상 / 시상 예고 |
| `MANAGER_VOTE_OF_CONFIDENCE_NEWS` / `CLUB_MANAGER_DEPARTURE_NEWS` | 감독 신임 투표 / 감독 떠남 |
| `BOARD_TAKEOVER_RUMOUR_MILL_NEWS` | 구단 인수 소문 |
| `PLAYER_CLUB_DEBUT_NEWS` / `PLAYER_ENDS_GOAL_DROUGHT_NEWS` / `RECORD_NEWS` | 데뷔 / 골 가뭄 끝 / 기록 |

공통 칸 (`db::NEWS_ITEM`): `+0x68` 답장 선택지 벡터(받은 편지함 버튼), `+0x98` 언론사(db::MEDIA_SOURCE), `+0xa0` 날짜(게임 날짜 형식), `+0xa8` 뉴스 번호, `+0xb0` 플래그. 그 뒤(`+0xb8~`)는 종류마다 달라요. 조사 기록: `logs/M24GA` M51·M53·M56.
