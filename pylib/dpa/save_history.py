# 출처: FM24 Dynamic PA v0.9.5 app/save_history.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Read FM24 saved league seasons without modifying the .fm file.

Independent parser based on documented container/person layout facts, verified
against an FM24 24.4.2 save and a separately captured live identity sample.
History ownership requires a direct, unique player-to-list reference. Unknown
competition, ambiguous identity, and unsupported record shapes stay excluded.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
import hashlib
import json
import re
import struct

from .save_archive import SaveArchive, SaveError
from .model import Player, decode_date
from .fm24_profile import POSITIONS

PARSER_VERSION = 'fm24-history-0.9.3-clubs'
U32 = struct.Struct('<I').unpack_from
U16 = struct.Struct('<H').unpack_from
I32 = struct.Struct('<i').unpack_from
NONE = 0xffffffff
INFO_HEADER = bytes.fromhex('03017461642e2a00')
HISTORY_WIDTH = 152

def u32(b,p): return U32(b,p)[0]
def u16(b,p): return U16(b,p)[0]

def read_setup(info, db):
    if len(info)<40 or info[:8]!=INFO_HEADER or u32(info,8)!=8 or info[12:20]!=b'24.3.0+0':
        raise SaveError('지원하지 않는 FM24 내부 세이브 형식입니다. 이 파일에서는 과거 기록을 가져오지 않습니다.')
    if len(db)<40: raise SaveError('선수 데이터베이스 헤더가 잘렸습니다.')
    day=decode_date(u32(db,36));sid=u32(info,34)
    if sid in (0,NONE): raise SaveError('세이브 내부 ID를 확인하지 못했습니다.')
    return {'save_id':sid,'game_date':str(day),'format_version':'24.3.0+0','parser_version':PARSER_VERSION}

def name_tables(b,cancel):
    def pool(at):
        count=u32(b,at);at+=4;values=[]
        if not 1<=count<=3000000: raise ValueError()
        for i in range(count):
            if i%8192==0:cancel()
            if at+8>len(b) or u32(b,at)!=i:raise ValueError()
            n=u32(b,at+4)
            if n>512 or at+8+n>len(b):raise ValueError()
            value=b[at+8:at+8+n].decode('utf-8')
            if any(ord(c)<32 for c in value):raise ValueError()
            values.append(value);at+=8+n
        return values,at
    marker=re.compile(rb'.{3}\x00\x00\x00\x00\x00[\x01-\x64]\x00\x00\x00',re.S)
    for index,m in enumerate(marker.finditer(b)):
        if index%8192==0:cancel()
        at=m.start();n=u32(b,at+8)
        if not 10000<=u32(b,at)<=3000000 or at+16+n>len(b) or u32(b,at+12+n)!=1:continue
        try:
            first,end=pool(at);last,end=pool(end);_,end=pool(end)
        except (ValueError,UnicodeError,struct.error):continue
        if len(last)>=10000:return first,last,end
    raise SaveError('FM24 이름 목록을 식별하지 못했습니다.')

PERSON_TAIL=re.compile(rb'([\x00-\xff][\x00\x01])([\x00-\xff][\x07\x08]).{5}([\x00-\xff])\x00\x00{6}([\x01-\x14]{8})',re.S)
PERSON_PREFIX=re.compile(rb'(?=.{4}\x00.{4}\x00.{4}\x00[\x00-\xc8]\x00\x00\x00)',re.S)
ABILITIES=re.compile(rb'[\x01-\x14]{15}[\x01-\x64]{54}')
IDENTITY=re.compile(rb'(?=[\x00\x01\x04\x05]\x00\x00\x00.{12})',re.S)

