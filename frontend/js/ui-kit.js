/* ui-kit.html: one live example of each shared component (records.js and ui.js). */
(() => {
  'use strict';

  const R = window.AGroupRecords;
  const UI = window.AGroupUI;
  const { esc } = UI;
  const $ = id => document.getElementById(id);
  const toast = text => {
    const box = document.querySelector('.toast');
    box.textContent = text;
    box.classList.add('show');
    setTimeout(() => box.classList.remove('show'), 2600);
  };
  const EXAMPLE_HISTORY = [
    { from_status: 'OPEN', to_status: 'AWAITING_INFO', actor_id: 'Helpdesk Agent', created_at: '2026-11-06T02:10:00Z',
      reason: 'Which browser shows the blank gallery?' },
    { from_status: 'AWAITING_INFO', to_status: 'RESOLVED', actor_id: 'Helpdesk Agent', created_at: '2026-11-07T04:30:00Z',
      reason: 'Fixed in the image viewer.' }];

  function statusSection() {
    $('kit-status').innerHTML = `<div class="kit-box"><h3>Badges</h3><p class="row" style="margin-top:12px">${
      ['OPEN', 'AWAITING_INFO', 'RESOLVED', 'PUBLISHED', 'HIDDEN', 'SUSPENDED', 'ACCEPTED'].map(R.statusBadge).join(' ')}</p></div>
      <div class="kit-box"><h3>Confirm with a reason</h3><p class="kit-note">Opens the dialog; the reason is required.</p>
        <button class="button outline" type="button" id="kit-reason" style="margin-top:12px">Suspend an account…</button></div>
      <div class="kit-box"><h3>History (example)</h3>${R.historyTimeline(EXAMPLE_HISTORY)}</div>`;
    $('kit-reason').addEventListener('click', async () => {
      const reason = await R.confirmWithReason({ title: 'Suspend this account', message: 'The account holder will see the reason.',
        confirmLabel: 'Suspend' });
      toast(reason === null ? 'Cancelled.' : `Reason given: ${reason}`);
    });
  }

  let listState = { q: '', page: 1 };
  async function listSection() {
    $('kit-states').innerHTML = ['loading', 'empty', 'error'].map(kind => `<div class="kit-box">${UI.state(kind)}</div>`).join('');
    $('kit-list').innerHTML = UI.state('loading');
    const all = await UI.loadCategories();
    const q = listState.q.toLowerCase();
    const found = all.filter(c => !q || c.name.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q));
    const pages = Math.max(1, Math.ceil(found.length / 5));
    listState.page = Math.min(listState.page, pages);
    const rows = found.slice((listState.page - 1) * 5, listState.page * 5);
    $('kit-list').innerHTML = UI.listPage({
      toolbar: UI.toolbar({ id: 'kit-list-form' }, [{ name: 'q', label: 'SEARCH', value: listState.q, placeholder: 'Category name' }], 'Search'),
      total: found.length, noun: 'category', page: listState.page, pages, empty: 'No category matches.',
      body: UI.table([{ label: 'Category', cell: c => `<b>${esc(c.name)}</b>` },
                      { label: 'Description', cell: c => esc(c.description || '') },
                      { label: 'Status', cell: c => R.statusBadge(String(c.status).toUpperCase()) }], rows),
      pageAttrs: p => `data-kit-page="${p}"` });
  }

  async function cardSection() {
    const r = await fetch('/api/catalog').then(x => x.json()).catch(() => ({ projects: [] }));
    const projects = (r.projects || []).slice(0, 3);
    $('kit-cards').innerHTML = projects.length ? projects.map(p => UI.projectCard(p)).join('')
      + UI.projectCard({ id: 0, title: 'A project without a photo', location: 'Example', image: 'missing-image' }, { saved: null })
      : UI.state('error', 'The catalogue could not be loaded.');
    const p = projects[0] || { title: 'Example', image: 'living' };
    $('kit-gallery').innerHTML = `<h3>${esc(p.title)}</h3>${UI.imageGallery([p.image, 'kitchen', 'dining', 'bedroom'], { title: p.title })}`;
  }

  async function pickerSection() {
    const categories = await UI.loadCategories();
    $('kit-picker-one').innerHTML = `<h3>Single</h3>${UI.categoryPicker(categories, { name: 'one' })}`;
    $('kit-picker-many').innerHTML = `<h3>Several</h3>${UI.categoryPicker(categories.slice(0, 12), { name: 'many', multiple: true, label: 'STYLES', selected: [categories[0]?.id] })}`;
  }

  async function reportSection(query = 'period=monthly') {
    const box = $('kit-report');
    const selector = UI.periodSelector({ period: new URLSearchParams(query).get('period') || 'monthly', form: { id: 'kit-period' } });
    box.innerHTML = selector + UI.state('loading');
    const r = await R.call('GET', `/api/reports/activity?${query}&group_by=day`);
    const series = [{ key: 'views', label: 'Views' }, { key: 'favourites', label: 'Favourites' }, { key: 'enquiries', label: 'Enquiries' }];
    if (r.ok) {
      box.innerHTML = selector + `<p class="kit-note">${esc(r.data.report.period.label)} · your projects (live)</p>` +
        UI.trendChart(r.data.report.rows, series, { title: 'Project activity per day' });
      return;
    }
    const example = ['01 Nov', '02 Nov', '03 Nov', '04 Nov', '05 Nov', '06 Nov', '07 Nov'].map((label, i) =>
      ({ label, views: [12, 18, 15, 24, 30, 22, 28][i], favourites: [3, 5, 4, 8, 9, 6, 7][i], enquiries: [1, 1, 2, 3, 2, 2, 4][i] }));
    box.innerHTML = selector + `<p class="kit-note">Example numbers. Sign in as an interior designer or the Platform Manager to see live activity.</p>` +
      UI.trendChart(example, series, { title: 'Project activity per day (example)' });
  }

  function uploadSection() {
    $('kit-upload-image').innerHTML = `<h3>Project images</h3>${UI.uploadWidget({ name: 'images', label: 'Choose images', kind: 'image' })}`;
    $('kit-upload-doc').innerHTML = `<h3>Verification documents</h3>${UI.uploadWidget({ name: 'documents', label: 'Choose documents', kind: 'document' })}`;
  }

  function ratingSection() {
    $('kit-rating-display').innerHTML = `<h3>Average</h3><p style="margin:10px 0">${UI.ratingDisplay(4.3, 27)}</p><p>${UI.ratingDisplay(2.5, 4)}</p>`;
    $('kit-rating-form').innerHTML = UI.ratingForm({ form: { id: 'kit-rating' }, title: 'How was the support you received?' });
  }

  function formSection() {
    $('kit-form').innerHTML = `<form id="kit-account-form" class="form-grid" novalidate>
      <label>FULL NAME<input name="name" required maxlength="70" value="Alex Tan"></label>
      <label>EMAIL ADDRESS<input name="email" type="email" required value="customer@demo.agroup"></label>
      <div class="full row"><button class="button" type="submit">Create account</button>
        <span class="kit-note">Shows how a server error such as "already registered" appears next to its field.</span></div></form>`;
  }

  function recordSection() {
    const names = { 'CUS-101': 'Alex Tan', 'user-helpdesk': 'Helpdesk Agent' };
    $('kit-record').innerHTML = UI.recordPage({
      eyebrow: 'TKT-1001 · Technical problem (example)', title: 'Gallery is blank on my phone', status: 'AWAITING_INFO',
      details: [['Requester', 'Alex Tan (customer)'], ['Opened', R.time('2026-11-06T01:00:00Z')], ['Handler', 'Helpdesk Agent']],
      actions: `<button class="button outline" type="button">${UI.icon('check')} Resolve</button><button class="button outline" type="button">${UI.icon('arrow-up-right')} Escalate</button>`,
      sections: [
        { title: 'Conversation', icon: 'message-square', body: R.messageThread([
          { id: 'MSG-1', author_id: 'CUS-101', body: 'The gallery is blank on my phone.', sent_at: '2026-11-06T01:00:00Z' },
          { id: 'MSG-2', author_id: 'user-helpdesk', body: 'Which browser do you use?', sent_at: '2026-11-06T02:10:00Z' }], 'user-helpdesk', names) },
        { title: 'Internal notes', icon: 'sticky-note', body: R.notesPanel([{ text: 'Same issue as TKT-0998.', author_id: 'user-helpdesk', created_at: '2026-11-06T02:12:00Z' }], names) },
        { title: 'History', icon: 'history', body: R.historyTimeline(EXAMPLE_HISTORY.slice(0, 1)) }] });
  }

  document.addEventListener('click', event => {
    const page = event.target.closest('[data-kit-page]');
    if (page) { listState.page = Number(page.dataset.kitPage); listSection(); }
  });

  document.addEventListener('submit', async event => {
    const form = event.target;
    event.preventDefault();
    if (form.id === 'kit-list-form') { listState = { q: form.elements.q.value.trim(), page: 1 }; listSection(); }
    else if (form.id === 'kit-period') reportSection(UI.periodQuery(form));
    else if (form.id === 'kit-rating') {
      if (!form.reportValidity()) return;
      UI.formView.done(form, `Thank you. You gave ${form.elements.score.value} out of 5 (example, not saved).`);
    } else if (form.id === 'kit-account-form') {
      UI.formView.busy(form, true);
      await new Promise(r => setTimeout(r, 600));
      UI.formView.busy(form, false);
      UI.formView.showErrors(form, { error: 'This email address is already registered.', field: 'email' });
    }
  });

  document.addEventListener('DOMContentLoaded', () => {
    statusSection(); listSection(); cardSection(); pickerSection(); reportSection(); uploadSection(); ratingSection();
    formSection(); recordSection();
  });
})();
