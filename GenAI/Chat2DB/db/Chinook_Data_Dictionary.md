# Chinook Database - Data Dictionary

## Overview
The Chinook database represents a digital media store, similar to iTunes. It contains information about artists, albums, tracks, customers, employees, invoices, and more.

## Tables and Columns

### Album
| Column    | Type         | Description                        | Constraints       |
|-----------|-------------|-------------------------------------|-------------------|
| album_id  | INT          | Unique identifier for the album    | PRIMARY KEY        |
| title     | VARCHAR(160) | Album title                        | NOT NULL           |
| artist_id | INT          | Reference to the artist            | FOREIGN KEY → Artist |

### Artist
| Column    | Type         | Description                        | Constraints       |
|-----------|-------------|-------------------------------------|-------------------|
| artist_id | INT          | Unique identifier for the artist   | PRIMARY KEY        |
| name      | VARCHAR(120) | Artist or band name                |                    |

### Customer
| Column         | Type         | Description                        | Constraints       |
|----------------|-------------|-------------------------------------|-------------------|
| customer_id    | INT          | Unique identifier for the customer | PRIMARY KEY        |
| first_name     | VARCHAR(40)  | Customer first name                | NOT NULL           |
| last_name      | VARCHAR(20)  | Customer last name                 | NOT NULL           |
| company        | VARCHAR(80)  | Company name                       |                    |
| address        | VARCHAR(70)  | Street address                     |                    |
| city           | VARCHAR(40)  | City                               |                    |
| state          | VARCHAR(40)  | State or province                  |                    |
| country        | VARCHAR(40)  | Country                            |                    |
| postal_code    | VARCHAR(10)  | Postal/ZIP code                    |                    |
| phone          | VARCHAR(24)  | Phone number                       |                    |
| fax            | VARCHAR(24)  | Fax number                         |                    |
| email          | VARCHAR(60)  | Email address                      | NOT NULL           |
| support_rep_id | INT          | Assigned support representative    | FOREIGN KEY → Employee |

### Employee
| Column      | Type         | Description                        | Constraints       |
|-------------|-------------|-------------------------------------|-------------------|
| employee_id | INT          | Unique identifier for the employee | PRIMARY KEY        |
| last_name   | VARCHAR(20)  | Employee last name                 | NOT NULL           |
| first_name  | VARCHAR(20)  | Employee first name                | NOT NULL           |
| title       | VARCHAR(30)  | Job title                          |                    |
| reports_to  | INT          | Manager's employee_id              | FOREIGN KEY → Employee (self-referencing) |
| birth_date  | TIMESTAMP    | Date of birth                      |                    |
| hire_date   | TIMESTAMP    | Date hired                         |                    |
| address     | VARCHAR(70)  | Street address                     |                    |
| city        | VARCHAR(40)  | City                               |                    |
| state       | VARCHAR(40)  | State or province                  |                    |
| country     | VARCHAR(40)  | Country                            |                    |
| postal_code | VARCHAR(10)  | Postal/ZIP code                    |                    |
| phone       | VARCHAR(24)  | Phone number                       |                    |
| fax         | VARCHAR(24)  | Fax number                         |                    |
| email       | VARCHAR(60)  | Email address                      |                    |

### Genre
| Column   | Type         | Description                        | Constraints       |
|----------|-------------|-------------------------------------|-------------------|
| genre_id | INT          | Unique identifier for the genre    | PRIMARY KEY        |
| name     | VARCHAR(120) | Genre name (e.g., Rock, Jazz)      |                    |

### Invoice
| Column              | Type          | Description                        | Constraints       |
|---------------------|--------------|-------------------------------------|-------------------|
| invoice_id          | INT           | Unique identifier for the invoice  | PRIMARY KEY        |
| customer_id         | INT           | Customer who made the purchase     | FOREIGN KEY → Customer |
| invoice_date        | TIMESTAMP     | Date of the invoice                | NOT NULL           |
| billing_address     | VARCHAR(70)   | Billing street address             |                    |
| billing_city        | VARCHAR(40)   | Billing city                       |                    |
| billing_state       | VARCHAR(40)   | Billing state                      |                    |
| billing_country     | VARCHAR(40)   | Billing country                    |                    |
| billing_postal_code | VARCHAR(10)   | Billing postal code                |                    |
| total               | NUMERIC(10,2) | Total amount of the invoice        | NOT NULL           |

### InvoiceLine
| Column          | Type          | Description                                  | Constraints       |
|-----------------|--------------|----------------------------------------------|-------------------|
| invoice_line_id | INT           | Unique identifier for the invoice line item  | PRIMARY KEY        |
| invoice_id      | INT           | Reference to the invoice                     | FOREIGN KEY → Invoice |
| track_id        | INT           | Reference to the track purchased             | FOREIGN KEY → Track |
| unit_price      | NUMERIC(10,2) | Price per unit                               | NOT NULL           |
| quantity        | INT           | Number of units purchased                    | NOT NULL           |

### MediaType
| Column        | Type         | Description                                      | Constraints       |
|---------------|-------------|--------------------------------------------------|-------------------|
| media_type_id | INT          | Unique identifier for the media type             | PRIMARY KEY        |
| name          | VARCHAR(120) | Media type name (e.g., MPEG audio file, AAC)     |                    |

### Playlist
| Column      | Type         | Description                        | Constraints       |
|-------------|-------------|-------------------------------------|-------------------|
| playlist_id | INT          | Unique identifier for the playlist | PRIMARY KEY        |
| name        | VARCHAR(120) | Playlist name                      |                    |

### PlaylistTrack
| Column      | Type | Description                        | Constraints       |
|-------------|------|-------------------------------------|-------------------|
| playlist_id | INT  | Reference to the playlist          | COMPOSITE PRIMARY KEY, FOREIGN KEY → Playlist |
| track_id    | INT  | Reference to the track             | COMPOSITE PRIMARY KEY, FOREIGN KEY → Track |

### Track
| Column        | Type          | Description                                    | Constraints       |
|---------------|--------------|------------------------------------------------|-------------------|
| track_id      | INT           | Unique identifier for the track                | PRIMARY KEY        |
| name          | VARCHAR(200)  | Track name                                     | NOT NULL           |
| album_id      | INT           | Reference to the album                         | FOREIGN KEY → Album |
| media_type_id | INT           | Reference to the media type                    | FOREIGN KEY → MediaType, NOT NULL |
| genre_id      | INT           | Reference to the genre                         | FOREIGN KEY → Genre |
| composer      | VARCHAR(220)  | Composer(s) of the track                       |                    |
| milliseconds  | INT           | Track duration in milliseconds                 | NOT NULL           |
| bytes         | INT           | File size in bytes                             |                    |
| unit_price    | NUMERIC(10,2) | Price per track                                | NOT NULL           |

## Key Business Concepts

### Revenue and Sales
- Revenue is calculated from `invoice_line.unit_price * invoice_line.quantity`
- Total invoice amounts are stored in `invoice.total`
- Each invoice belongs to a customer via `invoice.customer_id`

### Music Catalog
- Tracks belong to albums via `track.album_id`
- Albums belong to artists via `album.artist_id`
- Tracks have genres via `track.genre_id`
- Tracks have media types via `track.media_type_id`

### Playlists
- Playlists contain tracks via the `playlist_track` junction table
- A track can appear in multiple playlists
- A playlist can contain multiple tracks

### Organization
- Employees have a hierarchical structure via `employee.reports_to`
- Customers are assigned support representatives via `customer.support_rep_id`
