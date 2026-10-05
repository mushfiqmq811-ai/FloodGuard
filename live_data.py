"""Authentic live BWDB chart + Copernicus GloFAS ingestion.

No synthetic fallback exists in this module.
"""
from datetime import datetime, timezone
import os, threading, time, requests
from real_data import fetch_bwdb_station_catalog, choose_station, fetch_bwdb_chart, EWDS_API_URL, GLOFAS_HISTORICAL_DATASET

CACHE={}; LOCK=threading.Lock()
CACHE_TTL=int(os.getenv('LIVE_REFRESH_SECONDS','300'))


def _station_source(station):
    catalog=fetch_bwdb_station_catalog()
    match=choose_station(catalog,station['station'],station['river'],station['lat'],station['lon'])
    if not match: raise RuntimeError(f'No defensible BWDB station match for {station["name"]}')
    rows=fetch_bwdb_chart(match['chart_url'])
    if not rows: raise RuntimeError(f'No observations returned by BWDB chart for {station["name"]}')
    return match, rows


def fetch_ffwc_current(stations=None):
    stations=stations or {}
    data={}; failures=[]
    for key,st in stations.items():
        try:
            match,rows=_station_source(st)
            latest=rows[-1]
            previous=rows[-2] if len(rows)>1 else None
            data[(norm(st['river']),norm(st['station']))]={
                'river':st['river'],'station':st['station'],'current':latest['water_level_m'],
                'observed_at':latest['observed_at'],'source':'BWDB Hydrology chart observation',
                'source_url':match['chart_url'],'live':True,'snapshot':False,'simulation':False,
                'danger':st.get('danger'),
                'previous_level':previous['water_level_m'] if previous else None,
                'bwdb_station_id':match['station_id'],'bwdb_match_score':match['match_score'],'history':[{'time':r['observed_at'],'level':r['water_level_m'],'kind':'BWDB observed'} for r in rows]
            }
        except Exception as exc:
            failures.append({'station':key,'error':str(exc)})
    if not data:
        raise RuntimeError('No authentic BWDB chart observations could be fetched: '+str(failures[:3]))
    return {'ok':True,'source':'BWDB Hydrology chart observations','source_url':'https://www.hydrology.bwdb.gov.bd/','fetched_at':datetime.now(timezone.utc).isoformat(),'data':data,'failures':failures}


def norm(x):
    import re
    return ''.join(ch for ch in str(x).lower() if ch.isalnum())


def fetch_glofas_forecast(station):
    """Fetch live GloFAS forecast through the current EWDS API using cdsapi.
    Returns an authentic source result; never fabricates discharge values.
    """
    key=os.getenv('CDS_API_KEY','').strip()
    if not key: raise RuntimeError('CDS_API_KEY is not configured')
    try:
        import cdsapi
    except ImportError as exc: raise RuntimeError('cdsapi is required') from exc
    client=cdsapi.Client(url=EWDS_API_URL,key=key,quiet=True)
    # The current EWDS download form exposes 24-hourly lead times through 720 h.
    target=os.path.join('/tmp',f"glofas_{station['id']}_{int(time.time())}.grib")
    req={
      'system_version':['operational'],
      'hydrological_model':['lisflood'],
      'product_type':['control_forecast'],
      'variable':['river_discharge_in_the_last_24_hours'],
      'leadtime_hour':[str(h) for h in range(24,721,24)],
      'data_format':'grib',
      'geographical_area':[station['lat']+0.05,station['lon']-0.05,station['lat']-0.05,station['lon']+0.05]
    }
    client.retrieve('cems-glofas-forecast',req,target)
    if not os.path.exists(target) or os.path.getsize(target)==0: raise RuntimeError('GloFAS returned no data file')
    return {'ok':True,'source':'Copernicus GloFAS forecast','source_url':EWDS_API_URL,'file':target,'station':station['id']}
