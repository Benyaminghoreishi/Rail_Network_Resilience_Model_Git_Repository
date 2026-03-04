# Stage 1 – FAF Rail Freight Disaggregation to County Level

## Overview

This module performs spatial disaggregation of FAF (Freight Analysis Framework) rail freight flows from FAF zone-level origin–destination (OD) pairs to county-level OD flows. The process preserves total freight volumes while increasing spatial resolution for network-level modeling.

The script prepares freight demand inputs for subsequent rail network assignment and resilience analysis.

---

## Script

- `faf_county_flow_disaggregation.py`

---

## Purpose

FAF freight data is typically provided at aggregated FAF zone levels. However, network modeling requires demand at finer spatial resolution (county-to-county).  

This script converts:

FAF Zone → FAF Zone flows  

into:

County → County flows  

while preserving:

- Total tonnage
- Commodity structure (SCTG classification)
- Mode filtering (Rail mode only)

---

## Required Inputs

1. **FAF Freight Flow Dataset**
   - Origin FAF zone
   - Destination FAF zone
   - Mode (filtered to Rail – Mode 2)
   - Commodity (SCTG)
   - Freight tonnage and/or value

2. **Geographic Boundary Files**
   - FAF zone shapefile
   - County shapefile
   - Spatial crosswalk between FAF zones and counties

3. **Optional Supporting Data**
   - County population or economic weights (if weighted disaggregation is applied)

---

## Processing Steps

### Step 1 – Load Data
- Import FAF freight flow dataset
- Import spatial boundary files (FAF zones and counties)
- Clean column names and standardize identifiers

---

### Step 2 – Filter Rail Mode
- Select Mode 2 (Rail shipments only)
- Remove non-rail shipments
- Verify total tonnage after filtering

---

### Step 3 – Prepare FAF-to-County Mapping
- Identify counties within each FAF zone
- Create a crosswalk table linking:
  - FAF zone ID
  - County FIPS codes
- Compute allocation weights for each county within a FAF zone

Weights may be based on:
- Equal distribution
- Population
- Economic activity
- Freight proxy indicators

---

### Step 4 – Spatial Disaggregation

For each FAF OD pair:

1. Identify origin FAF zone counties
2. Identify destination FAF zone counties
3. Distribute total FAF flow across all county-to-county combinations
4. Apply proportional weights
5. Ensure total flow is preserved

Mathematically:

If:
F_ij = FAF flow from zone i to zone j

Then for counties c ∈ i and d ∈ j:

f_cd = F_ij × w_c × w_d

Where:
- w_c = origin county weight
- w_d = destination county weight

---

### Step 5 – Preserve Flow Consistency

- Validate that:
  - Sum of county-level flows = original FAF flow
- Check for rounding errors
- Correct minor discrepancies if needed

---

### Step 6 – Clean and Format Output

- Generate structured county-to-county OD matrix
- Include:
  - Origin county FIPS
  - Destination county FIPS
  - Commodity code
  - Tonnage
  - Optional freight value
- Export as CSV or data frame for Stage 2

---

## Outputs

- County-to-county freight flow dataset
- Rail-only demand matrix
- Spatially consistent OD demand file for network assignment

---

## Quality Checks Performed

- Total tonnage preservation
- No negative flows
- No missing counties
- Mode verification (Rail only)

---

## Role in Overall Framework

This stage establishes the demand foundation for:

- Network topology construction
- OD flow assignment
- Baseline performance evaluation
- Disruption and resilience modeling

Without accurate spatial disaggregation, downstream network analysis would misrepresent flow distribution and system vulnerability.

---

## Computational Considerations

- Computational complexity increases with number of counties per FAF zone
- Memory management may be required for large OD matrices
- Efficient merging and grouping operations are critical

---

## Summary

Stage 1 converts aggregated FAF rail freight flows into high-resolution county-level OD demand while preserving total freight volume and commodity structure. This step ensures spatial consistency between freight demand and the constructed rail network.
