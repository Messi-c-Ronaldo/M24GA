# 게임 속성 코드

> 이 문서는 `python -X utf8 tools/props_catalog.py --docs`가 `core/properties.json`에서 만들어요. 고치려면 등록부의 `ko`를 고치세요.

게임 화면(스킨)은 `get_property="Tpos"`처럼 **4글자 속성 코드**로 값을 물어요. 게임 객체마다 답하는 코드가 정해져 있고, M24GA는 그 목록을 전부 조사해 등록부(`core/properties.json`)로 만들었어요 (코어 0.36.0, 기능 `read.prop`).

```js
api.prop('myteam', 'TpoN')          // 리그 순위 (정수)
api.props('myteam', { re: '^Cc' })  // {코드: 값} — 그 객체가 답하는 코드 중 정규식에 맞는 것
api.propInfo('Pced')                // { code, t: 'date', k: ['player', ...], ko }
api.deref(api.prop('myteam', 'Topp')) // {dref} → 객체 (사람·팀·구단·대회)
```

- 대상: 객체 포인터(어느 칸을 가리켜도 됨) 또는 `'me'`(내 감독) · `'myteam'` · `'myclub'` · `'myjob'`(내 감독 계약) · 사람 참조 `'p123'`/`'s45'`.
- 값 종류: `int` 정수, `u32` 부호 없는 정수, `num` 실수, `bool`, `str` 글, `date` 날짜(`'2038-06-30'`, 빈 날짜는 null), `color` 색(`'#rrggbbaa'`), `rec` 묶음(`{키: 값}`), `list` 목록, `data` 내부 자료(null), `empty` 조사한 객체에서는 늘 빈 값.
- `{dref: 번호}` = 다른 게임 객체 링크. 위 8비트가 종류예요: `0x01` 사람, `0x03` 구단, `0x18` 팀, `0x19` 대회 (`api.deref`). 국가·경기장 등 나머지 종류는 링크로 못 따라가고, 다른 객체가 가리키는 포인터로만 닿아요 (예: `matchEnded`의 `ev.stadium`).
- 값은 **게임 화면이 보여 주는 값 그대로**예요. 뜻(ko)을 적은 것만 화면과 맞춰 봤어요. 나머지는 이름을 보고 짐작해서 쓰되, 직접 확인하세요.
- 이름은 게임 파일(`properties.fmf` + 번역 파일)에만 있어서 저장소에 넣지 않았어요. `python -X utf8 tools/prop_names.py`가 자기 게임 파일에서 `~/m24ga_data/prop_names.tsv`(코드, 영어, 게임 언어, 표시 형식, 분류)를 만들고, 있으면 CLI `props`·`prop-info`가 이름·표시 형식을 같이 보여 줘요.

**부르지 않는 코드** (게임 안에서 접근 오류): `CMli`

## 객체 종류

| 종류 | 게임 클래스 | 코드 수 | 뜻 |
|---|---|---|---|
| `team` | `db::TEAM` (+0x0) | 760 | 팀 (구단의 1군·2군 등, 코어 clubs 표) |
| `club` | `db::CLUB` (+0x0) | 767 | 구단 |
| `nation` | `db::NATIONAL_TEAM` (+0x0) | 397 | 국가대표팀 |
| `player` | `db::ACTUAL_PLAYER` (+0x278) | 989 | 선수 (코어 persons 표) |
| `staff` | `db::ACTUAL_NON_PLAYER` (+0xf8) | 623 | 감독·스태프 (코어 staff 표) |
| `human` | `db::HUMAN_NON_PLAYER` (+0x450) | 737 | 사람 감독 (myHuman()) |
| `comp` | `db::COMP` (+0x0) | 494 | 대회 (코어 comps 표) |
| `award` | `db::AWARD` (+0x0) | 522 | 상 (코어 awards 표) |
| `country` | `db::NATION` (+0x0) | 334 | 국가 (축구협회 포함, 국가대표팀과 다름) |
| `stadium` | `db::STADIUM` (+0x0) | 133 | 경기장 |
| `city` | `db::CITY` (+0x0) | 64 | 도시 |
| `continent` | `db::CONTINENT` (+0x0) | 105 | 대륙 (연맹) |
| `media` | `db::MEDIA_SOURCE` (+0x0) | 73 | 언론사 (뉴스 +0x98) |
| `contract` | `db::FULL_CONTRACT` (+0x0) | 118 | 계약 (사람 감독 +0x518 = 'myjob') |
| `loan` | `db::LOAN_CONTRACT` (+0x0) | 122 | 임대 계약 |
| `injury` | `db::INJURY` (+0x0) | 63 | 부상 종류 |

## 화면과 맞춰 본 코드

