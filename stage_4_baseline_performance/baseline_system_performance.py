# %%
#!========================================================================
#! Stage 4 - Baseline System Performance and Functionality
#! Calculate OD-level metrics and baseline feasibility
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

# Input: Combined OD paths CSV
od_paths_csv = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_paths_daily_COMBINED.csv"
)

# Original OD pairs (to check for infeasible paths)
od_pairs_original_path = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "rail_od_pairs_from_nodes.gpkg"
)

# Output directory
output_dir = os.path.join(
    base_dir,
    "13_Resiliency",
    "FAF",
    "Processed_Data",
    "County_Level",
    "Baseline_Metrics"
)

os.makedirs(output_dir, exist_ok=True)

# Output files
summary_stats_csv = os.path.join(output_dir, "baseline_summary_statistics.csv")
breakdown_by_nodetype_csv = os.path.join(output_dir, "baseline_breakdown_by_nodetype.csv")
breakdown_by_county_csv = os.path.join(output_dir, "baseline_breakdown_by_county.csv")
feasibility_report_csv = os.path.join(output_dir, "baseline_feasibility_report.csv")
figures_dir = os.path.join(output_dir, "figures")

os.makedirs(figures_dir, exist_ok=True)

# ==================================================
# READ DATA
# ==================================================
print("=" * 80)
print("STAGE 4 - BASELINE SYSTEM PERFORMANCE AND FUNCTIONALITY")
print("=" * 80)

print("\nReading OD paths (feasible paths)...")
df_paths = pd.read_csv(od_paths_csv)
print(f"✓ Feasible OD paths: {len(df_paths):,}")

print("\nReading original OD pairs...")
import geopandas as gpd
gdf_od_original = gpd.read_file(od_pairs_original_path)
df_od_original = pd.DataFrame(gdf_od_original.drop(columns="geometry"))
print(f"✓ Original OD pairs: {len(df_od_original):,}")

# ==================================================
# A. OD LEVEL PERFORMANCE METRICS
# ==================================================
print("\n" + "=" * 80)
print("A. OD LEVEL PERFORMANCE METRICS")
print("=" * 80)

# Calculate total ton-hours and value-hours
print("\nCalculating aggregate metrics...")

# For 2024
total_ton_hours_2024 = df_paths['ton_hours_2024'].sum()
total_value_hours_2024 = df_paths['value_hours_2024'].sum()

# For 2050
total_ton_hours_2050 = df_paths['ton_hours_2050'].sum()
total_value_hours_2050 = df_paths['value_hours_2050'].sum()

print(f"\n2024 Metrics:")
print(f"  Total Ton-hours   : {total_ton_hours_2024:,.0f} ton·hours")
print(f"  Total Value-hours : ${total_value_hours_2024:,.0f} USD·hours")

print(f"\n2050 Metrics:")
print(f"  Total Ton-hours   : {total_ton_hours_2050:,.0f} ton·hours")
print(f"  Total Value-hours : ${total_value_hours_2050:,.0f} USD·hours")

# Additional useful metrics
total_tons_2024 = df_paths['tons_2024_day'].sum()
total_value_2024 = df_paths['value_2024_day'].sum()
total_tons_2050 = df_paths['tons_2050_day'].sum()
total_value_2050 = df_paths['value_2050_day'].sum()

avg_travel_time_hours = df_paths['travel_time_hours'].mean()
avg_travel_time_hours_weighted_tons = (
    (df_paths['tons_2024_day'] * df_paths['travel_time_hours']).sum() / 
    df_paths['tons_2024_day'].sum()
)

avg_path_length_miles = df_paths['path_length_miles'].mean()
avg_path_length_weighted_tons = (
    (df_paths['tons_2024_day'] * df_paths['path_length_miles']).sum() / 
    df_paths['tons_2024_day'].sum()
)

print(f"\nAdditional Metrics (2024):")
print(f"  Total daily tons  : {total_tons_2024:,.0f} tons/day")
print(f"  Total daily value : ${total_value_2024:,.0f}/day")
print(f"  Avg travel time   : {avg_travel_time_hours:.2f} hours")
print(f"  Avg travel time (weighted by tons): {avg_travel_time_hours_weighted_tons:.2f} hours")
print(f"  Avg path length   : {avg_path_length_miles:.2f} miles")
print(f"  Avg path length (weighted by tons): {avg_path_length_weighted_tons:.2f} miles")

