import re, json
from datetime import datetime, timezone
import requests

URLS = [
    'https://api.ffwc.gov.bd/?format=json',
    'https://ffwc.gov.bd/app/observed-water-level',
]
TIMEOUT = 6

def norm(x): return ''.join(ch for ch in str(x).lower() if ch.isalnum())

def parse_json_payload(obj):
    rows=[]
    def walk(x):
        if isinstance(x, dict):
            keys={norm(k):k for k in x.keys()}
            # Flexible station record detection.
            river=next((x[k] for nk,k in keys.items() if nk in {'river','rivername','river_name','rivernameenglish'}),None)
            station=next((x[k] for nk,k in keys.items() if nk in {'station','stationname','station_name','location'}),None)
            if river and station:
                nums=[]
                for nk,k in keys.items():
                    v=x[k]
                    if isinstance(v,(int,float)): nums.append(float(v))
                    elif isinstance(v,str):
                        m=re.fullmatch(r'\s*-?\d+(?:\.\d+)?\s*',v.replace(',',''))
                        if m: nums.append(float(v.replace(',','')))
                danger=None; current=None
                for nk,k in keys.items():
                    if any(s in nk for s in ['dangerlevel','danger_level','dl']):
                        try: danger=float(x[k])
                        except: pass
                    if any(s in nk for s in ['waterlevel','observedlevel','currentlevel','level','wl']):
                        try: current=float(x[k])
                        except: pass
                if danger is None and nums: danger=nums[0]
                if current is None and nums: current=nums[-1]
                if danger is not None and current is not None and -100<current<100 and 0<danger<100:
                    rows.append({'river':str(river),'station':str(station),'danger':danger,'current':current,'observed_at':str(x.get('datetime') or x.get('date') or x.get('time') or '')})
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(obj)
    return rows

def parse_html(text):
    rows=[]; text=re.sub(r'<script.*?</script>|<style.*?</style>',' ',text,flags=re.S|re.I)
    for raw in re.findall(r'<tr[^>]*>(.*?)</tr>',text,flags=re.S|re.I):
        cells=[re.sub(r'\s+',' ',re.sub('<.*?>',' ',c)).strip() for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',raw,flags=re.S|re.I)]
        cells=[c for c in cells if c]
        if len(cells)<4: continue
        nums=[]
        for c in cells[2:]:
            try: nums.append(float(c.replace(',',''))) 
            except: pass
        if len(nums)>=2:
            rows.append({'river':cells[0],'station':cells[1],'danger':nums[0],'current':nums[-1],'observed_at':''})
    return rows

def fetch_ffwc_current():
    errors=[]
    for url in URLS:
        try:
            r=requests.get(url,timeout=TIMEOUT,headers={'User-Agent':'FloodGuardBD/4.0'}); r.raise_for_status()
            ctype=r.headers.get('content-type','').lower(); rows=[]
            if 'json' in ctype or url.startswith('https://api.'):
                try: rows=parse_json_payload(r.json())
                except Exception: rows=[]
            if not rows: rows=parse_html(r.text)
            if rows:
                data={(norm(x['river']),norm(x['station'])): {**x,'source':'FFWC observed data','source_url':url} for x in rows}
                return {'ok':True,'source':'FFWC','source_url':url,'table_date':None,'fetched_at':datetime.now(timezone.utc).isoformat(),'data':data}
            errors.append(f'{url}: no usable station records')
        except Exception as exc: errors.append(f'{url}: {exc}')
    raise RuntimeError('FFWC public source unavailable: ' + ' | '.join(errors[-2:]))
