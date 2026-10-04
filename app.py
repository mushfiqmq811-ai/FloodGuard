from flask import Flask, render_template, jsonify, request, Response, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, timezone
import math, random, threading, time, statistics, os, sqlite3, re, smtplib, urllib.parse, json
from live_data import fetch_ffwc_current

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'floodguard.db')
app = Flask(__name__, template_folder='.', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'floodguard-dev-secret-change-me')

# User-provided Mymensingh readings retained as historical project observations.
MYMENSINGH_REAL = [
('2026-05-09 09:00:00',9.29),('2026-05-09 12:00:00',9.23),('2026-05-09 15:00:00',9.18),('2026-05-09 18:00:00',9.13),
('2026-05-10 06:00:00',8.87),('2026-05-10 09:00:00',8.82),('2026-05-10 12:00:00',8.75),('2026-05-10 15:00:00',8.69),('2026-05-10 18:00:00',8.64),
('2026-05-11 06:00:00',8.41),('2026-05-11 09:00:00',8.36),('2026-05-11 12:00:00',8.30),('2026-05-11 15:00:00',8.25),('2026-05-11 18:00:00',8.20),
('2026-05-12 06:00:00',8.04),('2026-05-12 09:00:00',7.99),('2026-05-12 12:00:00',7.96),('2026-05-12 15:00:00',7.92),('2026-05-12 18:00:00',7.88),
('2026-05-13 06:00:00',7.80),('2026-05-13 09:00:00',7.78),('2026-05-13 12:00:00',7.79),('2026-05-13 15:00:00',7.80),('2026-05-13 18:00:00',7.78),
('2026-05-14 06:00:00',7.76),('2026-05-14 09:00:00',7.76),('2026-05-14 12:00:00',7.75),('2026-05-14 15:00:00',7.75),('2026-05-14 18:00:00',7.74),
('2026-05-15 06:00:00',8.11),('2026-05-15 09:00:00',8.36),('2026-05-15 12:00:00',9.06),('2026-05-15 15:00:00',9.96),('2026-05-15 18:00:00',10.86),
('2026-05-16 06:00:00',11.64),('2026-05-16 09:00:00',11.68)
]

# Representative station set. Danger-level values are configuration references, not claims of current official measurements.
STATIONS = {
 'mymensingh': {'name':'Mymensingh — Old Brahmaputra','district':'Mymensingh','division':'Mymensingh','river':'Old Brahmaputra','station':'Mymensingh','danger':12.05,'lat':24.747,'lon':90.420,'seed':11,'base':7.1,'wave':0.16},
 'jamalpur': {'name':'Jamalpur — Old Brahmaputra','district':'Jamalpur','division':'Mymensingh','river':'Old Brahmaputra','station':'Jamalpur','danger':16.55,'lat':24.937,'lon':89.937,'seed':12,'base':11.8,'wave':0.20},
 'tangail': {'name':'Tangail — Dhaleshwari','district':'Tangail','division':'Dhaka','river':'Dhaleshwari','station':'Tangail','danger':7.95,'lat':24.251,'lon':89.916,'seed':13,'base':5.9,'wave':0.14},
 'sylhet': {'name':'Sylhet — Surma','district':'Sylhet','division':'Sylhet','river':'Surma','station':'Sylhet','danger':10.50,'lat':24.895,'lon':91.869,'seed':14,'base':8.4,'wave':0.18},
 'sunamganj': {'name':'Sunamganj — Surma','district':'Sunamganj','division':'Sylhet','river':'Surma','station':'Sunamganj','danger':7.20,'lat':25.066,'lon':91.395,'seed':15,'base':5.8,'wave':0.13},
 'netrokona': {'name':'Netrokona — Kangsha','district':'Netrokona','division':'Mymensingh','river':'Kangsha','station':'Netrokona','danger':10.10,'lat':24.883,'lon':90.727,'seed':16,'base':7.5,'wave':0.17},
 'kurigram': {'name':'Kurigram — Dharla','district':'Kurigram','division':'Rangpur','river':'Dharla','station':'Kurigram','danger':26.50,'lat':25.805,'lon':89.636,'seed':17,'base':24.7,'wave':0.28},
 'gaibandha': {'name':'Gaibandha — Ghaghat','district':'Gaibandha','division':'Rangpur','river':'Ghaghat','station':'Gaibandha','danger':21.25,'lat':25.329,'lon':89.542,'seed':18,'base':17.4,'wave':0.21},
 'nilphamari': {'name':'Nilphamari — Teesta','district':'Nilphamari','division':'Rangpur','river':'Teesta','station':'Nilphamari','danger':21.00,'lat':25.932,'lon':88.856,'seed':19,'base':18.1,'wave':0.22},
 'sirajganj': {'name':'Sirajganj — Jamuna','district':'Sirajganj','division':'Rajshahi','river':'Jamuna','station':'Sirajganj','danger':13.35,'lat':24.453,'lon':89.700,'seed':20,'base':11.3,'wave':0.18},
 'bogura': {'name':'Bogura — Karatoya','district':'Bogura','division':'Rajshahi','river':'Karatoya','station':'Bogura','danger':16.85,'lat':24.849,'lon':89.374,'seed':21,'base':13.7,'wave':0.15},
 'rajshahi': {'name':'Rajshahi — Padma','district':'Rajshahi','division':'Rajshahi','river':'Padma','station':'Rajshahi','danger':18.50,'lat':24.374,'lon':88.604,'seed':22,'base':15.1,'wave':0.18},
 'chapainawabganj': {'name':'Chapainawabganj — Mahananda','district':'Chapainawabganj','division':'Rajshahi','river':'Mahananda','station':'Chapainawabganj','danger':20.80,'lat':24.596,'lon':88.277,'seed':23,'base':17.6,'wave':0.17},
 'faridpur': {'name':'Faridpur — Padma','district':'Faridpur','division':'Dhaka','river':'Padma','station':'Faridpur','danger':9.65,'lat':23.607,'lon':89.842,'seed':24,'base':8.0,'wave':0.13},
 'madaripur': {'name':'Madaripur — Arial Khan','district':'Madaripur','division':'Dhaka','river':'Arial Khan','station':'Madaripur','danger':6.80,'lat':23.165,'lon':90.195,'seed':25,'base':5.7,'wave':0.11},
 'barishal': {'name':'Barishal — Kirtankhola','district':'Barishal','division':'Barishal','river':'Kirtankhola','station':'Barishal','danger':2.95,'lat':22.701,'lon':90.353,'seed':26,'base':2.35,'wave':0.08},
 'khulna': {'name':'Khulna — Rupsa','district':'Khulna','division':'Khulna','river':'Rupsa','station':'Khulna','danger':2.55,'lat':22.845,'lon':89.540,'seed':27,'base':1.95,'wave':0.06},
 'jessore': {'name':'Jashore — Bhairab','district':'Jashore','division':'Khulna','river':'Bhairab','station':'Jashore','danger':4.80,'lat':23.167,'lon':89.216,'seed':28,'base':3.95,'wave':0.09},
 'chattogram': {'name':'Chattogram — Karnaphuli','district':'Chattogram','division':'Chattogram','river':'Karnaphuli','station':'Chattogram','danger':5.35,'lat':22.356,'lon':91.783,'seed':29,'base':4.10,'wave':0.12},
 'feni': {'name':'Feni — Muhuri','district':'Feni','division':'Chattogram','river':'Muhuri','station':'Feni','danger':4.35,'lat':23.015,'lon':91.396,'seed':30,'base':3.45,'wave':0.11},
}

