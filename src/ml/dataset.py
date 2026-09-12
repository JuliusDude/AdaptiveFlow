"""Dataset generation pipeline for supervised traffic signal control."""

import argparse
import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Any
import pandas as pd
from src.features.feature_engineering import FEATURE_NAMES, validate_features
from src.optimization.timing_optimizer import TimingOptimizer


DATA_DIR = Path("data/processed")


def sample_scenario_rates(rng: random.Random) -> Dict[str, float]:
    """Sample diverse traffic demand patterns across 8 representative archetypes."""
    archetype = rng.choice([
        "balanced",
        "north_heavy",
        "south_heavy",
        "east_heavy",
        "west_heavy",
        "opposing_ns",
        "opposing_ew",
        "random_mix",
    ])

    if archetype == "balanced":
        base = rng.uniform(10.0, 25.0)
        return {app: round(base + rng.uniform(-3.0, 3.0), 1) for app in ("N", "S", "E", "W")}

    elif archetype == "north_heavy":
        return {
            "N": round(rng.uniform(28.0, 45.0), 1),
            "S": round(rng.uniform(10.0, 22.0), 1),
            "E": round(rng.uniform(5.0, 14.0), 1),
            "W": round(rng.uniform(5.0, 14.0), 1),
        }

    elif archetype == "south_heavy":
        return {
            "N": round(rng.uniform(10.0, 22.0), 1),
            "S": round(rng.uniform(28.0, 45.0), 1),
            "E": round(rng.uniform(5.0, 14.0), 1),
            "W": round(rng.uniform(5.0, 14.0), 1),
        }

    elif archetype == "east_heavy":
        return {
            "N": round(rng.uniform(5.0, 14.0), 1),
            "S": round(rng.uniform(5.0, 14.0), 1),
            "E": round(rng.uniform(28.0, 45.0), 1),
            "W": round(rng.uniform(10.0, 22.0), 1),
        }

    elif archetype == "west_heavy":
        return {
            "N": round(rng.uniform(5.0, 14.0), 1),
            "S": round(rng.uniform(5.0, 14.0), 1),
            "E": round(rng.uniform(10.0, 22.0), 1),
            "W": round(rng.uniform(28.0, 45.0), 1),
        }

    elif archetype == "opposing_ns":
        return {
            "N": round(rng.uniform(25.0, 40.0), 1),
            "S": round(rng.uniform(25.0, 40.0), 1),
            "E": round(rng.uniform(5.0, 12.0), 1),
            "W": round(rng.uniform(5.0, 12.0), 1),
        }

    elif archetype == "opposing_ew":
        return {
            "N": round(rng.uniform(5.0, 12.0), 1),
            "S": round(rng.uniform(5.0, 12.0), 1),
            "E": round(rng.uniform(25.0, 40.0), 1),
            "W": round(rng.uniform(25.0, 40.0), 1),
        }

    else:  # random_mix
        return {
            app: round(rng.uniform(5.0, 38.0), 1)
            for app in ("N", "S", "E", "W")
        }


def _process_single_scenario(args: Tuple[int, Dict[str, float], int, int]) -> Dict[str, Any]:
    """Worker task to run warmup and ground-truth optimization for one scenario."""
    scenario_id, rates, warmup_steps, horizon_steps = args
    optimizer = TimingOptimizer()

    features, best_plan, all_delays = optimizer.evaluate_scenario(
        preset_or_rates=rates,
        warmup_steps=warmup_steps,
        horizon_steps=horizon_steps,
        seed=scenario_id,
    )

    validate_features(features)

    row = dict(features)
    row["scenario_id"] = scenario_id
    row["target_plan"] = best_plan
    row["best_delay"] = all_delays[best_plan]
    return row


def generate_dataset(
    num_scenarios: int = 500,
    warmup_steps: int = 35,
    horizon_steps: int = 70,
    seed: int = 42,
    output_dir: Path = DATA_DIR,
    max_workers: int = 8,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate labeled dataset using parallel ground-truth forward simulation.

    Args:
        num_scenarios: Total number of traffic scenarios to generate.
        warmup_steps: Simulation warmup steps before feature capture.
        horizon_steps: Forward evaluation window for candidate timing plans.
        seed: Master random seed.
        output_dir: Directory where train.csv, val.csv, and test.csv will be saved.
        max_workers: Number of parallel worker processes.

    Returns:
        Tuple of (train_df, val_df, test_df).
    """
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    tasks: List[Tuple[int, Dict[str, float], int, int]] = []
    for scenario_id in range(1, num_scenarios + 1):
        rates = sample_scenario_rates(rng)
        tasks.append((scenario_id, rates, warmup_steps, horizon_steps))

    print(f"Generating {num_scenarios} scenarios with {max_workers} parallel workers...")

    results: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_single_scenario, t): t[0] for t in tasks}
        for future in as_completed(futures):
            res = future.result()
            results.append(res)

    # Sort deterministically by scenario_id
    results.sort(key=lambda r: r["scenario_id"])
    df = pd.DataFrame(results)

    # Scenario-level split: 70% train, 15% val, 15% test
    n = len(df)
    train_idx = int(0.70 * n)
    val_idx = int(0.85 * n)

    train_df = df.iloc[:train_idx].copy().reset_index(drop=True)
    val_df = df.iloc[train_idx:val_idx].copy().reset_index(drop=True)
    test_df = df.iloc[val_idx:].copy().reset_index(drop=True)

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
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4), help="Parallel workers.")
    args = parser.parse_args()

    generate_dataset(num_scenarios=args.num_scenarios, max_workers=args.workers)
