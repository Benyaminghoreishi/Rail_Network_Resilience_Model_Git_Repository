# %%
#! =======================================================================
#! 1
#! FAF5.7.1: Extracting Key Fields and 2024 and 2050 Tons 
#! Output: FAF Level → 5 fields + 2024/2050 tons/values → 365,031 rows (mode 2 only)
#! =======================================================================

import pandas as pd
import os
import re
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Absolute path to FAF data
base_dir = os.path.abspath(os.path.join("..", ".."))

faf_path = os.path.join(base_dir, "13_Resiliency", "FAF", "Downloaded_Data", "FAF5.7.1_raw_data", "FAF5.7.1.csv")

# Read
faf_df = pd.read_csv(faf_path)

# Make column access case-insensitive and uniform
faf_df.columns = [c.strip().lower() for c in faf_df.columns]

# Required columns (the “colored” ones)
base_cols = ["dms_orig", "dms_dest", "sctg2", "dms_mode", "trade_type", "tons_2024", "value_2024", "tons_2050", "value_2050"]

FAF_df = faf_df[base_cols].copy()

# Optional: ensure numeric
FAF_df["tons_2024"] = pd.to_numeric(FAF_df["tons_2024"], errors="coerce")
FAF_df["tons_2050"] = pd.to_numeric(FAF_df["tons_2050"], errors="coerce")

# Just keep the rows that has number 2 in the dms_mode column
FAF_df = FAF_df[FAF_df["dms_mode"] == 2]

# Save
out_path = os.path.join(base_dir, "13_Resiliency", "FAF", "Processed_Data", "FAF5.7.1_selected_2024_tons.csv")
FAF_df.to_csv(out_path, index=False)

print(f"Saved {len(FAF_df):,} rows to:\n{out_path}")

# Print the sum of tons_2024 and tons_2050
total_tons_2024 = FAF_df["tons_2024"].sum()
total_tons_2050 = FAF_df["tons_2050"].sum()
print(f"Total Tons (2024, Mode 2): {total_tons_2024:,.0f} thousand tons")
print(f"Total Tons (2050, Mode 2): {total_tons_2050:,.0f} thousand tons")

# Print the sum of value_2024 and value_2050
total_value_2024 = FAF_df["value_2024"].sum()
total_value_2050 = FAF_df["value_2050"].sum()
print(f"Total Value (2024, Mode 2): ${total_value_2024:,.0f} million 2017 USD")
print(f"Total Value (2050, Mode 2): ${total_value_2050:,.0f} million 2017 USD")

#%%
#! =======================================================================
#! 2
#! FAF5.7.1: Aggregating SCTG categories into 5 groups 
#! sctg_all_categories_concat.csv (45651 rows) + sctg_category_totals.csv (5 rows)
#! sctg0109.csv, sctg1014.csv, sctg1519.csv, sctg2033.csv, sctg3499.csv
#! =======================================================================

import pandas as pd
import os

# Absolute path to FAF data
base_dir = os.path.abspath(os.path.join("..", ".."))
faf_path = os.path.join(base_dir, "13_Resiliency", "FAF", "Downloaded_Data", "FAF5.7.1_raw_data", "FAF5.7.1.csv")

# Read
faf_df = pd.read_csv(faf_path)
faf_df.columns = [c.strip().lower() for c in faf_df.columns]

# Required columns
base_cols = ["dms_orig", "dms_dest", "sctg2", "dms_mode", "trade_type", "tons_2024", "value_2024", "tons_2050", "value_2050"]
FAF_df = faf_df[base_cols].copy()

# Ensure numeric
FAF_df["tons_2024"] = pd.to_numeric(FAF_df["tons_2024"], errors="coerce")
FAF_df["value_2024"] = pd.to_numeric(FAF_df["value_2024"], errors="coerce")
FAF_df["tons_2050"] = pd.to_numeric(FAF_df["tons_2050"], errors="coerce")
FAF_df["value_2050"] = pd.to_numeric(FAF_df["value_2050"], errors="coerce")

# Keep only mode 2
FAF_df = FAF_df[FAF_df["dms_mode"] == 2]

# -------------------------------------------------------
# Define aggregation bins (mapping SCTG 2-digit to 5 groups)
# -------------------------------------------------------
bins = {
    "sctg0109": range(1, 10),
    "sctg1014": range(10, 15),
    "sctg1519": range(15, 20),
    "sctg2033": range(20, 34),
    "sctg3499": range(34, 100),
}

def map_category(sctg):
    for cat, r in bins.items():
        if sctg in r:
            return cat
    return None

FAF_df["category"] = FAF_df["sctg2"].apply(map_category)

# -------------------------------------------------------
# Aggregate by OD pair and new category
# -------------------------------------------------------
agg_df = (
    FAF_df.groupby(["dms_orig", "dms_dest", "trade_type", "category"], as_index=False)
    .agg({"tons_2024": "sum", "value_2024": "sum", "tons_2050": "sum", "value_2050": "sum"})
)

# -------------------------------------------------------
# Save one CSV file for each category
# -------------------------------------------------------
out_dir = os.path.join(base_dir, "13_Resiliency", "FAF", "Processed_Data", "Aggregated_Categories")
os.makedirs(out_dir, exist_ok=True)

for cat in agg_df["category"].unique():
    subset = agg_df[agg_df["category"] == cat]
    out_path = os.path.join(out_dir, f"{cat}.csv")
    subset.to_csv(out_path, index=False)
    print(f"Saved {len(subset):,} rows to {out_path}")

