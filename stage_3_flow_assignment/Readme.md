# Stage 3 - Rail Freight Flow Assignment Pipeline

## Overview

This pipeline converts **FAF freight demand** into **rail network flows** using a scalable, graph-based workflow.

It integrates:

* FAF county-level freight demand
* FRA-referenced rail network (FRANODEID)
* Spatial node mapping
* Network assignment with link-level tracking

The output is a **fully assigned rail flow network** suitable for:

* Resilience and disruption modeling
* Infrastructure criticality analysis
* Freight routing and flow visualization

---

## Pipeline Structure

```
Stage 1 — County Flow Aggregation (Aggregated County to County CSV File)
        ↓
Stage 2 — County Freight to Rail Node Allocator → (FAF Rail OD Matrix Generator)
        ↓
Stage 3 — Node-Level OD Generation (Links have Summation of Commodity Volumes and Values)
        ↓
Stage 4 — Create Presentation-Quality Animated GIF for Origin 301117
```
---


---

## Stage Descriptions

### Stage 1 — County Flow Aggregation
- Input:
  - County-level FAF flows disaggregated by commodity (SCTG groups)

- Process:
  - Aggregates flows across all commodity groups (SCTG5 → total)
  - Groups by:
    - Origin county (`dms_orig_cnty`)
    - Destination county (`dms_dest_cnty`)
  - Sums:
    - Tons (2024, 2050)  
    - Value (2024, 2050)

- Data cleaning:
  - Removes OD pairs with **all-zero flows**  
  - Removes **Alaska-related flows (CONUS-only)**  

- Output:
  - `county_od_all_sctg_aggregated.csv`  
  - ~4.7M county OD pairs (non-zero flows)

---

### Stage 2 — County Freight to Rail Node Allocator  
*(FAF Rail OD Matrix Generator)*

- Objective:
  - Map county-level demand to **rail network nodes (FRANODEID)**  

- Node selection hierarchy:
  1. **YARD nodes** (preferred)  
  2. **END nodes**  
  3. **O_JUNCTION nodes**  
  4. **Nearest node (fallback)**  

- Process:
  - Finds nodes within each county via spatial intersection  
  - Uses caching to improve performance  
  - Expands each county OD pair into multiple **node OD pairs**

- Flow allocation:
\[
\text{Flow per node pair} = \frac{\text{County flow}}{\text{(\# origin nodes × \# destination nodes)}}
\]

- Outputs:
  - `rail_od_pairs_from_nodes.csv`  
  - `rail_od_pairs_from_nodes.gpkg`  

- Includes:
  - Node labels and `FRANODEID`  
  - Tons and value (2024 & 2050)  
  - Geometry (origin–destination lines)  

- Validation:
  - All node IDs verified against:
    - Node layer  
    - FRA reference dataset  

---

### Stage 3 — Node-Level OD Generation  
*(Link Flow Assignment with Path Tracking)*

- Converts node-level OD demand into **network flows**

#### Graph Construction
- Builds a **NetworkX graph**:
  - Nodes → `FRANODEID`  
  - Edges → rail links  
  - Weight → link length (miles)

#### Shortest Path Assignment
- Uses:
  - **Single-source Dijkstra** per origin node  
- Computes:
  - Shortest paths to all destinations  
  - Travel time (based on assumed speed)  

#### Flow Propagation
- Assigns flows along each path:
  - Tons/day  
  - Value/day  

- Accumulates flows per link:
\[
\text{Link Flow} = \sum_{\text{all OD paths using link}} \text{OD flow}
\]

#### Key Enhancement: Link Tracking
- Each path stores:
  - `path_link_fids` (list of edge IDs)  
- Enables:
  - Fast disruption simulation  
  - Link-level dependency analysis  

#### Outputs

1. **OD Paths by Origin**
   - Individual CSV files per origin node  
   - Optional GeoPackages for validation  

2. **Combined OD Paths**
   - `rail_od_paths_daily_COMBINED.csv`  

3. **Link Flow Network**
   - `rail_link_flows_daily_ALL_LINKS.gpkg`  
   - Includes:
     - Daily tons and value  
     - Number of OD paths per link  
     - Full edge attributes  

---

### Stage 4 — Create Presentation-Quality Animated GIF for Origin 301117

- Visualizes:
  - All destination flows from a single origin node  

- Features:
  - Animated path drawing  
  - Node-type-based color coding:
    - YARD → cyan  
    - END → orange  
    - JUNCTION → green  
    - O_JUNCTION → yellow  

- Displays:
  - Cumulative tons and value  
  - Travel time statistics  
  - Path progression over time  

- Output:
  - High-resolution animated GIF  
  - Designed for presentations and communication  

---

## Outputs Summary

### Tabular Outputs
- `county_od_all_sctg_aggregated.csv`  
- `rail_od_pairs_from_nodes.csv`  
- `rail_od_paths_daily_COMBINED.csv`  

### Spatial Outputs
- `rail_od_pairs_from_nodes.gpkg`  
- `rail_link_flows_daily_ALL_LINKS.gpkg`  

### Visualization
- Animated GIF (origin-based flow visualization)

---

## Notes

- Units:
  - Tons → thousand tons (converted to tons/day)  
  - Value → million USD (converted to daily value)  

- The pipeline ensures:
  - **Mass conservation from FAF → network level**  
  - **Full traceability (county → node → link)**  
  - **Compatibility with disruption and resilience models**  

- Performance considerations:
  - Node caching significantly reduces runtime  
  - Path computation is parallelizable by origin  
  - Link tracking enables fast post-processing  

---