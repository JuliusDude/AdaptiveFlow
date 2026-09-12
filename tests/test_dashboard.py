"""Unit tests for the dashboard helper functions and components."""

import pytest
from src.dashboard.app import render_signal_badge, get_predictor, load_training_metrics


def test_render_signal_badge():
    green_badge = render_signal_badge("GREEN")
    assert "#28a745" in green_badge
    assert "GREEN" in green_badge

    yellow_badge = render_signal_badge("YELLOW")
    assert "#ffc107" in yellow_badge

    red_badge = render_signal_badge("RED")
    assert "#dc3545" in red_badge


def test_dashboard_model_and_metrics_loading():
    predictor = get_predictor()
    assert predictor is not None
    assert len(predictor.classes) > 0

    metrics = load_training_metrics()
    assert isinstance(metrics, dict)
    assert "feature_importances" in metrics
