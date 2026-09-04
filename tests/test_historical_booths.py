from io import BytesIO
import pandas as pd

from core.historical_booths import read_iees_historical_excel
from core.casillas import normalize_booth_catalog


def test_historical_excel_header_detection():
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as w:
        pd.DataFrame([
            ["REPORTE HISTORICO",None,None,None],
            ["SECCION","MUNICIPIO","CASILLA","LISTA NOMINAL"],
            [316,"AHOME","Básica 1",650],
            [316,"AHOME","Contigua 1",649],
        ]).to_excel(w,index=False,header=False,sheet_name="Datos")
    raw=read_iees_historical_excel(buf.getvalue())
    booths,_=normalize_booth_catalog(raw)
    assert len(booths)==2
    assert set(booths["tipo_casilla"])=={"B","C1"}
