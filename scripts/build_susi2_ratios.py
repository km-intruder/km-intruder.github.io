"""수시 2차 경쟁률 파일 생성기.

학과마다 수시 1차 비교 파일(depts/<학과>/ratios.json)을 본으로
depts/<학과>/ratios-susi2.json 을 만든다.

- 비교 학교: 수시 1차와 같은 전문대 (4년제는 수시 2차가 없어 뺀다)
- 2027: 진학사 스마트경쟁률의 '수시2차' 경쟁률 원문 (진학어플라이·유웨이어플라이)
- 모집단위: 수시 1차와 같은 학과. 수시 2차에 모집하지 않는 학과는 빠진다.
  전형은 수시 1차와 같은 전형이 있으면 그것, 없으면 일반고·일반전형 순으로 고른다.
- 경민대: 학과 정원내 전형 합계(sum: true) + 수시 1차와 같은 주 전형(main)
- 2026: 진학사 스마트경쟁률 과거 경쟁률(PastRatioUniv)의 2026 수시2차, 같은 학과·전형

이후 지원인원은 매시 수집기(update_admissions_ratios.py)가 갱신한다.

    python scripts/build_susi2_ratios.py [--dry-run]
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import build_national_ratios as B
import update_admissions_ratios as U

DEPT_DIR = Path(__file__).resolve().parent.parent / "admissions-2026" / "depts"
OUT = "ratios-susi2.json"
# 이름이 바뀐 경민대 학과 (2026 학과명) — build_trends.py 의 ALIAS 와 같다
KM_ALIAS = {
    "지능형소프트웨어과": ["컴퓨터소프트웨어과"], "사이버·정보시스템학과": ["사이버보안학과"],
    "효충군사학과": ["효충사관과"], "호텔관광학과": ["호텔관광경영과"], "미디어영상과": ["영상콘텐츠과"],
    "연기예술과": ["공연예술과"], "의료미용과": ["뷰티케어과"],
}
GENERAL = r"일반고|일반전형|^일반$|일반학생"
NOT_MAIN = r"특성화|성인|만학|독자|특별인재|특기|추천|면접"


def round2():
    """스마트경쟁률의 2027 수시 2차 전문대 {이름: {url, uid}}."""
    page = U._fetch(B.SMART)
    syn = {long: uid for _, long, uid in reversed(B.hidden_json(page, "hdnSynonym")["Synonym"])}
    out = {}
    for c in B.table(B.hidden_json(page, "hdnResultNow")):
        if c["UnivType"] != 2 or c["CategoryDisplayName"] != "수시2차" or not (c["RatioLink"] or "").strip():
            continue
        m = re.search(r"/Notice/(\d{4})\d{3}/", c["WonseoLink"] or "")
        url = c["RatioLink"].strip().replace("http://addon.", "https://addon.")
        out[c["UnivName"]] = {"url": url, "uid": int(m.group(1)) if m else syn.get(c["UnivName"])}
    return out


def pick(cands, track, key=lambda e: e["section"]):
    """같은 학과 후보 중 전형 고르기: 수시 1차와 같은 전형 → 일반고·일반전형 → 하나뿐이면 그것."""
    t = U.norm_track(track or "")
    same = [e for e in cands if t and t in U.norm_track(key(e))]
    if same:
        return same
    gen = [e for e in cands if re.search(GENERAL, key(e)) and not re.search(NOT_MAIN, key(e))]
    if gen:
        return gen
    return [e for e in cands if not re.search(NOT_MAIN, key(e))] or cands


def past_rows(past, names):
    keys = {U.norm(n) for n in names}
    return [p for p in past if p["CategoryDisplayName"] == "수시2차" and U.norm(p["MajorName"]) in keys
            and not re.search(U.OUTSIDE, p["SelTypeName"]) and not re.search(U.SUMMARY, p["SelTypeName"])]


def build_km(row, entries, past, warn):
    hits = U.dept_hits(row["dept"], entries)
    if not hits:
        return None
    out = {k: v for k, v in row.items() if k in ("school", "dept", "field", "comparable", "rankWith")}
    out.update(track="정원내 전체", quota=sum(e["quota"] for e in hits), applied=sum(e["applied"] for e in hits), sum=True)
    main = pick(hits, (row.get("main") or {}).get("track") or "일반전형")
    if len(hits) > 1 and len(main) == 1 and main[0]["quota"]:
        out["main"] = {"track": U.track_name(main[0]["section"]), "quota": main[0]["quota"], "applied": main[0]["applied"]}
    pr = past_rows(past, [row["dept"]] + KM_ALIAS.get(row["dept"], []))
    if pr:
        q, a = sum(p["Mojip"] for p in pr), sum(p["Jiwon"] for p in pr)
        out.update(prior=round(a / q, 2) if q else None, priorQuota=q, priorApplied=a, priorUrl=None)
        if pr[0]["MajorName"] != row["dept"]:
            out["priorName"] = pr[0]["MajorName"]
    else:
        out["comparable"] = False
        out["priorNote"] = "2026학년도 수시 2차에 같은 모집단위 없음"
        warn(f"경민대 {row['dept']}: 2026 수시 2차 값 없음")
    out["note"] = "진학어플라이 공개값 (정원내 전형 합계)"
    return out


def build_row(row, entries, past, warn):
    hits = U.dept_hits(row["dept"], entries)
    if not hits:
        return None
    chosen = pick(hits, row.get("track"))
    chosen = [e for e in chosen if e["section"] == chosen[0]["section"]]
    out = {k: v for k, v in row.items() if k in ("school", "dept", "field")}
    out.update(track=U.track_name(chosen[0]["section"]), quota=sum(e["quota"] for e in chosen),
               applied=sum(e["applied"] for e in chosen))
    if len(chosen) > 1:  # 한 전형 안에서 전공별로 나뉜 모집단위는 합친다 (수집기도 sum 으로 합계를 낸다)
        out["sum"] = True
        warn(f"{row['dept']} {out['track']}: 전공 {len(chosen)}개 합계 ({', '.join(e['label'][:20] for e in chosen)})")
    pr = pick(past_rows(past, [row["dept"]]), out["track"], key=lambda p: p["SelTypeName"])
    pr = [p for p in pr if U.norm_track(p["SelTypeName"]) == U.norm_track(out["track"])]
    if len(pr) == 1:
        p = pr[0]
        out.update(prior=round(p["Ratio"], 2), priorName=p["MajorName"], priorQuota=p["Mojip"], priorApplied=p["Jiwon"],
                   priorUrl=None, comparable=bool(p["Mojip"]))
    else:
        out.update(comparable=False, priorNote="2026학년도 수시 2차 같은 모집단위·전형 값을 찾지 못함")
    return out


def main():
    dry = "--dry-run" in sys.argv
    r2 = round2()
    print(f"수시 2차 전문대 {len(r2)}곳")
    files = sorted(DEPT_DIR.glob("*/ratios.json"))
    names = {s["name"] for f in files for s in json.loads(f.read_text(encoding="utf-8"))["schools"] if s["type"] != "4년제"}

    def load(name):
        info = r2.get(name)
        if not info:
            return name, None
        try:
            html = U._fetch(info["url"])
            past = B.table(B.hidden_json(U._fetch(B.PAST.format(info["uid"])), "hdnResult")) if info["uid"] else []
        except Exception as e:  # 한 학교 실패가 전체를 막지 않도록
            print(f"[{name}] 불러오기 실패: {e}")
            return name, None
        return name, {**info, "entries": U.parse_entries(html), "time": U.parse_time(html), "past": past}

    with ThreadPoolExecutor(8) as ex:
        pages = dict(ex.map(load, sorted(names)))
    for n in sorted(names):
        p = pages[n]
        print(f"  {n}: " + ("수시 2차 원문 없음" if not p else f"{len(p['entries'])}행 · 2026 과거 {sum(x['CategoryDisplayName'] == '수시2차' for x in p['past'])}행"))

    for f in files:
        src = json.loads(f.read_text(encoding="utf-8"))
        warns = []
        byid = {s["id"]: s for s in src["schools"]}
        rows, used = [], set()
        for row in src["rows"]:
            s = byid[row["school"]]
            p = pages.get(s["name"]) if s["type"] != "4년제" else None
            if not p:
                continue
            w = lambda m, n=s["name"]: warns.append(f"[{n}] {m}")
            new = (build_km if row["school"] == "km" else build_row)(row, p["entries"], p["past"], w)
            if new:
                rows.append(new)
                used.add(s["id"])
            elif row["school"] == "km" and row["dept"] == src["baseline"]["dept"]:
                warns.append(f"기준 학과 {row['dept']} 가 수시 2차 원문에 없음")
        schools = []
        for s in src["schools"]:
            if s["id"] not in used:
                continue
            p = pages[s["name"]]
            s = {k: v for k, v in s.items() if k != "time"}
            s["url"] = p["url"]
            if p["time"]:
                s["time"] = p["time"]
            schools.append(s)
        out = {"schools": schools, "rows": rows, "live": sorted(used), "finalized": [],
               "checkedAt": U.datetime.now(U.KST).strftime("%Y-%m-%d %H:%M"), "baseline": src["baseline"]}
        print(f"== {f.parent.name}: 학교 {len(schools)} · 모집단위 {len(rows)} (수시 1차 {len(src['rows'])})")
        for m in warns:
            print("   " + m)
        if not dry:
            (f.parent / OUT).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
