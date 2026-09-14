"""Traffic-state feature extraction and validation for AdaptiveFlow."""

from typing import Dict, List, Sequence, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from src.simulator.intersection import IntersectionSimulation


# Exact 22 canonical features in defined order
FEATURE_NAMES: Tuple[str, ...] = (
    # Demand (4)
    "N_count",
    "S_count",
    "E_count",
    "W_count",
    # Congestion (4)
    "N_queue",
    "S_queue",
    "E_queue",
    "W_queue",
    # Arrival dynamics (4)
    "N_arrival",
    "S_arrival",
    "E_arrival",
    "W_arrival",
    # Speed (4)
    "N_speed",
    "S_speed",
    "E_speed",
    "W_speed",
    # Queue dynamics (4)
    "N_queue_growth",
    "S_queue_growth",
    "E_queue_growth",
    "W_queue_growth",
    # Signal state (2)
    "current_phase",
    "elapsed_phase_time",
)


def extract_features(sim: IntersectionSimulation) -> Dict[str, float]:
    """Extract 22 traffic-state features from the simulation instance.

    Args:
        sim: An active IntersectionSimulation instance.

    Returns:
        Dictionary mapping each of the 22 feature names to its floating-point value.
    """
    raw_features = sim.get_feature_dict()
    # Ensure ordered dict matching canonical FEATURE_NAMES
    return {name: float(raw_features[name]) for name in FEATURE_NAMES}


def features_to_vector(features: Dict[str, float]) -> np.ndarray:
    """Convert a 22-feature dictionary into a 1D NumPy array in canonical order.

    Args:
        features: Dictionary containing all 22 feature names.

    Returns:
        1D NumPy array with shape (22,) and dtype float32.
    """
    return np.array([features[name] for name in FEATURE_NAMES], dtype=np.float32)


def features_to_dataframe(features_list: Sequence[Dict[str, float]]) -> pd.DataFrame:
    """Convert a sequence of feature dictionaries into a validated pandas DataFrame.

    Args:
        features_list: Sequence of dictionaries, each containing all 22 features.

    Returns:
        pandas DataFrame with 22 canonical columns.
    """
    df = pd.DataFrame(list(features_list), columns=list(FEATURE_NAMES))
    return df.astype(np.float32)


def validate_features(features: Dict[str, float]) -> bool:
    """Validate that all 22 features are present, finite, and within valid domains.

    Args:
        features: Dictionary of extracted features.

    Returns:
        True if all features pass validation.

    Raises:
        ValueError: If any feature is missing, NaN/infinite, or out of domain.
    """
    for name in FEATURE_NAMES:
        if name not in features:
            raise ValueError(f"Missing required feature: '{name}'")

        val = features[name]
        if not np.isfinite(val):
            raise ValueError(f"Feature '{name}' has non-finite value: {val}")

        # Check domain constraints
        if "count" in name and val < 0:
            raise ValueError(f"Negative vehicle count in '{name}': {val}")
        if "queue" in name and "growth" not in name and val < 0:
            raise ValueError(f"Negative queue in '{name}': {val}")
        if "arrival" in name and val < 0:
            raise ValueError(f"Negative arrival rate in '{name}': {val}")
        if "speed" in name and val < 0:
            raise ValueError(f"Negative speed in '{name}': {val}")
        if name == "current_phase" and val not in (0.0, 1.0):
            raise ValueError(f"Invalid current_phase: {val}. Must be 0.0 or 1.0")
        if name == "elapsed_phase_time" and val < 0:
            raise ValueError(f"Negative elapsed_phase_time: {val}")

    return True


# 12 Engineered Interaction & Ratio Features (Phase A / Phase B directional balance)
ENGINEERED_FEATURE_NAMES: Tuple[str, ...] = (
    # Directional totals (Phase A vs Phase B)
    "NS_count_total",
    "EW_count_total",
    "NS_queue_total",
    "EW_queue_total",
    "NS_arrival_total",
    "EW_arrival_total",
    # Directional ratios (North-South fraction of total demand)
    "demand_ratio_ns",
    "queue_ratio_ns",
    "arrival_ratio_ns",
    # Directional pressure differences
    "count_diff_ns_ew",
    "queue_diff_ns_ew",
    "arrival_diff_ns_ew",
)

ALL_FEATURE_NAMES: Tuple[str, ...] = FEATURE_NAMES + ENGINEERED_FEATURE_NAMES


