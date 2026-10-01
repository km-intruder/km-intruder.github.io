/* 공통: ratios.json 로드와 경민대 기준 비교 계산 */
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
    const rows = data.rows.map(r => {
      const s = byId[r.school];
      const rate = r.quota ? r.applied / r.quota : 0;
      const change = r.comparable && r.prior ? (rate - r.prior) / r.prior * 100 : null;
      const row = { ...r, s, rate, change, final: finalized.has(r.school) };
      row.cause = change == null ? '' : cause(row);
      return row;
    });
    const b = data.baseline || { school: 'km', dept: '지능형소프트웨어과' };
    const base = rows.find(r => r.school === b.school && r.dept === b.dept);
    rows.forEach(r => {
      r.isBase = r === base;
      r.vsBase = base && base.rate ? r.rate / base.rate : null;
      r.gap = base ? r.rate - base.rate : null;
    });
    // 순위·평균은 전문대 수시 1차 모집단위끼리만 (4년제는 전형 구조가 달라 제외)
    const peers = rows.filter(r => r.s.type !== '4년제');
    const ranked = [...peers].sort((x, y) => y.rate - x.rate);
    const others = peers.filter(r => !r.isBase);
    const median = arr => { const v = arr.map(r => r.rate).sort((a, c) => a - c); const m = v.length >> 1; return v.length ? (v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2) : null; };
    return {
      data, byId, rows, base, peers,
      rank: base ? ranked.indexOf(base) + 1 : null,
      peerCount: peers.length,
      median: median(others),
      above: others.filter(r => r.rate > (base?.rate ?? 0)).length,
      comparable: rows.filter(r => r.change != null && !r.isBase),
    };
  }

  async function load() {
    const res = await fetch('ratios.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('ratios.json ' + res.status);
    return prepare(await res.json());
  }

  window.Ratio = { load, esc, num, fx, pct, signed };
})();