| 코드 | 종류 | 값 | 뜻 |
|---|---|---|---|
| `CSbR` | club | int | 스카우트 예산 — 내부 단위 (M71 재정 화면 4.66억 = 280000) |
| `Ccba` | team, club | int | 잔고 — 내부 단위, ×1664.7 = 원 (M55 화면 확인: 3,604억) |
| `Ccfa` | team, club | int | 구단 부대 시설(기업 시설) 수준 1~20 (M71) |
| `Ccww` | team, club | int | 주급 총액 — 내부 단위 (M55 화면 확인: 137.17억) |
| `Cdiv` | team, club | rec | 소속 리그(대회) {dref} (M56 확인) |
| `Ceda` | contract, loan | date | 계약 만료일 (계약 객체, M58 내 감독 계약 2038-06-30) |
| `Cmxp` | team, club, nation, comp, award, country | int | 미디어 예상 순위 — 정수 |
| `Cnam` | team, club, nation, comp, award, country, city, continent | str | 대륙 이름 (팀·대회에서는 소속 대륙, 예: 유럽) (M56 확인) |
| `Crcb` | club | int | 유소년 발굴 수준 1~20 (M71) |
| `Csda` | contract, loan | date | 계약 시작일 (M58) |
| `Ctea` | team, club, nation, comp, award, country, continent, contract, loan | rec | 계약한 팀 {dref} (M58) |
| `Ctfc` | team, club | int | 이적 예산 — 내부 단위 (M55 화면 확인: 4,144억) |
| `Ctlv` | club | int | 훈련 시설 수준 1~20 (M71 쓰기 확인) |
| `Ctpr` | team, club | num | 티켓 가격 — 실수 |
| `Cvag` | team, club, nation, comp, award, country | num | 스쿼드 평균 나이 — 실수 |
| `Cwwb` | team, club | int | 주급 예산 — 내부 단위 (M55 화면 확인: 133.18억) |
| `Cwwn` | contract, loan | int | 주급 추정 — 내부 단위 (M58, 화면 미확인) |
| `Cyfb` | club | int | 유소년 시설 수준 1~20 (M71) |
| `Cytv` | club | int | 유소년 코칭 수준 1~20 (M71) |
| `Hplk` | human | int | 감독의 선수 이해도 1~20 (M71) |
| `Natt` | team, club, staff, human, comp, award, country | int | 스태프 코칭 능력: 공격 1~20 (M71) |
| `Ncrr` | staff, human | int | 감독 명성 — 정수 |
| `Ndal` | staff, human | int | 스태프 성향: 반칙 허용 1~20 (M71) |
| `Nnfx` | team, club, comp, award, country | rec | 다음 경기 묶음 {fixi {fxdt 날짜, fxtm}, home {dref}, …} (M56, 뜻 일부) |
| `Npaf` | staff, human | int | 선호 포메이션 (1순위 / 2순위 추정 / 공격·수비 추정) — 정수 0~65 (포메이션 번호) |
| `Npde` | staff, human | int | 결단력 — 정수 1~20 |
| `Npdf` | staff, human | int | 선호 포메이션 (1순위 / 2순위 추정 / 공격·수비 추정) — 정수 0~65 (포메이션 번호) |
| `Npmm` | staff, human | int | 선수 관리 — 정수 1~20 |
| `Nppf` | staff, human | int | 선호 포메이션 (1순위 / 2순위 추정 / 공격·수비 추정) — 정수 0~65 (포메이션 번호) |
| `Npsf` | staff, human | int | 선호 포메이션 (1순위 / 2순위 추정 / 공격·수비 추정) — 정수 0~65 (포메이션 번호) |
| `Nptk` | staff, human | int | 전술 지식 — 정수 1~20 |
| `Ntem` | staff, human | int | 기질 (숨은 값) — 정수 1~20 |
| `PAap` | player | int | 통산 출전 — 정수 |
| `PAcg` | player | int | 골 — 정수 |
| `PCAB` | player | int | 현재 능력 CA (M58: 필드 player.ca와 같음 179) |
| `PCON` | player | int | 꾸준함 (숨은 성향) 1~20 (M71) |
| `PCRP` | player | int | 명성 — 정수 (0~10000) |
| `PHRP` | player | int | 고국 명성 0~10000 (M71) |
| `PNaC` | player, staff, human | rec | 이름 (화면 이름, M64) |
| `POps` | player | rec | 페널티 득점 (화면 이름, M64) |
| `POpt` | player | rec | PK (화면 이름, M64) |
| `PPAB` | player | int | 잠재 능력 PA (M58: 필드 player.pa와 같음 180) |
| `PSag` | player, staff, human | rec | 나이 (화면 이름, M64) |
| `PSpi` | player, staff, human | rec | 상태 (화면 이름, M64) |
| `PWRP` | player | int | 세계 명성 0~10000 (M71) |
| `Paab` | player | data | 공중 장악력 (화면 이름, M64) — 선수는 필드 player.attr.aerialReach로 읽기 |
| `Pacc` | player | data | 가속도 (화면 이름, M64) — 선수는 필드 player.attr.acceleration로 읽기 |
| `Pace` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Page` | player, staff, human | int | 나이 — 정수 |
| `Pagg` | player | data | 적극성 (화면 이름, M64) — 선수는 필드 player.attr.aggression로 읽기 |
| `Pagi` | player | data | 민첩성 (화면 이름, M64) — 선수는 필드 player.attr.agility로 읽기 |
| `Pamb` | player, staff, human | int | 야망 — 정수 1~20 |
| `Pamc` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Paml` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pamr` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pant` | player | data | 예측력 (화면 이름, M64) — 선수는 필드 player.attr.anticipation로 읽기 |
| `Pbal` | player | data | 균형 감각 (화면 이름, M64) — 선수는 필드 player.attr.balance로 읽기 |
| `Pbra` | player | data | 대담성 (화면 이름, M64) — 선수는 필드 player.attr.bravery로 읽기 |
| `PcCt` | player, staff, human | rec | 계약 묶음 {Ctyp 종류, Ceda 만료일} |
| `Pcac` | player | data | 능력 (화면 이름, M64) |
| `Pced` | player, staff, human | date | 계약 만료일 (M55 화면 확인) |
| `Pcex` | player, staff, human | date | 계약 만료일 (Pced와 같음) |
| `Pcjd` | player, staff, human | date | 지금 구단 입단일 |
| `Pcmp` | player, staff, human | data | 침착성 (화면 이름, M64) — 선수는 필드 player.attr.composure로 읽기 |
| `Pcnt` | player | data | 집중력 (화면 이름, M64) — 선수는 필드 player.attr.concentration로 읽기 |
| `Pcoa` | player | data | 페널티 박스 장악력 (화면 이름, M64) — 선수는 필드 player.attr.commandOfArea로 읽기 |
| `Pcom` | player | data | 수비 조율 (화면 이름, M64) — 선수는 필드 player.attr.communication로 읽기 |
| `Pcor` | player | data | 코너킥 (화면 이름, M64) — 선수는 필드 player.attr.corners로 읽기 |
| `Pcpt` | player, staff, human | rec | 동의한 출전 시간 (화면 이름, M64) |
| `Pcre` | player | data | 시야 (화면 이름, M64) — 선수는 필드 player.attr.vision로 읽기 |
| `Pcro` | player | data | 크로스 (화면 이름, M64) — 선수는 필드 player.attr.crossing로 읽기 |
| `Pcvy` | player, staff, human | int | 논란 성향 — 정수 1~20 |
| `Pcwg` | player, staff, human | int | 주급 — 내부 단위, ×1664.7 = 원 (M55 화면 확인: 6.01억) |
| `Pcww` | player, staff, human | int | 주급 (Pcwg와 같음) |
| `Pdce` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pdec` | player | data | 판단력 (화면 이름, M64) — 선수는 필드 player.attr.decisions로 읽기 |
| `Pdet` | player | data | 승부욕 (화면 이름, M64) — 선수는 필드 player.attr.determination로 읽기 |
| `Pdir` | player | int | 더티 플레이 (숨은 성향) 1~20 (M71) |
| `Pdls` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pdmc` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pdob` | player, staff, human | date | 생년월일 (M55 화면 확인) |
| `Pdri` | player | data | 드리블 (화면 이름, M64) — 선수는 필드 player.attr.dribbling로 읽기 |
| `Pdrs` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pdva` | player | rec | 몸값 (화면 이름, M64) |
| `Pecc` | player | data | 기행 (화면 이름, M64) — 선수는 필드 player.attr.eccentricity로 읽기 |
| `Pfcr` | player, staff, human | list | 랭킹 (화면 이름, M64) |
| `Pfin` | player | data | 골 결정력 (화면 이름, M64) — 선수는 필드 player.attr.finishing로 읽기 |
| `Pfit` | player | int | 경기 감각 0~10000 (M71) |
| `Pfla` | player | data | 천재성 (화면 이름, M64) — 선수는 필드 player.attr.flair로 읽기 |
| `Pfln` | player, staff, human | str | 전체 이름 (글) |
| `Pfrk` | player | data | 프리킥 (화면 이름, M64) — 선수는 필드 player.attr.freeKicks로 읽기 |
| `Pfrm` | player | rec | 최근 폼 — `{Prat 평균, Pgls 골, Pfrm [최근 5경기 평점]}` |
| `Pfrs` | player | data | 퍼스트 터치 (화면 이름, M64) — 선수는 필드 player.attr.firstTouch로 읽기 |
| `Pgls` | player | rec | 시즌 골 — `{valu, numb}` |
| `Pgoa` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Phan` | player | data | 볼 핸들링 (화면 이름, M64) — 선수는 필드 player.attr.handling로 읽기 |
| `Phea` | player | data | 헤더 (화면 이름, M64) — 선수는 필드 player.attr.heading로 읽기 |
| `Phei` | player, staff, human | int | 키 cm (M58 화면 187) |
| `Piap` | player, staff, human | int | 국가대표 출전 — 정수 |
| `Pigl` | player, staff, human | int | 골 — 정수 |
| `Pimp` | player | int | 중요 경기 (숨은 성향) 1~20 (M71) |
| `Pinf` | player | data | 리더십 (화면 이름, M64) — 선수는 필드 player.attr.leadership로 읽기 |
| `Pipr` | player | int | 부상 경향 (숨은 값) — 정수 1~20 |
| `Pjum` | player | data | 점프 거리 (화면 이름, M64) — 선수는 필드 player.attr.jumpingReach로 읽기 |
| `Pkic` | player | data | 골킥 (화면 이름, M64) — 선수는 필드 player.attr.kicking로 읽기 |
| `Ploy` | player, staff, human | int | 충성심 — 정수 1~20 |
| `Plsh` | player | data | 중거리 슛 (화면 이름, M64) — 선수는 필드 player.attr.longShots로 읽기 |
| `Plth` | player | data | 장거리 스로인 (화면 이름, M64) — 선수는 필드 player.attr.longThrows로 읽기 |
| `Pmar` | player | data | 일대일 마크 (화면 이름, M64) — 선수는 필드 player.attr.marking로 읽기 |
| `Pmce` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pmls` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pmor` | player | int | 사기 — 정수 (1~20) |
| `Pmrs` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pnam` | player, staff, human | rec | 이름 — `{Pfna: 전체 이름, ...}` |
| `Pnfo` | player, staff, human | rec | 상태 (화면 이름, M64) |
| `Pnft` | player | data | 타고난 체력 (화면 이름, M64) — 선수는 필드 player.attr.naturalFitness로 읽기 |
| `Pnms` | player, staff, human | rec | 이름 (화면 이름, M64) |
| `Poap` | player | rec | 경기 (화면 이름, M64) |
| `Poav` | player | rec | 시즌 평균 평점 — `{valu, numb(출전)}` |
| `Pogl` | player | rec | 골 (화면 이름, M64) |
| `Pooo` | player | data | 1:1 방어 (화면 이름, M64) — 선수는 필드 player.attr.oneOnOnes로 읽기 |
| `Porc` | player | rec | 퇴장 — `{valu, numb}` |
| `Potb` | player | data | 오프 더 볼 (화면 이름, M64) — 선수는 필드 player.attr.offTheBall로 읽기 |
| `PoxG` | player | rec | xG — `{valu, numb}` |
| `Poyc` | player | rec | 시즌 경고 — `{valu, numb}` |
| `PpAH` | player | rec | 성적 (화면 이름, M64) |
| `Ppac` | player | data | 주력 (화면 이름, M64) — 선수는 필드 player.attr.pace로 읽기 |
| `Ppas` | player | data | 패스 (화면 이름, M64) — 선수는 필드 player.attr.passing로 읽기 |
| `Ppen` | player | data | 페널티킥 (화면 이름, M64) — 선수는 필드 player.attr.penaltyTaking로 읽기 |
| `Pppc` | player | data | 잠재력 (화면 이름, M64) |
| `PpsC` | player | rec | 포지션 (화면 이름, M64) |
| `Ppsn` | player | data | 수비 위치 선정 (화면 이름, M64) — 선수는 필드 player.attr.positioning로 읽기 |
| `Pref` | player | data | 반사 신경 (화면 이름, M64) — 선수는 필드 player.attr.reflexes로 읽기 |
| `Prft` | player | int | 오른발 능숙도 1~20 (M71) |
| `Prou` | player | data | 돌진(빈도) (화면 이름, M64) — 선수는 필드 player.attr.rushingOut로 읽기 |
| `Psta` | player | data | 지구력 (화면 이름, M64) — 선수는 필드 player.attr.stamina로 읽기 |
| `Pstr` | player | data | 몸싸움 (화면 이름, M64) — 선수는 필드 player.attr.strength로 읽기 |
| `Ptac` | player | data | 태클 (화면 이름, M64) — 선수는 필드 player.attr.tackling로 읽기 |
| `Ptec` | player | data | 개인기 (화면 이름, M64) — 선수는 필드 player.attr.technique로 읽기 |
| `Pthr` | player | data | 공 던지기 (화면 이름, M64) — 선수는 필드 player.attr.throwing로 읽기 |
| `PtmT` | player | empty | 선수단 (화면 이름, M64) |
| `Ptrt` | player | num | 훈련 평점 (화면 이름, M64) |
| `PtsL` | player | rec | 선택한 포지션 (화면 이름, M64) |
| `Pttp` | player | data | 펀칭(빈도) (화면 이름, M64) — 선수는 필드 player.attr.punching로 읽기 |
| `Ptwr` | player | data | 팀워크 (화면 이름, M64) — 선수는 필드 player.attr.teamwork로 읽기 |
| `Pver` | player | int | 다재다능 (숨은 성향) 1~20 (M71) |
| `Pwbl` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pwbr` | player | int | 포지션 숙련도 (골키퍼, 중앙 수비 … 스트라이커) — 정수 1~20 (`mainPosition`이 가장 높은 것을 고름) |
| `Pwei` | player, staff, human | int | 몸무게 kg (M58 화면 81) |
| `Pwkr` | player | data | 활동량 (화면 이름, M64) — 선수는 필드 player.attr.workRate로 읽기 |
| `TCst` | team, club, nation, comp, award, country | list | 팀 스태프 목록 [{dref}] (M55) |
| `TMnR` | team, club, nation, comp, award, country | rec | 지금 팀 감독 (임시 감독 포함) — `{dref}` (0x01xxxxxx = 사람 링크 번호) |
| `Tfrm` | team, club, nation, comp, award, country | list | 최근 5경기 — 배열, **[0]이 가장 오래된 것**, 3 승 / 1·2 무 / 0 패 |
| `Tlgc` | team, club, nation, comp, award, country | int | 리그 실점 — 정수 |
| `Tlgs` | team, club, nation, comp, award, country | int | 리그 득점 — 정수 |
| `Tnam` | team, nation | rec | 팀 이름 묶음 {Tsna 짧은 이름, Tlna 정식 이름} (M56 확인) |
| `Tnts` | team, nation | int | 이적 순지출 — 정수 (게임 내부 단위, 원화 환산은 ×1664.7) |
| `Tomp` | team, nation | int | 이번 시즌 경기 수 — 정수 |
| `Topp` | team, nation | rec | 다음 경기 상대 — `{dref}` (0x18xxxxxx = 클럽 링크 번호) |
| `TpoN` | team, club, nation, comp, award, country | int | 리그 순위 — 정수 |
| `Trep` | team, nation | int | 팀 명성 0~10000 (M71) |
| `Tsar` | team, nation | rec | 최고 평점 — `{plys: [{dref}], valu}` |
| `Tsma` | team, nation | rec | 도움 1위 — `{plys: [{dref}], valu}` |
| `Tstg` | team, nation | rec | 팀 최다 득점자 — `{plys: [{dref}], valu}` |
| `Ttea` | team, nation, human | int | 구단 (화면 이름, M64) |
| `ccca` | team, club, nation | int | 구단 분위기 — 정수 |
| `ccms` | team, club, nation | int | 감독 지지도 — 정수 |
| `chil` | team, club, nation, player, staff, human, comp, award, country, stadium, city, continent, media, injury | list | 팀 선수 목록 [{dref}] (M55) |
| `cnam` | team, club, comp, award | str | 대회 이름 (팀이면 소속 리그 이름) (M56 확인) |
| `crep` | team, club, comp, award | int | 대회 명성 1~200 (M71, 조사 대회 9~179) |
| `csnm` | team, club, comp, award | str | 대회 짧은 이름 (M56 확인) |
| `duni` | team, club, nation, player, staff, human, comp, award, country, stadium, city, continent, media, injury | int | 클럽 고유 ID (팬 응원 클럽 `Salo`와 같은 번호) — 정수 |

## 쓰기 (코어 0.42.0, 기능 `write.prop`)

`api.setProp(대상, '코드', 값, {expect, reason})` → Promise `{ok, before, after, code, key, error}` (Python `ctx.set_prop`). 게임 자신의 setter(속성 객체 vtable +0x18)를 화면 스레드에서 불러요. 정수·불리언·실수만 되고, 기록되고 앱에서 되돌릴 수 있어요.

- **safe** (29개): 쓰기 → 화면 → 하루 진행 → 저장 뒤 다시 불러오기까지 확인했어요 (M71).
- **tested** (200개): setter가 받고 +1·되돌리기만 확인했어요. `{tested: true}`를 줘야 써지고, 게임에서 결과를 꼭 확인하세요.
- **쓰지 않는 코드**: `DELE`, `duni`, `dsha`, `noni`, `nsss`, `rdui`, `Ptyp` (`Ptyp`는 사람 종류를 바꿔서 게임이 객체를 새로 만들어요).

| 코드 | 종류 | 범위 | 뜻 |
|---|---|---|---|
| `Ccba` | club, team | -2000000000~2000000000 | 잔고 — 내부 단위, ×1664.7 = 원 (M55 화면 확인: 3,604억) |
| `Ctfc` | club | 0~2000000000 | 이적 예산 — 내부 단위 (M55 화면 확인: 4,144억) |
| `Cwwb` | club | 0~2000000000 | 주급 예산 — 내부 단위 (M55 화면 확인: 133.18억) |
| `CSbR` | club | 0~2000000000 | 스카우트 예산 — 내부 단위 (M71 재정 화면 4.66억 = 280000) |
| `Ctlv` | club | 1~20 | 훈련 시설 수준 1~20 (M71 쓰기 확인) |
| `Cyfb` | club | 1~20 | 유소년 시설 수준 1~20 (M71) |
| `Crcb` | club | 1~20 | 유소년 발굴 수준 1~20 (M71) |
| `Cytv` | club | 1~20 | 유소년 코칭 수준 1~20 (M71) |
| `Ccfa` | club | 1~20 | 구단 부대 시설(기업 시설) 수준 1~20 (M71) |
| `Trep` | team, nation | 0~10000 | 팀 명성 0~10000 (M71) |
| `crep` | comp | 1~200 | 대회 명성 1~200 (M71, 조사 대회 9~179) |
| `Hplk` | human | 1~20 | 감독의 선수 이해도 1~20 (M71) |
| `Natt` | staff | 1~20 | 스태프 코칭 능력: 공격 1~20 (M71) |
| `Ndal` | staff | 1~20 | 스태프 성향: 반칙 허용 1~20 (M71) |
| `PCAB` | player | 1~200 (≤ PPAB) | 현재 능력 CA (M58: 필드 player.ca와 같음 179) |
| `PPAB` | player | 1~200 (≥ PCAB) | 잠재 능력 PA (M58: 필드 player.pa와 같음 180) |
| `PCRP` | player | 0~10000 | 명성 — 정수 (0~10000) |
| `PHRP` | player | 0~10000 | 고국 명성 0~10000 (M71) |
| `PWRP` | player | 0~10000 | 세계 명성 0~10000 (M71) |
| `Pdir` | player | 1~20 | 더티 플레이 (숨은 성향) 1~20 (M71) |
| `Pimp` | player | 1~20 | 중요 경기 (숨은 성향) 1~20 (M71) |
| `Pipr` | player | 1~20 | 부상 경향 (숨은 값) — 정수 1~20 |
| `PCON` | player | 1~20 | 꾸준함 (숨은 성향) 1~20 (M71) |
| `Pver` | player | 1~20 | 다재다능 (숨은 성향) 1~20 (M71) |
| `Prft` | player | 1~20 | 오른발 능숙도 1~20 (M71) |
| `Pmor` | player | 1~20 | 사기 — 정수 (1~20) |
| `Phei` | player | 140~220 | 키 cm (M58 화면 187) |
| `Pwei` | player | 40~140 | 몸무게 kg (M58 화면 81) |
| `Pfit` | player | 0~10000 | 경기 감각 0~10000 (M71) |

<details><summary><b>tested 코드</b> (종류별)</summary>

- **award** (14): `AWap` `AWbr` `AWdr` `AWfo` `AWmg` `AWnp` `AWpo` `AWrb` `AWre` `AWrt` `AWty` `AWvf` `AWwh` `AWwr`
- **club** (44): `C2at` `C2lp` `C2pf` `C2rp` `C2ty` `C2un` `C2xa` `C3at` `C3xa` `CScP` `Cafo` `Catd` `Ccda` `Ccdr` `Ccpc` `Cdfo` `Cect` `Cels` `Cemn` `Cemx` `Cepr` `Cetl` `Chsd` `Chti` `Clpn` `Clps` `Cmle` `Cmna` `Cmtm` `Cmxa` `Cnsb` `Cntb` `Cown` `Cpfa` `Cpfr` `Cprs` `Csaf` `Csdl` `Csly` `CteA` `Cyfn` `Cyim` `TCng` `TCoi`
- **comp** (15): `CTty` `Ccre` `LAUC` `Pchd` `Pctd` `cmnl` `cmnw` `cmxl` `cmxw` `csso` `cuae` `dbty` `levl` `wben` `wbst`
- **contract** (4): `Ceda` `Csda` `Csts` `PSJO`
- **human** (12): `HSbr` `Hcit` `MHSP` `MHTY` `MREP` `MRSP` `MTSP` `Nnat` `mdty` `mibh` `mmCA` `mrCA`
- **media** (3): `Mper` `Mscp` `Msty`
- **staff** (52): `Nbpl` `Nbus` `Ncra` `Ncrr` `Ncsp` `Ncta` `Ncte` `Ndep` `Ndir` `Necc` `Nfla` `Nflx` `Nhat` `Nhmr` `Nint` `Nmig` `Nneg` `NpIM` `Npad` `Npaf` `Npat` `Npcs` `Npde` `Npdf` `Npgd` `Npgh` `Npgs` `Npld` `Npmm` `Npmo` `Nppf` `Npph` `Npre` `Npsf` `Npta` `Nptk` `Npvr` `Npwy` `Nres` `Nrot` `Ntem` `Nwid` `Nwrr` `Phes` `Pwes` `SPDm` `SPaf` `SPan` `SPdn` `SPdt` `SPpd` `Spdl`
- **country** (4): `Necf` `Ngct` `Nsod` `Nygn`
- **player** (20): `Pamc` `Paml` `Pamr` `Pdce` `Pdls` `Pdmc` `Pdrs` `Phes` `Pirr` `Pjad` `Plcp` `Pmce` `Pmrs` `PnrI` `Porl` `Prid` `Psnu` `Pwbl` `Pwbr` `Pwes`
- **stadium** (25): `Sbld` `Scov` `Scpy` `Sdah` `Sdcy` `Sdtr` `Secy` `Senv` `Slat` `Slon` `Snft` `Soty` `Sovl` `Sprr` `Sptc` `Spty` `Srbd` `Srrf` `Sscy` `SsfT` `Sste` `Su19` `Su21` `Sunt` `Sush`
- **nation** (6): `Tlpn` `Tlpo` `Tlps` `Tolp` `Tpvr` `Ttyp`
- **team** (6): `Tlpn` `Tlpo` `Tlps` `Tolp` `Tpvr` `Ttyp`
- **injury** (3): `icla` `inSr` `iscl`

</details>

## 전체 목록 (종류별)

값 종류 뒤 `{…}`는 묶음·목록 항목의 키예요.

<details><summary><b>team</b> — 760개</summary>

- **int** (218): `CFal` `CFcY` `CNGl` `CNGp` `CScA` `CTty` `Catd` `CcSC` `Ccba` `Ccfa` `Cclu` `Ccon` `Ccre`{dref} `Ccst` `Ccww` `Cfis` `Cmna` `Cmwa` `Cmxa` `Cmxp` `Cnpm` `Cnre` `Cnsb` `Cntb` `Covv` `Cown` `CpRp` `Cpfa` `Cprs` `Crsc` `Csfs` `Csrp` `Csth` `CteA` `Ctfc` `Ctra` `Ctro` `Cwwb` `Cyfn` `Cyou` `Cyrc` `LAUC` `Mfpc` `Mopm` `More` `NYRt` `Nafm` `Natt` `Ndep` `Ndfm` `Ndir` `Necf` `Nfap` `Nflm` `Nflx` `Nfml` `Nfpa` `Nfrc` `Nfrl` `Nfrp`{fmat,valu} `Ngct` `Ngim` `Nmar` `Nmya` `Nnat`{dref} `NnsC` `Noff` `Npop` `Nprf` `Nprs` `Nrep` `Nsod` `Nspf` `Nstb` `Nsts` `Ntpo` `Nupm` `Nwid` `Nygn` `PLgn` `Pcda` `Pcdf` `Pcdr` `Pchd` `Pcsb` `Pcsc` `Pcsr`{Pcsr,TeIl,icla} `Pcss` `Pctd`{stDT,valu} `Sbdy` `Scpy` `Sdcy` `Senv` `Sptc` `SsfT` `Sucy` `TClg` `TCng` `TCoi` `TCrp` `TCsg` `TDpG` `TFag` `TGwr` `THat` `THmp` `TLat` `TPco` `Tapc` `TavP` `Tbna` `TcFC` `TcFK` `TcIK` `TcSA` `TclS` `Tcon` `Tcot` `TcrC` `TcrP` `Tdna` `Tfow` `TgDK` `TgFC` `TgIK` `Tgsl` `Tgwc` `Tgws` `Tgww` `Thia` `Tks3` `TksA` `TksH` `Tlgc` `Tlgs` `Tlir` `Tlng` `Tlpn` `Tlpo` `Tlps` `Tmsg` `Tnts` `Tolp` `Tomp` `Torc` `Toyc` `Tpen` `TpoN` `TpsC` `Tpvr` `Trep` `Trsp` `Tsgc` `Tsgs` `Tsir` `Tslo` `Tsng` `TsoP` `TsoT` `Tspa` `Tstc` `Ttea` `Ttgs` `Ttva` `Ttyp` `Twhm` `Twir` `Tyts` `VARt` `WpBn` `YMAN` `cICu` `cNAR` `cREp` `cTdt` `camc` `cccA` `ccca` `ccmS` `ccms` `ccrp` `clrp` `cmtc` `cosr` `cpca` `cpms` `crep` `cumc` `dbty` `dsha` `dsub` `duni` `ftBB` `ftTB` `ftWB` `indx` `lREp` `levl` `noni` `nsss` `obtd`{Pccj,dtty} `rdui` `sfCi` `sfCx` `sfMi` `sfMx` `sfSi` `sfSx` `sqBD` `syCi` `syCx` `syMi` `syMx` `tcNT` `tcRT` `ttYc` `type` `xGPo`
- **u32** (6): `CNaC` `CPop` `CTeC` `Cncl` `actC` `sqSI`
- **num** (29): `Ccsw` `Crat` `Crgs` `Cstp` `Cstr` `Ctpr` `Cvag` `Ne10` `Ne11` `TmpO` `Tspl` `Tspw` `UCt2` `UCto` `UCy0` `UCy1` `UCy2` `UCy3` `UCy4` `UCy5` `cmnl` `cmnw` `cmxl` `cmxw` `ovxG` `oxGA` `oxGP` `oxPP` `scfd`
- **bool** (64): `BaCP` `CICF` `CLFf` `Cadm` `Cbkr` `Ccsc` `Cfak` `Chwb` `CibC` `Cico` `Cilb` `Cimd` `CisF` `Cmid` `Cmla` `Cmls` `CoII` `Cuhg` `DELE` `HKEt` `ISTP` `IsHu` `NDDB` `Neec` `Nffm` `Niaf` `Nndn` `Numa` `Sush` `TChb` `TChn` `TISC` `TISN` `TMLS` `TcFr` `Tccf` `Thnf` `Ti0t` `Ti1t` `Ti2t` `Ti3t` `Tiat` `Tibt` `Tift` `Tint` `Tirt` `Tisc` `Tisn` `Tist` `TmHc` `Toff` `VACS` `VARv` `cFin` `caca` `ccno` `cext` `csso` `cuae` `culn` `cusn` `dSAw` `disa` `nhrl`
- **str** (35): `C3ln` `Ccty`{city} `Cfdn` `ChAf` `Cnam` `Cnkn` `Csfn` `Duni` `N3ln` `NmdT` `Nnam` `Nnty` `NsdT` `Nsnm` `TC3n` `TCht` `TCln` `TCnm` `TCnn` `TCns` `TCsn` `Tava` `Tlna` `TmlD` `Tsna` `apRS` `c3ln` `cnam` `csnm` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (10): `Ccrd` `Ceed` `Cned` `TfSE` `TsSE` `TsSd` `VARd` `cTda` `wben` `wbst`
- **color** (30): `CTbc` `CTfc` `CTtc` `Tbc1` `Tbc2` `Tbc3` `Tfc1` `Tfc2` `Tfc3` `Tgbc` `Tgfc` `Tnc1` `Tnc2` `Tnc3` `Toc1` `Toc2` `Toc3` `bkcl` `cbcl` `cfcl` `ctcl` `fcol` `nbgc` `nfgc` `nmcl` `nolc` `tbcl` `ttbw` `ttcl` `wbcl`
- **rec** (147): `Bfis`{maxv,minv} `CDOF`{dref} `CFcR`{dref} `CLnf`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `CLpm`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `CLrR`{dref} `CLwR`{dref} `CMAN`{dref} `CPSm`{CCxS,Cmop,Cstm} `CRef`{dref} `CTPl`{CTPl,Tftm} `Ccfl`{clas,kind,prop} `Ccfs`{Ccfs,dinf} `Ccti`{cont} `Cdiv`{dref} `CfLk`{dref} `ChoR`{dref} `Chol`{acti} `Cknw`{Tknl,Tkrl,Tkwt} `CmgR`{StTy,cmtr} `Cnti`{Nnat} `Cocf`{clas,kind,prop} `Cpst`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Cptf`{clas,kind,prop} `Cptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Crcs`{Cclu,Crcs} `Crpc`{text,valu} `CsSP`{date,numb,valu} `Csca`{Ccsc,Ccst} `Csta`{srto,valu} `Ctea`{Ctea,dref,filt} `Ctop`{PScA,dref} `Ctsi`{stad} `Cyos`{Cclu,Cyos} `Dnat`{dref} `FiLi`{FiLi,hgst} `NMTA`{dref} `NSPC`{PLPC,PLYC} `NacC`{Next,Prev,date,itms} `Ncac`{dref} `Ncni`{dref} `NcpR`{dref} `Ncpi`{city} `Ncti`{cont} `Ncur`{curr} `Nffr`{NffT,Nffr} `Nlan`{LBac,LFlu,LGoo} `NmdR`{srto,valu} `Nmdv`{dref} `Nmni`{Pers} `Nmte`{dref} `NnfP`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `Nnfx`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `NnsR`{dref} `Nnsi`{stad} `Nptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `NrgR`{dref} `Nrgi`{regi} `Nriv`{Nrvf,Nrvo} `NsdR`{srto,valu} `SctI`{dref} `SdeS`{Sdim,Sptc} `Sdim`{lgth,widt} `TCMJ`{TCMJ,TCmg} `TCSO`{nDOF,nLma,nTdr,nbAR,nbsa,nbtR…} `TCap`{dref} `TCmg`{dref} `TDgM`{dref} `TKpA`{dref} `TKpL`{dref} `TMnR`{dref} `TVca`{dref} `TWhm`{DDhr,DDmn} `TaFx`{T5ff,valu} `TcHc`{CLPs,TcHo,clpo} `TcSs`{CElS,CInS} `Tcap`{Pers} `Tcec`{CLPs,TcHo,clpo} `TcmH`{CLPs,TcHo,clpo} `Tcrf`{dref} `Tdfn`{dref} `Tdiv`{dref} `TdvS`{dref} `Tdvi`{comp} `TfMR`{dref} `TfcD`{Cclu,Ctfs,Ctgm,Ctgp} `Tftm`{dref} `ThFx`{T5ff,valu} `Tldi`{comp} `TmDm`{plys,valu} `TmPc`{plys,valu} `Tmni`{Pers} `Tmtd`{comp} `TnWP`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `Tnam`{Tcon,Tisc,Tisn,Tlna,Tlng,Tsna…} `Tnat`{dref} `Tnef`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `Todr`{dref} `Topp`{dref} `TpLC`{PLPC,PLYC} `Tpos`{FxNm,comp,stin,valu} `Tprs`{srto,valu} `Trpc`{text,valu} `Trst`{srto,valu} `Tsar`{plys,valu} `Tsbf`{plys,size,valu} `Tsma`{plys,valu} `Tsmm`{plys,valu} `Tsrc`{plys,valu} `Tsre`{dref} `TstD`{Scpy,Secy,SexP,Sexp,Sscy,Sucy…} `Tsta`{dref} `Tstg`{plys,valu} `Tsti`{stad} `Tsyc`{plys,valu} `Ttsl`{dref} `Tvcp`{Pers} `Tycs`{srto,valu} `Tyfs`{srto,valu} `Tyrs`{srto,valu} `Tysc`{Tycs,Tyfs,Tyrs,srto,valu} `apRP`{dfpa,path,shph,srec} `cCoR`{dref} `cLAF`{dref} `cPCR`{dref} `ccti`{cont} `cdif`{text,valu} `chst`{chst} `cmtm`{dref} `cnat`{dref} `cnti`{Nnat} `comp`{dref} `crps`{srto,valu} `dref`{dref} `filt`{clas,kind,prop} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `nati`{dref} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `tpea`{plys,valu}
- **list** (126): `Accl` `AdLe` `AvCl`{dref} `AwLV` `AwLi`{AWad,AWis,AWty,AhHy,AwEd,AwSd…} `CMna`{dref} `CN5f`{dcnt,dref} `CNTM`{Ttea} `CRrs`{dcnt,dref} `CRtm` `CTMS`{Ttea} `Calt` `Cddl`{dref} `Clep`{dcnt,dref} `CmcM`{dref} `Cnat`{dref} `CoIT`{TeIl,Ttea} `CoLI`{TeIl,Ttea} `Cocl`{dref} `CsEi`{TeIl,Ttea} `Cshs`{comp} `Csps` `Cvbr`{Ctid,topi} `CxFx` `HiSe` `MLIl` `MsEi` `NCro` `NPri` `NSOD` `NSho` `NSps`{repu,valu} `NTRv`{repu,valu} `NWGv`{repu,valu} `Naag`{dref} `Nagr`{NGag,NGed,NGsd} `Nchi`{Pers} `Nctp`{affl,cont,maxa,mina,rati} `Nefr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nfmp`{desc,heig,perm,pers,rtng,side} `Nfnl`{dref} `Nlns`{lang,perc} `Nnfr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nntp`{affl,maxa,mina,nati,rati,sckn} `Nphi`{Pers} `Nrre`{dcnt,dref} `Nrtp`{affl,maxa,mina,rati,regi} `Nrvn`{leve,nati} `Ntrc`{cclv,ccmp,ctlr,ctna,ctos} `Ntxr`{capa,eytr,fram,leve,lowa,perc…} `Nwcp`{dref} `OTMS` `RelO`{dref} `Sltt` `TCrs`{PUnI,PUnJ,PUnP,PUnT} `TCst`{dref} `TDer`{dref} `TIlE`{PPIn,PPMa,PPMi,Pcpt,Pcsr,Pers…} `TLeg`{dcnt,dref} `TcMh`{mhac,mhbd} `Tchi`{Pers} `Tchl` `Tcmp`{dref} `Tdvn`{dref} `TeIl`{InSd,PPIn,PPMa,PPMi,Pcpt,Pcsr…} `Tfrm` `Tkg1`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg2`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg3`{bost,comp,kite,kits,ksbg,ksfg…} `Tko1`{bost,comp,kite,kits,ksbg,ksfg…} `Tko2`{bost,comp,kite,kits,ksbg,ksfg…} `Tko3`{bost,comp,kite,kits,ksbg,ksfg…} `Tl5f`{dcnt,dref} `Tphi`{Pers} `Tsaf` `Tshf` `Tsof` `Tsqi`{Pers} `Tvsp`{TvSp,TvsA,TvsC} `actm`{dref} `alnm` `cRwn`{Ttea,year} `chil`{chil,dref,fold,id  } `cntm`{Ttea} `crgt` `csap` `ctms`{Ttea} `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hgpc`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `nsod` `ntgs` `otms` `pAcl` `pTcl` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rgts`{Ttea} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `scpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `team`{Tcon,Ttea,Ttsl,Ttyp,type} `trns`{Pers,buyt,date,selt,valu} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (11): `Cfcs` `Chns` `Ctfs` `Cvis` `GACd` `GASd` `GTdt` `NFrh` `TFad` `TFfd` `sbin`
- **empty** (83): `CAAa` `CAAc` `CAAd` `CFGc` `CHst` `CLRe` `CLRg` `CLRs` `CMAa` `CMAn` `CMAp` `CMCc` `CMGg` `CMGn` `CMGp` `CWCe` `CWCg` `CWCs` `CWLe` `CWLg` `CWLs` `CWRe` `CWRg` `CWRs` `CWSe` `CWSg` `CWSs` `CWWe` `CWWg` `CWWs` `CmPc` `Cmag` `Cnag` `Csar` `Csbf` `Cshp` `Csht` `Csma` `Csmm` `Csrc` `Cstg` `Csyc` `HCAa` `HCAd` `IsAC` `LCAa` `LCAd` `MArl` `NAfn` `NAgl` `NApe` `NAsn` `NGfn` `NGgl` `NGpe` `NGsn` `SctW` `Sren` `TRPp` `TRsc` `TRty` `TaTF` `TmSE` `TmSd` `Tmhm` `TmlA` `TmlP` `Tndi` `Tnod` `Todo` `Trta` `cAFm` `ceas` `cnor` `cpcm` `csou` `cwes` `ssCi` `ssCx` `ssMi` `ssMx` `sySi` `sySx`
- **unknown** (1): `ocol`

</details>

<details><summary><b>club</b> — 767개</summary>

- **int** (223): `C2at` `C2lp` `C2pf` `C2ri` `C2rp` `C2ty` `C2un` `C2xa` `C3at` `C3xa` `CFal` `CFcY` `CMwg` `CNGl` `CNGp` `CSbR` `CScA` `CScP` `CTty` `CWsc` `Cafo` `Catd` `Caww` `CcSC` `Ccba` `Ccda` `Ccdr` `Ccfa` `Cclu` `Ccon` `Ccpc` `Ccre`{dref} `Ccsb` `Ccss` `Ccst` `Ccww` `Cdfo` `Cect` `Cees` `Cels` `Cemn` `Cemx` `Cepr` `Cetl` `Cexs` `Cfis` `Cfls` `Cfpl` `Chsd` `Chti` `Clls` `Clpn` `Clps` `Clst` `Cmle` `Cmna` `Cmtm` `Cmwa` `Cmxa` `Cmxp` `Cnpm` `Cnre` `Cnsb` `Cntb` `Covv` `Cown` `CpRp` `Cpfa` `Cpfr` `Cpls` `Cprp` `Cprs` `Cpsc` `Crcb` `Crep` `Crsc` `CsGA` `CsSF` `CsSS` `CsST` `CsTA` `Csaf` `Csdl` `Csfs` `Csly` `Cspt` `Csrp` `Cste` `Csth` `Csts` `CteA` `Ctfc` `Ctfu` `Ctlv` `Ctra` `Ctro` `Cwwb` `Cyfb` `Cyfn` `Cyim` `Cyou` `Cyrc` `Cytv` `LAUC` `Mfpc` `Mopm` `More` `NYRt` `Nafm` `Nafy` `Natt` `Ndep` `Ndfm` `Ndir` `Necf` `Nfap` `Nfay` `Nfdy` `Nflm` `Nflx` `Nfml` `Nfpa` `Nfrc` `Nfrl` `Nfrp`{fmat,valu} `Ngct` `Ngim` `Nmar` `Nmya` `Nnat`{dref} `NnsC` `Noff` `Npop` `Nprf` `Nprs` `Nrep` `Nsod` `Nspf` `Nstb` `Nsts` `Ntpo` `Nupm` `Nwid` `Nygn` `PLgn` `Pcda` `Pcdf` `Pcdr` `Pchd` `Pcsb` `Pcsc` `Pcsr`{Pcsr,TeIl,icla} `Pcss` `Pctd`{stDT,valu} `Sbdy` `Scpy` `Sdcy` `SsfT` `Sucy` `TClg` `TCng` `TCoi` `TCrp` `TCsg` `Tcon` `Tcot` `Tlgc` `Tlgs` `TpoN` `Tsgc` `Tsgs` `Tstc` `Ttgs` `Twhm` `Tyts` `VARt` `WpBn` `cAIS` `cREp` `cTIS` `cTdt` `camc` `cccA` `ccca` `ccmS` `ccms` `ccrp` `clrp` `cmIP` `cmUp` `cmtc` `cosr` `cpca` `cpms` `crep` `cumc` `dbty` `dsha` `dsub` `duni` `ftBB` `ftTB` `ftWB` `indx` `lREp` `levl` `noni` `nsss` `obtd`{Pccj,dtty} `rdui` `sfCi` `sfCx` `sfMi` `sfMx` `sfSi` `sfSx` `sqBD` `syCi` `syCx` `syMi` `syMx` `tcRT` `type`
- **u32** (5): `CNaC` `CPop` `CTeC` `Cncl` `actC`
- **num** (20): `CLat` `CLon` `Casp` `Ccsw` `Cf10` `Crat` `Crgs` `Cstp` `Cstr` `Ctpr` `Cvag` `Ne10` `Ne11` `Tspl` `Tspw` `cmnl` `cmnw` `cmxl` `cmxw` `scfd`
- **bool** (59): `BaCP` `C2ds` `C2hs` `CASt` `CICF` `CINA` `CIns` `CLFf` `Cadm` `Calg` `Cbkr` `Ccsc` `Cedp` `Cext` `Cfak` `Chdb` `Chwb` `CiEC` `CibC` `Cico` `Cilb` `Cimd` `CisF` `Cmid` `Cmla` `Cmls` `CnCV` `CoII` `Csot` `Cuhg` `DELE` `HKEt` `ISTP` `MlsF` `NDDB` `Neec` `Nffm` `Niaf` `Nndn` `Numa` `Sush` `TChb` `TChn` `TISC` `TISN` `TcFr` `TmHc` `VACS` `VARv` `cFin` `caca` `ccno` `cext` `csso` `cuae` `culn` `cusn` `dSAw` `nhrl`
- **str** (40): `C3ln` `CSnm` `Ca3n` `Ccty`{city} `Cfdn` `ChAf` `Chrd` `Cl3n` `Cnam` `Cnkn` `CrcS` `Csfn` `Csnm` `Csxn` `Duni` `N3ln` `NmdT` `Nnam` `Nnty` `NsdT` `Nsnm` `TC3n` `TC6n` `TCht` `TCln` `TCnm` `TCnn` `TCns` `TCsn` `Tava` `apRS` `c3ln` `cnam` `csnm` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (10): `Ccrd` `Cead` `Cebd` `Ceed` `Cesd` `Cned` `VARd` `cTda` `wben` `wbst`
- **color** (15): `CTbc` `CTfc` `CTtc` `bkcl` `cbcl` `cfcl` `ctcl` `fcol` `nbgc` `nfgc` `nolc` `tbcl` `ttbw` `ttcl` `wbcl`
- **rec** (133): `Bfis`{maxv,minv} `C2dv`{comp} `C2ld`{comp} `C2mn`{Pers} `CCSC`{dref} `CDOF`{dref} `CFcR`{dref} `CLnf`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `CLpm`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `CLrR`{dref} `CLwR`{dref} `CMAN`{dref} `CPSm`{CCxS,Cmop,Cstm} `CRef`{dref} `CTPl`{CTPl,Tftm} `Cbni`{Nnat} `Cccn`{Nnat} `Ccfl`{clas,kind,prop} `Ccfs`{Ccfs,dinf} `Cchs`{Pers} `Ccti`{cont} `Cdiv`{dref} `Cdof`{Pers} `Cdvi`{comp} `CfLk`{dref} `ChoR`{dref} `Chol`{acti} `Chph`{Pers} `Chyd`{Pers} `Cknw`{Tknl,Tkrl,Tkwt} `Cldi`{comp} `Clri`{lcrg} `Cmai`{FxNm,comp,stin,valu} `CmgR`{StTy,cmtr} `Cmni`{Pers} `Cnti`{Nnat} `Cocf`{clas,kind,prop} `Cpst`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Cptf`{clas,kind,prop} `Cpts`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Cptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Crcs`{Cclu,Crcs} `Cref`{dref} `Crpc`{text,valu} `CsSP`{date,numb,valu} `Csca`{Ccsc,Ccst} `Csta`{srto,valu} `Ctea`{Ctea,dref,filt} `Ctop`{PScA,dref} `Ctsi`{stad} `Cyos`{Cclu,Cyos} `Dnat`{dref} `FiLi`{FiLi,hgst} `NMTA`{dref} `NSPC`{PLPC,PLYC} `NacC`{Next,Prev,date,itms} `Ncac`{dref} `Ncni`{dref} `NcpR`{dref} `Ncpi`{city} `Ncti`{cont} `Ncur`{curr} `Nffr`{NffT,Nffr} `Nlan`{LBac,LFlu,LGoo} `NmdR`{srto,valu} `Nmdv`{dref} `Nmni`{Pers} `Nmte`{dref} `NnfP`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `Nnfx`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `NnsR`{dref} `Nnsi`{stad} `Nptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `NrgR`{dref} `Nrgi`{regi} `Nriv`{Nrvf,Nrvo} `NsdR`{srto,valu} `SctI`{dref} `SdeS`{Sdim,Sptc} `TCMJ`{TCMJ,TCmg} `TCSO`{nDOF,nLma,nTdr,nbAR,nbsa,nbtR…} `TCap`{dref} `TCmg`{dref} `TDgM`{dref} `TKpA`{dref} `TKpL`{dref} `TMnR`{dref} `TVca`{dref} `TWhm`{DDhr,DDmn} `TcHc`{CLPs,TcHo,clpo} `TcSs`{CElS,CInS} `Tcap`{Pers} `Tcec`{CLPs,TcHo,clpo} `TcmH`{CLPs,TcHo,clpo} `Tdfn`{dref} `Tdiv`{dref} `TdvS`{dref} `TfcD`{Cclu,Ctfs,Ctgm,Ctgp} `Tftm`{dref} `Tnat`{dref} `Tnef`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `Tpos`{FxNm,comp,stin,valu} `Tsre`{dref} `TstD`{Scpy,Secy,SexP,Sexp,Sscy,Sucy…} `Tsta`{dref} `Tvcp`{Pers} `apRP`{dfpa,path,shph,srec} `cCoR`{dref} `cLAF`{dref} `cPCR`{dref} `ccti`{cont} `cdif`{text,valu} `chst`{chst} `cmtm`{dref} `cnat`{dref} `cnti`{Nnat} `comp`{dref} `crps`{srto,valu} `dref`{dref} `filt`{clas,kind,prop} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `name`{Cnam,Pcna,Pfln,Pfna,Pihu,Pnna…} `nati`{dref} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `tpea`{plys,valu}
- **list** (166): `Accl` `AdLe` `AvCl`{dref} `AwLV` `AwLi`{AWad,AWis,AWty,AhHy,AwEd,AwSd…} `C1sq`{Pers} `C2g1`{bost,comp,kite,kits,ksbg,ksfg…} `C2g2`{bost,comp,kite,kits,ksbg,ksfg…} `C2g3`{bost,comp,kite,kits,ksbg,ksfg…} `C2o1`{bost,comp,kite,kits,ksbg,ksfg…} `C2o2`{bost,comp,kite,kits,ksbg,ksfg…} `C2o3`{bost,comp,kite,kits,ksbg,ksfg…} `C3g1`{bost,comp,kite,kits,ksbg,ksfg…} `C3g2`{bost,comp,kite,kits,ksbg,ksfg…} `C3g3`{bost,comp,kite,kits,ksbg,ksfg…} `C3o1`{bost,comp,kite,kits,ksbg,ksfg…} `C3o2`{bost,comp,kite,kits,ksbg,ksfg…} `C3o3`{bost,comp,kite,kits,ksbg,ksfg…} `CAmb` `CCBc` `CDlo`{dfpa,path,shph,srec} `CIcl` `CMna`{dref} `CN5f`{dcnt,dref} `CNTM`{Ttea} `CPsL` `CRrs`{dcnt,dref} `CRtm` `CSrs` `CTMS`{Ttea} `Cafl`{UsSK,affl,cpsd,endt,fnhl,fotb…} `Calo` `Calt` `Camc`{apfr,apps,cash,club,play,type} `Cbbl` `Cchi`{Pers} `Cdbt` `Cddl`{dref} `Cdri`{Pers} `Cdsp`{leve,perm,pers} `Cffp` `Cfln`{amot,cnre,endt,iffp,iopy,mire…} `Cfvp`{leve,perm,pers,rnsp,rrea} `ChpM`{dref} `Clep`{dcnt,dref} `Clgl` `Clhs` `Clnp` `CmcM`{dref} `CmpM`{dref} `Cnat`{dref} `Cnec` `CoIT`{TeIl,Ttea} `CoLI`{TeIl,Ttea} `Cocl`{dref} `Coin`{cash,endt,fxin,rnin,stdt,type} `CpTI` `Cphi`{Pers} `Crdl`{comp,leve,year} `Cren`{rsnn,rsnp,rsnr} `Crty`{Ttyp} `Crvc`{club,leve,rcdt,rrea} `CsEi`{TeIl,Ttea} `Csci`{Pers} `Cscm` `Cshs`{comp} `Csme` `Csoc`{club,perc,play} `Cspe` `Csps` `Ctam` `Cvbr`{Ctid,topi} `Cvfl`{UsSK,affl,cpsd,endt,fnhl,fotb…} `Cwcl` `CxFx` `HiSe` `NCro` `NPri` `NSOD` `NSho` `NSps`{repu,valu} `NTRv`{repu,valu} `NWGv`{repu,valu} `Naag`{dref} `Nagr`{NGag,NGed,NGsd} `Nchi`{Pers} `Nctp`{affl,cont,maxa,mina,rati} `Nefr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nfmp`{desc,heig,perm,pers,rtng,side} `Nfnl`{dref} `Nlns`{lang,perc} `Nnfr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nntp`{affl,maxa,mina,nati,rati,sckn} `Nphi`{Pers} `Nrre`{dcnt,dref} `Nrtp`{affl,maxa,mina,rati,regi} `Nrvn`{leve,nati} `Ntrc`{cclv,ccmp,ctlr,ctna,ctos} `Ntxr`{capa,eytr,fram,leve,lowa,perc…} `Nwcp`{dref} `OTMS` `RelO`{dref} `TCrs`{PUnI,PUnJ,PUnP,PUnT} `TCst`{dref} `TDer`{dref} `TLeg`{dcnt,dref} `TcMh`{mhac,mhbd} `Tchl` `Tdvn`{dref} `TeIl`{InSd,PPIn,PPMa,PPMi,Pcpt,Pcsr…} `Tfrm` `Tkg1`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg2`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg3`{bost,comp,kite,kits,ksbg,ksfg…} `Tko1`{bost,comp,kite,kits,ksbg,ksfg…} `Tko2`{bost,comp,kite,kits,ksbg,ksfg…} `Tko3`{bost,comp,kite,kits,ksbg,ksfg…} `Tvsp`{TvSp,TvsA,TvsC} `actm`{dref} `alnm` `cRwn`{Ttea,year} `chil`{chil,dref,fold,id  } `cntm`{Ttea} `crgt` `csap` `ctms`{Ttea} `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hgpc`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `nsod` `ntgs` `otms` `pAcl` `pTcl` `pcpt`{PtLy,PtPl} `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rgts`{Ttea} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `scpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `team`{Tcon,Ttea,Ttsl,Ttyp,type} `trns`{Pers,buyt,date,selt,valu} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (7): `CfSI` `Cfcs` `Chns` `Ctfs` `Cvis` `NFrh` `sbin`
- **empty** (88): `C2od` `CAAa` `CAAc` `CAAd` `CFGc` `CHst` `CLRe` `CLRg` `CLRs` `CMAa` `CMAn` `CMAp` `CMCc` `CMGg` `CMGn` `CMGp` `CMOg` `CMOn` `CMOp` `CPSp` `CPSx` `CRst` `CWCe` `CWCg` `CWCs` `CWLe` `CWLg` `CWLs` `CWRe` `CWRg` `CWRs` `CWSe` `CWSg` `CWSs` `CWWe` `CWWg` `CWWs` `Chaf` `CmPc` `Cmag` `Cnag` `Cndi` `Codi` `CreX` `Csar` `Csbf` `Cshp` `Csht` `Csjd` `Csld` `Csma` `Csmm` `Csmn` `Csna` `Csrc` `Cstg` `Csyc` `EDBN` `HCAa` `HCAd` `IsAC` `LCAa` `LCAd` `MArl` `NAfn` `NAgl` `NApe` `NAsn` `NGfn` `NGgl` `NGpe` `NGsn` `SctW` `Sren` `Tmhm` `Trta` `cAFm` `ceas` `cnor` `cpcm` `csou` `cwes` `ssCi` `ssCx` `ssMi` `ssMx` `sySi` `sySx`
- **unknown** (1): `ocol`

</details>

<details><summary><b>nation</b> — 397개</summary>

- **int** (107): `Cclu` `Cmxp` `Nafy` `Nfay` `Nfdy` `Nnat`{dref} `PLgn` `Sbdy` `Scpy` `Sdcy` `Senv` `Sptc` `SsfT` `Sucy` `TClg` `TCsg` `TDpG` `TFag` `TGwr` `THat` `THmp` `TLat` `TPco` `Tapc` `TavP` `Tbna` `TcFC` `TcFK` `TcIK` `TcSA` `TclS` `Tcon` `Tcot` `TcrC` `TcrP` `Tdna` `Tfow` `TgDK` `TgFC` `TgIK` `Tgsl` `Tgwc` `Tgws` `Tgww` `Thia` `Tks3` `TksA` `TksH` `Tlgc` `Tlgs` `Tlir` `Tlng` `Tlpn` `Tlpo` `Tlps` `Tmsg` `Tnts` `Tolp` `Tomp` `Torc` `Toyc` `Tpen` `TpoN` `TpsC` `Tpvr` `Trep` `Trsp` `Tsgc` `Tsgs` `Tsir` `Tslo` `Tsng` `TsoP` `TsoT` `Tspa` `Tstc` `Ttea` `Ttgs` `Ttva` `Ttyp` `Twhm` `Twir` `Tyts` `YMAN` `cICu` `cNAR` `camc` `cccA` `ccca` `ccmS` `ccms` `cmtc` `cpca` `cpms` `cumc` `dsha` `dsub` `duni` `indx` `noni` `nsss` `obtd`{Pccj,dtty} `rdui` `tcNT` `tcRT` `ttYc` `xGPo`
- **u32** (4): `CNaC` `CPop` `CTeC` `sqSI`
- **num** (17): `Crgs` `Cvag` `TmpO` `Tspl` `Tspw` `UCt2` `UCto` `UCy0` `UCy1` `UCy2` `UCy3` `UCy4` `UCy5` `ovxG` `oxGA` `oxGP` `oxPP`
- **bool** (32): `BaCP` `CLFf` `CibC` `Cmla` `Cmls` `Cuhg` `DELE` `ISTP` `IsHu` `NDDB` `Sush` `TChb` `TMLS` `Tccf` `Thnf` `Ti0t` `Ti1t` `Ti2t` `Ti3t` `Tiat` `Tibt` `Tift` `Tint` `Tirt` `Tisc` `Tisn` `Tist` `TmHc` `Toff` `ccno` `dSAw` `disa`
- **str** (20): `C3ln` `Ccty`{city} `Cfdn` `Cnam` `Csfn` `Duni` `TCln` `TCnn` `TCsn` `Tava` `Tlna` `TmlD` `Tsna` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (3): `TfSE` `TsSE` `TsSd`
- **color** (26): `CTbc` `CTfc` `CTtc` `Tbc1` `Tbc2` `Tbc3` `Tfc1` `Tfc2` `Tfc3` `Tgbc` `Tgfc` `Tnc1` `Tnc2` `Tnc3` `Toc1` `Toc2` `Toc3` `bkcl` `fcol` `nbgc` `nfgc` `nmcl` `nolc` `tbcl` `ttbw` `ttcl`
- **rec** (92): `CLnf`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `CLpm`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `CMAN`{dref} `CRef`{dref} `Ccfl`{clas,kind,prop} `Ccti`{cont} `Cocf`{clas,kind,prop} `Cptf`{clas,kind,prop} `Cptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Ctea`{Ctea,dref,filt} `Dnat`{dref} `FiLi`{FiLi,hgst} `Ncac`{dref} `Ncni`{dref} `Nffr`{NffT,Nffr} `Nlan`{LBac,LFlu,LGoo} `Nmdv`{dref} `NnsR`{dref} `Nriv`{Nrvf,Nrvo} `SctI`{dref} `SdeS`{Sdim,Sptc} `Sdim`{lgth,widt} `TCap`{dref} `TCmg`{dref} `TDgM`{dref} `TMnR`{dref} `TVca`{dref} `TaFx`{T5ff,valu} `TcHc`{CLPs,TcHo,clpo} `TcSs`{CElS,CInS} `Tcap`{Pers} `Tcec`{CLPs,TcHo,clpo} `TcmH`{CLPs,TcHo,clpo} `Tcrf`{dref} `Tdfn`{dref} `Tdiv`{dref} `TdvS`{dref} `Tdvi`{comp} `TfMR`{dref} `TfcD`{Cclu,Ctfs,Ctgm,Ctgp} `Tftm`{dref} `ThFx`{T5ff,valu} `Tldi`{comp} `TmDm`{plys,valu} `TmPc`{plys,valu} `Tmni`{Pers} `Tmtd`{comp} `TnWP`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `Tnam`{Tcon,Tisc,Tisn,Tlna,Tlng,Tsna…} `Tnat`{dref} `Tnef`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `Todr`{dref} `Topp`{dref} `TpLC`{PLPC,PLYC} `Tpos`{FxNm,comp,stin,valu} `Tprs`{srto,valu} `Trpc`{text,valu} `Trst`{srto,valu} `Tsar`{plys,valu} `Tsbf`{plys,size,valu} `Tsma`{plys,valu} `Tsmm`{plys,valu} `Tsrc`{plys,valu} `Tsre`{dref} `TstD`{Scpy,Secy,SexP,Sexp,Sscy,Sucy…} `Tsta`{dref} `Tstg`{plys,valu} `Tsti`{stad} `Tsyc`{plys,valu} `Ttsl`{dref} `Tvcp`{Pers} `Tycs`{srto,valu} `Tyfs`{srto,valu} `Tyrs`{srto,valu} `Tysc`{Tycs,Tyfs,Tyrs,srto,valu} `apRP`{dfpa,path,shph,srec} `cLAF`{dref} `chst`{chst} `cmtm`{dref} `dref`{dref} `filt`{clas,kind,prop} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `tpea`{plys,valu}
- **list** (71): `Accl` `AwLV` `AwLi`{AWad,AWis,AWty,AhHy,AwEd,AwSd…} `CMna`{dref} `CN5f`{dcnt,dref} `Cddl`{dref} `ChpM`{dref} `CmcM`{dref} `CmpM`{dref} `Cocl`{dref} `HiSe` `MLIl` `MsEi` `Naag`{dref} `Nfnl`{dref} `Nwcp`{dref} `RelO`{dref} `Sltt` `TCst`{dref} `TDer`{dref} `TIlE`{PPIn,PPMa,PPMi,Pcpt,Pcsr,Pers…} `TcMh`{mhac,mhbd} `Tchi`{Pers} `Tchl` `Tcmp`{dref} `Tdvn`{dref} `TeIl`{InSd,PPIn,PPMa,PPMi,Pcpt,Pcsr…} `Tfrm` `Tl5f`{dcnt,dref} `Tphi`{Pers} `Tsaf` `Tshf` `Tsof` `Tsqi`{Pers} `alnm` `chil`{chil,dref,fold,id  } `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hgpc`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `pAcl` `pTcl` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `team`{Tcon,Ttea,Ttsl,Ttyp,type} `trns`{Pers,buyt,date,selt,valu} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (6): `GACd` `GASd` `GTdt` `TFad` `TFfd` `sbin`
- **empty** (18): `Cmag` `Cnag` `SctW` `Sren` `TRPp` `TRsc` `TRty` `TaTF` `TmSE` `TmSd` `Tmhm` `TmlA` `TmlP` `Tndi` `Tnod` `Todo` `Trta` `cAFm`
- **unknown** (1): `ocol`

</details>

<details><summary><b>player</b> — 989개</summary>

- **int** (313): `CcCS` `CcGo` `ERCA` `ERCL` `Lsap` `Mdes` `NPag` `Npbt` `PABA` `PABF` `PAap` `PAcg` `PAla` `PAlg` `PApM` `PAps` `PAvM` `PBps` `PBrI` `PBrP` `PBys` `PCAB` `PCAP` `PCJO` `PCON` `PCRP` `PCXT` `PCas` `PCgo` `PCif` `PCmi` `PCmp` `PCmt` `PCps` `PDbl` `PDbr` `PDec` `PDhd` `PDhn` `PDij` `PDim` `PDjm` `PDkc` `PDmr` `PDmv` `PDnf` `PDoo` `PDrf` `PDri` `PDro` `PDsm` `PDst` `PDvs` `PDvt` `PDwr` `PFDv` `PFTa` `PGRP` `PHRP` `PHcs` `PI19` `PIas` `PIgo` `PImi` `PImp` `PInt` `PIps` `PLSl` `PLag` `PLij` `PMAv` `PMid` `PMlo` `PNCA` `PNCG` `PNCf` `PNJO` `PPAB` `PPAv` `PPBi` `PPMX` `PPUT` `PPUW` `PPam` `PPby` `PPch` `PPco` `PPda` `PPdf` `PPfc` `PPgk` `PPhy` `PPmn` `PPsc` `PPsp` `PPss` `PPst` `PPtd` `PRCA` `PRDF` `PRRa` `PRRo` `PRRs` `PReg` `PSJO` `PSae` `PSle` `PSpE` `PSse` `PTAv` `PTef` `PTha` `PThd`{PTha,PThr,Piin,Ptra} `PTpp` `PWRP` `PXBF` `PXBG` `PacP` `Pace` `Paco` `Pada` `Page` `Pamb` `Pamc` `Paml` `Pamr` `Papr` `ParP` `Pblc` `Pbll` `Pbpc` `Pbps` `PbvE` `PcAb` `PcAt` `PcCp` `PcTy` `Pcap` `Pcbr` `Pcbv` `Pccf` `Pcds` `Pces` `Pcfi` `Pcfl` `Pcgb` `Pcif` `Pcjo` `Pcls` `Pcnj` `Pcon` `Pcps` `Pcqu` `Pcsr`{Pcsr,TeIl,icla} `Pcst` `Pcvy` `Pcwg` `Pcww` `PcyF` `Pdat` `Pday` `Pdce` `Pdcj` `Pdir` `Pdls` `Pdmc` `Pdny` `Pdol` `Pdrs` `Pdsj` `Peth` `Pfht` `Pfit` `Pgef` `Pghm` `PgkR` `Pgoa` `Phcl` `Phei` `Phes` `Phgs` `Phln` `PhrM` `Phst` `PiCI` `Piap` `Piaw` `Pidp` `Pigl` `Pimp` `Pins` `Pipr` `Pirr` `Pisu` `Pjad` `PlLp` `PlSa` `PlSp` `PlSs` `Plcp` `PlfG` `Plft` `Plmc` `Plmt` `Ploy` `Pmce` `Pmfr` `Pmls` `Pmmf` `Pmna` `Pmnd` `Pmor` `Pmrs` `Pmst` `Pmxa` `Pmxd` `Pnar` `Pnat` `Pndc` `Pnjo` `Pnob` `Pnps` `PnrI` `PntF` `Pnts` `Poar` `Pocc` `PofR` `Pohl` `Pokp` `Pops` `Posa` `Posu` `PpAN` `PpPs` `Ppec` `Pper` `Ppln` `Pplr` `Ppos` `Ppre` `Ppro` `Ppsp` `Ppwt` `PrOb` `PrOf` `Prcm` `Prea` `PrfG` `Prft` `Prmc` `PsVL` `Psbl` `Psjb` `Pskt` `Psnt` `Psnu` `Psof` `Pspo` `PsrP` `Psrt` `Pstm` `Ptat` `Ptcn` `Ptem` `Ptfi` `Ptmo` `PtrI` `PtrM` `Ptyb` `Ptym` `Ptyp` `Puia` `Puig` `Puix` `Pusb` `Pver` `Pwbc` `Pwbl` `Pwbr` `Pwcn` `Pwea` `Pwei` `Pwes` `Pywi` `THic` `awor` `awre` `deit` `dept` `dsha` `dsub` `duni` `hsLF` `hsrF` `iRec` `icla` `inCa` `inNL` `inNS` `inNY` `inSr` `indx` `itre` `itrs` `mxtf` `noni` `npTs` `nsss` `obtd`{Pccj,dtty} `rdui` `xMcc` `xMec`
- **u32** (10): `PMcn` `PPsr` `Parc` `Pbdc` `Pbds` `Pbrc` `Pbrs` `PiCc` `Porl` `Pprm`
- **num** (6): `CcAR` `PCRD` `PCra` `PIra` `PNCR` `Ptrt`
- **bool** (119): `BRsS` `BaCP` `DELE` `Dftd` `ISTP` `NDDB` `NEUI` `NeWP` `P EU` `PAcx` `PAvN` `PAvR` `PAvU` `PBfV` `PCDB` `PCPv` `PCfV` `PFRe` `PFre` `PGcc` `PGpP` `PHCH` `PHNO` `PHoP` `PHsg` `PHsn` `PLPv` `PMrl` `PNba` `POlT` `PTas` `PTgs`{cate,impr} `PToE` `PTrt` `PcHC` `PcMM` `PcSS` `Pcml` `Pdfn` `Pdlo` `PeTR` `Pemp` `Pfiv` `Pfke` `Pfrg` `PhEb` `Phac` `Phar` `Phij` `Phnc` `Phnj` `Phnp` `Phor` `Phpj` `Phsp` `Phvt` `Piag` `Piam` `Piat` `Picr` `Pide` `Pife` `Pigo` `Pihu` `Piid` `Piin` `Pila` `Pilc` `Pima` `Pinh` `Pinp` `Piof` `Pion` `Piou` `Piph` `Pipl` `Pitl` `Pitr` `Pivi` `Plec` `PliF` `PmOD` `Pmcr` `Pmds` `Pmgp` `Pmhe` `Pmiv` `PmlD` `Pmma` `Pmrh` `Pn21` `PnCV` `PoWL` `PofC` `Popj` `Ppcr` `Prdc` `Pred` `Preg` `Prid` `Prtd` `Prtg` `PsLI` `PsfR` `Pslr` `Pspa` `Ptoa` `Purn` `Pwcm` `PycX` `btov` `ccno` `islk` `ofIT` `offr` `pbcn` `pclv` `pcta` `prdv`
- **str** (24): `Duni` `PAcn` `PAfn` `PAna` `PSCR` `PShN` `Pbrl` `Pcna` `Pfln` `Pfna` `PftS` `PnRV` `Pnhs` `Pnna` `Ppss` `PrOt` `Psna` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (22): `NpBu` `PCNj` `PCfd` `PFCS` `PIfd` `Pahd` `Pard` `PcSd` `Pced` `Pcex` `PcjY` `Pcjd` `Pdob` `Perm` `Pidd` `Pigd` `Pird` `Pled` `Plme` `Pmfe` `Pnjd` `iida`
- **color** (9): `Phce` `Pske` `bkcl` `fcol` `nbgc` `nfgc` `nolc` `tbcl` `ttcl`
- **rec** (221): `CcoR`{TPrl,posn} `DRsd` `InOf`{HOco,Hcad,Pndc,Ptof,btov,ofIT…} `Lang`{LBac,LFlu,LGoo} `MnIn`{dref} `NrSr`{Page,Pcrp,Pinp,srto,valu} `P1fm`{P1fm,Pers,Pgls,Prat} `P9te`{tetl} `P9tr`{tetl} `P9tt` `PCcj`{Cjob,Pife,Ttea,prty} `PCcl`{dref} `PCij`{Cjob,Pife,prty} `PCop`{dref} `PCsb`{Pers,minu,play,valu} `PCtm`{dref} `PExD`{PFRe,Pagn,Pcte,PcxC,Perm,Pivi…} `PHcm`{phde,phds,phmh,phmp,phms,phps…} `PHct`{phde,phds,phmh,phmp,phms,phps…} `PHgh`{dref} `PHih`{dref} `PHlt`{dref} `PHmt`{phde,phds,phmh,phmp,phms,phps…} `PHph`{phde,phds,phmh,phmp,phms,phps…} `PHpt`{phde,phds,phmh,phmp,phms,phps…} `PHst`{dref} `PHtr`{phCh,phtl} `PIDo`{Nnat} `PIGo`{Nnat} `PInn`{dref} `PIop`{dref} `PIsb`{Pers,minu,play,valu} `PMCC`{dref} `PNaC`{Pclb,PnmP} `PNat`{dref} `PNx9`{numb,valu} `PNxg`{numb,valu} `POCg`{numb,valu} `POMg`{numb,valu} `POWg`{numb,valu} `POag`{numb,valu} `POcs`{numb,valu} `POgg`{numb,valu} `POmg`{numb,valu} `POmi`{numb,valu} `POpr`{numb,valu} `POps`{numb,valu} `POpt`{numb,valu} `POwg`{numb,valu} `PRCF`{Pcon,Pfit} `PSNA`{Posa,Posu,shzv} `PSag`{day ,srto,valu} `PScj`{Cjob,Pife,prty} `PSia`{inre,otfl,pros} `PSpi`{inre,otfl,pros} `PTaf`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `PTif`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `PTnp`{PPUT,PPUW,Pers,posn,sltd,tarf…} `PTpm`{pmar,pmit} `PTta`{dref} `Pagn`{dref} `Pagt`{Pers} `ParS`{dref} `Parp` `PbIa`{dref} `Pbas`{Pbsd,Pbsn} `Pbep`{TsIx,posn} `Pbni`{Nnat} `Pbpr`{Ptcp,TPrl} `Pbsd`{dref} `Pbsn`{dref} `PcCt`{Ceda,Ctyp} `PcJj`{Cjob,Pife,Ttea,prty} `PcLp`{Clst,Pers,Ttea,disa} `PcMt`{dref} `PcTp`{Ctst,Pers,Ttea,disa} `Pcbi`{city} `Pccj`{Cjob,Pife,Ttea,prty} `PcjN`{Cjob,Pife,prty} `PclC`{dref} `Pclb`{dref} `Pcmc`{dref} `Pcnp`{dref} `Pcob`{dref} `PcpH`{plbt,plti} `Pcpc`{itms,numb} `Pcpt`{plbt,plti} `Pcrp`{Page,Pcrp,Pinp} `Pcsj`{Cjob,Pife,Ttea,prty} `Pcte`{dref} `Pcti`{Ttea} `Pctt`{dref} `Pctx`{dref} `PcxC`{CAgF,CGpm,CMCC,Cabo,Cbla,Ccla…} `PdIi`{PIfS,PKiU,PKnL,PLAd,PLoF,PLoH…} `Pdva`{PIfS,PKiU,PKnL,PLAd,PLoF,PLoH…} `Pdvi`{comp} `Pers`{dref} `Pfot`{PlfG,PrfG} `Pfpv`{pfpf,pfpl} `Pfrm`{Pers,Pfrm,Pgls,Prat} `Pfte`{tetl} `Pftr`{tetl} `Pftt` `Pgls`{numb,valu} `Phdd` `Phte`{tetl} `Phtp`{posn} `Phtr`{tetl} `Phtt` `PiaP`{Posa,Posu} `Pias`{numb,valu} `Piav`{numb,valu} `Pico`{numb,valu} `Pidt`{dref} `Pigt`{dref} `Pipi`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pist`{Piap,Pigl,Pn21,Puia,Puig,Puix} `Pkct`{dref} `Pkot` `Pkte`{tetl} `Pktr`{tetl} `Plcb` `Plcf`{Plcf,Ttea,resu} `Plcl`{dref} `Plif`{Plif,Ttea,resu} `PmCo`{Pers,objL} `PmLi`{PTpm,Pers,PmRC,PmmA,PmmR,Ttea…} `PnFT`{dref} `Pnam`{Pcna,Pfln,Pfna,Pihu,Pnna,Psna…} `Pnbi`{Nnat} `Pndf`{Nnat} `PnfN`{inre,otfl,pros} `PnfS`{inre,otfl,pros} `Pnfo`{inre,otfl,pros} `Pnhw`{Pers,Psfl,THic,srto} `PnmN`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `PnmP`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `PnmS`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pnms`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pnpc`{itms,numb} `Pnrs`{Page,Pcrp,Pinp} `Pnte`{dref} `Pnti`{Nnat} `Pntn`{dref} `Poap`{Posa,Posu} `Poas`{numb,valu} `Poav`{numb,valu} `Poco`{numb,valu} `Pofc`{DoFo,PcRs,PcoE,Pcso,offr,prcd…} `Pogl`{numb,valu} `Polc`{dref} `Pomo`{numb,valu} `Porc`{numb,valu} `PoxG`{numb,valu} `Poyc`{numb,valu} `PpAH`{atrs,disa} `Ppdv`{dref} `Ppfj`{Cjob,Pife,prty} `Ppmm`{id  ,valu} `Pprs`{Page,Pcrp,Pinp} `PpsC`{Pnps,Ppos} `Ppyd`{PSap,PSas,PSgo,PsAr,stsu} `PrSr`{Page,Pcrp,Pinp,srto,valu} `Prat`{numb,valu} `Prbi`{lcrg} `Pres`{numb,valu} `Pret` `Prob`{dref} `Prrc`{itms,numb} `Prsa`{Page,Pcrp,Pinp,srto,valu} `Psgl`{numb,valu} `PsnS`{Pigo,Psnu,PtsL} `Psnm`{PNPj,Pcjo,Pcnj,Pers,Pihu,Pipl…} `PsrS`{dref} `Psrp` `Pste`{dref} `Pt9p`{posn} `PtIN`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `PtWC`{PcwC,Ptrt} `Ptaj`{Pjle,Psjo,Ttea} `Ptfp`{posn} `Ptkp`{posn} `Ptrv`{Piid,Ptrv,date} `PtsL`{Pnfo,Ptcn,Ptcp} `Ptss`{Hret,Pirs,Ptra,TSch} `WPin`{type,valu} `apRP`{dfpa,path,shph,srec} `asTC`{Pers,itre,sltd} `dfln`{lang} `dref`{dref} `gDhI`{cdat,cjot,clna,crep,cwse,dclb…} `gLtG`{cdat,cjot,clna,crep,dclb,dhag…} `gMoD`{cdat,cjot,clna,crep,dclb,dhag…} `gStG`{cdat,cjot,clna,crep,cwse,dclb…} `hpRP`{dfpa,path,shph,srec} `iito`{Piin,maxv,minv} `inDT` `inRI`{inCa,injr} `inRs`{InSd,TrRf,icla,inMR,inRf,inRl…} `injr`{InSd,PPMa,PPMi,iRec,ifix,iida…} `ipRP`{dfpa,path,shph,srec} `itrd`{Nnat,Pers,buyt,selt,valu} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `name`{Cnam,Pcna,Pfln,Pfna,Pihu,Pnna…} `ntfl`{filt} `pACo` `pCSp`{Ppsa,Ptcp,TsIx,disa,indx} `pcrd`{valu} `plsM`{dref} `prnt`{dref} `ptiT`{PeTT,Ttea,hsLF,ottm} `ptoL`{Ttea,hsLF} `ptoT`{PeTT,Ttea,hsLF,ottm} `rlhn`{Hhum,Pjle,Prel,Preo} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `with`{resu,valu}
- **list** (114): `Aban`{band,comp,fban} `Accl` `HgCP`{Cclu,Ndne,Peqd,comp,type} `HgNP`{Ndne,Nnat,Peqd,comp,type} `HiSe` `P2ni` `PAPD` `PATL`{WAMC,WAML,WAMR,WDMC,WWBL,WWBR…} `PElg`{csln,lang,proe,prof} `PErt` `PNRs`{nati,ntin} `PNal`{dref} `POCl` `PPsT` `PQnl` `PRLS`{duty,posi,role,scor} `PRSS`{duty,posi,role,scor} `PWEI`{WAMC,WAML,WAMR,WDMC,WWBL,WWBR…} `Pacl` `Pajl`{Pjle,valu} `Pats` `Pbnl` `PcPL` `PcbV` `Pcbl` `Pcij` `Pcpl`{CPcl,CPcm,CPco,CPnt,PcPc,PcPj…} `Pcpn` `Pdcn`{0t21,Ttea,bfat,d152,days,etto} `Pdpe`{dcnt,dref} `Pdsc` `Pdsp`{leve,perm,pers} `Pefn`{dref} `Pfcl`{dcnt,dref} `Pfcr`{Pnat,Preo} `Pfpe`{dcnt,dref} `Pfvc`{club,leve,rrea} `Pfvp`{leve,perm,pers,rrea} `PhCe`{dref,numb} `PhgC`{dref,numb} `PhgN`{dref} `Phgc`{club,hgty} `Phgn`{hgty,nati} `Pici` `Picl` `Picm` `Pijl` `Pjls`{Pjle,valu} `PkHs` `Pkna`{Pkno,valu} `Plhs`{apps,cash,clid,divi,gols,hsfl…} `Pmbm` `Pmtm`{dref} `Pnph`{join,left,team,tjob} `Ponc` `Pony` `Ppma`{Prat,away,date,dref,home} `PprA`{PAvM,PAvN,PAvR,PAvU,Pers,PliF…} `Prls` `Psjr`{Pjle,valu} `PsqI`{indx,posn} `Ptof` `RelO`{dref} `TeIl`{InSd,PPIn,PPMa,PPMi,Pcpt,Pcsr…} `alnm` `band`{badd,badm,bstd,date,dayb,dsrl…} `chil`{chil,dref,fold,id  } `ddpr` `fban`{badd,bncd,cutt,dcin,lbcd,mpfy…} `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `form`{Ttea,form} `fspr`{dfpa,path,shph,srec} `hiCl`{eday,leag,lpcP,lpos,lufn,motm…} `hiLo`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hiUY`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hier`{id  ,sibs} `hisA`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `itpt` `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `pAcl` `pFet` `pTcl` `peba`{Ccas,Ccbv} `pebg` `pebx`{Ccbv,Ccga} `peig` `pewg` `pmfh`{pmfb} `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `scpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (66): `MPIn` `PAtt` `PCsc` `PIsc` `PPdm` `PScA` `PSpA` `PTra` `Paab` `Pacc` `Pagg` `Pagi` `Pant` `Pbal` `Pbla` `Pbra` `Pcab` `Pcac` `Pcmp`{dref} `Pcnt` `Pcoa` `Pcom` `Pcor` `Pcre` `Pcro` `Pdec` `Pdet` `Pdri` `Pecc` `Pfin` `Pfla` `Pfrk` `Pfrs` `Phan` `Phea` `Pica` `Pinf` `Pipa` `Pjum` `Pkic` `Plsh` `Plth` `Pmar` `Pnft` `Pooo` `Potb` `Ppab` `Ppac` `Ppas` `Ppen` `Pppc` `Ppsn` `Pref` `Prou` `Prpt` `Psta` `Pstr` `Ptac` `Ptec` `Pthr` `Ptrc` `Pttp` `Ptwr` `Pwkr` `ifix` `sbin`
- **empty** (83): `Dfcl` `Dfpk` `Dfrd` `Dpad` `HOco` `InOt` `LMrt` `PBAd` `PBsP` `PECd` `PGAs` `PGmM` `PGpf` `PGpr` `PGps` `PHmc` `PMsq` `PNPj` `POg9` `PPAR` `PPsq` `PReA` `PTbl` `PXrR` `PabP` `Pacp` `Parr` `PcRf` `Pcae` `Pcoo` `Pcpi` `Pcrd` `Pcxl` `PdCh` `PdcF` `Pdcf` `Pdcp` `Pdex` `Pfag` `Pfce` `Pfcf` `Pfgg` `Pgrp` `Phde` `Phdr` `Picb` `PinG` `PinW` `PkCA` `PkPA` `PlOt` `PlPS` `PlcD` `Pllc` `Pmac` `Pmdt` `Pmrg` `Pnai` `Pndy` `Pnpa` `Pnpr` `Ppcl` `Ppsq` `Pptt` `Prrf` `Psfc` `Psfp` `Pspc` `Ptcp` `Ptgs` `PtmT` `Ptpi` `Ptrd` `Pwps` `Pwwg` `Pwwl` `PxGP` `Pxg9` `Pyar` `Pypr` `SPDl` `SPam` `paad`
- **unknown** (2): `Pdes` `ocol`

