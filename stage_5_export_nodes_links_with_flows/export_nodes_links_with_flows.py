# %%
#! ============================================================================
#! export_nodes_links_with_flows.py
#!
#! Computes rail network flows from OD paths: link through-flows for edges and
#! node through-flows plus origin and destination flows for nodes.
#! ============================================================================

import os
import time
import warnings

import geopandas as gpd
import pandas as pd

warnings.filterwarnings("ignore")

# ============================================================================
# CONFIGURATION
# ============================================================================

base_dir = os.path.abspath(os.path.join("..", ".."))

OD_PATHS_CSV = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "rail_od_paths_daily_COMBINED.csv"
)

RAIL_GRAPH_GPKG = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Rail_Graph", "Rail_Graph_Nodes_Edges.gpkg"
)

OUTPUT_DIR = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Disruption_Scenario_Inputs"
)

# Rows of OD paths per chunk — lower if you still get OOM, raise for speed
CHUNK_SIZE = 250_000

# ============================================================================
# HELPERS
# ============================================================================

def safe_numeric(series):
    return pd.to_numeric(series, errors="coerce").fillna(0.0)

def add_xy_columns(gdf):
    """Add x_lon / y_lat columns (WGS-84 centroid of each geometry)."""
    gdf = gdf.copy()
    centroids    = gdf.geometry.centroid
    gdf["x_lon"] = centroids.x
    gdf["y_lat"] = centroids.y
    return gdf

# ============================================================================
# STEP 0 – Setup
# ============================================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("EXPORT NODES & LINKS WITH ASSIGNED FLOWS")
print("=" * 70)

t_start = time.time()

# ============================================================================
# STEP 1 – Read spatial layers & build edge lookup
# ============================================================================

print("\n[1/4] Reading Rail Graph layers...")

gdf_nodes = gpd.read_file(RAIL_GRAPH_GPKG, layer="nodes").to_crs(epsg=4326)
gdf_edges = gpd.read_file(RAIL_GRAPH_GPKG, layer="edges").to_crs(epsg=4326)

# Give each edge an explicit integer FID matching the row index stored
# in path_link_fids during od_flow_assignment.py
gdf_edges = gdf_edges.reset_index(drop=False).rename(columns={"index": "edge_fid"})

print(f"  Nodes : {len(gdf_nodes):,}")
print(f"  Edges : {len(gdf_edges):,}")

# Build fast edge_fid → (FRFRANODE, TOFRANODE) lookups — fits easily in RAM
edge_endpoints = (
    gdf_edges[["edge_fid", "FRFRANODE", "TOFRANODE"]]
    .set_index("edge_fid")
)
fid_to_fr = edge_endpoints["FRFRANODE"].to_dict()
fid_to_to = edge_endpoints["TOFRANODE"].to_dict()

print(f"  Edge endpoint lookup built ({len(fid_to_fr):,} entries)")

# ============================================================================
# STEP 2 – Single chunked pass over the CSV
#           Accumulate node throughput / origin / dest AND link flows
# ============================================================================

print(f"\n[2/4] Reading OD paths CSV in chunks of {CHUNK_SIZE:,}...")
print("       Accumulating node and link flows simultaneously...")

flow_cols = [
    "tons_2024_day", "value_2024_day",
    "tons_2050_day", "value_2050_day",
]

# ── Node accumulators ──────────────────────────────────────────────────────
# throughput : every OD path that CONTAINS this node (credited once per path)
node_throughput  = {fc: {} for fc in flow_cols}   # franodeid → running sum
node_origin      = {fc: {} for fc in flow_cols}
node_dest        = {fc: {} for fc in flow_cols}
node_paths_through = {}   # franodeid → count of paths through it

# ── Link accumulators ──────────────────────────────────────────────────────
link_flow    = {fc: {} for fc in flow_cols}   # edge_fid → running sum
link_npairs  = {}                              # edge_fid → OD pair count

# ── Counters ──────────────────────────────────────────────────────────────
n_total        = 0
n_missing_fids = 0

cols_needed = (
    ["origin_franodeid", "destination_franodeid", "path_link_fids"]
    + flow_cols
)

