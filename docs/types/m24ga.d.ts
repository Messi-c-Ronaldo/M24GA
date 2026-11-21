/**
 * M24GA 코어 0.8.1: 모드의 게임 쪽 JS(mod.js)에서 쓸 수 있는 이름의 목록.
 *
 * 편집기(VS Code 등) 자동완성용이에요. mod.js 맨 위에 아래 한 줄을 적으면 이 파일을 읽어요 (경로는 이 파일 위치에 맞게):
 *     /// <reference path="C:/Program Files/Epic Games/M24GA/docs/types/m24ga.d.ts" />
 *
 * 기능 이름(mod.json "capabilities")과 위험 등급은 docs/CAPABILITIES.md에 있어요. 아래 이름을 쓰면 그 기능을 선언해야 해요.
 * 속성 코드(getVal/getInt의 4글자)는 docs/PROPERTIES.md에 확인된 것만 있어요.
 * AI에게: **여기 없는 함수는 없는 거예요.** 지어내지 말고, 필요한 기능이 여기 없으면 사용자에게 "코어에 아직 없다"고 알려 주세요.
 * Frida가 기본으로 주는 것(File, Memory, send, recv, setInterval ...)은 Frida 타입(@types/frida-gum)이 정의해요.
 * 게임 객체의 주소는 Frida의 NativePointer예요 (여기서는 Ptr로 적어요).
 *
 * 주의: 아래 "코어 함수"는 core/core.js의 전역 함수를 그대로 내놓은 거라 0.x 동안 이름이나 모양이 바뀔 수 있어요.
 * 게임 객체를 읽는 함수는 객체가 맞는지 먼저 확인하고(lookup), 항상 try/catch로 감싸세요. 잘못된 주소는 게임을 튕기게 해요.
 */

/** Frida NativePointer */
type Ptr = any;

/** 소셜 패널(소셜피드 글 한 칸) 이벤트 */
interface SocialPanelEvent {
  /** 패널 객체 주소 */
  th: Ptr;
  /** 글 종류: 0 뉴스 제목, 2·4 팬 댓글, 3·5 공식 글 */
  type: number;
  /** 글자 칸 주소 (setStr의 첫 인자) */
  dst: Ptr;
  /** 지금 화면의 글 */
  text: string;
}

