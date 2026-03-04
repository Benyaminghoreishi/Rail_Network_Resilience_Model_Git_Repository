# %%
#! ============================================================
#! 1 
#! Code to aggregate FAF SCTGG5 county-to-county flows to
#! total county-to-county flows (summing over all SCTGG5 categories)
#! ============================================================
import geopandas as gpd
import pandas as pd
import os
from difflib import SequenceMatcher

# --------------------------------------------------
# Base directory
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

# --------------------------------------------------
# Paths and read data
# --------------------------------------------------
faf_flow_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "county_level_all_categories.csv"
)

print("Reading data...")
gdf_flow_county = pd.read_csv(faf_flow_path)

print(f"Counties: {len(gdf_flow_county)}")

# Ensure numeric
for c in ["tons_2024", "value_2024", "tons_2050", "value_2050"]:
    gdf_flow_county[c] = pd.to_numeric(gdf_flow_county[c], errors="coerce").fillna(0.0)

# AGGREGATE: sum over all SCTGG5
od_county = (
    gdf_flow_county.groupby(
        ["dms_orig_cnty", "dms_dest_cnty"], as_index=False
    )
    .agg(
        tons_2024=("tons_2024", "sum"),
        value_2024=("value_2024", "sum"),
        tons_2050=("tons_2050", "sum"),
        value_2050=("value_2050", "sum"),
    )
)

print(f"Original rows : {len(gdf_flow_county):,}")
print(f"County OD rows: {len(od_county):,}")

# --------------------------------------------------
# DROP rows where ALL flow columns are zero
# --------------------------------------------------
flow_cols = ["tons_2024", "value_2024", "tons_2050", "value_2050"]

od_county = od_county[
    (od_county[flow_cols] != 0).any(axis=1)
].copy()

print(f"County OD rows after dropping all-zero flows: {len(od_county):,}")

# --------------------------------------------------
# DROP Alaska (STATEFP == '02') OD pairs
# --------------------------------------------------
# Ensure county codes are 5-digit strings
od_county["dms_orig_cnty"] = od_county["dms_orig_cnty"].astype(str).str.zfill(5)
od_county["dms_dest_cnty"] = od_county["dms_dest_cnty"].astype(str).str.zfill(5)

alaska_mask = (
    od_county["dms_orig_cnty"].str.startswith("02") |
    od_county["dms_dest_cnty"].str.startswith("02")
)

print(f"Dropping Alaska OD rows: {alaska_mask.sum():,}")

od_county = od_county.loc[~alaska_mask].copy()

print(f"County OD rows after dropping Alaska: {len(od_county):,}")

# --------------------------------------------------
# SAVE aggregated county-to-county OD CSV
# --------------------------------------------------
out_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level"
)
os.makedirs(out_dir, exist_ok=True)

out_csv = os.path.join(out_dir, "county_od_all_sctg_aggregated.csv")

od_county.to_csv(out_csv, index=False)

print(f"\n✅ Aggregated county-level OD saved to:")
print(out_csv)
print(f"Rows: {len(od_county):,}")

# # %%
# #!========================================================================
# #! 2
# #! Create OD Pairs from Rail Graph Nodes using County FAF Flows (Optimized)
# #!========================================================================

# import geopandas as gpd
# import pandas as pd
# import numpy as np
# import os
# from shapely.geometry import LineString
# from collections import defaultdict
# import warnings

# # --------------------------------------------------
# # Base directory
# # --------------------------------------------------
# base_dir = os.path.abspath(os.path.join("..", ".."))

# # --------------------------------------------------
# # Paths
# # --------------------------------------------------
# # 2606 counties in CONUS
# county_gpkg = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "faf_county_with_flows_CONUS.gpkg"
# )

# # 16438 nodes and 20664 edges in the rail graph
# rail_links_nodes_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Rail_Graph",
#     "Rail_Graph_Nodes_Edges.gpkg"
# )

# # 4,698,768 county OD pairs with flows in 2024 or 2050
# faf_flow_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "county_od_all_sctg_aggregated.csv"
# )

# output_csv_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "rail_od_pairs_from_nodes.csv"
# )

# output_gpkg_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "rail_od_pairs_from_nodes.gpkg"
# )

# # --------------------------------------------------
# # Read data
# # --------------------------------------------------
# print("Reading data...")
# gdf_counties = gpd.read_file(county_gpkg)
# df_faf_flows = pd.read_csv(faf_flow_path)
# gdf_rails = gpd.read_file(rail_links_nodes_path, layer="edges")
# gdf_nodes = gpd.read_file(rail_links_nodes_path, layer="nodes")

# print(f"Counties loaded: {len(gdf_counties)}")
# print(f"FAF flows loaded: {len(df_faf_flows)}")
# print(f"Rail nodes loaded: {len(gdf_nodes)}")

# # --------------------------------------------------
# # Data preparation
# # --------------------------------------------------
# print("\nPreparing data...")

# # Store original CRS
# original_crs = gdf_counties.crs
# print(f"Original CRS: {original_crs}")

# # Reproject to a projected CRS for accurate distance calculations
# # Using USA Contiguous Albers Equal Area Conic (EPSG:5070)
# projected_crs = "EPSG:5070"
# print(f"Reprojecting to {projected_crs} for distance calculations...")

# gdf_counties_proj = gdf_counties.to_crs(projected_crs)
# gdf_nodes_proj = gdf_nodes.to_crs(projected_crs)

# print(f"Reprojection complete")

# # Ensure GEOID columns are 5-digit strings
# gdf_counties['GEOID'] = gdf_counties['GEOID'].astype(str).str.zfill(5)
# gdf_counties_proj['GEOID'] = gdf_counties_proj['GEOID'].astype(str).str.zfill(5)
# df_faf_flows['dms_orig_cnty'] = df_faf_flows['dms_orig_cnty'].astype(str).str.zfill(5)
# df_faf_flows['dms_dest_cnty'] = df_faf_flows['dms_dest_cnty'].astype(str).str.zfill(5)

# print(f"Filtered FAF flows (non-zero 2024 or 2050): {len(df_faf_flows)}")

# # --------------------------------------------------
# # Helper Functions
# # --------------------------------------------------

# def find_nodes_in_county(county_geoid, node_type, gdf_counties_proj, gdf_nodes_proj):
#     """
#     Find all nodes of a specific type within a county using spatial intersection.
    
#     Parameters:
#     - county_geoid: GEOID of the county
#     - node_type: Type of node to search for ('YARD', 'END', 'O_JUNCTION')
#     - gdf_counties_proj: GeoDataFrame of counties (projected)
#     - gdf_nodes_proj: GeoDataFrame of nodes (projected)
    
#     Returns:
#     - List of node information dictionaries
#     """
#     # Get county geometry
#     county_row = gdf_counties_proj[gdf_counties_proj['GEOID'] == county_geoid]
    
#     if len(county_row) == 0:
#         return []
    
#     county_geom = county_row.iloc[0].geometry
    
#     # Filter nodes by type
#     nodes_of_type = gdf_nodes_proj[gdf_nodes_proj['NODE_TYPE'] == node_type].copy()
    
#     if len(nodes_of_type) == 0:
#         return []
    
#     # Spatial intersection: find nodes within county
#     nodes_in_county = nodes_of_type[nodes_of_type.within(county_geom)].copy()
    
#     # Create node information list
#     node_info_list = []
#     for idx, (i, node) in enumerate(nodes_in_county.iterrows(), start=1):
#         if node_type == 'YARD':
#             # Format: GEOID_YARDNAME
#             yard_name = str(node['YARD_NAME']) if pd.notna(node['YARD_NAME']) else 'UNKNOWN'
#             node_label = f"{county_geoid}_{yard_name}"
#         else:
#             # Format: GEOID_NODETYPE# (e.g., 12345_END1)
#             node_label = f"{county_geoid}_{node_type}{idx}"
        
#         node_info_list.append({
#             'node_label': node_label,
#             'node_id': node['NODE_ID'],
#             'node_type': node_type,
#             'geometry': node.geometry
#         })
    
#     return node_info_list


# def find_nearest_node(county_geoid, gdf_counties_proj, gdf_nodes_proj):
#     """
#     Find the nearest node (any type) to the county centroid.
#     Uses projected CRS for accurate distance calculation.
    
#     Parameters:
#     - county_geoid: GEOID of the county
#     - gdf_counties_proj: GeoDataFrame of counties (projected)
#     - gdf_nodes_proj: GeoDataFrame of nodes (projected)
    
#     Returns:
#     - Single node information dictionary
#     """
#     # Get county geometry and centroid
#     county_row = gdf_counties_proj[gdf_counties_proj['GEOID'] == county_geoid]
    
#     if len(county_row) == 0:
#         return None
    
#     county_centroid = county_row.iloc[0].geometry.centroid
    
#     # Calculate distance from centroid to all nodes (now in projected CRS)
#     gdf_nodes_copy = gdf_nodes_proj.copy()
#     gdf_nodes_copy['distance'] = gdf_nodes_copy.geometry.distance(county_centroid)
    
#     # Find nearest node
#     nearest_node = gdf_nodes_copy.loc[gdf_nodes_copy['distance'].idxmin()]
    
#     # Create label based on node type
#     node_type = nearest_node['NODE_TYPE']
#     if node_type == 'YARD':
#         yard_name = str(nearest_node['YARD_NAME']) if pd.notna(nearest_node['YARD_NAME']) else 'UNKNOWN'
#         node_label = f"{county_geoid}_{yard_name}"
#     else:
#         node_label = f"{county_geoid}_{node_type}1"
    
#     return {
#         'node_label': node_label,
#         'node_id': nearest_node['NODE_ID'],
#         'node_type': node_type,
#         'geometry': nearest_node.geometry
#     }


# def get_nodes_for_county(county_geoid, gdf_counties_proj, gdf_nodes_proj, node_cache):
#     """
#     Get nodes for a county following the priority: YARD -> END -> O_JUNCTION -> Nearest.
#     Uses caching to avoid redundant calculations.
    
#     Parameters:
#     - county_geoid: GEOID of the county
#     - gdf_counties_proj: GeoDataFrame of counties (projected)
#     - gdf_nodes_proj: GeoDataFrame of nodes (projected)
#     - node_cache: Dictionary to cache results
    
#     Returns:
#     - List of node information dictionaries
#     """
#     # Check cache first
#     if county_geoid in node_cache:
#         return node_cache[county_geoid]
    
#     # Try YARD nodes first
#     nodes = find_nodes_in_county(county_geoid, 'YARD', gdf_counties_proj, gdf_nodes_proj)
#     if len(nodes) > 0:
#         node_cache[county_geoid] = nodes
#         return nodes
    
#     # Try END nodes
#     nodes = find_nodes_in_county(county_geoid, 'END', gdf_counties_proj, gdf_nodes_proj)
#     if len(nodes) > 0:
#         node_cache[county_geoid] = nodes
#         return nodes
    
#     # Try O_JUNCTION nodes
#     nodes = find_nodes_in_county(county_geoid, 'O_JUNCTION', gdf_counties_proj, gdf_nodes_proj)
#     if len(nodes) > 0:
#         node_cache[county_geoid] = nodes
#         return nodes
    
#     # Find nearest node of any type
#     nearest = find_nearest_node(county_geoid, gdf_counties_proj, gdf_nodes_proj)
#     if nearest:
#         nodes = [nearest]
#         node_cache[county_geoid] = nodes
#         return nodes
    
#     node_cache[county_geoid] = []
#     return []


# # --------------------------------------------------
# # Process FAF Flows and Create OD Pairs
# # --------------------------------------------------
# print("\nProcessing FAF flows and creating OD pairs...")
# print("Using caching to optimize performance...")

