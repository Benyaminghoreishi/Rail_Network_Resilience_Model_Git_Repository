# 🚆 The U.S. Freight Rail Resilience Modeling Framework

## 📌 Overview

This repository implements a **complete end-to-end framework** for modeling, assigning, and analyzing **rail freight flows in the U.S.** using FAF data and network-based methods.

It transforms raw freight data into a **fully assigned rail network** and evaluates **system performance and resilience under disruptions**.

---

## 🧠 What This Project Does

This framework integrates:

- 📦 FAF freight demand (county-level)
- 🛤️ U.S. rail network (FRA-based)
- 📍 Spatial allocation & node mapping
- 🔗 Graph-based flow assignment
- ⚠️ Disruption and resilience analysis

---

## 🔄 Full Pipeline

```
FAF Data
↓
Stage 1 — County-Level Freight Flows
↓
Stage 2 — Rail Network Construction
↓
Stage 3 — Flow Assignment (OD → Network)
↓
Stage 4 — Baseline Performance Analysis
↓
Stage 5 — Export Network with Flows
↓
Stage 6 — Targeted Disruption Analysis
↓
Stage 7 — Flood Risk Disruption Analysis
```

---

## 📂 Project Structure

```
stage_1_input_data/
stage_2_network_preprocessing/
stage_3_flow_assignment/
stage_4_baseline_performance/
stage_5_export_nodes_links_with_flows/
stage_6_disruption_analysis_value2024/
stage_7_disruption_analysis_floodrisk/
```


Each stage is modular and can be run independently.

---

## 🧩 Stage Summary

### 📊 Stage 1 — FAF → County Flows
- Converts FAF zone-level data into **county-to-county flows**
- Preserves:
  - Tons, value, commodities
- Outputs:
  - CSV + GeoPackage datasets 

👉 See Stage 1 README for details

---

### 🛤️ Stage 2 — Rail Network Construction
- Builds **topologically consistent rail graph**
- Uses:
  - FRA nodes (`FRANODEID`)
  - Rail geometries
- Outputs:
  - Nodes + edges (GeoPackage)  

👉 See Stage 2 README for details

---

### 🔗 Stage 3 — Flow Assignment
- Maps county demand → rail nodes
- Assigns flows using **shortest-path routing**
- Tracks:
  - Link usage (`path_link_fids`)
- Outputs:
  - OD paths + link flows  

👉 See Stage 3 README for details

---

### 📈 Stage 4 — Baseline Performance
- Evaluates network under normal conditions
- Computes:
  - Travel time, ton-hours, feasibility  
- Outputs:
  - Summary statistics + plots  

👉 See Stage 4 README for details

---

### 🌐 Stage 5 — Export Nodes & Links with Flows
- Aggregates flows to:
  - **Links (through-flows)**
  - **Nodes (origin/destination/throughput)**
- Outputs:
  - CSV + GeoPackage  

👉 See Stage 5 README for details

---

### ⚠️ Stage 6 — Disruption Analysis
- Simulates disruptions:
  - Links and nodes (top % by importance)
- Recomputes:
  - Paths, feasibility, flow redistribution
- Outputs:
  - Resilience metrics + scenarios  

👉 See Stage 6 README for details

---

### 🌊 Stage 7 — Flood Risk Analysis
- Integrates **flood-risk scores with rail network**
- Runs two scenarios:
  - Max risk (localized extremes)
  - Sum risk (cumulative exposure)
- Outputs:
  - Resilience curves + comparison plots  

👉 See Stage 7 README for details

---

## 📊 Key Concepts

- **Mass Conservation**  
  Freight totals remain consistent across transformations  

- **Graph-Based Routing**  
  Uses NetworkX + Dijkstra for scalable assignment  

- **Traceability**  
  County → Node → Link mapping is preserved  

- **Resilience Metrics (OD Level - (Value×Travel Time))**
\[
F = \frac{1}{K} \sum f_k
\]

- **Flow Update under Disruption (Link Level)**
\[
\text{Post-flow} = \text{Baseline} - \text{Original} + \text{Rerouted}
\]

---

## ⚙️ Requirements

- Python 3.9+
- Key libraries:
  - `pandas`
  - `geopandas`
  - `networkx`
  - `numpy`
  - `matplotlib`
  - `seaborn`

---

## 🚀 How to Run

Run stages sequentially:

1. Start from **Stage 1**
2. Proceed step-by-step through Stage 7  
3. Each stage produces inputs for the next  

💡 Tip: Each stage has its own README for detailed instructions.

---

## 📌 Applications

- 🚆 Freight network modeling  
- 🛡️ Infrastructure resilience analysis  
- 🌊 Extreme hazards risk assessment (flood impacts)  
- 📍 Corridor and bottleneck identification  

---

## 🧾 Notes

- All paths use **relative structure (`base_dir`)**
- Designed for **large-scale datasets (millions of OD pairs)**
- Modular design supports:
  - Scenario testing  
  - Model extensions  
  - Policy analysis  

---

## ✨ Final Thought

This framework provides a **fully integrated pipeline** from raw freight data to **network-level resilience insights**, enabling both **academic research** and **practical infrastructure analysis**.

---

## 📌 Citation and Acknowledgements

If you use or adapt this code, please cite the associated manuscript:

> [Manuscript Title Placeholder]  
> [Journal / Status Placeholder]

**Acknowledgements (project-level):**  
This work was supported through the Federal Railroad Administration (FRA) research context described in the manuscript and associated rail resilience initiatives. Please refer to the manuscript acknowledgements for official wording.

---



## 📩 Contact
For questions, reproducibility support, or collaboration:

**Benyamin Ghoreishi**  
Email: `ghoreisb@oregonstate.edu`