</details>

<details><summary><b>staff</b> — 623개</summary>

- **int** (214): `CcCS` `CcGo` `Mdes` `NDat` `NDbp` `NDbs` `NDca` `NDec` `NDfi` `NDfm` `NDfx` `NDgd` `NDgh` `NDgs` `NDht` `NDim` `NDin` `NDld` `NDph` `NDpr` `NDpt` `NDrs` `NDsp` `NDsr` `NDvr` `NDwd` `NDwy` `NIst` `NNeg` `NPag` `NRCA` `NRCJ` `Natt` `Nbpl` `Nbus` `Ncha` `Nchd` `Nchf` `Nchm` `Ncra` `Ncrr` `Ncsp` `Ncta` `Ncte` `Ndal` `Ndep` `Ndir` `Necc` `Nfla` `Nflx` `Nhat` `Nhmr` `Nhnr` `Nint` `Nmig` `Nneg` `NpIM` `Npad` `Npaf` `Npat` `Npbt` `Npcs` `Npde` `Npdf` `Npgd` `Npgh` `Npgs` `Npja` `Npjd` `Npjp` `Npjr` `Npjs` `Npld` `Npmm` `Npmo` `Nppf` `Npph` `Npre` `Npsf` `Npta` `Nptk` `Npvr` `Npwy` `Nres` `Nrot` `Nsta` `Ntem` `Nwid` `Nwrr` `PABA` `PABF` `PCJO` `PCif` `PLag` `PNCA` `PNCG` `PNJO` `PPUT` `PPUW` `PPam` `PPch` `PPco` `PPda` `PPdf` `PPfc` `PPgk` `PPhy` `PPmn` `PPsc` `PPss` `PPst` `PPtd` `PReg` `PSJO` `PTha` `PThd`{PTha,PThr,Piin,Ptra} `PTpp` `PXBF` `PXBG` `PacP` `Paco` `Pada` `Page` `Pamb` `PcAb` `PcAt` `PcTy` `Pcap` `Pcbr` `Pcds` `Pces` `Pcgb` `Pcif` `Pcjo` `Pcls` `Pcnj` `Pcqu` `Pcst` `Pcvy` `Pcwg` `Pcww` `PcyF` `Pdcj` `Pdol` `Pdsj` `Peth` `Pfht` `Pghm` `Phcl` `Phei` `Phes` `Phln` `Phst` `Piap` `Pigl` `Plmc` `Plmt` `Ploy` `Pmfr` `Pmmf` `Pnat` `Pndc` `Pnjo` `Pnob` `PntF` `Pnts` `Pocc` `Ppre` `Ppro` `Prcm` `PscR` `Psca` `Psjb` `Pskt` `Psnt` `Psof` `Pspo` `Ptat` `Ptem` `Ptyb` `Ptym` `Ptyp` `Puia` `Puig` `Puix` `Pusb` `Pwei` `Pwes` `Pywi` `SPDm` `SPaf` `SPan` `SPdn` `SPdt` `SPpd` `Spdl` `Tgpl` `deit` `dept` `dsha` `dsub` `duni` `indx` `itrs` `noni` `npTs` `npcs` `npmm` `nppm` `nppp` `nppt` `nsss` `obtd`{Pccj,dtty} `rdui`
- **u32** (2): `PiCc` `Pprm`
- **num** (2): `CcAR` `PNCR`
- **bool** (75): `BRsS` `BaCP` `DELE` `ISTP` `NDDB` `NcCF` `NcNF` `NeWP` `P EU` `PAcx` `PCDB` `PFRe` `PGcc` `PHsn` `PTgs`{cate,impr} `PcHC` `PcMM` `Pcml` `Pdlo` `PeTR` `Pemp` `Pfke` `Pfrg` `PhEb` `Phac` `Phar` `Phnc` `Phnj` `Phor` `Phpj` `Phsp` `Piag` `Piam` `Picr` `Pife` `Pigo` `Pihu` `Pilc` `Pima` `Pinh` `Pinp` `Piof` `Piph` `Pipl` `Pivi` `Plec` `Pmcr` `Pmds` `Pmhe` `PmlD` `Pmma` `Pmrh` `Pn21` `PnCV` `PofC` `Popj` `Ppcr` `Prdc` `Preg` `Prtd` `Prtg` `PsfR` `Pslr` `Pspa` `Purn` `Pwcm` `btov` `ccno` `islk` `ofIT` `offr` `pbcn` `pclv` `pcta` `prdv`
- **str** (20): `Duni` `NSCR` `PAcn` `PAfn` `PAna` `PShN` `Pcna` `Pfln` `Pfna` `PnRV` `Pnhs` `Pnna` `Psna` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (15): `NpBu` `PCNj` `Pahd` `Pard` `PcSd` `Pced` `Pcex` `PcjY` `Pcjd` `Pdob` `Pidd` `Pigd` `Plme` `Pmfe` `Pnjd`
- **color** (9): `Phce` `Pske` `bkcl` `fcol` `nbgc` `nfgc` `nolc` `tbcl` `ttcl`
- **rec** (137): `Ccdf`{numb,valu} `Cclf`{numb,valu} `Ccmd`{numb,valu} `Ccml`{numb,valu} `Ccmw`{numb,valu} `Ccwr`{numb,valu} `Cnga`{numb,valu} `Cngd`{numb,valu} `Cngf`{numb,valu} `Cnmd`{numb,valu} `Cnml`{numb,valu} `Cnmw`{numb,valu} `Cnwr`{numb,valu} `InOf`{HOco,Hcad,Pndc,Ptof,btov,ofIT…} `KNpK`{Tknl,Tkrl,Tkwt} `Lang`{LBac,LFlu,LGoo} `NPxD`{PFRe,Pagn,Pcte,PcxC,Pihu} `NrSr`{Page,Pcrp,Pinp,srto,valu} `PCcj`{Cjob,Pife,Ttea,prty} `PCij`{Cjob,Pife,prty} `PCtm`{dref} `PHgh`{dref} `PHih`{dref} `PHlt`{dref} `PHst`{dref} `PIDo`{Nnat} `PIGo`{Nnat} `PMCC`{dref} `PNaC`{Pclb,PnmP} `PNat`{dref} `PSNA`{Posa,Posu,shzv} `PSag`{day ,srto,valu} `PScj`{Cjob,Pife,prty} `PSia`{inre,otfl,pros} `PSpi`{inre,otfl,pros} `PTaf`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `PTif`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `PTnp`{PPUT,PPUW,Pers,posn,sltd,tarf…} `PTta`{dref} `Pagn`{dref} `Pagt`{Pers} `PbIa`{dref} `Pbas`{Pbsd,Pbsn} `Pbep`{TsIx,posn} `Pbni`{Nnat} `Pbsd`{dref} `Pbsn`{dref} `PcCt`{Ceda,Ctyp} `PcJj`{Cjob,Pife,Ttea,prty} `PcLp`{Clst,Pers,Ttea,disa} `PcMt`{dref} `PcTp`{Ctst,Pers,Ttea,disa} `Pcbi`{city} `Pccj`{Cjob,Pife,Ttea,prty} `PcjN`{Cjob,Pife,prty} `Pclb`{dref} `Pcnp`{dref} `Pcob`{dref} `PcpH`{plbt,plti} `Pcpt`{plbt,plti} `Pcrp`{Page,Pcrp,Pinp} `Pcsj`{Cjob,Pife,Ttea,prty} `Pcte`{dref} `Pcti`{Ttea} `Pctt`{dref} `Pctx`{dref} `PcxC`{CAgF,CGpm,CMCC,Cabo,Cbla,Ccla…} `Pdvi`{comp} `Pers`{dref} `Pfpv`{pfpf,pfpl} `Pidt`{dref} `Pigt`{dref} `Pipi`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pist`{Piap,Pigl,Pn21,Puia,Puig,Puix} `Pkct`{dref} `Plcl`{dref} `PmCo`{Pers,objL} `PmLi`{PTpm,Pers,PmRC,PmmA,PmmR,Ttea…} `PnFT`{dref} `Pnam`{Pcna,Pfln,Pfna,Pihu,Pnna,Psna…} `Pnbi`{Nnat} `PnfN`{inre,otfl,pros} `PnfS`{inre,otfl,pros} `Pnfo`{inre,otfl,pros} `PnmN`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `PnmP`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `PnmS`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pnms`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pnrs`{Page,Pcrp,Pinp} `Pnte`{dref} `Pnti`{Nnat} `Pofc`{DoFo,PcRs,PcoE,Pcso,offr,prcd…} `Polc`{dref} `Ppdv`{dref} `Ppfj`{Cjob,Pife,prty} `Ppmm`{id  ,valu} `Pprs`{Page,Pcrp,Pinp} `PrHi`{PrHi,dbrc} `PrSr`{Page,Pcrp,Pinp,srto,valu} `Prbi`{lcrg} `Pret` `Prob`{dref} `Prsa`{Page,Pcrp,Pinp,srto,valu} `Psnm`{PNPj,Pcjo,Pcnj,Pers,Pihu,Pipl…} `Pste`{dref} `PtIN`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `Ptaj`{Pjle,Psjo,Ttea} `Ptss`{Hret,Pirs,Ptra,TSch} `Tgaa`{numb,valu} `Tgfr`{numb,valu} `Tgwr`{numb,valu} `WPin`{type,valu} `apRP`{dfpa,path,shph,srec} `asTC`{Pers,itre,sltd} `dfln`{lang} `dref`{dref} `gDhI`{cdat,cjot,clna,crep,cwse,dclb…} `gLtG`{cdat,cjot,clna,crep,dclb,dhag…} `gMoD`{cdat,cjot,clna,crep,dclb,dhag…} `gStG`{cdat,cjot,clna,crep,cwse,dclb…} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `itrd`{Nnat,Pers,buyt,selt,valu} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `name`{Cnam,Pcna,Pfln,Pfna,Pihu,Pnna…} `ntfl`{filt} `pACo` `pcrd`{valu} `plsM`{dref} `prnt`{dref} `rlhn`{Hhum,Pjle,Prel,Preo} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `with`{resu,valu}
- **list** (95): `Accl` `Ccla`{numb,valu} `EDpr` `HiSe` `NAte` `NPAT`{cond,cont,name,valu,weig} `NRLS`{jobr,scor} `P2ni` `PElg`{csln,lang,proe,prof} `PErt` `PNRs`{nati,ntin} `PNal`{dref} `POCl` `PPsT` `Pacl` `Pajl`{Pjle,valu} `Pats` `PcPL` `PcbV` `Pcbl` `Pcpl`{CPcl,CPcm,CPco,CPnt,PcPc,PcPj…} `Pcpn` `Pdcn`{0t21,Ttea,bfat,d152,days,etto} `Pdpe`{dcnt,dref} `Pdsc` `Pdsp`{leve,perm,pers} `Pfcl`{dcnt,dref} `Pfcr`{Pnat,Preo} `Pfpe`{dcnt,dref} `Pfvc`{club,leve,rrea} `Pfvp`{leve,perm,pers,rrea} `Phgc`{club,hgty} `Phgn`{hgty,nati} `Pici` `Picl` `Picm` `Pjls`{Pjle,valu} `PkHs` `Pkna`{Pkno,valu} `Plhs`{apps,cash,clid,divi,gols,hsfl…} `Pmbm` `Pmtm`{dref} `Pnph`{join,left,team,tjob} `Ponc` `Pony` `Prls` `Psjr`{Pjle,valu} `Ptof` `RelO`{dref} `alnm` `chil`{chil,dref,fold,id  } `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hiCl`{eday,leag,lpcP,lpos,lufn,motm…} `hiLo`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hiUY`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hier`{id  ,sibs} `hisA`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `itpt` `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `npRf` `ntgs` `pAcl` `pTcl` `peba`{Ccas,Ccbv} `pebg` `pebx`{Ccbv,Ccga} `peig` `pewg` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `scpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (3): `PPdm` `Pcmp`{dref} `sbin`
- **empty** (49): `HOco` `PECd` `PHmc` `PMsq` `PNPj` `Pacp` `Parr` `PcRf` `Pcae` `Pcoo` `Pcpi` `Pcrd` `Pcxl` `PdCh` `PdcF` `Pdcf` `Pdcp` `Pdex` `Pfag` `Pfce` `Pfcf` `Pfgg` `Pgrp` `Phde` `Phdr` `Picb` `PinG` `PinW` `PlOt` `Pmac` `Pnai` `Pnpa` `Pnpr` `Ppcl` `Prrf` `Psfc` `Psfp` `Ptgs` `Ptpi` `Ptrd` `Pwps` `Pwwg` `Pwwl` `Pyar` `Pypr` `cpsa` `npMs` `npsa` `paad`
- **unknown** (2): `Pdes` `ocol`

</details>

<details><summary><b>human</b> — 737개</summary>

- **int** (265): `CcCS` `CcGo` `HDEI` `HDYI` `HSCI` `HSTI` `HSbr` `HTER` `HTRI` `Hcit` `Hcoi` `Hdpb` `Hfca` `Hhei` `Hhoa` `Hmdh` `Hpac` `Hpco` `Hpcs` `Hpct` `Hplk` `Hpll` `Hsqd` `Hsre` `HtSf` `Htco` `Hwei` `Hynk` `MHSP` `MHTY` `MREP` `MRSP` `MTSP` `Mdes` `NDat` `NDbp` `NDbs` `NDca` `NDec` `NDfi` `NDfm` `NDfx` `NDgd` `NDgh` `NDgs` `NDht` `NDim` `NDin` `NDld` `NDph` `NDpr` `NDpt` `NDrs` `NDsp` `NDsr` `NDvr` `NDwd` `NDwy` `NIst` `NNeg` `NPag` `NRCA` `NRCJ` `Natt` `Nbpl` `Nbus` `Ncha` `Nchd` `Nchf` `Nchm` `Ncra` `Ncrr` `Ncsp` `Ncta` `Ncte` `Ndal` `Ndep` `Ndir` `Ndoh` `Necc` `Nfla` `Nflx` `Ngda` `Nhat` `Nhmr` `Nhnr` `Nint` `Nmig` `Nnat`{dref} `Nneg` `NpIM` `Npad` `Npaf` `Npat` `Npbt` `Npcs` `Npde` `Npdf` `Npgd` `Npgh` `Npgs` `Npja` `Npjd` `Npjp` `Npjr` `Npjs` `Npld` `Npmm` `Npmo` `Nppf` `Npph` `Npre` `Npsf` `Npta` `Nptk` `Npvr` `Npwy` `Nres` `Nrot` `Nsta` `Ntem` `Nwid` `Nwrr` `PABA` `PABF` `PCJO` `PCif` `PLag` `PNCA` `PNCG` `PNJO` `PPUT` `PPUW` `PPam` `PPch` `PPco` `PPda` `PPdf` `PPfc` `PPgk` `PPhy` `PPmn` `PPsc` `PPss` `PPst` `PPtd` `PReg` `PSJO` `PTha` `PThd`{PTha,PThr,Piin,Ptra} `PTpp` `PXBF` `PXBG` `PacP` `Paco` `Pada` `Page` `Pamb` `PcAb` `PcAt` `PcTy` `Pcap` `Pcbr` `Pcds` `Pces` `Pcgb` `Pcif` `Pcjo` `Pcls` `Pcnj` `Pcqu` `Pcst` `Pctd`{stDT,valu} `Pcvy` `Pcwg` `Pcww` `PcyF` `Pdcj` `Pdol` `Pdsj` `Peth` `Pfht` `Pghm` `Phcl` `Phei` `Phes` `Phln` `Phst` `Piap` `Pigl` `Plmc` `Plmt` `Ploy` `Pmfr` `Pmmf` `Pnat` `Pndc` `Pnjo` `Pnob` `PntF` `Pnts` `Pocc` `Ppre` `Ppro` `Prcm` `PscR` `Psca` `Psjb` `Pskt` `Psnt` `Psof` `Pspo` `Ptat` `Ptem` `Ptyb` `Ptym` `Ptyp` `Puia` `Puig` `Puix` `Pusb` `Pwei` `Pwes` `Pywi` `SPDm` `SPaf` `SPan` `SPdn` `SPdt` `SPpd` `Spdl` `Tgpl` `Ttea` `deit` `dept` `dsha` `dsub` `duni` `fav1` `fav2` `fav3` `fave` `indx` `itrs` `lng2` `lng3` `mdty` `mibh` `mmCA` `mrCA` `noni` `npTs` `npcs` `npmm` `nppm` `nppp` `nppt` `nsss` `obtd`{Pccj,dtty} `ottm` `phuf` `rdui` `repu` `tmvw` `tovw`
- **u32** (3): `HPbr` `PiCc` `Pprm`
- **num** (2): `CcAR` `PNCR`
- **bool** (88): `BRsS` `BaCP` `DELE` `Himp` `Hsak` `ISTP` `NDDB` `NcCF` `NcNF` `NeWP` `P EU` `PAcx` `PCDB` `PFRe` `PGcc` `PHsn` `PTgs`{cate,impr} `PcHC` `PcMM` `Pcml` `Pdfn` `Pdlo` `PeTR` `Pemp` `Pfke` `Pfrg` `PhEb` `Phac` `Phar` `Phnc` `Phnj` `Phor` `Phpj` `Phsp` `Piag` `Piam` `Picr` `Pife` `Pigo` `Pihu` `Pilc` `Pima` `Pinh` `Pinp` `Piof` `Piph` `Pipl` `Pivi` `Plec` `Pmcr` `Pmds` `Pmhe` `PmlD` `Pmma` `Pmrh` `Pn21` `PnCV` `PofC` `Popj` `Ppcr` `Prdc` `Preg` `Prtd` `Prtg` `PsfR` `Pslr` `Pspa` `Purn` `Pwcm` `btov` `ccno` `dnPO` `islk` `istu` `mCan` `mgen` `mmAR` `mmCR` `mrAR` `mrCR` `ofIT` `offr` `pbcn` `pclv` `pcta` `prdv` `usep` `vnsA`
- **str** (24): `Duni` `NSCR` `PAcn` `PAfn` `PAna` `PShN` `Pcna` `Pfln` `Pfna` `PnRV` `Pnhs` `Pnna` `Psna` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `namf` `naml` `pass` `tpRS` `verp`
- **date** (17): `NpBu` `PCNj` `Pahd` `Pard` `PcSd` `Pced` `Pcex` `PcjY` `Pcjd` `Pdob` `Pidd` `Pigd` `Plme` `Pmfe` `Pnjd` `date` `hlsd`
- **color** (9): `Phce` `Pske` `bkcl` `fcol` `nbgc` `nfgc` `nolc` `tbcl` `ttcl`
- **rec** (149): `CLwR`{dref} `Ccdf`{numb,valu} `Cclf`{numb,valu} `Ccmd`{numb,valu} `Ccml`{numb,valu} `Ccmw`{numb,valu} `Ccwr`{numb,valu} `Cnga`{numb,valu} `Cngd`{numb,valu} `Cngf`{numb,valu} `Cnmd`{numb,valu} `Cnml`{numb,valu} `Cnmw`{numb,valu} `Cnwr`{numb,valu} `HDlN`{dref} `HTlN`{dref} `HUlN`{dref} `Hpri`{day ,valu} `InOf`{HOco,Hcad,Pndc,Ptof,btov,ofIT…} `KNpK`{Tknl,Tkrl,Tkwt} `Lang`{LBac,LFlu,LGoo} `NPxD`{PFRe,Pagn,Pcte,PcxC,Pihu} `NrSr`{Page,Pcrp,Pinp,srto,valu} `PCcj`{Cjob,Pife,Ttea,prty} `PCij`{Cjob,Pife,prty} `PCtm`{dref} `PHgh`{dref} `PHih`{dref} `PHlt`{dref} `PHst`{dref} `PIDo`{Nnat} `PIGo`{Nnat} `PMCC`{dref} `PNaC`{Pclb,PnmP} `PNat`{dref} `PPcd`{cStD,cStE,datS,enDT,stDT} `PSNA`{Posa,Posu,shzv} `PSag`{day ,srto,valu} `PScj`{Cjob,Pife,prty} `PSia`{inre,otfl,pros} `PSpi`{inre,otfl,pros} `PTaf`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `PTif`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `PTnp`{PPUT,PPUW,Pers,posn,sltd,tarf…} `PTta`{dref} `Pagn`{dref} `Pagt`{Pers} `PbIa`{dref} `Pbas`{Pbsd,Pbsn} `Pbep`{TsIx,posn} `Pbni`{Nnat} `Pbsd`{dref} `Pbsn`{dref} `PcCt`{Ceda,Ctyp} `PcJj`{Cjob,Pife,Ttea,prty} `PcLp`{Clst,Pers,Ttea,disa} `PcMt`{dref} `PcTp`{Ctst,Pers,Ttea,disa} `Pcbi`{city} `Pccj`{Cjob,Pife,Ttea,prty} `PcjN`{Cjob,Pife,prty} `Pclb`{dref} `Pcld`{cStD,cStE,datS,enDT,stDT} `Pcnp`{dref} `Pcob`{dref} `PcpH`{plbt,plti} `Pcpt`{plbt,plti} `Pcrp`{Page,Pcrp,Pinp} `Pcsj`{Cjob,Pife,Ttea,prty} `Pcte`{dref} `Pcti`{Ttea} `Pctt`{dref} `Pctx`{dref} `PcxC`{CAgF,CGpm,CMCC,Cabo,Cbla,Ccla…} `Pdvi`{comp} `Pers`{dref} `Pfpv`{pfpf,pfpl} `Pidt`{dref} `Pigt`{dref} `Pipi`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pist`{Piap,Pigl,Pn21,Puia,Puig,Puix} `Pkct`{dref} `Plcl`{dref} `PmCo`{Pers,objL} `PmLi`{PTpm,Pers,PmRC,PmmA,PmmR,Ttea…} `PnFT`{dref} `Pnam`{Pcna,Pfln,Pfna,Pihu,Pnna,Psna…} `Pnbi`{Nnat} `PnfN`{inre,otfl,pros} `PnfS`{inre,otfl,pros} `Pnfo`{inre,otfl,pros} `PnmN`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `PnmP`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `PnmS`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pnms`{PNPj,Pcjo,Pcnj,Pers,Piag,Pihu…} `Pnrs`{Page,Pcrp,Pinp} `Pnte`{dref} `Pnti`{Nnat} `Pofc`{DoFo,PcRs,PcoE,Pcso,offr,prcd…} `Polc`{dref} `Ppdv`{dref} `Ppfj`{Cjob,Pife,prty} `Ppmm`{id  ,valu} `Pprs`{Page,Pcrp,Pinp} `PrHi`{PrHi,dbrc} `PrSr`{Page,Pcrp,Pinp,srto,valu} `Prbi`{lcrg} `Pret` `Prob`{dref} `Prsa`{Page,Pcrp,Pinp,srto,valu} `Psnm`{PNPj,Pcjo,Pcnj,Pers,Pihu,Pipl…} `Pste`{dref} `PtIN`{PPUT,PPUW,PPra,PPrd,Pers,Ppwt…} `Ptaj`{Pjle,Psjo,Ttea} `Ptss`{Hret,Pirs,Ptra,TSch} `Tgaa`{numb,valu} `Tgfr`{numb,valu} `Tgwr`{numb,valu} `WPin`{type,valu} `apRP`{dfpa,path,shph,srec} `asTC`{Pers,itre,sltd} `dfln`{lang} `dref`{dref} `gDhI`{cdat,cjot,clna,crep,cwse,dclb…} `gLtG`{cdat,cjot,clna,crep,dclb,dhag…} `gMoD`{cdat,cjot,clna,crep,dclb,dhag…} `gStG`{cdat,cjot,clna,crep,cwse,dclb…} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `itrd`{Nnat,Pers,buyt,selt,valu} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `mcHF`{id  ,valu} `mprf`{mprf} `name`{Cnam,Pcna,Pfln,Pfna,Pihu,Pnna…} `ntfl`{filt} `pACo` `pCeD`{cStD,cStE,datS,enDT,stDT} `pcER`{cStD,cStE,datS,enDT,stDT} `pcFD`{cStD,cStE,datS,enDT,stDT} `pcrd`{valu} `plsM`{dref} `prnt`{dref} `rlhn`{Hhum,Pjle,Prel,Preo} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `with`{resu,valu}
- **list** (112): `Accl` `Ccla`{numb,valu} `EDpr` `HBRq`{Ctid,topi} `HPrA` `HTcm` `HTco` `HTna` `Hbpm` `Hclu` `Hfcs` `HiSe` `Hmpm` `Hnns` `Hppm`{MPed,MPmg,MPmt,MPol,MPot,MPpc…} `Hrtp` `HtRa`{Pttp,id  ,itms,posn,text} `HtWc` `HtWn` `NAte` `NPAT`{cond,cont,name,valu,weig} `NRLS`{jobr,scor} `P2ni` `PElg`{csln,lang,proe,prof} `PErt` `PNRs`{nati,ntin} `PNal`{dref} `POCl` `PPsT` `Pacl` `Pajl`{Pjle,valu} `Pats` `PcPL` `PcbV` `Pcbl` `Pcpl`{CPcl,CPcm,CPco,CPnt,PcPc,PcPj…} `Pcpn` `Pdcn`{0t21,Ttea,bfat,d152,days,etto} `Pdpe`{dcnt,dref} `Pdsc` `Pdsp`{leve,perm,pers} `Pfcl`{dcnt,dref} `Pfcr`{Pnat,Preo} `Pfpe`{dcnt,dref} `Pfvc`{club,leve,rrea} `Pfvp`{leve,perm,pers,rrea} `Phgc`{club,hgty} `Phgn`{hgty,nati} `Phrp`{dref} `Pici` `Picl` `Picm` `Pjls`{Pjle,valu} `PkHs` `Pkna`{Pkno,valu} `Plhs`{apps,cash,clid,divi,gols,hsfl…} `Pmbm` `Pmtm`{dref} `Pnph`{join,left,team,tjob} `Ponc` `Pony` `Prls` `Psjr`{Pjle,valu} `Ptof` `RelO`{dref} `alnm` `chil`{chil,dref,fold,id  } `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hiCl`{eday,leag,lpcP,lpos,lufn,motm…} `hiLo`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hiUY`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hier`{id  ,sibs} `hisA`{Pcti,Pjle,Pjtd,Pltd,Pmdj,Ttea…} `hlog`{dfpa,path,shph,srec} `hmsk` `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `itpt` `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `npRf` `ntgs` `pAcl` `pTcl` `peba`{Ccas,Ccbv} `pebg` `pebx`{Ccbv,Ccga} `peig` `pewg` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `scpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (6): `HdvW` `HunW` `PPdm` `Pcmp`{dref} `mgpc` `sbin`
- **empty** (58): `CHSP` `CHTY` `CREP` `CRSP` `CTSP` `Cibh` `HOco` `Hcad` `Hsde` `PECd` `PHmc` `PMsq` `PNPj` `Pacp` `Parr` `PcRf` `Pcae` `Pcoo` `Pcpi` `Pcrd` `Pcxl` `PdCh` `PdcF` `Pdcf` `Pdcp` `Pdex` `Pfag` `Pfce` `Pfcf` `Pfgg` `Pgrp` `Phde` `Phdr` `Picb` `PinG` `PinW` `PlOt` `Pmac` `Pnai` `Pnpa` `Pnpr` `Ppcl` `Prrf` `Psfc` `Psfp` `Ptgs` `Ptpi` `Ptrd` `Pwps` `Pwwg` `Pwwl` `Pyar` `Pypr` `cpsa` `iadC` `npMs` `npsa` `paad`
- **unknown** (4): `Ntce` `Pdes` `hlst` `ocol`

