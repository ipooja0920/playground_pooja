# Chinook Database — Business Rules & Query Patterns

## Revenue Calculations

- **Track-level revenue**: Use `invoice_line` table. Revenue = `unit_price * quantity` per line item. Do NOT use the `invoice.total` column for track-level breakdowns.
- **Customer total spend**: `SUM(invoice.total)` grouped by customer. Join `customer` → `invoice` on `customer_id`.
- **Artist revenue**: JOIN `artist` → `album` → `track` → `invoice_line`. Revenue = `SUM(invoice_line.unit_price * invoice_line.quantity)`.
- **Genre revenue**: JOIN `genre` → `track` → `invoice_line`. Revenue = `SUM(invoice_line.unit_price * invoice_line.quantity)`.
- **Revenue by country**: Use `invoice.billing_country`, not `customer.country`. Group by `billing_country`, SUM `invoice.total`.

## Column Meanings

- `track.milliseconds`: Track duration in milliseconds. To convert to minutes: `milliseconds / 60000.0`.
- `track.bytes`: File size of the audio file — not relevant for business queries.
- `track.unit_price`: Price of one download of the track (either $0.99 or $1.99).
- `invoice.total`: Pre-computed total for the entire invoice (sum of all line items). Use for customer-level totals only.
- `invoice_line.quantity`: Always 1 for digital downloads in Chinook. Use `unit_price * quantity` anyway for correctness.
- `employee.reports_to`: Self-referencing FK to `employee.employee_id` — used to find manager-subordinate relationships.

## Common Query Patterns

- **Top N tracks by revenue**: JOIN `track` → `invoice_line`, GROUP BY `track.name`, ORDER BY `SUM(unit_price * quantity) DESC`, LIMIT N.
- **Top customers**: JOIN `customer` → `invoice`, GROUP BY `customer.customer_id`, ORDER BY `SUM(total) DESC`.
- **Albums by artist**: JOIN `artist` → `album` on `artist.artist_id = album.artist_id`.
- **Tracks by genre**: JOIN `genre` → `track` on `genre.genre_id = track.genre_id`.
- **Playlist contents**: JOIN `playlist` → `playlist_track` → `track`.
- **Employee hierarchy**: Self-join on `employee.reports_to = employee.employee_id`.

## Known Gotchas

- `invoice` does NOT have a `track_id`. To connect invoices to tracks, you must go through `invoice_line`.
- There is no direct FK between `album` and `invoice`. Path: `album` → `track` → `invoice_line` → `invoice`.
- `customer.support_rep_id` references `employee.employee_id` — use this to find which sales rep serves which customer.
- Genre names are stored exactly as: "Rock", "Jazz", "Metal", "Alternative & Punk", "Classical", "Blues", "Latin", "Reggae", "Pop", "Soundtrack". Use ILIKE for case-insensitive matching.
- `track.composer` is frequently NULL — do not filter on it unless explicitly asked.

## Aggregation Rules

- Customer spend → always `SUM(invoice.total)`, never AVG unless asked for average.
- Track popularity → use count of `invoice_line` rows, or SUM of quantity.
- "Most popular" = highest revenue or most purchased — clarify with revenue (`SUM`) unless user says "most played" or "most bought" (then use COUNT).
- When asked "how many X per Y", use `COUNT(*)` with GROUP BY Y.
- For ranking queries, always use `ORDER BY ... DESC` + `LIMIT N`.

## Table Row Counts (approximate)

- `artist`: 275 rows
- `album`: 347 rows
- `track`: 3,503 rows
- `customer`: 59 rows
- `invoice`: 412 rows
- `invoice_line`: 2,240 rows
- `genre`: 25 rows
- `playlist`: 18 rows
