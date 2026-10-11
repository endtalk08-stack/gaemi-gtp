/* Sidebar Home — visual navigation/layout only.
   The primary menu deliberately does not open market/watchlist/plugin views yet. */
(function () {
  'use strict';

  const RECENT_STORAGE_KEY = 'gaemiGTP_recent_searches_v1';
  const RECENT_LIMIT = 10;
  let recentFallback = [];

  function readRecent() {
    try {
      const saved = localStorage.getItem(RECENT_STORAGE_KEY);
      if (!saved) return [];
      const entries = JSON.parse(saved);
      if (!Array.isArray(entries)) return [];
      return entries.filter((entry) => entry && ['stock', 'question'].includes(entry.type)
        && typeof entry.value === 'string' && entry.value.trim()).slice(0, RECENT_LIMIT);
    } catch (_) {
      return recentFallback.slice();
    }
  }

  function renderRecent() {
    const list = document.getElementById('leftSidebarHomeRecentList');
    const empty = document.getElementById('leftSidebarHomeRecentEmpty');
    if (!list) return;
    const entries = readRecent();
    list.replaceChildren();
    entries.forEach((entry, index) => {
      const row = document.createElement('li');
      row.className = 'left-sidebar-home__item';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'left-sidebar-home__recent-link';
      button.dataset.recentIndex = String(index);
      button.textContent = entry.value;
      button.title = entry.value;
      button.setAttribute('aria-label', `${entry.type === 'stock' ? '종목' : '질문'} 다시 열기: ${entry.value}`);
      row.appendChild(button);
      list.appendChild(row);
    });
    if (empty) empty.hidden = entries.length > 0;
  }

  function recordRecent(type, value) {
    if (type !== 'stock' && type !== 'question') return;
    const text = String(value || '').trim().slice(0, type === 'stock' ? 80 : 240);
    if (!text) return;
    const entries = readRecent().filter((entry) => !(
      entry.type === type && entry.value.toLocaleLowerCase() === text.toLocaleLowerCase()
    ));
    const next = [{ type, value: text }, ...entries].slice(0, RECENT_LIMIT);
    recentFallback = next;
    try { localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(next)); } catch (_) { /* browser storage unavailable */ }
    renderRecent();
  }

  function openRecent(index) {
    const entry = readRecent()[index];
    if (!entry) return;
    if (window.innerWidth < 1024) close();
    if (entry.type === 'stock') {
      window.GaemiGTPCenterChatSearch?.openStockInChat?.(entry.value);
    } else {
      window.GaemiGTPCenterChatSearch?.enterChatWorkspace?.();
      applyState();
      window.GaemiGTPApp?.submitQuestion?.(entry.value, { newConversation: true });
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function setActiveNav(id) {
    const target = id || 'home';
    document.querySelectorAll('#leftSidebarHome [data-left-home-nav]').forEach((button) => {
      const active = button.dataset.leftHomeNav === target;
      button.classList.toggle('is-active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
  }

  function applyState() {
    window.GaemiGTPWorkspaceShellState?.apply?.();
  }

  function toggle() {
    if (typeof window.workspaceUIReady !== 'undefined' && !window.workspaceUIReady) return;
    const isOpen = document.body.classList.contains('left-home-open');
    if (isOpen) {
      document.body.classList.remove('left-home-open');
    } else {
      document.body.classList.remove('left-market-open', 'left-context-open', 'left-plugin-open');
      if (window.innerWidth < 1024) document.body.classList.remove('right-panel-open', 'right-panel-maximized');
      document.body.classList.add('left-home-open');
    }
    applyState();
  }

  function bindToggleControls() {
    document.querySelectorAll('[data-left-sidebar-toggle]').forEach((el) => {
      if (el.dataset.sidebarListenerBound === 'true') return;
      el.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggle();
      });
      el.dataset.sidebarListenerBound = 'true';
    });
  }

  function close() {
    document.body.classList.remove('left-home-open');
    applyState();
  }

  function toggleMenu() {
    const menu = document.getElementById('leftSidebarHomeMenu');
    const button = document.querySelector('[data-left-sidebar-home-menu-toggle]');
    if (!menu || !button) return;
    const open = menu.classList.toggle('hidden') === false;
    button.setAttribute('aria-expanded', String(open));
  }

  const sectionOrigins = new Map();

  function showSection(section = 'home') {
    if (typeof window.workspaceUIReady !== 'undefined' && !window.workspaceUIReady) return;
    const homeDefault = document.getElementById('leftSidebarHomeDefault');
    const host = document.getElementById('leftSidebarHomeSectionContent');
    const title = document.querySelector('.left-sidebar-home__title');
    if (!homeDefault || !host) return;

    sectionOrigins.forEach((origin, node) => {
      if (node.parentNode === host) {
        node.style.removeProperty('width');
        node.style.removeProperty('flex-basis');
        origin.parent.insertBefore(node, origin.nextSibling);
      }
    });
    sectionOrigins.clear();
    host.replaceChildren();
    host.classList.add('hidden');
    homeDefault.classList.remove('hidden');

    if (section !== 'home') {
      const idBySection = {
        market: 'leftMarketSidebar',
        context: 'leftContextSidebar',
        plugin: 'leftPluginSidebar'
      };
      const node = document.getElementById(idBySection[section]);
      if (!node || !node.parentNode) return;
      sectionOrigins.set(node, { parent: node.parentNode, nextSibling: node.nextSibling });
      host.appendChild(node);
      homeDefault.classList.add('hidden');
      host.classList.remove('hidden');
    }

    document.body.classList.add('left-home-open');
    document.body.classList.remove('left-market-open', 'left-context-open', 'left-plugin-open');
    document.getElementById('leftSidebarHomeMenu')?.classList.add('hidden');
    document.querySelector('[data-left-sidebar-home-menu-toggle]')?.setAttribute('aria-expanded', 'false');

    const embedded = host.firstElementChild;
    if (embedded) {
      embedded.removeAttribute('aria-hidden');
      embedded.style.width = '100%';
      embedded.style.flexBasis = '100%';
    }
    if (section === 'plugin') window.GaemiGTPPluginSidebar?.render?.();
    if (title) title.textContent = 'gaemiGTP';
    applyState();
  }

  function render() {
    const list = document.getElementById('leftSidebarHomePluginList');
    const empty = document.getElementById('leftSidebarHomePluginEmpty');
    if (!list) return;

    const catalog = window.GaemiGTPWidgetCatalog || {};
    const active = window.GaemiGTPWidgetDock?.getActiveIds?.() || [];
    const visible = active.filter((id) => catalog[id]);

    list.innerHTML = visible
      .map((id) => `<li class="left-sidebar-home__item">${escapeHtml(catalog[id].title)}</li>`)
      .join('');

    if (empty) empty.hidden = visible.length > 0;
    renderRecent();
    if (window.lucide) window.lucide.createIcons();
  }

  document.addEventListener('click', (event) => {
    const recentButton = event.target.closest('#leftSidebarHome [data-recent-index]');
    if (recentButton) {
      openRecent(Number(recentButton.dataset.recentIndex));
      return;
    }

    const navButton = event.target.closest('#leftSidebarHome [data-left-home-nav]');
    if (navButton) {
      const nav = navButton.dataset.leftHomeNav;
      setActiveNav(nav);
      return;
    }

    const sectionToggle = event.target.closest('#leftSidebarHome [data-left-home-section-toggle]');
    if (sectionToggle) {
      const bodyId = sectionToggle.getAttribute('aria-controls');
      const sectionBody = bodyId ? document.getElementById(bodyId) : null;
      if (!sectionBody) return;
      const expanded = sectionToggle.getAttribute('aria-expanded') !== 'false';
      sectionToggle.setAttribute('aria-expanded', String(!expanded));
      const sectionName = {
        watchlist: '관심종목', plugins: '플러그인', recent: '최근'
      }[sectionToggle.dataset.leftHomeSectionToggle] || '메뉴';
      sectionToggle.setAttribute('aria-label', `${sectionName} ${expanded ? '펼치기' : '접기'}`);
      sectionToggle.setAttribute('title', sectionToggle.getAttribute('aria-label'));
      sectionBody.hidden = expanded;
      return;
    }
  });

  window.GaemiGTPSidebarHome = { render, recordRecent, setActiveNav, toggle, bindToggleControls, close, toggleMenu, showSection };
  window.addEventListener('storage', (event) => {
    if (event.key === RECENT_STORAGE_KEY) renderRecent();
  });
  window.toggleLeftSidebarHome = toggle;
  window.closeLeftSidebarHome = close;
  window.toggleLeftSidebarHomeMenu = toggleMenu;
  window.showLeftSidebarHomeSection = showSection;
  window.openLeftSidebarSection = showSection;

  document.addEventListener('DOMContentLoaded', () => {
    bindToggleControls();
    setActiveNav('home');
    render();
  });
}());
