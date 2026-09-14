import sys
from pathlib import Path

# Ensure repository root is in sys.path regardless of execution working directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from typing import Dict, List, Optional, Union, Any, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from src.features.feature_engineering import FEATURE_NAMES, extract_features, features_to_vector
from src.simulator.intersection import IntersectionSimulation
from src.simulator.signal import TIMING_PLANS

DEFAULT_MODEL_PATH = Path("models/random_forest.pkl")


class SignalTimingPredictor:
    """Wrapper around trained machine learning model for sub-millisecond inference."""

    def __init__(self, model_path: Union[str, Path] = DEFAULT_MODEL_PATH) -> None:
        """Initialize predictor by loading serialized model.

        Args:
            model_path: Path to serialized joblib model.
        """
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found at {self.model_path}. Run training first.")

        self.model = joblib.load(self.model_path)
        self.classes: List[str] = list(self.model.classes_)

    def predict_with_proba(
        self, features: Union[Dict[str, float], np.ndarray, pd.DataFrame]
    ) -> Tuple[str, Dict[str, float]]:
        """Predict top timing plan and full probability distribution in a single forward pass.

        Args:
            features: Feature dict, 1D/2D array, or DataFrame.

        Returns:
            Tuple of (best_plan_name, probabilities_dict).
        """
        if isinstance(features, dict):
            df = pd.DataFrame([features], columns=list(FEATURE_NAMES))
        elif isinstance(features, np.ndarray):
            vec = features.reshape(1, -1) if features.ndim == 1 else features
            df = pd.DataFrame(vec, columns=list(FEATURE_NAMES))
        elif isinstance(features, pd.DataFrame):
            df = features[list(FEATURE_NAMES)]
        else:
            raise TypeError(f"Unsupported features type: {type(features)}")

        probs = self.model.predict_proba(df)[0]
        best_idx = int(np.argmax(probs))
        best_plan = str(self.classes[best_idx])
        prob_dict = {cls_name: round(float(p), 4) for cls_name, p in zip(self.classes, probs)}
        return best_plan, prob_dict

    def predict(self, features: Union[Dict[str, float], np.ndarray, pd.DataFrame]) -> str:
        """Predict the optimal integer timing plan from input features."""
        plan, _ = self.predict_with_proba(features)
        return plan

    def predict_proba(self, features: Union[Dict[str, float], np.ndarray, pd.DataFrame]) -> Dict[str, float]:
        """Predict class probability distribution over timing plans."""
        _, probs = self.predict_with_proba(features)
        return probs

    def predict_from_sim(self, sim: IntersectionSimulation) -> str:
        """Extract features directly from live simulation and predict next plan.

        Args:
            sim: Active IntersectionSimulation instance.

        Returns:
            Selected timing plan identifier.
        """
        features = extract_features(sim)
        return self.predict(features)


