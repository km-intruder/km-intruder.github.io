/* 게시판형 탭: posts/<분류>/index.json 목록 + 마크다운 본문
   새 글 추가: posts/<분류>/YYYY-MM.md 작성 후 index.json 맨 앞에 항목 추가 */
(function () {
  const root = document.getElementById('board');
  const cat = root.dataset.cat;
  const base = 'posts/' + cat + '/';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  async function getJSON(url) {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(url + ' ' + res.status);
    return res.json();
  }

  function renderList(posts) {
    const sorted = [...posts].sort((a, b) => b.date.localeCompare(a.date));
    root.innerHTML = sorted.length ? `<ul class="board-list">${sorted.map(p => `
      <li><a href="?post=${encodeURIComponent(p.slug)}">
        <time datetime="${esc(p.date)}">${esc(p.date)}</time>
        <div><strong>${esc(p.title)}</strong><p>${esc(p.summary)}</p>
          ${p.tags?.length ? `<div class="tags">${p.tags.map(t => `<span>${esc(t)}</span>`).join('')}</div>` : ''}</div>
      </a></li>`).join('')}</ul>` : '<p class="empty">아직 게시글이 없습니다.</p>';
  }

  async function renderPost(posts, slug) {
    const p = posts.find(x => x.slug === slug);
    if (!p) { root.innerHTML = '<p class="empty">게시글을 찾을 수 없습니다. <a href="?">목록으로</a></p>'; return; }
    const res = await fetch(base + p.file, { cache: 'no-store' });
    const md = res.ok ? await res.text() : '본문을 불러오지 못했습니다.';
    const html = window.marked && window.DOMPurify
      ? DOMPurify.sanitize(marked.parse(md), { ADD_ATTR: ['target'] })
      : '<pre>' + esc(md) + '</pre>';
    root.innerHTML = `<div class="post-head"><a class="back" href="?">← 목록</a>
      <h2>${esc(p.title)}</h2><time datetime="${esc(p.date)}">${esc(p.date)}</time></div>
      <article class="post">${html}</article>`;
    root.querySelectorAll('.post a[href^="http"]').forEach(a => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
    document.title = p.title;
  }

  getJSON(base + 'index.json').then(posts => {
    const slug = new URLSearchParams(location.search).get('post');
    return slug ? renderPost(posts, slug) : renderList(posts);
  }).catch(() => { root.innerHTML = '<p class="empty alert">게시글 목록을 불러오지 못했습니다.</p>'; });
})();
