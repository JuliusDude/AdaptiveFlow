import sys
from pathlib import Path

# Ensure repository root is in sys.path regardless of execution working directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any
import pandas as pd
from src.features.feature_engineering import FEATURE_NAMES, validate_features, extract_features
from src.optimization.timing_optimizer import TimingOptimizer


DATA_DIR = Path("data/processed")


def sample_scenario_rates(rng: random.Random) -> Tuple[str, Dict[str, float]]:
    """Sample diverse traffic demand patterns with balanced coverage across P1 through P7."""
    archetype = rng.choice([
        "balanced",
        "balanced",
        "slight_ns",
        "slight_ns",
        "slight_ew",
        "slight_ew",
        "moderate_ns",
        "moderate_ns",
        "moderate_ew",
        "moderate_ew",
        "heavy_ns",
        "heavy_ew",
        "random_mix",
    ])

    if archetype == "balanced":
        # Target: P4 (30s NS / 30s EW)
        base = rng.uniform(14.0, 22.0)
        rates = {app: round(base + rng.uniform(-1.5, 1.5), 1) for app in ("N", "S", "E", "W")}

    elif archetype == "slight_ns":
        # Target: P5 (35s NS / 25s EW) - Demand ratio ~1.3-1.45
        rates = {
            "N": round(rng.uniform(19.0, 25.0), 1),
            "S": round(rng.uniform(17.0, 23.0), 1),
            "E": round(rng.uniform(13.0, 17.0), 1),
            "W": round(rng.uniform(13.0, 17.0), 1),
        }

    elif archetype == "slight_ew":
        # Target: P3 (25s NS / 35s EW) - Demand ratio ~1.3-1.45 favoring EW
        rates = {
            "N": round(rng.uniform(13.0, 17.0), 1),
            "S": round(rng.uniform(13.0, 17.0), 1),
            "E": round(rng.uniform(19.0, 25.0), 1),
            "W": round(rng.uniform(17.0, 23.0), 1),
        }

    elif archetype == "moderate_ns":
        # Target: P6 (40s NS / 20s EW) - Demand ratio ~1.8-2.2
        rates = {
            "N": round(rng.uniform(25.0, 32.0), 1),
            "S": round(rng.uniform(19.0, 26.0), 1),
            "E": round(rng.uniform(9.0, 14.0), 1),
            "W": round(rng.uniform(9.0, 14.0), 1),
        }

    elif archetype == "moderate_ew":
        # Target: P2 (20s NS / 40s EW) - Demand ratio ~1.8-2.2 favoring EW
        rates = {
            "N": round(rng.uniform(9.0, 14.0), 1),
            "S": round(rng.uniform(9.0, 14.0), 1),
            "E": round(rng.uniform(25.0, 32.0), 1),
            "W": round(rng.uniform(19.0, 26.0), 1),
        }

    elif archetype == "heavy_ns":
        # Target: P7 (45s NS / 15s EW) - Demand ratio >= 2.8
        rates = {
            "N": round(rng.uniform(34.0, 44.0), 1),
            "S": round(rng.uniform(24.0, 34.0), 1),
            "E": round(rng.uniform(5.0, 9.0), 1),
            "W": round(rng.uniform(5.0, 9.0), 1),
        }

    elif archetype == "heavy_ew":
        # Target: P1 (15s NS / 45s EW) - Demand ratio >= 2.8 favoring EW
        rates = {
            "N": round(rng.uniform(5.0, 9.0), 1),
            "S": round(rng.uniform(5.0, 9.0), 1),
            "E": round(rng.uniform(34.0, 44.0), 1),
            "W": round(rng.uniform(24.0, 34.0), 1),
        }

    else:  # random_mix
        rates = {
            app: round(rng.uniform(7.0, 32.0), 1)
            for app in ("N", "S", "E", "W")
        }

    return archetype, rates


def _process_single_scenario(
    args: Tuple[int, str, Dict[str, float], int, int, int]
) -> List[Dict[str, Any]]:
    """Worker task to simulate multiple cycles and extract multi-snapshot ground truth."""
    from src.simulator.traffic_generator import TrafficGenerator
    from src.simulator.signal import TrafficSignal
    from src.simulator.intersection import IntersectionSimulation

    scenario_id, archetype, rates, warmup_steps, horizon_steps, snapshots_per_scenario = args

    generator = TrafficGenerator(rates=rates, seed=scenario_id)
    signal = TrafficSignal(initial_plan="P4")
    sim = IntersectionSimulation(signal=signal, generator=generator, seed=scenario_id)
    optimizer = TimingOptimizer()

    rows: List[Dict[str, Any]] = []

    for cycle_idx in range(1, snapshots_per_scenario + 1):
        # Step simulation for a full cycle (70s)
        for _ in range(70):
            sim.step(dt=1.0)

        # Extract features at cycle boundary (t = 70 * cycle_idx)
        features = extract_features(sim)
        validate_features(features)

        # Forward optimize optimal timing plan from current active state
        best_plan, best_delay, all_delays = optimizer.optimize(
            sim=sim,
            horizon_steps=horizon_steps,
            dt=1.0,
        )

        row = dict(features)
        row["scenario_id"] = scenario_id
        row["cycle_idx"] = cycle_idx
        row["archetype"] = archetype
        row["true_N_rate"] = rates["N"]
        row["true_S_rate"] = rates["S"]
        row["true_E_rate"] = rates["E"]
        row["true_W_rate"] = rates["W"]
        row["target_plan"] = best_plan
        row["best_delay"] = all_delays[best_plan]
        rows.append(row)

        # Actuate plan for the subsequent cycle
        signal.apply_plan_now(best_plan)

    return rows


