"""Unit and integration tests for the ML pipeline and closed-loop controller."""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from src.features.feature_engineering import FEATURE_NAMES
from src.simulator.intersection import IntersectionSimulation
from src.simulator.signal import TIMING_PLANS
from src.ml.predict import SignalTimingPredictor, AdaptiveMLController
from src.ml.evaluate import run_scenario_trial


def test_predictor_initialization_and_inference():
    predictor = SignalTimingPredictor()
    assert len(predictor.classes) > 0

    # Test dummy features input
    dummy_features = {feat: 5.0 for feat in FEATURE_NAMES}
    dummy_features["current_phase"] = 0.0
    dummy_features["elapsed_phase_time"] = 10.0

    # 1. Predict single plan
    plan = predictor.predict(dummy_features)
    assert plan in TIMING_PLANS, f"Invalid predicted plan: {plan}"

    # 2. Predict probability distribution
    probs = predictor.predict_proba(dummy_features)
    assert len(probs) == len(predictor.classes)
    assert pytest.approx(sum(probs.values()), abs=1e-3) == 1.0


def test_predictor_from_live_simulation():
    sim = IntersectionSimulation(seed=42)
    for _ in range(25):
        sim.step(dt=1.0)

    predictor = SignalTimingPredictor()
    plan = predictor.predict_from_sim(sim)
    assert plan in TIMING_PLANS


def test_adaptive_ml_controller_closed_loop():
    sim = IntersectionSimulation(seed=123)
    controller = AdaptiveMLController()

    # Initial update
    initial_plan = controller.update(sim, force_update=True)
    assert initial_plan in TIMING_PLANS
    assert len(controller.decision_history) == 1

    # Step simulation for a full cycle (70s)
    for _ in range(70):
        sim.step(dt=1.0)
        controller.update(sim)

    # Controller should have triggered a decision at cycle completion
    assert len(controller.decision_history) >= 2
    last_decision = controller.decision_history[-1]
    assert "selected_plan" in last_decision
    assert "ns_green" in last_decision
    assert "ew_green" in last_decision


def test_run_scenario_trial_benchmark():
    rates = {"N": 25.0, "S": 15.0, "E": 10.0, "W": 10.0}
    res = run_scenario_trial(rates=rates, seed=77, duration_seconds=140)

    assert "fixed" in res
    assert "ml" in res
    assert res["fixed"]["total_exited"] > 0
    assert res["ml"]["total_exited"] > 0
    assert res["fixed"]["average_delay"] >= 0.0
    assert res["ml"]["average_delay"] >= 0.0
