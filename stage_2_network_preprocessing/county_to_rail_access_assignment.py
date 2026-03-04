# %%
#! ============================================================
#! 1
#! Normalize yard names within counties + assign MIN/MAX YARD_ID
#! FIXED VERSION with proper fuzzy matching
#! RunTime ~ 1 minute and 35 seconds on my machine
#! ============================================================

# ? 1 new 
import geopandas as gpd
import pandas as pd
import os
from difflib import SequenceMatcher

# --------------------------------------------------
# Base directory
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

# --------------------------------------------------
# Paths
# --------------------------------------------------
faf_county_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "county_level_with_faf_flows.gpkg"
)

rail_path = os.path.join(
    base_dir,
    "Shapefiles",
    "North_American_Rail_Network_Lines",
    "North_American_Rail_Network_Lines.shp"
)

# --------------------------------------------------
# Read data
# --------------------------------------------------
print("Reading data...")
gdf_county = gpd.read_file(faf_county_path)
gdf_rail = gpd.read_file(rail_path)

print(f"Counties: {len(gdf_county)}")
print(f"Rail links: {len(gdf_rail)}")

# --------------------------------------------------
# Reproject rail to county CRS
# --------------------------------------------------
gdf_rail = gdf_rail.to_crs(gdf_county.crs)

# --------------------------------------------------
# Assign counties to rail links
# --------------------------------------------------
print("\nSpatial join: assigning counties to rail links...")
rail_with_county = gpd.sjoin(
    gdf_rail,
    gdf_county[["GEOID", "geometry"]],
    how="left",
    predicate="within"
)

# --------------------------------------------------
# Keep only valid yard names
# --------------------------------------------------
rail_with_county = rail_with_county[
    rail_with_county["YARDNAME"].notna() &
    (rail_with_county["YARDNAME"].astype(str).str.strip() != "") &
    (rail_with_county["YARDNAME"] != 0)
].copy()

rail_with_county["YARDNAME"] = (
    rail_with_county["YARDNAME"]
    .astype(str)
    .str.strip()
)

print(f"Rail links with valid yard names: {len(rail_with_county)}")
print(f"Unique yard names: {rail_with_county['YARDNAME'].nunique()}")

# --------------------------------------------------
# Helper: normalize string for comparison
# --------------------------------------------------
def normalize_for_comparison(name):
    """Normalize name for comparison (remove spaces, uppercase, but DON'T sort)"""
    return name.replace(" ", "").upper()

def similarity_ratio(name1, name2):
    """Calculate similarity ratio between two strings (0-1)"""
    return SequenceMatcher(None, 
                          normalize_for_comparison(name1), 
                          normalize_for_comparison(name2)).ratio()

def names_should_merge(name1, name2, similarity_threshold=0.8):
    """
    Determine if two names should be merged based on:
    1. One is a substring of the other (after normalization)
    2. High similarity ratio (fuzzy match)
    """
    norm1 = normalize_for_comparison(name1)
    norm2 = normalize_for_comparison(name2)
    
    # Check if one is substring of the other
    if norm1 in norm2 or norm2 in norm1:
        return True
    
    # Check similarity ratio
    if similarity_ratio(name1, name2) >= similarity_threshold:
        return True
    
    return False

# --------------------------------------------------
# Normalize yard names within each county using Union-Find
# --------------------------------------------------
print("\nNormalizing yard names within counties...")

# Union-Find data structure for grouping
class UnionFind:
    def __init__(self):
        self.parent = {}
    
    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # Path compression
        return self.parent[x]
    
    def union(self, x, y):
        root_x = self.find(x)
        root_y = self.find(y)
        if root_x != root_y:
            self.parent[root_x] = root_y

name_map = {}
total_merges = 0
county_stats = []

for geoid, grp in rail_with_county.groupby("GEOID"):
    names = sorted(grp["YARDNAME"].unique())
    
    if len(names) <= 1:
        continue
    
    # Build union-find structure for this county
    uf = UnionFind()
    
    # Compare all pairs of names
    for i, name1 in enumerate(names):
        for name2 in names[i+1:]:
            if names_should_merge(name1, name2):
                uf.union(name1, name2)
    
    # Group names by their root
    groups = {}
    for name in names:
        root = uf.find(name)
        if root not in groups:
            groups[root] = []
        groups[root].append(name)
    
    # For each group, choose the longest name as canonical
    merges_in_county = 0
    for group_names in groups.values():
        if len(group_names) > 1:
            canonical = max(group_names, key=len)
            for name in group_names:
                name_map[(geoid, name)] = canonical
            merges_in_county += len(group_names) - 1
    
    if merges_in_county > 0:
        county_stats.append({
            "GEOID": geoid,
            "unique_names_before": len(names),
            "unique_names_after": len(groups),
            "names_merged": merges_in_county
        })
        total_merges += merges_in_county

print(f"\nTotal yard name merges: {total_merges}")
print(f"Counties with merges: {len(county_stats)}")

if county_stats:
    print("\nTop 10 counties by number of merges:")
    df_stats = pd.DataFrame(county_stats).sort_values("names_merged", ascending=False)
    print(df_stats.head(10).to_string(index=False))

# --------------------------------------------------
# Apply normalized names
# --------------------------------------------------
print("\nApplying normalized names to rail data...")

rail_with_county["YARDNAME_NORMALIZED"] = rail_with_county.apply(
    lambda r: name_map.get((r["GEOID"], r["YARDNAME"]), r["YARDNAME"]),
    axis=1
)

# Show some examples of merges
print("\nExample yard name merges:")
merge_examples = rail_with_county[
    rail_with_county["YARDNAME"] != rail_with_county["YARDNAME_NORMALIZED"]
][["GEOID", "YARDNAME", "YARDNAME_NORMALIZED"]].drop_duplicates()

if len(merge_examples) > 0:
    print(merge_examples.head(20).to_string(index=False))
else:
    print("No yard names were merged!")

# --------------------------------------------------
# Apply back to original rail GeoDataFrame
# --------------------------------------------------
# Create a mapping from OBJECTID to normalized yard name
objectid_to_normalized = dict(
    zip(rail_with_county["OBJECTID"], 
        rail_with_county["YARDNAME_NORMALIZED"])
)

# Apply to original gdf_rail
gdf_rail["YARDNAME"] = gdf_rail["OBJECTID"].map(objectid_to_normalized).fillna(gdf_rail["YARDNAME"])

# --------------------------------------------------
# Save new rail file
# --------------------------------------------------
print("\nSaving normalized rail data...")
new_rail_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Yard_Normalized",
    "North_American_Rail_Network_Lines_YARD_NORMALIZED.gpkg"
)

os.makedirs(os.path.dirname(new_rail_path), exist_ok=True)
gdf_rail.to_file(new_rail_path, driver="GPKG")
print(f"Saved to: {new_rail_path}")

# --------------------------------------------------
# Compute MIN and MAX OBJECTID per normalized yard per county
# --------------------------------------------------
print("\nComputing MIN/MAX OBJECTID per yard per county...")

yard_min_max = (
    rail_with_county
    .groupby(["GEOID", "YARDNAME_NORMALIZED"])["OBJECTID"]
    .agg(["min", "max"])
    .reset_index()
)

print(f"Unique (county, yard) combinations: {len(yard_min_max)}")

# --------------------------------------------------
# Build aligned comma-separated strings per county
# --------------------------------------------------
min_ids_per_county = (
    yard_min_max
    .groupby("GEOID")["min"]
    .apply(lambda x: ",".join(x.astype(str)))
)

max_ids_per_county = (
    yard_min_max
    .groupby("GEOID")["max"]
    .apply(lambda x: ",".join(x.astype(str)))
)

# --------------------------------------------------
# Add new columns to county GeoDataFrame
# --------------------------------------------------
gdf_county["MIN_YARD_ID"] = gdf_county["GEOID"].map(min_ids_per_county)
gdf_county["MAX_YARD_ID"] = gdf_county["GEOID"].map(max_ids_per_county)

# Count yards per county
yard_counts = yard_min_max.groupby("GEOID").size()
gdf_county["NUM_YARDS"] = gdf_county["GEOID"].map(yard_counts).fillna(0).astype(int)

# --------------------------------------------------
# Save new county file
# --------------------------------------------------
print("\nSaving county data with yard information...")
new_county_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "county_level_with_faf_flows_YARD_NORMALIZED.gpkg"
)

os.makedirs(os.path.dirname(new_county_path), exist_ok=True)
gdf_county.to_file(new_county_path, driver="GPKG")
print(f"Saved to: {new_county_path}")

# --------------------------------------------------
# Summary statistics
# --------------------------------------------------
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"Total rail links: {len(gdf_rail)}")
print(f"Links with yard names: {len(rail_with_county)}")
print(f"Unique normalized yard names: {rail_with_county['YARDNAME_NORMALIZED'].nunique()}")
print(f"Counties with yards: {gdf_county[gdf_county['NUM_YARDS'] > 0]['NUM_YARDS'].count()}")
print(f"\nYards per county statistics:")
print(gdf_county[gdf_county['NUM_YARDS'] > 0]['NUM_YARDS'].describe())

print("\nDone!")

# ==================================================
# Remove counties with zero / null flows (2024 & 2050)
# ==================================================

print("\nFiltering counties with all-zero in/out flows (2024 & 2050)...")

flow_cols = [
    "out_sum_tons_2024",
    "out_sum_value_2024",
    "in_sum_tons_2024",
    "in_sum_value_2024",
    "out_sum_tons_2050",
    "out_sum_value_2050",
    "in_sum_tons_2050",
    "in_sum_value_2050",
]

# Safety check
missing_cols = [c for c in flow_cols if c not in gdf_county.columns]
if missing_cols:
    raise ValueError(f"Missing required flow columns: {missing_cols}")

# Replace NaN with 0
gdf_county_filtered = gdf_county.copy()
gdf_county_filtered[flow_cols] = (
    gdf_county_filtered[flow_cols]
    .apply(pd.to_numeric, errors="coerce")
    .fillna(0.0)
)

# --------------------------------------------------
# STEP 1: Drop counties with ALL-zero flows
# --------------------------------------------------
all_zero_mask = (gdf_county_filtered[flow_cols].sum(axis=1) == 0)

num_zero_dropped = all_zero_mask.sum()
print(f"Counties dropped (all-zero flows): {num_zero_dropped}")

gdf_county_non_zero = gdf_county_filtered.loc[~all_zero_mask].copy()

# --------------------------------------------------
# STEP 2: Drop Alaska (STATEFP == '02')
# --------------------------------------------------
if "STATEFP" not in gdf_county_non_zero.columns:
    raise ValueError("STATEFP column not found in county data")

alaska_mask = gdf_county_non_zero["STATEFP"].astype(str).str.zfill(2) == "02"
num_alaska_dropped = alaska_mask.sum()

print(f"Counties dropped (Alaska): {num_alaska_dropped}")

gdf_county_final = gdf_county_non_zero.loc[~alaska_mask].copy()

print(f"Counties kept (final): {len(gdf_county_final)}")

# --------------------------------------------------
# Save output GeoPackage
# --------------------------------------------------
out_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "faf_county_with_flows_CONUS.gpkg"
)

os.makedirs(os.path.dirname(out_path), exist_ok=True)
gdf_county_final.to_file(out_path, driver="GPKG")

print(f"\nSaved filtered county file to:\n{out_path}")

# %%
#! ============================================================
#! 2 
#! Create M and I only rail network
#! Keep giant connected component, isolate orphan links
#! ============================================================

import geopandas as gpd
import os
import networkx as nx

# --------------------------------------------------
# Base directory
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

# --------------------------------------------------
# Paths
# --------------------------------------------------
rail_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Yard_Normalized",
    "North_American_Rail_Network_Lines_YARD_NORMALIZED.gpkg"
)

out_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "M_and_I_Only"
)
os.makedirs(out_dir, exist_ok=True)

out_all_mi = os.path.join(
    out_dir,
    "North_American_Rail_Network_Lines_NET_M_I.gpkg"
)

out_giant = os.path.join(
    out_dir,
    "North_American_Rail_Network_Lines_NET_M_I_GIANT.gpkg"
)

out_orphans = os.path.join(
    out_dir,
    "North_American_Rail_Network_Lines_NET_M_I_ORPHANS.gpkg"
)

# --------------------------------------------------
# Read rail data
# --------------------------------------------------
print("Reading rail data...")
gdf_rail = gpd.read_file(rail_path)
print(f"Total rail links (all): {len(gdf_rail)}")

# --------------------------------------------------
# Filter NET = M or I
# --------------------------------------------------
gdf_mi = gdf_rail[gdf_rail["NET"].isin(["M", "I"])].copy()
print(f"M/I rail links: {len(gdf_mi)}")

# Save full M/I network
gdf_mi.to_file(out_all_mi, driver="GPKG")

# --------------------------------------------------
# Ensure projected CRS for endpoint comparison
# --------------------------------------------------
if not gdf_mi.crs.is_projected:
    print("Reprojecting to EPSG:5070 for topology checks...")
    gdf_mi = gdf_mi.to_crs(epsg=5070)

