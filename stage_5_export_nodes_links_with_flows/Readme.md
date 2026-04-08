# Stage 5 - Export Nodes & Links with Assigned Flows

## Overview

This module computes **rail network flows** from assigned OD paths and exports:

- **Link-level flows** (through-flows on edges)  
- **Node-level flows**:
  - Throughput (passing flows)  
  - Origin flows  
  - Destination flows  

Outputs are provided in both **CSV** and **GeoPackage (GPKG)** formats for analysis and visualization.

---

## Workflow
```
OD Paths (Node-Level Assignment)
↓
Read Rail Graph (Nodes + Edges)
↓
Chunked Processing of OD Paths
↓
Flow Accumulation:
- Link flows
- Node throughput
- Node origin/destination
↓
Merge with Spatial Layers
↓
Export (CSV + GPKG)
```

---

## Key Steps

### 1. Read Inputs
- OD paths:
  - `rail_od_paths_daily_COMBINED.csv`  
- Rail network:
  - Nodes and edges from GeoPackage  

- Builds lookup:
edge_fid → (FRFRANODE, TOFRANODE)


---

### 2. Chunked Flow Processing
- Reads OD paths in chunks (memory-efficient)
- For each chunk:
  - Aggregates **origin and destination flows**
  - Explodes `path_link_fids` → individual edges  
  - Maps edges to nodes  

---

### 3. Flow Accumulation

#### Link Flows
- For each edge:
  - Total tons and value  
  - Number of OD pairs using the link  

#### Node Flows
- **Throughput**: flow passing through node  
- **Origin**: flow starting at node  
- **Destination**: flow ending at node  

- Ensures:
  - Each OD path contributes **once per node** (deduplication)

---

### 4. Output Construction
- Merges flow results with spatial layers  
- Adds:
  - Coordinates (`x_lon`, `y_lat`)  
  - Flow attributes  

- Filters:
  - Removes links with zero flow  

---

## Outputs

### Nodes
- `nodes_with_flows.csv`  
- `nodes_with_flows.gpkg`  

Includes:
- Throughput flows  
- Origin/destination flows  
- Number of paths through node  

---

### Links
- `links_with_flows.csv`  
- `links_with_flows.gpkg`  

Includes:
- Total flow (tons & value)  
- Number of OD pairs per link  

---

## Notes

- Uses **chunked processing** for scalability  
- Ensures:
  - No double counting of node flows  
  - Consistent mapping between OD paths and network  

- Outputs serve as inputs for:
  - Disruption analysis  
  - Resilience modeling  