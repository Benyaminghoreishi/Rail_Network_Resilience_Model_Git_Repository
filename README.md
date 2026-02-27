# Rail Network Resilience Model

## Overview
This project develops a comprehensive framework for assessing the resilience of a national rail freight network under targeted and hazard-driven disruptions. The model integrates freight demand disaggregation, network construction, flow assignment, system performance evaluation, and post-disruption resilience analysis.

The workflow is organized into five stages:

---

## Framework Stages

### Stage 1 — Input Data
- Railroad network (main lines and major industrial leads)
- FAF freight demand (OD flows)
- Disruption scenarios:
  - Targeted node removal
  - Targeted link removal
  - Flood-induced disruption

### Stage 2 — Network, Demand, and Preprocessing
- Spatial disaggregation of FAF flows (zone → county level)
- Railroad network topology construction
- Hierarchical county-to-rail access assignment

### Stage 3 — Baseline Flow Assignment
- Shortest travel-time path assignment
- Multiple OD flows may share links
- Identification of infeasible OD pairs

### Stage 4 — Baseline System Performance
- OD-level performance metrics:
  - Ton-hours
  - Value-hours
- System feasibility
- Network functionality and resilience reference state

### Stage 5 — Post-Disruption Performance & Resilience
- Simulation of disruption types
- Classification of OD flows:
  - Unaffected
  - Delayed
  - Infeasible
- Network-level functionality metrics
- Resilience curve generation

---

## Key Outputs
- Baseline and disrupted system performance metrics
- OD-level delay and feasibility classification
- Network-level functionality measures
- Resilience curves under different disruption scenarios
- Visualization and presentation outputs (e.g., GIF animations)

---

## Purpose
This framework supports infrastructure resilience assessment, disruption impact analysis, and freight system risk evaluation for large-scale rail networks.

---

## Author
For questions, reproducibility support, or collaboration:

Benyamin Ghoreishi
Email: ghoreisb@oregonstate.edu