# --------------------------------------------------
# Build connectivity graph (nodes = endpoints, edges = links)
# --------------------------------------------------
print("Building connectivity graph...")

G = nx.Graph()

for idx, row in gdf_mi.iterrows():
    geom = row.geometry
    u = tuple(geom.coords[0])
    v = tuple(geom.coords[-1])
    G.add_edge(u, v, link_idx=idx)

print(f"Graph nodes: {G.number_of_nodes()}")
print(f"Graph edges: {G.number_of_edges()}")

# --------------------------------------------------
# Find connected components (by endpoints)
# --------------------------------------------------
print("Identifying connected components...")

components = list(nx.connected_components(G))
print(f"Total connected components: {len(components)}")

# --------------------------------------------------
# Identify giant component (largest by number of links)
# --------------------------------------------------
def component_edge_indices(component_nodes):
    """Return link indices belonging to a component"""
    idxs = set()
    for u, v, data in G.edges(component_nodes, data=True):
        idxs.add(data["link_idx"])
    return idxs

component_edges = [
    component_edge_indices(comp) for comp in components
]

giant_component_edges = max(component_edges, key=len)

print(f"Giant component links: {len(giant_component_edges)}")

# --------------------------------------------------
# Orphan links = everything not in giant component
# --------------------------------------------------
all_indices = set(gdf_mi.index)
orphan_indices = list(all_indices - giant_component_edges)

print(f"Orphan links (non-giant components): {len(orphan_indices)}")

# --------------------------------------------------
# Split GeoDataFrame
# --------------------------------------------------
gdf_giant = gdf_mi.loc[list(giant_component_edges)].copy()
gdf_orphans = gdf_mi.loc[orphan_indices].copy()

print(f"Check sum: {len(gdf_giant) + len(gdf_orphans)}")

# --------------------------------------------------
# Save outputs
# --------------------------------------------------
print("Saving outputs...")

gdf_giant.to_file(out_giant, driver="GPKG")
gdf_orphans.to_file(out_orphans, driver="GPKG")

print("\n========================================")
print("PROCESS COMPLETE")
print("========================================")
print(f"Giant component network:\n{out_giant}")
print(f"Orphan (non-giant) links:\n{out_orphans}")

#%%
#! ============================================================
#! 3
#! Create YARD, END, and JUNCTION nodes for M/I rail network
#! RunTime ~ 3 minutes and 15 seconds on my machine
#! ============================================================
# import geopandas as gpd
# import pandas as pd
# import numpy as np
# import os
# from shapely.geometry import Point
# from shapely.ops import nearest_points
# from sklearn.cluster import DBSCAN
# from scipy.spatial.distance import pdist, squareform

# # --------------------------------------------------
# # Paths
# # --------------------------------------------------
# base_dir = os.path.abspath(os.path.join("..", ".."))

# rail_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "M_and_I_Only",
#     "North_American_Rail_Network_Lines_NET_M_I_GIANT.gpkg"
# )


# out_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Rail_Nodes",
#     "Rail_Nodes_M_I_Yards_End_Junction.gpkg"
# )

# out_csv = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Rail_Nodes",
#     "Yard_Node_Distance_Report.csv"
# )

# # --------------------------------------------------
# # Parameters
# # --------------------------------------------------
# YARD_EXCLUSION_DIST = 1000      # meters
# DIST_PREF_RATIO = 1.2
# UNNAMED_CLUSTER_DIST = 5000    # meters
# MERGE_TO_NAMED_DIST = 1000     # meters
# ENDPOINT_TOL = 1              # meters (endpoint clustering)
# DUPLICATE_TOL = 5              # meters (tolerance for detecting duplicate nodes)
# SPATIAL_CLUSTER_DIST = 16093.4  # 10 miles in meters

# # --------------------------------------------------
# # Read rail data
# # --------------------------------------------------
# print("Reading rail data...")
# gdf_rail_MI = gpd.read_file(rail_path).to_crs(epsg=5070)

# # Backbone rail (M/I only)

# gdf_M = gdf_rail_MI[gdf_rail_MI["NET"] == "M"].copy()
# gdf_I = gdf_rail_MI[gdf_rail_MI["NET"] == "I"].copy()


# print(f"Total M/I links: {len(gdf_rail_MI)}")
# print(f"M links: {len(gdf_M)}")
# print(f"I links: {len(gdf_I)}")

# # --------------------------------------------------
# # HELPER: Extract all endpoints from M/I network
# # --------------------------------------------------
# print("\nExtracting M/I link endpoints...")

# m_endpoints = []
# for idx, row in gdf_M.iterrows():
#     line = row.geometry
#     m_endpoints.append({
#         "geometry": Point(line.coords[0]),
#         "OBJECTID": row["OBJECTID"],
#         "endpoint_type": "start",
#         "link_index": idx
#     })
#     m_endpoints.append({
#         "geometry": Point(line.coords[-1]),
#         "OBJECTID": row["OBJECTID"],
#         "endpoint_type": "end",
#         "link_index": idx
#     })

# gdf_m_endpoints = gpd.GeoDataFrame(m_endpoints, crs=gdf_rail_MI.crs)

# i_endpoints = []
# for idx, row in gdf_I.iterrows():
#     line = row.geometry
#     i_endpoints.append({
#         "geometry": Point(line.coords[0]),
#         "OBJECTID": row["OBJECTID"],
#         "endpoint_type": "start",
#         "link_index": idx
#     })
#     i_endpoints.append({
#         "geometry": Point(line.coords[-1]),
#         "OBJECTID": row["OBJECTID"],
#         "endpoint_type": "end",
#         "link_index": idx
#     })

# gdf_i_endpoints = gpd.GeoDataFrame(i_endpoints, crs=gdf_rail_MI.crs)

# print(f"M endpoints: {len(gdf_m_endpoints)}")
# print(f"I endpoints: {len(gdf_i_endpoints)}")

# # --------------------------------------------------
# # HELPER FUNCTION: Cluster by pairwise maximum distance
# # --------------------------------------------------
# def cluster_by_max_pairwise_distance(coords, max_distance):
#     """
#     Cluster points such that all points in a cluster are within max_distance 
#     of ALL other points in that cluster (not just neighbors).
    
#     Returns: array of cluster labels
#     """
#     if len(coords) == 1:
#         return np.array([0])
    
#     # Start with each point in its own cluster
#     n = len(coords)
#     labels = np.arange(n)
    
#     # Compute pairwise distance matrix
#     dist_matrix = squareform(pdist(coords))
    
#     # Try to merge clusters iteratively
#     merged = True
#     while merged:
#         merged = False
#         unique_labels = np.unique(labels)
        
#         for i, label_i in enumerate(unique_labels):
#             for label_j in unique_labels[i+1:]:
#                 # Get points in each cluster
#                 cluster_i = np.where(labels == label_i)[0]
#                 cluster_j = np.where(labels == label_j)[0]
                
#                 # Check if all pairwise distances between clusters are <= max_distance
#                 can_merge = True
#                 for idx_i in cluster_i:
#                     for idx_j in cluster_j:
#                         if dist_matrix[idx_i, idx_j] > max_distance:
#                             can_merge = False
#                             break
#                     if not can_merge:
#                         break
                
#                 # If we can merge, do it
#                 if can_merge:
#                     # Check that merged cluster satisfies constraint
#                     merged_indices = np.concatenate([cluster_i, cluster_j])
#                     max_dist_in_merged = 0
#                     for ii in range(len(merged_indices)):
#                         for jj in range(ii+1, len(merged_indices)):
#                             d = dist_matrix[merged_indices[ii], merged_indices[jj]]
#                             if d > max_dist_in_merged:
#                                 max_dist_in_merged = d
                    
#                     if max_dist_in_merged <= max_distance:
#                         labels[labels == label_j] = label_i
#                         merged = True
#                         break
            
#             if merged:
#                 break
    
#     # Relabel to be consecutive starting from 0
#     unique_labels = np.unique(labels)
#     relabeled = np.zeros(n, dtype=int)
#     for new_label, old_label in enumerate(unique_labels):
#         relabeled[labels == old_label] = new_label
    
#     return relabeled

# # --------------------------------------------------
# # HELPER FUNCTION: Find both endpoints of nearest link
# # --------------------------------------------------
# def find_link_endpoints(point, gdf_links, gdf_endpoints):
#     """
#     Find the nearest link to a point, then return both endpoints of that link.
#     Returns: (start_point, end_point, objectid, distance_to_nearest_endpoint, link_index)
#     """
#     # Find nearest endpoint first
#     distances = gdf_endpoints.geometry.distance(point)
#     min_idx = distances.idxmin()
#     min_dist = distances.loc[min_idx]
    
#     nearest_row = gdf_endpoints.loc[min_idx]
#     objectid = nearest_row["OBJECTID"]
#     link_idx = nearest_row["link_index"]
    
#     # Get the link geometry
#     link = gdf_links.loc[link_idx]
#     line = link.geometry
    
#     # Get both endpoints
#     start_point = Point(line.coords[0])
#     end_point = Point(line.coords[-1])
    
#     return start_point, end_point, objectid, min_dist, link_idx

# # --------------------------------------------------
# # STEP 1: YARD nodes (named + unnamed) WITH SPATIAL CLUSTERING
# # --------------------------------------------------
# print("\nProcessing YARD nodes with spatial clustering...")
# yard_records = []
# yard_distance_records = []  # For CSV reporting

# # ---- Named yards with 10-mile spatial clustering
# named_yards = gdf_rail_MI[
#     gdf_rail_MI["YARDNAME"].notna() &
#     (gdf_rail_MI["YARDNAME"].astype(str).str.strip() != "") &
#     (gdf_rail_MI["YARDNAME"] != 0)
# ]

# print(f"Named yards: {len(named_yards['YARDNAME'].unique())} unique names")

# named_centroids = []
# spatial_cluster_count = 0

# for (yard, fips), grp in named_yards.groupby(["YARDNAME", "CNTYFIPS"]):
#     # Get centroids of all segments for this yard
#     centroids = grp.geometry.centroid
#     coords = np.column_stack([centroids.x.values, centroids.y.values])
    
#     # Apply spatial clustering with pairwise distance constraint
#     if len(coords) > 1:
#         cluster_labels = cluster_by_max_pairwise_distance(coords, SPATIAL_CLUSTER_DIST)
#         num_clusters = len(np.unique(cluster_labels))
#     else:
#         cluster_labels = np.array([0])
#         num_clusters = 1
    
#     if num_clusters > 1:
#         spatial_cluster_count += 1
#         print(f"  Split '{yard}' in county {fips} into {num_clusters} clusters")
    
#     # Process each spatial cluster separately
#     for cluster_id in range(num_clusters):
#         cluster_mask = cluster_labels == cluster_id
#         cluster_centroids = centroids.iloc[cluster_mask]
        
#         # Calculate mean point for this cluster
#         mean_pt = Point(cluster_centroids.x.mean(), cluster_centroids.y.mean())
#         named_centroids.append(mean_pt)
        
#         # Add suffix if multiple clusters
#         if num_clusters > 1:
#             yard_name_with_suffix = f"{yard}_{cluster_id + 1}"
#         else:
#             yard_name_with_suffix = yard

#         # Find nearest link and get both endpoints for M and I networks
#         m_start, m_end, m_obj, m_dist, m_link_idx = find_link_endpoints(mean_pt, gdf_M, gdf_m_endpoints)
#         i_start, i_end, i_obj, i_dist, i_link_idx = find_link_endpoints(mean_pt, gdf_I, gdf_i_endpoints)

#         # Choose based on distance preference
#         if m_dist <= DIST_PREF_RATIO * i_dist:
#             # Use M network
#             start_point = m_start
#             end_point = m_end
#             node_net = "YARD_M"
#             node_obj = m_obj
#             chosen_link_idx = m_link_idx
#             chosen_network = "M"
            
#             # Determine which endpoint is closer
#             dist_to_start = mean_pt.distance(start_point)
#             dist_to_end = mean_pt.distance(end_point)
            
#             if dist_to_start < dist_to_end:
#                 snap_geom = start_point
#                 chosen_endpoint = "start"
#                 dist_from_actual = dist_to_start
#             else:
#                 snap_geom = end_point
#                 chosen_endpoint = "end"
#                 dist_from_actual = dist_to_end
#         else:
#             # Use I network
#             start_point = i_start
#             end_point = i_end
#             node_net = "YARD_I"
#             node_obj = i_obj
#             chosen_link_idx = i_link_idx
#             chosen_network = "I"
            
#             # Determine which endpoint is closer
#             dist_to_start = mean_pt.distance(start_point)
#             dist_to_end = mean_pt.distance(end_point)
            
#             if dist_to_start < dist_to_end:
#                 snap_geom = start_point
#                 chosen_endpoint = "start"
#                 dist_from_actual = dist_to_start
#             else:
#                 snap_geom = end_point
#                 chosen_endpoint = "end"
#                 dist_from_actual = dist_to_end