# -------------------------------------------------------
# Also save: (a) all categories concatenated, (b) 5-row totals
# -------------------------------------------------------

# (a) Concatenate all per-category rows into one file
all_concat_path = os.path.join(out_dir, "sctg_all_categories_concat.csv")
agg_df.sort_values(["category", "dms_orig", "dms_dest", "trade_type"]).to_csv(all_concat_path, index=False)
print(f"Saved concatenated rows to {all_concat_path}")

# (b) Five-row totals (sum over OD pairs per category)
totals_df = (
    agg_df.groupby("category", as_index=False)[["tons_2024", "value_2024"]]
          .sum()
          .sort_values("category")
)
#%%
#! =======================================================================
#! 3
#! Integrated FAF Rail (Mode 2) Visualization
#! Generates 6 plots: SCTG2 and Aggregated Categories for 2024, 2050, and combined
#! Units: tons -> million tons | value -> million 2017 USD
#! =======================================================================

import os, glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FuncFormatter
from matplotlib.lines import Line2D

sns.set_style("white")

# SCTG Descriptions
sctg_desc = {
    1: "Live animals/fish", 2: "Cereal grains", 3: "Other ag. prods.", 4: "Animal feed",
    5: "Meat/seafood", 6: "Milled grain prods.", 7: "Other foodstuffs", 8: "Alcoholic beverages",
    9: "Tobacco prods.", 10: "Building stone", 11: "Natural sands", 12: "Gravel",
    13: "Nonmetallic minerals", 14: "Metallic ores", 15: "Coal", 16: "Crude petroleum",
    17: "Gasoline", 18: "Fuel oils", 19: "Nat. gas & other fossil prods.", 20: "Basic chemicals",
    21: "Pharmaceuticals", 22: "Fertilizers", 23: "Chemical prods.", 24: "Plastics/rubber",
    25: "Logs", 26: "Wood prods.", 27: "Newsprint/paper", 28: "Paper articles",
    29: "Printed prods.", 30: "Textiles/leather", 31: "Nonmetallic min. prods.", 32: "Base metals",
    33: "Articles-base metal", 34: "Machinery", 35: "Electronics", 36: "Motorized vehicles",
    37: "Transport equip.", 38: "Precision instruments", 39: "Furniture", 40: "Misc. mfg. prods.",
    41: "Waste/scrap", 43: "Mixed freight"
}

agg_desc = {
    "sctg0109": "Agricultural products",
    "sctg1014": "Gravel and mining products",
    "sctg1519": "Coal and other energy products",
    "sctg2033": "Chemical, wood and metals",
    "sctg3499": "Manufactured goods, mixed freight, waste & unknown"
}

# Formatter functions
def fmt_m_tons(x, _): return f"{x:,.1f}"
def fmt_musd(x, _): return f"${x:,.0f}M"

# Convert FAF units
FAF_df["tons_million_2024"] = pd.to_numeric(FAF_df["tons_2024"], errors="coerce") / 1e3
FAF_df["value_2024"] = pd.to_numeric(FAF_df["value_2024"], errors="coerce")
FAF_df["tons_million_2050"] = pd.to_numeric(FAF_df["tons_2050"], errors="coerce") / 1e3
FAF_df["value_2050"] = pd.to_numeric(FAF_df["value_2050"], errors="coerce")

# Aggregate by SCTG2
sctg_sum = (
    FAF_df.groupby("sctg2", as_index=False)
          .agg(tons_million_2024=("tons_million_2024", "sum"),
               value_2024=("value_2024", "sum"),
               tons_million_2050=("tons_million_2050", "sum"),
               value_2050=("value_2050", "sum"))
          .sort_values("sctg2")
)

# Load aggregated categories
out_dir = os.path.join(base_dir, "13_Resiliency", "FAF", "Processed_Data", "Aggregated_Categories")
cat_rows = []
for file in sorted(glob.glob(os.path.join(out_dir, "sctg*.csv"))):
    df_cat = pd.read_csv(file)
    df_cat["tons_2024"] = pd.to_numeric(df_cat["tons_2024"], errors="coerce")
    df_cat["value_2024"] = pd.to_numeric(df_cat["value_2024"], errors="coerce")
    df_cat["tons_2050"] = pd.to_numeric(df_cat["tons_2050"], errors="coerce")
    df_cat["value_2050"] = pd.to_numeric(df_cat["value_2050"], errors="coerce")
    
    cat_name = os.path.splitext(os.path.basename(file))[0]
    cat_rows.append((cat_name, df_cat["tons_2024"].sum() / 1e3, df_cat["value_2024"].sum(),
                     df_cat["tons_2050"].sum() / 1e3, df_cat["value_2050"].sum()))

cat_df = pd.DataFrame(cat_rows, columns=["category", "tons_million_2024", "value_2024",
                                         "tons_million_2050", "value_2050"]).sort_values("category")
cat_df = cat_df[cat_df["category"] != "sctg_all_categories_concat"]