interface ModApi {
  /** 이 모드의 id */
  readonly id: string;
  /** 소셜 패널이 그려질 때. 화면을 그리는 스레드에서 불려요 */
  on(event: 'socialPanel', fn: (ev: SocialPanelEvent) => void): void;
  /** 화면 스레드의 프레임이 끝날 때 (초당 약 20번). 오래 걸리는 일은 하지 마세요 */
  on(event: 'frame', fn: () => void): void;
  /** (코어 0.5.0) 게임 날짜가 바뀔 때 (0.5초마다 확인, 화면 스레드 아님) */
  on(event: 'dateChanged', fn: (ev: { from: GameDate; to: GameDate; days: number }) => void): void;
  /** (코어 0.5.0) 다른 세이브를 불러왔을 때. 나중에 올라온 모드는 처음에 saveInfo()로 확인하세요 */
  on(event: 'saveLoaded', fn: (ev: { id: number; nonce: number; date: GameDate | null }) => void): void;
  /** (코어 0.35.0, event.newsAdded) 게임이 뉴스를 넣을 때마다 (하루 수백 번). 게임 스레드라 짧게. text()는 본문 평문 (비쌈, 콜백 안에서만) */
  on(event: 'newsAdded', fn: (ev: { cls: string; flags: number; toInbox: boolean; team: Ptr | null; mine: boolean; text(): string;
    /** (코어 0.37.0) 뉴스 번호, 날짜 'YYYY-MM-DD', 관련 기록 (콜백 안에서만) */
    id: number; date: string | null; refs(): { people: Ptr[]; teams: Ptr[]; clubs: Ptr[]; comps: Ptr[]; refs: number[] } | null }) => void): void;
  /** (코어 0.37.0, event.matchEnded) 경기 보고 뉴스가 나온 경기마다 한 번 (게임이 보도하는 경기만). 팀은 db::TEAM (api.prop으로 읽기) */
  on(event: 'matchEnded', fn: (ev: { home: Ptr; away: Ptr; homeGoals: number; awayGoals: number; comp: Ptr | null; stadium: Ptr | null; mine: boolean; date: string | null; text(): string }) => void): void;
  /** (코어 0.35.0, event.gameSaved) 게임 저장이 끝났을 때 (.fm 파일 쓰기 완료 뒤) */
  on(event: 'gameSaved', fn: (ev: { ms: number; save: { id: number; nonce: number } | null }) => void): void;
  /** (코어 0.5.0) ms마다 fn (최소 50ms). stop()으로 멈추고, 모드를 내리면 코어가 멈춰요. 화면 스레드 아님 */
  every(ms: number, fn: () => void): { stop(): void };
  /** (코어 0.5.0) ms 뒤 한 번 fn */
  after(ms: number, fn: () => void): { stop(): void };
  /** (코어 0.7.0, 기능 write.player.pa, 사용자 허용 필요) 선수 잠재력(PA)을 바꿔요. uid = 선수 UID, pa = 1~200 정수(CA 이상).
   *  opts.expect를 주면 지금 PA가 그 값일 때만 써요. 모든 쓰기는 기록되고 앱에서 되돌릴 수 있어요. 게임을 저장하면 세이브에 남아요 */
  setPlayerPA(uid: number, pa: number, opts?: { expect?: number; reason?: string }): { ok: boolean; before?: number; after?: number; name?: string; same?: boolean; error?: string };
  /** (코어 0.10.0, 기능 write.field 또는 그 필드의 cap) 필드 등록부에서 write가 safe인 칸을 바꿔요. obj = 게임 객체 또는 그 종류의 key(선수는 UID).
   *  코어가 종류·형식 범위·range·gte/lte·expect·쓰기 전후 신원을 확인하고 기록해요 (앱에서 되돌리기). 목록은 docs/FIELDS.md */
  /** (코어 0.42.0, 기능 write.prop) 속성 코드 값을 게임 setter로 바꿔요. core/properties.json write.codes의 코드만 (tested 코드는 {tested: true}). 기록·되돌리기 됨 */
  setProp(target: Ptr | string, code: string, value: number | boolean | string, opts?: { expect?: number | string; reason?: string; tested?: boolean }): Promise<{ ok: boolean; before?: number | string; after?: number | string; code?: string; key?: number | string; same?: boolean; error?: string }>;
  /** (코어 0.42.0) 여러 코드를 한 번에. 하나라도 실패하면 앞에서 바꾼 것을 되돌려요. 날짜 코드는 'YYYY-MM-DD' */
  setProps(target: Ptr | string, values: Record<string, number | boolean | string>, opts?: { reason?: string; tested?: boolean }): Promise<{ ok: boolean; results?: Record<string, any>; error?: string; rolledBack?: string[] }>;
  setField(obj: Ptr | number | string, name: string, value: number, opts?: { expect?: number; reason?: string }): { ok: boolean; before?: number; after?: number; name?: string; same?: boolean; error?: string };
  /** (코어 0.11.0, 기능 hook.function, 사용자 허용 필요) 함수 등록부(docs/FUNCTIONS.md)의 게임 함수에 끼어들어요. 모드를 내리면 코어가 떼요.
   *  콜백은 게임 스레드에서 불리니 짧게. 반환 { ok, stop(), error } (ok가 false면 error를 보세요: 모르는 함수, 코어 전용, 서명이 다름) */
  hook(name: string, handlers: { before?: (ev: HookEvent) => void; after?: (ev: HookEvent) => void }): { ok: boolean; stop?: () => void; error?: string };
  /** (코어 0.15.0, 기능 hook.gate, 사용자 허용 필요) 게이트 등록부(docs/FUNCTIONS.md '게이트')의 게이트를 켜요. on을 false로 주면 걸어만 두고 끈 상태.
   *  set(켬/끔)으로 바꾸고, stats()는 { scope: 범위 함수 호출, inScope: 범위 안 질문, answered: 바꾼 답, on }. 모드를 내리면 코어가 원래대로 돌려요 */
  gate(name: string, on?: boolean): { ok: boolean; error?: string; set?: (on: boolean) => void; stats?: () => { scope: number; inScope: number; answered: number; on: boolean } | null; stop?: () => void };
  /** (코어 0.17.0, hook.scale) 등록부에서 scale이 있는 함수의 반환값에 객체별 배율 (예: api.scale('player.value').set(선수, 1.2)). 함수 하나에 모드 하나 */
  scale(name: string): { ok: boolean; error?: string; set?: (obj: Ptr, factor: number) => boolean; get?: (obj: Ptr) => number; clear?: () => void; enable?: (on: boolean) => void; stats?: () => { calls: number; changed: number; entries: number; on: boolean } | null; stop?: () => void };
  /** (코어 0.23.0, ui.panel) 게임 안에 FM 모양 대화상자를 띄운다. 양식 = { title, text, fields: [{ id, type: 'text'|'number'|'check'|'select'|'label', label, value, min, max, options }], buttons: [{ id, label }] } */
  /** (코어 0.26.0, write.relation) 감독의 좋아하는/싫어하는 구단 넣기(on=true)·빼기. 화면 스레드에서만. 기록·되돌리기 */
  setRelation(h: Ptr, kind: 'favClub' | 'dislikedClub' | 'favPerson' | 'dislikedPerson', target: Ptr, on?: boolean, opts?: { reason?: string }): { ok: boolean; same?: boolean; error?: string };
  /** (코어 0.31.0, 기능 read.engine / write.engine) 매치엔진 표. 계획은 Python pylib/m24engine.py plan()으로 */
  engine: {
    /** 메모리 그대로 읽기. weights {ints}, physics {entries[{ver,f32[30],i16[7],delays[[열쇠,조각]]}]}, momentum {rows[[사건,구역,좌우,점수]]}, ratings {entries[{ver,start,exp[22],roles[[52]]}]}, (코어 0.32.0) styles {styles[{folder,code,attr[[번호,최소,최대]],tend[...]}], key} = 전술 스타일 (첫 진행일 전에는 {error}), (코어 0.33.0) xg {models[{ver[해,릴리스,주,부], coef{슛 종류: f32[]}, icpt{슛 종류: f32}}]} */
    dump(table: 'weights' | 'physics' | 'momentum' | 'ratings' | 'styles' | 'xg'): any;
    /** 있는 칸에만 쓰기 (styles는 목록 전체, 칸이 늘면 코어가 버퍼를 새로 만듦). 게임이 진행 중이면 거절. 세이브에 안 남음 */
    write(table: 'weights' | 'physics' | 'momentum' | 'ratings' | 'styles' | 'xg', spec: any): { ok?: boolean; written?: number; missing?: any[]; error?: string };
  };
  /** (코어 0.34.0, 기능 ui.inbox) 게임 받은 편지함에 메일 한 통. '보낸이의 말: 제목'으로 보이고 세이브에 남아요 (되돌리기 없음, 1분에 10통) */
  inbox: {
    /** title 200자·body 8000자까지. from = 사람 객체 (myHuman(), personByName(이름).person, 없으면 내 감독). 내 감독이 팀을 맡고 있어야 해요 */
    send(mail: { title: string; body?: string; from?: Ptr | 'me' }): Promise<{ ok: boolean; error?: string; title?: string; chars?: number }>;
    /** 이 코어가 받은 편지함 메일을 지원하는가 */
    available(): boolean;
  };
  /** (코어 0.36.0, 기능 read.prop) 게임 속성 코드 읽기 (core/properties.json, docs/PROPERTIES.md). 대상 = 객체 포인터 또는 'me'|'myteam'|'myclub'|'myjob'|'p123'|'s45'|'team:<번호>'|'comp:<번호>'.
   *  값 / null(빈 값) / undefined(이 객체가 답하지 않는 코드). 모르는 객체·막은 코드는 예외 */
  prop(obj: Ptr | string, code: string): any;
  /** 그 객체가 답하는 코드(등록부 기준) 전부 {코드: 값}. re = 코드 정규식, codes = 코드 목록, empty = 빈 값도 */
  props(obj: Ptr | string, opts?: { re?: string; codes?: string[]; empty?: boolean }): { [code: string]: any };
  /** 등록부 정보: t = 값 종류(int|u32|num|bool|str|date|color|rec|list|data|empty), k = 답하는 객체 종류 */
  propInfo(code: string): { code: string; t: string; k: string[]; blocked: boolean; writable: 'safe' | 'tested' | 'deny' | false; writeKinds?: string[]; range?: [number, number] } | null;
  /** {dref} 또는 번호 -> 게임 객체 (0x01 사람, 0x03 구단, 0x18 팀, 0x19 대회). 모르면 null */
  deref(d: { dref: number } | number): Ptr | null;
  /** (코어 0.40.0, read.prop) 리그 경기 결과 (보도 안 되는 경기 포함). 대회 객체 또는 'myleague'. 지난번 부른 뒤 끝난 경기. 처음엔 기준만 잡고 [] */
  leagueResults(comp: Ptr | 'myleague'): { home: Ptr; away: Ptr; homeGoals: number; awayGoals: number; date: string | null; fixture: number; comp: Ptr }[];
  /** (코어 0.41.0, 기능 read.action) 게임 메뉴가 그 대상(사람·팀·대회)에 보여 주는 명령. opts.all = 숨은 것도. docs/ACTIONS.md */
  actionsFor(target: Ptr | string | { dref: number } | number, opts?: { all?: boolean }): Promise<{ id: string; cls: string | null; hidden: boolean; disabled: boolean; canRun: boolean; events: string[]; click: string[]; confirm: string | null; args: Record<string, any> }[] | { ok: false; error: string }>;
  /** (코어 0.41.0, 기능 game.action, 세이브를 바꿈) 게임이 보여 주는 명령일 때만 실행. event = 처리기 이벤트(하나면 생략, 확인 창 명령은 확인 뒤 이벤트 예: PmcP의 pmcC), danger = 사임·은퇴 같은 명령 허용 */
  action(id: string, target: Ptr | string | { dref: number } | number, opts?: { event?: string; danger?: boolean }): Promise<{ ok: boolean; error?: string; id?: string; cls?: string; event?: string; target?: number; handled?: boolean }>;
  panel: {
    open(form: PanelForm, cb?: (ev: PanelEvent) => void): PanelHandle;
    /** 게임 안 패널을 지금 쓸 수 있는가 (패널 칸 파일과 게임 함수 확인) */
    available(): boolean;
  };
  /** (코어 0.12.0) 이 모드의 설정 값 {key: 값} (mod.json settings, 파일에 없거나 틀린 값은 default, 비밀번호 형식은 빠짐). 부를 때마다 새 복사본. 사용자 허용 필요 없음 */
  settings(): Record<string, string | number | boolean>;
  /** (코어 0.12.0) 앱에서 설정이 바뀌면 새 값으로 불려요. 한 모드에 하나 (나중 것이 앞의 것을 바꿈). 게임 스레드가 아닐 수 있어요 */
  onSettings(fn: (settings: Record<string, string | number | boolean>) => void): void;
  /** 앱/로더 상태에 합쳐질 값을 돌려주는 함수를 등록 */
  status(fn: () => Record<string, unknown>): void;
  /** 게임 데이터 표(clubs, persons, staff ...)를 만들기 시작하고 값 종류를 얻어요. 소셜 패널 안에서 한 번 부르면 돼요. 표는 1~2분 걸리고 끝나면 mapsReady가 true */
  prepareData(th: Ptr): void;
  /** loader.log에 "game: [모드id] 글"로 남겨요 (console.log는 안 보여요) */
  log(msg: string): void;
  /** 이 모드의 Python 부분(ctx.recv)으로 메시지를 보내요. JSON으로 바꿀 수 있어야 해요. 유실될 수 있어요 */
  send(data: unknown): void;
  /** Python의 ctx.post()로 온 메시지를 받아요. 하나만 등록돼요 (나중 것이 앞의 것을 바꿔요) */
  recv(fn: (data: any) => void): void;
  /** (코어 0.3.0) 모드를 내릴 때(끄기, 새 버전, 다시 올리기) 불려요. 모드가 직접 건 Interceptor·setInterval·바꿔 둔 화면 글자를 여기서 치워요.
   *  api로 등록한 것(on, status, recv)은 코어가 알아서 떼요. 이 안에서 log/send는 되지만 새로 등록은 안 돼요 */
  onUnload(fn: () => void): void;
  /** (코어 0.3.0) 이 모드가 아직 올라가 있나. 내린 뒤에는 false이고 api 호출은 아무 일도 안 해요 */
  alive(): boolean;
}

