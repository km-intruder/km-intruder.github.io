"""전국 공개 전문대 비교 파일 생성기.

2026 대비 지원자가 줄어든 학과(nav.js 의 S1N 학과)마다
admissions-2026/depts/<학과>/ratios-national.json 을 만든다.

- 학교 목록: 진학사 스마트경쟁률(2027 수시 1차 전문대, 한국폴리텍 제외)
- 2027: 각 학교 경쟁률 원문(진학어플라이·유웨이어플라이·학교 입학처). 원문이 없는 학교는 비교에서 빠진다.
- 2026: 진학사 스마트경쟁률 과거 경쟁률(PastRatioUniv)
- 모든 모집단위는 '정원내 전형 합계'로 묶는다 (학교마다 주 전형 이름이 달라서).
  경민대 행은 학과의 ratios.json(학교 집계 최종값)을 그대로 쓴다.

수시 1차가 끝난 뒤 한 번 만드는 자료라 모든 행을 locked 로 둔다 (매시 수집기가 덮어쓰지 않음).

비공식 자료: 공식 경쟁률 원문이 없는 학교는 학교 공지·입시결과·기사·기타 사이트에서 찾은 값을
depts/national-extra.json 에 출처와 함께 정리해 두고 합친다 (행에 source 가 붙고 화면에 '비공식'으로 표시).

    python scripts/build_national_ratios.py
"""
import html as H
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import update_admissions_ratios as U

DEPT_DIR = Path(__file__).resolve().parent.parent / "admissions-2026" / "depts"
EXTRA_FILE = DEPT_DIR / "national-extra.json"
SMART = "https://apply.jinhakapply.com/SmartRatio"
PAST = SMART + "/PastRatioUniv?univid={}&year=2026&category=1"
KST = timezone(timedelta(hours=9))

# 학과별 분야: (분야, 정규식) — 앞에서부터 처음 맞는 분야. EXCLUDE 는 이름에 키워드만 겹치는 다른 계열
DEPTS = {
    "cafe-bakery": [("제과제빵", r"제과|제빵|베이커리|파티시|디저트"), ("카페·바리스타", r"바리스타|카페|커피")],
    "hotel-culinary": [("호텔조리", r"호텔.*조리|조리.*호텔"), ("외식조리", r"조리|외식|요리|셰프|쿠킹|푸드")],
    "software": [("SW", r"소프트웨어|SW|프로그래밍|웹|앱|모바일"), ("AI", r"인공지능|AI|빅데이터|데이터"),
                 ("컴퓨터", r"컴퓨터|전산"), ("IT", r"정보통신|정보시스템|정보기술|ICT|IT|정보보안|사이버|보안")],
    "leports": [("스포츠지도·레저", r"레포츠|레저|생활체육|스포츠|체육|골프|피트니스|헬스|운동")],
    "taekwondo": [("태권도", r"태권"), ("경호·무도", r"경호|무도|무술")],
    "free-major": [("자유·자율전공", r"자유전공|자율전공|무전공|자유학부|자율학부|VISTA")],
}
EXCLUDE = {
    "cafe-bakery": r"조리(?!.*제과)|외식(?!.*제과)",
    "hotel-culinary": r"제과|제빵|베이커리|디저트|바리스타|카페|영양|푸드스타일|푸드테크|식품공학|바이오",
    "software": r"게임|간호|뷰티|미용|자동차|건축|기계|헬스|스포츠|패션|디자인|영상|방송|사무|세무|경영|회계|부동산|마케팅|물류|항공"
                r"|반도체|전기|화학|바이오|식품|드론|로봇|의료|보건|e스포츠|이스포츠|음악|웹툰|만화|애니",
    "leports": r"태권|경호|무도|e스포츠|이스포츠|E스포츠|스포츠재활|재활|마케팅|경찰|군사|헬스케어|뷰티|미용|간호|물리|작업|방사선"
               r"|임상|치위생|응급|보건|요가|경영",
    "taekwondo": r"경찰행정|교정",
    "free-major": r"$^",
}
# 자동 분류 뒤 원문을 확인해 뺀 모집단위 (학교, 학과명 일부)
DROP = {
    "hotel-culinary": [("울산과학대학교", "푸드케어")],
    "software": [("한국영상대학교", "웹소설"), ("한양여자대학교", "중국어"), ("연성대학교", "경찰경호"), ("연성대학교", "전자공학")],
    "leports": [("삼육보건대학교", "스포츠인재"), ("수원여자대학교", "라이프케어"), ("장안대학교", "족구"), ("울산과학대학교", "골프")],
    "taekwondo": [], "cafe-bakery": [],
    # 방송·영상 계열 안에서만 고르는 자유전공은 학교 전체 자유전공과 성격이 달라 뺀다
    "free-major": [("동아방송예술대학교", "자유전공"), ("한국영상대학교", "자율전공")],
}
# 정원외·특수 전형, 합계 행
OUTSIDE = (r"정원\s*외|농어촌|기초|수급|차상위|한부모|기회균형|고른기회\s*(?:1|Ⅰ|I)(?!I)|재직자|재외|외국인|북한|장애|졸업자|대졸"
           r"|전문대.*졸|전문대학이상|이상\s*졸업|학사학위|서해|특수교육|순수외국|전공심화|위탁")