#         yard_records.append({
#             "NODE_TYPE": "YARD",
#             "NODE_NET": node_net,
#             "NODE_OBJECTID": node_obj,
#             "YARD_NAME": yard_name_with_suffix,
#             "geometry": snap_geom,
#             "start_endpoint": start_point,
#             "end_endpoint": end_point,
#             "chosen_endpoint": chosen_endpoint,
#             "link_index": chosen_link_idx
#         })
        
#         # Record distance for CSV
#         yard_distance_records.append({
#             "YARD_NAME": yard_name_with_suffix,
#             "YARD_TYPE": "Named",
#             "SPATIAL_CLUSTER": f"{cluster_id + 1}/{num_clusters}" if num_clusters > 1 else "1/1",
#             "NODE_NET": node_net,
#             "NODE_OBJECTID": node_obj,
#             "ACTUAL_X": mean_pt.x,
#             "ACTUAL_Y": mean_pt.y,
#             "SNAPPED_X": snap_geom.x,
#             "SNAPPED_Y": snap_geom.y,
#             "DISTANCE_METERS": dist_from_actual,
#             "CHOSEN_ENDPOINT": chosen_endpoint,
#             "NETWORK": chosen_network
#         })

# named_yard_points = gpd.GeoSeries(named_centroids, crs=gdf_rail_MI.crs)

# print(f"Named yard nodes created: {len(yard_records)}")
# print(f"Named yards split into multiple clusters: {spatial_cluster_count}")

# # ---- Unnamed yards (NET == Y)
# unnamed_yards = gdf_rail_MI[
#     (gdf_rail_MI["NET"] == "Y") &
#     (gdf_rail_MI["YARDNAME"].isna())
# ]

# print(f"Unnamed yard segments: {len(unnamed_yards)}")

# unnamed_count = 0

# for fips, grp in unnamed_yards.groupby("CNTYFIPS"):
#     coords = np.column_stack([
#         grp.geometry.centroid.x.values,
#         grp.geometry.centroid.y.values
#     ])

#     if len(coords) == 0:
#         continue

#     clustering = DBSCAN(
#         eps=UNNAMED_CLUSTER_DIST,
#         min_samples=1
#     ).fit(coords)

#     grp = grp.copy()
#     grp["cluster"] = clustering.labels_

#     for _, cgrp in grp.groupby("cluster"):
#         centroids = cgrp.geometry.centroid
#         mean_pt = Point(centroids.x.mean(), centroids.y.mean())

#         # Skip if too close to named yard
#         if len(named_yard_points) > 0:
#             if named_yard_points.distance(mean_pt).min() <= MERGE_TO_NAMED_DIST:
#                 continue

#         # Find nearest link and get both endpoints for M and I networks
#         m_start, m_end, m_obj, m_dist, m_link_idx = find_link_endpoints(mean_pt, gdf_M, gdf_m_endpoints)
#         i_start, i_end, i_obj, i_dist, i_link_idx = find_link_endpoints(mean_pt, gdf_I, gdf_i_endpoints)

#         # Choose based on distance preference
#         if m_dist <= DIST_PREF_RATIO * i_dist:
#             # Use M network
#             start_point = m_start
#             end_point = m_end
#             node_net = "YARD_M"
#             node_obj = m_obj
#             chosen_link_idx = m_link_idx
#             chosen_network = "M"
            
#             # Determine which endpoint is closer
#             dist_to_start = mean_pt.distance(start_point)
#             dist_to_end = mean_pt.distance(end_point)
            
#             if dist_to_start < dist_to_end:
#                 snap_geom = start_point
#                 chosen_endpoint = "start"
#                 dist_from_actual = dist_to_start
#             else:
#                 snap_geom = end_point
#                 chosen_endpoint = "end"
#                 dist_from_actual = dist_to_end
#         else:
#             # Use I network
#             start_point = i_start
#             end_point = i_end
#             node_net = "YARD_I"
#             node_obj = i_obj
#             chosen_link_idx = i_link_idx
#             chosen_network = "I"
            
#             # Determine which endpoint is closer
#             dist_to_start = mean_pt.distance(start_point)
#             dist_to_end = mean_pt.distance(end_point)
            
#             if dist_to_start < dist_to_end:
#                 snap_geom = start_point
#                 chosen_endpoint = "start"
#                 dist_from_actual = dist_to_start
#             else:
#                 snap_geom = end_point
#                 chosen_endpoint = "end"
#                 dist_from_actual = dist_to_end

#         yard_records.append({
#             "NODE_TYPE": "YARD",
#             "NODE_NET": node_net,
#             "NODE_OBJECTID": node_obj,
#             "YARD_NAME": f"Unnamed_{unnamed_count}",
#             "geometry": snap_geom,
#             "start_endpoint": start_point,
#             "end_endpoint": end_point,
#             "chosen_endpoint": chosen_endpoint,
#             "link_index": chosen_link_idx
#         })
        
#         # Record distance for CSV
#         yard_distance_records.append({
#             "YARD_NAME": f"Unnamed_{unnamed_count}",
#             "YARD_TYPE": "Unnamed",
#             "SPATIAL_CLUSTER": "N/A",
#             "NODE_NET": node_net,
#             "NODE_OBJECTID": node_obj,
#             "ACTUAL_X": mean_pt.x,
#             "ACTUAL_Y": mean_pt.y,
#             "SNAPPED_X": snap_geom.x,
#             "SNAPPED_Y": snap_geom.y,
#             "DISTANCE_METERS": dist_from_actual,
#             "CHOSEN_ENDPOINT": chosen_endpoint,
#             "NETWORK": chosen_network
#         })
        
#         unnamed_count += 1

# print(f"Unnamed yard nodes created: {unnamed_count}")

# gdf_yards = gpd.GeoDataFrame(yard_records, crs=gdf_rail_MI.crs)
# print(f"Total yard nodes: {len(gdf_yards)}")

# # --------------------------------------------------
# # STEP 2: END & JUNCTION nodes (endpoint-based)
# # --------------------------------------------------
# print("\nProcessing END and JUNCTION nodes...")

# endpoints = []

# for _, row in gdf_rail_MI.iterrows():
#     line = row.geometry
#     endpoints.append({
#         "geometry": Point(line.coords[0]),
#         "OBJECTID": row["OBJECTID"],
#         "NET": row["NET"]
#     })
#     endpoints.append({
#         "geometry": Point(line.coords[-1]),
#         "OBJECTID": row["OBJECTID"],
#         "NET": row["NET"]
#     })

# gdf_endpts = gpd.GeoDataFrame(endpoints, crs=gdf_rail_MI.crs)

# coords = np.column_stack([
#     gdf_endpts.geometry.x.values,
#     gdf_endpts.geometry.y.values
# ])

# clustering = DBSCAN(eps=ENDPOINT_TOL, min_samples=1).fit(coords)
# gdf_endpts["cluster"] = clustering.labels_

# node_records = []

# for cid, grp in gdf_endpts.groupby("cluster"):
#     degree = grp["OBJECTID"].nunique()

#     if degree == 1:
#         node_type = "END"
#     elif degree >= 3:
#         node_type = "JUNCTION"
#     else:
#         continue  # drop degree-2 (these are intermediate points, not nodes)

#     nets = set(grp["NET"])
#     if nets == {"M"}:
#         node_net = f"{node_type}_M"
#     elif nets == {"I"}:
#         node_net = f"{node_type}_I"
#     else:
#         node_net = f"{node_type}_MI"

#     mean_pt = Point(grp.geometry.x.mean(), grp.geometry.y.mean())
#     grp["dist"] = grp.geometry.distance(mean_pt)
#     node_obj = grp.loc[grp["dist"].idxmin(), "OBJECTID"]

#     node_records.append({
#         "NODE_TYPE": node_type,
#         "NODE_NET": node_net,
#         "NODE_OBJECTID": node_obj,
#         "geometry": mean_pt
#     })

# gdf_other_nodes = gpd.GeoDataFrame(node_records, crs=gdf_rail_MI.crs)

# print(f"END nodes (before filtering): {len(gdf_other_nodes[gdf_other_nodes['NODE_TYPE'] == 'END'])}")
# print(f"JUNCTION nodes: {len(gdf_other_nodes[gdf_other_nodes['NODE_TYPE'] == 'JUNCTION'])}")

# # --------------------------------------------------
# # STEP 3: Resolve conflicts between YARD and END/JUNCTION nodes
# # --------------------------------------------------
# print("\nResolving conflicts between YARD and END/JUNCTION nodes...")
# print("Priority: YARD always wins - remove conflicting END and JUNCTION nodes")

# # Separate END and JUNCTION nodes
# gdf_end_nodes = gdf_other_nodes[gdf_other_nodes["NODE_TYPE"] == "END"].copy()
# gdf_junction_nodes = gdf_other_nodes[gdf_other_nodes["NODE_TYPE"] == "JUNCTION"].copy()

# # Create spatial indices
# end_nodes_sindex = gdf_end_nodes.sindex
# junction_nodes_sindex = gdf_junction_nodes.sindex

# removed_ends = []
# removed_junctions = []

# for idx, yard in gdf_yards.iterrows():
#     yard_geom = yard.geometry
    
#     # Check for conflict with END nodes
#     nearby_end_idx = list(end_nodes_sindex.intersection(yard_geom.buffer(DUPLICATE_TOL).bounds))
#     if nearby_end_idx:
#         nearby_ends = gdf_end_nodes.iloc[nearby_end_idx]
#         nearby_ends = nearby_ends[nearby_ends.geometry.distance(yard_geom) < DUPLICATE_TOL]
        
#         if len(nearby_ends) > 0:
#             # YARD wins over END - remove the END node
#             print(f"  Conflict: YARD '{yard['YARD_NAME']}' at same location as END node")
#             print(f"    → Removing END node (keeping YARD)")
#             removed_ends.extend(nearby_ends.index.tolist())
    
#     # Check for conflict with JUNCTION nodes
#     nearby_junction_idx = list(junction_nodes_sindex.intersection(yard_geom.buffer(DUPLICATE_TOL).bounds))
#     if nearby_junction_idx:
#         nearby_junctions = gdf_junction_nodes.iloc[nearby_junction_idx]
#         nearby_junctions = nearby_junctions[nearby_junctions.geometry.distance(yard_geom) < DUPLICATE_TOL]
        
#         if len(nearby_junctions) > 0:
#             # YARD wins over JUNCTION - remove the JUNCTION node
#             print(f"  Conflict: YARD '{yard['YARD_NAME']}' at same location as JUNCTION node")
#             print(f"    → Removing JUNCTION node (keeping YARD)")
#             removed_junctions.extend(nearby_junctions.index.tolist())

# # Remove conflicting END nodes
# if removed_ends:
#     gdf_end_nodes = gdf_end_nodes.drop(removed_ends)
#     print(f"\nRemoved {len(removed_ends)} END nodes that conflicted with YARD nodes")

# # Remove conflicting JUNCTION nodes
# if removed_junctions:
#     gdf_junction_nodes = gdf_junction_nodes.drop(removed_junctions)
#     print(f"Removed {len(removed_junctions)} JUNCTION nodes that conflicted with YARD nodes")

# print(f"\nYARD nodes are never moved or removed - they always win conflicts!")

# # --------------------------------------------------
# # STEP 4: Remove END nodes near YARD (keep JUNCTION always)
# # --------------------------------------------------
# print("\nRemoving END nodes near YARDs...")

# yard_union = gdf_yards.geometry.union_all()

# # Remove END nodes close to yards
# before_count = len(gdf_end_nodes)
# gdf_end_nodes = gdf_end_nodes[
#     gdf_end_nodes.geometry.distance(yard_union) > YARD_EXCLUSION_DIST
# ]
# after_count = len(gdf_end_nodes)

# print(f"Removed {before_count - after_count} END nodes within {YARD_EXCLUSION_DIST}m of YARDs")

# # Recombine END and JUNCTION nodes
# gdf_other_nodes = pd.concat(
#     [gdf_end_nodes, gdf_junction_nodes],
#     ignore_index=True
# )

# print(f"Final END nodes: {len(gdf_end_nodes)}")
# print(f"Final JUNCTION nodes: {len(gdf_junction_nodes)}")

# # --------------------------------------------------
# # STEP 5: Combine & save
# # --------------------------------------------------
# print("\nCombining all nodes...")

# # Add YARD_NAME column to other_nodes (will be None/null for END and JUNCTION)
# gdf_other_nodes["YARD_NAME"] = None

# gdf_all_nodes = gpd.GeoDataFrame(
#     pd.concat(
#         [
#             gdf_yards[["NODE_TYPE", "NODE_NET", "NODE_OBJECTID", "YARD_NAME", "geometry"]],
#             gdf_other_nodes[["NODE_TYPE", "NODE_NET", "NODE_OBJECTID", "YARD_NAME", "geometry"]],
#         ],
#         ignore_index=True,
#     ),
#     crs=gdf_rail_MI.crs,
# )

