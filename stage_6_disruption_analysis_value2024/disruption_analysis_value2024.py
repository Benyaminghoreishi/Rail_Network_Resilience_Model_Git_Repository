# %%
#! ============================================================================
#! 1 – Disruption Analysis (Value 2024 Only)
#
#! STEP 0  Add path_node_fids to baseline CSV.
#!          Derives node sequences from existing path_link_fids via the
#!          edge → (FRFRANODE, TOFRANODE) lookup.  No Dijkstra re-run.
#
#! STEP 2  Run disruption scenarios – links AND nodes, separately.
#!          • Saves ONLY the affected (rerouted/infeasible) OD rows per run.
#!          • Filename: od_paths_<Scenario>_<Xpct>.csv  (never overwrites).
#!          • Optionally saves one GPKG per run with updated post-disruption
#!            flows (fractions configurable via GPKG_SAVE_FRACTIONS).
#
#! MEMORY DESIGN
#! ─────────────
#! GPKG flow update uses the delta approach:
#!   post_flow = baseline_flow
#!             − flows carried by affected OD pairs on their ORIGINAL paths
#!             + flows carried by affected OD pairs on their REROUTED paths
#
#! All three accumulators (rerouted flows AND affected-original flows) are
#! built inside reroute() in a single Dijkstra pass — no explode(), no extra
#! DataFrame copies inside the per-GPKG call.  The baseline flow dicts are
#! computed once (vectorised explode on the full df_baseline) and then only
#! plain Python dicts (≪ 1 GB) are held in memory for the rest of the run.
#! ============================================================================

import geopandas as gpd
import pandas as pd
import networkx as nx
import os, time, gc, warnings
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")


# ============================================================================
# PROGRESS UTILITIES
# ============================================================================

