import os, json, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

BASE = 'https://demo.tradelocker.com/backend-api'
ACCOUNT_ID = '2656810'
START = 5000.0
RISK = 0.005
RR = 2.0
DAILY = 50.0
SPREAD = 0.29  # assumed historical spread, USD per ounce
SLIPPAGE = 0.05  # assumed per fill, USD per ounce
FEE = 0.02  # assumed round-trip fee per ounce


def log(*args):
    print(*args, flush=True)


def api(path, headers=None, data=None):
    if data is not None and path != '/auth/jwt/token':
        raise ValueError('POST blocked')
    if path.startswith('/trade/') and data is not None:
        raise ValueError('Trading blocked')
    req = urllib.request.Request(BASE + path, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def connect():
    if os.environ.get('TL_ENVIRONMENT', '').lower() != 'demo':
        raise ValueError('Only DEMO allowed')
    auth = api('/auth/jwt/token', {'Content-Type': 'application/json'},
               json.dumps({k: os.environ[v] for k, v in [('email','TL_EMAIL'),('password','TL_PASSWORD'),('server','TL_SERVER')]}).encode())
    headers = {'Authorization': 'Bearer ' + auth['accessToken']}
    accounts = api('/auth/jwt/all-accounts', headers)['accounts']
    account = next(a for a in accounts if str(a['id']) == ACCOUNT_ID)
    headers['accNum'] = str(account['accNum'])
    instruments = api(f'/trade/accounts/{ACCOUNT_ID}/instruments', headers)['d']['instruments']
    gold = next(i for i in instruments if i['name'].upper() == 'XAUUSD')
    route = next(r for r in gold['routes'] if r['type'] == 'INFO')
    params = {'routeId': route['id'], 'tradableInstrumentId': gold['tradableInstrumentId']}
    log('LOGIN SUCCESSFUL - CORRECT DEMO ACCOUNT - XAUUSD')
    return headers, params


def candles(headers, params, minutes):
    now = int(time.time()*1000)
    query = urllib.parse.urlencode(dict(params, resolution=f'{minutes}m', **{'from': now-7*86400000, 'to': now}))
    result = api('/trade/history?' + query, headers)
    if result.get('s') != 'ok':
        raise ValueError('History unavailable')
    bars = {}
    for b in result['d']['barDetails']:
        t = int(b['t'])
        if t + minutes*60000 <= now:
            bars[t] = (t, float(b['o']), float(b['h']), float(b['l']), float(b['c']))
    return sorted(bars.values())


def smooth(values, n, alpha):
    x = sum(values[:n])/n
    for v in values[n:]:
        x += alpha*(v-x)
    return x


def indicators(bars):
    if len(bars) < 100:
        return None
    bars = bars[-200:]
    c = [b[4] for b in bars]
    d = [y-x for x,y in zip(c,c[1:])]
    g = smooth([max(x,0) for x in d],14,1/14)
    l = smooth([max(-x,0) for x in d],14,1/14)
    rsi = 100-100/(1+g/l) if l else (100 if g else 50)
    e20 = smooth(c,20,2/21)
    e50 = smooth(c,50,2/51)
    tr = [max(b[2]-b[3],abs(b[2]-a[4]),abs(b[3]-a[4])) for a,b in zip(bars,bars[1:])]
    atr = smooth(tr,14,1/14)
    trend = 1 if c[-1]>e20>e50 else -1 if c[-1]<e20<e50 else 0
    return trend,rsi,atr


def signal(m5,m15):
    a,b = indicators(m5),indicators(m15)
    if a and b:
        if a[0]==b[0]==1 and 50<a[1]<70: return 1,a[2]
        if a[0]==b[0]==-1 and 30<a[1]<50: return -1,a[2]
    return 0,0


class Paper:
    def __init__(self):
        self.balance = self.peak = START
        self.dd = 0.0
        self.day = None
        self.day_start = START
        self.pos = None
        self.trades = self.wins = 0
        self.pending = None
        self.last = None

    def day_check(self,t):
        day = datetime.fromtimestamp(t/1000,timezone.utc).date()
        if day != self.day:
            self.day = day
            self.day_start = self.balance

    def enter(self,side,atr,price,spread):
        distance = 1.5*atr
        budget = min(self.balance*RISK, DAILY + self.balance-self.day_start)
        if distance <= 0 or budget <= 0 or self.pos: return
        cost = spread + 2*SLIPPAGE + FEE
        qty = budget/(distance+cost)
        self.pos = (side,price,distance,qty,spread)

    def close(self,price):
        side,entry,dist,qty,spread = self.pos
        pnl = qty*(side*(price-entry)-spread-2*SLIPPAGE-FEE)
        self.balance += pnl
        self.trades += 1
        self.wins += pnl>0
        self.peak = max(self.peak,self.balance)
        self.dd = max(self.dd,self.peak-self.balance)
        self.pos = None
        return pnl

    def step(self,bar,m5,m15,spread):
        t,o,h,l,c = bar
        self.day_check(t)
        if self.pending and not self.pos:
            side,atr,expected = self.pending
            if t==expected: self.enter(side,atr,o,spread)
        self.pending = None
        if self.pos:
            side,entry,d,qty,s = self.pos
            stop,target = entry-side*d,entry+side*(RR*(d+s+2*SLIPPAGE+FEE)+s+2*SLIPPAGE+FEE)
            if side==1:
                if l<=stop: self.close(min(o,stop))
                elif h>=target: self.close(target)
            else:
                if h>=stop: self.close(max(o,stop))
                elif l<=target: self.close(target)
        side,atr = signal(m5,m15)
        if not self.pos and self.balance>0 and self.day_start-self.balance<DAILY and side:
            self.pending = (side,atr,t+300000)
        self.last = t
        return side

    def report(self,label):
        log(label,'BALANCE:',round(self.balance,2),'TRADES:',self.trades,'WINRATE:',round(100*self.wins/self.trades,1) if self.trades else 'N/A','CLOSED DRAWDOWN:',round(self.dd,2),'OPEN:',bool(self.pos))


def process(engine,m5,m15,spread,initial=False):
    j=0
    for i,bar in enumerate(m5):
        t=bar[0]
        while j<len(m15) and m15[j][0]+900000<=t+300000: j+=1
        if engine.last is not None and t<=engine.last: continue
        if i<99 or j<100: continue
        # Never use an M15 candle that had not closed at decision time.
        recent15=m15[max(0,j-200):j]
        if t+300000-(recent15[-1][0]+900000)>1800000: recent15=[]
        side=engine.step(bar,m5[max(0,i-199):i+1],recent15,spread)
        if not initial: log('CLOSED M5:',datetime.fromtimestamp(t/1000,timezone.utc).isoformat(),'TEST SIGNAL:',{1:'BUY',-1:'SELL',0:'WAIT'}[side])


def main():
    log('DEMO READ ONLY - BACKTEST + PAPER - NO ORDERS')
    paper=None
    while True:
        try:
            headers,params=connect()
            while True:
                m5=candles(headers,params,5)
                m15=candles(headers,params,15)
                if len(m5)<100 or len(m15)<100: raise ValueError('Not enough history')
                quote=api('/trade/quotes?'+urllib.parse.urlencode(params),headers)['d']
                bid,ask=float(quote['bp']),float(quote['ap'])
                if bid<=0 or ask<bid: raise ValueError('Invalid quote')
                if paper is None:
                    back=Paper()
                    process(back,m5,m15,SPREAD,True)
                    back.report('BACKTEST 7 DAY WINDOW')
                    paper=Paper()
                    paper.last=m5[-1][0]
                    log('PAPER START - fresh simulation; no historical entries')
                else:
                    process(paper,m5,m15,ask-bid)
                log('BID:',bid,'ASK:',ask,'SPREAD:',round(ask-bid,3))
                paper.report('PAPER')
                log('MODE: READ ONLY - NO ORDERS')
                time.sleep(60)
        except urllib.error.HTTPError as e:
            log('HTTP ERROR:',e.code,'retry in 60 sec')
            time.sleep(60)
        except Exception as e:
            log('ERROR:',type(e).__name__,'retry in 60 sec')
            time.sleep(60)

if __name__=='__main__':
    main()

