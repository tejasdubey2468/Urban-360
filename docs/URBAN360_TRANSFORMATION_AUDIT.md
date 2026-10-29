# URBAN 360 — TRANSFORMATION AUDIT & BASELINE REPORT
**Project:** Urban 360 — Connecting People with Urban Services  
**Starting Codebase:** RAKSHA-FORCE Repository  
**Audit Date:** 2026-10-28  
**Audit Status:** Completed  

---

## 1. ACTUAL TECH STACK & DEPENDENCY VERSIONS
Based on repository inspection, dependency files (`requirements.txt`), and active runtime environment:

* **Runtime Environment:** Python 3.14.3 / macOS (Darwin 24.3.0)
* **Web Framework:** FastAPI `0.136.1` (declared in requirements: `0.115.5`)
* **ASGI Server:** Uvicorn `0.46.0` (declared: `0.32.1`)
* **Serverless Adapter:** Mangum `0.19.0` (for Vercel serverless functions)
* **Data Validation:** Pydantic `2.13.3`, Pydantic Settings `2.14.0` (declared: `2.10.3`, `2.7.0`)
* **BaaS / Database Client:** Supabase Python SDK `2.28.3` (declared: `2.10.0`), PostgREST / HTTPX `0.27.2`
* **JWT Cryptography:** PyJWT `2.10.1`
* **Environment Loader:** Python-dotenv `1.0.1`
* **Frontend Tech:**
  * Native HTML5 Semantic Markup (No React/Vue/Angular/Tailwind; purely native)
  * Vanilla CSS with Glassmorphism and Tactical Dark Theme
  * Vanilla ES6+ Modular JavaScript (`supabase-client.js`, `gps.js`, `utils.js`)
  * Geospatial Visualization: Leaflet.js `1.9.4` with CartoDB DarkMatter tiles
  * Typography: Google Fonts (`Rajdhani`, `Orbitron`, `Bebas Neue`)
* **Cloud Deployment Platform:** Vercel (@vercel/python serverless runtime + static asset hosting configured via `vercel.json`)

---

## 2. EXISTING PAGE & FILE INVENTORY

