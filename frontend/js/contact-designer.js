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
