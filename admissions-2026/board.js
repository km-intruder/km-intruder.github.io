/* 게시판형 탭: posts/<분류>/index.json 목록 + 마크다운 본문 (10개씩 페이지)
   새 글 추가 방법은 posts/README.md 참고 */
(function () {
  const PER_PAGE = 10;
  const root = document.getElementById('board');
  const cat = root.dataset.cat;
  const base = 'posts/' + cat + '/';
  const params = new URLSearchParams(location.search);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const pageHref = n => (n > 1 ? '?page=' + n : '?');

  async function getJSON(url) {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(url + ' ' + res.status);
    return res.json();
  }

  const newestFirst = posts => [...posts].sort((a, b) => b.date.localeCompare(a.date) || b.slug.localeCompare(a.slug));

  function pager(page, pages) {
    if (pages <= 1) return '';
    const nums = Array.from({ length: pages }, (_, i) => i + 1)
      .map(n => n === page ? `<span aria-current="page">${n}</span>` : `<a href="${pageHref(n)}">${n}</a>`).join('');
    return `<nav class="pager" aria-label="페이지">
      ${page > 1 ? `<a href="${pageHref(page - 1)}">‹ 이전</a>` : '<span class="off">‹ 이전</span>'}
      ${nums}
      ${page < pages ? `<a href="${pageHref(page + 1)}">다음 ›</a>` : '<span class="off">다음 ›</span>'}
    </nav>`;
  }

  function renderList(posts) {
    const sorted = newestFirst(posts);
    const pages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
    const page = Math.min(pages, Math.max(1, parseInt(params.get('page'), 10) || 1));
    const slice = sorted.slice((page - 1) * PER_PAGE, page * PER_PAGE);
    root.innerHTML = sorted.length ? `
      <div class="board-meta">전체 ${sorted.length}개 · ${page} / ${pages} 페이지</div>
      <ul class="board-list">${slice.map(p => `
      <li><a href="?post=${encodeURIComponent(p.slug)}">
        <time datetime="${esc(p.date)}">${esc(p.date)}</time>
        <div><strong>${esc(p.title)}</strong><p>${esc(p.summary)}</p>
          ${p.tags?.length ? `<div class="tags">${p.tags.map(t => `<span>${esc(t)}</span>`).join('')}</div>` : ''}</div>
      </a></li>`).join('')}</ul>${pager(page, pages)}` : '<p class="empty">아직 게시글이 없습니다.</p>';
  }

  async function renderPost(posts, slug) {
    const sorted = newestFirst(posts);
    const i = sorted.findIndex(x => x.slug === slug);
    if (i < 0) { root.innerHTML = '<p class="empty">게시글을 찾을 수 없습니다. <a href="?">목록으로</a></p>'; return; }
    const p = sorted[i], listPage = Math.floor(i / PER_PAGE) + 1;
    const res = await fetch(base + p.file, { cache: 'no-store' });
    const md = res.ok ? await res.text() : '본문을 불러오지 못했습니다.';
    const html = window.marked && window.DOMPurify
      ? DOMPurify.sanitize(marked.parse(md), { ADD_ATTR: ['target'] })
      : '<pre>' + esc(md) + '</pre>';
    const newer = sorted[i - 1], older = sorted[i + 1];
    const link = (x, label) => x ? `<a href="?post=${encodeURIComponent(x.slug)}"><small>${label}</small>${esc(x.title)}</a>` : '<span></span>';
    root.innerHTML = `<div class="post-head"><a class="back" href="${pageHref(listPage)}">← 목록</a>
      <h2>${esc(p.title)}</h2><time datetime="${esc(p.date)}">${esc(p.date)}</time></div>
      <article class="post">${html}</article>
      <nav class="post-nav">${link(older, '이전 글')}${link(newer, '다음 글')}</nav>`;
    root.querySelectorAll('.post a[href^="http"]').forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
    document.title = p.title;
  }

  getJSON(base + 'index.json').then(posts => {
    const slug = params.get('post');
    return slug ? renderPost(posts, slug) : renderList(posts);
  }).catch(() => { root.innerHTML = '<p class="empty alert">게시글 목록을 불러오지 못했습니다.</p>'; });
})();
