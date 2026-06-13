# -*- coding: utf-8 -*-
"""
로컬 PC에서 실행: 종가매매 후보를 계산해 results.json으로 저장하고 GitHub에 올림.
클라우드 앱(app.py)이 그 results.json을 읽어 어디서든 보여준다.

사용법:
    python publish.py                # 후보 + 백테스트 계산 후 GitHub push
    python publish.py --no-backtest  # 백테스트 생략(빠름)
    python publish.py --no-push      # 로컬 저장만(테스트용)

매일 15:05 자동 실행하려면 publish.bat을 작업 스케줄러에 등록하세요.
"""
import os
import sys
import json
import subprocess
import datetime as dt

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import screen
import backtest
import config as C

RESULTS = os.path.join(HERE, "results.json")


def git(*args):
    """git 명령 실행 (repo 디렉터리에서). 실패해도 죽지 않음."""
    try:
        r = subprocess.run(["git", *args], cwd=HERE, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:
        return 1, str(e)


def main():
    no_bt = "--no-backtest" in sys.argv
    no_push = "--no-push" in sys.argv
    now = dt.datetime.now()

    print(f"[{now:%H:%M}] 후보 계산 중...")
    res = screen.get_candidates()
    print(f"  후보 {len(res['results'])}개 (1차 통과 {res['candidate_count']}개)")

    bt = None
    if not no_bt:
        print("백테스트 계산 중... (1~2분)")
        try:
            b = backtest.run_backtest(limit=80, start="2024-01-01")
            if b:
                pt = b["per_trade"]
                yearly = [{"year": int(y), "mean": round(float(g["ret"].mean()), 2),
                           "n": int(len(g)), "win": int(round((g["ret"] > 0).mean() * 100))}
                          for y, g in pt.groupby("year")]
                bt = {"n": b["n"], "win_rate": round(b["win_rate"], 1),
                      "mean": round(b["mean"], 2), "median": round(b["median"], 2),
                      "yearly": yearly}
                print(f"  백테스트: {b['n']}매매, 승률 {b['win_rate']:.1f}%, 평균 {b['mean']:+.2f}%")
        except Exception as e:
            print(f"  백테스트 실패(건너뜀): {e}")

    payload = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "index": res["index"],
        "candidate_count": res["candidate_count"],
        "results": res["results"][:C.TOP_N],
        "guide": {"target": C.TARGET_PROFIT, "stop": C.STOP_LOSS},
        "backtest": bt,
    }
    with open(RESULTS, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"저장: {RESULTS}")

    if no_push:
        print("(--no-push: GitHub 업로드 생략)")
        return

    print("GitHub에 올리는 중...")
    git("add", "results.json")
    code, out = git("commit", "-m", f"data: {payload['generated_at']} 종가후보 갱신")
    if "nothing to commit" in out:
        print("  변경 없음 (오늘 이미 동일 데이터).")
        return
    code, out = git("push")
    if code == 0:
        print("  ✅ 업로드 완료. 1~2분 뒤 클라우드 앱에 반영됩니다.")
    else:
        print(f"  ⚠️ push 실패: {out}")


if __name__ == "__main__":
    main()
