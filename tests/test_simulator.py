"""Unit tests for the traffic simulator components."""

import pytest
from src.simulator.vehicle import Vehicle


def test_vehicle_initialization():
    v = Vehicle(id=1, approach="N", arrival_time=0.0)
    assert v.id == 1
    assert v.approach == "N"
    assert v.position == 0.0
    assert v.speed == 0.0
    assert v.state == "approaching"
    assert v.wait_time == 0.0


def test_vehicle_acceleration_and_stopping_at_red():
    v = Vehicle(id=1, approach="N", arrival_time=0.0, desired_speed=10.0)
    stop_line = 100.0
    end_pos = 120.0

    # Step simulation with red signal (can_proceed=False)
    for _ in range(25):
        v.update_kinematics(
            dt=1.0,
            stop_line_pos=stop_line,
            intersection_end_pos=end_pos,
            can_proceed=False,
            lead_vehicle=None,
        )

    # Vehicle should reach stop line (or near it) and stop
    assert v.position <= stop_line
    assert v.speed < 0.5
    assert v.state == "queued"
    assert v.wait_time > 0.0


def test_vehicle_crossing_on_green():
    v = Vehicle(id=1, approach="N", arrival_time=0.0, position=90.0, speed=5.0)
    stop_line = 100.0
    end_pos = 120.0

    # Step with green signal
    for _ in range(10):
        v.update_kinematics(
            dt=1.0,
            stop_line_pos=stop_line,
            intersection_end_pos=end_pos,
            can_proceed=True,
            lead_vehicle=None,
        )

    # Vehicle should have crossed intersection and reached 'exited'
    assert v.position >= end_pos
    assert v.state == "exited"


def test_vehicle_car_following_queue():
    stop_line = 100.0
    end_pos = 120.0

    # Lead vehicle stopped at stop line
    v1 = Vehicle(id=1, approach="N", arrival_time=0.0, position=stop_line, speed=0.0, state="queued")
    # Follower vehicle approaching behind
    v2 = Vehicle(id=2, approach="N", arrival_time=0.0, position=80.0, speed=5.0)

    for _ in range(10):
        v2.update_kinematics(
            dt=1.0,
            stop_line_pos=stop_line,
            intersection_end_pos=end_pos,
            can_proceed=False,
            lead_vehicle=v1,
        )

    # v2 must not crash into v1 (must respect effective_length: v1.position - 6.5)
    assert v2.position <= v1.position - v2.effective_length + 0.01
    assert v2.state == "queued"


from src.simulator.signal import TrafficSignal, SignalPhase, TIMING_PLANS


def test_traffic_signal_timing_plans():
    signal = TrafficSignal(initial_plan="P4")
    assert signal.current_plan_name == "P4"
    assert signal.plan == {"NS": 30, "EW": 30}
    assert signal.can_proceed("N") is True
    assert signal.can_proceed("S") is True
    assert signal.can_proceed("E") is False
    assert signal.can_proceed("W") is False


def test_traffic_signal_full_cycle_transition():
    # P4: NS=30, EW=30, Yellow=3, All-Red=2 -> Total cycle = 30 + 3 + 2 + 30 + 3 + 2 = 70s
    signal = TrafficSignal(initial_plan="P4", yellow_duration=3, all_red_duration=2)
    signal.set_next_plan("P1")

    # Step through Phase A Green (30s)
    for _ in range(30):
        signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_A_YELLOW
    assert signal.get_signal_color("N") == "YELLOW"

    # Step through Phase A Yellow (3s)
    for _ in range(3):
        signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_A_ALL_RED
    assert signal.get_signal_color("N") == "RED"
    assert signal.get_signal_color("E") == "RED"

    # Step through Phase A All-Red (2s)
    for _ in range(2):
        signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_B_GREEN
    assert signal.can_proceed("E") is True

    # Step through Phase B Green (30s)
    for _ in range(30):
        signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_B_YELLOW

    # Step through Phase B Yellow (3s)
    for _ in range(3):
        signal.step(dt=1.0)
    assert signal.current_phase == SignalPhase.PHASE_B_ALL_RED

    # Step through Phase B All-Red (2s)
    for _ in range(2):
        signal.step(dt=1.0)

    # Now cycle should be completed and new plan P1 active
    assert signal.cycle_count == 1
    assert signal.current_plan_name == "P1"
    assert signal.current_phase == SignalPhase.PHASE_A_GREEN
    assert signal.plan == {"NS": 15, "EW": 45}