</details>

<details><summary><b>comp</b> — 494개</summary>

- **int** (114): `CFcY` `CScA` `CTty` `Catd` `Ccre`{dref} `Cmna` `Cmxa` `Cmxp` `Cnpm` `Cnre` `CpRp` `Ctro` `LAUC` `Mfpc` `Mopm` `More` `NYRt` `Nafm` `Nafy` `Natt` `Ndep` `Ndfm` `Ndir` `Necf` `Nfap` `Nfay` `Nfdy` `Nflm` `Nflx` `Nfml` `Nfpa` `Nfrc` `Nfrl` `Nfrp`{fmat,valu} `Ngct` `Ngim` `Nmar` `Nmya` `Nnat`{dref} `NnsC` `Noff` `Npop` `Nprf` `Nprs` `Nrep` `Nsod` `Nspf` `Nstb` `Nsts` `Ntpo` `Nupm` `Nwid` `Nygn` `PLgn` `Pcda` `Pcdf` `Pcdr` `Pchd` `Pcsb` `Pcsc` `Pcsr`{Pcsr,TeIl,icla} `Pcss` `Pctd`{stDT,valu} `Sbdy` `Scpy` `Sdcy` `SsfT` `Sucy` `TClg` `TCng` `TCoi` `TCrp` `TCsg` `Tcon` `Tcot` `Tlgc` `Tlgs` `TpoN` `Tsgc` `Tsgs` `Tstc` `Ttgs` `Tyts` `VARt` `WpBn` `cREp` `cTdt` `ccrp` `clrp` `cosr` `crep` `dbty` `dsha` `dsub` `duni` `indx` `lREp` `levl` `noni` `nsss` `obtd`{Pccj,dtty} `rdui` `sfCi` `sfCx` `sfMi` `sfMx` `sfSi` `sfSx` `syCi` `syCx` `syMi` `syMx` `tcRT` `type`
- **u32** (5): `CNaC` `CPop` `CTeC` `Cncl` `actC`
- **num** (11): `Crgs` `Cvag` `Ne10` `Ne11` `Tspl` `Tspw` `cmnl` `cmnw` `cmxl` `cmxw` `scfd`
- **bool** (36): `BaCP` `CICF` `Cfak` `Cimd` `CisF` `Cmid` `CoII` `Cuhg` `DELE` `HKEt` `ISTP` `NDDB` `Neec` `Nffm` `Niaf` `Nndn` `Numa` `Sush` `TChb` `TChn` `TISC` `TISN` `TcFr` `TmHc` `VACS` `VARv` `cFin` `caca` `ccno` `cext` `csso` `cuae` `culn` `cusn` `dSAw` `nhrl`
- **str** (31): `C3ln` `Ccty`{city} `Cfdn` `Cnam` `Cnkn` `Csfn` `Duni` `N3ln` `NmdT` `Nnam` `Nnty` `NsdT` `Nsnm` `TC3n` `TCht` `TCln` `TCnm` `TCnn` `TCns` `TCsn` `Tava` `apRS` `c3ln` `cnam` `csnm` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (4): `VARd` `cTda` `wben` `wbst`
- **color** (15): `CTbc` `CTfc` `CTtc` `bkcl` `cbcl` `cfcl` `ctcl` `fcol` `nbgc` `nfgc` `nolc` `tbcl` `ttbw` `ttcl` `wbcl`
- **rec** (93): `CFcR`{dref} `CLrR`{dref} `CLwR`{dref} `CRef`{dref} `Ccfl`{clas,kind,prop} `Ccti`{cont} `CfLk`{dref} `ChoR`{dref} `Chol`{acti} `Cnti`{Nnat} `Cocf`{clas,kind,prop} `Cpst`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Cptf`{clas,kind,prop} `Cptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Ctea`{Ctea,dref,filt} `FiLi`{FiLi,hgst} `NMTA`{dref} `NSPC`{PLPC,PLYC} `NacC`{Next,Prev,date,itms} `Ncac`{dref} `Ncni`{dref} `NcpR`{dref} `Ncpi`{city} `Ncti`{cont} `Ncur`{curr} `Nffr`{NffT,Nffr} `Nlan`{LBac,LFlu,LGoo} `NmdR`{srto,valu} `Nmdv`{dref} `Nmni`{Pers} `Nmte`{dref} `NnfP`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `Nnfx`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `NnsR`{dref} `Nnsi`{stad} `Nptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `NrgR`{dref} `Nrgi`{regi} `Nriv`{Nrvf,Nrvo} `NsdR`{srto,valu} `SctI`{dref} `SdeS`{Sdim,Sptc} `TCMJ`{TCMJ,TCmg} `TCSO`{nDOF,nLma,nTdr,nbAR,nbsa,nbtR…} `TCap`{dref} `TCmg`{dref} `TDgM`{dref} `TKpA`{dref} `TKpL`{dref} `TMnR`{dref} `TVca`{dref} `TWhm`{DDhr,DDmn} `TcHc`{CLPs,TcHo,clpo} `TcSs`{CElS,CInS} `Tcap`{Pers} `Tcec`{CLPs,TcHo,clpo} `TcmH`{CLPs,TcHo,clpo} `Tdfn`{dref} `Tdiv`{dref} `TdvS`{dref} `TfcD`{Cclu,Ctfs,Ctgm,Ctgp} `Tftm`{dref} `Tnat`{dref} `Tnef`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `Tpos`{FxNm,comp,stin,valu} `Tsre`{dref} `TstD`{Scpy,Secy,SexP,Sexp,Sscy,Sucy…} `Tsta`{dref} `Tvcp`{Pers} `apRP`{dfpa,path,shph,srec} `cCoR`{dref} `cPCR`{dref} `ccti`{cont} `cdif`{text,valu} `chst`{chst} `cnat`{dref} `cnti`{Nnat} `comp`{dref} `crps`{srto,valu} `dref`{dref} `filt`{clas,kind,prop} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `nati`{dref} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `tpea`{plys,valu}
- **list** (112): `Accl` `AdLe` `AvCl`{dref} `AwLV` `AwLi`{AWad,AWis,AWty,AhHy,AwEd,AwSd…} `CMna`{dref} `CNTM`{Ttea} `CRrs`{dcnt,dref} `CRtm` `CTMS`{Ttea} `Calt` `Cddl`{dref} `ChpM`{dref} `CmcM`{dref} `CmpM`{dref} `Cnat`{dref} `CoIT`{TeIl,Ttea} `CoLI`{TeIl,Ttea} `Cocl`{dref} `CsEi`{TeIl,Ttea} `Cshs`{comp} `Csps` `CxFx` `HiSe` `NCro` `NPri` `NSOD` `NSho` `NSps`{repu,valu} `NTRv`{repu,valu} `NWGv`{repu,valu} `Naag`{dref} `Nagr`{NGag,NGed,NGsd} `Nchi`{Pers} `Nctp`{affl,cont,maxa,mina,rati} `Nefr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nfmp`{desc,heig,perm,pers,rtng,side} `Nfnl`{dref} `Nlns`{lang,perc} `Nnfr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nntp`{affl,maxa,mina,nati,rati,sckn} `Nphi`{Pers} `Nrre`{dcnt,dref} `Nrtp`{affl,maxa,mina,rati,regi} `Nrvn`{leve,nati} `Ntrc`{cclv,ccmp,ctlr,ctna,ctos} `Ntxr`{capa,eytr,fram,leve,lowa,perc…} `Nwcp`{dref} `OTMS` `RelO`{dref} `TCrs`{PUnI,PUnJ,PUnP,PUnT} `TCst`{dref} `TDer`{dref} `TLeg`{dcnt,dref} `TcMh`{mhac,mhbd} `Tchl` `Tdvn`{dref} `TeIl`{InSd,PPIn,PPMa,PPMi,Pcpt,Pcsr…} `Tfrm` `Tkg1`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg2`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg3`{bost,comp,kite,kits,ksbg,ksfg…} `Tko1`{bost,comp,kite,kits,ksbg,ksfg…} `Tko2`{bost,comp,kite,kits,ksbg,ksfg…} `Tko3`{bost,comp,kite,kits,ksbg,ksfg…} `Tvsp`{TvSp,TvsA,TvsC} `actm`{dref} `alnm` `cRwn`{Ttea,year} `chil`{chil,dref,fold,id  } `cntm`{Ttea} `crgt` `csap` `ctms`{Ttea} `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hgpc`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `nsod` `ntgs` `otms` `pAcl` `pTcl` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rgts`{Ttea} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `team`{Tcon,Ttea,Ttsl,Ttyp,type} `trns`{Pers,buyt,date,selt,valu} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (3): `Chns` `NFrh` `sbin`
- **empty** (69): `CAAa` `CAAc` `CAAd` `CFGc` `CHst` `CLRe` `CLRg` `CLRs` `CMAa` `CMAn` `CMAp` `CMCc` `CMGg` `CMGn` `CMGp` `CWCe` `CWCg` `CWCs` `CWLe` `CWLg` `CWLs` `CWRe` `CWRg` `CWRs` `CWSe` `CWSg` `CWSs` `CWWe` `CWWg` `CWWs` `CmPc` `Csar` `Csbf` `Cshp` `Csht` `Csma` `Csmm` `Csrc` `Cstg` `Csyc` `HCAa` `HCAd` `IsAC` `LCAa` `LCAd` `MArl` `NAfn` `NAgl` `NApe` `NAsn` `NGfn` `NGgl` `NGpe` `NGsn` `SctW` `Sren` `Trta` `VARf` `ceas` `cnor` `cpcm` `csou` `cwes` `ssCi` `ssCx` `ssMi` `ssMx` `sySi` `sySx`
- **unknown** (1): `ocol`

</details>

<details><summary><b>award</b> — 522개</summary>

- **int** (128): `AWap` `AWbr` `AWdr` `AWfo` `AWmg` `AWnp` `AWpo` `AWrb` `AWre` `AWrt` `AWty` `AWvf` `AWwh` `AWwr` `CFcY` `CScA` `CTty` `Catd` `Ccre`{dref} `Cmna` `Cmxa` `Cmxp` `Cnpm` `Cnre` `CpRp` `Ctro` `LAUC` `Mfpc` `Mopm` `More` `NYRt` `Nafm` `Nafy` `Natt` `Ndep` `Ndfm` `Ndir` `Necf` `Nfap` `Nfay` `Nfdy` `Nflm` `Nflx` `Nfml` `Nfpa` `Nfrc` `Nfrl` `Nfrp`{fmat,valu} `Ngct` `Ngim` `Nmar` `Nmya` `Nnat`{dref} `NnsC` `Noff` `Npop` `Nprf` `Nprs` `Nrep` `Nsod` `Nspf` `Nstb` `Nsts` `Ntpo` `Nupm` `Nwid` `Nygn` `PLgn` `Pcda` `Pcdf` `Pcdr` `Pchd` `Pcsb` `Pcsc` `Pcsr`{Pcsr,TeIl,icla} `Pcss` `Pctd`{stDT,valu} `Sbdy` `Scpy` `Sdcy` `SsfT` `Sucy` `TClg` `TCng` `TCoi` `TCrp` `TCsg` `Tcon` `Tcot` `Tlgc` `Tlgs` `TpoN` `Tsgc` `Tsgs` `Tstc` `Ttgs` `Tyts` `VARt` `WpBn` `cREp` `cTdt` `ccrp` `clrp` `cosr` `crep` `dbty` `dsha` `dsub` `duni` `indx` `lREp` `levl` `noni` `nsss` `obtd`{Pccj,dtty} `rdui` `sfCi` `sfCx` `sfMi` `sfMx` `sfSi` `sfSx` `syCi` `syCx` `syMi` `syMx` `tcRT` `type`
- **u32** (5): `CNaC` `CPop` `CTeC` `Cncl` `actC`
- **num** (11): `Crgs` `Cvag` `Ne10` `Ne11` `Tspl` `Tspw` `cmnl` `cmnw` `cmxl` `cmxw` `scfd`
- **bool** (39): `AWis` `AWop` `AWus` `BaCP` `CICF` `Cfak` `Cimd` `CisF` `Cmid` `CoII` `Cuhg` `DELE` `HKEt` `ISTP` `NDDB` `Neec` `Nffm` `Niaf` `Nndn` `Numa` `Sush` `TChb` `TChn` `TISC` `TISN` `TcFr` `TmHc` `VACS` `VARv` `cFin` `caca` `ccno` `cext` `csso` `cuae` `culn` `cusn` `dSAw` `nhrl`
- **str** (32): `AWna` `C3ln` `Ccty`{city} `Cfdn` `Cnam` `Cnkn` `Csfn` `Duni` `N3ln` `NmdT` `Nnam` `Nnty` `NsdT` `Nsnm` `TC3n` `TCht` `TCln` `TCnm` `TCnn` `TCns` `TCsn` `Tava` `apRS` `c3ln` `cnam` `csnm` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (6): `AWad` `AWda` `VARd` `cTda` `wben` `wbst`
- **color** (18): `AWbc` `AWfc` `AWtc` `CTbc` `CTfc` `CTtc` `bkcl` `cbcl` `cfcl` `ctcl` `fcol` `nbgc` `nfgc` `nolc` `tbcl` `ttbw` `ttcl` `wbcl`
- **rec** (97): `AWci`{cont} `AWmi`{comp} `AWni`{Nnat} `CFcR`{dref} `CLrR`{dref} `CLwR`{dref} `CRef`{dref} `Ccfl`{clas,kind,prop} `Ccti`{cont} `CfLk`{dref} `ChoR`{dref} `Chol`{acti} `Cnti`{Nnat} `Cocf`{clas,kind,prop} `Cpst`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Cptf`{clas,kind,prop} `Cptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Ctea`{Ctea,dref,filt} `FiLi`{FiLi,hgst} `NMTA`{dref} `NSPC`{PLPC,PLYC} `NacC`{Next,Prev,date,itms} `Ncac`{dref} `Ncni`{dref} `NcpR`{dref} `Ncpi`{city} `Ncti`{cont} `Ncur`{curr} `Nffr`{NffT,Nffr} `Nlan`{LBac,LFlu,LGoo} `NmdR`{srto,valu} `Nmdv`{dref} `Nmni`{Pers} `Nmte`{dref} `NnfP`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `Nnfx`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `NnsR`{dref} `Nnsi`{stad} `Nptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `NrgR`{dref} `Nrgi`{regi} `Nriv`{Nrvf,Nrvo} `NsdR`{srto,valu} `SctI`{dref} `SdeS`{Sdim,Sptc} `TCMJ`{TCMJ,TCmg} `TCSO`{nDOF,nLma,nTdr,nbAR,nbsa,nbtR…} `TCap`{dref} `TCmg`{dref} `TDgM`{dref} `TKpA`{dref} `TKpL`{dref} `TMnR`{dref} `TVca`{dref} `TWhm`{DDhr,DDmn} `TcHc`{CLPs,TcHo,clpo} `TcSs`{CElS,CInS} `Tcap`{Pers} `Tcec`{CLPs,TcHo,clpo} `TcmH`{CLPs,TcHo,clpo} `Tdfn`{dref} `Tdiv`{dref} `TdvS`{dref} `TfcD`{Cclu,Ctfs,Ctgm,Ctgp} `Tftm`{dref} `Tnat`{dref} `Tnef`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `Tpos`{FxNm,comp,stin,valu} `Tsre`{dref} `TstD`{Scpy,Secy,SexP,Sexp,Sscy,Sucy…} `Tsta`{dref} `Tvcp`{Pers} `apRP`{dfpa,path,shph,srec} `awrd`{dref} `cCoR`{dref} `cPCR`{dref} `ccti`{cont} `cdif`{text,valu} `chst`{chst} `cnat`{dref} `cnti`{Nnat} `comp`{dref} `crps`{srto,valu} `dref`{dref} `filt`{clas,kind,prop} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `nati`{dref} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `tpea`{plys,valu}
- **list** (111): `Accl` `AdLe` `AvCl`{dref} `AwLV` `AwLi`{AWad,AWis,AWty,AhHy,AwEd,AwSd…} `CMna`{dref} `CNTM`{Ttea} `CRrs`{dcnt,dref} `CRtm` `CTMS`{Ttea} `Calt` `Cddl`{dref} `ChpM`{dref} `CmcM`{dref} `CmpM`{dref} `Cnat`{dref} `CoIT`{TeIl,Ttea} `CoLI`{TeIl,Ttea} `Cocl`{dref} `CsEi`{TeIl,Ttea} `Cshs`{comp} `Csps` `CxFx` `HiSe` `NCro` `NPri` `NSOD` `NSho` `NSps`{repu,valu} `NTRv`{repu,valu} `NWGv`{repu,valu} `Naag`{dref} `Nagr`{NGag,NGed,NGsd} `Nchi`{Pers} `Nctp`{affl,cont,maxa,mina,rati} `Nefr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nfmp`{desc,heig,perm,pers,rtng,side} `Nfnl`{dref} `Nlns`{lang,perc} `Nnfr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nntp`{affl,maxa,mina,nati,rati,sckn} `Nphi`{Pers} `Nrre`{dcnt,dref} `Nrtp`{affl,maxa,mina,rati,regi} `Nrvn`{leve,nati} `Ntrc`{cclv,ccmp,ctlr,ctna,ctos} `Ntxr`{capa,eytr,fram,leve,lowa,perc…} `Nwcp`{dref} `OTMS` `RelO`{dref} `TCrs`{PUnI,PUnJ,PUnP,PUnT} `TCst`{dref} `TDer`{dref} `TLeg`{dcnt,dref} `TcMh`{mhac,mhbd} `Tchl` `Tdvn`{dref} `TeIl`{InSd,PPIn,PPMa,PPMi,Pcpt,Pcsr…} `Tfrm` `Tkg1`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg2`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg3`{bost,comp,kite,kits,ksbg,ksfg…} `Tko1`{bost,comp,kite,kits,ksbg,ksfg…} `Tko2`{bost,comp,kite,kits,ksbg,ksfg…} `Tko3`{bost,comp,kite,kits,ksbg,ksfg…} `Tvsp`{TvSp,TvsA,TvsC} `actm`{dref} `alnm` `cRwn`{Ttea,year} `chil`{chil,dref,fold,id  } `cntm`{Ttea} `crgt` `csap` `ctms`{Ttea} `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hgpc`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `nsod` `ntgs` `otms` `pAcl` `pTcl` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rgts`{Ttea} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `team`{Tcon,Ttea,Ttsl,Ttyp,type} `trns`{Pers,buyt,date,selt,valu} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (3): `Chns` `NFrh` `sbin`
- **empty** (71): `AWma` `AWxa` `CAAa` `CAAc` `CAAd` `CFGc` `CHst` `CLRe` `CLRg` `CLRs` `CMAa` `CMAn` `CMAp` `CMCc` `CMGg` `CMGn` `CMGp` `CWCe` `CWCg` `CWCs` `CWLe` `CWLg` `CWLs` `CWRe` `CWRg` `CWRs` `CWSe` `CWSg` `CWSs` `CWWe` `CWWg` `CWWs` `CmPc` `Csar` `Csbf` `Cshp` `Csht` `Csma` `Csmm` `Csrc` `Cstg` `Csyc` `HCAa` `HCAd` `IsAC` `LCAa` `LCAd` `MArl` `NAfn` `NAgl` `NApe` `NAsn` `NGfn` `NGgl` `NGpe` `NGsn` `SctW` `Sren` `Trta` `VARf` `ceas` `cnor` `cpcm` `csou` `cwes` `ssCi` `ssCx` `ssMi` `ssMx` `sySi` `sySx`
- **unknown** (1): `ocol`

