# # %%
# #!========================================================================
# #! Stage 5 - Part 1: Run Disruption Scenarios (CORRECTED)
# #! Randomly disrupt links and recalculate OD paths with flow data
# #!========================================================================

# import geopandas as gpd
# import pandas as pd
# import networkx as nx
# from collections import defaultdict
# import os
# import time
# import gc
# import numpy as np
# import random

# # ==================================================
# # CONFIGURATION
# # ==================================================
# SPEED_MPH = 49.0
# THOUSAND_TONS_TO_TONS = 1000.0
# DAYS_PER_YEAR = 365.0

# # Disruption Configuration
# DISRUPTION_PERCENTAGES = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]  # 5% to 50%
# NUM_MONTE_CARLO_RUNS = 1  # CHANGE THIS TO RUN MULTIPLE SCENARIOS

# # Random seed for reproducibility
# RANDOM_SEED = 42

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

# # Baseline OD paths with flow data
# baseline_od_paths_csv = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "rail_od_paths_daily_COMBINED.csv"
# )

# # Output directory
# disruption_scenarios_dir = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Disruption_Scenarios"
# )

# os.makedirs(disruption_scenarios_dir, exist_ok=True)

# # ==================================================
# # READ DATA
# # ==================================================
# print("=" * 80)
# print("STAGE 5 - PART 1: RUN DISRUPTION SCENARIOS")
# print("=" * 80)
# print(f"\nConfiguration:")
# print(f"  Disruption percentages: {[f'{p*100:.0f}%' for p in DISRUPTION_PERCENTAGES]}")
# print(f"  Monte Carlo runs: {NUM_MONTE_CARLO_RUNS}")
# print(f"  Total scenarios: {len(DISRUPTION_PERCENTAGES) * NUM_MONTE_CARLO_RUNS}")
# print()

# if RANDOM_SEED is not None:
#     random.seed(RANDOM_SEED)
#     np.random.seed(RANDOM_SEED)

# print("Reading rail network...")
# gdf_edges = gpd.read_file(rail_graph_path, layer="edges")
# gdf_nodes = gpd.read_file(rail_graph_path, layer="nodes")
# print(f"✓ Edges: {len(gdf_edges):,}")
# print(f"✓ Nodes: {len(gdf_nodes):,}")

# print("\nReading baseline OD paths...")
# df_baseline = pd.read_csv(baseline_od_paths_csv)
# print(f"✓ Baseline OD paths: {len(df_baseline):,}")

# # Convert baseline to proper units if needed
# if 'tons_2024_day' not in df_baseline.columns:
#     df_baseline["tons_2024_day"] = df_baseline["tons_2024"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR
#     df_baseline["value_2024_day"] = df_baseline["value_2024"] / DAYS_PER_YEAR
#     df_baseline["tons_2050_day"] = df_baseline["tons_2050"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR
#     df_baseline["value_2050_day"] = df_baseline["value_2050"] / DAYS_PER_YEAR

# # Create baseline lookup: (origin, dest) -> flow data
# print("\nCreating baseline lookup...")
# baseline_lookup = {}
# for _, row in df_baseline.iterrows():
#     key = (row['origin_franodeid'], row['destination_franodeid'])
#     baseline_lookup[key] = {
#         'tons_2024_day': row['tons_2024_day'],
#         'value_2024_day': row['value_2024_day'],
#         'tons_2050_day': row['tons_2050_day'],
#         'value_2050_day': row['value_2050_day'],
#         'origin_node_type': row['origin_node_type'],
#         'destination_node_type': row['destination_node_type'],
#         'original_origin_county': row['original_origin_county'],
#         'original_dest_county': row['original_dest_county']
#     }

# baseline_od_set = set(baseline_lookup.keys())
# print(f"✓ Baseline OD pairs in lookup: {len(baseline_od_set):,}")

# # ==================================================
# # HELPER: Build graph from edges
# # ==================================================
# def build_graph_from_edges(gdf_edges_subset):
#     """Build NetworkX graph from edge GeoDataFrame."""
#     G = nx.Graph()
    
#     for idx, e in gdf_edges_subset.iterrows():
#         u = e["FRFRANODE"]
#         v = e["TOFRANODE"]
        
#         if pd.isna(u) or pd.isna(v):
#             continue
        
#         length_miles = e["LENGTH"] / 1609.344
#         G.add_edge(u, v, weight=length_miles)
    
#     return G

# # ==================================================
# # HELPER: Calculate OD paths with flow data
# # ==================================================
# def calculate_disrupted_od_paths(G_disrupted, baseline_od_set, baseline_lookup):
#     """Calculate OD paths for disrupted network with flow data."""
    
#     od_paths = []
    
#     # Group by origin for efficient processing
#     od_by_origin = defaultdict(list)
#     for origin, dest in baseline_od_set:
#         od_by_origin[origin].append(dest)
    
#     total_origins = len(od_by_origin)
    
#     for i, (origin, destinations) in enumerate(od_by_origin.items(), start=1):
#         if i % 100 == 0:
#             print(f"    Processing origin {i}/{total_origins}...")
        
#         # Check if origin in disrupted graph
#         if origin not in G_disrupted:
#             # All OD pairs from this origin are infeasible
#             for dest in destinations:
#                 flow_data = baseline_lookup[(origin, dest)]
                
#                 od_paths.append({
#                     "origin_franodeid": origin,
#                     "destination_franodeid": dest,
#                     "origin_node_type": flow_data['origin_node_type'],
#                     "destination_node_type": flow_data['destination_node_type'],
#                     "original_origin_county": flow_data['original_origin_county'],
#                     "original_dest_county": flow_data['original_dest_county'],
#                     "path_length_miles": np.inf,
#                     "travel_time_hours": np.inf,
#                     "tons_2024_day": flow_data['tons_2024_day'],
#                     "value_2024_day": flow_data['value_2024_day'],
#                     "tons_2050_day": flow_data['tons_2050_day'],
#                     "value_2050_day": flow_data['value_2050_day'],
#                     "ton_hours_2024": np.inf,
#                     "value_hours_2024": np.inf,
#                     "ton_hours_2050": np.inf,
#                     "value_hours_2050": np.inf
#                 })
#             continue
        
#         # Run single-source Dijkstra
#         try:
#             lengths, paths = nx.single_source_dijkstra(G_disrupted, origin, weight="weight")
#         except Exception:
#             # Origin is isolated
#             for dest in destinations:
#                 flow_data = baseline_lookup[(origin, dest)]
                
#                 od_paths.append({
#                     "origin_franodeid": origin,
#                     "destination_franodeid": dest,
#                     "origin_node_type": flow_data['origin_node_type'],
#                     "destination_node_type": flow_data['destination_node_type'],
#                     "original_origin_county": flow_data['original_origin_county'],
#                     "original_dest_county": flow_data['original_dest_county'],
#                     "path_length_miles": np.inf,
#                     "travel_time_hours": np.inf,
#                     "tons_2024_day": flow_data['tons_2024_day'],
#                     "value_2024_day": flow_data['value_2024_day'],
#                     "tons_2050_day": flow_data['tons_2050_day'],
#                     "value_2050_day": flow_data['value_2050_day'],
#                     "ton_hours_2024": np.inf,
#                     "value_hours_2024": np.inf,
#                     "ton_hours_2050": np.inf,
#                     "value_hours_2050": np.inf
#                 })
#             continue
        
#         # Process each destination
#         for dest in destinations:
#             flow_data = baseline_lookup[(origin, dest)]
            
#             if dest not in paths:
#                 # Infeasible - no path
#                 od_paths.append({
#                     "origin_franodeid": origin,
#                     "destination_franodeid": dest,
#                     "origin_node_type": flow_data['origin_node_type'],
#                     "destination_node_type": flow_data['destination_node_type'],
#                     "original_origin_county": flow_data['original_origin_county'],
#                     "original_dest_county": flow_data['original_dest_county'],
#                     "path_length_miles": np.inf,
#                     "travel_time_hours": np.inf,
#                     "tons_2024_day": flow_data['tons_2024_day'],
#                     "value_2024_day": flow_data['value_2024_day'],
#                     "tons_2050_day": flow_data['tons_2050_day'],
#                     "value_2050_day": flow_data['value_2050_day'],
#                     "ton_hours_2024": np.inf,
#                     "value_hours_2024": np.inf,
#                     "ton_hours_2050": np.inf,
#                     "value_hours_2050": np.inf
#                 })
#             else:
#                 # Path exists
#                 path_len_miles = lengths[dest]
#                 travel_time_hours = path_len_miles / SPEED_MPH
                
#                 # Calculate ton-hours and value-hours
#                 ton_hours_2024 = flow_data['tons_2024_day'] * travel_time_hours
#                 value_hours_2024 = flow_data['value_2024_day'] * travel_time_hours
#                 ton_hours_2050 = flow_data['tons_2050_day'] * travel_time_hours
#                 value_hours_2050 = flow_data['value_2050_day'] * travel_time_hours
                
#                 od_paths.append({
#                     "origin_franodeid": origin,
#                     "destination_franodeid": dest,
#                     "origin_node_type": flow_data['origin_node_type'],
#                     "destination_node_type": flow_data['destination_node_type'],
#                     "original_origin_county": flow_data['original_origin_county'],
#                     "original_dest_county": flow_data['original_dest_county'],
#                     "path_length_miles": path_len_miles,
#                     "travel_time_hours": travel_time_hours,
#                     "tons_2024_day": flow_data['tons_2024_day'],
#                     "value_2024_day": flow_data['value_2024_day'],
#                     "tons_2050_day": flow_data['tons_2050_day'],
#                     "value_2050_day": flow_data['value_2050_day'],
#                     "ton_hours_2024": ton_hours_2024,
#                     "value_hours_2024": value_hours_2024,
#                     "ton_hours_2050": ton_hours_2050,
#                     "value_hours_2050": value_hours_2050
#                 })
    
