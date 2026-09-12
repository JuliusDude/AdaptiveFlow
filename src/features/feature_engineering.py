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