def generate_dataset(
    num_scenarios: int = 500,
    warmup_steps: int = 70,
    horizon_steps: int = 140,
    snapshots_per_scenario: int = 3,
    seed: int = 42,
    output_dir: Path = DATA_DIR,
    max_workers: int = 4,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate labeled dataset using parallel ground-truth forward simulation with multi-snapshot augmentation.

    Args:
        num_scenarios: Total number of traffic scenarios to generate (default 500).
        warmup_steps: Simulation warmup steps before feature capture (70s = 1 cycle).
        horizon_steps: Forward evaluation window for candidate plans (140s = 2 full cycles).
        snapshots_per_scenario: Number of consecutive cycle snapshots per scenario (default 3 = 1,500 samples).
        seed: Master random seed.
        output_dir: Directory where train.csv, val.csv, and test.csv will be saved.
        max_workers: Number of parallel worker processes.

    Returns:
        Tuple of (train_df, val_df, test_df).
    """
    from sklearn.model_selection import train_test_split

    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks: List[Tuple[int, str, Dict[str, float], int, int, int]] = []
    for scenario_id in range(1, num_scenarios + 1):
        archetype, rates = sample_scenario_rates(rng)
        tasks.append((scenario_id, archetype, rates, warmup_steps, horizon_steps, snapshots_per_scenario))

    total_samples_est = num_scenarios * snapshots_per_scenario
    print(f"Generating {num_scenarios} scenarios ({total_samples_est} multi-snapshot samples) with {max_workers} workers...")

    results: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_single_scenario, t): t[0] for t in tasks}
        for future in as_completed(futures):
            res_list = future.result()
            results.extend(res_list)

    df = pd.DataFrame(results)

    # Scenario-level stratified split (prevents intra-scenario data leakage across cycles)
    unique_scenarios = df[["scenario_id", "archetype"]].drop_duplicates()
    can_strat_1 = unique_scenarios["archetype"].value_counts().min() >= 2
    strat_1 = unique_scenarios["archetype"] if can_strat_1 else None
    train_scenarios, test_val_scenarios = train_test_split(
        unique_scenarios, test_size=0.30, stratify=strat_1, random_state=seed
    )

    can_strat_2 = test_val_scenarios["archetype"].value_counts().min() >= 2
    strat_2 = test_val_scenarios["archetype"] if can_strat_2 else None
    val_scenarios, test_scenarios = train_test_split(
        test_val_scenarios, test_size=0.50, stratify=strat_2, random_state=seed
    )

    train_ids = set(train_scenarios["scenario_id"])
    val_ids = set(val_scenarios["scenario_id"])
    test_ids = set(test_scenarios["scenario_id"])

    train_df = df[df["scenario_id"].isin(train_ids)].sort_values(by=["scenario_id", "cycle_idx"]).reset_index(drop=True)
    val_df = df[df["scenario_id"].isin(val_ids)].sort_values(by=["scenario_id", "cycle_idx"]).reset_index(drop=True)
    test_df = df[df["scenario_id"].isin(test_ids)].sort_values(by=["scenario_id", "cycle_idx"]).reset_index(drop=True)

    train_df.to_csv(output_dir / "train.csv", index=False)
    val_df.to_csv(output_dir / "val.csv", index=False)
    test_df.to_csv(output_dir / "test.csv", index=False)

    print(f"Dataset generated successfully:")
    print(f"  Train: {len(train_df)} samples -> {output_dir / 'train.csv'}")
    print(f"  Val:   {len(val_df)} samples -> {output_dir / 'val.csv'}")
    print(f"  Test:  {len(test_df)} samples -> {output_dir / 'test.csv'}")
    print(f"Class distribution in train:\n{train_df['target_plan'].value_counts().sort_index()}")

    return train_df, val_df, test_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AdaptiveFlow training dataset.")
    parser.add_argument("--num_scenarios", type=int, default=500, help="Number of scenarios.")
    parser.add_argument("--horizon", type=int, default=140, help="Forward horizon steps.")
    parser.add_argument("--snapshots", type=int, default=3, help="Snapshots per scenario.")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 2), help="Parallel workers.")
    args = parser.parse_args()

    generate_dataset(
        num_scenarios=args.num_scenarios,
        horizon_steps=args.horizon,
        snapshots_per_scenario=args.snapshots,
        max_workers=args.workers,
    )

