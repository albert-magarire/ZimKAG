/* ZimKAG recent-analyses dashboard. */
(() => {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const RISK_META = {
    high:        { label: 'High',        color: '#dc2626', icon: '🚨' },
    medium:      { label: 'Medium',      color: '#ea580c', icon: '🟠' },
    low:         { label: 'Low',         color: '#ca8a04', icon: '🟡' },
    opportunity: { label: 'Opportunity', color: '#16a34a', icon: '✅' },
    neutral:     { label: 'Neutral',     color: '#6b7280', icon: '⚪' },
  };

  const state = {
    items: [],
    total: 0,
    limit: 20,
    offset: 0,
    q: '',
    risk: '',
    expanded: new Set(),
  };

  // ── Dark mode ────────────────────────────────────────────────────────
  const root = document.documentElement;
  const stored = localStorage.getItem('zk-theme');
  if (stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    root.classList.add('dark');
  }
  $('#dark-toggle').addEventListener('click', () => {
    root.classList.toggle('dark');
    localStorage.setItem('zk-theme', root.classList.contains('dark') ? 'dark' : 'light');
  });

  // ── Status pill ──────────────────────────────────────────────────────
  (async () => {
    const pill = $('#status-pill');
    try {
      const r = await fetch('/api/status');
      const s = await r.json();
      if (s.ok && s.model_loaded) {
        pill.textContent = `● online · ${s.device}${s.llm_enabled ? ' · LLM on' : ''}`;
        pill.style.background = '#16a34a22';
        pill.style.color = '#16a34a';
      } else {
        pill.textContent = '● degraded';
        pill.style.background = '#ca8a0422';
        pill.style.color = '#ca8a04';
      }
    } catch { pill.textContent = '● offline'; }
  })();

  // ── Filters ──────────────────────────────────────────────────────────
  let searchTimer;
  $('#search-input').addEventListener('input', (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.q = e.target.value.trim();
      state.offset = 0;
      load();
    }, 250);
  });
  $$('.filter-pill').forEach(p => p.addEventListener('click', () => {
    $$('.filter-pill').forEach(x => x.classList.remove('filter-active'));
    p.classList.add('filter-active');
    state.risk = p.dataset.risk || '';
    state.offset = 0;
    load();
  }));
  $('#refresh-btn').addEventListener('click', () => load());
  $('#prev-btn').addEventListener('click', () => {
    state.offset = Math.max(0, state.offset - state.limit);
    load();
  });
  $('#next-btn').addEventListener('click', () => {
    if (state.offset + state.limit < state.total) {
      state.offset += state.limit;
      load();
    }
  });

  // ── Data fetch ───────────────────────────────────────────────────────
  async function load() {
    try {
      const params = new URLSearchParams({
        limit: state.limit, offset: state.offset,
      });
      if (state.q) params.set('q', state.q);
      if (state.risk) params.set('risk', state.risk);
      const r = await fetch(`/api/recent?${params}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      state.items = data.items || [];
      state.total = data.total || 0;
      renderStats(data.stats || {});
      renderTable();
      renderPagination();
    } catch (e) {
      toast(e.message || 'Could not load dashboard', true);
    }
  }

  // ── Render: stats cards ──────────────────────────────────────────────
  function renderStats(s) {
    $('#stat-total').textContent    = s.total_emails ?? 0;
    $('#stat-today').textContent    = s.today ?? 0;
    $('#stat-week').textContent     = s.this_week ?? 0;
    $('#stat-clauses').textContent  = s.total_clauses ?? 0;
    $('#stat-high').textContent     = s.total_high ?? 0;
    $('#stat-medium').textContent   = s.total_medium ?? 0;
    $('#stat-opp').textContent      = s.total_opportunity ?? 0;
    $('#stat-neutral').textContent  = s.total_neutral ?? 0;
  }

  // ── Render: table ────────────────────────────────────────────────────
  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, m => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');
    if (isNaN(d.getTime())) return iso;
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} d ago`;
    return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function riskBars(row) {
    const total = row.total_clauses || 1;
    const segments = [
      { key: 'high',        v: row.count_high },
      { key: 'medium',      v: row.count_medium },
      { key: 'low',         v: row.count_low },
      { key: 'opportunity', v: row.count_opportunity },
      { key: 'neutral',     v: row.count_neutral },
    ];
    return `
      <div class="risk-bar">
        ${segments.map(s => s.v > 0
          ? `<span title="${RISK_META[s.key].label}: ${s.v}" style="background:${RISK_META[s.key].color};width:${(s.v / total) * 100}%"></span>`
          : ''
        ).join('')}
      </div>
      <div class="risk-bar-legend">
        ${row.count_high      ? `<span class="lg" style="color:${RISK_META.high.color}">${row.count_high} high</span>` : ''}
        ${row.count_medium    ? `<span class="lg" style="color:${RISK_META.medium.color}">${row.count_medium} med</span>` : ''}
        ${row.count_opportunity ? `<span class="lg" style="color:${RISK_META.opportunity.color}">${row.count_opportunity} opp</span>` : ''}
      </div>
    `;
  }

  function rowHtml(row) {
    const expanded = state.expanded.has(row.id);
    return `
      <tr class="r-main hover:bg-slate-50 dark:hover:bg-slate-700/30 cursor-pointer" data-id="${row.id}">
        <td class="px-4 py-3 whitespace-nowrap text-slate-500 dark:text-slate-400">${formatDate(row.created_at)}</td>
        <td class="px-4 py-3 whitespace-nowrap">
          <div class="font-semibold">${escapeHtml(row.sender_name || row.sender_address || '—')}</div>
          <div class="text-[11px] text-slate-500 dark:text-slate-400">${escapeHtml(row.sender_address || '')}</div>
        </td>
        <td class="px-4 py-3 max-w-md">
          <div class="font-medium truncate" title="${escapeHtml(row.subject || '')}">${escapeHtml(row.subject || '(no subject)')}</div>
          <div class="text-[11px] text-slate-500 dark:text-slate-400 truncate font-mono">📎 ${escapeHtml(row.filename)}</div>
        </td>
        <td class="px-4 py-3 text-right font-mono font-bold text-zk-navy dark:text-zk-gold">${row.total_clauses}</td>
        <td class="px-4 py-3 min-w-[220px]">
          ${riskBars(row)}
        </td>
        <td class="px-4 py-3 text-right whitespace-nowrap">
          <a href="/api/recent/${row.id}/report" target="_blank" class="action-btn" title="Download PDF report" onclick="event.stopPropagation();">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3M5 20h14a2 2 0 002-2V8.5L13.5 2H6a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>
          </a>
          <button class="action-btn" data-toggle="${row.id}" title="${expanded ? 'Collapse' : 'Expand'} details">
            <svg class="w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </button>
        </td>
      </tr>
      ${expanded ? detailRowHtml(row) : ''}
    `;
  }

  function detailRowHtml(row) {
    return `
      <tr class="r-detail bg-slate-50 dark:bg-slate-900/40">
        <td colspan="6" class="px-4 py-4" id="detail-${row.id}">
          <div class="text-center py-4 text-slate-400 text-sm">Loading clauses…</div>
        </td>
      </tr>
    `;
  }

  function clauseCardHtml(c) {
    const meta = RISK_META[c.risk_level] || RISK_META.low;
    return `
      <div class="r-clause" data-risk="${c.risk_level}">
        <div class="r-clause-head">
          <span class="risk-pill ${c.risk_level}">${meta.icon} ${meta.label}</span>
          <span class="text-[11px] text-slate-500 font-mono ml-2">conf ${c.confidence}% · ${escapeHtml(c.clause_type || '—')}</span>
        </div>
        <p class="clause-text mt-2">${escapeHtml(c.clause)}</p>
        ${c.interpretation ? `<div class="mt-2"><span class="section-label">Interpretation</span><p class="clause-text">${escapeHtml(c.interpretation)}</p></div>` : ''}
        ${c.suggested_rewrite && c.suggested_rewrite !== c.clause ? `
          <div class="mt-2"><span class="section-label">Suggested rewrite</span>
            <div class="rewrite-text">${escapeHtml(c.suggested_rewrite)}</div>
          </div>` : ''}
      </div>
    `;
  }

  async function loadDetail(id) {
    const target = $(`#detail-${id}`);
    if (!target) return;
    try {
      const r = await fetch(`/api/recent/${id}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const results = data.results || [];
      const order = { high: 0, medium: 1, opportunity: 2, low: 3, neutral: 4 };
      const sorted = [...results].sort((a, b) => (order[a.risk_level] ?? 9) - (order[b.risk_level] ?? 9));
      const kw = (data.matched_keywords || []).slice(0, 10);
      target.innerHTML = `
        <div class="grid lg:grid-cols-3 gap-4 mb-3">
          <div class="r-meta">
            <div class="section-label">Email message</div>
            <p class="text-sm"><strong>${escapeHtml(data.sender_name || '')}</strong></p>
            <p class="text-[11px] text-slate-500 break-all">${escapeHtml(data.sender_address || '')}</p>
            ${data.message_id ? `<p class="text-[10px] text-slate-400 font-mono mt-1 break-all">${escapeHtml(data.message_id)}</p>` : ''}
          </div>
          <div class="r-meta">
            <div class="section-label">Attachment</div>
            <p class="text-sm font-mono">📎 ${escapeHtml(data.filename)}</p>
            <p class="text-[11px] text-slate-500">${(data.size_bytes / 1024).toFixed(1)} KB · ${data.keyword_hits} keyword hit${data.keyword_hits === 1 ? '' : 's'}</p>
          </div>
          <div class="r-meta">
            <div class="section-label">Matched keywords</div>
            <div class="mt-1">${kw.map(k => `<span class="kw-chip">${escapeHtml(k.replace(/_/g, ' '))}</span>`).join('')}</div>
          </div>
        </div>
        <div class="section-label mb-2">Clauses (${results.length}) · sorted by risk</div>
        <div class="grid gap-2 max-h-[60vh] overflow-y-auto pr-2">
          ${sorted.map(clauseCardHtml).join('') || '<p class="text-sm text-slate-400">No clauses recorded.</p>'}
        </div>
      `;
    } catch (e) {
      target.innerHTML = `<p class="text-red-500 text-sm">Failed to load detail: ${escapeHtml(e.message)}</p>`;
    }
  }

  function renderTable() {
    if (state.items.length === 0) {
      $('#empty-state').classList.remove('hidden');
      $('#results-wrap').classList.add('hidden');
      return;
    }
    $('#empty-state').classList.add('hidden');
    $('#results-wrap').classList.remove('hidden');
    $('#rows').innerHTML = state.items.map(rowHtml).join('');

    // Click handlers
    $$('#rows tr.r-main').forEach(tr => {
      tr.addEventListener('click', () => toggleDetail(tr.dataset.id));
    });
    $$('#rows button[data-toggle]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDetail(btn.dataset.toggle);
      });
    });

    // Hydrate any expanded detail rows
    state.expanded.forEach(id => {
      if (state.items.some(it => it.id === id)) loadDetail(id);
    });
  }

  function toggleDetail(id) {
    if (state.expanded.has(id)) state.expanded.delete(id);
    else state.expanded.add(id);
    renderTable();
  }

  function renderPagination() {
    const from = state.total === 0 ? 0 : state.offset + 1;
    const to = Math.min(state.offset + state.limit, state.total);
    $('#page-from').textContent = from;
    $('#page-to').textContent = to;
    $('#page-total').textContent = state.total;
    $('#prev-btn').disabled = state.offset === 0;
    $('#next-btn').disabled = state.offset + state.limit >= state.total;
  }

  let toastTimer;
  function toast(msg, isError = false) {
    const el = $('#toast');
    el.textContent = msg;
    el.style.background = isError ? '#dc2626' : '#0f172a';
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
  }

  // Initial load + auto-refresh every 30s
  load();
  setInterval(load, 30000);
})();
