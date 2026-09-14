"""Traffic-state feature extraction and validation for AdaptiveFlow."""

from typing import Dict, List, Sequence, Tuple, Union
import numpy as np
import pandas as pd
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


# 22 Engineered Interaction, Ratio, Critical-Lane, and Congestion Features
ENGINEERED_FEATURE_NAMES: Tuple[str, ...] = (
    # Directional totals (Phase A vs Phase B)
    "NS_count_total",
    "EW_count_total",
    "NS_queue_total",
    "EW_queue_total",
    "NS_arrival_total",
    "EW_arrival_total",
    # Directional ratios (North-South fraction of total)
    "demand_ratio_ns",
    "queue_ratio_ns",
    "arrival_ratio_ns",
    # Directional pressure differences
    "count_diff_ns_ew",
    "queue_diff_ns_ew",
    "arrival_diff_ns_ew",
    # Webster's Critical Lane Demand (heaviest approach per phase determines green requirement)
    "critical_demand_ns",
    "critical_demand_ew",
    "critical_queue_ns",
    "critical_queue_ew",
    "critical_demand_ratio",
    # Within-phase approach asymmetry
    "ns_internal_asymmetry",
    "ew_internal_asymmetry",
    # Speed deficiency indices (0 = free flow, 1 = standstill at 13.89 m/s)
    "speed_deficiency_ns",
    "speed_deficiency_ew",
    # Link storage saturation ratio (150m / 6.5m ≈ 23 vehicles capacity)
    "queue_storage_ratio_max",
)

ALL_FEATURE_NAMES: Tuple[str, ...] = FEATURE_NAMES + ENGINEERED_FEATURE_NAMES


