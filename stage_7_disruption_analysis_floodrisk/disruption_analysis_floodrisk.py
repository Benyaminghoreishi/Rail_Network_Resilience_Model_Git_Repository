# %% [markdown]
# # Flood-Risk Disruption Analysis  (Links only)
# Four independent blocks — run each cell on its own.
# Block 1 → Spatial join: risk scores onto flow-network LINKS only → save enriched GPKG + CSV
# Block 2 → FloodRisk_Max: disruption + resilience + plots
# Block 3 → FloodRisk_Sum: disruption + resilience + plots
# Block 4 → Combined comparison figures (Max vs Sum on one figure per metric)

# %%
# ============================================================================
# BLOCK 1 – Spatial Join: FRA Risk Segments → Flow-Network Links
# ============================================================================
#
# Reads:
#   * Rail_Segments_FlashFlood_WithRiskScores.gpkg  (original FRA segments)
#   * links_with_flows.gpkg / .csv                  (merged flow-network links)
#
# Any FRA segment that spatially intersects a merged link (even 1 m) transfers:
#   link_Max_Risk_Score = MAX of all intersecting FRA Max_Risk_Score values
#   link_Sum_Risk_Score = SUM of all intersecting FRA Sum_Risk_Score values
#   n_risk_segments     = count of intersecting FRA segments
#
# Saves (new files — originals untouched):
#   links_with_flows_riskscores.csv
#   links_with_flows_riskscores.gpkg
#
# Skip guard: if output CSV already exists, block prints a message and stops.
# Delete the CSV to re-run the spatial join.
# ============================================================================

import geopandas as gpd
import pandas as pd
import os, time, gc, warnings
warnings.filterwarnings("ignore")

def fmt_time(s):
    s = max(0, int(s))
    h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else (f"{m}m {s:02d}s" if m else f"{s}s")

# ── Paths ─────────────────────────────────────────────────────────────────────
base_dir = os.path.abspath(os.path.join("..", ".."))
inputs   = os.path.join(base_dir, "13_Resiliency", "FAF",
                        "Processed_Data", "County_Level",
                        "Disruption_Scenario_Inputs")

FLOOD_RISK_GPKG       = (
    r"C:\Users\ghoreisb\Box\Oregon State University\000- Papers&Posters"
    r"\Publish Purpose\2025\TRB2026\RailRoad"
    r"\Assigning_HUC12_to_Railroad\Rail_Segments_FlashFlood_WithRiskScores.gpkg"
)
LINKS_WITH_FLOWS_CSV  = os.path.join(inputs, "links_with_flows.csv")
LINKS_WITH_FLOWS_GPKG = os.path.join(inputs, "links_with_flows.gpkg")
LINKS_RISK_CSV        = os.path.join(inputs, "links_with_flows_riskscores.csv")
LINKS_RISK_GPKG       = os.path.join(inputs, "links_with_flows_riskscores.gpkg")

os.makedirs(inputs, exist_ok=True)

print("=" * 70)
print("BLOCK 1 – Spatial join: flood-risk scores → flow-network links")
print("=" * 70)

if os.path.exists(LINKS_RISK_CSV):
    print(f"  Output already exists — skipping.")
    print(f"  Delete {LINKS_RISK_CSV} to re-run.")
else:
    print("  Reading flood-risk shapefile ...")
    gdf_risk = gpd.read_file(FLOOD_RISK_GPKG)
    print(f"  Risk segments : {len(gdf_risk):,}   CRS: {gdf_risk.crs}")

    for col in ["Max_Risk_Score", "Sum_Risk_Score"]:
        if col not in gdf_risk.columns:
            raise ValueError(
                f"Column '{col}' not found in risk shapefile.\n"
                f"Available: {list(gdf_risk.columns)}")

    gdf_risk = (gdf_risk[["geometry", "Max_Risk_Score", "Sum_Risk_Score"]]
                .dropna(subset=["geometry"]).copy())

    print("  Reading flow-network links ...")
    gdf_links = gpd.read_file(LINKS_WITH_FLOWS_GPKG)
    if "edge_fid" not in gdf_links.columns:
        gdf_links = (gdf_links.reset_index(drop=False)
                              .rename(columns={"index": "edge_fid"}))
    print(f"  Flow links    : {len(gdf_links):,}   CRS: {gdf_links.crs}")

    if gdf_risk.crs != gdf_links.crs:
        print(f"  Reprojecting risk {gdf_risk.crs} to {gdf_links.crs} ...")
        gdf_risk = gdf_risk.to_crs(gdf_links.crs)

    print("  Spatial join links x risk (intersects) ...")
    t0     = time.time()
    joined = gpd.sjoin(
        gdf_links[["edge_fid", "geometry"]],
        gdf_risk[["Max_Risk_Score", "Sum_Risk_Score", "geometry"]],
        how="left", predicate="intersects",
    )
    print(f"  sjoin rows    : {len(joined):,}   ({fmt_time(time.time()-t0)})")

    agg = (joined
           .groupby("edge_fid", as_index=False)
           .agg(
               link_Max_Risk_Score=("Max_Risk_Score", "max"),
               link_Sum_Risk_Score=("Sum_Risk_Score", "sum"),
               n_risk_segments    =("Max_Risk_Score", "count"),
           ))
    agg["link_Max_Risk_Score"] = agg["link_Max_Risk_Score"].fillna(0.0)
    agg["link_Sum_Risk_Score"] = agg["link_Sum_Risk_Score"].fillna(0.0)
    agg["n_risk_segments"]     = agg["n_risk_segments"].fillna(0).astype(int)
    del joined

    df_csv = pd.read_csv(LINKS_WITH_FLOWS_CSV)
    if "edge_fid" not in df_csv.columns:
        df_csv = df_csv.reset_index(drop=False).rename(columns={"index": "edge_fid"})
    df_csv = df_csv.merge(agg, on="edge_fid", how="left")
    df_csv["link_Max_Risk_Score"] = df_csv["link_Max_Risk_Score"].fillna(0.0)
    df_csv["link_Sum_Risk_Score"] = df_csv["link_Sum_Risk_Score"].fillna(0.0)
    df_csv["n_risk_segments"]     = df_csv["n_risk_segments"].fillna(0).astype(int)

    gdf_out = gdf_links.merge(
        agg[["edge_fid", "link_Max_Risk_Score",
             "link_Sum_Risk_Score", "n_risk_segments"]],
        on="edge_fid", how="left")
    gdf_out["link_Max_Risk_Score"] = gdf_out["link_Max_Risk_Score"].fillna(0.0)
    gdf_out["link_Sum_Risk_Score"] = gdf_out["link_Sum_Risk_Score"].fillna(0.0)
    gdf_out["n_risk_segments"]     = gdf_out["n_risk_segments"].fillna(0).astype(int)

    n_with = int((df_csv["link_Max_Risk_Score"] > 0).sum())
    print(f"  Links with risk > 0 : {n_with:,} / {len(df_csv):,}")

    df_csv.to_csv(LINKS_RISK_CSV, index=False)
    gdf_out.to_file(LINKS_RISK_GPKG, driver="GPKG")
    print(f"  CSV  saved: {LINKS_RISK_CSV}")
    print(f"  GPKG saved: {LINKS_RISK_GPKG}")

    del gdf_risk, gdf_links, gdf_out, df_csv, agg
    gc.collect()

df_check = pd.read_csv(LINKS_RISK_CSV)
print(f"\n  Score summary (links):")
print(f"    Max_Risk_Score : {df_check['link_Max_Risk_Score'].min():.4f} - "
      f"{df_check['link_Max_Risk_Score'].max():.4f}   "
      f"non-zero: {(df_check['link_Max_Risk_Score'] > 0).sum():,}")