for chunk in pd.read_csv(OD_PATHS_CSV, usecols=cols_needed,
                         chunksize=CHUNK_SIZE):

    n_total += len(chunk)

    # Ensure numeric flows
    for fc in flow_cols:
        chunk[fc] = safe_numeric(chunk[fc])

    # ── Separate rows with / without path_link_fids ────────────────────────
    has_fids = (
        chunk["path_link_fids"].notna() &
        (chunk["path_link_fids"].astype(str).str.strip() != "nan")
    )
    n_missing_fids += (~has_fids).sum()

    chunk_with    = chunk[has_fids].copy()
    chunk_without = chunk[~has_fids].copy()

    # ── Origin / dest accumulation (ALL rows, no path needed) ─────────────
    for sub in [chunk_with, chunk_without]:
        if sub.empty:
            continue

        orig_agg = sub.groupby("origin_franodeid")[flow_cols].sum()
        for fc in flow_cols:
            for nid, val in orig_agg[fc].items():
                node_origin[fc][nid] = node_origin[fc].get(nid, 0.0) + val

        dest_agg = sub.groupby("destination_franodeid")[flow_cols].sum()
        for fc in flow_cols:
            for nid, val in dest_agg[fc].items():
                node_dest[fc][nid] = node_dest[fc].get(nid, 0.0) + val

    # ── Path-based accumulation (rows that HAVE path_link_fids) ───────────
    if chunk_with.empty:
        continue

    # Reset index so we have a clean integer row identifier for dedup later
    chunk_with = chunk_with.reset_index(drop=True)
    chunk_with.index.name = "_path_idx"
    chunk_with = chunk_with.reset_index()   # _path_idx becomes a column

    # ── Explode path_link_fids → one row per (OD path × edge) ─────────────
    chunk_with["edge_fid"] = (
        chunk_with["path_link_fids"].astype(str).str.split(",")
    )
    exp = chunk_with.explode("edge_fid")
    exp["edge_fid"] = pd.to_numeric(exp["edge_fid"].str.strip(), errors="coerce")
    exp = exp.dropna(subset=["edge_fid"])
    exp["edge_fid"] = exp["edge_fid"].astype(int)

    # ── Link flow accumulation ─────────────────────────────────────────────
    link_agg = exp.groupby("edge_fid")[flow_cols].sum()
    link_cnt = exp.groupby("edge_fid")["tons_2024_day"].count()

    for fc in flow_cols:
        for fid, val in link_agg[fc].items():
            link_flow[fc][fid] = link_flow[fc].get(fid, 0.0) + val
    for fid, cnt in link_cnt.items():
        link_npairs[fid] = link_npairs.get(fid, 0) + cnt

    # Map edge → both endpoint node IDs
    exp["fr_node"] = exp["edge_fid"].map(fid_to_fr)
    exp["to_node"] = exp["edge_fid"].map(fid_to_to)

    # Build long table: (_path_idx, franodeid, flow_cols...)
    # One record per (path × edge endpoint)
    keep_cols = ["_path_idx"] + flow_cols

    fr_df = exp[keep_cols + ["fr_node"]].rename(columns={"fr_node": "franodeid"})
    to_df = exp[keep_cols + ["to_node"]].rename(columns={"to_node": "franodeid"})

    # Also include the explicit origin & dest nodes so paths where the origin
    # IS a leaf node (no incoming edge) are still captured
    orig_df = chunk_with[keep_cols + ["origin_franodeid"]].rename(
        columns={"origin_franodeid": "franodeid"})
    dest_df = chunk_with[keep_cols + ["destination_franodeid"]].rename(
        columns={"destination_franodeid": "franodeid"})

    node_long = pd.concat([fr_df, to_df, orig_df, dest_df], ignore_index=True)
    node_long = node_long.dropna(subset=["franodeid"])
    node_long["franodeid"] = node_long["franodeid"].astype(int)

    # *** KEY DEDUPLICATION ***
    # Each OD path must credit each node AT MOST ONCE.
    # Drop duplicate (_path_idx, franodeid) pairs — keep first occurrence.
    node_long = node_long.drop_duplicates(subset=["_path_idx", "franodeid"])

    # Aggregate flows per node across all OD paths in this chunk
    node_agg = node_long.groupby("franodeid")[flow_cols].sum()
    node_cnt = node_long.groupby("franodeid")["tons_2024_day"].count()

    for fc in flow_cols:
        for nid, val in node_agg[fc].items():
            node_throughput[fc][nid] = node_throughput[fc].get(nid, 0.0) + val
    for nid, cnt in node_cnt.items():
        node_paths_through[nid] = node_paths_through.get(nid, 0) + cnt

    print(f"  ... {n_total:,} rows processed", end="\r")

