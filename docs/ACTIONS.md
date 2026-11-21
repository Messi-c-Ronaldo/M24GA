# 게임 액션(명령) 목록

> `python -X utf8 tools/actions_catalog.py`가 `core/actions.json`에서 만들어요. 직접 고치지 마세요.

FM24에서 사용자가 하는 명령(관심 목록에 넣기, 이적 제의, 계약 제의, 휴가 …)은 게임 안에서 **액션 객체 198개**예요. M24GA는 그 목록을 등록부로 만들어 뒀어요. **모드가 액션을 실행하는 API는 아직 없어요** (세이브를 바꾸는 명령이라 안전 장치를 먼저 만들어야 해요).

- 액션 id = 4글자 (예: `PGoH` 휴가, `AtSo` 관심 목록에 넣기, `offr` 이적 제의).
- 화면이 열릴 때 게임은 액션마다 '이 대상에 대해' 확인 함수를 불러요. 넘기는 문맥 묶음: `Pers` 대상 사람 {dref}, `Ttea` 팀 {dref}, `Hhum` 명령하는 사람 감독 {dref}, `SidT` 감독의 팀 {dref}, `islc` 지역(이 PC) 감독인가, `objt` 화면의 대상 객체 {dref}.
- `protected` = 확인 함수가 Denuvo 보호 구역이라 정적으로 못 읽은 것. `keys` = 확인 함수가 읽는 키 후보.
- CLI: `cli.py actions [정규식]` (게임 없이 됨).

## 계약 (8)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `Papc` | `ASSIGN_PERSON_CONTRACT_RENEWAL_HANDLING_ACTION` |  | `dreL` `Hhum` `pmcr` `pacr` `pisa` `hidn` |
| `Ptac` | `AUTO_EXTEND_PERSON_CONTRACT_ACTION` |  | `pney` `dreL` `Hhum` `hidn` |
| `Altc` | `LIFETIME_CONTRACT_ACTION` |  | `hidn` `dref` `Hhum` `info` |
| `MTco` | `MUTUAL_CONTRACT_TERMINATION_ACTION` |  | `tfic` `sclp` `hidn` `dreL` `Hhum` |
| `ppad` | `PERSUADE_PLAYER_AGENT_TO_DISREGARD_FAILED_CONTRACT_NEGOTIATIONS_ACTION` | 예 |  |
| `Rfta` | `RELEASE_FROM_CLUB_CONTRACT_ACTION` |  | `ftco` `ftaf` `pfwc` `sclp` `algt` `dpgd` `gcbc` `hidn` `dreL` `pgpw` |
| `Rftn` | `RELEASE_FROM_NATION_CONTRACT_ACTION` |  | `hidn` `dreL` `Hhum` `Ttea` |
| `Wdco` | `WITHDRAW_CONTRACT_OFFER_ACTION` |  | `hidn` `dref` `Hhum` `buyc` |

## 만들기 (3)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `Filt` | `CREATE_FILTER_FROM_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` |
| `SFil` | `CREATE_FILTER_FROM_STAFF_ACTION` |  | `Hhum` `dref` `Tcon` `hidn` |
| `CRNO` | `CREATE_NOTE_ACTION` |  | `hidn` `Hhum` `DRno` `islk` `dref` |