def fmt_time(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h: return f"{h}h {m:02d}m {s:02d}s"
    if m: return f"{m}m {s:02d}s"
    return f"{s}s"


class StepTimer:
    """Progress bar that fires only at 25 / 50 / 75 / 100 % milestones."""
    def __init__(self, total, label=""):
        self.total      = total
        self.label      = label
        self.done       = 0
        self.t_start    = time.time()
        self._last_mile = -1

    def tick(self, note=""):
        self.done += 1
        elapsed   = time.time() - self.t_start
        eta       = (elapsed / self.done) * (self.total - self.done)
        pct       = self.done / self.total * 100
        milestone = int(pct // 25) * 25

        if milestone != self._last_mile or self.done == self.total:
            self._last_mile = milestone
            filled = int(28 * self.done / self.total)
            bar    = "█" * filled + "░" * (28 - filled)
            note_s = f"  ← {note}" if note else ""
            print(f"  [{bar}] {self.done}/{self.total} ({pct:.0f}%)  "
                  f"elapsed {fmt_time(elapsed)}  ETA {fmt_time(eta)}{note_s}")

    def summary(self):
        elapsed = time.time() - self.t_start
        print(f"  ✅ {self.label} complete – "
              f"{self.done} runs  total {fmt_time(elapsed)}  "
              f"avg {fmt_time(elapsed / max(self.done,1))}/run\n")


# ============================================================================
# ════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION  –  edit this section only
# ════════════════════════════════════════════════════════════════════════════
# ============================================================================

SPEED_MPH     = 49.0
HOURS_PER_DAY = 24.0

# ── Disruption levels: 0.5%…15.0% ───────────────────────────────────────────
DISRUPTION_FRACTIONS = [round(0.005 * i, 4) for i in range(1, 31)]  # 0.005 … 0.150

# ── GPKG export ──────────────────────────────────────────────────────────────
# All disruption fractions saved as GPKG.
# Set to [] to skip GPKG export entirely.
GPKG_SAVE_FRACTIONS = DISRUPTION_FRACTIONS[:]

# ── Columns in the disrupted-OD CSV (affected rows only) ────────────────────
SAVE_COLS = [
    "origin_franodeid",
    "destination_franodeid",
    "value_2024_day",       # daily $ flow (unchanged from baseline)
    "value_hours_2024",     # inf if infeasible; updated value if rerouted
    "travel_time_hours",    # useful for QA / spot-checks
    # ── uncomment + mirror in _make_record() to include additional cols ──────
    # "tons_2024_day",
    # "ton_hours_2024",
    # "path_length_miles",
    # "travel_time_days",
    # "origin_node_type",
    # "destination_node_type",
    # "original_origin_county",
    # "original_dest_county",
]

# ── Paths ────────────────────────────────────────────────────────────────────
base_dir = os.path.abspath(os.path.join("..", ".."))

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

os.makedirs(DISRUPTION_BASE_DIR,  exist_ok=True)
os.makedirs(RESILIENCE_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(RESILIENCE_OUTPUT_DIR, "figures"), exist_ok=True)


# ============================================================================
# ============================================================================
# STEP 0 – Add path_node_fids to baseline CSV
# ============================================================================
# ============================================================================

print("=" * 70)
print("STEP 0 – Add path_node_fids to baseline CSV")
print("=" * 70)

df_baseline = pd.read_csv(BASELINE_CSV)
print(f"  Baseline OD rows : {len(df_baseline):,}")

if "path_node_fids" in df_baseline.columns:
    print("  ✅ path_node_fids already present – skipping Step 0.\n")

else:
    if "path_link_fids" not in df_baseline.columns:
        raise ValueError(
            "path_link_fids column not found in baseline CSV. "
            "Run the Quick Fix step first."
        )

    print("  Building edge → (FRFRANODE, TOFRANODE) lookup …")
    _gdf = (gpd.read_file(RAIL_GRAPH_GPKG, layer="edges")
              .reset_index(drop=False)
              .rename(columns={"index": "edge_fid"}))
    fid_to_fr = dict(zip(_gdf["edge_fid"], _gdf["FRFRANODE"]))
    fid_to_to = dict(zip(_gdf["edge_fid"], _gdf["TOFRANODE"]))
    del _gdf

    def _link_fids_to_node_fids(s):
        if pd.isna(s) or str(s).strip() in ("", "nan"):
            return ""
        try:
            fids = [int(x.strip()) for x in str(s).split(",") if x.strip()]
        except ValueError:
            return ""
        nodes = []
        for i, fid in enumerate(fids):
            fr, to = fid_to_fr.get(fid), fid_to_to.get(fid)
            if fr is None or to is None:
                continue
            if i == 0:
                nodes.append(int(fr))
            nodes.append(int(to))
        return ",".join(str(n) for n in nodes)

    t0 = time.time()
    df_baseline["path_node_fids"] = df_baseline["path_link_fids"].apply(
        _link_fids_to_node_fids
    )
    n_empty = (df_baseline["path_node_fids"] == "").sum()
    n_empty_links = (
        df_baseline["path_link_fids"].isna()
        | df_baseline["path_link_fids"].astype(str).str.strip().isin(["", "nan"])
    ).sum()
    print(f"  Done in {fmt_time(time.time()-t0)}  "
          f"empty: {n_empty:,} (expected ≈ {n_empty_links:,})")
    df_baseline.to_csv(BASELINE_CSV, index=False)
    print(f"  ✅ Saved → {BASELINE_CSV}\n")


# ============================================================================
# ============================================================================
# STEP 2 – Disruption Analysis
# ============================================================================
# ============================================================================

print("=" * 70)
print("STEP 2 – Disruption Analysis (Links + Nodes, Value 2024)")
print("=" * 70)

df_baseline = pd.read_csv(BASELINE_CSV)
print(f"  Baseline OD rows : {len(df_baseline):,}")
assert "path_link_fids" in df_baseline.columns, "path_link_fids missing"
assert "path_node_fids" in df_baseline.columns, "path_node_fids missing"

# ── Rail graph edges ──────────────────────────────────────────────────────────
print("  Reading rail graph edges …")
gdf_edges = (gpd.read_file(RAIL_GRAPH_GPKG, layer="edges")
               .reset_index(drop=False)
               .rename(columns={"index": "edge_fid"}))
print(f"  Edges: {len(gdf_edges):,}")

# ── Flow-ranked tables ────────────────────────────────────────────────────────
print("  Reading links_with_flows …")
df_links_flows = pd.read_csv(LINKS_WITH_FLOWS_CSV)
assert "edge_fid"            in df_links_flows.columns
assert "flow_value_2024_day" in df_links_flows.columns
df_links_sorted = df_links_flows.sort_values(
    "flow_value_2024_day", ascending=False).reset_index(drop=True)

print("  Reading nodes_with_flows …")
df_nodes_flows = pd.read_csv(NODES_WITH_FLOWS_CSV)
assert "FRANODEID"                 in df_nodes_flows.columns
assert "throughput_value_2024_day" in df_nodes_flows.columns
df_nodes_sorted = df_nodes_flows.sort_values(
    "throughput_value_2024_day", ascending=False).reset_index(drop=True)

# ── Spatial layers + baseline flow dicts (GPKG fractions only) ───────────────
# gdf_links_geo / gdf_nodes_geo: held as plain GeoDataFrames, NEVER copied.
#   We assign updated flow columns directly and drop them after each write.
# _bl_link_flow / _bl_node_flow: plain Python dicts (much lighter than DFs).
#   Built once here via vectorised explode; reused for every GPKG call.
gdf_links_geo  = None
gdf_nodes_geo  = None
_bl_link_flow  = {}   # edge_fid  → baseline flow_value_2024_day
_bl_node_flow  = {}   # FRANODEID → baseline throughput_value_2024_day
_bl_link_tons  = {}   # edge_fid  → baseline flow_tons_2024_day
_bl_node_tons  = {}   # FRANODEID → baseline throughput_tons_2024_day

if GPKG_SAVE_FRACTIONS:
    print("  Reading spatial layers for GPKG …")
    gdf_links_geo = gpd.read_file(LINKS_WITH_FLOWS_GPKG).to_crs(epsg=4326)
    gdf_nodes_geo = gpd.read_file(NODES_WITH_FLOWS_GPKG).to_crs(epsg=4326)
    if "edge_fid" not in gdf_links_geo.columns:
        gdf_links_geo = (gdf_links_geo.reset_index(drop=False)
                                       .rename(columns={"index": "edge_fid"}))
    print(f"  Spatial links: {len(gdf_links_geo):,}   nodes: {len(gdf_nodes_geo):,}")

    # Chunked row-by-row accumulation — never materialises a large intermediate
    # DataFrame.  Constant peak RAM regardless of baseline size.
    # CHUNK_SIZE controls how many rows are processed at once (tune if needed).
    CHUNK_SIZE = 50_000
    print("  Pre-computing full baseline link & node flows (chunked) …")
    _t0 = time.time()
    n_rows = len(df_baseline)

    for _start in range(0, n_rows, CHUNK_SIZE):
        _chunk = df_baseline.iloc[_start : _start + CHUNK_SIZE]
        _pct   = min(_start + CHUNK_SIZE, n_rows) / n_rows * 100
        print(f"    chunk {_start:,}-{min(_start+CHUNK_SIZE, n_rows):,} / {n_rows:,} ({_pct:.0f}%)", end="\r", flush=True)

        for _, _row in _chunk.iterrows():
            _val  = _row["value_2024_day"]
            _tons = _row["tons_2024_day"]

            # link flows (value + tons in one pass)
            _s = _row.get("path_link_fids", "")
            if not (pd.isna(_s) or str(_s).strip() in ("", "nan")):
                for _fid_s in str(_s).split(","):
                    _fid_s = _fid_s.strip()
                    if _fid_s:
                        try:
                            _fid = int(_fid_s)
                            _bl_link_flow[_fid] = (
                                _bl_link_flow.get(_fid, 0.0) + _val)
                            _bl_link_tons[_fid] = (
                                _bl_link_tons.get(_fid, 0.0) + _tons)
                        except ValueError:
                            pass

            # node flows (value + tons in one pass)
            _s = _row.get("path_node_fids", "")
            if not (pd.isna(_s) or str(_s).strip() in ("", "nan")):
                for _nid_s in str(_s).split(","):
                    _nid_s = _nid_s.strip()
                    if _nid_s:
                        try:
                            _nid = int(_nid_s)
                            _bl_node_flow[_nid] = (
                                _bl_node_flow.get(_nid, 0.0) + _val)
                            _bl_node_tons[_nid] = (
                                _bl_node_tons.get(_nid, 0.0) + _tons)
                        except ValueError:
                            pass

    print()  # newline after \r progress
    print(f"  Baseline dicts ready: "
          f"{len(_bl_link_flow):,} links  {len(_bl_node_flow):,} nodes  "
          f"(value + tons)  ({fmt_time(time.time()-_t0)})")

print()


# ============================================================================
# HELPERS
# ============================================================================

def build_graph(gdf_sub):
    """Undirected NetworkX graph, edge weight = length in miles."""
    G = nx.Graph()
    for _, e in gdf_sub.iterrows():
        u, v = e["FRFRANODE"], e["TOFRANODE"]
        if pd.isna(u) or pd.isna(v):
            continue
        G.add_edge(u, v, weight=e["LENGTH"] / 1609.344)
    return G


def affected_mask_links(df, dis_set):
    def chk(s):
        if pd.isna(s) or str(s).strip() in ("", "nan"):
            return False
        return bool({int(x) for x in str(s).split(",") if x.strip()} & dis_set)
    return df["path_link_fids"].apply(chk)


def affected_mask_nodes(df, dis_set):
    def chk(row):
        if row["origin_franodeid"]      in dis_set: return True
        if row["destination_franodeid"] in dis_set: return True
        s = row["path_node_fids"]
        if pd.isna(s) or str(s).strip() in ("", "nan"):
            return False
        return bool({int(x) for x in str(s).split(",") if x.strip()} & dis_set)
    return df.apply(chk, axis=1)


def _make_record(row, dist_miles):
    t_hrs = np.inf if dist_miles is None else dist_miles / SPEED_MPH
    rec = {
        "origin_franodeid":      row["origin_franodeid"],
        "destination_franodeid": row["destination_franodeid"],
        "value_2024_day":        row["value_2024_day"],
        "value_hours_2024":      (np.inf if np.isinf(t_hrs)
                                  else row["value_2024_day"] * t_hrs),
        "travel_time_hours":     t_hrs,
        # "tons_2024_day":          row["tons_2024_day"],
        # "ton_hours_2024":         (np.inf if np.isinf(t_hrs)
        #                            else row["tons_2024_day"] * t_hrs),
        # "path_length_miles":      np.inf if dist_miles is None else dist_miles,
        # "travel_time_days":       (np.inf if np.isinf(t_hrs)
        #                            else t_hrs / HOURS_PER_DAY),
        # "origin_node_type":       row.get("origin_node_type"),
        # "destination_node_type":  row.get("destination_node_type"),
        # "original_origin_county": row.get("original_origin_county"),
        # "original_dest_county":   row.get("original_dest_county"),
    }
    return {k: v for k, v in rec.items() if k in SAVE_COLS}


# ── (u,v) sorted → edge_fid lookup, built once from gdf_edges ────────────────
_edge_key_to_fid = {
    tuple(sorted((int(r["FRFRANODE"]), int(r["TOFRANODE"])))): int(r["edge_fid"])
    for _, r in gdf_edges.iterrows()
    if not (pd.isna(r["FRFRANODE"]) or pd.isna(r["TOFRANODE"]))
}


def reroute(G_dis, df_affected, accumulate_flows=False):
    """
    Single-source Dijkstra for every unique origin in df_affected.
    Progress printed at 25 % intervals of unique origins.

    When accumulate_flows=True (only for GPKG fractions), accumulates
    THREE flow dicts in one pass — no second iteration, no explode():

      link_flow_rerouted   – flows on NEW paths (rerouted feasible OD pairs)
      node_flow_rerouted   – node throughput on NEW paths
      link_flow_orig       – flows these OD pairs carried on ORIGINAL paths
      node_flow_orig       – node throughput on ORIGINAL paths

    Delta approach in save_gpkg():
      post = baseline − orig + rerouted
    Infeasible pairs: orig is subtracted, rerouted = 0 → flow simply lost.

    Returns (df_out, link_flow_rerouted, node_flow_rerouted,
                     link_flow_orig,     node_flow_orig)
    All four dicts are None when accumulate_flows=False.
    """
    records            = []
    link_flow_rerouted = {} if accumulate_flows else None
    node_flow_rerouted = {} if accumulate_flows else None
    link_flow_orig     = {} if accumulate_flows else None
    node_flow_orig     = {} if accumulate_flows else None
    link_tons_rerouted = {} if accumulate_flows else None
    node_tons_rerouted = {} if accumulate_flows else None
    link_tons_orig     = {} if accumulate_flows else None
    node_tons_orig     = {} if accumulate_flows else None

    groups    = list(df_affected.groupby("origin_franodeid"))
    n_orig    = len(groups)
    t0        = time.time()
    last_mile = -1

    for i, (origin, grp) in enumerate(groups, start=1):
        pct       = i / n_orig * 100
        milestone = int(pct // 25) * 25
        if milestone != last_mile or i == n_orig:
            last_mile = milestone
            elapsed   = time.time() - t0
            eta       = (elapsed / i) * (n_orig - i) if i < n_orig else 0
            print(f"      reroute {i:,}/{n_orig:,} origins ({pct:.0f}%)  "
                  f"elapsed {fmt_time(elapsed)}  ETA {fmt_time(eta)}")

        # ── Accumulate ORIGINAL path flows for this origin's group ────────
        if accumulate_flows:
            for _, row in grp.iterrows():
                val  = row["value_2024_day"]
                tons = row["tons_2024_day"]

                # original link flows (value + tons)
                s_lnk = row.get("path_link_fids", "")
                if not (pd.isna(s_lnk) or str(s_lnk).strip() in ("", "nan")):
                    for fid_s in str(s_lnk).split(","):
                        fid_s = fid_s.strip()
                        if fid_s:
                            fid = int(fid_s)
                            link_flow_orig[fid] = (
                                link_flow_orig.get(fid, 0.0) + val)
                            link_tons_orig[fid] = (
                                link_tons_orig.get(fid, 0.0) + tons)

                # original node flows (value + tons)
                s_nod = row.get("path_node_fids", "")
                if not (pd.isna(s_nod) or str(s_nod).strip() in ("", "nan")):
                    for nid_s in str(s_nod).split(","):
                        nid_s = nid_s.strip()
                        if nid_s:
                            nid = int(nid_s)
                            node_flow_orig[nid] = (
                                node_flow_orig.get(nid, 0.0) + val)
                            node_tons_orig[nid] = (
                                node_tons_orig.get(nid, 0.0) + tons)

        # ── Dijkstra from this origin ─────────────────────────────────────
        if origin not in G_dis:
            for _, row in grp.iterrows():
                records.append(_make_record(row, None))
            continue
        try:
            if accumulate_flows:
                lengths, paths = nx.single_source_dijkstra(
                    G_dis, origin, weight="weight")
            else:
                lengths, _     = nx.single_source_dijkstra(
                    G_dis, origin, weight="weight")
        except Exception:
            for _, row in grp.iterrows():
                records.append(_make_record(row, None))
            continue

        for _, row in grp.iterrows():
            dest = row["destination_franodeid"]
            dist = lengths.get(dest)          # None → infeasible
            val  = row["value_2024_day"]
            records.append(_make_record(row, dist))

            # ── Accumulate REROUTED path flows (value + tons) ────────────
            if accumulate_flows and dist is not None:
                node_path = paths[dest]
                tons      = row["tons_2024_day"]

                for nid in node_path:
                    node_flow_rerouted[nid] = (
                        node_flow_rerouted.get(nid, 0.0) + val)
                    node_tons_rerouted[nid] = (
                        node_tons_rerouted.get(nid, 0.0) + tons)

                for k in range(len(node_path) - 1):
                    ekey = tuple(sorted((node_path[k], node_path[k + 1])))
                    fid  = _edge_key_to_fid.get(ekey)
                    if fid is not None:
                        link_flow_rerouted[fid] = (
                            link_flow_rerouted.get(fid, 0.0) + val)
                        link_tons_rerouted[fid] = (
                            link_tons_rerouted.get(fid, 0.0) + tons)

    print(f"      done – {len(records):,} rows  {fmt_time(time.time()-t0)}")
    return (pd.DataFrame(records),
            link_flow_rerouted, node_flow_rerouted,
            link_flow_orig,     node_flow_orig,
            link_tons_rerouted, node_tons_rerouted,
            link_tons_orig,     node_tons_orig)


def save_gpkg(stype, disrupted_ids, sname, pct_label, out_dir,
              link_flow_rerouted, node_flow_rerouted,
              link_flow_orig,     node_flow_orig,
              link_tons_rerouted, node_tons_rerouted,
              link_tons_orig,     node_tons_orig):
    """
    Write one GPKG with accurate post-disruption flows.

    post_flow = baseline − orig_affected + rerouted_affected
    (applied identically for both value_2024 and tons_2024)

    All inputs are plain Python dicts — no DataFrame copies, no explode().
    Flow columns on gdf_links_geo / gdf_nodes_geo are updated in-place and
    restored immediately after writing, so the objects stay lean across calls.

    GPKG layers:
      Link scenario : remaining_links | disrupted_links | nodes
      Node scenario : remaining_nodes | disrupted_nodes
                      | remaining_links | disrupted_links

    Each layer has four flow columns (post-disruption + baseline reference):
      flow_value_2024_day          – post-disruption value   ← style by this
      flow_value_2024_day_baseline – original baseline value
      flow_tons_2024_day           – post-disruption tons
      flow_tons_2024_day_baseline  – original baseline tons
    """
    gpkg_path = os.path.join(out_dir, f"network_{sname}_{pct_label}.gpkg")

    # ── Compute post-disruption flow for every link ───────────────────────────
    all_link_fids = (set(_bl_link_flow)
                     | set(link_flow_orig     or {})
                     | set(link_flow_rerouted or {}))
    link_post = {
        fid: max(0.0,
                 _bl_link_flow.get(fid, 0.0)
                 - (link_flow_orig     or {}).get(fid, 0.0)
                 + (link_flow_rerouted or {}).get(fid, 0.0))
        for fid in all_link_fids
    }

    all_link_fids_t = (set(_bl_link_tons)
                       | set(link_tons_orig     or {})
                       | set(link_tons_rerouted or {}))
    link_tons_post = {
        fid: max(0.0,
                 _bl_link_tons.get(fid, 0.0)
                 - (link_tons_orig     or {}).get(fid, 0.0)
                 + (link_tons_rerouted or {}).get(fid, 0.0))
        for fid in all_link_fids_t
    }

    all_node_ids = (set(_bl_node_flow)
                    | set(node_flow_orig     or {})
                    | set(node_flow_rerouted or {}))
    node_post = {
        nid: max(0.0,
                 _bl_node_flow.get(nid, 0.0)
                 - (node_flow_orig     or {}).get(nid, 0.0)
                 + (node_flow_rerouted or {}).get(nid, 0.0))
        for nid in all_node_ids
    }

    all_node_ids_t = (set(_bl_node_tons)
                      | set(node_tons_orig     or {})
                      | set(node_tons_rerouted or {}))
    node_tons_post = {
        nid: max(0.0,
                 _bl_node_tons.get(nid, 0.0)
                 - (node_tons_orig     or {}).get(nid, 0.0)
                 + (node_tons_rerouted or {}).get(nid, 0.0))
        for nid in all_node_ids_t
    }

    # ── Attach updated flows IN-PLACE; restore after writing ─────────────────
    # We add _baseline cols + overwrite post-disruption cols, write, then
    # restore everything — avoids keeping any full GeoDataFrame copies.
    gdf_links_geo["flow_value_2024_day_baseline"] = (
        gdf_links_geo["flow_value_2024_day"])
    gdf_links_geo["flow_value_2024_day"] = (
        gdf_links_geo["edge_fid"].map(link_post).fillna(0.0))
    gdf_links_geo["flow_tons_2024_day_baseline"] = (
        gdf_links_geo["flow_tons_2024_day"])
    gdf_links_geo["flow_tons_2024_day"] = (
        gdf_links_geo["edge_fid"].map(link_tons_post).fillna(0.0))

    gdf_nodes_geo["throughput_value_2024_day_baseline"] = (
        gdf_nodes_geo["throughput_value_2024_day"])
    gdf_nodes_geo["throughput_value_2024_day"] = (
        gdf_nodes_geo["FRANODEID"].map(node_post).fillna(0.0))
    gdf_nodes_geo["throughput_tons_2024_day_baseline"] = (
        gdf_nodes_geo["throughput_tons_2024_day"])
    gdf_nodes_geo["throughput_tons_2024_day"] = (
        gdf_nodes_geo["FRANODEID"].map(node_tons_post).fillna(0.0))

    # ── Write layers ──────────────────────────────────────────────────────────
    try:
        if stype == "links":
            dis_mask = gdf_links_geo["edge_fid"].isin(disrupted_ids)
            gdf_links_geo[~dis_mask].to_file(
                gpkg_path, layer="remaining_links", driver="GPKG")
            gdf_links_geo[ dis_mask].to_file(
                gpkg_path, layer="disrupted_links", driver="GPKG")
            gdf_nodes_geo.to_file(gpkg_path, layer="nodes", driver="GPKG")

        else:  # nodes
            n_dis = gdf_nodes_geo["FRANODEID"].isin(disrupted_ids)
            gdf_nodes_geo[~n_dis].to_file(
                gpkg_path, layer="remaining_nodes", driver="GPKG")
            gdf_nodes_geo[ n_dis].to_file(
                gpkg_path, layer="disrupted_nodes", driver="GPKG")

            if "FRFRANODE" in gdf_links_geo.columns:
                l_dis = (gdf_links_geo["FRFRANODE"].isin(disrupted_ids)
                         | gdf_links_geo["TOFRANODE"].isin(disrupted_ids))
            else:
                l_dis = pd.Series(False, index=gdf_links_geo.index)
            gdf_links_geo[~l_dis].to_file(
                gpkg_path, layer="remaining_links", driver="GPKG")
            gdf_links_geo[ l_dis].to_file(
                gpkg_path, layer="disrupted_links", driver="GPKG")

    finally:
        # ── Restore original flow columns (drop the temp ones) ────────────
        gdf_links_geo["flow_value_2024_day"] = (
            gdf_links_geo["flow_value_2024_day_baseline"])
        gdf_links_geo["flow_tons_2024_day"] = (
            gdf_links_geo["flow_tons_2024_day_baseline"])
        gdf_links_geo.drop(
            columns=["flow_value_2024_day_baseline",
                     "flow_tons_2024_day_baseline"], inplace=True)

        gdf_nodes_geo["throughput_value_2024_day"] = (
            gdf_nodes_geo["throughput_value_2024_day_baseline"])
        gdf_nodes_geo["throughput_tons_2024_day"] = (
            gdf_nodes_geo["throughput_tons_2024_day_baseline"])
        gdf_nodes_geo.drop(
            columns=["throughput_value_2024_day_baseline",
                     "throughput_tons_2024_day_baseline"], inplace=True)

    print(f"      📦 GPKG → {gpkg_path}")


# ============================================================================
# RUN ALL SCENARIOS
# ============================================================================

SCENARIOS = [
    {"name": "Links_Value2024", "type": "links",
     "ranked": df_links_sorted,  "id_col": "edge_fid"},
    {"name": "Nodes_Value2024", "type": "nodes",
     "ranked": df_nodes_sorted,  "id_col": "FRANODEID"},
]

total_runs = len(SCENARIOS) * len(DISRUPTION_FRACTIONS)
s2_timer   = StepTimer(total=total_runs, label="Step 2")

print(f"  Runs : {total_runs}  "
      f"({len(SCENARIOS)} scenarios × {len(DISRUPTION_FRACTIONS)} fractions)")
print(f"  Fractions : {[f'{f*100:.1f}%' for f in DISRUPTION_FRACTIONS]}\n")

for scen in SCENARIOS:
    sname, stype   = scen["name"], scen["type"]
    ranked, id_col = scen["ranked"], scen["id_col"]
    n_elem         = len(ranked)
    metric_col     = ("flow_value_2024_day" if stype == "links"
                      else "throughput_value_2024_day")

    print("=" * 70)
    print(f"SCENARIO: {sname}  |  {n_elem:,} "
          f"{'links' if stype=='links' else 'nodes'} ranked by {metric_col}")
    print("=" * 70)

    for frac in DISRUPTION_FRACTIONS:
        pct_label = f"{frac*100:.1f}pct"
        frac_dir  = os.path.join(DISRUPTION_BASE_DIR, sname, f"Frac_{pct_label}")
        os.makedirs(frac_dir, exist_ok=True)
        out_csv   = os.path.join(frac_dir, f"od_paths_{sname}_{pct_label}.csv")

        print(f"\n  ── {sname} @ {pct_label} ──")

        if os.path.exists(out_csv):
            print(f"      ✅ File exists – skipping.")
            s2_timer.tick(note=f"skipped {sname} @ {pct_label}")
            continue

        # ── Disrupted element set ────────────────────────────────────
        n_dis         = max(1, int(n_elem * frac))
        disrupted_ids = set(ranked[id_col].iloc[:n_dis].tolist())

        # ── Affected OD pairs ────────────────────────────────────────
        mask = (affected_mask_links(df_baseline, disrupted_ids)
                if stype == "links"
                else affected_mask_nodes(df_baseline, disrupted_ids))
        df_affected = df_baseline[mask].copy()
        n_aff       = len(df_affected)
        print(f"      Disrupting {n_dis:,}/{n_elem:,} "
              f"{'links' if stype=='links' else 'nodes'}  |  "
              f"affected OD pairs: {n_aff:,} "
              f"({n_aff / len(df_baseline) * 100:.1f}%)")

        # Decide once: do we need flow accumulation for this fraction?
        need_gpkg = (frac in GPKG_SAVE_FRACTIONS and gdf_links_geo is not None)

        if n_aff == 0:
            pd.DataFrame(columns=SAVE_COLS).to_csv(out_csv, index=False)
            print(f"      No affected pairs – empty CSV saved.")
            link_flow_rerouted = node_flow_rerouted = {}
            link_flow_orig     = node_flow_orig     = {}
            link_tons_rerouted = node_tons_rerouted = {}
            link_tons_orig     = node_tons_orig     = {}
        else:
            # ── Build disrupted graph ────────────────────────────────
            if stype == "links":
                gdf_sub = gdf_edges[~gdf_edges["edge_fid"].isin(disrupted_ids)]
            else:
                gdf_sub = gdf_edges[
                    ~(gdf_edges["FRFRANODE"].isin(disrupted_ids)
                      | gdf_edges["TOFRANODE"].isin(disrupted_ids))]
            G_dis = build_graph(gdf_sub)
            del gdf_sub
            print(f"      Disrupted graph : {G_dis.number_of_nodes():,} nodes  "
                  f"{G_dis.number_of_edges():,} edges")

            # ── Reroute + optionally accumulate flows ────────────────
            (df_out,
             link_flow_rerouted, node_flow_rerouted,
             link_flow_orig,     node_flow_orig,
             link_tons_rerouted, node_tons_rerouted,
             link_tons_orig,     node_tons_orig) = reroute(
                G_dis, df_affected, accumulate_flows=need_gpkg
            )
            del G_dis
            gc.collect()

            # ── Save affected rows only ──────────────────────────────
            cols = [c for c in SAVE_COLS if c in df_out.columns]
            df_out[cols].to_csv(out_csv, index=False)
            n_inf = int(np.isinf(df_out["value_hours_2024"]).sum())
            print(f"      Saved {len(df_out):,} rows  "
                  f"infeasible {n_inf:,}  rerouted {len(df_out)-n_inf:,}")
            print(f"      → {out_csv}")
            del df_out
            gc.collect()

        # ── GPKG with updated post-disruption flows ───────────────────
        if need_gpkg:
            save_gpkg(
                stype, disrupted_ids, sname, pct_label, frac_dir,
                link_flow_rerouted = link_flow_rerouted,
                node_flow_rerouted = node_flow_rerouted,
                link_flow_orig     = link_flow_orig,
                node_flow_orig     = node_flow_orig,
                link_tons_rerouted = link_tons_rerouted,
                node_tons_rerouted = node_tons_rerouted,
                link_tons_orig     = link_tons_orig,
                node_tons_orig     = node_tons_orig,
            )

        del df_affected, disrupted_ids
        del link_flow_rerouted, node_flow_rerouted
        del link_flow_orig, node_flow_orig
        del link_tons_rerouted, node_tons_rerouted
        del link_tons_orig, node_tons_orig
        gc.collect()

        s2_timer.tick(note=f"{sname} @ {pct_label}")

s2_timer.summary()

#%%
#! ============================================================================
#! 2 – Resilience Curves + GPKG fractions
#! ============================================================================

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches

# ============================================================
# PATHS
# ============================================================
base_dir = os.path.abspath(os.path.join("..", ".."))

BASELINE_CSV = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data",
    "County_Level", "rail_od_paths_daily_COMBINED.csv"
)
DISRUPTION_BASE_DIR = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data",
    "County_Level", "Disruption_Scenarios_Value2024_15pct"
)
OUTPUT_DIR = os.path.join(
    base_dir, "13_Resiliency", "FAF", "Processed_Data",
    "County_Level", "Resilience_Analysis_Value2024_15pct_Recomputed"
)
FIG_DIR = os.path.join(OUTPUT_DIR, "figures")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FIG_DIR, exist_ok=True)

