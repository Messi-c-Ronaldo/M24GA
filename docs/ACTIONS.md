# 게임 액션(명령) 목록

> `python -X utf8 tools/actions_catalog.py`가 `core/actions.json`에서 만들어요. 직접 고치지 마세요.

FM24에서 사용자가 하는 명령(관심 목록에 넣기, 이적 제의, 계약 제의, 휴가 …)은 게임 안에서 **액션 객체 198개**예요. M24GA는 그 목록을 등록부로 만들어 뒀어요. 모드는 (코어 0.41.0) `api.actionsFor(대상)`으로 게임 메뉴가 그 대상에 보여 주는 명령을 읽고 (기능 `read.action`), `api.action(id, 대상, {event})`로 실행해요 (기능 `game.action`, 세이브를 바꿔서 사용자 허용·기록).

- 액션 id = 4글자 (예: `PGoH` 휴가, `AtSo` 관심 목록에 넣기, `offr` 이적 제의).
- 화면이 열릴 때 게임은 액션마다 '이 대상에 대해' 확인 함수를 불러요. 넘기는 문맥 묶음: `Pers` 대상 사람 {dref}, `Ttea` 팀 {dref}, `Hhum` 명령하는 사람 감독 {dref}, `SidT` 감독의 팀 {dref}, `islc` 지역(이 PC) 감독인가, `objt` 화면의 대상 객체 {dref}.
- `protected` = 확인 함수가 Denuvo 보호 구역이라 정적으로 못 읽은 것. `keys` = 확인 함수가 읽는 키 후보.
- `실행 이벤트` = 실행 쪽 처리기(*_ACTION_UI)가 받는 이벤트. **굵게** = 메뉴를 누를 때 보내는 이벤트(`click`, 확인 창·화면을 여는 단계가 많아요), ✔ = 확인 뒤 이벤트(`confirm`, 확인 창 없이 실행). 하나면 `api.action`에서 생략, 여럿이면 `{event}`로 골라요. `실행 불가` = 처리기가 비어 있어 이 길로 실행할 수 없는 명령 (화면 이동 LINK, 사임 등), '-' = 실행 객체 없음.
- 실기 확인 (M65): `SUBS` 구독 / `USUB` 구독 취소 = 바로 반영. 리더십 훈련 코스(`Ablc`)는 화면 메뉴로 확인. 주장 지정 `PmcP`는 누름 `pmcE`(확인 창, 모드에서 부르면 창이 안 뜸)가 아니라 확인 뒤 `pmcC`를 주면 실행되고 다음 날 처리 때 반영 (주장 바뀜 → 되돌림 확인). 다른 `confirm`은 같은 꼴(이벤트 2개 중 누름이 아닌 쪽)이라 적은 것이고 실기는 아직이에요.
- CLI: `cli.py actions [정규식]` (게임 없이 됨).

## 계약 (8)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `Papc` | `ASSIGN_PERSON_CONTRACT_RENEWAL_HANDLING_ACTION` |  | `dreL` `Hhum` `pmcr` `pacr` `pisa` `hidn` | `ptec` |
| `Ptac` | `AUTO_EXTEND_PERSON_CONTRACT_ACTION` |  | `pney` `dreL` `Hhum` `hidn` | `offd` `EPSB` `offE` `offM` `offe` **`psec`** `ptec` |
| `Altc` | `LIFETIME_CONTRACT_ACTION` |  | `hidn` `dref` `Hhum` `info` | `Palc` **`Prlc`** **`STOR`** |
| `MTco` | `MUTUAL_CONTRACT_TERMINATION_ACTION` |  | `tfic` `sclp` `hidn` `dreL` `Hhum` | `offL` `EPSB` `ecct` `offE` `offM` `offe` **`prct`** |
| `ppad` | `PERSUADE_PLAYER_AGENT_TO_DISREGARD_FAILED_CONTRACT_NEGOTIATIONS_ACTION` | 예 |  | `pinc` |
| `Rfta` | `RELEASE_FROM_CLUB_CONTRACT_ACTION` |  | `ftco` `ftaf` `pfwc` `sclp` `algt` `dpgd` `gcbc` `hidn` `dreL` `pgpw` | `offD` `EPSB` `frec` **`free`** `offE` `offM` `offe` |
| `Rftn` | `RELEASE_FROM_NATION_CONTRACT_ACTION` |  | `hidn` `dreL` `Hhum` `Ttea` | `offD` `EPSB` `frec` **`free`** `offE` `offM` `offe` |
| `Wdco` | `WITHDRAW_CONTRACT_OFFER_ACTION` |  | `hidn` `dref` `Hhum` `buyc` | `PWNN` `offL` `PWNO` `offE` `EPSB` `Mhwi` **`PWNC`** `offM` `offe` |

