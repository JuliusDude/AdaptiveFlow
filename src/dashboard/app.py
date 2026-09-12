"""Streamlit Interactive Dashboard for AdaptiveFlow.

Visualizes 4-way intersection dynamics, live signal phases, real-time ML decisions,
and head-to-head performance benchmarks between Fixed-Time and ML Adaptive controllers.
"""

import json
from pathlib import Path
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.features.feature_engineering import extract_features
from src.ml.predict import SignalTimingPredictor, AdaptiveMLController
from src.simulator.intersection import IntersectionSimulation
from src.simulator.signal import TIMING_PLANS, TrafficSignal
from src.simulator.traffic_generator import TrafficGenerator, SCENARIO_PRESETS


st.set_page_config(
    page_title="AdaptiveFlow | Predictive Signal Control",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_predictor() -> SignalTimingPredictor:
    """Load and cache the trained Random Forest predictor."""
    return SignalTimingPredictor()


@st.cache_data
def load_training_metrics() -> Dict[str, Any]:
    """Load offline model training metrics."""
    path = Path("results/metrics/training_metrics.json")
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {}


def init_session_state() -> None:
    """Initialize session state variables for simulation playback."""
    if "sim_fixed" not in st.session_state or "sim_ml" not in st.session_state:
        reset_simulation("balanced")


def reset_simulation(preset: str, custom_rates: Dict[str, float] = None, seed: int = 42) -> None:
    """Reset both Fixed and ML simulations with identical traffic demand."""
    rates = custom_rates if custom_rates is not None else SCENARIO_PRESETS.get(preset, SCENARIO_PRESETS["balanced"])

    # Fixed-time baseline simulation (P4: 30s NS, 30s EW)
    fixed_gen = TrafficGenerator(rates=rates, seed=seed)
    fixed_signal = TrafficSignal(initial_plan="P4")
    st.session_state.sim_fixed = IntersectionSimulation(signal=fixed_signal, generator=fixed_gen, seed=seed)

    # Adaptive ML simulation
    ml_gen = TrafficGenerator(rates=rates, seed=seed)
    ml_signal = TrafficSignal(initial_plan="P4")
    st.session_state.sim_ml = IntersectionSimulation(signal=ml_signal, generator=ml_gen, seed=seed)
    st.session_state.ml_controller = AdaptiveMLController(predictor=get_predictor())

    # Initial ML decision
    st.session_state.ml_controller.update(st.session_state.sim_ml, force_update=True)
    st.session_state.sim_history = []
    st.session_state.current_preset = preset


def step_both_simulations(num_steps: int = 1) -> None:
    """Advance both Fixed Baseline and ML Adaptive simulations simultaneously."""
    for _ in range(num_steps):
        st.session_state.sim_fixed.step(dt=1.0)
        st.session_state.sim_ml.step(dt=1.0)
        st.session_state.ml_controller.update(st.session_state.sim_ml)

        # Record time-series telemetry
        t = st.session_state.sim_ml.current_time
        f_summary = st.session_state.sim_fixed.get_summary()
        m_summary = st.session_state.sim_ml.get_summary()

        st.session_state.sim_history.append({
            "time": t,
            "fixed_delay": f_summary.get("comprehensive_delay", f_summary["average_delay"]),
            "ml_delay": m_summary.get("comprehensive_delay", m_summary["average_delay"]),
            "fixed_queue": f_summary["average_queue"],
            "ml_queue": m_summary["average_queue"],
            "fixed_throughput": f_summary["throughput_vph"],
            "ml_throughput": m_summary["throughput_vph"],
        })


def render_signal_badge(color: str) -> str:
    """Return colored HTML pill badge for signal color."""
    colors = {
        "GREEN": "#28a745",
        "YELLOW": "#ffc107",
        "RED": "#dc3545",
    }
    hex_col = colors.get(color, "#6c757d")
    text_col = "#000" if color == "YELLOW" else "#fff"
    return f"<span style='background-color:{hex_col};color:{text_col};padding:3px 10px;border-radius:12px;font-weight:bold;'>{color}</span>"


def main() -> None:
    init_session_state()

    # --- Sidebar Controls ---
    st.sidebar.title("🚦 AdaptiveFlow Control")
    st.sidebar.caption("Closed-Loop Adaptive Signal Optimization")

    preset = st.sidebar.selectbox(
        "Traffic Demand Preset",
        options=list(SCENARIO_PRESETS.keys()) + ["custom"],
        index=0,
    )

    custom_rates = None
    if preset == "custom":
        st.sidebar.subheader("Approach Arrival Rates (veh/min)")
        r_n = st.sidebar.slider("North Rate", 5.0, 50.0, 25.0, 1.0)
        r_s = st.sidebar.slider("South Rate", 5.0, 50.0, 15.0, 1.0)
        r_e = st.sidebar.slider("East Rate", 5.0, 50.0, 10.0, 1.0)
        r_w = st.sidebar.slider("West Rate", 5.0, 50.0, 10.0, 1.0)
        custom_rates = {"N": r_n, "S": r_s, "E": r_e, "W": r_w}

    # Auto-detect preset changes and reset simulation
    if st.session_state.get("current_preset") != preset:
        reset_simulation(preset, custom_rates)

    if st.sidebar.button("🔄 Reset Simulation", use_container_width=True):
        reset_simulation(preset, custom_rates)
        st.rerun()

    sim_duration = st.sidebar.radio("Simulate Forward By:", [1, 10, 35, 70, 140], index=3, horizontal=True)
    if st.sidebar.button(f"▶️ Advance {sim_duration}s", type="primary", use_container_width=True):
        step_both_simulations(sim_duration)
        st.rerun()

    st.sidebar.divider()
    st.sidebar.markdown("### ⚙️ Current Timing Plans")
    st.sidebar.markdown("**Fixed Baseline:** `P4` (30s NS / 30s EW)")
    active_ml_plan = st.session_state.sim_ml.signal.current_plan_name
    active_plan_info = TIMING_PLANS[active_ml_plan]
    st.sidebar.markdown(f"**ML Adaptive Active:** `{active_ml_plan}` ({active_plan_info['NS']}s NS / {active_plan_info['EW']}s EW)")

    # --- Main Header ---
    st.title("Predictive Urban Intersection Management")
    st.markdown(
        "**Closed-Loop Adaptive Traffic Signal Control using Supervised Random Forest Machine Learning.**  \n"
        "Compares real-time ML-driven dynamic green allocations against a fixed-time (30s/30s) baseline."
    )

    sim_ml = st.session_state.sim_ml
    sim_fixed = st.session_state.sim_fixed
    ml_controller = st.session_state.ml_controller

    # Top Status Bar
    t_now = int(sim_ml.current_time)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Simulation Clock", f"{t_now} s", f"{round(t_now / 70.0, 1)} Cycles")
    c2.metric("ML Active Plan", active_ml_plan, f"NS: {active_plan_info['NS']}s | EW: {active_plan_info['EW']}s")
    c3.metric("Fixed Plan", "P4", "NS: 30s | EW: 30s")
    c4.metric("Cycle Counter", f"{sim_ml.signal.cycle_count} Completed")

    st.divider()

    # --- Section 1: Intersection Visual & Live Telemetry ---
    col_vis, col_telemetry = st.columns([3, 2])

    with col_vis:
        st.subheader("📍 4-Way Intersection Real-Time State")

        # Visual layout for signals & queues
        ns_color = sim_ml.signal.get_signal_color("N")
        ew_color = sim_ml.signal.get_signal_color("E")

        q_n = len([v for v in sim_ml.vehicles["N"] if v.state == "queued"])
        q_s = len([v for v in sim_ml.vehicles["S"] if v.state == "queued"])
        q_e = len([v for v in sim_ml.vehicles["E"] if v.state == "queued"])
        q_w = len([v for v in sim_ml.vehicles["W"] if v.state == "queued"])

        c_n = len(sim_ml.vehicles["N"])
        c_s = len(sim_ml.vehicles["S"])
        c_e = len(sim_ml.vehicles["E"])
        c_w = len(sim_ml.vehicles["W"])

        # Schematic cards
        st.markdown(f"""
        <div style="background-color:#1e1e24;padding:15px;border-radius:10px;text-align:center;">
            <div style="font-size:16px;font-weight:bold;color:#4da6ff;">NORTH APPROACH</div>
            <div>Signal: {render_signal_badge(ns_color)} &nbsp;|&nbsp; <b>Vehicles:</b> {c_n} &nbsp;|&nbsp; <b>Queue:</b> {q_n}</div>
            <div style="margin:20px 0;display:flex;justify-content:space-around;align-items:center;">
                <div style="width:40%;text-align:left;">
                    <div style="font-weight:bold;color:#ffa31a;">WEST APPROACH</div>
                    <div>Signal: {render_signal_badge(ew_color)}</div>
                    <div>Vehicles: {c_w} | Queue: {q_w}</div>
                </div>
                <div style="border:2px dashed #888;padding:15px 25px;border-radius:8px;font-size:14px;background:#2a2a35;">
                    <b>INTERSECTION</b><br>
                    Phase: {sim_ml.signal.current_phase.value}<br>
                    Elapsed: {int(sim_ml.signal.phase_elapsed_time)} s
                </div>
                <div style="width:40%;text-align:right;">
                    <div style="font-weight:bold;color:#ffa31a;">EAST APPROACH</div>
                    <div>Signal: {render_signal_badge(ew_color)}</div>
                    <div>Vehicles: {c_e} | Queue: {q_e}</div>
                </div>
            </div>
            <div style="font-size:16px;font-weight:bold;color:#4da6ff;">SOUTH APPROACH</div>
            <div>Signal: {render_signal_badge(ns_color)} &nbsp;|&nbsp; <b>Vehicles:</b> {c_s} &nbsp;|&nbsp; <b>Queue:</b> {q_s}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_telemetry:
        st.subheader("📊 22-Feature Live Vector")
        features = extract_features(sim_ml)
        feat_df = pd.DataFrame([
            {"Category": "Demand (Vehicles)", "N": features["N_count"], "S": features["S_count"], "E": features["E_count"], "W": features["W_count"]},
            {"Category": "Queues (Stopped)", "N": features["N_queue"], "S": features["S_queue"], "E": features["E_queue"], "W": features["W_queue"]},
            {"Category": "Arrivals (veh/min)", "N": features["N_arrival"], "S": features["S_arrival"], "E": features["E_arrival"], "W": features["W_arrival"]},
            {"Category": "Speed (m/s)", "N": features["N_speed"], "S": features["S_speed"], "E": features["E_speed"], "W": features["W_speed"]},
            {"Category": "Queue Growth", "N": features["N_queue_growth"], "S": features["S_queue_growth"], "E": features["E_queue_growth"], "W": features["W_queue_growth"]},
        ])
        st.dataframe(feat_df, use_container_width=True, hide_index=True)
        st.caption(f"Signal State: Phase={int(features['current_phase'])} ({'N/S' if features['current_phase']==0 else 'E/W'}), Elapsed={features['elapsed_phase_time']}s")

    st.divider()

    # --- Section 2: Head-to-Head Comparative Benchmark ---
    st.subheader("⚖️ Live Performance Comparison: Fixed Baseline vs ML Adaptive")

    f_res = sim_fixed.get_summary()
    m_res = sim_ml.get_summary()

    f_comp_delay = f_res.get("comprehensive_delay", f_res["average_delay"])
    m_comp_delay = m_res.get("comprehensive_delay", m_res["average_delay"])
    comp_delay_diff_pct = ((f_comp_delay - m_comp_delay) / max(0.1, f_comp_delay)) * 100.0 if f_comp_delay > 0 else 0.0

    f_queue = f_res["average_queue"]
    m_queue = m_res["average_queue"]
    queue_diff_pct = ((f_queue - m_queue) / max(0.1, f_queue)) * 100.0 if f_queue > 0 else 0.0

    f_tp = f_res["throughput_vph"]
    m_tp = m_res["throughput_vph"]
    tp_diff = m_tp - f_tp

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Comprehensive Delay", f"{m_comp_delay:.2f} s", f"{comp_delay_diff_pct:+.1f}% vs Fixed ({f_comp_delay:.2f}s)", delta_color="inverse")
    m2.metric("Average Queue Length", f"{m_queue:.2f}", f"{queue_diff_pct:+.1f}% vs Fixed ({f_queue:.2f})", delta_color="inverse")
    m3.metric("Throughput", f"{m_tp:.0f} vph", f"{tp_diff:+.0f} vph vs Fixed ({f_tp:.0f})")
    m4.metric("Exited Trips (Delay)", f"{m_res['total_exited']} ({m_res['average_delay']:.1f}s)", f"vs Fixed: {f_res['total_exited']} ({f_res['average_delay']:.1f}s)")

    # Time series charts
    if st.session_state.sim_history:
        hist_df = pd.DataFrame(st.session_state.sim_history)
        ch_col1, ch_col2 = st.columns(2)
        with ch_col1:
            st.markdown("##### ⏱️ Comprehensive Vehicle Delay Over Time (s)")
            delay_chart_df = hist_df.rename(
                columns={"fixed_delay": "Fixed Delay", "ml_delay": "ML Adaptive Delay"}
            ).set_index("time")[["Fixed Delay", "ML Adaptive Delay"]]
            st.line_chart(delay_chart_df, color=["#dc3545", "#28a745"])
            st.caption("Comprehensive delay accounts for completed trips plus active queued and crawling vehicles.")
        with ch_col2:
            st.markdown("##### 🚗 Average Queue Length Over Time")
            queue_chart_df = hist_df.rename(
                columns={"fixed_queue": "Fixed Queue", "ml_queue": "ML Adaptive Queue"}
            ).set_index("time")[["Fixed Queue", "ML Adaptive Queue"]]
            st.line_chart(queue_chart_df, color=["#dc3545", "#28a745"])
            st.caption("Aggregate stopped and buffered queue count across all approaches.")

    st.divider()

    # --- Section 3: Machine Learning Model Insights ---
    st.subheader("🧠 Model Decision History & Probabilities")
    col_decisions, col_model = st.columns([3, 2])

    with col_decisions:
        st.markdown("##### Recent ML Controller Decisions")
        if ml_controller.decision_history:
            recent_decisions = list(reversed(ml_controller.decision_history[-8:]))
            dec_table = []
            for d in recent_decisions:
                dec_table.append({
                    "Time (s)": int(d["time"]),
                    "Cycle": d["cycle"],
                    "Plan": d["selected_plan"],
                    "N/S Green": f"{d['ns_green']}s",
                    "E/W Green": f"{d['ew_green']}s",
                })
            st.dataframe(pd.DataFrame(dec_table), use_container_width=True, hide_index=True)
        else:
            st.info("No cycle transitions logged yet. Advance the simulation to see ML decisions.")

    with col_model:
        st.markdown("##### Top Feature Importances (Random Forest)")
        train_metrics = load_training_metrics()
        if "feature_importances" in train_metrics:
            top_feats = list(train_metrics["feature_importances"].items())[:6]
            imp_df = pd.DataFrame(top_feats, columns=["Feature", "Importance"]).set_index("Feature")
            st.bar_chart(imp_df, horizontal=True)
        else:
            st.caption("Training metrics not found. Run model training to view feature importances.")


if __name__ == "__main__":
    main()
