# 출처: FM24 Dynamic PA v0.9.5 app/club_context.py (GPL-3.0-or-later). M24GA 포텐 모드에 그대로 넣었어요.
"""Read club-owned team references in FM24; never guess a club from a team footer.

Names belong to the body AFTER a serialized footer. The UID used for editor
renames belongs to the closing footer, not the preceding one. The FM24 finance
lists use 24/12-byte entries (not FM26's 25/12). All mappings are display-only.
"""
import re,struct
from collections import defaultdict

U=struct.Struct('<I').unpack_from
NONE=0xffffffff
VERSION='fm24-clubs-0.9.3'
def u32(b,p):return U(b,p)[0]
def name_at(b,p,end):
    if p+4>end:return None
    n=u32(b,p)
    if not 1<=n<=1024 or p+4+n>end:return None
    try:s=b[p+4:p+4+n].decode('utf-8')
    except UnicodeError:return None
    return (s.strip(),p+4+n) if s.strip() and s.isprintable() else None

def headers(b,end,cancel):
    rows=[]
    # A broad name scan also catches created clubs and non-null nation fields.
    for i,m in enumerate(re.compile(rb'[\x01-\xff]\x00\x00\x00').finditer(b,0,end)):
        if i%8192==0:cancel()
        p=m.start()-39
        if p<0 or b[p+12]!=0:continue
        ordinal,uid,copy=struct.unpack_from('<III',b,p)
        if ordinal>500000 or uid in (0,NONE) or copy in (0,NONE):continue
        if any(u32(b,p+k)>1000 and u32(b,p+k)!=NONE for k in (13,21,25)):continue
        long=name_at(b,p+39,end)
        if not long:continue
        short=name_at(b,long[1],end)
        if not short:continue
        rows.append(dict(id=ordinal+1,preceding_uid=uid,offset=p,name=long[0],short_name=short[0],names_end=short[1],nation_id=u32(b,p+13)))
    return rows

def team_list(b,start,end):
    cur=start+37
    for width in (24,12):
        if cur>=end:return None
        n=b[cur];stop=cur+1+n*width
        if stop>end or any(b[p]!=1 for p in range(cur+1,stop,width)):return None
        cur=stop
    cur+=9
    if cur>=end:return None
    n=b[cur]
    if not 1<=n<=16 or cur+1+4*n>=end:return None
    ids=struct.unpack_from('<'+'I'*n,b,cur+1)
    if len(set(ids))!=n or any(not 1<=x<=3000000 for x in ids):return None
    return ids

def owned_teams(b,row,end):
    # Prefer the independently shaped three-date anchor. Float-only candidates
    # are accepted only when they give one unambiguous list inside this body.
    p=row['names_end'];null=struct.pack('<HH',1,1900)*3
    anchors=[];q=b.find(null,p,end)
    while q>=0:
        ids=team_list(b,q,end)
        if ids:anchors.append(ids)
        q=b.find(null,q+1,end)
    if anchors:
        unique=set(anchors)
        return next(iter(unique)) if len(unique)==1 else ()
    candidates=set();q=b.find(b'\x00\x00\x80\x3f',p+33,end)
    while q>=0:
        ids=team_list(b,q-33,end)
        if ids:candidates.add(ids)
        q=b.find(b'\x00\x00\x80\x3f',q+1,end)
    return next(iter(candidates)) if len(candidates)==1 else ()

def read_clubs(b,end,cancel=lambda:None):
    candidates=headers(b,end,cancel);clubs=[];claims=defaultdict(list)
    for i,(row,nxt) in enumerate(zip(candidates,candidates[1:])):
        if i%1024==0:cancel()
        # A neighbouring body authenticates this closing footer's ordinal.
        # Gaps/unsupported variants stay unresolved instead of shifting names.
        if nxt['id']!=row['id']+1 or not 60<nxt['offset']-row['offset']<1024*1024:continue
        ids=owned_teams(b,row,nxt['offset'])
        if not ids:continue
        c={k:row[k] for k in ('id','name','short_name','nation_id')}
        c.update(uid=nxt['preceding_uid'],team_ids=list(ids),source='club_owned_team_list')
        clubs.append(c)
    id_counts=defaultdict(int);uid_counts=defaultdict(int)
    for c in clubs:id_counts[c['id']]+=1;uid_counts[c['uid']]+=1
    clubs={c['id']:c for c in clubs if id_counts[c['id']]==1 and uid_counts[c['uid']]==1}
    for c in clubs.values():
        for tid in c['team_ids']:claims[tid].append(c['id'])
    teams={tid-1:dict(id=tid-1,club=owners[0],source='club_owned_team_list') for tid,owners in claims.items() if len(owners)==1}
    return clubs,teams
