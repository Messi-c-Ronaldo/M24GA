# M24GA 필드 목록 (코어 0.39.0)

> 이 파일은 `core/fields.json`에서 `python -X utf8 tools/m24.py caps`로 만들어요. 직접 고치지 마세요.

게임 객체의 칸을 이름으로 읽어요: `getField(obj, '이름')` (기능 `read.field`). 쓰기가 확인된 칸(**쓰기: safe**)은 `api.setField(obj, '이름', 값, { expect, reason })`로 바꿀 수 있어요 (그 칸의 쓰기 기능, 사용자 허용 필요, 모든 쓰기가 기록되고 앱에서 되돌릴 수 있어요).
객체는 `findObj('player', uid)`, `playerByUid(uid)`, `myInfo().co` 같은 코어 함수로 얻어요. 객체 종류는 클래스 이름(RTTI)으로 확인해서, 종류가 다른 객체를 넘기면 `null`이에요.
새 칸을 찾으면 `core/fields.json`에 한 줄 더하면 돼요 (찾는 법: CLI `explore`, [`CLI.md`](CLI.md)). 확인하지 못한 칸은 `verified: false`로 두세요.

빌드: FM24 Epic, fm.exe 2026-10-24 빌드

## 객체 종류

| 종류 | 클래스 | 설명 |
|---|---|---|
| `player` (선수) | `db::ACTUAL_PLAYER` | 선수 객체 (playerByUid/playerOf). 선수 겸 감독·스태프(db::ACTUAL_PLAYER_AND_NON_PLAYER)는 일부 칸 위치가 달라 alt에 적는다. 사람 데이터 객체(personOf, +0x278)를 넘겨도 된다 |
| `team` (팀) | `db::TEAM` | 클럽의 팀(1군·리저브·유스) 또는 대표팀이 아닌 팀. clubs 표의 객체(CLUB_VT)와 같은 종류 |
| `club` (클럽) | `db::CLUB` | 클럽 객체 (myInfo().co, team.club) |
| `human` (사람 감독) | `db::HUMAN_NON_PLAYER` | 사람이 조종하는 감독. findObj('human', 0) = 이 PC의 감독 (코어 0.24.0: 전역 HUMAN_NON_PLAYER_MANAGER fm+0x6365118 +0x18 목록, 쓰기 기록의 열쇠도 이 순번). 코어 newsCtx는 이 객체의 +0x450 위치 |

## 선수 (`player`)

