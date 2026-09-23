# Workspace refresh state persistence v5.4

Changed only the workspace state persistence behavior.

On browser refresh, the app now restores:
- home vs stock-analysis screen
- active stock name
- left market sidebar open/closed state
- right panel open/closed state
- right panel maximized/restored state
- right panel width
- app mode label state

Default when no saved state exists remains closed sidebars/panel on the home screen.

Existing API, DB, widget calculations/rendering, and data flow were not changed.