def compute_engineered_features(
    features_input: Union[pd.DataFrame, np.ndarray, Dict[str, float]]
) -> Union[pd.DataFrame, np.ndarray, Dict[str, float]]:
    """Compute 12 directional interaction and ratio features from the 22 canonical features.

    Derives Phase A (N+S) vs Phase B (E+W) sums, demand/queue/arrival ratios,
    and net pressure differentials.
    """
    if isinstance(features_input, dict):
        ns_count = float(features_input["N_count"] + features_input["S_count"])
        ew_count = float(features_input["E_count"] + features_input["W_count"])
        ns_q = float(features_input["N_queue"] + features_input["S_queue"])
        ew_q = float(features_input["E_queue"] + features_input["W_queue"])
        ns_arr = float(features_input["N_arrival"] + features_input["S_arrival"])
        ew_arr = float(features_input["E_arrival"] + features_input["W_arrival"])

        tot_count = ns_count + ew_count
        tot_q = ns_q + ew_q
        tot_arr = ns_arr + ew_arr

        engineered = {
            "NS_count_total": ns_count,
            "EW_count_total": ew_count,
            "NS_queue_total": ns_q,
            "EW_queue_total": ew_q,
            "NS_arrival_total": ns_arr,
            "EW_arrival_total": ew_arr,
            "demand_ratio_ns": ns_count / max(0.1, tot_count),
            "queue_ratio_ns": ns_q / max(0.1, tot_q),
            "arrival_ratio_ns": ns_arr / max(0.1, tot_arr),
            "count_diff_ns_ew": ns_count - ew_count,
            "queue_diff_ns_ew": ns_q - ew_q,
            "arrival_diff_ns_ew": ns_arr - ew_arr,
        }
        res = dict(features_input)
        res.update(engineered)
        return res

    elif isinstance(features_input, pd.DataFrame):
        df = features_input.copy()
        ns_count = df["N_count"] + df["S_count"]
        ew_count = df["E_count"] + df["W_count"]
        ns_q = df["N_queue"] + df["S_queue"]
        ew_q = df["E_queue"] + df["W_queue"]
        ns_arr = df["N_arrival"] + df["S_arrival"]
        ew_arr = df["E_arrival"] + df["W_arrival"]

        tot_count = np.maximum(0.1, ns_count + ew_count)
        tot_q = np.maximum(0.1, ns_q + ew_q)
        tot_arr = np.maximum(0.1, ns_arr + ew_arr)

        df["NS_count_total"] = ns_count.astype(np.float32)
        df["EW_count_total"] = ew_count.astype(np.float32)
        df["NS_queue_total"] = ns_q.astype(np.float32)
        df["EW_queue_total"] = ew_q.astype(np.float32)
        df["NS_arrival_total"] = ns_arr.astype(np.float32)
        df["EW_arrival_total"] = ew_arr.astype(np.float32)
        df["demand_ratio_ns"] = (ns_count / tot_count).astype(np.float32)
        df["queue_ratio_ns"] = (ns_q / tot_q).astype(np.float32)
        df["arrival_ratio_ns"] = (ns_arr / tot_arr).astype(np.float32)
        df["count_diff_ns_ew"] = (ns_count - ew_count).astype(np.float32)
        df["queue_diff_ns_ew"] = (ns_q - ew_q).astype(np.float32)
        df["arrival_diff_ns_ew"] = (ns_arr - ew_arr).astype(np.float32)
        return df

    elif isinstance(features_input, np.ndarray):
        # Assumes canonical order of 22 features
        # N_count=0, S_count=1, E_count=2, W_count=3
        # N_queue=4, S_queue=5, E_queue=6, W_queue=7
        # N_arrival=8, S_arrival=9, E_arrival=10, W_arrival=11
        if features_input.ndim == 1:
            x_2d = features_input.reshape(1, -1)
            was_1d = True
        else:
            x_2d = features_input
            was_1d = False

        ns_count = x_2d[:, 0] + x_2d[:, 1]
        ew_count = x_2d[:, 2] + x_2d[:, 3]
        ns_q = x_2d[:, 4] + x_2d[:, 5]
        ew_q = x_2d[:, 6] + x_2d[:, 7]
        ns_arr = x_2d[:, 8] + x_2d[:, 9]
        ew_arr = x_2d[:, 10] + x_2d[:, 11]

        tot_count = np.maximum(0.1, ns_count + ew_count)
        tot_q = np.maximum(0.1, ns_q + ew_q)
        tot_arr = np.maximum(0.1, ns_arr + ew_arr)

        eng = np.column_stack([
            ns_count,
            ew_count,
            ns_q,
            ew_q,
            ns_arr,
            ew_arr,
            ns_count / tot_count,
            ns_q / tot_q,
            ns_arr / tot_arr,
            ns_count - ew_count,
            ns_q - ew_q,
            ns_arr - ew_arr,
        ]).astype(np.float32)

        out = np.hstack([x_2d, eng])
        return out[0] if was_1d else out

    else:
        raise TypeError(f"Unsupported input type for compute_engineered_features: {type(features_input)}")


class TrafficFeatureTransformer(BaseEstimator, TransformerMixin):
    """Scikit-learn compatible transformer that enriches 22 canonical features with directional interactions and ratios."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return compute_engineered_features(X)