## 목록에 넣기 (15)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `ADDa` | `ADD_AI_MANAGER_ACTION` |  | `hidn` `aimn` `islc` `reas` `maxm` `curm` `disa` |
| `ADDm` | `ADD_MANAGER_ACTION` |  | `hidn` `aimn` `islc` `reas` `maxm` `curm` `disa` |
| `ADma` | `ADD_MULTIPLE_AI_MANAGER_ACTION` |  | `hidn` `aimn` `islc` `reas` `maxm` `curm` `disa` |
| `AnPo` | `ADD_NON_PLAYERS_TO_SHORTLIST_ACTION` |  | `hidn` `Ttea` `alAD` `Hhum` `dreL` `ctxt` `numb` `wsst` |
| `AotT` | `ADD_OWN_PLAYER_PRESS_PRAISE_TO_CURRENT_TOP_TARGET_ACTION` |  | `hidn` `Hhum` `dref` `ToTa` |
| `ApTt` | `ADD_PLAYERS_AS_TRANSFER_TARGETS_ACTION` |  | `hidn` `dreL` |
| `ApD2` | `ADD_PLAYERS_TO_CLUB_DISCARD_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` |
| `ApSH` | `ADD_PLAYERS_TO_CLUB_SQUAD_PLANNER_ACTION` |  | `hidn` `Ttea` `Hhum` `TcIx` `uTiS` `dref` `shcp` `pSqP` `indx` `stID` |
| `ApDl` | `ADD_PLAYERS_TO_DEVELOPMENT_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` |
| `ApD3` | `ADD_PLAYERS_TO_NATIONAL_TEAM_DISCARD_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` |
| `Naps` | `ADD_PLAYERS_TO_NATION_SHORTLIST_ACTION` |  | `hidn` `Hhum` `Nnat` `dreL` |
| `AnSH` | `ADD_PLAYERS_TO_NATION_SQUAD_PLANNER_ACTION` |  | `hidn` `Ttea` `Hhum` `TcIx` `uTiS` `dref` `shcp` `pSqP` `indx` `stID` |
| `AtSo` | `ADD_PLAYERS_TO_SHORTLIST_ACTION` |  | `hidn` `Ttea` `alAD` `Hhum` `dreL` `ctxt` `numb` `wsst` |
| `ApUl` | `ADD_PLAYERS_TO_UNWANTED_LIST_ACTION` |  | `hidn` `SFAp` `SFor` `SHal` `SAny` `SorR` `Ttea` `Hhum` `dreL` |
| `tAdt` | `ADD_PLAYER_TO_FIRST_TEAM_TRAINING_ACTION` |  | `TrPB` `team` `Ttea` `plys` `Pers` `sltd` `Hhum` `dref` `ptyt` `hidn` |

## 목록에서 빼기 (10)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `RNfs` | `REMOVE_NON_PLAYERS_FROM_SHORTLIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` `wpst` `ctxt` |
| `RpD2` | `REMOVE_PLAYERS_FROM_CLUB_DISCARD_LIST_ACTION` |  | `Hhum` `dreL` `hidn` |
| `RpDl` | `REMOVE_PLAYERS_FROM_DEVELOPMENT_LIST_ACTION` |  | `Hhum` `dreL` `hidn` |
| `RmLL` | `REMOVE_PLAYERS_FROM_LOAN_LIST_ACTION` |  | `Ttea` `ctxt` `Hhum` `dreL` `hidn` |
| `RpD3` | `REMOVE_PLAYERS_FROM_NATIONAL_TEAM_DISCARD_LIST_ACTION` |  | `Hhum` `dreL` `hidn` |
| `Nrps` | `REMOVE_PLAYERS_FROM_NATION_SHORTLIST_ACTION` |  | `Hhum` `Nnat` `dreL` `hidn` |
| `RPfs` | `REMOVE_PLAYERS_FROM_SHORTLIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` `wpst` `ctxt` |
| `RmTL` | `REMOVE_PLAYERS_FROM_TRANSFER_LIST_ACTION` |  | `hidn` `Ttea` `ctxt` `Hhum` `dreL` |
| `RpTt` | `REMOVE_PLAYERS_FROM_TRANSFER_TARGETS_ACTION` | 예 |  |
| `RpUl` | `REMOVE_PLAYERS_FROM_UNWANTED_LIST_ACTION` |  | `Hhum` `dreL` `hidn` |

## 바꾸기 (3)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `Chut` | `CHANGE_HUMAN_TEAM_ACTION` | 예 |  |
| `Cpcs` | `CHANGE_PLAYERS_CLUB_SQUAD_ACTION` |  | `hidn` `csss` `Cclu` `Hhum` `dreL` `slis` |
| `chTr` | `CHANGE_PLAYER_TRANSFER_OFFER_ACTION` |  | `hidn` `entr` |

## 비교 (2)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `Comp` | `COMPARE_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` `comp` `hcsp` `hnsp` `pinp` |
| `SCom` | `COMPARE_STAFF_ACTION` |  | `hidn` `Hhum` `dref` `comp` `hcsp` `hnsp` `siap` |

