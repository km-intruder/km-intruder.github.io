"""학과별 입시 추이(2023~2027학년도 수시 1차) 파일 생성기.

admissions-2026/depts/<학과>/trends.json 을 학과마다 만든다.

- 비교 대상: 학과 ratios.json 의 전문대 모집단위(수도권 비교군) + ratios-national.json 모집단위(공식·비공식)
- 2023~2026: 진학사 스마트경쟁률 과거 경쟁률(PastRatioUniv)
- 2027: 경민대는 학교 집계(school/susi1-2027.json), 다른 학교는 경쟁률 원문
- 모든 해를 '수시 1차 정원내 전형 합계'로 묶는다 (build_national_ratios.py 와 같은 기준).
- 주 전형 경쟁률(일반고, 없으면 일반전형)을 해마다 따로 둔다 — 학교마다 전형 구성이 달라도 같은 기준으로 비교하려고.
- 진학사 과거값이 없는 학교(비공식 자료 학교 등)는 national-extra.json 의 2027·2026 값과
  전문대학포털(전문대교협) 전년도 입시결과(학과 모집인원 + 전형별 경쟁률)로 채우고 해마다 unofficial 로 표시한다.
  진학사 과거값이 있는 해(공식)를 먼저 쓰고, 없는 해는 포털 '대학별 전형방법'의 전형별 모집인원(입학전형 시행계획)과
  '전년도 입시결과'의 전형별 경쟁률을 곱해 지원자를 계산한다(정원내 전형 합계, 주·야 구분).

    python scripts/build_trends.py
"""
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import build_national_ratios as N
import update_admissions_ratios as U

ROOT = N.DEPT_DIR.parent
YEARS = [2023, 2024, 2025, 2026, 2027]
PAST_YEARS = YEARS[:-1]
PAST = "https://apply.jinhakapply.com/SmartRatio/PastRatioUniv?univid={}&year={}&category=1"
PORTAL = "https://www.procollege.kr/web/entrance/webEntrancePreResult.do"
PORTAL_TITLE = "전문대학포털(한국전문대학교육협의회) 전년도 입시결과"
PLAN = "https://www.procollege.kr/web/entrance/webEntranceTypeGradeModel.do"
PLAN_TITLE = "전문대학포털 대학별 전형방법(전형별 모집인원)"
PLAN_ROW = re.compile(r"<tr>\s*<td>([^<]*)</td>\s*<td><a[^>]*fn_goLink[^>]*>([^<]*)</a></td>\s*<td>\s*([^<]*?)\s*</td>\s*<td>\s*"
                      r"<span[^>]*>([^<]*)</span>\s*</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>")
GENERAL_HS = r"일반고|일반계고|인문계고"
GENERAL = r"일반전형|^일반$|일반_일반"
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
    ("서영대학교(파주)", "조리제과제빵과(주간)"): ["호텔외식조리과"],
    ("서영대학교(파주)", "조리제과제빵과(야간)"): ["호텔외식조리과(야)"],
}


def base_name(s):
    """대조용: 괄호 설명·학제 표기·끝의 과/학과/전공을 뗀 이름."""
    # 끝의 괄호 설명만 뗀다 — '생활스포츠(족구)과'처럼 이름 가운데 괄호는 다른 모집단위라 남긴다
    s = re.sub(r"(\([^)]*\)|\[[^\]]*\])+$", "", N.clean(s)[1].strip())
    s = re.sub(r"(과|학과)-\S+$", lambda m: m.group(1), s)   # 경민대 '태권도외교과-시범', '레포츠과-축구' 같은 세부 모집단위는 학과로 합친다
    s = N.key(s)
    return re.sub(r"(학과|학부|과|전공|계열)$", "", s)


def main_track(rows):
    """[(전형, 모집, 지원)] → 주 전형(일반고, 없으면 일반전형) 이름·경쟁률."""
    for name, rx in (("일반고", GENERAL_HS), ("일반전형", GENERAL)):
        # '일반_특별전형'처럼 일반 계열 안의 특별전형은 일반전형으로 보지 않는다
        hit = [(q, a) for tr, q, a in rows if re.search(rx, tr) and (name == "일반고" or "특별" not in tr)]
        q = sum(h[0] for h in hit)
        if q:
            return name, round(sum(h[1] for h in hit) / q, 2)
    return None, None


