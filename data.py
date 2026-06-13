# -*- coding: utf-8 -*-
"""
데이터 레이어. 전부 무료 소스(FinanceDataReader), 인증 불필요.
 - get_universe_snapshot(): 전 종목 당일 스냅샷(거래대금·등락률·시총 포함)
 - get_history(code): 종목별 과거 일봉 (로컬 캐시)
 - get_index_change(): 코스피/코스닥 지수 당일 등락률 (시장 필터용)
"""
import os
import datetime as dt
import pandas as pd
import FinanceDataReader as fdr

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def get_universe_snapshot():
    """KRX 전 종목 당일 스냅샷. 컬럼 일부를 한글로 정규화해서 반환."""
    df = fdr.StockListing("KRX")
    df = df.rename(columns={
        "Code": "code", "Name": "name", "Market": "market",
        "Close": "close", "Open": "open", "High": "high", "Low": "low",
        "Volume": "volume", "Amount": "amount", "Marcap": "marcap",
        "ChagesRatio": "change_pct", "Stocks": "shares",
    })
    keep = ["code", "name", "market", "close", "open", "high", "low",
            "volume", "amount", "marcap", "change_pct"]
    df = df[[c for c in keep if c in df.columns]].copy()
    # 숫자형 보정
    for c in ["close", "open", "high", "low", "volume", "amount", "marcap", "change_pct"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["close"]).reset_index(drop=True)


def get_history(code, days=150, use_cache=True):
    """종목 과거 일봉. 같은 날 재실행 시 캐시 사용."""
    today = dt.date.today().isoformat()
    cache_file = os.path.join(CACHE_DIR, f"{code}_{today}.csv")
    if use_cache and os.path.exists(cache_file):
        try:
            return pd.read_csv(cache_file, index_col=0, parse_dates=True)
        except Exception:
            pass
    start = (dt.date.today() - dt.timedelta(days=days * 2)).isoformat()
    try:
        df = fdr.DataReader(code, start)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = df.tail(days)
    if use_cache:
        try:
            df.to_csv(cache_file)
        except Exception:
            pass
    return df


def get_history_full(code, start="2019-01-01"):
    """백테스트용 장기 일봉 (캐시 안 함)."""
    try:
        df = fdr.DataReader(code, start)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def get_index_change():
    """코스피(KS11), 코스닥(KQ11) 당일 등락률(%). 실패 시 None."""
    out = {}
    for name, sym in [("KOSPI", "KS11"), ("KOSDAQ", "KQ11")]:
        try:
            d = fdr.DataReader(sym, (dt.date.today() - dt.timedelta(days=10)).isoformat())
            last = d.iloc[-1]
            if "Change" in d.columns:
                out[name] = round(float(last["Change"]) * 100, 2)
            else:
                prev = d.iloc[-2]["Close"]
                out[name] = round((last["Close"] / prev - 1) * 100, 2)
        except Exception:
            out[name] = None
    return out