</details>

<details><summary><b>country</b> — 334개</summary>

- **int** (71): `Catd` `Cmna` `Cmxa` `Cmxp` `NYRt` `Nafm` `Nafy` `Natt` `Ndep` `Ndfm` `Ndir` `Necf` `Nfap` `Nfay` `Nfdy` `Nflm` `Nflx` `Nfml` `Nfpa` `Nfrc` `Nfrl` `Nfrp`{fmat,valu} `Ngct` `Ngim` `Nmar` `Nmya` `Nnat`{dref} `NnsC` `Noff` `Npop` `Nprf` `Nprs` `Nrep` `Nsod` `Nspf` `Nstb` `Nsts` `Ntpo` `Nupm` `Nwid` `Nygn` `PLgn` `Sbdy` `Scpy` `Sdcy` `SsfT` `Sucy` `TClg` `TCng` `TCoi` `TCrp` `TCsg` `Tcon` `Tcot` `Tlgc` `Tlgs` `TpoN` `Tsgc` `Tsgs` `Tstc` `Ttgs` `Tyts` `dsha` `dsub` `duni` `indx` `noni` `nsss` `obtd`{Pccj,dtty} `rdui` `tcRT`
- **u32** (3): `CNaC` `CPop` `CTeC`
- **num** (6): `Crgs` `Cvag` `Ne10` `Ne11` `Tspl` `Tspw`
- **bool** (19): `BaCP` `Cuhg` `DELE` `ISTP` `NDDB` `Neec` `Nffm` `Niaf` `Nndn` `Numa` `Sush` `TChb` `TChn` `TISC` `TISN` `TcFr` `TmHc` `ccno` `nhrl`
- **str** (28): `C3ln` `Ccty`{city} `Cfdn` `Cnam` `Cnkn` `Csfn` `Duni` `N3ln` `NmdT` `Nnam` `Nnty` `NsdT` `Nsnm` `TC3n` `TCht` `TCln` `TCnm` `TCnn` `TCns` `TCsn` `Tava` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **color** (11): `CTbc` `CTfc` `CTtc` `bkcl` `fcol` `nbgc` `nfgc` `nolc` `tbcl` `ttbw` `ttcl`
- **rec** (75): `CRef`{dref} `Ccfl`{clas,kind,prop} `Ccti`{cont} `Cnti`{Nnat} `Cocf`{clas,kind,prop} `Cptf`{clas,kind,prop} `Cptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Ctea`{Ctea,dref,filt} `FiLi`{FiLi,hgst} `NMTA`{dref} `NSPC`{PLPC,PLYC} `NacC`{Next,Prev,date,itms} `Ncac`{dref} `Ncni`{dref} `NcpR`{dref} `Ncpi`{city} `Ncti`{cont} `Ncur`{curr} `Nffr`{NffT,Nffr} `Nlan`{LBac,LFlu,LGoo} `NmdR`{srto,valu} `Nmdv`{dref} `Nmni`{Pers} `Nmte`{dref} `NnfP`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxPF…} `Nnfx`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `NnsR`{dref} `Nnsi`{stad} `Nptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `NrgR`{dref} `Nrgi`{regi} `Nriv`{Nrvf,Nrvo} `NsdR`{srto,valu} `SctI`{dref} `SdeS`{Sdim,Sptc} `TCMJ`{TCMJ,TCmg} `TCSO`{nDOF,nLma,nTdr,nbAR,nbsa,nbtR…} `TCap`{dref} `TCmg`{dref} `TDgM`{dref} `TKpA`{dref} `TKpL`{dref} `TMnR`{dref} `TVca`{dref} `TcHc`{CLPs,TcHo,clpo} `TcSs`{CElS,CInS} `Tcap`{Pers} `Tcec`{CLPs,TcHo,clpo} `TcmH`{CLPs,TcHo,clpo} `Tdfn`{dref} `Tdiv`{dref} `TdvS`{dref} `TfcD`{Cclu,Ctfs,Ctgm,Ctgp} `Tftm`{dref} `Tnat`{dref} `Tnef`{FRfr,Fsrs,FxAN,FxHN,FxNm,FxRl…} `Tpos`{FxNm,comp,stin,valu} `Tsre`{dref} `TstD`{Scpy,Secy,SexP,Sexp,Sscy,Sucy…} `Tsta`{dref} `Tvcp`{Pers} `apRP`{dfpa,path,shph,srec} `dref`{dref} `filt`{clas,kind,prop} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec} `tpea`{plys,valu}
- **list** (89): `Accl` `AwLV` `AwLi`{AWad,AWis,AWty,AhHy,AwEd,AwSd…} `CMna`{dref} `Calt` `Cddl`{dref} `ChpM`{dref} `CmcM`{dref} `CmpM`{dref} `Cnat`{dref} `Cocl`{dref} `HiSe` `NCro` `NPri` `NSho` `NSps`{repu,valu} `NTRv`{repu,valu} `NWGv`{repu,valu} `Naag`{dref} `Nagr`{NGag,NGed,NGsd} `Nchi`{Pers} `Nctp`{affl,cont,maxa,mina,rati} `Nefr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nfmp`{desc,heig,perm,pers,rtng,side} `Nfnl`{dref} `Nlns`{lang,perc} `Nnfr`{endt,fren,nfra,nfrc,nfrn,nfrr…} `Nntp`{affl,maxa,mina,nati,rati,sckn} `Nphi`{Pers} `Nrre`{dcnt,dref} `Nrtp`{affl,maxa,mina,rati,regi} `Nrvn`{leve,nati} `Ntrc`{cclv,ccmp,ctlr,ctna,ctos} `Ntxr`{capa,eytr,fram,leve,lowa,perc…} `Nwcp`{dref} `RelO`{dref} `TCrs`{PUnI,PUnJ,PUnP,PUnT} `TCst`{dref} `TDer`{dref} `TLeg`{dcnt,dref} `TcMh`{mhac,mhbd} `Tchl` `Tdvn`{dref} `TeIl`{InSd,PPIn,PPMa,PPMi,Pcpt,Pcsr…} `Tfrm` `Tkg1`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg2`{bost,comp,kite,kits,ksbg,ksfg…} `Tkg3`{bost,comp,kite,kits,ksbg,ksfg…} `Tko1`{bost,comp,kite,kits,ksbg,ksfg…} `Tko2`{bost,comp,kite,kits,ksbg,ksfg…} `Tko3`{bost,comp,kite,kits,ksbg,ksfg…} `Tvsp`{TvSp,TvsA,TvsC} `alnm` `chil`{chil,dref,fold,id  } `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hgpc`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `pAcl` `pTcl` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `team`{Tcon,Ttea,Ttsl,Ttyp,type} `trns`{Pers,buyt,date,selt,valu} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (2): `NFrh` `sbin`
- **empty** (29): `CLRe` `CLRg` `CLRs` `CWCe` `CWCg` `CWCs` `CWLe` `CWLg` `CWLs` `CWRe` `CWRg` `CWRs` `CWSe` `CWSg` `CWSs` `CWWe` `CWWg` `CWWs` `NAfn` `NAgl` `NApe` `NAsn` `NGfn` `NGgl` `NGpe` `NGsn` `SctW` `Sren` `Trta`
- **unknown** (1): `ocol`

