# Chinook Database - Data Model

## Entity Relationship Diagram

The Chinook database models a digital media store with the following entity relationships:

```
Artist (1) ──────────── (N) Album (1) ──────────── (N) Track
                                                        │
                                                        │ (N)
                                                        │
Genre (1) ──────────────────────────────────────────────┘
                                                        │
MediaType (1) ──────────────────────────────────────────┘
                                                        │
                                                        │ (N)
                                                        ▼
Playlist (1) ────── (N) PlaylistTrack (N) ──────── (1) Track
                                                        │
                                                        │ (N)
                                                        ▼
                                                   InvoiceLine
                                                        │
                                                        │ (N)
                                                        ▼
Customer (1) ────── (N) Invoice (1) ────────────── (N) InvoiceLine
    │
    │ (support_rep_id)
    ▼
Employee (self-referencing via reports_to)
```

## Relationships

### Artist → Album (One-to-Many)
- One artist can have many albums
- Each album belongs to exactly one artist
- Foreign Key: `album.artist_id → artist.artist_id`

### Album → Track (One-to-Many)
- One album can contain many tracks
- Each track belongs to at most one album
- Foreign Key: `track.album_id → album.album_id`

### Genre → Track (One-to-Many)
- One genre can categorize many tracks
- Each track belongs to at most one genre
- Foreign Key: `track.genre_id → genre.genre_id`

### MediaType → Track (One-to-Many)
- One media type can be associated with many tracks
- Each track has exactly one media type
- Foreign Key: `track.media_type_id → media_type.media_type_id`

### Playlist ↔ Track (Many-to-Many)
- A playlist can contain many tracks
- A track can appear in many playlists
- Junction Table: `playlist_track` with composite key (`playlist_id`, `track_id`)
- Foreign Keys:
  - `playlist_track.playlist_id → playlist.playlist_id`
  - `playlist_track.track_id → track.track_id`

### Customer → Invoice (One-to-Many)
- One customer can have many invoices
- Each invoice belongs to exactly one customer
- Foreign Key: `invoice.customer_id → customer.customer_id`

### Invoice → InvoiceLine (One-to-Many)
- One invoice can have many line items
- Each line item belongs to exactly one invoice
- Foreign Key: `invoice_line.invoice_id → invoice.invoice_id`

### Track → InvoiceLine (One-to-Many)
- One track can appear in many invoice line items (purchased multiple times)
- Each invoice line item references exactly one track
- Foreign Key: `invoice_line.track_id → track.track_id`

### Employee → Customer (One-to-Many, Support Representative)
- One employee can support many customers
- Each customer is assigned one support representative
- Foreign Key: `customer.support_rep_id → employee.employee_id`

### Employee → Employee (Self-Referencing, Hierarchy)
- An employee can report to another employee (manager)
- One manager can have many direct reports
- Foreign Key: `employee.reports_to → employee.employee_id`

## Data Statistics
- **275** artists
- **347** albums
- **3,503** tracks
- **25** genres
- **5** media types
- **18** playlists
- **59** customers
- **8** employees
- **412** invoices
- **2,240** invoice line items

## Common SQL Query Patterns

### Revenue Analysis
```sql
-- Total revenue by genre
SELECT g.name AS genre, SUM(il.unit_price * il.quantity) AS total_revenue
FROM genre g
JOIN track t ON g.genre_id = t.genre_id
JOIN invoice_line il ON t.track_id = il.track_id
GROUP BY g.name
ORDER BY total_revenue DESC;
```

### Top Selling Tracks
```sql
-- Tracks with most revenue
SELECT t.name AS track, SUM(il.unit_price * il.quantity) AS revenue
FROM track t
JOIN invoice_line il ON t.track_id = il.track_id
GROUP BY t.name
ORDER BY revenue DESC
LIMIT 10;
```

### Customer Spending
```sql
-- Top spending customers
SELECT c.first_name || ' ' || c.last_name AS customer, SUM(i.total) AS total_spent
FROM customer c
JOIN invoice i ON c.customer_id = i.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name
ORDER BY total_spent DESC
LIMIT 10;
```