/** 게임 날짜. doy = 연중 일수, iso = "2035-04-25" */
interface GameDate { y: number; m: number; d: number; doy: number; iso: string }
/** (코어 0.5.0) 지금 게임 날짜. 세이브를 안 불러왔으면 null */
declare function gameDate(): GameDate | null;
/** (코어 0.5.0) 지금 세이브 식별 {id, nonce}. 없으면 null */
declare function saveInfo(): { id: number; nonce: number } | null;

/** 로더가 넣어 주는 API. registerMod는 쓰지 않아요 */
declare const api: ModApi;
/** 이 모드의 데이터 폴더 (끝에 / 포함). 파일을 읽고 쓸 때는 이 안에서만 */
declare const DIR: string;

// ---- 게임 데이터 표 (api.prepareData 뒤, mapsReady가 true일 때 쓸 수 있어요) ----
/** 번호 -> 데이터 객체 주소 */
declare const clubs: Record<number, Ptr>;
declare const persons: Record<number, Ptr>;
declare const staff: Record<number, Ptr>;
declare const mapsReady: boolean;
declare const uidReady: boolean;
/** 클럽 번호가 없어진 감독 자리 */
declare const vacant: Record<number, boolean>;
/** 객체 종류 확인용 vtable 주소 (lookup의 세 번째 인자) */
declare const CLUB_VT: Ptr;
declare const PERSON_VT: Ptr;
declare const STAFF_VT: Ptr;
declare const CLUBOBJ_VT: Ptr;
declare const NT_VT: Ptr;
/** fm.exe 기준 주소 */
declare const B: Ptr;
/** 화면을 그리는 스레드 번호 (패널을 그린 적이 있으면) */
declare let uiTid: number;