## 설정 (5)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `admn` | `SET_AS_ADMIN_ACTION` |  | `coid` `isad` `cnls` `hidn` |
| `sfDp` | `SET_FOR_DOF_CONTRACT_RENEWAL_PLAYER_ACTION` |  | `DoFr` `Hhum` `dreL` `hidn` |
| `sfrp` | `SET_FOR_RELEASE_PLAYER_ACTION` |  | `Hhum` `dreL` `ctxt` `RMAr` `hidn` |
| `staP` | `SET_PLAYERS_PLAYING_TIME_ACTION` |  | `disa` `valu` `id  ` `UnhP` `UnPs` `hidn` `Ttea` `ctxt` `Pqop` `Hhum` |
| `staA` | `SET_PLAYERS_TRANSFER_STATUS_ACTION` |  | `hidn` `Ttea` `ctxt` `tqop` `toop` `lqop` `Hhum` `dreL` `UnhT` `UnhL` |

## 옮기기 (4)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `moNP` | `MOVE_NON_PLAYERS_TO_CLUB_SHORTLIST_ACTION` |  | `Ttea` `Hhum` `dreL` `ctxt` `wsst` `hidn` |
| `Move` | `MOVE_PLAYERS_TO_AFFILIATES_ACTION` |  | `Hhum` `dreL` `aals` `pnum` `fist` `hidn` |
| `movC` | `MOVE_PLAYERS_TO_CLUB_SHORTLIST_ACTION` |  | `Ttea` `Hhum` `dreL` `ctxt` `wsst` `hidn` |
| `MvCt` | `MOVE_TO_CHILD_TEAM_AFFILIATE_ACTION` |  | `Hhum` `dreL` `aals` `pnum` `fist` `hidn` |

## 요청·문의 (7)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `craa` | `ASK_AGENT_ABOUT_CLIENT_CONTRACT_RENEWAL_ACTION` | 예 |  |
| `caoc` | `ASK_AGENT_TO_OFFER_CLIENT_TO_CLUBS_ACTION` | 예 |  |
| `AsKc` | `ASK_FOR_CONFIRMATION_ACTION` |  | `hidn` `Hhum` `dreL` |
| `hIoC` | `ASK_INTERMEDIARIES_TO_OFFER_PLAYER_TO_CLUBS_ACTION` |  | `hidn` `plyr` `objL` |
| `reti` | `ASK_NOT_TO_RETIRE_ACTION` |  | `hidn` `Hhum` `dref` `topi` |
| `apaa` | `ASK_PLAYER_AGENT_ABOUT_CLIENT_AVAILABILITY_ACTION` | 예 |  |
| `Pari` | `ASK_TO_RECONSIDER_INT_RETIREMENT_ACTION` | 예 |  |

## 이적 (9)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `CTra` | `CLUB_TRANSFERS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CTru` | `COMPETITION_TRANSFER_RUMOURS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `Diip` | `DECLARE_TRANSFER_INTEREST_IN_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` `cdtt` `cdti` `cdli` `cdst` `cdrt` |
| `Cdof` | `DOF_SUGGEST_TRANSFER_TARGETS_ACTION` | 예 |  |
| `Sfre` | `DREAM_TRANSFER_ACTION` |  | `dref` `Hhum` `info` `hidn` |
| `exch` | `EXCHANGE_PLAYER_IN_TRANSFER_ACTION` |  | `hidn` `dref` `Hhum` |
| `pGmT` | `IMMEDIATE_TRANSFER_ACTION` |  | `Pers` `Hhum` `buyt` `selt` `AsPr` `DpVl` `hidn` |
| `Tuft` | `TRIAL_UNTIL_FUTURE_TRANSFER_ACTION` |  | `date` `hidn` `dreL` `Hhum` |
| `with` | `WITHDRAW_PLAYER_TRANSFER_OFFER_ACTION` |  | `hidn` `entr` |