| Path | Type | Primary Role & Description | Transformation Strategy |
| :--- | :--- | :--- | :--- |
| `index.html` (88.3 KB) | Frontend (HTML/JS) | Public entry portal, emergency hotline directory, quick SOS, report form, live feed, volunteer section, auth modals. | **Reuse & Modify Content:** Retain exact layout, styles, and components. Replace emergency hotlines/SOS with civic service categories, complaint reporting, and department contacts. |
| `citizen.html` (106.8 KB) | Frontend (HTML/JS) | Citizen Portal: 4 sub-pages (`#page-dashboard`, `#page-report`, `#page-myreports`, `#page-track`), live progress tracker, photo upload, chat, multilingual support (EN/HI/MR). | **Reuse & Modify:** Convert emergency incident report flow to civic complaint submission and tracking. Retain 4-stage stepper, map tracking, and chat. |
| `admin.html` (91.1 KB) | Frontend (HTML/JS) | Command HQ: 7 sub-pages (`#page-dashboard`, `#page-command`, `#page-incidents`, `#page-teams`, `#page-resources`, `#page-alerts`, `#page-analytics`), GIS map HUD, assignment panel. | **Reuse & Adapt:** Convert tactical dispatch to municipal operations & department staff/officer view. Replace emergency KPIs with civic service metrics. |
| `app.py` (2.8 KB) | Backend (FastAPI) | Local unified development server combining all routers and serving static files. | **Reuse:** Update title, preserve route mounts and static file serving. |
| `vercel.json` (1.5 KB) | Deployment Config | Vercel serverless build definitions, rewrites, and CORS headers. | **Reuse:** Maintain serverless rewrites and add any new route mappings. |
| `assets/css/style.css` (2.7 KB) | Design System | Global design tokens, CSS variables, utility classes, and responsive breakpoints. | **Preserve 100%:** Keep all tokens, colors, glassmorphism, glowing borders, and animations strictly locked. |
| `assets/js/supabase-client.js` (6.1 KB) | Frontend Shared Client | Supabase client wrapper, session management, REST API fetch bridge, auth helpers. | **Reuse & Enhance:** Maintain token handling and add civic endpoint helpers and robust error handling. |
| `assets/js/gps.js` (9.2 KB) | Frontend Geolocation | Client-side geolocation manager, permission watcher, Leaflet integration, accuracy thresholding. | **Reuse:** Keep permission-guarded location capture with manual fallback for civic reporting. |
| `assets/js/utils.js` (2.7 KB) | Frontend Utilities | Date formatting, relative time calculation, animated toast notification system. | **Reuse 100%:** Standard utility for all interfaces. |
| `database/schema.sql` (26.6 KB) | Database Schema | Supabase PostgreSQL schema: 10 tables, triggers, indexes, RLS policies, and seed data. | **Preserve & Extend:** Keep legacy tables for backward compatibility; add safe additive migrations for civic services (`departments`, `complaint_status_history`, `feedback`). |
| `api/auth.py` (11.4 KB) | API Router | User registration, login, logout, profile session validation. | **Reuse & Enhance:** Support `citizen`, `officer`, `worker`, `admin` roles securely. |
| `api/incidents.py` (15.1 KB) | API Router | Incident creation, filtering, detail retrieval, keyword auto-priority, geospatial duplicate detection. | **Reuse & Adapt:** Retain contract for civic complaints (`roads`, `waste`, `water`, `drainage`, `streetlights`, etc.) and adapt duplicate logic. |
| `api/dispatch.py` (13.7 KB) | API Router | Nearest unit match using Haversine distance, unit type penalty, and load factor. | **Reuse & Adapt:** Map to municipal department/worker assignment workflow. |
| `api/sos.py` (10.7 KB) | API Router | Emergency SOS creation and admin retrieval. | **Preserve for Compatibility:** Keep API alive for legacy safety, but remove public UI promotion in Urban 360. |
| `api/gps.py` (8.2 KB) | API Router | User and staff GPS telemetry upserts. | **Reuse:** Restrict telemetry tracking to authorized operations. |
| `api/volunteers.py` (9.6 KB) | API Router | Volunteer registry and skills querying. | **Reuse:** Adapt to civic community volunteers / community leaders. |
| `api/utils/` | Shared Modules | `auth.py` (JWT/RBAC), `db.py` (Supabase client), `geo.py` (Haversine/ETA), `logger.py` (JSON logging), `rate_limit.py` (Sliding window rate limiters). | **Reuse 100%:** Solid operational foundations. |

---

## 3. EXISTING BACKEND ROUTES & PURPOSES

* `POST /api/auth/register` — Register citizen/officer profile (Admin registration gated by secret header).
* `POST /api/auth/login` — Sign in and issue JWT tokens.
* `POST /api/auth/logout` — Invalidate user session.
* `GET  /api/auth/me` — Return user profile and role claims.
* `POST /api/incidents` — Submit report (with automated triage and deduplication).
* `GET  /api/incidents` — List reports with status, priority, and role filtering.
* `GET  /api/incidents/{incident_id}` — Get report details with associated conversation history.
* `PATCH /api/incidents/{incident_id}` — Update report status/priority (Staff/Admin).
* `POST /api/dispatch` — Calculate optimal unit match and assign team.
* `GET  /api/dispatch/{incident_id}` — Fetch assignment status and ETA.
* `DELETE /api/dispatch/{incident_id}` — Revert assignment and return unit to available queue.
* `POST /api/gps` — Update location telemetry.
* `GET  /api/gps` — Query active GPS locations.
* `POST /api/sos` — Trigger raw distress alert.
* `GET  /api/sos` — List active distress alerts.
* `POST /api/volunteers` — Volunteer registration.
* `GET  /api/volunteers` — List volunteers with skills/city filter.

---

## 4. SUPABASE DATABASE, TRIGGERS & RLS AUDIT