// ---- 코어 함수: 읽기 ----
/** 표에서 번호로 객체를 꺼내고 아직 같은 객체인지 확인해요. 아니면 null. 표의 객체는 항상 lookup으로 꺼내세요 */
declare function lookup(map: Record<number, Ptr>, idx: number, vt: Ptr): Ptr | null;
/** 데이터 객체의 속성을 읽어요 (4글자 코드). 숫자·글자·{...} 객체·배열 중 하나, 없으면 null. 객체가 클럽/사람이 아니면 예외 */
declare function getVal(obj: Ptr, code: string): any;
/** 정수 속성만 읽어요. 없거나 정수가 아니면 null */
declare function getInt(obj: Ptr, code: string): number | null;
/** 글 속 링크를 풀어요. type 0x18 = 클럽, 0x01 = 사람 */
declare function linkIds(text: string): { name: string; type: number; idx: number }[];
/** 뉴스 기사 본문 (평문). 실패하면 '' */
declare function newsBody(news: Ptr): string;
/** 내 감독과 클럽. 무직이면 mgr만, 못 구하면 null */
declare function myInfo(): { mgr: string; co: Ptr; club?: string; full?: string } | null;
/** 팬 고유 ID(Salo) -> 응원 클럽 정보 */
declare function fanClub(uid: number): {
  uid: number; name?: string; full?: string; mine?: boolean;
  mgr?: string; mgr_caretaker?: boolean; mgr_vacant?: boolean; mgr_d?: Record<string, any>;
  /** 최근 5경기, [0]이 가장 최근. 값은 0~3 */
  form?: number[];
};
/** 클럽 번호 -> 지금 감독 {이름, 객체, 임시감독 여부}. 없으면 null */
declare function clubManagerObj(idx: number, count?: boolean): { name: string; obj: Ptr; caretaker?: boolean } | null;
declare function clubManager(idx: number): string;
declare function clubManagerAttrs(m: { name: string; obj: Ptr }): Record<string, any> | null;
/** 사람 ID(0x01xxxxxx 형식 dref) -> 이름 */
declare function personName(dref: number): string | null;
/** 선수 폼: avg 시즌 평균 평점, apps 출전, goals 골, recent 최근 5경기 평점 배열, recentAvg, recentGoals */
declare function personForm(o: Ptr): { avg?: number; apps?: number; goals?: number; recent?: number[]; recentAvg?: number; recentGoals?: number };
declare function formText(f: ReturnType<typeof personForm>): string;
declare function personExtra(o: Ptr): Record<string, any>;
/** 가장 숙련된 포지션 이름 (선수가 아니면 null) */
declare function mainPosition(obj: Ptr): string | null;
/** 클럽의 핵심 선수: code는 Tstg/Tsma/Tsar, ids[이름]에 사람 ID가 채워져요 */
declare function topPlayer(obj: Ptr, code: string, ids: Record<string, number>): string | null;
/** 클럽 정보를 d에 채워 넣어요 */
declare function clubExtra(obj: Ptr, d: Record<string, any>): void;
declare function clubSituation(obj: Ptr, d: Record<string, any>): void;
declare function staffAttrs(obj: Ptr): Record<string, any>;
declare function decodeVal(tp: Ptr, vbuf: Ptr, depth: number): any;

