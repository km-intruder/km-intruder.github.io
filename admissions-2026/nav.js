/* 공통 탭 메뉴 · 학교/학과 선택
   - 학교 화면: 경민대 전체 · 전문대 동향 · 학교 소식
   - 학과 화면: 수시 1차(회차별) · 교육과정 비교 · 산업 현황(boards: true 인 학과만)
   학과 추가: DEPTS 에 한 줄 + depts/<id>/ 폴더(dept.json, ratios.json) 생성 (depts/README.md 참고)
   회차 추가: 해당 학과 rounds 에 { id: 'susi2', label: '수시 2차', file: 'ratios-susi2.json' } 추가 */
(function () {
  const S1 = [{ id: 'susi1', label: '수시 1차', file: 'ratios.json' }];
  const DEPTS = [
    { id: 'nursing', name: '간호학과', rounds: S1 },
    { id: 'health-admin', name: '보건의료행정과', rounds: S1 },
    { id: 'speech-therapy', name: '언어치료학과', rounds: S1 },
    { id: 'medical-beauty', name: '의료미용과', rounds: S1 },
    { id: 'fire-safety', name: '소방안전관리과', rounds: S1 },
    { id: 'emergency-rescue', name: '응급구조학과', rounds: S1 },
    { id: 'cafe-bakery', name: '카페베이커리과', rounds: S1 },
    { id: 'hotel-tourism', name: '호텔관광학과', rounds: S1 },
    { id: 'hotel-culinary', name: '호텔조리과', rounds: S1 },
    { id: 'interior-design', name: '건축공간디자인학과', rounds: S1 },
    { id: 'social-welfare', name: '사회복지과', rounds: S1 },
    { id: 'early-childhood', name: '유아교육학과', rounds: S1 },
    { id: 'defense-drone', name: '국방드론봇시스템과', rounds: S1 },
    { id: 'cyber-security', name: '사이버·정보시스템학과', rounds: S1 },
    { id: 'software', name: '지능형소프트웨어과', boards: true, rounds: S1 },
    { id: 'military', name: '효충군사학과', rounds: S1 },
    { id: 'media-video', name: '미디어영상과', rounds: S1 },
    { id: 'practical-music', name: '실용음악과', rounds: S1 },
    { id: 'acting-arts', name: '연기예술과', rounds: S1 },
    { id: 'game-contents', name: '게임콘텐츠과', rounds: S1 },
    { id: 'leports', name: '레포츠과', rounds: S1 },
    { id: 'taekwondo', name: '태권도외교과', rounds: S1 },
    { id: 'hair-design', name: '헤어디자인과', rounds: S1 },
    { id: 'free-major', name: '자유전공학과', rounds: S1 },
  ];
  const SCHOOL_PAGES = [
    { href: 'school.html', label: '경민대 전체' },
    { href: 'colleges.html', label: '전문대 동향' },
    { href: 'kyungmin.html', label: '학교 소식' },
  ];

  const params = new URLSearchParams(location.search);
  const page = location.pathname.split('/').pop() || 'index.html';
  const schoolScope = SCHOOL_PAGES.some(p => p.href === page);
  // 학과 화면에서 dept 가 없으면 기존 주소 호환을 위해 지능형소프트웨어과
  const DEFAULT = DEPTS.find(d => d.id === 'software');
  const dept = schoolScope ? null : (DEPTS.find(d => d.id === params.get('dept')) || DEFAULT);
  const round = dept ? (dept.rounds.find(r => r.id === params.get('round')) || dept.rounds[0]) : null;

  // 기본 학과·기본 회차는 주소에 붙이지 않아 기존 주소가 그대로 유지된다
  const link = (href, extra = {}) => {
    const q = new URLSearchParams();
    if (dept && dept !== DEFAULT) q.set('dept', dept.id);
    for (const [k, v] of Object.entries(extra)) if (v) q.set(k, v);
    const s = q.toString();
    return href + (s ? '?' + s : '');
  };

  const links = schoolScope
    ? SCHOOL_PAGES.map(p => ({ href: p.href, label: p.label, active: page === p.href }))
    : [
      { href: 'school.html', label: '← 경민대 전체' },
      ...dept.rounds.map(r => ({
        href: link('admissions-dashboard.html', { round: r === dept.rounds[0] ? '' : r.id }),
        label: r.label, active: page === 'admissions-dashboard.html' && r === round,
      })),
      { href: link('competition-curriculum.html'), label: '교육과정 비교', active: page === 'competition-curriculum.html' },
      ...(dept.boards ? [{ href: link('industry.html'), label: '산업 현황', active: page === 'industry.html' }] : []),
    ];

  const nav = document.getElementById('tabs');
  if (nav) {
    nav.innerHTML = links.map(l => `<a href="${l.href}"${l.active ? ' aria-current="page"' : ''}>${l.label}</a>`).join('');
    const sel = document.createElement('select');
    sel.className = 'dept-select';
    sel.setAttribute('aria-label', '학교 전체 또는 학과 선택');
    sel.innerHTML = `<option value="">경민대 전체</option>` +
      DEPTS.map(d => `<option value="${d.id}"${d === dept ? ' selected' : ''}>${d.name}</option>`).join('');
    sel.addEventListener('change', () => {
      if (!sel.value) { location.href = 'school.html'; return; }
      const next = DEPTS.find(d => d.id === sel.value);
      const target = schoolScope || (page === 'industry.html' && !next.boards) ? 'admissions-dashboard.html' : page;
      location.href = target + (next === DEFAULT ? '' : '?dept=' + next.id);
    });
    nav.appendChild(sel);
  }

  const base = dept ? 'depts/' + dept.id + '/' : '';
  let deptConfig = null;
  window.Admission = {
    DEPTS, dept, round, base, link,
    dataFile: dept ? base + round.file : null,
    deptHref: id => 'admissions-dashboard.html' + (id === DEFAULT.id ? '' : '?dept=' + id),
    // 학과 설정(dept.json): 이름·분야·교육과정 데이터
    loadDept() {
      return deptConfig || (deptConfig = fetch(base + 'dept.json', { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error('dept.json ' + r.status);
        return r.json();
      }));
    },
    // data-dept="name" 같은 자리에 학과 설정값을 채운다
    fill(cfg) {
      document.querySelectorAll('[data-dept]').forEach(e => { e.textContent = cfg[e.dataset.dept] ?? ''; });
      // 경민대 입학처 학과 소개 요약 (출처 링크 포함)
      const it = cfg.kmIntro;
      document.querySelectorAll('[data-dept-intro]').forEach(e => {
        e.hidden = !it;
        if (!it) return;
        e.textContent = '학과 소개: ' + it.text + ' ';
        const l = document.createElement('a');
        Object.assign(l, { href: it.url, target: '_blank', rel: 'noopener noreferrer', textContent: '입학처 원문' });
        e.append(l, ` (${it.checked} 확인)`);
      });
    },
  };
})();
