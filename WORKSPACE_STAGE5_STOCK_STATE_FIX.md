# Stage 5.3 — Analysis transition state preservation

## Fixed
When entering stock analysis from the hero search, quick stock buttons, or left market sidebar, the app no longer force-closes the left market sidebar or right panel.

The current Workspace UI state is preserved across the transition.

## Preserved
- Left market sidebar open/closed state
- Right panel open/closed state
- Right panel maximize state
- Existing panel width

## Intentionally unchanged
- Data/API/backend flow
- Widget logic
- DB logic
- Mobile mutual-exclusion behavior for sidebars
