# 출처: FM24 Dynamic PA v0.9.5 app/save_context.py (GPL-3.0-or-later). M24GA 포텐 모드에 넣으면서 import 경로만 패키지용(.모듈)으로 바꿨어요. 계산은 그대로예요.
"""Read-only club/team/name context; unknown competition classes stay unknown.

FM24 club/team record facts: FM SaveLens 24. Competition identity markers were
independently checked against this FM24 archive; names from editor tags are
display-only, never used to infer a competition's age restrictions.
"""
from collections import defaultdict
from pathlib import Path
import json,re,struct

U32=struct.Struct('<I').unpack_from
U16=struct.Struct('<H').unpack_from
NONE=0xffffffff
def u32(b,p):return U32(b,p)[0]
def clean(b):
    try:s=b.decode('utf-8')
    except UnicodeError:return None
    return s if s and all(ord(c)>=32 for c in s) else None

NATIONS=json.loads((Path(__file__).with_name('nations.json')).read_text(encoding='utf-8'))
def nation(n):return NATIONS.get(str(n),f'국가 #{n}' if isinstance(n,int) and n!=NONE else '국가 미확인')

def unique(rows,key):
    groups=defaultdict(list)
    for row in rows:groups[row[key]].append(row)
    return {k:v[0] for k,v in groups.items() if len(v)==1}

def read_context(b,players,cancel=lambda:None):
    boundary=min((r.get('ability_offset',len(b)) for r in players),default=len(b))
    from .club_context import read_clubs
    clubs,teams=read_clubs(b,boundary,cancel)
    # The user's editor name overrides can supply names absent from base records.
    overrides={}
    marker=re.compile(rb'yttd\x01\x11([\x03\x19])inud\x01\x0f(.{8})ytrp\x01\x02(manC|manc)lvwn\x01\x1a',re.S)
    for i,m in enumerate(marker.finditer(b)):
        if i%4096==0:cancel()
        p=m.end()
        if p+4>len(b):continue
        length=u32(b,p)
        if not 1<=length<=400 or p+4+length>len(b):continue
        text=clean(b[p+4:p+4+length])
        if text:overrides[(m[1][0],u32(m[2],0))]=text
    for c in clubs.values():c['name']=overrides.get((3,c['uid']),c['name']).strip()
    counts=__import__('collections').Counter(c['name'] for c in clubs.values())
    for c in clubs.values():
        if counts[c['name']]>1:c['name']+=f" [#{c['uid']}]"
    comps=[]
    for i,m in enumerate(re.compile(b'\xff'*16+b'\x01').finditer(b,0,boundary)):
        if i%2048==0:cancel()
        p=m.start()+30
        if p+80>=boundary:continue
        cid,uid,copy=struct.unpack_from('<III',b,p)
        if cid>199999 or uid in (0,NONE) or uid!=copy:continue
        if any(b[p+k]!=v for k,v in ((12,0),(15,1),(22,0),(23,0),(24,0),(25,0),(26,1),(32,2),(40,3))):continue
        comps.append(dict(id=cid,uid=uid,name=overrides.get((25,uid),f'대회 #{uid}'),category=None,nation_name=None))
    comps=unique(comps,'id');duplicate_uids={k for k,v in __import__('collections').Counter(c['uid'] for c in comps.values()).items() if v>1}
    comps={k:v for k,v in comps.items() if v['uid'] not in duplicate_uids}
    for row in players:
        p=row['player'];ctx=p.context;t=teams.get(ctx.get('current_team_id',0)-1)
        c=clubs.get(t['club']) if t else None
        ctx.update(nationality=nation(ctx.get('nation_id')),current_team=c['name'] if c else '소속팀 미확인',
                   current_league='현재 리그 미확인',current_league_country='국가 미확인')
    return dict(clubs=clubs,teams=teams,competitions=comps,diagnostics={'context_clubs':len(clubs),'context_teams':len(teams),'context_competitions':len(comps)})

def category_label(category):
    return {0:'성인',1:'성인',14:'성인',8:'리저브',33:'U23',34:'U22',35:'U21',36:'U20',37:'U19',38:'U18'}.get(category,'대회 구분 미확인')

def decorate(player,total,parts,context):
    comps=context['competitions'];teams=context['teams'];clubs=context['clubs']
    for part in parts:
        comp=comps.get(part['league']-1,{})
        # Stored team references are 1-based; record ordinals are 0-based.
        team=teams.get(part['season_team']-1,{});club=clubs.get(team.get('club'),{})
        part.update(league_name=comp.get('name',f"대회 번호 {part['league']-1}"),
                    league_country=comp.get('nation_name') or '국가 미확인',
                    competition_class=category_label(comp.get('category')),
                    season_team_name=club.get('name',f"팀 번호 {part['season_team']}"))
    def names(key):return list(dict.fromkeys(p[key] for p in parts))
    classes=names('competition_class')
    total.update(context_v090=True,**{key:player.context.get(key) for key in ('current_team','current_league','current_league_country','nationality')},
                 evaluated_team_ids=list(dict.fromkeys(p['season_team'] for p in parts)),evaluated_teams=names('season_team_name'),evaluated_leagues=names('league_name'),evaluated_countries=names('league_country'),
                 evaluated_team=' / '.join(names('season_team_name')),evaluated_league=' / '.join(names('league_name')),
                 league_country=' / '.join(names('league_country')),competition_class=' / '.join(classes),
                 competition_classes=classes,competition_class_known='대회 구분 미확인' not in classes,
                 youth_minutes=sum(p['minutes'] for p in parts if p['competition_class'] in ('U18','U19','U20','U21','U22','U23','리저브')))
