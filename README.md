# Smart Bus Stop Dashboard

This project implements a small end-to-end data pipeline and visualization system for bus operations.
It ingests raw bus telemetry data, derives operational indicators, and presents them through a web dashboard and exportable reports.

The system is implemented as a Django web application and is designed to be runnable entirely through Docker.

---

## System Overview

The application processes bus data in three stages:

1. **Data ingestion**
2. **Derived metric computation**
3. **Visualization and export**

Raw input data (CSV) contains per-vehicle GPS and operational attributes.  
From this data, the system computes:

- **Crowding level** (estimated occupancy)
- **Estimated Time of Arrival (ETA)** to a selected bus stop

All raw and derived data are stored in a relational database and can be inspected via the Django admin interface.

---

## Data Flow

**CSV Upload → Database → Dashboard / XLSX Export**

1. A user uploads a CSV file containing bus telemetry data.
2. Each row is parsed and stored as a `GPSRecord`.
3. For each GPS record:
   - A **crowding record** is derived using vehicle capacity and load weight.
   - An **ETA record** is derived using distance to a bus stop and current speed.
4. The dashboard queries the most recent records per bus and visualizes trends.
5. The same data can be exported as an Excel file.

---

## Core Data Models

The system is built around five core entities:

- **Bus**  
  Represents a vehicle (unique bus ID and capacity).

- **BusStop**  
  Represents a physical stop with geographic coordinates.

- **GPSRecord**  
  Raw telemetry data for a bus at a specific timestamp  
  (location, speed, optional weight).

- **CrowdingRecord**  
  Derived from a GPS record.  
  Stores estimated occupancy ratio and categorical crowding level.

- **ETARecord**  
  Derived from a GPS record and a bus stop.  
  Stores distance and estimated arrival time.

Relationships:
- One bus has many GPS, crowding, and ETA records.
- One bus stop can have ETA records from many buses.

An ERD diagram is provided in `docs/erd.png`.

---

## Crowding Estimation Logic

Crowding is estimated deterministically from vehicle weight:

- Assumed average passenger weight: **75 kg**
- Estimated passengers = `vehicle_weight / 75`
- Occupancy ratio = `estimated_passengers / bus_capacity`

Crowding levels:
- `< 0.5` → LOW
- `< 0.8` → MEDIUM
- `< 1.0` → HIGH
- `>= 1.0` → OVERCROWDED

This logic is intentionally simple and transparent.

---

## ETA Computation Logic

ETA is computed using:

- **Haversine distance** between current bus location and selected stop
- **Instantaneous speed** from the GPS record

Steps:
1. Compute distance (meters) using latitude/longitude.
2. Convert speed from km/h to m/s.
3. ETA = `distance / speed`

If speed is too low (or zero), ETA is recorded as unavailable.

---

## Web Interface

### Home
`/`

Entry point with links to all major functions.

---

### Data Upload
`/upload/`

- Accepts a CSV file.
- Each upload is processed row-by-row.
- Displays a summary of how many records were read, inserted, or skipped.

Expected CSV header:
```csv
bus_id,timestamp,lat,lon,speed,capacity,weight,stop_id,stop_name,stop_lat,stop_lon
