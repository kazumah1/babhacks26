import streamlit as st
import pandas as pd
import json
from pathlib import Path

try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_RESULTS = [
    {"agent_id":"claude-sonnet","market_id":"market-001","market_question":"Will the Fed cut rates in June 2025?","market_type":"long_horizon","brier_score":0.18,"edge_vs_market":0.12,"directional_correct":True,"simulated_pnl":0.15,"resolution_pnl":0.22,"exit_reason":"price_target","estimated_probability":0.65,"market_probability":0.53,"final_resolution":True,"rationale":"Recent CPI data showed cooling inflation. The Fed has signaled openness to cuts. Labor market softening supports the case for easing."},
    {"agent_id":"gpt-4o","market_id":"market-001","market_question":"Will the Fed cut rates in June 2025?","market_type":"long_horizon","brier_score":0.24,"edge_vs_market":0.04,"directional_correct":True,"simulated_pnl":0.08,"resolution_pnl":0.12,"exit_reason":"to_resolution","estimated_probability":0.57,"market_probability":0.53,"final_resolution":True,"rationale":"Inflation is moderating but the Fed may want more data before cutting."},
    {"agent_id":"market_baseline","market_id":"market-001","market_question":"Will the Fed cut rates in June 2025?","market_type":"long_horizon","brier_score":0.22,"edge_vs_market":0.0,"directional_correct":None,"simulated_pnl":0.0,"resolution_pnl":0.47,"exit_reason":"no_entry","estimated_probability":0.53,"market_probability":0.53,"final_resolution":True,"rationale":"Market baseline: echoes current market probability."},
    {"agent_id":"claude-sonnet","market_id":"market-002","market_question":"Will Powell say 'inflation' in the next FOMC presser?","market_type":"speech","brier_score":0.09,"edge_vs_market":0.18,"directional_correct":True,"simulated_pnl":0.21,"resolution_pnl":0.30,"exit_reason":"price_target","estimated_probability":0.88,"market_probability":0.70,"final_resolution":True,"rationale":"Powell has used 'inflation' in every FOMC presser since 2021. Word-frequency analysis of the last 6 transcripts shows 100% usage rate."},
    {"agent_id":"gpt-4o","market_id":"market-002","market_question":"Will Powell say 'inflation' in the next FOMC presser?","market_type":"speech","brier_score":0.14,"edge_vs_market":0.08,"directional_correct":True,"simulated_pnl":0.11,"resolution_pnl":0.19,"exit_reason":"to_resolution","estimated_probability":0.78,"market_probability":0.70,"final_resolution":True,"rationale":"Transcript analysis supports high likelihood. Slight discount for a deliberately brief statement."},
    {"agent_id":"market_baseline","market_id":"market-002","market_question":"Will Powell say 'inflation' in the next FOMC presser?","market_type":"speech","brier_score":0.18,"edge_vs_market":0.0,"directional_correct":None,"simulated_pnl":0.0,"resolution_pnl":0.30,"exit_reason":"no_entry","estimated_probability":0.70,"market_probability":0.70,"final_resolution":True,"rationale":"Market baseline: echoes current market probability."},
    {"agent_id":"claude-sonnet","market_id":"market-003","market_question":"Will Apple release a new Mac Pro in 2025?","market_type":"long_horizon","brier_score":0.31,"edge_vs_market":-0.05,"directional_correct":False,"simulated_pnl":-0.06,"resolution_pnl":-0.10,"exit_reason":"stop_loss","estimated_probability":0.40,"market_probability":0.45,"final_resolution":False,"rationale":"M3 Ultra supply constraints suggest a delay is plausible, but the model underweighted existing roadmap signals."},
    {"agent_id":"gpt-4o","market_id":"market-003","market_question":"Will Apple release a new Mac Pro in 2025?","market_type":"long_horizon","brier_score":0.20,"edge_vs_market":0.10,"directional_correct":False,"simulated_pnl":0.04,"resolution_pnl":0.05,"exit_reason":"time_limit","estimated_probability":0.35,"market_probability":0.45,"final_resolution":False,"rationale":"Focus on AI MacBooks suggests Mac Pro refresh may slip to 2026. Underdog NO bet appears correct."},
    {"agent_id":"market_baseline","market_id":"market-003","market_question":"Will Apple release a new Mac Pro in 2025?","market_type":"long_horizon","brier_score":0.25,"edge_vs_market":0.0,"directional_correct":None,"simulated_pnl":0.0,"resolution_pnl":0.45,"exit_reason":"no_entry","estimated_probability":0.45,"market_probability":0.45,"final_resolution":False,"rationale":"Market baseline: echoes current market probability."},
]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="MarketAdapters Arena", page_icon="📊",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