# od_pairs_list = []
# node_cache = {}  # Cache for county -> nodes mapping
# total_rows = len(df_faf_flows)
# batch_size = 10000  # Save periodically to avoid memory issues

# cache_hits = 0
# cache_misses = 0

# for idx, row in df_faf_flows.iterrows():
#     if (idx + 1) % 1000 == 0:
#         print(f"Processing row {idx + 1}/{total_rows}... (Cache hits: {cache_hits}, misses: {cache_misses}, OD pairs: {len(od_pairs_list)})")
    
#     orig_county = row['dms_orig_cnty']
#     dest_county = row['dms_dest_cnty']
    
#     # Get nodes for origin county (with caching)
#     if orig_county in node_cache:
#         cache_hits += 1
#         origin_nodes = node_cache[orig_county]
#     else:
#         cache_misses += 1
#         origin_nodes = get_nodes_for_county(orig_county, gdf_counties_proj, gdf_nodes_proj, node_cache)
    
#     # Get nodes for destination county (with caching)
#     if dest_county in node_cache:
#         cache_hits += 1
#         dest_nodes = node_cache[dest_county]
#     else:
#         cache_misses += 1
#         dest_nodes = get_nodes_for_county(dest_county, gdf_counties_proj, gdf_nodes_proj, node_cache)
    
#     # Check if we found nodes for both origin and destination
#     if len(origin_nodes) == 0:
#         print(f"Warning: No nodes found for origin county {orig_county}")
#         continue
    
#     if len(dest_nodes) == 0:
#         print(f"Warning: No nodes found for destination county {dest_county}")
#         continue
    
#     # Calculate number of OD pairs
#     num_od_pairs = len(origin_nodes) * len(dest_nodes)
    
#     # Divide flows equally among OD pairs
#     tons_2024_per_pair = row['tons_2024'] / num_od_pairs if num_od_pairs > 0 else 0
#     value_2024_per_pair = row['value_2024'] / num_od_pairs if num_od_pairs > 0 else 0
#     tons_2050_per_pair = row['tons_2050'] / num_od_pairs if num_od_pairs > 0 else 0
#     value_2050_per_pair = row['value_2050'] / num_od_pairs if num_od_pairs > 0 else 0
    
#     # Create all OD pairs
#     for origin_node in origin_nodes:
#         for dest_node in dest_nodes:
#             od_pair = {
#                 'origin_node_label': origin_node['node_label'],
#                 'origin_node_id': origin_node['node_id'],
#                 'origin_node_type': origin_node['node_type'],
#                 'destination_node_label': dest_node['node_label'],
#                 'destination_node_id': dest_node['node_id'],
#                 'destination_node_type': dest_node['node_type'],
#                 'tons_2024': tons_2024_per_pair,
#                 'value_2024': value_2024_per_pair,
#                 'tons_2050': tons_2050_per_pair,
#                 'value_2050': value_2050_per_pair,
#                 'original_origin_county': orig_county,
#                 'original_dest_county': dest_county,
#                 'num_origin_nodes': len(origin_nodes),
#                 'num_dest_nodes': len(dest_nodes),
#                 'origin_geometry': origin_node['geometry'],
#                 'dest_geometry': dest_node['geometry']
#             }
#             od_pairs_list.append(od_pair)

# print(f"\nTotal OD pairs created: {len(od_pairs_list)}")
# print(f"Cache statistics - Hits: {cache_hits}, Misses: {cache_misses}")
# print(f"Unique counties processed: {len(node_cache)}")

# # --------------------------------------------------
# # Create DataFrame and GeoDataFrame
# # --------------------------------------------------
# print("\nCreating output dataframes...")

# df_od_pairs = pd.DataFrame(od_pairs_list)

# # Create GeoDataFrame with LineString geometries connecting origin to destination
# geometries = []
# for _, row in df_od_pairs.iterrows():
#     line = LineString([row['origin_geometry'], row['dest_geometry']])
#     geometries.append(line)

# # Drop the individual geometry columns and create GeoDataFrame
# df_od_pairs_for_gpkg = df_od_pairs.drop(columns=['origin_geometry', 'dest_geometry']).copy()
# gdf_od_pairs = gpd.GeoDataFrame(
#     df_od_pairs_for_gpkg,
#     geometry=geometries,
#     crs=projected_crs
# )

# # Convert back to original CRS for output
# print(f"Converting back to original CRS: {original_crs}")
# gdf_od_pairs = gdf_od_pairs.to_crs(original_crs)

# # For CSV, drop geometry columns
# df_od_pairs_csv = df_od_pairs.drop(columns=['origin_geometry', 'dest_geometry'])

# # --------------------------------------------------
# # Save outputs
# # --------------------------------------------------
# print("\nSaving outputs...")

# # Save CSV
# df_od_pairs_csv.to_csv(output_csv_path, index=False)
# print(f"CSV saved to: {output_csv_path}")

# # Save GeoPackage
# gdf_od_pairs.to_file(output_gpkg_path, driver="GPKG")
# print(f"GeoPackage saved to: {output_gpkg_path}")

# # --------------------------------------------------
# # Summary Statistics
# # --------------------------------------------------
# print("\n" + "="*60)
# print("SUMMARY STATISTICS")
# print("="*60)
# print(f"Total OD pairs created: {len(df_od_pairs_csv):,}")
# print(f"\nTotal tons 2024: {df_od_pairs_csv['tons_2024'].sum():,.2f}")
# print(f"Total value 2024: ${df_od_pairs_csv['value_2024'].sum():,.2f}")
# print(f"Total tons 2050: {df_od_pairs_csv['tons_2050'].sum():,.2f}")
# print(f"Total value 2050: ${df_od_pairs_csv['value_2050'].sum():,.2f}")

# print("\nNode type distribution (origins):")
# print(df_od_pairs_csv['origin_node_type'].value_counts())

# print("\nNode type distribution (destinations):")
# print(df_od_pairs_csv['destination_node_type'].value_counts())

# print("\nTop 10 OD pairs by tons 2024:")
# print(df_od_pairs_csv.nlargest(10, 'tons_2024')[
#     ['origin_node_label', 'destination_node_label', 'tons_2024', 'value_2024']
# ])

# print("\n" + "="*60)
# print("PROCESSING COMPLETE!")
# print("="*60)
# %%
#!========================================================================
#! 2
#! Create OD Pairs from Rail Graph Nodes using County FAF Flows (FRANODEID Version)
#!========================================================================

import geopandas as gpd
import pandas as pd
import numpy as np
import os
from shapely.geometry import LineString
from collections import defaultdict
import warnings

# --------------------------------------------------
# Base directory
# --------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

# --------------------------------------------------
# Paths
# --------------------------------------------------
# 2606 counties in CONUS
county_gpkg = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "faf_county_with_flows_CONUS.gpkg"
)

# Rail graph with FRANODEID-based nodes
rail_links_nodes_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Graph",
    "Rail_Graph_Nodes_Edges.gpkg"
)

# FRA reference nodes (for validation)
fra_nodes_path = os.path.join(
    base_dir,
    "Shapefiles",
    "North_American_Rail_Network_Nodes",
    "North_American_Rail_Network_Nodes.shp"
)

# 4,698,768 county OD pairs with flows in 2024 or 2050
faf_flow_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "county_od_all_sctg_aggregated.csv"
)

output_csv_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_pairs_from_nodes.csv"
)

output_gpkg_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_pairs_from_nodes.gpkg"
)

# --------------------------------------------------
# Read data
# --------------------------------------------------
print("Reading data...")
gdf_counties = gpd.read_file(county_gpkg)
df_faf_flows = pd.read_csv(faf_flow_path)
gdf_rails = gpd.read_file(rail_links_nodes_path, layer="edges")
gdf_nodes = gpd.read_file(rail_links_nodes_path, layer="nodes")
gdf_fra_nodes = gpd.read_file(fra_nodes_path)

print(f"Counties loaded: {len(gdf_counties)}")
print(f"FAF flows loaded: {len(df_faf_flows)}")
print(f"Rail nodes loaded: {len(gdf_nodes)}")
print(f"FRA reference nodes loaded: {len(gdf_fra_nodes)}")

# Verify nodes have FRANODEID
if 'FRANODEID' not in gdf_nodes.columns:
    raise ValueError("Nodes layer must have FRANODEID column")

print(f"\nNode types in nodes layer:")
print(gdf_nodes['NODE_TYPE'].value_counts())

# --------------------------------------------------
# Data preparation
# --------------------------------------------------
print("\nPreparing data...")

# Store original CRS
original_crs = gdf_counties.crs
print(f"Original CRS: {original_crs}")

# Reproject to a projected CRS for accurate distance calculations
# Using USA Contiguous Albers Equal Area Conic (EPSG:5070)
projected_crs = "EPSG:5070"
print(f"Reprojecting to {projected_crs} for distance calculations...")

gdf_counties_proj = gdf_counties.to_crs(projected_crs)
gdf_nodes_proj = gdf_nodes.to_crs(projected_crs)

print(f"Reprojection complete")

# Ensure GEOID columns are 5-digit strings
gdf_counties['GEOID'] = gdf_counties['GEOID'].astype(str).str.zfill(5)
gdf_counties_proj['GEOID'] = gdf_counties_proj['GEOID'].astype(str).str.zfill(5)
df_faf_flows['dms_orig_cnty'] = df_faf_flows['dms_orig_cnty'].astype(str).str.zfill(5)
df_faf_flows['dms_dest_cnty'] = df_faf_flows['dms_dest_cnty'].astype(str).str.zfill(5)

print(f"Filtered FAF flows (non-zero 2024 or 2050): {len(df_faf_flows)}")

# --------------------------------------------------
# Helper Functions
# --------------------------------------------------

def find_nodes_in_county(county_geoid, node_type, gdf_counties_proj, gdf_nodes_proj):
    """
    Find all nodes of a specific type within a county using spatial intersection.
    
    Parameters:
    - county_geoid: GEOID of the county
    - node_type: Type of node to search for ('YARD', 'END', 'O_JUNCTION')
    - gdf_counties_proj: GeoDataFrame of counties (projected)
    - gdf_nodes_proj: GeoDataFrame of nodes (projected)
    
    Returns:
    - List of node information dictionaries
    """
    # Get county geometry
    county_row = gdf_counties_proj[gdf_counties_proj['GEOID'] == county_geoid]
    
    if len(county_row) == 0:
        return []
    
    county_geom = county_row.iloc[0].geometry
    
    # Filter nodes by type
    nodes_of_type = gdf_nodes_proj[gdf_nodes_proj['NODE_TYPE'] == node_type].copy()
    
    if len(nodes_of_type) == 0:
        return []
    
    # Spatial intersection: find nodes within county
    nodes_in_county = nodes_of_type[nodes_of_type.within(county_geom)].copy()
    
    # Create node information list
    node_info_list = []
    for idx, (i, node) in enumerate(nodes_in_county.iterrows(), start=1):
        if node_type == 'YARD':
            # Format: GEOID_YARDNAME_FRANODEID
            yard_name = str(node['YARD_NAME']) if pd.notna(node['YARD_NAME']) else 'UNKNOWN'
            node_label = f"{county_geoid}_{yard_name}_{node['FRANODEID']}"
        else:
            # Format: GEOID_NODETYPE#_FRANODEID (e.g., 12345_END1_302584)
            node_label = f"{county_geoid}_{node_type}{idx}_{node['FRANODEID']}"
        
        node_info_list.append({
            'node_label': node_label,
            'franodeid': node['FRANODEID'],
            'node_type': node_type,
            'geometry': node.geometry
        })
    
    return node_info_list


