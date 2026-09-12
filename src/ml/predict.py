"""Real-time inference and closed-loop adaptive signal controller."""

from pathlib import Path
from typing import Dict, List, Optional, Union, Any
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

        self.model: RandomForestClassifier = joblib.load(self.model_path)
        self.classes: List[str] = list(self.model.classes_)

    def predict(self, features: Union[Dict[str, float], np.ndarray, pd.DataFrame]) -> str:
        """Predict the optimal integer timing plan from input features.

        Args:
            features: Feature dict, 1D array of length 22, or single-row DataFrame.

        Returns:
            Selected plan identifier (e.g. 'P1' to 'P7').
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

        pred = self.model.predict(df)[0]
        return str(pred)

    def predict_proba(self, features: Union[Dict[str, float], np.ndarray]) -> Dict[str, float]:
        """Predict class probability distribution over timing plans.

        Args:
            features: Feature dict or 1D array of length 22.

        Returns:
            Dictionary mapping plan name to probability.
        """
        if isinstance(features, dict):
            df = pd.DataFrame([features], columns=list(FEATURE_NAMES))
        elif isinstance(features, np.ndarray):
            vec = features.reshape(1, -1) if features.ndim == 1 else features
            df = pd.DataFrame(vec, columns=list(FEATURE_NAMES))
        else:
            df = features[list(FEATURE_NAMES)]

        probs = self.model.predict_proba(df)[0]
        return {cls_name: round(float(p), 4) for cls_name, p in zip(self.classes, probs)}

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

    def __init__(self, predictor: Optional[SignalTimingPredictor] = None) -> None:
        """Initialize controller.

        Args:
            predictor: SignalTimingPredictor instance (creates default if None).
        """
        self.predictor = predictor if predictor is not None else SignalTimingPredictor()
        self.decision_history: List[Dict[str, Any]] = []

    def update(self, sim: IntersectionSimulation, force_update: bool = False) -> Optional[str]:
        """Evaluate simulation state and assign timing plan at cycle completion boundaries.

        Args:
            sim: The active IntersectionSimulation.
            force_update: If True, evaluate and set plan immediately regardless of cycle state.

        Returns:
            Recommended timing plan if an update occurred, else None.
        """
        # Apply update at cycle boundary or when forced
        if force_update or sim.signal.just_completed_cycle or sim.signal.cycle_count == 0 and sim.current_time == 0:
            features = extract_features(sim)
            plan = self.predictor.predict(features)
            probs = self.predictor.predict_proba(features)

            sim.signal.set_next_plan(plan)

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
