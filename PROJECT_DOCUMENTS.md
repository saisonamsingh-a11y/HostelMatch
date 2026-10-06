# HostelMatch – Project Documents

## 1. Project Requirements Document
**Goal:** help students find a hostel that fits budget, commute and lifestyle, with a transparent match score.

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | Enter preferences: monthly budget, max commute (km), room types, amenities | Must |
| FR2 | Recommendation API returns ranked hostels with a 0-100% match | Must |
| FR3 | Show score breakdown (budget, distance, amenities, room, rating) | Must |
| FR4 | Sort by match, price, rating, distance | Must |
| FR5 | Save/shortlist hostels, persisted per browser | Must |
| FR6 | Hostel detail popup (rooms, prices, amenities, breakdown) | Must |
| FR7 | Responsive on phones, keyboard accessible | Must |
| FR8 | Admin add/edit hostels, user accounts, reviews | Later |

**Non-functional:** responses under 300 ms for up to 1,000 hostels; input validation on every endpoint; no personal data stored (anonymous client ID only).

## 2. Architecture
```
Browser (HTML/CSS/JS)  --JSON/HTTP-->  Flask app (app.py)  -->  SQLite (hostels, shortlist)
```
- **Presentation:** one Jinja-served page, vanilla JS, no build step.
- **API layer:** Flask routes validate input and return JSON.
- **Domain logic:** `parse()` validates, `score()` computes the match.
- **Data:** SQLite, seeded on first run. Swap to PostgreSQL by replacing `db()`.

Endpoints: `POST /api/recommend`, `GET /api/hostels/<id>`, `GET /api/shortlist`, `POST|DELETE /api/shortlist/<id>`.

## 3. Rules
**Matching rules**
1. Hard filters: price must be within budget, distance within max commute, and at least one selected room type offered (if any selected).
2. Score (100 points): amenities 30, budget 25, distance 25, room type 10, rating 10.
3. Budget points: full at 80% of budget or less, falling to 15/25 at the limit.
4. Distance points: 25 at 0 km, falling to 10/25 at the limit.
5. Amenities points: share of selected amenities offered (full if none selected).
6. Price shown is the cheapest room matching the selected types.

**Engineering rules:** validate all input; parameterized SQL only; every API returns JSON with proper status codes (400 bad input, 404 missing); the shortlist needs an `X-Client-Id` header; escape user-facing text.

## 4. Project Phases
| Phase | Scope | Output |
|-------|-------|--------|
| 1. Discovery | Requirements, user interviews with students | This document |
| 2. Design | Data model, scoring rules, UI | Architecture, wireframes |
| 3. Build | Backend API, database, frontend | Working MVP (this repo) |
| 4. Test | Unit tests for scoring, API tests, mobile checks | Test report |
| 5. Launch | Deploy (gunicorn + host), real hostel data | Live site |
| 6. Improve | Accounts, reviews, map view, admin panel | v2 |

## 5. Design
- **Layout:** preference panel on the left, ranked results on the right; stacks on mobile.
- **Signature element:** each card has a percentage ring; the detail popup shows the bar breakdown behind it.
- **Palette:** ink #12263A, paper #EDF2F7, teal #0E8F7E (match), amber #E8A33D (saved), line #CBD6E0.
- **Type:** Bricolage Grotesque with system fallback.
- **Accessibility:** visible focus, labelled controls, live result count, reduced motion respected.

## 6. Memory (Data and Storage) Requirements
| Store | Content | Size estimate |
|-------|---------|---------------|
| `hostels` table | name, area, distance, rating, rooms JSON, amenities JSON, about | ~1 KB per row; 1,000 rows = ~1 MB |
| `shortlist` table | client_id + hostel_id | ~100 bytes per row |
| Browser `localStorage` | anonymous client ID | under 100 bytes |
| Runtime RAM | Flask + SQLite | about 50-80 MB |

Scoring runs in memory per request; no caching needed until the catalogue exceeds roughly 10,000 hostels.