def find_nearest_node(county_geoid, gdf_counties_proj, gdf_nodes_proj):
    """
    Find the nearest node (any type) to the county centroid.
    Uses projected CRS for accurate distance calculation.
    
    Parameters:
    - county_geoid: GEOID of the county
    - gdf_counties_proj: GeoDataFrame of counties (projected)
    - gdf_nodes_proj: GeoDataFrame of nodes (projected)
    
    Returns:
    - Single node information dictionary
    """
    # Get county geometry and centroid
    county_row = gdf_counties_proj[gdf_counties_proj['GEOID'] == county_geoid]
    
    if len(county_row) == 0:
        return None
    
    county_centroid = county_row.iloc[0].geometry.centroid
    
    # Calculate distance from centroid to all nodes (now in projected CRS)
    gdf_nodes_copy = gdf_nodes_proj.copy()
    gdf_nodes_copy['distance'] = gdf_nodes_copy.geometry.distance(county_centroid)
    
    # Find nearest node
    nearest_node = gdf_nodes_copy.loc[gdf_nodes_copy['distance'].idxmin()]
    
    # Create label based on node type
    node_type = nearest_node['NODE_TYPE']
    if node_type == 'YARD':
        yard_name = str(nearest_node['YARD_NAME']) if pd.notna(nearest_node['YARD_NAME']) else 'UNKNOWN'
        node_label = f"{county_geoid}_{yard_name}_{nearest_node['FRANODEID']}"
    else:
        node_label = f"{county_geoid}_{node_type}1_{nearest_node['FRANODEID']}"
    
    return {
        'node_label': node_label,
        'franodeid': nearest_node['FRANODEID'],
        'node_type': node_type,
        'geometry': nearest_node.geometry
    }


def get_nodes_for_county(county_geoid, gdf_counties_proj, gdf_nodes_proj, node_cache):
    """
    Get nodes for a county following the priority: YARD -> END -> O_JUNCTION -> Nearest.
    Uses caching to avoid redundant calculations.
    
    Parameters:
    - county_geoid: GEOID of the county
    - gdf_counties_proj: GeoDataFrame of counties (projected)
    - gdf_nodes_proj: GeoDataFrame of nodes (projected)
    - node_cache: Dictionary to cache results
    
    Returns:
    - List of node information dictionaries
    """
    # Check cache first
    if county_geoid in node_cache:
        return node_cache[county_geoid]
    
    # Try YARD nodes first
    nodes = find_nodes_in_county(county_geoid, 'YARD', gdf_counties_proj, gdf_nodes_proj)
    if len(nodes) > 0:
        node_cache[county_geoid] = nodes
        return nodes
    
    # Try END nodes
    nodes = find_nodes_in_county(county_geoid, 'END', gdf_counties_proj, gdf_nodes_proj)
    if len(nodes) > 0:
        node_cache[county_geoid] = nodes
        return nodes
    
    # Try O_JUNCTION nodes
    nodes = find_nodes_in_county(county_geoid, 'O_JUNCTION', gdf_counties_proj, gdf_nodes_proj)
    if len(nodes) > 0:
        node_cache[county_geoid] = nodes
        return nodes
    
    # Find nearest node of any type
    nearest = find_nearest_node(county_geoid, gdf_counties_proj, gdf_nodes_proj)
    if nearest:
        nodes = [nearest]
        node_cache[county_geoid] = nodes
        return nodes
    
    node_cache[county_geoid] = []
    return []


# --------------------------------------------------
# Process FAF Flows and Create OD Pairs
# --------------------------------------------------
print("\nProcessing FAF flows and creating OD pairs...")
print("Using caching to optimize performance...")

od_pairs_list = []
node_cache = {}  # Cache for county -> nodes mapping
total_rows = len(df_faf_flows)

cache_hits = 0
cache_misses = 0

for idx, row in df_faf_flows.iterrows():
    if (idx + 1) % 1000 == 0:
        print(f"Processing row {idx + 1}/{total_rows}... (Cache hits: {cache_hits}, misses: {cache_misses}, OD pairs: {len(od_pairs_list)})")
    
    orig_county = row['dms_orig_cnty']
    dest_county = row['dms_dest_cnty']
    
    # Get nodes for origin county (with caching)
    if orig_county in node_cache:
        cache_hits += 1
        origin_nodes = node_cache[orig_county]
    else:
        cache_misses += 1
        origin_nodes = get_nodes_for_county(orig_county, gdf_counties_proj, gdf_nodes_proj, node_cache)
    
    # Get nodes for destination county (with caching)
    if dest_county in node_cache:
        cache_hits += 1
        dest_nodes = node_cache[dest_county]
    else:
        cache_misses += 1
        dest_nodes = get_nodes_for_county(dest_county, gdf_counties_proj, gdf_nodes_proj, node_cache)
    
    # Check if we found nodes for both origin and destination
    if len(origin_nodes) == 0:
        print(f"Warning: No nodes found for origin county {orig_county}")
        continue
    
    if len(dest_nodes) == 0:
        print(f"Warning: No nodes found for destination county {dest_county}")
        continue
    
    # Calculate number of OD pairs
    num_od_pairs = len(origin_nodes) * len(dest_nodes)
    
    # Divide flows equally among OD pairs
    tons_2024_per_pair = row['tons_2024'] / num_od_pairs if num_od_pairs > 0 else 0
    value_2024_per_pair = row['value_2024'] / num_od_pairs if num_od_pairs > 0 else 0
    tons_2050_per_pair = row['tons_2050'] / num_od_pairs if num_od_pairs > 0 else 0
    value_2050_per_pair = row['value_2050'] / num_od_pairs if num_od_pairs > 0 else 0
    
    # Create all OD pairs
    for origin_node in origin_nodes:
        for dest_node in dest_nodes:
            od_pair = {
                'origin_node_label': origin_node['node_label'],
                'origin_franodeid': origin_node['franodeid'],
                'origin_node_type': origin_node['node_type'],
                'destination_node_label': dest_node['node_label'],
                'destination_franodeid': dest_node['franodeid'],
                'destination_node_type': dest_node['node_type'],
                'tons_2024': tons_2024_per_pair,
                'value_2024': value_2024_per_pair,
                'tons_2050': tons_2050_per_pair,
                'value_2050': value_2050_per_pair,
                'original_origin_county': orig_county,
                'original_dest_county': dest_county,
                'num_origin_nodes': len(origin_nodes),
                'num_dest_nodes': len(dest_nodes),
                'origin_geometry': origin_node['geometry'],
                'dest_geometry': dest_node['geometry']
            }
            od_pairs_list.append(od_pair)

print(f"\nTotal OD pairs created: {len(od_pairs_list)}")
print(f"Cache statistics - Hits: {cache_hits}, Misses: {cache_misses}")
print(f"Unique counties processed: {len(node_cache)}")

# --------------------------------------------------
# Create DataFrame and GeoDataFrame
# --------------------------------------------------
print("\nCreating output dataframes...")

df_od_pairs = pd.DataFrame(od_pairs_list)

# Create GeoDataFrame with LineString geometries connecting origin to destination
geometries = []
for _, row in df_od_pairs.iterrows():
    line = LineString([row['origin_geometry'], row['dest_geometry']])
    geometries.append(line)

# Drop the individual geometry columns and create GeoDataFrame
df_od_pairs_for_gpkg = df_od_pairs.drop(columns=['origin_geometry', 'dest_geometry']).copy()
gdf_od_pairs = gpd.GeoDataFrame(
    df_od_pairs_for_gpkg,
    geometry=geometries,
    crs=projected_crs
)

# Convert back to original CRS for output
print(f"Converting back to original CRS: {original_crs}")
gdf_od_pairs = gdf_od_pairs.to_crs(original_crs)

# For CSV, drop geometry columns
df_od_pairs_csv = df_od_pairs.drop(columns=['origin_geometry', 'dest_geometry'])

# --------------------------------------------------
# VALIDATION: Check FRANODEIDs
# --------------------------------------------------
print("\n" + "="*70)
print("VALIDATION: FRANODEID Verification")
print("="*70)

# Get all unique FRANODEIDs from OD pairs
od_origin_franodeids = set(df_od_pairs_csv['origin_franodeid'].dropna().values)
od_dest_franodeids = set(df_od_pairs_csv['destination_franodeid'].dropna().values)
od_all_franodeids = od_origin_franodeids.union(od_dest_franodeids)

print(f"Unique FRANODEIDs in OD pairs:")
print(f"  Origins: {len(od_origin_franodeids)}")
print(f"  Destinations: {len(od_dest_franodeids)}")
print(f"  Combined: {len(od_all_franodeids)}")

# Check against nodes layer
nodes_franodeids = set(gdf_nodes['FRANODEID'].values)
missing_from_nodes = od_all_franodeids - nodes_franodeids

if len(missing_from_nodes) > 0:
    print(f"\n✗ ERROR: {len(missing_from_nodes)} OD pair FRANODEIDs not found in nodes layer!")
    print(f"  Sample missing IDs: {list(missing_from_nodes)[:10]}")
else:
    print(f"\n✓ SUCCESS: All OD pair FRANODEIDs exist in nodes layer!")

# Check against FRA reference data
fra_franodeids = set(gdf_fra_nodes['FRANODEID'].values)
missing_from_fra = od_all_franodeids - fra_franodeids

if len(missing_from_fra) > 0:
    print(f"\n✗ ERROR: {len(missing_from_fra)} OD pair FRANODEIDs not found in FRA reference data!")
    print(f"  Sample missing IDs: {list(missing_from_fra)[:10]}")
else:
    print(f"\n✓ SUCCESS: All OD pair FRANODEIDs exist in FRA reference data!")

# Cross-check: are all node FRANODEIDs used in OD pairs?
unused_nodes = nodes_franodeids - od_all_franodeids
if len(unused_nodes) > 0:
    print(f"\nInfo: {len(unused_nodes)} nodes in nodes layer are not used in any OD pair")
    # Show which types are unused
    unused_node_types = gdf_nodes[gdf_nodes['FRANODEID'].isin(unused_nodes)]['NODE_TYPE'].value_counts()
    print(f"  Unused node types:")
    for node_type, count in unused_node_types.items():
        print(f"    {node_type}: {count}")

# --------------------------------------------------
# Save outputs
# --------------------------------------------------
print("\n" + "="*70)
print("SAVING OUTPUTS")
print("="*70)

# Save CSV
df_od_pairs_csv.to_csv(output_csv_path, index=False)
print(f"CSV saved to: {output_csv_path}")

# Save GeoPackage
gdf_od_pairs.to_file(output_gpkg_path, driver="GPKG")
print(f"GeoPackage saved to: {output_gpkg_path}")

# --------------------------------------------------
# Summary Statistics
# --------------------------------------------------
print("\n" + "="*70)
print("SUMMARY STATISTICS")
print("="*70)
print(f"Total OD pairs created: {len(df_od_pairs_csv):,}")
print(f"\nTotal tons 2024: {df_od_pairs_csv['tons_2024'].sum():,.2f}")
print(f"Total value 2024: ${df_od_pairs_csv['value_2024'].sum():,.2f}")
print(f"Total tons 2050: {df_od_pairs_csv['tons_2050'].sum():,.2f}")
print(f"Total value 2050: ${df_od_pairs_csv['value_2050'].sum():,.2f}")

print("\nNode type distribution (origins):")
print(df_od_pairs_csv['origin_node_type'].value_counts())