# ============================================================
# LOAD BASELINE
# ============================================================
print("Loading baseline...")
baseline_df = pd.read_csv(BASELINE_CSV)

df_bl = baseline_df[
    ["origin_franodeid", "destination_franodeid",
     "value_hours_2024", "value_2024_day"]
].rename(columns={
    "value_hours_2024": "vh_bl",
    "value_2024_day":   "val"
})

K = len(df_bl)
print(f"Total OD pairs: {K:,}\n")

# ============================================================
# SCENARIOS
# ============================================================
SCENARIOS = ["Nodes_Value2024", "Links_Value2024"]
results   = []

# ============================================================
# LOOP
# ============================================================
for scenario in SCENARIOS:
    print(f"\n=== SCENARIO: {scenario} ===")
    scenario_path = os.path.join(DISRUPTION_BASE_DIR, scenario)

    if not os.path.exists(scenario_path):
        print(f"⚠️  Missing folder: {scenario_path}")
        continue

    frac_folders = sorted(
        [f for f in os.listdir(scenario_path) if f.startswith("Frac_")],
        key=lambda x: float(x.replace("Frac_", "").replace("pct", ""))
    )

    for frac_folder in frac_folders:
        frac_path = os.path.join(scenario_path, frac_folder)
        if not os.path.isdir(frac_path):
            continue

        pct       = float(frac_folder.replace("Frac_", "").replace("pct", ""))
        pct_label = f"{pct:.1f}pct"
        csv_name  = f"od_paths_{scenario}_{pct_label}.csv"
        csv_path  = os.path.join(frac_path, csv_name)

        if not os.path.exists(csv_path):
            print(f"  Missing: {csv_name}")
            continue

        print(f"  Processing {pct_label}")
        df_dis = pd.read_csv(csv_path)[
            ["origin_franodeid", "destination_franodeid", "value_hours_2024"]
        ].rename(columns={"value_hours_2024": "vh_dis"})

        df_dis = df_dis.drop_duplicates(
            subset=["origin_franodeid", "destination_franodeid"], keep="first"
        )

        df = df_bl.merge(
            df_dis,
            on=["origin_franodeid", "destination_franodeid"],
            how="left"
        )

        if len(df) != K:
            print(f"  ⚠️  Row mismatch: merged={len(df):,} baseline={K:,}")

        df["vh_dis"] = df["vh_dis"].fillna(df["vh_bl"])

        infeasible = np.isinf(df["vh_dis"]) | df["vh_dis"].isna()
        delta      = np.clip(df["vh_dis"] - df["vh_bl"], 0, None)
        f_k        = np.where(infeasible, 0.0, 1.0 / (1.0 + delta))
        status     = np.where(infeasible, "infeasible",
                     np.where(delta == 0,  "unaffected", "delayed"))

        n_un  = np.sum(status == "unaffected")
        n_del = np.sum(status == "delayed")
        n_inf = np.sum(status == "infeasible")

        F            = f_k.sum() / K
        reachability = (n_un + n_del) / K
        val          = df["val"].values

        results.append({
            "scenario":           scenario,
            "disruption_pct":     pct,
            "F_value_2024":       F,
            "reachability":       reachability,
            "num_unaffected":     n_un,
            "num_delayed":        n_del,
            "num_infeasible":     n_inf,
            "pct_unaffected":     n_un  / K * 100,
            "pct_delayed":        n_del / K * 100,
            "pct_infeasible":     n_inf / K * 100,
            "val_unaffected_day": float(val[status == "unaffected"].sum()),
            "val_delayed_day":    float(val[status == "delayed"].sum()),
            "val_infeasible_day": float(val[status == "infeasible"].sum()),
            "val_total_day":      float(val.sum()),
        })

        print(f"    F={F:.4f} | Reach={reachability:.4f} | infeasible={n_inf:,}")

