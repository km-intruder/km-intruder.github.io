/* 공통 탭 메뉴. 입시 회차를 추가하려면 ROUNDS 에 한 줄 추가하고 데이터 파일을 만든다.
   예) { id: 'susi2', label: '수시 2차', file: 'ratios-susi2.json' }
   데이터 파일 형식은 ratios.json 과 같고, scripts/update_admissions_ratios.py 가 ratios*.json 을 모두 갱신한다. */
(function () {
  const ROUNDS = [
    { id: 'susi1', label: '수시 1차', file: 'ratios.json' },
  ];
  const BOARDS = [
    { href: 'competition-curriculum.html', label: '교육과정 비교' },
    { href: 'kyungmin.html', label: '경민대 소식' },
    { href: 'colleges.html', label: '전문대 현황' },
    { href: 'industry.html', label: '산업 현황' },
  ];

  const page = location.pathname.split('/').pop() || 'index.html';
  const roundId = new URLSearchParams(location.search).get('round');
  const current = ROUNDS.find(r => r.id === roundId) || ROUNDS[0];
  const roundHref = r => 'admissions-dashboard.html' + (r === ROUNDS[0] ? '' : '?round=' + r.id);

  const links = [
    ...ROUNDS.map(r => ({ href: roundHref(r), label: r.label, active: page === 'admissions-dashboard.html' && r === current })),
    ...BOARDS.map(b => ({ ...b, active: page === b.href })),
  ];
  const nav = document.getElementById('tabs');
  if (nav) nav.innerHTML = links.map(l => `<a href="${l.href}"${l.active ? ' aria-current="page"' : ''}>${l.label}</a>`).join('');

  window.Admission = { ROUNDS, round: current };
})();