# ========================================================================
# PLOTTING FUNCTION
# ========================================================================
def plot_data(data, x_col, year, data_type, ylim_tons=None, ylim_val=None):
    """Generic plotting function for both SCTG2 and aggregated categories"""
    x = np.arange(len(data))
    labels = data[x_col].astype(str).tolist()
    
    fig, ax1 = plt.subplots(figsize=(14, 6) if data_type == "SCTG2" else (12, 6), constrained_layout=True)
    
    # Color scheme - darker shades for lines to ensure visibility
    if year == "2024":
        bar_color = "steelblue" if data_type == "SCTG2" else "seagreen"
        line_color = "darkblue" if data_type == "SCTG2" else "darkgreen"
    else:  # 2050
        bar_color = "lightsteelblue" if data_type == "SCTG2" else "lightgreen"
        line_color = "steelblue" if data_type == "SCTG2" else "seagreen"
    
    # Bars: million tons
    bar = ax1.bar(x, data[f"tons_million_{year}"], color=bar_color)
    if ylim_tons: ax1.set_ylim(0, ylim_tons)
    ax1.set_ylabel(f"Million Tons ({year})", color="black")
    ax1.yaxis.set_major_formatter(FuncFormatter(fmt_m_tons))
    ax1.set_xlabel(data_type if data_type == "SCTG2" else "Aggregated Category")
    ax1.set_xticks(x, labels, rotation=0)
    title = f"FAF Rail (Mode 2) — Tons & Values by {data_type} ({year})" if data_type == "SCTG2" else f"Rail (Mode 2) — Tons & Values by Aggregated Category ({year})"
    ax1.set_title(title)
    
    # Annotate tons above bars
    for i, v in enumerate(data[f"tons_million_{year}"]):
        ax1.text(x[i], v, f"{v:,.1f}", ha="center", va="bottom", fontsize=8 if data_type == "SCTG2" else 11)
    
    # Right axis: value line
    ax2 = ax1.twinx()
    ax2.plot(x, data[f"value_{year}"], color=line_color, marker="o", linewidth=1.5 if data_type == "SCTG2" else 1.8)
    ax2.set_ylabel(f"Value {year} (Million 2017 USD)", color=line_color)
    ax2.tick_params(axis='y', labelcolor=line_color)
    ax2.yaxis.set_major_formatter(FuncFormatter(fmt_musd))
    
    # Annotate value near markers
    ylim2 = ax2.get_ylim()
    dy_val = 0.015 * (ylim2[1] - ylim2[0])
    for i, v in enumerate(data[f"value_{year}"]):
        ax2.text(x[i], v + dy_val, f"{v:,.0f}M", color=line_color,
                 ha="center", va="bottom", fontsize=9 if data_type == "SCTG2" else 11)
    
    # Legend A: Tons + Value
    legend_series = ax1.legend(
        [bar, ax2.lines[0]],
        [f"Million Tons ({year})", f"Value {year} (Million 2017 USD)"],
        loc="upper left", fontsize=10, frameon=True, bbox_to_anchor=(0, 0.92)
    )
    
    # Legend B: Descriptions
    if data_type == "SCTG2":
        legend_texts = [f"{k:02d} = {v}" for k, v in sctg_desc.items()]
        bbox = (0.50, 0.99)
        ncol = 2
        fontsize = 8
    else:
        legend_texts = [f"{k} = {v}" for k, v in agg_desc.items()]
        bbox = (0, 0.82)
        ncol = 1
        fontsize = 10
    
    dummy_handles = [Line2D([0], [0], linestyle="none") for _ in legend_texts]
    legend_desc = ax1.legend(dummy_handles, legend_texts, loc="upper left", fontsize=fontsize,
                             ncol=ncol, bbox_to_anchor=bbox, frameon=True,
                             handlelength=0, handletextpad=0.3)
    ax1.add_artist(legend_series)
    
    # Totals
    total_tons = data[f"tons_million_{year}"].sum()
    total_val = data[f"value_{year}"].sum()
    ax1.text(0.01, 0.98, f"Total Tons: {total_tons:,.1f} M\nTotal Value: ${total_val:,.0f}M",
             transform=ax1.transAxes, ha="left", va="top", fontsize=11, fontweight="bold")
    
    return fig

