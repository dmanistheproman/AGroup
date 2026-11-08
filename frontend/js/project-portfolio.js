/* Project portfolio page for interior designers (ID-03), built from the shared components (ui.js, records.js).
   List own projects with their real status and client activity; create and edit them with the details customers see
   (C-03); add images and choose the primary one; publish or unpublish (S-04); delete with an impact check.
   shared-workspace.js shows it for #designer/projects. */
(() => {
  'use strict';

  const UI = window.AGroupUI;
  const R = window.AGroupRecords;
  const { esc, icon } = UI;
  const toast = text => (window.AG && window.AG.toast ? window.AG.toast(text) : alert(text));
  const HOME_TYPES = ['HDB', 'Condominium', 'Landed', 'Commercial', 'Other'];
  let projects = [];
  let filter = { q: '', status: '' };
  let target = null;

  function imageOf(p) {
    const image = p.image || (p.attachments || [])[0];
    return image ? (/[/.]/.test(image) ? `/${String(image).replace(/^\//, '')}` : `assets/${image}.jpg`) : 'assets/living.jpg';
  }

  async function render(main, stillHere = () => true) {
    target = main || target;
    target.innerHTML = heading() + UI.state('loading');
    const r = await R.call('GET', '/api/projects');
    if (!stillHere()) return;
    if (!r.ok || !Array.isArray(r.data)) { target.innerHTML = heading() + UI.state('error', r.data.error || 'Could not load your projects.'); return; }
    projects = r.data;
    const q = filter.q.toLowerCase();
    const rows = projects.filter(p => (!filter.status || p.status === filter.status) &&
      (!q || `${p.title} ${p.category_name || ''} ${p.location || ''}`.toLowerCase().includes(q)));
    target.innerHTML = heading() + UI.listPage({
      toolbar: UI.toolbar({ 'data-portfolio-form': 'filter' }, [
        { name: 'q', label: 'SEARCH', value: filter.q, placeholder: 'Title, category or location' },
        { name: 'status', label: 'STATUS', type: 'select', value: filter.status,
          options: [['', 'All'], ['DRAFT', 'Draft'], ['PUBLISHED', 'Published'], ['UNPUBLISHED', 'Unpublished'], ['HIDDEN', 'Hidden']] }]),
      total: rows.length, noun: 'project', empty: 'No projects yet. Add your first past project.',
      body: UI.table([
        { label: 'Project', cell: p => `<div class="portfolio-title"><img src="${esc(imageOf(p))}" alt="" onerror="this.src='assets/living.jpg'">
            <span><b>${esc(p.title)}</b><small>${esc(p.category_name || '')} · ${esc(p.stage || '')}${p.location ? ` · ${esc(p.location)}` : ''}</small></span></div>` },
        { label: 'Status', cell: p => R.statusBadge(p.status) },
        { label: 'Estimated cost', cell: p => (p.price ? UI.money(p.price) : '<span class="small-note">Not given</span>') },
        { label: 'Clients', cell: p => `${p.views || 0} views · ${p.favourites || 0} saves` },
        { label: '', cell: actions }], rows) });
  }

  function heading() {
    return `<div class="page-title"><div><p class="eyebrow">INTERIOR DESIGNER / WORKSPACE</p><h1>Project portfolio</h1>
      <p>Your past and current projects. Publish a project to show it to customers.</p></div>
      <button class="button" type="button" data-portfolio="new">${icon('folder-plus')} New project</button></div>`;
  }

  function actions(p) {
    const status = p.status === 'PUBLISHED'
      ? `<button class="text-button" data-portfolio="status" data-id="${esc(p.id)}" data-status="UNPUBLISHED">${icon('eye-off')} Unpublish</button>`
      : p.status === 'HIDDEN' ? '<span class="small-note">Hidden by the helpdesk</span>'
        : `<button class="text-button" data-portfolio="status" data-id="${esc(p.id)}" data-status="PUBLISHED">${icon('eye')} Publish</button>`;
    return `<div class="portfolio-actions">${status}
      <button class="text-button" data-portfolio="edit" data-id="${esc(p.id)}">${icon('pencil')} Edit</button>
      <button class="text-button" data-portfolio="delete" data-id="${esc(p.id)}">${icon('trash-2')} Delete</button></div>`;
  }

  async function form(project) {
    const categories = await UI.loadCategories();
    const p = project || {};
    const images = p.attachments || [];
    const option = (value, current) => `<option ${value === current ? 'selected' : ''}>${esc(value)}</option>`;
    const dialog = document.querySelector('#modal');
    document.querySelector('#modal-content').innerHTML = `<h2>${project ? 'Edit project' : 'New project'}</h2>
      <form class="form-grid portfolio-form" data-portfolio-form="${project ? 'edit' : 'create'}" data-id="${esc(p.id || '')}" novalidate>
        <label class="full">TITLE<input name="title" required maxlength="100" value="${esc(p.title || '')}"></label>
        <label class="full">DESCRIPTION<textarea name="description" required maxlength="2000">${esc(p.description || '')}</textarea></label>
        ${UI.categoryPicker(categories, { name: 'category_id', required: true, selected: p.category_id ? [p.category_id] : [] })}
        <label>STAGE<select name="stage">${['Past project', 'Current project'].map(s => option(s, p.stage || 'Past project')).join('')}</select></label>
        <label class="full">MATERIALS<input name="materials" maxlength="500" value="${esc(p.materials || '')}" placeholder="For example: oak veneer, limewash walls, linen"></label>
        <label>ESTIMATED COST (S$)<input name="estimated_cost" inputmode="numeric" value="${esc(p.price || '')}" placeholder="48000"></label>
        <label>LOCATION<input name="location" maxlength="60" value="${esc(p.location || '')}" placeholder="Tampines"></label>
        <label>HOME TYPE<select name="home_type"><option value="">Choose</option>${HOME_TYPES.map(t => option(t, p.type)).join('')}</select></label>
        <label>AREA<input name="area" maxlength="20" value="${esc(p.area || '')}" placeholder="92 m²"></label>
        ${images.length ? `<div class="full"><b class="portfolio-label">IMAGES</b><div class="portfolio-images">${images.map((src, i) => `<figure>
            <img src="/${esc(String(src).replace(/^\//, ''))}" alt="Project image ${i + 1}">
            ${i === 0 ? '<figcaption>Primary</figcaption>' : `<button type="button" class="text-button" data-portfolio="primary" data-id="${esc(p.id)}" data-image="${esc(src)}">Make primary</button>`}</figure>`).join('')}</div></div>` : ''}
        <div class="full">${UI.uploadWidget({ name: 'images', label: project ? 'Add more images' : 'Project images', kind: 'image' })}</div>
        <div class="full row"><button class="button" type="submit">${project ? 'Save changes' : 'Save as draft'}</button>
          <button class="text-button" type="button" data-portfolio="close">Cancel</button></div></form>`;
    if (!dialog.open) dialog.showModal();
  }

  async function save(formElement) {
    if (!formElement.reportValidity()) return;
    const input = formElement.querySelector('input[type=file]');
    const check = UI.checkFiles(input, 'image');
    if (!check.ok) { UI.formView.message(formElement, check.errors[0], 'error'); return; }
    const data = new FormData(formElement);
    const editing = formElement.dataset.portfolioForm === 'edit';
    UI.formView.busy(formElement, true);
    const progress = formElement.querySelector('.upload-progress');
    if (input.files.length) progress.hidden = false;
    const url = editing ? `/api/projects/${encodeURIComponent(formElement.dataset.id)}` : '/api/projects';
    const r = editing ? await patch(url, data) : await UI.send(url, data, value => { progress.value = value; });
    UI.formView.busy(formElement, false);
    progress.hidden = true;
    if (!r.ok) { UI.formView.showErrors(formElement, r.data); return; }
    document.querySelector('#modal').close();
    toast(editing ? 'Project saved.' : 'Project saved as a draft. Publish it to show it to customers.');
    render();
  }

  async function patch(url, data) {
    const res = await fetch(url, { method: 'PATCH', body: data, credentials: 'same-origin' });
    return { ok: res.ok, status: res.status, data: await res.json().catch(() => ({})) };
  }

  async function remove(id) {
    const first = await R.call('DELETE', `/api/projects/${encodeURIComponent(id)}`);
    if (!first.ok) { toast(first.data.error || 'Could not delete.'); return; }
    if (first.data.requires_confirmation) {
      if (!confirm(`${first.data.impact} Delete it anyway? It will leave customers' favourites and folders; its numbers stay in your reports.`)) return;
      const second = await R.call('DELETE', `/api/projects/${encodeURIComponent(id)}?confirm_impact=true`);
      if (!second.ok) { toast(second.data.error || 'Could not delete.'); return; }
    }
    toast('Project deleted.');
    render();
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-portfolio]');
    if (!button) return;
    const action = button.dataset.portfolio;
    const project = projects.find(p => p.id === button.dataset.id);
    if (action === 'new') form(null);
    else if (action === 'edit' && project) form(project);
    else if (action === 'close') document.querySelector('#modal').close();
    else if (action === 'delete') {
      if (confirm(`Delete "${project ? project.title : button.dataset.id}"?`)) remove(button.dataset.id);
    } else if (action === 'status') {
      const r = await R.call('POST', `/api/projects/${encodeURIComponent(button.dataset.id)}/status`, { status: button.dataset.status });
      toast(r.ok ? (button.dataset.status === 'PUBLISHED' ? 'Published. Customers can now find this project.' : 'Unpublished.')
                 : (r.data.error || 'Could not change the status.'));
      render();
    } else if (action === 'primary') {
      const r = await R.call('POST', `/api/projects/${encodeURIComponent(button.dataset.id)}/primary-image`, { image: button.dataset.image });
      if (!r.ok) { toast(r.data.error || 'Could not change the image.'); return; }
      await render();
      form(projects.find(p => p.id === button.dataset.id));
    }
  });

  document.addEventListener('submit', event => {
    const formElement = event.target.closest('[data-portfolio-form]');
    if (!formElement) return;
    event.preventDefault();
    event.stopPropagation();
    if (formElement.dataset.portfolioForm === 'filter') {
      filter = { q: formElement.elements.q.value.trim(), status: formElement.elements.status.value };
      render();
    } else save(formElement);
  }, true);

  window.ProjectPortfolio = { render };
})();
