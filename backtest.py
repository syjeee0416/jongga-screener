# -*- coding: utf-8 -*-
"""
종가 매매 전략 백테스트.
가정: 신호 발생일(T) 종가에 매수 → 다음날(T+1) 시초가에 매도 (종가베팅 정석 청산).

사용법:
    python backtest.py             # 기본: 유동성 상위 200종목, 최근 3년
    python backtest.py 300 2022-01-01

주의(정직하게):
 - 현재 상장 종목만 사용 → 상장폐지 종목 누락(생존편향). 실제보다 결과가 낙관적일 수 있음.
 - 슬리피지/세금/수수료 미반영. 실거래 시 매매당 약 -0.2~-0.4%p 차감해서 보세요.
 - 과거 성과가 미래를 보장하지 않습니다.
"""
import os
import sys
import datetime as dt
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

import data
import strategy
import config as C


def build_universe(limit):
    """현재 스냅샷에서 유동성·시총 적격 종목 상위 limit개."""
    snap = data.get_universe_snapshot()
    snap = snap[snap.apply(lambda r: strategy.is_tradeable(r["name"], r["code"]), axis=1)]
    snap = snap[(snap["marcap"] >= C.MIN_MARCAP) & (snap["marcap"] <= C.MAX_MARCAP)]
    snap = snap.sort_values("amount", ascending=False).head(limit)
    return list(zip(snap["code"], snap["name"]))


def signals_for_stock(df):
    """일봉 DataFrame → 신호 마스크 + 다음날 시초가 수익률 시리즈."""
    df = df.rename(columns=str.title)
    if not {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns):
        return None
    o, h, l, c, v = df["Open"], df["High"], df["Low"], df["Close"], df["Volume"]

    rng = (h - l).replace(0, np.nan)
    close_pos = (c - l) / rng
    change = c.pct_change() * 100
    ma5 = c.rolling(C.MA_SHORT).mean()
    ma20 = c.rolling(C.MA_LONG).mean()
    vol_ma = v.rolling(C.VOL_MA_WINDOW).mean().shift(1)
    vol_ratio = v / vol_ma
    amount = c * v  # 거래대금 근사
    high_n = h.rolling(C.HIGH_LOOKBACK).max().shift(1)

    sig = (
        (c > o) &                                   # 양봉
        (close_pos >= C.MIN_CLOSE_POSITION) &       # 고점 마감
        (vol_ratio >= C.MIN_VOL_RATIO) &            # 거래량 급증
        (change >= C.MIN_CHANGE) & (change <= C.MAX_CHANGE) &
        (amount >= C.MIN_AMOUNT) &
        (c >= ma5)                                  # 5일선 위
    )
    # 다음날 시초가 매도 수익률(%)
    next_open = o.shift(-1)
    ret = (next_open / c - 1) * 100
    return sig, ret, close_pos, vol_ratio


def run_backtest(limit=200, start="2023-01-01", progress=None):
    """백테스트 핵심 계산 (웹/CLI 공용). return dict 또는 None(신호없음)."""
    universe = build_universe(limit)
    all_rets = []
    per_trade = []
    total = len(universe)
    for done, (code, name) in enumerate(universe, 1):
        df = data.get_history_full(code, start=start)
        if progress:
            progress(done, total)
        if df is None or len(df) < C.MA_LONG + 5:
            continue
        res = signals_for_stock(df)
        if res is None:
            continue
        sig, ret, _, _ = res
        valid = sig & ret.notna()
        r = ret[valid]
        all_rets.extend(r.tolist())
        for d, val in r.items():
            per_trade.append((d, code, name, val))

    if not all_rets:
        return None

    a = np.array(all_rets)
    pt = pd.DataFrame(per_trade, columns=["date", "code", "name", "ret"])
    pt["year"] = pd.to_datetime(pt["date"]).dt.year
    return {
        "universe_size": len(universe), "start": start,
        "rets": a, "per_trade": pt,
        "n": len(a), "win_rate": float((a > 0).mean() * 100),
        "mean": float(a.mean()), "median": float(np.median(a)),
        "std": float(a.std()), "max": float(a.max()), "min": float(a.min()),
    }


def run(limit=200, start="2023-01-01"):
    print("=" * 64)
    print(f"  종가 매매 백테스트  (유동성 상위 {limit}종목, {start}~)")
    print("=" * 64)
    print("데이터 수집/분석 중...\n")
    bt = run_backtest(limit, start)
    if bt is None:
        print("신호 없음. 조건을 완화해 보세요(config.py).")
        return
    a = bt["rets"]
    print("\n" + "=" * 64)
    print("  결과: 종가 매수 → 다음날 시초가 매도")
    print("=" * 64)
    print(f"  총 매매 횟수 : {len(a):,}")
    print(f"  승률         : {(a > 0).mean()*100:.1f}%")
    print(f"  평균 수익률  : {a.mean():+.2f}%   (중앙값 {np.median(a):+.2f}%)")
    print(f"  표준편차     : {a.std():.2f}%")
    print(f"  최고 / 최저  : {a.max():+.1f}% / {a.min():+.1f}%")
    print(f"  기대값(평균) : 매매당 {a.mean():+.2f}%  ※ 수수료·세금 약 -0.3%p 별도 차감")

    # 수익 구간 분포
    bins = [(-100, -3), (-3, 0), (0, 3), (3, 10), (10, 100)]
    print("\n  수익률 분포:")
    for lo, hi in bins:
        cnt = ((a >= lo) & (a < hi)).sum()
        print(f"    {lo:+4d}% ~ {hi:+4d}% : {cnt:5d}  ({cnt/len(a)*100:4.1f}%)")

    # 연도별
    pt = bt["per_trade"]
    print("\n  연도별 평균 수익률 / 매매수 / 승률:")
    for y, g in pt.groupby("year"):
        print(f"    {y}: {g['ret'].mean():+.2f}%   n={len(g):5d}   승률 {(g['ret']>0).mean()*100:.0f}%")

    print("\n" + "-" * 64)
    print("해석 가이드:")
    print(" - 평균 수익률이 수수료·세금(약 0.3%p)보다 확실히 높고 승률 50%+ 이면 엣지 가능성.")
    print(" - 0 근처거나 마이너스면 이 조건으론 수익화 어려움 → config.py 조건 조정 후 재검증.")
    print(" - 생존편향·슬리피지 미반영이라 실제는 더 보수적으로 보세요.")
    print("-" * 64)

    # CSV 저장
    out = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(out, exist_ok=True)
    fp = os.path.join(out, f"backtest_{dt.date.today():%Y%m%d}.csv")
    pt.sort_values("date").to_csv(fp, index=False, encoding="utf-8-sig")
    print(f"\n매매 내역 저장: {fp}")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    st = sys.argv[2] if len(sys.argv) > 2 else "2023-01-01"
    run(lim, st)