def plot_comparison(data, x_col, data_type):
    """Plotting function for 2024 vs 2050 comparison"""
    x = np.arange(len(data))
    labels = data[x_col].astype(str).tolist()
    bar_width = 0.35
    
    fig, ax1 = plt.subplots(figsize=(14, 6) if data_type == "SCTG2" else (12, 6), constrained_layout=True)
    
    # Color scheme - darker shades for lines to ensure visibility
    if data_type == "SCTG2":
        color_2024_bar, color_2024_line = "steelblue", "darkblue"
        color_2050_bar, color_2050_line = "lightsteelblue", "navy"
    else:
        color_2024_bar, color_2024_line = "seagreen", "darkgreen"
        color_2050_bar, color_2050_line = "lightgreen", "forestgreen"
    
    # Bars: million tons
    bar1 = ax1.bar(x - bar_width/2, data["tons_million_2024"], bar_width, color=color_2024_bar, label="2024 Tons")
    bar2 = ax1.bar(x + bar_width/2, data["tons_million_2050"], bar_width, color=color_2050_bar, label="2050 Tons")
    if data_type == "SCTG2":
        ax1.set_ylim(0, 350)
    else:
        ax1.set_ylim(0, 950)
    ax1.set_ylabel("Million Tons", color="black")
    ax1.yaxis.set_major_formatter(FuncFormatter(fmt_m_tons))
    ax1.set_xlabel(data_type if data_type == "SCTG2" else "Aggregated Category")
    ax1.set_xticks(x, labels, rotation=0)
    title = f"FAF Rail (Mode 2) — Tons & Values by {data_type} (2024 vs 2050)" if data_type == "SCTG2" else "Rail (Mode 2) — Tons & Values by Aggregated Category (2024 vs 2050)"
    ax1.set_title(title)
    
    # Annotate tons above bars
    fontsize = 7 if data_type == "SCTG2" else 10
    for i, v in enumerate(data["tons_million_2024"]):
        ax1.text(x[i] - bar_width/2, v, f"{v:,.1f}", ha="center", va="bottom", fontsize=fontsize)
    for i, v in enumerate(data["tons_million_2050"]):
        ax1.text(x[i] + bar_width/2, v, f"{v:,.1f}", ha="center", va="bottom", fontsize=fontsize)
    
    # Right axis: value lines
    ax2 = ax1.twinx()
    line1 = ax2.plot(x, data["value_2024"], color=color_2024_line, marker="o", linewidth=1.5 if data_type == "SCTG2" else 1.8, label="2024 Value")
    line2 = ax2.plot(x, data["value_2050"], color=color_2050_line, marker="s", linewidth=1.5 if data_type == "SCTG2" else 1.8, label="2050 Value")
    ax2.set_ylabel("Value (Million 2017 USD)", color="black")
    ax2.yaxis.set_major_formatter(FuncFormatter(fmt_musd))
    
    # Annotate value near markers - 2024 BELOW, 2050 ABOVE
    ylim2 = ax2.get_ylim()
    dy_val = 0.015 * (ylim2[1] - ylim2[0])
    for i, v in enumerate(data["value_2024"]):
        ax2.text(x[i], v - dy_val, f"{v:,.0f}M", color=color_2024_line, ha="center", va="top", fontsize=fontsize)
    for i, v in enumerate(data["value_2050"]):
        ax2.text(x[i], v + dy_val, f"{v:,.0f}M", color=color_2050_line, ha="center", va="bottom", fontsize=fontsize)
    
    # Legend A: Tons + Value
    legend_series = ax1.legend(
        [bar1, bar2, line1[0], line2[0]],
        ["Million Tons (2024)", "Million Tons (2050)", "Value 2024 (Million 2017 USD)", "Value 2050 (Million 2017 USD)"],
        loc="upper left", fontsize=9, frameon=True, bbox_to_anchor=(0, 0.92)
    )
    
    # Legend B: Descriptions
    if data_type == "SCTG2":
        legend_texts = [f"{k:02d} = {v}" for k, v in sctg_desc.items()]
        bbox = (0.50, 0.99)
        ncol = 2
        fontsize_desc = 7
    else:
        legend_texts = [f"{k} = {v}" for k, v in agg_desc.items()]
        bbox = (0, 0.77)
        ncol = 1
        fontsize_desc = 10
    
    dummy_handles = [Line2D([0], [0], linestyle="none") for _ in legend_texts]
    legend_desc = ax1.legend(dummy_handles, legend_texts, loc="upper left", fontsize=fontsize_desc,
                             ncol=ncol, bbox_to_anchor=bbox, frameon=True,
                             handlelength=0, handletextpad=0.3)
    ax1.add_artist(legend_series)
    
    # Totals
    total_tons_2024 = data["tons_million_2024"].sum()
    total_val_2024 = data["value_2024"].sum()
    total_tons_2050 = data["tons_million_2050"].sum()
    total_val_2050 = data["value_2050"].sum()
    ax1.text(0.01, 0.98,
             f"2024 — Tons: {total_tons_2024:,.1f}M | Value: ${total_val_2024:,.0f}M\n"
             f"2050 — Tons: {total_tons_2050:,.1f}M | Value: ${total_val_2050:,.0f}M",
             transform=ax1.transAxes, ha="left", va="top", fontsize=11, fontweight="bold")
    
    return fig

# ========================================================================
# GENERATE ALL 6 PLOTS
# ========================================================================

# Create output directory for figures
output_dir = os.path.join(base_dir, "13_Resiliency", "FAF", "Figures")
os.makedirs(output_dir, exist_ok=True)

# Plot 1: SCTG2 - 2024
fig1 = plot_data(sctg_sum, "sctg2", "2024", "SCTG2")
fig1.savefig(os.path.join(output_dir, "01_SCTG2_2024.png"), dpi=720, bbox_inches='tight')
plt.show()

# Plot 2: Aggregated Categories - 2024
fig2 = plot_data(cat_df, "category", "2024", "Aggregated")
fig2.savefig(os.path.join(output_dir, "02_Aggregated_2024.png"), dpi=720, bbox_inches='tight')
plt.show()

# Plot 3: SCTG2 - 2050
fig3 = plot_data(sctg_sum, "sctg2", "2050", "SCTG2", ylim_tons=300)
fig3.savefig(os.path.join(output_dir, "03_SCTG2_2050.png"), dpi=720, bbox_inches='tight')
plt.show()

# Plot 4: Aggregated Categories - 2050
fig4 = plot_data(cat_df, "category", "2050", "Aggregated", ylim_tons=950)
fig4.savefig(os.path.join(output_dir, "04_Aggregated_2050.png"), dpi=720, bbox_inches='tight')
plt.show()

# Plot 5: SCTG2 - 2024 vs 2050
fig5 = plot_comparison(sctg_sum, "sctg2", "SCTG2")
fig5.savefig(os.path.join(output_dir, "05_SCTG2_Comparison.png"), dpi=720, bbox_inches='tight')
plt.show()

# Plot 6: Aggregated Categories - 2024 vs 2050
fig6 = plot_comparison(cat_df, "category", "Aggregated")
fig6.savefig(os.path.join(output_dir, "06_Aggregated_Comparison.png"), dpi=720, bbox_inches='tight')
plt.show()

print(f"\nAll 6 figures saved to: {output_dir}")