## 임대 (4)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `lf1m` | `LOAN_FOR_ONE_MATCH_ACTION` |  | `hidn` `Pers` `Hhum` `selt` `CLpI` |
| `lpFB` | `LOAN_PLAYER_FEEDBACK_ACTION` | 예 |  |
| `loan` | `RECALL_PLAYER_FROM_LOAN_ACTION` |  | `CtLR` `hidn` `dreL` `Hhum` `recl` |
| `toPl` | `TAKE_OVER_PLAYER_LOAN_ACTION` |  | `tolr` `hidn` `dreL` `Hhum` |

## 정하기·제의 (4)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `offr` | `MAKE_OFFER_TO_PLAYER_ACTION` | 예 |  |
| `Mpar` | `MAKE_PLAYERS_AVAILABLE_FOR_RESERVES_ACTION` |  | `hidn` `Ttea` `Hhum` `isGK` `sIcT` `PlTm` `aRTT` `RTaf` `PlCl` `aPRT` |
| `PmcP` | `MAKE_PLAYER_CAPTAIN_ACTION` |  | `hidn` `Ttea` `Hhum` `TCap` `TVca` `dref` |
| `PmvP` | `MAKE_PLAYER_VICE_CAPTAIN_ACTION` |  | `hidn` `Ttea` `Hhum` `TCap` `TVca` `dref` |

## 제의 (6)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `Poct` | `OFFER_CONTRACT_ACTION` |  | `hidn` `NoAg` `irct` `Ttea` `dref` `RMAr` |
| `poel` | `OFFER_EXTEND_LOAN_ACTION` |  | `Pers` `Hhum` `buyt` `selt` `hidn` |
| `osnk` | `OFFER_STAFF_NATIONAL_JOB_ACTION` |  | `hidn` `Hhum` `dref` `acnp` |
| `Otcl` | `OFFER_TO_CLUBS_ACTION` |  | `Pers` `hidn` `disa` `Potc` `PocR` `plyr` `Ttea` `dreL` `Hhum` `UnhT` |
| `oftr` | `OFFER_TRIAL_ACTION` |  | `Hhum` `dreL` `CmoL` `psst` `psen` `disa` `hidn` |
| `Povc` | `OFFER_VIRTUAL_CONTRACT_ACTION` |  | `dreL` `Hhum` `hidn` |

## 취소 (1)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `CanO` | `CANCEL_PLAYER_TRANSFER_OFFER_ACTION` |  | `hidn` `entr` |

## 훈련 (8)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `CaRe` | `CALL_BACK_FROM_TRAINING_REST_ACTION` | 예 |  |
| `ptfA` | `PLAYER_TRAINING_FOCUS_ACTION` |  | `hidn` `PTra` `ituc` `itCc` `intr` `itre` `sltd` `itrg` `itcf` `itpt` |
| `tIRa` | `PLAYER_TRAINING_INTENSITY_REST_ACTION` |  | `hidn` `PTiR` `PTAC` `PTIC` `PTRd` `pITi` `pTIR` `pITa` `TFxL` `ppLs` |
| `pnew` | `PLAYER_TRAINING_NEW_POSITION_ACTION` |  | `hidn` `PTif` `posn` `vlps` `PPrd` `itrm` `indx` `sltd` |
| `nPMo` | `PLAYER_TRAINING_PREFERRED_MOVE_ACTION` |  | `hidn` `sltd` `asTC` `itre` `PmLi` `indx` |
| `PLtr` | `REQUEST_TRAINING_REPORT_ACTION` |  | `hidn` `disa` `dref` `dreL` `lisC` |
| `Rest` | `REST_PLAYERS_FROM_TRAINING_ACTION` |  | `hidn` |
| `Tsca` | `TRAINING_SCHEDULE_ACTION` | 예 |  |

## 기타 (109)