print(f"    Sum_Risk_Score : {df_check['link_Sum_Risk_Score'].min():.4f} - "
      f"{df_check['link_Sum_Risk_Score'].max():.4f}   "
      f"non-zero: {(df_check['link_Sum_Risk_Score'] > 0).sum():,}")
del df_check
print("\n  BLOCK 1 COMPLETE\n")


# %%
# ============================================================================
# BLOCK 2 – FloodRisk_Max: Disruption + Resilience + Plots
# ============================================================================
#
# Ranks merged links by link_Max_Risk_Score descending.
# Step k = remove ALL links whose score equals the k-th highest unique value
#          (cumulative: all previous steps always included).
# TOP_N_MAX           : number of unique score levels to step through.
# GPKG_SAVE_STEPS_MAX : step numbers that get a GPKG saved.
#
# GPKG layers per saved step (links only — no nodes layer):
#   remaining_links : post-disruption flow_value_2024_day / flow_tons_2024_day
#   disrupted_links : same columns (flows = 0 on removed links)
#
# Outputs:
#   Disruption_Scenarios_FloodRisk/FloodRisk_Max/step<NNN>/
#     od_paths_FloodRisk_Max_step<NNN>.csv
#     network_FloodRisk_Max_step<NNN>.gpkg    (selected steps only)
#   Resilience_Analysis_FloodRisk/
#     steps_FloodRisk_Max.csv
#     resilience_summary_FloodRisk_Max.csv
#     figures/
#       F_FloodRisk_Max.png
#       reachability_FloodRisk_Max.png
#       value_infeasible_FloodRisk_Max.png
#       cumul_links_FloodRisk_Max.png
#       od_classification_FloodRisk_Max.png
# ============================================================================

import geopandas as gpd
import pandas as pd
import networkx as nx
import os, time, gc, warnings
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
warnings.filterwarnings("ignore")

def fmt_time(s):
    s = max(0, int(s))
    h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else (f"{m}m {s:02d}s" if m else f"{s}s")

