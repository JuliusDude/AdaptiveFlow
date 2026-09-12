"""Traffic demand and vehicle arrival generation."""

import random
from typing import Dict, List, Optional
from src.simulator.vehicle import Vehicle


# Standard scenario presets (rates in vehicles per minute)
SCENARIO_PRESETS: Dict[str, Dict[str, float]] = {
    "balanced": {"N": 15.0, "S": 15.0, "E": 15.0, "W": 15.0},
    "north_heavy": {"N": 35.0, "S": 10.0, "E": 8.0, "W": 8.0},
    "east_heavy": {"N": 8.0, "S": 6.0, "E": 35.0, "W": 10.0},
    "opposing_ns_heavy": {"N": 30.0, "S": 25.0, "E": 6.0, "W": 6.0},
    "opposing_ew_heavy": {"N": 6.0, "S": 6.0, "E": 30.0, "W": 28.0},
    "mixed": {"N": 18.0, "S": 8.0, "E": 24.0, "W": 12.0},
    "congested": {"N": 32.0, "S": 28.0, "E": 30.0, "W": 26.0},
    "low_traffic": {"N": 6.0, "S": 6.0, "E": 6.0, "W": 6.0},
}


class TrafficGenerator:
    """Generates vehicle arrivals for the four intersection approaches."""

    def __init__(
        self,
        rates: Optional[Dict[str, float]] = None,
        preset: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> None:
        """Initialize traffic generator.

        Args:
            rates: Dict mapping approach ('N', 'S', 'E', 'W') to arrival rate (veh/min).
            preset: Preset name from SCENARIO_PRESETS.
            seed: Optional random seed for reproducible traffic generation.
        """
        self.rng = random.Random(seed)
        self.next_vehicle_id = 1

        if preset is not None:
            if preset not in SCENARIO_PRESETS:
                raise ValueError(f"Unknown preset '{preset}'. Available: {list(SCENARIO_PRESETS.keys())}")
            self.rates = dict(SCENARIO_PRESETS[preset])
        elif rates is not None:
            for app in ("N", "S", "E", "W"):
                if app not in rates:
                    raise ValueError(f"Missing arrival rate for approach '{app}'.")
            self.rates = dict(rates)
        else:
            self.rates = dict(SCENARIO_PRESETS["balanced"])

    def set_rates(self, rates: Dict[str, float]) -> None:
        """Update arrival rates."""
        for app in ("N", "S", "E", "W"):
            if app in rates:
                self.rates[app] = float(rates[app])

    def generate_step(self, current_time: float, dt: float = 1.0) -> List[Vehicle]:
        """Generate vehicle arrivals for a time step dt.

        Arrivals are modeled as Poisson / Bernoulli arrivals:
        Probability of arrival in time dt = rate_per_sec * dt.

        Args:
            current_time: Simulation timestamp in seconds.
            dt: Time step duration in seconds.

        Returns:
            List of newly spawned Vehicle instances.
        """
        new_vehicles: List[Vehicle] = []

        for approach in ("N", "S", "E", "W"):
            rate_per_min = self.rates[approach]
            rate_per_sec = rate_per_min / 60.0
            expected_arrivals = rate_per_sec * dt

            # Poisson number of arrivals or Bernoulli when expected < 1
            # Using Poisson approximation via Knuth's algorithm with self.rng
            arrivals = self._sample_poisson(expected_arrivals)

            for _ in range(arrivals):
                vehicle = Vehicle(
                    id=self.next_vehicle_id,
                    approach=approach,
                    arrival_time=current_time,
                    position=0.0,
                    speed=max(5.0, min(13.89, self.rng.gauss(11.0, 1.5))),
                    desired_speed=max(8.0, min(15.0, self.rng.gauss(13.89, 1.0))),
                )
                self.next_vehicle_id += 1
                new_vehicles.append(vehicle)

        return new_vehicles

    def _sample_poisson(self, lam: float) -> int:
        """Sample from Poisson distribution using inverse transform."""
        if lam <= 0.0:
            return 0
        if lam > 10.0:
            # Gaussian approximation for large lambda
            val = int(round(self.rng.gauss(lam, lam**0.5)))
            return max(0, val)

        import math
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= self.rng.random()
            if p <= L:
                return k - 1