#     return od_paths

# # ==================================================
# # RUN DISRUPTION SCENARIOS
# # ==================================================
# print("\n" + "=" * 80)
# print("RUNNING DISRUPTION SCENARIOS")
# print("=" * 80)

# all_edge_indices = list(gdf_edges.index)
# total_edges = len(all_edge_indices)
# print(f"\nTotal M/I links: {total_edges:,}")

# scenario_metadata = []
# overall_start_time = time.time()
# scenario_count = 0
# total_scenarios = len(DISRUPTION_PERCENTAGES) * NUM_MONTE_CARLO_RUNS

# for disrupt_pct in DISRUPTION_PERCENTAGES:
#     print(f"\n{'='*80}")
#     print(f"DISRUPTION LEVEL: {disrupt_pct*100:.0f}%")
#     print(f"{'='*80}")
    
#     num_links_to_disrupt = int(total_edges * disrupt_pct)
#     print(f"Links to disrupt: {num_links_to_disrupt:,}")
    
#     for mc_run in range(1, NUM_MONTE_CARLO_RUNS + 1):
#         scenario_count += 1
#         scenario_start_time = time.time()
        
#         print(f"\n--- Run {mc_run}/{NUM_MONTE_CARLO_RUNS} ---")
        
#         # Random disruption
#         disrupted_edge_indices = random.sample(all_edge_indices, num_links_to_disrupt)
#         gdf_edges_remaining = gdf_edges.drop(disrupted_edge_indices)
        
#         print(f"  Remaining links: {len(gdf_edges_remaining):,}")
        
#         # Build disrupted graph
#         print(f"  Building disrupted graph...")
#         G_disrupted = build_graph_from_edges(gdf_edges_remaining)
#         print(f"  Graph: {G_disrupted.number_of_nodes():,} nodes, {G_disrupted.number_of_edges():,} edges")
        
#         # Calculate paths
#         print(f"  Calculating OD paths...")
#         od_paths_disrupted = calculate_disrupted_od_paths(
#             G_disrupted, baseline_od_set, baseline_lookup
#         )
        
#         num_feasible = sum(1 for p in od_paths_disrupted if not np.isinf(p['travel_time_hours']))
#         num_infeasible = len(od_paths_disrupted) - num_feasible
        
#         print(f"  Feasible: {num_feasible:,}, Infeasible: {num_infeasible:,}")
        
#         # Save
#         scenario_id = f"disrupt_{int(disrupt_pct*100):02d}pct_run_{mc_run:03d}"
#         csv_filename = f"{scenario_id}_od_paths.csv"
#         csv_path = os.path.join(disruption_scenarios_dir, csv_filename)
        
#         df_disrupted = pd.DataFrame(od_paths_disrupted)
#         df_disrupted.to_csv(csv_path, index=False)
#         print(f"  ✓ Saved: {csv_filename}")
        
#         # Save disrupted links
#         disrupted_links_csv = f"{scenario_id}_disrupted_links.csv"
#         disrupted_links_path = os.path.join(disruption_scenarios_dir, disrupted_links_csv)
#         gdf_edges.loc[disrupted_edge_indices][['FRFRANODE', 'TOFRANODE', 'LENGTH']].to_csv(
#             disrupted_links_path, index=False
#         )
        
#         scenario_time = time.time() - scenario_start_time
        
#         # Metadata
#         scenario_metadata.append({
#             'scenario_id': scenario_id,
#             'disruption_percentage': disrupt_pct,
#             'monte_carlo_run': mc_run,
#             'num_links_disrupted': num_links_to_disrupt,
#             'num_feasible_paths': num_feasible,
#             'num_infeasible_paths': num_infeasible,
#             'processing_time_sec': scenario_time,
#             'od_paths_file': csv_filename
#         })
        
#         print(f"  ⏱ Time: {scenario_time:.1f}s | Progress: {scenario_count}/{total_scenarios}")
        
#         # ETA
#         elapsed = time.time() - overall_start_time
#         eta_min = (elapsed / scenario_count) * (total_scenarios - scenario_count) / 60
#         print(f"  ETA: {eta_min:.1f} min")
        
#         del G_disrupted, od_paths_disrupted, df_disrupted
#         gc.collect()

# total_time = time.time() - overall_start_time

# # Save metadata
# df_metadata = pd.DataFrame(scenario_metadata)
# metadata_path = os.path.join(disruption_scenarios_dir, "scenario_metadata.csv")
# df_metadata.to_csv(metadata_path, index=False)

# print("\n" + "=" * 80)
# print("COMPLETE!")
# print("=" * 80)
# print(f"Total time: {total_time/60:.1f} min")
# print(f"Output: {disruption_scenarios_dir}")
# print("=" * 80)
# # %%
# #!========================================================================
# #! Stage 5 - Part 2: Resilience Analysis (CORRECTED)
# #! Using weighted travel time (ton-hours and value-hours)
# #!========================================================================

# import pandas as pd
# import numpy as np
# import os
# import matplotlib.pyplot as plt
# import seaborn as sns
# from scipy import stats

# # ==================================================
# # PATHS
# # ==================================================
# base_dir = os.path.abspath(os.path.join("..", ".."))

# baseline_od_paths_csv = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "rail_od_paths_daily_COMBINED.csv"
# )

# disruption_scenarios_dir = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Disruption_Scenarios"
# )

# metadata_path = os.path.join(disruption_scenarios_dir, "scenario_metadata.csv")

# output_dir = os.path.join(
#     base_dir,
#     "13_Resiliency",
#     "FAF",
#     "Processed_Data",
#     "County_Level",
#     "Resilience_Analysis"
# )

# os.makedirs(output_dir, exist_ok=True)

# resilience_summary_csv = os.path.join(output_dir, "resilience_summary.csv")
# figures_dir = os.path.join(output_dir, "figures")
# os.makedirs(figures_dir, exist_ok=True)

# # ==================================================
# # CONFIGURATION
# # ==================================================
# THOUSAND_TONS_TO_TONS = 1000.0
# DAYS_PER_YEAR = 365.0

# # ==================================================
# # READ BASELINE
# # ==================================================
# print("=" * 80)
# print("STAGE 5 - PART 2: RESILIENCE ANALYSIS")
# print("=" * 80)

# print("\nReading baseline...")
# df_baseline = pd.read_csv(baseline_od_paths_csv)
# print(f"✓ Baseline OD paths: {len(df_baseline):,}")

# # Ensure proper units
# if 'tons_2024_day' not in df_baseline.columns:
#     df_baseline["tons_2024_day"] = df_baseline["tons_2024"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR
#     df_baseline["value_2024_day"] = df_baseline["value_2024"] / DAYS_PER_YEAR
#     df_baseline["tons_2050_day"] = df_baseline["tons_2050"] * THOUSAND_TONS_TO_TONS / DAYS_PER_YEAR
#     df_baseline["value_2050_day"] = df_baseline["value_2050"] / DAYS_PER_YEAR

# # Calculate baseline ton-hours and value-hours
# df_baseline['ton_hours_2024'] = df_baseline['tons_2024_day'] * df_baseline['travel_time_hours']
# df_baseline['value_hours_2024'] = df_baseline['value_2024_day'] * df_baseline['travel_time_hours']
# df_baseline['ton_hours_2050'] = df_baseline['tons_2050_day'] * df_baseline['travel_time_hours']
# df_baseline['value_hours_2050'] = df_baseline['value_2050_day'] * df_baseline['travel_time_hours']

# # Create baseline lookup
# baseline_lookup = {}
# for _, row in df_baseline.iterrows():
#     key = (row['origin_franodeid'], row['destination_franodeid'])
#     baseline_lookup[key] = {
#         'ton_hours_2024': row['ton_hours_2024'],
#         'value_hours_2024': row['value_hours_2024'],
#         'ton_hours_2050': row['ton_hours_2050'],
#         'value_hours_2050': row['value_hours_2050'],
#         'tons_2024_day': row['tons_2024_day'],
#         'value_2024_day': row['value_2024_day']
#     }

# print(f"✓ Baseline lookup created: {len(baseline_lookup):,} OD pairs")

# # Read metadata
# df_metadata = pd.read_csv(metadata_path)
# print(f"✓ Scenarios: {len(df_metadata)}")

# # ==================================================
# # ANALYZE SCENARIOS
# # ==================================================
# print("\n" + "=" * 80)
# print("ANALYZING SCENARIOS")
# print("=" * 80)

# scenario_results = []

# for idx, scenario_row in df_metadata.iterrows():
#     scenario_id = scenario_row['scenario_id']
#     disrupt_pct = scenario_row['disruption_percentage']
#     mc_run = scenario_row['monte_carlo_run']
#     od_paths_file = scenario_row['od_paths_file']
    
#     print(f"\n[{idx+1}/{len(df_metadata)}] {scenario_id}...")
    
#     # Read disrupted paths
#     od_paths_path = os.path.join(disruption_scenarios_dir, od_paths_file)
#     df_disrupted = pd.read_csv(od_paths_path)
    
#     # Initialize counters
#     num_total = len(df_disrupted)
#     num_unaffected = 0
#     num_delayed = 0
#     num_infeasible = 0
    
#     sum_f_ton_2024 = 0
#     sum_f_value_2024 = 0
#     sum_f_ton_2050 = 0
#     sum_f_value_2050 = 0
    
#     unaffected_tons_2024 = 0
#     delayed_tons_2024 = 0
#     infeasible_tons_2024 = 0
    
#     unaffected_value_2024 = 0
#     delayed_value_2024 = 0
#     infeasible_value_2024 = 0
    
