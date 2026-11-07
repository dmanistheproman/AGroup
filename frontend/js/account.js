/* Shared account state and the header account menu.
   Demo only: the session is kept in this browser (localStorage key "agroup-session")
   until the backend login (/api/auth/...) is connected. */
(() => {
  'use strict';

  const KEY = 'agroup-session';

  // Role -> where the role's home page is (Log In use case: "the user sees the home page of their role").
  const ROLES = {
    customer:   { label: 'Customer',          home: 'index.html' },
    designer:   { label: 'Interior Designer', home: 'portal.html#designer/overview' },
    helpdesk:   { label: 'Helpdesk Agent',    home: 'portal.html#helpdesk/overview' },
    admin:      { label: 'User Admin',        home: 'portal.html#admin/overview' },
    management: { label: 'Platform Manager',  home: 'portal.html#management/overview' },
  };

  // Demo accounts offered on the login page. Any other email signs in as a customer.
  const DEMO_ACCOUNTS = [
    { email: 'customer@demo.agroup', name: 'Alex Tan',         role: 'customer' },
    { email: 'designer@demo.agroup', name: 'Form & Field',     role: 'designer' },
    { email: 'helpdesk@demo.agroup', name: 'Helpdesk Agent',   role: 'helpdesk' },
    { email: 'admin@demo.agroup',    name: 'User Admin',       role: 'admin' },
    { email: 'manager@demo.agroup',  name: 'Platform Manager', role: 'management' },
  ];

  function current() {
    try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch { return null; }
  }

  function signIn(email) {
    const known = DEMO_ACCOUNTS.find(a => a.email === email.toLowerCase());
    const user = known
      ? { ...known, demo: true }
      : { email, name: email.split('@')[0], role: 'customer', demo: true };
    try { localStorage.setItem(KEY, JSON.stringify(user)); } catch { /* storage blocked: stays signed out */ }
    return user;
  }

  function signOut() {
    try { localStorage.removeItem(KEY); } catch { /* nothing to clear */ }
  }

  function homeFor(user) {
    return (ROLES[user && user.role] || ROLES.customer).home;
  }

  function initials(name) {
    const parts = String(name || '?').replace(/[^A-Za-z0-9 ]/g, ' ').trim().split(/\s+/);
    return ((parts[0] || '?')[0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
  }

  const icon = name => (window.AGroupIcons ? window.AGroupIcons.icon(name) : '');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  /* ---------- header account menu ---------- */

  function renderMenu(slot) {
    const user = current();
    if (!user) {
      slot.innerHTML = `<a class="button small" href="login.html">Log in ${icon('log-in')}</a>`;
      return;
    }
    const role = ROLES[user.role] || ROLES.customer;
    const staff = user.role !== 'customer';
    slot.innerHTML = `
      <div class="account-menu">
        <button class="account-avatar" type="button" aria-haspopup="true" aria-expanded="false"
                aria-label="Account menu for ${esc(user.name)}">${esc(initials(user.name))}</button>
        <div class="account-dropdown" role="menu">
          <div class="account-who"><strong>${esc(user.name)}</strong><small>${esc(role.label)}${user.demo ? ' · demo' : ''}</small></div>
          <button type="button" role="menuitem" data-action="profile">${icon('user')}My space</button>
          <button type="button" role="menuitem" data-action="inquiries">${icon('inbox')}My enquiries</button>
          <button type="button" role="menuitem" data-action="preferences">${icon('bell')}Notification preferences</button>
          ${staff ? `<a role="menuitem" href="${esc(role.home)}">${icon('layout-dashboard')}My workspace</a>` : ''}
          <button type="button" role="menuitem" data-account="logout">${icon('log-out')}Log out</button>
        </div>
      </div>`;

    const menu = slot.querySelector('.account-menu');
    const toggle = slot.querySelector('.account-avatar');
    const setOpen = open => { menu.classList.toggle('open', open); toggle.setAttribute('aria-expanded', String(open)); };

    toggle.addEventListener('click', () => setOpen(!menu.classList.contains('open')));
    menu.addEventListener('click', event => {
      if (event.target.closest('[role="menuitem"]')) setOpen(false);
      if (event.target.closest('[data-account="logout"]')) { signOut(); renderMenu(slot); }
    });
    menu.addEventListener('keydown', event => { if (event.key === 'Escape') { setOpen(false); toggle.focus(); } });
    document.addEventListener('click', event => { if (!menu.contains(event.target)) setOpen(false); });
  }

  window.AGroupAccount = { current, signIn, signOut, homeFor, DEMO_ACCOUNTS };

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-account-slot]').forEach(renderMenu);
  });
})();
