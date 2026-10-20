# 학과 추가 방법

학과마다 폴더 하나를 둡니다. 공통 화면 코드(`../*.html`, `common.js`, `nav.js`, `board.js`)는 고치지 않습니다.

```
depts/<학과 id>/
├─ dept.json        학과 이름·분야·교육과정 비교 데이터
├─ ratios.json      수시 1차 경쟁률 (회차가 늘면 ratios-susi2.json …)
├─ ratios-national.json  수시 1차 전국 공개 전문대 비교 (지원 감소 학과만, 아래 참고)
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

## 전국 비교 (ratios-national.json)

2026 대비 지원자가 줄어든 학과(카페베이커리·호텔조리·지능형SW·레포츠·태권도외교·자유전공)는 `nav.js`의 `S1N` 회차로 ‘수시 1차 전국’ 탭이 붙는다. 같은 `admissions-dashboard.html`을 `scope: 'national'`로 보여 준다.

- 만들기: `python scripts/build_national_ratios.py` (진학사 스마트경쟁률 전문대 목록 → 각 학교 경쟁률 원문 + 2026 진학사 과거 경쟁률)
- 모든 모집단위는 정원내 전형 합계. 경민대 행은 그 학과 `ratios.json`의 학교 집계값을 쓴다
- 경쟁률을 공개하지 않은 지방 전문대가 많아 비교 학교는 대부분 수도권이다. 빠진 학교는 `coverage`에 권역별로 남는다
- 비교 학과 고르기: 스크립트의 `DEPTS`(키워드)·`EXCLUDE`·`DROP`. 매시 수집기는 이 파일을 건드리지 않는다
- 공식 원문이 없는 학교는 `depts/national-extra.json`에 학교 공지·입시결과·기사 등에서 찾은 값을 출처와 함께 적어 두면 생성기가 합친다. `official: false` 행은 화면에 '비공식'과 출처가 표시되고, 03 표의 자료 선택으로 빼고 볼 수 있다. 진학사 스마트경쟁률에 등록된 학교 경쟁률 링크에서 직접 읽은 값만 `official: true`
- 성인학습자·만학도만 뽑는 모집단위는 공식·비공식 모두 비교에서 뺀다. 조리·제과제빵 통합 학과는 호텔조리·카페베이커리 두 비교에 모두 넣는다

## 입시 추이 (trends.json)

모든 학과에 ‘입시 추이’ 탭(`trends.html`)이 붙는다. 2023~2027학년도 수시 1차의 학령인구·모집인원·지원자·경쟁률을 비교 학교와 함께 보여 준다.

- 만들기: `python scripts/build_trends.py` (학과 `ratios.json`·`ratios-national.json`의 공식 모집단위 → 2023~2026 진학사 과거 경쟁률 + 2027 원문, 경민대 2027은 학교 집계)
- 모든 해를 수시 1차 정원내 전형 합계로 묶는다. 이름이 바뀐 경민대 학과는 스크립트의 `ALIAS`로 잇는다 (해마다 실제 학과명은 파일·화면에 남는다)
- 학령인구: `school/population.json` (수능 재학생 지원자, 연도별 출처)
- 주 전형 경쟁률(일반고, 없으면 일반전형)을 해마다 따로 둔다 — 학교마다 전형 구성이 달라도 같은 기준으로 비교
- 비공식: 전국 비교가 있는 학과는 `national-extra.json` 학교도 넣는다. 2027·2026은 조사 자료, 2023~2026은 진학사 과거값이 공개된 해는 공식값, 나머지 해는 전문대학포털(전문대교협)의 전형별 모집인원(대학별 전형방법) × 전형별 경쟁률(전년도 입시결과)로 계산한다. 이런 값은 해마다 `unofficial: true` 로 표시되어 화면에 점선·빈 점·주황 *로 나온다