SUMMARY = r"합계|소계|총계|전체|^계$|정원\s*내\s*$"

REGION = {"서울": "서울", "인천": "인천", "경기": "경기", "강원": "강원", "충남": "충청", "충북": "충청", "대전": "충청", "세종": "충청",
          "전북": "호남", "전남광주": "호남", "대구": "대구·경북", "경북": "대구·경북", "부산": "부산·울산·경남", "울산": "부산·울산·경남",
          "경남": "부산·울산·경남", "제주": "제주"}
# 학과 ratios.json 에 없는 학교 좌표 (대학 소재지 참고 위치)
PLACES = {
    "강릉영동대학교": ("강릉", 37.777, 128.878), "경인여자대학교": ("인천 계양", 37.539, 126.731), "계원예술대학교": ("의왕", 37.371, 126.968),
    "국립한국농수산대학교": ("전주", 35.823, 127.050), "국제대학교": ("평택", 37.030, 127.043), "김포대학교": ("김포", 37.648, 126.622),
    "동남보건대학교": ("수원", 37.293, 126.986), "동아방송예술대학교": ("안성", 37.034, 127.311), "두원공과대학교": ("안성", 37.040, 127.213),
    "배화여자대학교": ("서울 종로", 37.578, 126.968), "백석문화대학교": ("천안", 36.840, 127.182), "삼육보건대학교": ("서울 동대문", 37.588, 127.078),
    "서울여자간호대학교": ("서울 서대문", 37.580, 126.940), "송곡대학교": ("춘천", 37.880, 127.742), "수원여자대학교": ("수원", 37.268, 126.950),
    "숭의여자대학교": ("서울 중구", 37.556, 126.988), "안산대학교": ("안산", 37.304, 126.873), "연암대학교": ("천안", 36.860, 127.112),
    "울산과학대학교": ("울산", 35.500, 129.431), "장안대학교": ("화성", 37.212, 126.976), "청강문화산업대학교": ("이천", 37.252, 127.480),
    "한국영상대학교": ("세종", 36.531, 127.268), "한림성심대학교": ("춘천", 37.864, 127.758), "한양여자대학교": ("서울 성동", 37.559, 127.045),
    "한국관광대학교": ("이천", 37.198, 127.463),
}
# 진학사·유웨이에 없고 입학처 표를 직접 옮긴 학교 (정원내 일반·특별전형)
MANUAL = {
    "한국관광대학교": ("https://iphak.ktc.ac.kr/page/admissions/competition1", [
        ("스포츠트레이너과", "특별전형", 23, 82), ("카페디저트과", "특별전형", 35, 412), ("호텔조리과", "일반전형", 50, 304),
        ("호텔조리과", "특별전형", 70, 617), ("VISTA(자율전공)학과", "특별전형", 25, 133)]),
}

UNIT = r"(?:과|학과|전공|학부|계열|과정|자율전공|자유전공)(?:\([^)]*\))?$"


def hidden_json(page, name):
    m = re.search(r'id="' + name + r'" value="([^"]*)"', page)
    return json.loads(H.unescape(m.group(1))) if m else {"Columns": [], "Rows": []}


def table(d):
    return [dict(zip(d["Columns"], r)) for r in d["Rows"]]


