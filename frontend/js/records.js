/* Shared record components (S-04, S-20, S-01, S-02), used by the portal and the customer pages:
     AGroupRecords.statusBadge(status)                       StatusBadge
     AGroupRecords.confirmWithReason({title, ...}) -> Promise ConfirmWithReasonDialog (resolves the reason, or null)
     AGroupRecords.historyTimeline(entries)                  HistoryTimeline (audit log entries)
     AGroupRecords.messageThread(messages, meId, names)      MessageThread
     AGroupRecords.notesPanel(notes, names)                  NotesPanel
     AGroupRecords.call(method, url, body) -> {ok, status, data}
*/
(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = name => (window.AGroupIcons ? window.AGroupIcons.icon(name) : '');
  const ATTENTION = ['OPEN', 'AWAITING_INFO', 'ESCALATED', 'PENDING_REVIEW', 'AWAITING_REPLY',
                     'WAITING_CLIENT_CONFIRMATION', 'HIDDEN', 'SUSPENDED'];

  function label(status) {
    const text = String(status || '').toLowerCase().replace(/_/g, ' ');
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function time(iso) {
    if (!iso) return '';
    const date = new Date(iso);
    return isNaN(date) ? esc(iso) : date.toLocaleString('en-SG', { dateStyle: 'medium', timeStyle: 'short' });
  }

  function statusBadge(status) {
    return `<span class="status record-status ${ATTENTION.includes(status) ? 'dark' : ''}">${esc(label(status))}</span>`;
  }

  async function call(method, url, body) {
    const res = await fetch(url, {
      method, credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  }

  // ConfirmWithReasonDialog: its own <dialog>, so it can open on top of a record page.
  function confirmWithReason({ title, message = '', confirmLabel = 'Confirm', reasonRequired = true,
                               placeholder = 'Explain the reason. The other side will see it.' }) {
    let dialog = document.querySelector('#reason-dialog');
    if (!dialog) {
      dialog = document.createElement('dialog');
      dialog.id = 'reason-dialog';
      dialog.className = 'reason-dialog';
      document.body.append(dialog);
    }
    dialog.innerHTML = `<form method="dialog" class="form-stack">
      <h2>${esc(title)}</h2>${message ? `<p>${esc(message)}</p>` : ''}
      <label>REASON${reasonRequired ? '' : ' (OPTIONAL)'}
        <textarea name="reason" maxlength="500" ${reasonRequired ? 'required' : ''} placeholder="${esc(placeholder)}"></textarea></label>
      <p class="inline-error" role="alert" hidden></p>
      <div class="reason-actions"><button class="button" value="confirm">${esc(confirmLabel)}</button>
        <button class="text-button" value="cancel" formnovalidate>Cancel</button></div></form>`;
    return new Promise(resolve => {
      const form = dialog.querySelector('form');
      form.addEventListener('submit', event => {
        const confirmed = event.submitter && event.submitter.value === 'confirm';
        const reason = form.elements.reason.value.trim();
        if (confirmed && reasonRequired && !reason) {
          event.preventDefault();
          const error = form.querySelector('.inline-error');
          error.textContent = 'Give a reason first.';
          error.hidden = false;
          return;
        }
        event.stopPropagation();
        resolve(confirmed ? reason : null);
      }, { capture: true });
      dialog.addEventListener('cancel', () => resolve(null), { once: true });
      dialog.showModal();
      form.elements.reason.focus();
    });
  }

  function historyTimeline(entries, names = {}) {
    if (!entries || !entries.length) return '<p class="small-note">No status changes yet.</p>';
    return `<ol class="history-timeline">${entries.map(e => `<li>
      <b>${esc(label(e.from_status))} → ${esc(label(e.to_status))}</b>
      <small>${esc(names[e.actor_id] || e.actor_id || '')} · ${time(e.created_at)}</small>
      ${e.reason ? `<p>${esc(e.reason)}</p>` : ''}</li>`).join('')}</ol>`;
  }

  // reportable: show "Report" on other people's messages (S-15 report a message).
  function messageThread(messages, meId, names = {}, { reportable = false } = {}) {
    if (!messages || !messages.length) return '<p class="small-note">No messages yet.</p>';
    return `<ol class="message-thread">${messages.map(m => `<li class="${m.author_id === meId ? 'mine' : ''}">
      <small>${esc(m.author_id === meId ? 'You' : (names[m.author_id] || m.author_id))} · ${time(m.sent_at)}</small>
      <p>${esc(m.body)}</p>${reportable && m.author_id !== meId ? `<button type="button" class="text-button report-message"
        data-report-message="${esc(m.id)}">${icon('flag')} Report</button>` : ''}</li>`).join('')}</ol>`;
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-report-message]');
    if (!button) return;
    const reason = await confirmWithReason({ title: 'Report this message',
      message: 'The helpdesk will see this message and your reason.', confirmLabel: 'Send report',
      placeholder: 'For example: asks me to pay outside the platform.' });
    if (reason === null) return;
    const r = await call('POST', `/api/reports/messages/${encodeURIComponent(button.dataset.reportMessage)}`, { reason });
    const say = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));
    say(r.ok ? `Report sent. Your reference is ${r.data.ticket.id}.` : (r.data.error || 'The report could not be sent.'));
  });

  function notesPanel(notes, names = {}) {
    if (!notes || !notes.length) return '<p class="small-note">No internal notes yet.</p>';
    return `<ul class="notes-panel">${notes.map(n => `<li>${icon('sticky-note')}<div><p>${esc(n.text)}</p>
      <small>${esc(names[n.author_id] || n.author_id)} · ${time(n.created_at)}</small></div></li>`).join('')}</ul>`;
  }

  window.AGroupRecords = { esc, icon, label, time, statusBadge, call, confirmWithReason, historyTimeline,
                           messageThread, notesPanel };
})();