## 만들기 (3)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `Filt` | `CREATE_FILTER_FROM_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` | **`pcsf`** |
| `SFil` | `CREATE_FILTER_FROM_STAFF_ACTION` |  | `Hhum` `dref` `Tcon` `hidn` | **`pssf`** |
| `CRNO` | `CREATE_NOTE_ACTION` |  | `hidn` `Hhum` `DRno` `islk` `dref` | `CRNO` |

## 목록에 넣기 (15)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `ADDa` | `ADD_AI_MANAGER_ACTION` |  | `hidn` `aimn` `islc` `reas` `maxm` `curm` `disa` | `AddM` |
| `ADDm` | `ADD_MANAGER_ACTION` |  | `hidn` `aimn` `islc` `reas` `maxm` `curm` `disa` | `AddM` |
| `ADma` | `ADD_MULTIPLE_AI_MANAGER_ACTION` |  | `hidn` `aimn` `islc` `reas` `maxm` `curm` `disa` | **`AddM`** |
| `AnPo` | `ADD_NON_PLAYERS_TO_SHORTLIST_ACTION` |  | `hidn` `Ttea` `alAD` `Hhum` `dreL` `ctxt` `numb` `wsst` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `AotT` | `ADD_OWN_PLAYER_PRESS_PRAISE_TO_CURRENT_TOP_TARGET_ACTION` |  | `hidn` `Hhum` `dref` `ToTa` | `mpPt` ✔ **`MppT`** |
| `ApTt` | `ADD_PLAYERS_AS_TRANSFER_TARGETS_ACTION` |  | `hidn` `dreL` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `ApD2` | `ADD_PLAYERS_TO_CLUB_DISCARD_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` **`pCdl`** |
| `ApSH` | `ADD_PLAYERS_TO_CLUB_SQUAD_PLANNER_ACTION` |  | `hidn` `Ttea` `Hhum` `TcIx` `uTiS` `dref` `shcp` `pSqP` `indx` `stID` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` **`reSQ`** |
| `ApDl` | `ADD_PLAYERS_TO_DEVELOPMENT_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `ApD3` | `ADD_PLAYERS_TO_NATIONAL_TEAM_DISCARD_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` | `pDVk` `pspd` `pUNv` `pDVl` **`pNdl`** `dscn` `pATS` `dsco` |
| `Naps` | `ADD_PLAYERS_TO_NATION_SHORTLIST_ACTION` |  | `hidn` `Hhum` `Nnat` `dreL` | **`ncua`** `erro` ✔ |
| `AnSH` | `ADD_PLAYERS_TO_NATION_SQUAD_PLANNER_ACTION` |  | `hidn` `Ttea` `Hhum` `TcIx` `uTiS` `dref` `shcp` `pSqP` `indx` `stID` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` **`reSQ`** |
| `AtSo` | `ADD_PLAYERS_TO_SHORTLIST_ACTION` |  | `hidn` `Ttea` `alAD` `Hhum` `dreL` `ctxt` `numb` `wsst` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `ApUl` | `ADD_PLAYERS_TO_UNWANTED_LIST_ACTION` |  | `hidn` `SFAp` `SFor` `SHal` `SAny` `SorR` `Ttea` `Hhum` `dreL` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `tAdt` | `ADD_PLAYER_TO_FIRST_TEAM_TRAINING_ACTION` |  | `TrPB` `team` `Ttea` `plys` `Pers` `sltd` `Hhum` `dref` `ptyt` `hidn` | `ssTU` `adTg` |

## 목록에서 빼기 (10)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `RNfs` | `REMOVE_NON_PLAYERS_FROM_SHORTLIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` `wpst` `ctxt` | `remc` `remo` |
| `RpD2` | `REMOVE_PLAYERS_FROM_CLUB_DISCARD_LIST_ACTION` |  | `Hhum` `dreL` `hidn` | `rmCC` `rmCd` |
| `RpDl` | `REMOVE_PLAYERS_FROM_DEVELOPMENT_LIST_ACTION` |  | `Hhum` `dreL` `hidn` | `rmDC` `rmDL` |
| `RmLL` | `REMOVE_PLAYERS_FROM_LOAN_LIST_ACTION` |  | `Ttea` `ctxt` `Hhum` `dreL` `hidn` | `crLL` ✔ **`reLL`** |
| `RpD3` | `REMOVE_PLAYERS_FROM_NATIONAL_TEAM_DISCARD_LIST_ACTION` |  | `Hhum` `dreL` `hidn` | `rmNC` `rmNd` |
| `Nrps` | `REMOVE_PLAYERS_FROM_NATION_SHORTLIST_ACTION` |  | `Hhum` `Nnat` `dreL` `hidn` | `erro` `ncua` **`remo`** |
| `RPfs` | `REMOVE_PLAYERS_FROM_SHORTLIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` `wpst` `ctxt` | `remc` `remo` |
| `RmTL` | `REMOVE_PLAYERS_FROM_TRANSFER_LIST_ACTION` |  | `hidn` `Ttea` `ctxt` `Hhum` `dreL` | `crTL` ✔ **`reTL`** |
| `RpTt` | `REMOVE_PLAYERS_FROM_TRANSFER_TARGETS_ACTION` | 예 |  | `rmTC` `rmTT` |
| `RpUl` | `REMOVE_PLAYERS_FROM_UNWANTED_LIST_ACTION` |  | `Hhum` `dreL` `hidn` | `rmUC` `rmUL` |

## 바꾸기 (3)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `Chut` | `CHANGE_HUMAN_TEAM_ACTION` | 예 |  | **`AssT`** |
| `Cpcs` | `CHANGE_PLAYERS_CLUB_SQUAD_ACTION` |  | `hidn` `csss` `Cclu` `Hhum` `dreL` `slis` | **`move`** |
| `chTr` | `CHANGE_PLAYER_TRANSFER_OFFER_ACTION` |  | `hidn` `entr` | `offL` `EPSB` `offE` `offM` **`offe`** |

## 비교 (2)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `Comp` | `COMPARE_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` `comp` `hcsp` `hnsp` `pinp` | `ecop` |
| `SCom` | `COMPARE_STAFF_ACTION` |  | `hidn` `Hhum` `dref` `comp` `hcsp` `hnsp` `siap` | `ecos` |

## 설정 (5)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `admn` | `SET_AS_ADMIN_ACTION` |  | `coid` `isad` `cnls` `hidn` | **`sadm`** |
| `sfDp` | `SET_FOR_DOF_CONTRACT_RENEWAL_PLAYER_ACTION` |  | `DoFr` `Hhum` `dreL` `hidn` | `DFrd` ✔ **`DoFr`** |
| `sfrp` | `SET_FOR_RELEASE_PLAYER_ACTION` |  | `Hhum` `dreL` `ctxt` `RMAr` `hidn` | `sfrc` ✔ **`sfre`** |
| `staP` | `SET_PLAYERS_PLAYING_TIME_ACTION` |  | `disa` `valu` `id  ` `UnhP` `UnPs` `hidn` `Ttea` `ctxt` `Pqop` `Hhum` | `plaC` `play` |
| `staA` | `SET_PLAYERS_TRANSFER_STATUS_ACTION` |  | `hidn` `Ttea` `ctxt` `tqop` `toop` `lqop` `Hhum` `dreL` `UnhT` `UnhL` |  |

## 옮기기 (4)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `moNP` | `MOVE_NON_PLAYERS_TO_CLUB_SHORTLIST_ACTION` |  | `Ttea` `Hhum` `dreL` `ctxt` `wsst` `hidn` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `Move` | `MOVE_PLAYERS_TO_AFFILIATES_ACTION` |  | `Hhum` `dreL` `aals` `pnum` `fist` `hidn` | `sent` ✔ **`send`** |
| `movC` | `MOVE_PLAYERS_TO_CLUB_SHORTLIST_ACTION` |  | `Ttea` `Hhum` `dreL` `ctxt` `wsst` `hidn` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `MvCt` | `MOVE_TO_CHILD_TEAM_AFFILIATE_ACTION` |  | `Hhum` `dreL` `aals` `pnum` `fist` `hidn` | `sent` `send` |

## 요청·문의 (7)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `craa` | `ASK_AGENT_ABOUT_CLIENT_CONTRACT_RENEWAL_ACTION` | 예 |  | `pinc` |
| `caoc` | `ASK_AGENT_TO_OFFER_CLIENT_TO_CLUBS_ACTION` | 예 |  | `pinc` |
| `AsKc` | `ASK_FOR_CONFIRMATION_ACTION` |  | `hidn` `Hhum` `dreL` | `pAKc` ✔ **`pasc`** |
| `hIoC` | `ASK_INTERMEDIARIES_TO_OFFER_PLAYER_TO_CLUBS_ACTION` |  | `hidn` `plyr` `objL` | `ChIn` ✔ **`AthI`** |
| `reti` | `ASK_NOT_TO_RETIRE_ACTION` |  | `hidn` `Hhum` `dref` `topi` | `nrc?` `nret` `ret?` |
| `apaa` | `ASK_PLAYER_AGENT_ABOUT_CLIENT_AVAILABILITY_ACTION` | 예 |  | `pinc` |
| `Pari` | `ASK_TO_RECONSIDER_INT_RETIREMENT_ACTION` | 예 |  | `crir` `arir` |

## 이적 (9)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `CTra` | `CLUB_TRANSFERS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CTru` | `COMPETITION_TRANSFER_RUMOURS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `Diip` | `DECLARE_TRANSFER_INTEREST_IN_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` `cdtt` `cdti` `cdli` `cdst` `cdrt` | `dcls` `cdci` **`dcll`** **`dctt`** **`dclt`** |
| `Cdof` | `DOF_SUGGEST_TRANSFER_TARGETS_ACTION` | 예 |  | `supl` |
| `Sfre` | `DREAM_TRANSFER_ACTION` |  | `dref` `Hhum` `info` `hidn` | `Aspf` **`Sfre`** **`STOR`** |
| `exch` | `EXCHANGE_PLAYER_IN_TRANSFER_ACTION` |  | `hidn` `dref` `Hhum` | `offD` `offE` `offM` `offe` `EPSB` **`exhc`** |
| `pGmT` | `IMMEDIATE_TRANSFER_ACTION` |  | `Pers` `Hhum` `buyt` `selt` `AsPr` `DpVl` `hidn` | `IMtp` `IMpc` |
| `Tuft` | `TRIAL_UNTIL_FUTURE_TRANSFER_ACTION` |  | `date` `hidn` `dreL` `Hhum` | `pttf` ✔ **`ptft`** |
| `with` | `WITHDRAW_PLAYER_TRANSFER_OFFER_ACTION` |  | `hidn` `entr` | `offL` `EPSB` `WIDR` `offE` `offM` `offe` **`offw`** |