def colleges():
    """스마트경쟁률의 2027 수시 1차 전문대 목록 (한국폴리텍 제외)."""
    page = U._fetch(SMART)
    syn = {long: uid for _, long, uid in reversed(hidden_json(page, "hdnSynonym")["Synonym"])}
    out = []
    for c in table(hidden_json(page, "hdnResultNow")):
        if c["UnivType"] != 2 or "폴리텍" in c["UnivName"]:
            continue
        m = re.search(r"/Notice/(\d{4})\d{3}/", c["WonseoLink"] or "")
        out.append({"name": c["UnivName"], "province": c["PresidentName"], "url": (c["RatioLink"] or "").strip(),
                    "uid": int(m.group(1)) if m else syn.get(c["UnivName"])})
    return out


def collect(c):
    """학교 하나: 2027 원문 항목과 2026 과거 경쟁률."""
    if c["name"] in MANUAL:
        c["url"], rows = MANUAL[c["name"]]
        c.update(entries=[{"section": t, "label": n, "quota": q, "applied": a} for n, t, q, a in rows], final=True, time="")
    elif c["url"].startswith("http"):
        try:
            page = U._fetch(c["url"])
            c.update(entries=U.parse_entries(page), time=U.parse_time(page) or "",
                     final=bool(U.FINAL_RE.search(re.sub(r"<[^>]+>", " ", page))))
        except Exception as e:  # 한 학교 실패가 전체를 막지 않도록
            print(f"[{c['name']}] 불러오기 실패: {e}")
    if c.get("entries") and c["uid"]:
        try:
            c["past"] = [x for x in table(hidden_json(U._fetch(PAST.format(c["uid"])), "hdnResult"))
                         if x["CategoryDisplayName"] == "수시1차"]
        except Exception as e:
            print(f"[{c['name']}] 2026 과거 경쟁률 실패: {e}")
    return c


def outside(track):
    return bool(re.search(OUTSIDE, track))


def clean(label):
    """원문 학과명에서 소개 문구를 떼고 (표시 이름, 분류·대조에 쓸 학과 이름)을 돌려준다."""
    # 백석문화대: "경찰행정과/…(인문사회자율학부)" → 2026 표기와 같은 "자율학부(인문사회)"
    m = re.search(r"\((\w+)자율학부\)\s*$", label)
    if m:
        return (f"자율학부({m.group(1)})",) * 2
    s = re.sub(r"[●★◈]", "", label)
    s = re.split(r"[□①※\"“]|\[주간\]|\[야간\]", s)[0]
    s = re.sub(r"(\s*-)+\s*$", "", s).strip(" -")
    keep, seen = [], False
    for t in s.split():
        if seen and not (len(t) >= 4 and re.search(UNIT, t)):
            break
        keep.append(t)
        seen = seen or bool(re.search(UNIT, t))
    name = " ".join(keep) or s
    # 계열·학부 머리말 뒤에 학과가 오면 그 학과 이름으로 분류한다
    core = keep[-1] if keep else s
    for i, t in enumerate(keep[:-1]):
        if re.search(r"(계열|학부)$", t):
            core = " ".join(keep[i + 1:])
    return name, core


def key(s):
    s = re.sub(r"\((?:\d년제?|주|야|주간|야간)\)|\d년제|\(\d년\)", "", s)
    return re.sub(r"[\s·ㆍ.,()\[\]\-~/]", "", s)


def track_name(t):
    t = re.sub(r"\d{4}학년도|지원\s*현황|경쟁률\s*현황|경쟁률|정원\s*내|[()]", " ", t)
    t = " ".join(dict.fromkeys(t.split()))   # "일반전형 일반전형" 같은 반복 제거
    return t if 0 < len(t) <= 15 else ""   # 표 제목 전체가 들어온 경우 등은 생략


def field_of(dept, core):
    if re.search(EXCLUDE[dept], core):
        return None
    return next((f for f, rx in DEPTS[dept] if re.search(rx, core)), None)


def group(items, dept):
    """[(학과명, 전형, 모집, 지원)] → 학과별 정원내 합계."""
    g = {}
    for label, track, q, a in items:
        if not q or re.search(SUMMARY, label) or outside(track) or outside(label):
            continue
        name, core = clean(label)
        f = field_of(dept, core)
        if not f:
            continue
        x = g.setdefault(key(core), {"dept": name, "field": f, "quota": 0, "applied": 0, "tracks": []})
        x["quota"] += q
        x["applied"] += a
        x["tracks"].append(track_name(track))
    return g