def main_rate_text(track, quota, applied, derived="", note=""):
    """비공식 행의 전형 설명·계산식·메모(조사 자료)에서 주 전형 경쟁률."""
    for name, rx in (("일반고", r"일반고(?:/학생부|교)?"), ("일반전형", r"일반전형|일반(?![고_·])")):
        m = re.search(rf"(?:{rx})\s*\(?\s*(\d+)\s*/\s*(\d+)", track)
        if m and int(m.group(1)):
            return name, round(int(m.group(2)) / int(m.group(1)), 2)
        m = re.search(rf"(?:{rx})\s*\(?\s*(\d+)\s*명?\s*,?\s*(\d+(?:\.\d+)?)\s*:\s*1", track)
        if m:
            return name, float(m.group(2))
    # '정원내 일반전형(다른 정원내 전형 모집 없음)'처럼 일반전형 하나뿐이면 합계 경쟁률이 곧 주 전형 경쟁률
    m = re.search(r"일반(고|전형)?\s*\([^)]*(모집 없음|유일|다른 정원내)", track)
    if m and quota:
        return ("일반고" if m.group(1) == "고" else "일반전형"), round(applied / quota, 2)
    # 계산식 '일반고 45×6.4=288' / 메모 '전형별: 일반고 14.75'
    for name, rx in (("일반고", r"일반고"), ("일반전형", r"일반(?:전형)?(?![고_·])")):
        m = re.search(rf"(?:{rx})\s*(\d+)\s*[×x]\s*(\d+(?:\.\d+)?)", derived)
        if m:
            return name, float(m.group(2))
        m = re.search(rf"전형별:?\s*(?:{rx})\s*(\d+(?:\.\d+)?)", note)
        if m:
            return name, float(m.group(1))
    # 메모 '전형별 10/75, 9/78 …' 또는 '주간 8/61, 4/57 · 야간 4/5, 5/7' — 전형 설명에서 일반고가 맨 앞이면 각 묶음의 첫 값
    first = re.search(r"\((?:주간\s*)?(일반고|일반전형|일반)\+", track)
    if first:
        pairs = [re.findall(r"(\d+)\s*/\s*(\d+)", g) for g in re.split(r"·", note)]
        pairs = [p[0] for p in pairs if p]
        q = sum(int(a) for a, _ in pairs)
        if q:
            return ("일반고" if first.group(1) == "일반고" else "일반전형"), round(sum(int(b) for _, b in pairs) / q, 2)
    return None, None


def total(rows, names):
    """한 해 원문 행 [(학과명, 전형, 모집, 지원)] 에서 names 에 맞는 정원내 합계와 주 전형 경쟁률."""
    want = {base_name(n) for n in names}
    # 주간·야간을 따로 모집하는 학과: 이름에 주/야가 있으면 그 과정 행만
    shift = "야" if re.search(r"\(야|야간", names[0]) else "주" if re.search(r"\(주|주간", names[0]) else None
    rows = [(label, mq, ma, base_name(label), track) for label, track, mq, ma in rows
            if mq and not re.search(N.SUMMARY, label) and not N.outside(track) and not N.outside(label)
            and (shift != "야" or re.search(r"\(야|야간", label)) and (shift != "주" or not re.search(r"\(야|야간", label))]
    # 같은 이름이 있으면 그것만, 없을 때만 이름 일부 일치(개명·학부 머리말)를 쓴다
    picked = [r for r in rows if r[3] in want] or \
             [r for r in rows if any(w and len(w) >= 3 and (w in r[3] or r[3] in w) for w in want)]
    if len({r[3] for r in picked}) > 1 and not any(r[3] in want for r in picked):
        return None   # 이름 일부가 여러 모집단위에 걸리면 같은 단위인지 알 수 없어 비운다
    if not picked:
        return None
    mt, mr = main_track([(r[4], r[1], r[2]) for r in picked])
    out = {"quota": sum(r[1] for r in picked), "applied": sum(r[2] for r in picked),
           "name": " · ".join(sorted({N.clean(r[0])[0] for r in picked}))}
    if mr is not None:
        out.update(mainTrack=mt, mainRate=mr)
    return out


def past_rows(uid, year):
    page = U._fetch(PAST.format(uid, year))
    return [(x["MajorName"], x["SelTypeName"], x["Mojip"], x["Jiwon"])
            for x in N.table(N.hidden_json(page, "hdnResult")) if x["CategoryDisplayName"] == "수시1차"]