# Official bulletin snapshot values supplied in the chat. Never labelled as live.
FFWC_BULLETIN_SNAPSHOT = {
    'mymensingh': {'current': 6.32, 'danger': 12.05, 'observed_at': '2026-09-09 09:00', 'source': 'FFWC bulletin snapshot'},
    'jamalpur': {'current': 12.14, 'danger': 16.55, 'observed_at': '2026-09-09 09:00', 'source': 'FFWC bulletin snapshot'},
}

LIVE_CACHE = {'payload': None, 'expires': 0, 'error': None, 'state': 'idle', 'last_attempt': None}
CACHE_SECONDS = int(os.environ.get('LIVE_REFRESH_SECONDS', '300'))
_cache_lock = threading.Lock(); _worker_lock = threading.Lock(); _worker_running = False

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, zone TEXT, language TEXT DEFAULT "en", whatsapp TEXT, alerts INTEGER DEFAULT 0, email_alerts INTEGER DEFAULT 1, whatsapp_alerts INTEGER DEFAULT 1)')
    # Backward-compatible columns for existing databases
    cols={r[1] for r in con.execute('PRAGMA table_info(users)').fetchall()}
    if 'email_alerts' not in cols: con.execute('ALTER TABLE users ADD COLUMN email_alerts INTEGER DEFAULT 1')
    if 'whatsapp_alerts' not in cols: con.execute('ALTER TABLE users ADD COLUMN whatsapp_alerts INTEGER DEFAULT 1')
    con.execute('CREATE TABLE IF NOT EXISTS alert_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, event_type TEXT NOT NULL, event_key TEXT NOT NULL, sent_at TEXT NOT NULL, UNIQUE(user_id,event_type,event_key))')
    con.execute('CREATE TABLE IF NOT EXISTS alert_state (user_id INTEGER PRIMARY KEY, last_risk TEXT, last_daily_date TEXT, welcome_sent INTEGER DEFAULT 0, updated_at TEXT NOT NULL)')
    con.commit(); con.close()

init_db()

# ---------- Notification engine ----------
def _email_script_url():
    return os.environ.get('FLOODGUARD_EMAIL_WEBAPP_URL', '').strip() or 'https://script.google.com/macros/s/AKfycbzZUhJCgthQPXjUbVY7DgspCln2QpANsVRlmF56ShtP0k2I9s1UkRjWy1L8prw7vx8P/exec'

def _email_configured():
    return bool(_email_script_url())

def _smtp_configured():
    return bool(os.environ.get('SMTP_HOST') and os.environ.get('SMTP_USER') and os.environ.get('SMTP_PASS') and os.environ.get('EMAIL_FROM'))

def _whatsapp_bridge_configured():
    return bool(_email_script_url())

def _send_email(to_email, subject, body):
    # Primary path: Google Apps Script -> Gmail. Optional SMTP fallback remains available.
    url=_email_script_url()
    if url:
        try:
            import requests
            r=requests.post(url, json={'action':'send_email','to':to_email,'subject':subject,'body':body}, timeout=20)
            if 200 <= r.status_code < 300:
                try:
                    out=r.json()
                    if out.get('ok'):
                        return True, 'sent via Google Apps Script'
                    return False, out.get('error','Google Apps Script rejected email')
                except Exception:
                    return True, 'sent via Google Apps Script'
            return False, f'Email bridge HTTP {r.status_code}'
        except Exception as exc:
            if not _smtp_configured():
                return False, f'Email bridge error: {exc}'
    if _smtp_configured():
        host=os.environ.get('SMTP_HOST'); port=int(os.environ.get('SMTP_PORT','587')); user=os.environ.get('SMTP_USER'); pw=os.environ.get('SMTP_PASS'); sender=os.environ.get('EMAIL_FROM')
        msg=f"From: {sender}\r\nTo: {to_email}\r\nSubject: {subject}\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n{body}"
        try:
            with smtplib.SMTP(host,port,timeout=15) as server:
                server.starttls(); server.login(user,pw); server.sendmail(sender,[to_email],msg.encode('utf-8'))
            return True, 'sent via SMTP'
        except Exception as exc:
            return False, str(exc)
    return False, 'Email provider is not configured.'

