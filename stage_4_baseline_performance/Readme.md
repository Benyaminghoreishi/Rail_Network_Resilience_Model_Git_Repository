# Stage 4 — Baseline System Performance and Functionality

## Overview

This stage evaluates the **baseline performance of the rail freight network** after flow assignment.

It computes:

- OD-level performance metrics  
- Network feasibility (served vs unserved OD pairs)  
- Flow distribution by node type and county  
- Summary statistics and visualization outputs  

---

## Workflow

```
Assigned OD Paths (Feasible)
+
Original OD Pairs
↓
OD-Level Metrics Calculation
↓
Feasibility Analysis (φ₀)
↓
Breakdown by Node Type
↓
Breakdown by County (Origin + Destination)
↓
Summary Statistics + Reports + Figures

```


---

## Key Components

### 1. OD-Level Performance Metrics
- Computes:
  - **Total ton-hours**  
  - **Total value-hours**  
  - **Total daily tons and value**  
  - **Average travel time and path length**  

- Includes:
  - Weighted metrics (by tons)  
  - Results for both **2024 and 2050**

---

### 2. Baseline Feasibility

- Defines:
\[
\phi_0 = \frac{K_f}{K}
\]

Where:
- \(K\) = total OD pairs  
- \(K_f\) = feasible OD pairs  

- Outputs:
  - Number of feasible and infeasible OD pairs  
  - Feasibility percentage  
  - Share of demand (tons/value) that is infeasible  

---

### 3. Breakdown by Node Type

- Groups flows by:

Origin Node Type → Destination Node Type


- Computes:
  - Number of OD pairs  
  - Tons and value  
  - Ton-hours and value-hours  
  - Average travel time and distance  

---

### 4. Breakdown by County

- Aggregates flows by:
  - **Origin county**
  - **Destination county**

- Outputs:
  - Total tons and value (origin + destination)  
  - County-level contribution to network demand  

---

## Outputs

### Tables
- `baseline_summary_statistics.csv`  
- `baseline_breakdown_by_nodetype.csv`  
- `baseline_breakdown_by_county.csv`  
- `baseline_feasibility_report.csv`  

### Figures
- Feasibility pie chart  
- OD type combination bar chart  
- Top origin/destination counties  

---

## Notes

- Units:
  - Tons → tons/day  
  - Value → USD/day  
  - Time → hours  

- This stage provides the **baseline benchmark** for:
  - Disruption analysis  
  - Network resilience evaluation  