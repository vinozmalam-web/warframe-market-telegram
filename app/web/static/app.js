(function () {
  'use strict';

  // Telegram WebApp Initialization
  const tg = window.Telegram?.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  const urlParams = new URLSearchParams(window.location.search);
  let authToken = urlParams.get('token') || localStorage.getItem('wfm_web_app_token') || '';
  if (urlParams.get('token')) {
    localStorage.setItem('wfm_web_app_token', urlParams.get('token'));
  }

  function getInitData() {
    if (tg?.initData) {
      return tg.initData;
    }
    if (window.Telegram?.WebApp?.initData) {
      return window.Telegram.WebApp.initData;
    }
    try {
      const search = window.location.search || '';
      const searchParams = new URLSearchParams(search);
      if (searchParams.has('tgWebAppData')) return searchParams.get('tgWebAppData');
      if (searchParams.has('initData')) return searchParams.get('initData');

      const hash = window.location.hash || '';
      if (hash.includes('tgWebAppData=')) {
        const hashClean = hash.startsWith('#') ? hash.slice(1) : hash;
        const hashParams = new URLSearchParams(hashClean);
        if (hashParams.has('tgWebAppData')) return hashParams.get('tgWebAppData');
      }
    } catch (e) {
      console.error('Failed to parse fallback initData:', e);
    }
    return '';
  }

  function getAuthHeaders() {
    const headers = {};
    const initData = getInitData();
    if (initData) {
      headers['X-Telegram-Init-Data'] = initData;
    }
    if (authToken) {
      headers['X-Auth-Token'] = authToken;
    }
    return headers;
  }

  // State
  let weapons = [];
  let attributes = [];
  let rules = [];
  let currentPosStatCount = 0;

  // DOM Elements
  const activeRulesBadge = document.getElementById('activeRulesBadge');
  const rulesListContainer = document.getElementById('rulesListContainer');
  const openAddModalBtn = document.getElementById('openAddModalBtn');
  const ruleModalOverlay = document.getElementById('ruleModalOverlay');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const ruleForm = document.getElementById('ruleForm');
  const modalTitleText = document.getElementById('modalTitleText');

  const ruleIdInput = document.getElementById('ruleIdInput');
  const ruleNameInput = document.getElementById('ruleNameInput');
  const weaponSelect = document.getElementById('weaponSelect');
  const minPriceInput = document.getElementById('minPriceInput');
  const maxPriceInput = document.getElementById('maxPriceInput');
  const minRerollsInput = document.getElementById('minRerollsInput');
  const maxRerollsInput = document.getElementById('maxRerollsInput');
  const sellerStatusSelect = document.getElementById('sellerStatusSelect');

  const addPosStatBtn = document.getElementById('addPosStatBtn');
  const posStatsContainer = document.getElementById('posStatsContainer');
  const negModeSelect = document.getElementById('negModeSelect');
  const specificNegGroup = document.getElementById('specificNegGroup');
  const negStatSelect = document.getElementById('negStatSelect');
  const negMinInput = document.getElementById('negMinInput');
  const negMaxInput = document.getElementById('negMaxInput');
  const toastMessage = document.getElementById('toastMessage');

  // Load initial data
  init();

  async function init() {
    setupEventListeners();
    const okMeta = await fetchMetadata();
    if (okMeta) {
      await fetchRules();
    }
  }

  function setupEventListeners() {
    openAddModalBtn.addEventListener('click', () => openModal());
    closeModalBtn.addEventListener('click', closeModal);
    ruleModalOverlay.addEventListener('click', (e) => {
      if (e.target === ruleModalOverlay) closeModal();
    });

    addPosStatBtn.addEventListener('click', () => addPosStatRow());
    negModeSelect.addEventListener('change', () => {
      specificNegGroup.style.display = negModeSelect.value === 'specific' ? 'block' : 'none';
    });

    ruleForm.addEventListener('submit', handleFormSubmit);
  }

  function renderUnauthorizedState() {
    activeRulesBadge.textContent = '🔒 Заблокировано';
    openAddModalBtn.style.display = 'none';
    rulesListContainer.innerHTML = `
      <div class="empty-state" style="padding: 40px 20px;">
        <div class="empty-state-icon" style="font-size: 48px; margin-bottom: 12px;">🔒</div>
        <h3 style="margin-bottom: 8px; color: var(--text-primary);">Доступ ограничен</h3>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px; line-height: 1.5;">
          Данный WEB_APP_URL доступен только владельцу бота через Telegram Mini App или по секретному токену.
        </p>
        <div style="display: flex; flex-direction: column; gap: 10px; width: 100%; max-width: 300px; margin: 0 auto;">
          <input type="password" id="tokenInputField" placeholder="Секретный токен (WEB_APP_SECRET_TOKEN)" style="width: 100%; padding: 12px; border-radius: 8px; border: 1px solid var(--border-color); background: rgba(0,0,0,0.2); color: #fff; font-size: 14px;">
          <button type="button" id="submitTokenBtn" class="btn-primary" style="justify-content: center; width: 100%; padding: 12px;">Войти по токену</button>
        </div>
      </div>
    `;
    const submitBtn = document.getElementById('submitTokenBtn');
    const tokenInput = document.getElementById('tokenInputField');
    if (submitBtn && tokenInput) {
      submitBtn.addEventListener('click', () => {
        const val = tokenInput.value.trim();
        if (val) {
          authToken = val;
          localStorage.setItem('wfm_web_app_token', val);
          openAddModalBtn.style.display = 'inline-flex';
          init();
        }
      });
    }
  }

  async function fetchMetadata() {
    try {
      const res = await fetch('/api/riven/meta', { headers: getAuthHeaders() });
      if (res.status === 401 || res.status === 403) {
        renderUnauthorizedState();
        return false;
      }
      if (!res.ok) return false;
      const data = await res.json();
      weapons = data.weapons || [];
      attributes = data.attributes || [];

      populateWeaponSelect();
      populateNegAttributeSelect();
      refreshPosStatSelects();
      return true;
    } catch (err) {
      console.error('Failed to load metadata:', err);
      return false;
    }
  }

  function populateWeaponSelect() {
    weaponSelect.innerHTML = '<option value="*">✨ Любое оружие (Any Weapon)</option>';

    const groups = {};
    weapons.forEach(w => {
      const g = (w.group || 'primary').toLowerCase();
      if (!groups[g]) groups[g] = [];
      groups[g].push(w);
    });

    const groupTitles = {
      primary: '🔫 Основное оружие (Primary)',
      secondary: '🔫 Вторичное оружие (Secondary)',
      melee: '⚔️ Ближний бой (Melee)',
      archgun: '🚀 Арчган (Archgun)',
      other: '✨ Другое (Other)',
    };

    const sortedKeys = Object.keys(groups).sort((a, b) => {
      const order = ['primary', 'secondary', 'melee', 'archgun', 'other'];
      const ia = order.indexOf(a) >= 0 ? order.indexOf(a) : 99;
      const ib = order.indexOf(b) >= 0 ? order.indexOf(b) : 99;
      return ia - ib;
    });

    sortedKeys.forEach(gKey => {
      const optgroup = document.createElement('optgroup');
      optgroup.label = groupTitles[gKey] || gKey.toUpperCase();
      groups[gKey]
        .sort((a, b) => a.item_name.localeCompare(b.item_name))
        .forEach(w => {
          const opt = document.createElement('option');
          opt.value = w.url_name;
          opt.textContent = w.item_name;
          optgroup.appendChild(opt);
        });
      weaponSelect.appendChild(optgroup);
    });

    initSearchableSelect(weaponSelect);
  }

  function populateNegAttributeSelect() {
    negStatSelect.innerHTML = '';
    attributes.sort((a, b) => a.effect.localeCompare(b.effect)).forEach(attr => {
      const opt = document.createElement('option');
      opt.value = attr.url_name;
      opt.textContent = attr.effect;
      negStatSelect.appendChild(opt);
    });

    initSearchableSelect(negStatSelect);
  }

  function refreshPosStatSelects() {
    posStatsContainer.querySelectorAll('.pos-stat-select').forEach(sel => {
      const currentVal = sel.value;
      let optionsHtml = '';
      attributes.sort((a, b) => a.effect.localeCompare(b.effect)).forEach(attr => {
        const selected = attr.url_name === currentVal ? 'selected' : '';
        optionsHtml += `<option value="${attr.url_name}" ${selected}>${attr.effect}</option>`;
      });
      sel.innerHTML = optionsHtml;
      if (currentVal) sel.value = currentVal;

      initSearchableSelect(sel);
    });
  }

  async function fetchRules() {
    try {
      const res = await fetch('/api/rules', { headers: getAuthHeaders() });
      if (res.status === 401 || res.status === 403) {
        renderUnauthorizedState();
        return false;
      }
      if (!res.ok) return false;
      rules = await res.json();
      renderRules();
      return true;
    } catch (err) {
      console.error('Failed to load rules:', err);
      return false;
    }
  }

  function renderRules() {
    const activeCount = rules.filter(r => r.is_active).length;
    activeRulesBadge.textContent = `${activeCount} Активно`;

    if (rules.length === 0) {
      rulesListContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🔎</div>
          <p>У вас пока нет настроенных правил</p>
          <p style="font-size: 12px; margin-top: 6px;">Нажмите "+ Новое правило", чтобы добавить снайпер ривенов.</p>
        </div>
      `;
      return;
    }

    rulesListContainer.innerHTML = '';
    rules.forEach(rule => {
      const card = document.createElement('div');
      card.className = `rule-card ${rule.is_active ? '' : 'inactive'}`;

      const weaponName = rule.weapon_url_name === '*' ? 'Любое оружие' : (
        weapons.find(w => w.url_name === rule.weapon_url_name)?.item_name || rule.weapon_url_name
      );

      const priceText = rule.max_price ? `до ${rule.max_price} 💎` : 'любая цена';
      const rerollsText = rule.max_rerolls !== null ? `роллы <= ${rule.max_rerolls}` : '';

      let posTags = (rule.positive_stats || []).map(p => {
        const attrObj = attributes.find(a => a.url_name === p.url_name);
        const name = attrObj ? attrObj.effect : p.url_name;
        const minStr = p.min_value ? `>=${p.min_value}%` : '';
        return `<span class="tag tag-pos">+ ${name} ${minStr}</span>`;
      }).join(' ');

      let negTag = '';
      if (rule.negative_stat?.mode === 'none') {
        negTag = '<span class="tag tag-neg">Без негатива</span>';
      } else if (rule.negative_stat?.mode === 'any') {
        negTag = '<span class="tag tag-neg">Любой негатив</span>';
      } else if (rule.negative_stat?.mode === 'specific') {
        const attrObj = attributes.find(a => a.url_name === rule.negative_stat.url_name);
        const name = attrObj ? attrObj.effect : rule.negative_stat.url_name;
        negTag = `<span class="tag tag-neg">- ${name}</span>`;
      }

      card.innerHTML = `
        <div class="rule-header">
          <div>
            <div class="rule-title">${escapeHtml(rule.name)}</div>
            <div class="rule-target">🔫 ${escapeHtml(weaponName)} • 💰 ${priceText} ${rerollsText ? '• 🔄 ' + rerollsText : ''}</div>
          </div>
          <div class="rule-actions">
            <label class="toggle-switch">
              <input type="checkbox" ${rule.is_active ? 'checked' : ''} data-id="${rule.id}" class="rule-toggle">
              <span class="slider"></span>
            </label>
            <button class="icon-btn edit-rule-btn" data-id="${rule.id}" title="Редактировать">✏️</button>
            <button class="icon-btn delete-rule-btn" data-id="${rule.id}" title="Удалить">🗑️</button>
          </div>
        </div>
        <div class="rule-details">
          <span class="tag">Статус продавца: ${rule.seller_status}</span>
          ${posTags}
          ${negTag}
        </div>
      `;

      rulesListContainer.appendChild(card);
    });

    // Add card action listeners
    document.querySelectorAll('.rule-toggle').forEach(chk => {
      chk.addEventListener('change', async (e) => {
        const id = parseInt(e.target.dataset.id, 10);
        const rule = rules.find(r => r.id === id);
        if (rule) {
          rule.is_active = e.target.checked;
          await saveRule(rule);
          renderRules();
        }
      });
    });

    document.querySelectorAll('.edit-rule-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = parseInt(btn.dataset.id, 10);
        const rule = rules.find(r => r.id === id);
        if (rule) openModal(rule);
      });
    });

    document.querySelectorAll('.delete-rule-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = parseInt(btn.dataset.id, 10);
        if (confirm('Удалить это правило снайпера?')) {
          await deleteRule(id);
        }
      });
    });
  }

  function addPosStatRow(existingData = null) {
    if (currentPosStatCount >= 3) {
      showToast('Максимум 3 позитивные характеристики');
      return;
    }

    const rowId = `pos_stat_row_${Date.now()}_${Math.random().toString(36).substring(2, 5)}`;
    const div = document.createElement('div');
    div.className = 'stat-row';
    div.id = rowId;

    let optionsHtml = '';
    attributes.sort((a, b) => a.effect.localeCompare(b.effect)).forEach(attr => {
      const selected = existingData && existingData.url_name === attr.url_name ? 'selected' : '';
      optionsHtml += `<option value="${attr.url_name}" ${selected}>${attr.effect}</option>`;
    });

    div.innerHTML = `
      <div class="stat-header">
        <span style="font-size: 12px; color: var(--accent-green); font-weight: 600;">+ Характеристика</span>
        <button type="button" class="icon-btn remove-stat-btn" style="color: var(--accent-red); font-size: 14px;">✕</button>
      </div>
      <div class="form-group" style="margin-bottom: 8px;">
        <select class="pos-stat-select">${optionsHtml}</select>
      </div>
      <div class="grid-2">
        <input type="number" class="pos-min-input" placeholder="Мин %" step="0.1" value="${existingData?.min_value ?? ''}">
        <input type="number" class="pos-max-input" placeholder="Макс %" step="0.1" value="${existingData?.max_value ?? ''}">
      </div>
    `;

    posStatsContainer.appendChild(div);
    currentPosStatCount++;

    initSearchableSelect(div.querySelector('.pos-stat-select'));

    div.querySelector('.remove-stat-btn').addEventListener('click', () => {
      div.remove();
      currentPosStatCount--;
    });
  }

  function openModal(rule = null) {
    ruleForm.reset();
    posStatsContainer.innerHTML = '';
    currentPosStatCount = 0;

    if (rule) {
      modalTitleText.textContent = 'Редактировать правило';
      ruleIdInput.value = rule.id;
      ruleNameInput.value = rule.name;
      weaponSelect.value = rule.weapon_url_name || '*';
      minPriceInput.value = rule.min_price ?? '';
      maxPriceInput.value = rule.max_price ?? '';
      minRerollsInput.value = rule.min_rerolls ?? '';
      maxRerollsInput.value = rule.max_rerolls ?? '';
      sellerStatusSelect.value = rule.seller_status || 'ingame';

      (rule.positive_stats || []).forEach(p => addPosStatRow(p));

      negModeSelect.value = rule.negative_stat?.mode || 'any_or_none';
      specificNegGroup.style.display = negModeSelect.value === 'specific' ? 'block' : 'none';
      if (rule.negative_stat?.url_name) {
        negStatSelect.value = rule.negative_stat.url_name;
      }
      negMinInput.value = rule.negative_stat?.min_value ?? '';
      negMaxInput.value = rule.negative_stat?.max_value ?? '';
    } else {
      modalTitleText.textContent = 'Создать новое правило';
      ruleIdInput.value = '';
      weaponSelect.value = '*';
      sellerStatusSelect.value = 'ingame';
      negModeSelect.value = 'any_or_none';
      specificNegGroup.style.display = 'none';
      addPosStatRow();
    }

    initSearchableSelect(weaponSelect)?.updateSelectedLabel();
    initSearchableSelect(negStatSelect)?.updateSelectedLabel();

    ruleModalOverlay.classList.add('active');
  }

  function closeModal() {
    ruleModalOverlay.classList.remove('active');
  }

  async function handleFormSubmit(e) {
    e.preventDefault();

    const positive_stats = [];
    posStatsContainer.querySelectorAll('.stat-row').forEach(row => {
      const sel = row.querySelector('.pos-stat-select');
      const minIn = row.querySelector('.pos-min-input');
      const maxIn = row.querySelector('.pos-max-input');
      if (sel && sel.value) {
        positive_stats.push({
          url_name: sel.value,
          min_value: minIn.value ? parseFloat(minIn.value) : null,
          max_value: maxIn.value ? parseFloat(maxIn.value) : null,
        });
      }
    });

    const negMode = negModeSelect.value;
    let negative_stat = { mode: negMode };
    if (negMode === 'specific') {
      negative_stat = {
        mode: 'specific',
        url_name: negStatSelect.value,
        min_value: negMinInput.value ? parseFloat(negMinInput.value) : null,
        max_value: negMaxInput.value ? parseFloat(negMaxInput.value) : null,
      };
    }

    const payload = {
      id: ruleIdInput.value ? parseInt(ruleIdInput.value, 10) : null,
      name: ruleNameInput.value.trim() || 'Riven Rule',
      item_type: 'riven',
      weapon_url_name: weaponSelect.value,
      target_name: weaponSelect.options[weaponSelect.selectedIndex]?.text || 'Any Weapon',
      min_price: minPriceInput.value ? parseInt(minPriceInput.value, 10) : null,
      max_price: maxPriceInput.value ? parseInt(maxPriceInput.value, 10) : null,
      min_rerolls: minRerollsInput.value ? parseInt(minRerollsInput.value, 10) : null,
      max_rerolls: maxRerollsInput.value ? parseInt(maxRerollsInput.value, 10) : null,
      seller_status: sellerStatusSelect.value,
      positive_stats: positive_stats,
      negative_stat: negative_stat,
      is_active: true,
      initData: getInitData(),
    };

    await saveRule(payload);
    closeModal();
    await fetchRules();
    showToast('Правило успешно сохранено');
  }

  async function saveRule(ruleData) {
    const isUpdate = Boolean(ruleData.id);
    const url = isUpdate ? `/api/rules/${ruleData.id}` : '/api/rules';
    const method = isUpdate ? 'PUT' : 'POST';

    try {
      const headers = Object.assign({ 'Content-Type': 'application/json' }, getAuthHeaders());
      const res = await fetch(url, {
        method,
        headers,
        body: JSON.stringify(ruleData),
      });

      if (!res.ok) {
        const err = await res.json();
        showToast(err.error || 'Ошибка сохранения');
      }
    } catch (err) {
      console.error('Save rule error:', err);
      showToast('Ошибка сети при сохранении');
    }
  }

  async function deleteRule(id) {
    try {
      const res = await fetch(`/api/rules/${id}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (res.ok) {
        showToast('Правило удалено');
        await fetchRules();
      } else {
        showToast('Не удалось удалить правило');
      }
    } catch (err) {
      console.error('Delete rule error:', err);
    }
  }

  function showToast(msg) {
    toastMessage.textContent = msg;
    toastMessage.classList.add('show');
    setTimeout(() => {
      toastMessage.classList.remove('show');
    }, 2500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  class SearchableSelect {
    constructor(selectElement) {
      this.select = selectElement;
      if (this.select._searchableSelect) {
        this.select._searchableSelect.update();
        return this.select._searchableSelect;
      }
      this.select._searchableSelect = this;
      this.isOpen = false;
      this.optionsData = [];
      this.filteredData = [];

      this.initUI();
      this.bindEvents();
      this.update();
    }

    initUI() {
      this.select.style.display = 'none';

      this.container = document.createElement('div');
      this.container.className = 'custom-select-container';

      this.trigger = document.createElement('button');
      this.trigger.type = 'button';
      this.trigger.className = 'custom-select-trigger';
      this.trigger.innerHTML = `
        <span class="custom-select-label"></span>
        <span class="custom-select-arrow">▼</span>
      `;

      this.dropdown = document.createElement('div');
      this.dropdown.className = 'custom-select-dropdown';

      this.searchWrap = document.createElement('div');
      this.searchWrap.className = 'custom-select-search-wrap';

      this.searchInput = document.createElement('input');
      this.searchInput.type = 'text';
      this.searchInput.className = 'custom-select-search-input';
      this.searchInput.placeholder = '🔍 Поиск...';
      this.searchInput.setAttribute('autocomplete', 'off');

      this.clearBtn = document.createElement('button');
      this.clearBtn.type = 'button';
      this.clearBtn.className = 'custom-select-clear-btn';
      this.clearBtn.textContent = '✕';
      this.clearBtn.style.display = 'none';

      this.searchWrap.appendChild(this.searchInput);
      this.searchWrap.appendChild(this.clearBtn);

      this.optionsList = document.createElement('div');
      this.optionsList.className = 'custom-select-options';

      this.dropdown.appendChild(this.searchWrap);
      this.dropdown.appendChild(this.optionsList);

      this.container.appendChild(this.trigger);
      this.container.appendChild(this.dropdown);

      this.select.parentNode.insertBefore(this.container, this.select.nextSibling);
    }

    bindEvents() {
      this.trigger.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggle();
      });

      this.searchInput.addEventListener('input', () => {
        this.clearBtn.style.display = this.searchInput.value ? 'block' : 'none';
        this.filter(this.searchInput.value);
      });

      this.searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          this.close();
        }
      });

      this.clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.searchInput.value = '';
        this.clearBtn.style.display = 'none';
        this.filter('');
        this.searchInput.focus();
      });

      document.addEventListener('click', (e) => {
        if (this.isOpen && !this.container.contains(e.target)) {
          this.close();
        }
      });

      this.select.addEventListener('change', () => {
        this.updateSelectedLabel();
      });
    }

    update() {
      this.optionsData = [];
      const children = Array.from(this.select.children);

      children.forEach(child => {
        if (child.tagName === 'OPTGROUP') {
          const groupTitle = child.label;
          Array.from(child.children).forEach(opt => {
            if (opt.tagName === 'OPTION') {
              this.optionsData.push({
                value: opt.value,
                text: opt.textContent,
                group: groupTitle
              });
            }
          });
        } else if (child.tagName === 'OPTION') {
          this.optionsData.push({
            value: child.value,
            text: child.textContent,
            group: null
          });
        }
      });

      this.updateSelectedLabel();
      if (this.isOpen) {
        this.filter(this.searchInput.value);
      }
    }

    updateSelectedLabel() {
      const selectedOpt = this.optionsData.find(o => o.value === this.select.value) || this.optionsData[0];
      const labelSpan = this.trigger.querySelector('.custom-select-label');
      if (labelSpan) {
        labelSpan.textContent = selectedOpt ? selectedOpt.text : 'Выберите...';
      }
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }

    open() {
      document.querySelectorAll('.custom-select-container.is-open').forEach(c => {
        if (c !== this.container && c._searchableSelect) {
          c._searchableSelect.close();
        }
      });

      this.isOpen = true;
      this.container.classList.add('is-open');
      this.searchInput.value = '';
      this.clearBtn.style.display = 'none';
      this.filter('');

      setTimeout(() => {
        this.searchInput.focus();
      }, 50);
    }

    close() {
      this.isOpen = false;
      this.container.classList.remove('is-open');
    }

    filter(query) {
      const q = query.trim().toLowerCase();
      this.filteredData = this.optionsData.filter(item => {
        if (!q) return true;
        const textMatch = item.text.toLowerCase().includes(q);
        const valMatch = item.value.toLowerCase().includes(q);
        const groupMatch = item.group ? item.group.toLowerCase().includes(q) : false;
        return textMatch || valMatch || groupMatch;
      });

      this.renderOptions();
    }

    renderOptions() {
      this.optionsList.innerHTML = '';

      if (this.filteredData.length === 0) {
        const emptyDiv = document.createElement('div');
        emptyDiv.className = 'custom-select-empty';
        emptyDiv.textContent = '🔍 Ничего не найдено';
        this.optionsList.appendChild(emptyDiv);
        return;
      }

      let lastGroup = undefined;
      this.filteredData.forEach(item => {
        if (item.group !== lastGroup) {
          lastGroup = item.group;
          if (item.group) {
            const groupHeader = document.createElement('div');
            groupHeader.className = 'custom-select-group-header';
            groupHeader.textContent = item.group;
            this.optionsList.appendChild(groupHeader);
          }
        }

        const optionEl = document.createElement('div');
        const isSelected = item.value === this.select.value;
        optionEl.className = `custom-select-option ${isSelected ? 'selected' : ''}`;
        optionEl.textContent = item.text;
        optionEl.dataset.value = item.value;

        optionEl.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          this.selectValue(item.value);
        });

        this.optionsList.appendChild(optionEl);
      });
    }

    selectValue(val) {
      this.select.value = val;
      this.select.dispatchEvent(new Event('change', { bubbles: true }));
      this.updateSelectedLabel();
      this.close();
    }
  }

  function initSearchableSelect(selectEl) {
    if (!selectEl) return null;
    return new SearchableSelect(selectEl);
  }

})();