# print(f"\nFinal node counts:")
# print(gdf_all_nodes["NODE_TYPE"].value_counts())

# os.makedirs(os.path.dirname(out_path), exist_ok=True)
# gdf_all_nodes.to_file(out_path, driver="GPKG")

# print(f"\nSaved to: {out_path}")

# # --------------------------------------------------
# # STEP 6: Save distance report CSV
# # --------------------------------------------------
# print("\nCreating distance report CSV...")

# # Convert distance records to DataFrame
# df_distances = pd.DataFrame(yard_distance_records)

# # Sort by distance (descending) to see largest distances first
# df_distances = df_distances.sort_values("DISTANCE_METERS", ascending=False)

# # Save to CSV
# df_distances.to_csv(out_csv, index=False)

# print(f"Saved distance report to: {out_csv}")

# # Print summary statistics
# print("\n" + "="*70)
# print("DISTANCE REPORT SUMMARY")
# print("="*70)
# print(f"Total yard nodes: {len(df_distances)}")
# print(f"\nDistance statistics (meters):")
# print(f"  Mean: {df_distances['DISTANCE_METERS'].mean():.2f}")
# print(f"  Median: {df_distances['DISTANCE_METERS'].median():.2f}")
# print(f"  Min: {df_distances['DISTANCE_METERS'].min():.2f}")
# print(f"  Max: {df_distances['DISTANCE_METERS'].max():.2f}")
# print(f"  Std Dev: {df_distances['DISTANCE_METERS'].std():.2f}")

# print(f"\nTop 10 largest distances:")
# print(df_distances[["YARD_NAME", "NODE_OBJECTID", "DISTANCE_METERS", "CHOSEN_ENDPOINT", "NETWORK"]].head(10).to_string(index=False))

# print(f"\nSpatial clustering summary:")
# multi_cluster = df_distances[df_distances["SPATIAL_CLUSTER"].str.contains("/2|/3|/4|/5", na=False)]
# print(f"  Yards split into multiple spatial clusters: {len(multi_cluster)}")

# print(f"\nEndpoint distribution:")
# print(df_distances["CHOSEN_ENDPOINT"].value_counts())

# # --------------------------------------------------
# # VALIDATION: Check for duplicate nodes at same location
# # --------------------------------------------------
# print("\n" + "="*70)
# print("VALIDATION: Checking for duplicate nodes")
# print("="*70)

# # Cluster all nodes to find duplicates
# all_coords = np.column_stack([
#     gdf_all_nodes.geometry.x.values,
#     gdf_all_nodes.geometry.y.values
# ])

# clustering = DBSCAN(eps=1, min_samples=1).fit(all_coords)
# gdf_all_nodes["validation_cluster"] = clustering.labels_

# duplicates = gdf_all_nodes.groupby("validation_cluster").size()
# duplicates = duplicates[duplicates > 1]

# if len(duplicates) > 0:
#     print(f"WARNING: Found {len(duplicates)} locations with multiple nodes!")
#     print("\nSample duplicates:")
#     for cluster_id in list(duplicates.index)[:5]:
#         cluster_nodes = gdf_all_nodes[gdf_all_nodes["validation_cluster"] == cluster_id]
#         print(f"\nCluster {cluster_id}:")
#         print(cluster_nodes[["NODE_TYPE", "NODE_NET", "NODE_OBJECTID", "YARD_NAME"]])
# else:
#     print("✓ No duplicate nodes found - all nodes are at unique locations")

# print("\nDone!")
# %%
#! ============================================================
#! 3
#! Create YARD, END, and JUNCTION nodes for M/I rail network
#! RunTime ~ 3 minutes and 15 seconds on my machine
#! ============================================================

import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.geometry import Point
from shapely.ops import nearest_points
from sklearn.cluster import DBSCAN
from scipy.spatial.distance import pdist, squareform

# --------------------------------------------------
# Paths
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

rail_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "M_and_I_Only",
    "North_American_Rail_Network_Lines_NET_M_I_GIANT.gpkg"
)

fra_nodes_path = os.path.join(
    base_dir,
    "Shapefiles",
    "North_American_Rail_Network_Nodes",
    "North_American_Rail_Network_Nodes.shp"
)

out_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Nodes",
    "Rail_Nodes_M_I_Yards_End_Junction.gpkg"
)

out_csv = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Nodes",
    "Yard_Node_Distance_Report.csv"
)

# --------------------------------------------------
# Parameters
# --------------------------------------------------
YARD_EXCLUSION_DIST = 1000
DIST_PREF_RATIO = 1.2
UNNAMED_CLUSTER_DIST = 5000
MERGE_TO_NAMED_DIST = 1000
ENDPOINT_TOL = 1
DUPLICATE_TOL = 5
SPATIAL_CLUSTER_DIST = 16093.4
FRA_SNAP_DIST = 5  # meters

# --------------------------------------------------
# Read rail data
# --------------------------------------------------
print("Reading rail data...")
gdf_rail_MI = gpd.read_file(rail_path).to_crs(epsg=5070)

gdf_M = gdf_rail_MI[gdf_rail_MI["NET"] == "M"].copy()
gdf_I = gdf_rail_MI[gdf_rail_MI["NET"] == "I"].copy()

print(f"Total M/I links: {len(gdf_rail_MI)}")
print(f"M links: {len(gdf_M)}")
print(f"I links: {len(gdf_I)}")

# --------------------------------------------------
# Read FRA node data (AUTHORITATIVE NODE IDS)
# --------------------------------------------------
print("Reading FRA node data...")
gdf_fra_nodes = (
    gpd.read_file(fra_nodes_path)
    .to_crs(gdf_rail_MI.crs)
    [["FRANODEID", "geometry"]]
    .drop_duplicates("FRANODEID")
)

fra_sindex = gdf_fra_nodes.sindex

# --------------------------------------------------
# HELPER: snap to FRA node
# --------------------------------------------------
def snap_to_fra_node(point, max_dist=FRA_SNAP_DIST):
    cand_idx = list(fra_sindex.intersection(point.buffer(max_dist).bounds))
    if not cand_idx:
        raise RuntimeError("No FRA node found near snapped geometry")

    cand = gdf_fra_nodes.iloc[cand_idx].copy()
    cand["dist"] = cand.geometry.distance(point)
    best = cand.loc[cand["dist"].idxmin()]

    return best["FRANODEID"], best.geometry

# --------------------------------------------------
# HELPER: Extract all endpoints from M/I network
# --------------------------------------------------
print("\nExtracting M/I link endpoints...")

m_endpoints = []
for idx, row in gdf_M.iterrows():
    line = row.geometry
    m_endpoints.append({
        "geometry": Point(line.coords[0]),
        "OBJECTID": row["OBJECTID"],
        "endpoint_type": "start",
        "link_index": idx
    })
    m_endpoints.append({
        "geometry": Point(line.coords[-1]),
        "OBJECTID": row["OBJECTID"],
        "endpoint_type": "end",
        "link_index": idx
    })

gdf_m_endpoints = gpd.GeoDataFrame(m_endpoints, crs=gdf_rail_MI.crs)

i_endpoints = []
for idx, row in gdf_I.iterrows():
    line = row.geometry
    i_endpoints.append({
        "geometry": Point(line.coords[0]),
        "OBJECTID": row["OBJECTID"],
        "endpoint_type": "start",
        "link_index": idx
    })
    i_endpoints.append({
        "geometry": Point(line.coords[-1]),
        "OBJECTID": row["OBJECTID"],
        "endpoint_type": "end",
        "link_index": idx
    })

gdf_i_endpoints = gpd.GeoDataFrame(i_endpoints, crs=gdf_rail_MI.crs)

print(f"M endpoints: {len(gdf_m_endpoints)}")
print(f"I endpoints: {len(gdf_i_endpoints)}")

# --------------------------------------------------
# HELPER FUNCTION: Cluster by pairwise maximum distance
# --------------------------------------------------
def cluster_by_max_pairwise_distance(coords, max_distance):
    if len(coords) == 1:
        return np.array([0])

    n = len(coords)
    labels = np.arange(n)
    dist_matrix = squareform(pdist(coords))

    merged = True
    while merged:
        merged = False
        for i in range(n):
            for j in range(i + 1, n):
                if labels[i] != labels[j]:
                    ci = np.where(labels == labels[i])[0]
                    cj = np.where(labels == labels[j])[0]
                    if np.all(dist_matrix[np.ix_(ci, cj)] <= max_distance):
                        labels[cj] = labels[i]
                        merged = True
                        break
            if merged:
                break

    uniq = np.unique(labels)
    return np.array([np.where(uniq == l)[0][0] for l in labels])

# --------------------------------------------------
# HELPER FUNCTION: Find nearest link endpoints
# --------------------------------------------------
def find_link_endpoints(point, gdf_links, gdf_endpoints):
    distances = gdf_endpoints.geometry.distance(point)
    min_idx = distances.idxmin()
    min_dist = distances.loc[min_idx]

    nearest_row = gdf_endpoints.loc[min_idx]
    link_idx = nearest_row["link_index"]
    line = gdf_links.loc[link_idx].geometry

    start_point = Point(line.coords[0])
    end_point = Point(line.coords[-1])

    return start_point, end_point, min_dist, link_idx

# --------------------------------------------------
# STEP 1: YARD nodes (named + unnamed)
# --------------------------------------------------
print("\nProcessing YARD nodes with spatial clustering...")
yard_records = []
yard_distance_records = []

named_yards = gdf_rail_MI[
    gdf_rail_MI["YARDNAME"].notna() &
    (gdf_rail_MI["YARDNAME"].astype(str).str.strip() != "") &
    (gdf_rail_MI["YARDNAME"] != 0)
]

named_centroids = []

for (yard, fips), grp in named_yards.groupby(["YARDNAME", "CNTYFIPS"]):

    centroids = grp.geometry.centroid
    coords = np.column_stack([centroids.x.values, centroids.y.values])

    cluster_labels = cluster_by_max_pairwise_distance(coords, SPATIAL_CLUSTER_DIST)

    for cluster_id in np.unique(cluster_labels):
        mask = cluster_labels == cluster_id
        cluster_centroids = centroids.iloc[mask]
        mean_pt = Point(cluster_centroids.x.mean(), cluster_centroids.y.mean())

        m_start, m_end, m_dist, _ = find_link_endpoints(mean_pt, gdf_M, gdf_m_endpoints)
        i_start, i_end, i_dist, _ = find_link_endpoints(mean_pt, gdf_I, gdf_i_endpoints)

        if m_dist <= DIST_PREF_RATIO * i_dist:
            snap_geom = m_start if mean_pt.distance(m_start) < mean_pt.distance(m_end) else m_end
            node_net = "YARD_M"
        else:
            snap_geom = i_start if mean_pt.distance(i_start) < mean_pt.distance(i_end) else i_end
            node_net = "YARD_I"

        franodeid, fra_geom = snap_to_fra_node(snap_geom)

        yard_name = f"{yard}_{cluster_id + 1}" if len(np.unique(cluster_labels)) > 1 else yard

        yard_records.append({
            "NODE_TYPE": "YARD",
            "NODE_NET": node_net,
            "NODE_OBJECTID": franodeid,
            "YARD_NAME": yard_name,
            "geometry": fra_geom
        })

        yard_distance_records.append({
            "YARD_NAME": yard_name,
            "NODE_NET": node_net,
            "NODE_OBJECTID": franodeid,
            "DISTANCE_METERS": mean_pt.distance(fra_geom)
        })

gdf_yards = gpd.GeoDataFrame(yard_records, crs=gdf_rail_MI.crs)

print(f"Total yard nodes: {len(gdf_yards)}")

# --------------------------------------------------
# STEP 2: END & JUNCTION nodes
# --------------------------------------------------
print("\nProcessing END and JUNCTION nodes...")

endpoints = []
for _, row in gdf_rail_MI.iterrows():
    line = row.geometry
    endpoints.append(Point(line.coords[0]))
    endpoints.append(Point(line.coords[-1]))

coords = np.column_stack([[p.x for p in endpoints], [p.y for p in endpoints]])
labels = DBSCAN(eps=ENDPOINT_TOL, min_samples=1).fit(coords).labels_

gdf_endpts = gpd.GeoDataFrame({"cluster": labels, "geometry": endpoints}, crs=gdf_rail_MI.crs)

node_records = []

for cid, grp in gdf_endpts.groupby("cluster"):
    mean_pt = grp.geometry.union_all().centroid
    franodeid, fra_geom = snap_to_fra_node(mean_pt)

    degree = (
        (gdf_rail_MI["FRFRANODE"] == franodeid) |
        (gdf_rail_MI["TOFRANODE"] == franodeid)
    ).sum()

    if degree == 1:
        node_type = "END"
    elif degree >= 3:
        node_type = "JUNCTION"
    else:
        continue

    node_records.append({
        "NODE_TYPE": node_type,
        "NODE_NET": f"{node_type}_MI",
        "NODE_OBJECTID": franodeid,
        "geometry": fra_geom
    })

