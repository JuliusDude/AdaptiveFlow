"""4-Way discrete-time intersection simulation engine."""

import copy
from collections import deque
from typing import Dict, List, Optional, Tuple, Any
from src.simulator.vehicle import Vehicle
from src.simulator.signal import TrafficSignal
from src.simulator.traffic_generator import TrafficGenerator
from src.simulator.metrics import SimulationMetrics


class IntersectionSimulation:
    """Simulates a four-way intersection with vehicle dynamics, signals, and telemetry."""

    def __init__(
        self,
        approach_length: float = 150.0,
        intersection_width: float = 20.0,
        signal: Optional[TrafficSignal] = None,
        generator: Optional[TrafficGenerator] = None,
        seed: Optional[int] = None,
    ) -> None:
        """Initialize 4-way intersection simulation.

        Args:
            approach_length: Distance from spawn to stop line in meters (default 150m).
            intersection_width: Distance through intersection in meters (default 20m).
            signal: Optional custom TrafficSignal instance.
            generator: Optional custom TrafficGenerator instance.
            seed: Random seed for reproducible runs.
        """
        self.approach_length = approach_length
        self.intersection_width = intersection_width
        self.stop_line_pos = approach_length
        self.intersection_end_pos = approach_length + intersection_width

        # Components
        self.signal = signal if signal is not None else TrafficSignal()
        self.generator = generator if generator is not None else TrafficGenerator(seed=seed)
        self.metrics = SimulationMetrics()

        # Simulation clock
        self.current_time: float = 0.0

        # Active vehicles on each approach: dict of lists, sorted by position descending (leaders first)
        self.vehicles: Dict[str, List[Vehicle]] = {"N": [], "S": [], "E": [], "W": []}

        # Entrance holding buffers when queues spill back to approach entry (position 0.0)
        self.entry_buffers: Dict[str, deque] = {
            "N": deque(),
            "S": deque(),
            "E": deque(),
            "W": deque(),
        }

        # Rolling history buffers for 22-feature calculation
        # Arrival events per approach: list of timestamps within last 30s
        self._recent_arrivals: Dict[str, deque] = {
            "N": deque(),
            "S": deque(),
            "E": deque(),
            "W": deque(),
        }
        # Queue history per approach: last 11 seconds (index 0 is current, index -1 is 10s ago)
        self._recent_queues: Dict[str, deque] = {
            "N": deque(maxlen=11),
            "S": deque(maxlen=11),
            "E": deque(maxlen=11),
            "W": deque(maxlen=11),
        }
        # Mean speed history per approach: last 10 seconds
        self._recent_speeds: Dict[str, deque] = {
            "N": deque(maxlen=10),
            "S": deque(maxlen=10),
            "E": deque(maxlen=10),
            "W": deque(maxlen=10),
        }

        # Initialize history buffers with zeros
        for app in ("N", "S", "E", "W"):
            for _ in range(11):
                self._recent_queues[app].append(0)
            for _ in range(10):
                self._recent_speeds[app].append(13.89)

    def clone(self) -> "IntersectionSimulation":
        """Create a deep copy of the simulation state for lookahead optimization."""
        return copy.deepcopy(self)

    def step(self, dt: float = 1.0) -> None:
        """Advance the simulation by dt seconds (default 1.0s).

        Args:
            dt: Time step duration in seconds.
        """
        self.current_time += dt

        # 1. Spawn new vehicles and queue them into entry buffers
        new_vehicles = self.generator.generate_step(self.current_time, dt=dt)
        for v in new_vehicles:
            self.entry_buffers[v.approach].append(v)
            self.metrics.record_spawn(v)
            self._recent_arrivals[v.approach].append(self.current_time)

        # 2. Advance traffic signal
        self.signal.step(dt=dt)

        # 3. Update vehicle kinematics and inject buffered vehicles per approach
        for app in ("N", "S", "E", "W"):
            # Sort vehicles so leaders are at the front (highest position first)
            self.vehicles[app].sort(key=lambda veh: veh.position, reverse=True)

            can_proceed = self.signal.can_proceed(app)
            active_list: List[Vehicle] = []
            speeds_this_step: List[float] = []

            lead_veh: Optional[Vehicle] = None
            for veh in self.vehicles[app]:
                veh.update_kinematics(
                    dt=dt,
                    stop_line_pos=self.stop_line_pos,
                    intersection_end_pos=self.intersection_end_pos,
                    can_proceed=can_proceed,
                    lead_vehicle=lead_veh,
                )

                if veh.state == "exited":
                    # Record exit metrics
                    free_flow_time = self.intersection_end_pos / max(1.0, veh.desired_speed)
                    self.metrics.record_exit(veh, exit_time=self.current_time, free_flow_time=free_flow_time)
                else:
                    active_list.append(veh)
                    speeds_this_step.append(veh.speed)
                    lead_veh = veh

            self.vehicles[app] = active_list

            # Release vehicles from entry buffer if space is clear (rearmost position >= 6.5m)
            while self.entry_buffers[app]:
                rearmost_pos = min((v.position for v in self.vehicles[app]), default=float("inf"))
                if rearmost_pos >= 6.5:
                    v_entry = self.entry_buffers[app].popleft()
                    v_entry.position = 0.0
                    v_entry.speed = 0.0
                    v_entry.state = "approaching"
                    self.vehicles[app].append(v_entry)
                else:
                    break

            # Accumulate waiting time for any vehicles still stuck in entrance buffer
            for v_buf in self.entry_buffers[app]:
                v_buf.wait_time += dt
                v_buf.state = "queued"
                v_buf.speed = 0.0

            # Telemetry buffering: mean speed this step
            if speeds_this_step:
                mean_spd = sum(speeds_this_step) / len(speeds_this_step)
            else:
                mean_spd = 13.89  # Default to free flow speed if empty
            self._recent_speeds[app].append(mean_spd)

            # Telemetry buffering: clean old arrivals (> 30s ago)
            cutoff_time = self.current_time - 30.0
            while self._recent_arrivals[app] and self._recent_arrivals[app][0] < cutoff_time:
                self._recent_arrivals[app].popleft()

            # Telemetry buffering: current queue (stopped on road + queued in entry buffer)
            road_q = sum(1 for v in self.vehicles[app] if v.state == "queued")
            total_q = road_q + len(self.entry_buffers[app])
            self._recent_queues[app].append(total_q)

        # 4. Record step queues in metrics
        step_queues = {app: self._recent_queues[app][-1] for app in ("N", "S", "E", "W")}
        self.metrics.record_step_queues(step_queues)

    def get_feature_dict(self) -> Dict[str, float]:
        """Extract the exact 22 traffic-state features defined in project.md Section 4.

        Returns:
            Dictionary containing the 22 features:
            - Demand (4): N_count, S_count, E_count, W_count
            - Congestion (4): N_queue, S_queue, E_queue, W_queue
            - Arrival dynamics (4): N_arrival, S_arrival, E_arrival, W_arrival (veh/min over last 30s)
            - Speed (4): N_speed, S_speed, E_speed, W_speed (mean speed over last 10s)
            - Queue dynamics (4): N_queue_growth, S_queue_growth, E_queue_growth, W_queue_growth (Q_t - Q_t-10)
            - Signal state (2): current_phase (0=N/S, 1=E/W), elapsed_phase_time (s)
        """
        features: Dict[str, float] = {}

        # 1. Demand: vehicle count inside observation zone and entry buffer
        for app in ("N", "S", "E", "W"):
            features[f"{app}_count"] = float(len(self.vehicles[app]) + len(self.entry_buffers[app]))

        # 2. Congestion: stopped queue length (including entry buffer)
        for app in ("N", "S", "E", "W"):
            q_now = self._recent_queues[app][-1]
            features[f"{app}_queue"] = float(q_now)

        # 3. Arrival dynamics: arrivals in previous 30s * 2 (veh/min)
        for app in ("N", "S", "E", "W"):
            count_30s = len(self._recent_arrivals[app])
            features[f"{app}_arrival"] = float(count_30s * 2.0)

        # 4. Speed: mean speed over previous 10s
        for app in ("N", "S", "E", "W"):
            spd_hist = list(self._recent_speeds[app])
            avg_spd = (sum(spd_hist) / len(spd_hist)) if spd_hist else 13.89
            features[f"{app}_speed"] = round(avg_spd, 2)

        # 5. Queue growth: Q_current - Q_10s_ago
        for app in ("N", "S", "E", "W"):
            q_now = self._recent_queues[app][-1]
            q_10s_ago = self._recent_queues[app][0]  # Oldest element in maxlen=11 deque
            features[f"{app}_queue_growth"] = float(q_now - q_10s_ago)

        # 6. Signal state: current_phase (0=NS, 1=EW) and elapsed_phase_time
        phase_enc, elapsed_time = self.signal.get_feature_encoding()
        features["current_phase"] = float(phase_enc)
        features["elapsed_phase_time"] = round(elapsed_time, 2)

        return features

    def get_summary(self) -> Dict[str, Any]:
        """Return comprehensive simulation metrics summary."""
        active_vehs = [v for app_vehs in self.vehicles.values() for v in app_vehs] + [
            v for buf in self.entry_buffers.values() for v in buf
        ]
        return self.metrics.get_summary(elapsed_seconds=self.current_time, active_vehicles=active_vehs)
