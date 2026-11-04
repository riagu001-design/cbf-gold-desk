#!/usr/bin/env python3
"""Rules v3 backtest: 15m trigger vs 5m trigger, same window, both walked forward on 5m candles.
python3 bt5.py data.json"""
import json,sys,bisect
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
L=ZoneInfo('Europe/London'); H=3600e3; M=60e3
def ema(x,n):
    k,o=2/(n+1),[x[0]]
    for v in x[1:]: o.append(v*k+o[-1]*(1-k))
    return o
def atr(b,n=14):
    tr=[b[0]['h']-b[0]['l']]+[max(x['h']-x['l'],abs(x['h']-p['c']),abs(x['l']-p['c'])) for p,x in zip(b,b[1:])]
    o,a=[None]*len(b),sum(tr[:n])/n; o[n-1]=a
    for i in range(n,len(tr)): a=(a*(n-1)+tr[i])/n; o[i]=a
    return o
def grp(b,ms):
    o=[]
    for x in b:
        k=x['t']//ms*ms
        if o and o[-1]['t']==k: y=o[-1]; y['h']=max(y['h'],x['h']); y['l']=min(y['l'],x['l']); y['c']=x['c']; y['n']+=1
        else: o.append(dict(t=k,o=x['o'],h=x['h'],l=x['l'],c=x['c'],n=1))
    return o
