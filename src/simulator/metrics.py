"""Performance metrics tracking for intersection simulation."""

from typing import Dict, List, Any, Optional
from src.simulator.vehicle import Vehicle


class SimulationMetrics:
    """Tracks delays, queues, throughput, and performance telemetry."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all accumulated metrics."""
        self.total_spawned: int = 0
        self.total_exited: int = 0
        self.total_delay_seconds: float = 0.0
        self.total_wait_seconds: float = 0.0  # Stopped delay

        # Per-approach metrics
        self.spawned_per_approach: Dict[str, int] = {"N": 0, "S": 0, "E": 0, "W": 0}
        self.exited_per_approach: Dict[str, int] = {"N": 0, "S": 0, "E": 0, "W": 0}
        self.delay_per_approach: Dict[str, float] = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
        self.wait_per_approach: Dict[str, float] = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}

        # Queue tracking
        self.queue_history: List[Dict[str, int]] = []
        self.max_queue_per_approach: Dict[str, int] = {"N": 0, "S": 0, "E": 0, "W": 0}

    def record_spawn(self, vehicle: Vehicle) -> None:
        """Record a newly spawned vehicle."""
        self.total_spawned += 1
        self.spawned_per_approach[vehicle.approach] += 1

    def record_exit(self, vehicle: Vehicle, exit_time: float, free_flow_time: float) -> None:
        """Record vehicle departure through the intersection.

        Args:
            vehicle: The departed Vehicle instance.
            exit_time: Simulation timestamp of departure.
            free_flow_time: Expected unobstructed travel time across approach + intersection.
        """
        self.total_exited += 1
        app = vehicle.approach
        self.exited_per_approach[app] += 1

        actual_travel_time = exit_time - vehicle.arrival_time
        delay = max(0.0, actual_travel_time - free_flow_time)

        self.total_delay_seconds += delay
        self.total_wait_seconds += vehicle.wait_time
        self.delay_per_approach[app] += delay
        self.wait_per_approach[app] += vehicle.wait_time

    def record_step_queues(self, queues: Dict[str, int]) -> None:
        """Record instantaneous queue counts for all approaches."""
        self.queue_history.append(dict(queues))
        for app, q in queues.items():
            if q > self.max_queue_per_approach[app]:
                self.max_queue_per_approach[app] = q

    @property
    def average_delay(self) -> float:
        """Average vehicle delay in seconds for completed trips."""
        if self.total_exited == 0:
            return 0.0
        return self.total_delay_seconds / self.total_exited

    @property
    def average_wait(self) -> float:
        """Average stopped wait time in seconds for completed trips."""
        if self.total_exited == 0:
            return 0.0
        return self.total_wait_seconds / self.total_exited

    @property
    def max_queue(self) -> int:
        """Maximum queue length observed across all approaches."""
        if not self.max_queue_per_approach:
            return 0
        return max(self.max_queue_per_approach.values())

    @property
    def average_queue(self) -> float:
        """Average total queue across all approaches across all time steps."""
        if not self.queue_history:
            return 0.0
        total_q_sum = sum(sum(step.values()) for step in self.queue_history)
        return total_q_sum / len(self.queue_history)

    def calculate_comprehensive_delay(
        self,
        active_vehicles: List[Vehicle],
        current_time: Optional[float] = None,
    ) -> float:
        """Calculate average delay including both completed trips and in-network waiting vehicles.

        Eliminates survivorship and crawling bias by penalizing controllers that leave vehicles
        trapped in queues or crawling at low speeds.

        Args:
            active_vehicles: List of Vehicle instances currently inside the network or entry buffer.
            current_time: Current simulation timestamp. If provided, calculates true lost time
                (elapsed - free-flow travel time). If None, defaults to stopped wait_time.
        """
        if current_time is not None:
            active_delay = sum(
                max(0.0, (current_time - v.arrival_time) - (v.position / max(1.0, v.desired_speed)))
                for v in active_vehicles
            )
        else:
            active_delay = sum(v.wait_time for v in active_vehicles)

        total_delay = self.total_delay_seconds + active_delay
        total_vehicles = self.total_exited + len(active_vehicles)
        if total_vehicles == 0:
            return 0.0
        return total_delay / total_vehicles

    def get_summary(
        self,
        elapsed_seconds: float = 1.0,
        active_vehicles: Optional[List[Vehicle]] = None,
    ) -> Dict[str, Any]:
        """Compute performance summary dictionary.

        Args:
            elapsed_seconds: Total elapsed simulation time.
            active_vehicles: Optional list of all in-network/queued vehicles for comprehensive delay.
        """
        throughput_vph = (self.total_exited / max(1.0, elapsed_seconds)) * 3600.0

        if active_vehicles is not None:
            comp_delay = round(self.calculate_comprehensive_delay(active_vehicles, current_time=elapsed_seconds), 2)
            active_count = len(active_vehicles)
        else:
            comp_delay = round(self.average_delay, 2)
            active_count = 0

        per_approach_summary = {}
        for app in ("N", "S", "E", "W"):
            exited = self.exited_per_approach[app]
            avg_d = (self.delay_per_approach[app] / exited) if exited > 0 else 0.0
            avg_w = (self.wait_per_approach[app] / exited) if exited > 0 else 0.0
            per_approach_summary[app] = {
                "spawned": self.spawned_per_approach[app],
                "exited": exited,
                "avg_delay": round(avg_d, 2),
                "avg_wait": round(avg_w, 2),
                "max_queue": self.max_queue_per_approach[app],
            }

        return {
            "total_spawned": self.total_spawned,
            "total_exited": self.total_exited,
            "active_in_network": active_count,
            "throughput_vph": round(throughput_vph, 1),
            "average_delay": round(self.average_delay, 2),
            "comprehensive_delay": comp_delay,
            "average_wait": round(self.average_wait, 2),
            "average_queue": round(self.average_queue, 2),
            "max_queue": self.max_queue,
            "per_approach": per_approach_summary,
        }
