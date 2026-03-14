import streamlit as st
import pandas as pd
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_RESULTS = [
    {"agent_id":"claude-sonnet","market_id":"market-001","market_question":"Will the Fed cut rates in June 2025?","market_type":"long_horizon","brier_score":0.18,"edge_vs_market":0.12,"directional_correct":True,"simulated_pnl":0.15,"resolution_pnl":0.22,"exit_reason":"price_target","estimated_probability":0.65,"market_probability":0.53,"final_resolution":True,"rationale":"Recent CPI data showed cooling inflation. The Fed has signaled openness to cuts. Labor market softening supports the case for easing.","confidence":0.75,"direction":"YES"},
    {"agent_id":"gpt-4o","market_id":"market-001","market_question":"Will the Fed cut rates in June 2025?","market_type":"long_horizon","brier_score":0.24,"edge_vs_market":0.04,"directional_correct":True,"simulated_pnl":0.08,"resolution_pnl":0.12,"exit_reason":"to_resolution","estimated_probability":0.57,"market_probability":0.53,"final_resolution":True,"rationale":"Inflation is moderating but the Fed may want more data before cutting.","confidence":0.55,"direction":"YES"},
    {"agent_id":"market_baseline","market_id":"market-001","market_question":"Will the Fed cut rates in June 2025?","market_type":"long_horizon","brier_score":0.22,"edge_vs_market":0.0,"directional_correct":None,"simulated_pnl":0.0,"resolution_pnl":0.47,"exit_reason":"no_entry","estimated_probability":0.53,"market_probability":0.53,"final_resolution":True,"rationale":"Market baseline: echoes current market probability.","confidence":0.0,"direction":"PASS"},
    {"agent_id":"claude-sonnet","market_id":"market-002","market_question":"Will Powell say 'inflation' in the next FOMC presser?","market_type":"speech","brier_score":0.09,"edge_vs_market":0.18,"directional_correct":True,"simulated_pnl":0.21,"resolution_pnl":0.30,"exit_reason":"price_target","estimated_probability":0.88,"market_probability":0.70,"final_resolution":True,"rationale":"Powell has used 'inflation' in every FOMC presser since 2021. Word-frequency analysis of the last 6 transcripts shows 100% usage rate.","confidence":0.88,"direction":"YES"},
    {"agent_id":"gpt-4o","market_id":"market-002","market_question":"Will Powell say 'inflation' in the next FOMC presser?","market_type":"speech","brier_score":0.14,"edge_vs_market":0.08,"directional_correct":True,"simulated_pnl":0.11,"resolution_pnl":0.19,"exit_reason":"to_resolution","estimated_probability":0.78,"market_probability":0.70,"final_resolution":True,"rationale":"Transcript analysis supports high likelihood. Slight discount for a deliberately brief statement.","confidence":0.65,"direction":"YES"},
    {"agent_id":"market_baseline","market_id":"market-002","market_question":"Will Powell say 'inflation' in the next FOMC presser?","market_type":"speech","brier_score":0.18,"edge_vs_market":0.0,"directional_correct":None,"simulated_pnl":0.0,"resolution_pnl":0.30,"exit_reason":"no_entry","estimated_probability":0.70,"market_probability":0.70,"final_resolution":True,"rationale":"Market baseline: echoes current market probability.","confidence":0.0,"direction":"PASS"},
    {"agent_id":"claude-sonnet","market_id":"market-003","market_question":"Will Apple release a new Mac Pro in 2025?","market_type":"long_horizon","brier_score":0.31,"edge_vs_market":-0.05,"directional_correct":False,"simulated_pnl":-0.06,"resolution_pnl":-0.10,"exit_reason":"stop_loss","estimated_probability":0.40,"market_probability":0.45,"final_resolution":False,"rationale":"M3 Ultra supply constraints suggest a delay is plausible, but the model underweighted existing roadmap signals.","confidence":0.50,"direction":"NO"},
    {"agent_id":"gpt-4o","market_id":"market-003","market_question":"Will Apple release a new Mac Pro in 2025?","market_type":"long_horizon","brier_score":0.20,"edge_vs_market":0.10,"directional_correct":False,"simulated_pnl":0.04,"resolution_pnl":0.05,"exit_reason":"time_limit","estimated_probability":0.35,"market_probability":0.45,"final_resolution":False,"rationale":"Focus on AI MacBooks suggests Mac Pro refresh may slip to 2026. Underdog NO bet appears correct.","confidence":0.70,"direction":"NO"},
    {"agent_id":"market_baseline","market_id":"market-003","market_question":"Will Apple release a new Mac Pro in 2025?","market_type":"long_horizon","brier_score":0.25,"edge_vs_market":0.0,"directional_correct":None,"simulated_pnl":0.0,"resolution_pnl":0.45,"exit_reason":"no_entry","estimated_probability":0.45,"market_probability":0.45,"final_resolution":False,"rationale":"Market baseline: echoes current market probability.","confidence":0.0,"direction":"PASS"},
]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="MarketAdapters Arena", page_icon="📊",
                   layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# CSS — muted, low-contrast palette
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family:'Inter',sans-serif; background:#0e1117 !important; }
.stApp,
[data-testid="stAppViewContainer"],
section.main { background:#0e1117 !important; }
[data-testid="stHeader"] { display:none !important; }
section[data-testid="stSidebar"] { display:none !important; }
#MainMenu, footer { visibility:hidden; }

.block-container { max-width:100% !important; padding:0 !important; margin:0 !important; }

[data-testid="stHorizontalBlock"] { gap:0 !important; padding:0 !important; align-items:flex-start !important; }
[data-testid="column"] { padding:0 !important; }
[data-testid="column"]:nth-child(1) { background:#0b0e14; border-right:1px solid #1e232e; }
[data-testid="column"]:nth-child(2) { background:#0e1117; }

[data-testid="column"] [data-testid="element-container"],
[data-testid="column"] [data-testid="stVerticalBlock"] > div { margin:0 !important; padding:0 !important; gap:0 !important; }

div[data-testid="stSelectbox"] { padding:0 1rem 0.75rem !important; }
div[data-testid="stSelectbox"] label { color:#3a4455 !important; font-size:.6rem !important; font-weight:600; letter-spacing:.07em; text-transform:uppercase; }
div[data-testid="stSelectbox"] > div > div { background:#12161f !important; border:1px solid #1e232e !important; color:#8a95a8 !important; border-radius:6px !important; font-size:.78rem !important; }

::-webkit-scrollbar { width:3px; height:3px; }
::-webkit-scrollbar-track { background:#0b0e14; }
::-webkit-scrollbar-thumb { background:#1e232e; border-radius:3px; }

.pos { color:#5a9e6f !important; }
.neg { color:#9e5a5a !important; }
.neu { color:#3a4455 !important; }

/* ── Topbar ── */
.topbar {
    background:#0b0e14; border-bottom:1px solid #1e232e;
    padding:0 1.5rem; height:48px;
    display:flex; align-items:center; gap:1.5rem;
}
.t-logo { font-size:.88rem; font-weight:700; color:#c8cdd6; letter-spacing:-.01em; white-space:nowrap; }
.t-logo .acc { color:#7a8fa8; }
.t-links { display:flex; gap:2px; flex:1; }
.t-link { color:#3a4455; font-size:.71rem; font-weight:500; padding:5px 9px; border-radius:5px; }
.t-link.on { color:#8a95a8; background:#12161f; }
.t-right { display:flex; gap:7px; align-items:center; margin-left:auto; }
.tbtn { border-radius:5px; padding:4px 11px; font-size:.7rem; font-weight:600; cursor:pointer; border:none; }
.tbtn-g { background:#12161f; color:#5a6478; border:1px solid #1e232e; }
.dbadge { border-radius:4px; padding:2px 7px; font-size:.58rem; font-weight:700; letter-spacing:.07em; text-transform:uppercase; }
.dbadge-live { background:#0d1f14; color:#5a9e6f; border:1px solid #1e3a28; }
.dbadge-mock { background:#1f1608; color:#9e8050; border:1px solid #3a2a10; }

/* ── KPI strip ── */
.kpi-strip {
    background:#0b0e14; border-bottom:1px solid #1e232e;
    padding:.5rem 1.5rem;
    display:grid; grid-template-columns:repeat(4,1fr); gap:.5rem;
}
.kpi-box { background:#12161f; border:1px solid #1e232e; border-radius:7px; padding:.5rem .7rem; }
.kpi-box.hi { border-color:#2a3040; }
.kpi-lbl { font-size:.55rem; font-weight:600; color:#3a4455; letter-spacing:.07em; text-transform:uppercase; margin-bottom:2px; }
.kpi-val { font-size:1rem; font-weight:700; font-family:'JetBrains Mono',monospace; color:#c8cdd6; line-height:1.1; }
.kpi-sub { font-size:.58rem; color:#3a4455; margin-top:1px; }

/* ── Panel header ── */
.ph {
    font-size:.56rem; font-weight:700; color:#3a4455;
    letter-spacing:.1em; text-transform:uppercase;
    padding:.7rem 1rem .4rem; border-bottom:1px solid #12161f;
    margin-bottom:.5rem; display:flex; align-items:center; justify-content:space-between;
}
.ph-count { background:#12161f; color:#3a4455; border-radius:100px; padding:1px 6px; font-size:.54rem; font-weight:600; }

/* ── Leaderboard ── */
.lb-body { padding:0 .75rem .75rem; display:flex; flex-direction:column; gap:3px; }
.lb-row {
    background:#12161f; border:1px solid #1e232e; border-radius:7px;
    padding:.55rem .7rem;
    display:grid; grid-template-columns:18px 24px 1fr auto auto;
    align-items:center; gap:.45rem;
}
.lb-row.top { border-left:2px solid #4a5568; }
.lbr-rk { font-size:.62rem; font-weight:700; color:#3a4455; text-align:center; font-family:'JetBrains Mono',monospace; }
.lbr-rk.r1 { color:#8a95a8; }
.lbr-rk.r2 { color:#5a6478; }
.lbr-rk.r3 { color:#4a5568; }
.av { width:24px; height:24px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:.52rem; font-weight:700; color:#c8cdd6; flex-shrink:0; }
.lbr-info { min-width:0; }
.lbr-nm  { font-size:.73rem; font-weight:600; color:#8a95a8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.lbr-sub { font-size:.56rem; color:#3a4455; margin-top:1px; }

/* ── Wallet badge ── */
.wallet { text-align:right; white-space:nowrap; }
.w-bal { font-size:.8rem; font-weight:700; font-family:'JetBrains Mono',monospace; line-height:1.1; }
.w-chg { font-size:.56rem; font-weight:600; font-family:'JetBrains Mono',monospace; margin-top:1px; }

/* ── Edge badge ── */
.edgebadge { text-align:right; white-space:nowrap; }
.eb-val { font-size:.72rem; font-weight:600; font-family:'JetBrains Mono',monospace; }
.eb-lbl { font-size:.5rem; color:#3a4455; letter-spacing:.05em; text-transform:uppercase; }

/* ── Type chips ── */
.chip { display:inline-block; border-radius:4px; padding:1px 6px; font-size:.54rem; font-weight:600; letter-spacing:.04em; text-transform:uppercase; }
.c-lh  { background:#111827; color:#6b7a94; border:1px solid #1e2a3a; }
.c-sp  { background:#141118; color:#7a6b94; border:1px solid #2a1e3a; }
.c-yes { background:#0d1a12; color:#5a9e6f; border:1px solid #1e3a28; }
.c-no  { background:#1a0d0d; color:#9e5a5a; border:1px solid #3a1e1e; }
.c-opn { background:#12161f; color:#4a5568; border:1px solid #1e232e; }
.dir-yes { background:#0d1a12; color:#5a9e6f; border:1px solid #1a3022; padding:1px 5px; border-radius:3px; font-size:.52rem; font-weight:700; letter-spacing:.04em; }
.dir-no  { background:#1a0d0d; color:#9e5a5a; border:1px solid #301a1a; padding:1px 5px; border-radius:3px; font-size:.52rem; font-weight:700; letter-spacing:.04em; }
.dir-pass{ background:#12161f; color:#3a4455; border:1px solid #1e232e; padding:1px 5px; border-radius:3px; font-size:.52rem; font-weight:700; letter-spacing:.04em; }

/* ── Market cards ── */
.mc-wrap { padding:0 .75rem .75rem; display:flex; flex-direction:column; gap:.5rem; }
.mc { background:#12161f; border:1px solid #1e232e; border-radius:8px; overflow:hidden; }
.mc-hd { padding:.55rem .7rem .45rem; display:flex; gap:.55rem; align-items:flex-start; border-bottom:1px solid #1a1e28; }
.mc-ico { width:28px; height:28px; border-radius:6px; display:flex; align-items:center; justify-content:center; font-size:.8rem; flex-shrink:0; }
.mc-q { font-size:.76rem; font-weight:600; color:#8a95a8; line-height:1.35; margin-bottom:.2rem; }
.mc-meta { display:flex; gap:.3rem; flex-wrap:wrap; align-items:center; }
.mc-agents { display:flex; flex-direction:column; gap:0; }
.mc-arow {
    display:grid; grid-template-columns:90px 50px 1fr 68px 52px;
    align-items:center; gap:.45rem;
    padding:.35rem .7rem;
    border-bottom:1px solid #12161f;
}
.mc-arow:last-child { border-bottom:none; }
.mc-aname { display:flex; align-items:center; gap:5px; }
.mc-anm { font-size:.66rem; font-weight:500; color:#5a6478; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mc-prob { font-size:.78rem; font-weight:700; font-family:'JetBrains Mono',monospace; color:#8a95a8; text-align:right; }
.mc-bar-wrap { position:relative; height:3px; background:#1a1e28; border-radius:2px; overflow:hidden; }
.mc-bar-fill { position:absolute; top:0; left:0; height:100%; border-radius:2px; }
.mc-edgcell { font-size:.63rem; font-weight:600; font-family:'JetBrains Mono',monospace; text-align:right; white-space:nowrap; color:#3a4455; }
.mc-stake { font-size:.6rem; font-family:'JetBrains Mono',monospace; text-align:right; white-space:nowrap; color:#4a5568; }

/* ── Reasoning traces ── */
.trace-wrap { padding:0 .75rem .75rem; display:flex; flex-direction:column; gap:.4rem; }
.tc { background:#12161f; border:1px solid #1e232e; border-radius:7px; padding:.6rem .7rem; }
.tc-hd { display:flex; align-items:center; gap:6px; font-size:.63rem; font-weight:600; letter-spacing:.04em; text-transform:uppercase; margin-bottom:.4rem; color:#5a6478; }
.tc-stats { display:grid; grid-template-columns:repeat(4,1fr); gap:.25rem; margin-bottom:.35rem; }
.tc-s { background:#0e1117; border:1px solid #1e232e; border-radius:4px; padding:.28rem .35rem; text-align:center; }
.tc-sl { font-size:.5rem; color:#3a4455; font-weight:600; letter-spacing:.04em; text-transform:uppercase; }
.tc-sv { font-size:.74rem; font-weight:600; font-family:'JetBrains Mono',monospace; color:#8a95a8; }
.tc-rt { font-size:.68rem; color:#4a5568; line-height:1.6; padding:.4rem .5rem; background:#0e1117; border-radius:4px; border-left:2px solid #1e232e; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data load
# ---------------------------------------------------------------------------

RESULTS_PATH = Path("data/results.json")
using_mock   = not RESULTS_PATH.exists()
results      = MOCK_RESULTS if using_mock else json.loads(RESULTS_PATH.read_text())

df = pd.DataFrame(results)
for c in ["brier_score","edge_vs_market","simulated_pnl","resolution_pnl",
          "estimated_probability","market_probability"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

if "confidence" not in df.columns:
    df["confidence"] = 0.5
else:
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.5)

# Direction from data if present, else infer: YES if prob >= 0.5, NO if prob < 0.5, PASS if prob == 0
def infer_direction(row):
    if "direction" in row and str(row.get("direction","")).upper() in ("YES","NO","PASS"):
        return str(row["direction"]).upper()
    prob = float(row.get("estimated_probability", 0.5))
    if prob == 0.0:
        return "PASS"
    return "YES" if prob >= 0.5 else "NO"

df["direction"] = df.apply(infer_direction, axis=1)

# ---------------------------------------------------------------------------
# Wallet calculation — probability-weighted allocation
# ---------------------------------------------------------------------------
# Each agent has $1,000 total budget split across all markets.
# Allocation per market = (estimated_probability / sum_of_all_probs) * $1,000
# 0% probability = $0 allocated (PASS).
# pnl_dollars = allocation * simulated_pnl
# final wallet = $1,000 + sum(pnl_dollars)  [gains/losses on top of starting balance]

STARTING_BALANCE = 1000.0

# Compute total probability weight per agent across all markets
prob_totals = df[df["direction"] != "PASS"].groupby("agent_id")["estimated_probability"].sum().rename("prob_total")
df = df.join(prob_totals, on="agent_id")
df["prob_total"] = df["prob_total"].fillna(1.0)

def calc_stake(row):
    if str(row.get("direction", "PASS")).upper() == "PASS":
        return 0.0
    prob = float(row.get("estimated_probability", 0.0))
    if prob == 0.0:
        return 0.0
    total = float(row.get("prob_total", 1.0))
    return (prob / total) * STARTING_BALANCE

df["stake"]       = df.apply(calc_stake, axis=1)
df["pnl_dollars"] = df["stake"] * df["simulated_pnl"]

# Leaderboard aggregation
lb = (
    df.groupby("agent_id")
    .agg(avg_brier=("brier_score","mean"), avg_edge=("edge_vs_market","mean"),
         total_pnl=("simulated_pnl","sum"), total_pnl_dollars=("pnl_dollars","sum"),
         markets=("market_id","nunique"))
    .reset_index().sort_values("avg_edge", ascending=False).reset_index(drop=True)
)

lb["wallet"]     = STARTING_BALANCE + lb["total_pnl_dollars"]
lb["wallet_pct"] = (lb["wallet"] - STARTING_BALANCE) / STARTING_BALANCE

all_agents = lb["agent_id"].tolist()
questions  = df["market_question"].unique().tolist()
n_mkts     = int(df["market_id"].nunique())
n_types    = df["market_type"].nunique()

ai_lb       = lb[lb["agent_id"] != "market_baseline"]
best        = ai_lb.iloc[0] if not ai_lb.empty else lb.iloc[0]
avg_edge    = float(ai_lb["avg_edge"].mean()) if not ai_lb.empty else 0.0
best_wallet = float(ai_lb["wallet"].max()) if not ai_lb.empty else STARTING_BALANCE

# Color palette — muted, desaturated
PALETTE = ["#5a7a9e","#7a6b8a","#4a8a6a","#8a7a4a","#7a4a5a","#4a7a8a"]
COLOR_MAP = {}
pi = 0
for a in all_agents:
    if a == "market_baseline":
        COLOR_MAP[a] = "#2e3a4a"
    else:
        COLOR_MAP[a] = PALETTE[pi % len(PALETTE)]
        pi += 1

def ac(a):  return COLOR_MAP.get(a, "#5a7a9e")
def pc(v):  return "pos" if v > 0.001 else ("neg" if v < -0.001 else "neu")
def pcs(v): return "#5a9e6f" if v > 0.001 else ("#9e5a5a" if v < -0.001 else "#3a4455")

def agent_initials(name):
    parts = name.replace("-", " ").replace("_", " ").split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()

# ---------------------------------------------------------------------------
# Topbar
# ---------------------------------------------------------------------------

bc_cls = "dbadge-mock" if using_mock else "dbadge-live"
bc_txt = "MOCK"        if using_mock else "● LIVE"

st.markdown(f"""
<div class="topbar">
  <div class="t-logo">MarketAdapters <span class="acc">Arena</span></div>
  <div class="t-links">
    <span class="t-link on">Dashboard</span>
    <span class="t-link">Markets</span>
    <span class="t-link">Adapters</span>
    <span class="t-link">Replay</span>
  </div>
  <div class="t-right">
    <span class="dbadge {bc_cls}">{bc_txt}</span>
    <button class="tbtn tbtn-g">Run Evaluation</button>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------

best_wallet_pct = (best_wallet - STARTING_BALANCE) / STARTING_BALANCE
wc = "#5a9e6f" if best_wallet_pct >= 0 else "#9e5a5a"
ec = "#5a9e6f" if avg_edge > 0 else "#9e5a5a"

st.markdown(f"""
<div class="kpi-strip">
  <div class="kpi-box hi">
    <div class="kpi-lbl">Top Agent</div>
    <div class="kpi-val" style="font-size:.8rem;font-family:'Inter',sans-serif;color:#8a95a8">{best['agent_id']}</div>
    <div class="kpi-sub">avg edge {best['avg_edge']:+.3f}</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Best Wallet</div>
    <div class="kpi-val" style="color:{wc}">${best_wallet:,.2f}</div>
    <div class="kpi-sub">{best_wallet_pct:+.1%} from $1,000</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Avg Edge</div>
    <div class="kpi-val" style="color:{ec}">{avg_edge:+.3f}</div>
    <div class="kpi-sub">all AI agents</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Markets / Types</div>
    <div class="kpi-val">{n_mkts}<span style="font-size:.6rem;color:#3a4455;font-family:'Inter',sans-serif"> / {n_types}</span></div>
    <div class="kpi-sub">evaluated</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Two columns
# ---------------------------------------------------------------------------

left, right = st.columns([2.8, 7.2])

# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Leaderboard + Reasoning traces
# ══════════════════════════════════════════════════════════════════════════════

with left:
    lb_rows = ""
    for i, row in lb.iterrows():
        rc  = ["r1","r2","r3"][i] if i < 3 else ""
        top = "top" if i == 0 else ""
        col = ac(row["agent_id"])
        ico = agent_initials(row["agent_id"])
        ep  = pc(row["avg_edge"])
        w   = row["wallet"]
        wp  = row["wallet_pct"]
        wc2 = "#5a9e6f" if wp >= 0 else "#9e5a5a"
        lb_rows += f"""
        <div class="lb-row {top}">
          <div class="lbr-rk {rc}">{i+1}</div>
          <div class="av" style="background:{col}">{ico}</div>
          <div class="lbr-info">
            <div class="lbr-nm">{row['agent_id']}</div>
            <div class="lbr-sub">{int(row['markets'])} markets</div>
          </div>
          <div class="edgebadge">
            <div class="eb-val {ep}">{row['avg_edge']:+.3f}</div>
            <div class="eb-lbl">edge</div>
          </div>
          <div class="wallet">
            <div class="w-bal" style="color:{wc2}">${w:,.0f}</div>
            <div class="w-chg" style="color:{wc2}">{wp:+.1%}</div>
          </div>
        </div>"""

    st.markdown(f"""
    <div class="ph">Leaderboard <span class="ph-count">{len(lb)}</span></div>
    <div class="lb-body">{lb_rows}</div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ph" style="margin-top:.25rem">Reasoning Traces</div>', unsafe_allow_html=True)
    sel_q = st.selectbox(
        "market", questions, label_visibility="collapsed",
        format_func=lambda q: q[:46]+"…" if len(q) > 46 else q,
    )

    traces_html = '<div class="trace-wrap">'
    for agent in all_agents:
        row = df[(df["agent_id"] == agent) & (df["market_question"] == sel_q)]
        if row.empty:
            continue
        r   = row.iloc[0]
        est = float(r["estimated_probability"])
        edg = float(r["edge_vs_market"])
        sp  = float(r["simulated_pnl"])
        stk = float(r["stake"])
        pnl_d = float(r["pnl_dollars"])
        col = ac(agent)
        ico = agent_initials(agent)
        ec2 = pcs(edg)
        sc2 = pcs(sp)
        dc2 = pcs(pnl_d)
        direction = str(r.get("direction", "PASS")).upper()
        dir_cls = {"YES":"dir-yes","NO":"dir-no"}.get(direction,"dir-pass")

        traces_html += f"""
        <div class="tc">
          <div class="tc-hd">
            <div class="av" style="background:{col};width:20px;height:20px">{ico}</div>
            <span>{agent}</span>
            <span class="{dir_cls}" style="margin-left:auto">{direction}</span>
          </div>
          <div class="tc-stats">
            <div class="tc-s"><div class="tc-sl">P(YES)</div><div class="tc-sv">{est:.0%}</div></div>
            <div class="tc-s"><div class="tc-sl">Edge</div><div class="tc-sv" style="color:{ec2}">{edg:+.3f}</div></div>
            <div class="tc-s"><div class="tc-sl">Stake</div><div class="tc-sv">${stk:.0f}</div></div>
            <div class="tc-s"><div class="tc-sl">P&L</div><div class="tc-sv" style="color:{dc2}">{pnl_d:+.2f}</div></div>
          </div>
          <div class="tc-rt">{r['rationale']}</div>
        </div>"""

    traces_html += "</div>"
    st.markdown(traces_html, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — Market cards
# ══════════════════════════════════════════════════════════════════════════════

with right:
    mc_cards = ""
    for q in questions:
        mdf   = df[df["market_question"] == q]
        s     = mdf.iloc[0]
        mtype = s["market_type"]
        tc    = "c-sp" if mtype == "speech" else "c-lh"
        tl    = mtype.replace("_", " ").title()
        icon  = "🎙" if mtype == "speech" else "📈"
        mkt_p = float(s["market_probability"])
        res   = s.get("final_resolution")
        ibg   = "#0f1520" if mtype == "long_horizon" else "#12101a"
        rhtml = ('<span class="chip c-yes">YES</span>' if res is True else
                 '<span class="chip c-no">NO</span>'   if res is False else
                 '<span class="chip c-opn">Open</span>')

        agent_rows = ""
        for agent in all_agents:
            arow = mdf[mdf["agent_id"] == agent]
            if arow.empty:
                continue
            r         = arow.iloc[0]
            est       = float(r["estimated_probability"])
            edg       = float(r["edge_vs_market"])
            stk       = float(r["stake"])
            pnl_d     = float(r["pnl_dollars"])
            direction = str(r.get("direction","PASS")).upper()
            col       = ac(agent)
            ico       = agent_initials(agent)
            pw        = int(est * 100)
            ec2       = pcs(edg)
            dc2       = pcs(pnl_d)
            dir_cls   = {"YES":"dir-yes","NO":"dir-no"}.get(direction,"dir-pass")
            stake_txt = f"${stk:.0f}" if stk > 0 else "—"
            pnl_txt   = f"{pnl_d:+.2f}" if stk > 0 else "—"

            agent_rows += f"""
            <div class="mc-arow">
              <div class="mc-aname">
                <div class="av" style="background:{col};width:18px;height:18px;font-size:.48rem">{ico}</div>
                <span class="mc-anm">{agent}</span>
              </div>
              <div class="mc-prob">{est:.0%}</div>
              <div class="mc-bar-wrap">
                <div class="mc-bar-fill" style="width:{pw}%;background:{col}70"></div>
              </div>
              <div class="mc-stake">
                <span class="{dir_cls}">{direction}</span> {stake_txt}
              </div>
              <div class="mc-edgcell" style="color:{dc2}">{pnl_txt}</div>
            </div>"""

        mc_cards += f"""<div class="mc">
          <div class="mc-hd">
            <div class="mc-ico" style="background:{ibg}">{icon}</div>
            <div style="flex:1;min-width:0">
              <div class="mc-q">{q}</div>
              <div class="mc-meta">
                <span class="chip {tc}">{tl}</span>{rhtml}
                <span style="font-size:.56rem;color:#3a4455">Mkt <strong style="color:#5a6478;font-family:'JetBrains Mono',monospace">{mkt_p:.0%}</strong></span>
              </div>
            </div>
          </div>
          <div class="mc-agents">{agent_rows}</div>
        </div>"""

    st.markdown(f"""
    <div class="ph">Market Detail <span class="ph-count">{len(questions)}</span></div>
    <div class="mc-wrap">{mc_cards}</div>
    """, unsafe_allow_html=True)