// ---- 코어 함수: 선수 (코어 0.6.0, read.player) ----
/** 선수 정보. ca = 현재 능력, pa = 잠재력 (1~200, PA가 음수면 범위로 지정된 잠재력) */
interface PlayerInfo { uid: number; ca: number; pa: number; dob: GameDate | null; name: string }
/** 사람 데이터 객체(persons 표에서 lookup한 것) -> 선수 객체. 선수가 아니면 null */
declare function playerOf(o: Ptr): Ptr | null;
/** 선수 UID(게임 DB 고유 ID) -> 선수 객체. 없으면 null */
declare function playerByUid(uid: number): Ptr | null;
/** 선수 객체 -> 정보. 못 읽으면 null */
declare function playerInfo(p: Ptr): PlayerInfo | null;
/** (코어 0.17.0, read.player.value) 게임의 선수 가치(몸값) 계산. club = 평가하는 구단(없으면 구단 없이). 내부 돈 단위 (원화 = ×1664.7).
 * 게임이 진행 중이면 { error, busy }. 타이머에서 부를 것 (frame·api.hook 콜백 안에서는 게이트·배율이 빠진 값) */
declare function playerValue(p: Ptr, club?: Ptr | null): { value: number; reasons: { code: number; a: number; b: number }[] | null; club: string | null } | { error: string; busy?: boolean } | null;
/** (코어 0.20.0, read.award) 대회 번호 -> 정보 (번호 = 세이브 기록의 대회 번호). 표가 없거나 모르는 번호면 null */
declare function compInfo(idx: number): { idx: number; uid: number; name: string; short: string; nation: string | null; continent: string | null } | null;
/** (코어 0.20.0, read.award) 상 번호 -> 정보 (comp = 딸린 대회 번호) */
declare function awardInfo(idx: number): { idx: number; name: string; short: string; comp: number | null; nation: string | null; continent: string | null } | null;
declare function compIds(): number[];
/** (코어 0.21.0, read.award) 대회의 가장 최근에 끝난 시즌 결과 (팀 번호). 없으면 null */
declare function compLatest(idx: number): { comp: number; start: number; end: number; winner: number | null; runnerUp: number | null; third: number | null } | null;
declare function awardIds(): number[];
/** 지금 세이브의 모든 선수 UID (약 12만 개, 자주 부르지 마세요) */
declare function playerUids(): number[];
/** 사람 데이터 객체의 고유 ID(= 선수 UID). 없으면 null */
declare function personUid(o: Ptr): number | null;

