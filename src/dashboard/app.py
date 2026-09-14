"""Streamlit Interactive Dashboard for AdaptiveFlow.

Rebuilt with Taste-Skill design principles (Ethereal Dark Cockpit theme, double-bezel cards),
hardware-accelerated 60 FPS HTML5 Canvas / SVG 4-way intersection simulation, real-time
moving vehicles with dynamic braking tail lights, physical traffic signal heads with
countdown timers, and a complete playback deck (Play, Pause, Rewind, Forward, Scrub).
"""

import sys
from pathlib import Path

# Ensure repository root is in sys.path regardless of working directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json
from typing import Dict, List, Any
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.features.feature_engineering import extract_features
from src.ml.predict import SignalTimingPredictor, AdaptiveMLController
from src.simulator.intersection import IntersectionSimulation
from src.simulator.signal import TIMING_PLANS, TrafficSignal
from src.simulator.traffic_generator import TrafficGenerator, SCENARIO_PRESETS
from src.dashboard.playback import SimulationPlaybackBuffer
from src.dashboard.canvas_visualizer import generate_intersection_html
from src.dashboard.styles import COCKPIT_CSS


st.set_page_config(
    page_title="AdaptiveFlow | Predictive Signal Control",
    page_icon=None,
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
    if "playback_buffer" not in st.session_state:
        buffer = SimulationPlaybackBuffer(preset="balanced", seed=42, predictor=get_predictor())
        # Buffer initial 140s (2 full signal cycles) for immediate scrubbing
        buffer.buffer_horizon(140)
        st.session_state.playback_buffer = buffer
        st.session_state.sim_fixed = buffer.sim_fixed
        st.session_state.sim_ml = buffer.sim_ml
        st.session_state.ml_controller = buffer.ml_controller
        st.session_state.current_preset = "balanced"


def reset_simulation(preset: str, custom_rates: Dict[str, float] = None, seed: int = 42) -> None:
    """Reset simulation playback buffer with updated traffic demand rates."""
    buffer = SimulationPlaybackBuffer(
        preset=preset,
        custom_rates=custom_rates,
        seed=seed,
        predictor=get_predictor(),
    )
    buffer.buffer_horizon(140)
    st.session_state.playback_buffer = buffer
    st.session_state.sim_fixed = buffer.sim_fixed
    st.session_state.sim_ml = buffer.sim_ml
    st.session_state.ml_controller = buffer.ml_controller
    st.session_state.current_preset = preset


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
    # Inject Taste-Skill Dark Cockpit CSS
    st.markdown(COCKPIT_CSS, unsafe_allow_html=True)
    init_session_state()

    buffer: SimulationPlaybackBuffer = st.session_state.playback_buffer
    sim_ml: IntersectionSimulation = buffer.sim_ml
    sim_fixed: IntersectionSimulation = buffer.sim_fixed
    ml_controller: AdaptiveMLController = buffer.ml_controller

    # --- Sidebar Controls ---
    st.sidebar.markdown(
        """
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <div style="width:34px;height:34px;border-radius:8px;background:rgba(0,240,255,0.08);border:1px solid rgba(0,240,255,0.25);display:flex;align-items:center;justify-content:center;box-shadow:0 0 12px rgba(0,240,255,0.15);">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="2" fill="#00f0ff"/>
                    <path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
                </svg>
            </div>
            <div>
                <div style="font-size:15px;font-weight:800;color:#f8fafc;letter-spacing:0.04em;text-transform:uppercase;">AdaptiveFlow</div>
                <div style="font-size:10px;color:#94a3b8;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;font-family:monospace;">Tactical Traffic AI</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Closed-Loop Adaptive Signal Optimization")

    preset = st.sidebar.selectbox(
        "Traffic Demand Scenario",
        options=list(SCENARIO_PRESETS.keys()) + ["custom"],
        index=0,
        key="traffic_preset_select",
    )

    custom_rates = None
    if preset == "custom":
        st.sidebar.subheader("Approach Arrival Rates (veh/min)")
        r_n = st.sidebar.slider("North Rate", 5.0, 50.0, 25.0, 1.0, key="slider_north_rate")
        r_s = st.sidebar.slider("South Rate", 5.0, 50.0, 15.0, 1.0, key="slider_south_rate")
        r_e = st.sidebar.slider("East Rate", 5.0, 50.0, 10.0, 1.0, key="slider_east_rate")
        r_w = st.sidebar.slider("West Rate", 5.0, 50.0, 10.0, 1.0, key="slider_west_rate")
        custom_rates = {"N": r_n, "S": r_s, "E": r_e, "W": r_w}

    # Auto-detect preset changes and reset simulation
    if st.session_state.get("current_preset") != preset:
        reset_simulation(preset, custom_rates)
        st.rerun()

    c_btn1, c_btn2 = st.sidebar.columns(2)
    with c_btn1:
        if st.button("Reset Sim", use_container_width=True, key="btn_reset_sim"):
            reset_simulation(preset, custom_rates)
            st.rerun()
    with c_btn2:
        if st.button("Extend +70s", use_container_width=True, key="btn_extend_sim"):
            buffer.buffer_horizon(len(buffer.frames) + 70)
            st.rerun()

    st.sidebar.divider()
    st.sidebar.markdown(
        """
        <div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:8px;font-family:monospace;">
            Timing Specifications
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("**Fixed Baseline:** `P4` (30s NS / 30s EW)")
    active_ml_plan = sim_ml.signal.current_plan_name
    active_plan_info = TIMING_PLANS[active_ml_plan]
    st.sidebar.markdown(
        f"**Adaptive ML Active:** `{active_ml_plan}` ({active_plan_info['NS']}s NS / {active_plan_info['EW']}s EW)"
    )

    st.sidebar.markdown(
        """
        <div style="margin-top:20px;padding:12px;background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.06);border-radius:12px;">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
                <span class="led-pip cyan"></span>
                <span style="font-size:10px;font-weight:700;color:#38bdf8;text-transform:uppercase;letter-spacing:0.12em;font-family:monospace;">Kinematic Shortcuts</span>
            </div>
            <div style="font-size:11px;color:#94a3b8;line-height:1.7;">
                <div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                    <span>Play / Pause</span><span style="font-family:monospace;color:#f8fafc;font-weight:700;">Space</span>
                </div>
                <div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                    <span>Step Backward</span><span style="font-family:monospace;color:#f8fafc;font-weight:700;">Left Arrow</span>
                </div>
                <div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                    <span>Step Forward</span><span style="font-family:monospace;color:#f8fafc;font-weight:700;">Right Arrow</span>
                </div>
                <div style="display:flex;justify-content:space-between;padding:2px 0;">
                    <span>Timeline Scrub</span><span style="font-family:monospace;color:#f8fafc;font-weight:700;">Drag Slider</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Main Header ---
    st.markdown(
        """
        <div style="margin-bottom:18px;">
            <div class="eyebrow-pill eyebrow-cyan">AdaptiveFlow AI Telemetry & Kinematics</div>
            <h1 style="font-size:28px;font-weight:800;margin:0 0 4px 0;">Predictive Urban Intersection Management</h1>
            <p style="color:#94a3b8;font-size:13px;margin:0;">
                Closed-loop adaptive traffic signal optimization powered by supervised Random Forest ML.
                Real-time 60 FPS vehicle kinematics, dynamic braking tail lights, physical 3-lamp signals, and complete playback controls.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Top Status Banner
    total_buffered = len(buffer.frames) - 1
    t_now = int(sim_ml.current_time)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sim Horizon", f"{total_buffered} s", f"{round(total_buffered / 70.0, 1)} Cycles")
    c2.metric("ML Active Plan", active_ml_plan, f"NS: {active_plan_info['NS']}s | EW: {active_plan_info['EW']}s")
    c3.metric("Fixed Plan", "P4", "NS: 30s | EW: 30s")
    c4.metric("Cycle Counter", f"{sim_ml.signal.cycle_count} Completed")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # --- Section 1: Hero Stage - Interactive 4-Way Intersection ---
    st.markdown(
        """
        <div class="double-bezel-card">
            <div class="double-bezel-inner" style="padding:10px 14px 14px 14px;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#00f0ff;box-shadow:0 0 8px #00f0ff;"></span>
                        <span style="font-size:12px;font-weight:700;color:#f8fafc;letter-spacing:0.04em;text-transform:uppercase;">
                            Interactive 4-Way Intersection Live Telemetry (60 FPS)
                        </span>
                    </div>
                    <span style="font-size:11px;color:#94a3b8;font-family:monospace;">
                        Live Kinematics &amp; Phase Control
                    </span>
                </div>
        """,
        unsafe_allow_html=True,
    )

    # Generate and embed the 60 FPS HTML5 Canvas/SVG visualizer
    playback_json = buffer.to_json()
    html_content = generate_intersection_html(playback_json)
    components.html(html_content, height=620, scrolling=False)

    st.markdown("</div></div>", unsafe_allow_html=True)

    # --- Section 2: Head-to-Head Comparative Benchmark Bento ---
    st.markdown(
        """
        <div style="margin-top:20px;margin-bottom:12px;">
            <div class="eyebrow-pill eyebrow-emerald">Comparative Evaluation Bento</div>
            <h3 style="font-size:20px;font-weight:800;margin:0;">Live Performance Comparison: Fixed Baseline vs ML Adaptive</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    f_res = sim_fixed.get_summary()
    m_res = sim_ml.get_summary()

    f_comp_delay = f_res.get("comprehensive_delay", f_res["average_delay"])
    m_comp_delay = m_res.get("comprehensive_delay", m_res["average_delay"])
    comp_delay_diff_pct = (
        ((f_comp_delay - m_comp_delay) / max(0.1, f_comp_delay)) * 100.0
        if f_comp_delay > 0
        else 0.0
    )

    f_queue = f_res["average_queue"]
    m_queue = m_res["average_queue"]
    queue_diff_pct = (
        ((f_queue - m_queue) / max(0.1, f_queue)) * 100.0 if f_queue > 0 else 0.0
    )

    f_tp = f_res["throughput_vph"]
    m_tp = m_res["throughput_vph"]
    tp_diff = m_tp - f_tp

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Comprehensive Delay",
        f"{m_comp_delay:.2f} s",
        f"{comp_delay_diff_pct:+.1f}% vs Fixed ({f_comp_delay:.2f}s)",
        delta_color="inverse",
    )
    m2.metric(
        "Average Queue Length",
        f"{m_queue:.2f}",
        f"{queue_diff_pct:+.1f}% vs Fixed ({f_queue:.2f})",
        delta_color="inverse",
    )
    m3.metric(
        "Throughput",
        f"{m_tp:.0f} vph",
        f"{tp_diff:+.0f} vph vs Fixed ({f_tp:.0f})",
    )
    m4.metric(
        "Exited Trips (Delay)",
        f"{m_res['total_exited']} ({m_res['average_delay']:.1f}s)",
        f"vs Fixed: {f_res['total_exited']} ({f_res['average_delay']:.1f}s)",
    )

    # Time series charts from buffered trajectory history
    if buffer.frames:
        chart_records = []
        for fr in buffer.frames:
            t = fr["t"]
            chart_records.append({
                "time": t,
                "Fixed Delay": fr["fixed"]["metrics"]["comp_delay"],
                "ML Adaptive Delay": fr["ml"]["metrics"]["comp_delay"],
                "Fixed Queue": fr["fixed"]["metrics"]["avg_queue"],
                "ML Adaptive Queue": fr["ml"]["metrics"]["avg_queue"],
            })
        hist_df = pd.DataFrame(chart_records)
        ch_col1, ch_col2 = st.columns(2)
        with ch_col1:
            st.markdown(
                """
                <div style="display:flex;align-items:center;gap:7px;margin-bottom:8px;">
                    <span class="led-pip amber"></span>
                    <span style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#cbd5e1;font-family:monospace;">
                        Comprehensive Vehicle Delay Over Time (s)
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            delay_chart_df = hist_df.set_index("time")[["Fixed Delay", "ML Adaptive Delay"]]
            st.line_chart(delay_chart_df, color=["#dc3545", "#28a745"])
            st.caption("Comprehensive delay accounts for completed trips plus active queued and crawling vehicles.")
        with ch_col2:
            st.markdown(
                """
                <div style="display:flex;align-items:center;gap:7px;margin-bottom:8px;">
                    <span class="led-pip cyan"></span>
                    <span style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#cbd5e1;font-family:monospace;">
                        Average Queue Length Over Time
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            queue_chart_df = hist_df.set_index("time")[["Fixed Queue", "ML Adaptive Queue"]]
            st.line_chart(queue_chart_df, color=["#dc3545", "#28a745"])
            st.caption("Aggregate stopped and buffered queue count across all approaches.")

    st.divider()

    # --- Section 3: Telemetry & Machine Learning Insights ---
    col_decisions, col_model = st.columns([3, 2])

    with col_decisions:
        st.markdown(
            """
            <div style="margin-bottom:10px;">
                <div class="eyebrow-pill eyebrow-cyan">Decision Stream</div>
                <h3 style="font-size:18px;font-weight:700;margin:2px 0 6px 0;">Recent ML Controller Decisions</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
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
            st.info("No cycle transitions logged yet. Advance the simulation to observe controller policy.")

    with col_model:
        st.markdown(
            """
            <div style="margin-bottom:10px;">
                <div class="eyebrow-pill eyebrow-emerald">Feature Attribution</div>
                <h3 style="font-size:18px;font-weight:700;margin:2px 0 6px 0;">Top Feature Importances (Random Forest)</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        train_metrics = load_training_metrics()
        if "feature_importances" in train_metrics:
            top_feats = list(train_metrics["feature_importances"].items())[:6]
            imp_df = pd.DataFrame(top_feats, columns=["Feature", "Importance"]).set_index("Feature")
            try:
                st.bar_chart(imp_df, horizontal=True)
            except TypeError:
                st.bar_chart(imp_df)
        else:
            st.caption("Training metrics not found. Run model training to view feature importances.")

    # 22-Feature Live Vector
    st.markdown(
        """
        <div style="margin-top:20px;margin-bottom:10px;">
            <div class="eyebrow-pill eyebrow-purple">State Vector</div>
            <h3 style="font-size:18px;font-weight:700;margin:2px 0 6px 0;">22-Feature Live Telemetry Vector</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    features = extract_features(sim_ml)
    feat_df = pd.DataFrame([
        {"Category": "Demand (Vehicles)", "N": features["N_count"], "S": features["S_count"], "E": features["E_count"], "W": features["W_count"]},
        {"Category": "Queues (Stopped)", "N": features["N_queue"], "S": features["S_queue"], "E": features["E_queue"], "W": features["W_queue"]},
        {"Category": "Arrivals (veh/min)", "N": features["N_arrival"], "S": features["S_arrival"], "E": features["E_arrival"], "W": features["W_arrival"]},
        {"Category": "Speed (m/s)", "N": features["N_speed"], "S": features["S_speed"], "E": features["E_speed"], "W": features["W_speed"]},
        {"Category": "Queue Growth", "N": features["N_queue_growth"], "S": features["S_queue_growth"], "E": features["E_queue_growth"], "W": features["W_queue_growth"]},
    ])
    st.dataframe(feat_df, use_container_width=True, hide_index=True)
    st.caption(f"Active Signal State: Phase={int(features['current_phase'])} ({'N/S' if features['current_phase']==0 else 'E/W'}), Elapsed={features['elapsed_phase_time']}s")


if __name__ == "__main__":
    main()
