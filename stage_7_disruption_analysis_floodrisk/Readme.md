# Stage 7 — Flood Risk Disruption Analysis

## Overview

This module evaluates **rail network resilience under flood risk** by integrating:

- Flood-risk scores (FRA segments)
- Link-level freight flows
- Network disruption and rerouting

It consists of **four independent blocks**, each performing a key step in the analysis.

---

## Workflow

```
Flood Risk Segments + Link Flows
↓
Block 1 — Spatial Join (Risk → Links)
↓
Block 2 — Disruption (Max Risk)
↓
Block 3 — Disruption (Sum Risk)

Block 4 — Resilience Curve (Max & Sum)

```


---

## Block Descriptions

### Block 1 — Spatial Join: Risk → Links
- Integrates **flood-risk scores with rail links**
- For each link:
  - `link_Max_Risk_Score` → maximum intersecting risk  
  - `link_Sum_Risk_Score` → cumulative risk  
  - `n_risk_segments` → number of intersecting segments  

- Key features:
  - Uses **spatial intersection (GeoPandas sjoin)**  
  - Handles CRS alignment  
  - Ensures missing values → 0  

- Outputs:
  - `links_with_flows_riskscores.csv`  
  - `links_with_flows_riskscores.gpkg`  

---

### Block 2 — FloodRisk_Max (Disruption + Resilience)
- Ranks links by **maximum flood risk score**
- Applies **cumulative disruption scenarios**:
  - Step 1 → remove highest-risk links  
  - Step k → remove top-k risk levels  

- Key processes:
  - Identify affected OD pairs  
  - Reroute using **Dijkstra shortest path**  
  - Detect infeasible OD pairs  

- Computes resilience metrics:
  - Network functionality \(F\)  
  - Reachability  
  - Infeasible demand (value/day)  
  - OD classification (unaffected / delayed / infeasible)  

- Outputs:
  - OD results per step (CSV)  
  - Network snapshots (GPKG)  
  - Plots (functionality, reachability, losses)  

---

### Block 3 — FloodRisk_Sum (Disruption + Resilience)
- Same structure as Block 2  
- Difference:
  - Links ranked by **cumulative (sum) flood risk**  

- Purpose:
  - Compare **localized extreme risk (Max)** vs  
    **distributed cumulative risk (Sum)**  

- Outputs:
  - Parallel results to Block 2  
  - Separate resilience metrics and plots  

---

### Block 4 — Combined Comparison (Max vs Sum)
- Compares results from Blocks 2 and 3  

- Generates combined figures:
  - Network functionality vs disruption  
  - Reachability vs disruption  
  - Value loss vs disruption  
  - Cumulative disrupted links  
  - OD classification  

- Key insight:
  - Highlights differences between **risk definitions**  
  - Supports interpretation of **system vulnerability patterns**  

---

## Outputs Summary

### Data
- Link-level risk-enhanced network  
- OD disruption results (per step, per scenario)  
- Resilience summary tables  

### Figures
- Scenario-specific plots (Max, Sum)  
- Combined comparison plots  

---

## Notes

- Disruptions are **cumulative and scenario-based**  
- Flow updates follow:
\[
\text{Post-flow} = \text{Baseline} - \text{Original} + \text{Rerouted}
\]

- Designed for:
  - Large-scale networks  
  - Efficient rerouting and evaluation  
  - Comparative resilience analysis  

---