class StepTimer:
    def __init__(self, total, label=""):
        self.total = total; self.label = label; self.done = 0
        self.t_start = time.time(); self._last_mile = -1
    def tick(self, note=""):
        self.done += 1
        el  = time.time() - self.t_start
        eta = (el / self.done) * (self.total - self.done)
        pct = self.done / self.total * 100
        mile = int(pct // 25) * 25
        if mile != self._last_mile or self.done == self.total:
            self._last_mile = mile
            filled = int(28 * self.done / self.total)
            bar = "#" * filled + "." * (28 - filled)
            ns  = f"  <- {note}" if note else ""
            print(f"  [{bar}] {self.done}/{self.total} ({pct:.0f}%)  "
                  f"elapsed {fmt_time(el)}  ETA {fmt_time(eta)}{ns}")
    def summary(self):
        e = time.time() - self.t_start
        print(f"  {self.label} complete - {self.done} runs  "
              f"total {fmt_time(e)}  avg {fmt_time(e/max(self.done,1))}/run\n")

# ── Configuration ─────────────────────────────────────────────────────────────
SPEED_MPH           = 49.0
TOP_N_MAX           = 50
GPKG_SAVE_STEPS_MAX = [1, 5, 10, 20, 30, 40, 50]
SAVE_COLS = ["origin_franodeid", "destination_franodeid",
             "value_2024_day", "value_hours_2024", "travel_time_hours"]
SCENARIO_NAME = "FloodRisk_Max"
SCORE_COL     = "link_Max_Risk_Score"

# ── Paths ─────────────────────────────────────────────────────────────────────
base_dir = os.path.abspath(os.path.join("..", ".."))
county   = os.path.join(base_dir, "13_Resiliency", "FAF",
                        "Processed_Data", "County_Level")
inputs   = os.path.join(county, "Disruption_Scenario_Inputs")

BASELINE_CSV    = os.path.join(county, "rail_od_paths_daily_COMBINED.csv")
RAIL_GRAPH_GPKG = os.path.join(county, "Rail_Graph", "Rail_Graph_Nodes_Edges.gpkg")
LINKS_RISK_CSV  = os.path.join(inputs, "links_with_flows_riskscores.csv")
LINKS_RISK_GPKG = os.path.join(inputs, "links_with_flows_riskscores.gpkg")

DISRUPTION_DIR  = os.path.join(county, "Disruption_Scenarios_FloodRisk", SCENARIO_NAME)
RESILIENCE_DIR  = os.path.join(county, "Resilience_Analysis_FloodRisk")
FIGURES_DIR     = os.path.join(RESILIENCE_DIR, "figures")
for d in [DISRUPTION_DIR, RESILIENCE_DIR, FIGURES_DIR]:
    os.makedirs(d, exist_ok=True)

print("=" * 70)
print(f"BLOCK 2 - {SCENARIO_NAME}: disruption + resilience + plots")
print("=" * 70)

df_baseline = pd.read_csv(BASELINE_CSV)
print(f"  Baseline OD rows : {len(df_baseline):,}")
assert "path_link_fids" in df_baseline.columns, "path_link_fids missing"
assert "path_node_fids" in df_baseline.columns, "path_node_fids missing"

gdf_edges = (gpd.read_file(RAIL_GRAPH_GPKG, layer="edges")
               .reset_index(drop=False)
               .rename(columns={"index": "edge_fid"}))
print(f"  Graph edges      : {len(gdf_edges):,}")

df_links_risk = pd.read_csv(LINKS_RISK_CSV)
assert SCORE_COL in df_links_risk.columns, \
    f"{SCORE_COL} missing - run Block 1 first."

# ── Build cumulative disruption steps ─────────────────────────────────────────
def build_steps(df, score_col, top_n):
    df_c   = df[df[score_col] > 0].copy()
    scores = sorted(df_c[score_col].unique(), reverse=True)[:top_n]
    steps  = []; cumul = set()
    for i, v in enumerate(scores, 1):
        new   = set(df_c.loc[df_c[score_col] == v, "edge_fid"].tolist())
        cumul = cumul | new
        steps.append({"step": i, "score_value": v,
                      "cumul_fids": set(cumul),
                      "n_new": len(new), "n_cumul": len(cumul)})
    return steps

steps = build_steps(df_links_risk, SCORE_COL, TOP_N_MAX)
print(f"  Steps built      : {len(steps)}  "
      f"(scores {steps[0]['score_value']:.4f} to {steps[-1]['score_value']:.4f})")
pd.DataFrame([{"step": s["step"], "score_value": s["score_value"],
               "n_new": s["n_new"], "n_cumul": s["n_cumul"]}
              for s in steps]).to_csv(
    os.path.join(RESILIENCE_DIR, f"steps_{SCENARIO_NAME}.csv"), index=False)

# ── Spatial layer + baseline flow dicts (links only) ──────────────────────────
gdf_links_geo = None
_bl_lf = {}   # edge_fid -> baseline flow_value_2024_day
_bl_lt = {}   # edge_fid -> baseline flow_tons_2024_day

if GPKG_SAVE_STEPS_MAX:
    print("  Loading links spatial layer ...")
    gdf_links_geo = gpd.read_file(LINKS_RISK_GPKG).to_crs(epsg=4326)
    if "edge_fid" not in gdf_links_geo.columns:
        gdf_links_geo = (gdf_links_geo.reset_index(drop=False)
                                       .rename(columns={"index": "edge_fid"}))
    print(f"  Spatial links    : {len(gdf_links_geo):,}")

    CHUNK  = 50_000
    n_rows = len(df_baseline)
    print("  Building baseline link flow dicts (chunked, no explode) ...")
    _t0 = time.time()
    for _s in range(0, n_rows, CHUNK):
        for _, r in df_baseline.iloc[_s:_s + CHUNK].iterrows():
            _v  = r["value_2024_day"]
            _t  = r["tons_2024_day"]
            _lnk = r.get("path_link_fids", "")
            if not (pd.isna(_lnk) or str(_lnk).strip() in ("", "nan")):
                for x in str(_lnk).split(","):
                    x = x.strip()
                    if x:
                        try:
                            f = int(x)
                            _bl_lf[f] = _bl_lf.get(f, 0.) + _v
                            _bl_lt[f] = _bl_lt.get(f, 0.) + _t
                        except ValueError:
                            pass
        pct = min(_s + CHUNK, n_rows) / n_rows * 100
        print(f"    {min(_s+CHUNK,n_rows):,}/{n_rows:,} ({pct:.0f}%)",
              end="\r", flush=True)
    print(f"\n  Link dicts ready : {len(_bl_lf):,} links  "
          f"({fmt_time(time.time()-_t0)})")
print()

# ── Helpers ───────────────────────────────────────────────────────────────────
def build_graph(gdf_sub):
    G = nx.Graph()
    for _, e in gdf_sub.iterrows():
        u, v = e["FRFRANODE"], e["TOFRANODE"]
        if pd.isna(u) or pd.isna(v): continue
        G.add_edge(u, v, weight=e["LENGTH"] / 1609.344)
    return G

def affected_mask(df, dis_set):
    def chk(s):
        if pd.isna(s) or str(s).strip() in ("", "nan"): return False
        return bool({int(x) for x in str(s).split(",") if x.strip()} & dis_set)
    return df["path_link_fids"].apply(chk)

def make_record(row, dist):
    t = np.inf if dist is None else dist / SPEED_MPH
    rec = {"origin_franodeid":      row["origin_franodeid"],
           "destination_franodeid": row["destination_franodeid"],
           "value_2024_day":        row["value_2024_day"],
           "value_hours_2024":      np.inf if np.isinf(t) else row["value_2024_day"] * t,
           "travel_time_hours":     t}
    return {k: v for k, v in rec.items() if k in SAVE_COLS}

# (u,v) -> edge_fid lookup for rerouted path tracking
_ekf = {tuple(sorted((int(r["FRFRANODE"]), int(r["TOFRANODE"])))): int(r["edge_fid"])
        for _, r in gdf_edges.iterrows()
        if not (pd.isna(r["FRFRANODE"]) or pd.isna(r["TOFRANODE"]))}


def reroute(G_dis, df_aff, acc=False):
    """
    Dijkstra reroute. When acc=True accumulates 4 link-only flow dicts
    in one pass (no node dicts, no explode):
      lf_re : link value flows on NEW (rerouted) paths
      lt_re : link tons  flows on NEW paths
      lf_or : link value flows on ORIGINAL paths of affected OD pairs
      lt_or : link tons  flows on ORIGINAL paths
    Returns (df_out, lf_re, lt_re, lf_or, lt_or)
    All dicts are None when acc=False.
    """
    records = []
    lf_re = lt_re = lf_or = lt_or = None
    if acc:
        lf_re = {}; lt_re = {}; lf_or = {}; lt_or = {}

    groups = list(df_aff.groupby("origin_franodeid"))
    n = len(groups); t0 = time.time(); lm = -1

    for i, (origin, grp) in enumerate(groups, 1):
        pct  = i / n * 100; mile = int(pct // 25) * 25
        if mile != lm or i == n:
            lm = mile; el = time.time() - t0
            eta = (el / i) * (n - i) if i < n else 0
            print(f"      reroute {i:,}/{n:,} ({pct:.0f}%)  "
                  f"elapsed {fmt_time(el)}  ETA {fmt_time(eta)}")

        # Accumulate ORIGINAL link flows
        if acc:
            for _, row in grp.iterrows():
                v = row["value_2024_day"]; t = row["tons_2024_day"]
                s = row.get("path_link_fids", "")
                if not (pd.isna(s) or str(s).strip() in ("", "nan")):
                    for x in str(s).split(","):
                        x = x.strip()
                        if x:
                            f = int(x)
                            lf_or[f] = lf_or.get(f, 0.) + v
                            lt_or[f] = lt_or.get(f, 0.) + t

        if origin not in G_dis:
            for _, row in grp.iterrows():
                records.append(make_record(row, None))
            continue
        try:
            if acc: lengths, paths = nx.single_source_dijkstra(G_dis, origin, weight="weight")
            else:   lengths, _     = nx.single_source_dijkstra(G_dis, origin, weight="weight")
        except Exception:
            for _, row in grp.iterrows():
                records.append(make_record(row, None))
            continue

        for _, row in grp.iterrows():
            dest = row["destination_franodeid"]
            dist = lengths.get(dest)
            v    = row["value_2024_day"]
            records.append(make_record(row, dist))

            # Accumulate REROUTED link flows
            if acc and dist is not None:
                t   = row["tons_2024_day"]
                np_ = paths[dest]
                for k in range(len(np_) - 1):
                    ek = tuple(sorted((np_[k], np_[k + 1])))
                    f  = _ekf.get(ek)
                    if f is not None:
                        lf_re[f] = lf_re.get(f, 0.) + v
                        lt_re[f] = lt_re.get(f, 0.) + t

    print(f"      done - {len(records):,} rows  {fmt_time(time.time()-t0)}")
    return pd.DataFrame(records), lf_re, lt_re, lf_or, lt_or


def save_gpkg(dis_ids, step_label, out_dir, lf_re, lt_re, lf_or, lt_or):
    """
    Write GPKG with two layers: remaining_links and disrupted_links.
    post_flow = baseline - orig_affected + rerouted
    Flow columns:
      flow_value_2024_day / flow_value_2024_day_baseline
      flow_tons_2024_day  / flow_tons_2024_day_baseline
    gdf_links_geo updated in-place and restored in finally block.
    """
    path = os.path.join(out_dir, f"network_{SCENARIO_NAME}_{step_label}.gpkg")

    all_lf  = set(_bl_lf) | set(lf_or or {}) | set(lf_re or {})
    lv_post = {f: max(0., _bl_lf.get(f, 0.)
                         - (lf_or or {}).get(f, 0.)
                         + (lf_re or {}).get(f, 0.))
               for f in all_lf}

    all_lt  = set(_bl_lt) | set(lt_or or {}) | set(lt_re or {})
    lt_post = {f: max(0., _bl_lt.get(f, 0.)
                         - (lt_or or {}).get(f, 0.)
                         + (lt_re or {}).get(f, 0.))
               for f in all_lt}

    gdf_links_geo["flow_value_2024_day_baseline"] = gdf_links_geo["flow_value_2024_day"]
    gdf_links_geo["flow_value_2024_day"]          = gdf_links_geo["edge_fid"].map(lv_post).fillna(0.)
    gdf_links_geo["flow_tons_2024_day_baseline"]  = gdf_links_geo["flow_tons_2024_day"]
    gdf_links_geo["flow_tons_2024_day"]           = gdf_links_geo["edge_fid"].map(lt_post).fillna(0.)

    try:
        dm = gdf_links_geo["edge_fid"].isin(dis_ids)
        gdf_links_geo[~dm].to_file(path, layer="remaining_links", driver="GPKG")
        gdf_links_geo[ dm].to_file(path, layer="disrupted_links", driver="GPKG")
    finally:
        gdf_links_geo["flow_value_2024_day"] = gdf_links_geo["flow_value_2024_day_baseline"]
        gdf_links_geo["flow_tons_2024_day"]  = gdf_links_geo["flow_tons_2024_day_baseline"]
        gdf_links_geo.drop(columns=["flow_value_2024_day_baseline",
                                    "flow_tons_2024_day_baseline"], inplace=True)
    print(f"      GPKG saved: {path}")


# ── Run scenario ───────────────────────────────────────────────────────────────
timer = StepTimer(total=len(steps), label=SCENARIO_NAME)
for si in steps:
    sn      = si["step"]; sl = f"step{sn:03d}"
    sd      = os.path.join(DISRUPTION_DIR, sl); os.makedirs(sd, exist_ok=True)
    csv_out = os.path.join(sd, f"od_paths_{SCENARIO_NAME}_{sl}.csv")
    print(f"\n  -- {SCENARIO_NAME} step {sn:>3}  "
          f"score={si['score_value']:.4f}  cumul_links={si['n_cumul']:,} --")

    if os.path.exists(csv_out):
        print("      exists - skipping")
        timer.tick(note=f"skip step {sn}"); continue

    mask   = affected_mask(df_baseline, si["cumul_fids"])
    df_aff = df_baseline[mask].copy(); n_aff = len(df_aff)
    print(f"      Affected OD pairs : {n_aff:,} ({n_aff/len(df_baseline)*100:.1f}%)")
    need_gpkg = sn in GPKG_SAVE_STEPS_MAX and gdf_links_geo is not None

    if n_aff == 0:
        pd.DataFrame(columns=SAVE_COLS).to_csv(csv_out, index=False)
        lf_re = lt_re = lf_or = lt_or = {}
    else:
        G_dis = build_graph(gdf_edges[~gdf_edges["edge_fid"].isin(si["cumul_fids"])])
        print(f"      Graph: {G_dis.number_of_nodes():,} nodes  "
              f"{G_dis.number_of_edges():,} edges")
        df_out, lf_re, lt_re, lf_or, lt_or = reroute(G_dis, df_aff, acc=need_gpkg)
        del G_dis; gc.collect()

        df_out[[c for c in SAVE_COLS if c in df_out.columns]].to_csv(csv_out, index=False)
        ni = int(np.isinf(df_out["value_hours_2024"]).sum())
        print(f"      Saved {len(df_out):,} rows  "
              f"infeasible {ni:,}  rerouted {len(df_out)-ni:,}")
        del df_out; gc.collect()

    if need_gpkg:
        save_gpkg(si["cumul_fids"], sl, sd, lf_re, lt_re, lf_or, lt_or)

    del df_aff, lf_re, lt_re, lf_or, lt_or; gc.collect()
    timer.tick(note=f"step {sn}")
timer.summary()

# ── Resilience metrics ─────────────────────────────────────────────────────────
print("  Computing resilience metrics ...")
K     = len(df_baseline)
df_bl = df_baseline[["origin_franodeid", "destination_franodeid",
                      "value_hours_2024", "value_2024_day"]].rename(
    columns={"value_hours_2024": "vh_bl", "value_2024_day": "val_bl"})
# Deduplicate baseline: if (origin, destination) appears more than once,
# keep the row with the highest vh_bl (most conservative baseline for f_k)
df_bl = df_bl.drop_duplicates(
    subset=["origin_franodeid", "destination_franodeid"], keep="first")
K = len(df_bl)   # recompute K from deduplicated baseline
print(f"  Deduplicated baseline : {K:,} unique OD pairs")
results = []
for si in steps:
    sl = f"step{si['step']:03d}"
    fp = os.path.join(DISRUPTION_DIR, sl, f"od_paths_{SCENARIO_NAME}_{sl}.csv")
    if not os.path.exists(fp): continue
    df_dis = pd.read_csv(fp)
    # Deduplicate disrupted CSV — keep worst (highest value_hours) per OD pair
    df_dis_dedup = (df_dis[["origin_franodeid", "destination_franodeid", "value_hours_2024"]]
                    .sort_values("value_hours_2024", ascending=False)
                    .drop_duplicates(subset=["origin_franodeid", "destination_franodeid"],
                                     keep="first"))
    del df_dis
    df_m = df_bl.merge(
        df_dis_dedup.rename(columns={"value_hours_2024": "vh_dis"}),
        on=["origin_franodeid", "destination_franodeid"], how="left")
    del df_dis_dedup
    # inf_ must be checked BEFORE fillna — NaN means unaffected (not in disrupted CSV)
    # inf means truly infeasible (value_hours_2024 = inf in disrupted CSV)
    inf_ = np.isinf(df_m["vh_dis"])          # True only for real infeasible rows
    df_m["vh_dis"] = df_m["vh_dis"].fillna(df_m["vh_bl"])  # unaffected -> f_k = 1

    # delta clamped to >= 0: reroutes that happen to be shorter than baseline
    # still count as unaffected (f_k = 1), never push F above 1
    delta = np.where(inf_, np.inf,
                     np.clip(df_m["vh_dis"].values - df_m["vh_bl"].values, 0.0, None))

    # f_k in [0, 1] always
    fk  = np.where(inf_, 0.0, 1.0 / (1.0 + delta))

    # classification: infeasible | delayed (delta > 0) | unaffected (delta == 0)
    cls = np.where(inf_, "infeasible",
          np.where(delta > 0, "delayed", "unaffected"))
    nu  = int((cls == "unaffected").sum())
    nd_ = int((cls == "delayed"   ).sum())
    ni  = int((cls == "infeasible").sum())
    val = df_m["val_bl"].values; del df_m
    results.append({
        "step": si["step"], "score_value": si["score_value"],
        "n_cumul_links": si["n_cumul"], "num_total": K,
        "num_unaffected": nu, "num_delayed": nd_, "num_infeasible": ni,
        "num_feasible": nu + nd_,
        "pct_unaffected": nu / K * 100, "pct_delayed": nd_ / K * 100,
        "pct_infeasible": ni / K * 100, "reachability": (nu + nd_) / K,
        "F_value_2024": float(fk.sum()) / K,
        "val_infeasible_day": float(val[cls == "infeasible"].sum()),
        "val_total_day": float(val.sum()),
    })

df_res   = pd.DataFrame(results)
summ_csv = os.path.join(RESILIENCE_DIR, f"resilience_summary_{SCENARIO_NAME}.csv")
df_res.to_csv(summ_csv, index=False)
print(f"  Summary saved: {summ_csv}  ({len(df_res)} rows)\n")

# ── Plots ──────────────────────────────────────────────────────────────────────
print("  Creating plots ...")
sns.set_style("whitegrid"); plt.rcParams["figure.dpi"] = 100
COLOR = "#E84855"

def _plot(y, ylabel, title, fname, ylim=None):
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(df_res["step"], df_res[y], marker="o", linewidth=2.5,
            markersize=6, color=COLOR, label=SCENARIO_NAME)
    ax.set_xlabel("Cumulative Flood-Risk Step  (1 = highest Max_Risk_Score)",
                  fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=13, fontweight="bold")
    ax.set_title(title,   fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=11); ax.grid(True, alpha=0.3)
    if ylim: ax.set_ylim(ylim)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, fname), dpi=300, bbox_inches="tight")
    plt.close(); print(f"    {fname}")

