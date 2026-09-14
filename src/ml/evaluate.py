import sys
from pathlib import Path

# Ensure repository root is in sys.path regardless of execution working directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import json
from typing import Dict, List, Any, Optional
import pandas as pd
from src.simulator.intersection import IntersectionSimulation
from src.simulator.signal import TrafficSignal
from src.simulator.traffic_generator import TrafficGenerator, SCENARIO_PRESETS
from src.ml.predict import SignalTimingPredictor, AdaptiveMLController

BENCHMARK_OUTPUT_PATH = Path("results/metrics/evaluation_benchmark.json")


def run_scenario_trial(
    rates: Dict[str, float],
    seed: int,
    duration_seconds: int = 280,  # ~4 full cycles
    controller: Optional[AdaptiveMLController] = None,
) -> Dict[str, Dict[str, Any]]:
    """Run an identical traffic scenario under both Fixed Baseline and ML Adaptive controllers.

    Args:
        rates: Dict of approach arrival rates (N, S, E, W).
        seed: Random seed ensuring identical vehicle arrivals.
        duration_seconds: Total simulation duration in seconds.
        controller: Optional pre-loaded AdaptiveMLController instance for high throughput.

    Returns:
        Dictionary with keys 'fixed' and 'ml', each containing simulation summary metrics.
    """
    # 1. Fixed-time baseline (P4: 30s NS, 30s EW)
    fixed_gen = TrafficGenerator(rates=rates, seed=seed)
    fixed_signal = TrafficSignal(initial_plan="P4")
    fixed_sim = IntersectionSimulation(signal=fixed_signal, generator=fixed_gen, seed=seed)

    for _ in range(duration_seconds):
        fixed_sim.step(dt=1.0)
    fixed_summary = fixed_sim.get_summary()

    # 2. Adaptive ML Controller
    ml_gen = TrafficGenerator(rates=rates, seed=seed)
    ml_signal = TrafficSignal(initial_plan="P4")
    ml_sim = IntersectionSimulation(signal=ml_signal, generator=ml_gen, seed=seed)
    if controller is None:
        ctrl = AdaptiveMLController()
    else:
        ctrl = controller
        ctrl.decision_history = []

    # Initial decision at t=0
    ctrl.update(ml_sim, force_update=True)

    for _ in range(duration_seconds):
        ml_sim.step(dt=1.0)
        ctrl.update(ml_sim)

    ml_summary = ml_sim.get_summary()
    ml_summary["plans_selected"] = [d["selected_plan"] for d in ctrl.decision_history]

    return {"fixed": fixed_summary, "ml": ml_summary}


