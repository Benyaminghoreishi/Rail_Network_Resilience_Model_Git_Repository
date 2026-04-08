#%%

import geopandas as gpd
import pandas as pd
import networkx as nx
import os, time, gc, warnings
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ── Paths ────────────────────────────────────────────────────────────────────
base_dir = os.path.abspath(os.path.join(".."))

BASELINE_CSV = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "rail_od_paths_daily_COMBINED.csv",
)
RAIL_GRAPH_GPKG = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Rail_Graph", "Rail_Graph_Nodes_Edges.gpkg",
)
NODES_WITH_FLOWS_CSV = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Disruption_Scenario_Inputs", "nodes_with_flows.csv",
)
LINKS_WITH_FLOWS_CSV = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Disruption_Scenario_Inputs", "links_with_flows.csv",
)
NODES_WITH_FLOWS_GPKG = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Disruption_Scenario_Inputs", "nodes_with_flows.gpkg",
)
LINKS_WITH_FLOWS_GPKG = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Disruption_Scenario_Inputs", "links_with_flows.gpkg",
)
DISRUPTION_BASE_DIR = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Disruption_Scenarios_Value2024_15pct",
)
RESILIENCE_OUTPUT_DIR = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Resilience_Analysis_Value2024_15pct",
)


# %%
#  read and then print the columns names of all above files
baseline_df = pd.read_csv(BASELINE_CSV)
print("Baseline CSV columns:", baseline_df.columns.tolist())

# sum of value_hours_2024 column in baseline_df
total_value_hours_2024 = baseline_df["value_hours_2024"].sum()
print("Total value hours in 2024:", total_value_hours_2024)

rail_graph_gpkg = gpd.read_file(RAIL_GRAPH_GPKG, layer="edges")
print("Rail Graph GPKG columns:", rail_graph_gpkg.columns.tolist())

nodes_with_flows_csv = pd.read_csv(NODES_WITH_FLOWS_CSV)
print("Nodes with Flows CSV columns:", nodes_with_flows_csv.columns.tolist())

# Sum of the throughput_value_2024 column in nodes_with_flows_csv
total_throughput_value_2024 = nodes_with_flows_csv["throughput_value_2024_day"].sum()
print("Total throughput value in 2024:", total_throughput_value_2024)

links_with_flows_csv = pd.read_csv(LINKS_WITH_FLOWS_CSV)
print("Links with Flows CSV columns:", links_with_flows_csv.columns.tolist())

# SUm of the flow_value_2024_day column in links_with_flows_csv
total_flow_value_2024 = links_with_flows_csv["flow_value_2024_day"].sum()
print("Total flow value in 2024:", total_flow_value_2024)

nodes_with_flows_gpkg = gpd.read_file(NODES_WITH_FLOWS_GPKG)
print("Nodes with Flows GPKG columns:", nodes_with_flows_gpkg.columns.tolist())

links_with_flows_gpkg = gpd.read_file(LINKS_WITH_FLOWS_GPKG)
print("Links with Flows GPKG columns:", links_with_flows_gpkg.columns.tolist())



# %%
# Please read "C:\Users\ghoreisb\Box\Oregon State University\0000- Research_OSU\1_Rail_Project\13_Resiliency\FAF\Processed_Data\County_Level\Disruption_Scenarios_Value2024_15pct\Nodes_Value2024\Frac_0.5pct\od_paths_Nodes_Value2024_0.5pct.csv" file and print the columns names and the first 5 rows of the file.
disruption_csv_path = os.path.join(
    DISRUPTION_BASE_DIR, "Nodes_Value2024", "Frac_0.5pct", "od_paths_Nodes_Value2024_0.5pct.csv"
)
disruption_df = pd.read_csv(disruption_csv_path)
print(disruption_df.head(5))
# print the sum of the value_hours_2024 column in disruption_df
total_disrupted_value_hours_2024 = disruption_df["value_hours_2024"].sum()
print("Total disrupted value hours in 2024 for 0.5% disruption:", total_disrupted_value_hours_2024)
#%%

import pandas as pd
import numpy as np
import os

# ================================
# PATHS (EDIT IF NEEDED)
# ================================
BASELINE_CSV = r"PATH_TO_YOUR_BASELINE_CSV"

DISRUPTION_BASE_DIR = r"PATH_TO_DISRUPTION_BASE_DIR"

disruption_csv_path = os.path.join(
    DISRUPTION_BASE_DIR,
    "Nodes_Value2024",
    "Frac_0.5pct",
    "od_paths_Nodes_Value2024_0.5pct.csv"
)

# ================================
# LOAD DATA
# ================================
baseline_df = pd.read_csv(BASELINE_CSV)
disruption_df = pd.read_csv(disruption_csv_path)

print(f"Baseline rows: {len(baseline_df):,}")
print(f"Disrupted rows (affected only): {len(disruption_df):,}")

# ================================
# KEEP ONLY REQUIRED COLUMNS
# ================================
df_bl = baseline_df[
    ["origin_franodeid", "destination_franodeid", "value_hours_2024", "value_2024_day"]
].rename(columns={
    "value_hours_2024": "vh_bl",
    "value_2024_day": "val"
})

df_dis = disruption_df[
    ["origin_franodeid", "destination_franodeid", "value_hours_2024"]
].rename(columns={
    "value_hours_2024": "vh_dis"
})

# ================================
# MERGE (KEY STEP)
# ================================
df = df_bl.merge(
    df_dis,
    on=["origin_franodeid", "destination_franodeid"],
    how="left"
)

# Fill missing (unaffected OD pairs)
df["vh_dis"] = df["vh_dis"].fillna(df["vh_bl"])

# ================================
# COMPUTE DELTA
# ================================
infeasible = np.isinf(df["vh_dis"]) | df["vh_dis"].isna()

delta = df["vh_dis"] - df["vh_bl"]

# IMPORTANT: clamp negative values
delta = np.clip(delta, 0, None)

# ================================
# COMPUTE f_k (PERFORMANCE PER OD)
# ================================
f_k = np.where(infeasible, 0.0, 1.0 / (1.0 + delta))

# ================================
# FINAL METRICS
# ================================
K = len(df)

F = f_k.sum() / K
reachability = np.sum(~infeasible) / K

# ================================
# DEBUG CHECKS
# ================================
print("\n===== DEBUG CHECKS =====")
print(f"Min f_k: {f_k.min():.6f}")
print(f"Max f_k: {f_k.max():.6f}")

if f_k.max() > 1:
    print("⚠️ ERROR: f_k > 1 detected!")

# ================================
# RESULTS
# ================================
print("\n===== RESULTS =====")
print(f"F (Network Performance): {F:.6f}")
print(f"Reachability: {reachability:.6f}")

# ================================
# OPTIONAL: CLASSIFICATION
# ================================
df["status"] = np.where(infeasible, "infeasible",
                np.where(delta == 0, "unaffected", "delayed"))

print("\n===== COUNTS =====")
print(df["status"].value_counts())