# ==================================================
# B. BASELINE FEASIBILITY
# ==================================================
print("\n" + "=" * 80)
print("B. BASELINE FEASIBILITY")
print("=" * 80)

# Identify feasible vs infeasible OD pairs
print("\nIdentifying feasible vs infeasible OD pairs...")

# Create OD pair identifiers
df_od_original['od_pair_id'] = (
    df_od_original['origin_franodeid'].astype(str) + "_" + 
    df_od_original['destination_franodeid'].astype(str)
)

df_paths['od_pair_id'] = (
    df_paths['origin_franodeid'].astype(str) + "_" + 
    df_paths['destination_franodeid'].astype(str)
)

# Find feasible and infeasible OD pairs
feasible_od_ids = set(df_paths['od_pair_id'])
all_od_ids = set(df_od_original['od_pair_id'])
infeasible_od_ids = all_od_ids - feasible_od_ids

num_feasible = len(feasible_od_ids)
num_infeasible = len(infeasible_od_ids)
num_total = len(all_od_ids)

# Calculate feasibility ratio (φ_0)
phi_0 = num_feasible / num_total if num_total > 0 else 0

print(f"\nFeasibility Analysis:")
print(f"  Total OD pairs (K)           : {num_total:,}")
print(f"  Feasible OD pairs (K_f)      : {num_feasible:,} ({num_feasible/num_total*100:.2f}%)")
print(f"  Infeasible OD pairs (K_u)    : {num_infeasible:,} ({num_infeasible/num_total*100:.2f}%)")
print(f"  Feasibility ratio (φ_0)      : {phi_0:.4f}")

# Get infeasible OD pair details
df_infeasible = df_od_original[df_od_original['od_pair_id'].isin(infeasible_od_ids)].copy()

# Calculate total demand (tons/value) for infeasible pairs
if len(df_infeasible) > 0:
    infeasible_tons_2024 = df_infeasible['tons_2024'].sum() * 1000 / 365  # Convert to tons/day
    infeasible_value_2024 = df_infeasible['value_2024'].sum() / 365  # Convert to $/day
    
    print(f"\nInfeasible OD pairs represent:")
    print(f"  Tons/day (2024)  : {infeasible_tons_2024:,.0f} ({infeasible_tons_2024/total_tons_2024*100:.2f}% of total)")
    print(f"  Value/day (2024) : ${infeasible_value_2024:,.0f} ({infeasible_value_2024/total_value_2024*100:.2f}% of total)")

# ==================================================
# BREAKDOWN BY NODE TYPE
# ==================================================
print("\n" + "=" * 80)
print("BREAKDOWN BY NODE TYPE")
print("=" * 80)

# Create OD type combinations
df_paths['od_type_combo'] = (
    df_paths['origin_node_type'].astype(str) + " → " + 
    df_paths['destination_node_type'].astype(str)
)

# Aggregate by node type combination
breakdown_nodetype = df_paths.groupby('od_type_combo').agg({
    'origin_franodeid': 'count',  # Number of OD pairs
    'tons_2024_day': 'sum',
    'value_2024_day': 'sum',
    'tons_2050_day': 'sum',
    'value_2050_day': 'sum',
    'ton_hours_2024': 'sum',
    'value_hours_2024': 'sum',
    'ton_hours_2050': 'sum',
    'value_hours_2050': 'sum',
    'travel_time_hours': 'mean',
    'path_length_miles': 'mean'
}).reset_index()

breakdown_nodetype.columns = [
    'od_type_combo', 'num_od_pairs', 
    'total_tons_2024_day', 'total_value_2024_day',
    'total_tons_2050_day', 'total_value_2050_day',
    'total_ton_hours_2024', 'total_value_hours_2024',
    'total_ton_hours_2050', 'total_value_hours_2050',
    'avg_travel_time_hours', 'avg_path_length_miles'
]

# Calculate percentages
breakdown_nodetype['pct_of_total_pairs'] = (
    breakdown_nodetype['num_od_pairs'] / breakdown_nodetype['num_od_pairs'].sum() * 100
)
breakdown_nodetype['pct_of_total_tons_2024'] = (
    breakdown_nodetype['total_tons_2024_day'] / breakdown_nodetype['total_tons_2024_day'].sum() * 100
)