#     total_tons_2024 = df_disrupted['tons_2024_day'].sum()
#     total_value_2024 = df_disrupted['value_2024_day'].sum()
    
#     # Analyze each OD pair
#     for _, row in df_disrupted.iterrows():
#         key = (row['origin_franodeid'], row['destination_franodeid'])
#         baseline_data = baseline_lookup[key]
        
#         tons_2024 = row['tons_2024_day']
#         value_2024 = row['value_2024_day']
        
#         # Get baseline ton-hours and value-hours
#         ton_hours_baseline_2024 = baseline_data['ton_hours_2024']
#         value_hours_baseline_2024 = baseline_data['value_hours_2024']
#         ton_hours_baseline_2050 = baseline_data['ton_hours_2050']
#         value_hours_baseline_2050 = baseline_data['value_hours_2050']
        
#         # Get disrupted ton-hours and value-hours
#         ton_hours_disrupted_2024 = row['ton_hours_2024']
#         value_hours_disrupted_2024 = row['value_hours_2024']
#         ton_hours_disrupted_2050 = row['ton_hours_2050']
#         value_hours_disrupted_2050 = row['value_hours_2050']
        
#         # Check if infeasible
#         if np.isinf(ton_hours_disrupted_2024):
#             # Infeasible
#             num_infeasible += 1
#             infeasible_tons_2024 += tons_2024
#             infeasible_value_2024 += value_2024
            
#             # f_k = 0 for infeasible
#             f_ton_2024 = 0
#             f_value_2024 = 0
#             f_ton_2050 = 0
#             f_value_2050 = 0
#         else:
#             # Calculate Δ(ton-hours) and Δ(value-hours)
#             delta_ton_hours_2024 = ton_hours_disrupted_2024 - ton_hours_baseline_2024
#             delta_value_hours_2024 = value_hours_disrupted_2024 - value_hours_baseline_2024
#             delta_ton_hours_2050 = ton_hours_disrupted_2050 - ton_hours_baseline_2050
#             delta_value_hours_2050 = value_hours_disrupted_2050 - value_hours_baseline_2050
            
#             # Calculate functionality: f_k = 1 / (1 + Δ)
#             f_ton_2024 = 1.0 / (1.0 + delta_ton_hours_2024)
#             f_value_2024 = 1.0 / (1.0 + delta_value_hours_2024)
#             f_ton_2050 = 1.0 / (1.0 + delta_ton_hours_2050)
#             f_value_2050 = 1.0 / (1.0 + delta_value_hours_2050)
            
#             # Classify
#             if abs(delta_ton_hours_2024) < 0.001:  # Essentially zero
#                 num_unaffected += 1
#                 unaffected_tons_2024 += tons_2024
#                 unaffected_value_2024 += value_2024
#             else:
#                 num_delayed += 1
#                 delayed_tons_2024 += tons_2024
#                 delayed_value_2024 += value_2024
        
#         # Accumulate functionality
#         sum_f_ton_2024 += f_ton_2024
#         sum_f_value_2024 += f_value_2024
#         sum_f_ton_2050 += f_ton_2050
#         sum_f_value_2050 += f_value_2050
    
#     # Calculate network functionality (simple average)
#     F_ton_2024 = sum_f_ton_2024 / num_total if num_total > 0 else 0
#     F_value_2024 = sum_f_value_2024 / num_total if num_total > 0 else 0
#     F_ton_2050 = sum_f_ton_2050 / num_total if num_total > 0 else 0
#     F_value_2050 = sum_f_value_2050 / num_total if num_total > 0 else 0
    
#     # Reachability
#     reachability = (num_unaffected + num_delayed) / num_total if num_total > 0 else 0
    
#     print(f"  Unaffected: {num_unaffected:,} ({num_unaffected/num_total*100:.1f}%)")
#     print(f"  Delayed: {num_delayed:,} ({num_delayed/num_total*100:.1f}%)")
#     print(f"  Infeasible: {num_infeasible:,} ({num_infeasible/num_total*100:.1f}%)")
#     print(f"  Reachability: {reachability:.4f}")
#     print(f"  F_ton_2024: {F_ton_2024:.4f}")
#     print(f"  F_value_2024: {F_value_2024:.4f}")
    
#     # Store results
#     scenario_results.append({
#         'scenario_id': scenario_id,
#         'disruption_percentage': disrupt_pct,
#         'monte_carlo_run': mc_run,
#         'num_total': num_total,
#         'num_unaffected': num_unaffected,
#         'num_delayed': num_delayed,
#         'num_infeasible': num_infeasible,
#         'pct_unaffected': num_unaffected / num_total * 100,
#         'pct_delayed': num_delayed / num_total * 100,
#         'pct_infeasible': num_infeasible / num_total * 100,
#         'unaffected_tons_2024': unaffected_tons_2024,
#         'delayed_tons_2024': delayed_tons_2024,
#         'infeasible_tons_2024': infeasible_tons_2024,
#         'total_tons_2024': total_tons_2024,
#         'unaffected_value_2024': unaffected_value_2024,
#         'delayed_value_2024': delayed_value_2024,
#         'infeasible_value_2024': infeasible_value_2024,
#         'total_value_2024': total_value_2024,
#         'reachability': reachability,
#         'F_ton_2024': F_ton_2024,
#         'F_value_2024': F_value_2024,
#         'F_ton_2050': F_ton_2050,
#         'F_value_2050': F_value_2050
#     })

# df_results = pd.DataFrame(scenario_results)
# df_results.to_csv(resilience_summary_csv, index=False)
# print(f"\n✓ Saved: {resilience_summary_csv}")

# # ==================================================
# # CREATE RESILIENCE CURVES
# # ==================================================
# print("\n" + "=" * 80)
# print("CREATING RESILIENCE CURVES")
# print("=" * 80)

# # Group by disruption percentage
# df_grouped = df_results.groupby('disruption_percentage').agg({
#     'reachability': ['mean', 'std'],
#     'F_ton_2024': ['mean', 'std'],
#     'F_value_2024': ['mean', 'std'],
#     'F_ton_2050': ['mean', 'std'],
#     'F_value_2050': ['mean', 'std']
# }).reset_index()

# df_grouped.columns = ['_'.join(col).strip('_') for col in df_grouped.columns.values]

# num_mc_runs = df_results['monte_carlo_run'].nunique()

# # Calculate 95% CI if multiple runs
# if num_mc_runs > 1:
#     for metric in ['reachability', 'F_ton_2024', 'F_value_2024', 'F_ton_2050', 'F_value_2050']:
#         df_grouped[f'{metric}_ci'] = df_grouped[f'{metric}_std'] * stats.t.ppf(0.975, num_mc_runs - 1) / np.sqrt(num_mc_runs)
#     print(f"✓ 95% CI calculated (n={num_mc_runs})")
# else:
#     print(f"⚠ Single run - no CI")

# sns.set_style("whitegrid")

# # Figure 1: Reachability
# fig, ax = plt.subplots(figsize=(10, 7))
# ax.plot(df_grouped['disruption_percentage'] * 100, df_grouped['reachability_mean'], 
#         'o-', linewidth=2.5, markersize=8, color='#2E86AB')
# if num_mc_runs > 1:
#     ax.fill_between(df_grouped['disruption_percentage'] * 100,
#                      df_grouped['reachability_mean'] - df_grouped['reachability_ci'],
#                      df_grouped['reachability_mean'] + df_grouped['reachability_ci'],
#                      alpha=0.3, color='#2E86AB')
# ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=13, fontweight='bold')
# ax.set_ylabel('Reachability', fontsize=13, fontweight='bold')
# ax.set_title('Network Reachability vs Link Disruption', fontsize=14, fontweight='bold')
# ax.grid(True, alpha=0.3)
# ax.set_ylim([0, 1.05])
# plt.tight_layout()
# fig.savefig(os.path.join(figures_dir, 'resilience_reachability.png'), dpi=300, bbox_inches='tight')
# print("✓ Saved: resilience_reachability.png")
# plt.close()

# # Figure 2: F_ton_2024
# fig, ax = plt.subplots(figsize=(10, 7))
# ax.plot(df_grouped['disruption_percentage'] * 100, df_grouped['F_ton_2024_mean'], 
#         'o-', linewidth=2.5, markersize=8, color='#A23B72')
# if num_mc_runs > 1:
#     ax.fill_between(df_grouped['disruption_percentage'] * 100,
#                      df_grouped['F_ton_2024_mean'] - df_grouped['F_ton_2024_ci'],
#                      df_grouped['F_ton_2024_mean'] + df_grouped['F_ton_2024_ci'],
#                      alpha=0.3, color='#A23B72')
# ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=13, fontweight='bold')
# ax.set_ylabel('Network Functionality F(Gd)', fontsize=13, fontweight='bold')
# ax.set_title('Network Functionality vs Link Disruption\nWeighted by Ton-Hours (2024)', fontsize=14, fontweight='bold')
# ax.grid(True, alpha=0.3)
# ax.set_ylim([0, 1.05])
# plt.tight_layout()
# fig.savefig(os.path.join(figures_dir, 'resilience_F_ton_2024.png'), dpi=300, bbox_inches='tight')
# print("✓ Saved: resilience_F_ton_2024.png")
# plt.close()

# # Figure 3: F_value_2024
# fig, ax = plt.subplots(figsize=(10, 7))
# ax.plot(df_grouped['disruption_percentage'] * 100, df_grouped['F_value_2024_mean'], 
#         'o-', linewidth=2.5, markersize=8, color='#F18F01')
# if num_mc_runs > 1:
#     ax.fill_between(df_grouped['disruption_percentage'] * 100,
#                      df_grouped['F_value_2024_mean'] - df_grouped['F_value_2024_ci'],
#                      df_grouped['F_value_2024_mean'] + df_grouped['F_value_2024_ci'],
#                      alpha=0.3, color='#F18F01')
# ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=13, fontweight='bold')
# ax.set_ylabel('Network Functionality F(Gd)', fontsize=13, fontweight='bold')
# ax.set_title('Network Functionality vs Link Disruption\nWeighted by Value-Hours (2024)', fontsize=14, fontweight='bold')
# ax.grid(True, alpha=0.3)
# ax.set_ylim([0, 1.05])
# plt.tight_layout()
# fig.savefig(os.path.join(figures_dir, 'resilience_F_value_2024.png'), dpi=300, bbox_inches='tight')
# print("✓ Saved: resilience_F_value_2024.png")
# plt.close()