print("\nNode type distribution (destinations):")
print(df_od_pairs_csv['destination_node_type'].value_counts())

print("\nTop 10 OD pairs by tons 2024:")
top_10 = df_od_pairs_csv.nlargest(10, 'tons_2024')[
    ['origin_node_label', 'destination_node_label', 'origin_franodeid', 
     'destination_franodeid', 'tons_2024', 'value_2024']
]
print(top_10.to_string(index=False))

# Check for any same-node OD pairs (origin == destination)
same_node_pairs = df_od_pairs_csv[
    df_od_pairs_csv['origin_franodeid'] == df_od_pairs_csv['destination_franodeid']
]
if len(same_node_pairs) > 0:
    print(f"\nWarning: {len(same_node_pairs)} OD pairs have same origin and destination node")
    print(f"  Total tons in same-node pairs: {same_node_pairs['tons_2024'].sum():,.2f}")

print("\n" + "="*70)
print("PROCESSING COMPLETE!")
print("="*70)
print(f"""
Key changes from previous version:
  - All node references now use FRANODEID (official FRA node IDs)
  - Node labels include FRANODEID for traceability
  - Output columns: origin_franodeid, destination_franodeid
  - Full validation against nodes layer and FRA reference data
  - All IDs are official FRA IDs - no relative/internal numbering
""")

# %%
#!========================================================================
#! 3
#! OPTIMIZED Rail Assignment with CSV-Only Output (FRANODEID Version)
#! Strategy: CSV only for speed, first 5 origins as GPKG for verification
#!========================================================================

# import geopandas as gpd
# import pandas as pd
# import networkx as nx
# from shapely.geometry import LineString, MultiLineString
# from shapely.ops import linemerge
# from collections import defaultdict
# import os
# import time
# import gc

# # ==================================================
# # CONFIGURATION
# # ==================================================
# SPEED_MPH = 49.0
# HOURS_PER_DAY = 24.0
# DAYS_PER_YEAR = 365.0
# THOUSAND_TONS_TO_TONS = 1000.0

# # Verification - save first N origins as GPKG
# NUM_GPKG_FOR_VERIFICATION = 5

# # ==================================================
# # PATHS
# # ==================================================
# base_dir = os.path.abspath(os.path.join("..", ".."))

# rail_graph_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Rail_Graph",
#     "Rail_Graph_Nodes_Edges.gpkg"
# )

# od_pairs_path = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "rail_od_pairs_from_nodes.gpkg"
# )

# # Individual origin files directory
# od_paths_by_origin_dir = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "OD_Paths_By_Origin"
# )

# # Final combined outputs
# output_links_gpkg = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "rail_link_flows_daily_ALL_LINKS.gpkg"
# )

# output_od_paths_combined_csv = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "rail_od_paths_daily_COMBINED.csv"
# )

# # Progress tracking file
# progress_file = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "processing_progress.csv"
# )

# # Create output directory
# os.makedirs(od_paths_by_origin_dir, exist_ok=True)

# # ==================================================
# # READ DATA
# # ==================================================
# print("=" * 80)
# print("OPTIMIZED RAIL ASSIGNMENT - CSV ONLY (FRANODEID VERSION)")
# print("=" * 80)
# print(f"\nConfiguration:")
# print(f"  - CSV files for ALL origins (fast)")
# print(f"  - GPKG files for first {NUM_GPKG_FOR_VERIFICATION} origins only (verification)")
# print(f"  - Origin/Destination X/Y coordinates in CSV")
# print(f"  - Final link flows include ALL M/I links (even zero flow)")
# print(f"\nOutput directory: {od_paths_by_origin_dir}")
# print()

# print("Reading rail network...")
# gdf_edges = gpd.read_file(rail_graph_path, layer="edges")
# gdf_nodes = gpd.read_file(rail_graph_path, layer="nodes")

# print(f"✓ Edges: {len(gdf_edges):,}")
# print(f"✓ Nodes: {len(gdf_nodes):,}")

# # Verify required columns
# required_edge_cols = ['FRFRANODE', 'TOFRANODE', 'LENGTH', 'NET', 'NUM_MERGED', 'MERGED_OBJECTIDS']
# missing_edge_cols = [col for col in required_edge_cols if col not in gdf_edges.columns]
# if missing_edge_cols:
#     raise ValueError(f"Missing required edge columns: {missing_edge_cols}")

# required_node_cols = ['FRANODEID']
# missing_node_cols = [col for col in required_node_cols if col not in gdf_nodes.columns]
# if missing_node_cols:
#     raise ValueError(f"Missing required node columns: {missing_node_cols}")

# print("\nReading OD pairs (this may take a moment)...")
# gdf_od = gpd.read_file(od_pairs_path)
# print(f"✓ OD pairs: {len(gdf_od):,}")

# # Verify OD pairs have FRANODEID columns
# required_od_cols = ['origin_franodeid', 'destination_franodeid']
# missing_od_cols = [col for col in required_od_cols if col not in gdf_od.columns]
# if missing_od_cols:
#     raise ValueError(f"Missing required OD pair columns: {missing_od_cols}")

# # Convert to DataFrame and drop geometry to save memory for processing
# print("Converting to DataFrame...")
# df_od = pd.DataFrame(gdf_od.drop(columns="geometry"))

# del gdf_od  # Free memory
# gc.collect()

# # ==================================================
# # VALIDATION: Check FRANODEIDs
# # ==================================================
# print("\n" + "=" * 80)
# print("VALIDATION: FRANODEID Verification")
# print("=" * 80)

# # Get all unique FRANODEIDs from nodes layer
# node_franodeids = set(gdf_nodes['FRANODEID'].values)
# print(f"Nodes in graph: {len(node_franodeids):,}")

# # Get all unique FRANODEIDs from edges
# edge_from_nodes = set(gdf_edges['FRFRANODE'].dropna().values)
# edge_to_nodes = set(gdf_edges['TOFRANODE'].dropna().values)
# edge_all_nodes = edge_from_nodes.union(edge_to_nodes)
# print(f"Unique FRANODEIDs in edges: {len(edge_all_nodes):,}")

# # Get all unique FRANODEIDs from OD pairs
# od_origin_nodes = set(df_od['origin_franodeid'].dropna().values)
# od_dest_nodes = set(df_od['destination_franodeid'].dropna().values)
# od_all_nodes = od_origin_nodes.union(od_dest_nodes)
# print(f"Unique FRANODEIDs in OD pairs: {len(od_all_nodes):,}")

# # Check if all OD nodes exist in graph
# od_nodes_not_in_graph = od_all_nodes - edge_all_nodes
# if len(od_nodes_not_in_graph) > 0:
#     print(f"\n✗ WARNING: {len(od_nodes_not_in_graph)} OD FRANODEIDs not found in graph!")
#     print(f"  Sample missing nodes: {list(od_nodes_not_in_graph)[:10]}")
#     print(f"  These OD pairs will not find paths!")
    
#     # Count affected OD pairs
#     affected_origins = df_od[df_od['origin_franodeid'].isin(od_nodes_not_in_graph)]
#     affected_dests = df_od[df_od['destination_franodeid'].isin(od_nodes_not_in_graph)]
#     total_affected = len(affected_origins) + len(affected_dests)
#     print(f"  Affected OD pairs: {total_affected:,} ({total_affected/len(df_od)*100:.2f}%)")
# else:
#     print(f"\n✓ SUCCESS: All OD pair FRANODEIDs exist in graph!")

# print("=" * 80)

# # ==================================================
# # UNIT CONVERSIONS
# # ==================================================
# print("\nApplying unit conversions...")

# df_od["tons_2024_day"] = (
#     df_od["tons_2024"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR
# )
# df_od["tons_2050_day"] = (
#     df_od["tons_2050"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR
# )
# df_od["value_2024_day"] = df_od["value_2024"] / DAYS_PER_YEAR
# df_od["value_2050_day"] = df_od["value_2050"] / DAYS_PER_YEAR

# print("✓ Converted to tons/day and value/day")

# # ==================================================
# # BUILD GRAPH (using FRFRANODE and TOFRANODE)
# # ==================================================
# print("\nBuilding NetworkX graph using FRANODEIDs...")
# t0 = time.time()

# G = nx.Graph()
# edge_geom = {}
# edge_data = {}

# # Create a lookup for node geometries and coordinates
# node_geom_lookup = dict(zip(gdf_nodes['FRANODEID'], gdf_nodes.geometry))
# node_coords_lookup = {}
# for franodeid, geom in node_geom_lookup.items():
#     node_coords_lookup[franodeid] = (geom.x, geom.y)

# for idx, e in gdf_edges.iterrows():
#     u = e["FRFRANODE"]
#     v = e["TOFRANODE"]
    
#     # Skip if either node is null
#     if pd.isna(u) or pd.isna(v):
#         continue
    
#     # Converting the length from meter to miles
#     length_miles = e["LENGTH"] / 1609.344  # meters to miles conversion
#     G.add_edge(u, v, weight=length_miles)
    
#     # Store edge as undirected (sorted tuple)
#     edge_key = tuple(sorted((u, v)))
#     edge_geom[edge_key] = e.geometry
#     edge_data[edge_key] = {
#         'FRFRANODE': u,
#         'TOFRANODE': v,
#         'LENGTH_MILES': length_miles,
#         'LENGTH_METERS': e["LENGTH"],
#         'NET': e['NET'],
#         'NUM_MERGED': e['NUM_MERGED'],
#         'MERGED_OBJECTIDS': e['MERGED_OBJECTIDS']
#     }

# print(
#     f"✓ Graph: {G.number_of_nodes():,} nodes, "
#     f"{G.number_of_edges():,} edges "
#     f"({time.time() - t0:.2f}s)"
# )

# # Verify graph connectivity
# if not nx.is_connected(G):
#     num_components = nx.number_connected_components(G)
#     print(f"\n⚠ WARNING: Graph has {num_components} disconnected components!")
#     components = list(nx.connected_components(G))
#     largest_component = max(components, key=len)
#     print(f"  Largest component: {len(largest_component):,} nodes")
#     print(f"  Some OD pairs may not find paths between components")
# else:
#     print(f"✓ Graph is fully connected")

# # ==================================================
# # GROUP OD PAIRS BY ORIGIN FRANODEID
# # ==================================================
# print("\nGrouping OD pairs by origin FRANODEID...")
# t0 = time.time()

# od_groups = df_od.groupby("origin_franodeid").indices
# unique_origins = list(od_groups.keys())

# print(f"✓ Unique origin FRANODEIDs: {len(unique_origins):,}")
# print(f"✓ Grouping time: {time.time() - t0:.2f}s")

# # ==================================================
# # HELPER: Build path geometry from edge geometries (for GPKG only)
# # ==================================================
# def build_path_geometry(node_path, edge_geom):
#     """
#     Build continuous path geometry by merging edge geometries.
#     Only used for verification GPKGs.
#     """
#     if len(node_path) < 2:
#         return None
    
#     edge_geoms = []
    
#     for i in range(len(node_path) - 1):
#         u = node_path[i]
#         v = node_path[i + 1]
#         edge_key = tuple(sorted((u, v)))
        
#         if edge_key in edge_geom:
#             geom = edge_geom[edge_key]
            
#             if i > 0 and len(edge_geoms) > 0:
#                 prev_geom = edge_geoms[-1]
#                 prev_end = prev_geom.coords[-1]
                
#                 curr_start = geom.coords[0]
#                 curr_end = geom.coords[-1]
                
#                 dist_to_start = ((prev_end[0] - curr_start[0])**2 + (prev_end[1] - curr_start[1])**2)**0.5
#                 dist_to_end = ((prev_end[0] - curr_end[0])**2 + (prev_end[1] - curr_end[1])**2)**0.5
                
