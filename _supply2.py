# -*- coding: utf-8 -*-
import sys; sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd, requests
# 네이버 외국인/기관 일별 순매매 (frgn 페이지)
code="005930"
url=f"https://finance.naver.com/item/frgn.naver?code={code}&page=1"
hdr={"User-Agent":"Mozilla/5.0"}
try:
    r=requests.get(url,headers=hdr,timeout=10)
    print("status:",r.status_code, "len:",len(r.text))
    tables=pd.read_html(r.text, encoding="euc-kr")
    print("표 개수:",len(tables))
    for i,t in enumerate(tables):
        if t.shape[0]>3 and t.shape[1]>=6:
            print(f"--- table {i} shape={t.shape} ---")
            print(t.head(4).to_string())
except Exception as e:
    print("ERR:",repr(e))