</details>

<details><summary><b>stadium</b> — 133개</summary>

- **int** (27): `Sbdy` `Scpy` `Sdcy` `Sdtr` `Secy` `Senv` `Snft` `Soty` `Sprr` `Sptc` `Spty` `Srby` `Sscy` `SsfT` `Sste` `Su19` `Su21` `Sucy` `Sunt` `dsha` `dsub` `duni` `indx` `noni` `nsss` `obtd`{Pccj,dtty} `rdui`
- **num** (10): `SlIM` `Slat` `Slon` `Smnl` `Smnw` `Smxl` `Smxw` `Spln` `Spwd` `SwIM`
- **bool** (15): `BaCP` `DELE` `ISTP` `NDDB` `Nucf` `Scov` `Sdah` `Sext` `Sitg` `Snew` `Sovl` `Srrf` `Sush` `Wucf` `ccno`
- **str** (9): `Duni` `Snam` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (5): `Doco` `Sbld` `SplR` `Sprl` `Srbd`
- **color** (5): `Sscl` `bkcl` `fcol` `tbcl` `ttcl`
- **rec** (23): `SMdi`{lgth,widt} `SctI`{dref} `Scti`{city} `SdeS`{Sdim,Sptc} `Sdim`{lgth,widt} `Snat`{dref} `Snti`{Nnat} `Sowi`{Cclu} `Sown`{dref} `TstD`{Scpy,Secy,SexP,Sexp,Sscy,Sucy…} `apRP`{dfpa,path,shph,srec} `dref`{dref} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `ntfl`{filt} `prnt`{dref} `stad`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec}
- **list** (31): `HiSe` `RelO`{dref} `Scpc` `Ssds`{capc,cond,exis,indx,iuse,reno…} `Susr` `alnm` `chil`{chil,dref,fold,id  } `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `port`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sibs`{dref} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (2): `Ctfs` `sbin`
- **empty** (5): `Scas` `SctW` `Snbs` `Splr` `Sren`
- **unknown** (1): `ocol`