def _send_whatsapp(number, body):
    # WhatsApp is sent through the same Google Apps Script bridge.
    # The script holds the WhatsApp Cloud API credentials in Script Properties.
    url=_email_script_url()
    if not url: return False, 'WhatsApp bridge is not configured.'
    try:
        import requests
        r=requests.post(url, json={'action':'send_whatsapp','to':number,'body':body}, timeout=20)
        if 200 <= r.status_code < 300:
            try:
                out=r.json()
                return bool(out.get('ok')), out.get('error') or ('sent via Google Apps Script' if out.get('ok') else 'WhatsApp send failed')
            except Exception:
                return True, 'sent via Google Apps Script'
        return False, f'WhatsApp bridge HTTP {r.status_code}'
    except Exception as exc:
        return False, str(exc)

def _user_event_sent(user_id,event_type,event_key):
    con=db(); row=con.execute('SELECT 1 FROM alert_events WHERE user_id=? AND event_type=? AND event_key=?',(user_id,event_type,event_key)).fetchone(); con.close(); return bool(row)

def _mark_event(user_id,event_type,event_key):
    con=db(); con.execute('INSERT OR IGNORE INTO alert_events(user_id,event_type,event_key,sent_at) VALUES(?,?,?,?)',(user_id,event_type,event_key,datetime.now(timezone.utc).isoformat())); con.commit(); con.close()

def _get_alert_state(user_id):
    con=db(); row=con.execute('SELECT * FROM alert_state WHERE user_id=?',(user_id,)).fetchone(); con.close(); return row

def _set_alert_state(user_id, **fields):
    cur=_get_alert_state(user_id)
    now=datetime.now(timezone.utc).isoformat()
    last_risk=fields.get('last_risk', cur['last_risk'] if cur else None)
    last_daily_date=fields.get('last_daily_date', cur['last_daily_date'] if cur else None)
    welcome_sent=fields.get('welcome_sent', cur['welcome_sent'] if cur else 0)
    con=db(); con.execute('INSERT INTO alert_state(user_id,last_risk,last_daily_date,welcome_sent,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET last_risk=excluded.last_risk,last_daily_date=excluded.last_daily_date,welcome_sent=excluded.welcome_sent,updated_at=excluded.updated_at',(user_id,last_risk,last_daily_date,welcome_sent,now)); con.commit(); con.close()

def _message_for(z,lang,kind):
    risk=z['risk']; district=z['district']; current=z['current']; danger=z['danger']; trend=z['trend_3h_cm']; predicted=z['predicted']
    direction='rising' if trend>0.2 else ('falling' if trend<-0.2 else 'stable')
    if lang=='bn':
        if kind=='welcome': return f"FloodGuard BD\nআপনার {district} zone-এর flood alert চালু হয়েছে। বর্তমান ঝুঁকি: {risk_label_bn(risk)}।"
        if kind=='daily': return f"FloodGuard BD — দৈনিক বন্যা আপডেট\n{district}: পানির স্তর {current:.2f} মি; গত ৩ ঘণ্টায় {'বাড়ছে' if direction=='rising' else 'কমছে' if direction=='falling' else 'প্রায় স্থির'}। ঝুঁকি: {risk_label_bn(risk)}। আগামী ২৪ ঘণ্টার আনুমানিক স্তর: {predicted:.2f} মি।"
        return f"FloodGuard BD সতর্কতা\n{district}-এ ঝুঁকির স্তর {risk_label_bn(risk)} হয়েছে। বর্তমান পানি {current:.2f} মি; রেফারেন্স বিপদসীমা {danger:.2f} মি। স্থানীয় কর্তৃপক্ষের নির্দেশনা অনুসরণ করুন।"
    else:
        if kind=='welcome': return f"FloodGuard BD\nFlood alerts for your {district} zone are now enabled. Current risk: {risk}."
        if kind=='daily': return f"FloodGuard BD — Daily flood update\n{district}: water level {current:.2f} m; {direction} over the last 3 hours. Risk: {risk}. Next-24h estimate: {predicted:.2f} m."
        return f"FloodGuard BD alert\nRisk in {district} changed to {risk}. Current water level: {current:.2f} m; danger reference: {danger:.2f} m. Follow local-authority guidance."

def risk_label_bn(r): return {'NORMAL':'স্বাভাবিক','WARNING':'সতর্কতা','FLOOD':'বন্যার ঝুঁকি','SEVERE':'তীব্র ঝুঁকি'}.get(r,r)

def _dispatch_user_event(row, event_type, event_key, kind, z):
    if _user_event_sent(row['id'],event_type,event_key): return {'sent':False,'skipped':'already_sent'}
    subject=f"FloodGuard BD — {z['district']} update"
    body=_message_for(z,row['language'] or 'en',kind)
    sent=False; details=[]
    if row['email_alerts'] and row['alerts']:
        ok,detail=_send_email(row['email'],subject,body); details.append('email:'+('sent' if ok else detail)); sent=sent or ok
    if row['whatsapp_alerts'] and row['alerts'] and row['whatsapp']:
        ok,detail=_send_whatsapp(row['whatsapp'],body); details.append('whatsapp:'+('sent' if ok else detail)); sent=sent or ok
    if sent: _mark_event(row['id'],event_type,event_key)
    return {'sent':sent,'details':details}

