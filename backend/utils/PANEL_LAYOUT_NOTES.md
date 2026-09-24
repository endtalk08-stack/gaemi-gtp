# Panel layout change

- Desktop uses one flex row: market panel + main + movable panel.
- The panel is not positioned with a free-floating left/top coordinate.
- Dragging the panel header past the viewport midpoint changes flex order, so the market panel and main content reflow together.
- Mobile keeps overlay behavior.
- Backend files are unchanged.