#%%
#! ============================================================================================
#! 4
#! Title: FAF Rail Demand Disaggregation to County-Level OD Flows (2024 & 2050)
#! Description:
#!   Expands FAF aggregated rail origin–destination flows into county-to-county
#!   OD flows using FAF experimental disaggregation factors for multiple SCTG groups.
#!   Preserves total tons and values for both 2024 and 2050 forecast years.
#! Outputs:
#!   - County-level OD CSV per SCTG group (2024 & 2050) 
#!   - Combined county-level OD CSV (all categories)
#!   - Summary CSV of total tons and values by category and year
#! ============================================================================================

import pandas as pd
import os

# -------------------------------------------------------------
# Base paths (same pattern you used earlier)
# -------------------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

agg_dir = os.path.join(base_dir, "13_Resiliency", "FAF", "Processed_Data", "Aggregated_Categories")
orig_factors_path = os.path.join(base_dir, "13_Resiliency", "FAF", "Downloaded_Data", "rail_origin_factors.csv")
dest_factors_path = os.path.join(base_dir, "13_Resiliency", "FAF", "Downloaded_Data", "rail_destination_factors.csv")

out_dir = os.path.join(base_dir, "13_Resiliency", "FAF", "Processed_Data", "County_Level")
os.makedirs(out_dir, exist_ok=True)

# The five aggregated SCTG groups to process
CATS = ["sctg0109", "sctg1014", "sctg1519", "sctg2033", "sctg3499"]

# -------------------------------------------------------------
# Load and normalize factor files once
# -------------------------------------------------------------
orig_factors = pd.read_csv(orig_factors_path)
dest_factors = pd.read_csv(dest_factors_path)

for df in (orig_factors, dest_factors):
    df.columns = [c.strip().lower() for c in df.columns]

# Optional: ensure factor columns are numeric
orig_factors["f_orig"] = pd.to_numeric(orig_factors["f_orig"], errors="coerce")
dest_factors["f_dest"] = pd.to_numeric(dest_factors["f_dest"], errors="coerce")

# -------------------------------------------------------------
# Helper: expand one FAF category file to county-level OD
# -------------------------------------------------------------
def expand_category_to_county(cat_code: str) -> pd.DataFrame:
    """Return county-level OD dataframe for a single aggregated category (e.g., 'sctg0109')."""
    cat_path = os.path.join(agg_dir, f"{cat_code}.csv")
    if not os.path.exists(cat_path):
        print(f"[WARN] File not found for {cat_code}: {cat_path}")
        return pd.DataFrame()

    # Read FAF OD pairs for this category
    faf_df = pd.read_csv(cat_path)
    faf_df.columns = [c.strip().lower() for c in faf_df.columns]
    faf_df["tons_2024"]  = pd.to_numeric(faf_df.get("tons_2024"),  errors="coerce").fillna(0.0)
    faf_df["value_2024"] = pd.to_numeric(faf_df.get("value_2024"), errors="coerce").fillna(0.0)
    faf_df["tons_2050"]  = pd.to_numeric(faf_df.get("tons_2050"),  errors="coerce").fillna(0.0)
    faf_df["value_2050"] = pd.to_numeric(faf_df.get("value_2050"), errors="coerce").fillna(0.0)

    # Keep only columns we need
    faf_df = faf_df[
        ["dms_orig", "dms_dest", "trade_type",
        "tons_2024", "value_2024",
        "tons_2050", "value_2050"]
    ]

    missing = {"tons_2050", "value_2050"} - set(faf_df.columns)
    if missing:
        raise ValueError(f"Missing required 2050 columns: {missing}")

    expanded_chunks = []
    # Process one FAF (orig, dest) at a time 
    for (orig, dest), g in faf_df.groupby(["dms_orig", "dms_dest"], dropna=False):
        faf_tons_2024 = g["tons_2024"].sum()     # still in *thousand tons* (FAF units)
        faf_val_2024  = g["value_2024"].sum()    # in *million 2017 USD*
        faf_tons_2050 = g["tons_2050"].sum()
        faf_val_2050  = g["value_2050"].sum()

        # Pull the factor lists for this origin and destination in this category
        o_df = orig_factors[
            (orig_factors["dms_orig"] == orig) & (orig_factors["sctgg5"] == cat_code)
        ][["dms_orig_cnty", "f_orig"]].dropna()

        d_df = dest_factors[
            (dest_factors["dms_dest"] == dest) & (dest_factors["sctgg5"] == cat_code)
        ][["dms_dest_cnty", "f_dest"]].dropna()

        if o_df.empty or d_df.empty:
            # If either side lacks factors, skip gracefully (or log)
            print(f"[SKIP] Missing factors for {cat_code} FAF ({orig}→{dest}). "
                  f"orig_cnties={len(o_df)}, dest_cnties={len(d_df)}")
            continue

        # Cross-join (requires pandas >= 1.2)
        expanded = o_df.merge(d_df, how="cross")

        # Proportional allocation
        # Units preserved: tons_2024 remains 'thousand tons', value_2024 remains 'million 2017 USD'
        factor_prod = expanded["f_orig"] * expanded["f_dest"]
        expanded["tons_2024"]  = factor_prod * faf_tons_2024
        expanded["value_2024"] = factor_prod * faf_val_2024
        expanded["tons_2050"]  = factor_prod * faf_tons_2050
        expanded["value_2050"] = factor_prod * faf_val_2050


        # Metadata
        expanded["faf_orig"]  = orig
        expanded["faf_dest"]  = dest
        expanded["trade_type"] = g["trade_type"].iloc[0] if "trade_type" in g.columns else None
        expanded["sctgg5"]     = cat_code

        expanded_chunks.append(expanded)

    if not expanded_chunks:
        return pd.DataFrame()

    county_level = pd.concat(expanded_chunks, ignore_index=True)

    # Order columns nicely
    col_order = [
        "sctgg5", "faf_orig", "faf_dest", "trade_type",
        "dms_orig_cnty", "dms_dest_cnty",
        "f_orig", "f_dest",
        "tons_2024", "value_2024",
        "tons_2050", "value_2050"
    ]

    county_level = county_level[col_order]

    return county_level

