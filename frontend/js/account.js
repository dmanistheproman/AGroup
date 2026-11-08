/* Shared account state and the header account menu.
   The server session (/api/auth/...) is the source of truth; a copy of the user is kept in
   localStorage ("agroup-session") so pages can draw the header straight away. */
(() => {
  'use strict';

  const KEY = 'agroup-session';

  // Backend role -> page key used by the portal (#designer/..., #admin/...).
  const ROLE_KEYS = {
    CUSTOMER: 'customer', DESIGNER: 'designer', HELPDESK: 'helpdesk',
    USER_ADMIN: 'admin', PLATFORM_MANAGER: 'management',
  };

  // Log In use case: "the user sees the home page of their role".
  const ROLES = {
    customer:   { label: 'Customer',          home: 'index.html' },
    designer:   { label: 'Interior Designer', home: 'portal.html#designer/overview' },
    helpdesk:   { label: 'Helpdesk Agent',    home: 'portal.html#helpdesk/overview' },
    admin:      { label: 'User Admin',        home: 'portal.html#admin/overview' },
    management: { label: 'Platform Manager',  home: 'portal.html#management/overview' },
  };

  // Demo accounts shown on the login page (password "demo"; see backend user_account_repo.py).
  const DEMO_ACCOUNTS = [
    { email: 'customer@demo.agroup',     label: 'Customer · Alex Tan' },
    { email: 'designer@demo.agroup',     label: 'Form & Field' },
    { email: 'commonground@demo.agroup', label: 'Common Ground' },
    { email: 'helpdesk@demo.agroup',     label: 'Helpdesk Agent' },
    { email: 'admin@demo.agroup',        label: 'User Admin' },
    { email: 'manager@demo.agroup',      label: 'Platform Manager' },
  ];

  /* ---------- session copy ---------- */

  function current() {
    try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch { return null; }
  }

  function remember(user) {
    const copy = user ? { id: user.id, name: user.name, email: user.email, role: ROLE_KEYS[user.role] || 'customer' } : null;
    try { copy ? localStorage.setItem(KEY, JSON.stringify(copy)) : localStorage.removeItem(KEY); } catch { /* storage blocked */ }
    return copy;
  }

  const userId = () => (current() || {}).id || '';

  /* ---------- server calls ---------- */

  async function call(method, url, body) {
    const res = await fetch(url, {
      method, credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch { /* empty or non-JSON body */ }
    return { ok: res.ok, status: res.status, data };
  }

  async function signIn(email, password) {
    try {
      const r = await call('POST', '/api/auth/login', { email, password });
      if (!r.ok) return { error: r.data.error || 'Log in failed. Please try again.' };
      return { user: remember(r.data.user) };
    } catch {
      return { error: 'Cannot reach the server. Start it with python run.py and try again.' };
    }
  }

  // Create Account (S-13): customer self-registration; the server logs the new customer in.
  async function register(name, email, password) {
    try {
      const r = await call('POST', '/api/auth/register', { name, email, password });
      if (!r.ok) return { error: r.data.error || 'The account could not be created. Please try again.', field: r.data.field };
      return { user: remember(r.data.user) };
    } catch {
      return { error: 'Cannot reach the server. Start it with python run.py and try again.' };
    }
  }

  async function signOut() {
    try { await call('POST', '/api/auth/logout'); } catch { /* still clear the local copy */ }
    remember(null);
  }

  // Bring the local copy in line with the server session (e.g. after a server restart).
  async function sync() {
    try {
      const r = await call('GET', '/api/auth/me');
      const before = JSON.stringify(current());
      remember(r.ok ? r.data.user : null);
      return before !== JSON.stringify(current());
    } catch {
      return false;   // server not reachable: keep what we have
    }
  }

  function homeFor(user) {
    return (ROLES[user && user.role] || ROLES.customer).home;
  }

  /* ---------- header account menu ---------- */

  function initials(name) {
    const parts = String(name || '?').replace(/[^A-Za-z0-9 ]/g, ' ').trim().split(/\s+/);
    return ((parts[0] || '?')[0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
  }

  const icon = name => (window.AGroupIcons ? window.AGroupIcons.icon(name) : '');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function renderMenu(slot) {
    const user = current();
    if (!user) {
      slot.innerHTML = `<a class="button small" href="login.html">Log in ${icon('log-in')}</a>`;
      return;
    }
    const role = ROLES[user.role] || ROLES.customer;
    const staff = user.role !== 'customer';
    const canContactSupport = user.role === 'customer' || user.role === 'designer';
    slot.innerHTML = `
      <div class="account-bar">
      <div data-notification-bell></div>
      <div class="account-menu">
        <button class="account-avatar" type="button" aria-haspopup="true" aria-expanded="false"
                aria-label="Account menu for ${esc(user.name)}">${esc(initials(user.name))}</button>
        <div class="account-dropdown" role="menu">
          <div class="account-who"><strong>${esc(user.name)}</strong><small>${esc(role.label)}</small></div>
          ${staff ? `
          <a role="menuitem" href="${esc(role.home)}">${icon('layout-dashboard')}My workspace</a>
          <a role="menuitem" href="index.html">${icon('house')}Customer website</a>` : `
          <button type="button" role="menuitem" data-action="profile">${icon('user')}My space</button>
          <button type="button" role="menuitem" data-action="inquiries">${icon('inbox')}My enquiries</button>
          <button type="button" role="menuitem" data-action="preferences">${icon('settings')}Notification preferences</button>`}
          <a role="menuitem" href="notifications.html">${icon('bell')}Notifications<span class="menu-count" data-notification-count hidden></span></a>
          ${canContactSupport ? `<button type="button" role="menuitem" data-support="contact">${icon('life-buoy')}Contact support</button>` : ''}
          <button type="button" role="menuitem" data-account="logout">${icon('log-out')}Log out</button>
        </div>
      </div>
      </div>`;

    const menu = slot.querySelector('.account-menu');
    const toggle = slot.querySelector('.account-avatar');
    const setOpen = open => { menu.classList.toggle('open', open); toggle.setAttribute('aria-expanded', String(open)); };

    toggle.addEventListener('click', () => setOpen(!menu.classList.contains('open')));
    menu.addEventListener('click', async event => {
      if (event.target.closest('[role="menuitem"]')) setOpen(false);
      if (event.target.closest('[data-account="logout"]')) { await signOut(); renderAll(); reroutePortal(); }
    });
    menu.addEventListener('keydown', event => { if (event.key === 'Escape') { setOpen(false); toggle.focus(); } });
    document.addEventListener('click', event => { if (!menu.contains(event.target)) setOpen(false); });
  }

  // The portal shows the workspace of the logged-in role: redraw it when the session changes.
  function reroutePortal() {
    if (document.querySelector('#portal-nav')) window.dispatchEvent(new HashChangeEvent('hashchange'));
  }

  function renderAll() {
    document.querySelectorAll('[data-account-slot]').forEach(renderMenu);
    document.dispatchEvent(new CustomEvent('agroup:account-rendered'));   // lets the notification bell redraw
  }

  window.AGroupAccount = { current, userId, signIn, register, signOut, sync, homeFor, DEMO_ACCOUNTS };

  document.addEventListener('DOMContentLoaded', async () => {
    renderAll();                                   // draw from the local copy first
    if (await sync()) {                            // then follow the server session
      renderAll();
      reroutePortal();
    }
  });
})();