# # Figure 4: F_ton_2050
# fig, ax = plt.subplots(figsize=(10, 7))
# ax.plot(df_grouped['disruption_percentage'] * 100, df_grouped['F_ton_2050_mean'], 
#         'o-', linewidth=2.5, markersize=8, color='#06A77D')
# if num_mc_runs > 1:
#     ax.fill_between(df_grouped['disruption_percentage'] * 100,
#                      df_grouped['F_ton_2050_mean'] - df_grouped['F_ton_2050_ci'],
#                      df_grouped['F_ton_2050_mean'] + df_grouped['F_ton_2050_ci'],
#                      alpha=0.3, color='#06A77D')
# ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=13, fontweight='bold')
# ax.set_ylabel('Network Functionality F(Gd)', fontsize=13, fontweight='bold')
# ax.set_title('Network Functionality vs Link Disruption\nWeighted by Ton-Hours (2050)', fontsize=14, fontweight='bold')
# ax.grid(True, alpha=0.3)
# ax.set_ylim([0, 1.05])
# plt.tight_layout()
# fig.savefig(os.path.join(figures_dir, 'resilience_F_ton_2050.png'), dpi=300, bbox_inches='tight')
# print("✓ Saved: resilience_F_ton_2050.png")
# plt.close()

# # Figure 5: F_value_2050
# fig, ax = plt.subplots(figsize=(10, 7))
# ax.plot(df_grouped['disruption_percentage'] * 100, df_grouped['F_value_2050_mean'], 
#         'o-', linewidth=2.5, markersize=8, color='#C73E1D')
# if num_mc_runs > 1:
#     ax.fill_between(df_grouped['disruption_percentage'] * 100,
#                      df_grouped['F_value_2050_mean'] - df_grouped['F_value_2050_ci'],
#                      df_grouped['F_value_2050_mean'] + df_grouped['F_value_2050_ci'],
#                      alpha=0.3, color='#C73E1D')
# ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=13, fontweight='bold')
# ax.set_ylabel('Network Functionality F(Gd)', fontsize=13, fontweight='bold')
# ax.set_title('Network Functionality vs Link Disruption\nWeighted by Value-Hours (2050)', fontsize=14, fontweight='bold')
# ax.grid(True, alpha=0.3)
# ax.set_ylim([0, 1.05])
# plt.tight_layout()
# fig.savefig(os.path.join(figures_dir, 'resilience_F_value_2050.png'), dpi=300, bbox_inches='tight')
# print("✓ Saved: resilience_F_value_2050.png")
# plt.close()

# print("\n" + "=" * 80)
# print("RESILIENCE ANALYSIS COMPLETE!")
# print("=" * 80)
# print(f"Outputs: {output_dir}")
# print("=" * 80)
# %%
# %%
#!========================================================================
#! QUICK FIX: Add FID column and path_link_fids without re-running baseline
#! This adds the missing columns to your existing files
#!========================================================================

import geopandas as gpd
import pandas as pd
import networkx as nx
import os
import time

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

link_flows_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_link_flows_daily_ALL_LINKS.gpkg"
)

baseline_combined_csv = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_paths_daily_COMBINED.csv"
)

print("=" * 80)
print("QUICK FIX: Adding FID and path_link_fids columns")
print("=" * 80)

# ==================================================
# STEP 1: Add FID column to link flows
# ==================================================
print("\nStep 1: Adding FID column to link flows...")

gdf_links = gpd.read_file(link_flows_path)
print(f"✓ Read link flows: {len(gdf_links):,} links")

# Check if FID already exists
if 'FID' in gdf_links.columns:
    print("  ⚠ FID column already exists!")
else:
    # Add FID column (just use the index)
    gdf_links['FID'] = gdf_links.index
    
    # Save back
    gdf_links.to_file(link_flows_path, layer="rail_link_flows", driver="GPKG")
    print(f"  ✓ Added FID column and saved to: {link_flows_path}")

# ==================================================
# STEP 2: Add path_link_fids to baseline CSV
# ==================================================
print("\nStep 2: Adding path_link_fids to baseline CSV...")

df_baseline = pd.read_csv(baseline_combined_csv)
print(f"✓ Read baseline OD paths: {len(df_baseline):,}")

# Check if path_link_fids already exists
if 'path_link_fids' in df_baseline.columns:
    print("  ⚠ path_link_fids column already exists!")
    print("\n✓ Both columns already exist - you're good to go!")
else:
    print("  Building network graph to find paths...")
    
    # Read network
    gdf_edges = gpd.read_file(rail_graph_path, layer="edges")
    print(f"  ✓ Read edges: {len(gdf_edges):,}")
    
    # Build graph
    G = nx.Graph()
    edge_key_to_fid = {}
    
    for idx, e in gdf_edges.iterrows():
        u = e["FRFRANODE"]
        v = e["TOFRANODE"]
        
        if pd.isna(u) or pd.isna(v):
            continue
        
        length_miles = e["LENGTH"] / 1609.344
        G.add_edge(u, v, weight=length_miles)
        
        edge_key = tuple(sorted((u, v)))
        edge_key_to_fid[edge_key] = idx  # FID is the row index
    
    print(f"  ✓ Graph built: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    
    # Group by origin for efficiency
    print("  Finding paths and tracking link FIDs...")
    od_groups = df_baseline.groupby('origin_franodeid')
    
    path_link_fids_list = []
    num_origins = len(od_groups)
    
    for i, (origin, group) in enumerate(od_groups, start=1):
        if i % 100 == 0:
            print(f"    Progress: {i:,}/{num_origins:,} origins ({i/num_origins*100:.1f}%)")
        
        if origin not in G:
            # Origin not in graph - no paths
            for _ in range(len(group)):
                path_link_fids_list.append("")
            continue
        
        try:
            lengths, paths = nx.single_source_dijkstra(G, origin, weight="weight")
        except:
            for _ in range(len(group)):
                path_link_fids_list.append("")
            continue
        
        for idx, row in group.iterrows():
            dest = row['destination_franodeid']
            
            if dest not in paths:
                path_link_fids_list.append("")
            else:
                node_path = paths[dest]
                
                # Collect FIDs
                fids = []
                for k in range(len(node_path) - 1):
                    edge_key = tuple(sorted((node_path[k], node_path[k + 1])))
                    if edge_key in edge_key_to_fid:
                        fids.append(edge_key_to_fid[edge_key])
                
                path_link_fids_list.append(",".join(str(fid) for fid in fids))
    
    # Add column to dataframe
    df_baseline['path_link_fids'] = path_link_fids_list
    
    # Save
    print(f"\n  Saving updated baseline CSV...")
    df_baseline.to_csv(baseline_combined_csv, index=False)
    print(f"  ✓ Saved to: {baseline_combined_csv}")

print("\n" + "=" * 80)
print("QUICK FIX COMPLETE!")
print("=" * 80)
print("\nYou can now run:")
print("  1. Step 2 (5a_disruption_analysis_rerouting_only.py)")
print("  2. Step 3 (5b_resilience_analysis_metrics_and_plots.py)")
print("=" * 80)

# %%
#!========================================================================
#! STEP 2: OPTIMIZED DISRUPTION ANALYSIS WITH PROGRESS TRACKING
#! Re-routes affected OD pairs and saves disrupted network results
#! Does NOT calculate resilience metrics (that's Step 3)
#!========================================================================

import geopandas as gpd
import pandas as pd
import networkx as nx
from collections import defaultdict
import os
import time
import gc
import numpy as np

# ==================================================
# CONFIGURATION
# ==================================================
SPEED_MPH = 49.0
HOURS_PER_DAY = 24.0

# Disruption fractions (0.1% to 1.0% in 0.1% increments)
DISRUPTION_FRACTIONS = [0.001 * i for i in range(1, 11)]  # [0.001, 0.002, ..., 0.010]

# Disruption scenarios (which metric to use for selecting top links)
DISRUPTION_SCENARIOS = [
    {'name': 'Tons_2024', 'column': 'tons_2024_day'},
    {'name': 'Value_2024', 'column': 'value_2024_day'},
    {'name': 'Tons_2050', 'column': 'tons_2050_day'},
    {'name': 'Value_2050', 'column': 'value_2050_day'}
]

# ==================================================
# PATHS
# ==================================================
base_dir = os.path.abspath(os.path.join("..", ".."))

# Baseline data
baseline_combined_csv = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_paths_daily_COMBINED.csv"
)

rail_graph_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Rail_Graph",
    "Rail_Graph_Nodes_Edges.gpkg"
)

link_flows_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_link_flows_daily_ALL_LINKS.gpkg"
)

# Output directory
disruption_base_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Disruption_Scenarios"
)

os.makedirs(disruption_base_dir, exist_ok=True)

# ==================================================
# READ BASELINE DATA
# ==================================================
print("=" * 80)
print("STEP 2: DISRUPTION ANALYSIS - RE-ROUTING ONLY")
print("=" * 80)
print(f"\nReading baseline data...")

# Read baseline OD paths
print("  Reading baseline OD paths...")
df_baseline = pd.read_csv(baseline_combined_csv)
print(f"  ✓ Baseline OD paths: {len(df_baseline):,}")