# -------------------------------------------------------------
# Run for all five categories, save per-category + combined
# -------------------------------------------------------------
all_cats = []
for cat in CATS:
    print(f"\n=== Expanding {cat} to county level ===")
    county_df = expand_category_to_county(cat)

    if county_df.empty:
        print(f"[INFO] No county rows produced for {cat}.")
        continue

    # Save per-category county file
    out_file = os.path.join(out_dir, f"county_level_{cat}.csv")
    county_df.to_csv(out_file, index=False)
    print(f"[OK] Saved {len(county_df):,} rows -> {out_file}")

    # Sanity check: compare allocated totals vs FAF totals in the category file
    # (read the FAF file again just to compute original totals cleanly)
    faf_file = os.path.join(agg_dir, f"{cat}.csv")
    faf_df_chk = pd.read_csv(faf_file)
    faf_df_chk["tons_2024"]  = pd.to_numeric(faf_df_chk["tons_2024"],  errors="coerce").fillna(0.0)
    faf_df_chk["value_2024"] = pd.to_numeric(faf_df_chk["value_2024"], errors="coerce").fillna(0.0)

    faf_tons_total = faf_df_chk["tons_2024"].sum()
    faf_val_total  = faf_df_chk["value_2024"].sum()

    alloc_tons_total = county_df["tons_2024"].sum()
    alloc_val_total  = county_df["value_2024"].sum()

    print(f"    FAF totals  (thousand tons / million USD): {faf_tons_total:,.0f} / {faf_val_total:,.0f}")
    print(f"    Allocated   (thousand tons / million USD): {alloc_tons_total:,.0f} / {alloc_val_total:,.0f}")
    print(f"    Diff        (tons / value): "
          f"{(alloc_tons_total - faf_tons_total):,.3f} / {(alloc_val_total - faf_val_total):,.3f}")

    # Non-zero OD count
    nonzero_cnt = (county_df["tons_2024"] > 0).sum()
    print(f"    County OD pairs with non-zero tons: {nonzero_cnt:,}")

    all_cats.append(county_df)

# Combined file with all five categories
if all_cats:
    combined = pd.concat(all_cats, ignore_index=True)
    combined_out = os.path.join(out_dir, "county_level_all_categories.csv")
    combined.to_csv(combined_out, index=False)
    print(f"\n[ALL] Saved combined county-level file with {len(combined):,} rows -> {combined_out}")
else:
    print("\n[ALL] No categories produced output; nothing to combine.")

# -------------------------------------------------------------
# Summary table: totals by category and year
# -------------------------------------------------------------
summary_rows = []

for cat in CATS:
    cat_file = os.path.join(out_dir, f"county_level_{cat}.csv")
    if not os.path.exists(cat_file):
        continue

    df = pd.read_csv(cat_file)

    summary_rows.append({
        "sctgg5": cat,
        "tons_2024":  df["tons_2024"].sum(),
        "value_2024": df["value_2024"].sum(),
        "tons_2050":  df["tons_2050"].sum(),
        "value_2050": df["value_2050"].sum(),
    })

summary_df = pd.DataFrame(summary_rows)

summary_out = os.path.join(out_dir, "county_level_summary_2024_2050.csv")
summary_df.to_csv(summary_out, index=False)

print(f"\n📊 Saved category summary file -> {summary_out}")
print(summary_df)


# %%
#! ============================================================================================
#! 5
#! Spatial Assignment and Aggregation of County-Level Rail Freight Flows
#! FAF County-to-County OD → County-Level Incoming / Outgoing Flow VECTORS
#! (Preserves OD pairing + order, 2024 & 2050, Global + per-SCTG)
#! Column naming:
#!   out_dest_cnty_list, out_tons_2024, ..., out_sum_value_2050
#!   in_orig_cnty_list,  in_tons_2024,  ..., in_sum_value_2050
#!   Per-SCTG columns append _<sctgXXXX>
#! ============================================================================================

import pandas as pd
import geopandas as gpd
import os

# ------------------------------------------------------------- 
# Base paths (same pattern you used earlier) 
# -------------------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

# --------------------------------------------------
# File paths
# --------------------------------------------------
csv_path = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "county_level_all_categories.csv"
)

shp_path = os.path.join(
    base_dir,
    "Shapefiles", "tl_2024_us_county",
    "tl_2024_us_county.shp"
)

output_path = os.path.join(
    os.path.dirname(csv_path),
    "county_level_with_faf_flows.gpkg"
)

# --------------------------------------------------
# Read data
# --------------------------------------------------
df = pd.read_csv(csv_path)
gdf = gpd.read_file(shp_path)

# --------------------------------------------------
# Normalize IDs
# --------------------------------------------------
gdf["GEOID_INT"] = gdf["GEOID"].astype(str).str.lstrip("0").astype(int)

df["dms_orig_cnty"] = df["dms_orig_cnty"].astype(int)
df["dms_dest_cnty"] = df["dms_dest_cnty"].astype(int)