| 필드 | 위치 | 형식 | 뜻 | 쓰기 | 확인 |
|---|---|---|---|---|---|
| `player.uid` | +0x284 (ACTUAL_PLAYER_AND_NON_PLAYER: +0x374) | u32 | 선수 고유 ID (UID). 게임 화면 ID와 같다 | - | ✔ M11, M13 |
| `player.dob` | +0x2bc (ACTUAL_PLAYER_AND_NON_PLAYER: +0x3ac) | date | 생년월일 | - | ✔ M11, M13 |
| `player.name` | +0x2d0 (ACTUAL_PLAYER_AND_NON_PLAYER: 없음) | strref | 이름 (게임 언어) | - | ✔ M11, M13 |
| `player.ca` | +0x200 | i16 | 현재 능력 (CA). 히든 패널의 '현재 능력'과 같다 ('추천 현재 능력치'가 아님) [1~200] | - | ✔ M11, 몸값모드 V02 |
| `player.pa` | +0x202 | i16 | 잠재 능력 (PA). 음수면 범위로 지정된 잠재력(-10 등) [1~200] | **safe** (범위 1~200, ≥ `player.ca`, 기능 `write.player.pa`) | ✔ M11, M14 (쓰기 실기 149->150->149) |
| `player.link` | +0x280 (ACTUAL_PLAYER_AND_NON_PLAYER: 없음) | u32 | 사람 링크 번호 (persons 표 번호, 글 링크의 idx). 사람 데이터 객체(+0x278)의 +8과 같다 | - | ✔ M13, M19 |
| `player.team` | +0x130 | ptr → `team` | 소속 팀 (없으면 null) | - | ✔ P04 (playerTeam), M19 RTTI |
| `player.intlData` | +0x120 | ptr | 국가대표 자료 객체 (db::INTERNATIONAL_PLAYER_DATA) | - | 미확인 M19 RTTI |
| `player.askingPrice` | +0x1d0 | i32 | 이적 시 요구 금액 / 몸값 (게임 내부 돈 단위, 원화 = ×1664.7). 0 이하면 없음. 몸값인지 요구 금액인지는 아직 확정 전 [money] | - | ✔ 몸값모드 V02 (화면 값 3/3 일치) |
| `player.ambition` | +0x2f1 (ACTUAL_PLAYER_AND_NON_PLAYER: +0x3e1) | u8 | 야망 (숨은 성격) [1~20] | - | ✔ P03, P04 (playerTraits) |
| `player.professionalism` | +0x2f4 (ACTUAL_PLAYER_AND_NON_PLAYER: +0x3e4) | u8 | 프로의식 (숨은 성격) [1~20] | - | ✔ P03, P04 (playerTraits) |
| `player.determination` | +0x24a | u8 (t20) | 결단력 (게임은 1~100으로 저장, (v+2)/5로 1~20에 맞춤) [1~20 (저장은 1~100)] | - | ✔ P03, P04 (playerTraits) |
| `player.workRate` | +0x234 | u8 (t20) | 활동량 (게임은 1~100으로 저장, (v+2)/5로 1~20에 맞춤) [1~20 (저장은 1~100)] | - | ✔ P03, P04 (playerTraits) |
| `player.flair` | +0x231 | u8 (t20) | 창의성 (게임은 1~100으로 저장, (v+2)/5로 1~20에 맞춤) [1~20 (저장은 1~100)] | - | ✔ P03, P04 (playerTraits) |
| `player.pos.GK` | +0x208 | u8 | 포지션 숙련도 GK [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.SW` | +0x209 | u8 | 포지션 숙련도 SW [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.DL` | +0x20a | u8 | 포지션 숙련도 DL [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.DC` | +0x20b | u8 | 포지션 숙련도 DC [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.DR` | +0x20c | u8 | 포지션 숙련도 DR [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.DM` | +0x20d | u8 | 포지션 숙련도 DM [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.ML` | +0x20e | u8 | 포지션 숙련도 ML [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.MC` | +0x20f | u8 | 포지션 숙련도 MC [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.MR` | +0x210 | u8 | 포지션 숙련도 MR [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.AML` | +0x211 | u8 | 포지션 숙련도 AML [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.AMC` | +0x212 | u8 | 포지션 숙련도 AMC [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.AMR` | +0x213 | u8 | 포지션 숙련도 AMR [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.ST` | +0x214 | u8 | 포지션 숙련도 ST [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.WBL` | +0x215 | u8 | 포지션 숙련도 WBL [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.pos.WBR` | +0x216 | u8 | 포지션 숙련도 WBR [1~20] | - | ✔ P03, P04 (playerPositions, 게임 속성 Pgoa… 와 칸별 일치) |
| `player.season.club.ratingSum` | +0x108 → +0x48 → +0x8 | u16 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): 평점 합 ×10 (평균 = 합 / 평점 받은 경기 / 10) | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.club.minutes` | +0x108 → +0x48 → +0xa | u16 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): 출전 분 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.club.starts` | +0x108 → +0x48 → +0xc | u8 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): 선발 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.club.subs` | +0x108 → +0x48 → +0xd | u8 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): 교체 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.club.rated` | +0x108 → +0x48 → +0xe | u8 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): 평점 받은 경기 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.club.goals` | +0x108 → +0x48 → +0xf | u8 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.club.assists` | +0x108 → +0x48 → +0x10 | u8 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): 도움 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.club.pens` | +0x108 → +0x48 → +0x13 | u8 | 이번 시즌 클럽 공식전 합계(리그+컵+대륙컵): PK 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.ratingSum` | +0x108 → +0x28 → +0x8 | u16 | 이번 시즌 리그: 평점 합 ×10 (평균 = 합 / 평점 받은 경기 / 10) | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.minutes` | +0x108 → +0x28 → +0xa | u16 | 이번 시즌 리그: 출전 분 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.starts` | +0x108 → +0x28 → +0xc | u8 | 이번 시즌 리그: 선발 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.subs` | +0x108 → +0x28 → +0xd | u8 | 이번 시즌 리그: 교체 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.rated` | +0x108 → +0x28 → +0xe | u8 | 이번 시즌 리그: 평점 받은 경기 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.goals` | +0x108 → +0x28 → +0xf | u8 | 이번 시즌 리그: 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.assists` | +0x108 → +0x28 → +0x10 | u8 | 이번 시즌 리그: 도움 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.league.pens` | +0x108 → +0x28 → +0x13 | u8 | 이번 시즌 리그: PK 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.ratingSum` | +0x108 → +0x30 → +0x8 | u16 | 이번 시즌 국내 컵: 평점 합 ×10 (평균 = 합 / 평점 받은 경기 / 10) | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.minutes` | +0x108 → +0x30 → +0xa | u16 | 이번 시즌 국내 컵: 출전 분 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.starts` | +0x108 → +0x30 → +0xc | u8 | 이번 시즌 국내 컵: 선발 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.subs` | +0x108 → +0x30 → +0xd | u8 | 이번 시즌 국내 컵: 교체 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.rated` | +0x108 → +0x30 → +0xe | u8 | 이번 시즌 국내 컵: 평점 받은 경기 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.goals` | +0x108 → +0x30 → +0xf | u8 | 이번 시즌 국내 컵: 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.assists` | +0x108 → +0x30 → +0x10 | u8 | 이번 시즌 국내 컵: 도움 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.cup.pens` | +0x108 → +0x30 → +0x13 | u8 | 이번 시즌 국내 컵: PK 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.ratingSum` | +0x108 → +0x38 → +0x8 | u16 | 이번 시즌 대륙컵: 평점 합 ×10 (평균 = 합 / 평점 받은 경기 / 10) | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.minutes` | +0x108 → +0x38 → +0xa | u16 | 이번 시즌 대륙컵: 출전 분 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.starts` | +0x108 → +0x38 → +0xc | u8 | 이번 시즌 대륙컵: 선발 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.subs` | +0x108 → +0x38 → +0xd | u8 | 이번 시즌 대륙컵: 교체 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.rated` | +0x108 → +0x38 → +0xe | u8 | 이번 시즌 대륙컵: 평점 받은 경기 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.goals` | +0x108 → +0x38 → +0xf | u8 | 이번 시즌 대륙컵: 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.assists` | +0x108 → +0x38 → +0x10 | u8 | 이번 시즌 대륙컵: 도움 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.continental.pens` | +0x108 → +0x38 → +0x13 | u8 | 이번 시즌 대륙컵: PK 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.ratingSum` | +0x108 → +0x40 → +0x8 | u16 | 이번 시즌 국가대표: 평점 합 ×10 (평균 = 합 / 평점 받은 경기 / 10) | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.minutes` | +0x108 → +0x40 → +0xa | u16 | 이번 시즌 국가대표: 출전 분 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.starts` | +0x108 → +0x40 → +0xc | u8 | 이번 시즌 국가대표: 선발 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.subs` | +0x108 → +0x40 → +0xd | u8 | 이번 시즌 국가대표: 교체 출전 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.rated` | +0x108 → +0x40 → +0xe | u8 | 이번 시즌 국가대표: 평점 받은 경기 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.goals` | +0x108 → +0x40 → +0xf | u8 | 이번 시즌 국가대표: 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.assists` | +0x108 → +0x40 → +0x10 | u8 | 이번 시즌 국가대표: 도움 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.season.international.pens` | +0x108 → +0x40 → +0x13 | u8 | 이번 시즌 국가대표: PK 골 | - | ✔ P03, P04 (playerSeason, 합계가 Poav·Pgls와 896/896 일치) |
| `player.intlCaps` | +0x3dc | u8 | A매치(성인 국가대표) 통산 출전 (사람 데이터 객체 기준 +0x164. 선수 겸 감독 객체(db::ACTUAL_PLAYER_AND_NON_PLAYER)는 확인 안 함) | - | ✔ 몸값모드 V10 (사람 데이터 객체 +0x164~0x167, 화면 값: 사카 A매치 156경기 66골·청소년 1경기, 홀란 98경기 86골·청소년 3경기, 다른 선수 25명 값도 그럴듯함) |
| `player.youthCaps` | +0x3dd | u8 | 청소년 국가대표 통산 출전 (사람 데이터 객체 기준 +0x165. 선수 겸 감독 객체(db::ACTUAL_PLAYER_AND_NON_PLAYER)는 확인 안 함) | - | ✔ 몸값모드 V10 (사람 데이터 객체 +0x164~0x167, 화면 값: 사카 A매치 156경기 66골·청소년 1경기, 홀란 98경기 86골·청소년 3경기, 다른 선수 25명 값도 그럴듯함) |
| `player.intlGoals` | +0x3de | u8 | A매치 통산 골 (사람 데이터 객체 기준 +0x166. 선수 겸 감독 객체(db::ACTUAL_PLAYER_AND_NON_PLAYER)는 확인 안 함) | - | ✔ 몸값모드 V10 (사람 데이터 객체 +0x164~0x167, 화면 값: 사카 A매치 156경기 66골·청소년 1경기, 홀란 98경기 86골·청소년 3경기, 다른 선수 25명 값도 그럴듯함) |
| `player.youthGoals` | +0x3df | u8 | 청소년 국가대표 통산 골 (사람 데이터 객체 기준 +0x167. 선수 겸 감독 객체(db::ACTUAL_PLAYER_AND_NON_PLAYER)는 확인 안 함) | - | ✔ 몸값모드 V10 (사람 데이터 객체 +0x164~0x167, 화면 값: 사카 A매치 156경기 66골·청소년 1경기, 홀란 98경기 86골·청소년 3경기, 다른 선수 25명 값도 그럴듯함) |
| `player.recordList` | +0x388 | u32 | 경력 사건 기록 목록 번호 (사람 데이터 객체 기준 +0x110. 세이브 person_record_history의 목록 번호, Python 공용 라이브러리 m24career.load(...).of(번호)). 사람 번호(player.link)와 다르다 (홀란 45806 -> 32192). 기록이 없으면 0xffffffff. 스태프의 사람 데이터 객체도 +0x110 (선수 겸 감독 객체는 확인 안 함) | - | ✔ 몸값모드 V17 (사람 117,442명 중 116,099개가 서로 다름, 목록 4,235개 중 82%에 현재 팀이 나옴, 홀란·사카·카마빙가·야말 이적·우승·데뷔 기록이 실제와 맞음) |

## 팀 (`team`)

| 필드 | 위치 | 형식 | 뜻 | 쓰기 | 확인 |
|---|---|---|---|---|---|
| `team.club` | +0x30 | ptr → `club` | 이 팀의 클럽 | - | ✔ P04, M19 RTTI |
| `team.comp` | +0x50 | ptr | 이 팀이 뛰는 대회(리그) 객체 | - | ✔ P04 |
| `team.compUid` | +0x50 → +0xc | u32 | 이 팀이 뛰는 대회(리그) UID | - | ✔ P04 (playerTeam.compUid) |

## 클럽 (`club`)

| 필드 | 위치 | 형식 | 뜻 | 쓰기 | 확인 |
|---|---|---|---|---|---|
| `club.name` | +0xc0 | str | 클럽 정식 이름 | - | ✔ 소셜피드 로그 18 (clubFullName) |
| `club.short` | +0xc8 | str | 클럽 짧은 이름 | - | ✔ 소셜피드 로그 18 (clubShortName) |

## 사람 감독 (`human`)

| 필드 | 위치 | 형식 | 뜻 | 쓰기 | 확인 |
|---|---|---|---|---|---|
| `human.name` | +0x4b8 | strref | 사람 감독 이름 (myInfo().mgr) | - | ✔ 소셜피드 로그 21 (newsCtx +0x68), M19 |
| `human.firstName` | +0x4a8 | strref | 사람 감독 이름 (예: 라온). 생성 직후에도 있다 (human.name은 비어 있을 수 있음) | - | ✔ 감독커리어모드 C02 |
| `human.lastName` | +0x4b0 | strref | 사람 감독 성 (예: 윤) | - | ✔ 감독커리어모드 C02 |
| `human.job` | +0x518 | ptr | 지금 직장(계약) 객체. +0x10 = 클럽 데이터 객체(db::TEAM) | - | ✔ myInfo (newsCtx +0xc8), M19 |
| `human.pastPlayingExperience` | +0x410 | u16 | 과거 선수 경력 값: 0 없음, 2750 조기 축구회, 3250 세미프로, 4500 프로(지역 수준), 5250 프로(해당 지역에서 유명), 6000 프로(국가에서 유명), 7000 국제(대륙간 대회 수준), 8000 국제(글로벌 수준). 감독 생성 때 정해지고 구단 면접 질문(GAME_JOB_INTERVIEW)이 국내 명성과의 비율로 읽는다 [0, 2750~8000] | **safe** (범위 0~10000, 기능 `write.field`) | ✔ 감독커리어모드 C01 (fm+0x302e380 감독 생성 설정 적용: +0x410=경력 값, +0xd0/+0xd2/+0xd4 시작 명성 계산), M43 7절 (윤라온 +0x410=8000, 명성 10000/10000/10000); 확인: 새 게임에서 국제(글로벌 수준)로 만든 감독 = 8000 (C02); 쓰기 실기 C03: 8000->3250->되돌리기 8000, 7000으로 쓰고 게임 저장 -> 모드 끄고 다시 불러와도 7000 (세이브에 남음) |
| `human.repCurrent` | +0xd0 | i16 | (추정) 현재 명성 0~10000. 생성 코드상 경력 값을 현재 능력(+0xd6)x50 기준 범위로 조정해 넣음 (실측: 경력 8000으로 만든 감독 = 현재 8000, 국내 7999, 세계 5000. 생성 뒤 다른 단계가 조금 바꿈) (화면에 숫자로 보이는 속성을 찾지 못해 이름은 추정, C06) | - | 미확인 감독커리어모드 C01 (fm+0x302e380 감독 생성 설정 적용: +0x410=경력 값, +0xd0/+0xd2/+0xd4 시작 명성 계산), M43 7절 (윤라온 +0x410=8000, 명성 10000/10000/10000) |
| `human.repHome` | +0xd2 | i16 | (추정) 국내 명성 0~10000. 생성 코드상 경력 값 그대로 (실측: 경력 8000으로 만든 감독 = 현재 8000, 국내 7999, 세계 5000. 생성 뒤 다른 단계가 조금 바꿈) (화면에 숫자로 보이는 속성을 찾지 못해 이름은 추정, C06) | - | 미확인 감독커리어모드 C01 (fm+0x302e380 감독 생성 설정 적용: +0x410=경력 값, +0xd0/+0xd2/+0xd4 시작 명성 계산), M43 7절 (윤라온 +0x410=8000, 명성 10000/10000/10000) |
| `human.repWorld` | +0xd4 | i16 | 세계(글로벌) 명성 0~10000. 감독 미니 프로필의 세계 명성 별(속성 Prsa)의 srto 값과 같다. 생성 코드상 min(경력/2, 경력-4000)을 능력 기준 상한으로 (실측: 경력 8000 감독 = 5000) | - | ✔ 감독커리어모드 C01 (fm+0x302e380 감독 생성 설정 적용: +0x410=경력 값, +0xd0/+0xd2/+0xd4 시작 명성 계산), M43 7절 (윤라온 +0x410=8000, 명성 10000/10000/10000); C06: 속성 Prsa = {valu 별, srto 5000} = +0xd4 |
| `human.favClub` | +0x588 | ptr | (추정) 선호 구단 (db::CLUB). 감독 생성 화면 favo. 선호 구단을 안 고른 새 감독은 null. 바로 앞 +0x570~+0x580은 언어 목록(db::LANGUAGE) | - | 미확인 M43 7절 (윤라온 객체 +0x588 = db::CLUB, 빈 사람 감독은 0) |