# ============================================================
# SAVE RESULTS
# ============================================================
df_results  = pd.DataFrame(results)
summary_path = os.path.join(OUTPUT_DIR, "resilience_summary_recomputed.csv")
df_results.to_csv(summary_path, index=False)
print(f"\n✅ Saved: {summary_path}")

# ── anchor rows so every curve starts at (0, perfect) ────────────────────────
anchors = [{
    "scenario":           s,
    "disruption_pct":     0.0,
    "F_value_2024":       1.0,
    "reachability":       1.0,
    "pct_unaffected":     100.0,
    "pct_delayed":        0.0,
    "pct_infeasible":     0.0,
    "val_unaffected_day": 0.0,
    "val_delayed_day":    0.0,
    "val_infeasible_day": 0.0,
    "val_total_day":      0.0,
} for s in SCENARIOS]

df_plot = pd.concat([pd.DataFrame(anchors), df_results], ignore_index=True)

# ============================================================
# PLOTTING
# ============================================================

# ── rcParams ──────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":        "serif",
    "font.serif":         ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size":          9,
    "axes.labelsize":     10,
    "axes.titlesize":     9.5,
    "axes.linewidth":     0.7,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "xtick.labelsize":    8.5,
    "ytick.labelsize":    8.5,
    "xtick.major.width":  0.7,
    "ytick.major.width":  0.7,
    "xtick.minor.width":  0.4,
    "ytick.minor.width":  0.4,
    "xtick.major.size":   3.5,
    "ytick.major.size":   3.5,
    "xtick.minor.size":   2,
    "ytick.minor.size":   2,
    "xtick.direction":    "out",
    "ytick.direction":    "out",
    "legend.fontsize":    8.5,
    "legend.frameon":     False,
    "lines.linewidth":    1.5,
    "savefig.dpi":        600,
    "savefig.bbox":       "tight",
    "savefig.pad_inches": 0.03,
    "pdf.fonttype":       42,
    "ps.fonttype":        42,
})

