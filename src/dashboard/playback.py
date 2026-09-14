"""Playback buffer and frame serializer for AdaptiveFlow dashboard.

Pre-simulates and captures synchronized trajectories for both Fixed Baseline
and AdaptiveFlow ML Controller, recording vehicle positions, signal states,
and telemetry for client-side 60 FPS playback, rewinding, and scrubbing.
"""

from typing import Dict, List, Any, Optional
import json

from src.simulator.intersection import IntersectionSimulation
from src.simulator.signal import TrafficSignal, TIMING_PLANS, SignalPhase
from src.simulator.traffic_generator import TrafficGenerator, SCENARIO_PRESETS
from src.ml.predict import SignalTimingPredictor, AdaptiveMLController
from src.features.feature_engineering import extract_features


class SimulationPlaybackBuffer:
    """Buffers synchronized time-series frames for dual intersection simulations."""

    def __init__(
        self,
        preset: str = "balanced",
        custom_rates: Optional[Dict[str, float]] = None,
        seed: int = 42,
        predictor: Optional[SignalTimingPredictor] = None,
    ) -> None:
        self.preset = preset
        self.custom_rates = custom_rates
        self.seed = seed
        self.predictor = predictor if predictor is not None else SignalTimingPredictor()

        self.sim_fixed: Optional[IntersectionSimulation] = None
        self.sim_ml: Optional[IntersectionSimulation] = None
        self.ml_controller: Optional[AdaptiveMLController] = None

        self.frames: List[Dict[str, Any]] = []
        self.reset(preset, custom_rates, seed)

    def reset(
        self,
        preset: str = "balanced",
        custom_rates: Optional[Dict[str, float]] = None,
        seed: int = 42,
    ) -> None:
        """Initialize both simulations with identical traffic demand streams."""
        self.preset = preset
        self.custom_rates = custom_rates
        self.seed = seed

        rates = (
            custom_rates
            if custom_rates is not None
            else SCENARIO_PRESETS.get(preset, SCENARIO_PRESETS["balanced"])
        )

        # Fixed baseline simulation (P4: 30s NS, 30s EW)
        fixed_gen = TrafficGenerator(rates=rates, seed=seed)
        fixed_signal = TrafficSignal(initial_plan="P4")
        self.sim_fixed = IntersectionSimulation(signal=fixed_signal, generator=fixed_gen, seed=seed)

        # ML Adaptive simulation
        ml_gen = TrafficGenerator(rates=rates, seed=seed)
        ml_signal = TrafficSignal(initial_plan="P4")
        self.sim_ml = IntersectionSimulation(signal=ml_signal, generator=ml_gen, seed=seed)
        self.ml_controller = AdaptiveMLController(predictor=self.predictor)
        self.ml_controller.update(self.sim_ml, force_update=True)

        self.frames = []
        # Record initial frame t=0
        self._record_frame()

    def _serialize_sim_state(self, sim: IntersectionSimulation, is_ml: bool = False) -> Dict[str, Any]:
        """Serialize a single simulation instance's instantaneous state."""
        signal = sim.signal
        ns_color = signal.get_signal_color("N")
        ew_color = signal.get_signal_color("E")

        active_plan = signal.current_plan_name
        plan_info = TIMING_PLANS.get(active_plan, {"NS": 30, "EW": 30})

        # Determine remaining seconds in current phase
        cur_phase = signal.current_phase
        if cur_phase == SignalPhase.PHASE_A_GREEN:
            dur = signal.plan["NS"]
        elif cur_phase == SignalPhase.PHASE_A_YELLOW:
            dur = signal.yellow_duration
        elif cur_phase == SignalPhase.PHASE_A_ALL_RED:
            dur = signal.all_red_duration
        elif cur_phase == SignalPhase.PHASE_B_GREEN:
            dur = signal.plan["EW"]
        elif cur_phase == SignalPhase.PHASE_B_YELLOW:
            dur = signal.yellow_duration
        else:
            dur = signal.all_red_duration

        remaining = max(0.0, dur - signal.phase_elapsed_time)

        # Vehicles
        v_list = []
        for app in ["N", "S", "E", "W"]:
            for v in sim.vehicles[app]:
                if v.state != "exited":
                    v_list.append({
                        "id": v.id,
                        "app": v.approach,
                        "pos": round(v.position, 2),
                        "spd": round(v.speed, 2),
                        "st": v.state,
                        "wt": round(v.wait_time, 1),
                    })

        summary = sim.get_summary()
        comp_delay = summary.get("comprehensive_delay", summary["average_delay"])

        state_data = {
            "phase_name": cur_phase.value,
            "ns_color": ns_color,
            "ew_color": ew_color,
            "phase_elapsed": round(signal.phase_elapsed_time, 1),
            "phase_duration": round(dur, 1),
            "remaining": round(remaining, 1),
            "plan": active_plan,
            "ns_green": plan_info["NS"],
            "ew_green": plan_info["EW"],
            "cycle": signal.cycle_count,
            "vehicles": v_list,
            "metrics": {
                "comp_delay": round(comp_delay, 2),
                "avg_queue": round(summary["average_queue"], 2),
                "throughput": round(summary["throughput_vph"], 1),
                "exited": summary["total_exited"],
                "avg_speed": round(sum(v["spd"] for v in v_list) / max(1, len(v_list)), 2),
            },
        }

        if is_ml and self.ml_controller is not None and len(self.ml_controller.decision_history) > 0:
            last_dec = self.ml_controller.decision_history[-1]
            state_data["ml_decision"] = {
                "plan": last_dec.get("selected_plan", active_plan),
                "probs": {k: round(v, 3) for k, v in last_dec.get("probabilities", {}).items()},
                "ns_green": last_dec.get("ns_green", plan_info["NS"]),
                "ew_green": last_dec.get("ew_green", plan_info["EW"]),
            }

        return state_data

    def _record_frame(self) -> None:
        """Capture synchronized state across ML and Fixed simulations."""
        t = round(self.sim_ml.current_time, 1)
        ml_state = self._serialize_sim_state(self.sim_ml, is_ml=True)
        fixed_state = self._serialize_sim_state(self.sim_fixed, is_ml=False)

        self.frames.append({
            "t": t,
            "ml": ml_state,
            "fixed": fixed_state,
        })

    def step(self, dt: float = 1.0) -> None:
        """Advance both simulations by dt and record a frame."""
        self.sim_fixed.step(dt=dt)
        self.sim_ml.step(dt=dt)
        self.ml_controller.update(self.sim_ml)
        self._record_frame()

    def buffer_horizon(self, seconds: int = 140) -> None:
        """Pre-compute and buffer simulation frames up to specified duration."""
        current_steps = len(self.frames) - 1
        needed_steps = int(seconds) - current_steps
        for _ in range(max(0, needed_steps)):
            self.step(dt=1.0)

    def get_frame(self, index: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific frame by index."""
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None

    def get_latest_frame(self) -> Dict[str, Any]:
        """Retrieve the most recent simulation frame."""
        return self.frames[-1]

    def to_json(self) -> str:
        """Export buffered trajectory frames as compact JSON."""
        return json.dumps(self.frames, separators=(",", ":"))