## 임대 (4)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `lf1m` | `LOAN_FOR_ONE_MATCH_ACTION` |  | `hidn` `Pers` `Hhum` `selt` `CLpI` | `1mlo` `1mlc` |
| `lpFB` | `LOAN_PLAYER_FEEDBACK_ACTION` | 예 |  | `pinc` |
| `loan` | `RECALL_PLAYER_FROM_LOAN_ACTION` |  | `CtLR` `hidn` `dreL` `Hhum` `recl` | `tlcc` ✔ **`tlco`** |
| `toPl` | `TAKE_OVER_PLAYER_LOAN_ACTION` |  | `tolr` `hidn` `dreL` `Hhum` | `plTo` ✔ **`plto`** |

## 정하기·제의 (4)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `offr` | `MAKE_OFFER_TO_PLAYER_ACTION` | 예 |  | `offL` `EPSB` `offE` `offM` `offe` |
| `Mpar` | `MAKE_PLAYERS_AVAILABLE_FOR_RESERVES_ACTION` |  | `hidn` `Ttea` `Hhum` `isGK` `sIcT` `PlTm` `aRTT` `RTaf` `PlCl` `aPRT` | `pmar` |
| `PmcP` | `MAKE_PLAYER_CAPTAIN_ACTION` |  | `hidn` `Ttea` `Hhum` `TCap` `TVca` `dref` | `pmcC` ✔ **`pmcE`** |
| `PmvP` | `MAKE_PLAYER_VICE_CAPTAIN_ACTION` |  | `hidn` `Ttea` `Hhum` `TCap` `TVca` `dref` | `pmcC` ✔ **`pmcE`** |