_plot("F_value_2024",
      "Network Functionality  F(G_d)",
      f"Network Functionality vs Flood-Risk Steps\n({SCENARIO_NAME})",
      f"F_{SCENARIO_NAME}.png", (0, 1.05))
_plot("reachability",
      "Reachability  |K_feasible| / |K|",
      f"Network Reachability vs Flood-Risk Steps\n({SCENARIO_NAME})",
      f"reachability_{SCENARIO_NAME}.png", (0, 1.05))
_plot("val_infeasible_day",
      "Daily Value Infeasible  ($M/day)",
      f"Daily Value Lost vs Flood-Risk Steps\n({SCENARIO_NAME})",
      f"value_infeasible_{SCENARIO_NAME}.png")
_plot("n_cumul_links",
      "Cumulative Disrupted Links",
      f"Cumulative Links Removed vs Step\n({SCENARIO_NAME})",
      f"cumul_links_{SCENARIO_NAME}.png")

fig, ax = plt.subplots(figsize=(12, 7)); x = df_res["step"].values
ax.fill_between(x, 0, df_res["pct_unaffected"],
                label="Unaffected", color="#90EE90", alpha=0.8)
ax.fill_between(x, df_res["pct_unaffected"],
                df_res["pct_unaffected"] + df_res["pct_delayed"],
                label="Delayed",    color="#FFD700", alpha=0.8)