</details>

<details><summary><b>city</b> — 64개</summary>

- **int** (8): `dsha` `dsub` `duni` `indx` `noni` `nsss` `obtd`{Pccj,dtty} `rdui`
- **bool** (5): `BaCP` `DELE` `ISTP` `NDDB` `ccno`
- **str** (9): `Cnam` `Duni` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **rec** (13): `Clri`{lcrg} `Cnti`{Nnat} `apRP`{dfpa,path,shph,srec} `dref`{dref} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `lpRP`{dfpa,path,shph,srec} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec}
- **list** (28): `Calt` `HiSe` `RelO`{dref} `alnm` `chil`{chil,dref,fold,id  } `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `port`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sibs`{dref} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (1): `sbin`

</details>

<details><summary><b>continent</b> — 105개</summary>

- **int** (8): `dsha` `dsub` `duni` `indx` `noni` `nsss` `obtd`{Pccj,dtty} `rdui`
- **u32** (3): `CNaC` `CPop` `CTeC`
- **num** (1): `Crgs`
- **bool** (5): `BaCP` `DELE` `ISTP` `NDDB` `ccno`
- **str** (13): `C3ln` `Ccty`{city} `Cfdn` `Cnam` `Csfn` `Duni` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **color** (7): `CTbc` `CTfc` `CTtc` `bkcl` `fcol` `tbcl` `ttcl`
- **rec** (19): `CRef`{dref} `Ccfl`{clas,kind,prop} `Cocf`{clas,kind,prop} `Cptf`{clas,kind,prop} `Cptt`{COti,COto,Phpj,Prtd,TfIN,TfOU…} `Ctea`{Ctea,dref,filt} `FiLi`{FiLi,hgst} `apRP`{dfpa,path,shph,srec} `dref`{dref} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec}
- **list** (47): `Accl` `AwLV` `AwLi`{AWad,AWis,AWty,AhHy,AwEd,AwSd…} `CMna`{dref} `Cddl`{dref} `ChpM`{dref} `CmcM`{dref} `CmpM`{dref} `Cnat`{dref} `Cocl`{dref} `HiSe` `RelO`{dref} `alnm` `chil`{chil,dref,fold,id  } `ddpr` `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `icon`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mbpc`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `pAcl` `pTcl` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sbpc`{dfpa,path,shph,srec} `sibs`{dref} `smpc`{dfpa,path,shph,srec} `trns`{Pers,buyt,date,selt,valu} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (1): `sbin`
- **unknown** (1): `ocol`

</details>

<details><summary><b>media</b> — 73개</summary>

- **int** (11): `Mper` `Mscp` `Msty` `dsha` `dsub` `duni` `indx` `noni` `nsss` `obtd`{Pccj,dtty} `rdui`
- **bool** (5): `BaCP` `DELE` `ISTP` `NDDB` `ccno`
- **str** (11): `Duni` `Mgna` `Mnrf` `Murl` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **date** (1): `Mdlp`
- **color** (2): `fcol` `ttcl`
- **rec** (12): `apRP`{dfpa,path,shph,srec} `dref`{dref} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `link`{Ttea,awrd,objt} `lpRP`{dfpa,path,shph,srec} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec}
- **list** (30): `HiSe` `Mtyp`{Mtyp} `RelO`{dref} `alnm` `chil`{chil,dref,fold,id  } `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mnpc`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `port`{dfpa,path,shph,srec} `prpc`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sibs`{dref} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (1): `sbin`