# Verify path_link_fids column exists
if 'path_link_fids' not in df_baseline.columns:
    raise ValueError("ERROR: 'path_link_fids' column not found! Please run Step 0 (quick fix) first.")

# Read rail network
print("  Reading rail network...")
gdf_edges = gpd.read_file(rail_graph_path, layer="edges")
gdf_nodes = gpd.read_file(rail_graph_path, layer="nodes")
print(f"  ✓ Edges: {len(gdf_edges):,}")
print(f"  ✓ Nodes: {len(gdf_nodes):,}")

# Read link flows (with FID column)
print("  Reading link flows...")
gdf_links = gpd.read_file(link_flows_path)
print(f"  ✓ Links: {len(gdf_links):,}")

# Verify FID column exists
if 'FID' not in gdf_links.columns:
    print("  ⚠ FID not found → using index as FID")
    gdf_links['FID'] = gdf_links.index

# Create node coordinates lookup
node_coords_lookup = {}
for idx, node in gdf_nodes.iterrows():
    node_coords_lookup[node['FRANODEID']] = (node.geometry.x, node.geometry.y)

print("\n✓ All baseline data loaded successfully")

# ==================================================
# HELPER FUNCTIONS
# ==================================================

def build_graph_from_edges(gdf_edges_subset):
    """Build NetworkX graph from edge GeoDataFrame"""
    G = nx.Graph()
    
    for idx, e in gdf_edges_subset.iterrows():
        u = e["FRFRANODE"]
        v = e["TOFRANODE"]
        
        if pd.isna(u) or pd.isna(v):
            continue
        
        length_miles = e["LENGTH"] / 1609.344
        G.add_edge(u, v, weight=length_miles)
    
    return G


def get_affected_od_pairs(df_baseline, disrupted_fids):
    """
    Identify which OD pairs use any of the disrupted links
    Returns DataFrame of affected OD pairs
    """
    disrupted_fids_set = set(disrupted_fids)
    
    def uses_disrupted_link(path_fids_str):
        if pd.isna(path_fids_str) or path_fids_str == '':
            return False
        fids = set(int(x) for x in str(path_fids_str).split(','))
        return bool(fids & disrupted_fids_set)
    
    mask = df_baseline['path_link_fids'].apply(uses_disrupted_link)
    return df_baseline[mask].copy()


def calculate_shortest_paths_for_od_pairs(G, df_od_subset, node_coords_lookup):
    """
    Calculate shortest paths for a subset of OD pairs
    Returns list of path records with same structure as baseline
    """
    paths_data = []
    
    # Group by origin for efficiency
    od_groups = df_od_subset.groupby('origin_franodeid')
    
    for origin, group in od_groups:
        if origin not in G:
            # Origin not in graph - all destinations are infeasible
            for idx, row in group.iterrows():
                path_rec = create_infeasible_record(row, node_coords_lookup)
                paths_data.append(path_rec)
            continue
        
        try:
            lengths, paths = nx.single_source_dijkstra(G, origin, weight="weight")
        except Exception as e:
            print(f"    ERROR computing paths from origin {origin}: {e}")
            for idx, row in group.iterrows():
                path_rec = create_infeasible_record(row, node_coords_lookup)
                paths_data.append(path_rec)
            continue
        
        for idx, row in group.iterrows():
            dest = row['destination_franodeid']
            
            if dest not in paths:
                # No path exists - infeasible
                path_rec = create_infeasible_record(row, node_coords_lookup)
                paths_data.append(path_rec)
            else:
                # Path exists - create record
                node_path = paths[dest]
                path_len_miles = lengths[dest]
                travel_time_hours = path_len_miles / SPEED_MPH
                travel_time_days = travel_time_hours / HOURS_PER_DAY
                
                origin_coords = node_coords_lookup.get(origin, (None, None))
                dest_coords = node_coords_lookup.get(dest, (None, None))
                
                path_rec = {
                    "origin_franodeid": row['origin_franodeid'],
                    "destination_franodeid": row['destination_franodeid'],
                    "origin_x": origin_coords[0],
                    "origin_y": origin_coords[1],
                    "destination_x": dest_coords[0],
                    "destination_y": dest_coords[1],
                    "origin_node_label": row['origin_node_label'],
                    "destination_node_label": row['destination_node_label'],
                    "origin_node_type": row['origin_node_type'],
                    "destination_node_type": row['destination_node_type'],
                    "path_length_miles": path_len_miles,
                    "travel_time_hours": travel_time_hours,
                    "travel_time_days": travel_time_days,
                    "tons_2024_day": row['tons_2024_day'],
                    "value_2024_day": row['value_2024_day'],
                    "tons_2050_day": row['tons_2050_day'],
                    "value_2050_day": row['value_2050_day'],
                    "ton_hours_2024": row['tons_2024_day'] * travel_time_hours,
                    "value_hours_2024": row['value_2024_day'] * travel_time_hours,
                    "ton_hours_2050": row['tons_2050_day'] * travel_time_hours,
                    "value_hours_2050": row['value_2050_day'] * travel_time_hours,
                    "num_edges_in_path": len(node_path) - 1,
                    "original_origin_county": row['original_origin_county'],
                    "original_dest_county": row['original_dest_county'],
                    "path_link_fids": ""
                }
                paths_data.append(path_rec)
    
    return paths_data


def create_infeasible_record(row, node_coords_lookup):
    """Create an infeasible OD record (infinite travel time)"""
    origin_coords = node_coords_lookup.get(row['origin_franodeid'], (None, None))
    dest_coords = node_coords_lookup.get(row['destination_franodeid'], (None, None))
    
    return {
        "origin_franodeid": row['origin_franodeid'],
        "destination_franodeid": row['destination_franodeid'],
        "origin_x": origin_coords[0],
        "origin_y": origin_coords[1],
        "destination_x": dest_coords[0],
        "destination_y": dest_coords[1],
        "origin_node_label": row['origin_node_label'],
        "destination_node_label": row['destination_node_label'],
        "origin_node_type": row['origin_node_type'],
        "destination_node_type": row['destination_node_type'],
        "path_length_miles": np.inf,
        "travel_time_hours": np.inf,
        "travel_time_days": np.inf,
        "tons_2024_day": row['tons_2024_day'],
        "value_2024_day": row['value_2024_day'],
        "tons_2050_day": row['tons_2050_day'],
        "value_2050_day": row['value_2050_day'],
        "ton_hours_2024": np.inf,
        "value_hours_2024": np.inf,
        "ton_hours_2050": np.inf,
        "value_hours_2050": np.inf,
        "num_edges_in_path": 0,
        "original_origin_county": row['original_origin_county'],
        "original_dest_county": row['original_dest_county'],
        "path_link_fids": ""
    }


# ==================================================
# RUN DISRUPTION SCENARIOS WITH PROGRESS TRACKING
# ==================================================

print("\n" + "=" * 80)
print("STARTING DISRUPTION ANALYSIS")
print("=" * 80)
print(f"\nConfiguration:")
print(f"  Disruption fractions: {len(DISRUPTION_FRACTIONS)} ({DISRUPTION_FRACTIONS[0]*100:.1f}% to {DISRUPTION_FRACTIONS[-1]*100:.1f}%)")
print(f"  Scenarios: {len(DISRUPTION_SCENARIOS)}")
print(f"  Total baseline OD pairs: {len(df_baseline):,}")

# Progress tracking
total_runs = len(DISRUPTION_SCENARIOS) * len(DISRUPTION_FRACTIONS)
completed_runs = 0
overall_start_time = time.time()
run_times = []

print(f"\n📊 PROGRESS TRACKING:")
print(f"   Total runs to complete: {total_runs}")
print(f"   Estimated time: 5-10 hours (depends on affected OD pairs)")
print("=" * 80)