ax.fill_between(x, df_res["pct_unaffected"] + df_res["pct_delayed"], 100,
                label="Infeasible", color="#FF6B6B", alpha=0.8)
ax.set_xlabel("Cumulative Flood-Risk Step", fontsize=12)
ax.set_ylabel("% of OD Pairs",             fontsize=12)
ax.set_title(f"OD Classification vs Flood-Risk Steps\n({SCENARIO_NAME})",
             fontsize=14, fontweight="bold")
ax.legend(fontsize=10); ax.grid(True, alpha=0.3); ax.set_ylim([0, 105])
plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, f"od_classification_{SCENARIO_NAME}.png"),
            dpi=300, bbox_inches="tight")
plt.close(); print(f"    od_classification_{SCENARIO_NAME}.png")

print(f"\n  BLOCK 2 COMPLETE\n")


# %%
# ============================================================================
# BLOCK 3 – FloodRisk_Sum: Disruption + Resilience + Plots
# ============================================================================
#
# Identical structure to Block 2 but ranks links by link_Sum_Risk_Score.
# TOP_N_SUM           : number of unique score levels to step through.
# GPKG_SAVE_STEPS_SUM : step numbers that get a GPKG saved.
#
# Outputs:
#   Disruption_Scenarios_FloodRisk/FloodRisk_Sum/step<NNN>/
#     od_paths_FloodRisk_Sum_step<NNN>.csv
#     network_FloodRisk_Sum_step<NNN>.gpkg    (selected steps only)
#   Resilience_Analysis_FloodRisk/
#     steps_FloodRisk_Sum.csv
#     resilience_summary_FloodRisk_Sum.csv
#     figures/
#       F_FloodRisk_Sum.png
#       reachability_FloodRisk_Sum.png
#       value_infeasible_FloodRisk_Sum.png
#       cumul_links_FloodRisk_Sum.png
#       od_classification_FloodRisk_Sum.png
# ============================================================================

import geopandas as gpd
import pandas as pd
import networkx as nx
import os, time, gc, warnings
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
warnings.filterwarnings("ignore")

def fmt_time(s):
    s = max(0, int(s))
    h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else (f"{m}m {s:02d}s" if m else f"{s}s")

