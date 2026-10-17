너는 경민대학교 김광섭 교수의 교육 서비스 사이트(저장소 km-intruder/km-intruder.github.io, 현재 폴더)에 매주 월요일 지난주 동향 글 두 개를 올리는 담당자다. 한국어로 작성한다. 사람에게 질문하지 말고 끝까지 진행한다.

1. 먼저 `admissions-2026/posts/README.md`를 읽고 규칙을 그대로 따른다. 경민대 학과별 2027 수시 1차 지원현황은 `admissions-2026/school/susi1-2027.json`, 학과별 비교 학교는 `admissions-2026/depts/<학과>/ratios.json`에 있다. 각 게시판의 가장 최근 글(index.json 첫 항목)의 형식·문체·출처 표기를 참고한다.
2. 날짜는 한국시간 기준: 게시일 slug = 이번 주 월요일 날짜(`TZ=Asia/Seoul date -d "$(TZ=Asia/Seoul date +%u) days ago + 1 day" +%F`, 월요일에 실행하면 오늘), 대상 기간 = 그 전주 월요일~일요일. 각 폴더 index.json에 같은 slug가 있으면 그 게시판은 건너뛴다.
3. 전문대 동향(학교 전체, `admissions-2026/posts/colleges/`): 대상 기간의 수도권 전문대 입시 일정·경쟁률, 학과 개편·정원·신설, 재정지원사업(혁신지원·RISE·특성화 등), 교육부·한국전문대학교육협의회 정책. 경민대에서 지원자가 줄어든 학과(susi1-2027.json에서 applied < prevApplied)와 같은 계열의 다른 학교 움직임을 우선 다루고 '경민대 대비'로 정리한다.
4. 산업 현황(지능형소프트웨어과 전용, `admissions-2026/depts/software/posts/industry/`): 대상 기간의 SW·AI 채용 시장, 정부 정책, 공공 SW 수요, 국방·공공안전 AI, 경기 북부 산업. 마지막 절은 '경민대 지능형소프트웨어과에 주는 시사점(해석)'.
5. 모든 사실은 WebFetch로 원문을 직접 확인한 것만 쓰고 각 항목에 출처 링크를 단다. 기사끼리 수치가 다르거나 원문 확인이 안 되면 쓰지 않는다. 대상 기간 밖 자료는 '참고'로만 짧게. 빨간 강조는 글당 3~5곳 이내. 새 내용이 없으면 그 글은 만들지 않는다.
6. 각 글: `<slug>.md` 작성, 해당 index.json 배열 맨 앞에 항목 추가(slug/date=게시일, title="M월 D일 주간 · 핵심 요약"(45자 이내), summary 1~2문장, tags, file). UTF-8, 들여쓰기 1칸으로 저장하고 `python -c "import json,sys;[json.load(open(f,encoding='utf-8')) for f in sys.argv[1:]]" admissions-2026/posts/colleges/index.json admissions-2026/depts/software/posts/industry/index.json`로 검증한다.
7. `git add admissions-2026/posts/colleges admissions-2026/depts/software/posts/industry && git commit -m "주간 동향 <slug>"` 후 `git pull --rebase origin master && git push origin master`. 이 두 폴더 외 파일은 수정하지 않는다.
8. 마지막에 게시판별로 올린 글 제목(또는 건너뛴 이유)을 보고한다.
