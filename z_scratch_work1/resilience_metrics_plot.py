#%%
# import pandas as pd
import matplotlib.pyplot as plt
import os
import pandas as pd

# ==================================================
# PATHS
# ==================================================
base_dir = os.path.abspath(os.path.join("..", ".."))

resilience_csv = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Resilience_Analysis", "resilience_summary.csv"
)
# ==================================================
# READ DATA
# ==================================================
print(f"Reading data from: {resilience_csv}")
df = pd.read_csv(resilience_csv)

print(f"\nData shape: {df.shape}")
print(f"\nColumns: {df.columns.tolist()}")

# ==================================================
# GET UNIQUE SCENARIOS
# ==================================================
unique_scenarios = df['scenario_name'].unique()
print(f"\nUnique scenarios ({len(unique_scenarios)}):")
for scenario in unique_scenarios:
    print(f"  - {scenario}")

# ==================================================
# CREATE OUTPUT DIRECTORY
# ==================================================
output_dir = os.path.join(os.path.dirname(__file__), 'resilience_figures')
os.makedirs(output_dir, exist_ok=True)

# ==================================================
# CREATE A FIGURE FOR EACH SCENARIO
# ==================================================
for scenario in unique_scenarios:
    print(f"\nProcessing scenario: {scenario}")
    
    # Filter data for this scenario
    scenario_data = df[df['scenario_name'] == scenario].copy()
    
    # Sort by disruption_percentage
    scenario_data = scenario_data.sort_values('disruption_percentage')
    
    # Extract data
    x = scenario_data['disruption_percentage']
    y_unaffected = scenario_data['pct_unaffected']
    y_delayed = scenario_data['pct_delayed']
    y_infeasible = scenario_data['pct_infeasible']
    
    # Verify sum is 100% (for checking)
    total_pct = y_unaffected + y_delayed + y_infeasible
    print(f"  Total percentage range: {total_pct.min():.2f}% - {total_pct.max():.2f}%")
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot three lines with circles
    ax.plot(x, y_unaffected, marker='o', linestyle='-', linewidth=2, 
            markersize=8, label='Unaffected', color='green', alpha=0.7)
    ax.plot(x, y_delayed, marker='o', linestyle='-', linewidth=2, 
            markersize=8, label='Delayed', color='orange', alpha=0.7)
    ax.plot(x, y_infeasible, marker='o', linestyle='-', linewidth=2, 
            markersize=8, label='Infeasible', color='red', alpha=0.7)
    
    # ==================================================
    # CALCULATE Y-AXIS LIMITS (10% padding)
    # ==================================================
    all_values = pd.concat([y_unaffected, y_delayed, y_infeasible])
    y_min = all_values.min()
    y_max = all_values.max()

    y_range = y_max - y_min

    # If all values are the same, avoid zero range
    if y_range == 0:
        y_range = 5

    padding = 0.1 * y_range

    y_bottom = y_min - padding
    y_top = y_max + padding

    # Keep reasonable bounds
    y_bottom = max(-5, y_bottom)
    y_top = min(105, y_top)

    ax.set_ylim(y_bottom, y_top)

    
    print(f"  Y-axis range: {y_bottom:.2f}% - {y_top:.2f}%")
    
    # ==================================================
    # FORMATTING
    # ==================================================
    ax.set_xlabel('Disruption Percentage (%)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
    ax.set_title(f'Resilience Analysis: {scenario}\nSystem Performance by Disruption Level', 
                 fontsize=14, fontweight='bold', pad=20)
    
    # Grid
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Legend
    ax.legend(loc='best', framealpha=0.9, fontsize=11)
    
    # Tight layout
    plt.tight_layout()
    
    # ==================================================
    # SAVE FIGURE
    # ==================================================
    # Create safe filename from scenario name
    safe_filename = scenario.replace(' ', '_').replace('/', '_').replace('\\', '_')
    output_path = os.path.join(output_dir, f'{safe_filename}.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"  Saved: {output_path}")
    
    plt.close()

print(f"\n{'='*60}")
print(f"All figures saved to: {output_dir}")
print(f"Total figures created: {len(unique_scenarios)}")
print(f"{'='*60}")

# %%
#%%
#%%
import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
import math

# ==================================================
# PATHS
# ==================================================
base_dir = os.path.abspath(os.path.join("..", ".."))

resilience_csv = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "Resilience_Analysis", "resilience_summary.csv"
)

# ==================================================
# READ DATA
# ==================================================
print(f"Reading data from: {resilience_csv}")
df = pd.read_csv(resilience_csv)

print(f"\nData shape: {df.shape}")
print(f"\nColumns: {df.columns.tolist()}")

# ==================================================
# GET UNIQUE SCENARIOS
# ==================================================
unique_scenarios = df['scenario_name'].unique()

# ==================================================
# CREATE OUTPUT DIRECTORY
# ==================================================
output_dir = os.path.join(os.path.dirname(__file__), 'freight_figures')
os.makedirs(output_dir, exist_ok=True)

# ==================================================
# DEFINE MARKERS AND COLORS
# ==================================================
tons_marker = 'o'
value_marker = 's'
tons_color = '#1f77b4'
value_color = '#ff7f0e'

# ==================================================
# GROUP SCENARIOS
# ==================================================
scenario_groups = {
    'Tons_2024': [],
    'Tons_2050': [],
    'Value_2024': [],
    'Value_2050': []
}

for scenario in unique_scenarios:
    s = scenario.lower()
    if 'tons_2024' in s:
        scenario_groups['Tons_2024'].append(scenario)
    elif 'tons_2050' in s:
        scenario_groups['Tons_2050'].append(scenario)
    elif 'value_2024' in s:
        scenario_groups['Value_2024'].append(scenario)
    elif 'value_2050' in s:
        scenario_groups['Value_2050'].append(scenario)

# ==================================================
# CREATE FIGURES
# ==================================================
for group_name, scenarios_in_group in scenario_groups.items():

    if not scenarios_in_group:
        continue

    print(f"\nCreating figure: {group_name}")

    # Determine correct columns
    if '2024' in group_name:
        tons_col = 'F_tons_2024'
        value_col = 'F_value_2024'
        year = '2024'
    else:
        tons_col = 'F_tons_2050'
        value_col = 'F_value_2050'
        year = '2050'

    fig, ax = plt.subplots(figsize=(12, 8))

    tons_x_all, tons_y_all = [], []
    value_x_all, value_y_all = [], []
    all_values = []

    # ----------------------------------------------
    # Collect Data
    # ----------------------------------------------
    for scenario in scenarios_in_group:

        scenario_data = df[df['scenario_name'] == scenario].copy()
        scenario_data = scenario_data.sort_values('disruption_percentage')

        x = scenario_data['disruption_percentage']
        y_tons = scenario_data[tons_col]
        y_value = scenario_data[value_col]

        # Add starting point (0, 1)
        x_with_zero = pd.concat([pd.Series([0]), x], ignore_index=True)
        y_tons_with_zero = pd.concat([pd.Series([1.0]), y_tons], ignore_index=True)
        y_value_with_zero = pd.concat([pd.Series([1.0]), y_value], ignore_index=True)

        tons_x_all.extend(x_with_zero.tolist())
        tons_y_all.extend(y_tons_with_zero.tolist())
        value_x_all.extend(x_with_zero.tolist())
        value_y_all.extend(y_value_with_zero.tolist())

        all_values.extend(y_tons_with_zero.tolist())
        all_values.extend(y_value_with_zero.tolist())

    # Sort for plotting
    tons_sorted = sorted(zip(tons_x_all, tons_y_all))
    value_sorted = sorted(zip(value_x_all, value_y_all))

    tons_x, tons_y = zip(*tons_sorted)
    value_x, value_y = zip(*value_sorted)

    # ----------------------------------------------
    # Plot Lines
    # ----------------------------------------------
    ax.plot(tons_x, tons_y,
            marker=tons_marker,
            linestyle='-',
            linewidth=2.5,
            markersize=9,
            label=f'Freight Tons {year}',
            color=tons_color,
            alpha=0.8)

    ax.plot(value_x, value_y,
            marker=value_marker,
            linestyle='-',
            linewidth=2.5,
            markersize=9,
            label=f'Freight Value {year}',
            color=value_color,
            alpha=0.8)

    # ----------------------------------------------
    # Add Percentage Labels
    # ----------------------------------------------
    for x_val, y_val in zip(tons_x, tons_y):
        ax.text(x_val,
                y_val + 0.002,
                f"{y_val*100:.2f}%",
                ha='center',
                va='bottom',
                fontsize=9,
                color=tons_color)

    for x_val, y_val in zip(value_x, value_y):
        ax.text(x_val,
                y_val + 0.002,
                f"{y_val*100:.2f}%",
                ha='center',
                va='bottom',
                fontsize=9,
                color=value_color)

    # ----------------------------------------------
    # Y-Axis Limits (with padding)
    # ----------------------------------------------
    y_min = min(all_values)
    y_max = max(all_values)
    y_range = y_max - y_min

    padding = 0.15 * y_range
    y_bottom = max(0, y_min - padding)
    y_top = y_max + padding

    ax.set_ylim(y_bottom, y_top)

    # ----------------------------------------------
    # X-Axis from 0 to 1.1 with 0.1 increments
    # ----------------------------------------------
    x_max = 1.1
    ax.set_xlim(0, x_max)
    ax.set_xticks(np.arange(0, x_max + 0.001, 0.1))
    ax.xaxis.set_major_formatter(lambda x, pos: f"{x:.1f}")

    # ----------------------------------------------
    # Formatting
    # ----------------------------------------------
    ax.set_xlabel('Disruption Percentage (%)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Normalized Value', fontsize=12, fontweight='bold')
    ax.set_title(f'Resilience Analysis: {group_name}\nFreight Tons and Value - Year {year}',
                 fontsize=14, fontweight='bold', pad=20)

    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='best', framealpha=0.9, fontsize=11)

    plt.tight_layout()

    # ----------------------------------------------
    # Save
    # ----------------------------------------------
    output_path = os.path.join(output_dir, f'{group_name}_freight.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Saved: {output_path}")

print("\nAll figures created successfully.")

# %%