class StepTimer:
    def __init__(self, total, label=""):
        self.total = total; self.label = label; self.done = 0
        self.t_start = time.time(); self._last_mile = -1
    def tick(self, note=""):
        self.done += 1
        el  = time.time() - self.t_start
        eta = (el / self.done) * (self.total - self.done)
        pct = self.done / self.total * 100; mile = int(pct // 25) * 25
        if mile != self._last_mile or self.done == self.total:
            self._last_mile = mile; filled = int(28 * self.done / self.total)
            bar = "#" * filled + "." * (28 - filled)
            ns  = f"  <- {note}" if note else ""
            print(f"  [{bar}] {self.done}/{self.total} ({pct:.0f}%)  "
                  f"elapsed {fmt_time(el)}  ETA {fmt_time(eta)}{ns}")
    def summary(self):
        e = time.time() - self.t_start
        print(f"  {self.label} complete - {self.done} runs  "
              f"total {fmt_time(e)}  avg {fmt_time(e/max(self.done,1))}/run\n")

# ── Configuration ─────────────────────────────────────────────────────────────
SPEED_MPH           = 49.0
TOP_N_SUM           = 50
GPKG_SAVE_STEPS_SUM = [1, 5, 10, 20, 30, 40, 50]
SAVE_COLS = ["origin_franodeid", "destination_franodeid",
             "value_2024_day", "value_hours_2024", "travel_time_hours"]
SCENARIO_NAME = "FloodRisk_Sum"
SCORE_COL     = "link_Sum_Risk_Score"

# ── Paths ─────────────────────────────────────────────────────────────────────
base_dir = os.path.abspath(os.path.join("..", ".."))
county   = os.path.join(base_dir, "13_Resiliency", "FAF",
                        "Processed_Data", "County_Level")
inputs   = os.path.join(county, "Disruption_Scenario_Inputs")

BASELINE_CSV    = os.path.join(county, "rail_od_paths_daily_COMBINED.csv")
RAIL_GRAPH_GPKG = os.path.join(county, "Rail_Graph", "Rail_Graph_Nodes_Edges.gpkg")
LINKS_RISK_CSV  = os.path.join(inputs, "links_with_flows_riskscores.csv")
LINKS_RISK_GPKG = os.path.join(inputs, "links_with_flows_riskscores.gpkg")

DISRUPTION_DIR  = os.path.join(county, "Disruption_Scenarios_FloodRisk", SCENARIO_NAME)
RESILIENCE_DIR  = os.path.join(county, "Resilience_Analysis_FloodRisk")
FIGURES_DIR     = os.path.join(RESILIENCE_DIR, "figures")
for d in [DISRUPTION_DIR, RESILIENCE_DIR, FIGURES_DIR]:
    os.makedirs(d, exist_ok=True)

print("=" * 70)
print(f"BLOCK 3 - {SCENARIO_NAME}: disruption + resilience + plots")
print("=" * 70)

df_baseline = pd.read_csv(BASELINE_CSV)
print(f"  Baseline OD rows : {len(df_baseline):,}")
assert "path_link_fids" in df_baseline.columns, "path_link_fids missing"
assert "path_node_fids" in df_baseline.columns, "path_node_fids missing"

gdf_edges = (gpd.read_file(RAIL_GRAPH_GPKG, layer="edges")
               .reset_index(drop=False).rename(columns={"index": "edge_fid"}))
print(f"  Graph edges      : {len(gdf_edges):,}")

df_links_risk = pd.read_csv(LINKS_RISK_CSV)
assert SCORE_COL in df_links_risk.columns, \
    f"{SCORE_COL} missing - run Block 1 first."

def build_steps(df, score_col, top_n):
    df_c   = df[df[score_col] > 0].copy()
    scores = sorted(df_c[score_col].unique(), reverse=True)[:top_n]
    steps  = []; cumul = set()
    for i, v in enumerate(scores, 1):
        new   = set(df_c.loc[df_c[score_col] == v, "edge_fid"].tolist())
        cumul = cumul | new
        steps.append({"step": i, "score_value": v,
                      "cumul_fids": set(cumul),
                      "n_new": len(new), "n_cumul": len(cumul)})
    return steps

steps = build_steps(df_links_risk, SCORE_COL, TOP_N_SUM)
print(f"  Steps built      : {len(steps)}  "
      f"(scores {steps[0]['score_value']:.4f} to {steps[-1]['score_value']:.4f})")
pd.DataFrame([{"step": s["step"], "score_value": s["score_value"],
               "n_new": s["n_new"], "n_cumul": s["n_cumul"]}
              for s in steps]).to_csv(
    os.path.join(RESILIENCE_DIR, f"steps_{SCENARIO_NAME}.csv"), index=False)

gdf_links_geo = None
_bl_lf = {}; _bl_lt = {}

if GPKG_SAVE_STEPS_SUM:
    print("  Loading links spatial layer ...")
    gdf_links_geo = gpd.read_file(LINKS_RISK_GPKG).to_crs(epsg=4326)
    if "edge_fid" not in gdf_links_geo.columns:
        gdf_links_geo = (gdf_links_geo.reset_index(drop=False)
                                       .rename(columns={"index": "edge_fid"}))
    print(f"  Spatial links    : {len(gdf_links_geo):,}")

    CHUNK  = 50_000; n_rows = len(df_baseline)
    print("  Building baseline link flow dicts (chunked, no explode) ..."); _t0 = time.time()
    for _s in range(0, n_rows, CHUNK):
        for _, r in df_baseline.iloc[_s:_s + CHUNK].iterrows():
            _v = r["value_2024_day"]; _t = r["tons_2024_day"]
            _lnk = r.get("path_link_fids", "")
            if not (pd.isna(_lnk) or str(_lnk).strip() in ("", "nan")):
                for x in str(_lnk).split(","):
                    x = x.strip()
                    if x:
                        try:
                            f = int(x)
                            _bl_lf[f] = _bl_lf.get(f, 0.) + _v
                            _bl_lt[f] = _bl_lt.get(f, 0.) + _t
                        except ValueError: pass
        pct = min(_s + CHUNK, n_rows) / n_rows * 100
        print(f"    {min(_s+CHUNK,n_rows):,}/{n_rows:,} ({pct:.0f}%)",
              end="\r", flush=True)
    print(f"\n  Link dicts ready : {len(_bl_lf):,} links  "
          f"({fmt_time(time.time()-_t0)})")
print()

def build_graph(gdf_sub):
    G = nx.Graph()
    for _, e in gdf_sub.iterrows():
        u, v = e["FRFRANODE"], e["TOFRANODE"]
        if pd.isna(u) or pd.isna(v): continue
        G.add_edge(u, v, weight=e["LENGTH"] / 1609.344)
    return G

def affected_mask(df, dis_set):
    def chk(s):
        if pd.isna(s) or str(s).strip() in ("", "nan"): return False
        return bool({int(x) for x in str(s).split(",") if x.strip()} & dis_set)
    return df["path_link_fids"].apply(chk)

def make_record(row, dist):
    t = np.inf if dist is None else dist / SPEED_MPH
    rec = {"origin_franodeid":      row["origin_franodeid"],
           "destination_franodeid": row["destination_franodeid"],
           "value_2024_day":        row["value_2024_day"],
           "value_hours_2024":      np.inf if np.isinf(t) else row["value_2024_day"] * t,
           "travel_time_hours":     t}
    return {k: v for k, v in rec.items() if k in SAVE_COLS}

_ekf = {tuple(sorted((int(r["FRFRANODE"]), int(r["TOFRANODE"])))): int(r["edge_fid"])
        for _, r in gdf_edges.iterrows()
        if not (pd.isna(r["FRFRANODE"]) or pd.isna(r["TOFRANODE"]))}

def reroute(G_dis, df_aff, acc=False):
    records = []
    lf_re = lt_re = lf_or = lt_or = None
    if acc:
        lf_re = {}; lt_re = {}; lf_or = {}; lt_or = {}
    groups = list(df_aff.groupby("origin_franodeid"))
    n = len(groups); t0 = time.time(); lm = -1
    for i, (origin, grp) in enumerate(groups, 1):
        pct = i / n * 100; mile = int(pct // 25) * 25
        if mile != lm or i == n:
            lm = mile; el = time.time() - t0
            eta = (el / i) * (n - i) if i < n else 0
            print(f"      reroute {i:,}/{n:,} ({pct:.0f}%)  "
                  f"elapsed {fmt_time(el)}  ETA {fmt_time(eta)}")
        if acc:
            for _, row in grp.iterrows():
                v = row["value_2024_day"]; t = row["tons_2024_day"]
                s = row.get("path_link_fids", "")
                if not (pd.isna(s) or str(s).strip() in ("", "nan")):
                    for x in str(s).split(","):
                        x = x.strip()
                        if x:
                            f = int(x)
                            lf_or[f] = lf_or.get(f, 0.) + v
                            lt_or[f] = lt_or.get(f, 0.) + t
        if origin not in G_dis:
            for _, row in grp.iterrows(): records.append(make_record(row, None))
            continue
        try:
            if acc: lengths, paths = nx.single_source_dijkstra(G_dis, origin, weight="weight")
            else:   lengths, _     = nx.single_source_dijkstra(G_dis, origin, weight="weight")
        except Exception:
            for _, row in grp.iterrows(): records.append(make_record(row, None))
            continue
        for _, row in grp.iterrows():
            dest = row["destination_franodeid"]; dist = lengths.get(dest)
            v    = row["value_2024_day"]; records.append(make_record(row, dist))
            if acc and dist is not None:
                t = row["tons_2024_day"]; np_ = paths[dest]
                for k in range(len(np_) - 1):
                    ek = tuple(sorted((np_[k], np_[k + 1]))); f = _ekf.get(ek)
                    if f is not None:
                        lf_re[f] = lf_re.get(f, 0.) + v
                        lt_re[f] = lt_re.get(f, 0.) + t
    print(f"      done - {len(records):,} rows  {fmt_time(time.time()-t0)}")
    return pd.DataFrame(records), lf_re, lt_re, lf_or, lt_or

def save_gpkg(dis_ids, step_label, out_dir, lf_re, lt_re, lf_or, lt_or):
    path = os.path.join(out_dir, f"network_{SCENARIO_NAME}_{step_label}.gpkg")
    all_lf  = set(_bl_lf) | set(lf_or or {}) | set(lf_re or {})
    lv_post = {f: max(0., _bl_lf.get(f, 0.)
                         - (lf_or or {}).get(f, 0.)
                         + (lf_re or {}).get(f, 0.)) for f in all_lf}
    all_lt  = set(_bl_lt) | set(lt_or or {}) | set(lt_re or {})
    lt_post = {f: max(0., _bl_lt.get(f, 0.)
                         - (lt_or or {}).get(f, 0.)
                         + (lt_re or {}).get(f, 0.)) for f in all_lt}
    gdf_links_geo["flow_value_2024_day_baseline"] = gdf_links_geo["flow_value_2024_day"]
    gdf_links_geo["flow_value_2024_day"]          = gdf_links_geo["edge_fid"].map(lv_post).fillna(0.)
    gdf_links_geo["flow_tons_2024_day_baseline"]  = gdf_links_geo["flow_tons_2024_day"]
    gdf_links_geo["flow_tons_2024_day"]           = gdf_links_geo["edge_fid"].map(lt_post).fillna(0.)
    try:
        dm = gdf_links_geo["edge_fid"].isin(dis_ids)
        gdf_links_geo[~dm].to_file(path, layer="remaining_links", driver="GPKG")
        gdf_links_geo[ dm].to_file(path, layer="disrupted_links", driver="GPKG")
    finally:
        gdf_links_geo["flow_value_2024_day"] = gdf_links_geo["flow_value_2024_day_baseline"]
        gdf_links_geo["flow_tons_2024_day"]  = gdf_links_geo["flow_tons_2024_day_baseline"]
        gdf_links_geo.drop(columns=["flow_value_2024_day_baseline",
                                    "flow_tons_2024_day_baseline"], inplace=True)
    print(f"      GPKG saved: {path}")

# Run
timer = StepTimer(total=len(steps), label=SCENARIO_NAME)
for si in steps:
    sn      = si["step"]; sl = f"step{sn:03d}"
    sd      = os.path.join(DISRUPTION_DIR, sl); os.makedirs(sd, exist_ok=True)
    csv_out = os.path.join(sd, f"od_paths_{SCENARIO_NAME}_{sl}.csv")
    print(f"\n  -- {SCENARIO_NAME} step {sn:>3}  "
          f"score={si['score_value']:.4f}  cumul_links={si['n_cumul']:,} --")
    if os.path.exists(csv_out):
        print("      exists - skipping"); timer.tick(note=f"skip step {sn}"); continue
    mask   = affected_mask(df_baseline, si["cumul_fids"])
    df_aff = df_baseline[mask].copy(); n_aff = len(df_aff)
    print(f"      Affected OD pairs : {n_aff:,} ({n_aff/len(df_baseline)*100:.1f}%)")
    need_gpkg = sn in GPKG_SAVE_STEPS_SUM and gdf_links_geo is not None
    if n_aff == 0:
        pd.DataFrame(columns=SAVE_COLS).to_csv(csv_out, index=False)
        lf_re = lt_re = lf_or = lt_or = {}
    else:
        G_dis = build_graph(gdf_edges[~gdf_edges["edge_fid"].isin(si["cumul_fids"])])
        print(f"      Graph: {G_dis.number_of_nodes():,} nodes  "
              f"{G_dis.number_of_edges():,} edges")
        df_out, lf_re, lt_re, lf_or, lt_or = reroute(G_dis, df_aff, acc=need_gpkg)
        del G_dis; gc.collect()
        df_out[[c for c in SAVE_COLS if c in df_out.columns]].to_csv(csv_out, index=False)
        ni = int(np.isinf(df_out["value_hours_2024"]).sum())
        print(f"      Saved {len(df_out):,} rows  "
              f"infeasible {ni:,}  rerouted {len(df_out)-ni:,}")
        del df_out; gc.collect()
    if need_gpkg:
        save_gpkg(si["cumul_fids"], sl, sd, lf_re, lt_re, lf_or, lt_or)
    del df_aff, lf_re, lt_re, lf_or, lt_or; gc.collect()
    timer.tick(note=f"step {sn}")
timer.summary()

# Resilience
K     = len(df_baseline)
df_bl = df_baseline[["origin_franodeid", "destination_franodeid",
                      "value_hours_2024", "value_2024_day"]].rename(
    columns={"value_hours_2024": "vh_bl", "value_2024_day": "val_bl"})
# Deduplicate baseline: if (origin, destination) appears more than once,
# keep the row with the highest vh_bl (most conservative baseline for f_k)
df_bl = df_bl.drop_duplicates(
    subset=["origin_franodeid", "destination_franodeid"], keep="first")
K = len(df_bl)   # recompute K from deduplicated baseline
print(f"  Deduplicated baseline : {K:,} unique OD pairs")
results = []
for si in steps:
    sl = f"step{si['step']:03d}"
    fp = os.path.join(DISRUPTION_DIR, sl, f"od_paths_{SCENARIO_NAME}_{sl}.csv")
    if not os.path.exists(fp): continue
    df_dis = pd.read_csv(fp)
    # Deduplicate disrupted CSV — keep worst (highest value_hours) per OD pair
    df_dis_dedup = (df_dis[["origin_franodeid", "destination_franodeid", "value_hours_2024"]]
                    .sort_values("value_hours_2024", ascending=False)
                    .drop_duplicates(subset=["origin_franodeid", "destination_franodeid"],
                                     keep="first"))
    del df_dis
    df_m = df_bl.merge(
        df_dis_dedup.rename(columns={"value_hours_2024": "vh_dis"}),
        on=["origin_franodeid", "destination_franodeid"], how="left")
    del df_dis_dedup
    # inf_ must be checked BEFORE fillna — NaN means unaffected (not in disrupted CSV)
    # inf means truly infeasible (value_hours_2024 = inf in disrupted CSV)
    inf_ = np.isinf(df_m["vh_dis"])          # True only for real infeasible rows
    df_m["vh_dis"] = df_m["vh_dis"].fillna(df_m["vh_bl"])  # unaffected -> f_k = 1

    # delta clamped to >= 0: reroutes that happen to be shorter than baseline
    # still count as unaffected (f_k = 1), never push F above 1
    delta = np.where(inf_, np.inf,
                     np.clip(df_m["vh_dis"].values - df_m["vh_bl"].values, 0.0, None))

    # f_k in [0, 1] always
    fk  = np.where(inf_, 0.0, 1.0 / (1.0 + delta))

    # classification: infeasible | delayed (delta > 0) | unaffected (delta == 0)
    cls = np.where(inf_, "infeasible",
          np.where(delta > 0, "delayed", "unaffected"))
    nu  = int((cls == "unaffected").sum())
    nd_ = int((cls == "delayed"   ).sum())
    ni  = int((cls == "infeasible").sum())
    val = df_m["val_bl"].values; del df_m
    results.append({
        "step": si["step"], "score_value": si["score_value"],
        "n_cumul_links": si["n_cumul"], "num_total": K,
        "num_unaffected": nu, "num_delayed": nd_, "num_infeasible": ni,
        "num_feasible": nu + nd_,
        "pct_unaffected": nu / K * 100, "pct_delayed": nd_ / K * 100,
        "pct_infeasible": ni / K * 100, "reachability": (nu + nd_) / K,
        "F_value_2024": float(fk.sum()) / K,
        "val_infeasible_day": float(val[cls == "infeasible"].sum()),
        "val_total_day": float(val.sum()),
    })

df_res   = pd.DataFrame(results)
summ_csv = os.path.join(RESILIENCE_DIR, f"resilience_summary_{SCENARIO_NAME}.csv")
df_res.to_csv(summ_csv, index=False)
print(f"  Summary saved: {summ_csv}  ({len(df_res)} rows)\n")

# Plots
sns.set_style("whitegrid"); plt.rcParams["figure.dpi"] = 100
COLOR = "#3A86FF"

def _plot(y, ylabel, title, fname, ylim=None):
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(df_res["step"], df_res[y], marker="o", linewidth=2.5,
            markersize=6, color=COLOR, label=SCENARIO_NAME)
    ax.set_xlabel("Cumulative Flood-Risk Step  (1 = highest Sum_Risk_Score)",
                  fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=13, fontweight="bold")
    ax.set_title(title,   fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=11); ax.grid(True, alpha=0.3)
    if ylim: ax.set_ylim(ylim)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGURES_DIR, fname), dpi=300, bbox_inches="tight")
    plt.close(); print(f"    {fname}")