def run(d,tf,stopmode,cost=0.35,start=None):
    m5,m15,h1=d['5m'],d['15m'],d['1h']; h4=[b for b in grp(h1,4*H) if b['n']==4]
    e20,e50,a15=ema([b['c'] for b in m15],20),ema([b['c'] for b in m15],50),atr(m15)
    e50h=ema([b['c'] for b in h1],50); e504=ema([b['c'] for b in h4],50)
    t15=[b['t']+15*M for b in m15]; t1=[b['t']+H for b in h1]; t4=[b['t']+4*H for b in h4]
    sh,sl=[],[]
    for i in range(2,len(h1)-2):
        w=h1[i-2:i+3]; k=h1[i+2]['t']+H
        if h1[i]['h']==max(x['h'] for x in w): sh.append((k,h1[i]['h']))
        if h1[i]['l']==min(x['l'] for x in w): sl.append((k,h1[i]['l']))
    shk=[k for k,_ in sh]; slk=[k for k,_ in sl]
    days={}
    for b in m15:
        dd=days.setdefault(b['t']//86400000,[b['h'],b['l']]); dd[0]=max(dd[0],b['h']); dd[1]=min(dd[1],b['l'])
    bars=m5 if tf==5 else m15; ab=atr(bars); dur=tf*M
    t5=[b['t'] for b in m5]
    first=start or m5[0]['t']
    tr=[]; busy=0; dpl={}; dl={}
    for i in range(60,len(bars)):
        b=bars[i]; T=b['t']+dur
        if b['t']<first or T<busy: continue
        lt=datetime.fromtimestamp(T/1000,timezone.utc).astimezone(L); day=lt.date(); mins=lt.hour*60+lt.minute
        if lt.weekday()>=5 or not(420<=mins<=630 or 780<=mins<=990): continue
        if dl.get(day,0)>=2 or dpl.get(day,0)<=-20: continue
        j=bisect.bisect_right(t15,T)-1; j1=bisect.bisect_right(t1,T)-1; j4=bisect.bisect_right(t4,T)-1
        if j<60 or j1<60 or j4<50 or a15[j] is None: continue
        hs=[p for _,p in sh[:bisect.bisect_right(shk,T)]][-4:]; ls=[p for _,p in sl[:bisect.bisect_right(slk,T)]][-4:]
        if len(hs)<2 or len(ls)<2: continue
        st='UP' if hs[-1]>hs[-2] and ls[-1]>ls[-2] else 'DN' if hs[-1]<hs[-2] and ls[-1]<ls[-2] else 'MIX'
        c1=h1[j1]['c']; bias='UP' if c1>e50h[j1] and st!='DN' else 'DN' if c1<e50h[j1] and st!='UP' else 'FLAT'
        if bias=='FLAT': continue
        buy=bias=='UP'; sg=1 if buy else -1; E20,E50,A=e20[j],e50[j],a15[j]
        if not(E20>E50 if buy else E20<E50): continue
        pv=bars[i-1]; rng=b['h']-b['l'] or 1e-9; pos=(b['c']-b['l'])/rng; body=abs(b['c']-b['o']); pb=abs(pv['c']-pv['o'])
        zlo,zhi=min(E20,E50)-0.25*A,max(E20,E50)+0.25*A
        pd=days.get(b['t']//86400000-1) or days.get(b['t']//86400000-3)
        if not pd: continue
        base=round(b['c']/25)*25; lv=list(pd)+hs+ls+[base+k*25 for k in(-2,-1,0,1,2)]
        zt=b['l']<=zhi if buy else b['h']>=zlo
        ltc=any((abs(b['l']-x)<=0.25*A and b['c']>x) if buy else (abs(b['h']-x)<=0.25*A and b['c']<x) for x in lv)
        if not(zt or ltc): continue
        strong=(b['c']>E20 and b['c']>b['o'] and pos>=2/3) if buy else (b['c']<E20 and b['c']<b['o'] and pos<=1/3)
        eng=(b['c']>b['o'] and pv['c']<pv['o'] and b['c']>=pv['o'] and b['o']<=pv['c'] and body>pb) if buy else (b['c']<b['o'] and pv['c']>pv['o'] and b['c']<=pv['c'] and b['o']>=pv['o'] and body>pb)
        wk=(min(b['o'],b['c'])-b['l']) if buy else (b['h']-max(b['o'],b['c']))
        pin=wk>=2*max(body,1e-9) and wk>=0.5*rng and (pos>=0.6 if buy else pos<=0.4)
        bey=b['c']>E20 if buy else b['c']<E20
        if not(strong or (bey and (eng or pin))): continue
        en=b['c']
        if abs(en-E20)>1.5*A or rng>2*(ab[i] or A): continue
        if stopmode=='own': ext=min(x['l'] for x in bars[i-2:i+1]) if buy else max(x['h'] for x in bars[i-2:i+1]); mn=0.5*(ab[i] or A)
        else:
            k=j; ext=min(x['l'] for x in m15[k-2:k+1]+[b]) if buy else max(x['h'] for x in m15[k-2:k+1]+[b]); mn=0.5*A
        stp=ext-sg*1.5
        if sg*(en-stp)<mn: stp=en-sg*mn
        R=abs(en-stp)
        if R>10: continue
        opp=[x for x in lv if x>en+0.1] if buy else [x for x in lv if x<en-0.1]
        nx=(min(opp) if buy else max(opp)) if opp else None
        rr=abs(nx-en)/R if nx else 9
        if rr<1: continue
        b4='UP' if h4[j4]['c']>e504[j4] else 'DN'; cap=2 if b4==bias else 1.5
        tp=en+sg*R*min(cap,rr)
        k=bisect.bisect_left(t5,T); res=None
        while k<len(m5):
            x=m5[k]; xt=datetime.fromtimestamp((x['t']+5*M)/1000,timezone.utc).astimezone(L)
            if (x['l']<=stp) if buy else (x['h']>=stp): res=sg*(stp-en); break
            if (x['h']>=tp) if buy else (x['l']<=tp): res=sg*(tp-en); break
            if x['t']+5*M-T>=8*H or xt.hour>=21: res=sg*(x['c']-en); break
            k+=1
        if res is None: break
        pl=round(res-cost,2); busy=m5[k]['t']+5*M
        tr.append(dict(t=lt.strftime('%m-%d %H:%M'),side='BUY' if buy else 'SELL',en=en,R=round(R,2),pl=pl))
        dpl[day]=dpl.get(day,0)+pl; dl[day]=dl.get(day,0)+(pl<0)
    return tr
def stats(t):
    if not t: return 'no trades'
    w=[x for x in t if x['pl']>0]; gp=sum(x['pl'] for x in w); gl=-sum(x['pl'] for x in t if x['pl']<0)
    eq=pk=dd=0
    for x in t: eq+=x['pl']; pk=max(pk,eq); dd=max(dd,pk-eq)
    return f"{len(t):3d} trades, {100*len(w)/len(t):3.0f}% wins, ${sum(x['pl'] for x in t):+7.2f}, PF {gp/gl if gl else 99:4.2f}, avg risk ${sum(x['R'] for x in t)/len(t):.2f}, worst drop ${dd:.2f}"
d=json.load(open(sys.argv[1]))
for name,tf,sm in (('15m trigger (current)',15,'own'),('5m trigger, 5m stop',5,'own'),('5m trigger, 15m stop',5,'15')):
    for c in (0.35,0.70):
        t=run(d,tf,sm,c); h=len(t)//2
        print(f'{name:24s} cost ${c:.2f}: {stats(t)}')
        if c==0.35: print(f'{"":24s}   1st half {stats(t[:h])}\n{"":24s}   2nd half {stats(t[h:])}')