gdf_other_nodes = gpd.GeoDataFrame(node_records, crs=gdf_rail_MI.crs)

# --------------------------------------------------
# STEP 3: Resolve conflicts (YARD always wins)
# --------------------------------------------------
yard_ids = set(gdf_yards["NODE_OBJECTID"])
gdf_other_nodes = gdf_other_nodes[
    ~gdf_other_nodes["NODE_OBJECTID"].isin(yard_ids)
]

# --------------------------------------------------
# STEP 4: Remove END nodes near YARDs
# --------------------------------------------------
yard_union = gdf_yards.geometry.union_all()
gdf_other_nodes = gdf_other_nodes[
    ~(
        (gdf_other_nodes["NODE_TYPE"] == "END") &
        (gdf_other_nodes.geometry.distance(yard_union) <= YARD_EXCLUSION_DIST)
    )
]

# --------------------------------------------------
# STEP 5: Combine & save
# --------------------------------------------------
gdf_other_nodes["YARD_NAME"] = None

gdf_all_nodes = gpd.GeoDataFrame(
    pd.concat([gdf_yards, gdf_other_nodes], ignore_index=True),
    crs=gdf_rail_MI.crs
)

print("\nFinal node counts:")
print(gdf_all_nodes["NODE_TYPE"].value_counts())

os.makedirs(os.path.dirname(out_path), exist_ok=True)
gdf_all_nodes.to_file(out_path, driver="GPKG")

print(f"\nSaved to: {out_path}")

# --------------------------------------------------
# STEP 6: Save distance report CSV
# --------------------------------------------------
df_distances = pd.DataFrame(yard_distance_records)
df_distances = df_distances.sort_values("DISTANCE_METERS", ascending=False)
df_distances.to_csv(out_csv, index=False)

print(f"Saved distance report to: {out_csv}")

# --------------------------------------------------
# FINAL VALIDATION
# --------------------------------------------------
edge_nodes = set(gdf_rail_MI["FRFRANODE"]).union(gdf_rail_MI["TOFRANODE"])
missing = set(gdf_all_nodes["NODE_OBJECTID"]) - edge_nodes

if missing:
    raise RuntimeError(f"{len(missing)} nodes not referenced by edges")

print("✓ FRA topology validation passed")
print("\nDone!")
# %%
#! ============================================================
#! 4
#! Where does the O network physically connect to the M/I backbone?
#! (FULL VERSION – FRANODEID INCLUDED)
#! ============================================================

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point
from sklearn.cluster import DBSCAN
import os

# --------------------------------------------------
# Paths (LINKS ONLY)
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

rail_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "M_and_I_Only",
    "North_American_Rail_Network_Lines_NET_M_I_GIANT.gpkg"
)

rail_o_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Yard_Normalized",
    "North_American_Rail_Network_Lines_YARD_NORMALIZED.gpkg"
)

fra_nodes_path = os.path.join(
    base_dir,
    "Shapefiles",
    "North_American_Rail_Network_Nodes",
    "North_American_Rail_Network_Nodes.shp"
)

out_gpkg = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "O_to_M_I_Junctions",
    "O_to_M_I_Junctions.gpkg"
)

# --------------------------------------------------
# Parameters
# --------------------------------------------------
ENDPOINT_TOL = 1   # meters
FRA_SNAP_TOL = 3   # meters

# --------------------------------------------------
# Read rail links
# --------------------------------------------------
print("Reading M/I backbone links...")
gdf_mi = gpd.read_file(rail_path).to_crs(epsg=5070)

print("Reading O-network links...")
gdf_o = gpd.read_file(rail_o_path).to_crs(epsg=5070)
gdf_o = gdf_o[gdf_o["NET"] == "O"].copy()

# Combine all links
gdf_links = pd.concat([gdf_mi, gdf_o], ignore_index=True)

# --------------------------------------------------
# Read FRA node table (AUTHORITATIVE)
# --------------------------------------------------
print("Reading FRA node table...")
gdf_fra_nodes = (
    gpd.read_file(fra_nodes_path)
    .to_crs(gdf_links.crs)
    [["FRANODEID", "geometry"]]
    .drop_duplicates("FRANODEID")
)

fra_sindex = gdf_fra_nodes.sindex

# --------------------------------------------------
# Helper: snap point to FRANODEID
# --------------------------------------------------
def snap_to_fra_node(point, tol=FRA_SNAP_TOL):
    idx = list(fra_sindex.intersection(point.buffer(tol).bounds))
    if not idx:
        return None, None

    cand = gdf_fra_nodes.iloc[idx].copy()
    cand["dist"] = cand.geometry.distance(point)
    best = cand.loc[cand["dist"].idxmin()]

    return best["FRANODEID"], best.geometry

# --------------------------------------------------
# Extract endpoints from all links
# --------------------------------------------------
records = []

for _, row in gdf_links.iterrows():
    geom = row.geometry
    records.append({
        "geometry": Point(geom.coords[0]),
        "OBJECTID": row["OBJECTID"],
        "NET": row["NET"]
    })
    records.append({
        "geometry": Point(geom.coords[-1]),
        "OBJECTID": row["OBJECTID"],
        "NET": row["NET"]
    })

gdf_pts = gpd.GeoDataFrame(records, crs=gdf_links.crs)

# --------------------------------------------------
# Cluster coincident endpoints
# --------------------------------------------------
coords = np.column_stack([
    gdf_pts.geometry.x.values,
    gdf_pts.geometry.y.values
])

clustering = DBSCAN(
    eps=ENDPOINT_TOL,
    min_samples=1
).fit(coords)

gdf_pts["cluster"] = clustering.labels_

# --------------------------------------------------
# Identify O ↔ M/I junctions (DOF ≥ 3)
# --------------------------------------------------
junction_records = []

for cid, grp in gdf_pts.groupby("cluster"):
    dof = grp["OBJECTID"].nunique()
    nets = set(grp["NET"])

    if dof < 3:
        continue

    if not ("O" in nets and ("M" in nets or "I" in nets)):
        continue

    mean_pt = Point(grp.geometry.x.mean(), grp.geometry.y.mean())
    franodeid, fra_geom = snap_to_fra_node(mean_pt)

    if franodeid is None:
        continue

    junction_records.append({
        "FRANODEID": franodeid,
        "DOF": dof,
        "CONNECTED_NETS": ",".join(sorted(nets)),
        "geometry": fra_geom
    })

# --------------------------------------------------
# Output GeoDataFrame
# --------------------------------------------------
gdf_out = gpd.GeoDataFrame(
    junction_records,
    crs=gdf_links.crs
)

# --------------------------------------------------
# Save
# --------------------------------------------------
os.makedirs(os.path.dirname(out_gpkg), exist_ok=True)

gdf_out.to_file(
    out_gpkg,
    layer="O_M_I_Junctions_DOF3",
    driver="GPKG"
)

print(f"Found {len(gdf_out)} O–M/I junctions with DOF ≥ 3.")
print(f"Saved to: {out_gpkg}")

#%%
#! ============================================================
#! 5
#! Which counties need an O_JUNCTION node, and where should it be placed?
#! ============================================================


import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.geometry import Point

# --------------------------------------------------
# Paths (PROCESSED DATA ONLY)
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

rail_nodes_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Nodes",
    "Rail_Nodes_M_I_Yards_End_Junction.gpkg"
)

county_gpkg = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "faf_county_with_flows_CONUS.gpkg"
)

o_junctions_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "O_to_M_I_Junctions",
    "O_to_M_I_Junctions.gpkg"
)

output_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Nodes",
    "Rail_Nodes_M_I_Yards_End_Junction_with_O.gpkg"
)

# --------------------------------------------------
# Read data
# --------------------------------------------------
print("Reading data...")
gdf_counties = gpd.read_file(county_gpkg)
gdf_nodes = gpd.read_file(rail_nodes_path)
gdf_o_junctions = gpd.read_file(o_junctions_path, layer="O_M_I_Junctions_DOF3")

print(f"Counties: {len(gdf_counties)}")
print(f"Existing nodes: {len(gdf_nodes)}")
print(f"O junctions: {len(gdf_o_junctions)}")

# Make sure all are in same CRS
gdf_counties = gdf_counties.to_crs(epsg=5070)
gdf_nodes = gdf_nodes.to_crs(epsg=5070)
gdf_o_junctions = gdf_o_junctions.to_crs(epsg=5070)

# --------------------------------------------------
# STEP 1: Filter counties with freight flow (tons > 0)
# --------------------------------------------------
print("\n" + "="*70)
print("STEP 1: Filtering counties with freight flow")
print("="*70)

counties_with_flow = gdf_counties[
    (gdf_counties["out_sum_tons_2024"]  > 0) |
    (gdf_counties["in_sum_tons_2024"]   > 0) |
    (gdf_counties["out_sum_value_2024"] > 0) |
    (gdf_counties["in_sum_value_2024"]  > 0) |
    (gdf_counties["out_sum_tons_2050"]  > 0) |
    (gdf_counties["in_sum_tons_2050"]   > 0) |
    (gdf_counties["out_sum_value_2050"] > 0) |
    (gdf_counties["in_sum_value_2050"]  > 0)
].copy()

print(f"Counties with out_sum_tons_2024 > 0 OR in_sum_tons_2024 > 0: {len(counties_with_flow)}")

# --------------------------------------------------
# STEP 2: Filter counties without YARD or END nodes
# --------------------------------------------------
print("\n" + "="*70)
print("STEP 2: Finding counties without YARD or END nodes")
print("="*70)

# Spatial join to count nodes in each county
nodes_in_counties = gpd.sjoin(
    gdf_nodes,
    counties_with_flow[["GEOID", "geometry"]],
    how="inner",
    predicate="within"
)

print(f"Total nodes in counties with flow: {len(nodes_in_counties)}")

# Count YARD and END nodes per county
yard_end_counts = (
    nodes_in_counties[nodes_in_counties["NODE_TYPE"].isin(["YARD", "END"])]
    .groupby("GEOID")
    .size()
    .reset_index(name="yard_end_count")
)

print(f"\nCounties with at least one YARD or END node: {len(yard_end_counts)}")

# Filter counties: have flow BUT no YARD or END nodes
counties_needing_o_node = counties_with_flow[
    ~counties_with_flow["GEOID"].isin(yard_end_counts["GEOID"])
].copy()

print(f"\nCounties with flow but NO YARD or END nodes: {len(counties_needing_o_node)}")

# Show some statistics about these counties
if len(counties_needing_o_node) > 0:
    # Check if they have JUNCTION nodes
    junction_in_counties = (
        nodes_in_counties[nodes_in_counties["NODE_TYPE"] == "JUNCTION"]
        .groupby("GEOID")
        .size()
        .reset_index(name="junction_count")
    )
    
    counties_needing_o_node = counties_needing_o_node.merge(
        junction_in_counties,
        on="GEOID",
        how="left"
    )
    counties_needing_o_node["junction_count"] = counties_needing_o_node["junction_count"].fillna(0)
    
    print(f"\nOf these {len(counties_needing_o_node)} counties:")
    print(f"  - With JUNCTION nodes: {(counties_needing_o_node['junction_count'] > 0).sum()}")
    print(f"  - Without any nodes: {(counties_needing_o_node['junction_count'] == 0).sum()}")
    
    print(f"\nSample counties needing O junction nodes:")
    print(counties_needing_o_node[["GEOID", "NAME", "out_sum_tons_2024", "in_sum_tons_2024", "junction_count"]].head(10))

# --------------------------------------------------
# STEP 3: Select one O junction per county (closest to centroid)
# --------------------------------------------------
print("\n" + "="*70)
print("STEP 3: Selecting closest O junction to county centroid")
print("="*70)

selected_o_nodes = []

for idx, county in counties_needing_o_node.iterrows():
    county_geoid = county["GEOID"]
    county_geom = county.geometry
    county_centroid = county_geom.centroid
    
    # Find O junctions within this county
    o_junctions_in_county = gdf_o_junctions[
        gdf_o_junctions.geometry.within(county_geom)
    ].copy()
    
    if len(o_junctions_in_county) == 0:
        print(f"  WARNING: County {county_geoid} ({county.get('NAME', 'Unknown')}) has no O junctions - skipping")
        continue
    
    # Calculate distance to centroid
    o_junctions_in_county["dist_to_centroid"] = o_junctions_in_county.geometry.distance(county_centroid)
    
    # Select the closest one
    closest_idx = o_junctions_in_county["dist_to_centroid"].idxmin()
    closest_o_junction = o_junctions_in_county.loc[closest_idx]
    
    # Store the selected node
    selected_o_nodes.append({
        "GEOID": county_geoid,
        "COUNTY_NAME": county.get("NAME", "Unknown"),
        "NODE_TYPE": "O_JUNCTION",
        "NODE_NET": "O",
        "NODE_OBJECTID": closest_o_junction["FRANODEID"],
        "YARD_NAME": None,
        "geometry": closest_o_junction.geometry,
        "original_DoF": closest_o_junction.get("DOF", None),
        "dist_to_centroid": closest_o_junction["dist_to_centroid"]
    })

    
