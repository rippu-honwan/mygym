"""Causal rep counter on velocity along one axis: v from band-passed acceleration,
a rep per full swing (Schmitt trigger at +-k x recent RMS)."""
import numpy as np, glob, os, json, sys
D=os.path.expanduser("~/dev/mygym/data/motion/" + os.environ["MYGYM_UID"])
class Vel:
    def __init__(s, mode="vert", hz=50, hp=0.7, leak=0.8, lp=0.12, k=0.6, tau=3.0, floor=0.02, min_period=0.6):
        s.dt=1/hz; s.mode=mode; s.hp=s.dt/hp; s.leak=s.dt/leak; s.lp=s.dt/lp; s.k=k; s.tb=s.dt/tau; s.floor=floor; s.minp=min_period
        s.am=None; s.v=np.zeros(3); s.vs=np.zeros(3); s.C=np.eye(3)*1e-6; s.ax=np.array([1.,0,0]); s.ms=0.0
        s.state=0; s.reps=0; s.last=-9; s.events=[]; s.x=[]; s.hi=0; s.lo=0; s.pp=[]; s.per=[]; s.gate=True
    def push(s,t,a,g):
        a=np.asarray(a,float)*9.81; g=np.asarray(g,float)
        if s.mode=="vert": a=np.array([a@g/np.linalg.norm(g),0,0])
        if s.am is None: s.am=a
        s.am=s.am+(a-s.am)*s.hp
        s.v=s.v+(a-s.am)*s.dt; s.v=s.v-s.v*s.leak
        s.vs=s.vs+(s.v-s.vs)*s.lp
        if s.mode=="vert": x=s.vs[0]
        else:
            s.C=s.C+(np.outer(s.vs,s.vs)-s.C)*s.tb
            n=s.C@s.ax; nn=np.linalg.norm(n)
            if nn>0: s.ax=n/nn
            x=float(s.vs@s.ax)
        s.ms=s.ms+(x*x-s.ms)*s.tb
        th=max(s.floor, s.k*s.ms**0.5); s.x.append(x)
        s.hi=max(s.hi,x); s.lo=min(s.lo,x)
        if x>th and s.state<=0:
            if s.state<0 and t-s.last>=s.minp:
                pp=s.hi-s.lo; per=t-s.last
                ok=True
                if s.gate and len(s.pp)>=2:
                    mp=float(np.median(s.pp[-5:])); mq=float(np.median(s.per[-5:]))
                    ok = pp>=0.45*mp and (per<=2.5*mq or True)
                if ok and pp>=0.12:
                    s.reps+=1; s.events.append(round(t,1)); s.pp.append(pp)
                    if per<20: s.per.append(per)
                s.last=t
            s.state=1; s.hi=x; s.lo=0 if s.state==0 else s.lo
            s.lo=0
        elif x<-th and s.state>=0: s.state=-1
        return s.reps
def load(f):
    a=np.genfromtxt(f,delimiter=",",skip_header=2); return a[:,0],a[:,1:4],a[:,7:10]
def run(f,**kw):
    t,a,g=load(f); c=Vel(**kw)
    for i in range(len(t)): c.push(t[i],a[i],g[i])
    return c
if __name__=="__main__":
    sys.path.insert(0,"."); from explore import TRUTH
    T=dict(TRUTH); 
    for k in ("224519_0025_s1","224735_0025_s2","224809_0025_s3","224910_0031_s1"): T[k]=10
    kw=json.loads(sys.argv[1]) if len(sys.argv)>1 else {}
    for mode in ("vert","pca"):
        out=[]
        for k,tr in T.items():
            c=run(glob.glob(f"{D}/*{k}.csv")[0],mode=mode,**kw); out.append(f"{k[7:]}:{c.reps-tr:+d}")
        print(mode," ".join(out))
