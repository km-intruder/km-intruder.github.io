/* 공통 탭 메뉴 · 학과/회차 선택
   학과 추가: DEPTS 에 한 줄 + depts/<id>/ 폴더(dept.json, ratios.json, posts/) 생성
   회차 추가: 해당 학과 rounds 에 { id: 'susi2', label: '수시 2차', file: 'ratios-susi2.json' } 추가
   데이터 파일 형식은 depts/software 를 기준으로 한다. */
(function () {
  const DEPTS = [
    { id: 'software', name: '지능형소프트웨어과', rounds: [{ id: 'susi1', label: '수시 1차', file: 'ratios.json' }] },
  ];
  const BOARDS = [
    { href: 'competition-curriculum.html', label: '교육과정 비교' },
    { href: 'kyungmin.html', label: '경민대 소식', shared: true },
    { href: 'colleges.html', label: '전문대 현황' },
    { href: 'industry.html', label: '산업 현황' },
  ];

  const params = new URLSearchParams(location.search);
  const page = location.pathname.split('/').pop() || 'index.html';
  const dept = DEPTS.find(d => d.id === params.get('dept')) || DEPTS[0];
  const round = dept.rounds.find(r => r.id === params.get('round')) || dept.rounds[0];

  // 기본 학과·기본 회차는 주소에 붙이지 않아 기존 주소가 그대로 유지된다
  const link = (href, extra = {}) => {
    const q = new URLSearchParams();
    if (dept !== DEPTS[0]) q.set('dept', dept.id);
    for (const [k, v] of Object.entries(extra)) if (v) q.set(k, v);
    const s = q.toString();
    return href + (s ? '?' + s : '');
  };

  const links = [
    ...dept.rounds.map(r => ({
      href: link('admissions-dashboard.html', { round: r === dept.rounds[0] ? '' : r.id }),
      label: r.label, active: page === 'admissions-dashboard.html' && r === round,
    })),
    ...BOARDS.map(b => ({ href: link(b.href), label: b.label, active: page === b.href })),
  ];
  const nav = document.getElementById('tabs');
  if (nav) {
    nav.innerHTML = links.map(l => `<a href="${l.href}"${l.active ? ' aria-current="page"' : ''}>${l.label}</a>`).join('');
    if (DEPTS.length > 1) {
      const sel = document.createElement('select');
      sel.className = 'dept-select';
      sel.setAttribute('aria-label', '학과 선택');
      sel.innerHTML = DEPTS.map(d => `<option value="${d.id}"${d === dept ? ' selected' : ''}>경민대 ${d.name}</option>`).join('');
      sel.addEventListener('change', () => {
        const q = new URLSearchParams(location.search);
        q.delete('round'); q.delete('post'); q.delete('page');
        if (sel.value === DEPTS[0].id) q.delete('dept'); else q.set('dept', sel.value);
        const s = q.toString();
        location.href = page + (s ? '?' + s : '');
      });
      nav.appendChild(sel);
    }
  }

  const base = 'depts/' + dept.id + '/';
  let deptConfig = null;
  window.Admission = {
    DEPTS, dept, round, base, link,
    dataFile: base + round.file,
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
    },
  };
})();
