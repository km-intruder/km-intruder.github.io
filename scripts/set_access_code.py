"""사이트 접근 코드 설정: assets/gate.js 의 HASH 를 새 코드의 해시로 바꾼다.

    python scripts/set_access_code.py <새 코드>

코드 원문은 어디에도 저장되지 않는다. 바꾼 뒤 커밋·푸시하면 기존 기기도 다시 입력해야 한다.
"""
import hashlib
import re
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parent.parent / "assets" / "gate.js"
SALT = "km-intruder:"

if len(sys.argv) != 2 or len(sys.argv[1]) < 6:
    sys.exit("사용법: python scripts/set_access_code.py <6자 이상 코드>")

digest = hashlib.sha256((SALT + sys.argv[1]).encode("utf-8")).hexdigest()
src = GATE.read_text(encoding="utf-8")
new, n = re.subn(r"var HASH = '[0-9a-f]{64}';", f"var HASH = '{digest}';", src)
if n != 1:
    sys.exit("gate.js 에서 HASH 줄을 찾지 못했습니다.")
GATE.write_text(new, encoding="utf-8")
print("접근 코드를 바꿨습니다. 커밋·푸시하면 적용됩니다.")
