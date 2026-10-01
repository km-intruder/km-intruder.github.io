"""수시 경쟁률 공개값 수집기.

admissions-2026/ratios*.json (회차별: ratios.json=수시 1차, ratios-susi2.json=수시 2차 …)에
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


def fetch(url):
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


def match_row(row, entries):
    dept = norm(row["dept"])
    cands = [e for e in entries if dept and dept in norm(e["label"])]
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


def main():
    dry_run = "--dry-run" in sys.argv
    for path in sorted(DATA_DIR.glob("ratios*.json")):
        update_file(path, dry_run)


if __name__ == "__main__":
    main()