#                 if dist_to_end < dist_to_start:
#                     geom = LineString(list(geom.coords)[::-1])
            
#             edge_geoms.append(geom)
    
#     if len(edge_geoms) == 0:
#         return None
    
#     try:
#         merged = linemerge(edge_geoms)
#         return merged
#     except:
#         return MultiLineString(edge_geoms)

# # ==================================================
# # ACCUMULATORS
# # ==================================================
# link_flows = defaultdict(lambda: {
#     "tons_2024_day": 0.0,
#     "value_2024_day": 0.0,
#     "tons_2050_day": 0.0,
#     "value_2050_day": 0.0,
#     "num_od_pairs": 0
# })

# # Progress tracking
# progress_data = []

# # ==================================================
# # ASSIGNMENT WITH CSV-ONLY OUTPUT
# # ==================================================
# print("\n" + "=" * 80)
# print("RUNNING SHORTEST-PATH ASSIGNMENT")
# print(f"Saving CSV for ALL origins, GPKG for first {NUM_GPKG_FOR_VERIFICATION} only")
# print("=" * 80)

# start_time = time.time()
# num_origins = len(unique_origins)

# # Statistics
# total_od_paths = 0
# total_od_no_path = 0
# total_od_origin_not_in_graph = 0
# gpkg_count = 0

# for i, origin in enumerate(unique_origins, start=1):
    
#     origin_start_time = time.time()
    
#     # Progress update
#     if i % 10 == 0 or i == 1:
#         elapsed = time.time() - start_time
#         avg_sec = elapsed / max(i, 1)
#         eta_hours = avg_sec * (num_origins - i) / 3600.0
#         remaining = num_origins - i
#         print(
#             f"\nOrigin {i:,}/{num_origins:,} ({i/num_origins*100:.1f}%) | "
#             f"Remaining: {remaining:,} | ETA: {eta_hours:.1f} hours"
#         )
#         print(f"  Total paths: {total_od_paths:,} | No path: {total_od_no_path:,}")
#         print(f"  Avg time/origin: {avg_sec:.1f} sec")
    
#     # Check if origin exists in graph
#     if origin not in G:
#         total_od_origin_not_in_graph += len(od_groups[origin])
        
#         progress_data.append({
#             'origin_franodeid': origin,
#             'status': 'SKIPPED_NOT_IN_GRAPH',
#             'num_destinations': len(od_groups[origin]),
#             'paths_found': 0,
#             'processing_time_sec': 0
#         })
#         continue
    
#     try:
#         lengths, paths = nx.single_source_dijkstra(G, origin, weight="weight")
#     except Exception as e:
#         print(f"  ERROR: Origin {origin}: {e}")
#         progress_data.append({
#             'origin_franodeid': origin,
#             'status': 'ERROR',
#             'num_destinations': len(od_groups[origin]),
#             'paths_found': 0,
#             'processing_time_sec': time.time() - origin_start_time
#         })
#         continue
    
#     # Collect paths for this origin
#     origin_paths = []
#     origin_paths_found = 0
#     origin_no_path = 0
    
#     # Get origin coordinates
#     origin_coords = node_coords_lookup.get(origin, (None, None))
#     origin_x, origin_y = origin_coords
    
#     # Process all destinations for this origin
#     for idx in od_groups[origin]:
#         od = df_od.loc[idx]
#         dest = od["destination_franodeid"]
        
#         # Check if path exists
#         if dest not in paths:
#             origin_no_path += 1
#             total_od_no_path += 1
#             continue
        
#         node_path = paths[dest]
#         path_len_miles = lengths[dest]
        
#         # Travel time
#         travel_time_hours = path_len_miles / SPEED_MPH
#         travel_time_days = travel_time_hours / HOURS_PER_DAY
        
#         # Get destination coordinates
#         dest_coords = node_coords_lookup.get(dest, (None, None))
#         dest_x, dest_y = dest_coords
        
#         # Store path data (CSV-friendly)
#         od_rec = {
#             "origin_franodeid": origin,
#             "destination_franodeid": dest,
#             "origin_x": origin_x,
#             "origin_y": origin_y,
#             "destination_x": dest_x,
#             "destination_y": dest_y,
#             "origin_node_label": od["origin_node_label"],
#             "destination_node_label": od["destination_node_label"],
#             "origin_node_type": od["origin_node_type"],
#             "destination_node_type": od["destination_node_type"],
#             "path_length_miles": path_len_miles,
#             "travel_time_hours": travel_time_hours,
#             "travel_time_days": travel_time_days,
#             "tons_2024_day": od["tons_2024_day"],
#             "value_2024_day": od["value_2024_day"],
#             "tons_2050_day": od["tons_2050_day"],
#             "value_2050_day": od["value_2050_day"],
#             "ton_hours_2024": od["tons_2024_day"] * travel_time_hours,
#             "value_hours_2024": od["value_2024_day"] * travel_time_hours,
#             "ton_hours_2050": od["tons_2050_day"] * travel_time_hours,
#             "value_hours_2050": od["value_2050_day"] * travel_time_hours,
#             "num_edges_in_path": len(node_path) - 1,
#             "original_origin_county": od["original_origin_county"],
#             "original_dest_county": od["original_dest_county"]
#         }
        
#         origin_paths.append(od_rec)
#         origin_paths_found += 1
#         total_od_paths += 1
        
#         # Accumulate link flows
#         for k in range(len(node_path) - 1):
#             edge_key = tuple(sorted((node_path[k], node_path[k + 1])))
            
#             link_flows[edge_key]["tons_2024_day"] += od["tons_2024_day"]
#             link_flows[edge_key]["value_2024_day"] += od["value_2024_day"]
#             link_flows[edge_key]["tons_2050_day"] += od["tons_2050_day"]
#             link_flows[edge_key]["value_2050_day"] += od["value_2050_day"]
#             link_flows[edge_key]["num_od_pairs"] += 1
    
#     # Save this origin's paths
#     if len(origin_paths) > 0:
#         # ALWAYS save CSV (fast)
#         df_origin_csv = pd.DataFrame(origin_paths)
#         csv_path = os.path.join(od_paths_by_origin_dir, f"origin_{int(origin)}.csv")
#         df_origin_csv.to_csv(csv_path, index=False)
        
#         # Only save GPKG for first N origins (verification)
#         if gpkg_count < NUM_GPKG_FOR_VERIFICATION:
#             print(f"  → Creating verification GPKG for origin {int(origin)} ({gpkg_count + 1}/{NUM_GPKG_FOR_VERIFICATION})")
            
#             # Add geometry for GPKG
#             origin_paths_with_geom = []
#             for path_data in origin_paths:
#                 # Rebuild node path from origin to dest
#                 dest = path_data["destination_franodeid"]
#                 if dest in paths:
#                     node_path = paths[dest]
#                     path_geom = build_path_geometry(node_path, edge_geom)
                    
#                     path_data_copy = path_data.copy()
#                     path_data_copy['geometry'] = path_geom
#                     origin_paths_with_geom.append(path_data_copy)
            
#             if len(origin_paths_with_geom) > 0:
#                 gdf_origin = gpd.GeoDataFrame(origin_paths_with_geom, crs=gdf_edges.crs)
#                 gpkg_path = os.path.join(od_paths_by_origin_dir, f"origin_{int(origin)}.gpkg")
#                 gdf_origin.to_file(gpkg_path, driver="GPKG")
#                 print(f"  ✓ GPKG saved for verification")
            
#             gpkg_count += 1
        
#         print(f"  ✓ Saved origin {int(origin)}: {origin_paths_found:,} paths ({origin_no_path:,} no path) [{time.time() - origin_start_time:.1f}s]")
    
#     # Track progress
#     origin_time = time.time() - origin_start_time
#     progress_data.append({
#         'origin_franodeid': origin,
#         'status': 'SUCCESS',
#         'num_destinations': len(od_groups[origin]),
#         'paths_found': origin_paths_found,
#         'paths_not_found': origin_no_path,
#         'processing_time_sec': origin_time
#     })
    
#     # Save progress file periodically
#     if i % 100 == 0 or i == num_origins:
#         df_progress = pd.DataFrame(progress_data)
#         df_progress.to_csv(progress_file, index=False)
#         print(f"  → Progress saved ({i}/{num_origins} origins)")

# total_time = time.time() - start_time

# print("\n" + "=" * 80)
# print("INDIVIDUAL ORIGIN FILES COMPLETE")
# print("=" * 80)
# print(f"✓ Processing finished in {total_time/60:.1f} minutes ({total_time/3600:.1f} hours)")
# print(f"✓ Total OD paths found: {total_od_paths:,}")
# print(f"✗ OD pairs with no path: {total_od_no_path:,}")
# if total_od_origin_not_in_graph > 0:
#     print(f"✗ OD pairs with origin not in graph: {total_od_origin_not_in_graph:,}")

# # ==================================================
# # CREATE COMBINED OD PATHS CSV
# # ==================================================
# print("\n" + "=" * 80)
# print("CREATING COMBINED OD PATHS CSV")
# print("=" * 80)
# print("Reading all individual CSV files and combining...")

# all_origin_files_csv = [f for f in os.listdir(od_paths_by_origin_dir) if f.endswith('.csv')]
# print(f"Found {len(all_origin_files_csv)} CSV files")

# # Combine all CSVs
# print("\nCombining CSVs...")
# combined_dfs = []
# for i, csv_file in enumerate(all_origin_files_csv, start=1):
#     if i % 100 == 0:
#         print(f"  Reading file {i}/{len(all_origin_files_csv)}...")
    
#     csv_path = os.path.join(od_paths_by_origin_dir, csv_file)
#     df = pd.read_csv(csv_path)
#     combined_dfs.append(df)

# df_combined = pd.concat(combined_dfs, ignore_index=True)

# print(f"✓ Combined DataFrame: {len(df_combined):,} paths")

# # Save combined CSV
# print(f"Saving combined CSV to: {output_od_paths_combined_csv}")
# df_combined.to_csv(output_od_paths_combined_csv, index=False)
# print(f"✓ Saved")

# # Clean up
# del combined_dfs, df_combined
# gc.collect()

# # ==================================================
# # CREATE OUTPUT: LINK-LEVEL FLOWS (ALL M/I LINKS)
# # ==================================================
# print("\n" + "=" * 80)
# print("CREATING LINK-LEVEL FLOW GEOPACKAGE")
# print("Including ALL M/I links (even those with zero flow)")
# print("=" * 80)

# link_rows = []

# # Iterate through ALL edges in the original M/I network
# for idx, e in gdf_edges.iterrows():
#     u = e["FRFRANODE"]
#     v = e["TOFRANODE"]
    
#     if pd.isna(u) or pd.isna(v):
#         continue
    
#     edge_key = tuple(sorted((u, v)))
    
#     # Get flows for this edge (will be 0 if not used)
#     flows = link_flows.get(edge_key, {
#         "tons_2024_day": 0.0,
#         "value_2024_day": 0.0,
#         "tons_2050_day": 0.0,
#         "value_2050_day": 0.0,
#         "num_od_pairs": 0
#     })
    
#     link_rows.append({
#         "FRFRANODE": u,
#         "TOFRANODE": v,
#         "LENGTH_MILES": e["LENGTH"] / 1609.344,
#         "LENGTH_METERS": e["LENGTH"],
#         "NET": e['NET'],
#         "NUM_MERGED": e['NUM_MERGED'],
#         "MERGED_OBJECTIDS": e['MERGED_OBJECTIDS'],
#         "tons_2024_day": flows["tons_2024_day"],
#         "value_2024_day": flows["value_2024_day"],
#         "tons_2050_day": flows["tons_2050_day"],
#         "value_2050_day": flows["value_2050_day"],
#         "num_od_pairs": flows["num_od_pairs"],
#         "geometry": e.geometry
#     })