| id | 클래스 | 보호 | 문맥 키 |
|---|---|---|---|
| `awol` | `ALLOW_PLAYER_AN_ABSENCE_OF_LEAVE_ACTION` | 예 |  |
| `apwp` | `APPLY_FOR_WORK_PERMIT_ACTION` |  | `hidn` |
| `Rams` | `APPLY_MAGIC_SPONGE_ACTION` |  | `dref` `Hhum` `info` `hidn` |
| `Papt` | `APPROACH_TO_SIGN_ACTION` | 예 |  |
| `bane` | `BAN_USER_ACTION` |  | `coid` `dref` `hidn` |
| `BscA` | `BUY_DOWN_MLS_PLAYER_SALARY_CAP_IMPACT_ACTION` |  | `hidn` `Ttea` `dref` |
| `Call` | `CALL_UP_TO_NATIONAL_SQUAD_ACTION` |  | `Hhum` `dreL` `acnp` `hidn` |
| `Pcpl` | `CHAT_TO_PLAYER_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `chat` | `CHAT_TO_USER_ACTION` |  | `hidn` `coid` `dref` `Hhum` |
| `ofml` | `CLAIM_PLAYERS_FROM_WAIVER_LIST_ACTION` |  | `dreL` `Hhum` `Ttea` `hidn` |
| `Cxdp` | `CLUB_ADD_EXTRA_DP_SLOT_ACTION` |  | `hidn` `Ttea` `Hhum` |
| `CAfC` | `CLUB_AFFILIATED_CLUB_LINK_ACTION` |  | `hidn` `team` `Ttea` |
| `CAsS` | `CLUB_ASSIGN_SCOUT_ACTION` |  | `hidn` `Cclu` `lisS` |
| `Cboa` | `CLUB_BOARD_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CBud` | `CLUB_BUDGET_ADJUSTMENT_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CFin` | `CLUB_FINANCE_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CMTE` | `CLUB_MLS_ENQUIRY_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CMTr` | `CLUB_MLS_TRADE_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CPFv` | `CLUB_PICK_AS_FAVOURITE_ACTION` |  | `hidn` `Hhum` `Ttea` `fave` `remf` |
| `CAff` | `CLUB_REQUEST_AFFILIATE_LINK_ACTION` | 예 |  |
| `CSlF` | `CLUB_SELECT_FEEDER_ACTION` |  | `hidn` `Ttea` `Hhum` |
| `ccra` | `COACHING_COURSE_ACTION` |  | `hidn` `Hhum` `dref` `Cclu` `Pcqu` |
| `cnai` | `COMMIT_TO_NATION_ACTION` |  | `hidn` `Hhum` `Nnat` `type` `dreL` `acne` `mode` |
| `CAdd` | `COMPETITION_ADD_AS_PLAYABLE_LEAGUE_ACTION` | 예 |  |
| `CAwa` | `COMPETITION_AWARDS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `Fixt` | `COMPETITION_FIXTURES_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CPst` | `COMPETITION_PLAYER_STATS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `CSco` | `COMPETITION_SCOUT_REPORT_ACTION` |  | `hidn` `CSct` `objt` `SctA` `comp` `ctxt` |
| `CTst` | `COMPETITION_TEAM_STATS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `disp` | `DISCIPLINE_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` `fint` `Ttea` |
| `ebpl` | `ENQUIRE_ACTION` |  | `buyt` `selt` `Hhum` `dreL` `disa` `hidn` `cotx` |
| `FAna` | `FIXTURE_ANALYSIS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `FMst` | `FIXTURE_MATCH_STATS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `FPlr` | `FIXTURE_PLAYER_RATINGS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `forc` | `FORCE_CONTINUE_USER_ACTION` |  | `coid` `dref` `lisC` `hidn` |
| `forh` | `FORCE_HOLIDAY_USER_ACTION` | 예 |  |
| `Repo` | `GET_PLAYERS_MATCH_REPORT` |  | `Ttea` `Hhum` `dreL` `lisC` `lisS` `ctxt` `hidn` |
| `PGoH` | `GO_ON_HOLIDAY_ACTION` | 예 |  |
| `Hres` | `HUMAN_RESIGN_ACTION` |  | `hidn` `team` |
| `OMLS` | `INTERNAL_OFFER_TO_MLS_CLUBS_ACTION` |  | `hidn` `dreL` `Hhum` `Cclu` |
| `krpd` | `KEEP_RETIRED_PERSON_DATA_ACTION` |  | `dref` `Hhum` `tick` `csta` `hidn` |
| `kick` | `KICK_USER_ACTION` |  | `coid` `dref` `hidn` |
| `lcra` | `LEADERSHIP_COURSE_ACTION` |  | `hidn` `Hhum` `dref` `Cclu` |
| `pTrM` | `MLS_ROSTER_CHAT_CONVERSATION_ACTION` | 예 |  |
| `NAsS` | `NATION_ASSIGN_SCOUT_ACTION` |  | `hidn` `knlv` `scrs` `disa` `Pers` `Nnat` `TCsL` |
| `CNws` | `NEWS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `nick` | `NICKNAME_ACTION` |  | `niha` `dreL` `Hhum` `Ttea` `hidn` |
| `ObLn` | `OBJECT_LINK_ACTION` |  | `hidn` `islk` `Ttea` `NovP` `tciG` `Tcon` `sect` `smpc` `Pfke` `fcgn` |
| `Pcrl` | `PERSON_COACH_REPORTS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `Pnrl` | `PERSON_NATIONAL_REPORTS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `Psal` | `PERSON_SCOUT_ASSIGNMENTS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `Psrl` | `PERSON_SCOUT_REPORTS_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `draf` | `PICK_PLAYER_FROM_DRAFT_ACTION` |  | `hidn` `Ttea` `isFD` `Hhum` `dref` `comp` `dpsc` `dpsa` `pdpl` `Pdva` |
| `mlil` | `PLACE_MLS_PLAYER_ON_INJURY_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` `pdll` |
| `pach` | `PLAYER_ADVICE_ACTION` | 예 |  |
| `pamb` | `PLAYER_AMBASSADORIAL_ACTION` | 예 |  |
| `pcai` | `PLAYER_CONCERNED_ACTION` | 예 |  |
| `ppai` | `PRAISE_PLAYER_ACTION` | 예 |  |
| `chan` | `PRIVATE_NATIONAL_CONVERSATION_ACTION` | 예 |  |
| `pCtp` | `PROMOTE_CLUB_TO_ANOTHER_PLAYER_BY_TALKING_WITH_THE_PRESS_ACTION` | 예 |  |
| `rols` | `RECALL_PLAYER_FROM_HOLIDAY_ACTION` | 예 |  |
| `PRLQ` | `RELINQUISH_CONTROL_ACTION` | 예 |  |
| `PrIR` | `REQUEST_INJURY_RISK_UPDATE_ACTION` |  | `hidn` `dref` `Hhum` `team` |
| `PRpr` | `REQUEST_PHYSIO_REPORT_ACTION` |  | `hidn` `dref` `Hhum` `team` |
| `rpaa` | `RESPOND_TO_PLAYER_AGENT_ABOUT_CLIENT_AVAILABILITY_ACTION` | 예 |  |
| `rpla` | `REST_PLAYER_CONVERSATION_ACTION` | 예 |  |
| `Pret` | `RETIRE_ACTION` | 예 |  |
| `CScc` | `SCOUT_PLAYERS_CLUB_ACTION` |  | `hidn` `TtPl` `Ttea` `Cclu` `Hhum` `dreL` `lisC` `lisS` `piFA` `ctxt` |
| `NSco` | `SCOUT_PLAYERS_NATIONAL_ACTION` |  | `Ttea` `Hhum` `dreL` `lisC` `lisS` `piFA` `ctxt` `hidn` |
| `Pgra` | `SCOUT_PLAYER_GET_REPORT_ACTION` |  | `hidn` `lisS` `lisA` `dreL` |
| `STAi` | `SCOUT_TEAM_ACTION` |  | `hidn` `Ttea` `Alre` `SdtS` `Sgtm` `Scls` |
| `mooh` | `SEND_MESSAGE_TO_OTHER_HUMAN_ACTION` | 예 |  |
| `silc` | `SEND_ON_INTENSIVE_LANGUAGE_COURSE_ACTION` |  | `hidn` `ilcl` |
| `hols` | `SEND_PLAYER_ON_HOLIDAY_ACTION` |  | `Ttea` `objL` `hidn` |
| `Tpfa` | `SERVE_DODGY_LASAGNE_ACTION` |  | `dref` `Hhum` `info` `hidn` |
| `rSTO` | `STOP_SCOUT_PLAYERS_CLUB_ACTION` |  | `Hhum` `dreL` `hidn` |
| `SUBS` | `SUBSCRIBE_ACTION` |  | `Hhum` `hidn` `dreL` |
| `PSns` | `SUGGEST_NATIONAL_SQUAD_ACTION` |  | `hidn` `dref` `Hhum` `team` |
| `pTij` | `TALK_TO_INJURED_PLAYER_ACTION` | 예 |  |
| `Ptom` | `TALK_TO_OTHER_CLUB_MANAGER_ACTION` | 예 |  |
| `Tuta` | `TALK_TO_UNHAPPY_TEAMMATE_ACTION` | 예 |  |
| `TApJ` | `TEAM_APPLY_FOR_JOB_ACTION` | 예 |  |
| `TCpJ` | `TEAM_CONTAINER_APPLY_FOR_JOB_ACTION` |  | `hidn` `Hhum` `team` |
| `TCdI` | `TEAM_CONTAINER_DECLARE_INTEREST_ACTION` |  | `hidn` `Hhum` `team` |
| `TCEx` | `TEAM_CONTAINER_EXPORT_ACTION` | 예 |  |
| `TCIn` | `TEAM_CONTAINER_INFORMATION_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `TCFF` | `TEAM_CONTAINER_PICK_FOR_FRIENDLY_ACTION` |  | `hidn` `Hhum` `team` |
| `TCFr` | `TEAM_CONTAINER_PROPOSE_FRIENDLY_ACTION` |  | `hidn` `Hhum` `Ttea` `team` |
| `TCRE` | `TEAM_CONTAINER_RESPONSIBILITIES_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `TCSq` | `TEAM_CONTAINER_SQUAD_LINK_ACTION` |  | `hidn` `Ttea` `TeSq` `dref` `sect` `lnks` `Tcon` |
| `TCSt` | `TEAM_CONTAINER_STAFF_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `TCkC` | `TEAM_CONTAINER_TAKE_CONTROL_ACTION` |  | `hidn` `Hhum` `team` |
| `TDeI` | `TEAM_DECLARE_INTEREST_ACTION` |  | `hidn` `Ttea` `Hhum` `ottm` |
| `TExa` | `TEAM_EXPORT_ACTION` | 예 |  |
| `TFix` | `TEAM_FIXTURES_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `Tpco` | `TEAM_PARENT_COMPETITION_LINK_ACTION` |  | `hidn` `lnks` |
| `Tptc` | `TEAM_PARENT_TEAM_CONTAINER_LINK_ACTION` |  | `hidn` `lnks` `Tcon` |
| `TPFv` | `TEAM_PICK_AS_FAVOURITE_ACTION` |  | `hidn` `Hhum` `Ttea` `fave` `remf` |
| `TPFF` | `TEAM_PICK_FOR_FRIENDLY_ACTION` |  | `hidn` `Ttea` `Hhum` |
| `TpFr` | `TEAM_PROPOSE_FRIENDLY_ACTION` |  | `hidn` `NcNF` `Ttea` `Hhum` `fopt` `NcCF` |
| `Tres` | `TEAM_RESIGN_ACTION` | 예 |  |
| `Trgu` | `TEAM_RESOLVE_GROUP_UNHAPPINESS_ACTION` | 예 |  |
| `TSlF` | `TEAM_SELECT_FEEDER_ACTION` |  | `hidn` `Ttea` `Hhum` |
| `TTkC` | `TEAM_TAKE_CONTROL_ACTION` |  | `hidn` `Ttea` `Hhum` |
| `TMee` | `TEAM_TEAM_MEETING_LINK_ACTION` |  | `hidn` `dref` `sect` |
| `TTTk` | `TEAM_TEAM_TALK_FEEDBACK_ACTION` | 예 |  |
| `triC` | `TERMINATE_TRIAL_ACTION` |  | `ttrs` `hidn` `Hhum` `dreL` |
| `USUB` | `UNSUBSCRIBE_ACTION` |  | `hidn` `Hhum` `dreL` |
| `wpai` | `WARN_PLAYER_ACTION` | 예 |  |