// ---- 코어 함수: 선수 시즌 기록·포지션·성격·소속 (코어 0.8.0, read.player) ----
/** 대회 구분: club = 클럽 공식전 합계(리그+국내 컵+대륙컵), league 리그, cup 국내 컵, continental 대륙컵(챔스 등), international 국가대표 */
type SeasonKind = 'club' | 'league' | 'cup' | 'continental' | 'international';
/** 이번 시즌 기록. avg = 평균 평점(소수 둘째 자리, 평점 받은 경기가 없으면 null), minutes = 출전 분, pens = PK 골 */
interface PlayerSeason { apps: number; starts: number; subs: number; minutes: number; rated: number; ratingSum: number; avg: number | null; goals: number; assists: number; pens: number }
/** 이번 시즌 상세 기록(합계 횟수). xg·xa·npxg는 소수. 게임 속성과 맞춰 본 건 xg뿐이에요 */
interface PlayerSeasonDetail { xg: number; xa: number; npxg: number; shots: number; shotsOnTarget: number; keyPasses: number; dribbles: number;
  passesAttempted: number; passesCompleted: number; progressivePasses: number; tacklesAttempted: number; tacklesCompleted: number;
  headersAttempted: number; headersWon: number; interceptions: number; clearances: number; pressuresAttempted: number; pressuresCompleted: number;
  crossesAttempted: number; crossesCompleted: number }
/** 선수 객체 -> 이번 시즌 기록 (kind 기본 'club'). 기록이 없거나 범위가 이상하면 null */
declare function playerSeason(p: Ptr, kind?: SeasonKind): PlayerSeason | null;
/** 선수 객체 -> 이번 시즌 상세 기록 (kind 기본 'club'). 없으면 null */
declare function playerSeasonDetail(p: Ptr, kind?: SeasonKind): PlayerSeasonDetail | null;
/** 포지션 코드 (게임 순서) */
type PositionCode = 'GK' | 'SW' | 'DL' | 'DC' | 'DR' | 'DM' | 'ML' | 'MC' | 'MR' | 'AML' | 'AMC' | 'AMR' | 'ST' | 'WBL' | 'WBR';
/** 선수 객체 -> 포지션별 숙련도 1~20 (20 = 자연스러움). 못 읽으면 null */
declare function playerPositions(p: Ptr): Record<PositionCode, number> | null;
/** 가장 숙련된 포지션 (같으면 게임 순서로 앞의 것) */
declare function playerPosition(p: Ptr): { code: PositionCode; level: number } | null;
/** 성격·정신 (모두 1~20, 못 읽은 칸은 null) */
declare function playerTraits(p: Ptr): { ambition: number | null; professionalism: number | null; determination: number | null; workRate: number | null; flair: number | null } | null;
/** (코어 0.8.1) 부상 상태. 부상 중이면 injured=true와 type(부상 종류 번호)·category·daysSince(부상 후 지난 일수)·remainMin/remainMax(남은 예상 일수 범위)·expectedTotal(예상 전체 일수, 대략).
 *  proneness = 부상 경향 1~20. 로더가 붙은 뒤 사람 표가 다 만들어지기 전(1~2분)에는 null */
declare function playerInjury(p: Ptr): { injured: boolean; proneness: number | null; type?: number; category?: number; daysSince?: number; remainMin?: number; remainMax?: number; expectedTotal?: number } | null;
/** 소속 팀. club = 클럽 객체(대표팀·없으면 null), name/short = 클럽 이름, compUid = 팀이 뛰는 대회(리그) UID (없으면 null). 팀이 없으면 null */
declare function playerTeam(p: Ptr): { team: Ptr; club: Ptr | null; name: string; short: string; compUid: number | null } | null;
/** (코어 0.9.0) 선수 객체 -> 사람 데이터 객체 (getVal/getInt로 속성을 읽는 객체, persons 표의 것과 같음). 선수 객체 +0x278 위치. 선수가 아니면 null */
declare function personOf(p: Ptr): Ptr | null;