def dispatch_alerts():
    now=datetime.now(timezone.utc); today=now.strftime('%Y-%m-%d')
    con=db(); users=con.execute('SELECT * FROM users WHERE alerts=1').fetchall(); con.close(); results=[]
    for row in users:
        try:
            z=package_station(row['zone'] if row['zone'] in STATIONS else 'mymensingh')
            state=_get_alert_state(row['id'])
            # First run after enabling alerts: welcome + initialize state.
            if not state or not state['welcome_sent']:
                r=_dispatch_user_event(row,'welcome','v1','welcome',z); results.append(r)
                if r.get('sent') or not (row['email_alerts'] or row['whatsapp_alerts']): _set_alert_state(row['id'],welcome_sent=1,last_risk=z['risk'])
            else:
                # Notify only when risk actually changes.
                if state['last_risk'] and state['last_risk'] != z['risk']:
                    r=_dispatch_user_event(row,'risk_change',f"{state['last_risk']}->{z['risk']}",'change',z); results.append(r)
                    if r.get('sent'): _set_alert_state(row['id'],last_risk=z['risk'])
                elif not state['last_risk']:
                    _set_alert_state(row['id'],last_risk=z['risk'])
            state=_get_alert_state(row['id'])
            if not state or state['last_risk'] == z['risk']:
                if not state or state['last_daily_date'] != today:
                    r=_dispatch_user_event(row,'daily',today,'daily',z); results.append(r)
                    if r.get('sent'): _set_alert_state(row['id'],last_daily_date=today,last_risk=z['risk'])
        except Exception as exc: results.append({'sent':False,'error':str(exc)})
    return results

def _alert_loop():
    while True:
        try: dispatch_alerts()
        except Exception: pass
        time.sleep(int(os.environ.get('ALERT_CHECK_SECONDS','300')))

def start_alert_loop():
    global _ALERT_THREAD_STARTED
    if _ALERT_THREAD_STARTED: return
    _ALERT_THREAD_STARTED=True
    threading.Thread(target=_alert_loop,daemon=True,name='floodguard-alerts').start()


def _live_worker():
    global _worker_running
    try:
        with _cache_lock:
            LIVE_CACHE['state']='syncing'; LIVE_CACHE['last_attempt']=datetime.now(timezone.utc).isoformat()
        payload=fetch_ffwc_current()
        with _cache_lock:
            LIVE_CACHE.update(payload=payload, expires=time.time()+CACHE_SECONDS, error=None, state='connected')
    except Exception as exc:
        with _cache_lock:
            LIVE_CACHE['error']=str(exc); LIVE_CACHE['state']='stale' if LIVE_CACHE.get('payload') else 'unavailable'
    finally:
        with _worker_lock: _worker_running=False

def trigger_live_refresh(force=False):
    global _worker_running
    with _worker_lock:
        now=time.time()
        if _worker_running or (not force and LIVE_CACHE.get('payload') and now < LIVE_CACHE.get('expires',0)):
            return False
        _worker_running=True
        threading.Thread(target=_live_worker, daemon=True).start(); return True

# Start notification worker on WSGI import so Gunicorn/Render also processes scheduled alerts.
try:
    start_alert_loop()
except Exception:
    pass

@app.before_request
def _ensure_background_live_sync():
    # Never block a page request. If the cache is stale/empty, launch one background refresh.
    trigger_live_refresh(False)

def live_snapshot():
    with _cache_lock:
        payload=LIVE_CACHE.get('payload'); state=LIVE_CACHE.get('state','idle'); err=LIVE_CACHE.get('error')
    if payload: return payload
    return {'ok':False,'source':'FFWC public feed','source_url':'https://ffwc.gov.bd/app/observed-water-level','fetched_at':None,'table_date':None,'data':{},'state':state,'error':err}

def norm(x): return ''.join(ch for ch in str(x).lower() if ch.isalnum())

def live_for_station(key):
    st=STATIONS[key]; snap=live_snapshot(); data=snap.get('data',{})
    target=(norm(st['river']),norm(st['station']))
    hit=data.get(target)
    if hit: return {**hit,'live':True}
    for (river,station),v in data.items():
        if station==norm(st['station']) or (station in norm(st['station']) or norm(st['station']) in station):
            return {**v,'live':True}
    snaprow=FFWC_BULLETIN_SNAPSHOT.get(key)
    if snaprow:
        return {**snaprow,'live':False,'snapshot':True,'source_url':'https://ffwc.gov.bd/app/daily-waterlevel-report'}
    return simulated_current(key)

def simulated_current(key):
    st=STATIONS[key]; now=datetime.now(timezone.utc); seconds=(now.hour*3600+now.minute*60+now.second)
    day_index=(now.date()-datetime(2026,1,1).date()).days
    phase=(day_index*0.39)+(seconds/86400)*2*math.pi
    rng=random.Random(st['seed'])
    trend=0.14*math.sin(phase/2.4)+0.07*math.sin(phase/5.1)
    spike=0.0
    if st['seed'] % 4 == 0: spike=0.45*math.sin(phase*1.7)
    current=max(0, st['base']+st['wave']*math.sin(phase)+trend+spike)
    return {'live':False,'simulation':True,'source':'FloodGuard simulation scenario','current':round(current,2),'danger':st['danger'],'observed_at':now.astimezone().strftime('%Y-%m-%d %H:%M:%S'),'source_url':'https://ffwc.gov.bd/app/observed-water-level'}