# ── design tokens ─────────────────────────────────────────────────────────────
C  = {"Nodes_Value2024": "#B5382A",   # brick red
      "Links_Value2024": "#1A4E8A"}   # deep navy
MK = {"Nodes_Value2024": "o",
      "Links_Value2024": "s"}
LB = {"Nodes_Value2024": "Node disruption",
      "Links_Value2024": "Link disruption"}

# stacked-area palette — visually distinct, print-safe
CLR_UN = "#4393C3"   # strong blue
CLR_DL = "#F4A736"   # warm amber
CLR_IN = "#B5382A"   # brick red  (echoes line color)

W1 = 3.35    # single-column (inches)
W2 = 6.85    # double-column
FH = 2.7


# ── helpers ───────────────────────────────────────────────────────────────────
def _style_ax(ax, xlabel, ylabel, ylim=None, pct_y=False):
    """Minimal, clean axis styling."""
    ax.set_xlabel(xlabel, labelpad=4)
    ax.set_ylabel(ylabel, labelpad=4)
    if ylim:
        ax.set_ylim(*ylim)
    ax.set_xlim(left=0)
    # horizontal reference lines only — very faint
    ax.yaxis.grid(True, which="major", color="#EBEBEB", lw=0.6, zorder=0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.xaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    # integer x-ticks, no trailing decimals
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True, nbins=6))
    if pct_y:
        ax.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))


