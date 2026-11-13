# -*- coding: utf-8 -*-
"""
정직한 검증: "이 전략이 비용 빼고도 실제로 돈이 되는가?"
 - 실거래 비용(수수료·세금·슬리피지) 반영
 - 아웃오브샘플: 과거(IS)로 보고 → 최근 1년(OOS)에서 진짜 성과 확인
 - 시장 레짐 필터(지수 20일선 위에서만 매매) 효과 비교

사용법: python validate.py [종목수] [시작일] [OOS시작일]
예시:   python validate.py 150 2022-01-01 2025-06-01
"""
import os, sys
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))
import data, config as C


def build_universe_with_market(limit):
    snap = data.get_universe_snapshot()
    import strategy
    snap = snap[snap.apply(lambda r: strategy.is_tradeable(r["name"], r["code"]), axis=1)]
    snap = snap[(snap["marcap"] >= C.MIN_MARCAP) & (snap["marcap"] <= C.MAX_MARCAP)]
    snap = snap.sort_values("amount", ascending=False).head(limit)
    return list(zip(snap["code"], snap["name"], snap["market"]))


def regime_series(symbol, start):
    """지수 일별 상승추세 여부(종가>20일선) → {Timestamp: bool}."""
    try:
        d = data.get_history_full(symbol, start=start)
        if d is None or d.empty:
            return {}
        c = d["Close"]
        up = c > c.rolling(20).mean()
        return up.to_dict()
    except Exception:
        return {}


def signals(df):
    df = df.rename(columns=str.title)
    if not {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns):
        return None
    o, h, l, c, v = df["Open"], df["High"], df["Low"], df["Close"], df["Volume"]
    rng = (h - l).replace(0, np.nan)
    close_pos = (c - l) / rng
    change = c.pct_change() * 100
    ma5 = c.rolling(C.MA_SHORT).mean()
    vol_ma = v.rolling(C.VOL_MA_WINDOW).mean().shift(1)
    vol_ratio = v / vol_ma
    amount = c * v
    sig = ((c > o) & (close_pos >= C.MIN_CLOSE_POSITION) & (vol_ratio >= C.MIN_VOL_RATIO) &
           (change >= C.MIN_CHANGE) & (change <= C.MAX_CHANGE) &
           (amount >= C.MIN_AMOUNT) & (c >= ma5))
    ret = (o.shift(-1) / c - 1) * 100      # 다음날 시초가 매도(총수익)
    return sig, ret


def stats(a):
    if len(a) == 0:
        return None
    return dict(n=len(a), win=float((a > 0).mean()*100), mean=float(a.mean()),
                med=float(np.median(a)))


def line(label, s):
    if s is None:
        return f"  {label:<22} 매매 없음"
    return (f"  {label:<22} n={s['n']:>5}  승률 {s['win']:4.1f}%  "
            f"평균 {s['mean']:+.3f}%  중앙 {s['med']:+.3f}%")


def run(limit=150, start="2022-01-01", oos="2025-06-01"):
    print("=" * 70)
    print(f"  정직한 검증  (상위 {limit}종목, {start}~, OOS={oos}~)")
    print(f"  비용 가정: 왕복 {C.COST_ROUNDTRIP}%p 차감")
    print("=" * 70)

    uni = build_universe_with_market(limit)
    reg = {"KOSPI": regime_series("KS11", start), "KOSDAQ": regime_series("KQ11", start)}
    print(f"유니버스 {len(uni)}종목 분석 중...\n")

    rows = []  # (date, market, gross, regime_ok)
    for i, (code, name, market) in enumerate(uni, 1):
        if i % 40 == 0:
            print(f"  ...{i}/{len(uni)}")
        df = data.get_history_full(code, start=start)
        if df is None or len(df) < C.MA_LONG + 5:
            continue
        r = signals(df)
        if r is None:
            continue
        sig, ret = r
        idx = sig & ret.notna()
        rmap = reg.get(market, {})
        for d, g in ret[idx].items():
            rows.append((d, market, float(g), bool(rmap.get(d, False))))

    if not rows:
        print("신호 없음.")
        return
    df = pd.DataFrame(rows, columns=["date", "market", "gross", "regime_ok"])
    df["date"] = pd.to_datetime(df["date"])
    df["net"] = df["gross"] - C.COST_ROUNDTRIP
    oos_dt = pd.to_datetime(oos)

    def block(title, sub):
        print(title)
        print(line("총수익(비용 전)", stats(sub["gross"].values)))
        print(line("순수익(비용 후)", stats(sub["net"].values)))
        rf = sub[sub["regime_ok"]]
        print(line("순수익+레짐필터", stats(rf["net"].values)))
        print()

    block("── 전체 기간 ─────────────────────────────────", df)
    block(f"── 인샘플 ({start}~{oos}) ───────────────────", df[df.date < oos_dt])
    block(f"── ★ 아웃오브샘플 ({oos}~) — 진짜 성과 ★ ──", df[df.date >= oos_dt])

    # 판정
    oos_df = df[df.date >= oos_dt]
    net = stats(oos_df["net"].values)
    netreg = stats(oos_df[oos_df["regime_ok"]]["net"].values)
    print("=" * 70)
    print("판정 (아웃오브샘플 순수익 기준):")
    for label, s in [("기본", net), ("레짐필터", netreg)]:
        if s and s["n"] >= 30:
            edge = s["mean"]
            verdict = "양(+) 엣지 가능" if edge > 0.1 else ("거의 본전" if edge > -0.1 else "마이너스(돈 잃음)")
            print(f"  {label}: 매매당 순 {edge:+.3f}%  → {verdict}  (표본 {s['n']})")
        elif s:
            print(f"  {label}: 표본 부족({s['n']}) — 판단 보류")
    print("  ※ 생존편향 미반영이라 실제는 이보다 보수적으로 보세요.")
    print("=" * 70)


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    st = sys.argv[2] if len(sys.argv) > 2 else "2022-01-01"
    oo = sys.argv[3] if len(sys.argv) > 3 else "2025-06-01"
    run(lim, st, oo)