def evaluate_benchmark(
    test_csv_path: Path = Path("data/processed/test.csv"),
    num_eval_scenarios: int = 25,
    duration_seconds: int = 280,
    output_path: Path = BENCHMARK_OUTPUT_PATH,
) -> Dict[str, Any]:
    """Evaluate Fixed Baseline vs ML Adaptive controller across test scenarios.

    Args:
        test_csv_path: Path to held-out test scenarios CSV.
        num_eval_scenarios: Number of test scenarios to evaluate.
        duration_seconds: Duration of each scenario evaluation run in seconds.
        output_path: JSON destination path.

    Returns:
        Comprehensive comparison metrics dictionary.
    """
    if test_csv_path.exists():
        test_df = pd.read_csv(test_csv_path)
        unique_scenarios = test_df.drop_duplicates(subset=["scenario_id"])
        eval_records = unique_scenarios.head(num_eval_scenarios).to_dict(orient="records")
    else:
        # Fallback to standard presets
        eval_records = [{"scenario_id": i, **preset} for i, preset in enumerate(SCENARIO_PRESETS.values())]

    print(f"Running comparative benchmark across {len(eval_records)} unseen test scenarios...")

    # Reuse single shared controller instance across all scenarios (avoids reloading model from disk)
    shared_controller = AdaptiveMLController()

    fixed_delays: List[float] = []
    ml_delays: List[float] = []
    fixed_exited_delays: List[float] = []
    ml_exited_delays: List[float] = []
    fixed_queues: List[float] = []
    ml_queues: List[float] = []
    fixed_throughputs: List[float] = []
    ml_throughputs: List[float] = []

    scenario_details: List[Dict[str, Any]] = []

    for i, rec in enumerate(eval_records):
        seed = int(rec.get("scenario_id", i + 1000))
        # Reconstruct arrival rates from test record (rates are already in veh/min)
        rates = {
            "N": float(rec.get("true_N_rate", rec.get("N_arrival", rec.get("N", 15.0)))),
            "S": float(rec.get("true_S_rate", rec.get("S_arrival", rec.get("S", 15.0)))),
            "E": float(rec.get("true_E_rate", rec.get("E_arrival", rec.get("E", 15.0)))),
            "W": float(rec.get("true_W_rate", rec.get("W_arrival", rec.get("W", 15.0)))),
        }

        trial = run_scenario_trial(
            rates=rates,
            seed=seed,
            duration_seconds=duration_seconds,
            controller=shared_controller,
        )
        f_res = trial["fixed"]
        m_res = trial["ml"]

        # Primary: comprehensive delay (penalizes trapped queues, eliminates survivorship bias)
        f_comp_delay = f_res.get("comprehensive_delay", f_res["average_delay"])
        m_comp_delay = m_res.get("comprehensive_delay", m_res["average_delay"])
        fixed_delays.append(f_comp_delay)
        ml_delays.append(m_comp_delay)

        # Secondary: exited-only trip delay
        fixed_exited_delays.append(f_res["average_delay"])
        ml_exited_delays.append(m_res["average_delay"])

        fixed_queues.append(f_res["average_queue"])
        ml_queues.append(m_res["average_queue"])
        fixed_throughputs.append(f_res["throughput_vph"])
        ml_throughputs.append(m_res["throughput_vph"])

        scenario_details.append({
            "scenario_id": seed,
            "rates": rates,
            "fixed_comprehensive_delay": f_comp_delay,
            "ml_comprehensive_delay": m_comp_delay,
            "fixed_exited_delay": f_res["average_delay"],
            "ml_exited_delay": m_res["average_delay"],
            "delay_improvement_pct": round(
                ((f_comp_delay - m_comp_delay) / max(0.1, f_comp_delay)) * 100.0,
                2,
            ),
            "plans_selected": m_res.get("plans_selected", []),
        })

    avg_f_delay = round(sum(fixed_delays) / len(fixed_delays), 2)
    avg_m_delay = round(sum(ml_delays) / len(ml_delays), 2)
    delay_improvement_pct = round(((avg_f_delay - avg_m_delay) / max(0.1, avg_f_delay)) * 100.0, 2)

    avg_f_exited_delay = round(sum(fixed_exited_delays) / len(fixed_exited_delays), 2)
    avg_m_exited_delay = round(sum(ml_exited_delays) / len(ml_exited_delays), 2)

    avg_f_queue = round(sum(fixed_queues) / len(fixed_queues), 2)
    avg_m_queue = round(sum(ml_queues) / len(ml_queues), 2)
    queue_improvement_pct = round(((avg_f_queue - avg_m_queue) / max(0.1, avg_f_queue)) * 100.0, 2)

    avg_f_tp = round(sum(fixed_throughputs) / len(fixed_throughputs), 1)
    avg_m_tp = round(sum(ml_throughputs) / len(ml_throughputs), 1)

    results = {
        "scenarios_evaluated": len(eval_records),
        "fixed_baseline": {
            "comprehensive_delay_s": avg_f_delay,
            "exited_delay_s": avg_f_exited_delay,
            "average_queue": avg_f_queue,
            "average_throughput_vph": avg_f_tp,
        },
        "ml_adaptive": {
            "comprehensive_delay_s": avg_m_delay,
            "exited_delay_s": avg_m_exited_delay,
            "average_queue": avg_m_queue,
            "average_throughput_vph": avg_m_tp,
        },
        "comparison": {
            "delay_reduction_pct": delay_improvement_pct,
            "queue_reduction_pct": queue_improvement_pct,
            "throughput_gain_vph": round(avg_m_tp - avg_f_tp, 1),
            "asymmetric_delay_reduction_pct": round(
                (
                    (
                        sum(
                            s["fixed_comprehensive_delay"]
                            for s in scenario_details
                            if abs((s["rates"]["N"] + s["rates"]["S"]) - (s["rates"]["E"] + s["rates"]["W"])) >= 8.0
                        )
                        / max(
                            1,
                            len([
                                s for s in scenario_details
                                if abs((s["rates"]["N"] + s["rates"]["S"]) - (s["rates"]["E"] + s["rates"]["W"])) >= 8.0
                            ]),
                        )
                        - sum(
                            s["ml_comprehensive_delay"]
                            for s in scenario_details
                            if abs((s["rates"]["N"] + s["rates"]["S"]) - (s["rates"]["E"] + s["rates"]["W"])) >= 8.0
                        )
                        / max(
                            1,
                            len([
                                s for s in scenario_details
                                if abs((s["rates"]["N"] + s["rates"]["S"]) - (s["rates"]["E"] + s["rates"]["W"])) >= 8.0
                            ]),
                        )
                    )
                    / max(
                        0.1,
                        sum(
                            s["fixed_comprehensive_delay"]
                            for s in scenario_details
                            if abs((s["rates"]["N"] + s["rates"]["S"]) - (s["rates"]["E"] + s["rates"]["W"])) >= 8.0
                        )
                        / max(
                            1,
                            len([
                                s for s in scenario_details
                                if abs((s["rates"]["N"] + s["rates"]["S"]) - (s["rates"]["E"] + s["rates"]["W"])) >= 8.0
                            ]),
                        ),
                    )
                )
                * 100.0,
                2,
            ) if any(abs((s["rates"]["N"] + s["rates"]["S"]) - (s["rates"]["E"] + s["rates"]["W"])) >= 8.0 for s in scenario_details) else delay_improvement_pct,
        },
        "scenario_details": scenario_details,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark results saved -> {output_path}")

    # Print summary table
    print("\n=======================================================")
    print("      AdaptiveFlow Benchmark Results (Fixed vs ML)     ")
    print("=======================================================")
    print(f"{'Metric':<25s} | {'Fixed (P4)':<12s} | {'ML Adaptive':<12s} | {'Improvement':<12s}")
    print("-------------------------------------------------------")
    print(f"{'Comprehensive Delay':<25s} | {avg_f_delay:>9.2f} s | {avg_m_delay:>9.2f} s | {delay_improvement_pct:>+9.2f} %")
    print(f"{'Exited-Only Delay':<25s} | {avg_f_exited_delay:>9.2f} s | {avg_m_exited_delay:>9.2f} s | {round(((avg_f_exited_delay-avg_m_exited_delay)/max(0.1, avg_f_exited_delay))*100, 2):>+9.2f} %")
    print(f"{'Average Queue Length':<25s} | {avg_f_queue:>10.2f} | {avg_m_queue:>10.2f} | {queue_improvement_pct:>+9.2f} %")
    print(f"{'Throughput (vph)':<25s} | {avg_f_tp:>10.1f} | {avg_m_tp:>10.1f} | {avg_m_tp - avg_f_tp:>+9.1f}")
    print("=======================================================\n")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Fixed Baseline vs ML Adaptive Controller.")
    parser.add_argument("--scenarios", type=int, default=25, help="Number of test scenarios to evaluate.")
    parser.add_argument("--duration", type=int, default=280, help="Simulation duration per scenario.")
    args = parser.parse_args()

    evaluate_benchmark(num_eval_scenarios=args.scenarios, duration_seconds=args.duration)
