"""수시 경쟁률 공개값 수집기.

admissions-2026/depts/<학과>/ratios*.json (회차별: ratios.json=수시 1차, ratios-susi2.json=수시 2차 …)에
정의된 학교(url)와 학과(rows)를 기준으로
진학어플라이 / 유웨이어플라이 경쟁률 페이지를 읽어 지원인원(applied)과
학교별 기준 시각(time)을 갱신한다. 표준 라이브러리만 사용한다.

    python scripts/update_admissions_ratios.py [--dry-run]
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "admissions-2026"
KST = timezone(timedelta(hours=9))
RATE_RE = re.compile(r"^\d+(?:\.\d+\s*(?::\s*1)?|\s*:\s*1)$")  # "7.74 : 1" 또는 "7.74"
FINAL_RE = re.compile(r"최종\s*(?:경쟁률\s*(?:현황)?\s*입니다|마감\s*(?:현황)?\s*입니다|마감되었습니다)")
NUM_RE = re.compile(r"^[\d,]+$")
OUTSIDE = (r"정원\s*외|농어촌|기초|수급|차상위|한부모|기회균형|고른기회\s*(?:1|Ⅰ|I)(?!I)|재직자|재외|외국인|북한|장애|졸업자|대졸"
           r"|전문대.*졸|전문대학이상|이상\s*졸업|학사학위|서해|특수교육|순수외국|전공심화|위탁")
SUMMARY = r"합계|소계|총계|전체|^계$|정원\s*내\s*$"
TIME_RE = re.compile(
    r"(\d{4})\s*[-./년]\s*(\d{1,2})\s*[-./월]\s*(\d{1,2})\s*일?[^\d<]{0,20}?"
    r"(오전|오후|AM|PM)?\s*(\d{1,2})\s*[:시]\s*(\d{2})?"
)


class RatioTableParser(HTMLParser):
    """제목(h2/h3/h4/caption)으로 전형 구간을 나누고, 표의 각 행을 셀 텍스트로 모은다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section = ""
        self.rows = []  # (section, [cell text...])
        self._heading = None
        self._cells = None
        self._cell = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("h2", "h3", "h4", "caption"):
            self._heading = []
        elif tag == "tr":
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("h2", "h3", "h4", "caption") and self._heading is not None:
            text = clean("".join(self._heading))
            if text:
                self.section = text
            self._heading = None
        elif tag in ("td", "th") and self._cell is not None:
            self._cells.append(clean("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            if self._cells:
                self.rows.append((self.section, self._cells))
            self._cells = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._heading is not None:
            self._heading.append(data)
        if self._cell is not None:
            self._cell.append(data)


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def norm(text):
    """비교용 정규화: 공백·구두점·학제 표기 제거."""
    text = re.sub(r"\((?:\d년제?|주간|야간)\)", "", text)
    return re.sub(r"[\s·ㆍ.,()\[\]\-]", "", text)


def norm_track(text):
    return re.sub(r"경쟁률|현황|전형|특별|학생부|[\s()\[\]·]", "", text).replace("고교", "고")


_PAGES = {}  # 한 번 실행하는 동안 같은 학교 원문은 한 번만 받는다 (학과 파일이 여러 개라서)


def fetch(url):
    if url not in _PAGES:
        _PAGES[url] = _fetch(url)
    return _PAGES[url]


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ratio-updater)"})
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read()
        charset = res.headers.get_content_charset()
    for enc in filter(None, (charset, "utf-8", "cp949")):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def parse_entries(html):
    """경쟁률 셀이 있는 행 → {section, label, quota, applied}."""
    parser = RatioTableParser()
    parser.feed(html)
    entries, last_label = [], ""
    for section, cells in parser.rows:
        idx = next((i for i, c in enumerate(cells) if RATE_RE.match(c)), None)
        if idx is None or idx < 2:
            continue
        quota, applied = cells[idx - 2], cells[idx - 1]
        if not (NUM_RE.match(quota) and NUM_RE.match(applied)):
            continue
        label = " ".join(c for c in cells[: idx - 2] if c and not NUM_RE.match(c)) or last_label
        last_label = label
        entries.append({
            "section": section,
            "label": label,
            "quota": int(quota.replace(",", "")),
            "applied": int(applied.replace(",", "")),
        })
    return entries


def parse_time(html):
    text = re.sub(r"<[^>]+>", " ", html)
    for m in TIME_RE.finditer(text):
        y, mo, d, ampm, h, mi = m.groups()
        h = int(h)
        if ampm in ("오후", "PM") and h < 12:
            h += 12
        if ampm in ("오전", "AM") and h == 12:
            h = 0
        try:
            return datetime(int(y), int(mo), int(d), h, int(mi or 0)).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return None


def inside(entry):
    """정원내 전형의 학과 행인지 (정원외·합계 행 제외)."""
    return not any(re.search(OUTSIDE, entry[k]) for k in ("section", "label")) and not re.search(SUMMARY, entry["section"])


def track_name(section):
    return re.sub(r"\s*경쟁률\s*(현황)?\s*$", "", section).strip() or section


def starts_word(d, label):
    """정규화한 학과 이름 d 가 label 의 어느 단어 첫머리에서 시작하는지."""
    return any(norm(label[m.start():]).startswith(d) for m in re.finditer(r"(?:^|(?<=\s))\S", label))


def dept_hits(dept, entries):
    """학과 이름이 단어 첫머리에서 맞는 정원내 행 (‘건축과’가 ‘실내건축과’에 걸리지 않게). 없으면 부분 일치."""
    d = norm(dept)
    hits = [e for e in entries if inside(e) and d and d in norm(e["label"])]
    return [e for e in hits if starts_word(d, e["label"])] or hits


def sum_row(row, entries):
    """sum: true 행 — 학과 정원내 합계(track '정원내 전체') 또는 한 전형 안의 여러 전공 합계."""
    hits = dept_hits(row["dept"], entries)
    if row.get("track") != "정원내 전체":
        hits = [e for e in hits if norm_track(track_name(e["section"])) == norm_track(row["track"])]
    if not hits:
        return None, None
    main = None
    if row.get("main"):
        m = [e for e in hits if norm_track(track_name(e["section"])) == norm_track(row["main"]["track"])]
        if m:
            main = {"track": row["main"]["track"], "quota": sum(e["quota"] for e in m), "applied": sum(e["applied"] for e in m)}
    return {"quota": sum(e["quota"] for e in hits), "applied": sum(e["applied"] for e in hits)}, main


def match_row(row, entries):
    if row.get("sum"):
        return sum_row(row, entries)[0]
    dept = norm(row["dept"])
    cands = [e for e in entries if dept and dept in norm(e["label"])]
    if len(cands) > 1:  # ‘건축과’ 행이 ‘실내건축과’에도 걸리면 단어 첫머리에서 맞는 쪽
        cands = [e for e in cands if starts_word(dept, e["label"])] or cands
    if len(cands) > 1:
        track = norm_track(row.get("track", ""))
        by_track = [e for e in cands if track and track in norm_track(e["section"])]
        cands = by_track or cands
    if len(cands) > 1:
        cands = [e for e in cands if e["quota"] == row.get("quota")]
    return cands[0] if len(cands) == 1 else None


def update_file(path, dry_run):
    print(f"== {path.name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    before = {k: v for k, v in data.items() if k != "checkedAt"}
    before = json.dumps(before, ensure_ascii=False, sort_keys=True)
    prev_live = set(data.get("live", []))
    rows_by_school = {}
    for row in data["rows"]:
        rows_by_school.setdefault(row["school"], []).append(row)

    changed, live = 0, []
    for school in data["schools"]:
        rows = rows_by_school.get(school["id"], [])
        if not rows or not school.get("url"):
            continue
        try:
            html = fetch(school["url"])
        except Exception as e:  # 한 학교 실패가 전체를 막지 않도록
            print(f"[{school['name']}] 불러오기 실패: {e}")
            if school["id"] in prev_live:  # 일시 장애로 대조 목록이 흔들리지 않게 유지
                live.append(school["id"])
            continue
        entries = parse_entries(html)
        if school["id"] == "km":
            entries = km_entries(entries)
        page_time = parse_time(html)
        is_final = bool(FINAL_RE.search(re.sub(r"<[^>]+>", " ", html)))
        if "최종" not in (school.get("time") or ""):
            if is_final:
                school["time"] = (page_time or datetime.now(KST).strftime("%Y-%m-%d"))[:10] + " 최종 마감"
            elif page_time:
                school["time"] = page_time
        if is_final and school["id"] not in data.setdefault("finalized", []):
            print(f"[{school['name']}] 최종 경쟁률 표시 확인")
            data["finalized"].append(school["id"])
        if any(match_row(row, entries) for row in rows):
            live.append(school["id"])
        for row in rows:
            if row.get("locked"):  # 학과에서 확인한 최종값은 원문 수집으로 덮어쓰지 않음
                continue
            hit = match_row(row, entries)
            if not hit:
                print(f"[{school['name']}] {row['dept']} ({row.get('track')}) - 일치 행 없음, 기존값 유지")
                continue
            if (hit["quota"], hit["applied"]) != (row["quota"], row["applied"]):
                print(f"[{school['name']}] {row['dept']}: {row['quota']}/{row['applied']} → {hit['quota']}/{hit['applied']}")
                row["quota"], row["applied"] = hit["quota"], hit["applied"]
                changed += 1
            main = sum_row(row, entries)[1] if row.get("sum") else None
            if main and main != row.get("main"):
                row["main"] = main

    data["live"] = live
    print(f"변경된 학과: {changed}개")
    after = json.dumps({k: v for k, v in data.items() if k != "checkedAt"}, ensure_ascii=False, sort_keys=True)
    if after == before:
        print("변경 없음 - 파일을 쓰지 않습니다.")
        return
    # checkedAt 은 공개값이 실제로 바뀐 시각 (매 실행마다 커밋이 쌓이지 않도록)
    data["checkedAt"] = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    if not dry_run:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ── 경민대 전체(학교 화면) 수시 2차 이후 회차: 진학어플라이 공개값의 학과별 정원내 전형 ──
SCHOOL_TRACKS = [(r"특별인재", "talent"), (r"성인|독자|특기", "special"), (r"특성화", "vocational"),
                 (r"일반고", "regular"), (r"일반", "general")]


def km_entries(entries):
    """경민대 원문: 학과 칸이 rowspan 으로 묶인 다음 줄(예: 레포츠과 '야구')은 학과명이 빠지므로 앞 줄 학과를 붙인다."""
    out, prev = [], None
    for e in entries:
        head = e["label"].split(" ")[0]
        if re.search(r"(과|학부|전공)$", head):
            prev = (e["section"], head)
        elif prev and prev[0] == e["section"] and not re.search(SUMMARY + r"|총계", e["label"]):
            e = {**e, "label": prev[1] + " " + e["label"]}
        out.append(e)
    return out


def school_depts(entries, names):
    """경민대 경쟁률 원문 → {학과명: {tracks, quota, applied}}. 학과명은 names 중 가장 길게 맞는 것,
    없으면 라벨 첫 단어(새로 생긴 모집단위)."""
    out = {}
    for e in km_entries(entries):
        if not inside(e) or re.search(r"^전형별", e["section"]) or re.search(SUMMARY + r"|총계", e["label"]):
            continue
        cands = [n for n in names if norm(e["label"]).startswith(norm(n))]
        name = max(cands, key=len) if cands else e["label"].split(" ")[0]
        key = next((k for p, k in SCHOOL_TRACKS if re.search(p, e["section"])), "special")
        d = out.setdefault(name, {"tracks": {}, "quota": 0, "applied": 0})
        q, a = d["tracks"].get(key, [0, 0])
        d["tracks"][key] = [q + e["quota"], a + e["applied"]]
        d["quota"] += e["quota"]
        d["applied"] += e["applied"]
    return out


def school_totals(data):
    day = [d for d in data["depts"] if not d.get("adult")]
    tot = lambda ds: {"quota": sum(d["quota"] for d in ds), "applied": sum(d["applied"] for d in ds),
                      "prevApplied": sum(d.get("prevApplied") or 0 for d in ds)}
    data["total"] = {**tot(data["depts"]), "day": tot(day)}


def update_school(path, dry_run):
    """school/susi2-2027.json: 모집·지원·전형별 값만 원문으로 갱신 (2026 값·계열 등은 생성기가 정한 그대로)."""
    print(f"== {path.relative_to(DATA_DIR)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("locked"):  # 학교 집계표 최종값으로 바꾼 파일은 원문 수집으로 덮어쓰지 않음
        print("최종값 잠금 - 건너뜁니다.")
        return
    before = json.dumps(data, ensure_ascii=False, sort_keys=True)
    try:
        html = fetch(data["url"])
    except Exception as e:
        print(f"[경민대학교] 불러오기 실패: {e}")
        return
    live = school_depts(parse_entries(html), [d["name"] for d in data["depts"]])
    for d in data["depts"]:
        v = live.get(d["name"])
        if v:
            d.update(v)
    t = parse_time(html)
    final = bool(FINAL_RE.search(re.sub(r"<[^>]+>", " ", html)))
    data["final"] = final
    if t:
        data["basis"] = f"{t} 기준 (진학어플라이 공개값{', 최종' if final else ', 접수 중'})"
    school_totals(data)
    if json.dumps(data, ensure_ascii=False, sort_keys=True) == before:
        print("변경 없음 - 파일을 쓰지 않습니다.")
        return
    print(f"총 지원 {data['total']['applied']}명 · {data['basis']}")
    if not dry_run:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    dry_run = "--dry-run" in sys.argv
    for path in sorted(DATA_DIR.glob("depts/*/ratios*.json")):
        if path.name == "ratios-national.json":  # 전국 비교는 마감 뒤 한 번 만드는 자료 (build_national_ratios.py)
            continue
        update_file(path, dry_run)
    for path in sorted(DATA_DIR.glob("school/susi[2-9]-*.json")):  # 수시 1차는 학교 집계표라 수동
        update_school(path, dry_run)


if __name__ == "__main__":
    main()