def adult_only(x):
    """성인학습자·만학도만 뽑는 모집단위 — 고교 졸업생 대상 학과와 비교하지 않는다."""
    return all(re.search(r"성인|만학|평생", t) for t in x["tracks"])


def find_prior(k, g26):
    if k in g26:
        return g26[k]
    c = [v for kk, v in g26.items() if kk and (kk in k or k in kk)]
    return c[0] if len(c) == 1 else None


def add_extra(dept, extra, schools, rows):
    """비공식 자료(national-extra.json)에서 이 학과 분야 행을 더한다."""
    for e in extra:
        picked = [x for x in e["rows"] if x["key"] == dept]
        if not picked:
            continue
        if e["name"] not in schools:
            used = {v["id"] for v in schools.values()}
            sid = f"u{len(schools):02d}"
            while sid in used:
                sid += "x"
            schools[e["name"]] = {"id": sid, "name": e["name"], "region": REGION[e["province"]], "province": e["province"],
                                  "city": e["city"], "url": picked[0]["source"]["url"], "lat": e["lat"], "lon": e["lon"],
                                  "type": "전문대", "unofficial": not any(x["official"] for x in picked),
                                  "time": "최종 마감" if all(x["asOf"].startswith("최종") for x in picked) else ""}
        for x in picked:
            row = {"school": schools[e["name"]]["id"], "dept": x["dept"], "field": x.get("field") or field_of(dept, x["dept"]) or DEPTS[dept][0][0],
                   "track": x["track"], "quota": x["quota"], "applied": x["applied"],
                   "prior": None, "priorQuota": None, "priorApplied": None, "priorUrl": None, "comparable": False, "locked": True,
                   "note": x["note"]}
            if not x["official"]:   # 등록된 경쟁률 원문이 아닌 학교 공지·기사 등: 출처를 함께 둔다
                row["source"] = {"asOf": x["asOf"], **x["source"]}
            pr = x.get("prior")
            if pr:
                row.update(prior=round(pr["applied"] / pr["quota"], 2), priorQuota=pr["quota"], priorApplied=pr["applied"],
                           priorSource={"url": pr.get("url"), "title": pr.get("title")})
                row["comparable"] = 0.67 <= x["quota"] / pr["quota"] <= 1.5
                if not row["comparable"]:
                    row["priorNote"] = "2026 자료와 모집인원·전형 구성이 달라 직접 비교 제외"
            else:
                row["priorNote"] = "2026 같은 기준 자료 없음"
            if not row["note"]:
                del row["note"]
            rows.append(row)