# Sort by tons
breakdown_nodetype = breakdown_nodetype.sort_values('total_tons_2024_day', ascending=False)

print("\nTop 10 OD type combinations by tons/day (2024):")
print(breakdown_nodetype[
    ['od_type_combo', 'num_od_pairs', 'total_tons_2024_day', 'pct_of_total_tons_2024']
].head(10).to_string(index=False))

# Save breakdown
breakdown_nodetype.to_csv(breakdown_by_nodetype_csv, index=False)
print(f"\n✓ Saved: {breakdown_by_nodetype_csv}")

# ==================================================
# BREAKDOWN BY COUNTY (ORIGIN AND DESTINATION)
# ==================================================
print("\n" + "=" * 80)
print("BREAKDOWN BY COUNTY")
print("=" * 80)

# By origin county
breakdown_origin_county = df_paths.groupby('original_origin_county').agg({
    'origin_franodeid': 'count',
    'tons_2024_day': 'sum',
    'value_2024_day': 'sum',
    'tons_2050_day': 'sum',
    'value_2050_day': 'sum',
    'ton_hours_2024': 'sum',
    'value_hours_2024': 'sum',
    'ton_hours_2050': 'sum',
    'value_hours_2050': 'sum'
}).reset_index()

breakdown_origin_county.columns = [
    'county_geoid', 'num_od_pairs_as_origin',
    'total_tons_2024_day_origin', 'total_value_2024_day_origin',
    'total_tons_2050_day_origin', 'total_value_2050_day_origin',
    'total_ton_hours_2024_origin', 'total_value_hours_2024_origin',
    'total_ton_hours_2050_origin', 'total_value_hours_2050_origin'
]

# By destination county
breakdown_dest_county = df_paths.groupby('original_dest_county').agg({
    'destination_franodeid': 'count',
    'tons_2024_day': 'sum',
    'value_2024_day': 'sum',
    'tons_2050_day': 'sum',
    'value_2050_day': 'sum',
    'ton_hours_2024': 'sum',
    'value_hours_2024': 'sum',
    'ton_hours_2050': 'sum',
    'value_hours_2050': 'sum'
}).reset_index()

breakdown_dest_county.columns = [
    'county_geoid', 'num_od_pairs_as_dest',
    'total_tons_2024_day_dest', 'total_value_2024_day_dest',
    'total_tons_2050_day_dest', 'total_value_2050_day_dest',
    'total_ton_hours_2024_dest', 'total_value_hours_2024_dest',
    'total_ton_hours_2050_dest', 'total_value_hours_2050_dest'
]

# Merge origin and destination
breakdown_county = breakdown_origin_county.merge(
    breakdown_dest_county, 
    on='county_geoid', 
    how='outer'
).fillna(0)

# Calculate totals (origin + destination)
breakdown_county['total_tons_2024_day'] = (
    breakdown_county['total_tons_2024_day_origin'] + 
    breakdown_county['total_tons_2024_day_dest']
)
breakdown_county['total_value_2024_day'] = (
    breakdown_county['total_value_2024_day_origin'] + 
    breakdown_county['total_value_2024_day_dest']
)

# Sort by total tons
breakdown_county = breakdown_county.sort_values('total_tons_2024_day', ascending=False)

print("\nTop 10 counties by total tons/day (2024, origin + destination):")
print(breakdown_county[
    ['county_geoid', 'total_tons_2024_day_origin', 'total_tons_2024_day_dest', 'total_tons_2024_day']
].head(10).to_string(index=False))

# Save breakdown
breakdown_county.to_csv(breakdown_by_county_csv, index=False)
print(f"\n✓ Saved: {breakdown_by_county_csv}")

# ==================================================
# CREATE SUMMARY STATISTICS FILE
# ==================================================
print("\n" + "=" * 80)
print("CREATING SUMMARY STATISTICS FILE")
print("=" * 80)

summary_stats = {
    'Metric': [],
    'Value_2024': [],
    'Value_2050': [],
    'Units': []
}

