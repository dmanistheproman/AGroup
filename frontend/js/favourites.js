/* FavouritesSync boundary (C-04): a logged-in customer's saved projects are kept on the server
   (GET / POST / DELETE /api/favourites), so they follow the account to any browser. Visitors who are not
   logged in keep them in this browser only, as before. Reads and updates the page's list through
   window.AGroupSaved (customer.js). */
(() => {
  'use strict';

  let loadedFor = null;   // the customer whose favourites are shown

  function customer() {
    const user = window.AGroupAccount && window.AGroupAccount.current();
    return user && user.role === 'customer' ? user : null;
  }

  const reference = id => `IDP-${String(id).padStart(3, '0')}`;
  const number = ref => Number(String(ref).replace('IDP-', ''));

  async function call(method, url, body) {
    const res = await fetch(url, {
      method, credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, data };
  }

  const page = () => window.AGroupSaved;
  const show = ids => page().set(ids);

  // Save or remove one project for the logged-in customer; undo the change on the page if the server refuses.
  async function toggle(id, on) {
    const r = on ? await call('POST', '/api/favourites', { project_id: id })
                 : await call('DELETE', `/api/favourites/${reference(id)}`);
    if (!r.ok) {
      const ids = page().get();
      show(on ? ids.filter(x => x !== id) : [...ids, id]);
      window.AG.toast(r.data.error || 'Your favourites could not be updated. Please try again.');
    }
  }

  // After logging in, show the account's favourites and add any saved on this browser before logging in.
  async function load() {
    if (!page()) return;   // customer.js has not started yet; DOMContentLoaded calls load again
    const user = customer();
    if (!user) {
      if (loadedFor) { loadedFor = null; show([]); }   // logged out: do not leave their list on this browser
      return;
    }
    if (loadedFor === user.id) return;
    loadedFor = user.id;
    const r = await call('GET', '/api/favourites');
    if (!r.ok) return;
    const ids = (r.data.project_ids || []).map(number);
    for (const id of page().get().filter(x => !ids.includes(x))) {
      const added = await call('POST', '/api/favourites', { project_id: id });
      if (added.ok) ids.push(id);
    }
    show(ids);
  }

  document.addEventListener('agroup:account-rendered', load);
  document.addEventListener('DOMContentLoaded', load);
  window.AGroupFavourites = { active: () => Boolean(customer()), toggle };
})();
