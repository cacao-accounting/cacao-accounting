---
applyTo: "**/templates/**/*.html"
---
# Smart Select Rules

- **Library:** Use `static/js/smart-select.js` via `x-data="smartSelect({...})"`.
- **Identification:** Hidden input for real ID; visible field for search only.
- **Context:** Pass filters via `filters` object. Support dependencies (e.g., company-filtered accounts).
- **Backend:** Search via `GET /api/search-select`. Registry-based only. No arbitrary tables.
- **UX:** Minimum chars for search. Show loading/error states. Clear on filter change.
- **Large Catalogs:** Never load all options in HTML. Use server-side search.
