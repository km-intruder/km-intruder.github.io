/* 공통: 학과별 경쟁률 파일(depts/<학과>/ratios*.json) 로드와 경민대 기준 비교 계산 */
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = n => Number(n).toLocaleString('ko-KR');
  const fx = (n, d = 2) => Number(n).toFixed(d);
  const pct = n => (n > 0 ? '+' : n < 0 ? '−' : '') + Math.abs(n).toFixed(1) + '%';
  const signed = (n, d = 2) => (n > 0 ? '+' : n < 0 ? '−' : '±') + Math.abs(n).toFixed(d);

  // 경쟁률 변화의 산술적 원인 분류 (모집·지원 인원 변화 기준)
  function cause(r) {
    if (r.priorQuota == null || r.priorApplied == null) return '2026 지원인원 미공개';
    const dq = r.quota - r.priorQuota, da = r.applied - r.priorApplied;
    if (r.change > 0) {
      if (dq < 0 && da <= 0) return '정원 축소 효과 (지원은 감소)';
      if (dq < 0) return '정원 축소 + 지원 증가';
      return '지원 증가';
    }
    if (r.change < 0) {
      if (dq > 0 && da >= 0) return '정원 확대 효과 (지원은 증가)';
      if (dq > 0) return '정원 확대 + 지원 감소';
      return '지원 감소';
    }
    return '';
  }

  function prepare(data) {
    const byId = Object.fromEntries(data.schools.map(s => [s.id, s]));
    const finalized = new Set(data.finalized || []);
    // 4년제는 전형 구조가 달라 비교 대상에서 제외하고 참고용으로만 따로 둔다
    const isUniv = r => byId[r.school]?.type === '4년제';
    const reference = data.rows.filter(isUniv).map(r => ({ ...r, s: byId[r.school], rate: r.quota ? r.applied / r.quota : 0, final: finalized.has(r.school) }));
    const b = data.baseline || { school: 'km', dept: '지능형소프트웨어과' };
    const all = data.rows.filter(r => !isUniv(r)).map(r => {
      const s = byId[r.school];
      const rate = r.quota ? r.applied / r.quota : 0;
      const change = r.comparable && r.prior ? (rate - r.prior) / r.prior * 100 : null;
      const row = { ...r, s, rate, totalRate: rate, change, final: finalized.has(r.school) };
      // 경민대는 학과 전체(정원내) 값이 기본이라, 비교 학교와 같은 주 전형 값이 있으면 순위·배수 비교에 그 값을 쓴다
      // (2026 대비 변화는 학과 전체 기준 그대로)
      if (r.main && r.main.quota) { row.rate = r.main.applied / r.main.quota; row.mainTrack = r.main.track; }
      row.cause = change == null ? '' : cause(row);
      return row;
    });
    const base = all.find(r => r.school === b.school && r.dept === b.dept);
    // 경민대의 다른 학과는 같은 학교라 비교군에서 빼고 참고용으로만 둔다
    const sameSchool = all.filter(r => r.school === b.school && r !== base);
    const rows = all.filter(r => !sameSchool.includes(r));
    // 경민대 소재지에서의 직선거리(km)
    const km = (a, c) => {
      const rad = x => x * Math.PI / 180, dLat = rad(c.lat - a.lat), dLon = rad(c.lon - a.lon);
      const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(c.lat)) * Math.sin(dLon / 2) ** 2;
      return 6371 * 2 * Math.asin(Math.sqrt(h));
    };
    // 순위표에는 진로가 겹치는 경민대 다른 학과(rankWith 표시)도 넣는다 (시장 합계·중앙값 계산에서는 빼 둔다)
    const rankRows = [...rows, ...sameSchool.filter(r => r.rankWith)];
    rankRows.forEach(r => {
      r.isSibling = sameSchool.includes(r);
      r.distKm = base ? km(base.s, r.s) : null;
      r.isBase = r === base;
      r.vsBase = base && base.rate ? r.rate / base.rate : null;
      r.gap = base ? r.rate - base.rate : null;
    });
    const peers = rows;
    const others = peers.filter(r => !r.isBase);
    const median = arr => { const v = arr.map(r => r.rate).sort((a, c) => a - c); const m = v.length >> 1; return v.length ? (v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2) : null; };
    return {
      data, byId, rows, base, peers, reference, sameSchool, rankRows,
      colleges: data.schools.filter(s => s.type !== '4년제'),
      universities: data.schools.filter(s => s.type === '4년제'),
      rank: base ? 1 + rankRows.filter(r => r.rate > base.rate).length : null,
      peerCount: rankRows.length,
      median: median(others),
      above: rankRows.filter(r => !r.isBase && r.rate > (base?.rate ?? 0)).length,
      below: rankRows.filter(r => !r.isBase && r.rate < (base?.rate ?? 0)).length,
      comparable: rows.filter(r => r.change != null && !r.isBase),
    };
  }

  async function load(file) {
    const res = await fetch(file, { cache: 'no-store' });
    if (!res.ok) throw new Error(file + ' ' + res.status);
    return prepare(await res.json());
  }

  window.Ratio = { load, esc, num, fx, pct, signed };
})();
