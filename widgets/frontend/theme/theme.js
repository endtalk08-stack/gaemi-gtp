/* gaemiGTP Theme Controller — v7.12
   Dark/Light mode is a shell-level concern.
   New pages/widgets should not implement their own theme state.
*/
(function () {
  'use strict';

  const KEY = 'gaemiGTP_theme_v1';
  const DEFAULT_THEME = 'dark';

  function normalize(value) {
    return value === 'light' ? 'light' : 'dark';
  }

  function readTheme() {
    try {
      const saved = localStorage.getItem(KEY);
      return normalize(saved || DEFAULT_THEME);
    } catch (_) {
      return DEFAULT_THEME;
    }
  }

  function applyTheme(theme, persist = true) {
    const normalized = normalize(theme);
    const html = document.documentElement;
    html.classList.toggle('dark', normalized === 'dark');
    html.dataset.theme = normalized;
    if (persist) {
      try { localStorage.setItem(KEY, normalized); } catch (_) {}
    }

    document.querySelectorAll('[data-theme-icon]').forEach(icon => {
      icon.setAttribute('data-lucide', normalized === 'dark' ? 'sun' : 'moon');
    });
    if (window.lucide) window.lucide.createIcons();
    return normalized;
  }

  function initialize() {
    return applyTheme(readTheme(), false);
  }

  function toggle() {
    const current = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
    return applyTheme(current === 'dark' ? 'light' : 'dark', true);
  }

  window.GaemiGTPTheme = Object.freeze({
    key: KEY,
    initialize,
    applyTheme,
    toggle,
    get: () => document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  });

  // Apply before normal UI initialization so newly added modules inherit the theme.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
