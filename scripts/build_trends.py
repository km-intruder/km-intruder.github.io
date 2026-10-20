"""학과별 입시 추이(2023~2027학년도 수시 1차) 파일 생성기.

admissions-2026/depts/<학과>/trends.json 을 학과마다 만든다.

- 비교 대상: 학과 ratios.json 의 전문대 모집단위(수도권 비교군) + ratios-national.json 의 공식 원문 모집단위
- 2023~2026: 진학사 스마트경쟁률 과거 경쟁률(PastRatioUniv)
- 2027: 경민대는 학교 집계(school/susi1-2027.json), 다른 학교는 경쟁률 원문
- 모든 해를 '수시 1차 정원내 전형 합계'로 묶는다 (build_national_ratios.py 와 같은 기준).
  비공식 자료로만 확인한 학교는 과거 값이 없어 넣지 않는다.

    python scripts/build_trends.py
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import build_national_ratios as N
import update_admissions_ratios as U

ROOT = N.DEPT_DIR.parent
YEARS = [2023, 2024, 2025, 2026, 2027]
PAST_YEARS = YEARS[:-1]
PAST = "https://apply.jinhakapply.com/SmartRatio/PastRatioUniv?univid={}&year={}&category=1"
# 해마다 이름이 바뀐 모집단위: (학교 이름, 현재 학과명) → 예전 학과명들
# (경민대: 입학처 학과명이 한 학과에서 다음 학과로 바로 이어진 경우만. 화면에는 해마다 실제 이름을 함께 보여 준다)
ALIAS = {
    ("경민대학교", "지능형소프트웨어과"): ["컴퓨터소프트웨어과"],
    ("경민대학교", "사이버·정보시스템학과"): ["사이버보안학과"],
    ("경민대학교", "효충군사학과"): ["효충사관과"],
    ("경민대학교", "호텔관광학과"): ["호텔관광경영과"],
    ("경민대학교", "미디어영상과"): ["영상콘텐츠과"],
    ("경민대학교", "연기예술과"): ["공연예술과"],
    ("경민대학교", "자유전공학과"): ["자율전공학부"],
    ("경민대학교", "의료미용과"): ["뷰티케어과"],
}


def base_name(s):
    """대조용: 괄호 설명·학제 표기·끝의 과/학과/전공을 뗀 이름."""
    # 끝의 괄호 설명만 뗀다 — '생활스포츠(족구)과'처럼 이름 가운데 괄호는 다른 모집단위라 남긴다
    s = re.sub(r"(\([^)]*\)|\[[^\]]*\])+$", "", N.clean(s)[1].strip())
    s = re.sub(r"(과|학과)-\S+$", lambda m: m.group(1), s)   # 경민대 '태권도외교과-시범', '레포츠과-축구' 같은 세부 모집단위는 학과로 합친다
    s = N.key(s)
    return re.sub(r"(학과|학부|과|전공|계열)$", "", s)


def total(rows, names):
    """한 해 원문 행 [(학과명, 전형, 모집, 지원)] 에서 names 에 맞는 정원내 합계."""
    want = {base_name(n) for n in names}
    rows = [(label, mq, ma, base_name(label)) for label, track, mq, ma in rows
            if mq and not re.search(N.SUMMARY, label) and not N.outside(track) and not N.outside(label)]
    # 같은 이름이 있으면 그것만, 없을 때만 이름 일부 일치(개명·학부 머리말)를 쓴다
    picked = [r for r in rows if r[3] in want] or \
             [r for r in rows if any(w and len(w) >= 3 and (w in r[3] or r[3] in w) for w in want)]
    if len({r[3] for r in picked}) > 1 and not any(r[3] in want for r in picked):
        return None   # 이름 일부가 여러 모집단위에 걸리면 같은 단위인지 알 수 없어 비운다
    if not picked:
        return None
    return {"quota": sum(r[1] for r in picked), "applied": sum(r[2] for r in picked),
            "name": " · ".join(sorted({N.clean(r[0])[0] for r in picked}))}


def past_rows(uid, year):
    page = U._fetch(PAST.format(uid, year))
    return [(x["MajorName"], x["SelTypeName"], x["Mojip"], x["Jiwon"])
            for x in N.table(N.hidden_json(page, "hdnResult")) if x["CategoryDisplayName"] == "수시1차"]


def main():
    cs = {c["name"]: c for c in N.colleges()}
    km_total = {d["id"]: d for d in json.loads((ROOT / "school" / "susi1-2027.json").read_text(encoding="utf-8"))["depts"] if d.get("id")}
    # 학과별 비교 모집단위 모으기
    plan = {}
    for f in sorted(N.DEPT_DIR.glob("*/ratios.json")):
        dept = f.parent.name
        units = []
        for name in ("ratios.json", "ratios-national.json"):
            p = f.parent / name
            if not p.exists():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            by = {s["id"]: s for s in data["schools"]}
            for r in data["rows"]:
                s = by[r["school"]]
                if s.get("type") == "4년제" or r.get("source") or s["name"] not in cs:
                    continue
                dname = re.sub(r"\((?:특기자|정원내|일반)[^)]*\)$", "", r["dept"]).strip()
                k = (s["name"], base_name(dname))
                if any((u["schoolName"], base_name(u["dept"])) == k for u in units):
                    continue
                units.append({"school": r["school"] if name == "ratios.json" else s["id"], "schoolName": s["name"],
                              "region": s["region"], "dept": dname, "isBase": r["school"] == "km" and dname == data["baseline"]["dept"],
                              "isKm": r["school"] == "km", "scope": "수도권" if name == "ratios.json" else "전국"})
        plan[dept] = units

    # 과거 원문(학교·연도별 한 번씩)과 2027 원문
    need = {u["schoolName"] for us in plan.values() for u in us}
    jobs = [(n, y) for n in need for y in PAST_YEARS if cs[n]["uid"]]
    with ThreadPoolExecutor(12) as ex:
        past = dict(zip(jobs, ex.map(lambda j: past_rows(cs[j[0]]["uid"], j[1]), jobs)))
        now = dict(zip(need, ex.map(lambda n: N.collect(dict(cs[n])).get("entries", []), need)))

    for dept, units in plan.items():
        out = []
        for u in units:
            names = [u["dept"]] + ALIAS.get((u["schoolName"], u["dept"]), [])
            series = {}
            for y in PAST_YEARS:
                v = total(past.get((u["schoolName"], y), []), names)
                if v:
                    series[str(y)] = v
            if u["isKm"]:
                d = next((d for d in km_total.values() if base_name(d["name"]) == base_name(u["dept"])), None)
                if d:   # 경민대 2027: 학교 집계 최종(정원내 학과 전체)
                    series["2027"] = {"quota": d["quota"], "applied": d["applied"], "name": d["name"], "source": "학교 집계"}
            else:
                v = total([(e["label"], e["section"], e["quota"], e["applied"]) for e in now.get(u["schoolName"], [])], names)
                if v:
                    series["2027"] = v
            if len(series) < 2 and not u["isBase"]:   # 기준 학과는 신설이라 한 해뿐이어도 남긴다
                print(f"  [{dept}] 자료 부족으로 뺌: {u['schoolName']} {u['dept']} ({', '.join(series) or '없음'})")
                continue
            out.append({**{k: u[k] for k in ("school", "schoolName", "region", "dept", "isBase", "isKm", "scope")}, "series": series})
        data = {"years": YEARS, "builtAt": datetime.now(N.KST).strftime("%Y-%m-%d"),
                "basis": "수시 1차 정원내 전형 합계 (농어촌·기초수급·대졸자·재직자 등 정원외 제외)",
                "sources": {"past": "진학사 스마트경쟁률 과거 경쟁률(2023~2026학년도 수시 1차)",
                            "now": "2027: 경민대 학교 집계, 다른 학교 경쟁률 원문(진학어플라이·유웨이어플라이·학교 입학처)"},
                "units": out}
        (N.DEPT_DIR / dept / "trends.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        base = next((x for x in out if x["isBase"]), None)
        print(f"{dept}: {len(out)}개 모집단위 · 경민대 기준 {'/'.join(base['series']) if base else '없음'}")


if __name__ == "__main__":
    main()
