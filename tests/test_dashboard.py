"""Unit tests for the dashboard helper functions, playback buffer, and canvas visualizer."""

import json
import pytest
from src.dashboard.app import render_signal_badge, get_predictor, load_training_metrics
from src.dashboard.playback import SimulationPlaybackBuffer
from src.dashboard.canvas_visualizer import generate_intersection_html


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


def test_playback_buffer_initialization_and_stepping():
    buf = SimulationPlaybackBuffer(preset="balanced", seed=42)
    assert len(buf.frames) == 1
    assert buf.frames[0]["t"] == 0.0

    # Test buffer horizon
    buf.buffer_horizon(10)
    assert len(buf.frames) == 11
    assert buf.frames[-1]["t"] == 10.0

    # Validate frame structure
    latest = buf.get_latest_frame()
    assert "ml" in latest and "fixed" in latest
    assert "vehicles" in latest["ml"]
    assert "metrics" in latest["ml"]
    assert "comp_delay" in latest["ml"]["metrics"]
    assert "plan" in latest["ml"]


def test_canvas_visualizer_html_generation():
    buf = SimulationPlaybackBuffer(preset="balanced", seed=42)
    buf.buffer_horizon(5)
    json_payload = buf.to_json()

    html = generate_intersection_html(json_payload)
    assert isinstance(html, str)
    assert len(html) > 1000
    assert "AdaptiveFlow Intersection Visualizer" in html
    assert "playback-dock" in html
    assert "timeScrubber" in html
    assert "sigML_N" in html
    assert "sigFixed_N" in html
    assert "btnModeDual" in html