# --------------------------------------------------
# Helper: ordered OD vectorization
# --------------------------------------------------
def vectorize_flows(sub_df, other_col):
    g = (
        sub_df
        .groupby(other_col)[
            ["tons_2024", "tons_2050", "value_2024", "value_2050"]
        ]
        .sum()
        .sort_index()
    )

    return pd.Series({
        f"{other_col}_list": ",".join(g.index.astype(str)),
        "tons_2024": ",".join(g["tons_2024"].round(6).astype(str)),
        "tons_2050": ",".join(g["tons_2050"].round(6).astype(str)),
        "value_2024": ",".join(g["value_2024"].round(6).astype(str)),
        "value_2050": ",".join(g["value_2050"].round(6).astype(str)),
        "sum_tons_2024": g["tons_2024"].sum(),
        "sum_tons_2050": g["tons_2050"].sum(),
        "sum_value_2024": g["value_2024"].sum(),
        "sum_value_2050": g["value_2050"].sum(),
    })

# --------------------------------------------------
# GLOBAL OUT FLOWS
# --------------------------------------------------
out_all = (
    df.groupby("dms_orig_cnty")
      .apply(lambda x: vectorize_flows(x, "dms_dest_cnty"))
      .reset_index()
      .rename(columns={"dms_orig_cnty": "GEOID_INT"})
)

out_all = out_all.rename(columns={
    "dms_dest_cnty_list": "out_dest_cnty_list",
    "tons_2024": "out_tons_2024",
    "tons_2050": "out_tons_2050",
    "value_2024": "out_value_2024",
    "value_2050": "out_value_2050",
    "sum_tons_2024": "out_sum_tons_2024",
    "sum_tons_2050": "out_sum_tons_2050",
    "sum_value_2024": "out_sum_value_2024",
    "sum_value_2050": "out_sum_value_2050",
})

# --------------------------------------------------
# GLOBAL IN FLOWS
# --------------------------------------------------
in_all = (
    df.groupby("dms_dest_cnty")
      .apply(lambda x: vectorize_flows(x, "dms_orig_cnty"))
      .reset_index()
      .rename(columns={"dms_dest_cnty": "GEOID_INT"})
)

in_all = in_all.rename(columns={
    "dms_orig_cnty_list": "in_orig_cnty_list",
    "tons_2024": "in_tons_2024",
    "tons_2050": "in_tons_2050",
    "value_2024": "in_value_2024",
    "value_2050": "in_value_2050",
    "sum_tons_2024": "in_sum_tons_2024",
    "sum_tons_2050": "in_sum_tons_2050",
    "sum_value_2024": "in_sum_value_2024",
    "sum_value_2050": "in_sum_value_2050",
})

# --------------------------------------------------
# PER-SCTG FLOWS
# --------------------------------------------------
out_sctg_tables = []
in_sctg_tables = []

for sctg in sorted(df["sctgg5"].unique()):
    sub = df[df["sctgg5"] == sctg]

    # OUT
    o = (
        sub.groupby("dms_orig_cnty")
           .apply(lambda x: vectorize_flows(x, "dms_dest_cnty"))
           .reset_index()
           .rename(columns={"dms_orig_cnty": "GEOID_INT"})
    )
    o = o.rename(columns={
        "dms_dest_cnty_list": f"out_dest_cnty_list_{sctg}",
        "tons_2024": f"out_tons_2024_{sctg}",
        "tons_2050": f"out_tons_2050_{sctg}",
        "value_2024": f"out_value_2024_{sctg}",
        "value_2050": f"out_value_2050_{sctg}",
        "sum_tons_2024": f"out_sum_tons_2024_{sctg}",
        "sum_tons_2050": f"out_sum_tons_2050_{sctg}",
        "sum_value_2024": f"out_sum_value_2024_{sctg}",
        "sum_value_2050": f"out_sum_value_2050_{sctg}",
    })
    out_sctg_tables.append(o)

    # IN
    i = (
        sub.groupby("dms_dest_cnty")
           .apply(lambda x: vectorize_flows(x, "dms_orig_cnty"))
           .reset_index()
           .rename(columns={"dms_dest_cnty": "GEOID_INT"})
    )
    i = i.rename(columns={
        "dms_orig_cnty_list": f"in_orig_cnty_list_{sctg}",
        "tons_2024": f"in_tons_2024_{sctg}",
        "tons_2050": f"in_tons_2050_{sctg}",
        "value_2024": f"in_value_2024_{sctg}",
        "value_2050": f"in_value_2050_{sctg}",
        "sum_tons_2024": f"in_sum_tons_2024_{sctg}",
        "sum_tons_2050": f"in_sum_tons_2050_{sctg}",
        "sum_value_2024": f"in_sum_value_2024_{sctg}",
        "sum_value_2050": f"in_sum_value_2050_{sctg}",
    })
    in_sctg_tables.append(i)

# --------------------------------------------------
# Merge everything
# --------------------------------------------------
gdf = gdf.merge(out_all, on="GEOID_INT", how="left")
gdf = gdf.merge(in_all,  on="GEOID_INT", how="left")

for t in out_sctg_tables:
    gdf = gdf.merge(t, on="GEOID_INT", how="left")

for t in in_sctg_tables:
    gdf = gdf.merge(t, on="GEOID_INT", how="left")

gdf = gdf.drop(columns=["GEOID_INT"])

# --------------------------------------------------
# Save GeoPackage
# --------------------------------------------------
gdf.to_file(
    output_path,
    layer="county_faf_flows",
    driver="GPKG"
)

