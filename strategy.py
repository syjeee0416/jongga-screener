# -*- coding: utf-8 -*-
"""
종가 매매 전략 규칙 (조사 기반).
 - 종목 적격성(우선주/스팩/ETF/관리종목 제외)
 - 피처 계산(거래량배수, 종가위치, 이평선, 신고가)
 - 점수화 + 사람이 읽을 근거 텍스트
"""
import re
import pandas as pd
import config as C

# ETF/ETN/스팩/리츠 등 종가베팅 대상이 아닌 이름 패턴
_EXCLUDE_NAME = re.compile(
    r"(KODEX|TIGER|KBSTAR|ARIRANG|HANARO|SOL |ACE |PLUS |RISE |KOSEF|TIMEFOLIO|"
    r"ETN|스팩|제\d+호|리츠|레버리지|인버스|선물)", re.IGNORECASE)


def is_tradeable(name, code):
    """종가베팅 대상으로 적합한 보통주인지."""
    if not isinstance(name, str):
        return False
    if _EXCLUDE_NAME.search(name):
        return False
    # 우선주: 종목코드 끝자리가 0이 아니면 대개 우선주/신주인수권 등
    if isinstance(code, str) and len(code) == 6 and not code.endswith("0"):
        return False
    return True


def close_position(open_, high, low, close):
    """당일 캔들에서 종가 위치 0~1. (종가-저가)/(고가-저가)."""
    rng = high - low
    if rng <= 0:
        return 1.0 if close >= open_ else 0.0
    return (close - low) / rng


def compute_features(hist, snapshot_row=None):
    """
    hist: 종목 일봉 DataFrame (Open/High/Low/Close/Volume, 마지막 행=오늘)
    return: 피처 dict 또는 None(데이터 부족)
    """
    if hist is None or len(hist) < C.MA_LONG + 1:
        return None
    df = hist.rename(columns=str.title)  # 컬럼명 표준화
    need = {"Open", "High", "Low", "Close", "Volume"}
    if not need.issubset(set(df.columns)):
        return None

    today = df.iloc[-1]
    o, h, l, c, v = (float(today["Open"]), float(today["High"]),
                     float(today["Low"]), float(today["Close"]), float(today["Volume"]))

    ma5 = df["Close"].tail(C.MA_SHORT).mean()
    ma20 = df["Close"].tail(C.MA_LONG).mean()
    vol_ma = df["Volume"].iloc[-(C.VOL_MA_WINDOW + 1):-1].mean()  # 오늘 제외 평균
    vol_ratio = (v / vol_ma) if vol_ma > 0 else 0.0
    high_n = df["High"].iloc[-(C.HIGH_LOOKBACK + 1):-1].max()  # 오늘 제외 고점
    pos = close_position(o, h, l, c)

    return {
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "ma5": ma5, "ma20": ma20,
        "vol_ratio": vol_ratio,
        "close_position": pos,
        "is_bullish": c > o,
        "above_ma5": c >= ma5,
        "ma_aligned": c > ma5 > ma20,
        "near_high": (high_n > 0 and c >= high_n * C.NEAR_HIGH_RATIO),
        "new_high": (high_n > 0 and c >= high_n),
        "high_n": high_n,
    }


def score(feat):
    """피처 → (점수, 근거리스트). 하드 조건 미달이면 (0, [])."""
    if feat is None:
        return 0, []
    # 하드 게이트: 양봉 + 종가위치 + 거래량 급증은 필수
    if not feat["is_bullish"]:
        return 0, []
    if feat["close_position"] < C.MIN_CLOSE_POSITION:
        return 0, []
    if feat["vol_ratio"] < C.MIN_VOL_RATIO:
        return 0, []

    s = 0
    reasons = []
    w = C.WEIGHTS

    # 거래량 급증 (배수가 클수록 가중)
    s += w["vol_surge"]
    reasons.append(f"거래량 {feat['vol_ratio']:.1f}배 급증")

    # 종가 위치
    s += w["close_position"]
    reasons.append(f"고점 마감(종가위치 {feat['close_position']*100:.0f}%)")

    if feat["above_ma5"]:
        s += w["above_ma5"]
        reasons.append("5일선 위")
    if feat["ma_aligned"]:
        s += w["ma_aligned"]
        reasons.append("정배열(종가>5>20일선)")
    if feat["new_high"]:
        s += w["near_high"]
        reasons.append("60일 신고가 경신")
    elif feat["near_high"]:
        s += int(w["near_high"] * 0.6)
        reasons.append("전고점 근접")

    return s, reasons


def passes_snapshot_filter(row):
    """전 종목 스냅샷에서 1차 후보 압축 (값싼 필터)."""
    try:
        if row["amount"] < C.MIN_AMOUNT:
            return False
        if not (C.MIN_MARCAP <= row["marcap"] <= C.MAX_MARCAP):
            return False
        if not (C.MIN_CHANGE <= row["change_pct"] <= C.MAX_CHANGE):
            return False
        if row["close"] <= row["open"]:   # 양봉만
            return False
        pos = close_position(row["open"], row["high"], row["low"], row["close"])
        if pos < C.MIN_CLOSE_POSITION:
            return False
    except (KeyError, TypeError):
        return False
    return True