def make_history(key, current):
    if key=='mymensingh':
        rows=[{'time':t,'level':v,'kind':'Project observation'} for t,v in MYMENSINGH_REAL]
        rng=random.Random(91)
        start=datetime.strptime(MYMENSINGH_REAL[0][0],'%Y-%m-%d %H:%M:%S')-timedelta(hours=3*90)
        for i in range(90):
            dt=start+timedelta(hours=3*i); val=9.65-0.022*i+0.10*math.sin(i/3)+rng.uniform(-0.03,0.03)
            rows.append({'time':dt.strftime('%Y-%m-%d %H:%M:%S'),'level':round(val,2),'kind':'Historical context'})
        rows.sort(key=lambda x:x['time'])
        rows[-1]={'time':datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S'),'level':current,'kind':'Latest available observation/model state'}
        return rows
    st=STATIONS[key]; rng=random.Random(st['seed']); rows=[]; now=datetime.now().astimezone().replace(minute=0,second=0,microsecond=0)
    start=now-timedelta(hours=3*95)
    for i in range(96):
        dt=start+timedelta(hours=3*i); progress=i/95
        val=st['base'] + (current-st['base'])*progress + st['wave']*math.sin(i/6)+0.06*math.sin(i/14)+rng.uniform(-0.035,0.035)
        rows.append({'time':dt.strftime('%Y-%m-%d %H:%M:%S'),'level':round(val,2),'kind':'Recorded / scenario history'})
    rows[-1]={'time':now.strftime('%Y-%m-%d %H:%M:%S'),'level':current,'kind':'Latest state'}
    return rows

def risk_for(level,danger):
    r=level/danger if danger else 0
    if r>=1.02:return 'SEVERE'
    if r>=0.96:return 'FLOOD'
    if r>=0.86:return 'WARNING'
    return 'NORMAL'

def predict_24h(history,current,danger):
    if len(history)>=4:
        recent=[x['level'] for x in history[-5:]]; slope=(recent[-1]-recent[0])/4
    else:slope=0
    predicted=max(0,current+slope*8)
    probability=max(2,min(98,round(100/(1+math.exp(-((predicted/danger)-.86)*18)))))
    return round(predicted,2),probability,risk_for(predicted,danger),round(slope,4)

def forecast_15_days(current,slope,danger,key):
    # Stable all-zone 15-day projection; deterministic per zone and anchored to current state.
    today=datetime.now().astimezone(); out=[]; st=STATIONS[key]
    rng=random.Random(st['seed']*17)
    for day in range(1,16):
        decay=0.92**(day-1)
        cyc=0.08*math.sin((day+st['seed'])/2.2)
        event=0.04*math.sin(day/1.8+st['seed'])
        level=max(0,current + slope*8*day*decay + cyc + event)
        # Clamp into a sensible range around the danger reference.
        level=min(level, danger*1.18); level=max(level, 0.05)
        prob=max(1,min(99,round(100/(1+math.exp(-((level/danger)-.86)*18)))))
        uncertainty=round(0.05+day*0.012,2)
        out.append({'date':(today+timedelta(days=day)).strftime('%Y-%m-%d'),'level':round(level,2),'probability':prob,'risk':risk_for(level,danger),'uncertainty':uncertainty})
    return out

def package_station(key):
    st=STATIONS[key]; live=live_for_station(key); current=float(live.get('current',st['base'])); danger=float(live.get('danger',st['danger']))
    hist=make_history(key,current); pred,prob,risk,slope=predict_24h(hist,current,danger); f15=forecast_15_days(current,slope,danger,key)
    status='LIVE' if live.get('live') else ('FFWC SNAPSHOT' if live.get('snapshot') else 'SIMULATION')
    return {'id':key,'name':st['name'],'district':st['district'],'division':st['division'],'river':st['river'],'station':st['station'],'current':round(current,2),'predicted':pred,'probability':prob,'risk':risk,'danger':round(danger,2),'lat':st['lat'],'lon':st['lon'],'trend_3h_cm':round(slope*100,1),'live':bool(live.get('live')),'simulation':bool(live.get('simulation')),'snapshot':bool(live.get('snapshot')),'status':status,'source':live.get('source','FFWC'),'source_url':live.get('source_url'),'observed_at':live.get('observed_at'),'fetched_at':live_snapshot().get('fetched_at'),'forecast15':f15,'day15':f15[-1]['level'],'day15risk':f15[-1]['risk']}

def build_dashboard(key):
    if key not in STATIONS:key='mymensingh'
    z=package_station(key); hist=make_history(key,z['current'])
    pred,prob,risk,slope=predict_24h(hist,z['current'],z['danger'])
    risk_now=z['risk']
    simple=make_simple_summary(z)
    return {'station':z,'current':z['current'],'predicted':pred,'probability':prob,'risk':risk_now,'trend_per_3h':slope,'forecast15':z['forecast15'],'history':hist,'advice':advice(risk_now),'simple':simple,'live_connected':bool(z['live'])}

def advice(risk):
    return {
      'NORMAL':['Monitor official updates.','Keep phones and power banks charged.','Know the nearest safe high ground or shelter.'],
      'WARNING':['Check official and local-authority updates regularly.','Prepare water, dry food, medicines and important documents.','Move valuables and electrical items higher and plan an evacuation route.'],
      'FLOOD':['Avoid unnecessary travel near rivers and fast-moving water.','Move valuables, documents, livestock and essentials higher.','Prepare for evacuation if local authorities advise it.'],
      'SEVERE':['Follow local-authority emergency instructions immediately.','Move to higher ground or a designated shelter when instructed.','Keep essential medicines and emergency supplies with you.']
    }[risk]

def make_simple_summary(z):
    gap=z['danger']-z['current']; direction='rising' if z['trend_3h_cm']>0.2 else ('falling' if z['trend_3h_cm']<-0.2 else 'fairly steady')
    if z['risk']=='SEVERE': headline=f"Severe flood risk near {z['district']}. Water level is {direction} and needs immediate attention."
    elif z['risk']=='FLOOD': headline=f"Flood conditions are possible in {z['district']}. Water level is {direction}; keep essentials ready."
    elif z['risk']=='WARNING': headline=f"Flood risk is increasing in {z['district']}. Water level is {direction}; stay alert."
    else: headline=f"Conditions are currently calmer in {z['district']}. Water level is {direction}; keep monitoring updates."
    if gap>=0: sub=f"Current level {z['current']:.2f} m; {gap:.2f} m below the reference danger level."
    else: sub=f"Current level {z['current']:.2f} m; {abs(gap):.2f} m above the reference danger level."
    return {'headline':headline,'sub':sub}

@app.route('/')
def index():
    # Serve the root index.html directly so deployment does not depend on templates/ being uploaded.
    root_index = os.path.join(BASE, 'index.html')
    if os.path.exists(root_index):
        return send_file(root_index)
    return render_template('index.html')
@app.route('/api/zones')
def zones(): return jsonify([package_station(k) for k in STATIONS])
@app.route('/api/dashboard')
def dashboard(): return jsonify(build_dashboard(request.args.get('station','mymensingh')))
@app.route('/api/national')
def national():
    zones=[package_station(k) for k in STATIONS]; counts={r:sum(z['risk']==r for z in zones) for r in ['NORMAL','WARNING','FLOOD','SEVERE']}
    return jsonify({'zones':zones,'counts':counts,'stations':len(zones),'live_stations':sum(z['live'] for z in zones)})
@app.route('/api/live-refresh')
def live_refresh():
    started=trigger_live_refresh(force=request.args.get('force')=='1'); snap=live_snapshot()
    return jsonify({'started':started,'state':LIVE_CACHE.get('state'),'connected':bool(snap.get('ok')),'fetched_at':snap.get('fetched_at'),'table_date':snap.get('table_date')})
@app.route('/api/live-status')
def live_status():
    snap=live_snapshot(); return jsonify({'connected':bool(snap.get('ok')),'state':LIVE_CACHE.get('state'),'source':snap.get('source'),'fetched_at':snap.get('fetched_at'),'table_date':snap.get('table_date'),'last_attempt':LIVE_CACHE.get('last_attempt'),'error':LIVE_CACHE.get('error')})
@app.route('/api/analytics')
def analytics():
    zones=[package_station(k) for k in STATIONS]; rising=sorted(zones,key=lambda z:z['trend_3h_cm'],reverse=True); close=sorted(zones,key=lambda z:z['current']/z['danger'],reverse=True)
    return jsonify({'counts':{r:sum(z['risk']==r for z in zones) for r in ['NORMAL','WARNING','FLOOD','SEVERE']},'avg_level':round(statistics.mean(z['current'] for z in zones),2),'rising':rising[:6],'closest':close[:6]})

@app.get('/api/hazards/earthquakes')
def earthquakes():
    """Recent earthquake monitoring near Bangladesh using the public USGS GeoJSON feed.
    Monitoring only; no earthquake prediction is performed.
    """
    import math
    try:
        import requests
        from datetime import timedelta
        days=max(1,min(int(request.args.get('days','7')),30))
        minmag=float(request.args.get('minmagnitude','2.5'))
        end=datetime.now(timezone.utc)
        start=end-timedelta(days=days)
        url='https://earthquake.usgs.gov/fdsnws/event/1/query'
        params={'format':'geojson','starttime':start.isoformat(),'endtime':end.isoformat(),'minmagnitude':minmag,'latitude':23.685,'longitude':90.356,'maxradiuskm':900,'limit':200,'orderby':'time'}
        r=requests.get(url,params=params,timeout=12,headers={'User-Agent':'FloodGuard-BD/1.0'})
        r.raise_for_status(); data=r.json()
        def hav(lat1,lon1,lat2,lon2):
            R=6371.0; p1=math.radians(lat1); p2=math.radians(lat2); dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
            h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
            return R*2*math.atan2(math.sqrt(h),math.sqrt(max(0,1-h)))
        ev=[]
        for f in data.get('features',[]):
            p=f.get('properties') or {}; coords=(f.get('geometry') or {}).get('coordinates') or []
            if len(coords)<3: continue
            lon,lat,depth=coords[0],coords[1],coords[2]
            mag=p.get('mag')
            if lat is None or lon is None or mag is None: continue
            dist=hav(23.685,90.356,float(lat),float(lon))
            ts=p.get('time')
            try: local=datetime.fromtimestamp(ts/1000,tz=timezone.utc).astimezone().strftime('%d %b %Y, %I:%M %p')
            except Exception: local='Unknown time'
            ev.append({'id':f.get('id'),'place':p.get('place') or 'Unknown location','magnitude':float(mag),'depth_km':float(depth or 0),'distance_km':float(dist),'local_time':local,'time_ms':ts,'url':p.get('url')})
        ev.sort(key=lambda x:x.get('time_ms') or 0,reverse=True)
        return jsonify({'ok':True,'count':len(ev),'max_magnitude':max((x['magnitude'] for x in ev),default=None),'nearest_km':min((x['distance_km'] for x in ev),default=None),'center':{'lat':23.685,'lon':90.356},'source':'USGS','source_url':'https://earthquake.usgs.gov/earthquakes/feed/','events':ev})
    except Exception as e:
        return jsonify({'ok':False,'error':str(e),'source':'USGS','source_url':'https://earthquake.usgs.gov/earthquakes/feed/','events':[]}),502



# ---------- Multi-hazard data ----------
WEATHER_CACHE = {}
WEATHER_CACHE_SECONDS = 180

def _weather_cache_get(key):
    item = WEATHER_CACHE.get(key)
    if item and time.time() - item.get('ts', 0) < WEATHER_CACHE_SECONDS:
        return item.get('data')
    return None

def _weather_cache_set(key, data):
    WEATHER_CACHE[key] = {'ts': time.time(), 'data': data}
    return data

def _wmo_label(code):
    labels = {0:'Clear',1:'Mainly clear',2:'Partly cloudy',3:'Overcast',45:'Fog',48:'Depositing rime fog',
              51:'Light drizzle',53:'Drizzle',55:'Dense drizzle',56:'Freezing drizzle',57:'Freezing drizzle',
              61:'Light rain',63:'Rain',65:'Heavy rain',66:'Freezing rain',67:'Heavy freezing rain',
              71:'Light snow',73:'Snow',75:'Heavy snow',77:'Snow grains',80:'Rain showers',81:'Rain showers',
              82:'Heavy rain showers',85:'Snow showers',86:'Heavy snow showers',95:'Thunderstorm',96:'Thunderstorm with hail',99:'Thunderstorm with heavy hail'}
    return labels.get(int(code),'Weather') if code is not None else 'Weather unavailable'

def _weather_hazard_score(current, daily, hourly):
    max_wind = max(daily.get('wind_gusts_10m_max') or [0]) if daily.get('wind_gusts_10m_max') else 0
    max_rain = max(daily.get('precipitation_probability_max') or [0]) if daily.get('precipitation_probability_max') else 0
    max_temp = max(daily.get('temperature_2m_max') or [0]) if daily.get('temperature_2m_max') else 0
    thunder = sum(1 for c in (hourly.get('weather_code') or []) if c is not None and int(c) >= 95)
    rain_sum = max(daily.get('precipitation_sum') or [0]) if daily.get('precipitation_sum') else 0
    severe = []
    if max_wind >= 55: severe.append(('Wind alert','Strong gust potential'))
    elif max_wind >= 40: severe.append(('Wind watch','Gusty conditions possible'))
    if max_rain >= 80 or rain_sum >= 50: severe.append(('Heavy rain watch','High rainfall potential'))
    elif max_rain >= 60 or rain_sum >= 25: severe.append(('Rain watch','Rainfall potential elevated'))
    if thunder >= 1: severe.append(('Thunderstorm watch',f'{thunder} forecast thunderstorm hour(s) in the next 5 days'))
    if max_temp >= 38: severe.append(('Heat watch','High temperature outlook'))
    elif max_temp >= 36: severe.append(('Heat watch','Hot conditions possible'))
    return {'wind_gust_max_kmh':max_wind,'rain_probability_max_pct':max_rain,'rain_sum_max_mm':rain_sum,'thunderstorm_hours':thunder,'max_temp_c':max_temp,'flags':severe}

@app.get('/api/hazards/weather')
def weather():
    try:
        zone_key = request.args.get('station','mymensingh')
        z = STATIONS.get(zone_key, STATIONS['mymensingh'])
        lat, lon = z['lat'], z['lon']
        cache_key = f'{zone_key}:{round(float(lat),3)}:{round(float(lon),3)}'
        cached = _weather_cache_get(cache_key)
        if cached: return jsonify(cached)
        import requests
        params = {
            'latitude':lat,'longitude':lon,'current':'temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,pressure_msl',
            'hourly':'temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_gusts_10m',
            'daily':'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max',
            'forecast_days':5,'timezone':'Asia/Dhaka'
        }
        r=requests.get('https://api.open-meteo.com/v1/forecast',params=params,timeout=8,headers={'User-Agent':'FloodGuard-BD/1.0'}); r.raise_for_status(); d=r.json()
        out={'ok':True,'zone':z['district'],'coordinates':{'lat':lat,'lon':lon},'current':d.get('current',{}),'daily':d.get('daily',{}),'hourly':d.get('hourly',{}),'hazard':_weather_hazard_score(d.get('current',{}),d.get('daily',{}),d.get('hourly',{})),'source':'Open-Meteo'}
        out['current']['label']=_wmo_label(out['current'].get('weather_code'))
        return jsonify(_weather_cache_set(cache_key,out))
    except Exception as e:
        return jsonify({'ok':False,'error':str(e),'source':'Open-Meteo'}),502

@app.get('/api/hazards/cyclones')
def cyclones():
    """In-site tropical-cyclone watch using GDACS API. Does not predict cyclones."""
    try:
        import requests, math, xml.etree.ElementTree as ET
        from datetime import timedelta
        end=datetime.now(timezone.utc); start=end-timedelta(days=14)
        url='https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH'
        params={'eventlist':'TC','fromdate':start.strftime('%Y-%m-%d'),'todate':end.strftime('%Y-%m-%d'),'alertlevel':'green;orange;red'}
        r=requests.get(url,params=params,timeout=10,headers={'User-Agent':'FloodGuard-BD/1.0'}); r.raise_for_status()
        raw=r.text
        events=[]
        try:
            payload=r.json()
            if isinstance(payload,dict):
                raw_items=payload.get('features') or payload.get('events') or payload.get('data') or []
                for it in raw_items:
                    pr=it.get('properties',it) if isinstance(it,dict) else {}
                    geom=(it.get('geometry') or {}).get('coordinates') if isinstance(it,dict) else None
                    ev={'name':pr.get('eventname') or pr.get('name') or pr.get('eventName') or 'Tropical cyclone', 'alert':str(pr.get('alertlevel') or pr.get('alertLevel') or 'information').upper(), 'lat':None,'lon':None,'wind_kmh':pr.get('maxwind') or pr.get('maxWind') or pr.get('windSpeed')}
                    if geom and len(geom)>=2: ev.update({'lon':float(geom[0]),'lat':float(geom[1])})
                    if ev['lat'] is not None and ev['lon'] is not None: events.append(ev)
        except Exception:
            pass
        # A resilient XML fallback for common GDACS feed structures.
        if not events:
            try:
                root=ET.fromstring(raw)
                for item in root.iter():
                    tag=item.tag.lower()
                    if tag.endswith('item'):
                        txt={c.tag.lower().split('}')[-1]: (c.text or '').strip() for c in item}
                        name=txt.get('eventname') or txt.get('title') or txt.get('name')
                        if name: events.append({'name':name,'alert':(txt.get('alertlevel') or 'information').upper(),'lat':None,'lon':None,'wind_kmh':None})
            except Exception:
                pass
        # Keep the UI useful even when GDACS returns no structured event records.
        events=events[:10]
        return jsonify({'ok':True,'active_count':len(events),'events':events,'source':'GDACS'})
    except Exception as e:
        return jsonify({'ok':False,'error':str(e),'source':'GDACS','active_count':0,'events':[]}),502

@app.route('/api/report')
def report():
    zones=[package_station(k) for k in STATIONS]; now=datetime.now().astimezone().strftime('%d %b %Y, %I:%M:%S %p')
    lines=['FLOODGUARD BD — FLOOD SITUATION REPORT','',f'Generated: {now}','Data states are labelled as Live, FFWC Snapshot, or Simulation.','']
    for z in zones: lines.append(f"{z['name']} | {z['current']:.2f} m | ref {z['danger']:.2f} m | {z['risk']} | {z['status']}")
    return Response('\n'.join(lines),mimetype='text/plain',headers={'Content-Disposition':'attachment; filename="FloodGuard_BD_Situation_Report.txt"'})

# --- Auth + WhatsApp notification settings. Actual delivery requires provider credentials. ---
@app.post('/api/auth/register')
def register():
    data=request.get_json(force=True); email=(data.get('email') or '').strip().lower(); password=data.get('password') or ''
    if not email or len(password)<6:return jsonify({'ok':False,'error':'Use a valid email and a password of at least 6 characters.'}),400
    try:
        con=db(); cur=con.execute('INSERT INTO users(email,password_hash,zone,language,whatsapp,alerts,email_alerts,whatsapp_alerts) VALUES(?,?,?,?,?,0,1,1)',(email,generate_password_hash(password),'mymensingh','en','')); con.commit(); uid=cur.lastrowid; con.close(); session['uid']=uid
        return jsonify({'ok':True,'user':{'email':email,'zone':'mymensingh','language':'en','whatsapp':'','alerts':False}})
    except sqlite3.IntegrityError:return jsonify({'ok':False,'error':'Account already exists.'}),409
@app.post('/api/auth/login')
def login():
    data=request.get_json(force=True); email=(data.get('email') or '').strip().lower(); password=data.get('password') or ''
    con=db(); row=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); con.close()
    if not row or not check_password_hash(row['password_hash'],password):return jsonify({'ok':False,'error':'Invalid email or password.'}),401
    session['uid']=row['id']; return jsonify({'ok':True,'user':dict_user(row)})