* **Tables Defined in `schema.sql`:**
  1. `profiles`: User ID (references `auth.users`), full name, phone, role (`citizen`, `responder`, `admin`).
  2. `teams`: Response units / crews with type (`fire`, `medical`, `police`, `ndrf`), coordinates, capacity, and current load.
  3. `resources`: Public infrastructure facilities (`hospital`, `shelter`, `depot`), coordinates, total and available capacity.
  4. `incident_reports`: Primary distress reports, coordinates, emergency type, status (`pending`, `assigned`, `on_the_way`, `resolved`), priority (1–4), assigned team, duplicate reference.
  5. `sos_alerts`: Rapid distress signals with coordinates and status.
  6. `gps_locations`: Real-time user telemetry mapped to page context.
  7. `assignments`: Unique linking between incident and assigned team with ETA and notes.
  8. `incident_messages`: Chronological multi-role chat related to a specific incident.
  9. `volunteers`: Community volunteer directory with skills and availability.
  10. `area_alerts`: Broadcast civic/safety alerts targeted by geographic area.
* **Triggers & Stored Functions:**
  * `set_updated_at()`: Automatically updates `updated_at` timestamps on updates for `incident_reports` and `gps_locations`.
  * `sync_profile_from_auth()`: Automatically captures new signups from `auth.users` and synchronizes `profiles`.
* **Row-Level Security (RLS):**
  * Enabled across all tables. Citizens have scoped access to their own reports; Admins have system-wide access.
* **Connectivity Verification & Blocker Identification:**
  * Testing against `SUPABASE_URL=https://xjjalkcmevxqkjqcbfge.supabase.co` indicated DNS resolution failure (`[Errno 8] nodename nor servname provided, or not known`).
  * **Status:** The remote Supabase reference in the legacy `.env` is currently unreachable/paused.
  * **Remediation Strategy:** The application will be equipped with resilient offline/fallback mock data handling for demo accounts so local evaluation remains 100% functional, and complete additive migration scripts (`database/urban360_migration.sql`) will be prepared for execution on any active Supabase instance.

---

## 5. FEATURE STATUS MATRIX

| Feature Area | Legacy RAKSHA-FORCE Status | Target Urban 360 Status | Notes |
| :--- | :--- | :--- | :--- |
| **Public Landing Page** | Working | Working (Transformed) | Retain exact layout; replace emergency hotlines with municipal services. |
| **Citizen Auth & Profiles** | Working | Working | RBAC with 4 roles: `citizen`, `officer`, `worker`, `admin`. |
| **Civic Complaint Reporting** | Working (as Incident) | Working (Enhanced) | Category mapping, photo upload preview, GPS pin-drop. |
| **4-Stage Progress Stepper** | Working (`pending` &rarr; `resolved`) | Working (Mapped) | `submitted` &rarr; `assigned` &rarr; `in_progress` &rarr; `resolved`. |
| **Incident Messages / Chat** | Working | Working | Real-time communication between citizen and assigned department. |
| **Command Center GIS Map** | Working | Working | Multi-layer Leaflet visualization (Complaints, Teams, Resources). |
| **Smart Dispatch / Routing** | Working | Working (Adapted) | Haversine distance, department match, and crew workload factor. |
| **Municipal Resources** | Working (Hospitals/Depots) | Working (Civic Assets) | Waste depots, water stations, ward offices, public facilities. |
| **Area Alerts** | Working | Working | Civic advisories (water shutoff, road work, sanitation drives). |
| **Multilingual Switcher** | Partial (EN/HI in citizen UI) | Working | Preserved and cleaned up for civic terms. |
| **Role-based Officer/Worker Views** | Partial (Combined in Admin) | Working | Role-aware filtering in operations dashboard. |
| **Citizen Post-Resolution Feedback**| Missing in legacy | Added | Additive feedback rating & review after resolution. |

---

## 6. LOCKED UI ELEMENTS & DESIGN TOKENS (MUST REMAIN UNCHANGED)

The following design system tokens from `assets/css/style.css` and existing inline styles are strictly frozen:

```css
:root {
  --red: #C8102E;         /* Emergency accent / Critical priority */
  --orange: #E07B00;      /* In progress / Warning */
  --amber: #D4A017;       /* Pending / Advisory */
  --blue: #003087;        /* Brand accent / Primary action */
  --lightblue: #6B9FE0;   /* Secondary accent / Links */
  --black: #080C10;       /* Base background */
  --dark: #0D1117;        /* Secondary dark / Panel background */
  --card: #111820;        /* Card surface */
  --card2: #161E28;       /* Elevated card surface */
  --border: rgba(200, 16, 46, 0.2);
  --border2: rgba(0, 48, 135, 0.35);
  --text: #E2E8F0;        /* High-contrast body text */
  --muted: #7A8899;       /* Secondary text */
  --green: #00CC66;       /* Resolved status / Operational */
  --glow: 0 0 28px rgba(200, 16, 46, 0.35);
  --glow-blue: 0 0 18px rgba(0, 48, 135, 0.45);
}
```