# gdf_links = gpd.GeoDataFrame(link_rows, crs=gdf_edges.crs)

# # Sort by flow volume for easier analysis
# gdf_links = gdf_links.sort_values('tons_2024_day', ascending=False)

# gdf_links.to_file(output_links_gpkg, layer="rail_link_flows", driver="GPKG")

# print(f"✓ Saved link flows → {output_links_gpkg}")
# print(f"  Total M/I links: {len(gdf_links):,}")
# print(f"  Links with flow > 0: {(gdf_links['tons_2024_day'] > 0).sum():,}")
# print(f"  Links with zero flow: {(gdf_links['tons_2024_day'] == 0).sum():,}")

# # ==================================================
# # FLOW STATISTICS
# # ==================================================
# print("\n" + "=" * 80)
# print("FLOW STATISTICS")
# print("=" * 80)

# print(f"\n2024 Flow Summary:")
# print(f"  Total daily tons  : {gdf_links['tons_2024_day'].sum():,.0f}")
# print(f"  Total daily value : ${gdf_links['value_2024_day'].sum():,.0f}")
# print(f"  Max link tons/day : {gdf_links['tons_2024_day'].max():,.0f}")
# print(f"  Avg link tons/day (non-zero): {gdf_links[gdf_links['tons_2024_day'] > 0]['tons_2024_day'].mean():,.0f}")

# print(f"\n2050 Flow Summary:")
# print(f"  Total daily tons  : {gdf_links['tons_2050_day'].sum():,.0f}")
# print(f"  Total daily value : ${gdf_links['value_2050_day'].sum():,.0f}")
# print(f"  Max link tons/day : {gdf_links['tons_2050_day'].max():,.0f}")
# print(f"  Avg link tons/day (non-zero): {gdf_links[gdf_links['tons_2050_day'] > 0]['tons_2050_day'].mean():,.0f}")

# print(f"\nTop 10 busiest links (2024 tons/day):")
# top_links = gdf_links.nlargest(10, 'tons_2024_day')[
#     ['FRFRANODE', 'TOFRANODE', 'LENGTH_MILES', 'tons_2024_day', 'num_od_pairs']
# ]
# print(top_links.to_string(index=False))

# # ==================================================
# # FINAL SUMMARY
# # ==================================================
# print("\n" + "=" * 80)
# print("FINAL SUMMARY")
# print("=" * 80)

# print(f"""
# INPUT:
#   OD pairs total           : {len(df_od):,}
#   Unique origin FRANODEIDs : {len(unique_origins):,}
#   Unique dest FRANODEIDs   : {len(od_dest_nodes):,}

# OUTPUT - INDIVIDUAL ORIGIN FILES:
#   Directory                : {od_paths_by_origin_dir}
#   CSV files created        : {len(all_origin_files_csv):,}
#   GPKG files (verification): {gpkg_count} (first {NUM_GPKG_FOR_VERIFICATION} origins)

# OUTPUT - COMBINED FILES:
#   OD paths found           : {total_od_paths:,} ({total_od_paths/len(df_od)*100:.1f}%)
#   OD pairs with no path    : {total_od_no_path:,} ({total_od_no_path/len(df_od)*100:.1f}%)
  
# LINK FLOWS:
#   Total M/I links          : {len(gdf_links):,}
#   Links with flows         : {(gdf_links['tons_2024_day'] > 0).sum():,}
#   Links with zero flow     : {(gdf_links['tons_2024_day'] == 0).sum():,}

# PERFORMANCE:
#   Total processing time    : {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)
#   Average speed            : {total_od_paths/total_time:.0f} OD paths/second
#   Average time per origin  : {total_time/num_origins:.1f} seconds

# FLOWS (2024):
#   Total daily tons         : {gdf_links['tons_2024_day'].sum():,.0f}
#   Total daily value        : ${gdf_links['value_2024_day'].sum():,.0f}
# """)

# print("=" * 80)
# print("ALL OUTPUTS:")
# print("=" * 80)
# print(f"\n1. INDIVIDUAL ORIGIN CSV FILES:")
# print(f"   {od_paths_by_origin_dir}/")
# print(f"   - origin_<FRANODEID>.csv")
# print(f"   - Includes origin_x, origin_y, destination_x, destination_y")
# print(f"   - Can import to QGIS using 'Add Delimited Text Layer'")
# print(f"   Total: {len(all_origin_files_csv):,} CSV files")

# print(f"\n2. VERIFICATION GPKG FILES (first {NUM_GPKG_FOR_VERIFICATION} origins):")
# print(f"   {od_paths_by_origin_dir}/")
# print(f"   - origin_<FRANODEID>.gpkg")
# print(f"   - Verify path geometries are correct")

# print(f"\n3. COMBINED OD PATHS CSV:")
# print(f"   {output_od_paths_combined_csv}")
# print(f"   - {total_od_paths:,} total paths")
# print(f"   - origin_franodeid, destination_franodeid columns")
# print(f"   - origin_x, origin_y, destination_x, destination_y")
# print(f"   - All flow and time data")

# print(f"\n4. LINK FLOWS GEOPACKAGE (ALL M/I LINKS WITH WEIGHTS):")
# print(f"   {output_links_gpkg}")
# print(f"   - ALL {len(gdf_links):,} M/I rail links")
# print(f"   - Links WITH flow: {(gdf_links['tons_2024_day'] > 0).sum():,}")
# print(f"   - Links with ZERO flow: {(gdf_links['tons_2024_day'] == 0).sum():,}")
# print(f"   - FRFRANODE, TOFRANODE columns")
# print(f"   - tons_2024_day, value_2024_day (link weights)")
# print(f"   - tons_2050_day, value_2050_day (future weights)")
# print(f"   - Use for visualization and analysis")

# print(f"\n5. PROGRESS TRACKING:")
# print(f"   {progress_file}")
# print(f"   - Processing time per origin")
# print(f"   - Success/error status")

# print("\n" + "=" * 80)
# print("DONE!")
# print(f"Check first {NUM_GPKG_FOR_VERIFICATION} GPKG files to verify path geometries")
# print("All origin CSVs can be imported to QGIS using origin_x/y and destination_x/y")
# print("=" * 80)

# %%
#!========================================================================
#! 3 - MODIFIED BASELINE
#! Add link tracking for faster disruption analysis
#? Run time: 170 minutes
#!========================================================================

import geopandas as gpd
import pandas as pd
import networkx as nx
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge
from collections import defaultdict
import os
import time
import gc

# ==================================================
# CONFIGURATION
# ==================================================
SPEED_MPH = 49.0
HOURS_PER_DAY = 24.0
DAYS_PER_YEAR = 365.0
THOUSAND_TONS_TO_TONS = 1000.0

NUM_GPKG_FOR_VERIFICATION = 5

# ==================================================
# PATHS
# ==================================================
base_dir = os.path.abspath(os.path.join("..", ".."))

rail_graph_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Graph",
    "Rail_Graph_Nodes_Edges.gpkg"
)

od_pairs_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_pairs_from_nodes.gpkg"
)

od_paths_by_origin_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "OD_Paths_By_Origin"
)

output_links_gpkg = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_link_flows_daily_ALL_LINKS.gpkg"
)

output_od_paths_combined_csv = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_paths_daily_COMBINED.csv"
)

progress_file = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "processing_progress.csv"
)

os.makedirs(od_paths_by_origin_dir, exist_ok=True)

# ==================================================
# READ DATA
# ==================================================
print("=" * 80)
print("MODIFIED BASELINE - WITH LINK TRACKING")
print("=" * 80)

print("Reading rail network...")
gdf_edges = gpd.read_file(rail_graph_path, layer="edges")
gdf_nodes = gpd.read_file(rail_graph_path, layer="nodes")

print(f"✓ Edges: {len(gdf_edges):,}")
print(f"✓ Nodes: {len(gdf_nodes):,}")

print("\nReading OD pairs...")
gdf_od = gpd.read_file(od_pairs_path)
print(f"✓ OD pairs: {len(gdf_od):,}")

df_od = pd.DataFrame(gdf_od.drop(columns="geometry"))
del gdf_od
gc.collect()

# ==================================================
# UNIT CONVERSIONS
# ==================================================
print("\nApplying unit conversions...")

