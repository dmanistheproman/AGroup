/* Shared UI components (boundary classes of the shared parts), used by every role's pages.
   Record parts (status badge, reason dialog, history, messages, notes) are in records.js; this file adds:
     S-05 ListPage        AGroupUI.toolbar(...), table(...), pager(...), listPage(...), state(kind, text)
     S-03 UploadWidget    AGroupUI.uploadWidget({...}), checkFiles(input, kind), send(url, formData, onProgress)
     S-06 PeriodSelector  AGroupUI.periodSelector({...}), periodQuery(form)
     S-06 TrendChart      AGroupUI.trendChart(rows, series, {title})
     S-08 ProjectCard     AGroupUI.projectCard(project, {saved}), imageGallery(images, {title})
     S-10 CategoryPicker  AGroupUI.categoryPicker(categories, {...}), loadCategories()
     S-11 Rating          AGroupUI.ratingInput(name, value), ratingDisplay(average, count), ratingForm({...})
     S-12 FormView        AGroupUI.formView.submit(form, method, url, body), showErrors, clearErrors, busy, done
     S-20 RecordPage      AGroupUI.recordPage({eyebrow, title, status, details, actions, sections})
   Every function returns HTML text (or a Promise) so it works in the customer site and the portal alike.
   ui-kit.html shows each component. Styles: css/ui.css. */