</details>

<details><summary><b>contract</b> — 118개</summary>

- **int** (25): `CAgF` `CGpm` `Cclc` `Ccsb` `Clbn` `Clmf` `Clmt` `Clst` `Cmmr` `Crlb` `Csts` `Ctco` `Ctoo` `CtrL` `CtrT` `Ctst` `Ctyp` `CwwA` `CwwT` `Cwwa` `Cwwn` `CwyF` `PCJO` `PSJO` `mlCT`
- **bool** (16): `CGCC` `CIRC` `CMCR` `CMHE` `CWCM` `Ccsc` `Chwp` `Cilc` `Cilf` `Circ` `Citc` `Clec` `Cmma` `Crdc` `Cvmr` `ydpc`
- **date** (5): `Ceda` `Clme` `Csda` `Ctld` `Cwpp`
- **rec** (7): `CMCC`{dref} `Cloa`{dref} `Cnxs`{Pers,plbt,plti,ptpt,ptpv} `CnyF`{Pers,plbt,plti,ptpt,ptpv} `Cpns`{Pers,plbt,plti,ptpt,ptpv} `Csfp`{Pers,plbt,plti,ptpt,ptpv} `Ctea`{Ctea,dref,filt}
- **list** (11): `Cbla` `Ccbl` `Ccla`{numb,valu} `Ccpb` `Ceba` `Cebg` `Cebx` `Ceig` `Cewg` `Cnpe` `Cspe`
- **empty** (54): `C1YE` `C1YP` `C1YR` `CABA` `CABF` `CACE` `CACP` `CGBF` `CGBG` `CIIG` `CIIW` `CMDc` `CMDe` `CMFF` `CMFH` `CMFe` `CMHe` `CMac` `CMae` `CMcc` `CMce` `CNPA` `CPCL` `CPGP` `CPIG` `CPIW` `CPWS` `CRRA` `CSOF` `CSPC` `CSPP` `CTDD` `CTDI` `CXBF` `CXBG` `Cabo` `Cdtf` `Cgbo` `Cicb` `Cmfc` `Cmfe` `Cnpr` `Cpwi` `Crrf` `Crwd` `Csbo` `CsqH` `Csqs` `Ctgs` `Ctyb` `Cusb` `Cywi` `PMsq` `WpCw`

</details>

<details><summary><b>loan</b> — 122개</summary>

- **int** (34): `CAgF` `CGpm` `Cclc` `Ccsb` `ClDf` `ClDw` `ClEt` `ClMm` `ClMt` `ClPt` `Clbb` `Clbn` `Clff` `Clmf` `Clmt` `Clpp` `Clpw` `Clst` `Cmmr` `Crlb` `Csts` `Ctco` `Ctoo` `CtrL` `CtrT` `Ctst` `Ctyp` `CwwA` `CwwT` `Cwwa` `Cwwn` `CwyF` `PCJO` `mlCT`
- **u32** (2): `Clfl` `Clpr`
- **bool** (16): `CGCC` `CIRC` `CMCR` `CMHE` `CWCM` `Ccsc` `Chwp` `Cilc` `Cilf` `Circ` `Citc` `Clec` `Cmma` `Crdc` `Cvmr` `ydpc`
- **date** (5): `Ceda` `Clme` `Csda` `Ctld` `Cwpp`
- **rec** (7): `CMCC`{dref} `ClFc`{dref} `Cloa`{dref} `Cnxs`{Pers,plbt,plti,ptpt,ptpv} `CnyF`{Pers,plbt,plti,ptpt,ptpv} `Cpns`{Pers,plbt,plti,ptpt,ptpv} `Ctea`{Ctea,dref,filt}
- **list** (4): `Cbla` `Ccla`{numb,valu} `Ccpb` `Clcb`
- **data** (1): `ClFs`
- **empty** (53): `C1YE` `C1YP` `C1YR` `CABA` `CABF` `CACE` `CACP` `CGBF` `CGBG` `CIIG` `CIIW` `CMDc` `CMDe` `CMFF` `CMFH` `CMFe` `CMHe` `CMac` `CMae` `CMcc` `CMce` `CNPA` `CPCL` `CPGP` `CPIG` `CPIW` `CPWS` `CRRA` `CSOF` `CSPC` `CSPP` `CTDD` `CTDI` `CXBF` `CXBG` `Cabo` `Cdtf` `Cgbo` `Cicb` `Cmfc` `Cmfe` `Cnpr` `Cpwi` `Crrf` `Crwd` `Csbo` `CsqH` `Csqs` `Ctgs` `Ctyb` `Cusb` `Cywi` `WpCw`

</details>

<details><summary><b>injury</b> — 63개</summary>

- **int** (11): `dsha` `dsub` `duni` `icla` `inSr` `indx` `iscl` `noni` `nsss` `obtd`{Pccj,dtty} `rdui`
- **bool** (5): `BaCP` `DELE` `ISTP` `NDDB` `ccno`
- **str** (8): `Duni` `apRS` `dAPw` `dbnm` `hpRS` `ipRS` `lpRS` `tpRS`
- **rec** (11): `apRP`{dfpa,path,shph,srec} `dref`{dref} `hpRP`{dfpa,path,shph,srec} `ipRP`{dfpa,path,shph,srec} `lpRP`{dfpa,path,shph,srec} `ntfl`{filt} `prnt`{dref} `subo`{objL} `subt`{CFcR,CFcY,CHst,CLwR,Chns,Cknw…} `titl`{CFcR,CFcY,Psnu} `tpRP`{dfpa,path,shph,srec}
- **list** (27): `HiSe` `RelO`{dref} `alnm` `chil`{chil,dref,fold,id  } `firt`{dfpa,path,shph,srec} `flag`{dfpa,path,shph,srec} `fspr`{dfpa,path,shph,srec} `hier`{id  ,sibs} `hlog`{dfpa,path,shph,srec} `hsub` `icnp`{dfpa,path,shph,srec} `kit1`{dfpa,path,shph,srec} `kit2`{brep,dfpa,grep,path,rrep,shph…} `kit3`{brep,dfpa,grep,path,rrep,shph…} `ktgb`{dfpa,path,shph,srec} `llgb`{dfpa,path,shph,srec} `logo`{dfpa,path,shph,srec} `mprt`{dfpa,path,shph,srec} `mspr`{dfpa,path,shph,srec} `nots`{dref,id  ,lnks,ncda,nord,norr…} `ntgs` `port`{dfpa,path,shph,srec} `rlgb`{dfpa,path,shph,srec} `sLst` `sibs`{dref} `trop`{dfpa,path,shph,srec} `xsub`
- **data** (1): `sbin`

</details>