class AdaptiveMLController:
    """Closed-loop controller orchestrating ML timing plan updates at cycle boundaries."""

    def __init__(
        self,
        predictor: Optional[SignalTimingPredictor] = None,
        confidence_threshold: float = 0.22,
        smoothing_window: int = 5,
    ) -> None:
        """Initialize controller.

        Args:
            predictor: SignalTimingPredictor instance (creates default if None).
            confidence_threshold: Minimum prediction confidence before switching away from balanced baseline.
            smoothing_window: Number of recent 1s simulation steps to average features over before decision.
        """
        self.predictor = predictor if predictor is not None else SignalTimingPredictor()
        self.confidence_threshold = confidence_threshold
        self.smoothing_window = max(1, smoothing_window)
        self.feature_history: List[Dict[str, float]] = []
        self.decision_history: List[Dict[str, Any]] = []

    def update(self, sim: IntersectionSimulation, force_update: bool = False) -> Optional[str]:
        """Evaluate simulation state and assign timing plan at cycle completion boundaries.

        Args:
            sim: The active IntersectionSimulation.
            force_update: If True, evaluate and set plan immediately regardless of cycle state.

        Returns:
            Recommended timing plan if an update occurred, else None.
        """
        # Buffer live feature frame for smoothing
        current_feat = extract_features(sim)
        self.feature_history.append(current_feat)
        if len(self.feature_history) > self.smoothing_window:
            self.feature_history.pop(0)

        # Apply update at cycle boundary or when forced
        if force_update or sim.signal.just_completed_cycle or (sim.signal.cycle_count == 0 and sim.current_time == 0):
            # For empty simulation start (t=0 with no vehicles), default to balanced baseline P4
            total_active_vehs = sum(len(q) for q in sim.vehicles.values()) + sum(
                len(b) for b in getattr(sim, "entry_buffers", {}).values()
            )
            if sim.current_time == 0 and total_active_vehs == 0:
                plan = "P4"
                probs = {p: (1.0 if p == "P4" else 0.0) for p in TIMING_PLANS}
            else:
                # Average buffered continuous features over the smoothing window to eliminate momentary sensor noise
                features = dict(self.feature_history[-1])
                for k in [
                    "N_count", "S_count", "E_count", "W_count",
                    "N_queue", "S_queue", "E_queue", "W_queue",
                    "N_speed", "S_speed", "E_speed", "W_speed",
                    "N_wait", "S_wait", "E_wait", "W_wait",
                    "total_vehicles", "total_queue", "mean_system_speed", "system_arrival_rate",
                ]:
                    if k in features:
                        features[k] = float(np.mean([f[k] for f in self.feature_history]))

                # Fast single-pass inference (predict plan and probabilities in one call)
                plan, probs = self.predictor.predict_with_proba(features)

                ns_vol = features["N_count"] + features["S_count"]
                ew_vol = features["E_count"] + features["W_count"]
                ns_q = features["N_queue"] + features["S_queue"]
                ew_q = features["E_queue"] + features["W_queue"]
                tot_vol = max(1.0, ns_vol + ew_vol)
                demand_ratio = ns_vol / tot_vol
                top_conf = probs.get(plan, 0.0)

                # Stability Guard 1: In near-balanced demand, lock to P4 to avoid micro-flapping
                is_balanced = (
                    (0.42 <= demand_ratio <= 0.58 and abs(ns_q - ew_q) <= 4)
                    or (abs(ns_vol - ew_vol) <= 4 and abs(ns_q - ew_q) <= 5)
                    or (top_conf < self.confidence_threshold and abs(ns_vol - ew_vol) <= 6)
                )
                if is_balanced:
                    plan = "P4"
                elif sim.current_time > 0 and sim.signal.current_plan_name:
                    # Stability Guard 2: Hysteresis slew-rate limiter
                    current_idx = int(sim.signal.current_plan_name[1:])
                    pred_idx = int(plan[1:])
                    delta = pred_idx - current_idx
                    # Relax slew limiter for extreme demand asymmetry (emergency surge)
                    is_extreme_surge = (
                        demand_ratio < 0.30 or demand_ratio > 0.70 or abs(ns_vol - ew_vol) >= 15
                    )
                    max_step = 4 if is_extreme_surge else 2
                    if abs(delta) > max_step:
                        step_dir = max_step if delta > 0 else -max_step
                        plan = f"P{current_idx + step_dir}"

            # Reset smoothing buffer for next cycle
            self.feature_history.clear()

            # Apply plan immediately so current cycle actuates the selected timings (no 70s actuation lag)
            sim.signal.apply_plan_now(plan)

            decision = {
                "time": sim.current_time,
                "cycle": sim.signal.cycle_count,
                "selected_plan": plan,
                "ns_green": TIMING_PLANS[plan]["NS"],
                "ew_green": TIMING_PLANS[plan]["EW"],
                "probabilities": probs,
            }
            self.decision_history.append(decision)
            return plan

        return None

