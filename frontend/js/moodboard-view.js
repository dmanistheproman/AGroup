/* Shared moodboard view (C-13): what family members see through a share link, read-only and without an account.
   The token is in the address after #, so it is not sent to the server in the page request or in a Referer. */
(() => {
  'use strict';

  const UI = window.AGroupUI;
  const { esc } = UI;
  const main = document.querySelector('#shared-board');

  function tile(item) {
    if (item.item_type === 'PROJECT') {
      const p = item.project || { title: item.project_id };
      return `<div class="board-tile"><img src="assets/${esc(p.image || 'living')}.jpg" alt="${esc(p.title)}"><p>${esc(p.title)}</p><small>${esc(p.firm || '')}</small></div>`;
    }
    if (item.item_type === 'IMAGE') return `<div class="board-tile"><img src="${esc(item.image_url || 'assets/living.jpg')}" alt="Inspiration image"><p>Inspiration</p></div>`;
    if (item.item_type === 'COLOUR') return `<div class="board-tile"><div class="mood-swatch" style="background:${/^#[0-9a-f]{6}$/i.test(item.colour) ? item.colour : '#b4b9a1'}"></div><p>${esc(item.colour)}</p></div>`;
    return `<div class="board-tile"><p class="mood-note-text">${esc(item.note)}</p></div>`;
  }

  async function show() {
    const token = location.hash.replace('#', '');
    if (!token) { main.innerHTML = UI.state('error', 'This link is incomplete. Ask for the link again.'); return; }
    main.innerHTML = UI.state('loading');
    const res = await fetch(`/api/moodboards/shared/${encodeURIComponent(token)}`).catch(() => null);
    const data = res ? await res.json().catch(() => ({})) : {};
    if (!res || !res.ok) {
      main.innerHTML = `<div class="empty"><h3>This moodboard is not shared any more.</h3>
        <p>The owner may have stopped sharing it. Ask them for a new link.</p><a class="button" href="index.html">Explore AGroup</a></div>`;
      return;
    }
    document.title = `AGroup — ${data.name}`;
    main.innerHTML = `<p class="eyebrow">SHARED MOODBOARD · READ-ONLY</p><h1>${esc(data.name)}</h1>
      <p class="hint">Someone shared this board with you. You can look, but not change it.</p>
      <div class="board-surface shared-surface">${data.items.length ? data.items.map(tile).join('')
        : '<div class="empty"><h3>This board is still empty.</h3></div>'}</div>`;
  }

  window.addEventListener('hashchange', show);
  document.addEventListener('DOMContentLoaded', show);
})();
