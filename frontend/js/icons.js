/* Lucide icons from assets/icons/lucide.svg (build with scripts/build_icons.py).
   AGroupIcons.icon('heart') returns the SVG markup; the icon takes the text size and colour. */
(() => {
  'use strict';
  const SPRITE = 'assets/icons/lucide.svg';

  function icon(name, label) {
    const a11y = label ? `role="img" aria-label="${String(label).replace(/"/g, '&quot;')}"` : 'aria-hidden="true"';
    return `<svg class="icon icon-${name}" ${a11y} focusable="false"><use href="${SPRITE}#${name}"></use></svg>`;
  }

  window.AGroupIcons = { icon };
})();
