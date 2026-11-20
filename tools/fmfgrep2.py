import sys, os, re, glob, collections, time
sys.path.insert(0, sys.argv[1])
import zstandard as zstd
M=b"\x28\xb5\x2f\xfd"
pat=re.compile(sys.argv[2].encode(), re.I)
targets=sys.argv[3:]
WIN=2*1024*1024
for f in targets:
    t=time.time()
    data=open(f,"rb").read(); mv=memoryview(data); pos=0; hits=collections.Counter(); ex={}; nf=0
    while True:
        i=data.find(M,pos)
        if i<0: break
        try:
            o=zstd.ZstdDecompressor().decompressobj()
            out=o.decompress(mv[i:i+WIN])
            used=min(WIN,len(data)-i)-len(o.unused_data)
            pos=i+max(used,4); nf+=1
        except Exception:
            pos=i+4; continue
        for m in pat.finditer(out):
            k=m.group(0).lower(); hits[k]+=1
            ex.setdefault(k,(i,out[max(0,m.start()-80):m.end()+160]))
    print("##",os.path.basename(f),"frames",nf,"sec",round(time.time()-t,1),dict(hits.most_common(8)),flush=True)
    for k,(i,c) in list(ex.items())[:4]: print("   @",i,c.decode("utf8","replace").replace("\n"," ")[:240],flush=True)
