import json, time, requests
API='https://api.hyperliquid.xyz/info'
def get(iv, start_ms):
    out=[]; s=start_ms
    while True:
        r=requests.post(API,json={'type':'candleSnapshot','req':{'coin':'xyz:GOLD','interval':iv,'startTime':s}},timeout=30).json()
        if not r: break
        new=[b for b in r if not out or b['t']>out[-1]['t']]
        if not new: break
        out+=new; s=new[-1]['t']+1
        if len(r)<4000: break
    return [dict(t=b['t'],T=b['T'],o=float(b['o']),h=float(b['h']),l=float(b['l']),c=float(b['c'])) for b in out]
import datetime as dt
st=lambda d: int(dt.datetime(2026,*d,tzinfo=dt.timezone.utc).timestamp()*1000)
d={'5m':get('5m',st((10,28))),'15m':get('15m',st((10,25))),'1h':get('1h',st((10,20))),'4h':get('4h',st((9,25))),'1d':get('1d',st((10,20)))}
for k,v in d.items(): print(k,len(v),dt.datetime.utcfromtimestamp(v[0]['t']/1000),dt.datetime.utcfromtimestamp(v[-1]['t']/1000))
json.dump(d,open('data.json','w'))
