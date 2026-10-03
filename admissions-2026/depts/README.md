# 학과 추가 방법

학과마다 폴더 하나를 둡니다. 공통 화면 코드(`../*.html`, `common.js`, `nav.js`, `board.js`)는 고치지 않습니다.

```
depts/<학과 id>/
├─ dept.json        학과 이름·분야·교육과정 비교 데이터
├─ ratios.json      수시 1차 경쟁률 (회차가 늘면 ratios-susi2.json …)
└─ posts/            전문대·산업 현황 게시판 (boards: true 인 학과만, 현재 software)
```

## 절차

1. `depts/software/`를 본보기로 위 파일을 만든다.
2. `../nav.js`의 `DEPTS`에 한 줄 추가:
   `{ id: 'hotel-culinary', name: '호텔조리과', boards: false, rounds: [{ id: 'susi1', label: '수시 1차', file: 'ratios.json' }] }`
3. 확인: `admissions-dashboard.html?dept=<학과 id>`. 학과가 둘 이상이면 탭 오른쪽에 학과 선택 메뉴가 나타난다.

경쟁률 수집(`scripts/update_admissions_ratios.py`)은 `depts/*/`를 모두 돌기 때문에 따로 등록할 필요가 없다. 매주 게시(전문대·산업 현황)는 지능형소프트웨어과만 한다.

## dept.json

| 키 | 뜻 | software 예 |
|---|---|---|
| `id`, `name` | 학과 id, 경민대 학과명 | `software`, `지능형소프트웨어과` |
| `shortName` | 짧은 이름 | `지능형SW` |
| `fieldLabel` | 비교 계열 이름 (제목에 쓰임) | `SW·AI 계열` |
| `fields` | 03 표 분야 필터 = ratios.json 각 행의 `field` 값 | `["SW","AI",…]` |
| `familyLabel` | 경민대 안 같은 계열 묶음 (진단 표) | `IT 계열` |
| `renameNote` | 학과명 변경 안내 (없으면 `""`) | `학과명 변경(… → …)` |
| `industryLabel` | 산업 현황 탭 설명 | `SW·AI 산업과 채용 시장, 관련 정책 동향` |
| `curriculum` | 교육과정 비교: `axes`(교육축), `km`(경민대 학과), `schools`(비교 전문대), `references`(참고 4년제), `context`, `community` | software 참고 |

## ratios.json

- `baseline`: `{ "school": "km", "dept": "<경민대 기준 모집단위 이름>" }`
- `schools`: 학교 id·이름·`region`(서울/경기 북부/경기 남부/경기 서부/인천)·`city`·`type`(전문대/4년제)·경쟁률 원문 `url`·`lat`/`lon`
- `rows`: 모집단위별 `school`, `dept`, `field`, `track`, `quota`, `applied`, 2026 대비용 `prior`·`priorQuota`·`priorApplied`·`priorUrl`, 직접 비교 가능 여부 `comparable`
- 경민대의 같은 학교 다른 학과 행은 비교군에서 자동 제외되고 진단 표의 “경민대 ○○ 계열 합계”에만 쓰인다
- 학과에서 받은 확정값은 `"locked": true`로 두면 자동 수집이 덮어쓰지 않는다
