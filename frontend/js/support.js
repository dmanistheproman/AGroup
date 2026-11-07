/* ContactSupportForm boundary — submit(type, details), displayMessage(message)  (Open Support Request)
   ReportAction boundary       — reportProject(projectId, reason)                   (Report IDP)
   Open with any element carrying data-support="contact" or data-report-project="<id>" (+ data-title). */
(() => {
  'use strict';

  const icon = name => (window.AGroupIcons ? window.AGroupIcons.icon(name) : '');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const TYPES = [['TECHNICAL', 'Technical problem'], ['ACCOUNT', 'Account'], ['PROJECT', 'Project or listing'], ['OTHER', 'Other']];

  let dialog;
  function getDialog() {
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.className = 'support-dialog';
      dialog.addEventListener('click', event => {
        if (event.target === dialog || event.target.closest('[data-support-close]')) dialog.close();
      });
      document.body.appendChild(dialog);
    }
    return dialog;
  }

  function open(html) {
    const d = getDialog();
    d.innerHTML = `<div class="support-top"><p class="eyebrow">AGROUP / SUPPORT</p>
      <button type="button" class="support-close" data-support-close aria-label="Close">${icon('x')}</button></div>${html}`;
    if (!d.open) d.showModal();
    d.querySelector('textarea, select, .button')?.focus();
  }

  function displayMessage(message, isError) {
    const p = dialog.querySelector('.support-message');
    p.textContent = message;
    p.className = 'support-message ' + (isError ? 'inline-error' : 'hint');
    p.hidden = !message;
  }

  function loginFirst(what) {
    open(`<h2>Log in to ${what}.</h2><p class="hint">Customers and interior designers can contact the helpdesk after logging in.</p>
      <p class="support-actions"><a class="button" href="login.html">Log in ${icon('log-in')}</a>
      <button type="button" class="button outline" data-support-close>Cancel</button></p>`);
  }

  function signedInRequester() {
    const user = window.AGroupAccount && window.AGroupAccount.current();
    return user && (user.role === 'customer' || user.role === 'designer') ? user : null;
  }

  async function send(url, payload, button) {
    button.disabled = true;
    try {
      const res = await fetch(url, { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { displayMessage(data.error || 'The request could not be sent. Please try again.', true); return null; }
      document.dispatchEvent(new CustomEvent('agroup:notifications-refresh'));
      return data.ticket;
    } catch {
      displayMessage('Cannot reach the server. Start it with python run.py and try again.', true);
      return null;
    } finally {
      button.disabled = false;
    }
  }

  function confirmation(ticket, heading) {
    open(`<h2>${heading}</h2><p>Your reference is <b>${esc(ticket.id)}</b>. The helpdesk will follow up, and you will get a notification.</p>
      <p class="support-actions"><button type="button" class="button" data-support-close>Done</button></p>`);
  }

  /* ---- ContactSupportForm ---- */
  function openContactForm() {
    if (!signedInRequester()) return loginFirst('contact support');
    open(`<h2>Contact support.</h2><p class="hint">Tell us what went wrong. A helpdesk agent will reply inside the platform.</p>
      <form class="form-stack support-form" novalidate>
        <label>REQUEST TYPE<select name="type" required><option value="">Choose a type</option>
          ${TYPES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></label>
        <label>DETAILS<textarea name="details" maxlength="2000" required placeholder="What happened, and where?"></textarea></label>
        <p class="support-message" role="alert" aria-live="polite" hidden></p>
        <p class="support-actions"><button class="button">Send request ${icon('arrow-up-right')}</button>
          <button type="button" class="button outline" data-support-close>Cancel</button></p>
      </form>`);
    const form = dialog.querySelector('form');
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const type = form.type.value, details = form.details.value.trim();
      if (!type) return displayMessage('Choose a request type.', true);
      if (!details) return displayMessage('Describe your request.', true);
      const ticket = await send('/api/support/tickets', { type, details }, form.querySelector('.button'));
      if (ticket) confirmation(ticket, 'Request sent.');
    });
  }

  /* ---- ReportAction ---- */
  function reportProject(projectId, title) {
    if (!signedInRequester()) return loginFirst('report a project');
    open(`<h2>Report this project.</h2><p class="hint">Reporting <b>${esc(title || projectId)}</b>. Tell the helpdesk what looks misleading or inappropriate.</p>
      <form class="form-stack support-form" novalidate>
        <label>REASON<textarea name="reason" maxlength="2000" required placeholder="e.g. The photos belong to another studio."></textarea></label>
        <p class="support-message" role="alert" aria-live="polite" hidden></p>
        <p class="support-actions"><button class="button">Send report ${icon('flag')}</button>
          <button type="button" class="button outline" data-support-close>Cancel</button></p>
      </form>`);
    const form = dialog.querySelector('form');
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const reason = form.reason.value.trim();
      if (!reason) return displayMessage('Enter the reason for your report.', true);
      const ticket = await send(`/api/reports/projects/${encodeURIComponent(projectId)}`, { reason, title }, form.querySelector('.button'));
      if (ticket) confirmation(ticket, 'Report sent.');
    });
  }

  document.addEventListener('click', event => {
    const contact = event.target.closest('[data-support="contact"]');
    if (contact) { event.preventDefault(); openContactForm(); return; }
    const report = event.target.closest('[data-report-project]');
    if (report) { event.preventDefault(); reportProject(report.dataset.reportProject, report.dataset.title); }
  });

  window.AGroupSupport = { openContactForm, reportProject };
})();