class Portal:
    """전문대학포털 전년도 입시결과 검색 (학교 이름·학년도)."""

    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0")]
        self.op.open(PORTAL, timeout=40).read()

    def rows(self, school, year):
        """[(지역, 학과, 모집시기별 입학정원, 전형명, 경쟁률, 주/야)] — 수시 1차만."""
        name, out, page = school.split("(")[0], [], 1
        while True:
            data = urllib.parse.urlencode({"cate": "1", "univName": name, "sel_1": str(year), "sel_2": "", "sel_3": "",
                                           "sel_4": "", "pageUnit": "100", "pageIndex": str(page), "codeyear": "2026",
                                           "schOrderField": "korname", "schOrderBy": "asc"}).encode()
            t = self.op.open(urllib.request.Request(PORTAL, data=data), timeout=60).read().decode("utf-8", "replace")
            i = t.find("<tbody")
            j = t.find("</tbody>", i)
            rows = [[re.sub(r"<[^>]+>|\s+", " ", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
                    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t[i:j], re.S)]
            rows = [r for r in rows if len(r) > 10]
            out += rows
            if len(rows) < 100:
                break
            page += 1
        res = []
        for r in out:
            if r[1] != name or not r[2].startswith("수시1"):
                continue
            try:
                res.append((r[0], r[3], int(r[4] or 0), r[7] or r[6], float(r[10]), "야" if "야" in r[5] else "주"))
            except ValueError:
                continue
        return res


    def plan(self, school, year):
        """[(지역, 전형구분, 전형명, 학과, 주간 인원, 야간 인원)] — 수시 1차 입학전형 시행계획."""
        name, out, page = school.split("(")[0], [], 1
        while True:
            data = urllib.parse.urlencode({"cate": "1", "univName": name, "sel_1": str(year), "sel_2": "11", "sel_3": "", "sel_4": "",
                                           "pageUnit": "100", "pageIndex": str(page), "codeyear": str(year), "searchY": "Y",
                                           "schOrderField": "korname", "schOrderBy": "asc"}).encode()
            t = self.op.open(urllib.request.Request(PLAN, data=data), timeout=60).read().decode("utf-8", "replace")
            rows = PLAN_ROW.findall(t)
            out += rows
            if len(rows) < 100:
                break
            page += 1
        num = lambda s: int(s) if s.strip().isdigit() else 0
        return [(r[0], r[2], r[3], r[4], num(r[7]), num(r[8])) for r in out if r[1] == name and r[6].startswith("수시1")]


def track_key(s):
    return re.sub(r"[\s\d·Ⅰ-Ⅹ()]", "", s).replace("기준", "")


def portal_year(rows, province, names, plan=()):
    """포털 한 해 행에서 모집단위 값: 주 전형 경쟁률, 정원내 전형이 하나뿐이면 지원자(모집인원 × 경쟁률)."""
    want = {base_name(n) for n in names}
    shift = "야" if re.search(r"\(야|야간", names[0]) else "주" if re.search(r"\(주|주간", names[0]) else None
    rows = [r for r in rows if (r[0] in province or province in r[0]) and not N.outside(r[3]) and (not shift or r[5] == shift)]
    picked = [r for r in rows if base_name(r[1]) in want] or \
             [r for r in rows if any(w and len(w) >= 3 and (w in base_name(r[1]) or base_name(r[1]) in w) for w in want)]
    if not picked or (len({base_name(r[1]) for r in picked}) > 1 and not any(base_name(r[1]) in want for r in picked)):
        return None
    seats = max(r[2] for r in picked)
    tracks = {}
    for r in picked:
        tracks.setdefault(r[3], r[4])
    out = {"name": picked[0][1], "unofficial": True,
           "tracks": f"학과 모집 {seats}명 · " + " · ".join(f"{k} {v:g}" for k, v in tracks.items()),
           "source": {"kind": "portal", "title": PORTAL_TITLE, "url": PORTAL}}
    for mt, rx in (("일반고", GENERAL_HS), ("일반전형", GENERAL)):
        hit = [v for k, v in tracks.items() if re.search(rx, k)]
        if hit:
            out.update(mainTrack=mt, mainRate=hit[0])
            break
    # 전형별 모집인원(시행계획) × 전형별 경쟁률(입시결과) → 정원내 지원자 합계
    unit = base_name(picked[0][1])
    prow = [p for p in plan if (p[0] in province or province in p[0]) and base_name(p[3]) == unit and not N.outside(p[2])]
    parts, miss = [], []
    for p in prow:
        seat = (p[5] if shift == "야" else p[4] if shift == "주" else p[4] + p[5])
        if not seat:
            continue
        rate = next((v for k, v in tracks.items() if track_key(k) and (track_key(k).startswith(track_key(p[2])) or track_key(p[2]).startswith(track_key(k)))), None)
        if rate is None:
            miss.append(f"{p[2]} {seat}명")
            continue
        parts.append((p[2], seat, rate))
    if parts:
        q = sum(s for _, s, _ in parts)
        out.update(quota=q, applied=round(sum(s * r for _, s, r in parts)),
                   derived="지원자 = 전형별 모집인원 × 전형별 경쟁률: " + ", ".join(f"{k} {s}×{r:g}" for k, s, r in parts)
                   + (f" (경쟁률 없는 전형 제외: {', '.join(miss)})" if miss else "")
                   + " — 경쟁률이 소수 한두 자리라 몇 명 차이 날 수 있음",
                   planSource={"title": PLAN_TITLE, "url": PLAN})
    elif len(tracks) == 1 and seats:
        rate = next(iter(tracks.values()))
        out.update(quota=seats, applied=round(seats * rate),
                   derived=f"정원내 전형이 하나뿐이라 지원자 = 학과 모집인원 {seats} × 경쟁률 {rate:g}")
    return out


def extra_units(dept, extra, units):
    """national-extra.json 의 이 학과 분야 모집단위 (진학사 과거값이 없는 학교)."""
    out = []
    for e in extra:
        for x in e["rows"]:
            if x["key"] != dept:
                continue
            k = (e["name"], base_name(x["dept"]))
            if any((u["schoolName"], base_name(u["dept"])) == k for u in units + out):
                continue
            out.append({"school": "x:" + e["name"], "schoolName": e["name"], "region": N.REGION[e["province"]],
                        "province": e["province"], "dept": x["dept"], "isBase": False, "isKm": False, "scope": "전국", "extra": x})
    return out


def extra_series(u, prows, plans, past, cs):
    x = u["extra"]
    s27 = {"quota": x["quota"], "applied": x["applied"], "name": x["dept"], "unofficial": not x["official"]}
    if not x["official"]:
        s27["source"] = {k: x["source"].get(k) for k in ("kind", "title", "url", "date")}
    if x["source"].get("derived"):
        s27["derived"] = x["source"]["derived"]
    mt, mr = main_rate_text(x["track"], x["quota"], x["applied"], x["source"].get("derived") or "", x.get("note") or "")
    if mr is not None:
        s27.update(mainTrack=mt, mainRate=mr)
    series = {"2027": s27}
    p = x.get("prior")
    if p and p.get("quota") and p.get("applied") is not None:
        s26 = {"quota": p["quota"], "applied": p["applied"], "name": x["dept"], "unofficial": True,
               "source": {"kind": "school-notice", "title": p.get("title") or "", "url": p.get("url") or ""}}
        mt, mr = main_rate_text(p.get("track") or "", p["quota"], p["applied"])
        if mr is not None:
            s26.update(mainTrack=mt, mainRate=mr)
        series["2026"] = s26
    names = [u["dept"]] + ALIAS.get((u["schoolName"], u["dept"]), [])
    for y in PAST_YEARS:
        if str(y) not in series and cs.get(u["schoolName"], {}).get("uid"):
            v = total(past.get((u["schoolName"], y), []), names)   # 진학사 과거 경쟁률이 공개된 해는 공식값
            if v:
                series[str(y)] = v
                continue
        v = portal_year(prows.get((u["schoolName"], y), []), u["province"], names, plans.get((u["schoolName"], y), []))
        if not v:
            continue
        if str(y) in series:   # 학교 자료가 있는 해는 포털에서 주 전형 경쟁률만 보탠다
            if "mainRate" not in series[str(y)] and "mainRate" in v:
                series[str(y)].update(mainTrack=v["mainTrack"], mainRate=v["mainRate"], mainSource="portal")
            continue
        series[str(y)] = v
    return {y: series[y] for y in sorted(series)}


def main():
    cs = {c["name"]: c for c in N.colleges()}
    km_total = {d["id"]: d for d in json.loads((ROOT / "school" / "susi1-2027.json").read_text(encoding="utf-8"))["depts"] if d.get("id")}
    # 학과별 비교 모집단위 모으기
    plan = {}
    extra = json.loads(N.EXTRA_FILE.read_text(encoding="utf-8"))["schools"] if N.EXTRA_FILE.exists() else []
    # 조사 자료(national-extra.json)에서 온 모집단위는 진학사 과거값이 없어 포털로 채우는 경로로 보낸다
    extra_keys = {(e["name"], base_name(x["dept"])) for e in extra for x in e["rows"]}
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
                if name == "ratios-national.json" and (s["name"], base_name(dname)) in extra_keys:
                    continue
                k = (s["name"], base_name(dname))
                if any((u["schoolName"], base_name(u["dept"])) == k for u in units):
                    continue
                units.append({"school": r["school"] if name == "ratios.json" else s["id"], "schoolName": s["name"],
                              "region": s["region"], "dept": dname, "isBase": r["school"] == "km" and dname == data["baseline"]["dept"],
                              "isKm": r["school"] == "km", "scope": "수도권" if name == "ratios.json" else "전국"})
        # 비공식 자료 학교는 전국 비교가 있는 학과만 (national-extra.json 의 분야 key = 학과 id)
        plan[dept] = units + (extra_units(dept, extra, units) if (f.parent / "ratios-national.json").exists() else [])

    # 과거 원문(학교·연도별 한 번씩)과 2027 원문
    need = {u["schoolName"] for us in plan.values() for u in us if "extra" not in u}
    jobs = [(n, y) for n in need for y in PAST_YEARS if cs[n]["uid"]]
    with ThreadPoolExecutor(12) as ex:
        past = dict(zip(jobs, ex.map(lambda j: past_rows(cs[j[0]]["uid"], j[1]), jobs)))
        now = dict(zip(need, ex.map(lambda n: N.collect(dict(cs[n])).get("entries", []), need)))
    portal = Portal()
    pjobs = sorted({(u["schoolName"], y) for us in plan.values() for u in us if "extra" in u for y in PAST_YEARS})
    with ThreadPoolExecutor(4) as ex:
        prows = dict(zip(pjobs, ex.map(lambda j: portal.rows(*j), pjobs)))
        plans = dict(zip(pjobs, ex.map(lambda j: portal.plan(*j), pjobs)))
    # 비공식 경로 학교도 진학사 과거 경쟁률이 공개된 해가 있으면 공식값으로 쓴다
    xjobs = sorted({(u["schoolName"], y) for us in plan.values() for u in us if "extra" in u
                    for y in PAST_YEARS if cs.get(u["schoolName"], {}).get("uid")} - set(past))
    with ThreadPoolExecutor(12) as ex:
        past.update(zip(xjobs, ex.map(lambda j: past_rows(cs[j[0]]["uid"], j[1]), xjobs)))

    for dept, units in plan.items():
        out = []
        for u in units:
            names = [u["dept"]] + ALIAS.get((u["schoolName"], u["dept"]), [])
            series = {}
            if "extra" in u:
                series = extra_series(u, prows, plans, past, cs)
                if len(series) < 2:
                    print(f"  [{dept}] 자료 부족으로 뺌: {u['schoolName']} {u['dept']} ({', '.join(series) or '없음'})")
                    continue
                out.append({**{k: u[k] for k in ("school", "schoolName", "region", "dept", "isBase", "isKm", "scope")},
                            "unofficial": not u["extra"]["official"], "series": series})
                continue
            for y in PAST_YEARS:
                v = total(past.get((u["schoolName"], y), []), names)
                if v:
                    series[str(y)] = v
            if u["isKm"]:
                d = next((d for d in km_total.values() if base_name(d["name"]) == base_name(u["dept"])), None)
                if d:   # 경민대 2027: 학교 집계 최종(정원내 학과 전체)
                    series["2027"] = {"quota": d["quota"], "applied": d["applied"], "name": d["name"], "source": "학교 집계"}
                    for mt, k in (("일반고", "regular"), ("일반전형", "general")):
                        if k in d["tracks"] and d["tracks"][k][0]:
                            q, a = d["tracks"][k]
                            series["2027"].update(mainTrack=mt, mainRate=round(a / q, 2))
                            break
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
                "mainBasis": "주 전형 경쟁률 = 일반고 전형, 없으면 일반전형",
                "sources": {"past": "진학사 스마트경쟁률 과거 경쟁률(2023~2026학년도 수시 1차)",
                            "now": "2027: 경민대 학교 집계, 다른 학교 경쟁률 원문(진학어플라이·유웨이어플라이·학교 입학처)",
                            "unofficial": "비공식: 학교 공지·입학처 화면 등 조사 자료, 그리고 " + PLAN_TITLE + " × " + PORTAL_TITLE
                                          + "의 전형별 경쟁률로 계산한 지원자 (진학사에 공개된 해는 공식값)"},
                "units": out}
        (N.DEPT_DIR / dept / "trends.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        base = next((x for x in out if x["isBase"]), None)
        print(f"{dept}: {len(out)}개 모집단위 · 경민대 기준 {'/'.join(base['series']) if base else '없음'}")


if __name__ == "__main__":
    main()