def _draw_lines(ax, metric, scale=1.0, mark_step=4):
    """Draw both scenarios onto ax."""
    for scen in SCENARIOS:
        sub = df_plot[df_plot.scenario == scen].sort_values("disruption_pct")
        x   = sub["disruption_pct"].values
        y   = sub[metric].values * scale

        # continuous line
        ax.plot(x, y, color=C[scen], lw=1.5, zorder=3,
                solid_capstyle="round", solid_joinstyle="round")

        # markers at every mark_step-th point (skip index 0 = anchor)
        idx = np.arange(0, len(x), mark_step)
        ax.scatter(x[idx], y[idx],
                   s=18, color=C[scen], marker=MK[scen],
                   zorder=5, linewidths=0, label=LB[scen])


def _legend_outside(ax):
    """Place legend just below the axes, no frame, two columns."""
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=2,
        handlelength=1.4,
        handletextpad=0.4,
        columnspacing=1.2,
        borderaxespad=0,
    )


def _legend_inline(ax, loc="lower left"):
    ax.legend(loc=loc, handlelength=1.4, handletextpad=0.4,
              labelspacing=0.3, borderaxespad=0.4)


def _save(fig, name):
    path = os.path.join(FIG_DIR, f"{name}.png")
    fig.savefig(path, dpi=600)
    print(f"  → {path}")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — Network Functionality
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(W1, FH))