# Run each scenario
for scenario_idx, scenario in enumerate(DISRUPTION_SCENARIOS, start=1):
    
    scenario_name = scenario['name']
    metric_column = scenario['column']
    
    print("\n" + "=" * 80)
    print(f"SCENARIO {scenario_idx}/{len(DISRUPTION_SCENARIOS)}: {scenario_name}")
    print(f"Disrupting top links by: {metric_column}")
    print("=" * 80)
    
    scenario_start_time = time.time()
    
    # Sort links by metric (descending)
    gdf_links_sorted = gdf_links.sort_values(metric_column, ascending=False).copy()
    
    # Run each disruption fraction
    for frac_idx, disruption_frac in enumerate(DISRUPTION_FRACTIONS, start=1):
        
        # ============================================
        # CHECKPOINT: Check if this run already exists
        # ============================================
        frac_dir = os.path.join(
            disruption_base_dir,
            scenario_name,
            f"Frac_{disruption_frac*100:.1f}pct"
        )
        os.makedirs(frac_dir, exist_ok=True)  # Ensure directory exists
        
        combined_csv_path = os.path.join(frac_dir, "od_paths_combined.csv")
        
        # Check if file exists and is valid (FAST METHOD - no CSV reading!)
        skip_this_run = False
        if os.path.exists(combined_csv_path):
            try:
                # Method 1: Check file size (very fast)
                file_size = os.path.getsize(combined_csv_path)
                
                # Minimum expected file size (rough estimate: ~500 bytes per row)
                min_expected_size = len(df_baseline) * 400  # Conservative estimate
                
                if file_size < min_expected_size:
                    print(f"\n  [{scenario_idx}.{frac_idx}] Disruption fraction: {disruption_frac*100:.1f}%")
                    print(f"  ⚠️  File too small ({file_size:,} bytes, expected >{min_expected_size:,}) - Re-running")
                else:
                    # Method 2: Count lines (fast, no parsing)
                    with open(combined_csv_path, 'r') as f:
                        line_count = sum(1 for _ in f)
                    
                    # Should be baseline rows + 1 header row
                    expected_lines = len(df_baseline) + 1
                    
                    if line_count == expected_lines:
                        print(f"\n  [{scenario_idx}.{frac_idx}] Disruption fraction: {disruption_frac*100:.1f}%")
                        print(f"  ✅ ALREADY COMPLETE - Skipping (validated {line_count:,} lines)")
                        skip_this_run = True
                        completed_runs += 1
                    else:
                        print(f"\n  [{scenario_idx}.{frac_idx}] Disruption fraction: {disruption_frac*100:.1f}%")
                        print(f"  ⚠️  Wrong line count ({line_count:,} lines, expected {expected_lines:,}) - Re-running")
                        
            except Exception as e:
                print(f"\n  [{scenario_idx}.{frac_idx}] Disruption fraction: {disruption_frac*100:.1f}%")
                print(f"  ⚠️  Error validating file - Re-running ({str(e)})")
        
        if skip_this_run:
            continue
        
        frac_start_time = time.time()
        
        # Calculate overall progress
        progress_pct = (completed_runs / total_runs) * 100
        
        if not skip_this_run:
            print(f"\n  [{scenario_idx}.{frac_idx}] Disruption fraction: {disruption_frac*100:.1f}%")
        print(f"  🔄 PROGRESS: Run {completed_runs + 1}/{total_runs} ({progress_pct:.1f}% complete)")
        
        # Calculate ETA if we have run time history
        if len(run_times) >= 3:
            avg_time_per_run = sum(run_times[-10:]) / len(run_times[-10:])  # Use last 10 runs
            remaining_runs = total_runs - completed_runs
            eta_seconds = avg_time_per_run * remaining_runs
            eta_hours = eta_seconds / 3600
            eta_minutes = (eta_seconds % 3600) / 60
            
            elapsed_seconds = time.time() - overall_start_time
            elapsed_hours = int(elapsed_seconds // 3600)
            elapsed_minutes = int((elapsed_seconds % 3600) // 60)
            
            print(f"  ⏱️  Elapsed: {elapsed_hours}h {elapsed_minutes}m | ETA: {int(eta_hours)}h {int(eta_minutes)}m remaining")
        
        # Select top X% of links to disrupt
        num_links_to_disrupt = max(1, int(len(gdf_links_sorted) * disruption_frac))
        disrupted_links = gdf_links_sorted.head(num_links_to_disrupt)
        disrupted_fids = disrupted_links['FID'].tolist()
        
        print(f"    Disrupting {num_links_to_disrupt:,} links (top {disruption_frac*100:.1f}% by {metric_column})")
        
        # Create disrupted network (remove disrupted links)
        gdf_edges_disrupted = gdf_edges[~gdf_edges.index.isin(disrupted_fids)].copy()
        
        print(f"    Building disrupted graph ({len(gdf_edges_disrupted):,} edges)...")
        G_disrupted = build_graph_from_edges(gdf_edges_disrupted)
        
        # Identify affected OD pairs (those using disrupted links)
        print(f"    Identifying affected OD pairs...")
        df_affected = get_affected_od_pairs(df_baseline, disrupted_fids)
        num_affected = len(df_affected)
        
        print(f"    Affected OD pairs: {num_affected:,} ({num_affected/len(df_baseline)*100:.2f}%)")
        
        if num_affected == 0:
            print(f"    ⚠ No OD pairs affected - using baseline results")
            df_disrupted_combined = df_baseline.copy()
        else:
            # Re-route only affected OD pairs
            print(f"    Re-routing {num_affected:,} affected OD pairs...")
            reroute_start = time.time()
            
            affected_paths = calculate_shortest_paths_for_od_pairs(
                G_disrupted, df_affected, node_coords_lookup
            )
            
            df_affected_rerouted = pd.DataFrame(affected_paths)
            
            print(f"    ✓ Re-routing complete ({time.time() - reroute_start:.1f}s)")
            
            # Combine with unaffected OD pairs
            df_unaffected = df_baseline[~df_baseline.index.isin(df_affected.index)].copy()
            df_disrupted_combined = pd.concat([df_unaffected, df_affected_rerouted], 
                                              ignore_index=True)
        
        # Save disrupted OD paths (COMBINED CSV ONLY - faster!)
        # Directory already created in checkpoint section above
        
        # Save combined CSV only
        df_disrupted_combined.to_csv(combined_csv_path, index=False)
        
        run_time = time.time() - frac_start_time
        run_times.append(run_time)
        completed_runs += 1
        
        print(f"    ✓ Saved: {combined_csv_path}")
        print(f"    ✅ Run complete in {run_time:.1f}s")
        
        # Clean up
        del df_disrupted_combined, G_disrupted, gdf_edges_disrupted
        if num_affected > 0:
            del df_affected, df_affected_rerouted, affected_paths
        gc.collect()
    
    scenario_time = time.time() - scenario_start_time
    print(f"\n  ✅ Scenario {scenario_name} complete in {scenario_time/60:.1f} minutes")
    print(f"  📈 Overall progress: {completed_runs}/{total_runs} runs ({completed_runs/total_runs*100:.1f}%)")

# ==================================================
# FINAL SUMMARY
# ==================================================
total_elapsed = time.time() - overall_start_time
total_hours = int(total_elapsed // 3600)
total_minutes = int((total_elapsed % 3600) // 60)

# Count actual runs vs skipped
actual_runs = len(run_times)
skipped_runs = completed_runs - actual_runs

print("\n" + "=" * 80)
print("STEP 2: DISRUPTION ANALYSIS COMPLETE! 🎉")
print("=" * 80)
print(f"\n⏱️  Total runtime: {total_hours}h {total_minutes}m")
print(f"📊 Total scenarios: {completed_runs}/{total_runs}")
if skipped_runs > 0:
    print(f"✅ Already complete (skipped): {skipped_runs}")
    print(f"🔄 Newly computed: {actual_runs}")
if actual_runs > 0:
    print(f"⚡ Average time per new run: {sum(run_times)/len(run_times):.1f}s")

print(f"""
SUMMARY:
  Scenarios completed: {len(DISRUPTION_SCENARIOS)}
  Disruption fractions: {len(DISRUPTION_FRACTIONS)}
  Total disruption runs: {completed_runs}

OUTPUT STRUCTURE:
  {disruption_base_dir}/
    ├── Tons_2024/
    │   ├── Frac_0.1pct/od_paths_combined.csv
    │   ├── Frac_0.2pct/od_paths_combined.csv
    │   └── ...
    ├── Value_2024/
    ├── Tons_2050/
    └── Value_2050/

NOTE: Individual origin files NOT saved (for speed optimization)

NEXT STEP:
  Run Step 3 to calculate resilience metrics and create resilience curves!
  python 5b_resilience_analysis_metrics_and_plots.py
""")

print("=" * 80)

# %%
#!========================================================================
#! STEP 3: RESILIENCE ANALYSIS
#! Reads disrupted OD files from Step 2 and calculates resilience metrics
#! Creates resilience curves and summary statistics
#!========================================================================

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

# ==================================================
# PATHS
# ==================================================
base_dir = os.path.abspath(os.path.join("..", ".."))

baseline_od_paths_csv = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_paths_daily_COMBINED.csv"
)

disruption_scenarios_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Disruption_Scenarios"
)

output_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Resilience_Analysis"
)

os.makedirs(output_dir, exist_ok=True)

resilience_summary_csv = os.path.join(output_dir, "resilience_summary.csv")
figures_dir = os.path.join(output_dir, "figures")
os.makedirs(figures_dir, exist_ok=True)

# ==================================================
# CONFIGURATION
# ==================================================
# Scenarios (must match Step 2)
SCENARIOS = ['Tons_2024', 'Value_2024', 'Tons_2050', 'Value_2050']

# Disruption fractions (must match Step 2)
DISRUPTION_FRACTIONS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

# ==================================================
# READ BASELINE
# ==================================================
print("=" * 80)
print("STEP 3: RESILIENCE ANALYSIS")
print("=" * 80)
print("\nFormulas Used:")
print("  - Δ(ton-hours)_k = T_disrupted × tons_k - T_baseline × tons_k")
print("  - Δ(value-hours)_k = T_disrupted × value_k - T_baseline × value_k")
print("  - f_tons_k = 1 / (1 + Δ(ton-hours)_k)  [= 0 if infeasible]")
print("  - f_value_k = 1 / (1 + Δ(value-hours)_k)  [= 0 if infeasible]")
print("  - F_tons = Σ(f_tons_k) / |K_total|")
print("  - F_value = Σ(f_value_k) / |K_total|")
print("  - Reach = |K_feasible| / |K_total|")
print("=" * 80)

print("\nReading baseline...")
df_baseline = pd.read_csv(baseline_od_paths_csv)
print(f"✓ Baseline OD paths: {len(df_baseline):,}")

# Create baseline lookup for comparison
baseline_lookup = {}
for _, row in df_baseline.iterrows():
    key = (row['origin_franodeid'], row['destination_franodeid'])
    baseline_lookup[key] = {
        'travel_time_hours': row['travel_time_hours'],
        'ton_hours_2024': row['ton_hours_2024'],
        'value_hours_2024': row['value_hours_2024'],
        'ton_hours_2050': row['ton_hours_2050'],
        'value_hours_2050': row['value_hours_2050'],
        'tons_2024_day': row['tons_2024_day'],
        'value_2024_day': row['value_2024_day'],
        'tons_2050_day': row['tons_2050_day'],
        'value_2050_day': row['value_2050_day']
    }

num_total_ods = len(df_baseline)
print(f"✓ Total OD pairs (|K|): {num_total_ods:,}")

# ==================================================
# ANALYZE DISRUPTION SCENARIOS
# ==================================================
print("\n" + "=" * 80)
print("ANALYZING DISRUPTION SCENARIOS")
print("=" * 80)

all_results = []

for scenario_name in SCENARIOS:
    print(f"\n{'='*80}")
    print(f"SCENARIO: {scenario_name}")
    print(f"  (Links disrupted based on highest {scenario_name})")
    print(f"{'='*80}")
    
    for disruption_pct in DISRUPTION_FRACTIONS:
        
        # Path to disrupted OD file
        frac_dir = os.path.join(
            disruption_scenarios_dir,
            scenario_name,
            f"Frac_{disruption_pct}pct"
        )
        
        od_paths_file = os.path.join(frac_dir, "od_paths_combined.csv")
        
        if not os.path.exists(od_paths_file):
            print(f"  ⚠ File not found: {od_paths_file}")
            print(f"     Run Step 2 first to generate disrupted OD files!")
            continue
        
        print(f"\n  [{scenario_name} @ {disruption_pct}%] Analyzing...")
        
        # Read disrupted OD paths
        df_disrupted = pd.read_csv(od_paths_file)
        
        if len(df_disrupted) != num_total_ods:
            print(f"    ⚠ WARNING: Disrupted has {len(df_disrupted):,} ODs, expected {num_total_ods:,}")
        
        # Initialize counters
        num_unaffected = 0
        num_delayed = 0
        num_infeasible = 0
        
        # Sum of f_k values (for network functionality)
        sum_f_tons_2024 = 0.0
        sum_f_value_2024 = 0.0
        sum_f_tons_2050 = 0.0
        sum_f_value_2050 = 0.0
        
        # Tonnage/value breakdown
        unaffected_tons_2024 = 0.0
        delayed_tons_2024 = 0.0
        infeasible_tons_2024 = 0.0
        
        unaffected_value_2024 = 0.0
        delayed_value_2024 = 0.0
        infeasible_value_2024 = 0.0
        
        # Analyze each OD pair
        for _, row in df_disrupted.iterrows():
            key = (row['origin_franodeid'], row['destination_franodeid'])
            
            if key not in baseline_lookup:
                print(f"      ⚠ OD pair not in baseline: {key}")
                continue
            
            baseline = baseline_lookup[key]
            
            # Get tons and values (from baseline - these don't change)
            tons_2024 = baseline['tons_2024_day']
            value_2024 = baseline['value_2024_day']
            tons_2050 = baseline['tons_2050_day']
            value_2050 = baseline['value_2050_day']
            
            # Get baseline ton-hours and value-hours
            ton_hours_baseline_2024 = baseline['ton_hours_2024']
            value_hours_baseline_2024 = baseline['value_hours_2024']
            ton_hours_baseline_2050 = baseline['ton_hours_2050']
            value_hours_baseline_2050 = baseline['value_hours_2050']
            
            # Get disrupted ton-hours and value-hours
            ton_hours_disrupted_2024 = row['ton_hours_2024']
            value_hours_disrupted_2024 = row['value_hours_2024']
            ton_hours_disrupted_2050 = row['ton_hours_2050']
            value_hours_disrupted_2050 = row['value_hours_2050']
            
            # ============================================
            # CHECK IF INFEASIBLE (travel time = infinity)
            # ============================================
            if np.isinf(ton_hours_disrupted_2024):
                # INFEASIBLE PATH - no route exists
                num_infeasible += 1
                infeasible_tons_2024 += tons_2024
                infeasible_value_2024 += value_2024
                
                # f_k = 0 for infeasible OD pairs (Δ = ∞, so f = 1/(1+∞) = 0)
                f_tons_2024 = 0.0
                f_value_2024 = 0.0
                f_tons_2050 = 0.0
                f_value_2050 = 0.0
                
            else:
                # FEASIBLE PATH - calculate functionality
                
                # ============================================
                # CALCULATE Δ(ton-hours) and Δ(value-hours)
                # ============================================
                delta_ton_hours_2024 = ton_hours_disrupted_2024 - ton_hours_baseline_2024
                delta_value_hours_2024 = value_hours_disrupted_2024 - value_hours_baseline_2024
                delta_ton_hours_2050 = ton_hours_disrupted_2050 - ton_hours_baseline_2050
                delta_value_hours_2050 = value_hours_disrupted_2050 - value_hours_baseline_2050
                
                # ============================================
                # CALCULATE f_k = 1 / (1 + Δ)
                # ============================================
                # If Δ is negative (shorter path - rare), cap f_k at 1.0
                if delta_ton_hours_2024 < 0:
                    f_tons_2024 = 1.0
                else:
                    f_tons_2024 = 1.0 / (1.0 + delta_ton_hours_2024)
                
                if delta_value_hours_2024 < 0:
                    f_value_2024 = 1.0
                else:
                    f_value_2024 = 1.0 / (1.0 + delta_value_hours_2024)
                
                if delta_ton_hours_2050 < 0:
                    f_tons_2050 = 1.0
                else:
                    f_tons_2050 = 1.0 / (1.0 + delta_ton_hours_2050)
                
                if delta_value_hours_2050 < 0:
                    f_value_2050 = 1.0
                else:
                    f_value_2050 = 1.0 / (1.0 + delta_value_hours_2050)
                
                # ============================================
                # CLASSIFY OD PAIR
                # ============================================
                # Unaffected: travel time essentially unchanged (< 0.001 hour difference)
                # Delayed: travel time increased
                if abs(delta_ton_hours_2024) < 0.001:  # Essentially zero change
                    num_unaffected += 1
                    unaffected_tons_2024 += tons_2024
                    unaffected_value_2024 += value_2024
                else:
                    num_delayed += 1
                    delayed_tons_2024 += tons_2024
                    delayed_value_2024 += value_2024
            
            # ============================================
            # ACCUMULATE f_k VALUES
            # ============================================
            sum_f_tons_2024 += f_tons_2024
            sum_f_value_2024 += f_value_2024
            sum_f_tons_2050 += f_tons_2050
            sum_f_value_2050 += f_value_2050
        
        # ================================================
        # CALCULATE NETWORK-LEVEL METRICS
        # ================================================
        
        # Network Functionality: F = Σ(f_k) / |K|
        F_tons_2024 = sum_f_tons_2024 / num_total_ods
        F_value_2024 = sum_f_value_2024 / num_total_ods
        F_tons_2050 = sum_f_tons_2050 / num_total_ods
        F_value_2050 = sum_f_value_2050 / num_total_ods
        
        # Reachability: Reach = |K_feasible| / |K|
        num_feasible = num_unaffected + num_delayed
        reachability = num_feasible / num_total_ods
        
        # Total tonnage/value
        total_tons_2024 = unaffected_tons_2024 + delayed_tons_2024 + infeasible_tons_2024
        total_value_2024 = unaffected_value_2024 + delayed_value_2024 + infeasible_value_2024
        
        # ================================================
        # PRINT RESULTS
        # ================================================
        print(f"    OD Classification:")
        print(f"      Unaffected : {num_unaffected:7,} ({num_unaffected/num_total_ods*100:5.2f}%)")
        print(f"      Delayed    : {num_delayed:7,} ({num_delayed/num_total_ods*100:5.2f}%)")
        print(f"      Infeasible : {num_infeasible:7,} ({num_infeasible/num_total_ods*100:5.2f}%)")
        print(f"      ─────────────────────────────")
        print(f"      Total      : {num_total_ods:7,}")
        
        print(f"\n    Network Metrics:")
        print(f"      Reachability     : {reachability:.4f} ({reachability*100:.2f}%)")
        print(f"      F_tons_2024      : {F_tons_2024:.4f}")
        print(f"      F_value_2024     : {F_value_2024:.4f}")
        print(f"      F_tons_2050      : {F_tons_2050:.4f}")
        print(f"      F_value_2050     : {F_value_2050:.4f}")
        
        print(f"\n    Tonnage Breakdown (2024):")
        print(f"      Unaffected : {unaffected_tons_2024:12,.0f} tons/day ({unaffected_tons_2024/total_tons_2024*100:5.2f}%)")
        print(f"      Delayed    : {delayed_tons_2024:12,.0f} tons/day ({delayed_tons_2024/total_tons_2024*100:5.2f}%)")
        print(f"      Infeasible : {infeasible_tons_2024:12,.0f} tons/day ({infeasible_tons_2024/total_tons_2024*100:5.2f}%)")
        
        # ================================================
        # STORE RESULTS
        # ================================================
        result_record = {
            'scenario_name': scenario_name,
            'disruption_percentage': disruption_pct,
            'num_total_ods': num_total_ods,
            'num_unaffected': num_unaffected,
            'num_delayed': num_delayed,
            'num_infeasible': num_infeasible,
            'num_feasible': num_feasible,
            'pct_unaffected': num_unaffected / num_total_ods * 100,
            'pct_delayed': num_delayed / num_total_ods * 100,
            'pct_infeasible': num_infeasible / num_total_ods * 100,
            'pct_feasible': num_feasible / num_total_ods * 100,
            'reachability': reachability,
            'F_tons_2024': F_tons_2024,
            'F_value_2024': F_value_2024,
            'F_tons_2050': F_tons_2050,
            'F_value_2050': F_value_2050,
            'unaffected_tons_2024': unaffected_tons_2024,
            'delayed_tons_2024': delayed_tons_2024,
            'infeasible_tons_2024': infeasible_tons_2024,
            'total_tons_2024': total_tons_2024,
            'unaffected_value_2024': unaffected_value_2024,
            'delayed_value_2024': delayed_value_2024,
            'infeasible_value_2024': infeasible_value_2024,
            'total_value_2024': total_value_2024
        }
        
        all_results.append(result_record)

# ================================================
# SAVE RESULTS
# ================================================
print("\n" + "=" * 80)
print("SAVING RESULTS")
print("=" * 80)

df_results = pd.DataFrame(all_results)
df_results.to_csv(resilience_summary_csv, index=False)
print(f"✓ Saved: {resilience_summary_csv}")
print(f"  Rows: {len(df_results)}")
print(f"  Columns: {len(df_results.columns)}")

# ================================================
# CREATE RESILIENCE CURVES
# ================================================
print("\n" + "=" * 80)
print("CREATING RESILIENCE CURVES")
print("=" * 80)

sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100

# Color palette for scenarios
colors = {
    'Tons_2024': '#2E86AB',
    'Value_2024': '#A23B72',
    'Tons_2050': '#F18F01',
    'Value_2050': '#06A77D'
}

# ================================================
# FIGURE 1: REACHABILITY BY SCENARIO
# ================================================
fig, ax = plt.subplots(figsize=(12, 8))

for scenario_name in SCENARIOS:
    df_scenario = df_results[df_results['scenario_name'] == scenario_name].sort_values('disruption_percentage')
    
    ax.plot(df_scenario['disruption_percentage'], 
            df_scenario['reachability'], 
            marker='o', 
            label=scenario_name,
            linewidth=2.5,
            markersize=8,
            color=colors[scenario_name])

ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=14, fontweight='bold')
ax.set_ylabel('Reachability (Fraction of Feasible OD Pairs)', fontsize=14, fontweight='bold')
ax.set_title('Network Reachability vs Link Disruption\n(Targeted Disruption by Scenario)', 
             fontsize=16, fontweight='bold', pad=20)
