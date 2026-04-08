# Stage 2 - Rail Network Construction (FAF-Based)

## Overview

This module builds a **topologically consistent U.S. rail network graph** by integrating:

* FAF county-level freight flows
* North American rail line data
* FRA node identifiers (`FRANODEID`)

The output is a **network-ready graph (nodes + edges)** suitable for routing, simulation, and resilience analysis.

---

## Pipeline

```id="flow1"

Stage 1 — Yard Normalization + YARDS info in Continues USA in Counties 
        ↓
Stage 2 — M/I Backbone Extraction (Giant Component and Orphans)
        ↓
Stage 3 — Node Creation (YARD / END / JUNCTION)
        ↓
Stage 4 — O Nodes → M/I Connection Detection (30096 Nodes)
        ↓
Stage 5 — County Node Assignment:
        - Yard       = 1380
        - End        = 3061
        - O_Junction = 917
        - Junction   = 10905
        ↓
Stage 6 — Graph Construction (Nodes + Edges)
```
---

## Step Descriptions

### 1. Yard Normalization + YARDS info in Continuous USA in Counties
- Assigns rail links to counties via spatial join  
- Cleans and normalizes `YARDNAME` values within each county:
  - Removes duplicates and inconsistencies  
  - Uses fuzzy matching and substring logic  
  - Applies **Union-Find grouping** for robust merging  

- Outputs:
  - Normalized yard names  
  - County-level yard statistics:
    - `MIN_YARD_ID`, `MAX_YARD_ID`  
    - `NUM_YARDS`  

- Filters dataset:
  - Removes counties with **zero freight flow**  
  - Excludes **Alaska (CONUS-only analysis)**  

---

### 2. M/I Backbone Extraction (Giant Component and Orphans)
- Filters rail network to:
  - `NET = M` (Mainline)  
  - `NET = I` (Intermodal)  

- Builds a connectivity graph using link endpoints  
- Identifies:
  - **Giant component** → primary rail backbone  
  - **Orphan links** → disconnected sub-networks  

- Outputs:
  - Full M/I network  
  - Giant connected component  
  - Orphan links (for diagnostics)

---

### 3. Node Creation (YARD / END / JUNCTION)
- Generates network nodes using spatial and topological rules:

#### YARD Nodes
- Derived from normalized yard locations  
- Spatial clustering applied to group nearby yard geometries  
- Snapped to nearest **FRA node (`FRANODEID`)**

#### END Nodes
- Nodes with degree = 1 (network endpoints)

#### JUNCTION Nodes
- Nodes with degree ≥ 3 (network intersections)

- Conflict resolution:
  - YARD nodes take precedence over other node types  
  - END nodes near yards are removed  

- Outputs:
  - Node dataset with:
    - `NODE_TYPE` (YARD / END / JUNCTION)  
    - `FRANODEID` (authoritative identifier)  

---

### 4. O Nodes → M/I Connection Detection (30096 Nodes)
- Identifies where **O-network (other rail lines)** connects to the M/I backbone  

- Method:
  - Extract endpoints from all links (M, I, O)  
  - Cluster coincident points  
  - Detect junctions with:
    - Degree of freedom (DOF) ≥ 3  
    - Mixed network types (O + M/I)  

- Snaps detected junctions to FRA nodes  

- Output:
  - GeoPackage of **O–M/I connection nodes**

---

### 5. County Node Assignment
- Identifies counties that:
  - Have freight flow  
  - Lack YARD or END nodes  

- For those counties:
  - Assigns one **O_JUNCTION node**  
  - Selected as the closest junction to county centroid  

- Final node types:
  - `YARD`       = 1380  
  - `END`        = 3061  
  - `O_JUNCTION` = 917  
  - `JUNCTION`   = 10905  

- Ensures:
  - Every relevant county has at least one functional network node  

---

### 6. Graph Construction (Nodes + Edges)
- Builds final rail graph using **FRA node IDs**

#### Nodes
- Include only major nodes:
  - YARD, END, JUNCTION, O_JUNCTION  
- Each node has:
  - `FRANODEID`  
  - Node type  
  - Degree (number of connections)

#### Edges
- Constructed by:
  - Traversing rail links  
  - Merging sequences of **degree-2 intermediate nodes**  
  - Connecting only between major nodes  

- Edge attributes:
  - `FRFRANODE` → start node  
  - `TOFRANODE` → end node  
  - `LENGTH` (meters)  
  - `NUM_MERGED` (number of original links)  
  - `MERGED_OBJECTIDS` (traceability)

---

## Outputs

### Graph Data (GeoPackage)
- `Rail_Graph_Nodes_Edges.gpkg`
  - **nodes layer**
    - Node type (YARD / END / JUNCTION / O_JUNCTION)  
    - FRA node ID  
    - Degree  

  - **edges layer**
    - Start/end FRA node IDs  
    - Geometry (merged lines)  
    - Length and metadata  

---

## Notes

- All node IDs are based on **official FRA identifiers (`FRANODEID`)**
- The graph is:
  - **Topologically consistent**
  - **Connected (giant component)**
  - **Reduced (intermediate nodes removed)**

- Edge simplification ensures:
  - Efficient routing  
  - Reduced graph complexity  
  - Full traceability to original rail links  

- The pipeline integrates:
  - Spatial processing (GeoPandas)  
  - Graph theory (NetworkX)  
  - Clustering (DBSCAN, custom methods)  

---