/* Shared workspace pages in the portal, on the real APIs (S-01, S-02, S-04, S-05, S-15, S-16, S-20, HD-05, HD-08, HD-09).
   portal.js asks SharedWorkspace.handles(role, section) and calls render(role, section) for:
     helpdesk: overview, tickets (active queue), resolved, complaints (reports), uploads (failed uploads)
     designer: messages (private conversations with customers)
   The ticket page opens in the portal's #modal. Buttons use data-shared (portal.js owns data-action). */
(() => {
  'use strict';

  const R = window.AGroupRecords;
  const { esc, icon, statusBadge } = R;
  const HANDLED = { helpdesk: ['overview', 'tickets', 'resolved', 'complaints', 'uploads'], designer: ['messages'] };
  const ACTIVE = ['OPEN', 'AWAITING_INFO', 'ESCALATED'];
  const DONE = ['RESOLVED', 'CLOSED', 'MERGED'];
  const TYPES = { ACCOUNT: 'Account', TECHNICAL: 'Technical problem', PROJECT: 'Project or listing', OTHER: 'Other',
                  REPORT_IDP: 'Reported IDP', REPORT_MESSAGE: 'Reported message' };
  const MOVE_LABEL = { AWAITING_INFO: 'Ask for information', ESCALATED: 'Escalate', RESOLVED: 'Resolve',
                       CLOSED: 'Close', OPEN: 'Reopen', MERGED: 'Mark as merged' };

  let generation = 0;                // ignore answers that arrive after the user moved on
  let list = { section: '', page: 1, q: '', status: '', type: '', handler: '' };
  let openTicket = null;             // ticket shown in the modal
  let openConversation = null;       // designer messages page

  const main = () => document.querySelector('#portal-main');
  const me = () => (window.AGroupAccount && window.AGroupAccount.current()) || {};
  const toast = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));
  const time = R.time;

  function handles(role, section) { return (HANDLED[role] || []).includes(section); }
  function leave() { generation++; }

  function title(role, heading, text) {
    const label = role === 'helpdesk' ? 'HELPDESK' : 'INTERIOR DESIGNER';
    return `<div class="page-title"><div><p class="eyebrow">${label} / WORKSPACE</p><h1>${esc(heading)}</h1><p>${esc(text)}</p></div></div>`;
  }

  async function render(role, section) {
    const mine = ++generation;
    const stillHere = () => mine === generation;
    if (role === 'helpdesk' && section === 'overview') return overview(stillHere);
    if (role === 'helpdesk' && section === 'uploads') return uploads(stillHere);
    if (role === 'helpdesk') {
      if (list.section !== section) list = { section, page: 1, q: '', status: '', type: '', handler: '' };
      return ticketList(stillHere);
    }
    if (role === 'designer' && section === 'messages') return messages(stillHere);
  }

  // ---------- Helpdesk overview ----------
  async function overview(stillHere) {
    main().innerHTML = title('helpdesk', 'Your support desk, at a glance.', 'Live numbers from the ticket queue.') +
      '<p class="small-note">Loading…</p>';
    const count = async q => ((await R.call('GET', `/api/support/tickets?page_size=1&${q}`)).data.total || 0);
    const [active, unassigned, waiting, escalated, reports, failures, mine] = await Promise.all([
      count('scope=active'), count('scope=active&handler=none'), count('status=AWAITING_INFO'),
      count('status=ESCALATED'), count('scope=active&type=REPORTS'),
      R.call('GET', '/api/uploads/failures?page_size=1').then(r => r.data.total || 0),
      R.call('GET', '/api/support/tickets?scope=active&handler=me&page_size=5').then(r => r.data.items || [])]);
    if (!stillHere()) return;
    const metric = (label, value, note, link) => `<a class="metric metric-link" href="#helpdesk/${link}">
      <p>${label}</p><strong>${value}</strong><small>${note}</small></a>`;
    main().innerHTML = title('helpdesk', 'Your support desk, at a glance.', 'Live numbers from the ticket queue.') +
      `<div class="metric-grid">${metric('Active tickets', active, `${unassigned} not claimed yet`, 'tickets')}
        ${metric('Waiting for the requester', waiting, 'Awaiting information', 'tickets')}
        ${metric('Escalated', escalated, 'Need the platform team', 'tickets')}
        ${metric('Open reports', reports, `${failures} failed uploads logged`, 'complaints')}</div>` +
      `<section class="panel"><div class="panel-heading"><h2>My active tickets</h2><small>Claimed by you</small></div>
        ${mine.length ? ticketTable(mine) : '<div class="panel-body"><p class="small-note">You have not claimed any active tickets. Open the queue to pick one.</p></div>'}</section>`;
  }

  // ---------- Ticket lists (queue, resolved, complaints) ----------
  function query() {
    const p = new URLSearchParams({ page: list.page, page_size: 15 });
    if (list.section === 'tickets') p.set('scope', 'active');
    if (list.section === 'resolved') p.set('scope', 'done');
    if (list.section === 'complaints') { p.set('type', 'REPORTS'); }
    else if (list.type) p.set('type', list.type);
    for (const key of ['q', 'status', 'handler']) if (list[key]) p.set(key, list[key]);
    return p.toString();
  }

  function ticketTable(items) {
    return `<div class="table-wrap"><table><thead><tr><th>Reference</th><th>Request</th><th>Requester</th><th>Status</th>
      <th>Handler</th><th>Opened</th><th></th></tr></thead><tbody>${items.map(t => `<tr>
        <td>${esc(t.id)}</td>
        <td><b>${esc(t.type_label || TYPES[t.type] || t.type)}</b><small>${esc(t.related_project_title ? `${t.related_project_title} · ` : '')}${esc((t.details || '').slice(0, 90))}</small></td>
        <td>${esc(t.requester_name || t.requester_id)}<small>${esc(t.requester_type === 'DESIGNER' ? 'Interior designer' : 'Customer')}</small></td>
        <td>${statusBadge(t.status)}</td><td>${esc(t.handler_name || 'Not claimed')}</td><td>${time(t.created_at)}</td>
        <td><button class="text-button" data-shared="open-ticket" data-id="${esc(t.id)}">Open ${icon('arrow-right')}</button></td>
      </tr>`).join('')}</tbody></table></div>`;
  }

  async function ticketList(stillHere) {
    const heading = { tickets: ['Active ticket queue', 'Open, awaiting information and escalated tickets.'],
                      resolved: ['Resolved tickets', 'Resolved, closed and merged tickets.'],
                      complaints: ['Complaints & listings', 'Reports about projects and messages.'] }[list.section];
    const statuses = list.section === 'resolved' ? DONE : ACTIVE;
    const r = await R.call('GET', `/api/support/tickets?${query()}`);
    if (!stillHere()) return;
    if (!r.ok) { main().innerHTML = title('helpdesk', heading[0], heading[1]) + `<p class="inline-error">${esc(r.data.error || 'Could not load tickets.')}</p>`; return; }
    const d = r.data;
    const option = (value, text, current) => `<option value="${value}" ${current === value ? 'selected' : ''}>${text}</option>`;
    main().innerHTML = title('helpdesk', heading[0], heading[1]) +
      `<form class="portal-toolbar" data-shared-form="filters">
        <label>SEARCH<input name="q" value="${esc(list.q)}" placeholder="Reference, details or project"></label>
        <label>STATUS<select name="status">${option('', 'All', list.status)}${statuses.map(s => option(s, R.label(s), list.status)).join('')}</select></label>
        ${list.section === 'complaints' ? '' : `<label>TYPE<select name="type">${option('', 'All types', list.type)}${Object.entries(TYPES).map(([k, v]) => option(k, v, list.type)).join('')}</select></label>`}
        <label>HANDLER<select name="handler">${option('', 'Anyone', list.handler)}${option('me', 'Claimed by me', list.handler)}${option('none', 'Not claimed', list.handler)}</select></label>
        <button class="button outline" type="submit">${icon('search')} Apply</button></form>` +
      `<section class="panel"><div class="panel-heading"><h2>${d.total} ticket${d.total === 1 ? '' : 's'}</h2><small>Page ${d.page} of ${d.pages}</small></div>
        ${d.items.length ? ticketTable(d.items) : '<div class="panel-body"><p class="small-note">No tickets match these filters.</p></div>'}
        <div class="pager"><button class="text-button" data-shared="page" data-page="${d.page - 1}" ${d.page <= 1 ? 'disabled' : ''}>${icon('arrow-left')} Previous</button>
          <button class="text-button" data-shared="page" data-page="${d.page + 1}" ${d.page >= d.pages ? 'disabled' : ''}>Next ${icon('arrow-right')}</button></div></section>`;
  }

  // ---------- Ticket page (RecordPage) ----------
  function modal() { return { dialog: document.querySelector('#modal'), content: document.querySelector('#modal-content') }; }

  async function showTicket(id) {
    const [page, notes] = await Promise.all([R.call('GET', `/api/support/tickets/${encodeURIComponent(id)}`),
                                            R.call('GET', `/api/notes/REQUEST/${encodeURIComponent(id)}`)]);
    if (!page.ok) { toast(page.data.error || 'Could not open the ticket.'); return; }
    const { ticket, messages, history, allowed_statuses: allowed, names } = page.data;
    openTicket = ticket;
    const user = me();
    const readOnly = ['MERGED', 'CLOSED'].includes(ticket.status);
    const project = ticket.related_project_id;
    const projectNumber = project ? Number(String(project).replace('IDP-', '')) : null;
    const { dialog, content } = modal();
    content.innerHTML = `<div class="record-page">
      <div class="record-header"><div><p class="eyebrow">${esc(ticket.id)} · ${esc(ticket.type_label)}</p>
        <h2>${esc(names[ticket.requester_id] || ticket.requester_id)}</h2></div>${statusBadge(ticket.status)}</div>
      <dl class="detail-list">
        <dt>Requester</dt><dd>${esc(names[ticket.requester_id] || ticket.requester_id)} (${ticket.requester_type === 'DESIGNER' ? 'interior designer' : 'customer'})</dd>
        <dt>Opened</dt><dd>${time(ticket.created_at)}</dd>
        <dt>Handler</dt><dd>${esc(names[ticket.handler_id] || 'Not claimed')}</dd>
        ${project ? `<dt>Project</dt><dd>${esc(ticket.related_project_title || project)} (${esc(project)}) · <a href="index.html#project-${projectNumber}" target="_blank" rel="noopener">View project</a></dd>` : ''}
        ${ticket.merged_into_id ? `<dt>Merged into</dt><dd><button class="text-button" data-shared="open-ticket" data-id="${esc(ticket.merged_into_id)}">${esc(ticket.merged_into_id)}</button></dd>` : ''}
        ${ticket.resolution_note ? `<dt>Resolution</dt><dd>${esc(ticket.resolution_note)}</dd>` : ''}
        ${page.data.reported_message ? `<dt>Reported message</dt><dd><blockquote class="reported-message">${esc(page.data.reported_message.body)}
          <small>${esc(names[page.data.reported_message.author_id] || page.data.reported_message.author_id)} · ${time(page.data.reported_message.sent_at)}</small></blockquote></dd>` : ''}
        <dt>Details</dt><dd>${esc(ticket.details)}</dd></dl>
      <div class="record-actions">
        ${ticket.handler_id !== user.id && !readOnly ? `<button class="button outline" data-shared="claim">${icon('user-check')} Claim</button>` : ''}
        ${allowed.filter(s => s !== 'MERGED').map(s => `<button class="button outline" data-shared="move" data-status="${s}">${esc(MOVE_LABEL[s] || R.label(s))}</button>`).join('')}
        ${project && ticket.type === 'REPORT_IDP' ? `<button class="button outline" data-shared="hide-project" data-project="${esc(project)}">${icon('eye-off')} Hide project</button>` : ''}
      </div>
      ${!readOnly ? `<form class="merge-form" data-shared-form="merge">
        <label>MERGE A DUPLICATE INTO THIS TICKET<input name="other" placeholder="Duplicate ticket reference, e.g. TKT-1002" required></label>
        <button class="button outline" type="submit">${icon('merge')} Merge</button></form>` : ''}
      <h3>${icon('message-square')} Conversation with the requester</h3>
      ${R.messageThread(messages, user.id, names)}
      ${readOnly ? '<p class="small-note">This ticket is read-only.</p>' : `<form class="reply-form" data-shared-form="reply">
        <label class="visually-hidden" for="reply-body">Reply</label>
        <textarea id="reply-body" name="body" maxlength="2000" required placeholder="Write to the requester"></textarea>
        <button class="button" type="submit">${icon('send')} Send</button></form>`}
      <h3>${icon('sticky-note')} Internal notes <small>(staff only)</small></h3>
      ${R.notesPanel(notes.ok ? notes.data.notes : [], names)}
      <form class="reply-form" data-shared-form="note"><label class="visually-hidden" for="note-text">Internal note</label>
        <textarea id="note-text" name="text" maxlength="2000" required placeholder="Add a note for other agents"></textarea>
        <button class="button outline" type="submit">${icon('sticky-note')} Add note</button></form>
      <h3>${icon('history')} History</h3>${R.historyTimeline(history, names)}</div>`;
    if (!dialog.open) dialog.showModal();
  }

  async function afterChange(result, success) {
    if (!result.ok) { toast(result.data.error || 'That did not work.'); return false; }
    if (success) toast(success);
    if (openTicket) await showTicket(openTicket.id);
    if (list.section && location.hash.startsWith('#helpdesk/')) render('helpdesk', location.hash.split('/')[1]);
    return true;
  }

  // ---------- Failed uploads (HD-08) ----------
  let uploadsQuery = { q: '', page: 1 };
  async function uploads(stillHere) {
    const p = new URLSearchParams({ page: uploadsQuery.page, page_size: 20, q: uploadsQuery.q });
    const r = await R.call('GET', `/api/uploads/failures?${p}`);
    if (!stillHere()) return;
    const d = r.data;
    main().innerHTML = title('helpdesk', 'Upload diagnostics', 'Files the platform refused, with who tried and why.') +
      `<form class="portal-toolbar" data-shared-form="uploads"><label>SEARCH<input name="q" value="${esc(uploadsQuery.q)}" placeholder="File name, reason, user or project"></label>
        <button class="button outline" type="submit">${icon('search')} Search</button></form>
      <section class="panel"><div class="panel-heading"><h2>${d.total || 0} failed upload${d.total === 1 ? '' : 's'}</h2><small>Page ${d.page || 1} of ${d.pages || 1}</small></div>
      ${(d.items || []).length ? `<div class="table-wrap"><table><thead><tr><th>When</th><th>File</th><th>User</th><th>Project</th><th>Reason</th></tr></thead><tbody>
        ${d.items.map(f => `<tr><td>${time(f.occurred_at)}</td><td>${esc(f.file_name)}</td><td>${esc(f.user_id || '—')}</td><td>${esc(f.project_id || '—')}</td><td>${esc(f.reason)}</td></tr>`).join('')}
      </tbody></table></div>` : '<div class="panel-body"><p class="small-note">No failed uploads.</p></div>'}
      <div class="pager"><button class="text-button" data-shared="uploads-page" data-page="${(d.page || 1) - 1}" ${(d.page || 1) <= 1 ? 'disabled' : ''}>${icon('arrow-left')} Previous</button>
        <button class="text-button" data-shared="uploads-page" data-page="${(d.page || 1) + 1}" ${(d.page || 1) >= (d.pages || 1) ? 'disabled' : ''}>Next ${icon('arrow-right')}</button></div></section>`;
  }

  // ---------- Designer: private conversations (S-16) ----------
  async function messages(stillHere) {
    const r = await R.call('GET', '/api/conversations');
    if (!stillHere()) return;
    const conversations = r.ok ? r.data.conversations : [];
    if (!openConversation && conversations.length) openConversation = conversations[0];
    let thread = '';
    if (openConversation) {
      const m = await R.call('GET', `/api/threads/${openConversation.thread_id}/messages`);
      if (!stillHere()) return;
      const names = { [openConversation.customer_id]: openConversation.customer_name };
      thread = `<h2>${esc(openConversation.customer_name || openConversation.customer_id)}</h2>
        ${R.messageThread(m.ok ? m.data.messages : [], me().id, names, { reportable: true })}
        <form class="reply-form" data-shared-form="conversation"><label class="visually-hidden" for="conv-body">Reply</label>
          <textarea id="conv-body" name="body" maxlength="2000" required placeholder="Write to the customer"></textarea>
          <button class="button" type="submit">${icon('send')} Send</button></form>`;
    }
    main().innerHTML = title('designer', 'Messages', 'Private conversations with customers.') +
      `<div class="conversation-layout"><ul class="conversation-list">${conversations.map(c => `<li>
          <button class="${openConversation && c.id === openConversation.id ? 'active' : ''}" data-shared="conversation" data-id="${esc(c.id)}">
          <b>${esc(c.customer_name || c.customer_id)}</b><small>${c.last_message_at ? time(c.last_message_at) : 'No messages yet'}</small></button></li>`).join('')
        || '<li class="small-note">No conversations yet. Customers start them from your company profile.</li>'}</ul>
        <section class="panel conversation-thread"><div class="panel-body">${thread || '<p class="small-note">Choose a conversation.</p>'}</div></section></div>`;
    window.__conversations = conversations;
  }

  // ---------- events ----------
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-shared]');
    if (!button) return;
    const action = button.dataset.shared;
    if (action === 'open-ticket') showTicket(button.dataset.id);
    else if (action === 'page') { list.page = Number(button.dataset.page); render('helpdesk', list.section); }
    else if (action === 'uploads-page') { uploadsQuery.page = Number(button.dataset.page); render('helpdesk', 'uploads'); }
    else if (action === 'claim') afterChange(await R.call('POST', `/api/support/tickets/${openTicket.id}/assign`), 'Ticket claimed.');
    else if (action === 'move') {
      const status = button.dataset.status;
      const needsReason = ['AWAITING_INFO', 'ESCALATED', 'RESOLVED'].includes(status);
      const reason = await R.confirmWithReason({ title: `${MOVE_LABEL[status] || R.label(status)} — ${openTicket.id}`,
        message: needsReason ? 'The requester will see this reason.' : '', confirmLabel: MOVE_LABEL[status] || 'Confirm',
        reasonRequired: needsReason });
      if (reason === null) return;
      afterChange(await R.call('POST', `/api/support/tickets/${openTicket.id}/status`, { status, reason }), 'Status updated.');
    } else if (action === 'hide-project') {
      const reason = await R.confirmWithReason({ title: `Hide ${button.dataset.project} from customers`,
        message: 'The project leaves the customer website and its designer is told why.', confirmLabel: 'Hide project' });
      if (reason === null) return;
      afterChange(await R.call('POST', `/api/projects/${button.dataset.project}/status`, { status: 'HIDDEN', reason }), 'Project hidden.');
    } else if (action === 'conversation') {
      openConversation = (window.__conversations || []).find(c => c.id === button.dataset.id) || null;
      render('designer', 'messages');
    }
  });

  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-shared-form]');
    if (!form) return;
    event.preventDefault();
    event.stopPropagation();
    const kind = form.dataset.sharedForm;
    const value = name => (form.elements[name] ? form.elements[name].value.trim() : '');
    if (kind === 'filters') {
      Object.assign(list, { q: value('q'), status: value('status'), type: value('type'), handler: value('handler'), page: 1 });
      render('helpdesk', list.section);
    } else if (kind === 'uploads') { uploadsQuery = { q: value('q'), page: 1 }; render('helpdesk', 'uploads'); }
    else if (kind === 'reply') afterChange(await R.call('POST', `/api/threads/${openTicket.thread_id}/messages`, { body: value('body') }), 'Reply sent.');
    else if (kind === 'note') afterChange(await R.call('POST', `/api/notes/REQUEST/${openTicket.id}`, { text: value('text') }), 'Note added.');
    else if (kind === 'merge') {
      const other = value('other').toUpperCase();
      const reason = await R.confirmWithReason({ title: `Merge ${other} into ${openTicket.id}`,
        message: `${other} will be closed as a duplicate; its messages and notes move here.`, confirmLabel: 'Merge',
        reasonRequired: false, placeholder: `Duplicate of ${openTicket.id}.` });
      if (reason === null) return;
      afterChange(await R.call('POST', '/api/support/tickets/merge', { main_ticket_id: openTicket.id, other_ticket_id: other, reason }),
                  `${other} merged into ${openTicket.id}.`);
    } else if (kind === 'conversation' && openConversation) {
      const r = await R.call('POST', `/api/threads/${openConversation.thread_id}/messages`, { body: value('body') });
      if (!r.ok) { toast(r.data.error || 'Could not send.'); return; }
      render('designer', 'messages');
    }
  }, true);

  document.querySelector('#modal')?.addEventListener('close', () => { openTicket = null; });
  window.SharedWorkspace = { handles, render, leave };
})();
