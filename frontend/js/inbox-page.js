/* InboxPage boundary for customers (S-14), with the conversation page (S-16), the offer page (S-21) and
   notification preferences (C-12). Tabs follow the hash: #requests, #messages[/CONV-x], #offers, #preferences.
   Uses AGroupRecords (records.js) for badges, threads and the reason dialog, and AGroupUI.recordPage (ui.js). */
(() => {
  'use strict';
  // C-10: customers see a confirmed enquiry as Accepted (Awaiting reply, Accepted, Declined, Completed)
  const customerStatus = (kind, status) => (kind === 'ENQUIRY' && status === 'CONFIRMED' ? 'ACCEPTED' : status);

  const R = window.AGroupRecords;
  const { esc, icon, statusBadge, time } = R;
  const content = document.querySelector('#inbox-content');
  const toast = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));
  const me = () => (window.AGroupAccount && window.AGroupAccount.current()) || null;
  const money = value => `S$${Number(value || 0).toLocaleString('en-SG')}`;
  let inbox = null;

  function tabFromHash() {
    const [tab, id] = location.hash.replace('#', '').split('/');
    return { tab: ['requests', 'messages', 'offers', 'preferences'].includes(tab) ? tab : 'requests', id };
  }

  async function show() {
    const user = me();
    if (!user) { content.innerHTML = `<p class="small-note">Please <a href="login.html">log in</a> to see your inbox.</p>`; return; }
    if (user.role !== 'customer') {
      content.innerHTML = '<p class="small-note">This inbox is for customers. Staff and designers use the portal.</p>';
      return;
    }
    const { tab, id } = tabFromHash();
    document.querySelectorAll('[data-tab]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
    const r = await R.call('GET', '/api/inbox');
    inbox = r.ok ? r.data : { requests: [], conversations: [], unread: { requests: 0, conversations: 0 } };
    for (const [key, value] of Object.entries(inbox.unread || {})) {
      const badge = document.querySelector(`[data-unread="${key}"]`);
      if (badge) badge.textContent = value ? value : '';
    }
    if (tab === 'requests') return id ? requestPage(id) : requests();
    if (tab === 'messages') return messages(id);
    if (tab === 'offers') return offers();
    return preferences();
  }

  // ---------- Requests ----------
  function requests() {
    const rows = inbox.requests;
    content.innerHTML = rows.length ? `<ul class="inbox-list">${rows.map(r => `<li>
        <a href="#requests/${esc(r.id)}" class="inbox-item ${r.unread ? 'unread' : ''}">
        <span class="inbox-icon">${icon(r.kind === 'SUPPORT_TICKET' ? 'life-buoy' : 'file-text')}</span>
        <span><b>${esc(r.title)} · ${esc(r.id)}</b><small>${esc(r.summary)}</small></span>
        <span class="inbox-meta">${statusBadge(customerStatus(r.kind, r.status))}<small>${time(r.created_at)}</small>${r.responded ? '<span class="inbox-unread">ID responded</span>' : ''}${r.unanswered ? '<span class="inbox-unread">Awaiting your reply</span>' : ''}${r.unread ? `<span class="inbox-unread">${r.unread} new</span>` : ''}</span></a></li>`).join('')}</ul>`
      : '<p class="small-note">No requests yet. Use "Contact support" in the account menu, or send an enquiry from a designer\'s page.</p>';
  }

  // One record page (S-20) for every kind of request: support tickets, enquiries, verification requests.
  async function requestPage(id) {
    const r = await R.call('GET', `/api/requests/${encodeURIComponent(id)}`);
    if (!r.ok) { content.innerHTML = `<p class="inline-error">${esc(r.data.error || 'This request could not be opened.')}</p>`; return; }
    const { messages, history, names } = r.data;
    const record = r.data.ticket || r.data.request;
    const isTicket = Boolean(r.data.ticket);
    const readOnly = ['MERGED', 'CLOSED', 'DECLINED', 'COMPLETED'].includes(record.status);
    const handler = names[record.handler_id] || (isTicket ? 'Waiting for an agent' : 'Waiting for a designer');
    const details = isTicket ? [
      ['Opened', time(record.created_at)], ['Handled by', esc(handler)],
      record.merged_into_id ? ['Merged into', `<a href="#requests/${esc(record.merged_into_id)}">${esc(record.merged_into_id)}</a>`] : null,
      record.resolution_note ? ['Resolution', esc(record.resolution_note)] : null,
      ['Your request', esc(record.details)]] : [
      ['Designer', esc(handler)], ['Your brief', esc(record.summary)],
      record.budget ? ['Budget', money(record.budget)] : null,
      record.decided_at ? ['Decided on', esc(record.decided_at)] : null,
      record.decision_reason ? ['Reason', esc(record.decision_reason)] : null];
    const questions = (record.questions || []).length ? `<ul class="notes-panel">${record.questions.map(q => `<li>${icon('message-square')}<div>
        <p><b>${esc(q.body)}</b></p><p>${q.answer ? esc(q.answer) : '<span class="small-note">Not answered yet.</span>'}</p>
        <small>${esc(q.asked_at || '')}${q.answered_at ? ` · answered ${esc(q.answered_at)}` : ''}</small></div></li>`).join('')}</ul>` : '';
    const reply = readOnly ? '<p class="small-note">This request is closed.</p>'
      : `<form class="reply-form" data-inbox-form="ticket-reply" data-thread="${esc(record.thread_id)}">
          <label class="visually-hidden" for="ticket-reply">Reply</label><textarea id="ticket-reply" name="body" maxlength="2000" required placeholder="${isTicket ? 'Reply to the helpdesk' : 'Write to your designer'}"></textarea>
          <button class="button" type="submit">${icon('send')} Send</button></form>`;
    content.innerHTML = `<a class="text-button" href="#requests">${icon('arrow-left')} All requests</a>
      <div class="inbox-record">${window.AGroupUI.recordPage({
        eyebrow: `${record.id} · ${isTicket ? record.type_label : record.title}`,
        title: isTicket ? (record.related_project_title || record.type_label)
          : record.kind === 'ENQUIRY' && record.handler_id ? `Your enquiry to ${handler}` : record.title,
        status: customerStatus(record.kind, record.status), details,
        sections: [
          questions ? { title: 'Your questions', icon: 'file-text', body: questions } : null,
          { title: isTicket ? 'Conversation with the helpdesk' : 'Conversation with your designer', icon: 'message-square',
            body: R.messageThread(messages, me().id, names, { reportable: !isTicket }) + reply },
          rating(r.data, record, isTicket, handler),
          { title: 'Progress', icon: 'history', body: R.historyTimeline(history, names) }] })}</div>`;
  }

  // Ticket feedback (HD-13) and a review of the designer (C-07), both with the S-11 rating form.
  function rating(page, record, isTicket, handler) {
    const UI = window.AGroupUI;
    if (isTicket) {
      if (page.can_give_feedback) {
        return { title: 'How did we do?', icon: 'star', body: UI.ratingForm({ form: { 'data-inbox-form': 'ticket-feedback',
          'data-id': record.id }, title: 'Rate the help you received', submitLabel: 'Send feedback' }) +
          '<p class="small-note">Only the helpdesk team sees your rating.</p>' };
      }
      return page.feedback_given ? { title: 'Your feedback', icon: 'star', body: '<p class="small-note">Thank you for rating this request.</p>' } : null;
    }
    if (page.review) {
      return { title: 'Your review', icon: 'star', body: `<p>${UI.ratingDisplay(page.review.rating)}</p><p>${esc(page.review.comment || '')}</p>
        <small>${esc(page.review.date)} · shown on ${esc(handler)}'s profile</small>` };
    }
    if (page.can_review) {
      return { title: `Review ${handler}`, icon: 'star', body: UI.ratingForm({ form: { 'data-inbox-form': 'review', 'data-id': record.id },
        title: 'How was working with them?', submitLabel: 'Publish review' }) +
        '<p class="small-note">Your review and your name appear on the designer\'s public profile.</p>' };
    }
    return null;
  }

  // ---------- Messages with designers (S-16) ----------
  async function messages(id) {
    const list = inbox.conversations;
    const open = list.find(c => c.id === id) || list[0];
    let thread = '<p class="small-note">Open a designer\'s page on the website and choose "Message designer" to start a conversation.</p>';
    if (open) {
      const m = await R.call('GET', `/api/threads/${open.thread_id}/messages`);
      thread = `<h2>${esc(open.company_name || open.company_id)}</h2>
        ${R.messageThread(m.ok ? m.data.messages : [], me().id, { [open.company_id]: open.company_name }, { reportable: true })}
        <form class="reply-form" data-inbox-form="message" data-thread="${esc(open.thread_id)}" data-conversation="${esc(open.id)}">
          <label class="visually-hidden" for="message-body">Message</label><textarea id="message-body" name="body" maxlength="2000" required placeholder="Write to the designer"></textarea>
          <button class="button" type="submit">${icon('send')} Send</button></form>`;
    }
    content.innerHTML = `<div class="conversation-layout"><ul class="conversation-list">${list.map(c => `<li>
        <a href="#messages/${esc(c.id)}" class="${open && c.id === open.id ? 'active' : ''}"><b>${esc(c.company_name || c.company_id)}</b>
        <small>${c.unread ? `${c.unread} new · ` : ''}${c.last_message_at ? time(c.last_message_at) : 'No messages yet'}</small></a></li>`).join('')
      || '<li class="small-note">No conversations yet.</li>'}</ul><section class="panel conversation-thread"><div class="panel-body">${thread}</div></section></div>`;
  }

  // ---------- Offers (S-21) ----------
  async function offers() {
    const r = await R.call('GET', '/api/offers');
    const { quotations = [], proposals = [] } = r.ok ? r.data : {};
    const threads = Object.fromEntries(await Promise.all(proposals.filter(p => p.thread_id).map(async p =>
      [p.id, (await R.call('GET', `/api/threads/${p.thread_id}/messages`)).data.messages || []])));
    const quotationCard = q => `<article class="offer-card"><div class="record-header"><div><p class="eyebrow">${esc(q.id)} · Quotation · version ${q.version}</p>
        <h3>${money(q.total)}</h3></div>${statusBadge(q.status)}</div>
      <dl class="detail-list"><dt>Design fee</dt><dd>${money(q.design_fee)}</dd><dt>Materials</dt><dd>${money(q.material_cost)}</dd>
        <dt>Construction</dt><dd>${money(q.construction_fee)}</dd><dt>Valid until</dt><dd>${esc(q.valid_until)}</dd>
        <dt>Payments</dt><dd>${esc(q.payment_schedule)}</dd>${q.adjustment_note ? `<dt>You asked</dt><dd>${esc(q.adjustment_note)}</dd>` : ''}</dl>
      ${q.status === 'WAITING_CLIENT_CONFIRMATION' ? `<div class="record-actions">
        <button class="button" data-inbox="accept" data-id="${esc(q.id)}">${icon('check')} Accept quotation</button>
        <button class="button outline" data-inbox="adjust" data-id="${esc(q.id)}">${icon('pencil')} Ask for changes</button></div>` : ''}</article>`;
    const proposalCard = p => `<article class="offer-card"><div class="record-header"><div><p class="eyebrow">${esc(p.id)} · Design proposal · version ${p.version}</p>
        <h3>${esc(p.title)}</h3></div>${statusBadge(p.status)}</div><p>${esc(p.description)}</p>
      ${p.status === 'UNDER_REVIEW' ? `<div class="record-actions"><button class="button" data-inbox="accept-proposal" data-id="${esc(p.id)}">${icon('check')} Accept proposal</button></div>
        <form class="reply-form" data-inbox-form="feedback" data-id="${esc(p.id)}">
        <label for="fb-${esc(p.id)}">YOUR FEEDBACK</label><textarea id="fb-${esc(p.id)}" name="feedback" maxlength="2000" required placeholder="What would you like changed?"></textarea>
        <button class="button outline" type="submit">${icon('send')} Send feedback</button></form>` : ''}
      ${p.thread_id ? `<details class="offer-thread" ${threads[p.id] && threads[p.id].length ? 'open' : ''}><summary>${icon('message-square')} Messages with the designer (${(threads[p.id] || []).length})</summary>
        ${R.messageThread(threads[p.id] || [], me().id, Object.fromEntries((threads[p.id] || []).map(m => [m.author_id, 'Your designer'])), { reportable: true })}
        <form class="reply-form" data-inbox-form="message" data-thread="${esc(p.thread_id)}">
          <label class="visually-hidden" for="pt-${esc(p.id)}">Message</label><textarea id="pt-${esc(p.id)}" name="body" maxlength="2000" required placeholder="Ask about this proposal"></textarea>
          <button class="button outline" type="submit">${icon('send')} Send</button></form></details>` : ''}</article>`;
    content.innerHTML = `<h3 class="inbox-subheading">Quotations</h3>${quotations.length ? quotations.map(quotationCard).join('') : '<p class="small-note">No quotations yet.</p>'}
      <h3 class="inbox-subheading">Design proposals</h3>${proposals.length ? proposals.map(proposalCard).join('') : '<p class="small-note">No proposals yet.</p>'}`;
  }

  // ---------- Preferences (C-12) ----------
  async function preferences() {
    const r = await R.call('GET', '/api/notification-preferences');
    const items = r.ok ? r.data.preferences : [];
    content.innerHTML = `<p>Choose which updates you are notified about. Confirmations of your own requests are always sent.</p>
      <ul class="preference-list">${items.map(p => `<li><label class="checkbox"><input type="checkbox" data-preference="${esc(p.event_type)}" ${p.is_enabled ? 'checked' : ''}>
        ${esc(p.label)}</label></li>`).join('')}</ul>`;
  }

  // ---------- events ----------
  document.addEventListener('click', async event => {
    const tab = event.target.closest('[data-tab]');
    if (tab) { location.hash = tab.dataset.tab; return; }
    const button = event.target.closest('[data-inbox]');
    if (!button) return;
    const id = button.dataset.id;
    if (button.dataset.inbox === 'accept') {
      if (!confirm(`Accept quotation ${id}? This records your decision to go ahead; the contract is signed outside the platform.`)) return;
      const r = await R.call('POST', `/api/offers/quotations/${id}/accept`);
      toast(r.ok ? 'Quotation accepted.' : (r.data.error || 'Could not accept.'));
    } else if (button.dataset.inbox === 'accept-proposal') {
      if (!confirm(`Accept design proposal ${id}? The designer will be told you are happy with it.`)) return;
      const r = await R.call('POST', `/api/offers/proposals/${id}/accept`);
      toast(r.ok ? 'Proposal accepted.' : (r.data.error || 'Could not accept.'));
    } else if (button.dataset.inbox === 'adjust') {
      const note = await R.confirmWithReason({ title: `Ask for changes to ${id}`, confirmLabel: 'Send request',
        placeholder: 'For example: could the material cost come down?' });
      if (note === null) return;
      const r = await R.call('POST', `/api/offers/quotations/${id}/adjustment`, { note });
      toast(r.ok ? 'Your request was sent to the designer.' : (r.data.error || 'Could not send.'));
    }
    show();
  });

  document.addEventListener('change', async event => {
    const box = event.target.closest('[data-preference]');
    if (!box) return;
    const r = await R.call('PUT', '/api/notification-preferences', { event_type: box.dataset.preference, is_enabled: box.checked });
    toast(r.ok ? 'Preference saved.' : (r.data.error || 'Could not save.'));
  });

  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-inbox-form]');
    if (!form) return;
    event.preventDefault();
    const kind = form.dataset.inboxForm;
    const text = name => form.elements[name].value.trim();
    let r;
    if (kind === 'ticket-reply' || kind === 'message') r = await R.call('POST', `/api/threads/${form.dataset.thread}/messages`, { body: text('body') });
    else if (kind === 'feedback') r = await R.call('POST', `/api/offers/proposals/${form.dataset.id}/feedback`, { feedback: text('feedback') });
    else if (kind === 'ticket-feedback' || kind === 'review') {
      const score = form.querySelector('input[name="score"]:checked');
      if (!score) { window.AGroupUI.formView.message(form, 'Choose a number of stars first.', 'error'); return; }
      const url = kind === 'review' ? `/api/requests/${form.dataset.id}/review` : `/api/support/tickets/${form.dataset.id}/feedback`;
      r = await window.AGroupUI.formView.submit(form, 'POST', url, { score: Number(score.value), comment: text('comment') });
      if (!r.ok) return;
    }
    if (!r.ok) { toast(r.data.error || 'Could not send.'); return; }
    toast({ feedback: 'Feedback sent to the designer.', 'ticket-feedback': 'Thank you for your feedback.',
            review: 'Your review is published.' }[kind] || 'Sent.');
    show();
  });

  window.addEventListener('hashchange', show);
  document.addEventListener('agroup:account-rendered', () => { if (!inbox) show(); });
  document.addEventListener('DOMContentLoaded', show);
})();
