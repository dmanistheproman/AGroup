/* MessageDesignerButton boundary (S-16): "Message designer" on a company's page starts (or reopens) the customer's
   private conversation with that company and opens it in the inbox. */
(() => {
  'use strict';

  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-message-firm]');
    if (!button) return;
    const user = window.AGroupAccount && window.AGroupAccount.current();
    if (!user) { location.href = 'login.html'; return; }
    const say = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));
    if (user.role !== 'customer') { say('Messages to designers are for customer accounts.'); return; }
    button.disabled = true;
    try {
      const companies = await (await fetch('/api/companies', { credentials: 'same-origin' })).json();
      const company = (companies.companies || []).find(c => c.name === button.dataset.messageFirm);
      if (!company) { say('This designer cannot receive messages yet.'); return; }
      const res = await fetch('/api/conversations', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: company.id }),
      });
      const data = await res.json();
      if (!res.ok) { say(data.error || 'The conversation could not be started.'); return; }
      location.href = `inbox.html#messages/${encodeURIComponent(data.conversation.id)}`;
    } catch {
      say('Cannot reach the server. Start it with python run.py and try again.');
    } finally {
      button.disabled = false;
    }
  });
})();

/* Company reviews (C-07): the company's page shows the average rating and the reviews customers left after a
   completed project (S-11 RatingDisplay). customer.js leaves a [data-firm-reviews] slot in the page. */
(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  async function fill(slot) {
    if (slot.dataset.loaded) return;
    slot.dataset.loaded = 'yes';
    try {
      const companies = await (await fetch('/api/companies')).json();
      const company = (companies.companies || []).find(c => c.name === slot.dataset.firmReviews);
      if (!company) return;   // a sample studio without an account keeps its sample line
      const data = await (await fetch(`/api/companies/${encodeURIComponent(company.id)}/reviews`)).json();
      const UI = window.AGroupUI;
      if (!data.count) { slot.innerHTML = '<small>No reviews yet. Customers can review after a completed project.</small>'; return; }
      slot.innerHTML = `${UI ? UI.ratingDisplay(data.average, data.count) : `${data.average} / 5 (${data.count})`}
        <ul class="review-list">${data.reviews.slice(0, 4).map(r => `<li><b>${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</b>
          <p>${esc(r.comment)}</p><small>${esc(r.customer)} · ${esc(r.date)}</small></li>`).join('')}</ul>`;
    } catch { /* offline: the sample line stays */ }
  }

  new MutationObserver(() => document.querySelectorAll('[data-firm-reviews]').forEach(fill))
    .observe(document.documentElement, { childList: true, subtree: true });
})();