df_od["tons_2024_day"] = (df_od["tons_2024"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR)
df_od["tons_2050_day"] = (df_od["tons_2050"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR)
df_od["value_2024_day"] = df_od["value_2024"] / DAYS_PER_YEAR
df_od["value_2050_day"] = df_od["value_2050"] / DAYS_PER_YEAR

print("✓ Converted to tons/day and value/day")

# ==================================================
# BUILD GRAPH AND EDGE LOOKUP
# ==================================================
print("\nBuilding NetworkX graph and edge lookup...")
t0 = time.time()

G = nx.Graph()
edge_geom = {}
edge_data = {}

# **KEY CHANGE**: Create FID lookup for each edge
# Map from (FRFRANODE, TOFRANODE) sorted tuple to row index (FID)
edge_key_to_fid = {}

node_geom_lookup = dict(zip(gdf_nodes['FRANODEID'], gdf_nodes.geometry))
node_coords_lookup = {}
for franodeid, geom in node_geom_lookup.items():
    node_coords_lookup[franodeid] = (geom.x, geom.y)

for idx, e in gdf_edges.iterrows():
    u = e["FRFRANODE"]
    v = e["TOFRANODE"]
    
    if pd.isna(u) or pd.isna(v):
        continue
    
    length_miles = e["LENGTH"] / 1609.344
    G.add_edge(u, v, weight=length_miles)
    
    edge_key = tuple(sorted((u, v)))
    edge_geom[edge_key] = e.geometry
    edge_data[edge_key] = {
        'FRFRANODE': u,
        'TOFRANODE': v,
        'LENGTH_MILES': length_miles,
        'LENGTH_METERS': e["LENGTH"],
        'NET': e['NET'],
        'NUM_MERGED': e['NUM_MERGED'],
        'MERGED_OBJECTIDS': e['MERGED_OBJECTIDS'],
        'FID': idx  # **KEY: Store the row index as FID**
    }
    
    # **KEY CHANGE**: Map edge to FID
    edge_key_to_fid[edge_key] = idx

print(f"✓ Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges ({time.time() - t0:.2f}s)")

# ==================================================
# GROUP OD PAIRS BY ORIGIN
# ==================================================
print("\nGrouping OD pairs by origin FRANODEID...")
od_groups = df_od.groupby("origin_franodeid").indices
unique_origins = list(od_groups.keys())
print(f"✓ Unique origin FRANODEIDs: {len(unique_origins):,}")

# ==================================================
# HELPER: Build path geometry (for verification GPKGs)
# ==================================================
def build_path_geometry(node_path, edge_geom):
    if len(node_path) < 2:
        return None
    
    edge_geoms = []
    for i in range(len(node_path) - 1):
        u = node_path[i]
        v = node_path[i + 1]
        edge_key = tuple(sorted((u, v)))
        
        if edge_key in edge_geom:
            geom = edge_geom[edge_key]
            
            if i > 0 and len(edge_geoms) > 0:
                prev_geom = edge_geoms[-1]
                prev_end = prev_geom.coords[-1]
                curr_start = geom.coords[0]
                curr_end = geom.coords[-1]
                
                dist_to_start = ((prev_end[0] - curr_start[0])**2 + (prev_end[1] - curr_start[1])**2)**0.5
                dist_to_end = ((prev_end[0] - curr_end[0])**2 + (prev_end[1] - curr_end[1])**2)**0.5
                
                if dist_to_end < dist_to_start:
                    geom = LineString(list(geom.coords)[::-1])
            
            edge_geoms.append(geom)
    
    if len(edge_geoms) == 0:
        return None
    
    try:
        merged = linemerge(edge_geoms)
        return merged
    except:
        return MultiLineString(edge_geoms)

# ==================================================
# ACCUMULATORS
# ==================================================
link_flows = defaultdict(lambda: {
    "tons_2024_day": 0.0,
    "value_2024_day": 0.0,
    "tons_2050_day": 0.0,
    "value_2050_day": 0.0,
    "num_od_pairs": 0
})

progress_data = []

# ==================================================
# ASSIGNMENT WITH LINK TRACKING
# ==================================================
print("\n" + "=" * 80)
print("RUNNING ASSIGNMENT - NOW TRACKING LINK FIDs")
print("=" * 80)

start_time = time.time()
num_origins = len(unique_origins)

total_od_paths = 0
total_od_no_path = 0
total_od_origin_not_in_graph = 0
gpkg_count = 0

for i, origin in enumerate(unique_origins, start=1):
    
    origin_start_time = time.time()
    
    if i % 10 == 0 or i == 1:
        elapsed = time.time() - start_time
        avg_sec = elapsed / max(i, 1)
        eta_hours = avg_sec * (num_origins - i) / 3600.0
        remaining = num_origins - i
        print(
            f"\nOrigin {i:,}/{num_origins:,} ({i/num_origins*100:.1f}%) | "
            f"Remaining: {remaining:,} | ETA: {eta_hours:.1f} hours"
        )
        print(f"  Total paths: {total_od_paths:,} | No path: {total_od_no_path:,}")
        print(f"  Avg time/origin: {avg_sec:.1f} sec")
    
    if origin not in G:
        total_od_origin_not_in_graph += len(od_groups[origin])
        progress_data.append({
            'origin_franodeid': origin,
            'status': 'SKIPPED_NOT_IN_GRAPH',
            'num_destinations': len(od_groups[origin]),
            'paths_found': 0,
            'processing_time_sec': 0
        })
        continue
    
    try:
        lengths, paths = nx.single_source_dijkstra(G, origin, weight="weight")
    except Exception as e:
        print(f"  ERROR: Origin {origin}: {e}")
        progress_data.append({
            'origin_franodeid': origin,
            'status': 'ERROR',
            'num_destinations': len(od_groups[origin]),
            'paths_found': 0,
            'processing_time_sec': time.time() - origin_start_time
        })
        continue
    
    origin_paths = []
    origin_paths_found = 0
    origin_no_path = 0
    
    origin_coords = node_coords_lookup.get(origin, (None, None))
    origin_x, origin_y = origin_coords
    
    for idx in od_groups[origin]:
        od = df_od.loc[idx]
        dest = od["destination_franodeid"]
        
        if dest not in paths:
            origin_no_path += 1
            total_od_no_path += 1
            continue
        
        node_path = paths[dest]
        path_len_miles = lengths[dest]
        
        travel_time_hours = path_len_miles / SPEED_MPH
        travel_time_days = travel_time_hours / HOURS_PER_DAY
        
        dest_coords = node_coords_lookup.get(dest, (None, None))
        dest_x, dest_y = dest_coords
        
        # **KEY CHANGE**: Collect FIDs of links in this path
        path_link_fids = []
        for k in range(len(node_path) - 1):
            edge_key = tuple(sorted((node_path[k], node_path[k + 1])))
            if edge_key in edge_key_to_fid:
                fid = edge_key_to_fid[edge_key]
                path_link_fids.append(fid)
        
        # Convert to comma-separated string
        path_link_fids_str = ",".join(str(fid) for fid in path_link_fids)
        
        od_rec = {
            "origin_franodeid": origin,
            "destination_franodeid": dest,
            "origin_x": origin_x,
            "origin_y": origin_y,
            "destination_x": dest_x,
            "destination_y": dest_y,
            "origin_node_label": od["origin_node_label"],
            "destination_node_label": od["destination_node_label"],
            "origin_node_type": od["origin_node_type"],
            "destination_node_type": od["destination_node_type"],
            "path_length_miles": path_len_miles,
            "travel_time_hours": travel_time_hours,
            "travel_time_days": travel_time_days,
            "tons_2024_day": od["tons_2024_day"],
            "value_2024_day": od["value_2024_day"],
            "tons_2050_day": od["tons_2050_day"],
            "value_2050_day": od["value_2050_day"],
            "ton_hours_2024": od["tons_2024_day"] * travel_time_hours,
            "value_hours_2024": od["value_2024_day"] * travel_time_hours,
            "ton_hours_2050": od["tons_2050_day"] * travel_time_hours,
            "value_hours_2050": od["value_2050_day"] * travel_time_hours,
            "num_edges_in_path": len(node_path) - 1,
            "original_origin_county": od["original_origin_county"],
            "original_dest_county": od["original_dest_county"],
            "path_link_fids": path_link_fids_str  # **KEY: New column**
        }
        
        origin_paths.append(od_rec)
        origin_paths_found += 1
        total_od_paths += 1
        
        # Accumulate link flows
        for k in range(len(node_path) - 1):
            edge_key = tuple(sorted((node_path[k], node_path[k + 1])))
            link_flows[edge_key]["tons_2024_day"] += od["tons_2024_day"]
            link_flows[edge_key]["value_2024_day"] += od["value_2024_day"]
            link_flows[edge_key]["tons_2050_day"] += od["tons_2050_day"]
            link_flows[edge_key]["value_2050_day"] += od["value_2050_day"]
            link_flows[edge_key]["num_od_pairs"] += 1
    
    if len(origin_paths) > 0:
        # Save CSV
        df_origin_csv = pd.DataFrame(origin_paths)
        csv_path = os.path.join(od_paths_by_origin_dir, f"origin_{int(origin)}.csv")
        df_origin_csv.to_csv(csv_path, index=False)
        
        # Save GPKG for first N origins
        if gpkg_count < NUM_GPKG_FOR_VERIFICATION:
            print(f"  → Creating verification GPKG for origin {int(origin)} ({gpkg_count + 1}/{NUM_GPKG_FOR_VERIFICATION})")
            
            origin_paths_with_geom = []
            for path_data in origin_paths:
                dest = path_data["destination_franodeid"]
                if dest in paths:
                    node_path = paths[dest]
                    path_geom = build_path_geometry(node_path, edge_geom)
                    
                    path_data_copy = path_data.copy()
                    path_data_copy['geometry'] = path_geom
                    origin_paths_with_geom.append(path_data_copy)
            
            if len(origin_paths_with_geom) > 0:
                gdf_origin = gpd.GeoDataFrame(origin_paths_with_geom, crs=gdf_edges.crs)
                gpkg_path = os.path.join(od_paths_by_origin_dir, f"origin_{int(origin)}.gpkg")
                gdf_origin.to_file(gpkg_path, driver="GPKG")
                print(f"  ✓ GPKG saved for verification")
            
            gpkg_count += 1
        
        print(f"  ✓ Saved origin {int(origin)}: {origin_paths_found:,} paths ({origin_no_path:,} no path) [{time.time() - origin_start_time:.1f}s]")
    
    origin_time = time.time() - origin_start_time
    progress_data.append({
        'origin_franodeid': origin,
        'status': 'SUCCESS',
        'num_destinations': len(od_groups[origin]),
        'paths_found': origin_paths_found,
        'paths_not_found': origin_no_path,
        'processing_time_sec': origin_time
    })
    
    if i % 100 == 0 or i == num_origins:
        df_progress = pd.DataFrame(progress_data)
        df_progress.to_csv(progress_file, index=False)
        print(f"  → Progress saved ({i}/{num_origins} origins)")

total_time = time.time() - start_time

print("\n" + "=" * 80)
print("BASELINE COMPLETE WITH LINK TRACKING")
print("=" * 80)
print(f"✓ Processing finished in {total_time/60:.1f} minutes ({total_time/3600:.1f} hours)")
print(f"✓ Total OD paths found: {total_od_paths:,}")

# ==================================================
# COMBINE CSVs
# ==================================================
print("\n" + "=" * 80)
print("CREATING COMBINED CSV")
print("=" * 80)

all_origin_files_csv = [f for f in os.listdir(od_paths_by_origin_dir) if f.endswith('.csv')]
print(f"Found {len(all_origin_files_csv)} CSV files")

combined_dfs = []
for i, csv_file in enumerate(all_origin_files_csv, start=1):
    if i % 100 == 0:
        print(f"  Reading file {i}/{len(all_origin_files_csv)}...")
    
    csv_path = os.path.join(od_paths_by_origin_dir, csv_file)
    df = pd.read_csv(csv_path)
    combined_dfs.append(df)

df_combined = pd.concat(combined_dfs, ignore_index=True)
print(f"✓ Combined DataFrame: {len(df_combined):,} paths")

df_combined.to_csv(output_od_paths_combined_csv, index=False)
print(f"✓ Saved: {output_od_paths_combined_csv}")

del combined_dfs, df_combined
gc.collect()

# ==================================================
# CREATE LINK FLOWS (ALL LINKS)
# ==================================================
print("\n" + "=" * 80)
print("CREATING LINK FLOWS GEOPACKAGE")
print("=" * 80)

link_rows = []
for idx, e in gdf_edges.iterrows():
    u = e["FRFRANODE"]
    v = e["TOFRANODE"]
    
    if pd.isna(u) or pd.isna(v):
        continue
    
    edge_key = tuple(sorted((u, v)))
    flows = link_flows.get(edge_key, {
        "tons_2024_day": 0.0,
        "value_2024_day": 0.0,
        "tons_2050_day": 0.0,
        "value_2050_day": 0.0,
        "num_od_pairs": 0
    })
    
    link_rows.append({
        "FID": idx,  # **KEY: Add FID column**
        "FRFRANODE": u,
        "TOFRANODE": v,
        "LENGTH_MILES": e["LENGTH"] / 1609.344,
        "LENGTH_METERS": e["LENGTH"],
        "NET": e['NET'],
        "NUM_MERGED": e['NUM_MERGED'],
        "MERGED_OBJECTIDS": e['MERGED_OBJECTIDS'],
        "tons_2024_day": flows["tons_2024_day"],
        "value_2024_day": flows["value_2024_day"],
        "tons_2050_day": flows["tons_2050_day"],
        "value_2050_day": flows["value_2050_day"],
        "num_od_pairs": flows["num_od_pairs"],
        "geometry": e.geometry
    })

gdf_links = gpd.GeoDataFrame(link_rows, crs=gdf_edges.crs)
gdf_links = gdf_links.sort_values('tons_2024_day', ascending=False)
gdf_links.to_file(output_links_gpkg, layer="rail_link_flows", driver="GPKG")

print(f"✓ Saved: {output_links_gpkg}")
print(f"  Total links: {len(gdf_links):,}")
print(f"  Links with flow > 0: {(gdf_links['tons_2024_day'] > 0).sum():,}")

print("\n" + "=" * 80)
print("DONE! Now ready for optimized disruption analysis!")
print("=" * 80)

# %%
#!========================================================================
#! CREATE PRESENTATION-QUALITY ANIMATED GIF FOR ORIGIN 301117
#! Shows all destination paths being drawn one-by-one
#! Professional styling for presentations
#!========================================================================

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
from shapely.geometry import LineString, MultiLineString
from shapely.ops import linemerge
import numpy as np
import os

# ==================================================
# CONFIGURATION
# ==================================================
ORIGIN_FRANODEID = 301117  # The origin to visualize

# Animation settings
FRAMES_PER_PATH = 0.2  # How many frames to show each path (1 = fast, 3-5 = slower)
FPS = 50  # Frames per second (10 = fast animation, 5 = slower)
DPI = 100  # Resolution (150 = good quality, 200 = high quality)

# Styling
FIGURE_SIZE = (16, 12)  # Large figure for presentation
BACKGROUND_COLOR = '#1a1a1a'  # Dark background (professional)
BASE_NETWORK_COLOR = '#404040'  # Gray for background network
BASE_NETWORK_ALPHA = 0.3
PATH_COLORS = {
    'YARD': '#00d4ff',      # Cyan for YARD destinations
    'END': '#ff6b35',       # Orange for END destinations
    'JUNCTION': '#a3de83',  # Light green for JUNCTION destinations
    'O_JUNCTION': '#ffd23f' # Yellow for O_JUNCTION destinations
}
ORIGIN_COLOR = '#ff1744'    # Bright red for origin point
DESTINATION_COLOR = '#ffffff'  # White for destination points
PATH_WIDTH = 2.5
ORIGIN_SIZE = 150
DESTINATION_SIZE = 50

# Text styling
TITLE_COLOR = '#ffffff'
TEXT_COLOR = '#e0e0e0'
STATS_COLOR = '#00ff00'

# ==================================================
# PATHS
# ==================================================
base_dir = os.path.abspath(os.path.join("..", ".."))

# Origin OD paths CSV
origin_csv = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "OD_Paths_By_Origin",
    f"origin_{ORIGIN_FRANODEID}.csv"
)

# Rail network
rail_graph_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Graph",
    "Rail_Graph_Nodes_Edges.gpkg"
)

