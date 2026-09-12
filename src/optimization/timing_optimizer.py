"""Ground-truth timing plan optimization via forward delay simulation."""

from typing import Dict, Tuple, Union, Optional, Any, Sequence
from src.simulator.intersection import IntersectionSimulation
from src.simulator.signal import TIMING_PLANS, TrafficSignal
from src.simulator.traffic_generator import TrafficGenerator
from src.features.feature_engineering import extract_features


class TimingOptimizer:
    """Evaluates candidate timing plans (P1-P7) and identifies the minimum delay plan."""

    def __init__(self, candidate_plans: Optional[Sequence[str]] = None) -> None:
        """Initialize timing optimizer.

        Args:
            candidate_plans: Optional list of plan names to evaluate (default P1-P7).
        """
        self.candidate_plans = list(candidate_plans) if candidate_plans else list(TIMING_PLANS.keys())

    def evaluate_plan(
        self,
        sim: IntersectionSimulation,
        plan_name: str,
        horizon_steps: int = 140,
        dt: float = 1.0,
    ) -> float:
        """Simulate a candidate plan forward from the current simulation state.

        Args:
            sim: Current intersection simulation state.
            plan_name: Candidate plan identifier (e.g. 'P1', ..., 'P7').
            horizon_steps: Number of simulation steps (seconds) to evaluate forward.
            dt: Simulation time step.

        Returns:
            Average vehicle delay (seconds) experienced across exited and queued vehicles.
        """
        eval_sim = sim.clone()

        # Set signal to evaluate this timing plan immediately and for subsequent cycles
        eval_sim.signal.current_plan_name = plan_name
        eval_sim.signal.next_plan_name = plan_name

        # Reset exit metrics so we only measure delay during the evaluation horizon
        eval_sim.metrics.reset()

        for _ in range(horizon_steps):
            eval_sim.step(dt=dt)

        # Calculate comprehensive delay:
        # 1. Total delay from vehicles that completed their trips during the horizon
        completed_delay = eval_sim.metrics.total_delay_seconds
        completed_vehicles = eval_sim.metrics.total_exited

        # 2. Total accumulated wait time from vehicles still queued/waiting at the end
        active_queued_delay = sum(
            v.wait_time for app_vehs in eval_sim.vehicles.values() for v in app_vehs
        )
        active_vehicles = sum(len(app_vehs) for app_vehs in eval_sim.vehicles.values())

        total_experienced_delay = completed_delay + active_queued_delay
        total_vehicles = completed_vehicles + active_vehicles

        if total_vehicles == 0:
            return 0.0

        return round(total_experienced_delay / total_vehicles, 2)

    def evaluate_all_plans(
        self,
        sim: IntersectionSimulation,
        horizon_steps: int = 140,
        dt: float = 1.0,
    ) -> Dict[str, float]:
        """Evaluate all candidate plans and return their respective average delays.

        Args:
            sim: Current intersection simulation state.
            horizon_steps: Number of forward simulation steps.
            dt: Simulation time step.

        Returns:
            Dictionary mapping plan name to its evaluated average delay.
        """
        results: Dict[str, float] = {}
        for plan_name in self.candidate_plans:
            results[plan_name] = self.evaluate_plan(
                sim=sim,
                plan_name=plan_name,
                horizon_steps=horizon_steps,
                dt=dt,
            )
        return results

    def optimize(
        self,
        sim: IntersectionSimulation,
        horizon_steps: int = 140,
        dt: float = 1.0,
    ) -> Tuple[str, float, Dict[str, float]]:
        """Identify the candidate plan with the minimum average vehicle delay.

        Args:
            sim: Current intersection simulation state.
            horizon_steps: Number of forward simulation steps.
            dt: Simulation time step.

        Returns:
            Tuple of (best_plan_name, best_delay, all_plan_delays_dict).
        """
        all_delays = self.evaluate_all_plans(sim=sim, horizon_steps=horizon_steps, dt=dt)

        # Select plan with minimum delay (tie-break prefers balanced P4)
        best_plan = min(
            self.candidate_plans,
            key=lambda p: (all_delays[p], abs(int(p[1:]) - 4)),
        )
        return best_plan, all_delays[best_plan], all_delays

    def evaluate_scenario(
        self,
        preset_or_rates: Union[str, Dict[str, float]],
        warmup_steps: int = 40,
        horizon_steps: int = 140,
        seed: Optional[int] = 42,
    ) -> Tuple[Dict[str, float], str, Dict[str, float]]:
        """Generate a scenario, run warmup, extract features, and optimize timing.

        Args:
            preset_or_rates: Preset string or dict of approach arrival rates.
            warmup_steps: Warmup duration to build realistic initial queues.
            horizon_steps: Forward evaluation window duration.
            seed: Random seed for reproducibility.

        Returns:
            Tuple of (features_dict, best_plan_name, all_delays_dict).
        """
        if isinstance(preset_or_rates, str):
            gen = TrafficGenerator(preset=preset_or_rates, seed=seed)
        else:
            gen = TrafficGenerator(rates=preset_or_rates, seed=seed)

        # Warmup under standard baseline P4
        signal = TrafficSignal(initial_plan="P4")
        sim = IntersectionSimulation(signal=signal, generator=gen, seed=seed)

        for _ in range(warmup_steps):
            sim.step(dt=1.0)

        # Extract features at decision boundary
        features = extract_features(sim)

        # Run forward plan evaluation
        best_plan, _, all_delays = self.optimize(sim=sim, horizon_steps=horizon_steps, dt=1.0)

        return features, best_plan, all_delays