def dict_user(row): return {'email':row['email'],'zone':row['zone'],'language':row['language'],'whatsapp':row['whatsapp'],'alerts':bool(row['alerts']),'email_alerts':bool(row['email_alerts']),'whatsapp_alerts':bool(row['whatsapp_alerts'])}
@app.post('/api/auth/logout')
def logout(): session.clear(); return jsonify({'ok':True})
@app.get('/api/auth/me')
def me():
    uid=session.get('uid');
    if not uid:return jsonify({'logged_in':False})
    con=db(); row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); con.close()
    return jsonify({'logged_in':bool(row),'user':dict_user(row) if row else None})
@app.post('/api/profile')
def profile():
    uid=session.get('uid')
    if not uid:
        return jsonify({'ok':False,'error':'Login required.'}),401
    data=request.get_json(force=True)
    zone=data.get('zone') if data.get('zone') in STATIONS else 'mymensingh'
    lang=data.get('language') if data.get('language') in {'en','bn'} else 'en'
    wa=(data.get('whatsapp') or '').strip()
    alerts=1 if data.get('alerts') else 0
    email_alerts=1 if data.get('email_alerts',True) else 0
    whatsapp_alerts=1 if data.get('whatsapp_alerts',True) else 0

    con=db()
    old=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not old:
        con.close()
        return jsonify({'ok':False,'error':'Account not found.'}),404
    old_zone=old['zone'] if old['zone'] in STATIONS else 'mymensingh'
    old_alerts=bool(old['alerts'])
    con.execute('UPDATE users SET zone=?,language=?,whatsapp=?,alerts=?,email_alerts=?,whatsapp_alerts=? WHERE id=?',(zone,lang,wa,alerts,email_alerts,whatsapp_alerts,uid))
    row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    con.commit(); con.close()

    # Immediate notification events: never wait for the background polling loop.
    immediate=[]
    z=package_station(zone)
    if alerts and not old_alerts:
        # Enabling alerts is a new subscription: send welcome immediately.
        _set_alert_state(uid,last_risk=z['risk'],welcome_sent=0,last_daily_date=None)
        immediate.append(_dispatch_user_event(row,'welcome',f"enable-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}",'welcome',z))
        if immediate[-1].get('sent'):
            _set_alert_state(uid,last_risk=z['risk'],welcome_sent=1)
    elif alerts and old_alerts and old_zone != zone:
        # Zone change while already subscribed: send one zone-update mail immediately.
        immediate.append(_dispatch_user_event(row,'zone_change',f'{old_zone}->{zone}','change',z))
        _set_alert_state(uid,last_risk=z['risk'])

    return jsonify({'ok':True,'user':dict_user(row),'email_configured':_email_configured(),'whatsapp_configured':_whatsapp_bridge_configured(),'immediate':immediate})