from src.simulator.traffic_generator import TrafficGenerator, SCENARIO_PRESETS


def test_traffic_generator_presets():
    gen = TrafficGenerator(preset="north_heavy", seed=42)
    assert gen.rates["N"] == 35.0
    assert gen.rates["S"] == 10.0
    assert gen.rates["E"] == 8.0
    assert gen.rates["W"] == 8.0


def test_traffic_generator_reproducibility():
    gen1 = TrafficGenerator(preset="balanced", seed=123)
    gen2 = TrafficGenerator(preset="balanced", seed=123)

    arrivals1 = [gen1.generate_step(t, dt=1.0) for t in range(60)]
    arrivals2 = [gen2.generate_step(t, dt=1.0) for t in range(60)]

    assert len(arrivals1) == len(arrivals2)
    for step1, step2 in zip(arrivals1, arrivals2):
        assert len(step1) == len(step2)
        for v1, v2 in zip(step1, step2):
            assert v1.approach == v2.approach
            assert v1.arrival_time == v2.arrival_time


from src.simulator.metrics import SimulationMetrics


def test_simulation_metrics():
    metrics = SimulationMetrics()
    v1 = Vehicle(id=1, approach="N", arrival_time=0.0, wait_time=5.0)
    v2 = Vehicle(id=2, approach="E", arrival_time=5.0, wait_time=10.0)

    metrics.record_spawn(v1)
    metrics.record_spawn(v2)
    assert metrics.total_spawned == 2

    # Free flow time = 10s.
    # v1 exits at t=20 (travel time = 20s, delay = 10s)
    metrics.record_exit(v1, exit_time=20.0, free_flow_time=10.0)
    # v2 exits at t=35 (travel time = 30s, delay = 20s)
    metrics.record_exit(v2, exit_time=35.0, free_flow_time=10.0)

    assert metrics.total_exited == 2
    # Avg delay = (10 + 20) / 2 = 15.0s
    assert metrics.average_delay == 15.0
    # Avg wait = (5 + 10) / 2 = 7.5s
    assert metrics.average_wait == 7.5

    # Test queues
    metrics.record_step_queues({"N": 3, "S": 2, "E": 5, "W": 1})
    metrics.record_step_queues({"N": 4, "S": 1, "E": 6, "W": 0})
    assert metrics.max_queue == 6
    # Step 1 sum = 11, Step 2 sum = 11, avg = 11.0
    assert metrics.average_queue == 11.0

    summary = metrics.get_summary(elapsed_seconds=60.0)
    assert summary["total_exited"] == 2
    assert summary["average_delay"] == 15.0
    assert summary["per_approach"]["N"]["exited"] == 1


from src.simulator.intersection import IntersectionSimulation


def test_intersection_simulation_features_and_step():
    sim = IntersectionSimulation(seed=42)

    # Step simulation for 70 seconds (1 full cycle)
    for _ in range(70):
        sim.step(dt=1.0)

    features = sim.get_feature_dict()

    expected_keys = [
        "N_count", "S_count", "E_count", "W_count",
        "N_queue", "S_queue", "E_queue", "W_queue",
        "N_arrival", "S_arrival", "E_arrival", "W_arrival",
        "N_speed", "S_speed", "E_speed", "W_speed",
        "N_queue_growth", "S_queue_growth", "E_queue_growth", "W_queue_growth",
        "current_phase", "elapsed_phase_time",
    ]

    assert len(features) == 22
    for k in expected_keys:
        assert k in features, f"Missing feature {k}"
        assert isinstance(features[k], (int, float))

    # Current phase must be 0 (N/S) or 1 (E/W)
    assert features["current_phase"] in (0.0, 1.0)

    # Summary metrics must have tracked operations
    summary = sim.get_summary()
    assert summary["total_spawned"] > 0
    assert summary["total_exited"] > 0
    assert summary["average_delay"] >= 0.0


def test_intersection_simulation_clone_independence():
    sim = IntersectionSimulation(seed=99)
    for _ in range(30):
        sim.step(dt=1.0)

    clone_sim = sim.clone()

    # Step clone for another 20s
    for _ in range(20):
        clone_sim.step(dt=1.0)

    assert clone_sim.current_time == 50.0
    assert sim.current_time == 30.0
    assert clone_sim.metrics.total_spawned >= sim.metrics.total_spawned