def compute_engineered_features(
    features_input: Union[pd.DataFrame, np.ndarray, Dict[str, float]]
) -> Union[pd.DataFrame, np.ndarray, Dict[str, float]]:
    """Compute 22 directional interaction, ratio, critical-lane, and congestion features.

    Derives Phase A vs Phase B totals, demand/queue/arrival ratios, critical lane bottleneck demands,
    within-phase asymmetries, and dimensionless congestion indices.
    """
    if isinstance(features_input, dict):
        n_c, s_c = float(features_input["N_count"]), float(features_input["S_count"])
        e_c, w_c = float(features_input["E_count"]), float(features_input["W_count"])
        n_q, s_q = float(features_input["N_queue"]), float(features_input["S_queue"])
        e_q, w_q = float(features_input["E_queue"]), float(features_input["W_queue"])
        n_arr, s_arr = float(features_input["N_arrival"]), float(features_input["S_arrival"])
        e_arr, w_arr = float(features_input["E_arrival"]), float(features_input["W_arrival"])
        n_spd, s_spd = float(features_input["N_speed"]), float(features_input["S_speed"])
        e_spd, w_spd = float(features_input["E_speed"]), float(features_input["W_speed"])

        ns_count = n_c + s_c
        ew_count = e_c + w_c
        ns_q = n_q + s_q
        ew_q = e_q + w_q
        ns_arr = n_arr + s_arr
        ew_arr = e_arr + w_arr

        tot_count = max(0.1, ns_count + ew_count)
        tot_q = max(0.1, ns_q + ew_q)
        tot_arr = max(0.1, ns_arr + ew_arr)

        crit_ns = max(n_c, s_c)
        crit_ew = max(e_c, w_c)
        crit_q_ns = max(n_q, s_q)
        crit_q_ew = max(e_q, w_q)
        crit_tot = max(0.1, crit_ns + crit_ew)

        max_q = max(n_q, s_q, e_q, w_q)

        engineered = {
            "NS_count_total": ns_count,
            "EW_count_total": ew_count,
            "NS_queue_total": ns_q,
            "EW_queue_total": ew_q,
            "NS_arrival_total": ns_arr,
            "EW_arrival_total": ew_arr,
            "demand_ratio_ns": ns_count / tot_count,
            "queue_ratio_ns": ns_q / tot_q,
            "arrival_ratio_ns": ns_arr / tot_arr,
            "count_diff_ns_ew": ns_count - ew_count,
            "queue_diff_ns_ew": ns_q - ew_q,
            "arrival_diff_ns_ew": ns_arr - ew_arr,
            "critical_demand_ns": crit_ns,
            "critical_demand_ew": crit_ew,
            "critical_queue_ns": crit_q_ns,
            "critical_queue_ew": crit_q_ew,
            "critical_demand_ratio": crit_ns / crit_tot,
            "ns_internal_asymmetry": abs(n_c - s_c),
            "ew_internal_asymmetry": abs(e_c - w_c),
            "speed_deficiency_ns": max(0.0, 1.0 - (n_spd + s_spd) / (2.0 * 13.89)),
            "speed_deficiency_ew": max(0.0, 1.0 - (e_spd + w_spd) / (2.0 * 13.89)),
            "queue_storage_ratio_max": min(1.0, max_q / 23.0),
        }
        res = dict(features_input)
        res.update(engineered)
        return res

    elif isinstance(features_input, pd.DataFrame):
        df = features_input.copy()
        n_c, s_c = df["N_count"], df["S_count"]
        e_c, w_c = df["E_count"], df["W_count"]
        n_q, s_q = df["N_queue"], df["S_queue"]
        e_q, w_q = df["E_queue"], df["W_queue"]
        n_arr, s_arr = df["N_arrival"], df["S_arrival"]
        e_arr, w_arr = df["E_arrival"], df["W_arrival"]
        n_spd, s_spd = df["N_speed"], df["S_speed"]
        e_spd, w_spd = df["E_speed"], df["W_speed"]

        ns_count = n_c + s_c
        ew_count = e_c + w_c
        ns_q = n_q + s_q
        ew_q = e_q + w_q
        ns_arr = n_arr + s_arr
        ew_arr = e_arr + w_arr

        tot_count = np.maximum(0.1, ns_count + ew_count)
        tot_q = np.maximum(0.1, ns_q + ew_q)
        tot_arr = np.maximum(0.1, ns_arr + ew_arr)

        crit_ns = np.maximum(n_c, s_c)
        crit_ew = np.maximum(e_c, w_c)
        crit_q_ns = np.maximum(n_q, s_q)
        crit_q_ew = np.maximum(e_q, w_q)
        crit_tot = np.maximum(0.1, crit_ns + crit_ew)

        max_q = np.maximum(np.maximum(n_q, s_q), np.maximum(e_q, w_q))

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
        df["critical_demand_ns"] = crit_ns.astype(np.float32)
        df["critical_demand_ew"] = crit_ew.astype(np.float32)
        df["critical_queue_ns"] = crit_q_ns.astype(np.float32)
        df["critical_queue_ew"] = crit_q_ew.astype(np.float32)
        df["critical_demand_ratio"] = (crit_ns / crit_tot).astype(np.float32)
        df["ns_internal_asymmetry"] = (n_c - s_c).abs().astype(np.float32)
        df["ew_internal_asymmetry"] = (e_c - w_c).abs().astype(np.float32)
        df["speed_deficiency_ns"] = np.clip(1.0 - (n_spd + s_spd) / (2.0 * 13.89), 0.0, 1.0).astype(np.float32)
        df["speed_deficiency_ew"] = np.clip(1.0 - (e_spd + w_spd) / (2.0 * 13.89), 0.0, 1.0).astype(np.float32)
        df["queue_storage_ratio_max"] = np.clip(max_q / 23.0, 0.0, 1.0).astype(np.float32)
        return df

    elif isinstance(features_input, np.ndarray):
        if features_input.ndim == 1:
            x_2d = features_input.reshape(1, -1)
            was_1d = True
        else:
            x_2d = features_input
            was_1d = False

        n_c, s_c, e_c, w_c = x_2d[:, 0], x_2d[:, 1], x_2d[:, 2], x_2d[:, 3]
        n_q, s_q, e_q, w_q = x_2d[:, 4], x_2d[:, 5], x_2d[:, 6], x_2d[:, 7]
        n_arr, s_arr, e_arr, w_arr = x_2d[:, 8], x_2d[:, 9], x_2d[:, 10], x_2d[:, 11]
        n_spd, s_spd, e_spd, w_spd = x_2d[:, 12], x_2d[:, 13], x_2d[:, 14], x_2d[:, 15]

        ns_count = n_c + s_c
        ew_count = e_c + w_c
        ns_q = n_q + s_q
        ew_q = e_q + w_q
        ns_arr = n_arr + s_arr
        ew_arr = e_arr + w_arr

        tot_count = np.maximum(0.1, ns_count + ew_count)
        tot_q = np.maximum(0.1, ns_q + ew_q)
        tot_arr = np.maximum(0.1, ns_arr + ew_arr)

        crit_ns = np.maximum(n_c, s_c)
        crit_ew = np.maximum(e_c, w_c)
        crit_q_ns = np.maximum(n_q, s_q)
        crit_q_ew = np.maximum(e_q, w_q)
        crit_tot = np.maximum(0.1, crit_ns + crit_ew)

        max_q = np.maximum(np.maximum(n_q, s_q), np.maximum(e_q, w_q))

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
            crit_ns,
            crit_ew,
            crit_q_ns,
            crit_q_ew,
            crit_ns / crit_tot,
            np.abs(n_c - s_c),
            np.abs(e_c - w_c),
            np.clip(1.0 - (n_spd + s_spd) / (2.0 * 13.89), 0.0, 1.0),
            np.clip(1.0 - (e_spd + w_spd) / (2.0 * 13.89), 0.0, 1.0),
            np.clip(max_q / 23.0, 0.0, 1.0),
        ]).astype(np.float32)

        out = np.hstack([x_2d, eng])
        return out[0] if was_1d else out

    else:
        raise TypeError(f"Unsupported input type for compute_engineered_features: {type(features_input)}")


class TrafficFeatureTransformer:
    """Scikit-learn compatible transformer that enriches 22 canonical features with directional interactions and ratios."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return compute_engineered_features(X)

    def get_params(self, deep: bool = True):
        return {}

    def set_params(self, **params):
        return self

    def __sklearn_tags__(self):
        try:
            from sklearn.utils._tags import TransformerTags
            return TransformerTags()
        except Exception:
            return None