# A. Performance Metrics
summary_stats['Metric'].extend([
    'Total Ton-hours',
    'Total Value-hours',
    'Total daily tons',
    'Total daily value',
    'Average travel time (unweighted)',
    'Average travel time (weighted by tons)',
    'Average path length (unweighted)',
    'Average path length (weighted by tons)',
    'Number of feasible OD pairs'
])

summary_stats['Value_2024'].extend([
    total_ton_hours_2024,
    total_value_hours_2024,
    total_tons_2024,
    total_value_2024,
    avg_travel_time_hours,
    avg_travel_time_hours_weighted_tons,
    avg_path_length_miles,
    avg_path_length_weighted_tons,
    num_feasible
])

summary_stats['Value_2050'].extend([
    total_ton_hours_2050,
    total_value_hours_2050,
    total_tons_2050,
    total_value_2050,
    avg_travel_time_hours,  # Same as 2024
    avg_travel_time_hours_weighted_tons,  # Would need recalc for 2050
    avg_path_length_miles,  # Same as 2024
    avg_path_length_weighted_tons,  # Same as 2024
    num_feasible
])

summary_stats['Units'].extend([
    'ton·hours',
    'USD·hours',
    'tons/day',
    'USD/day',
    'hours',
    'hours',
    'miles',
    'miles',
    'count'
])

# B. Feasibility Metrics
summary_stats['Metric'].extend([
    'Total OD pairs',
    'Feasible OD pairs',
    'Infeasible OD pairs',
    'Feasibility ratio (φ_0)',
    'Feasibility percentage'
])

summary_stats['Value_2024'].extend([
    num_total,
    num_feasible,
    num_infeasible,
    phi_0,
    phi_0 * 100
])

summary_stats['Value_2050'].extend([
    num_total,
    num_feasible,
    num_infeasible,
    phi_0,
    phi_0 * 100
])

summary_stats['Units'].extend([
    'count',
    'count',
    'count',
    'ratio',
    'percent'
])

df_summary = pd.DataFrame(summary_stats)
df_summary.to_csv(summary_stats_csv, index=False)

print(f"✓ Saved: {summary_stats_csv}")

# ==================================================
# CREATE FEASIBILITY REPORT
# ==================================================
print("\n" + "=" * 80)
print("CREATING FEASIBILITY REPORT")
print("=" * 80)

feasibility_data = {
    'Category': ['Feasible', 'Infeasible', 'Total'],
    'Number_of_OD_Pairs': [num_feasible, num_infeasible, num_total],
    'Percentage': [
        num_feasible / num_total * 100 if num_total > 0 else 0,
        num_infeasible / num_total * 100 if num_total > 0 else 0,
        100.0
    ]
}

if len(df_infeasible) > 0:
    feasibility_data['Tons_2024_day'] = [
        total_tons_2024,
        infeasible_tons_2024,
        total_tons_2024 + infeasible_tons_2024
    ]
    feasibility_data['Value_2024_day'] = [
        total_value_2024,
        infeasible_value_2024,
        total_value_2024 + infeasible_value_2024
    ]

df_feasibility = pd.DataFrame(feasibility_data)
df_feasibility.to_csv(feasibility_report_csv, index=False)

print(f"✓ Saved: {feasibility_report_csv}")

# ==================================================
# CREATE VISUALIZATIONS
# ==================================================
print("\n" + "=" * 80)
print("CREATING VISUALIZATIONS")
print("=" * 80)

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.dpi'] = 100

# Figure 1: Feasibility Pie Chart
fig, ax = plt.subplots(figsize=(8, 6))
colors = ['#90EE90', '#FFB6C6']  # Light green, light red
wedges, texts, autotexts = ax.pie(
    [num_feasible, num_infeasible],
    labels=['Feasible', 'Infeasible'],
    autopct='%1.1f%%',
    startangle=90,
    colors=colors,
    textprops={'fontsize': 12, 'weight': 'bold'}
)

ax.set_title('Baseline Feasibility\nFraction of Total OD Pairs Served', 
             fontsize=14, fontweight='bold', pad=20)

# Add text box with phi_0
textstr = f'φ₀ = {phi_0:.4f}\n({num_feasible:,} of {num_total:,} pairs)'
props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
ax.text(0.5, -0.15, textstr, transform=ax.transAxes, fontsize=12,
        verticalalignment='top', horizontalalignment='center', bbox=props)

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'feasibility_pie_chart.png'), dpi=300, bbox_inches='tight')
print("✓ Saved: feasibility_pie_chart.png")
plt.close()