// ---- 코어 함수: 객체의 클래스 이름 (코어 0.9.0, read.rtti) ----
/** 게임 객체의 클래스 정보. name = 'db::ACTUAL_PLAYER'처럼 이름공간까지, off = 이 vtable이 객체 안 어디 있는지(다중 상속), top = 객체 맨 앞 주소, bases = 물려받은 클래스(가까운 순). vtable·RTTI가 없으면 null */
declare function rttiInfo(obj: Ptr | string): { name: string; off: number; top: Ptr; bases: string[] } | null;
/** 게임 객체의 클래스 이름 (없으면 null) */
declare function className(obj: Ptr | string): string | null;
/** 이 클래스이거나 이 클래스를 물려받았나 (예: isA(p, 'db::PERSON')) */
declare function isA(obj: Ptr | string, name: string): boolean;

// ---- 코어 함수: 필드 등록부 (코어 0.10.0, read.field) — 목록은 docs/FIELDS.md ----
type FieldValue = number | string | Ptr | { y: number; m: number; d: number; doy: number; iso: string } | null;
/** 객체의 필드 값 (종류가 다르거나 못 읽으면 null). 모르는 필드 이름이면 예외. date는 {y, m, d, doy, iso}, ptr은 포인터, str/strref는 글 */
declare function getField(obj: Ptr | string, name: string): FieldValue;
/** 종류와 key로 객체 찾기: findObj('player', uid). key 필드가 없는 종류는 주소 글('0x...') */
declare function findObj(kind: 'player' | 'team' | 'club' | 'human' | string, key: number | string): Ptr | null;
/** 필드 정보 {kind, off, type, desc, write, ...} (없으면 null) */
declare function fieldInfo(name: string): { kind: string; off: string; via?: string[]; type: string; desc?: string; unit?: string; write?: 'no' | 'safe'; verified?: boolean } | null;
/** 필드 이름 목록 (prefix로 거르기, 예: fieldNames('player.season.league.')) */
declare function fieldNames(prefix?: string): string[];

// ---- 코어 함수: 소셜 패널 도우미 (코어 0.6.0, read.panel) ----
/** 패널 주소 문자열(th.toString())로 다시 찾기. 아직 소셜 패널이고 (type을 주면) 글 종류가 같으면 그 객체, 아니면 null */
declare function panelAt(addr: string, type?: number): Ptr | null;
/** 글자 칸 (setStr의 첫 인자, ev.dst와 같음) */
declare function panelDst(th: Ptr): Ptr;
/** 지금 패널 글. '' = 비어 있음, null = 못 읽음 */
declare function panelText(th: Ptr): string | null;
/** 지금 글자 객체의 주소 (내가 넣은 글이 그대로인지 비교용) */
declare function panelTextHandle(th: Ptr): string | null;
/** 스레드(뉴스) 객체 (newsBody에 넘김, 같은 글 묶기 키) */
declare function panelThread(th: Ptr): Ptr | null;
/** 댓글 작성자가 응원하는 클럽의 고유 ID (fanClub에 넘김). 없으면 0 */
declare function panelFanUid(th: Ptr): number;
/** 클럽 데이터 객체(clubs 표) -> 클럽 객체 (대표팀이면 null) */
declare function clubObj(cd: Ptr): Ptr | null;
/** 클럽 정식 이름 / 짧은 이름 (대표팀이면 '') */
declare function clubFullName(cd: Ptr): string;
declare function clubShortName(cd: Ptr): string;

// ---- 코어 함수: 화면 ----
/** 소셜 패널의 글자 칸을 새 글로 바꿔요 (dst는 SocialPanelEvent.dst) */
declare function setStr(dst: Ptr, str: string): void;
/** 패널을 다시 그려요. **화면 스레드에서만** (socialPanel / frame 콜백 안) */
declare function refreshPanel(th: Ptr): void;

// ---- 도우미 ----
declare function hash64(s: string): string;
/** 진단 기록 (~/m24ga_data/hook_debug.txt, 처음 40줄만). 평소에는 api.log를 쓰세요 */
declare function dbg(msg: string): void;

