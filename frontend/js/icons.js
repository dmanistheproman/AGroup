/* Lucide icons from assets/icons/lucide.svg (build with scripts/build_icons.py).
   AGroupIcons.icon('heart') returns the SVG markup; the icon takes the text size and colour.
   icon(name, label, extraClass): label makes it announced by screen readers (otherwise hidden);
   extraClass 'filled' fills the shape (e.g. a saved heart or a rating star). */
(() => {
  'use strict';
  const SPRITE = 'assets/icons/lucide.svg';

  function icon(name, label, extraClass) {
    const a11y = label ? `role="img" aria-label="${String(label).replace(/"/g, '&quot;')}"` : 'aria-hidden="true"';
    const cls = `icon icon-${name}${extraClass ? ' ' + extraClass : ''}`;
    return `<svg class="${cls}" ${a11y} focusable="false"><use href="${SPRITE}#${name}"></use></svg>`;
  }

  window.AGroupIcons = { icon };
})();