_draw_lines(ax, "F_value_2024", mark_step=3)
_style_ax(ax,
          xlabel="Disruption level (%)",
          ylabel=r"Network functionality, $F$",
          ylim=(0, 1.04))
ax.yaxis.set_major_locator(mticker.MultipleLocator(0.2))
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
_legend_inline(ax, "lower left")

fig.tight_layout(pad=0.6)
_save(fig, "fig1_network_functionality")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — Reachability
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(W1, FH))

_draw_lines(ax, "reachability", scale=100, mark_step=3)
_style_ax(ax,
          xlabel="Disruption level (%)",
          ylabel="Reachability (% of OD pairs)",
          ylim=(0, 104),
          pct_y=True)
ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
_legend_inline(ax, "lower left")

fig.tight_layout(pad=0.6)
_save(fig, "fig2_reachability")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — OD Classification stacked area (2-panel)
# ══════════════════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(W2, FH), sharey=True)
plt.subplots_adjust(wspace=0.04)

for ax, scen, panel in zip(axes, SCENARIOS, ["(a)", "(b)"]):
    sub   = df_plot[df_plot.scenario == scen].sort_values("disruption_pct")
    x     = sub["disruption_pct"].values
    cum_u = sub["pct_unaffected"].values
    cum_d = sub["pct_unaffected"].values + sub["pct_delayed"].values
    top   = np.full_like(x, 100.0)

    # fills
    ax.fill_between(x, 0,     cum_u, color=CLR_UN, lw=0, alpha=0.85, zorder=2)
    ax.fill_between(x, cum_u, cum_d, color=CLR_DL, lw=0, alpha=0.85, zorder=2)
    ax.fill_between(x, cum_d, top,   color=CLR_IN, lw=0, alpha=0.80, zorder=2)

    # crisp boundary lines — slightly darker shade of each fill
    ax.plot(x, cum_u, color="#2171B5", lw=0.8, zorder=4)   # darker blue
    ax.plot(x, cum_d, color="#CC7A00", lw=0.8, zorder=4)   # darker amber

    ax.set_title(LB[scen], fontsize=9.5, pad=5, fontweight="normal")
    ax.set_xlabel("Disruption level (%)", labelpad=4, fontsize=9)
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5))
    ax.xaxis.set_minor_locator(mticker.AutoMinorLocator(5))
    ax.yaxis.set_minor_locator(mticker.AutoMinorLocator(2))
    ax.tick_params(labelsize=8.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)
    ax.text(-0.10, 1.07, panel, transform=ax.transAxes,
            fontsize=10, fontweight="bold", va="top")

