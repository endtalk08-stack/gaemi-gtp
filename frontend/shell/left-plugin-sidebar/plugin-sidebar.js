/* Left Plugin Sidebar — widget catalog picker only. */
(function () {
  'use strict';

  function content() { return document.getElementById('leftPluginContent'); }
  function isOpen() { return document.body.classList.contains('left-plugin-open'); }

  function catalog() { return window.GaemiGTPWidgetCatalog || {}; }

  function render() {
    const el = content();
    if (!el) return;
    const entries = Object.entries(catalog());
    const active = window.GaemiGTPWidgetDock?.getActiveIds ? window.GaemiGTPWidgetDock.getActiveIds() : [];
    el.innerHTML = `
      <div class="plugin-sidebar-note">필요한 분석 위젯을 골라 중앙 Workspace에 추가하세요.</div>
      <div class="plugin-widget-list">
        ${entries.map(([id, meta]) => {
          const used = active.includes(id);
          return `
            <button type="button" class="plugin-widget-item" data-plugin-widget-id="${escapeHtml(id)}" ${used ? 'disabled' : ''}>
              <span class="plugin-widget-icon"><i data-lucide="${escapeHtml(meta.icon)}" class="w-4 h-4"></i></span>
              <span class="plugin-widget-meta">
                <span class="plugin-widget-title">${escapeHtml(meta.title)}</span>
                <span class="plugin-widget-desc">${escapeHtml(meta.description)}</span>
              </span>
              <span class="plugin-widget-status">${used ? '사용 중' : '추가'}</span>
            </button>`;
        }).join('')}
      </div>`;
    if (window.lucide) window.lucide.createIcons();
  }

  function setOpen(open) {
    const body = document.body;
    if (!open) {
      body.classList.remove('left-plugin-open');
    } else {
      body.classList.remove('left-market-open', 'left-context-open');
      if (window.innerWidth < 1024) body.classList.remove('right-panel-open', 'right-panel-maximized');
      body.classList.add('left-plugin-open');
    }
    if (typeof window.applySidebarState === 'function') window.applySidebarState();
    render();
  }

  window.toggleLeftPluginSidebar = function toggleLeftPluginSidebar() {
    if (typeof window.workspaceUIReady !== 'undefined' && !window.workspaceUIReady) return;
    setOpen(!isOpen());
  };

  window.closeLeftPluginSidebar = function closeLeftPluginSidebar() {
    setOpen(false);
  };

  function initialize() {
    const el = content();
    if (!el || el.dataset.bound === 'true') return;
    el.dataset.bound = 'true';
    render();
    el.addEventListener('click', (event) => {
      const btn = event.target.closest('[data-plugin-widget-id]');
      if (!btn || btn.disabled) return;
      const id = btn.dataset.pluginWidgetId;
      if (window.GaemiGTPWidgetDock?.add) {
        window.GaemiGTPWidgetDock.add(id);
        render();
      }
    });
  }

  window.GaemiGTPPluginSidebar = { initialize, render, setOpen };
  document.addEventListener('DOMContentLoaded', initialize);
}());

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
