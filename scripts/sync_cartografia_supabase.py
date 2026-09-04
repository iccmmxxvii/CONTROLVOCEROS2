from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from supabase import create_client

CAT=ROOT/'data'/'cartografia'/'secciones_catalogo.csv'


def main():
    url=os.getenv('SUPABASE_URL'); key=os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    if not url or not key:
        raise SystemExit('Define SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en variables de entorno.')
    client=create_client(url,key)
    df=pd.read_csv(CAT)
    munis=client.table('municipios').select('id,nombre_normalizado').execute().data or []
    muni_ids={m['nombre_normalizado']:m['id'] for m in munis}
    dls=client.table('distritos_locales').select('id,numero').execute().data or []
    dl_ids={int(x['numero']):x['id'] for x in dls}
    dfs=client.table('distritos_federales').select('id,numero').execute().data or []
    df_ids={int(x['numero']):x['id'] for x in dfs}
    payload=[]
    for _,r in df.iterrows():
        payload.append({
            'entidad':25,'numero':int(r['seccion']),'municipio_id':muni_ids.get(str(r['municipio']).upper()),
            'distrito_local_id':dl_ids.get(int(r['distrito_local'])),'distrito_federal_id':df_ids.get(int(r['distrito_federal'])),
            'tipo_seccion':r['tipo_seccion'],'centroide_lat':float(r['centroide_lat']),'centroide_lon':float(r['centroide_lon']),
            'fuente_catalogo':'Cartografía Sinaloa precargada V2','fuente_territorial':'SECCION→CARTOGRAFIA_SINALOA','estado_catalogo':'CARTOGRAFIA_PRECARGADA','activo':True,
        })
    for i in range(0,len(payload),300):
        client.table('secciones_electorales').upsert(payload[i:i+300],on_conflict='entidad,numero').execute()
        print(f"Sincronizadas {min(i+300,len(payload))}/{len(payload)}")

if __name__=='__main__': main()