axes[0].set_ylabel("OD pairs (%)", labelpad=4, fontsize=9)
axes[0].yaxis.set_major_locator(mticker.MultipleLocator(25))
axes[0].yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))

fig.legend(
    handles=[
        mpatches.Patch(facecolor=CLR_UN, alpha=0.85, edgecolor="none", label="Unaffected"),
        mpatches.Patch(facecolor=CLR_DL, alpha=0.85, edgecolor="none", label="Delayed"),
        mpatches.Patch(facecolor=CLR_IN, alpha=0.80, edgecolor="none", label="Infeasible"),
    ],
    loc="lower center", ncol=3,
    bbox_to_anchor=(0.5, -0.11),
    frameon=False,
    fontsize=8.5,
    handlelength=1.2, handletextpad=0.5,
    columnspacing=1.5,
)
fig.tight_layout(pad=0.6)
_save(fig, "fig3_od_classification")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — Daily Economic Loss (Million USD)
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(W1, FH))

for scen in SCENARIOS:
    sub = df_plot[df_plot.scenario == scen].sort_values("disruption_pct").copy()
    x   = sub["disruption_pct"].values

    # ✅ NO SCALING — already in million USD
    y   = sub["val_infeasible_day"].values

    ax.plot(x, y, color=C[scen], lw=1.5, zorder=3,
            solid_capstyle="round", solid_joinstyle="round")

    idx = np.arange(0, len(x), 3)
    ax.scatter(x[idx], y[idx],
               s=18, color=C[scen], marker=MK[scen],
               zorder=5, linewidths=0, label=LB[scen])

_style_ax(ax,
          xlabel="Disruption level (%)",
          ylabel="Daily economic loss (Million USD)",
          ylim=(0, None))

# Clean formatter (no fake scaling)
ax.yaxis.set_major_formatter(
    mticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
)

_legend_inline(ax, "upper left")
fig.tight_layout(pad=0.6)
_save(fig, "fig4_economic_loss")

print("\n✅ All figures saved to:", FIG_DIR)


print("\n✅ All figures saved to:", FIG_DIR)

