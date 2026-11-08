/* NotificationBell boundary (S-07, View Notifications):
   displayUnread(count), displayList(items), markRead(notificationId).
   Drawn into [data-notification-bell], which account.js adds next to the avatar when logged in. */
(() => {
  'use strict';

  const icon = (name, cls) => (window.AGroupIcons ? window.AGroupIcons.icon(name, null, cls) : '');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let items = [];
  let unread = 0;

  async function api(method, url) {
    const res = await fetch(url, { method, credentials: 'same-origin' });
    return res.ok ? res.json() : null;
  }

  function when(iso) {
    const d = new Date(iso);
    return isNaN(d) ? '' : d.toLocaleString('en-SG', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  }

  function displayUnread(count) {
    document.querySelectorAll('[data-notification-count]').forEach(el => { el.textContent = count; el.hidden = count === 0; });
    document.querySelectorAll('.notification-bell').forEach(bell => {
      const badge = bell.querySelector('.notification-badge');
      badge.textContent = count > 9 ? '9+' : String(count);
      badge.hidden = count === 0;
      bell.setAttribute('aria-label', `Notifications, ${count} unread`);
    });
  }

  function displayList(list) {
    document.querySelectorAll('.notification-list').forEach(ul => {
      ul.innerHTML = list.length
        ? list.map(n => `<li><button type="button" class="notification-item${n.read ? '' : ' unread'}" data-notification="${esc(n.id)}" data-link="${esc(n.link)}">
            <span class="notification-text">${esc(n.text)}</span><small>${esc(when(n.created_at))}</small></button></li>`).join('')
        : '<li class="notification-empty">You have no notifications yet.</li>';
    });
  }

  async function load() {
    const data = await api('GET', '/api/notifications?limit=5').catch(() => null);   // bell shows the latest 5
    if (!data) return;
    items = data.items; unread = data.unread;
    displayUnread(unread);
    displayList(items);
  }

  async function markRead(notificationId, link) {
    await api('POST', `/api/notifications/${encodeURIComponent(notificationId)}/read`).catch(() => null);
    await load();                        // the link may only change the #hash, so refresh the bell first
    if (link) location.href = link;      // open the related page
  }

  function render(slot) {
    slot.innerHTML = `
      <div class="notification-menu">
        <button type="button" class="notification-bell" aria-haspopup="true" aria-expanded="false" aria-label="Notifications">
          ${icon('bell')}<span class="notification-badge" hidden>0</span></button>
        <div class="notification-panel">
          <div class="notification-head"><strong>Notifications</strong>
            <button type="button" class="text-button" data-notifications="read-all">${icon('check-check')} Mark all read</button></div>
          <ul class="notification-list"><li class="notification-empty">Loading…</li></ul>
          <a class="notification-all" href="notifications.html">View all notifications ${icon('arrow-right')}</a>
        </div>
      </div>`;
    const menu = slot.querySelector('.notification-menu');
    const bell = slot.querySelector('.notification-bell');
    const setOpen = open => { menu.classList.toggle('open', open); bell.setAttribute('aria-expanded', String(open)); if (open) load(); };

    bell.addEventListener('click', () => setOpen(!menu.classList.contains('open')));
    menu.addEventListener('click', async event => {
      const item = event.target.closest('[data-notification]');
      if (item) { setOpen(false); markRead(item.dataset.notification, item.dataset.link); }
      if (event.target.closest('[data-notifications="read-all"]')) { await api('POST', '/api/notifications/read-all'); load(); }
    });
    menu.addEventListener('keydown', event => { if (event.key === 'Escape') { setOpen(false); bell.focus(); } });
    document.addEventListener('click', event => { if (!menu.contains(event.target)) setOpen(false); });
  }

  function renderAll() {
    const slots = document.querySelectorAll('[data-notification-bell]');
    slots.forEach(render);
    if (slots.length) { displayUnread(unread); load(); }
  }

  document.addEventListener('agroup:account-rendered', renderAll);
  document.addEventListener('agroup:notifications-refresh', load);
  setInterval(() => { if (!document.hidden && document.querySelector('.notification-bell')) load(); }, 30000);

  window.AGroupNotifications = { load };
})();
