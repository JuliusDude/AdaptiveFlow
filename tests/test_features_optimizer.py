"""Unit tests for feature engineering and timing plan optimizer."""

import pytest
import numpy as np
import pandas as pd
from src.simulator.intersection import IntersectionSimulation
from src.features.feature_engineering import (
    FEATURE_NAMES,
    extract_features,
    features_to_vector,
    features_to_dataframe,
    validate_features,
)
from src.optimization.timing_optimizer import TimingOptimizer


def test_feature_engineering_pipeline():
    sim = IntersectionSimulation(seed=42)
    for _ in range(35):
        sim.step(dt=1.0)

    # 1. Extract features
    features = extract_features(sim)
    assert len(features) == 22
    assert tuple(features.keys()) == FEATURE_NAMES

    # 2. Validate features
    assert validate_features(features) is True

    # 3. Convert to vector
    vec = features_to_vector(features)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (22,)
    assert vec.dtype == np.float32

    # 4. Convert to DataFrame
    df = features_to_dataframe([features, features])
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (2, 22)
    assert list(df.columns) == list(FEATURE_NAMES)


def test_feature_validation_errors():
    # Missing feature
    incomplete = {"N_count": 5.0, "S_count": 3.0}
    with pytest.raises(ValueError, match="Missing required feature"):
        validate_features(incomplete)

    # Negative count
    sim = IntersectionSimulation(seed=1)
    features = extract_features(sim)
    features["N_count"] = -1.0
    with pytest.raises(ValueError, match="Negative vehicle count"):
        validate_features(features)

    # Invalid current_phase
    features["N_count"] = 0.0
    features["current_phase"] = 2.0
    with pytest.raises(ValueError, match="Invalid current_phase"):
        validate_features(features)


def test_timing_optimizer_asymmetric_demand():
    optimizer = TimingOptimizer()

    # Case 1: Extreme North-heavy demand
    # P7 gives 45s NS / 15s EW, P1 gives 15s NS / 45s EW
    features_n, best_plan_n, delays_n = optimizer.evaluate_scenario(
        preset_or_rates={"N": 40.0, "S": 12.0, "E": 5.0, "W": 5.0},
        warmup_steps=40,
        horizon_steps=140,
        seed=101,
    )
    assert best_plan_n in ("P5", "P6", "P7"), (
        f"Expected N/S favoring plan for heavy north traffic, got {best_plan_n} (delays: {delays_n})"
    )
    # Delay under P7 should be strictly less than under P1
    assert delays_n["P7"] < delays_n["P1"]

    # Case 2: Extreme East-heavy demand
    features_e, best_plan_e, delays_e = optimizer.evaluate_scenario(
        preset_or_rates={"N": 5.0, "S": 5.0, "E": 40.0, "W": 12.0},
        warmup_steps=40,
        horizon_steps=140,
        seed=202,
    )
    assert best_plan_e in ("P1", "P2", "P3"), (
        f"Expected E/W favoring plan for heavy east traffic, got {best_plan_e} (delays: {delays_e})"
    )
    # Delay under P1 should be strictly less than under P7
    assert delays_e["P1"] < delays_e["P7"]


def test_engineered_features_and_transformer():
    from src.features.feature_engineering import (
        ENGINEERED_FEATURE_NAMES,
        ALL_FEATURE_NAMES,
        compute_engineered_features,
        TrafficFeatureTransformer,
    )

    sim = IntersectionSimulation(seed=42)
    features = extract_features(sim)
    assert len(features) == 22

    # 1. Dict transformation
    enriched_dict = compute_engineered_features(features)
    assert len(enriched_dict) == 34
    for eng_name in ENGINEERED_FEATURE_NAMES:
        assert eng_name in enriched_dict

    # 2. DataFrame transformation
    df_in = features_to_dataframe([features, features])
    transformer = TrafficFeatureTransformer()
    df_out = transformer.transform(df_in)
    assert isinstance(df_out, pd.DataFrame)
    assert df_out.shape == (2, 34)
    for col in ALL_FEATURE_NAMES:
        assert col in df_out.columns

    # 3. NumPy 2D and 1D transformation
    vec = features_to_vector(features)
    vec_out_1d = transformer.transform(vec)
    assert vec_out_1d.shape == (34,)

    vec_out_2d = transformer.transform(np.vstack([vec, vec]))
    assert vec_out_2d.shape == (2, 34)

