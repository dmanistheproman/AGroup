/* Boundary classes for the Platform Management workspace. */
(() => {
  'use strict';

  const escape = AG.escape;
  const api = AGroupAPI;
  const main = document.querySelector('#portal-main');
  const modal = document.querySelector('#modal');
  const modalContent = document.querySelector('#modal-content');
  const base = '/api/management';
  let activeSection = '';
  let generation = 0;
  let settings;

  function heading(title, description, action = '') {
    return `<div class="page-title"><div><p class="eyebrow">PLATFORM MANAGEMENT</p>
      <h1>${escape(title)}</h1><p>${escape(description)}</p></div>${action}</div>`;
  }

  function panel(title, body, note = '') {
    return `<section class="panel"><div class="panel-heading"><h2>${escape(title)}</h2>
      <small>${escape(note)}</small></div>${body}</section>`;
  }

  function button(label, action, id = '', extra = '') {
    return `<button type="button" class="button outline" data-management-action="${action}"
      data-id="${escape(id)}" ${extra}>${escape(label)}</button>`;
  }

  function status(value) {
    return `<span class="status">${escape(value)}</span>`;
  }

  function metrics(items) {
    return `<div class="metric-grid">${items.map(([label, value, note]) => `
      <article class="metric"><p>${escape(label)}</p><strong>${Number(value).toLocaleString('en-SG')}</strong>
      <small>${escape(note)}</small></article>`).join('')}</div>`;
  }

  function showDialog(markup) {
    modalContent.innerHTML = markup;
    if (!modal.open) modal.showModal();
    const first = modalContent.querySelector('input, select, textarea');
    if (first) first.focus();
  }

  function showError(error, target) {
    target.textContent = error.message || 'The request could not be completed. Please try again.';
  }

  function formError() {
    return '<p class="inline-error" data-management-error role="alert"></p>';
  }

  function dateLabel(value) {
    return new Date(value).toLocaleString('en-SG', { timeZone: 'Asia/Singapore', dateStyle: 'medium', timeStyle: 'short' });
  }

  class CategoryManagementPage {
    constructor() {
      this.categories = [];
      this.search = '';
      this.status = '';
      this.searchGeneration = 0;
    }

    async render(token) {
      main.innerHTML = heading('Project categories', 'Organise projects and manage the categories available to designers.',
        button('+ Create category', 'create')) + `
        <div class="portal-toolbar">
          <label>SEARCH CATEGORIES<input id="management-search" placeholder="Search by category name" value="${escape(this.search)}"></label>
          <label>STATUS<select id="management-status">${['', 'Active', 'Archived', 'Merged'].map(value =>
            `<option value="${value}" ${this.status === value ? 'selected' : ''}>${value || 'All statuses'}</option>`).join('')}</select></label>
          ${button('Merge categories', 'merge')}${button('Refresh', 'refresh')}
        </div><p id="management-list-error" class="inline-error" role="alert"></p>
        ${panel('Category directory', '<div id="management-categories" aria-live="polite"><p class="panel-body">Loading categories…</p></div>')}`;
      await this.refresh(token);
    }

    async refresh(token = generation) {
      if (activeSection !== 'categories') return;
      const searchToken = ++this.searchGeneration;
      const query = new URLSearchParams({ search: this.search, status: this.status });
      try {
        const result = await api.get(`${base}/categories?${query}`);
        if (token !== generation || searchToken !== this.searchGeneration || activeSection !== 'categories') return;
        this.categories = result.categories;
        document.querySelector('#management-list-error').textContent = '';
        document.querySelector('#management-categories').innerHTML = `<div class="table-wrap"><table>
          <thead><tr><th>Category</th><th>Projects</th><th>Status</th><th>Featured</th><th>Actions</th></tr></thead>
          <tbody>${this.categories.map(category => `<tr>
            <td><b>${escape(category.name)}</b><small>${escape(category.description)}</small>
              ${category.target ? `<small>Merged into ${escape(category.target)}</small>` : ''}</td>
            <td>${category.count}</td><td>${status(category.status)}</td><td>${category.featured ? 'Featured' : '—'}</td>
            <td>${button('Manage', 'edit', category.id)} ${button('Projects', 'projects', category.id)}
              ${category.count === 0 ? button('Delete', 'delete', category.id) : ''}</td>
          </tr>`).join('') || '<tr><td colspan="5">No categories match your search and status selection.</td></tr>'}</tbody>
          </table></div>`;
      } catch (error) {
        if (token === generation && searchToken === this.searchGeneration) {
          showError(error, document.querySelector('#management-list-error'));
        }
      }
    }

    async edit(id) {
      const token = generation;
      const records = await api.get(`${base}/categories`);
      if (token !== generation) return;
      const category = id ? records.categories.find(item => item.id === id) : null;
      if (id && !category) throw new Error('That category is no longer available. Refresh the list.');
      const editable = !category || category.status !== 'Merged';
      showDialog(`<h2>${category ? 'Manage category' : 'Create a category'}</h2>
        ${category ? `<p>${status(category.status)} ${category.featured ? 'Featured on customer discovery' : ''}</p>` : ''}
        <form data-management-form="category" data-id="${escape(id || '')}" data-version="${category?.version || ''}" class="form-stack">
          <label>CATEGORY NAME<input name="name" required maxlength="70" value="${escape(category?.name || '')}" ${editable ? '' : 'disabled'}></label>
          <label>DESCRIPTION<textarea name="description" maxlength="500" ${editable ? '' : 'disabled'}>${escape(category?.description || '')}</textarea></label>
          ${formError()}${editable ? '<button class="button">Save category</button>' : ''}
        </form>
        ${category ? `<div class="action-list">
          ${category.status === 'Active' ? button('Archive', 'archive', id) + button(category.featured ? 'Unfeature' : 'Feature category', 'feature', id) : ''}
          ${category.status === 'Archived' ? button('Restore category', 'restore', id) : ''}
          ${button('Review assigned projects', 'projects', id)}${button('Delete category', 'delete', id)}</div>
          <p class="hint">${category.target ? `Merged into ${escape(category.target)}.` : 'Review the assigned projects to assess the impact of a change.'}</p>` : ''}`);
    }

    async confirm(id, action) {
      const token = generation;
      const records = await api.get(`${base}/categories`);
      if (token !== generation) return;
      const category = records.categories.find(item => item.id === id);
      if (!category) throw new Error('Category not found.');
      if (action === 'delete' && category.count > 0) {
        const instruction = category.status === 'Archived'
          ? 'Restore this category, then merge its projects into another category before deleting it.'
          : 'Merge its projects into another category before deleting it.';
        showDialog(`<h2>Move the projects first</h2><p>${escape(category.name)} has ${category.count} assigned projects.</p>
          <p>${instruction}</p><div class="action-list">${button('Review assigned projects', 'projects', id)}${button('Close', 'cancel')}</div>`);
        return;
      }
      const descriptions = {
        archive: 'Existing project assignments will remain. Designers will no longer be able to select this category for new assignments.',
        restore: 'Designers will be able to select this category again.',
        feature: category.featured ? 'This category will be removed from the featured discovery list.' : 'Customers will see this category in the featured discovery list.',
        delete: 'This category will move to Deleted categories, where you can review its details and merge destination.',
      };
      const labels = { archive: 'Archive', restore: 'Restore', feature: category.featured ? 'Unfeature' : 'Feature', delete: 'Delete' };
      const label = labels[action];
      showDialog(`<h2>${label} ${escape(category.name)}?</h2><p>${descriptions[action]}</p>
        <form data-management-form="state" data-id="${escape(id)}" data-version="${category.version}"
          data-operation="${action}" data-featured="${!category.featured}" class="form-stack">
          ${formError()}<div class="action-list"><button class="button">${label} category</button>${button('Cancel', 'cancel')}</div>
        </form>`);
    }

    async merge() {
      const token = generation;
      const result = await api.get(`${base}/categories?status=Active`);
      if (token !== generation) return;
      this.mergeCandidates = result.categories;
      if (this.mergeCandidates.length < 2) throw new Error('Create or restore another category before merging. Two active categories are required.');
      const options = selected => this.mergeCandidates.map((category, index) =>
        `<option value="${escape(category.id)}" ${index === selected ? 'selected' : ''}>${escape(category.name)} · ${category.count} projects</option>`).join('');
      showDialog(`<h2>Merge project categories</h2>
        <p>Projects assigned to the source will be grouped under the target. A project already in both categories will keep one target assignment.</p>
        <form data-management-form="merge" class="form-stack">
          <label>SOURCE CATEGORY TO MERGE<select name="sourceId">${options(0)}</select></label>
          <label>TARGET CATEGORY TO KEEP<select name="targetId">${options(1)}</select></label>
          <p class="hint">The source will be marked as merged. The target keeps its name, description and featured setting.</p>
          <label class="checkbox"><input type="checkbox" required>I confirm the source and target selections.</label>
          ${formError()}<button class="button">Merge categories</button>
        </form>`);
    }

    async confirmMerge(sourceId, targetId) {
      const source = this.mergeCandidates.find(category => category.id === sourceId);
      const target = this.mergeCandidates.find(category => category.id === targetId);
      if (!source || !target) throw new Error('Reopen the merge form and select both categories.');
      const result = await api.send(`${base}/categories/merge`, {
        sourceId, targetId, sourceVersion: source.version, targetVersion: target.version,
      });
      AG.toast(`Merged ${result.movedCount} project assignments. Removed ${result.duplicatesRemoved} duplicate links.`);
      return result;
    }

    async projects(id) {
      const token = generation;
      const result = await api.get(`${base}/categories/${encodeURIComponent(id)}/projects`);
      if (token !== generation) return;
      showDialog(`<h2>Projects in ${escape(result.category.name)}</h2>
        <p>${result.projects.length} assigned projects · ${escape(result.category.status)}</p>
        ${result.target ? `<p>Merged into ${escape(result.target.name)}.
          ${result.target.deleted_at ? 'The target is listed in Deleted categories.' : button('Review target projects', 'projects', result.target.id)}</p>` : ''}
        <div class="management-project-list">${result.projects.map(project => `
          <article class="management-project"><img src="assets/${escape(project.image)}.jpg" alt="" loading="lazy">
            <div><b>${escape(project.title)}</b><p>${escape(project.firm)} · ${escape(project.type)} · ${escape(project.location)}</p>
              <small>${project.categoryNames.map(escape).join(' · ')}</small></div></article>`).join('') ||
          '<p>No projects are currently assigned to this category.</p>'}</div>`);
    }
  }

  class DeletedCategoriesPage {
    constructor() {
      this.search = '';
      this.searchGeneration = 0;
    }

    async render(token) {
      main.innerHTML = heading('Deleted categories', 'Review categories removed from the directory and their merge destinations.', button('Refresh', 'refresh')) + `
        <div class="portal-toolbar"><label>SEARCH DELETED CATEGORIES
          <input id="management-deleted-search" placeholder="Search by category name" value="${escape(this.search)}"></label></div>
        <p id="management-deleted-error" class="inline-error" role="alert"></p>
        ${panel('Deleted category history', '<div id="management-deleted" aria-live="polite"><p class="panel-body">Loading deleted categories…</p></div>')}`;
      await this.refresh(token);
    }

    async refresh(token = generation) {
      if (activeSection !== 'deleted') return;
      const searchToken = ++this.searchGeneration;
      const query = new URLSearchParams({ search: this.search });
      try {
        const result = await api.get(`${base}/categories/deleted?${query}`);
        if (token !== generation || searchToken !== this.searchGeneration) return;
        document.querySelector('#management-deleted-error').textContent = '';
        document.querySelector('#management-deleted').innerHTML = `<div class="table-wrap"><table>
          <thead><tr><th>Category</th><th>Previous status</th><th>Merged into</th><th>Deleted on</th></tr></thead>
          <tbody>${result.categories.map(category => `<tr>
            <td><b>${escape(category.name)}</b><small>${escape(category.description)}</small></td>
            <td>${status(category.status)}</td><td>${escape(category.target || '—')}</td>
            <td>${escape(dateLabel(category.deleted_at))}</td></tr>`).join('') ||
            `<tr><td colspan="4">${this.search ? 'No deleted categories match your search.' : 'No deleted categories yet.'}</td></tr>`}
          </tbody></table></div>`;
      } catch (error) {
        if (token === generation && searchToken === this.searchGeneration) {
          showError(error, document.querySelector('#management-deleted-error'));
        }
      }
    }
  }

  class CategoryUsagePage {
    async render(token) {
      const result = await api.get(`${base}/categories/usage`);
      if (token !== generation) return;
      main.innerHTML = heading('Category usage', 'Review current project assignments and all recorded activity before changing a category.', button('Refresh', 'refresh')) +
        panel('Usage by category', `<div class="table-wrap"><table>
          <thead><tr><th>Category</th><th>Projects</th><th>Views</th><th>Favourite additions</th><th>Enquiries</th><th>Action</th></tr></thead>
          <tbody>${result.categories.map(category => `<tr><td><b>${escape(category.name)}</b><small>${escape(category.status)}</small></td>
            <td>${category.projects}</td><td>${category.views}</td><td>${category.favourites}</td><td>${category.enquiries}</td>
            <td>${button('Review projects', 'projects', category.id)}</td></tr>`).join('') ||
          '<tr><td colspan="6">Create a category to begin tracking its usage.</td></tr>'}</tbody></table></div>`, 'All available history') +
        '<p class="small-note">Figures follow current category assignments. Projects can appear in several categories. Favourite additions count recorded save actions.</p>';
    }
  }

  class ActivityReportPage {
    constructor() {
      this.snapshot = null;
      this.selection = null;
    }

    async render(token, comparison) {
      const result = await api.get(`${base}/categories`);
      if (token !== generation) return;
      const previous = new Date(`${settings.today}T12:00:00Z`);
      previous.setUTCDate(1);
      previous.setUTCMonth(previous.getUTCMonth() - 1);
      const selection = { period: 'monthly', date: settings.today, categoryId: '',
        baselineDate: previous.toISOString().slice(0, 10), comparisonDate: settings.today, ...this.selection };
      const categories = result.categories.filter(category => category.status !== 'Merged');
      if (!categories.some(category => category.id === selection.categoryId)) selection.categoryId = '';
      main.innerHTML = heading(comparison ? 'Compare reporting periods' : 'Platform activity reports',
        'Review activity for a day, a Monday-to-Sunday week, or a calendar month.', button('Export displayed CSV', 'export', '', 'disabled id="management-export"')) + `
        <form data-management-form="report" class="portal-toolbar" data-comparison="${comparison}">
          <label>PERIOD<select name="period" aria-label="PERIOD">${['daily', 'weekly', 'monthly'].map(period =>
            `<option value="${period}" ${selection.period === period ? 'selected' : ''}>${period[0].toUpperCase() + period.slice(1)}</option>`).join('')}</select></label>
          ${comparison ? `<label>BASELINE DATE<input type="date" name="baselineDate" required value="${escape(selection.baselineDate)}"></label>
            <label>COMPARISON DATE<input type="date" name="comparisonDate" required value="${escape(selection.comparisonDate)}"></label>` :
            `<label>DATE IN PERIOD<input type="date" name="date" required value="${escape(selection.date)}"></label>`}
          <label>CATEGORY<select name="categoryId"><option value="">All categories</option>${categories.map(category =>
            `<option value="${escape(category.id)}" ${category.id === selection.categoryId ? 'selected' : ''}>${escape(category.name)}${category.status === 'Archived' ? ' (archived)' : ''}</option>`).join('')}</select></label>
          <button class="button">Apply selection</button>
        </form><p class="small-note">Apply your selections to update the displayed report. Dates use Singapore time.</p>
        <p class="inline-error" id="management-report-error" role="alert"></p>
        <div id="management-report" aria-live="polite"></div>`;
      const matchingKind = this.snapshot && (this.snapshot.kind === 'comparison') === comparison;
      if (matchingKind) this.showReport();
      else await this.generate(Object.fromEntries(new FormData(main.querySelector('form'))), comparison, token);
    }

    async generate(selection, comparison, token = generation) {
      try {
        const endpoint = comparison ? '/reports/compare' : '/reports';
        const result = await api.send(base + endpoint, selection);
        if (token !== generation) return;
        this.selection = { ...this.selection, ...selection };
        this.snapshot = result.report;
        document.querySelector('#management-report-error').textContent = '';
        this.showReport();
      } catch (error) {
        if (token === generation) showError(error, document.querySelector('#management-report-error'));
      }
    }

    showReport() {
      const report = this.snapshot;
      const comparison = report.kind === 'comparison';
      const scope = report.category ? report.category.name : 'All categories';
      const periods = comparison ? `Baseline ${report.baselinePeriod.label} · Comparison ${report.period.label}` : report.period.label;
      document.querySelector('#management-report').innerHTML = `<div class="management-report-caption">
        <b>${escape(scope)}</b><p>${escape(periods)} · Singapore time</p><small>Generated ${escape(dateLabel(report.generatedAt))}</small></div>` +
        metrics(report.rows.map(row => [row.label, row.value, comparison ? 'Comparison period' : 'Selected period'])) +
        panel(comparison ? 'Period comparison' : 'Activity totals', `<div class="table-wrap"><table>
          <thead><tr><th>Metric</th>${comparison ? '<th>Baseline</th><th>Comparison</th><th>Change</th><th>% change</th>' : '<th>Count</th>'}</tr></thead>
          <tbody>${report.rows.map(row => `<tr><td>${escape(row.label)}</td>${comparison ?
            `<td>${row.baseline}</td><td>${row.value}</td><td>${row.difference > 0 ? '+' : ''}${row.difference}</td>
             <td>${row.percentChange === null ? 'N/A' : `${row.percentChange > 0 ? '+' : ''}${row.percentChange}%`}</td>` :
            `<td>${row.value}</td>`}</tr>`).join('')}</tbody></table></div>`) +
        '<p class="small-note">Projects created counts new project records within the period. Activity follows current category assignments. A zero baseline gives N/A for percentage change.</p>';
      document.querySelector('#management-export').disabled = false;
    }

    async export() {
      if (!this.snapshot) throw new Error('Generate a report before exporting.');
      const response = await fetch(`${base}/reports/${encodeURIComponent(this.snapshot.id)}/export`);
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'The report could not be exported.');
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `AGroup-report-${this.snapshot.period.startDate}.csv`;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      AG.toast('The displayed report has been exported.');
    }
  }

  const categoryPage = new CategoryManagementPage();
  const deletedPage = new DeletedCategoriesPage();
  const usagePage = new CategoryUsagePage();
  const reportPage = new ActivityReportPage();

  async function overview(token) {
    const result = await api.get(`${base}/overview`);
    if (token !== generation) return;
    const counts = result.counts;
    main.innerHTML = heading('Your workspace, at a glance.', 'Manage project categories and understand activity across the platform.', button('Refresh', 'refresh')) +
      metrics([['Active categories', counts.activeCategories, `${counts.featuredCategories} featured for customers`],
        ['Project views', counts.views, result.period.label], ['Favourite additions', counts.favourites, result.period.label],
        ['Enquiries', counts.enquiries, result.period.label]]) + `<div class="dashboard-columns">` +
      panel('Manage your workspace', '<div class="panel-body"><div class="quick-actions">' +
        [['categories', 'Project categories'], ['deleted', 'Deleted categories'], ['usage', 'Category usage'], ['reports', 'Activity reports'], ['compare', 'Compare periods']]
          .map(([path, label]) => `<a href="#management/${path}">${label}<span>→</span></a>`).join('') + '</div></div>') +
      panel('Recent category changes', `<div class="panel-body"><ul class="activity-list">${result.recent.map(entry =>
        `<li><span class="activity-dot"></span><div>${escape(entry.action)}<small>${escape(entry.record)} · ${escape(dateLabel(entry.occurred_at))}</small></div></li>`).join('') ||
        '<li>Your category changes will appear here.</li>'}</ul></div>`) + '</div>';
  }

  async function render(section) {
    clearTimeout(searchTimer);
    activeSection = section;
    const token = ++generation;
    document.body.classList.add('management-live');
    document.querySelector('.portal-top .pill').textContent = 'LOCAL WORKSPACE';
    document.querySelector('.portal-footer').textContent = 'AGroup · Local development · Includes seeded sample projects and activity. Changes are saved on this computer.';
    main.innerHTML = '<p class="management-loading" role="status">Loading your workspace…</p>';
    try {
      settings = await api.session();
      if (token !== generation) return;
      if (section === 'categories') await categoryPage.render(token);
      else if (section === 'deleted') await deletedPage.render(token);
      else if (section === 'usage') await usagePage.render(token);
      else if (section === 'reports' || section === 'compare') await reportPage.render(token, section === 'compare');
      else await overview(token);
    } catch (error) {
      if (token !== generation) return;
      main.innerHTML = heading('Open the local application', 'Start the AGroup application server, then reload this workspace.') +
        `<section class="panel"><div class="panel-body"><p class="inline-error" role="alert">${escape(error.message)}</p>
          <p>From the AGroup folder, run</p><pre>.\.venv\Scripts\python.exe app.py</pre>
          <p>Open http://127.0.0.1:8000/portal.html#management/overview.</p>${button('Try again', 'refresh')}</div></section>`;
    }
  }

  function leave() {
    clearTimeout(searchTimer);
    generation += 1;
    activeSection = '';
    document.body.classList.remove('management-live');
    document.querySelector('.portal-top .pill').textContent = 'INTERACTIVE WIREFRAME';
    document.querySelector('.portal-footer').textContent = 'AGroup · Academic prototype · Sample records and browser-local actions for the other workspaces.';
  }

  document.addEventListener('click', async event => {
    const selected = event.target.closest('[data-management-action]');
    if (!selected || !activeSection) return;
    const action = selected.dataset.managementAction;
    try {
      if (action === 'create') await categoryPage.edit();
      else if (action === 'edit') await categoryPage.edit(selected.dataset.id);
      else if (['archive', 'restore', 'feature', 'delete'].includes(action)) await categoryPage.confirm(selected.dataset.id, action);
      else if (action === 'merge') await categoryPage.merge();
      else if (action === 'projects') await categoryPage.projects(selected.dataset.id);
      else if (action === 'export') await reportPage.export();
      else if (action === 'cancel') modal.close();
      else if (action === 'refresh') { modal.close(); await render(activeSection); }
    } catch (error) { AG.toast(error.message); }
  });

  let searchTimer;
  document.addEventListener('input', event => {
    if (event.target.id === 'management-deleted-search') {
      deletedPage.search = event.target.value;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => deletedPage.refresh(), 180);
      return;
    }
    if (event.target.id !== 'management-search') return;
    categoryPage.search = event.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => categoryPage.refresh(), 180);
  });
  document.addEventListener('change', event => {
    if (event.target.id !== 'management-status') return;
    categoryPage.status = event.target.value;
    categoryPage.refresh();
  });

  document.addEventListener('submit', async event => {
    const form = event.target.closest('[data-management-form]');
    if (!form) return;
    event.preventDefault();
    const token = generation;
    const values = Object.fromEntries(new FormData(form));
    const controls = [...form.querySelectorAll('button, input, select, textarea')];
    const previousDisabled = controls.map(control => control.disabled);
    controls.forEach(control => { control.disabled = true; });
    const errorTarget = form.querySelector('[data-management-error]');
    if (errorTarget) errorTarget.textContent = '';
    try {
      const kind = form.dataset.managementForm;
      if (kind === 'report') {
        await reportPage.generate(values, form.dataset.comparison === 'true', token);
        return;
      }
      if (kind === 'category') {
        const id = form.dataset.id;
        if (id) values.version = Number(form.dataset.version);
        await api.send(`${base}/categories${id ? '/' + encodeURIComponent(id) : ''}`, values, id ? 'PATCH' : 'POST');
        AG.toast('Category saved.');
      } else if (kind === 'state') {
        values.version = Number(form.dataset.version);
        if (form.dataset.operation === 'feature') values.featured = form.dataset.featured === 'true';
        const deleting = form.dataset.operation === 'delete';
        const endpoint = `${base}/categories/${encodeURIComponent(form.dataset.id)}${deleting ? '' : '/' + form.dataset.operation}`;
        await api.send(endpoint, values, deleting ? 'DELETE' : 'POST');
        AG.toast(deleting ? 'Category moved to Deleted categories.' : 'Category updated.');
      } else if (kind === 'merge') {
        await categoryPage.confirmMerge(values.sourceId, values.targetId);
      }
      if (token === generation && activeSection) {
        modal.close();
        await render(activeSection);
      }
    } catch (error) {
      if (errorTarget) showError(error, errorTarget);
      else AG.toast(error.message);
    } finally {
      controls.forEach((control, index) => { control.disabled = previousDisabled[index]; });
    }
  });

  window.PlatformManagement = { render, leave };
})();