/** (코어 0.11.0) api.hook 콜백이 받는 값. before와 after가 같은 객체를 받아요 */
interface HookEvent {
  /** 함수 이름 */
  name: string;
  /** functions.json의 args 형식대로 바꾼 인자 (ptr은 포인터, i32/u32는 숫자, i64는 글, bool) */
  args: Array<Ptr | number | string | boolean | null>;
  /** i번째 인자의 원래 포인터 값 (등록된 것보다 뒤의 인자도) */
  raw(i: number): Ptr;
  /** 부른 곳 'fm+0x...' */
  caller: string;
  /** 스레드 번호 */
  tid: number;
  /** before에서 after로 넘길 값을 두는 칸 */
  data: Record<string, unknown>;
  /** after에서: 반환값 (functions.json의 ret 형식) */
  ret?: Ptr | number | string | boolean;
  /** hook이 modify인 함수만, before에서 */
  setArg(i: number, v: Ptr | number): void;
  /** hook이 modify인 함수만, after에서 */
  setRet(v: Ptr | number): void;
}

/** 게임 안 패널 양식 (코어 0.23.0, api.panel.open) */
interface PanelForm {
  title?: string;
  text?: string;
  width?: number;
  closeLabel?: string;
  /** (코어 0.29.0) false면 person/club 칸에서 고른 뒤 창을 다시 그리지 않아요 */
  refreshOnPick?: boolean;
  /** person/club(코어 0.29.0) = 게임 검색칸. value에 { ref } / { uid }를 주면 "지금: …"으로 보여요. nowLabel = "지금: " 대신 쓸 글 */
  fields?: { id?: string; type?: 'text' | 'number' | 'check' | 'select' | 'label' | 'person' | 'club'; label?: string; value?: any; min?: number; max?: number; options?: (string | { value: any; label?: string })[]; nowLabel?: string }[];
  buttons?: { id: string; label?: string }[];
}
/** (코어 0.29.0) person/club 칸에서 고른 것. values()에서 안 골랐으면 { text } (친 글) 또는 null */
interface PanelPick { type: 'person' | 'club'; ref?: string | null; uid?: number | null; name: string | null; age?: number | null; club?: string | null; role?: 'player' | 'staff' | null; label: string; person?: Ptr; }
/** 게임 안 패널 이벤트. id = 칸·버튼 id 또는 'open'·'close'·'error' */
interface PanelEvent { id: string; kind: 'open' | 'close' | 'error' | 'button' | 'change' | 'check' | 'select' | 'pick'; value?: any; error?: string; values(): Record<string, any>; panel: PanelHandle; }
interface PanelHandle { ok: boolean; error?: string; slot?: number; isOpen?(): boolean; get?(id: string): any; values?(): Record<string, any>; close?(): void; }

// ---- 사람 감독 (코어 0.24.0, read.me) ----
/** 이 PC의 사람 감독 객체 (db::HUMAN_NON_PLAYER). 소셜 화면 없이 언제든. 세이브가 없으면 null. 칸은 getField(myHuman(), 'human.pastPlayingExperience') 등 */
declare function myHuman(): Ptr | null;
/** 사람이 조종하는 감독 목록 (온라인 게임이 아니면 하나) */
declare function humans(): Ptr[];
/** (코어 0.25.0) 감독의 관계 목록 (좋아하는/싫어하는 구단·사람). 읽기만. kind 1 좋아하는 사람, 2 싫어하는 사람, 3 좋아하는 구단, 4 싫어하는 구단 */
declare function humanRelations(h?: Ptr): { target: Ptr; cls: string | null; kind: number; kindName: string | null; level: number; reason: number; name?: string }[];
/** (코어 0.26.0) 정식 이름 또는 짧은 이름이 같은 구단 (db::CLUB). 없으면 null */
declare function clubByName(name: string): Ptr | null;
/** (코어 0.26.0) 구단 고유 번호 -> 구단 */
declare function clubByUid(uid: number): Ptr | null;
/** (코어 0.26.0) 구단 -> 고유 번호 */
declare function clubUid(club: Ptr): number | null;
/** (코어 0.27.0) 이름이 같은 사람 (선수·스태프). 이름 색인을 만드는 동안은 { pending: true } */
declare function personByName(name: string): { person: Ptr; ref: string; many: boolean; count: number } | { pending: true } | null;
/** (코어 0.27.0) 사람 참조 글('p123' 선수, 's45' 스태프) -> 사람 */
declare function personByRef(ref: string): Ptr | null;
/** (코어 0.27.0) 사람 -> 참조 글 */
declare function personRef(person: Ptr): string | null;
/** (코어 0.28.0) 사람 정보: 이름·나이·소속 구단 이름('' = 무소속)·선수/스태프 */
interface M24PersonInfo { person: Ptr; ref: string | null; name: string | null; age: number | null; club: string | null; role: 'player' | 'staff' | null }
/** (코어 0.28.0) 이름이 같은 사람 모두 (최대 8명). 이름 색인을 만드는 동안은 { pending: true } */
declare function personsByName(name: string): M24PersonInfo[] | { pending: true };
/** (코어 0.28.0) 사람 -> 정보 */
declare function personInfo(person: Ptr, ref?: string): M24PersonInfo;
