import sys, os
sys.path.insert(0, sys.argv[1])
import zstandard as zstd
M=b"\x28\xb5\x2f\xfd"
data=open(sys.argv[2],"rb").read(); outdir=sys.argv[3]; os.makedirs(outdir,exist_ok=True)
pos=0
while True:
    i=data.find(M,pos)
    if i<0: break
    try:
        out=zstd.ZstdDecompressor().decompressobj().decompress(data[i:i+64*1024*1024])
        open(os.path.join(outdir,f"{i:09d}.bin"),"wb").write(out)
    except Exception: pass
    pos=i+4