_plot("F_value_2024",
      "Network Functionality  F(G_d)",
      f"Network Functionality vs Flood-Risk Steps\n({SCENARIO_NAME})",
      f"F_{SCENARIO_NAME}.png", (0, 1.05))
_plot("reachability",
      "Reachability  |K_feasible| / |K|",
      f"Network Reachability vs Flood-Risk Steps\n({SCENARIO_NAME})",
      f"reachability_{SCENARIO_NAME}.png", (0, 1.05))
_plot("val_infeasible_day",
      "Daily Value Infeasible  ($M/day)",
      f"Daily Value Lost vs Flood-Risk Steps\n({SCENARIO_NAME})",
      f"value_infeasible_{SCENARIO_NAME}.png")
_plot("n_cumul_links",
      "Cumulative Disrupted Links",
      f"Cumulative Links Removed vs Step\n({SCENARIO_NAME})",
      f"cumul_links_{SCENARIO_NAME}.png")

fig, ax = plt.subplots(figsize=(12, 7)); x = df_res["step"].values
ax.fill_between(x, 0, df_res["pct_unaffected"],
                label="Unaffected", color="#90EE90", alpha=0.8)
ax.fill_between(x, df_res["pct_unaffected"],
                df_res["pct_unaffected"] + df_res["pct_delayed"],
                label="Delayed",    color="#FFD700", alpha=0.8)
