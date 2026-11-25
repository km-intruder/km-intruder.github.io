"""수시 2차 경민대 최종값(학교 내부 집계표, 2026-11-26 24시, 15일차) 반영.

school/susi2-2027.json 과 depts/*/ratios-susi2.json 의 경민대 행을 집계표 값으로 바꾸고
locked 로 표시해 매시 수집기가 덮어쓰지 않게 한다. 2026 지원인원도 집계표의 '전년도 지원인원'.

    python scripts/apply_susi2_final.py [--dry-run]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "admissions-2026"
BASIS = "2026-11-26 24시 기준 (15일차, 학교 내부 집계, 최종)"
NOTE = "학교 내부 집계 최종값 (정원내 전형 합계, 11.26 24시)"
TRACK = {"general": "일반전형", "regular": "특별전형-일반고", "vocational": "특별전형-특성화고",
         "special": "특별전형-성인/특기자/독자", "talent": "특별전형-특별인재"}
# 학과: 입학정원, 전형별 [모집, 지원], 전년도 지원인원(None=신설), 수시 2차 충원 후 잔존인원
T = {
    "간호학과": (145, {"regular": [17, 277], "vocational": [5, 58]}, 317, 274),
    "보건의료행정과": (60, {"regular": [5, 105], "vocational": [4, 22]}, 148, 68),
    "언어치료학과": (30, {"general": [5, 85]}, 30, -19),
    "의료미용과": (30, {"general": [3, 72]}, 39, 30),
    "소방안전관리과": (120, {"general": [16, 253], "special": [10, 38]}, 161, 121),
    "응급구조학과": (40, {"general": [7, 141]}, 151, 121),
    "카페베이커리과": (60, {"regular": [5, 78], "vocational": [3, 21]}, 117, 89),
    "호텔관광학과": (35, {"general": [5, 100]}, 132, 103),
    "호텔조리과": (72, {"regular": [6, 63], "vocational": [2, 12]}, 97, 73),
    "건축공간디자인학과": (35, {"general": [7, 164]}, 120, 25),
    "사회복지과": (50, {"general": [7, 168]}, 160, 73),
    "유아교육학과": (32, {"general": [6, 59]}, 111, 104),
    "국방드론봇시스템과": (30, {"general": [4, 47]}, None, None),
    "사이버·정보시스템학과": (20, {"general": [4, 34]}, 14, -8),
    "지능형소프트웨어과": (39, {"general": [3, 65]}, 62, -13),
    "효충군사학과": (40, {"general": [4, 53]}, 37, 23),
    "미디어영상과": (50, {"general": [12, 118]}, 173, 137),
    "실용음악과": (40, {"general": [13, 109]}, 62, 18),
    "연기예술과": (40, {"general": [15, 85]}, 51, 10),
    "게임콘텐츠과": (80, {"general": [10, 93], "special": [6, 38]}, 189, 151),
    "레포츠과": (50, {"general": [4, 21], "special": [11, 31], "talent": [1, 1]}, 56, 26),
    "태권도외교과": (100, {"special": [14, 88], "talent": [3, 12]}, 183, 155),
    "헤어디자인과": (30, {"general": [2, 106]}, 40, 28),
    "자유전공학과": (30, {"general": [7, 104]}, 128, 73),
    "라이프케어과": (90, {"special": [3, 26]}, 60, 39),
    "라이프콘텐츠과": (70, {"special": [2, 20]}, 20, 16),
}
DETAIL = {"태권도외교과": "전공별 — 시범: 특기자 7명·51명, 특별인재 1명·6명 · 품새: 3명·22명, 1명·4명 · "
                     "겨루기: 3명·12명, 1명·2명 · 자유품새: 특기자 1명·3명"}
TOTAL_CHECK = {"quota": 231, "applied": 2767, "prevApplied": 2658, "day": (226, 2721, 2578)}


def write(path, data, dry):
    if not dry:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def school(dry):
    p = ROOT / "school" / "susi2-2027.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    names = {d["name"] for d in data["depts"]}
    assert names == set(T), f"학과 불일치: {names ^ set(T)}"
    for d in data["depts"]:
        cap, tracks, prev, remain = T[d["name"]]
        d.update(capacity=cap, tracks=tracks, quota=sum(q for q, _ in tracks.values()),
                 applied=sum(a for _, a in tracks.values()), prevApplied=prev, remain=remain)
        d.pop("new", None)
        if prev is None:
            d["new"] = True
            d["prevQuota"] = None
        if d["name"] in DETAIL:
            d["trackDetail"] = DETAIL[d["name"]]
    data.update(title="2027학년도 수시 2차 정원내 지원현황", basis=BASIS, final=True, locked=True,
                source="경민대학교 수시 2차 내부 집계표(15일차 최종) · 2026은 집계표의 ‘전년도 지원인원’")
    day = [d for d in data["depts"] if not d.get("adult")]
    tot = lambda ds: {"quota": sum(d["quota"] for d in ds), "applied": sum(d["applied"] for d in ds),
                      "prevApplied": sum(d.get("prevApplied") or 0 for d in ds)}
    data["total"] = {**tot(data["depts"]), "day": tot(day)}
    t = data["total"]
    got = {"quota": t["quota"], "applied": t["applied"], "prevApplied": t["prevApplied"],
           "day": (t["day"]["quota"], t["day"]["applied"], t["day"]["prevApplied"])}
    assert got == TOTAL_CHECK, f"합계가 집계표와 다름: {got}"
    print(f"school/susi2-2027.json: {t}")
    write(p, data, dry)


def depts(dry):
    for p in sorted(ROOT.glob("depts/*/ratios-susi2.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for r in data["rows"]:
            if r["school"] != "km":
                continue
            _, tracks, prev, _ = T[r["dept"]]
            r.update(quota=sum(q for q, _ in tracks.values()), applied=sum(a for _, a in tracks.values()),
                     locked=True, note=NOTE)
            r.pop("sum", None)
            if r.get("main"):
                key = next(k for k, v in TRACK.items() if v == r["main"]["track"])
                r["main"].update(quota=tracks[key][0], applied=tracks[key][1])
            if prev is None:
                continue
            old = r.get("priorApplied")
            r["priorApplied"] = prev
            # 진학사 2026 값이 일부 전형만 잡혀 집계표와 크게 다르면 2026 모집인원·경쟁률을 믿지 않는다
            if old is None or abs(prev - old) > 0.1 * prev:
                r.update(priorQuota=None, prior=None, comparable=False,
                         priorNote="2026 지원인원은 학교 집계표 값, 2026 모집인원은 확인 안 됨")
            elif r.get("priorQuota"):
                r["prior"] = round(prev / r["priorQuota"], 2)
        for s in data["schools"]:
            if s["id"] == "km":
                s["time"] = "2026-11-26 24시 최종 (학교 집계)"
        if "km" not in data.setdefault("finalized", []):
            data["finalized"].insert(0, "km")
        write(p, data, dry)
        print(f"{p.parent.name}: " + ", ".join(f"{r['dept']} {r['applied']}/{r['quota']}" for r in data["rows"] if r["school"] == "km"))


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    school(dry)
    depts(dry)
