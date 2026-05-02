/* ZimKAG client app — vanilla JS, no build step. */
(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // ── State ────────────────────────────────────────────────────────────
  const state = {
    file: null,
    job: null,
    results: [],
    filter: 'all',
    search: '',
    chart: null,
  };

  const RISK_META = {
    high:        { label: 'High',        color: '#dc2626', icon: '🚨' },
    medium:      { label: 'Medium',      color: '#ea580c', icon: '🟠' },
    low:         { label: 'Low',         color: '#ca8a04', icon: '🟡' },
    opportunity: { label: 'Opportunity', color: '#16a34a', icon: '✅' },
    neutral:     { label: 'Neutral',     color: '#6b7280', icon: '⚪' },
  };

  // ── Dark-mode toggle ─────────────────────────────────────────────────
  const root = document.documentElement;
  const stored = localStorage.getItem('zk-theme');
  if (stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    root.classList.add('dark');
  }
  $('#dark-toggle').addEventListener('click', () => {
    root.classList.toggle('dark');
    localStorage.setItem('zk-theme', root.classList.contains('dark') ? 'dark' : 'light');
    if (state.chart) renderChart(state.results);
  });

  // ── Tabs ─────────────────────────────────────────────────────────────
  $('#tab-upload').addEventListener('click', () => switchTab('upload'));
  $('#tab-paste').addEventListener('click',  () => switchTab('paste'));
  function switchTab(which) {
    const upload = which === 'upload';
    $('#tab-upload').classList.toggle('tab-active', upload);
    $('#tab-paste').classList.toggle('tab-active', !upload);
    $('#pane-upload').classList.toggle('hidden', !upload);
    $('#pane-paste').classList.toggle('hidden',  upload);
  }

  // ── File input + drag/drop ───────────────────────────────────────────
  const dz = $('#drop-zone');
  const fileInput = $('#file-input');

  fileInput.addEventListener('change', (e) => setFile(e.target.files[0]));

  ['dragenter', 'dragover'].forEach(ev =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add('drag-over'); }));
  ['dragleave', 'drop'].forEach(ev =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove('drag-over'); }));
  dz.addEventListener('drop', (e) => {
    if (e.dataTransfer.files?.length) setFile(e.dataTransfer.files[0]);
  });

  function setFile(f) {
    if (!f) return;
    const ok = ['pdf', 'docx', 'txt'].includes(f.name.split('.').pop().toLowerCase());
    if (!ok) return toast('Unsupported file type. Use PDF, DOCX or TXT.', true);
    if (f.size > 25 * 1024 * 1024) return toast('File too large (max 25 MB).', true);
    state.file = f;
    const fn = $('#file-name');
    fn.textContent = `${f.name}  ·  ${(f.size / 1024).toFixed(1)} KB`;
    fn.classList.remove('hidden');
  }

  // ── Sample clauses ───────────────────────────────────────────────────
  $$('.sample-clause').forEach(b => b.addEventListener('click', () => {
    switchTab('paste');
    $('#text-input').value = b.dataset.clause;
    $('#text-input').focus();
  }));

  // ── Analyse button ───────────────────────────────────────────────────
  $('#analyse-btn').addEventListener('click', startAnalysis);

  async function startAnalysis() {
    const useLlm = $('#opt-llm').checked;
    const onUpload = !$('#pane-upload').classList.contains('hidden');
    const text = $('#text-input').value.trim();

    if (onUpload && !state.file)  return toast('Please choose a file first.', true);
    if (!onUpload && !text)        return toast('Please paste some contract text.', true);

    setLoading(true);
    showProgress(true);
    $('#empty-state').classList.add('hidden');
    $('#summary-panel').classList.add('hidden');
    $('#results-panel').classList.add('hidden');

    try {
      let resp;
      if (onUpload) {
        const fd = new FormData();
        fd.append('file', state.file);
        fd.append('with_llm', useLlm.toString());
        resp = await fetch('/api/analyze/file', { method: 'POST', body: fd });
      } else {
        resp = await fetch('/api/analyze/text', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, with_llm: useLlm }),
        });
      }
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const job = await resp.json();
      state.job = job;
      $('#progress-filename').textContent = job.filename;
      pollJob(job.job_id);
    } catch (err) {
      console.error(err);
      toast(err.message || 'Analysis failed.', true);
      setLoading(false);
      showProgress(false);
    }
  }

  async function pollJob(jobId) {
    const interval = setInterval(async () => {
      try {
        const r = await fetch(`/api/jobs/${jobId}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        $('#progress-pct').textContent = j.progress;
        $('#progress-bar').style.width = `${j.progress}%`;
        $('#progress-text').textContent = `Analysed ${j.done} of ${j.total} clauses`;
        if (j.status === 'done') {
          clearInterval(interval);
          showProgress(false);
          setLoading(false);
          renderResults(j);
        }
      } catch (e) {
        clearInterval(interval);
        showProgress(false);
        setLoading(false);
        toast(e.message || 'Lost connection to job.', true);
      }
    }, 800);
  }

  function setLoading(b) {
    $('#analyse-btn').disabled = b;
    $('#analyse-btn').textContent = b ? '⏳ Analysing…' : '🔍 Analyse contract';
  }
  function showProgress(b) {
    $('#progress-panel').classList.toggle('hidden', !b);
  }

  // ── Render results ───────────────────────────────────────────────────
  function renderResults(job) {
    state.results = job.results || [];
    state.job = job;
    $('#summary-panel').classList.remove('hidden');
    $('#results-panel').classList.remove('hidden');
    $('#summary-filename').textContent = `${job.filename} · ${state.results.length} clauses`;
    $('#download-pdf').href = `/api/jobs/${job.id}/report`;

    const counts = { high: 0, medium: 0, low: 0, opportunity: 0, neutral: 0 };
    state.results.forEach(r => { counts[r.risk_level] = (counts[r.risk_level] || 0) + 1; });
    Object.entries(counts).forEach(([k, v]) => { const el = $(`#count-${k}`); if (el) el.textContent = v; });

    renderChart(state.results);
    renderCards();
  }

  function renderChart(results) {
    const counts = { high: 0, medium: 0, low: 0, opportunity: 0, neutral: 0 };
    results.forEach(r => counts[r.risk_level] = (counts[r.risk_level] || 0) + 1);
    const ctx = $('#risk-chart').getContext('2d');
    if (state.chart) state.chart.destroy();
    const dark = root.classList.contains('dark');
    state.chart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: Object.keys(counts).map(k => RISK_META[k].label),
        datasets: [{
          data: Object.values(counts),
          backgroundColor: Object.keys(counts).map(k => RISK_META[k].color),
          borderColor: dark ? '#0f172a' : '#fff',
          borderWidth: 3,
          hoverOffset: 10,
        }],
      },
      options: {
        cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: dark ? '#cbd5e1' : '#334155', font: { size: 11, weight: '600' }, padding: 12, boxWidth: 12 },
          },
          tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.parsed} clauses` } },
        },
        responsive: true,
        maintainAspectRatio: false,
      },
    });
  }

  // ── Filters + search ─────────────────────────────────────────────────
  $$('.filter-pill').forEach(p => p.addEventListener('click', () => {
    $$('.filter-pill').forEach(x => x.classList.remove('filter-active'));
    p.classList.add('filter-active');
    state.filter = p.dataset.filter;
    renderCards();
  }));
  $('#search-input').addEventListener('input', (e) => {
    state.search = e.target.value.toLowerCase().trim();
    renderCards();
  });

  // ── Render clause cards ──────────────────────────────────────────────
  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, m => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  function highlight(text, query) {
    if (!query) return escapeHtml(text);
    const safe = escapeHtml(text);
    const rx = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig');
    return safe.replace(rx, '<mark style="background:#ffc10755;color:inherit;padding:0 2px;border-radius:3px;">$1</mark>');
  }

  function cardHtml(r, idx) {
    const meta = RISK_META[r.risk_level] || RISK_META.neutral;
    const conf = Math.max(2, Math.min(100, r.confidence || 0));
    return `
      <article class="clause-card collapsed" data-risk="${r.risk_level}">
        <header class="card-header" data-toggle>
          <div class="flex items-center gap-3 min-w-0">
            <span class="risk-pill ${r.risk_level}">${meta.icon} ${meta.label}</span>
            <span class="text-xs text-slate-400 dark:text-slate-500 font-mono">#${idx + 1}</span>
            <span class="text-sm truncate text-slate-700 dark:text-slate-200">${highlight(r.clause.slice(0, 140), state.search)}${r.clause.length > 140 ? '…' : ''}</span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <span class="text-xs font-mono text-slate-500 dark:text-slate-400">${r.confidence}%</span>
            <svg class="chev w-4 h-4 text-slate-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </div>
        </header>
        <div class="card-body">
          <div>
            <div class="section-label">Clause</div>
            <p class="clause-text">${highlight(r.clause, state.search)}</p>
            <div class="confidence-bar"><span style="width:${conf}%;background:${meta.color};"></span></div>
            <div class="meta-row">
              <span class="meta-chip">${escapeHtml(r.clause_type || '—')}</span>
              ${r.kg_match ? `<span class="meta-chip">KG: ${escapeHtml(r.kg_match.replace(/_/g, ' '))}</span>` : ''}
              <span class="meta-chip">conf ${r.confidence}%</span>
            </div>
          </div>

          <div class="section-divider"></div>

          <div>
            <div class="section-label">Interpretation</div>
            <p class="clause-text">${escapeHtml(r.interpretation || '')}</p>
          </div>

          ${r.kg_suggestion ? `
            <div class="section-divider"></div>
            <div>
              <div class="section-label">Knowledge-graph guidance</div>
              <p class="kg-text">${escapeHtml(r.kg_suggestion)}</p>
            </div>` : ''}

          ${r.suggested_rewrite && r.suggested_rewrite !== r.clause ? `
            <div class="section-divider"></div>
            <div>
              <div class="section-label">Suggested fairer rewrite</div>
              <div class="rewrite-text">${escapeHtml(r.suggested_rewrite)}</div>
            </div>` : ''}
        </div>
      </article>
    `;
  }

  function renderCards() {
    const container = $('#cards-container');
    let items = state.results;

    if (state.filter !== 'all') {
      items = items.filter(r => r.risk_level === state.filter);
    }
    if (state.search) {
      items = items.filter(r =>
        (r.clause || '').toLowerCase().includes(state.search) ||
        (r.suggested_rewrite || '').toLowerCase().includes(state.search) ||
        (r.kg_suggestion || '').toLowerCase().includes(state.search)
      );
    }

    // Always sort: high → medium → opportunity → low → neutral
    const order = { high: 0, medium: 1, opportunity: 2, low: 3, neutral: 4 };
    items = [...items].sort((a, b) => (order[a.risk_level] ?? 9) - (order[b.risk_level] ?? 9));

    if (!items.length) {
      container.innerHTML = `<p class="text-center text-slate-500 dark:text-slate-400 py-10">No clauses match this filter.</p>`;
      return;
    }
    container.innerHTML = items.map((r, i) => cardHtml(r, i)).join('');

    // Toggle handlers
    container.querySelectorAll('[data-toggle]').forEach(h => {
      h.addEventListener('click', () => {
        const card = h.closest('.clause-card');
        card.classList.toggle('collapsed');
        const chev = h.querySelector('.chev');
        if (chev) chev.style.transform = card.classList.contains('collapsed') ? '' : 'rotate(180deg)';
      });
    });
  }

  // ── Toast ────────────────────────────────────────────────────────────
  let toastTimer;
  function toast(msg, isError = false) {
    const el = $('#toast');
    el.textContent = msg;
    el.style.background = isError ? '#dc2626' : '#0f172a';
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
  }

  // ── Status pill ──────────────────────────────────────────────────────
  (async function checkStatus() {
    const pill = $('#status-pill');
    try {
      const r = await fetch('/api/status');
      const s = await r.json();
      if (s.ok && s.model_loaded) {
        pill.textContent = `● online · ${s.device}${s.llm_enabled ? ' · LLM on' : ''}`;
        pill.style.background = '#16a34a22';
        pill.style.color = '#16a34a';
      } else if (s.ok) {
        pill.textContent = `● KG-only mode${s.llm_enabled ? ' · LLM on' : ''}`;
        pill.style.background = '#ca8a0422';
        pill.style.color = '#ca8a04';
      } else {
        pill.textContent = '● model missing';
        pill.style.background = '#dc262622';
        pill.style.color = '#dc2626';
      }
    } catch {
      pill.textContent = '● offline';
      pill.style.background = '#dc262622';
      pill.style.color = '#dc2626';
    }
  })();

})();