* **Typography:** `Rajdhani` (Body and labels), `Orbitron` (Metrics and HUD counters), `Bebas Neue` (Logos and titles).
* **Grid & Layouts:** `.grid-2`, `.grid-3`, `.grid-4`, `.grid-7-5`, custom flex bars, fixed headers with `padding-top: 103px` offset.
* **Component Aesthetics:** Glassmorphic HUD borders, pulsating radar rings, custom styled scrollbars, crosshair cursor, animated particle drifts.

---

## 7. FILE-BY-FILE IMPLEMENTATION PLAN

1. **`index.html`**:
   * Update branding to **Urban 360 — Connecting People with Urban Services**.
   * Replace emergency hotline numbers (100, 101, 108) with municipal service tags (Roads, Waste, Water, Drainage, Lighting, Sanitation).
   * Replace the pulsating SOS button with a prominent **"REPORT CIVIC ISSUE"** trigger.
   * Replace emergency services cards with Civic Service Departments.
   * Update volunteer registration to Community Civic Volunteers.
   * Ensure guest citizen and guest admin links remain functional.
2. **`citizen.html`**:
   * Update branding to Urban 360 Citizen Portal.
   * Replace emergency category dropdown with 10 civic categories (`roads`, `waste`, `water`, `drainage`, `streetlights`, `sanitation`, `parks`, `infrastructure`, `traffic_signs`, `encroachment`).
   * Preserve 4-stage tracking stepper, Leaflet map, chat, and photo preview.
   * Add citizen feedback rating component after case resolution.
3. **`admin.html`**:
   * Update branding to Urban 360 Operations & Command Center.
   * Replace emergency metrics with civic indicators (Total Complaints, Under Review, Assigned, In Progress, Resolved).
   * Update Leaflet layer controls (Complaints, Field Crews, Municipal Resources).
   * Enhance role awareness for Dispatchers, Officers, and Field Workers.
4. **`api/incidents.py`**:
   * Add civic emergency/complaint types (`roads`, `waste`, `water`, `drainage`, `streetlights`, `sanitation`, `parks`, `infrastructure`, `traffic_signs`, `encroachment`, plus legacy compatibility).
   * Update priority auto-calculation to reflect civic infrastructure urgency (e.g. major water main burst or road cave-in = P1; routine streetlight repair = P3/P4).
   * Adapt duplicate detection to civic proximity windows.
5. **`api/dispatch.py`**:
   * Map civic categories to responsible municipal teams/departments.
   * Compute ETA based on municipal work vehicle transit.
6. **`database/schema.sql` & `database/urban360_migration.sql`**:
   * Create safe, additive SQL migration scripts adding `departments`, `complaint_status_history`, and `complaint_feedback` tables without altering or dropping existing tables.
7. **Local Fallback / Offline Resilience (`assets/js/supabase-client.js`)**:
   * Provide seamless fallback handling so that even if the remote Supabase project is unreachable, users can interactively demo login, complaint creation, tracking, and dashboard workflows.

---

## 8. BASELINE SCREENSHOT RECORD

Baseline screenshots before any visual or content alterations have been archived under `docs/baseline_screenshots/`:
* `docs/baseline_screenshots/homepage_loading.png` — Public portal initial loading state
* `docs/baseline_screenshots/homepage_desktop.png` — Public portal desktop layout
* `docs/baseline_screenshots/homepage_mobile.png` — Public portal mobile layout (375px)
* `docs/baseline_screenshots/citizen_desktop.png` — Citizen dashboard desktop
* `docs/baseline_screenshots/citizen_mobile.png` — Citizen dashboard mobile (375px)
* `docs/baseline_screenshots/admin_desktop.png` — Command center desktop
* `docs/baseline_screenshots/admin_mobile.png` — Command center mobile (375px)
* Full browser session recording: `baseline_screens_1793198171039.webp`

---
*Audit completed. Ready for incremental phase-by-phase implementation.*
