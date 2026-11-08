/* Moodboard boundary (C-11, C-13, S-22) for a logged-in customer on the Moodboard tab.
   Boards are MOODBOARD collections on the server: saved projects, uploaded inspiration images (S-03 upload widget),
   colours and notes, which the owner can remove and reorder, and share read-only through a revocable link.
   customer.js asks AGroupMoodboard.shows() and calls render(workspace); visitors keep the browser demo board. */
(() => {
  'use strict';

  const UI = window.AGroupUI;
  const R = window.AGroupRecords;
  const { esc, icon } = UI;
  const toast = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));
  let boards = [];
  let currentId = '';
  let target = null;
  let titles = {};

  const customer = () => {
    const user = window.AGroupAccount && window.AGroupAccount.current();
    return user && user.role === 'customer' ? user : null;
  };

  function shows() { return Boolean(customer()); }

  async function render(workspace) {
    target = workspace || target;
    if (!target) return;
    target.innerHTML = `<div class="section-heading"><div><p class="eyebrow">COLLECT A FEELING</p><h2>Your moodboards.</h2>
      <p>Saved projects, your own photos, colours and notes in one place. Share a board with family through a link.</p></div></div>`
      + UI.state('loading');
    const [list, saved, catalog] = await Promise.all([R.call('GET', '/api/collections'), R.call('GET', '/api/favourites'),
                                                       R.call('GET', '/api/catalog')]);
    titles = Object.fromEntries((catalog.ok ? catalog.data.projects : []).map(p => [`IDP-${String(p.id).padStart(3, '0')}`, p.title]));
    boards = (list.ok ? list.data.collections : []).filter(c => c.kind === 'MOODBOARD');
    if (!boards.find(b => b.id === currentId)) currentId = boards[0] ? boards[0].id : '';
    const savedIds = saved.ok ? (saved.data.project_ids || []) : [];
    const board = boards.find(b => b.id === currentId);
    target.innerHTML = `<div class="section-heading"><div><p class="eyebrow">COLLECT A FEELING</p><h2>Your moodboards.</h2>
        <p>Saved projects, your own photos, colours and notes in one place. Share a board with family through a link.</p></div></div>
      <div class="moodboard-tabs">${boards.map(b => `<button type="button" class="${b.id === currentId ? 'active' : ''}" data-board="open" data-id="${esc(b.id)}">
          ${esc(b.name)} <small>${b.items.length}</small></button>`).join('')}
        <form class="moodboard-new" data-board-form="create"><label class="visually-hidden" for="board-name">New moodboard name</label>
          <input id="board-name" name="name" maxlength="60" required placeholder="New moodboard, e.g. Living room">
          <button class="button outline" type="submit">${icon('folder-plus')} Create</button></form></div>
      ${board ? boardView(board, savedIds) : UI.state('empty', 'Create your first moodboard to start collecting ideas.')}`;
  }

  function tile(item, index, count) {
    const move = `<span class="tile-actions">
        <button type="button" class="icon-button" data-board="move" data-id="${esc(item.id)}" data-step="-1" ${index === 0 ? 'disabled' : ''} aria-label="Move earlier">${icon('arrow-left')}</button>
        <button type="button" class="icon-button" data-board="move" data-id="${esc(item.id)}" data-step="1" ${index === count - 1 ? 'disabled' : ''} aria-label="Move later">${icon('arrow-right')}</button>
        <button type="button" class="icon-button" data-board="remove" data-id="${esc(item.id)}" aria-label="Remove">${icon('trash-2')}</button></span>`;
    return `<div class="board-tile mood-${item.item_type.toLowerCase()}">${content(item)}${move}</div>`;
  }

  function content(item) {
    if (item.item_type === 'PROJECT') {
      const p = item.project || { title: item.project_id };
      return `<img src="assets/${esc(p.image || 'living')}.jpg" alt="${esc(p.title)}"><p>${esc(p.title)}</p><small>${esc(p.firm || '')}</small>`;
    }
    if (item.item_type === 'IMAGE') return `<img src="${esc(item.image_url || 'assets/living.jpg')}" alt="Your inspiration image"><p>Your inspiration</p>`;
    if (item.item_type === 'COLOUR') return `<div class="mood-swatch" style="background:${/^#[0-9a-f]{6}$/i.test(item.colour) ? item.colour : '#b4b9a1'}"></div><p>${esc(item.colour)}</p>`;
    return `<p class="mood-note-text">${esc(item.note)}</p>`;
  }

  function boardView(board, savedIds) {
    const onBoard = new Set(board.items.filter(i => i.project_id).map(i => i.project_id));
    const choices = savedIds.map(String).filter(id => !onBoard.has(id));
    const link = board.share_token ? `${location.origin}${location.pathname.replace(/[^/]*$/, '')}moodboard.html#${board.share_token}` : '';
    return `<div class="board-grid"><div class="board-surface">${board.items.length
        ? board.items.map((item, i) => tile(item, i, board.items.length)).join('')
        : '<div class="empty"><h3>A little blank canvas.</h3><p>Add a saved project, a photo, a colour or a note.</p></div>'}</div>
      <div class="form-stack moodboard-tools">
        <div class="row"><button class="button outline" type="button" data-board="rename">${icon('pencil')} Rename</button>
          <button class="button outline" type="button" data-board="delete">${icon('trash-2')} Delete board</button></div>
        <form class="form-stack" data-board-form="project"><label>ADD A SAVED PROJECT<select name="project_id" required>
            <option value="">${choices.length ? 'Choose a saved project' : 'Save a project first'}</option>${choices.map(id => `<option value="${esc(id)}">${esc(titles[id] || id)}</option>`).join('')}</select></label>
          <button class="button outline" type="submit" ${choices.length ? '' : 'disabled'}>Add project</button></form>
        <form class="form-stack" data-board-form="image">${UI.uploadWidget({ name: 'image', label: 'Add an inspiration photo', kind: 'image', multiple: false, required: true })}
          <button class="button outline" type="submit">${icon('upload')} Upload photo</button></form>
        <form class="row" data-board-form="colour"><label>PALETTE COLOUR<input type="color" name="colour" value="#6b7a5a"></label>
          <button class="button outline" type="submit">Add colour</button></form>
        <form class="form-stack" data-board-form="note"><label>NOTE<textarea name="note" maxlength="500" required placeholder="For example: warm oak with soft lighting"></textarea></label>
          <button class="button outline" type="submit">Add note</button></form>
        <div class="moodboard-share"><h3>${icon('arrow-up-right')} Share with family</h3>
          ${link ? `<p class="small-note">Anyone with this link can view the board, read-only, without an account.</p>
            <input readonly value="${esc(link)}" aria-label="Share link" onclick="this.select()">
            <div class="row"><button class="button outline" type="button" data-board="copy" data-link="${esc(link)}">Copy link</button>
              <button class="text-button" type="button" data-board="revoke">Stop sharing</button></div>`
            : `<p class="small-note">Create a read-only link. You can stop sharing at any time.</p>
            <button class="button outline" type="button" data-board="share">Create share link</button>`}</div></div></div>`;
  }

  async function act(result, success) {
    if (!result.ok) { toast(result.data.error || 'That did not work.'); return; }
    if (success) toast(success);
    render();
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-board]');
    if (!button || !customer()) return;
    const base = `/api/collections/${encodeURIComponent(currentId)}`;
    const action = button.dataset.board;
    if (action === 'open') { currentId = button.dataset.id; render(); }
    else if (action === 'remove') act(await R.call('DELETE', `${base}/items/${button.dataset.id}`), 'Removed from the board.');
    else if (action === 'move') {
      const board = boards.find(b => b.id === currentId);
      const ids = board.items.map(i => i.id);
      const from = ids.indexOf(button.dataset.id);
      const to = from + Number(button.dataset.step);
      if (to < 0 || to >= ids.length) return;
      [ids[from], ids[to]] = [ids[to], ids[from]];
      act(await R.call('PUT', `${base}/order`, { item_ids: ids }));
    } else if (action === 'rename') {
      const name = prompt('New name for this moodboard', boards.find(b => b.id === currentId)?.name || '');
      if (name) act(await R.call('PATCH', base, { name }), 'Renamed.');
    } else if (action === 'delete') {
      if (confirm('Delete this moodboard? Your saved projects stay saved.')) act(await R.call('DELETE', base), 'Moodboard deleted.');
    } else if (action === 'share') act(await R.call('POST', `${base}/share`), 'Share link created.');
    else if (action === 'revoke') act(await R.call('DELETE', `${base}/share`), 'The link no longer works.');
    else if (action === 'copy') {
      try { await navigator.clipboard.writeText(button.dataset.link); toast('Link copied.'); } catch { toast('Select the link and copy it.'); }
    }
  });

  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-board-form]');
    if (!form) return;
    event.preventDefault();
    event.stopPropagation();
    const kind = form.dataset.boardForm;
    const base = `/api/collections/${encodeURIComponent(currentId)}`;
    const value = name => form.elements[name].value.trim();
    if (kind === 'create') {
      const r = await R.call('POST', '/api/collections', { name: value('name'), kind: 'MOODBOARD' });
      if (r.ok) currentId = r.data.collection.id;
      act(r, 'Moodboard created.');
    } else if (kind === 'project') act(await R.call('POST', `${base}/items`, { item_type: 'PROJECT', project_id: value('project_id') }), 'Project added.');
    else if (kind === 'colour') act(await R.call('POST', `${base}/items`, { item_type: 'COLOUR', colour: value('colour') }), 'Colour added.');
    else if (kind === 'note') act(await R.call('POST', `${base}/items`, { item_type: 'NOTE', note: value('note') }), 'Note added.');
    else if (kind === 'image') {
      const input = form.querySelector('input[type=file]');
      const check = UI.checkFiles(input, 'image');
      if (!input.files.length || !check.ok) { toast(check.errors[0] || 'Choose a photo first.'); return; }
      const data = new FormData();
      data.append('image', input.files[0]);
      const progress = form.querySelector('.upload-progress');
      progress.hidden = false;
      const r = await UI.send(`${base}/images`, data, p => { progress.value = p; });
      progress.hidden = true;
      act(r, 'Photo added.');
    }
  }, true);

  window.AGroupMoodboard = { shows, render };
})();