print("✅ GeoPackage successfully created")
print("📦 Output:", output_path)
print(f"📊 Total columns: {len(gdf.columns)}")

# %%
#! ============================================================================================
#! 6
#! Sanity Check: Validation of County-Level FAF OD GeoPackage Outputs Against Main CSV OD File
#! ============================================================================================

import pandas as pd
import geopandas as gpd

# ------------------------------------------------------------- 
# Base paths (same pattern you used earlier) 
# -------------------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

# --------------------------------------------------
# Paths
# --------------------------------------------------
csv_path = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "county_level_all_categories.csv"
)

gpkg_path = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "county_level_with_faf_flows.gpkg"
)

# --------------------------------------------------
# Check parameters
# --------------------------------------------------
ORIG = 41005
DEST = 4019
SCTG = "sctg0109"

# --------------------------------------------------
# LONG TABLE (ground truth)
# --------------------------------------------------
df = pd.read_csv(csv_path)

df["dms_orig_cnty"] = df["dms_orig_cnty"].astype(int)
df["dms_dest_cnty"] = df["dms_dest_cnty"].astype(int)

df_chk = df[
    (df["dms_orig_cnty"] == ORIG) &
    (df["dms_dest_cnty"] == DEST) &
    (df["sctgg5"] == SCTG)
]

true_tons  = df_chk["tons_2024"].sum()
true_value = df_chk["value_2024"].sum()

print("CSV truth")
print("tons_2024 :", true_tons)
print("value_2024:", true_value)

# --------------------------------------------------
# WIDE TABLE (GeoPackage vectors)
# --------------------------------------------------
gdf = gpd.read_file(gpkg_path, layer="county_faf_flows")

row = gdf[gdf["GEOID"] == f"{ORIG:05d}"].iloc[0]

dest_list = list(
    map(int, row[f"out_dest_cnty_list_{SCTG}"].split(","))
)

tons_list = list(
    map(float, row[f"out_tons_2024_{SCTG}"].split(","))
)

value_list = list(
    map(float, row[f"out_value_2024_{SCTG}"].split(","))
)

tons_map  = dict(zip(dest_list, tons_list))
value_map = dict(zip(dest_list, value_list))

print("\nGPKG vector")
print("tons_2024 :", tons_map[DEST])
print("value_2024:", value_map[DEST])

# --------------------------------------------------
# Difference
# --------------------------------------------------
print("\nDIFF")
print("tons diff :", tons_map[DEST] - true_tons)
print("value diff:", value_map[DEST] - true_value)

# Print the total rows in the df that has non-zero tons_2024
nonzero_rows = df[df["tons_2024"] > 0]
print(f"\nTotal non-zero tons_2024 rows in CSV: {len(nonzero_rows):,}")

# %%
#! ============================================================
#! 7
#! Sanity Check: Global IN / OUT Totals (ALL Counties, ALL SCTGs)
#! ============================================================

import geopandas as gpd

# ------------------------------------------------------------- 
# Base paths (same pattern you used earlier) 
# -------------------------------------------------------------
base_dir = os.path.abspath(os.path.join("..", ".."))

# --------------------------------------------------
# Path
# --------------------------------------------------
gpkg_path = os.path.join(
    base_dir,
    "13_Resiliency", "FAF", "Processed_Data", "County_Level",
    "county_level_with_faf_flows.gpkg"
)

# --------------------------------------------------
# Read GeoPackage
# --------------------------------------------------
gdf = gpd.read_file(gpkg_path, layer="county_faf_flows")

# --------------------------------------------------
# OUT totals (all counties)
# --------------------------------------------------
out_tons_2024  = gdf["out_sum_tons_2024"].sum()
out_value_2024 = gdf["out_sum_value_2024"].sum()
out_tons_2050  = gdf["out_sum_tons_2050"].sum()
out_value_2050 = gdf["out_sum_value_2050"].sum()

# --------------------------------------------------
# IN totals (all counties)
# --------------------------------------------------
in_tons_2024  = gdf["in_sum_tons_2024"].sum()
in_value_2024 = gdf["in_sum_value_2024"].sum()
in_tons_2050  = gdf["in_sum_tons_2050"].sum()
in_value_2050 = gdf["in_sum_value_2050"].sum()

# --------------------------------------------------
# Print results
# --------------------------------------------------
print("GLOBAL TOTALS — GEO PACKAGE")
print("--------------------------------------------------")

print("\nOUT FLOWS")
print(f"tons 2024  : {out_tons_2024:,.4f}")
print(f"value 2024 : {out_value_2024:,.4f}")
print(f"tons 2050  : {out_tons_2050:,.4f}")
print(f"value 2050 : {out_value_2050:,.4f}")

print("\nIN FLOWS")
print(f"tons 2024  : {in_tons_2024:,.4f}")
print(f"value 2024 : {in_value_2024:,.4f}")
print(f"tons 2050  : {in_tons_2050:,.4f}")
print(f"value 2050 : {in_value_2050:,.4f}")

print("\nOUT + IN TOTALS")
print(f"tons 2024  : {(out_tons_2024 + in_tons_2024):,.4f}")
print(f"value 2024 : {(out_value_2024 + in_value_2024):,.4f}")
print(f"tons 2050  : {(out_tons_2050 + in_tons_2050):,.4f}")
print(f"value 2050 : {(out_value_2050 + in_value_2050):,.4f}")

# %%
# print the maximum value of the toms_2024 column
max_tons_2024 = gdf["out_sum_tons_2024"].max()
print(f"\nMaximum out_sum_tons_2024 in any county: {max_tons_2024:,.4f}")