print(f"\nSelected {len(selected_o_nodes)} O junction nodes (one per county)")

if len(selected_o_nodes) > 0:
    df_selected = pd.DataFrame(selected_o_nodes)
    print(f"\nDistance to centroid statistics (meters):")
    print(df_selected["dist_to_centroid"].describe())
    
    print(f"\nSample selected O junctions:")
    print(df_selected[["GEOID", "COUNTY_NAME", "dist_to_centroid"]].head(10))

# --------------------------------------------------
# STEP 4: Append to existing nodes and save
# --------------------------------------------------
print("\n" + "="*70)
print("STEP 4: Appending O junction nodes to existing nodes")
print("="*70)

if len(selected_o_nodes) == 0:
    print("No O junction nodes to add. Saving original nodes only.")
    gdf_final_nodes = gdf_nodes.copy()
else:
    # Create GeoDataFrame from selected O nodes
    gdf_new_o_nodes = gpd.GeoDataFrame(
        selected_o_nodes,
        geometry="geometry",
        crs=gdf_nodes.crs
    )
    
    # Keep only the fields that match the original nodes
    gdf_new_o_nodes_final = gdf_new_o_nodes[["NODE_TYPE", "NODE_NET", "NODE_OBJECTID", "YARD_NAME", "geometry"]].copy()
    
    # Combine with existing nodes
    gdf_final_nodes = pd.concat(
        [
            gdf_nodes[["NODE_TYPE", "NODE_NET", "NODE_OBJECTID", "YARD_NAME", "geometry"]],
            gdf_new_o_nodes_final
        ],
        ignore_index=True
    )
    
    gdf_final_nodes = gpd.GeoDataFrame(gdf_final_nodes, geometry="geometry", crs=gdf_nodes.crs)
    
    print(f"\nOriginal nodes: {len(gdf_nodes)}")
    print(f"New O junction nodes: {len(gdf_new_o_nodes_final)}")
    print(f"Total nodes: {len(gdf_final_nodes)}")

# --------------------------------------------------
# Save to file
# --------------------------------------------------
print("\nSaving to file...")
os.makedirs(os.path.dirname(output_path), exist_ok=True)
gdf_final_nodes.to_file(output_path, driver="GPKG")

print(f"Saved to: {output_path}")

# --------------------------------------------------
# Summary
# --------------------------------------------------
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"""
Process completed successfully!

Input:
  - Counties with freight flow: {len(counties_with_flow)}
  - Counties without YARD or END nodes: {len(counties_needing_o_node)}
  - O junctions available: {len(gdf_o_junctions)}

Output:
  - Original nodes: {len(gdf_nodes)}
  - Added O junction nodes: {len(selected_o_nodes)}
  - Total nodes in output: {len(gdf_final_nodes)}

Node type distribution in final output:
{gdf_final_nodes['NODE_TYPE'].value_counts().to_dict()}

The new nodes have:
  - NODE_TYPE: O_JUNCTION
  - NODE_NET: O
  - NODE_OBJECTID: None
  - YARD_NAME: None
""")

print("\nDone!")

# --------------------------------------------------
# ANALYSIS: Node frequency bar chart
# --------------------------------------------------
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# --------------------------------------------------
# Count nodes
# --------------------------------------------------
node_counts = (
    gdf_final_nodes["NODE_TYPE"]
    .value_counts()
    .sort_values(ascending=False)
)

total_nodes = node_counts.sum()

node_percentages = (node_counts / total_nodes) * 100

# --------------------------------------------------
# Create plot
# --------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 6))

bars = ax.bar(
    node_counts.index,
    node_counts.values
)

# Titles and labels
ax.set_title("Node Frequency by Node Type", fontsize=14)
ax.set_xlabel("Node Type", fontsize=12)
ax.set_ylabel("Number of Nodes", fontsize=12)

# Grid
ax.grid(axis="y", linestyle="--", alpha=0.6)

# 10% headroom
ax.set_ylim(0, node_counts.max() * 1.10)

# --------------------------------------------------
# Annotate bars with count and percentage
# --------------------------------------------------
for bar, count, perc in zip(bars, node_counts.values, node_percentages.values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height(),
        f"{count}\n({perc:.1f}%)",
        ha="center",
        va="bottom",
        fontsize=10
    )

# --------------------------------------------------
# Legend (including sum of all nodes)
# --------------------------------------------------
legend_handles = list(bars)

legend_labels = [
    f"{node_type}: {count} ({perc:.1f}%)"
    for node_type, count, perc in zip(
        node_counts.index,
        node_counts.values,
        node_percentages.values
    )
]

# Dummy handle for total sum (text-only)
total_handle = Patch(
    facecolor="none",
    edgecolor="none"
)

legend_handles.append(total_handle)
legend_labels.append(f"Sum of all nodes: {total_nodes:,}")

ax.legend(
    handles=legend_handles,
    labels=legend_labels,
    title="Node Summary",
    loc="upper right",
    frameon=True
)

# X-axis formatting
plt.xticks(rotation=45, ha="right")

plt.tight_layout()
plt.show()

#%%
# #! ============================================================
# #! 6
# #! Create rail graph edges and map to nodes
# #! RunTime ~ 41 minutes and 30 seconds on my machine
# #! ============================================================

# import geopandas as gpd
# import pandas as pd
# import numpy as np
# import os
# from shapely.geometry import Point, LineString
# from collections import defaultdict

# # --------------------------------------------------
# # Paths
# # --------------------------------------------------
# base_dir = os.path.abspath(os.path.join("..", ".."))

# rail_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "M_and_I_Only",
#     "North_American_Rail_Network_Lines_NET_M_I_GIANT.gpkg"
# )

# node_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Rail_Nodes",
#     "Rail_Nodes_M_I_Yards_End_Junction_with_O.gpkg"
# )

# out_gpkg = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Rail_Graph",
#     "Rail_Graph_Nodes_Edges.gpkg"
# )

# # --------------------------------------------------
# # Read data
# # --------------------------------------------------
# print("Reading data...")
# gdf_links = gpd.read_file(rail_path).to_crs(epsg=5070)
# gdf_nodes = gpd.read_file(node_path).to_crs(epsg=5070)

# print(f"Original links: {len(gdf_links)}")
# print(f"Major nodes from file: {len(gdf_nodes)}")

# # Only M/I links
# gdf_links = gdf_links[gdf_links["NET"].isin(["M", "I"])].copy()
# gdf_links = gdf_links.reset_index(drop=True)
# print(f"M/I links to process: {len(gdf_links)}")

# # --------------------------------------------------
# # Assign NODE_ID to major nodes
# # --------------------------------------------------
# gdf_nodes = gdf_nodes.reset_index(drop=True)
# gdf_nodes["NODE_ID"] = gdf_nodes.index.astype(int)

# print(f"\nMajor node types: {gdf_nodes['NODE_TYPE'].value_counts().to_dict()}")

# # --------------------------------------------------
# # STEP 1: Extract ALL unique endpoints from M/I links
# # --------------------------------------------------
# print("\nExtracting all unique endpoints from M/I links...")

# all_endpoints = []
# for idx, row in gdf_links.iterrows():
#     line = row.geometry
#     all_endpoints.append({
#         "geometry": Point(line.coords[0]),
#         "link_idx": idx,
#         "endpoint_type": "start"
#     })
#     all_endpoints.append({
#         "geometry": Point(line.coords[-1]),
#         "link_idx": idx,
#         "endpoint_type": "end"
#     })

# gdf_all_endpoints = gpd.GeoDataFrame(all_endpoints, crs=gdf_links.crs)

# # Cluster endpoints to find unique locations (tolerance = 1 meter)
# from sklearn.cluster import DBSCAN

# coords = np.column_stack([
#     gdf_all_endpoints.geometry.x.values,
#     gdf_all_endpoints.geometry.y.values
# ])

# clustering = DBSCAN(eps=1, min_samples=1).fit(coords)
# gdf_all_endpoints["cluster"] = clustering.labels_

# # Get unique endpoint locations
# unique_endpoint_clusters = gdf_all_endpoints.groupby("cluster").agg({
#     "geometry": lambda x: Point(x.iloc[0].x, x.iloc[0].y)  # Use first point as representative
# }).reset_index()

# print(f"Total unique endpoint locations: {len(unique_endpoint_clusters)}")

# # --------------------------------------------------
# # STEP 2: Match major nodes to endpoint clusters
# # --------------------------------------------------
# print("\nMatching major nodes to endpoint clusters...")

# # For each major node, find the closest endpoint cluster
# major_node_to_cluster = {}
# tolerance = 10  # 10 meters tolerance (some junctions are 3-5m from endpoints)

# for idx, node in gdf_nodes.iterrows():
#     node_pt = node.geometry
    
#     # Find closest endpoint cluster
#     distances = unique_endpoint_clusters["geometry"].distance(node_pt)
#     min_idx = distances.idxmin()
#     min_dist = distances.loc[min_idx]
    
#     if min_dist < tolerance:
#         cluster_id = unique_endpoint_clusters.loc[min_idx, "cluster"]
#         major_node_to_cluster[node["NODE_ID"]] = cluster_id
#     else:
#         print(f"  WARNING: Major node {node['NODE_ID']} ({node['NODE_TYPE']}) has no nearby endpoint (closest: {min_dist:.2f}m)")

# print(f"Matched {len(major_node_to_cluster)} major nodes to endpoint clusters")

# # Create reverse mapping: cluster -> NODE_ID (for major nodes only)
# cluster_to_major_node = {v: k for k, v in major_node_to_cluster.items()}

# # --------------------------------------------------
# # STEP 3: Assign NODE_ID to ALL endpoints (major or intermediate)
# # --------------------------------------------------
# print("\nAssigning NODE_ID to all link endpoints...")

# # Create a complete node list: major nodes + intermediate nodes
# all_node_records = []
# next_node_id = len(gdf_nodes)  # Start IDs after major nodes

# # Add major nodes
# for idx, node in gdf_nodes.iterrows():
#     all_node_records.append({
#         "NODE_ID": node["NODE_ID"],
#         "NODE_TYPE": node["NODE_TYPE"],
#         "IS_MAJOR": True,
#         "cluster": major_node_to_cluster.get(node["NODE_ID"], -1),
#         "geometry": node.geometry
#     })

# # Add intermediate nodes (endpoint clusters not matched to major nodes)
# for idx, cluster_row in unique_endpoint_clusters.iterrows():
#     cluster_id = cluster_row["cluster"]
    
#     if cluster_id not in cluster_to_major_node:
#         # This is an intermediate node
#         all_node_records.append({
#             "NODE_ID": next_node_id,
#             "NODE_TYPE": "INTERMEDIATE",
#             "IS_MAJOR": False,
#             "cluster": cluster_id,
#             "geometry": cluster_row["geometry"]
#         })
#         cluster_to_major_node[cluster_id] = next_node_id
#         next_node_id += 1

# gdf_all_nodes = gpd.GeoDataFrame(all_node_records, crs=gdf_nodes.crs)

# print(f"Total nodes (major + intermediate): {len(gdf_all_nodes)}")
# print(f"  Major nodes: {gdf_all_nodes['IS_MAJOR'].sum()}")
# print(f"  Intermediate nodes: {(~gdf_all_nodes['IS_MAJOR']).sum()}")

# # --------------------------------------------------
# # STEP 4: Map link endpoints to NODE_ID
# # --------------------------------------------------
# print("\nMapping link endpoints to NODE_IDs...")

# # Add cluster ID to each endpoint
# gdf_all_endpoints["NODE_ID"] = gdf_all_endpoints["cluster"].map(cluster_to_major_node)

# # Now map to links
# link_from_nodes = {}
# link_to_nodes = {}

# for idx, row in gdf_links.iterrows():
#     # Get endpoints for this link
#     start_endpoints = gdf_all_endpoints[(gdf_all_endpoints["link_idx"] == idx) & 
#                                        (gdf_all_endpoints["endpoint_type"] == "start")]
#     end_endpoints = gdf_all_endpoints[(gdf_all_endpoints["link_idx"] == idx) & 
#                                      (gdf_all_endpoints["endpoint_type"] == "end")]
    
#     if len(start_endpoints) > 0:
#         link_from_nodes[idx] = start_endpoints.iloc[0]["NODE_ID"]
    
#     if len(end_endpoints) > 0:
#         link_to_nodes[idx] = end_endpoints.iloc[0]["NODE_ID"]

# gdf_links["FROM_NODE"] = gdf_links.index.map(link_from_nodes)
# gdf_links["TO_NODE"] = gdf_links.index.map(link_to_nodes)

# # Check for unmapped links
# unmapped = gdf_links[(gdf_links["FROM_NODE"].isna()) | (gdf_links["TO_NODE"].isna())]
# print(f"Links with unmapped endpoints: {len(unmapped)}")