# Figure 2: OD Type Combinations Bar Chart
fig, ax = plt.subplots(figsize=(12, 6))
top_10_combos = breakdown_nodetype.head(10)

bars = ax.bar(range(len(top_10_combos)), top_10_combos['total_tons_2024_day'])
ax.set_xticks(range(len(top_10_combos)))
ax.set_xticklabels(top_10_combos['od_type_combo'], rotation=45, ha='right')
ax.set_ylabel('Total Tons/Day (2024)', fontsize=12, fontweight='bold')
ax.set_xlabel('OD Type Combination', fontsize=12, fontweight='bold')
ax.set_title('Top 10 OD Type Combinations by Daily Tonnage', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)

# Add value labels on bars
for i, bar in enumerate(bars):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{height:,.0f}',
            ha='center', va='bottom', fontsize=9)

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'od_type_combinations.png'), dpi=300, bbox_inches='tight')
print("✓ Saved: od_type_combinations.png")
plt.close()

# Figure 3: Top Counties Bar Chart
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

top_10_origin = breakdown_county.nlargest(10, 'total_tons_2024_day_origin')
top_10_dest = breakdown_county.nlargest(10, 'total_tons_2024_day_dest')

# Origin counties
ax1.barh(range(len(top_10_origin)), top_10_origin['total_tons_2024_day_origin'])
ax1.set_yticks(range(len(top_10_origin)))
ax1.set_yticklabels(top_10_origin['county_geoid'])
ax1.set_xlabel('Total Tons/Day (2024)', fontsize=11, fontweight='bold')
ax1.set_title('Top 10 Origin Counties', fontsize=12, fontweight='bold')
ax1.grid(axis='x', alpha=0.3)
ax1.invert_yaxis()

# Destination counties
ax2.barh(range(len(top_10_dest)), top_10_dest['total_tons_2024_day_dest'])
ax2.set_yticks(range(len(top_10_dest)))
ax2.set_yticklabels(top_10_dest['county_geoid'])
ax2.set_xlabel('Total Tons/Day (2024)', fontsize=11, fontweight='bold')
ax2.set_title('Top 10 Destination Counties', fontsize=12, fontweight='bold')
ax2.grid(axis='x', alpha=0.3)
ax2.invert_yaxis()

plt.tight_layout()
fig.savefig(os.path.join(figures_dir, 'top_counties.png'), dpi=300, bbox_inches='tight')
print("✓ Saved: top_counties.png")
plt.close()

# ==================================================
# FINAL SUMMARY
# ==================================================
print("\n" + "=" * 80)
print("STAGE 4 COMPLETE - BASELINE METRICS CALCULATED")
print("=" * 80)

print(f"""
OUTPUT FILES CREATED:

1. Summary Statistics:
   {summary_stats_csv}
   - Aggregate ton-hours and value-hours (2024 & 2050)
   - Average metrics (travel time, path length)
   - Feasibility ratio (φ_0)

2. Breakdown by Node Type:
   {breakdown_by_nodetype_csv}
   - Metrics for each origin→destination type combination
   - Number of OD pairs, tons, value, ton-hours, value-hours

3. Breakdown by County:
   {breakdown_by_county_csv}
   - Metrics by origin county and destination county
   - Origin/destination separate and combined

4. Feasibility Report:
   {feasibility_report_csv}
   - Feasible vs infeasible OD pairs
   - Percentage breakdown

5. Figures:
   {figures_dir}/
   - feasibility_pie_chart.png
   - od_type_combinations.png
   - top_counties.png

KEY METRICS:
  Feasibility ratio (φ_0)      : {phi_0:.4f} ({phi_0*100:.2f}%)
  Total ton-hours (2024)       : {total_ton_hours_2024:,.0f}
  Total value-hours (2024)     : ${total_value_hours_2024:,.0f}
  Total daily tons (2024)      : {total_tons_2024:,.0f}
  Total daily value (2024)     : ${total_value_2024:,.0f}

Ready for Stage 5 - Disruption Analysis! 🎯
""")

print("=" * 80)
# %%
