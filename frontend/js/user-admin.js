/* Boundary for the User Admin's account actions on the real accounts (next to Suspend, js/suspend-account.js):
     AGroupUserAdmin.flag()                 UA-09 Flag a user account, or remove the flag (modal)
     AGroupUserAdmin.notes()                UA-10 Internal notes on a user account (modal, shared NotesPanel S-02)
     AGroupUserAdmin.history(main, stillHere)  UA-11 Action history page: actions on accounts, newest first
     AGroupUserAdmin.accounts(main, stillHere) UA-06 Account list (UA-04 search, UA-05 filters) and an account's
                                            details, with suspend (UA-01) / reactivate (UA-02), flag and notes
   portal.js opens the modals (data-action) and passes their forms to submit(); the history page is drawn through
   SharedWorkspace (admin / history). Buttons on the history page use data-ua. */
(() => {
  'use strict';

  const R = window.AGroupRecords;
  const { esc } = R;
  const toast = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));
  const modal = () => document.querySelector('#modal');
  const content = () => document.querySelector('#modal-content');

  function open(html) {
    content().innerHTML = html;
    if (!modal().open) modal().showModal();
  }

  function error(form, text) {
    const box = form.querySelector('[role="alert"]');
    box.textContent = text || '';
  }

  const accountField = `<label>ACCOUNT ID
      <input name="accountId" required maxlength="100" placeholder="e.g. CUS-101"></label>`;

  // ---------- UA-09 Flag a user account ----------
  function flag() {
    open(`<h2>Flag a user account</h2>
      <p>Flag an account suspected of breaking the platform rules, so it can be investigated. The flag also lowers the
        customer's credit status that designers see (ID-12).</p>
      <form id="ua-flag-form" class="form-stack">${accountField}
        <label>REASON FOR FLAGGING
          <textarea name="reason" maxlength="500" placeholder="What looks suspicious about this account?"></textarea></label>
        <p class="inline-error" role="alert"></p>
        <div class="row"><button class="button" type="submit" value="flag">Flag account</button>
          <button class="button outline" type="submit" value="unflag">Remove flag</button>
          <button class="text-button" type="button" data-action="close">Cancel</button></div>
      </form>`);
  }

  async function submitFlag(form, submitter) {
    const id = form.elements.accountId.value.trim();
    const reason = form.elements.reason.value.trim();
    const removing = submitter && submitter.value === 'unflag';
    error(form, '');
    if (!removing && !reason) return error(form, 'Enter the reason for flagging the account.');
    const url = `/api/user-admin/accounts/${encodeURIComponent(id)}/flag`;
    const res = removing ? await R.call('DELETE', url) : await R.call('POST', url, { reason });
    if (!res.ok) return error(form, res.data.error || 'The account could not be changed.');
    const a = res.data.account;
    modal().close();
    toast(removing ? `The flag on ${a.name} (${a.id}) was removed.` : `${a.name} (${a.id}) is flagged: ${a.flag_reason}`);
  }

  // ---------- UA-10 Internal notes on a user account ----------
  function notes() {
    open(`<h2>Internal notes on a user account</h2>
      <p>Only staff see these notes.</p>
      <form id="ua-notes-form" class="form-stack">${accountField}
        <button class="button outline" type="submit" value="show">Show the account's notes</button>
        <div id="ua-notes-list"></div>
        <label>NEW NOTE<textarea name="text" maxlength="1000" placeholder="Write a note for the other staff."></textarea></label>
        <p class="inline-error" role="alert"></p>
        <div class="row"><button class="button" type="submit" value="save">Save note</button>
          <button class="text-button" type="button" data-action="close">Cancel</button></div>
      </form>`);
  }

  function authors() {   // the logged-in staff member's own notes show their name
    const me = (window.AGroupAccount && window.AGroupAccount.current()) || {};
    return me.id ? { [me.id]: me.name || 'You' } : {};
  }

  async function showNotes(form, id) {
    const res = await R.call('GET', `/api/notes/USER_ACCOUNT/${encodeURIComponent(id)}`);
    if (!res.ok) { error(form, res.data.error || 'The notes could not be loaded.'); return false; }
    form.querySelector('#ua-notes-list').innerHTML = `<p class="eyebrow">NOTES ON ${esc(id)}</p>` + R.notesPanel(res.data.notes, authors());
    return true;
  }

  async function submitNotes(form, submitter) {
    const id = form.elements.accountId.value.trim();
    error(form, '');
    if (!submitter || submitter.value === 'show') return showNotes(form, id);
    const text = form.elements.text.value.trim();
    if (!text) return error(form, 'Write the note before saving it.');
    const res = await R.call('POST', `/api/notes/USER_ACCOUNT/${encodeURIComponent(id)}`, { text });
    if (!res.ok) return error(form, res.data.error || 'The note could not be saved.');
    form.elements.text.value = '';
    await showNotes(form, id);
    toast(`Note saved on ${id}.`);
  }

  function submit(form, submitter) {
    if (form.id === 'ua-flag-form') return submitFlag(form, submitter);
    if (form.id === 'ua-notes-form') return submitNotes(form, submitter);
  }

  // ---------- UA-11 Action history ----------
  const heading = `<div class="page-title"><div><p class="eyebrow">USER ADMIN / WORKSPACE</p><h1>Action history</h1>
    <p>Every suspension, flag and removed flag on user accounts, newest first. Select an action to see who did it and why.</p></div></div>`;

  async function history(main, stillHere) {
    main.innerHTML = heading + window.AGroupUI.state('loading');
    const res = await R.call('GET', '/api/user-admin/history');
    if (!stillHere()) return;
    if (!res.ok) { main.innerHTML = heading + window.AGroupUI.state('error', res.data.error); return; }
    const actions = res.data.actions || [];
    main.innerHTML = heading + `<section class="panel"><div class="panel-heading"><h2>Actions on accounts</h2>
        <small>${actions.length} recorded</small></div>
      ${actions.length ? `<div class="table-wrap"><table><thead><tr><th>Date</th><th>Action</th><th>Account</th><th></th></tr></thead>
        <tbody>${actions.map(a => `<tr><td>${R.time(a.date)}</td><td>${esc(a.label)}</td>
          <td>${esc(a.account_name)}<small>${esc(a.account_id)}</small></td>
          <td><button class="text-button" data-ua="action" data-id="${esc(a.id)}">View</button></td></tr>`).join('')}</tbody></table></div>`
        : window.AGroupUI.state('empty', 'No administrative actions have been recorded yet.')}</section>`;
  }

  async function showAction(id) {
    const res = await R.call('GET', `/api/user-admin/history/${encodeURIComponent(id)}`);
    if (!res.ok) { toast(res.data.error || 'This action record is unavailable.'); return; }
    const a = res.data.action;
    const account = a.account;
    open(`<p class="eyebrow">ACTION ${esc(a.id)}</p><h2>${esc(a.label)}</h2>
      <dl class="detail-list">
        <dt>Account</dt><dd>${esc(a.account_name)} (${esc(a.account_id)})${account ? ` · ${esc(R.label(account.role))} · ${R.statusBadge(account.status)}${account.flagged ? ' · flagged' : ''}` : ''}</dd>
        <dt>Date</dt><dd>${R.time(a.date)}</dd>
        <dt>Administrator</dt><dd>${esc(a.admin_name)}</dd>
        ${a.from_status || a.to_status ? `<dt>Status</dt><dd>${esc(R.label(a.from_status))} → ${esc(R.label(a.to_status))}</dd>` : ''}
        <dt>Reason</dt><dd>${a.reason ? esc(a.reason) : '—'}</dd></dl>
      <div class="row"><button class="button outline" data-action="close">Close</button></div>`);
  }

  // ---------- UA-06 Accounts: list (UA-04 search, UA-05 filters) and details (UA-01, UA-02, UA-09, UA-10) ----------
  const ROLES = ['CUSTOMER', 'DESIGNER', 'HELPDESK', 'USER_ADMIN', 'PLATFORM_MANAGER'];
  const STATUSES = ['ACTIVE', 'SUSPENDED'];
  let listing = { q: '', role: '', status: '', page: 1 };
  let drawAccounts = null;   // redraws the list after a change

  const accountsHeading = `<div class="page-title"><div><p class="eyebrow">USER ADMIN / WORKSPACE</p><h1>Accounts</h1>
    <p>Find an account by name or email, filter by role or status, and open it to suspend, reactivate, flag or add a note.</p></div></div>`;

  function filters() {
    const options = (values, chosen, all) => `<option value="">${all}</option>` + values.map(v =>
      `<option value="${v}"${v === chosen ? ' selected' : ''}>${esc(R.label(v))}</option>`).join('');
    return `<form id="ua-accounts-filter" class="row filters">
      <label>SEARCH<input name="q" value="${esc(listing.q)}" placeholder="Name or email" maxlength="100"></label>
      <label>ROLE<select name="role">${options(ROLES, listing.role, 'All roles')}</select></label>
      <label>STATUS<select name="status">${options(STATUSES, listing.status, 'All statuses')}</select></label>
      <button class="button outline" type="submit">Search</button></form>`;
  }

  async function accounts(main, stillHere) {
    drawAccounts = () => accounts(main, stillHere);
    main.innerHTML = accountsHeading + window.AGroupUI.state('loading');
    const query = new URLSearchParams(Object.entries(listing).filter(([, v]) => v !== '' && v !== null));
    const res = await R.call('GET', `/api/user-admin/accounts?${query}`);
    if (!stillHere()) return;
    if (!res.ok) { main.innerHTML = accountsHeading + window.AGroupUI.state('error', res.data.error); return; }
    const { items, total, page, pages } = res.data;
    main.innerHTML = accountsHeading + `<section class="panel">${filters()}
      <div class="panel-heading"><h2>User accounts</h2><small>${total} found</small></div>
      ${items.length ? `<div class="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th></th></tr></thead>
        <tbody>${items.map(a => `<tr><td>${esc(a.name)}<small>${esc(a.id)}</small></td><td>${esc(a.email)}</td>
          <td>${esc(R.label(a.role))}</td><td>${R.statusBadge(a.status)}${a.flagged ? ' <small>flagged</small>' : ''}</td>
          <td><button class="text-button" data-ua="account" data-id="${esc(a.id)}">Open</button></td></tr>`).join('')}</tbody></table></div>
        <div class="row pager"><button class="text-button" data-ua="page" data-page="${page - 1}"${page <= 1 ? ' disabled' : ''}>Previous</button>
          <small>Page ${page} of ${pages}</small>
          <button class="text-button" data-ua="page" data-page="${page + 1}"${page >= pages ? ' disabled' : ''}>Next</button></div>`
        : window.AGroupUI.state('empty', 'No accounts match the search.')}</section>`;
  }

  async function showAccount(id) {
    const res = await R.call('GET', `/api/user-admin/accounts/${encodeURIComponent(id)}`);
    if (!res.ok) { toast(res.data.error || 'This account could not be opened.'); return; }
    const { account: a, allowed_statuses: allowed } = res.data;
    const move = allowed.includes('SUSPENDED') ? ['suspend', 'Suspend account', 'Why is the account suspended?']
      : allowed.includes('ACTIVE') ? ['reactivate', 'Reactivate account', 'Why can the account be used again?'] : null;
    open(`<p class="eyebrow">ACCOUNT ${esc(a.id)}</p><h2>${esc(a.name)}</h2>
      <dl class="detail-list"><dt>Email</dt><dd>${esc(a.email)}</dd><dt>Role</dt><dd>${esc(R.label(a.role))}</dd>
        <dt>Status</dt><dd>${R.statusBadge(a.status)}</dd>
        <dt>Flag</dt><dd>${a.flagged ? esc(a.flag_reason || 'Flagged') : 'Not flagged'}</dd></dl>
      ${move ? `<form id="ua-account-status" class="form-stack" data-id="${esc(a.id)}" data-move="${move[0]}">
        <label>REASON<textarea name="reason" required maxlength="500" placeholder="${move[2]}"></textarea></label>
        <p class="inline-error" role="alert"></p>
        <div class="row"><button class="button" type="submit">${move[1]}</button></div></form>` : ''}
      <div class="row"><button class="button outline" data-ua="flag" data-id="${esc(a.id)}">Flag or remove flag</button>
        <button class="button outline" data-ua="notes" data-id="${esc(a.id)}">Internal notes</button>
        <button class="text-button" data-action="close">Close</button></div>`);
  }

  async function submitStatus(form) {
    const reason = form.elements.reason.value.trim();
    error(form, '');
    if (!reason) return error(form, 'Enter the reason.');
    const res = await R.call('POST', `/api/user-admin/accounts/${encodeURIComponent(form.dataset.id)}/${form.dataset.move}`,
                             { reason });
    if (!res.ok) return error(form, res.data.error || 'The account could not be changed.');
    modal().close();
    toast(form.dataset.move === 'suspend' ? 'Account suspended.' : 'Account reactivated.');
    if (drawAccounts) drawAccounts();
  }

  function withAccount(openModal, id) {   // the flag and notes modals, already filled in with this account
    openModal();
    content().querySelector('[name="accountId"]').value = id;
  }

  document.addEventListener('submit', event => {
    const form = event.target;
    if (form.id === 'ua-accounts-filter') {
      event.preventDefault();
      listing = { ...listing, ...Object.fromEntries(new FormData(form)), page: 1 };
      if (drawAccounts) drawAccounts();
    } else if (form.id === 'ua-account-status') {
      event.preventDefault();
      submitStatus(form);
    }
  });

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-ua]');
    if (!button) return;
    const kind = button.dataset.ua;
    if (kind === 'action') showAction(button.dataset.id);
    else if (kind === 'account') showAccount(button.dataset.id);
    else if (kind === 'page' && !button.disabled) { listing.page = Number(button.dataset.page); drawAccounts(); }
    else if (kind === 'flag') withAccount(flag, button.dataset.id);
    else if (kind === 'notes') withAccount(notes, button.dataset.id);
  });

  window.AGroupUserAdmin = { flag, notes, submit, history, accounts };
})();