# if len(unmapped) > 0:
#     print("\nWARNING: Some links have unmapped endpoints!")
#     print("This should not happen. Sample unmapped links:")
#     print(unmapped[["OBJECTID", "FROM_NODE", "TO_NODE"]].head())

# # --------------------------------------------------
# # STEP 5: Build bidirectional adjacency
# # --------------------------------------------------
# print("\nBuilding adjacency list...")

# # Build adjacency: node -> list of (link_idx, neighbor_node, link_data) tuples
# adjacency = defaultdict(list)

# for idx, row in gdf_links.iterrows():
#     if pd.notna(row["FROM_NODE"]) and pd.notna(row["TO_NODE"]):
#         from_node = int(row["FROM_NODE"])
#         to_node = int(row["TO_NODE"])
        
#         # Add both directions (each link can be traversed both ways)
#         adjacency[from_node].append((idx, to_node, row))
#         adjacency[to_node].append((idx, from_node, row))

# # Calculate node degrees
# node_degrees = {node: len(neighbors) for node, neighbors in adjacency.items()}
# print(f"Nodes with connections: {len(node_degrees)}")

# degree_dist = pd.Series(node_degrees.values()).value_counts().sort_index()
# print(f"\nDegree distribution:")
# for deg, count in degree_dist.items():
#     print(f"  Degree {deg}: {count} nodes")

# # Identify major nodes (from the major nodes file)
# major_node_ids = set(gdf_nodes["NODE_ID"].values)
# print(f"\nMajor nodes (from file): {len(major_node_ids)}")

# # --------------------------------------------------
# # STEP 6: Walk and merge links between major nodes
# # --------------------------------------------------
# print("\nMerging links between major nodes...")
# print("(Walking through intermediate nodes, stopping at major nodes)")

# visited_links = set()
# edges = []
# edge_count = 0

# # Process each link exactly once
# for link_idx in gdf_links.index:
#     if link_idx in visited_links:
#         continue
    
#     if pd.isna(gdf_links.loc[link_idx, "FROM_NODE"]) or pd.isna(gdf_links.loc[link_idx, "TO_NODE"]):
#         continue
    
#     edge_count += 1
#     if edge_count % 5000 == 0:
#         print(f"  Processed {edge_count}/{len(gdf_links)} links...")
    
#     link_row = gdf_links.loc[link_idx]
    
#     # Start with this link
#     forward_path = [link_idx]
#     visited_links.add(link_idx)
    
#     # Walk forward from TO_NODE
#     current_node = int(link_row["TO_NODE"])
    
#     # Keep walking while current node is NOT a major node AND has degree 2
#     while current_node not in major_node_ids and node_degrees.get(current_node, 0) == 2:
#         # Find the other link at this intermediate node (not the one we came from)
#         neighbors = [n for n in adjacency[current_node] if n[0] not in visited_links]
        
#         if len(neighbors) != 1:
#             break
        
#         next_link_idx, next_node, next_link = neighbors[0]
        
#         forward_path.append(next_link_idx)
#         visited_links.add(next_link_idx)
#         current_node = next_node
    
#     end_node = current_node
    
#     # Walk backward from FROM_NODE
#     backward_path = []
#     current_node = int(link_row["FROM_NODE"])
    
#     # Keep walking while current node is NOT a major node AND has degree 2
#     while current_node not in major_node_ids and node_degrees.get(current_node, 0) == 2:
#         # Find the other link at this intermediate node (not the one we came from)
#         neighbors = [n for n in adjacency[current_node] if n[0] not in visited_links]
        
#         if len(neighbors) != 1:
#             break
        
#         next_link_idx, next_node, next_link = neighbors[0]
        
#         backward_path.append(next_link_idx)
#         visited_links.add(next_link_idx)
#         current_node = next_node
    
#     start_node = current_node
    
#     # Combine paths: backward (reversed) + current link + forward
#     full_path = list(reversed(backward_path)) + forward_path
    
#     # Get all links in the path
#     path_links = [gdf_links.loc[idx] for idx in full_path]
    
#     # Build merged geometry (single LineString)
#     coords = []
#     for i, link in enumerate(path_links):
#         link_coords = list(link.geometry.coords)
        
#         if i == 0:
#             # First link: determine orientation
#             # We're walking from start_node
#             link_from = int(link["FROM_NODE"])
#             link_to = int(link["TO_NODE"])
            
#             if link_from == start_node:
#                 # Link goes in forward direction
#                 coords.extend(link_coords)
#             else:
#                 # Link goes in reverse direction
#                 coords.extend(reversed(link_coords))
#         else:
#             # Subsequent links: match to previous endpoint
#             prev_end = Point(coords[-1])
#             link_start = Point(link_coords[0])
#             link_end = Point(link_coords[-1])
            
#             if link_start.distance(prev_end) < link_end.distance(prev_end):
#                 # Same direction - skip duplicate first point
#                 coords.extend(link_coords[1:])
#             else:
#                 # Reverse direction - skip duplicate last point
#                 coords.extend(list(reversed(link_coords))[1:])
    
#     # Create the merged geometry
#     merged_geom = LineString(coords)
    
#     # Store the edge
#     edges.append({
#         "FROM_NODE": start_node,
#         "TO_NODE": end_node,
#         "NET": path_links[0]["NET"],
#         "LENGTH": sum(link.geometry.length for link in path_links),
#         "NUM_MERGED": len(path_links),
#         "MERGED_OBJECTIDS": ",".join(str(gdf_links.loc[idx, "OBJECTID"]) for idx in full_path),
#         "geometry": merged_geom
#     })

# print(f"\nTotal edges created: {len(edges)}")

# gdf_edges = gpd.GeoDataFrame(edges, crs=gdf_links.crs)

# # --------------------------------------------------
# # Add degree information to major nodes only
# # --------------------------------------------------
# print("\nAdding degree information to major nodes...")
# gdf_nodes["DEGREE"] = gdf_nodes["NODE_ID"].apply(lambda x: node_degrees.get(int(x), 0))

# # --------------------------------------------------
# # Validate results
# # --------------------------------------------------
# print("\n" + "="*70)
# print("VALIDATION RESULTS")
# print("="*70)
# print(f"Original M/I links: {len(gdf_links)}")
# print(f"Final edges: {len(gdf_edges)}")
# print(f"Total links merged into edges: {gdf_edges['NUM_MERGED'].sum()}")
# print(f"Links visited: {len(visited_links)}")

# if gdf_edges['NUM_MERGED'].sum() == len(gdf_links):
#     print("\n✓ SUCCESS: All links accounted for!")
# else:
#     missing = len(gdf_links) - gdf_edges['NUM_MERGED'].sum()
#     print(f"\n✗ WARNING: {missing} links difference!")
#     print(f"  This might be due to unmapped endpoints")

# print(f"\nEdge merging statistics:")
# print(f"  Average links per edge: {gdf_edges['NUM_MERGED'].mean():.2f}")
# print(f"  Median links per edge: {gdf_edges['NUM_MERGED'].median():.0f}")
# print(f"  Max links in one edge: {gdf_edges['NUM_MERGED'].max()}")
# print(f"  Edges with 1 link (no merging): {(gdf_edges['NUM_MERGED'] == 1).sum()}")
# print(f"  Edges with 2+ links (merged): {(gdf_edges['NUM_MERGED'] > 1).sum()}")

# print(f"\nEdge length statistics (meters):")
# print(gdf_edges['LENGTH'].describe())

# # Check edge endpoint node types
# print(f"\nEdge endpoints by node type:")
# from_types = []
# to_types = []

# for _, edge in gdf_edges.iterrows():
#     from_node_info = gdf_nodes[gdf_nodes["NODE_ID"] == edge["FROM_NODE"]]
#     to_node_info = gdf_nodes[gdf_nodes["NODE_ID"] == edge["TO_NODE"]]
    
#     if len(from_node_info) > 0:
#         from_types.append(from_node_info.iloc[0]["NODE_TYPE"])
#     else:
#         from_types.append("INTERMEDIATE")
    
#     if len(to_node_info) > 0:
#         to_types.append(to_node_info.iloc[0]["NODE_TYPE"])
#     else:
#         to_types.append("INTERMEDIATE")

# from_counts = pd.Series(from_types).value_counts()
# to_counts = pd.Series(to_types).value_counts()

# print(f"  FROM_NODE types:")
# for node_type, count in from_counts.items():
#     print(f"    {node_type}: {count}")

# print(f"  TO_NODE types:")
# for node_type, count in to_counts.items():
#     print(f"    {node_type}: {count}")

# # --------------------------------------------------
# # Save GeoPackage
# # --------------------------------------------------
# print("\nSaving to GeoPackage...")
# os.makedirs(os.path.dirname(out_gpkg), exist_ok=True)

# # Save only major nodes (not intermediate nodes)
# gdf_nodes.to_file(out_gpkg, layer="nodes", driver="GPKG")
# gdf_edges.to_file(out_gpkg, layer="edges", driver="GPKG")

# print(f"\nSaved to: {out_gpkg}")
# print(f"  - Layer 'nodes': {len(gdf_nodes)} major nodes with DEGREE field")
# print(f"  - Layer 'edges': {len(gdf_edges)} edges")

# print("\n" + "="*70)
# print("SUMMARY")
# print("="*70)
# print(f"""
# Input:
#   - {len(gdf_links)} M/I rail links
#   - {len(gdf_nodes)} major nodes (YARD/END/JUNCTION)
#   - {len(gdf_all_nodes) - len(gdf_nodes)} intermediate nodes (auto-detected)

# Output:
#   - {len(gdf_edges)} simplified edges
#   - Each edge connects nodes (may be major or intermediate at endpoints)
#   - Intermediate degree-2 nodes are merged through
#   - All original link OBJECTIDs tracked in MERGED_OBJECTIDS field

# Usage for shortest path:
#   - Use edges layer for routing
#   - FROM_NODE and TO_NODE reference nodes layer
#   - LENGTH field for distance-based routing
#   - MERGED_OBJECTIDS traces back to original links
# """)

# print("\nDone!")

#%%
#! ============================================================
#! 6
#! Create rail graph edges and map to nodes (FRA ID VERSION)
#! RunTime ~ 41 minutes and 30 seconds on my machine
#! ============================================================

import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.geometry import Point, LineString
from collections import defaultdict

# --------------------------------------------------
# Paths
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

rail_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "M_and_I_Only",
    "North_American_Rail_Network_Lines_NET_M_I_GIANT.gpkg"
)

node_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Nodes",
    "Rail_Nodes_M_I_Yards_End_Junction_with_O.gpkg"
)

fra_nodes_path = os.path.join(
    base_dir,
    "Shapefiles",
    "North_American_Rail_Network_Nodes",
    "North_American_Rail_Network_Nodes.shp"
)

out_gpkg = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Graph",
    "Rail_Graph_Nodes_Edges.gpkg"
)

# --------------------------------------------------
# Read data
# --------------------------------------------------
print("Reading data...")
gdf_links = gpd.read_file(rail_path).to_crs(epsg=5070)
gdf_nodes = gpd.read_file(node_path).to_crs(epsg=5070)
gdf_fra_nodes = gpd.read_file(fra_nodes_path).to_crs(epsg=5070)

print(f"Original links: {len(gdf_links)}")
print(f"Major nodes from file: {len(gdf_nodes)}")
print(f"FRA nodes (reference): {len(gdf_fra_nodes)}")

# Only M/I links
gdf_links = gdf_links[gdf_links["NET"].isin(["M", "I"])].copy()
gdf_links = gdf_links.reset_index(drop=True)
print(f"M/I links to process: {len(gdf_links)}")

# Verify links have FRFRANODE and TOFRANODE
if "FRFRANODE" not in gdf_links.columns or "TOFRANODE" not in gdf_links.columns:
    raise ValueError("Links must have FRFRANODE and TOFRANODE fields from FRA data")

print(f"\nMajor node types: {gdf_nodes['NODE_TYPE'].value_counts().to_dict()}")

# --------------------------------------------------
# Verify all major nodes have NODE_OBJECTID (which should be FRANODEID)
# --------------------------------------------------
if gdf_nodes["NODE_OBJECTID"].isna().any():
    raise ValueError("Some major nodes are missing NODE_OBJECTID (FRANODEID)")

# Rename NODE_OBJECTID to FRANODEID for clarity
gdf_nodes = gdf_nodes.rename(columns={"NODE_OBJECTID": "FRANODEID"})
print(f"\nAll major nodes have FRANODEID: {len(gdf_nodes)}")

# Create set of major node FRANODEIDs
major_node_ids = set(gdf_nodes["FRANODEID"].values)
print(f"Unique major node FRANODEIDs: {len(major_node_ids)}")

# --------------------------------------------------
# STEP 1: Build adjacency using FRFRANODE and TOFRANODE
# --------------------------------------------------
print("\nBuilding adjacency list using FRA node IDs...")

# Build adjacency: FRANODEID -> list of (link_idx, neighbor_FRANODEID, link_data) tuples
adjacency = defaultdict(list)