## 제의 (6)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `Poct` | `OFFER_CONTRACT_ACTION` |  | `hidn` `NoAg` `irct` `Ttea` `dref` `RMAr` | `offd` `EPSB` `offE` `offM` `offe` `pocd` **`poco`** |
| `poel` | `OFFER_EXTEND_LOAN_ACTION` |  | `Pers` `Hhum` `buyt` `selt` `hidn` | `OElo` `OElc` |
| `osnk` | `OFFER_STAFF_NATIONAL_JOB_ACTION` |  | `hidn` `Hhum` `dref` `acnp` | `erro` `ncua` **`offp`** |
| `Otcl` | `OFFER_TO_CLUBS_ACTION` |  | `Pers` `hidn` `disa` `Potc` `PocR` `plyr` `Ttea` `dreL` `Hhum` `UnhT` | `Otfk` `OtcL` `EPSB` `Mult` `offL` **`Otfl`** `offE` **`OtcM`** **`Otcl`** `offM` `offe` |
| `oftr` | `OFFER_TRIAL_ACTION` |  | `Hhum` `dreL` `CmoL` `psst` `psen` `disa` `hidn` | `offD` `EPSB` `Otpc` `Ottp` |
| `Povc` | `OFFER_VIRTUAL_CONTRACT_ACTION` |  | `dreL` `Hhum` `hidn` | `offL` `EPSB` `OVPO` `offE` `offM` `offe` **`ovpc`** |

