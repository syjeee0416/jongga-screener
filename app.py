# -*- coding: utf-8 -*-
"""
종가 매매 스크리너 - 웹 뷰어 (Streamlit Cloud).

이 앱은 데이터를 직접 받지 않습니다. (KRX가 해외 서버를 차단하기 때문)
로컬 PC에서 publish.py가 계산해 results.json을 GitHub에 올리면,
이 앱은 그 결과만 읽어서 보여줍니다. → 어디서든 폰/PC로 접속해 확인.
"""
import os
import json
import datetime as dt
import streamlit as st

st.set_page_config(page_title="종가 매매 스크리너", page_icon="📈", layout="centered")

RESULTS = os.path.join(os.path.dirname(__file__), "results.json")


def load_results():
    if not os.path.exists(RESULTS):
        return None
    try:
        with open(RESULTS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


st.title("📈 종가 매매 스크리너")
st.caption("매일 종가베팅 후보를 추려주는 도구 · **수익 보장 아님** · 최종 매수는 본인 판단")

data = load_results()

if data is None:
    st.info("아직 데이터가 없습니다.\n\n로컬 PC에서 `python publish.py`를 먼저 실행하면 "
            "후보가 여기에 표시됩니다. (매일 15:05 자동 실행되도록 등록해 두면 편해요.)")
    st.stop()

# 갱신 시각
gen = data.get("generated_at", "?")
c_top = st.columns([3, 1])
c_top[0].caption(f"🕒 마지막 갱신: **{gen}** (로컬 PC 기준)")
if c_top[1].button("다시 읽기", use_container_width=True):
    st.rerun()

tab1, tab2, tab3 = st.tabs(["오늘의 후보", "백테스트", "도움말"])

# ── 탭 1: 오늘의 후보 ──────────────────────────────────────────
with tab1:
    idx = data.get("index", {})
    c1, c2 = st.columns(2)
    c1.metric("코스피", f"{idx.get('KOSPI')}%" if idx.get('KOSPI') is not None else "—")
    c2.metric("코스닥", f"{idx.get('KOSDAQ')}%" if idx.get('KOSDAQ') is not None else "—")
    weak = [k for k, v in idx.items() if v is not None and v <= -1.0]
    if weak:
        st.warning(f"⚠️ {', '.join(weak)} 약세 — 종가베팅 비중을 줄이거나 쉬는 게 안전합니다.")

    results = data.get("results", [])
    st.subheader(f"추천 후보 {len(results)}개  (1차 통과 {data.get('candidate_count', '?')}개)")
    if not results:
        st.info("조건을 만족하는 종목이 없습니다. 오늘은 쉬는 것도 전략입니다.")
    for i, r in enumerate(results, 1):
        with st.container(border=True):
            st.markdown(f"**{i}. {r['name']}**  `{r['code']}` · {r['market']}  ·  점수 **{r['score']}**")
            st.write(
                f"종가 **{r['close']:,.0f}원** · 등락 **+{r['change_pct']:.1f}%** · "
                f"거래대금 {r['amount']/1e8:,.0f}억")
            st.caption("근거: " + ", ".join(r["reasons"]))

    g = data.get("guide", {})
    st.divider()
    st.caption(
        f"매수 15:10~15:30 동시호가 · 매도 다음날 09:00~09:30 · "
        f"목표 +{g.get('target', 4):.0f}% / 손절 {g.get('stop', -3):.0f}% · 분할 익절 권장")

# ── 탭 2: 백테스트 ─────────────────────────────────────────────
with tab2:
    bt = data.get("backtest")
    if not bt:
        st.info("백테스트 결과가 아직 없습니다. 로컬 publish.py 실행 시 함께 계산됩니다.")
    else:
        m = st.columns(3)
        m[0].metric("총 매매", f"{bt['n']:,}회")
        m[1].metric("승률", f"{bt['win_rate']:.1f}%")
        m[2].metric("평균 수익", f"{bt['mean']:+.2f}%")
        st.caption(f"중앙값 {bt.get('median', 0):+.2f}% · 종가 매수 → 다음날 시초가 매도 기준")
        st.caption("※ 수수료·세금 약 -0.3%p 별도 차감 / 생존편향·슬리피지 미반영 → 실제는 더 보수적으로")
        if bt.get("yearly"):
            st.write("**연도별 성과**")
            st.dataframe(
                [{"연도": y["year"], "평균수익(%)": y["mean"], "매매수": y["n"], "승률(%)": y["win"]}
                 for y in bt["yearly"]],
                use_container_width=True, hide_index=True)

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

### 이 앱의 구조
KRX가 해외 서버를 차단해서, **로컬 PC가 계산 → 결과만 클라우드에 표시**합니다.
그래서 "오늘의 후보"는 로컬 PC가 마지막으로 실행한 시점 기준입니다.

### 꼭 기억하세요
- **후보만 추천**합니다. 자동주문 없음, 최종 판단은 본인.
- **수익을 보장하지 않습니다.** 모의계좌로 2주 이상 연습을 권장합니다.
""")