# Output
output_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Presentation_Materials"
)
os.makedirs(output_dir, exist_ok=True)

output_gif = os.path.join(output_dir, f"origin_{ORIGIN_FRANODEID}_paths_animation.gif")

# ==================================================
# READ DATA
# ==================================================
print("=" * 80)
print("CREATING PRESENTATION-QUALITY ANIMATED GIF")
print("=" * 80)
print(f"\nOrigin FRANODEID: {ORIGIN_FRANODEID}")

# Read OD paths
print("\nReading OD paths...")
df_paths = pd.read_csv(origin_csv)
print(f"✓ Paths from origin: {len(df_paths):,}")

# Read rail network
print("Reading rail network...")
gdf_edges = gpd.read_file(rail_graph_path, layer="edges")
gdf_nodes = gpd.read_file(rail_graph_path, layer="nodes")
print(f"✓ Network edges: {len(gdf_edges):,}")
print(f"✓ Network nodes: {len(gdf_nodes):,}")

# Get CRS
crs = gdf_edges.crs

# Create node lookup
node_geom = dict(zip(gdf_nodes['FRANODEID'], gdf_nodes.geometry))

# Create edge lookup for path geometry construction
edge_geom = {}
for idx, e in gdf_edges.iterrows():
    u = e["FRFRANODE"]
    v = e["TOFRANODE"]
    if pd.notna(u) and pd.notna(v):
        edge_key = tuple(sorted((u, v)))
        edge_geom[edge_key] = e.geometry

# ==================================================
# BUILD PATH GEOMETRIES
# ==================================================
print("\nBuilding path geometries...")

def build_path_geometry_from_nodes(origin, destination, edge_geom, node_geom):
    """
    Simplified path geometry builder that connects origin to destination
    using straight line (for presentation purposes)
    """
    if origin not in node_geom or destination not in node_geom:
        return None
    
    origin_point = node_geom[origin]
    dest_point = node_geom[destination]
    
    # Create straight line (simplified for visualization)
    return LineString([origin_point, dest_point])

path_geometries = []

for idx, row in df_paths.iterrows():
    dest = row['destination_franodeid']
    dest_type = row['destination_node_type']
    
    # Build path geometry (simplified)
    path_geom = build_path_geometry_from_nodes(ORIGIN_FRANODEID, dest, edge_geom, node_geom)
    
    if path_geom is not None:
        path_geometries.append({
            'geometry': path_geom,
            'destination': dest,
            'dest_type': dest_type,
            'dest_label': row['destination_node_label'],
            'tons_2024': row['tons_2024_day'],
            'value_2024': row['value_2024_day'],
            'travel_time': row['travel_time_hours'],
            'dest_x': row['destination_x'],
            'dest_y': row['destination_y']
        })

gdf_paths = gpd.GeoDataFrame(path_geometries, crs=crs)
print(f"✓ Path geometries created: {len(gdf_paths):,}")

# Get origin geometry
origin_geom = node_geom[ORIGIN_FRANODEID]

# ==================================================
# STATISTICS
# ==================================================
total_paths = len(gdf_paths)
total_tons = gdf_paths['tons_2024'].sum()
total_value = gdf_paths['value_2024'].sum()
avg_travel_time = gdf_paths['travel_time'].mean()

dest_type_counts = gdf_paths['dest_type'].value_counts()

print(f"\nStatistics:")
print(f"  Total paths: {total_paths:,}")
print(f"  Total daily tons (2024): {total_tons:,.0f}")
print(f"  Total daily value (2024): ${total_value:,.0f}")
print(f"  Average travel time: {avg_travel_time:.1f} hours")
print(f"\nDestination types:")
for dtype, count in dest_type_counts.items():
    print(f"  {dtype}: {count:,} ({count/total_paths*100:.1f}%)")

# ==================================================
# CREATE ANIMATION
# ==================================================
print("\n" + "=" * 80)
print("CREATING ANIMATION")
print("=" * 80)

# Create figure
fig, ax = plt.subplots(figsize=FIGURE_SIZE, facecolor=BACKGROUND_COLOR)
ax.set_facecolor(BACKGROUND_COLOR)

# Plot base network (background)
print("Plotting base network...")
gdf_edges.plot(ax=ax, color=BASE_NETWORK_COLOR, linewidth=0.5, alpha=BASE_NETWORK_ALPHA, zorder=1)

# Get bounds for zooming
bounds = gdf_paths.total_bounds
margin = 0.1 * max(bounds[2] - bounds[0], bounds[3] - bounds[1])
ax.set_xlim(bounds[0] - margin, bounds[2] + margin)
ax.set_ylim(bounds[1] - margin, bounds[3] + margin)

# Remove axes
ax.set_xticks([])
ax.set_yticks([])
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['bottom'].set_visible(False)
ax.spines['left'].set_visible(False)

# Plot origin point (always visible)
ax.scatter(origin_geom.x, origin_geom.y, 
           c=ORIGIN_COLOR, s=ORIGIN_SIZE, 
           marker='*', edgecolors='white', linewidths=2,
           zorder=100, label='Origin')

# Title and labels (will be updated)
title_text = ax.text(0.5, 0.98, f'Origin {ORIGIN_FRANODEID} - Freight Path Network', 
                     transform=ax.transAxes,
                     fontsize=20, fontweight='bold', 
                     ha='center', va='top',
                     color=TITLE_COLOR)

stats_text = ax.text(0.02, 0.98, '', 
                     transform=ax.transAxes,
                     fontsize=12, 
                     ha='left', va='top',
                     color=TEXT_COLOR,
                     family='monospace')

counter_text = ax.text(0.98, 0.98, '', 
                       transform=ax.transAxes,
                       fontsize=14, fontweight='bold',
                       ha='right', va='top',
                       color=STATS_COLOR)

# Prepare animation data
num_paths = len(gdf_paths)
total_frames = num_paths * FRAMES_PER_PATH

print(f"\nAnimation settings:")
print(f"  Total paths: {num_paths}")
print(f"  Frames per path: {FRAMES_PER_PATH}")
print(f"  Total frames: {total_frames}")
print(f"  FPS: {FPS}")
print(f"  Duration: {total_frames/FPS:.1f} seconds")

# Animation function
def animate(frame):
    """Update function for animation"""
    
    # Which path are we drawing?
    path_idx = frame // FRAMES_PER_PATH
    
    if path_idx >= num_paths:
        path_idx = num_paths - 1
    
    # Draw all paths up to current index
    for i in range(path_idx + 1):
        path_data = gdf_paths.iloc[i]
        dest_type = path_data['dest_type']
        color = PATH_COLORS.get(dest_type, '#ffffff')
        
        # Draw path
        if path_data.geometry.geom_type == 'LineString':
            x, y = path_data.geometry.xy
            ax.plot(x, y, color=color, linewidth=PATH_WIDTH, alpha=0.7, zorder=2)
        
        # Draw destination point
        ax.scatter(path_data['dest_x'], path_data['dest_y'],
                   c=color, s=DESTINATION_SIZE,
                   edgecolors='white', linewidths=1,
                   alpha=0.8, zorder=3)
    
    # Update counter
    counter_text.set_text(f'Paths: {path_idx + 1:,} / {num_paths:,}')
    
    # Update stats (cumulative)
    cumulative_paths = gdf_paths.iloc[:path_idx + 1]
    cumulative_tons = cumulative_paths['tons_2024'].sum()
    cumulative_value = cumulative_paths['value_2024'].sum()
    
    stats_str = (
        f"Cumulative Stats:\n"
        f"  Tons/day: {cumulative_tons:,.0f}\n"
        f"  Value/day: ${cumulative_value:,.0f}\n"
        f"  Avg Travel: {cumulative_paths['travel_time'].mean():.1f} hrs"
    )
    stats_text.set_text(stats_str)
    
    return [counter_text, stats_text]

# Create animation
print("\nGenerating animation frames...")
anim = animation.FuncAnimation(
    fig, 
    animate, 
    frames=total_frames,
    interval=1000/FPS,  # milliseconds between frames
    blit=False,
    repeat=True
)

# Add legend
legend_elements = [
    plt.Line2D([0], [0], marker='*', color='w', 
               markerfacecolor=ORIGIN_COLOR, markersize=15, 
               label='Origin', linestyle='None', markeredgecolor='white', markeredgewidth=1.5),
]

for dest_type, color in PATH_COLORS.items():
    count = dest_type_counts.get(dest_type, 0)
    if count > 0:
        legend_elements.append(
            plt.Line2D([0], [0], color=color, linewidth=3, 
                       label=f'{dest_type} ({count:,})', alpha=0.8)
        )

ax.legend(handles=legend_elements, 
          loc='lower right', 
          fontsize=11,
          framealpha=0.9,
          facecolor='#2a2a2a',
          edgecolor='white',
          labelcolor=TEXT_COLOR)

# Save animation
print(f"\nSaving GIF to: {output_gif}")
print("This may take a few minutes...")

writer = animation.PillowWriter(fps=FPS)
anim.save(output_gif, writer=writer, dpi=DPI)

plt.close()

print("\n" + "=" * 80)
print("ANIMATION COMPLETE!")
print("=" * 80)
print(f"\nOutput file: {output_gif}")
print(f"File size: {os.path.getsize(output_gif) / (1024*1024):.1f} MB")
print(f"\nAnimation specs:")
print(f"  Resolution: {int(FIGURE_SIZE[0]*DPI)} x {int(FIGURE_SIZE[1]*DPI)} pixels")
print(f"  Duration: {total_frames/FPS:.1f} seconds")
print(f"  FPS: {FPS}")
print(f"  Total frames: {total_frames}")
print(f"\nReady for presentation! 🎬")
print("=" * 80)

# %%