## 취소 (1)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `CanO` | `CANCEL_PLAYER_TRANSFER_OFFER_ACTION` |  | `hidn` `entr` | `CANC` `EPSB` |

## 훈련 (8)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `CaRe` | `CALL_BACK_FROM_TRAINING_REST_ACTION` | 예 |  | **`ects`** |
| `ptfA` | `PLAYER_TRAINING_FOCUS_ACTION` |  | `hidn` `PTra` `ituc` `itCc` `intr` `itre` `sltd` `itrg` `itcf` `itpt` | **`wfSL`** **`fSEL`** |
| `tIRa` | `PLAYER_TRAINING_INTENSITY_REST_ACTION` |  | `hidn` `PTiR` `PTAC` `PTIC` `PTRd` `pITi` `pTIR` `pITa` `TFxL` `ppLs` | `errc` `eshc` `etir` |
| `pnew` | `PLAYER_TRAINING_NEW_POSITION_ACTION` |  | `hidn` `PTif` `posn` `vlps` `PPrd` `itrm` `indx` `sltd` | **`pSEL`** |
| `nPMo` | `PLAYER_TRAINING_PREFERRED_MOVE_ACTION` |  | `hidn` `sltd` `asTC` `itre` `PmLi` `indx` | `aPTr` `stTw` **`shPD`** |
| `PLtr` | `REQUEST_TRAINING_REPORT_ACTION` |  | `hidn` `disa` `dref` `dreL` `lisC` | **`ptra`** |
| `Rest` | `REST_PLAYERS_FROM_TRAINING_ACTION` |  | `hidn` | `ects` |
| `Tsca` | `TRAINING_SCHEDULE_ACTION` | 예 |  | **`ects`** |

## 기타 (109)