for idx, row in gdf_links.iterrows():
    from_node = row["FRFRANODE"]
    to_node = row["TOFRANODE"]
    
    if pd.notna(from_node) and pd.notna(to_node):
        # Add both directions (each link can be traversed both ways)
        adjacency[from_node].append((idx, to_node, row))
        adjacency[to_node].append((idx, from_node, row))

# Calculate node degrees
node_degrees = {node: len(neighbors) for node, neighbors in adjacency.items()}
print(f"Nodes with connections: {len(node_degrees)}")

degree_dist = pd.Series(node_degrees.values()).value_counts().sort_index()
print(f"\nDegree distribution:")
for deg, count in degree_dist.items():
    print(f"  Degree {deg}: {count} nodes")

# Identify intermediate nodes (degree-2 nodes that are NOT major nodes)
intermediate_nodes = {
    node for node, deg in node_degrees.items() 
    if deg == 2 and node not in major_node_ids
}
print(f"\nIntermediate nodes (degree-2, non-major): {len(intermediate_nodes)}")

# --------------------------------------------------
# STEP 2: Walk and merge links between major nodes
# --------------------------------------------------
print("\nMerging links between major nodes...")
print("(Walking through intermediate nodes, stopping at major nodes)")

visited_links = set()
edges = []
edge_count = 0

# Process each link exactly once
for link_idx in gdf_links.index:
    if link_idx in visited_links:
        continue
    
    edge_count += 1
    if edge_count % 5000 == 0:
        print(f"  Processed {edge_count}/{len(gdf_links)} links...")
    
    link_row = gdf_links.loc[link_idx]
    
    # Start with this link
    forward_path = [link_idx]
    visited_links.add(link_idx)
    
    # Walk forward from TOFRANODE
    current_node = link_row["TOFRANODE"]
    
    # Keep walking while current node is intermediate (degree-2, non-major)
    while current_node in intermediate_nodes:
        # Find the other link at this intermediate node (not the one we came from)
        neighbors = [n for n in adjacency[current_node] if n[0] not in visited_links]
        
        if len(neighbors) != 1:
            break
        
        next_link_idx, next_node, next_link = neighbors[0]
        
        forward_path.append(next_link_idx)
        visited_links.add(next_link_idx)
        current_node = next_node
    
    end_node = current_node
    
    # Walk backward from FRFRANODE
    backward_path = []
    current_node = link_row["FRFRANODE"]
    
    # Keep walking while current node is intermediate (degree-2, non-major)
    while current_node in intermediate_nodes:
        # Find the other link at this intermediate node (not the one we came from)
        neighbors = [n for n in adjacency[current_node] if n[0] not in visited_links]
        
        if len(neighbors) != 1:
            break
        
        next_link_idx, next_node, next_link = neighbors[0]
        
        backward_path.append(next_link_idx)
        visited_links.add(next_link_idx)
        current_node = next_node
    
    start_node = current_node
    
    # Combine paths: backward (reversed) + current link + forward
    full_path = list(reversed(backward_path)) + forward_path
    
    # Get all links in the path
    path_links = [gdf_links.loc[idx] for idx in full_path]
    
    # Get FRFRANODE and TOFRANODE from first and last links
    first_link = path_links[0]
    last_link = path_links[-1]
    
    # Determine correct orientation
    # The path goes from start_node to end_node
    # First link: which end has start_node?
    if first_link["FRFRANODE"] == start_node:
        edge_frfranode = first_link["FRFRANODE"]
    else:
        edge_frfranode = first_link["TOFRANODE"]
    
    # Last link: which end has end_node?
    if last_link["TOFRANODE"] == end_node:
        edge_tofranode = last_link["TOFRANODE"]
    else:
        edge_tofranode = last_link["FRFRANODE"]
    
    # Build merged geometry (single LineString)
    coords = []
    for i, link in enumerate(path_links):
        link_coords = list(link.geometry.coords)
        
        if i == 0:
            # First link: determine orientation based on start_node
            if link["FRFRANODE"] == start_node:
                # Link goes in forward direction
                coords.extend(link_coords)
            else:
                # Link goes in reverse direction
                coords.extend(reversed(link_coords))
        else:
            # Subsequent links: match to previous endpoint
            prev_end = Point(coords[-1])
            link_start = Point(link_coords[0])
            link_end = Point(link_coords[-1])
            
            if link_start.distance(prev_end) < link_end.distance(prev_end):
                # Same direction - skip duplicate first point
                coords.extend(link_coords[1:])
            else:
                # Reverse direction - skip duplicate last point
                coords.extend(list(reversed(link_coords))[1:])
    
    # Create the merged geometry
    merged_geom = LineString(coords)
    
    # Store the edge
    edges.append({
        "FRFRANODE": edge_frfranode,
        "TOFRANODE": edge_tofranode,
        "NET": path_links[0]["NET"],
        "LENGTH": sum(link.geometry.length for link in path_links),
        "NUM_MERGED": len(path_links),
        "MERGED_OBJECTIDS": ",".join(str(gdf_links.loc[idx, "OBJECTID"]) for idx in full_path),
        "geometry": merged_geom
    })

print(f"\nTotal edges created: {len(edges)}")

gdf_edges = gpd.GeoDataFrame(edges, crs=gdf_links.crs)

# --------------------------------------------------
# Add degree information to major nodes
# --------------------------------------------------
print("\nAdding degree information to major nodes...")
gdf_nodes["DEGREE"] = gdf_nodes["FRANODEID"].apply(lambda x: node_degrees.get(x, 0))

# --------------------------------------------------
# VALIDATION 1: Check all links are accounted for
# --------------------------------------------------
print("\n" + "="*70)
print("VALIDATION 1: Link Accounting")
print("="*70)
print(f"Original M/I links: {len(gdf_links)}")
print(f"Final edges: {len(gdf_edges)}")
print(f"Total links merged into edges: {gdf_edges['NUM_MERGED'].sum()}")
print(f"Links visited: {len(visited_links)}")

if gdf_edges['NUM_MERGED'].sum() == len(gdf_links):
    print("\n✓ SUCCESS: All links accounted for!")
else:
    missing = len(gdf_links) - gdf_edges['NUM_MERGED'].sum()
    print(f"\n✗ WARNING: {missing} links difference!")

# --------------------------------------------------
# VALIDATION 2: Check FRFRANODE and TOFRANODE exist in FRA data
# --------------------------------------------------
print("\n" + "="*70)
print("VALIDATION 2: FRA Node ID Verification")
print("="*70)

# Get all unique FRANODEIDs from FRA reference data
fra_node_ids = set(gdf_fra_nodes["FRANODEID"].values)
print(f"Total FRANODEIDs in FRA reference: {len(fra_node_ids)}")

# Check edges
edge_from_nodes = set(gdf_edges["FRFRANODE"].dropna().values)
edge_to_nodes = set(gdf_edges["TOFRANODE"].dropna().values)
edge_all_nodes = edge_from_nodes.union(edge_to_nodes)

print(f"\nUnique FRANODEIDs in edges:")
print(f"  FRFRANODE: {len(edge_from_nodes)}")
print(f"  TOFRANODE: {len(edge_to_nodes)}")
print(f"  Combined: {len(edge_all_nodes)}")

# Check if all edge nodes exist in FRA data
missing_from_fra = edge_all_nodes - fra_node_ids
if len(missing_from_fra) > 0:
    print(f"\n✗ ERROR: {len(missing_from_fra)} edge FRANODEIDs not found in FRA reference!")
    print(f"  Sample missing IDs: {list(missing_from_fra)[:10]}")
else:
    print(f"\n✓ SUCCESS: All edge FRANODEIDs exist in FRA reference data!")

# Check major nodes
major_node_franodeids = set(gdf_nodes["FRANODEID"].values)
missing_major_nodes = major_node_franodeids - fra_node_ids
if len(missing_major_nodes) > 0:
    print(f"\n✗ ERROR: {len(missing_major_nodes)} major node FRANODEIDs not found in FRA reference!")
    print(f"  Sample missing IDs: {list(missing_major_nodes)[:10]}")
else:
    print(f"\n✓ SUCCESS: All major node FRANODEIDs exist in FRA reference data!")

# --------------------------------------------------
# VALIDATION 3: Check edge endpoints reference major nodes
# --------------------------------------------------
print("\n" + "="*70)
print("VALIDATION 3: Edge-Node Connectivity")
print("="*70)

edges_with_missing_nodes = gdf_edges[
    ~gdf_edges["FRFRANODE"].isin(major_node_franodeids) |
    ~gdf_edges["TOFRANODE"].isin(major_node_franodeids)
]

if len(edges_with_missing_nodes) > 0:
    print(f"\n✗ WARNING: {len(edges_with_missing_nodes)} edges reference nodes not in major nodes layer!")
    print(f"  This might be expected if edges connect to intermediate nodes at network boundaries")
    print(f"\n  Sample edges with missing nodes:")
    print(edges_with_missing_nodes[["FRFRANODE", "TOFRANODE", "NUM_MERGED"]].head())
else:
    print(f"\n✓ SUCCESS: All edges connect to major nodes!")

# --------------------------------------------------
# Statistics
# --------------------------------------------------
print("\n" + "="*70)
print("EDGE STATISTICS")
print("="*70)

print(f"\nEdge merging statistics:")
print(f"  Average links per edge: {gdf_edges['NUM_MERGED'].mean():.2f}")
print(f"  Median links per edge: {gdf_edges['NUM_MERGED'].median():.0f}")
print(f"  Max links in one edge: {gdf_edges['NUM_MERGED'].max()}")
print(f"  Edges with 1 link (no merging): {(gdf_edges['NUM_MERGED'] == 1).sum()}")
print(f"  Edges with 2+ links (merged): {(gdf_edges['NUM_MERGED'] > 1).sum()}")

print(f"\nEdge length statistics (meters):")
print(gdf_edges['LENGTH'].describe())

# Check edge endpoint node types
print(f"\nEdge endpoints by node type:")
from_types = []
to_types = []

for _, edge in gdf_edges.iterrows():
    from_node_info = gdf_nodes[gdf_nodes["FRANODEID"] == edge["FRFRANODE"]]
    to_node_info = gdf_nodes[gdf_nodes["FRANODEID"] == edge["TOFRANODE"]]
    
    if len(from_node_info) > 0:
        from_types.append(from_node_info.iloc[0]["NODE_TYPE"])
    else:
        from_types.append("NOT_IN_MAJOR_NODES")
    
    if len(to_node_info) > 0:
        to_types.append(to_node_info.iloc[0]["NODE_TYPE"])
    else:
        to_types.append("NOT_IN_MAJOR_NODES")

from_counts = pd.Series(from_types).value_counts()
to_counts = pd.Series(to_types).value_counts()

print(f"\n  FRFRANODE types:")
for node_type, count in from_counts.items():
    print(f"    {node_type}: {count}")

print(f"\n  TOFRANODE types:")
for node_type, count in to_counts.items():
    print(f"    {node_type}: {count}")

# --------------------------------------------------
# Save GeoPackage
# --------------------------------------------------
print("\n" + "="*70)
print("SAVING OUTPUT")
print("="*70)

os.makedirs(os.path.dirname(out_gpkg), exist_ok=True)

# Save nodes (only major nodes with FRANODEID)
gdf_nodes.to_file(out_gpkg, layer="nodes", driver="GPKG")

# Save edges (with FRFRANODE and TOFRANODE)
gdf_edges.to_file(out_gpkg, layer="edges", driver="GPKG")

print(f"\nSaved to: {out_gpkg}")
print(f"  - Layer 'nodes': {len(gdf_nodes)} major nodes")
print(f"    • NODE_TYPE: YARD/END/JUNCTION/O_JUNCTION")
print(f"    • FRANODEID: Official FRA node ID")
print(f"    • DEGREE: Number of connections")
print(f"\n  - Layer 'edges': {len(gdf_edges)} simplified edges")
print(f"    • FRFRANODE: FRA node ID at start")
print(f"    • TOFRANODE: FRA node ID at end")
print(f"    • MERGED_OBJECTIDS: Original link OBJECTIDs")
print(f"    • LENGTH: Total length in meters")

# --------------------------------------------------
# FINAL SUMMARY
# --------------------------------------------------
print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"""
Input:
  - {len(gdf_links)} M/I rail links (with FRFRANODE/TOFRANODE)
  - {len(gdf_nodes)} major nodes (YARD/END/JUNCTION/O_JUNCTION)
  - {len(intermediate_nodes)} intermediate degree-2 nodes (merged through)

Output:
  - {len(gdf_edges)} simplified edges
  - All edges use official FRA node IDs (FRFRANODE/TOFRANODE)
  - Edges can be cross-referenced with original FRA rail lines
  - Only major nodes appear in nodes layer

Usage for shortest path:
  - Use edges layer for routing
  - FRFRANODE and TOFRANODE reference nodes layer via FRANODEID
  - LENGTH field for distance-based routing
  - MERGED_OBJECTIDS traces back to original links
  - All IDs are official FRA IDs - no relative/internal numbering
""")

print("\nDone!")
# %%
