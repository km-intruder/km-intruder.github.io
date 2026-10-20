"""사이트 접근 코드 설정: assets/gate.js 의 해시를 새 코드의 해시로 바꾼다.

    python scripts/set_access_code.py <새 코드>            사이트 전체 코드
    python scripts/set_access_code.py --share <새 코드>    수시 분석 공유 코드 (admissions-2026 분석 화면만)
    python scripts/set_access_code.py --share --off        공유 코드 끄기

코드 원문은 어디에도 저장되지 않는다. 바꾼 뒤 커밋·푸시하면 기존 기기도 다시 입력해야 한다.
"""
import hashlib
import re
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / "assets" / "gate.js"
SALT = "km-intruder:"

args = sys.argv[1:]
share = "--share" in args
args = [a for a in args if a != "--share"]
src = GATE.read_text(encoding="utf-8")
if share and args == ["--off"]:
    new, n = re.subn(r"var SHARE_HASH = '[0-9a-f]*';", "var SHARE_HASH = '';", src)
    msg = "수시 분석 공유 코드를 껐습니다."
else:
    if len(args) != 1 or len(args[0]) < 6:
        sys.exit("사용법: python scripts/set_access_code.py [--share] <6자 이상 코드>")
    digest = hashlib.sha256((SALT + args[0]).encode("utf-8")).hexdigest()
    name = "SHARE_HASH" if share else "HASH"
    new, n = re.subn(rf"var {name} = '[0-9a-f]*';", f"var {name} = '{digest}';", src)
    msg = ("수시 분석 공유 코드" if share else "접근 코드") + "를 바꿨습니다. 커밋·푸시하면 적용됩니다."
if n != 1:
    sys.exit("gate.js 에서 해시 줄을 찾지 못했습니다.")
GATE.write_text(new, encoding="utf-8")
print(msg)