@app.post('/api/alerts/test-email')
def test_email():
    uid=session.get('uid')
    if not uid:return jsonify({'ok':False,'error':'Login required.'}),401
    con=db(); row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); con.close()
    if not row:return jsonify({'ok':False,'error':'Account not found.'}),404
    z=package_station(row['zone'] if row['zone'] in STATIONS else 'mymensingh')
    body=_message_for(z,row['language'] or 'en','daily')
    ok,detail=_send_email(row['email'],'FloodGuard BD — Test email',body)
    return jsonify({'ok':ok,'detail':detail})

@app.post('/api/alerts/enable')
def enable_alerts():
    uid=session.get('uid')
    if not uid:return jsonify({'ok':False,'error':'Login required.'}),401
    con=db(); row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); con.close()
    if not row:return jsonify({'ok':False,'error':'Account not found.'}),404
    z=package_station(row['zone'] if row['zone'] in STATIONS else 'mymensingh')
    _set_alert_state(uid,last_risk=z['risk'],welcome_sent=0,last_daily_date=None)
    fresh=con=None
    con=db(); row=con.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone(); con.close()
    result=_dispatch_user_event(row,'welcome',f"enable-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}",'welcome',z)
    if result.get('sent'):
        _set_alert_state(uid,last_risk=z['risk'],welcome_sent=1)
    return jsonify({'ok':bool(result.get('sent')),'message':'Welcome alert sent immediately.' if result.get('sent') else 'Could not send welcome alert.','details':result})

@app.post('/api/alerts/dispatch')
def alerts_dispatch():
    # Manual/cron-safe trigger for notification processing.
    return jsonify({'ok':True,'results':dispatch_alerts()})


if __name__=='__main__':
    trigger_live_refresh(False)
    start_alert_loop()
    port=int(os.environ.get('PORT','5081')); app.run(host='0.0.0.0',port=port,debug=False)