(() => {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = name => (window.AGroupIcons ? window.AGroupIcons.icon(name) : '');
  const money = n => `S$${Number(n || 0).toLocaleString('en-SG')}`;
  const attrs = obj => Object.entries(obj || {}).map(([k, v]) => `${k}="${esc(v)}"`).join(' ');

  // ---------- S-05 ListPage ----------
  function state(kind, text) {
    const defaults = { loading: 'Loading…', empty: 'Nothing to show yet.', error: 'Could not load this list.' };
    const role = kind === 'error' ? 'role="alert"' : kind === 'loading' ? 'aria-busy="true"' : '';
    return `<div class="list-state ${kind}" ${role}>${kind === 'error' ? icon('x') : ''}<p>${esc(text || defaults[kind])}</p></div>`;
  }

  /* fields: [{name, label, type: 'search' | 'select', value, placeholder, options: [[value, text], ...]}] */
  function toolbar(form, fields, submitLabel = 'Apply') {
    const field = f => f.type === 'select'
      ? `<label>${esc(f.label)}<select name="${esc(f.name)}">${f.options.map(([v, t]) =>
          `<option value="${esc(v)}" ${String(f.value ?? '') === String(v) ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></label>`
      : `<label>${esc(f.label)}<input type="search" name="${esc(f.name)}" value="${esc(f.value || '')}" placeholder="${esc(f.placeholder || '')}"></label>`;
    return `<form class="ui-toolbar" ${attrs(form)}>${fields.map(field).join('')}
      <button class="button outline" type="submit">${icon('search')} ${esc(submitLabel)}</button></form>`;
  }

  /* columns: [{label, cell: row => html}] — cells return HTML, so escape text with AGroupUI.esc */
  function table(columns, rows) {
    return `<div class="table-wrap"><table><thead><tr>${columns.map(c => `<th>${esc(c.label)}</th>`).join('')}</tr></thead>
      <tbody>${rows.map(r => `<tr>${columns.map(c => `<td>${c.cell(r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }

  /* pageAttrs(page) returns the attributes of a page button, e.g. p => `data-shared="page" data-page="${p}"` */
  function pager({ page = 1, pages = 1 }, pageAttrs) {
    if (pages <= 1) return '';
    return `<nav class="pager" aria-label="Pages"><button class="text-button" type="button" ${pageAttrs(page - 1)} ${page <= 1 ? 'disabled' : ''}>${icon('arrow-left')} Previous</button>
      <span>Page ${page} of ${pages}</span>
      <button class="text-button" type="button" ${pageAttrs(page + 1)} ${page >= pages ? 'disabled' : ''}>Next ${icon('arrow-right')}</button></nav>`;
  }

  /* One panel: heading with the count, the list (or its empty state) and the pager. */
  function plural(noun, count) {
    if (count === 1) return noun;
    return /[^aeiou]y$/.test(noun) ? `${noun.slice(0, -1)}ies` : `${noun}s`;
  }

  function listPage({ toolbar: tools = '', total = 0, noun = 'item', page = 1, pages = 1, body = '', empty, pageAttrs }) {
    return `${tools}<section class="panel ui-list"><div class="panel-heading"><h2>${total} ${esc(plural(noun, total))}</h2>
      ${pages > 1 ? `<small>Page ${page} of ${pages}</small>` : ''}</div>
      ${total ? body : state('empty', empty)}${pageAttrs ? pager({ page, pages }, pageAttrs) : ''}</section>`;
  }

  // ---------- S-03 UploadWidget ----------
  const UPLOAD_RULES = {   // the same rules as backend/services/file_upload_service.py
    image: { exts: ['.jpg', '.jpeg', '.png', '.webp'], max: 1024 * 1024, formats: 'JPG, PNG or WebP', limit: '1 MB' },
    document: { exts: ['.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg'], max: 5 * 1024 * 1024,
                formats: 'PDF, DOC/DOCX or an image', limit: '5 MB' },
  };

  function uploadWidget({ name = 'files', label = 'Files', kind = 'image', multiple = true, required = false } = {}) {
    const rule = UPLOAD_RULES[kind] || UPLOAD_RULES.image;
    return `<div class="upload-widget" data-upload-kind="${esc(kind)}">
      <label class="upload-drop">${icon('upload')}<span><b>${esc(label)}</b><small>${esc(`${rule.formats}, up to ${rule.limit} each`)}</small></span>
        <input type="file" name="${esc(name)}" accept="${rule.exts.join(',')}" ${multiple ? 'multiple' : ''} ${required ? 'required' : ''}></label>
      <ul class="upload-files" aria-live="polite"></ul>
      <progress class="upload-progress" max="100" value="0" hidden></progress></div>`;
  }

  /* Returns {ok, errors}; also lists the chosen files with their problems under the widget. */
  function checkFiles(input, kind) {
    const rule = UPLOAD_RULES[kind || input.closest('[data-upload-kind]')?.dataset.uploadKind] || UPLOAD_RULES.image;
    const errors = [];
    const rows = [...input.files].map(file => {
      const ext = (file.name.match(/\.[^.]+$/) || [''])[0].toLowerCase();
      let problem = '';
      if (!rule.exts.includes(ext)) problem = `Unsupported format. Use ${rule.formats}.`;
      else if (file.size > rule.max) problem = `Larger than ${rule.limit} (${(file.size / 1048576).toFixed(1)} MB).`;
      if (problem) errors.push(`${file.name}: ${problem}`);
      return `<li class="${problem ? 'bad' : ''}">${esc(file.name)} <small>${problem ? esc(problem) : `${Math.ceil(file.size / 1024)} KB`}</small></li>`;
    });
    const list = input.closest('.upload-widget')?.querySelector('.upload-files');
    if (list) list.innerHTML = rows.join('');
    return { ok: errors.length === 0, errors };
  }

  /* Sends FormData with upload progress; resolves {ok, status, data} like AGroupRecords.call. */
  function send(url, formData, onProgress) {
    return new Promise(resolve => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', url);
      xhr.withCredentials = true;
      xhr.upload.addEventListener('progress', e => { if (e.lengthComputable && onProgress) onProgress(Math.round(e.loaded * 100 / e.total)); });
      xhr.addEventListener('load', () => {
        let data = {};
        try { data = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
        resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data });
      });
      xhr.addEventListener('error', () => resolve({ ok: false, status: 0, data: { error: 'The upload could not reach the server.' } }));
      xhr.send(formData);
    });
  }

  document.addEventListener('change', event => {
    const input = event.target;
    if (input.matches && input.matches('.upload-widget input[type=file]')) checkFiles(input);
  });

  // ---------- S-06 PeriodSelector and TrendChart ----------
  const PERIODS = [['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly'], ['custom', 'Custom range']];

  function periodSelector({ period = 'weekly', date = '', from = '', to = '', form = {} } = {}) {
    const today = new Date().toISOString().slice(0, 10);
    return `<form class="period-selector" ${attrs(form)}>
      <label>PERIOD<select name="period">${PERIODS.map(([v, t]) => `<option value="${v}" ${v === period ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label data-period-part="single" ${period === 'custom' ? 'hidden' : ''}>DATE<input type="date" name="date" value="${esc(date || today)}" max="${today}"></label>
      <label data-period-part="range" ${period === 'custom' ? '' : 'hidden'}>FROM<input type="date" name="from" value="${esc(from)}" max="${today}"></label>
      <label data-period-part="range" ${period === 'custom' ? '' : 'hidden'}>TO<input type="date" name="to" value="${esc(to)}" max="${today}"></label>
      <button class="button outline" type="submit">Show</button></form>`;
  }

  /* The query string for GET /api/reports/activity from a period selector form. */
  function periodQuery(form) {
    const p = new URLSearchParams({ period: form.elements.period.value });
    if (p.get('period') === 'custom') { p.set('from', form.elements.from.value); p.set('to', form.elements.to.value); }
    else p.set('date', form.elements.date.value);
    return p.toString();
  }

  document.addEventListener('change', event => {
    const select = event.target;
    if (!select.matches || !select.matches('.period-selector select[name=period]')) return;
    const custom = select.value === 'custom';
    select.form.querySelectorAll('[data-period-part]').forEach(part => {
      part.hidden = (part.dataset.periodPart === 'range') !== custom;
    });
  });

  /* rows: [{label, views, favourites, ...}] (ReportService rows); series: [{key, label}] */
  function trendChart(rows, series, { title = 'Activity over time' } = {}) {
    if (!rows || !rows.length) return state('empty', 'No activity in this period.');
    const W = 640, H = 220, L = 40, B = 28, T = 12, R = 12;
    const max = Math.max(1, ...rows.flatMap(r => series.map(s => Number(r[s.key]) || 0)));
    const x = i => L + (rows.length === 1 ? (W - L - R) / 2 : i * (W - L - R) / (rows.length - 1));
    const y = v => T + (H - T - B) * (1 - v / max);
    const ticks = [0, Math.round(max / 2), max];
    const every = Math.ceil(rows.length / 8);
    const lines = series.map((s, n) => `<polyline class="series-${n}" points="${rows.map((r, i) => `${x(i).toFixed(1)},${y(Number(r[s.key]) || 0).toFixed(1)}`).join(' ')}"/>`).join('');
    return `<figure class="trend-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">
        <title>${esc(title)}</title>
        ${ticks.map(t => `<line class="grid" x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}"/><text class="axis" x="${L - 6}" y="${y(t) + 4}" text-anchor="end">${t}</text>`).join('')}
        ${rows.map((r, i) => i % every === 0 ? `<text class="axis" x="${x(i)}" y="${H - 8}" text-anchor="middle">${esc(r.label || r.key)}</text>` : '').join('')}
        ${lines}</svg>
      <figcaption>${series.map((s, n) => `<span class="legend series-${n}">${esc(s.label)}</span>`).join('')}</figcaption>
      <details><summary>Show as a table</summary>${table([{ label: 'Period', cell: r => esc(r.label || r.key) },
        ...series.map(s => ({ label: s.label, cell: r => esc(r[s.key] ?? 0) }))], rows)}</details></figure>`;
  }

  // ---------- S-08 ProjectCard and ImageGallery ----------
  const PLACEHOLDER = 'assets/living.jpg';

  function imageSrc(image) {
    if (!image) return PLACEHOLDER;
    return /[/.]/.test(image) ? image : `assets/${image}.jpg`;
  }

  function projectCard(p, { saved = false, link = `index.html#project-${p.id}` } = {}) {
    const firm = p.firm || p.company_name || '';
    const meta = [p.type || p.house_type, p.area].filter(Boolean).join(' · ');
    return `<article class="project-card ui-project-card"><div class="project-photo">
        <a href="${esc(link)}" aria-label="View ${esc(p.title)}"><img src="${esc(imageSrc(p.image || p.primary_image))}" alt="${esc(p.title)}" loading="lazy" onerror="this.src='${PLACEHOLDER}'"></a>
        ${saved !== null ? `<span class="save-button ${saved ? 'saved' : ''}" aria-hidden="true">${icon('heart')}</span>` : ''}
        ${p.style ? `<span class="project-badge">${esc(String(p.style).toUpperCase())}</span>` : ''}</div>
      <h3><a href="${esc(link)}">${esc(p.title || 'Untitled project')}</a></h3>
      <p class="card-firm">${firm ? `By ${esc(firm)}` : 'Designer not given'}${p.location ? ` · ${esc(p.location)}` : ''}</p>
      <div class="project-meta"><span>${esc(meta || '—')}</span><span>${p.price || p.estimated_cost ? `${money(p.price || p.estimated_cost)} <small>est.</small>` : 'Cost on request'}</span></div></article>`;
  }

  /* images: list of names or paths; the first is the primary image. Thumbnails swap the main image. */
  function imageGallery(images, { title = 'Project' } = {}) {
    const list = (images && images.length ? images : [null]).map(imageSrc);
    return `<div class="image-gallery"><img class="gallery-main" src="${esc(list[0])}" alt="${esc(title)}, image 1 of ${list.length}" onerror="this.src='${PLACEHOLDER}'">
      ${list.length > 1 ? `<div class="gallery-thumbs">${list.map((src, i) => `<button type="button" data-gallery-image="${esc(src)}" data-gallery-index="${i + 1}"
        aria-label="Show image ${i + 1}" ${i === 0 ? 'aria-current="true"' : ''}><img src="${esc(src)}" alt="" loading="lazy"></button>`).join('')}</div>` : ''}</div>`;
  }

  document.addEventListener('click', event => {
    const thumb = event.target.closest('[data-gallery-image]');
    if (!thumb) return;
    const gallery = thumb.closest('.image-gallery');
    const main = gallery.querySelector('.gallery-main');
    main.src = thumb.dataset.galleryImage;
    main.alt = main.alt.replace(/image \d+/, `image ${thumb.dataset.galleryIndex}`);
    gallery.querySelectorAll('[data-gallery-image]').forEach(b => b.removeAttribute('aria-current'));
    thumb.setAttribute('aria-current', 'true');
  });

  // ---------- S-10 CategoryPicker ----------
  let categoryCache = null;
  async function loadCategories() {
    if (!categoryCache) {
      categoryCache = fetch('/api/categories', { credentials: 'same-origin' })
        .then(r => (r.ok ? r.json() : { categories: [] })).then(d => d.categories || []).catch(() => []);
    }
    return categoryCache;
  }

  function categoryPicker(categories, { name = 'category_id', label = 'CATEGORY', multiple = false, selected = [], required = false } = {}) {
    const chosen = new Set([].concat(selected).map(String));
    if (!categories.length) return `<p class="small-note">No active categories.</p>`;
    if (!multiple) {
      return `<label>${esc(label)}<select name="${esc(name)}" ${required ? 'required' : ''}><option value="">Choose a category</option>
        ${categories.map(c => `<option value="${esc(c.id)}" ${chosen.has(String(c.id)) ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></label>`;
    }
    return `<fieldset class="category-picker"><legend>${esc(label)}</legend>${categories.map(c => `<label class="category-chip">
      <input type="checkbox" name="${esc(name)}" value="${esc(c.id)}" ${chosen.has(String(c.id)) ? 'checked' : ''}><span>${esc(c.name)}</span></label>`).join('')}</fieldset>`;
  }

  // ---------- S-11 Rating ----------
  function ratingInput(name = 'score', value = 0) {
    return `<fieldset class="rating-input"><legend>RATING</legend><div class="stars">${[5, 4, 3, 2, 1].map(n => `
      <input type="radio" id="${esc(name)}-${n}" name="${esc(name)}" value="${n}" ${Number(value) === n ? 'checked' : ''} required>
      <label for="${esc(name)}-${n}" title="${n} star${n > 1 ? 's' : ''}">${icon('star')}<span class="visually-hidden">${n} star${n > 1 ? 's' : ''}</span></label>`).join('')}</div></fieldset>`;
  }

  function ratingDisplay(average, count) {
    const value = Math.max(0, Math.min(5, Number(average) || 0));
    return `<span class="rating-display" aria-label="Rated ${value.toFixed(1)} out of 5${count !== undefined ? ` from ${count} review${count === 1 ? '' : 's'}` : ''}">
      <span class="stars-track" aria-hidden="true"><span class="stars-base">${icon('star').repeat(5)}</span>
        <span class="stars-fill" style="width:${(value / 5 * 100).toFixed(0)}%">${icon('star').repeat(5)}</span></span>
      <b>${value.toFixed(1)}</b>${count !== undefined ? `<small>(${count})</small>` : ''}</span>`;
  }

  function ratingForm({ form = {}, title = 'Rate your experience', commentLabel = 'COMMENT', submitLabel = 'Send rating' } = {}) {
    return `<form class="rating-form form-stack" ${attrs(form)}><h3>${esc(title)}</h3>${ratingInput('score')}
      <label>${esc(commentLabel)}<textarea name="comment" maxlength="1000" placeholder="What went well, and what could be better?"></textarea></label>
      <p class="form-message" role="status" hidden></p><button class="button" type="submit">${esc(submitLabel)}</button></form>`;
  }

  // ---------- S-12 FormView ----------
  async function sendForm(method, url, form) {
    const res = await fetch(url, { method, credentials: 'same-origin', body: form });
    return { ok: res.ok, status: res.status, data: await res.json().catch(() => ({})) };
  }

  const formView = {
    clearErrors(form) {
      form.querySelectorAll('.field-error').forEach(e => e.remove());
      form.querySelectorAll('[aria-invalid]').forEach(e => e.removeAttribute('aria-invalid'));
      const message = form.querySelector('.form-message');
      if (message) { message.hidden = true; message.className = 'form-message'; }
    },
    /* errors: {field: message} or the API's {error, field}; a message without a field goes to the form. */
    showErrors(form, errors) {
      formView.clearErrors(form);
      const list = errors && errors.field ? { [errors.field]: errors.error }
        : errors && errors.error ? { '': errors.error } : (errors || {});
      let first = null;
      for (const [field, text] of Object.entries(list)) {
        const input = field && form.elements[field];
        if (input && input.insertAdjacentHTML) {
          input.setAttribute('aria-invalid', 'true');
          input.insertAdjacentHTML('afterend', `<span class="field-error">${esc(text)}</span>`);
          first = first || input;
        } else {
          formView.message(form, text, 'error');
        }
      }
      if (first) first.focus();
    },
    message(form, text, kind = 'success') {
      let box = form.querySelector('.form-message');
      if (!box) { box = document.createElement('p'); box.className = 'form-message'; box.setAttribute('role', 'status'); form.append(box); }
      box.textContent = text;
      box.className = `form-message ${kind}`;
      box.hidden = false;
    },
    busy(form, on) {
      form.querySelectorAll('button[type=submit], button:not([type])').forEach(b => {
        if (on) { b.dataset.label = b.innerHTML; b.disabled = true; b.textContent = 'Saving…'; }
        else if (b.dataset.label !== undefined) { b.innerHTML = b.dataset.label; b.disabled = false; delete b.dataset.label; }
      });
      form.setAttribute('aria-busy', on ? 'true' : 'false');
    },
    done(form, text) { formView.message(form, text, 'success'); },
    /* Validates with the browser, sends the body (JSON, or multipart when it is a FormData with a file) and shows
       the result. Resolves {ok, status, data}. */
    async submit(form, method, url, body, success = 'Saved.') {
      formView.clearErrors(form);
      if (!form.reportValidity()) return { ok: false, status: 0, data: {} };
      formView.busy(form, true);
      let result;
      try {
        result = body instanceof FormData ? await sendForm(method, url, body) : await window.AGroupRecords.call(method, url, body);
      } catch {
        result = { ok: false, status: 0, data: { error: 'The server could not be reached. Try again.' } };
      }
      formView.busy(form, false);
      if (result.ok) formView.done(form, success);
      else formView.showErrors(form, result.data);
      return result;
    },
  };

  // ---------- S-20 RecordPage ----------
  /* details: [[label, html], ...]; actions: html; sections: [{title, icon, body}] */
  function recordPage({ eyebrow = '', title = '', status = '', details = [], actions = '', sections = [] }) {
    const R = window.AGroupRecords;
    return `<article class="record-page"><div class="record-header"><div>${eyebrow ? `<p class="eyebrow">${esc(eyebrow)}</p>` : ''}
        <h2>${esc(title)}</h2></div>${status ? R.statusBadge(status) : ''}</div>
      ${details.length ? `<dl class="detail-list">${details.filter(Boolean).map(([dt, dd]) => `<dt>${esc(dt)}</dt><dd>${dd}</dd>`).join('')}</dl>` : ''}
      ${actions ? `<div class="record-actions">${actions}</div>` : ''}
      ${sections.filter(Boolean).map(s => `<section class="record-section"><h3>${s.icon ? icon(s.icon) : ''} ${esc(s.title)}</h3>${s.body}</section>`).join('')}</article>`;
  }

  // ---------- Toast: the short message at the bottom of the page ----------
  /* Pages without data.js (the inbox) get the same toast as the website, instead of a browser alert. */
  if (!window.AG || !window.AG.toast) {
    window.AG = Object.assign(window.AG || {}, {
      toast(message) {
        let el = document.getElementById('toast');
        if (!el) {
          el = document.createElement('div');
          el.id = 'toast'; el.className = 'toast'; el.setAttribute('role', 'status'); el.setAttribute('aria-live', 'polite');
          document.body.append(el);
        }
        el.textContent = message;
        el.classList.add('show');
        clearTimeout(window.agToast);
        window.agToast = setTimeout(() => el.classList.remove('show'), 3500);
      },
    });
  }

  window.AGroupUI = { esc, icon, money, state, toolbar, table, pager, listPage, uploadWidget, checkFiles, send,
                      periodSelector, periodQuery, trendChart, projectCard, imageGallery, loadCategories,
                      categoryPicker, ratingInput, ratingDisplay, ratingForm, formView, recordPage, UPLOAD_RULES };
})();
