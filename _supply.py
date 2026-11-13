# -*- coding: utf-8 -*-
import sys; sys.stdout.reconfigure(encoding="utf-8")
from pykrx import stock
# 투자자별 순매수 (외국인/기관) - 종목별, 기간
try:
    df = stock.get_market_trading_value_by_date("20260601", "20260612", "005930")
    print("=== 종목 투자자별 거래대금(삼성전자) ===")
    print(df.tail(3).to_string())
    print("컬럼:", list(df.columns))
except Exception as e:
    print("ERR1:", e)
try:
    # 특정일 외국인 순매수 상위
    df2 = stock.get_market_net_purchases_of_equities("20260612","20260612","KOSPI","외국인")
    print("\n=== 외국인 순매수 상위(KOSPI 6/12) ===")
    print(df2.head(3).to_string())
except Exception as e:
    print("ERR2:", e)
