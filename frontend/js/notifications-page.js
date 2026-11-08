/* Notification list page (S-07, View Notifications): every notification, newest first.
   Filter All / Unread, mark all read; selecting one marks it read and opens the related page. */
(() => {
  'use strict';

  const icon = (name, cls) => (window.AGroupIcons ? window.AGroupIcons.icon(name, null, cls) : '');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const TYPE_ICONS = { WELCOME: 'house', TICKET_OPENED: 'life-buoy', TICKET_STATUS: 'life-buoy',
                       NEW_TICKET: 'inbox', NEW_REPORT: 'flag', MESSAGE: 'message-square' };

  const list = document.querySelector('.notification-cards');
  const toolbar = document.querySelector('.notification-toolbar');
  let filter = 'all';
  let items = [];

  function when(iso) {
    const d = new Date(iso);
    return isNaN(d) ? '' : d.toLocaleString('en-SG', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function backLink() {
    const user = window.AGroupAccount && window.AGroupAccount.current();
    const a = document.querySelector('#back-link');
    const toWorkspace = user && user.role !== 'customer';
    a.href = toWorkspace ? window.AGroupAccount.homeFor(user) : 'index.html';
    a.innerHTML = `${icon('arrow-left')} ${toWorkspace ? 'Back to workspace' : 'Back to website'}`;
  }

  function render() {
    const unread = items.filter(n => !n.read).length;
    document.querySelector('[data-count="all"]').textContent = items.length;
    document.querySelector('[data-count="unread"]').textContent = unread;
    document.querySelectorAll('[data-filter]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.filter === filter)));
    const readAll = document.querySelector('[data-page-action="read-all"]');
    readAll.innerHTML = `${icon('check-check')} Mark all read`;
    readAll.disabled = unread === 0;

    const shown = filter === 'unread' ? items.filter(n => !n.read) : items;
    list.innerHTML = shown.length
      ? shown.map(n => `<li><button type="button" class="notification-card${n.read ? '' : ' unread'}" data-id="${esc(n.id)}" data-link="${esc(n.link)}">
          <span class="notification-type">${icon(TYPE_ICONS[n.type] || 'bell')}</span>
          <span class="notification-body"><span class="notification-text">${esc(n.text)}</span><small>${esc(when(n.created_at))}</small></span>
          ${n.read ? '' : '<span class="notification-dot" aria-label="Unread"></span>'}
        </button></li>`).join('')
      : `<li class="notification-empty">${filter === 'unread' ? 'You have no unread notifications.' : 'You have no notifications yet.'}</li>`;
  }

  async function load() {
    const res = await fetch('/api/notifications', { credentials: 'same-origin' }).catch(() => null);
    if (!res || res.status === 401) return showLogin();
    if (!res.ok) { list.innerHTML = '<li class="notification-empty">Notifications could not be loaded. Please try again.</li>'; return; }
    items = (await res.json()).items;
    toolbar.hidden = false;
    render();
  }

  function showLogin() {
    toolbar.hidden = true;
    list.innerHTML = `<li class="notification-empty">Log in to see your notifications.<br><br>
      <a class="button" href="login.html">Log in ${icon('log-in')}</a></li>`;
  }

  async function post(url) {
    return fetch(url, { method: 'POST', credentials: 'same-origin' }).catch(() => null);
  }

  document.addEventListener('click', async event => {
    const tab = event.target.closest('[data-filter]');
    if (tab) { filter = tab.dataset.filter; render(); return; }
    if (event.target.closest('[data-page-action="read-all"]')) {
      await post('/api/notifications/read-all');
      await load();
      document.dispatchEvent(new CustomEvent('agroup:notifications-refresh'));   // header bell
      return;
    }
    const card = event.target.closest('.notification-card');
    if (card) {
      await post(`/api/notifications/${encodeURIComponent(card.dataset.id)}/read`);
      if (card.dataset.link) location.href = card.dataset.link;
      else { await load(); document.dispatchEvent(new CustomEvent('agroup:notifications-refresh')); }
    }
  });

  document.addEventListener('DOMContentLoaded', () => { backLink(); load(); });
  document.addEventListener('agroup:account-rendered', backLink);
})();
