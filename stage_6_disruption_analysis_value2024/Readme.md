# Stage 6 — Targeted Disruption Analysis & Resilience Evaluation

## Overview

This stage evaluates **rail network resilience** under disruption scenarios using the baseline assigned flows.

It consists of two main steps:

- **Step 0**: Prepare baseline paths (node sequences)  
- **Step 2**: Run disruption scenarios and compute resilience metrics  

---

## Workflow

```
Baseline OD Paths (with link paths)
↓
STEP 0 — Add Node Paths (path_node_fids)
↓
STEP 2 — Disruption Scenarios (Links + Nodes)
↓
Rerouting + Infeasibility Detection
↓
Resilience Metrics Calculation
↓
Outputs (CSV, GPKG, Figures)

```


---

## Step Descriptions

### STEP 0 — Add Node Paths (`path_node_fids`)
- Converts:
  - `path_link_fids` → `path_node_fids`

- Method:
  - Uses edge lookup:
    ```
    edge_fid → (FRFRANODE, TOFRANODE)
    ```
  - Reconstructs full node sequences for each OD path  

- Purpose:
  - Enables **node-based disruption analysis**
  - Avoids re-running shortest path algorithms  

---

### STEP 2 — Disruption Analysis (Links + Nodes)

#### Scenarios
- **Link disruptions** (ranked by flow value)  
- **Node disruptions** (ranked by throughput)  

- Disruption levels:
0.5% → 15% (incremental)


---

#### Process

1. **Select disrupted elements**
   - Top X% of links or nodes based on flow

2. **Identify affected OD pairs**
   - OD paths that use disrupted links/nodes  

3. **Recompute paths (Dijkstra)**
   - If path exists → rerouted  
   - If no path → infeasible  

4. **Update flows**
\[
\text{Post-flow} = \text{Baseline} - \text{Original} + \text{Rerouted}
\]

---

## Resilience Metrics

For each disruption level:

- **Network functionality**
\[
F = \frac{1}{K} \sum f_k
\]

- **Reachability**
  - Fraction of OD pairs still connected  

- **OD classification**
  - Unaffected  
  - Delayed  
  - Infeasible  

- **Economic impact**
  - Daily value loss (infeasible flows)  

---

## Outputs

### Disruption Results
- `od_paths_<Scenario>_<Xpct>.csv`
  - Only affected OD pairs  
  - Includes rerouted and infeasible cases  

### Spatial Outputs (Optional)
- `network_<Scenario>_<Xpct>.gpkg`
  - Updated link and node flows  
  - Separate layers:
    - Remaining  
    - Disrupted  

---

### Resilience Outputs
- `resilience_summary_recomputed.csv`

### Figures
- Network functionality curve  
- Reachability curve  
- OD classification (stacked)  
- Economic loss  

---

## Notes

- Uses **value (2024)** as primary metric  
- Fully preserves:
  - OD structure  
  - Flow conservation (via delta method)  

- Designed for:
  - Large-scale networks  
  - Memory-efficient processing  
  - Scenario-based resilience analysis  

---