ax.fill_between(x, df_res["pct_unaffected"] + df_res["pct_delayed"], 100,
                label="Infeasible", color="#FF6B6B", alpha=0.8)
ax.set_xlabel("Cumulative Flood-Risk Step", fontsize=12)
ax.set_ylabel("% of OD Pairs",             fontsize=12)
ax.set_title(f"OD Classification vs Flood-Risk Steps\n({SCENARIO_NAME})",
             fontsize=14, fontweight="bold")
ax.legend(fontsize=10); ax.grid(True, alpha=0.3); ax.set_ylim([0, 105])
plt.tight_layout()
fig.savefig(os.path.join(FIGURES_DIR, f"od_classification_{SCENARIO_NAME}.png"),
            dpi=300, bbox_inches="tight")
plt.close(); print(f"    od_classification_{SCENARIO_NAME}.png")

print(f"\n  BLOCK 3 COMPLETE\n")


# %%
# ============================================================================
# BLOCK 4 – Combined Comparison Figures  (Max vs Sum on one figure each)
# ============================================================================
#
# Reads resilience_summary_FloodRisk_Max.csv and _Sum.csv from Blocks 2 & 3.
# Both blocks must be run before this one.
#
# Produces one independent figure per metric — both scenarios on same axes:
#   combined_F_value2024.png
#   combined_reachability.png
#   combined_value_infeasible.png
#   combined_cumul_links.png
#   combined_od_classification.png
# ============================================================================

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os, warnings
warnings.filterwarnings("ignore")

base_dir = os.path.abspath(os.path.join("..", ".."))
county   = os.path.join(base_dir, "13_Resiliency", "FAF",
                        "Processed_Data", "County_Level")
RES_DIR  = os.path.join(county, "Resilience_Analysis_FloodRisk")
FIGS_DIR = os.path.join(RES_DIR, "figures")
os.makedirs(FIGS_DIR, exist_ok=True)

CSV_MAX = os.path.join(RES_DIR, "resilience_summary_FloodRisk_Max.csv")
CSV_SUM = os.path.join(RES_DIR, "resilience_summary_FloodRisk_Sum.csv")

print("=" * 70)
print("BLOCK 4 – Combined comparison figures")
print("=" * 70)

for p, lbl in [(CSV_MAX, "FloodRisk_Max"), (CSV_SUM, "FloodRisk_Sum")]:
    if not os.path.exists(p):
        raise FileNotFoundError(
            f"Missing: {p}\n"
            f"Run Block {'2' if 'Max' in lbl else '3'} first.")

df_max = pd.read_csv(CSV_MAX).sort_values("step")
df_sum = pd.read_csv(CSV_SUM).sort_values("step")
print(f"  FloodRisk_Max : {len(df_max)} steps")
print(f"  FloodRisk_Sum : {len(df_sum)} steps\n")

sns.set_style("whitegrid"); plt.rcParams["figure.dpi"] = 100
C_MAX  = "#E84855"; C_SUM = "#3A86FF"
XLABEL = "Cumulative Flood-Risk Step"

def combined_line(y, ylabel, title, fname, ylim=None):
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.plot(df_max["step"], df_max[y], marker="o", linewidth=2.5,
            markersize=6, color=C_MAX,
            label="FloodRisk_Max  (ranked by Max_Risk_Score)")
    ax.plot(df_sum["step"], df_sum[y], marker="s", linewidth=2.5,
            markersize=6, color=C_SUM,
            label="FloodRisk_Sum  (ranked by Sum_Risk_Score)")
    ax.set_xlabel(XLABEL, fontsize=13, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=13, fontweight="bold")
    ax.set_title(title,   fontsize=14, fontweight="bold", pad=15)
    ax.legend(fontsize=11); ax.grid(True, alpha=0.3)
    if ylim: ax.set_ylim(ylim)
    plt.tight_layout()
    fig.savefig(os.path.join(FIGS_DIR, fname), dpi=300, bbox_inches="tight")
    plt.close(); print(f"  {fname}")

combined_line("F_value_2024",
              "Network Functionality  F(G_d)",
              "Network Functionality vs Cumulative Flood-Risk Steps\n"
              "FloodRisk_Max vs FloodRisk_Sum",
              "combined_F_value2024.png", (0, 1.05))

combined_line("reachability",
              "Reachability  |K_feasible| / |K|",
              "Network Reachability vs Cumulative Flood-Risk Steps\n"
              "FloodRisk_Max vs FloodRisk_Sum",
              "combined_reachability.png", (0, 1.05))

combined_line("val_infeasible_day",
              "Daily Value Infeasible  ($M/day)",
              "Daily Value Lost vs Cumulative Flood-Risk Steps\n"
              "FloodRisk_Max vs FloodRisk_Sum",
              "combined_value_infeasible.png")

combined_line("n_cumul_links",
              "Cumulative Disrupted Links",
              "Links Removed Cumulatively vs Step\n"
              "FloodRisk_Max vs FloodRisk_Sum",
              "combined_cumul_links.png")

fig, axes = plt.subplots(1, 2, figsize=(18, 7), sharey=True)
for ax, (df_r, lbl, color) in zip(axes, [
        (df_max, "FloodRisk_Max", C_MAX),
        (df_sum, "FloodRisk_Sum", C_SUM)]):
    x = df_r["step"].values
    ax.fill_between(x, 0, df_r["pct_unaffected"],
                    label="Unaffected", color="#90EE90", alpha=0.85)
    ax.fill_between(x, df_r["pct_unaffected"],
                    df_r["pct_unaffected"] + df_r["pct_delayed"],
                    label="Delayed",    color="#FFD700", alpha=0.85)
    ax.fill_between(x, df_r["pct_unaffected"] + df_r["pct_delayed"], 100,
                    label="Infeasible", color="#FF6B6B", alpha=0.85)
    ax.set_title(lbl,     fontsize=13, fontweight="bold", color=color)
    ax.set_xlabel(XLABEL, fontsize=12)
    ax.set_ylabel("% of OD Pairs", fontsize=12)
    ax.legend(fontsize=10); ax.grid(True, alpha=0.3); ax.set_ylim([0, 105])
plt.suptitle("OD Pair Classification vs Cumulative Flood-Risk Steps",
             fontsize=15, fontweight="bold")
plt.tight_layout()
fig.savefig(os.path.join(FIGS_DIR, "combined_od_classification.png"),
            dpi=300, bbox_inches="tight")
plt.close(); print("  combined_od_classification.png")

print(f"\n  All figures saved to: {FIGS_DIR}")
print("\n  BLOCK 4 COMPLETE")


# %%