print(f"\n  Done. Total rows: {n_total:,}")
if n_missing_fids:
    print(f"  ⚠  Rows missing path_link_fids (skipped for throughput): "
          f"{n_missing_fids:,}")

# ============================================================================
# STEP 3 – Build output DataFrames and merge with spatial layers
# ============================================================================

print("\n[3/4] Building output DataFrames...")

# ── NODE output ────────────────────────────────────────────────────────────
# Union of all nodes seen in ANY accumulator
all_node_ids = (
    set(node_throughput["tons_2024_day"].keys())
    | set(node_origin["tons_2024_day"].keys())
    | set(node_dest["tons_2024_day"].keys())
)

node_rows = []
for nid in all_node_ids:
    rec = {"FRANODEID": nid}
    for fc in flow_cols:
        rec[f"throughput_{fc}"] = node_throughput[fc].get(nid, 0.0)
        rec[f"origin_{fc}"]     = node_origin[fc].get(nid, 0.0)
        rec[f"dest_{fc}"]       = node_dest[fc].get(nid, 0.0)
    rec["num_paths_through"] = node_paths_through.get(nid, 0)
    node_rows.append(rec)

df_node_flows = pd.DataFrame(node_rows)

# Merge with spatial layer (left join keeps all graph nodes)
gdf_nodes_wgs = add_xy_columns(gdf_nodes)
gdf_nodes_out = gdf_nodes_wgs.merge(df_node_flows, on="FRANODEID", how="left")

fill_cols = [c for c in gdf_nodes_out.columns
             if c.startswith(("throughput_", "origin_", "dest_", "num_paths"))]
gdf_nodes_out[fill_cols] = gdf_nodes_out[fill_cols].fillna(0.0)

print(f"  Nodes in output  : {len(gdf_nodes_out):,}")
print(f"  Columns in output: {len(gdf_nodes_out.columns):,}")

# ── LINK output ────────────────────────────────────────────────────────────
link_rows = []
for fid in link_npairs:
    rec = {"edge_fid": fid, "num_od_pairs": link_npairs[fid]}
    for fc in flow_cols:
        rec[f"flow_{fc}"] = link_flow[fc].get(fid, 0.0)
    link_rows.append(rec)

df_link_flows = pd.DataFrame(link_rows)

gdf_edges_wgs = add_xy_columns(gdf_edges)
gdf_links_out = gdf_edges_wgs.merge(df_link_flows, on="edge_fid", how="left")

flow_fill = [c for c in gdf_links_out.columns
             if c.startswith("flow_") or c == "num_od_pairs"]
gdf_links_out[flow_fill] = gdf_links_out[flow_fill].fillna(0.0)
gdf_links_out["num_od_pairs"] = gdf_links_out["num_od_pairs"].astype(int)

# Keep only links with flow > 0
n_before = len(gdf_links_out)
gdf_links_out = gdf_links_out[gdf_links_out["num_od_pairs"] > 0].copy()
print(f"  Zero-flow links dropped  : {n_before - len(gdf_links_out):,}")
print(f"  Links in output  : {len(gdf_links_out):,}")
print(f"  Columns in output: {len(gdf_links_out.columns):,}")

# ============================================================================
# STEP 4 – Save outputs
# ============================================================================

print("\n[4/4] Saving outputs...")

node_csv_path  = os.path.join(OUTPUT_DIR, "nodes_with_flows.csv")
node_gpkg_path = os.path.join(OUTPUT_DIR, "nodes_with_flows.gpkg")
link_csv_path  = os.path.join(OUTPUT_DIR, "links_with_flows.csv")
link_gpkg_path = os.path.join(OUTPUT_DIR, "links_with_flows.gpkg")

gdf_nodes_out.drop(columns="geometry").to_csv(node_csv_path, index=False)
print(f"  ✅ nodes CSV   → {node_csv_path}")

gdf_nodes_out.to_file(node_gpkg_path, layer="nodes_with_flows", driver="GPKG")
print(f"  ✅ nodes GPKG  → {node_gpkg_path}")

gdf_links_out.drop(columns="geometry").to_csv(link_csv_path, index=False)
print(f"  ✅ links CSV   → {link_csv_path}")

gdf_links_out.to_file(link_gpkg_path, layer="links_with_flows", driver="GPKG")
print(f"  ✅ links GPKG  → {link_gpkg_path}")