def player_records(b,cancel=lambda:None,progress=lambda s:None):
    first,last,start=name_tables(b,cancel);progress('이름 목록 확인 · 선수 신원 연결 중')
    people=[]
    for i,m in enumerate(PERSON_TAIL.finditer(b,start)):
        if i%2048==0:cancel()
        end=m.start()
        try:dob=str(decode_date(u32(b,end)))
        except ValueError:continue
        p=end-19
        if b[p+4]==b[p+9]==b[p+14]==0 and u32(b,p+15)==0:candidates=[p]
        else:candidates=[x.start() for x in PERSON_PREFIX.finditer(b,max(start,end-219),end)
                         if x.start()+19+u32(b,x.start()+15)==end]
        valid=[]
        for at in candidates:
            f,l=u32(b,at),u32(b,at+5)
            if (f!=NONE and f>=len(first)) or (l!=NONE and l>=len(last)):continue
            try:inline=b[at+19:end].decode('utf-8')
            except UnicodeError:continue
            # Some valid full-name fields contain a tab between name parts.
            # It is whitespace, not a reason to discard the entire identity.
            if any(ord(c)<32 and c!='\t' for c in inline):continue
            inline=' '.join(inline.split())
            name=' '.join(x for x in (first[f] if f!=NONE else '',last[l] if l!=NONE else '') if x) or inline
            if name:valid.append((at,end,dob,name))
        if len(valid)==1:people.append(valid[0])
    del first,last
    blocks=[]
    for i,m in enumerate(ABILITIES.finditer(b,start+57)):
        if i%2048==0:cancel()
        at=m.start()+15;ca,pa=u16(b,at-38),u16(b,at-36)
        if not 1<=ca<=200 or not 1<=pa<=200 or 20 not in b[at-15:at]:continue
        if u32(b,at-53) in (0,NONE) or u32(b,at-49) in (0,NONE):continue
        blocks.append((at,u32(b,at-57)+1,ca,pa))
    progress(f'선수 능력 블록 {len(blocks):,}개 · 고유 신원 대조 중')
    rows=[];j=0;counts=Counter()
    for i,(at,end,dob,name) in enumerate(people):
        if i%2048==0:cancel()
        prior=j
        while j<len(blocks) and blocks[j][0]<at:j+=1
        if j-prior!=1:continue
        ability,entity,ca,pa=blocks[prior];stop=people[i+1][0] if i+1<len(people) else len(b)
        identities=[]
        for m in IDENTITY.finditer(b,end+21,stop):
            q=m.start()+4;uid,source=u32(b,q+4),u32(b,q+8)
            if u32(b,q)!=entity or uid in (0,NONE) or (b[q-7]&7)>2:continue
            if uid!=source:
                try:decode_date(u32(b,q-12))
                except ValueError:continue
                if b[q-6]&0x85 or not b[q-6]&0x60 or not 1000<=source<NONE:continue
            identities.append((q,uid))
        if len(identities)!=1:counts['unresolved_identity']+=1;continue
        identity,uid=identities[0];ref_at=at-21
        if ref_at<ability+84:counts['bad_history_reference']+=1;continue
        try:
            decode_date(u32(b,ref_at-8));decode_date(u32(b,ref_at-4))
        except ValueError:counts['bad_history_reference']+=1;continue
        raw=b[ability:ability+54];personality=b[end+17:end+25];pos=b[ability-15:ability]
        scale=lambda x:max(1,min(20,(x+2)//5))
        p=Player(uid,name,dob,POSITIONS[max(range(15),key=lambda i:pos[i])],ca,pa,0,
                 personality[4],personality[1],scale(raw[51]),scale(raw[29]),flair=scale(raw[26]),context={'nation_id':u16(b,end+9),'current_team_id':u32(b,ability-23),'attributes':{name:scale(raw[index]) for name,index in {'decisions':18,'anticipation':17,'technique':23,'acceleration':34,'pace':38,'strength':36,'stamina':37,'consistency':44,'natural_fitness':50}.items()}})
        rows.append({'player':p,'history_ref':u32(b,ref_at),'entity_id':entity,
                     'ability_offset':ability,'pa_offset':ability-36,'identity_offset':identity,'dob_offset':end})
    duplicate_uids={uid for uid,n in Counter(x['player'].uid for x in rows).items() if n>1}
    duplicate_entities={eid for eid,n in Counter(x['entity_id'] for x in rows).items() if n>1}
    counts.update(people_headers=len(people),ability_blocks=len(blocks),resolved_players=len(rows),
                  duplicate_uids=len(duplicate_uids),duplicate_entities=len(duplicate_entities))
    result=[x for x in rows if x['player'].uid not in duplicate_uids and x['entity_id'] not in duplicate_entities]
    return result,dict(counts),duplicate_uids

def history_lists(ls,dt,cancel=lambda:None):
    if ls[:8]!=bytes.fromhex('03017461642e0400') or dt[:8]!=bytes.fromhex('0301746d632e0600') or (len(dt)-8)%HISTORY_WIDTH:
        raise SaveError('지원하지 않는 과거 시즌 기록 형식입니다.')
    total=(len(dt)-8)//HISTORY_WIDTH;at=8;seen=bytearray(total)
    def word(signed=False):
        nonlocal at
        if at+4>len(ls)-6:raise SaveError('과거 기록 목록이 잘렸습니다.')
        n=(I32 if signed else U32)(ls,at)[0];at+=4;return n
    def mark(off,value):
        if off<0 or off%HISTORY_WIDTH or off//HISTORY_WIDTH>=total or seen[off//HISTORY_WIDTH]:
            raise SaveError('과거 기록 참조가 중복되거나 범위를 벗어납니다.')
        seen[off//HISTORY_WIDTH]=value
    free=word()
    if free>total:raise SaveError('삭제된 과거 기록 수가 비정상입니다.')
    for i in range(free):
        if i%8192==0:cancel()
        mark(word(),2)
    count=word()
    if count>3000000 or count>(len(ls)-at-10)//4:raise SaveError('과거 선수 목록 수가 비정상입니다.')
    lists=[]
    for i in range(count):
        if i%4096==0:cancel()
        n=word()
        if n>(len(ls)-at-10)//4:raise SaveError('과거 기록 목록 길이가 비정상입니다.')
        refs=[];previous=0
        for _ in range(n):
            encoded=word(True);off=encoded+previous;previous=encoded;mark(off,1);refs.append(off)
        lists.append(refs)
    freed=word();free_lists=set()
    if freed>count:raise SaveError('삭제된 과거 선수 목록 수가 비정상입니다.')
    for _ in range(freed):
        index=word()
        if index>=count or index in free_lists or lists[index]:raise SaveError('삭제된 과거 선수 참조가 비정상입니다.')
        free_lists.add(index)
    if ls[at:]!=struct.pack('<IH',HISTORY_WIDTH,6) or 0 in seen:
        raise SaveError('과거 기록의 전체 참조 검증에 실패했습니다.')
    return lists,free_lists,{'history_lists':count,'history_records':total,'deleted_records':free,'deleted_lists':freed}

def decode_history(dt,offset):
    p=8+offset
    if p<8 or p+HISTORY_WIDTH>len(dt):raise SaveError('과거 기록의 읽기 범위 오류')
    year=u16(dt,p+11);minutes=u16(dt,p+15);starts=dt[p+24];subs=dt[p+25];rated=dt[p+26];rating=u16(dt,p+13)
    if dt[p]!=0 or dt[p+31]>4 or not 1901<=year<=2300:return None
    if minutes>130*(starts+subs) or rated>starts+subs:return None
    if (not rated and rating) or (rated and not 10*rated<=rating<=100*rated):return None
    if dt[p+19]>dt[p+18] or dt[p+19]>dt[p+27]:return None
    return {'year':year,'kind':dt[p+31],'team':u32(dt,p+1),'competition':u16(dt,p+5),
            'minutes':minutes,'rated':rated,'rating_sum':rating,'starts':starts,'subs':subs,
            'goals':dt[p+27],'assists':dt[p+28],'penalties':dt[p+19]}

def aggregate_history(players,lists,free_lists,dt,today,cancel=lambda:None,metadata=None):
    """League-only, explicit season labels. Never pretend these are dated matches."""
    conflicts={ref for ref,n in Counter(x['history_ref'] for x in players if x['history_ref']!=NONE).items() if n>1}
    annual={};counts=Counter();by_uid={}
    # Latest completed July accounting anchor. Never import current year labels.
    due_year=today.year if today>=date(today.year,7,1) else today.year-1
    wanted=set(range(due_year-3,due_year))
    for i,row in enumerate(players):
        if i%2048==0:cancel()
        p=row['player'];by_uid[p.uid]=p;ref=row['history_ref']
        if ref==NONE:counts['no_history']+=1;continue
        if ref in conflicts:counts['duplicate_history_owner']+=1;continue
        if ref>=len(lists) or ref in free_lists:counts['invalid_history_reference']+=1;continue
        grouped=defaultdict(list);invalid_owner=False
        for off in lists[ref]:
            r=decode_history(dt,off)
            if r is None:
                counts['invalid_stats_records']+=1;invalid_owner=True;continue
            if r['year'] not in wanted or r['kind']!=1:continue
            from .scouting_metrics import decode
            r['advanced'],r['advanced_issues']=decode(dt[8+off+32:8+off+152],r['minutes'],r['goals'],p.position)
            grouped[r['year']].append(r)
        if invalid_owner:
            counts['players_with_invalid_stats']+=1;continue
        for year,records in grouped.items():
            # Unknown/absent competition is never replaced by today's league.
            records=[r for r in records if r['minutes'] or r['rated']]
            if not records:continue
            if any(r['team'] in (0,NONE) or r['competition']==65535 for r in records):
                counts['unknown_historical_competition']+=1;continue
            unique={};ambiguous=False
            for r in records:
                key=(r['team'],r['competition'])
                if key in unique and unique[key]!=r:ambiguous=True
                unique[key]=r
            if ambiguous:counts['ambiguous_season_segments']+=1;continue
            # Keep every independently identified club/competition segment.
            leagues={r['competition'] for r in unique.values()}
            if len(leagues)>1:counts['multi_league_seasons_included']+=1
            keys=('minutes','rated','rating_sum','starts','subs','goals','assists','penalties')
            t={key:sum(r[key] for r in unique.values()) for key in keys}
            if t['minutes']>9000 or t['starts']+t['subs']>100:
                counts['implausible_annual_volume']+=1;continue
            # No advanced counts or historical CA are synthesized.
            segments=[dict(**{key:r[key] for key in keys},league=r['competition']+1,
                           season_team=r['team'],season_year=year,position=p.position,advanced=r.get('advanced',{}),advanced_issues=r.get('advanced_issues',[]))
                      for _,r in sorted(unique.items())]
            from .scouting_metrics import combine
            t.update(advanced=combine(segments))
            if metadata is not None:
                from .save_context import decorate
                decorate(p,t,segments,metadata)
            t.update(dob=p.dob,position=p.position,league=next(iter(leagues))+1 if len(leagues)==1 else 0,
                     season_team=records[0]['team'] if len({r['team'] for r in records})==1 else None,
                     competition_ordinal=next(iter(leagues)) if len(leagues)==1 else None,
                     segments=segments,league_count=len(leagues),segment_count=len(segments),
                     transfer_included=len(segments)>1,quality=True,coverage=None,
                     season_confidence=1.0,ca_growth=None,ca_end=None,
                     historical_ca_available=False,talent_age=p.age(today),ability_as_of=str(today),
                     source_kind='saved_league_season',season_year=year,
                     exact_july_window=False,advanced_available=bool(t['advanced']),season_complete=True)
            annual.setdefault(year,{})[p.uid]=t
    return by_uid,annual,dict(counts)

def parse_save(path,cancel=lambda:None,progress=lambda text:None):
    class CancelAdapter:
        def is_set(self):cancel();return False
    progress('세이브에서 과거 시즌 기록을 읽습니다.')
    with SaveArchive(path,CancelAdapter()) as archive:
        lookup={m.name:m for m in archive.members}
        required=('game_info.dat','game_db.dat','rgman/player_stats_hist_ls.dat','player_stats_hist_dt.cmt')
        if any(x not in lookup for x in required):raise SaveError('세이브에 지원하는 과거 시즌 기록 파일이 없습니다.')
        sizes={name:lookup[name].plain for name in required}
        if sizes['game_db.dat']>1536*1024**2 or sizes['player_stats_hist_dt.cmt']>512*1024**2 or sizes['rgman/player_stats_hist_ls.dat']>128*1024**2:
            raise SaveError('이 실험판의 과거 기록 판독 크기 제한을 초과했습니다.')
        if sizes['game_info.dat']>1024**2:raise SaveError('세이브 정보 헤더가 너무 큽니다.')
        def read(name):
            progress(f'파일 자료 읽는 중: {name}')
            return b''.join(archive.chunks(lookup[name]))
        info=read('game_info.dat');db=read('game_db.dat');setup=read_setup(info,db)
        players,diagnostics,duplicates=player_records(db,cancel,progress)
        from .save_context import read_context
        progress('팀·국가·대회 구분 자료 확인 중')
        metadata=read_context(db,players,cancel)
        del db
        ls=read('rgman/player_stats_hist_ls.dat');dt=read('player_stats_hist_dt.cmt')
        lists,free,stats=history_lists(ls,dt,cancel);del ls
        progress('과거 시즌 소유 선수와 리그 기록을 대조합니다.')
        by_uid,annual,issues=aggregate_history(players,lists,free,dt,date.fromisoformat(setup['game_date']),cancel,metadata)
        archive.assert_unchanged()
        result={'setup':setup,'players':by_uid,'seasons':annual,'diagnostics':{**diagnostics,**stats,**issues,**metadata.get('diagnostics',{})},
                'write_locations':{row['player'].uid:{k:row[k] for k in ('entity_id','pa_offset','identity_offset','dob_offset')} for row in players},
                'excluded_uids':sorted(duplicates),'source_size':archive.size,
                'source_fingerprint':archive.initial_stat,'source_name':Path(path).name}
        result['_context']=metadata
        result['diagnostics']['retained_players']=len(by_uid)
        result['diagnostics']['season_counts']={year:len(rows) for year,rows in annual.items()}
        return result