ax.legend(fontsize=12, loc='best')
ax.grid(True, alpha=0.3)
ax.set_ylim([0, 1.05])
ax.set_xlim([0, max(DISRUPTION_FRACTIONS) + 0.05])

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'resilience_reachability_all_scenarios.png'), 
            dpi=300, bbox_inches='tight')
print("✓ Saved: resilience_reachability_all_scenarios.png")
plt.close()

# ================================================
# FIGURE 2: NETWORK FUNCTIONALITY - 2024 TONS
# ================================================
fig, ax = plt.subplots(figsize=(12, 8))

for scenario_name in SCENARIOS:
    df_scenario = df_results[df_results['scenario_name'] == scenario_name].sort_values('disruption_percentage')
    
    ax.plot(df_scenario['disruption_percentage'], 
            df_scenario['F_tons_2024'], 
            marker='o', 
            label=scenario_name,
            linewidth=2.5,
            markersize=8,
            color=colors[scenario_name])

ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=14, fontweight='bold')
ax.set_ylabel('Network Functionality F(Gd)', fontsize=14, fontweight='bold')
ax.set_title('Network Functionality vs Link Disruption\nWeighted by Ton-Hours (2024)', 
             fontsize=16, fontweight='bold', pad=20)
ax.legend(fontsize=12, loc='best')
ax.grid(True, alpha=0.3)
ax.set_ylim([0, 1.05])
ax.set_xlim([0, max(DISRUPTION_FRACTIONS) + 0.05])

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'resilience_F_tons_2024_all_scenarios.png'), 
            dpi=300, bbox_inches='tight')
