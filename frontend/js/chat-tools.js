(() => {
  const trigger = document.getElementById('stockToolsTrigger');
  const menu = document.getElementById('stockToolsMenu');
  const modeButton = document.getElementById('bottomModeBtn');

  if (!trigger || !menu) return;

  const closeMenu = () => {
    menu.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
  };

  const openMenu = () => {
    document.getElementById('bottomModeMenu')?.classList.add('hidden');
    menu.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    requestAnimationFrame(() => {
      menu.querySelector('.stock-tools-menu__item')?.focus();
    });
  };

  const toggleMenu = () => {
    if (menu.hidden) openMenu();
    else closeMenu();
  };

  trigger.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleMenu();
  });

  modeButton?.addEventListener('click', closeMenu);

  document.addEventListener('click', (event) => {
    if (!menu.hidden && !menu.contains(event.target) && event.target !== trigger) closeMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || menu.hidden) return;
    closeMenu();
    trigger.focus();
  });

  window.GaemiGTPChatTools = {
    closeMenu,
    openMenu,
    toggleMenu
  };
})();