def test_end_to_end_multicycle_simulation():
    # Run 3 full cycles (210 seconds) under north-heavy traffic
    gen = TrafficGenerator(preset="north_heavy", seed=42)
    signal = TrafficSignal(initial_plan="P6")  # P6 favors N/S (40s NS / 20s EW)
    sim = IntersectionSimulation(signal=signal, generator=gen)

    for _ in range(210):
        sim.step(dt=1.0)

    summary = sim.get_summary()
    assert summary["total_spawned"] > 50
    assert summary["total_exited"] > 40
    # North approach should have handled significantly more vehicles
    assert summary["per_approach"]["N"]["spawned"] > summary["per_approach"]["E"]["spawned"]
    assert summary["throughput_vph"] > 0
    assert summary["average_delay"] > 0


def test_congested_queue_headway_integrity():
    # Verify vehicles maintain min_gap spacing even in extreme queue conditions
    sim = IntersectionSimulation(seed=777)
    # Step simulation while keeping signals red for all (or natural queue behind red)
    for _ in range(40):
        sim.step(dt=1.0)

    # Check vehicle spacing on each approach
    for app, veh_list in sim.vehicles.items():
        sorted_vehs = sorted(veh_list, key=lambda v: v.position, reverse=True)
        for i in range(len(sorted_vehs) - 1):
            leader = sorted_vehs[i]
            follower = sorted_vehs[i + 1]
            gap = leader.position - follower.position
            # Gap between vehicle positions must be at least follower's effective_length (4.5 + 2.0 = 6.5m)
            assert gap >= follower.effective_length - 0.05, (
                f"Headway violation on approach {app}: gap={gap}, effective_length={follower.effective_length}"
            )


def test_no_negative_vehicle_positions_in_heavy_congestion():
    # Run 300 steps under congested preset and verify position >= 0.0 always
    sim = IntersectionSimulation(generator=TrafficGenerator(preset="congested", seed=999))
    for _ in range(300):
        sim.step(dt=1.0)
        for app in ("N", "S", "E", "W"):
            for v in sim.vehicles[app]:
                assert v.position >= 0.0, f"Vehicle {v.id} on {app} had negative position {v.position}"


def test_moving_lead_vehicle_smooth_following():
    # When lead vehicle is moving at desired speed, follower within 15m should not brake abruptly
    v_lead = Vehicle(id=1, approach="N", arrival_time=0.0, position=50.0, speed=13.0, desired_speed=13.89)
    v_fol = Vehicle(id=2, approach="N", arrival_time=0.0, position=38.0, speed=13.0, desired_speed=13.89)

    v_fol.update_kinematics(
        dt=1.0,
        stop_line_pos=150.0,
        intersection_end_pos=170.0,
        can_proceed=True,
        lead_vehicle=v_lead,
    )
    # With moving leader, safe_speed >= 13 m/s, so follower should maintain or accelerate, not drop to 6-8 m/s
    assert v_fol.speed >= 12.5


def test_comprehensive_delay_penalizes_trapped_queues():
    metrics = SimulationMetrics()
    # 2 vehicles exited with 10s delay each
    v_ex1 = Vehicle(id=1, approach="N", arrival_time=0.0, wait_time=5.0)
    v_ex2 = Vehicle(id=2, approach="N", arrival_time=0.0, wait_time=5.0)
    metrics.record_exit(v_ex1, exit_time=20.0, free_flow_time=10.0)
    metrics.record_exit(v_ex2, exit_time=20.0, free_flow_time=10.0)

    # 4 vehicles trapped in queue with 50s wait each
    trapped_vehs = [Vehicle(id=i, approach="E", arrival_time=0.0, wait_time=50.0) for i in range(3, 7)]

    # Legacy exited-only average delay ignores trapped vehicles
    assert metrics.average_delay == 10.0

    # Comprehensive delay includes trapped vehicles: (2*10 + 4*50) / 6 = 220 / 6 = 36.67s
    comp_delay = metrics.calculate_comprehensive_delay(trapped_vehs)
    assert pytest.approx(comp_delay, abs=0.01) == 36.67