print("✓ Saved: resilience_F_tons_2024_all_scenarios.png")
plt.close()

# ================================================
# FIGURE 3: NETWORK FUNCTIONALITY - 2024 VALUE
# ================================================
fig, ax = plt.subplots(figsize=(12, 8))

for scenario_name in SCENARIOS:
    df_scenario = df_results[df_results['scenario_name'] == scenario_name].sort_values('disruption_percentage')
    
    ax.plot(df_scenario['disruption_percentage'], 
            df_scenario['F_value_2024'], 
            marker='o', 
            label=scenario_name,
            linewidth=2.5,
            markersize=8,
            color=colors[scenario_name])

ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=14, fontweight='bold')
ax.set_ylabel('Network Functionality F(Gd)', fontsize=14, fontweight='bold')
ax.set_title('Network Functionality vs Link Disruption\nWeighted by Value-Hours (2024)', 
             fontsize=16, fontweight='bold', pad=20)
ax.legend(fontsize=12, loc='best')
ax.grid(True, alpha=0.3)
ax.set_ylim([0, 1.05])
ax.set_xlim([0, max(DISRUPTION_FRACTIONS) + 0.05])

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'resilience_F_value_2024_all_scenarios.png'), 
            dpi=300, bbox_inches='tight')
print("✓ Saved: resilience_F_value_2024_all_scenarios.png")
plt.close()

# ================================================
# FIGURE 4: NETWORK FUNCTIONALITY - 2050 TONS
# ================================================
fig, ax = plt.subplots(figsize=(12, 8))

for scenario_name in SCENARIOS:
    df_scenario = df_results[df_results['scenario_name'] == scenario_name].sort_values('disruption_percentage')
    
    ax.plot(df_scenario['disruption_percentage'], 
            df_scenario['F_tons_2050'], 
            marker='o', 
            label=scenario_name,
            linewidth=2.5,
            markersize=8,
            color=colors[scenario_name])

ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=14, fontweight='bold')
ax.set_ylabel('Network Functionality F(Gd)', fontsize=14, fontweight='bold')
ax.set_title('Network Functionality vs Link Disruption\nWeighted by Ton-Hours (2050)', 
             fontsize=16, fontweight='bold', pad=20)
ax.legend(fontsize=12, loc='best')
ax.grid(True, alpha=0.3)
ax.set_ylim([0, 1.05])
ax.set_xlim([0, max(DISRUPTION_FRACTIONS) + 0.05])

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'resilience_F_tons_2050_all_scenarios.png'), 
            dpi=300, bbox_inches='tight')
print("✓ Saved: resilience_F_tons_2050_all_scenarios.png")
plt.close()

# ================================================
# FIGURE 5: NETWORK FUNCTIONALITY - 2050 VALUE
# ================================================
fig, ax = plt.subplots(figsize=(12, 8))

for scenario_name in SCENARIOS:
    df_scenario = df_results[df_results['scenario_name'] == scenario_name].sort_values('disruption_percentage')
    
    ax.plot(df_scenario['disruption_percentage'], 
            df_scenario['F_value_2050'], 
            marker='o', 
            label=scenario_name,
            linewidth=2.5,
            markersize=8,
            color=colors[scenario_name])

ax.set_xlabel('Fraction of Links Disrupted (%)', fontsize=14, fontweight='bold')
ax.set_ylabel('Network Functionality F(Gd)', fontsize=14, fontweight='bold')
ax.set_title('Network Functionality vs Link Disruption\nWeighted by Value-Hours (2050)', 
             fontsize=16, fontweight='bold', pad=20)
ax.legend(fontsize=12, loc='best')
ax.grid(True, alpha=0.3)
ax.set_ylim([0, 1.05])
ax.set_xlim([0, max(DISRUPTION_FRACTIONS) + 0.05])

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'resilience_F_value_2050_all_scenarios.png'), 
            dpi=300, bbox_inches='tight')
print("✓ Saved: resilience_F_value_2050_all_scenarios.png")
plt.close()

# ================================================
# FIGURE 6: OD CLASSIFICATION STACKED AREA
# ================================================
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
axes = axes.flatten()

for idx, scenario_name in enumerate(SCENARIOS):
    ax = axes[idx]
    df_scenario = df_results[df_results['scenario_name'] == scenario_name].sort_values('disruption_percentage')
    
    ax.fill_between(df_scenario['disruption_percentage'], 
                     0, 
                     df_scenario['pct_unaffected'],
                     label='Unaffected', 
                     color='#90EE90', 
                     alpha=0.7)
    
    ax.fill_between(df_scenario['disruption_percentage'], 
                     df_scenario['pct_unaffected'], 
                     df_scenario['pct_unaffected'] + df_scenario['pct_delayed'],
                     label='Delayed', 
                     color='#FFD700', 
                     alpha=0.7)
    
    ax.fill_between(df_scenario['disruption_percentage'], 
                     df_scenario['pct_unaffected'] + df_scenario['pct_delayed'],
                     100,
                     label='Infeasible', 
                     color='#FF6B6B', 
                     alpha=0.7)
    
    ax.set_xlabel('Disruption (%)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Percentage of OD Pairs', fontsize=12, fontweight='bold')
    ax.set_title(f'{scenario_name}', fontsize=13, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 105])
    ax.set_xlim([0, max(DISRUPTION_FRACTIONS) + 0.05])

plt.suptitle('OD Pair Classification by Disruption Scenario', 
             fontsize=16, fontweight='bold', y=0.995)
plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'od_classification_stacked.png'), 
            dpi=300, bbox_inches='tight')
print("✓ Saved: od_classification_stacked.png")
plt.close()

# ================================================
# FINAL SUMMARY
# ================================================
print("\n" + "=" * 80)
print("STEP 3: RESILIENCE ANALYSIS COMPLETE!")
print("=" * 80)

print(f"""
OUTPUTS CREATED:

1. Summary CSV:
   {resilience_summary_csv}
   - Contains all metrics for each scenario × disruption level
   - {len(df_results)} rows ({len(SCENARIOS)} scenarios × {len(DISRUPTION_FRACTIONS)} disruption levels)

2. Resilience Curves:
   {figures_dir}/
   - resilience_reachability_all_scenarios.png
   - resilience_F_tons_2024_all_scenarios.png
   - resilience_F_value_2024_all_scenarios.png
   - resilience_F_tons_2050_all_scenarios.png
   - resilience_F_value_2050_all_scenarios.png
   - od_classification_stacked.png

FORMULAS USED:
  Δ(ton-hours)_k = T_disrupted × tons - T_baseline × tons
  f_k = 1 / (1 + Δ)  [0 if infeasible]
  F = Σ(f_k) / |K_total|
  Reach = |K_feasible| / |K_total|

Ready for analysis and publication! 🎯
""")

print("=" * 80)

# %%