| id | 클래스 | 보호 | 문맥 키 | 실행 이벤트 |
|---|---|---|---|---|
| `awol` | `ALLOW_PLAYER_AN_ABSENCE_OF_LEAVE_ACTION` | 예 |  | `ephd` ✔ **`epho`** |
| `apwp` | `APPLY_FOR_WORK_PERMIT_ACTION` |  | `hidn` | `appd` ✔ **`app?`** |
| `Rams` | `APPLY_MAGIC_SPONGE_ACTION` |  | `dref` `Hhum` `info` `hidn` | `Amgs` **`Rams`** **`STOR`** |
| `Papt` | `APPROACH_TO_SIGN_ACTION` | 예 |  | `offD` `EPSB` `apsc` **`apsi`** `offE` `offM` `offe` |
| `bane` | `BAN_USER_ACTION` |  | `coid` `dref` `hidn` | `Kcon` ✔ **`kick`** |
| `BscA` | `BUY_DOWN_MLS_PLAYER_SALARY_CAP_IMPACT_ACTION` |  | `hidn` `Ttea` `dref` | **`Bmls`** |
| `Call` | `CALL_UP_TO_NATIONAL_SQUAD_ACTION` |  | `Hhum` `dreL` `acnp` `hidn` | `erro` `ncua` **`pcup`** |
| `Pcpl` | `CHAT_TO_PLAYER_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `chat` | `CHAT_TO_USER_ACTION` |  | `hidn` `coid` `dref` `Hhum` | **`chat`** |
| `ofml` | `CLAIM_PLAYERS_FROM_WAIVER_LIST_ACTION` |  | `dreL` `Hhum` `Ttea` `hidn` | `offD` `EPSB` **`ecwa`** `ecwc` `offE` `offM` `offe` |
| `Cxdp` | `CLUB_ADD_EXTRA_DP_SLOT_ACTION` |  | `hidn` `Ttea` `Hhum` | `edpc` `exdp` |
| `CAfC` | `CLUB_AFFILIATED_CLUB_LINK_ACTION` |  | `hidn` `team` `Ttea` | 실행 불가 |
| `CAsS` | `CLUB_ASSIGN_SCOUT_ACTION` |  | `hidn` `Cclu` `lisS` | 실행 불가 |
| `Cboa` | `CLUB_BOARD_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CBud` | `CLUB_BUDGET_ADJUSTMENT_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CFin` | `CLUB_FINANCE_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CMTE` | `CLUB_MLS_ENQUIRY_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CMTr` | `CLUB_MLS_TRADE_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CPFv` | `CLUB_PICK_AS_FAVOURITE_ACTION` |  | `hidn` `Hhum` `Ttea` `fave` `remf` | **`pkfv`** |
| `CAff` | `CLUB_REQUEST_AFFILIATE_LINK_ACTION` | 예 |  | `pinc` |
| `CSlF` | `CLUB_SELECT_FEEDER_ACTION` |  | `hidn` `Ttea` `Hhum` | **`pifc`** |
| `ccra` | `COACHING_COURSE_ACTION` |  | `hidn` `Hhum` `dref` `Cclu` `Pcqu` | **`Abtc`** `Chcc` **`Htcc`** |
| `cnai` | `COMMIT_TO_NATION_ACTION` |  | `hidn` `Hhum` `Nnat` `type` `dreL` `acne` `mode` | `ncua` `erro` **`cmtn`** |
| `CAdd` | `COMPETITION_ADD_AS_PLAYABLE_LEAGUE_ACTION` | 예 |  | 실행 불가 |
| `CAwa` | `COMPETITION_AWARDS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `Fixt` | `COMPETITION_FIXTURES_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CPst` | `COMPETITION_PLAYER_STATS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `CSco` | `COMPETITION_SCOUT_REPORT_ACTION` |  | `hidn` `CSct` `objt` `SctA` `comp` `ctxt` | `HtsC` ✔ **`AssS`** |
| `CTst` | `COMPETITION_TEAM_STATS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `disp` | `DISCIPLINE_PLAYER_ACTION` |  | `hidn` `Hhum` `dref` `fint` `Ttea` | `find` ✔ **`fine`** |
| `ebpl` | `ENQUIRE_ACTION` |  | `buyt` `selt` `Hhum` `dreL` `disa` `hidn` `cotx` | `offD` `offE` `offM` `offe` `EPSB` `Eabp` |
| `FAna` | `FIXTURE_ANALYSIS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `FMst` | `FIXTURE_MATCH_STATS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `FPlr` | `FIXTURE_PLAYER_RATINGS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `forc` | `FORCE_CONTINUE_USER_ACTION` |  | `coid` `dref` `lisC` `hidn` | **`pfco`** |
| `forh` | `FORCE_HOLIDAY_USER_ACTION` | 예 |  | `forh` |
| `Repo` | `GET_PLAYERS_MATCH_REPORT` |  | `Ttea` `Hhum` `dreL` `lisC` `lisS` `ctxt` `hidn` | - |
| `PGoH` | `GO_ON_HOLIDAY_ACTION` | 예 |  | 실행 불가 |
| `Hres` | `HUMAN_RESIGN_ACTION` |  | `hidn` `team` | 실행 불가 |
| `OMLS` | `INTERNAL_OFFER_TO_MLS_CLUBS_ACTION` |  | `hidn` `dreL` `Hhum` `Cclu` | `pomc` ✔ **`poml`** |
| `krpd` | `KEEP_RETIRED_PERSON_DATA_ACTION` |  | `dref` `Hhum` `tick` `csta` `hidn` | `tgkd` |
| `kick` | `KICK_USER_ACTION` |  | `coid` `dref` `hidn` | `Kcon` `kick` |
| `lcra` | `LEADERSHIP_COURSE_ACTION` |  | `hidn` `Hhum` `dref` `Cclu` | **`Ablc`** |
| `pTrM` | `MLS_ROSTER_CHAT_CONVERSATION_ACTION` | 예 |  | `pinc` |
| `NAsS` | `NATION_ASSIGN_SCOUT_ACTION` |  | `hidn` `knlv` `scrs` `disa` `Pers` `Nnat` `TCsL` | - |
| `CNws` | `NEWS_LINK_ACTION` |  | `hidn` `dref` `sect` | - |
| `nick` | `NICKNAME_ACTION` |  | `niha` `dreL` `Hhum` `Ttea` `hidn` | **`aske`** **`askr`** |
| `ObLn` | `OBJECT_LINK_ACTION` |  | `hidn` `islk` `Ttea` `NovP` `tciG` `Tcon` `sect` `smpc` `Pfke` `fcgn` | 실행 불가 |
| `Pcrl` | `PERSON_COACH_REPORTS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `Pnrl` | `PERSON_NATIONAL_REPORTS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `Psal` | `PERSON_SCOUT_ASSIGNMENTS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `Psrl` | `PERSON_SCOUT_REPORTS_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `draf` | `PICK_PLAYER_FROM_DRAFT_ACTION` |  | `hidn` `Ttea` `isFD` `Hhum` `dref` `comp` `dpsc` `dpsa` `pdpl` `Pdva` | `pppc` ✔ **`pppd`** |
| `mlil` | `PLACE_MLS_PLAYER_ON_INJURY_LIST_ACTION` |  | `hidn` `Ttea` `Hhum` `dreL` `pdll` | `rdl6` **`psei`** **`pdl6`** |
| `pach` | `PLAYER_ADVICE_ACTION` | 예 |  | `pinc` |
| `pamb` | `PLAYER_AMBASSADORIAL_ACTION` | 예 |  | `pinc` |
| `pcai` | `PLAYER_CONCERNED_ACTION` | 예 |  | `pinc` |
| `ppai` | `PRAISE_PLAYER_ACTION` | 예 |  | `pinc` |
| `chan` | `PRIVATE_NATIONAL_CONVERSATION_ACTION` | 예 |  | `pinc` |
| `pCtp` | `PROMOTE_CLUB_TO_ANOTHER_PLAYER_BY_TALKING_WITH_THE_PRESS_ACTION` | 예 |  | `pinc` |
| `rols` | `RECALL_PLAYER_FROM_HOLIDAY_ACTION` | 예 |  | **`recl`** |
| `PRLQ` | `RELINQUISH_CONTROL_ACTION` | 예 |  | 실행 불가 |
| `PrIR` | `REQUEST_INJURY_RISK_UPDATE_ACTION` |  | `hidn` `dref` `Hhum` `team` | `Rdir` `Rqir` |
| `PRpr` | `REQUEST_PHYSIO_REPORT_ACTION` |  | `hidn` `dref` `Hhum` `team` | `rdpr` `rptr` |
| `rpaa` | `RESPOND_TO_PLAYER_AGENT_ABOUT_CLIENT_AVAILABILITY_ACTION` | 예 |  | `pinc` |
| `rpla` | `REST_PLAYER_CONVERSATION_ACTION` | 예 |  | `pinc` |
| `Pret` | `RETIRE_ACTION` | 예 |  | 실행 불가 |
| `CScc` | `SCOUT_PLAYERS_CLUB_ACTION` |  | `hidn` `TtPl` `Ttea` `Cclu` `Hhum` `dreL` `lisC` `lisS` `piFA` `ctxt` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `NSco` | `SCOUT_PLAYERS_NATIONAL_ACTION` |  | `Ttea` `Hhum` `dreL` `lisC` `lisS` `piFA` `ctxt` `hidn` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` |
| `Pgra` | `SCOUT_PLAYER_GET_REPORT_ACTION` |  | `hidn` `lisS` `lisA` `dreL` | **`Pgra`** |
| `STAi` | `SCOUT_TEAM_ACTION` |  | `hidn` `Ttea` `Alre` `SdtS` `Sgtm` `Scls` | `esct` ✔ **`erst`** |
| `mooh` | `SEND_MESSAGE_TO_OTHER_HUMAN_ACTION` | 예 |  | 실행 불가 |
| `silc` | `SEND_ON_INTENSIVE_LANGUAGE_COURSE_ACTION` |  | `hidn` `ilcl` | `cspc` ✔ **`aspc`** |
| `hols` | `SEND_PLAYER_ON_HOLIDAY_ACTION` |  | `Ttea` `objL` `hidn` | **`hole`** |
| `Tpfa` | `SERVE_DODGY_LASAGNE_ACTION` |  | `dref` `Hhum` `info` `hidn` | `Apof` **`Rapf`** **`STOR`** |
| `rSTO` | `STOP_SCOUT_PLAYERS_CLUB_ACTION` |  | `Hhum` `dreL` `hidn` | `pDVk` `pspd` `pUNv` `pDVl` `pNdl` `dscn` `pATS` `dsco` **`SCrp`** |
| `SUBS` | `SUBSCRIBE_ACTION` |  | `Hhum` `hidn` `dreL` | `stSU` |
| `PSns` | `SUGGEST_NATIONAL_SQUAD_ACTION` |  | `hidn` `dref` `Hhum` `team` | `psdn` ✔ **`psns`** |
| `pTij` | `TALK_TO_INJURED_PLAYER_ACTION` | 예 |  | `pinc` |
| `Ptom` | `TALK_TO_OTHER_CLUB_MANAGER_ACTION` | 예 |  | `pinc` |
| `Tuta` | `TALK_TO_UNHAPPY_TEAMMATE_ACTION` | 예 |  | `pinc` |
| `TApJ` | `TEAM_APPLY_FOR_JOB_ACTION` | 예 |  | `apj!` ✔ **`apj?`** |
| `TCpJ` | `TEAM_CONTAINER_APPLY_FOR_JOB_ACTION` |  | `hidn` `Hhum` `team` | `apj!` `appj` **`apj?`** |
| `TCdI` | `TEAM_CONTAINER_DECLARE_INTEREST_ACTION` |  | `hidn` `Hhum` `team` | `Tdij` `tdiP` **`tdij`** |
| `TCEx` | `TEAM_CONTAINER_EXPORT_ACTION` | 예 |  | `SEXT` `excf` **`excd`** |
| `TCIn` | `TEAM_CONTAINER_INFORMATION_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `TCFF` | `TEAM_CONTAINER_PICK_FOR_FRIENDLY_ACTION` |  | `hidn` `Hhum` `team` | **`pkfr`** |
| `TCFr` | `TEAM_CONTAINER_PROPOSE_FRIENDLY_ACTION` |  | `hidn` `Hhum` `Ttea` `team` | 실행 불가 |
| `TCRE` | `TEAM_CONTAINER_RESPONSIBILITIES_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `TCSq` | `TEAM_CONTAINER_SQUAD_LINK_ACTION` |  | `hidn` `Ttea` `TeSq` `dref` `sect` `lnks` `Tcon` | 실행 불가 |
| `TCSt` | `TEAM_CONTAINER_STAFF_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `TCkC` | `TEAM_CONTAINER_TAKE_CONTROL_ACTION` |  | `hidn` `Hhum` `team` | **`tac!`** |
| `TDeI` | `TEAM_DECLARE_INTEREST_ACTION` |  | `hidn` `Ttea` `Hhum` `ottm` | `Diij` ✔ **`diij`** |
| `TExa` | `TEAM_EXPORT_ACTION` | 예 |  | `SEXT` `excf` `excd` |
| `TFix` | `TEAM_FIXTURES_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `Tpco` | `TEAM_PARENT_COMPETITION_LINK_ACTION` |  | `hidn` `lnks` | 실행 불가 |
| `Tptc` | `TEAM_PARENT_TEAM_CONTAINER_LINK_ACTION` |  | `hidn` `lnks` `Tcon` | 실행 불가 |
| `TPFv` | `TEAM_PICK_AS_FAVOURITE_ACTION` |  | `hidn` `Hhum` `Ttea` `fave` `remf` | **`pkfv`** |
| `TPFF` | `TEAM_PICK_FOR_FRIENDLY_ACTION` |  | `hidn` `Ttea` `Hhum` | **`pkfr`** |
| `TpFr` | `TEAM_PROPOSE_FRIENDLY_ACTION` |  | `hidn` `NcNF` `Ttea` `Hhum` `fopt` `NcCF` | `proF` |
| `Tres` | `TEAM_RESIGN_ACTION` | 예 |  | 실행 불가 |
| `Trgu` | `TEAM_RESOLVE_GROUP_UNHAPPINESS_ACTION` | 예 |  | `pinc` |
| `TSlF` | `TEAM_SELECT_FEEDER_ACTION` |  | `hidn` `Ttea` `Hhum` | **`pifc`** |
| `TTkC` | `TEAM_TAKE_CONTROL_ACTION` |  | `hidn` `Ttea` `Hhum` | **`tac!`** |
| `TMee` | `TEAM_TEAM_MEETING_LINK_ACTION` |  | `hidn` `dref` `sect` | 실행 불가 |
| `TTTk` | `TEAM_TEAM_TALK_FEEDBACK_ACTION` | 예 |  | **`gttf`** |
| `triC` | `TERMINATE_TRIAL_ACTION` |  | `ttrs` `hidn` `Hhum` `dreL` | `pptc` `pttc` |
| `USUB` | `UNSUBSCRIBE_ACTION` |  | `hidn` `Hhum` `dreL` | `stSU` |
| `wpai` | `WARN_PLAYER_ACTION` | 예 |  | `pinc` |