html, body, [class*="css"] { font-family:'Inter',sans-serif; background:#07090f !important; }
.stApp,
[data-testid="stAppViewContainer"],
section.main { background:#07090f !important; }
[data-testid="stHeader"] { display:none !important; }
section[data-testid="stSidebar"] { display:none !important; }
#MainMenu, footer { visibility:hidden; }

/* Strip block-container padding so we own every pixel */
.block-container { max-width:100% !important; padding:0 !important; margin:0 !important; }

/* Column gutters + backgrounds */
[data-testid="stHorizontalBlock"] {
    gap:0 !important; padding:0 !important; align-items:flex-start !important;
}
[data-testid="column"] { padding:0 !important; }
[data-testid="column"]:nth-child(1) { background:#09101e; border-right:1px solid #1c2a40; }
[data-testid="column"]:nth-child(2) { background:#07090f; border-right:1px solid #1c2a40; }
[data-testid="column"]:nth-child(3) { background:#09101e; }

/* Remove streamlit element spacing inside columns */
[data-testid="column"] [data-testid="element-container"],
[data-testid="column"] [data-testid="stVerticalBlock"] > div { margin:0 !important; padding:0 !important; gap:0 !important; }

/* Selectbox dark */
div[data-testid="stSelectbox"] { padding:0 1rem 0.5rem !important; }
div[data-testid="stSelectbox"] label { color:#2e4060 !important; font-size:.6rem !important; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
div[data-testid="stSelectbox"] > div > div { background:#0d1321 !important; border:1px solid #1c2a40 !important; color:#c8d5e8 !important; border-radius:7px !important; font-size:.78rem !important; }

/* Plotly transparent */
.js-plotly-plot { background:transparent !important; }
[data-testid="stPlotlyChart"] { padding:0 1rem !important; }

/* Scrollbars */
::-webkit-scrollbar { width:3px; height:3px; }
::-webkit-scrollbar-track { background:#09101e; }
::-webkit-scrollbar-thumb { background:#1c2a40; border-radius:3px; }

/* ── Color utils ── */
.pos { color:#22c55e !important; }
.neg { color:#ef4444 !important; }
.neu { color:#4a6080 !important; }

/* ── Topbar ── */
.topbar {
    background:#050810; border-bottom:1px solid #1c2a40;
    padding:0 1.5rem; height:50px;
    display:flex; align-items:center; gap:1.5rem;
}
.t-logo { font-size:.95rem; font-weight:900; color:#fff; letter-spacing:-.02em; text-transform:uppercase; white-space:nowrap; }
.t-logo .acc { color:#f97316; }
.t-links { display:flex; gap:2px; flex:1; }
.t-link { color:#2e4060; font-size:.72rem; font-weight:600; padding:5px 9px; border-radius:5px; cursor:pointer; }
.t-link.on { color:#e8edf5; background:#131e30; }
.t-right { display:flex; gap:7px; align-items:center; margin-left:auto; }
.tbtn { border-radius:6px; padding:5px 12px; font-size:.71rem; font-weight:700; cursor:pointer; border:none; }
.tbtn-g { background:#131e30; color:#7a8fa8; border:1px solid #1c2a40; }
.tbtn-o { background:#f97316; color:#fff; }
.dbadge { border-radius:5px; padding:3px 8px; font-size:.6rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.dbadge-live { background:#052e16; color:#4ade80; border:1px solid #166534; }
.dbadge-mock { background:#2d1500; color:#fb923c; border:1px solid #7c2d12; }

/* ── KPI strip ── */
.kpi-strip {
    background:#050810; border-bottom:1px solid #1c2a40;
    padding:.6rem 1.5rem;
    display:grid; grid-template-columns:repeat(6,1fr); gap:.5rem;
}
.kpi-box { background:#0d1321; border:1px solid #1c2a40; border-radius:8px; padding:.5rem .75rem; }
.kpi-box.hi { border-color:#f97316; background:#130d04; }
.kpi-lbl { font-size:.56rem; font-weight:700; color:#2e4060; letter-spacing:.08em; text-transform:uppercase; margin-bottom:2px; }
.kpi-val { font-size:1.05rem; font-weight:800; font-family:'JetBrains Mono',monospace; color:#e8edf5; line-height:1.1; }
.kpi-sub { font-size:.6rem; color:#2e4060; margin-top:1px; }

/* ── Panel header (used inline in HTML) ── */
.ph {
    font-size:.58rem; font-weight:700; color:#2e4060;
    letter-spacing:.1em; text-transform:uppercase;
    padding:.75rem 1rem .4rem; border-bottom:1px solid #131e30;
    margin-bottom:.5rem; display:flex; align-items:center; justify-content:space-between;
}
.ph-count { background:#131e30; color:#4a6080; border-radius:100px; padding:1px 6px; font-size:.55rem; font-weight:700; }

/* ── Leaderboard ── */
.lb-body { padding:0 .75rem .75rem; display:flex; flex-direction:column; gap:4px; }
.lb-row {
    background:#0d1321; border:1px solid #1c2a40; border-radius:8px;
    padding:.55rem .75rem;
    display:grid; grid-template-columns:18px 22px 1fr repeat(3,52px);
    align-items:center; gap:.4rem;
    transition:background .1s;
}
.lb-row:hover { background:#111927; border-color:#263d5c; }
.lb-row.top { border-left:2px solid #f97316; }
.lbr-rk { font-size:.65rem; font-weight:700; color:#2e4060; text-align:center; font-family:'JetBrains Mono',monospace; }
.lbr-rk.r1{color:#f97316} .lbr-rk.r2{color:#94a3b8} .lbr-rk.r3{color:#c2873a}
.av { width:22px; height:22px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.52rem; font-weight:800; color:#fff; flex-shrink:0; }
.lbr-nm  { font-size:.75rem; font-weight:600; color:#c8d5e8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.lbr-sub { font-size:.58rem; color:#2e4060; }
.lbr-s { text-align:right; }
.lbr-sv { font-size:.75rem; font-weight:700; font-family:'JetBrains Mono',monospace; color:#c8d5e8; }
.lbr-sl { font-size:.52rem; color:#2e4060; letter-spacing:.05em; text-transform:uppercase; }

/* Brier pills */
.bp { display:inline-block; border-radius:4px; padding:1px 5px; font-size:.7rem; font-family:'JetBrains Mono',monospace; font-weight:600; }
.b-g{background:#052e16;color:#4ade80} .b-y{background:#2d1b00;color:#fbbf24} .b-r{background:#2d0000;color:#f87171}

/* Type chips */
.chip { display:inline-block; border-radius:100px; padding:1px 6px; font-size:.56rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase; }
.c-lh { background:#0c1d3a; color:#60a5fa; border:1px solid #1e3a6e; }
.c-sp { background:#1a0c30; color:#c084fc; border:1px solid #3b1870; }
.c-yes{ background:#052e16; color:#4ade80; }
.c-no { background:#2d0000; color:#f87171; }
.c-opn{ background:#131e30; color:#4a6080; border:1px solid #1c2a40; }

/* ── Type breakdown ── */
.tt { width:100%; border-collapse:collapse; }
.tt th { background:#080d14; padding:.35rem .75rem; font-size:.55rem; font-weight:700; color:#2e4060; letter-spacing:.08em; text-transform:uppercase; border-bottom:1px solid #1c2a40; }
.tt th.r { text-align:right; }
.tt td { padding:.4rem .75rem; border-bottom:1px solid #131e30; color:#c8d5e8; font-size:.72rem; }
.tt td.r { text-align:right; font-family:'JetBrains Mono',monospace; font-size:.7rem; }
.tt tr:last-child td { border-bottom:none; }
.tt tr:hover td { background:#0f1726; }

/* ── Signal matrix ── */
.sm-wrap { padding:0 .75rem .75rem; }
.sm { width:100%; border-collapse:collapse; }
.sm th { background:#080d14; padding:.35rem .5rem; font-size:.54rem; font-weight:700; color:#2e4060; letter-spacing:.06em; text-transform:uppercase; border-bottom:1px solid #1c2a40; text-align:center; }
.sm th.la { text-align:left; }
.sm td { padding:.4rem .4rem; border-bottom:1px solid #131e30; }
.sm tr:last-child td { border-bottom:none; }
.sm tr:hover td { background:#0f1726; }
.sc { border-radius:6px; padding:.3rem .4rem; text-align:center; }
.sc-b{background:#052e16} .sc-r{background:#2d0000} .sc-n{background:#131e30}
.sc-pct { font-size:.78rem; font-weight:700; font-family:'JetBrains Mono',monospace; color:#e8edf5; line-height:1; }
.sc-edg { font-size:.58rem; font-weight:600; margin-top:1px; }
.sa  { display:flex; align-items:center; gap:5px; }

/* ── Market cards ── */
.mc-wrap { padding:0 .75rem .75rem; display:flex; flex-direction:column; gap:.6rem; }
.mc {
    background:#0d1321; border:1px solid #1c2a40; border-radius:9px; overflow:hidden;
    transition:border-color .1s;
}
.mc:hover { border-color:#263d5c; }
.mc-hd { padding:.55rem .75rem .45rem; display:flex; gap:.55rem; align-items:flex-start; border-bottom:1px solid #131e30; }
.mc-ico { width:30px; height:30px; border-radius:6px; display:flex; align-items:center; justify-content:center; font-size:.85rem; flex-shrink:0; }
.mc-q { font-size:.76rem; font-weight:600; color:#c8d5e8; line-height:1.3; margin-bottom:.2rem; }
.mc-meta { display:flex; gap:.3rem; flex-wrap:wrap; align-items:center; }
.mc-grid { display:grid; grid-template-columns:repeat(3,1fr); }
.mc-cell { padding:.45rem .55rem; border-right:1px solid #131e30; text-align:center; }
.mc-cell:last-child { border-right:none; }
.mc-an  { font-size:.58rem; font-weight:600; color:#2e4060; letter-spacing:.03em; margin-bottom:.15rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mc-pct { font-size:.9rem; font-weight:800; font-family:'JetBrains Mono',monospace; color:#e8edf5; line-height:1; }
.mc-edg { font-size:.6rem; font-weight:600; font-family:'JetBrains Mono',monospace; margin-top:1px; }
.mc-bar { height:3px; background:#131e30; border-radius:2px; margin:.25rem 0 0; position:relative; overflow:hidden; }
.mc-fill{ position:absolute; top:0; left:0; height:100%; border-radius:2px; }
.mc-ft  { padding:.35rem .75rem; background:#080d14; border-top:1px solid #131e30; display:flex; gap:.85rem; font-size:.61rem; color:#2e4060; }
.mc-ft strong { font-family:'JetBrains Mono',monospace; font-weight:600; }

/* ── Right panel ── */
.rp-ph { font-size:.58rem; font-weight:700; color:#2e4060; letter-spacing:.1em; text-transform:uppercase; padding:.75rem 1rem .35rem; border-bottom:1px solid #131e30; margin-bottom:.25rem; }
.trace-wrap { padding:0 .75rem .75rem; display:flex; flex-direction:column; gap:.5rem; }
.tc {
    background:#0d1321; border:1px solid #1c2a40; border-radius:8px; padding:.6rem .75rem;
}
.tc-hd { display:flex; align-items:center; gap:6px; font-size:.65rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase; margin-bottom:.4rem; }
.tc-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:.3rem; margin-bottom:.4rem; }
.tc-s { background:#080d14; border:1px solid #1c2a40; border-radius:5px; padding:.3rem .4rem; text-align:center; }
.tc-sl { font-size:.52rem; color:#2e4060; font-weight:700; letter-spacing:.05em; text-transform:uppercase; }
.tc-sv { font-size:.78rem; font-weight:700; font-family:'JetBrains Mono',monospace; color:#c8d5e8; }
.tc-rt { font-size:.7rem; color:#4a6080; line-height:1.55; padding:.45rem .55rem; background:#080d14; border-radius:5px; border-left:2px solid #1c2a40; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

RESULTS_PATH = Path("data/results.json")
using_mock   = not RESULTS_PATH.exists()
results      = MOCK_RESULTS if using_mock else json.loads(RESULTS_PATH.read_text())

df = pd.DataFrame(results)
for c in ["brier_score","edge_vs_market","simulated_pnl","resolution_pnl","estimated_probability","market_probability"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

lb = (
    df.groupby("agent_id")
    .agg(avg_brier=("brier_score","mean"), avg_edge=("edge_vs_market","mean"),
         total_pnl=("simulated_pnl","sum"), res_pnl=("resolution_pnl","sum"),
         dir_acc=("directional_correct","mean"), markets=("market_id","count"))
    .reset_index().sort_values("avg_brier").reset_index(drop=True)
)
ai        = lb[lb["agent_id"] != "market_baseline"]
best      = ai.iloc[0]
questions = df["market_question"].unique().tolist()
n_mkts    = int(df["market_id"].nunique())
n_types   = df["market_type"].nunique()

COLORS  = {"claude-sonnet":"#8b5cf6","gpt-4o":"#f97316","market_baseline":"#334155"}
ICONS   = {"claude-sonnet":"CS","gpt-4o":"G4","market_baseline":"MK"}
AGENTS  = ["claude-sonnet","gpt-4o","market_baseline"]

def ac(a): return COLORS.get(a,"#3b82f6")
def bc(v): return "b-g" if v<0.15 else ("b-y" if v<0.25 else "b-r")
def pc(v): return "pos" if v>0.001 else ("neg" if v<-0.001 else "neu")

# ---------------------------------------------------------------------------
# Topbar
# ---------------------------------------------------------------------------

bc_cls = "dbadge-mock" if using_mock else "dbadge-live"
bc_txt = "MOCK DATA"   if using_mock else "● LIVE"

st.markdown(f"""
<div class="topbar">
  <div class="t-logo">📊 Market<span class="acc">Adapters</span> Arena</div>
  <div class="t-links">
    <span class="t-link on">Dashboard</span>
    <span class="t-link">Markets</span>
    <span class="t-link">Adapters</span>
    <span class="t-link">Replay Engine</span>
  </div>
  <div class="t-right">
    <span class="dbadge {bc_cls}">{bc_txt}</span>
    <button class="tbtn tbtn-g">Docs</button>
    <button class="tbtn tbtn-o">Run Evaluation</button>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------

avg_edge = ai["avg_edge"].mean()
tot_pnl  = ai["total_pnl"].sum()
dir_acc  = ai["dir_acc"].mean()

st.markdown(f"""
<div class="kpi-strip">
  <div class="kpi-box hi">
    <div class="kpi-lbl">Top Agent</div>
    <div class="kpi-val" style="font-size:.82rem;font-family:'Inter',sans-serif">{best['agent_id']}</div>
    <div class="kpi-sub">Brier {best['avg_brier']:.4f}</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Best Sim PnL</div>
    <div class="kpi-val" style="color:{'#22c55e' if best['total_pnl']>0 else '#ef4444'}">{best['total_pnl']:+.4f}</div>
    <div class="kpi-sub">{best['agent_id']}</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Avg Edge</div>
    <div class="kpi-val" style="color:{'#22c55e' if avg_edge>0 else '#ef4444'}">{avg_edge:+.4f}</div>
    <div class="kpi-sub">all AI agents</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Total AI PnL</div>
    <div class="kpi-val" style="color:{'#22c55e' if tot_pnl>0 else '#ef4444'}">{tot_pnl:+.4f}</div>
    <div class="kpi-sub">combined</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Directional Acc</div>
    <div class="kpi-val">{dir_acc:.0%}</div>
    <div class="kpi-sub">avg across agents</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Markets / Types</div>
    <div class="kpi-val">{n_mkts}<span style="font-size:.65rem;color:#4a6080;font-family:'Inter',sans-serif"> / {n_types}</span></div>
    <div class="kpi-sub">evaluated</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Three columns
# ---------------------------------------------------------------------------

left, mid, right = st.columns([2.4, 5.0, 2.6])

# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Leaderboard + By-Type table  (one self-contained HTML block)
# ══════════════════════════════════════════════════════════════════════════════

with left:
    # ---- Leaderboard rows ----
    lb_rows = ""
    for i, row in lb.iterrows():
        rc   = ["r1","r2","r3"][i] if i < 3 else ""
        top  = "top" if i == 0 else ""
        col  = ac(row["agent_id"])
        ico  = ICONS.get(row["agent_id"],"??")
        ep   = pc(row["avg_edge"]); pp = pc(row["total_pnl"])
        b    = bc(row["avg_brier"])
        lb_rows += f"""
        <div class="lb-row {top}">
          <div class="lbr-rk {rc}">{i+1}</div>
          <div class="av" style="background:{col}">{ico}</div>
          <div>
            <div class="lbr-nm">{row['agent_id']}</div>
            <div class="lbr-sub">{int(row['markets'])} mkts</div>
          </div>
          <div class="lbr-s">
            <div class="lbr-sv"><span class="bp {b}">{row['avg_brier']:.3f}</span></div>
            <div class="lbr-sl">Brier</div>
          </div>
          <div class="lbr-s">
            <div class="lbr-sv {ep}">{row['avg_edge']:+.3f}</div>
            <div class="lbr-sl">Edge</div>
          </div>
          <div class="lbr-s">
            <div class="lbr-sv {pp}">{row['total_pnl']:+.4f}</div>
            <div class="lbr-sl">PnL</div>
          </div>
        </div>"""

    # ---- By-type rows ----
    type_df = (
        df.groupby(["agent_id","market_type"])
        .agg(avg_brier=("brier_score","mean"), avg_edge=("edge_vs_market","mean"),
             total_pnl=("simulated_pnl","sum"), markets=("market_id","count"))
        .reset_index().sort_values(["market_type","avg_brier"]).reset_index(drop=True)
    )
    tt_rows = ""
    for _, row in type_df.iterrows():
        col  = ac(row["agent_id"]); ico = ICONS.get(row["agent_id"],"??")
        tc   = "c-sp" if row["market_type"]=="speech" else "c-lh"
        tl   = row["market_type"].replace("_"," ").title()
        b    = bc(row["avg_brier"]); ep = pc(row["avg_edge"]); pp = pc(row["total_pnl"])
        tt_rows += f"""
        <tr>
          <td><div style="display:flex;align-items:center;gap:5px">
            <div class="av" style="background:{col};width:18px;height:18px;font-size:.5rem">{ico}</div>
            <span style="font-size:.68rem;font-weight:600;color:#7a8fa8">{row['agent_id']}</span>
          </div></td>
          <td><span class="chip {tc}">{tl}</span></td>
          <td class="r"><span class="bp {b}">{row['avg_brier']:.3f}</span></td>
          <td class="r {pp}">{row['total_pnl']:+.3f}</td>
        </tr>"""

    st.markdown(f"""
    <div class="ph">Agent Rankings <span class="ph-count">{len(lb)}</span></div>
    <div class="lb-body">{lb_rows}</div>

    <div class="ph" style="margin-top:.25rem">By Adapter Type</div>
    <div style="padding:0 .75rem .75rem">
      <table class="tt">
        <thead><tr>
          <th>Agent</th><th>Type</th><th class="r">Brier</th><th class="r">PnL</th>
        </tr></thead>
        <tbody>{tt_rows}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MIDDLE — Signal matrix + Market cards  (one self-contained HTML block)
# ══════════════════════════════════════════════════════════════════════════════

with mid:
    # ---- Signal matrix ----
    q_short = {q: (q[:26]+"…" if len(q)>26 else q) for q in questions}
    sm_th   = "".join(f'<th title="{q}"><div style="max-width:80px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{q_short[q]}</div></th>' for q in questions)
    sm_rows = ""
    for agent in AGENTS:
        col = ac(agent); ico = ICONS.get(agent,"??")
        cells = ""
        for q in questions:
            row = df[(df["agent_id"]==agent) & (df["market_question"]==q)]
            if row.empty:
                cells += '<td><div class="sc sc-n"><div class="sc-pct neu">—</div></div></td>'
                continue
            r    = row.iloc[0]
            est  = float(r["estimated_probability"])
            edg  = float(r["edge_vs_market"])
            diff = est - float(r["market_probability"])
            if diff > 0.03:   scls, ec, ei = "sc-b", "#22c55e", "▲"
            elif diff < -0.03: scls, ec, ei = "sc-r", "#ef4444", "▼"
            else:              scls, ec, ei = "sc-n", "#4a6080", "—"
            cells += f"""<td>
              <div class="sc {scls}">
                <div class="sc-pct">{est:.0%}</div>
                <div class="sc-edg" style="color:{ec}">{ei} {edg:+.2f}</div>
              </div></td>"""
        sm_rows += f"""<tr>
          <td><div class="sa">
            <div class="av" style="background:{col};width:20px;height:20px;font-size:.5rem">{ico}</div>
            <span style="font-size:.68rem;font-weight:600;color:#7a8fa8;white-space:nowrap">{agent}</span>
          </div></td>{cells}</tr>"""

    # ---- Market cards ----
    mc_cards = ""
    for q in questions:
        mdf   = df[df["market_question"]==q]
        s     = mdf.iloc[0]
        mtype = s["market_type"]
        tc    = "c-sp" if mtype=="speech" else "c-lh"
        tl    = mtype.replace("_"," ").title()
        icon  = "🎙️" if mtype=="speech" else "📈"
        mkt_p = float(s["market_probability"])
        res   = s.get("final_resolution")
        ibg   = "#0c1d3a" if mtype=="long_horizon" else "#1a0c30"
        rhtml = ('<span class="chip c-yes">YES</span>' if res is True else
                 '<span class="chip c-no">NO</span>'  if res is False else
                 '<span class="chip c-opn">Open</span>')

        agent_cells = ""
        for agent in AGENTS:
            arow = mdf[mdf["agent_id"]==agent]
            if arow.empty:
                agent_cells += '<div class="mc-cell"><div class="mc-an">—</div></div>'
                continue
            r   = arow.iloc[0]
            est = float(r["estimated_probability"]); edg = float(r["edge_vs_market"])
            col = ac(agent); pw = int(est*100)
            ec  = "#22c55e" if edg>0 else ("#ef4444" if edg<0 else "#4a6080")
            agent_cells += f"""<div class="mc-cell">
              <div class="mc-an">{agent}</div>
              <div class="mc-pct">{est:.0%}</div>
              <div class="mc-edg" style="color:{ec}">{edg:+.2f}</div>
              <div class="mc-bar"><div class="mc-fill" style="width:{pw}%;background:{col}90"></div></div>
            </div>"""

        br  = mdf[mdf["agent_id"]!="market_baseline"].iloc[0]
        sp  = float(br["simulated_pnl"]); ep = float(br["edge_vs_market"])
        spc = "#22c55e" if sp>0 else "#ef4444"; epc = "#22c55e" if ep>0 else "#ef4444"

        mc_cards += f"""<div class="mc">
          <div class="mc-hd">
            <div class="mc-ico" style="background:{ibg}">{icon}</div>
            <div style="flex:1;min-width:0">
              <div class="mc-q">{q}</div>
              <div class="mc-meta">
                <span class="chip {tc}">{tl}</span>{rhtml}
                <span style="font-size:.58rem;color:#2e4060">Mkt <strong style="color:#4a6080;font-family:JetBrains Mono">{mkt_p:.0%}</strong></span>
              </div>
            </div>
          </div>
          <div class="mc-grid">{agent_cells}</div>
          <div class="mc-ft">
            <span>Edge <strong style="color:{epc}">{ep:+.3f}</strong></span>
            <span>PnL <strong style="color:{spc}">{sp:+.4f}</strong></span>
            <span>Exit <strong style="color:#4a6080">{br['exit_reason'].replace('_',' ')}</strong></span>
          </div>
        </div>"""

    st.markdown(f"""
    <div class="ph">Signal Matrix — Agent × Market
      <span class="ph-count">{len(AGENTS)}A × {len(questions)}M</span>
    </div>
    <div class="sm-wrap">
      <table class="sm">
        <thead><tr><th class="la">Agent</th>{sm_th}</tr></thead>
        <tbody>{sm_rows}</tbody>
      </table>
    </div>

    <div class="ph" style="margin-top:.25rem">Market Detail
      <span class="ph-count">{len(questions)}</span>
    </div>
    <div class="mc-wrap">{mc_cards}</div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — Charts (Plotly) + Reasoning trace viewer (selectbox + HTML)
# ══════════════════════════════════════════════════════════════════════════════

with right:
    # Brier chart
    st.markdown('<div class="rp-ph">Brier Score by Agent</div>', unsafe_allow_html=True)
    if HAS_PLOTLY:
        fig_b = go.Figure()
        for _, row in lb.iterrows():
            fig_b.add_trace(go.Bar(
                x=[row["agent_id"]], y=[row["avg_brier"]],
                marker_color=ac(row["agent_id"]), marker_line_width=0,
                text=[f"{row['avg_brier']:.3f}"], textposition="outside",
                textfont=dict(size=9, family="JetBrains Mono", color="#4a6080"),
                showlegend=False,
            ))
        fig_b.update_layout(
            height=160, bargap=0.38, margin=dict(l=0,r=0,t=5,b=0),
            plot_bgcolor="#0d1321", paper_bgcolor="#09101e",
            yaxis=dict(gridcolor="#131e30", tickfont=dict(size=8,family="JetBrains Mono",color="#2e4060"), title=None),
            xaxis=dict(tickfont=dict(size=9,family="Inter",color="#4a6080"), title=None),
        )
        st.plotly_chart(fig_b, use_container_width=True, config={"displayModeBar":False})
    else:
        st.bar_chart(lb.set_index("agent_id")["avg_brier"])

    # PnL chart
    st.markdown('<div class="rp-ph">Simulated PnL by Agent</div>', unsafe_allow_html=True)
    if HAS_PLOTLY:
        fig_p = go.Figure()
        for _, row in lb.iterrows():
            fig_p.add_trace(go.Bar(
                x=[row["agent_id"]], y=[row["total_pnl"]],
                marker_color=ac(row["agent_id"]), marker_line_width=0,
                text=[f"{row['total_pnl']:+.4f}"], textposition="outside",
                textfont=dict(size=9, family="JetBrains Mono", color="#4a6080"),
                showlegend=False,
            ))
        fig_p.update_layout(
            height=160, bargap=0.38, margin=dict(l=0,r=0,t=5,b=0),
            plot_bgcolor="#0d1321", paper_bgcolor="#09101e",
            yaxis=dict(gridcolor="#131e30", zerolinecolor="#1c2a40",
                       tickfont=dict(size=8,family="JetBrains Mono",color="#2e4060"), title=None),
            xaxis=dict(tickfont=dict(size=9,family="Inter",color="#4a6080"), title=None),
        )
        st.plotly_chart(fig_p, use_container_width=True, config={"displayModeBar":False})
    else:
        st.bar_chart(lb.set_index("agent_id")["total_pnl"])

    # Reasoning trace — selectbox is a native Streamlit component, then pure HTML traces
    st.markdown('<div class="rp-ph">Reasoning Traces</div>', unsafe_allow_html=True)
    sel_q = st.selectbox(
        "market", questions, label_visibility="collapsed",
        format_func=lambda q: q[:40]+"…" if len(q) > 40 else q,
    )

    traces_html = '<div class="trace-wrap">'
    for agent in AGENTS:
        row = df[(df["agent_id"]==agent) & (df["market_question"]==sel_q)]
        if row.empty: continue
        r   = row.iloc[0]
        est = float(r["estimated_probability"]); mkt = float(r["market_probability"])
        edg = float(r["edge_vs_market"]);        sp  = float(r["simulated_pnl"])
        bri = r.get("brier_score")
        col = ac(agent)
        ec  = "#22c55e" if edg>0 else ("#ef4444" if edg<0 else "#4a6080")
        sc  = "#22c55e" if sp>0  else ("#ef4444" if sp<0  else "#4a6080")
        bv  = f"{float(bri):.3f}" if (bri is not None and not (isinstance(bri,float) and pd.isna(bri))) else "—"
        ico = ICONS.get(agent,"??")

        traces_html += f"""
        <div class="tc">
          <div class="tc-hd">
            <div class="av" style="background:{col}">{ico}</div>
            <span style="color:{col}">{agent}</span>
          </div>
          <div class="tc-stats">
            <div class="tc-s"><div class="tc-sl">P(YES)</div><div class="tc-sv">{est:.0%}</div></div>
            <div class="tc-s"><div class="tc-sl">Edge</div><div class="tc-sv" style="color:{ec}">{edg:+.3f}</div></div>
            <div class="tc-s"><div class="tc-sl">PnL</div><div class="tc-sv" style="color:{sc}">{sp:+.4f}</div></div>
            <div class="tc-s"><div class="tc-sl">Brier</div><div class="tc-sv">{bv}</div></div>
          </div>
          <div class="tc-rt">{r['rationale']}</div>
        </div>"""

    traces_html += "</div>"
    st.markdown(traces_html, unsafe_allow_html=True)
