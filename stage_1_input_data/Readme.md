# Stage 1 - FAF Rail Freight → County-Level Flow Processing

## Overview

This module processes **FAF5.7.1 rail freight data** and converts it from **FAF zone-level OD flows** into **county-to-county freight flows** for the U.S.

It preserves:

* Total freight tons and value
* Commodity structure (SCTG)
* OD relationships

Outputs are designed for:

* Network assignment
* GIS visualization
* Freight corridor analysis
* Resilience modeling

---

## Workflow

```
Stage 1 — FAF Raw Data
    ↓
Stage 2 — Rail Filtering (Mode 2) and Commodity Aggregation (SCTG → 5 groups)
    ↓
Stage 3 — Visualization (2024 / 2050 / Comparison)
    ↓
Stage 4 — FAF Zone → County Disaggregation (For 5 different commodity types)
    ↓
Stage 5 — County Flow Vectorization and Spatial Output (GeoPackage)
    ↓
Stage 6 — Validation & Sanity Checks
```


---

## Step Descriptions

### 1. FAF Raw Data
- Reads **FAF5.7.1 dataset**
- Extracts required fields:
  - FAF origin and destination zones  
  - Commodity (SCTG2)  
  - Mode and trade type  
  - Tons and value (2024 & 2050)

---

### 2. Rail Filtering & Commodity Aggregation
- Filters data to **rail mode (Mode = 2)**
- Aggregates **SCTG2 commodities into 5 groups**:
  - `sctg0109` — Agricultural products  
  - `sctg1014` — Mining & construction materials  
  - `sctg1519` — Energy products  
  - `sctg2033` — Chemicals, wood, and metals  
  - `sctg3499` — Manufactured goods and mixed freight  

- Aggregates flows by:
  - Origin–destination pairs  
  - Trade type  
  - Commodity group  

---

### 3. Visualization (2024 / 2050 / Comparison)
- Generates comparative plots for:
  - SCTG-level flows  
  - Aggregated commodity groups  
- Displays:
  - Freight volume (million tons)  
  - Freight value (million USD)  
- Supports both **single-year** and **side-by-side comparison (2024 vs 2050)**

---

### 4. FAF Zone → County Disaggregation
- Converts FAF zone-level OD flows into **county-level OD flows**
- Uses:
  - Origin allocation factors  
  - Destination allocation factors  

- Method:
  - Expands each FAF OD pair into multiple county pairs  
  - Applies proportional allocation:

\[
\text{County Flow} = \text{FAF Flow} \times f_{orig} \times f_{dest}
\]

- Ensures:
  - Total tons and values are preserved after disaggregation  

---

### 5. County Flow Vectorization & Spatial Output
- Converts OD tables into **county-level flow vectors**:
  - Outbound flows (to destination counties)  
  - Inbound flows (from origin counties)  

- Merges results with U.S. county shapefile
- Outputs:
  - **GeoPackage (.gpkg)** with:
    - Geometry  
    - Flow vectors  
    - Commodity-specific attributes  

---

### 6. Validation & Sanity Checks
- Performs multiple consistency checks:
  - FAF totals vs county-level totals  
  - OD pair validation (CSV vs GeoPackage)  
  - Global inbound vs outbound balance  

- Additional checks include:
  - Non-zero flow counts  
  - Maximum flow inspection  
  - Difference tracking for allocation accuracy  

---

## Outputs

### Tabular Outputs
- `county_level_<sctg>.csv` (per commodity group)  
- `county_level_all_categories.csv`  
- `county_level_summary_2024_2050.csv`  

### Spatial Output
- `county_level_with_faf_flows.gpkg`  
  - County geometries with inbound/outbound flow attributes  

### Figures
- 6 visualization plots (PNG format)

---

## Notes

- Units:
  - **Tons** → thousand tons (FAF standard)  
  - **Value** → million 2017 USD  

- The pipeline:
  - Preserves **mass balance across transformations**
  - Uses **modular steps for reproducibility**
  - Supports **scenario comparison (2024 vs 2050)**

---