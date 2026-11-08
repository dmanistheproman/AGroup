/* CollectionView boundary (S-22, C-04): named folders on the Saved page for a logged-in customer.
   Folders live on the server (/api/collections); only saved projects can be filed. customer.js asks
   AGroupFolders.shows(id) while filtering and calls AGroupFolders.decorate(workspace) after drawing. */
(() => {
  'use strict';

  let folders = [];
  let current = '';          // selected folder id; '' = all saved projects
  let loadedFor = null;

  const icon = name => (window.AGroupIcons ? window.AGroupIcons.icon(name) : '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const reference = id => `IDP-${String(id).padStart(3, '0')}`;
  const toast = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));

  function customer() {
    const user = window.AGroupAccount && window.AGroupAccount.current();
    return user && user.role === 'customer' ? user : null;
  }

  async function call(method, url, body) {
    const res = await fetch(url, {
      method, credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, data };
  }

  function refresh() {
    if (window.AGroupSaved) window.AGroupSaved.set(window.AGroupSaved.get());
  }

  async function load(force) {
    const user = customer();
    if (!user) {
      if (loadedFor) { folders = []; current = ''; loadedFor = null; refresh(); }
      return;
    }
    if (loadedFor === user.id && !force) return;
    loadedFor = user.id;
    const r = await call('GET', '/api/collections');
    folders = r.ok ? r.data.collections : [];
    if (current && !folders.some(f => f.id === current)) current = '';
    refresh();
  }

  async function act(request, success) {
    const r = await request;
    if (!r.ok) { toast(r.data.error || 'That did not work. Please try again.'); return; }
    if (success) toast(success);
    await load(true);
  }

  function shows(id) {
    if (!current) return true;
    const folder = folders.find(f => f.id === current);
    return Boolean(folder && folder.items.some(i => i.project_id === reference(id)));
  }

  function folderBar(savedCount) {
    const chip = (id, label, count) =>
      `<button type="button" class="folder-chip ${current === id ? 'active' : ''}" data-folder-action="select" data-folder="${id}"
         aria-pressed="${current === id}">${icon(id ? 'folder' : 'heart')}${esc(label)} <span>${count}</span></button>`;
    const selected = folders.find(f => f.id === current);
    return `<div class="folder-bar" aria-label="Folders">
      ${chip('', 'All saved', savedCount)}${folders.map(f => chip(f.id, f.name, f.items.length)).join('')}
      <form class="folder-new" data-folder-form>
        <label class="visually-hidden" for="folder-name">New folder name</label>
        <input id="folder-name" name="name" maxlength="60" placeholder="New folder" required>
        <button type="submit" class="text-button">${icon('folder-plus')} Add</button>
      </form>
      ${selected ? `<span class="folder-tools">
        <button type="button" class="text-button" data-folder-action="rename">${icon('pencil')} Rename</button>
        <button type="button" class="text-button" data-folder-action="delete">${icon('trash-2')} Delete folder</button>
      </span>` : ''}
    </div>`;
  }

  function cardTools(id) {
    if (current) {
      return `<button type="button" class="text-button folder-remove" data-folder-action="remove" data-id="${id}">
        ${icon('x')} Remove from this folder</button>`;
    }
    const options = folders.filter(f => !f.items.some(i => i.project_id === reference(id)));
    if (!options.length) return '';
    return `<label class="folder-add">${icon('folder')}<span class="visually-hidden">Add to folder</span>
      <select data-folder-add="${id}"><option value="">Add to folder…</option>
        ${options.map(f => `<option value="${f.id}">${esc(f.name)}</option>`).join('')}</select></label>`;
  }

  function decorate(root) {
    if (!customer() || !root) return;
    const bar = root.querySelector('.results-bar');
    if (!bar) return;
    const savedCount = window.AGroupSaved ? window.AGroupSaved.get().length : 0;
    bar.insertAdjacentHTML('afterend', folderBar(savedCount));
    root.querySelectorAll('.project-card').forEach(card => {
      const button = card.querySelector('[data-action="save"]');
      if (button) card.insertAdjacentHTML('beforeend', `<div class="folder-card-tools">${cardTools(Number(button.dataset.id))}</div>`);
    });
    if (current && !root.querySelector('.project-card')) {
      root.querySelector('.project-grid').innerHTML =
        '<div class="empty"><h3>This folder is empty.</h3><p>Open "All saved" and use "Add to folder" on a project.</p></div>';
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-folder-action]');
    if (!button) return;
    const folder = folders.find(f => f.id === current);
    const action = button.dataset.folderAction;
    if (action === 'select') { current = button.dataset.folder; refresh(); }
    else if (action === 'rename' && folder) {
      const name = prompt('Rename the folder', folder.name);
      if (name && name.trim() !== folder.name) act(call('PATCH', `/api/collections/${folder.id}`, { name }), 'Folder renamed.');
    } else if (action === 'delete' && folder) {
      if (confirm(`Delete the folder "${folder.name}"? The projects stay in your saved list.`)) {
        current = '';
        act(call('DELETE', `/api/collections/${folder.id}`), 'Folder deleted.');
      }
    } else if (action === 'remove' && folder) {
      const item = folder.items.find(i => i.project_id === reference(button.dataset.id));
      if (item) act(call('DELETE', `/api/collections/${folder.id}/items/${item.id}`), 'Removed from the folder.');
    }
  });

  document.addEventListener('change', event => {
    const select = event.target.closest('[data-folder-add]');
    if (!select || !select.value) return;
    act(call('POST', `/api/collections/${select.value}/items`, { item_type: 'PROJECT', project_id: Number(select.dataset.folderAdd) }),
        'Added to the folder.');
  });

  document.addEventListener('submit', event => {
    const form = event.target.closest('[data-folder-form]');
    if (!form) return;
    event.preventDefault();
    event.stopPropagation();
    act(call('POST', '/api/collections', { name: form.elements.name.value }), 'Folder created.');
  }, true);

  document.addEventListener('agroup:account-rendered', () => load(false));
  document.addEventListener('DOMContentLoaded', () => load(false));
  window.AGroupFolders = { shows, decorate, reload: () => load(true) };
})();
