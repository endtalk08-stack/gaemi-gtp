'use strict';

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { test } = require('node:test');
const { JSDOM } = require('jsdom');

const stateSource = readFileSync('frontend/shell/workspace-state.js', 'utf8');
const shellSource = readFileSync('frontend/shell/workspace-shell-state.js', 'utf8');
const initializerSource = readFileSync('frontend/shell/workspace-initializer.js', 'utf8');

function createWindow(saved = null) {
  const dom = new JSDOM(`
    <body class="left-home-closed left-market-closed left-context-closed left-plugin-closed right-panel-closed">
      <aside id="leftSidebarHome"></aside>
      <aside id="leftMarketSidebar"></aside>
      <aside id="leftContextSidebar"></aside>
      <aside id="leftPluginSidebar"></aside>
      <div id="leftPanelResizer"></div>
      <main id="mainContent"><div id="mainHeroView"></div><section id="gaemiCenterNewsFeed" hidden></section></main>
      <div id="rightPanelResizer"></div><aside id="rightPanel"></aside>
      <div id="sidebarBackdrop"></div>
    </body>`, { url: 'https://gaemigtp-main.pages.dev', runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  if (saved) w.localStorage.setItem('gaemiGTP_workspace_state_v1', JSON.stringify(saved));
  w.requestAnimationFrame = callback => w.setTimeout(callback, 0);
  w.GaemiGTPAppState = {
    getActiveStock: () => '삼성전자',
    getCurrentAppMode: () => 'gaemi',
    setActiveStock() {},
    setCurrentAppMode() {}
  };
  w.GaemiGTPRightPanelShell = { setPanelWidth() {}, initializeWorkspaceInteractions() {} };
  w.GaemiGTPCenterChatSearch = { selectAppMode() {}, enterChatWorkspace() {} };
  w.GaemiCenterNews = {
    showNews() {
      w.document.getElementById('mainHeroView').classList.add('hidden');
      w.document.body.classList.add('analysis-mode');
      w.document.getElementById('mainContent').classList.add('is-news-view');
      w.document.getElementById('gaemiCenterNewsFeed').hidden = false;
    },
    restoreScroll() {}
  };
  w.GaemiGTPApp = { restoreLastConversation() {} };
  w.eval(stateSource);
  w.eval(shellSource);
  w.eval(initializerSource);
  return { dom, window: w };
}

async function waitForRestore(window) {
  await new Promise(resolve => window.setTimeout(resolve, 20));
}

test('open left market sidebar survives page reload and is rendered as open', async () => {
  const first = createWindow();
  first.window.document.body.classList.add('left-market-open');
  first.window.GaemiGTPWorkspaceShellState.save();
  const saved = JSON.parse(first.window.localStorage.getItem('gaemiGTP_workspace_state_v1'));
  assert.equal(saved.leftMarketOpen, true);
  first.dom.window.close();

  const second = createWindow(saved);
  second.window.GaemiGTPWorkspaceInitializer.initialize();
  await waitForRestore(second.window);
  assert.equal(second.window.document.body.classList.contains('left-market-open'), true);
  assert.equal(second.window.document.body.classList.contains('left-market-closed'), false);
  assert.equal(second.window.document.getElementById('leftMarketSidebar').getAttribute('aria-hidden'), 'false');
  second.dom.window.close();
});

test('center News selection survives page reload without falling back to Chat home', async () => {
  const first = createWindow();
  first.window.document.getElementById('mainContent').classList.add('is-news-view');
  first.window.document.getElementById('mainHeroView').classList.add('hidden');
  first.window.document.body.classList.add('analysis-mode');
  first.window.GaemiGTPWorkspaceShellState.save();
  const saved = JSON.parse(first.window.localStorage.getItem('gaemiGTP_workspace_state_v1'));
  assert.equal(saved.centerView, 'news');
  first.dom.window.close();

  const second = createWindow(saved);
  second.window.GaemiGTPWorkspaceInitializer.initialize();
  await waitForRestore(second.window);
  assert.equal(second.window.document.getElementById('mainContent').classList.contains('is-news-view'), true);
  assert.equal(second.window.document.getElementById('gaemiCenterNewsFeed').hidden, false);
  assert.equal(second.window.document.getElementById('mainHeroView').classList.contains('hidden'), true);
  second.dom.window.close();
});
