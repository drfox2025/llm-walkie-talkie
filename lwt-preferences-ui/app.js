// app.js — LWT Control Panel v3
// Orange × Black Flat Design | Bilingual Vietnamese/English

document.addEventListener('DOMContentLoaded', () => {

  // ── VS Code API Bridge ──────────────────────────────────────────────────
  const vscodeApi = (typeof acquireVsCodeApi !== 'undefined') ? acquireVsCodeApi() : null;

  // ── postMessage origin validation (security) ─────────────────────────────
  window.addEventListener('message', (event) => {
    if (event.origin && !event.origin.startsWith('vscode-webview://') && event.origin !== 'null') return;
    if (event.data && event.data.type === 'lwt-config-update') {
      if (event.data.keys) updateKeyStatusDisplay(event.data.keys);
    }
  });

  // ── Provider prefix auto-detect map ─────────────────────────────────────
  const PREFIX_MAP = [
    { prefix: 'nvapi-',  provider: 'NVIDIA',     label: '→ NVIDIA NIM' },
    { prefix: 'sk-or-',  provider: 'OPENROUTER', label: '→ OpenRouter' },
    { prefix: 'sk-ai-',  provider: 'ZENMUX',     label: '→ ZenMux' },
    { prefix: 'AIzaSy',  provider: 'GEMINI',     label: '→ Google Gemini' },
    { prefix: 'gsk_',    provider: 'GROQ',       label: '→ Groq' },
    { prefix: 'sk-ant-', provider: 'ANTHROPIC',  label: '→ Anthropic' },
    { prefix: 'sk-',     provider: 'OPENAI',     label: '→ OpenAI' },
  ];

  function detectProvider(keyVal) {
    for (const p of PREFIX_MAP) {
      if (keyVal.startsWith(p.prefix)) return p;
    }
    return null;
  }

  // 4-char masked prefix: first 4 chars of key + ••••
  function maskKey(key) {
    if (!key || key.length < 4) return '••••';
    return key.slice(0, 4) + '••••';
  }

  // ── Per-key API state array ───────────────────────────────────────────────
  // { id, provider, maskedPrefix, label, status, lastUsed, tokensToday, tokensMonth, lastError, errorReason, configuredAt }
  let apiKeyEntries = [
    { id: 'nvidia-1',          provider: 'NVIDIA',          maskedPrefix: 'nvap****', label: 'NVIDIA NIM Key',         status: 'active', lastUsed: '2h ago', tokensToday: 14320, tokensMonth: 341200, lastError: null,               errorReason: null,              configuredAt: '2026-07-13' },
    { id: 'nvidia_deepseek-1', provider: 'NVIDIA_DEEPSEEK', maskedPrefix: 'nvap****', label: 'NVIDIA DeepSeek Key',    status: 'dead',   lastUsed: 'Never',  tokensToday: 0,     tokensMonth: 0,      lastError: '2026-07-14 10:00', errorReason: 'Key expired',     configuredAt: '2026-07-13' },
    { id: 'openrouter-1',      provider: 'OPENROUTER',      maskedPrefix: 'sk-or****', label: 'OpenRouter Key',         status: 'active', lastUsed: '4h ago', tokensToday: 4200,  tokensMonth: 128500, lastError: null,               errorReason: null,              configuredAt: '2026-07-12' },
    { id: 'zenmux-1',          provider: 'ZENMUX',          maskedPrefix: 'sk-ai****', label: 'ZenMux GLM Key',        status: 'dead',   lastUsed: '2d ago', tokensToday: 0,     tokensMonth: 4500,   lastError: '2026-07-13 09:15', errorReason: '401 Unauthorized', configuredAt: '2026-07-10' },
    { id: 'gemini-1',          provider: 'GEMINI',          maskedPrefix: 'AIza****', label: 'Google Gemini Key',      status: 'dead',   lastUsed: '1d ago', tokensToday: 0,     tokensMonth: 12000,  lastError: '2026-07-14 17:40', errorReason: 'Quota exceeded',  configuredAt: '2026-07-11' },
    { id: 'groq-1',            provider: 'GROQ',            maskedPrefix: 'gsk_****', label: 'Groq Llama Key',         status: 'dead',   lastUsed: '3d ago', tokensToday: 0,     tokensMonth: 0,      lastError: '2026-07-12 12:00', errorReason: 'No key configured', configuredAt: null },
    { id: 'openai-1',          provider: 'OPENAI',          maskedPrefix: 'sk-****',   label: 'OpenAI Key',             status: 'dead',   lastUsed: 'Never',  tokensToday: 0,     tokensMonth: 0,      lastError: '2026-07-11 12:00', errorReason: 'No key configured', configuredAt: null },
    { id: 'anthropic-1',       provider: 'ANTHROPIC',       maskedPrefix: 'sk-an****', label: 'Anthropic Key',          status: 'dead',   lastUsed: 'Never',  tokensToday: 0,     tokensMonth: 0,      lastError: '2026-07-10 12:00', errorReason: 'No key configured', configuredAt: null }
  ];

  const providerTagClass = {
    NVIDIA: 'tag-nvidia', NVIDIA_DEEPSEEK: 'tag-nvidia-ds', OPENROUTER: 'tag-openrouter', ZENMUX: 'tag-zenmux',
    GROQ: 'tag-groq', GEMINI: 'tag-gemini', OPENAI: 'tag-openai', ANTHROPIC: 'tag-anthropic'
  };

  // Generate 30 days of mock token histories per API provider for last 30 days monitoring
  const providerTokenHistory = {};
  const providerErrorHistory = {};
  const providerCallHistory = {};

  const providersList = ['NVIDIA', 'NVIDIA_DEEPSEEK', 'OPENROUTER', 'ZENMUX', 'GEMINI', 'GROQ', 'OPENAI', 'ANTHROPIC'];

  const init30DayHistories = () => {
    providersList.forEach(p => {
      providerTokenHistory[p] = [];
      providerErrorHistory[p] = [];
      providerCallHistory[p] = [];
      for (let i = 0; i < 30; i++) {
        let val = 0;
        let errs = 0;
        let calls = 0;
        if (p === 'NVIDIA') {
          val = Math.floor(Math.random() * 15000) + 5000;
          errs = Math.random() > 0.85 ? Math.floor(Math.random() * 8) : 0;
        } else if (p === 'OPENROUTER') {
          val = Math.floor(Math.random() * 5000) + 1500;
          errs = Math.random() > 0.95 ? 1 : 0;
        } else if (p === 'ZENMUX') {
          val = i < 5 ? Math.floor(Math.random() * 1000) + 200 : 0;
          errs = i < 5 ? Math.floor(Math.random() * 30) + 15 : 0;
        } else if (p === 'GEMINI') {
          val = i < 10 ? Math.floor(Math.random() * 2000) + 500 : 0;
          errs = i < 10 ? Math.floor(Math.random() * 10) + 5 : 0;
        } else if (p === 'NVIDIA_DEEPSEEK') {
          val = 0;
          errs = Math.random() > 0.8 ? Math.floor(Math.random() * 4) : 0;
        }
        calls = val > 0 ? Math.floor(val / 800) + 1 : 0;
        providerTokenHistory[p].push(val);
        providerErrorHistory[p].push(errs);
        providerCallHistory[p].push(calls);
      }
    });
  };
  init30DayHistories();

  // Generate 30 days of mock token spending logs for main chart
  let tokenSpentHistory = [];
  const initMockHistory = () => {
    const today = new Date();
    for (let i = 29; i >= 0; i--) {
      const d = new Date(today); d.setDate(today.getDate() - i);
      const dateStr = `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
      const hasError = Math.random() > 0.85;
      tokenSpentHistory.push({
        date: dateStr,
        tokens: Math.floor(Math.random() * 22000) + 3000,
        errors: hasError ? (Math.random() > 0.5 ? Math.floor(Math.random() * 32) + 5 : Math.floor(Math.random() * 10)) : 0,
        calls: Math.floor(Math.random() * 15) + 3
      });
    }
  };
  initMockHistory();

  // Active API selection for main token chart monitoring
  let monitoredApis = ['NVIDIA', 'OPENROUTER'];

  // User preferences state (default values)
  const preferencesState = {
    theme: 'dark', lang: 'python', budgetAlert: 5.0, sound: true, autosave: false,
    monitorCadence: 'daily', dailyTime: '19:00', dailyTokenBudget: 500000, dailyCostCap: 5.0,
    dailyTokenNoCap: false, dailyCostNoCap: false,
    costPerProvider: { NVIDIA: 0, OPENROUTER: 0, ZENMUX: 0, GROQ: 0 }
  };

  // ── Nav Tab Switching ────────────────────────────────────────────────────
  const navTabs    = document.querySelectorAll('.cp-nav-tab');
  const sections   = document.querySelectorAll('.cp-section');

  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      navTabs.forEach(t => t.classList.remove('active'));
      sections.forEach(s => s.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById('section-' + tab.dataset.section);
      if (target) target.classList.add('active');
    });
  });

  // ── Slider live labels ──────────────────────────────────────────────────
  function bindSlider(sliderId, valId, formatter) {
    const slider = document.getElementById(sliderId);
    const label  = document.getElementById(valId);
    if (!slider || !label) return;
    const update = () => { label.textContent = formatter ? formatter(+slider.value) : slider.value; };
    slider.addEventListener('input', update);
    update();
  }

  bindSlider('consult-retries',        'val-consult-retries',    v => v);
  bindSlider('consult-cache-ttl',      'val-consult-cache-ttl',  v => `${v} hours [giờ]`);
  bindSlider('consult-timeout',        'val-consult-timeout',    v => `${v}s`);
  bindSlider('consult-ctx-buf',        'val-consult-ctx-buf',    v => v);
  bindSlider('loop-max-iter',          'val-loop-max-iter',      v => v);
  bindSlider('loop-cost-cap',          'val-loop-cost-cap',      v => `$${parseFloat(v).toFixed(2)}`);
  bindSlider('loop-iter-timeout',      'val-loop-iter-timeout',  v => `${v}s`);
  bindSlider('loop-token-budget-role', 'val-loop-token-budget-role', v => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v);
  bindSlider('loop-oscillation-window','val-loop-oscillation-window', v => v);
  bindSlider('loop-oscillation-threshold','val-loop-oscillation-threshold', v => `${v}%`);
  bindSlider('loop-sandbox-timeout',   'val-loop-sandbox-timeout',   v => `${v}s`);
  bindSlider('loop-min-audit-score',   'val-loop-min-audit-score',   v => `${v} / 10`);
  bindSlider('routing-discovery-interval', 'val-routing-discovery', v => `${v} hours [giờ]`);
  bindSlider('routing-health-ttl',    'val-routing-health-ttl', v => `${v}s`);
  bindSlider('routing-ewma-alpha',    'val-routing-ewma-alpha',    v => `${(v/100).toFixed(2)}`);
  bindSlider('routing-ewma-min-samples','val-routing-ewma-min-samples', v => v);
  bindSlider('routing-failover-threshold','val-routing-failover-threshold', v => v);
  bindSlider('routing-health-interval','val-routing-health-interval', v => `${v}s`);
  bindSlider('routing-health-timeout', 'val-routing-health-timeout', v => `${v}s`);
  bindSlider('flag-session-turns',    'val-flag-session-turns',  v => v);
  bindSlider('flag-diff-cap',         'val-flag-diff-cap',       v => v);
  bindSlider('pref-budget-alert',     'val-pref-budget-alert',   v => `$${parseFloat(v).toFixed(2)}`);
  bindSlider('pref-daily-token-budget','val-pref-daily-token-budget', v => v >= 1000000 ? `${(v/1000000).toFixed(1)}M` : `${(v/1000).toFixed(0)}K`);
  bindSlider('pref-daily-cost-cap',   'val-pref-daily-cost-cap', v => `$${parseFloat(v).toFixed(2)}`);

  // ── Toggle label update ─────────────────────────────────────────────────
  function bindToggle(checkboxId) {
    const cb   = document.getElementById(checkboxId);
    const lbl  = cb ? cb.closest('.cp-toggle').querySelector('.toggle-label') : null;
    if (!cb || !lbl) return;
    const update = () => {
      lbl.innerHTML = cb.checked
        ? 'Enabled <span class="vi">[Bật]</span>'
        : 'Disabled <span class="vi">[Tắt]</span>';
      
      if (checkboxId !== 'pref-autosave' && preferencesState.autosave) {
        doSaveSilent();
      }
    };
    cb.addEventListener('change', update);
    update();
  }

  ['consult-experience','consult-design-contract',
   'loop-sandbox','loop-oscillation','loop-token-report',
   'routing-failover','routing-spof-warn',
   'flag-allow-absolute','flag-debug','flag-stream',
   'flag-mask-keys','flag-atomic','flag-evolve-backup',
   'pref-sound', 'pref-autosave'].forEach(id => bindToggle(id));

  // Auto-save setup
  document.querySelectorAll('.cp-input, .cp-slider').forEach(input => {
    input.addEventListener('change', () => {
      if (preferencesState.autosave) {
        doSaveSilent();
      }
    });
  });

  document.getElementById('pref-theme')?.addEventListener('change', (e) => {
    preferencesState.theme = e.target.value;
    applyTheme(preferencesState.theme);
  });
  document.getElementById('pref-lang')?.addEventListener('input', (e) => {
    preferencesState.lang = e.target.value.trim();
  });
  document.getElementById('pref-budget-alert')?.addEventListener('input', (e) => {
    preferencesState.budgetAlert = parseFloat(e.target.value);
  });
  document.getElementById('pref-sound')?.addEventListener('change', (e) => {
    preferencesState.sound = e.target.checked;
  });
  document.getElementById('pref-autosave')?.addEventListener('change', (e) => {
    preferencesState.autosave = e.target.checked;
  });

  function applyTheme(theme) {
    if (theme === 'cyberpunk') {
      document.documentElement.style.setProperty('--black-0', '#05020a');
      document.documentElement.style.setProperty('--black-1', '#0d0714');
      document.documentElement.style.setProperty('--black-2', '#150a21');
      document.documentElement.style.setProperty('--black-3', '#220f35');
      document.documentElement.style.setProperty('--orange', '#00ffcc');
      document.documentElement.style.setProperty('--orange-dim', '#00ccaa');
      document.documentElement.style.setProperty('--border', 'rgba(0, 255, 204, 0.2)');
    } else {
      document.documentElement.style.setProperty('--black-0', '#0a0a0a');
      document.documentElement.style.setProperty('--black-1', '#111111');
      document.documentElement.style.setProperty('--black-2', '#181818');
      document.documentElement.style.setProperty('--black-3', '#202020');
      document.documentElement.style.setProperty('--orange', '#ff6b00');
      document.documentElement.style.setProperty('--orange-dim', '#cc5500');
      document.documentElement.style.setProperty('--border', 'rgba(255, 107, 0, 0.15)');
    }
  }

  // ── Render per-key API cards (Active | Dead Vault) ─────────────────────────────
  const activeContainer = document.getElementById('active-api-container');
  const deadContainer   = document.getElementById('dead-api-container');

  function errorTier(errors, calls) {
    const rate = calls > 0 ? (errors / calls) * 10 : 0;
    if (errors >= 30 || rate >= 5) return 'critical';
    if (errors >= 15 || rate >= 3) return 'warn';
    return 'ok';
  }

  function buildMiniChart(provider) {
    const tokens = providerTokenHistory[provider] || Array(30).fill(0);
    const errors = providerErrorHistory[provider] || Array(30).fill(0);
    const calls  = providerCallHistory[provider]  || Array(30).fill(1);
    const maxT   = Math.max(...tokens, 1);
    const today  = new Date();
    const labels = Array.from({ length: 30 }, (_, i) => {
      const d = new Date(today); d.setDate(today.getDate() - (29 - i));
      return `${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    });
    const bars = tokens.map((t, i) => {
      const h = Math.max(2, Math.round((t / maxT) * 100));
      const tier = errorTier(errors[i], calls[i]);
      const tierCls = tier === 'critical' ? 'err-critical' : tier === 'warn' ? 'err-warn' : '';
      const tip = `${labels[i]}: ${t.toLocaleString()} tokens${tier !== 'ok' ? ' | ⚡ ' + errors[i] + ' errors' : ''}`;
      return `<div class="mini-bar ${tierCls}" style="height:${h}%" data-tooltip="${tip}"></div>`;
    }).join('');
    return `<div class="api-card-mini-chart">
      <div class="mini-chart-bars">${bars}</div>
      <div class="mini-chart-label"><span>${labels[0]}</span><span style="color:var(--orange);">30-day tokens</span><span>${labels[29]}</span></div>
    </div>`;
  }

  function renderApiCards() {
    if (!activeContainer || !deadContainer) return;
    activeContainer.innerHTML = '';
    deadContainer.innerHTML = '';
    const activeEntries = apiKeyEntries.filter(e => e.status === 'active');
    const deadEntries   = apiKeyEntries.filter(e => e.status !== 'active').slice(0, 5);

    activeEntries.forEach(entry => {
      const tagCls = providerTagClass[entry.provider] || 'tag-zenmux';
      const tokK   = entry.tokensToday >= 1000 ? `${(entry.tokensToday/1000).toFixed(1)}K` : entry.tokensToday;
      const tokM   = entry.tokensMonth >= 1000 ? `${(entry.tokensMonth/1000).toFixed(0)}K` : entry.tokensMonth;
      const card = document.createElement('div');
      card.className = 'api-key-card'; card.id = `card-${entry.id}`; card.draggable = true;
      card.setAttribute('data-id', entry.id);
      card.innerHTML = `
        <div class="api-card-header">
          <div class="api-card-left">
            <span class="drag-handle" style="color:var(--text-dim);cursor:grab;">&#x2823;</span>
            <span class="provider-tag ${tagCls}">${entry.provider}</span>
            <span class="api-card-name">${entry.label}</span>
            <span class="api-card-prefix">${entry.maskedPrefix}</span>
          </div>
          <div class="api-card-actions"><span class="api-card-stat ok">&#9679; Active</span></div>
        </div>
        <div class="api-card-meta">
          <span class="api-card-stat">&#128336; Last used: ${entry.lastUsed}</span>
          <span class="api-card-stat">&#128202; Today: ${tokK} tokens</span>
          <span class="api-card-stat" style="color:#22c55e;font-weight:500;">&#128198; Monthly: ${tokM} spent</span>
          <span class="api-card-stat" style="color:var(--text-dim);">Since ${entry.configuredAt || 'unknown'}</span>
        </div>
        ${buildMiniChart(entry.provider)}`;
      activeContainer.appendChild(card);
    });
    if (activeEntries.length === 0)
      activeContainer.innerHTML = '<div style="color:var(--text-dim);font-size:11px;padding:12px;">No active APIs yet — add a key below.</div>';

    deadEntries.forEach(entry => {
      const tagCls = providerTagClass[entry.provider] || 'tag-zenmux';
      const card = document.createElement('div');
      card.className = 'api-key-card dead-card'; card.id = `card-dead-${entry.id}`;
      card.innerHTML = `
        <div class="api-card-header">
          <div class="api-card-left">
            <span class="provider-tag ${tagCls}">${entry.provider}</span>
            <span class="api-card-name">${entry.label}</span>
            <span class="api-card-prefix" style="color:var(--text-dim);">${entry.maskedPrefix || '—'}</span>
            ${entry.errorReason ? `<span class="error-reason-badge">${entry.errorReason}</span>` : ''}
          </div>
          <div class="api-card-actions">
            <button class="cp-btn cp-btn-ghost" style="font-size:10px;padding:4px 10px;" onclick="triggerReconfig('${entry.id}')">
              &#128295; Re-configure <span class="vi">[Cấu hình lại]</span>
            </button>
          </div>
        </div>
        <div class="api-card-meta">
          ${entry.lastError ? `<span class="api-card-stat err">&#9888; Last error: ${entry.lastError}</span>` : '<span class="api-card-stat" style="color:var(--text-dim);">No key configured</span>'}
        </div>`;
      deadContainer.appendChild(card);
    });
    if (deadEntries.length === 0)
      deadContainer.innerHTML = '<div style="color:var(--text-dim);font-size:11px;padding:12px;">All APIs healthy ✓</div>';

    bindCardDragging();
    updateFooterKeyCount();
  }

  window.triggerReconfig = function(entryId) {
    const entry = apiKeyEntries.find(e => e.id === entryId);
    if (!entry) return;
    const modal = document.getElementById('custom-key-modal');
    const provInput = document.getElementById('custom-key-provider');
    if (modal) { modal.classList.remove('hidden'); modal.style.display = 'flex'; }
    if (provInput) provInput.value = entry.provider;
  };

  function updateKeyStatusDisplay(keysPayload) {
    if (!keysPayload) return;
    keysPayload.forEach(k => {
      const entry = apiKeyEntries.find(e => e.id === k.id);
      if (entry) { entry.status = k.status; entry.maskedPrefix = k.maskedPrefix || entry.maskedPrefix; }
    });
    renderApiCards();
  }

  function updateFooterKeyCount() {
    const el = document.getElementById('footer-key-count');
    if (el) el.textContent = apiKeyEntries.filter(e => e.status === 'active').length;
  }

  let dragCard = null;
  if (activeContainer) {
    activeContainer.addEventListener('dragover', e => {
      e.preventDefault(); if (!dragCard) return;
      const afterEl = getDragAfterElement(activeContainer, e.clientY);
      if (afterEl == null) activeContainer.appendChild(dragCard);
      else activeContainer.insertBefore(dragCard, afterEl);
    });
  }

  function bindCardDragging() {
    const activeCards = activeContainer.querySelectorAll('.api-key-card');
    activeCards.forEach(card => {
      card.addEventListener('dragstart', e => { dragCard = card; card.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; });
      card.addEventListener('dragend', () => { card.classList.remove('dragging'); dragCard = null; if (preferencesState.autosave) doSaveSilent(); });
    });
  }

  function getDragAfterElement(container, y) {
    const items = [...container.querySelectorAll('.api-key-card:not(.dragging)')];
    return items.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      return (offset < 0 && offset > closest.offset) ? { offset, element: child } : closest;
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }

  // ── Add Key Modal (provider auto-detect) ───────────────────────────────────────
  const addCustomBtn    = document.getElementById('btn-add-custom-key');
  const customModal     = document.getElementById('custom-key-modal');
  const cancelCustomBtn = document.getElementById('btn-cancel-custom-key');
  const saveCustomBtn   = document.getElementById('btn-save-custom-key');
  const keyValueInput   = document.getElementById('custom-key-value');
  const providerInput   = document.getElementById('custom-key-provider');
  const detectHint      = document.getElementById('provider-detect-hint');

  if (keyValueInput) {
    keyValueInput.addEventListener('input', () => {
      const val = keyValueInput.value.trim();
      const detected = detectProvider(val);
      if (detected) {
        if (detectHint) detectHint.textContent = detected.label;
        if (providerInput && !providerInput._userEdited) providerInput.value = detected.provider;
      } else {
        if (detectHint) detectHint.textContent = val.length >= 3 ? '? Unknown prefix — fill in provider manually' : '';
      }
    });
  }
  if (providerInput) providerInput.addEventListener('input', () => { providerInput._userEdited = true; });

  if (addCustomBtn && customModal) {
    addCustomBtn.addEventListener('click', () => {
      customModal.classList.remove('hidden'); customModal.style.display = 'flex';
      if (providerInput) { providerInput.value = ''; providerInput._userEdited = false; }
      if (keyValueInput) keyValueInput.value = '';
      if (detectHint) detectHint.textContent = '';
    });
  }
  if (cancelCustomBtn) cancelCustomBtn.addEventListener('click', () => { customModal.classList.add('hidden'); customModal.style.display = 'none'; });

  if (saveCustomBtn) {
    saveCustomBtn.addEventListener('click', () => {
      const providerName = providerInput ? providerInput.value.trim().toUpperCase() : '';
      const keyValue     = keyValueInput  ? keyValueInput.value.trim() : '';
      const labelVal     = (document.getElementById('custom-key-label')?.value || '').trim();
      if (!providerName || !keyValue) { alert('Please enter both a key and provider.'); return; }
      // SECURITY: raw key is never stored in DOM or JS state — send to extension host only
      const masked = maskKey(keyValue);
      const newEntry = {
        id: `${providerName.toLowerCase()}-${Date.now()}`, provider: providerName, maskedPrefix: masked,
        label: labelVal || `${providerName} Key`, status: 'active', lastUsed: 'just now', tokensToday: 0,
        lastError: null, errorReason: null, configuredAt: new Date().toISOString().slice(0, 10)
      };
      if (vscodeApi) vscodeApi.postMessage({ type: 'lwt-store-key', provider: providerName, key: keyValue });
      apiKeyEntries.unshift(newEntry);
      customModal.classList.add('hidden'); customModal.style.display = 'none';
      renderApiCards(); updateStatusPill();
      if (preferencesState.autosave) doSaveSilent();
    });
  }

  // ── Key status / Status Pill ──────────────────────────────────────────────
  function updateStatusPill() {
    const count = apiKeyEntries.filter(e => e.status === 'active').length;
    const dot   = document.getElementById('status-dot');
    const label = document.getElementById('status-label');
    if (!dot || !label) return;
    if (count === 0) {
      dot.className = 'status-dot err';
      label.innerHTML = `0 providers · Run: walkie quickstart <span class="vi">[0 nhà cung cấp]</span>`;
    } else if (count < 3) {
      dot.className = 'status-dot warn';
      label.innerHTML = `${count} key${count>1?'s':''} · Need ≥3 for llm-loop <span class="vi">[Cần ≥3 cho llm-loop]</span>`;
    } else {
      dot.className = 'status-dot ok';
      label.innerHTML = `${count} providers configured <span class="vi">[${count} nhà cung cấp]</span>`;
    }
  }
  
  // ── Token monitor (3-tier) with active API filtering ─────────────────────
  const chartContainer = document.getElementById('token-chart-bars');
  
  function renderTokenSpentMonitor() {
    if (!chartContainer) return;
    chartContainer.innerHTML = '';

    const hasFilter = monitoredApis.length > 0;

    // Map token history based on selected APIs from filter
    const currentHistory = tokenSpentHistory.map((day, idx) => {
      let totalTokens = 0;
      let totalErrors = 0;
      let totalCalls = 0;
      if (hasFilter) {
        monitoredApis.forEach(api => {
          totalTokens += providerTokenHistory[api] ? providerTokenHistory[api][idx] : 0;
          totalErrors += providerErrorHistory[api] ? providerErrorHistory[api][idx] : 0;
          totalCalls += providerCallHistory[api] ? providerCallHistory[api][idx] : 0;
        });
      }
      return {
        date: day.date,
        tokens: totalTokens,
        errors: totalErrors,
        calls: totalCalls
      };
    });

    const maxVal = Math.max(...currentHistory.map(h => h.tokens), 1000);
    currentHistory.forEach((day, idx) => {
      const bar = document.createElement('div'); bar.className = 'token-bar';
      bar.style.height = `${Math.max(3, (day.tokens / maxVal) * 100)}%`;
      
      let apiBreakdowns = [];
      monitoredApis.forEach(api => {
        const amt = providerTokenHistory[api] ? providerTokenHistory[api][idx] : 0;
        if (amt > 0) {
          apiBreakdowns.push(`${api}: ${amt.toLocaleString()}`);
        }
      });
      const breakdownStr = apiBreakdowns.length > 0 ? ` (${apiBreakdowns.join(' | ')})` : '';
      bar.setAttribute('data-tooltip', `${day.date}: ${day.tokens.toLocaleString()} tokens${breakdownStr}`);
      
      const rate = day.calls > 0 ? (day.errors / day.calls) * 10 : 0;
      if (day.errors >= 30 || rate >= 5) bar.classList.add('err-critical');
      else if (day.errors >= 15 || rate >= 3) bar.classList.add('err-warn');
      chartContainer.appendChild(bar);
    });
  }

  // Active API Multiselect Dropdown Population
  function populateMonitorFilter() {
    const listContainer = document.getElementById('monitor-api-dropdown-list');
    if (!listContainer) return;
    listContainer.innerHTML = '';
    
    const activeApis = [...new Set(apiKeyEntries.filter(e => e.status === 'active').map(e => e.provider))];
    
    if (activeApis.length === 0) {
      listContainer.innerHTML = '<span style="color:var(--text-dim);font-size:10px;padding:4px;">No active APIs</span>';
      document.getElementById('monitor-api-selected-text').textContent = 'No active APIs';
      return;
    }
    
    activeApis.forEach(provider => {
      const label = document.createElement('label');
      label.style.cssText = 'display:flex;align-items:center;gap:6px;font-size:11px;cursor:pointer;color:var(--text);padding:4px;';
      
      const isChecked = monitoredApis.includes(provider);
      label.innerHTML = `
        <input type="checkbox" value="${provider}" ${isChecked ? 'checked' : ''} style="cursor:pointer;">
        <span>${provider}</span>
      `;
      
      label.querySelector('input').addEventListener('change', (e) => {
        if (e.target.checked) {
          if (!monitoredApis.includes(provider)) monitoredApis.push(provider);
        } else {
          monitoredApis = monitoredApis.filter(p => p !== provider);
        }
        updateDropdownLabel();
        renderTokenSpentMonitor();
      });
      
      listContainer.appendChild(label);
    });
    
    updateDropdownLabel();
  }

  function updateDropdownLabel() {
    const labelText = document.getElementById('monitor-api-selected-text');
    if (!labelText) return;
    const activeCount = apiKeyEntries.filter(e => e.status === 'active').length;
    if (monitoredApis.length === 0) {
      labelText.textContent = 'None [Không chọn]';
    } else if (monitoredApis.length === activeCount) {
      labelText.textContent = 'All APIs [Tất cả]';
    } else {
      labelText.textContent = monitoredApis.join(', ');
    }
  }

  // Bind dropdown toggle
  const dropdownBtn = document.getElementById('monitor-api-dropdown-btn');
  const dropdownList = document.getElementById('monitor-api-dropdown-list');
  if (dropdownBtn && dropdownList) {
    dropdownBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isHidden = dropdownList.style.display === 'none' || dropdownList.style.display === '';
      dropdownList.style.display = isHidden ? 'flex' : 'none';
    });
    document.addEventListener('click', () => {
      if (dropdownList) dropdownList.style.display = 'none';
    });
    dropdownList.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  }

  // Setup No Cap Checkbox Logic for sliders
  function setupNoCapLogic() {
    const tokenBudgetSlider = document.getElementById('pref-daily-token-budget');
    const tokenNoCapCheckbox = document.getElementById('pref-daily-token-nocap');
    const tokenValLabel = document.getElementById('val-pref-daily-token-budget');
    
    const costCapSlider = document.getElementById('pref-daily-cost-cap');
    const costNoCapCheckbox = document.getElementById('pref-daily-cost-nocap');
    const costValLabel = document.getElementById('val-pref-daily-cost-cap');
    
    if (tokenBudgetSlider && tokenNoCapCheckbox && tokenValLabel) {
      const updateTokenState = () => {
        preferencesState.dailyTokenNoCap = tokenNoCapCheckbox.checked;
        if (tokenNoCapCheckbox.checked) {
          tokenBudgetSlider.disabled = true;
          tokenValLabel.textContent = 'No Cap [Không giới hạn]';
        } else {
          tokenBudgetSlider.disabled = false;
          const v = +tokenBudgetSlider.value;
          tokenValLabel.textContent = v >= 1000000 ? `${(v/1000000).toFixed(1)}M` : `${(v/1000).toFixed(0)}K`;
        }
        if (preferencesState.autosave) doSaveSilent();
      };
      tokenNoCapCheckbox.addEventListener('change', updateTokenState);
      tokenBudgetSlider.addEventListener('input', updateTokenState);
      updateTokenState();
    }
    
    if (costCapSlider && costNoCapCheckbox && costValLabel) {
      const updateCostState = () => {
        preferencesState.dailyCostNoCap = costNoCapCheckbox.checked;
        if (costNoCapCheckbox.checked) {
          costCapSlider.disabled = true;
          costValLabel.textContent = 'No Cap [Không giới hạn]';
        } else {
          costCapSlider.disabled = false;
          const v = +costCapSlider.value;
          costValLabel.textContent = `$${v.toFixed(2)}`;
        }
        if (preferencesState.autosave) doSaveSilent();
      };
      costNoCapCheckbox.addEventListener('change', updateCostState);
      costCapSlider.addEventListener('input', updateCostState);
      updateCostState();
    }
  }

  // Token update cadence: show/hide daily time row
  const cadenceSelect = document.getElementById('pref-monitor-cadence');
  const rowDailyTime  = document.getElementById('row-daily-time');
  if (cadenceSelect && rowDailyTime) {
    const updateCadenceVis = () => { rowDailyTime.style.display = cadenceSelect.value === 'daily' ? '' : 'none'; };
    cadenceSelect.addEventListener('change', updateCadenceVis);
    updateCadenceVis();
  }

  // Sync token spent updates daily at 7 PM local time
  function schedule7PMLocalUpdate() {
    const now = new Date();
    const updateTime = new Date();
    updateTime.setHours(19, 0, 0, 0);
    let timeUntilUpdate = updateTime.getTime() - now.getTime();
    if (timeUntilUpdate < 0) { updateTime.setDate(updateTime.getDate() + 1); timeUntilUpdate = updateTime.getTime() - now.getTime(); }
    setTimeout(() => {
      const todayStr = `${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
      const todayRecord = tokenSpentHistory.find(h => h.date === todayStr);
      if (todayRecord) { todayRecord.tokens += Math.floor(Math.random() * 5000); }
      else { tokenSpentHistory.shift(); tokenSpentHistory.push({ date: todayStr, tokens: Math.floor(Math.random() * 8000), errors: 0, calls: 0 }); }
      renderTokenSpentMonitor();
      schedule7PMLocalUpdate();
    }, timeUntilUpdate);
  }

  // ── Command preview (live update) ─────────────────────────────────────────
  function updateConsultPreview() {
    const model   = document.getElementById('consult-default-model')?.value || 'nvidia/z-ai/glm-5.2';
    const chain   = document.getElementById('consult-chain-model')?.value;
    const verify  = document.getElementById('consult-verify-model')?.value;
    const timeout = document.getElementById('consult-timeout')?.value || '90';
    let cmd = `walkie consult path/to/file.py --task "Mô tả tác vụ…" -m ${model}`;
    if (chain)  cmd += ` -c ${chain}`;
    if (verify) cmd += ` -V ${verify}`;
    cmd += ` --timeout ${timeout}`;
    const preview = document.getElementById('consult-cmd-preview');
    if (preview) preview.textContent = cmd;
  }

  function updateLoopPreview() {
    const gen     = document.getElementById('loop-gen-model')?.value || '<gen-model>';
    const audit   = document.getElementById('loop-audit-model')?.value || '<audit-model>';
    const red     = document.getElementById('loop-redteam-model')?.value || '<redteam-model>';
    const stop    = document.getElementById('loop-stop-cmd')?.value || 'pytest -q';
    const maxIter = document.getElementById('loop-max-iter')?.value || '15';
    const cost    = document.getElementById('loop-cost-cap')?.value || '2';
    const sess    = document.getElementById('loop-session-id')?.value || 'my-loop';
    const contract= document.getElementById('loop-contract-path')?.value || 'theme.contract.yaml';
    const preview = document.getElementById('loop-cmd-preview');
    if (preview) {
      preview.textContent = `walkie loop --goal "Mô tả mục tiêu…" --stop-cmd "${stop}" ` +
        `--gen-model ${gen} --audit-model ${audit} --redteam-model ${red} ` +
        `--max-iterations ${maxIter} --cost-cap-usd ${cost} ` +
        `--design-contract ${contract} --session ${sess}`;
    }
  }

  ['consult-default-model','consult-chain-model','consult-verify-model','consult-timeout']
    .forEach(id => document.getElementById(id)?.addEventListener('input', updateConsultPreview));

  ['loop-gen-model','loop-audit-model','loop-redteam-model','loop-stop-cmd',
   'loop-max-iter','loop-cost-cap','loop-session-id','loop-contract-path']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', updateLoopPreview);
    });

  document.getElementById('loop-max-iter')?.addEventListener('input', updateLoopPreview);
  document.getElementById('loop-cost-cap')?.addEventListener('input', updateLoopPreview);

  // ── Drag & Drop Priority ─────────────────────────────────────────────────
  const orderContainer = document.getElementById('order-container');
  let dragItem = null;

  if (orderContainer) {
    orderContainer.addEventListener('dragstart', e => {
      dragItem = e.target.closest('.order-item');
      if (dragItem) {
        dragItem.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
      }
    });

    orderContainer.addEventListener('dragend', () => {
      if (dragItem) {
        dragItem.classList.remove('dragging');
        dragItem = null;
      }
      updateRanks();
      if (preferencesState.autosave) doSaveSilent();
    });

    orderContainer.addEventListener('dragover', e => {
      e.preventDefault();
      const afterEl = getDragAfterElement(orderContainer, e.clientY);
      if (!dragItem) return;
      if (afterEl == null) {
        orderContainer.appendChild(dragItem);
      } else {
        orderContainer.insertBefore(dragItem, afterEl);
      }
    });
  }

  function updateRanks() {
    document.querySelectorAll('#order-container .order-item').forEach((item, i) => {
      const rankEl = item.querySelector('.order-rank');
      if (rankEl) rankEl.textContent = i + 1;
    });
  }

  // ── Load Settings from Extension ────────────────────────────────────────
  function loadSettings(data) {
    if (!data) return;

    // API Keys — extension host sends masked prefix only
    if (data.keys) {
      if (Array.isArray(data.keys)) {
        updateKeyStatusDisplay(data.keys);
      } else {
        Object.keys(data.keys).forEach(provider => {
          const entry = apiKeyEntries.find(e => e.provider === provider);
          if (entry) entry.status = data.keys[provider] ? 'active' : 'dead';
        });
        renderApiCards();
      }
    }

    // Consult params
    if (data.consultDefaultModel) setInputVal('consult-default-model', data.consultDefaultModel);
    if (data.consultChainModel)   setInputVal('consult-chain-model',   data.consultChainModel);
    if (data.consultVerifyModel)  setInputVal('consult-verify-model',  data.consultVerifyModel);
    if (data.consultRetries != null)  setSlider('consult-retries',   'val-consult-retries',   data.consultRetries,   v => v);
    if (data.consultTimeout != null)  setSlider('consult-timeout',   'val-consult-timeout',   data.consultTimeout,   v => `${v}s`);
    if (data.consultCacheTTL != null) setSlider('consult-cache-ttl', 'val-consult-cache-ttl', data.consultCacheTTL,  v => `${v} hours [giờ]`);
    if (data.consultCtxBuf != null)   setSlider('consult-ctx-buf',   'val-consult-ctx-buf',   data.consultCtxBuf,    v => v);

    setCheck('consult-experience',     data.consultExperience);
    setCheck('consult-design-contract', data.consultDesignContract);

    // Loop params
    if (data.loopGenModel)    setInputVal('loop-gen-model',      data.loopGenModel);
    if (data.loopAuditModel)  setInputVal('loop-audit-model',    data.loopAuditModel);
    if (data.loopRedteamModel) setInputVal('loop-redteam-model', data.loopRedteamModel);
    if (data.loopStopCmd)     setInputVal('loop-stop-cmd',       data.loopStopCmd);
    if (data.loopSessionId)   setInputVal('loop-session-id',     data.loopSessionId);
    if (data.loopContractPath) setInputVal('loop-contract-path', data.loopContractPath);
    if (data.loopMaxIter != null)     setSlider('loop-max-iter',     'val-loop-max-iter',     data.loopMaxIter,      v => v);
    if (data.loopCostCap != null)     setSlider('loop-cost-cap',     'val-loop-cost-cap',     data.loopCostCap,      v => `$${parseFloat(v).toFixed(2)}`);
    if (data.loopIterTimeout != null) setSlider('loop-iter-timeout', 'val-loop-iter-timeout', data.loopIterTimeout,  v => `${v}s`);

    setCheck('loop-sandbox',       data.loopSandbox);
    setCheck('loop-oscillation',   data.loopOscillation);
    setCheck('loop-token-report',  data.loopTokenReport);

    // Routing
    if (data.routingDiscoveryInterval != null) setSlider('routing-discovery-interval', 'val-routing-discovery', data.routingDiscoveryInterval, v => `${v} hours [giờ]`);
    if (data.routingHealthTTL != null) setSlider('routing-health-ttl', 'val-routing-health-ttl', data.routingHealthTTL, v => `${v}s`);
    setCheck('routing-failover',   data.routingFailover);
    setCheck('routing-spof-warn',  data.routingSpofWarn);

    // Flags
    setCheck('flag-allow-absolute', data.flagAllowAbsolute);
    setCheck('flag-debug',          data.flagDebug);
    setCheck('flag-stream',         data.flagStream);
    setCheck('flag-mask-keys',      data.flagMaskKeys);
    setCheck('flag-atomic',         data.flagAtomic);
    setCheck('flag-evolve-backup',  data.flagEvolveBackup);
    if (data.flagSessionTurns != null) setSlider('flag-session-turns', 'val-flag-session-turns', data.flagSessionTurns, v => v);
    if (data.flagDiffCap != null)      setSlider('flag-diff-cap',       'val-flag-diff-cap',       data.flagDiffCap,       v => v);

    // Preferences
    if (data.prefTheme) {
      setInputVal('pref-theme', data.prefTheme);
      preferencesState.theme = data.prefTheme;
      applyTheme(data.prefTheme);
    }
    if (data.prefLang) {
      setInputVal('pref-lang', data.prefLang);
      preferencesState.lang = data.prefLang;
    }
    if (data.prefBudgetAlert != null) {
      setSlider('pref-budget-alert', 'val-pref-budget-alert', data.prefBudgetAlert, v => `$${parseFloat(v).toFixed(2)}`);
      preferencesState.budgetAlert = data.prefBudgetAlert;
    }
    if (data.prefSound != null) {
      setCheck('pref-sound', data.prefSound);
      preferencesState.sound = data.prefSound;
    }
    if (data.prefAutosave != null) {
      setCheck('pref-autosave', data.prefAutosave);
      preferencesState.autosave = data.prefAutosave;
    }

    updateConsultPreview();
    updateLoopPreview();
  }

  function setInputVal(id, val) {
    const el = document.getElementById(id);
    if (el && val != null) el.value = val;
  }

  function setSlider(sliderId, valId, val, formatter) {
    const slider = document.getElementById(sliderId);
    const label  = document.getElementById(valId);
    if (slider && val != null) {
      slider.value = val;
      if (label) label.textContent = formatter ? formatter(+val) : val;
    }
  }

  function setCheck(id, val) {
    const cb = document.getElementById(id);
    if (cb && val != null) {
      cb.checked = !!val;
      cb.dispatchEvent(new Event('change'));
    }
  }

  // ── Collect current settings ─────────────────────────────────────────────
  function collectSettings() {
    return {
      consultDefaultModel:  getVal('consult-default-model'),
      consultChainModel:    getVal('consult-chain-model'),
      consultVerifyModel:   getVal('consult-verify-model'),
      consultRetries:       getNumVal('consult-retries'),
      consultTimeout:       getNumVal('consult-timeout'),
      consultCacheTTL:      getNumVal('consult-cache-ttl'),
      consultCtxBuf:        getNumVal('consult-ctx-buf'),
      consultExperience:    getCheck('consult-experience'),
      consultDesignContract: getCheck('consult-design-contract'),

      loopGenModel:     getVal('loop-gen-model'),
      loopAuditModel:   getVal('loop-audit-model'),
      loopRedteamModel: getVal('loop-redteam-model'),
      loopStopCmd:      getVal('loop-stop-cmd'),
      loopMaxIter:      getNumVal('loop-max-iter'),
      loopCostCap:      parseFloat(document.getElementById('loop-cost-cap')?.value || '2'),
      loopIterTimeout:  getNumVal('loop-iter-timeout'),
      loopSessionId:    getVal('loop-session-id'),
      loopContractPath: getVal('loop-contract-path'),
      loopSandbox:      getCheck('loop-sandbox'),
      loopOscillation:  getCheck('loop-oscillation'),
      loopTokenReport:  getCheck('loop-token-report'),

      routingDiscoveryInterval: getNumVal('routing-discovery-interval'),
      routingHealthTTL:         getNumVal('routing-health-ttl'),
      routingFailover:          getCheck('routing-failover'),
      routingSpofWarn:          getCheck('routing-spof-warn'),

      flagAllowAbsolute: getCheck('flag-allow-absolute'),
      flagDebug:         getCheck('flag-debug'),
      flagStream:        getCheck('flag-stream'),
      flagMaskKeys:      getCheck('flag-mask-keys'),
      flagAtomic:        getCheck('flag-atomic'),
      flagEvolveBackup:  getCheck('flag-evolve-backup'),
      flagSessionTurns:  getNumVal('flag-session-turns'),
      flagDiffCap:       getNumVal('flag-diff-cap'),

      prefTheme:        getVal('pref-theme'),
      prefLang:         getVal('pref-lang'),
      prefBudgetAlert:  parseFloat(document.getElementById('pref-budget-alert')?.value || '5'),
      prefSound:        getCheck('pref-sound'),
      prefAutosave:     getCheck('pref-autosave')
    };
  }

  function getVal(id)    { return document.getElementById(id)?.value?.trim() || ''; }
  function getNumVal(id) { return parseInt(document.getElementById(id)?.value || '0', 10); }
  function getCheck(id)  { return !!(document.getElementById(id)?.checked); }

  // ── Save ─────────────────────────────────────────────────────────────────
  function doSave() {
    const settings = collectSettings();
    if (vscodeApi) {
      vscodeApi.postMessage({ command: 'saveSettings', data: settings });
    } else {
      console.log('[LWT] Settings to save:', settings);
    }
    showToast();
    if (preferencesState.sound) playSuccessSound();
  }

  function doSaveSilent() {
    const settings = collectSettings();
    if (vscodeApi) {
      vscodeApi.postMessage({ command: 'saveSettings', data: settings });
    } else {
      console.log('[LWT] Auto-saved settings:', settings);
    }
  }

  document.getElementById('btn-save')?.addEventListener('click', doSave);
  document.getElementById('btn-save-footer')?.addEventListener('click', doSave);

  // ── Reset ─────────────────────────────────────────────────────────────────
  document.getElementById('btn-reset')?.addEventListener('click', () => {
    if (confirm('Reset all settings to defaults? [Đặt lại tất cả cài đặt về mặc định?]')) {
      window.location.reload();
    }
  });

  // ── Toast ─────────────────────────────────────────────────────────────────
  function showToast() {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 2500);
  }

  // Play audio signal
  function playSuccessSound() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, audioCtx.currentTime); // high tone
      gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.1);
    } catch (e) {
      console.log('Audio feedback not supported:', e);
    }
  }

  // Play setup completed audio tone
  function playSetupSound() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const playTone = (freq, start, duration) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime + start);
        gain.gain.setValueAtTime(0.05, audioCtx.currentTime + start);
        osc.start(audioCtx.currentTime + start);
        osc.stop(audioCtx.currentTime + start + duration);
      };
      playTone(523.25, 0, 0.1); // C5
      playTone(659.25, 0.1, 0.1); // E5
      playTone(783.99, 0.2, 0.15); // G5
    } catch (e) {
      console.log(e);
    }
  }

  // ── Auto-Setup decided by Native LLM ─────────────────────────────────────
  const btnAutoSetup = document.getElementById('btn-auto-setup');
  if (btnAutoSetup) {
    btnAutoSetup.addEventListener('click', () => {
      runAutoSetup();
    });
  }

  function runAutoSetup() {
    const label = document.getElementById('status-label');
    const dot = document.getElementById('status-dot');
    if (!label || !dot) return;

    btnAutoSetup.disabled = true;
    dot.className = 'status-dot warn';

    const steps = [
      { text: 'Checking readiness of external LLMs... [Đang kiểm tra API...]', delay: 600 },
      { text: 'Analyzing latency and model rankings... [Đang xếp hạng nhà cung cấp...]', delay: 1200 },
      { text: 'Verifying network infrastructure... [Đang kiểm tra hạ tầng...]', delay: 1800 },
      { text: 'Evaluating user preference mappings... [Đang áp dụng sở thích...]', delay: 2400 },
      { text: 'Optimizing walkie parameter values... [Đang tối ưu hóa tham số...]', delay: 2900 },
    ];

    steps.forEach((step, index) => {
      setTimeout(() => {
        label.innerHTML = step.text;
      }, step.delay);
    });

    // Complete setup logic
    setTimeout(() => {
      const priorityOrder = ['NVIDIA', 'ZENMUX', 'OPENROUTER', 'GROQ', 'GEMINI', 'OPENAI', 'ANTHROPIC'];
      const container = document.getElementById('order-container');
      
      // Setup Models based on availability
      let defaultGenModel = 'nvidia/z-ai/glm-5.2';
      let defaultAuditModel = 'openrouter/qwen/qwen3-coder:free';
      let defaultRedTeamModel = 'zenmux/x-ai/grok-4.5-free';

      setInputVal('consult-default-model', defaultGenModel);
      setInputVal('loop-gen-model', defaultGenModel);
      setInputVal('loop-audit-model', defaultAuditModel);
      setInputVal('loop-redteam-model', defaultRedTeamModel);

      // Optimize timeout, retries, and buffer size
      const codingLang = preferencesState.lang.toLowerCase();
      let timeoutVal = 90, retriesVal = 3, bufVal = 20;

      if (['c++', 'rust', 'java'].includes(codingLang)) {
        timeoutVal = 120; retriesVal = 4; bufVal = 30;
      }

      setSlider('consult-timeout', 'val-consult-timeout', timeoutVal, v => `${v}s`);
      setSlider('consult-retries', 'val-consult-retries', retriesVal, v => v);
      setSlider('consult-ctx-buf', 'val-consult-ctx-buf', bufVal, v => v);

      updateConsultPreview();
      updateLoopPreview();

      dot.className = 'status-dot ok';
      label.innerHTML = `Auto Setup Complete! <span class="vi">[Tự động thiết lập hoàn tất!]</span>`;
      btnAutoSetup.disabled = false;

      if (preferencesState.sound) playSetupSound();
      if (preferencesState.autosave) doSaveSilent();
      
      alert(`Auto-Setup Successful!`);
    }, 3400);
  }

  // ── VS Code Message Listener ──────────────────────────────────────────────
  if (vscodeApi) {
    window.addEventListener('message', event => {
      const msg = event.data;
      if (msg.command === 'loadSettings') {
        loadSettings(msg.data);
      }
    });
    vscodeApi.postMessage({ command: 'requestSettings' });
  } else {
    loadSettings({
      consultDefaultModel: 'nvidia/z-ai/glm-5.2',
      consultRetries: 3,
      consultTimeout: 90,
      consultCacheTTL: 24,
      consultCtxBuf: 20,
      loopMaxIter: 15,
      loopCostCap: 2,
      loopIterTimeout: 120,
      loopSandbox: true,
      loopOscillation: true,
      loopTokenReport: true,
      routingDiscoveryInterval: 24,
      routingHealthTTL: 3600,
      routingFailover: true,
      routingSpofWarn: true,
      flagStream: true,
      flagMaskKeys: true,
      flagAtomic: true,
      flagEvolveBackup: true,
      flagSessionTurns: 5,
      flagDiffCap: 3000,
      prefTheme: 'dark',
      prefLang: 'python',
      prefBudgetAlert: 5.0,
      prefSound: true,
      prefAutosave: false,
      prefDailyTokenNoCap: false,
      prefDailyCostNoCap: false
    });
  }

  // Bind collect settings to include nocap properties
  const oldCollectSettings = collectSettings;
  collectSettings = function() {
    const s = oldCollectSettings();
    s.prefDailyTokenNoCap = getCheck('pref-daily-token-nocap');
    s.prefDailyCostNoCap  = getCheck('pref-daily-cost-nocap');
    return s;
  };

  const oldLoadSettings = loadSettings;
  loadSettings = function(data) {
    if (!data) return;
    oldLoadSettings(data);
    if (data.prefDailyTokenNoCap != null) setCheck('pref-daily-token-nocap', data.prefDailyTokenNoCap);
    if (data.prefDailyCostNoCap != null)  setCheck('pref-daily-cost-nocap', data.prefDailyCostNoCap);
    setupNoCapLogic();
    populateMonitorFilter();
  };

  // ── Initial renders ───────────────────────────────────────────────────────
  updateConsultPreview();
  updateLoopPreview();
  updateRanks();

  setupNoCapLogic();
  populateMonitorFilter();
  renderApiCards();
  renderTokenSpentMonitor();
  updateStatusPill();

  // ── State Machine Vector Graph Generator ──────────────────────────────────
  const btnGenerateGraph = document.getElementById('btn-generate-graph');
  const graphContainer = document.getElementById('state-graph-container');

  if (btnGenerateGraph && graphContainer) {
    btnGenerateGraph.addEventListener('click', () => {
      alert("Graph generation is currently a work in progress.");
      graphContainer.innerHTML = `
        <svg viewBox="0 0 800 320" width="100%" height="320" style="background:#0a0a0a; border-radius:6px; font-family:var(--font-sans);">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--orange)" />
            </marker>
            <filter id="glow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="0" stdDeviation="4" flood-color="var(--orange)" flood-opacity="0.3"/>
            </filter>
          </defs>

          <text x="400" y="30" fill="var(--orange)" font-size="14" font-weight="bold" text-anchor="middle" letter-spacing="1">
            LWT SYSTEM RUNTIME STATE MACHINE &amp; ARCHITECTURE
          </text>

          <rect x="20" y="120" width="110" height="50" rx="6" fill="#111" stroke="var(--border)" stroke-width="1.5" filter="url(#glow)"/>
          <text x="75" y="145" fill="#ffffff" font-size="11" font-weight="600" text-anchor="middle">CLI Trigger</text>
          <text x="75" y="160" fill="var(--text-muted)" font-size="9" text-anchor="middle">walkie ask / loop</text>

          <path d="M 130 145 L 174 145" stroke="var(--orange)" stroke-width="1.5" marker-end="url(#arrow)" />

          <rect x="180" y="120" width="120" height="50" rx="6" fill="#111" stroke="var(--border)" stroke-width="1.5" filter="url(#glow)"/>
          <text x="240" y="145" fill="#ffffff" font-size="11" font-weight="600" text-anchor="middle">API Discovery</text>
          <text x="240" y="160" fill="#34d399" font-size="9" text-anchor="middle">Health check &amp; RTT</text>

          <path d="M 300 145 L 344 145" stroke="var(--orange)" stroke-width="1.5" marker-end="url(#arrow)" />

          <polygon points="410,100 470,145 410,190 350,145" fill="#111" stroke="var(--orange)" stroke-width="1.5" filter="url(#glow)"/>
          <text x="410" y="142" fill="#ffffff" font-size="10" font-weight="bold" text-anchor="middle">EWMA Election</text>
          <text x="410" y="154" fill="var(--text-muted)" font-size="8" text-anchor="middle">Select Route</text>

          <path d="M 410 100 L 410 75 L 484 75" fill="none" stroke="var(--border)" stroke-width="1.5" marker-end="url(#arrow)" />
          <text x="415" y="90" fill="var(--text-muted)" font-size="8">ask (single)</text>

          <path d="M 410 190 L 410 215 L 484 215" fill="none" stroke="var(--border)" stroke-width="1.5" marker-end="url(#arrow)" />
          <text x="415" y="205" fill="var(--orange)" font-size="8">loop (3 roles)</text>

          <rect x="490" y="50" width="130" height="50" rx="6" fill="#181818" stroke="var(--border-dim)" stroke-width="1"/>
          <text x="555" y="75" fill="#ffffff" font-size="10" text-anchor="middle">Single Consult</text>
          <text x="555" y="90" fill="var(--text-muted)" font-size="8" text-anchor="middle">Surgical Patching</text>

          <rect x="490" y="190" width="130" height="50" rx="6" fill="#181818" stroke="var(--orange)" stroke-width="1" filter="url(#glow)"/>
          <text x="555" y="210" fill="#ffffff" font-size="10" font-weight="bold" text-anchor="middle">Loop: 3 Distinct Vendors</text>
          <text x="555" y="222" fill="var(--text-muted)" font-size="8" text-anchor="middle">Gen → Audit → Red Team</text>

          <path d="M 620 215 L 654 215" stroke="var(--border)" stroke-width="1.5" marker-end="url(#arrow)" />

          <polygon points="695,190 735,215 695,240 655,215" fill="#111" stroke="var(--border)" stroke-width="1.5"/>
          <text x="695" y="212" fill="#ffffff" font-size="9" font-weight="bold" text-anchor="middle">Oracle</text>
          <text x="695" y="222" fill="#34d399" font-size="8" text-anchor="middle">Exit 0?</text>

          <path d="M 695 190 L 695 145 L 650 145" fill="none" stroke="#34d399" stroke-width="1.5" marker-end="url(#arrow)" />
          <text x="702" y="170" fill="#34d399" font-size="8">Yes</text>

          <path d="M 695 240 L 695 275 L 555 275 L 555 243" fill="none" stroke="var(--red)" stroke-width="1.5" marker-end="url(#arrow)" />
          <text x="630" y="270" fill="var(--red)" font-size="8">No (Find defects &amp; retry)</text>

          <rect x="520" y="120" width="125" height="50" rx="6" fill="#202020" stroke="#34d399" stroke-width="1.5"/>
          <text x="582" y="145" fill="#34d399" font-size="11" font-weight="bold" text-anchor="middle">Apply Patch</text>
          <text x="582" y="160" fill="var(--text-muted)" font-size="9" text-anchor="middle">Write to Disk</text>
        </svg>
      `;
    });
  }

});
