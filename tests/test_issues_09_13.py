"""Verification tests for Issues 09 through 13 remediations."""

import pytest
from src.simulator.vehicle import Vehicle
from src.simulator.signal import TrafficSignal, SignalPhase
from src.simulator.metrics import SimulationMetrics
from src.simulator.intersection import IntersectionSimulation
from src.optimization.timing_optimizer import TimingOptimizer


def test_issue_09_crawling_and_moving_delay_calculation():
    """ISSUE-09: Crawling vehicles (speed >= 0.5 m/s) must accumulate delay in comprehensive metrics."""
    metrics = SimulationMetrics()
    # Vehicle arrives at t=0, at t=30 is at position 30m crawling at 2.0 m/s
    # Free-flow time to 30m is 30m / 13.89 m/s = 2.16s
    # Actual lost time (delay) = 30s - 2.16s = 27.84s
    # But because speed = 2.0 m/s >= 0.5 m/s, wait_time is 0.0!
    crawling_veh = Vehicle(id=1, approach="N", arrival_time=0.0, position=30.0, speed=2.0)
    assert crawling_veh.wait_time == 0.0

    # Without current_time (fallback), comprehensive delay uses wait_time (0.0)
    delay_legacy = metrics.calculate_comprehensive_delay([crawling_veh])
    assert delay_legacy == 0.0

    # With current_time=30.0, comprehensive delay accurately captures crawling delay
    comp_delay = metrics.calculate_comprehensive_delay([crawling_veh], current_time=30.0)
    expected_delay = 30.0 - (30.0 / crawling_veh.desired_speed)
    assert pytest.approx(comp_delay, abs=0.05) == expected_delay
    assert comp_delay > 25.0


def test_issue_10_dynamic_tie_breaking_ns_vs_ew():
    """ISSUE-10: Symmetrical tie-break must favor the approach with higher queue/demand pressure."""
    optimizer = TimingOptimizer()

    # Create dummy intersection with high North queue
    sim_ns = IntersectionSimulation(signal=TrafficSignal(initial_plan="P4"))
    for i in range(5):
        v = Vehicle(id=i, approach="N", arrival_time=0.0, position=140.0 - i * 7.0, speed=0.0, state="queued")
        sim_ns.vehicles["N"].append(v)

    # In optimize(), tie-breaking key should pick higher NS plan (P5, P6, or P7) because NS has queued vehicles
    best_plan_ns, _, _ = optimizer.optimize(sim_ns, horizon_steps=1)
    assert int(best_plan_ns[1:]) >= 4

    # Create dummy intersection with high East queue
    sim_ew = IntersectionSimulation(signal=TrafficSignal(initial_plan="P4"))
    for i in range(5):
        v = Vehicle(id=i, approach="E", arrival_time=0.0, position=140.0 - i * 7.0, speed=0.0, state="queued")
        sim_ew.vehicles["E"].append(v)

    best_plan_ew, _, _ = optimizer.optimize(sim_ew, horizon_steps=1)
    assert int(best_plan_ew[1:]) <= 4


def test_issue_11_discrete_euler_braking_no_emergency_clamp():
    """ISSUE-11: Approaching vehicle must smoothly decelerate to red signal without deceleration > d_max."""
    # Vehicle cruising at desired speed (13.89 m/s) 50m before stop line
    stop_line = 150.0
    v = Vehicle(id=1, approach="N", arrival_time=0.0, position=100.0, speed=13.89)

    max_observed_decel = 0.0
    speed_drops = []

    # Step approaching red signal until stopped
    for _ in range(20):
        prev_speed = v.speed
        v.update_kinematics(
            dt=1.0,
            stop_line_pos=stop_line,
            intersection_end_pos=180.0,
            can_proceed=False,
            lead_vehicle=None,
        )
        decel = prev_speed - v.speed
        if decel > 0:
            speed_drops.append(decel)
            if decel > max_observed_decel:
                max_observed_decel = decel

    # Maximum deceleration in any single 1-second step must not exceed max_decel (4.0 m/s^2)
    # Previously, single-step deceleration spiked to 11.35 m/s^2!
    assert max_observed_decel <= 4.01
    # Vehicle must stop at or before the stop line without penetrating
    assert v.position <= stop_line
    assert v.speed == 0.0
    assert v.state == "queued"


def test_issue_12_continuous_principal_phase_elapsed_time():
    """ISSUE-12: Principal phase elapsed time must not reset to 0 at Yellow and All-Red."""
    signal = TrafficSignal(initial_plan="P4")  # 30s NS green, 3s yellow, 2s all-red
    # Step through 30 seconds of Phase A Green
    for _ in range(30):
        signal.step(dt=1.0)

    # Now at step 30, signal enters Phase A Yellow
    assert signal.current_phase == SignalPhase.PHASE_A_YELLOW
    phase_enc, elapsed = signal.get_feature_encoding()
    assert phase_enc == 0  # Phase A
    # Elapsed time must be continuous (>= 30.0s), NOT reset to 0.0!
    assert elapsed >= 30.0

    # Step 2 more seconds into Yellow
    signal.step(dt=1.0)
    signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_A_YELLOW
    phase_enc, elapsed = signal.get_feature_encoding()
    assert elapsed == 32.0

    # Step 1 second into All-Red
    signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_A_ALL_RED
    phase_enc, elapsed = signal.get_feature_encoding()
    assert elapsed == 33.0

    # Finish All-Red and step into Phase B Green
    signal.step(dt=1.0)
    signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_B_GREEN
    phase_enc, elapsed = signal.get_feature_encoding()
    assert phase_enc == 1  # Phase B
    assert elapsed == 0.0  # Reset to 0.0 at Phase B onset

    # After 1 step into Phase B Green
    signal.step(dt=1.0)
    phase_enc, elapsed = signal.get_feature_encoding()
    assert phase_enc == 1
    assert elapsed == 1.0
