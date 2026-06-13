# -*- coding: utf-8 -*-
"""
종가 매매 스크리너 - 웹앱 (Streamlit).
어디서든 브라우저로 접속해서 오늘의 후보 / 백테스트를 볼 수 있습니다.

로컬 실행:  streamlit run app.py
배포:      Streamlit Community Cloud (무료) - README 참고
"""
import os
import sys
import datetime as dt

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import screen
import backtest
import config as C

st.set_page_config(page_title="종가 매매 스크리너", page_icon="📈", layout="centered")

st.title("📈 종가 매매 스크리너")
st.caption("매일 종가베팅 후보를 추려주는 도구 · **수익 보장 아님** · 최종 매수는 본인 판단")

tab1, tab2, tab3 = st.tabs(["오늘의 후보", "백테스트", "도움말"])


@st.cache_data(ttl=3600, show_spinner=False)
def cached_candidates(daykey):
    """하루 1회만 계산하고 캐시 (daykey가 날짜라 매일 갱신)."""
    return screen.get_candidates()


# ── 탭 1: 오늘의 후보 ──────────────────────────────────────────
with tab1:
    st.write("장 마감 직전(오후 3시경)에 실행하면 가장 정확합니다.")
    go = st.button("🔍 오늘의 후보 불러오기", type="primary", use_container_width=True)
    if go:
        with st.spinner("전 종목 스냅샷 + 정밀 분석 중... (10~40초)"):
            res = cached_candidates(dt.date.today().isoformat())

        idx = res["index"]
        c1, c2 = st.columns(2)
        c1.metric("코스피", f"{idx.get('KOSPI')}%" if idx.get('KOSPI') is not None else "—")
        c2.metric("코스닥", f"{idx.get('KOSDAQ')}%" if idx.get('KOSDAQ') is not None else "—")
        weak = [k for k, v in idx.items() if v is not None and v <= C.MARKET_WARN_THRESHOLD]
        if weak:
            st.warning(f"⚠️ {', '.join(weak)} 약세 — 종가베팅 비중을 줄이거나 쉬는 게 안전합니다.")

        top = res["results"][:C.TOP_N]
        st.subheader(f"추천 후보 {len(top)}개  (1차 통과 {res['candidate_count']}개)")
        if not top:
            st.info("조건을 만족하는 종목이 없습니다. 오늘은 쉬는 것도 전략입니다.")
        for i, r in enumerate(top, 1):
            with st.container(border=True):
                st.markdown(f"**{i}. {r['name']}**  `{r['code']}` · {r['market']}  ·  점수 **{r['score']}**")
                st.write(
                    f"종가 **{r['close']:,.0f}원** · 등락 **+{r['change_pct']:.1f}%** · "
                    f"거래대금 {r['amount']/1e8:,.0f}억")
                st.caption("근거: " + ", ".join(r["reasons"]))

        st.divider()
        st.caption(
            f"매수 15:10~15:30 동시호가 · 매도 다음날 09:00~09:30 · "
            f"목표 +{C.TARGET_PROFIT:.0f}% / 손절 {C.STOP_LOSS:.0f}% · 분할 익절 권장")


# ── 탭 2: 백테스트 ─────────────────────────────────────────────
with tab2:
    st.write("이 전략으로 과거에 매매했다면 어땠을지 검증합니다.")
    col = st.columns(2)
    limit = col[0].slider("검증 종목 수 (유동성 상위)", 30, 200, 80, 10)
    start = col[1].text_input("시작일", "2023-01-01")
    if st.button("📊 백테스트 실행", use_container_width=True):
        bar = st.progress(0.0, text="데이터 수집 중...")

        def prog(done, total):
            bar.progress(done / total, text=f"분석 중... {done}/{total}")

        with st.spinner("백테스트 중... (종목 수에 따라 1~3분)"):
            bt = backtest.run_backtest(limit, start, progress=prog)
        bar.empty()

        if bt is None:
            st.error("신호가 없습니다. config.py 조건을 완화해 보세요.")
        else:
            m = st.columns(3)
            m[0].metric("총 매매", f"{bt['n']:,}회")
            m[1].metric("승률", f"{bt['win_rate']:.1f}%")
            m[2].metric("평균 수익", f"{bt['mean']:+.2f}%")
            st.caption(
                f"중앙값 {bt['median']:+.2f}% · 표준편차 {bt['std']:.2f}% · "
                f"최고 {bt['max']:+.0f}% / 최저 {bt['min']:+.0f}%")
            st.caption("※ 수수료·세금 약 -0.3%p 별도 차감 / 생존편향·슬리피지 미반영 → 실제는 더 보수적으로")

            pt = bt["per_trade"]
            yearly = pt.groupby("year")["ret"].agg(평균수익="mean", 매매수="count").round(2)
            yearly["승률%"] = pt.groupby("year")["ret"].apply(lambda g: round((g > 0).mean() * 100)).astype(int)
            st.write("**연도별 성과**")
            st.dataframe(yearly, use_container_width=True)
            st.write("**수익률 분포**")
            st.bar_chart(pt["ret"].clip(-10, 15))


# ── 탭 3: 도움말 ───────────────────────────────────────────────
with tab3:
    st.markdown("""
### 종가 매매란?
장 마감 직전(15:10~15:30 동시호가)에 매수해서 **다음 날 아침에 매도**하는 단기 전략.

### 후보 선정 조건
- 거래량 20일 평균 대비 **2배 이상 급증**
- 종가가 당일 고가 대비 **85% 이상** (윗꼬리 짧은 장대 양봉)
- 당일 등락 **+3~25%**, 거래대금 100억+, 시총 500억~5조
- 5일선 위 / 정배열 / 60일 신고가 근접 시 가점

### 꼭 기억하세요
- 이 도구는 **후보만 추천**합니다. 자동주문 없음, 최종 판단은 본인.
- **수익을 보장하지 않습니다.** 실거래 전 백테스트로 검증하고,
  가능하면 모의계좌로 2주 이상 연습하세요.
""")
