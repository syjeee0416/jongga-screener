# -*- coding: utf-8 -*-
"""
종가 매매 일일 스크리너 (메인 실행 파일).
오후 3시경 실행 → 종가베팅 후보 종목을 점수순으로 추천.

사용법:
    python screen.py
출력: 콘솔 표 + reports/ 폴더에 텍스트 리포트 저장
"""
import os
import sys
import datetime as dt

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

import data
import strategy
import config as C

REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def get_candidates(progress=None):
    """
    종가매매 후보 계산 (웹/CLI 공용 핵심 함수).
    progress: 선택적 콜백 progress(done, total) — 진행률 표시용.
    return: dict { 'index', 'candidate_count', 'results'(점수순 전체) }
    """
    idx = data.get_index_change()
    snap = data.get_universe_snapshot()
    cand = snap[snap.apply(strategy.passes_snapshot_filter, axis=1)]
    cand = cand[cand.apply(lambda r: strategy.is_tradeable(r["name"], r["code"]), axis=1)]
    cand = cand.reset_index(drop=True)

    results = []
    total = len(cand)
    for i, row in cand.iterrows():
        hist = data.get_history(row["code"], days=C.HISTORY_DAYS)
        feat = strategy.compute_features(hist)
        s, reasons = strategy.score(feat)
        if s > 0:
            results.append({
                "code": row["code"], "name": row["name"], "market": row["market"],
                "close": row["close"], "change_pct": row["change_pct"],
                "amount": row["amount"], "score": s, "reasons": reasons,
            })
        if progress:
            progress(i + 1, total)

    results.sort(key=lambda x: x["score"], reverse=True)
    return {"index": idx, "candidate_count": total, "results": results}


def run():
    now = dt.datetime.now()
    lines = []

    def out(msg=""):
        print(msg)
        lines.append(msg)

    out("=" * 64)
    out(f"  종가 매매 후보 스크리너   {now:%Y-%m-%d %H:%M}")
    out("=" * 64)

    # 시장 필터
    idx = data.get_index_change()
    out(f"\n[시장] 코스피 {idx.get('KOSPI')}%  /  코스닥 {idx.get('KOSDAQ')}%")
    weak = [k for k, v in idx.items() if v is not None and v <= C.MARKET_WARN_THRESHOLD]
    if weak:
        out(f"  ⚠️  {', '.join(weak)} 약세 — 종가베팅 비중 줄이거나 쉬는 게 안전합니다.")

    # 후보 계산 (공용 함수)
    out("\n전 종목 스냅샷 + 종목별 분석 중...")
    res = get_candidates()
    out(f"1차 통과 후보: {res['candidate_count']}개 (거래대금·등락률·고점마감 필터)")
    results = res["results"]
    top = results[:C.TOP_N]

    out("\n" + "=" * 64)
    out(f"  추천 종가매매 후보 TOP {len(top)}")
    out("=" * 64)
    if not top:
        out("\n  조건을 만족하는 종목이 없습니다. 오늘은 쉬는 것도 전략입니다.")
    for i, r in enumerate(top, 1):
        amt_eok = r["amount"] / 1e8
        out(f"\n{i}. {r['name']} ({r['code']}) · {r['market']}  [점수 {r['score']}]")
        out(f"   종가 {r['close']:,.0f}원  등락 +{r['change_pct']:.1f}%  거래대금 {amt_eok:,.0f}억")
        out(f"   근거: {', '.join(r['reasons'])}")

    # 매매 가이드
    out("\n" + "-" * 64)
    out("매매 가이드 (참고 / 자동매매 아님)")
    out(f"  매수: 15:10~15:30 동시호가  ·  매도: 다음날 09:00~09:30")
    out(f"  목표 +{C.TARGET_PROFIT:.0f}%  ·  손절 {C.STOP_LOSS:.0f}%  ·  분할 익절 권장")
    out("  ※ 이 목록은 '후보'입니다. 최종 매수는 본인 판단으로.")
    out("-" * 64)

    # 리포트 저장
    fname = os.path.join(REPORT_DIR, f"{now:%Y%m%d}_종가후보.txt")
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    out(f"\n리포트 저장: {fname}")
    return fname


if __name__ == "__main__":
    path = run()
    # 스케줄 실행 시(--open) 리포트를 자동으로 띄워 '알려줌'
    if "--open" in sys.argv and path:
        try:
            os.startfile(path)  # Windows
        except Exception:
            pass