def build(dept, sources, coverage, places, extra):
    local = json.loads((DEPT_DIR / dept / "ratios.json").read_text(encoding="utf-8"))
    schools = {"경민대학교": {**next(s for s in local["schools"] if s["id"] == "km"), "region": "경기"}}
    rows = []
    for r in local["rows"]:
        if r["school"] == "km":   # 경민대 기준·같은 계열 학과: 학교 집계 정원내 학과 전체 (주 전형 값은 쓰지 않음)
            rows.append({**{k: v for k, v in r.items() if k != "main"}, "note": "학교 집계 최종값(정원내 학과 전체, 10.1 24시)"})
    for s in sources:
        g27 = group([(e["label"], e["section"], e["quota"], e["applied"]) for e in s["entries"]], dept)
        g26 = group([(x["MajorName"], x["SelTypeName"], x["Mojip"], x["Jiwon"]) for x in s.get("past", [])], dept)
        for k, x in g27.items():
            if adult_only(x) or any(s["name"] == sn and frag in x["dept"] for sn, frag in DROP[dept]):
                continue
            if s["name"] not in schools:
                sid, city, lat, lon = places[s["name"]]
                used = {v["id"] for v in schools.values()}
                sid = sid or f"n{len(schools):02d}"
                while sid in used:
                    sid += "x"
                schools[s["name"]] = {"id": sid, "name": s["name"], "region": REGION[s["province"]], "province": s["province"],
                                      "city": city, "url": s["url"], "lat": lat, "lon": lon, "type": "전문대",
                                      "time": (s["time"][:10] + " 최종 마감").strip() if s["final"] else s["time"]}
            tracks = x["tracks"]
            row = {"school": schools[s["name"]]["id"], "dept": x["dept"], "field": x["field"],
                   "track": "정원내 합계" + (f" ({len(tracks)}개 전형)" if len(tracks) > 1 else f" ({tracks[0]})" if tracks[0] else ""),
                   "quota": x["quota"], "applied": x["applied"], "prior": None, "priorQuota": None, "priorApplied": None,
                   "priorUrl": None, "comparable": False, "locked": True}
            pr = find_prior(k, g26)
            if pr:
                row.update(prior=round(pr["applied"] / pr["quota"], 2), priorQuota=pr["quota"], priorApplied=pr["applied"],
                           priorUrl=PAST.format(s["uid"]))
                # 모집인원이 크게 바뀐 모집단위는 같은 단위로 보기 어려워 증감 비교에서 뺀다
                row["comparable"] = 0.67 <= x["quota"] / pr["quota"] <= 1.5
                notes = [] if row["comparable"] else [f"모집인원이 크게 바뀜 ({pr['quota']} → {x['quota']}명)"]
                if pr["dept"] != x["dept"]:
                    notes.append(f"2026 이름: {pr['dept']}")
                if notes:
                    row["priorNote"] = " · ".join(notes)
            else:
                row["priorNote"] = "2026 같은 이름 모집단위 없음(신설·개편)" if s.get("past") else "2026 공개 경쟁률 없음"
            rows.append(row)
    add_extra(dept, extra, schools, rows)
    data = {
        "scope": "national",
        "baseline": local["baseline"],
        "finalized": sorted(v["id"] for v in schools.values() if "최종" in (v.get("time") or "")),
        "coverage": coverage,
        "builtAt": datetime.now(KST).strftime("%Y-%m-%d"),
        "schools": list(schools.values()),
        "rows": rows,
    }
    (DEPT_DIR / dept / "ratios-national.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    peers = [r for r in rows if r["school"] != "km"]
    print(f"{dept}: {len(schools) - 1}개교 {len(peers)}개 모집단위 (2026 직접 비교 {sum(r['comparable'] for r in peers)}개)")


def main():
    cs = colleges()
    with ThreadPoolExecutor(12) as ex:
        cs = list(ex.map(collect, cs))
    sources = [c for c in cs if c.get("entries") and c["name"] != "경민대학교"]
    public = {c["name"] for c in sources} | {"경민대학교"}
    extra = [e for e in json.loads(EXTRA_FILE.read_text(encoding="utf-8"))["schools"] if e["rows"]] if EXTRA_FILE.exists() else []
    public |= {e["name"] for e in extra if any(x["official"] for x in e["rows"])}   # 등록 링크에서 직접 읽은 학교
    added = {e["name"] for e in extra} - public
    regions = {}
    for c in cs:
        r = regions.setdefault(REGION.get(c["province"], c["province"]), {"total": 0, "public": 0, "extra": 0, "hidden": []})
        r["total"] += 1
        if c["name"] in public:
            r["public"] += 1
        elif c["name"] in added:
            r["extra"] += 1
        else:
            r["hidden"].append(c["name"])
    coverage = {"total": len(cs), "public": len(public), "extra": len(added), "regions": regions,
                "source": "진학사 스마트경쟁률 2027 수시 1차 전문대 목록(한국폴리텍 제외)"}
    # 좌표: 학과 ratios.json 에 있는 학교는 그 id·좌표를 그대로 쓴다
    places = {n: (None, *v) for n, v in PLACES.items()}
    for f in DEPT_DIR.glob("*/ratios.json"):
        for s in json.loads(f.read_text(encoding="utf-8"))["schools"]:
            places.setdefault(s["name"], (s["id"], s["city"], s["lat"], s["lon"]))
    missing = [c["name"] for c in sources if c["name"] not in places]
    if missing:
        print("좌표 없음 (PLACES 에 추가):", ", ".join(missing))
    for dept in DEPTS:
        build(dept, [c for c in sources if c["name"] in places], coverage, places, extra)


if __name__ == "__main__":
    main()
