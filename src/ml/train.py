import sys
from pathlib import Path

# Ensure repository root is in sys.path regardless of execution working directory
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import json
from typing import Dict, Any, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from src.features.feature_engineering import (
    FEATURE_NAMES,
    ALL_FEATURE_NAMES,
    TrafficFeatureTransformer,
)


MODEL_DIR = Path("models")
RESULTS_DIR = Path("results/metrics")


def load_datasets(
    train_path: Path = Path("data/processed/train.csv"),
    val_path: Path = Path("data/processed/val.csv"),
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """Load train and validation datasets from CSV.

    Args:
        train_path: Path to train.csv.
        val_path: Path to val.csv.

    Returns:
        Tuple of (X_train, y_train, X_val, y_val).
    """
    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError(f"Dataset files not found at {train_path} or {val_path}.")

    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)

    feature_cols = list(FEATURE_NAMES)
    X_train = train_df[feature_cols]
    y_train = train_df["target_plan"]

    X_val = val_df[feature_cols]
    y_val = val_df["target_plan"]

    return X_train, y_train, X_val, y_val


def train_model(
    model_choice: str = "auto",
    rf_n_estimators: int = 400,
    rf_max_depth: int = 5,
    rf_min_samples_leaf: int = 6,
    rf_min_samples_split: int = 10,
    random_state: int = 42,
    model_output_path: Path = MODEL_DIR / "random_forest.pkl",
    metrics_output_path: Path = RESULTS_DIR / "training_metrics.json",
) -> Tuple[Pipeline, Dict[str, Any]]:
    """Train regularized model pipeline with engineered features, evaluate on validation set, and save artifacts.

    Performs 5-fold Stratified Cross-Validation on training data comparing Random Forest
    and HistGradientBoosting, selects the highest performing champion model, and serializes artifacts.

    Args:
        model_choice: "auto" (select best CV model), "rf", or "hgb".
        rf_n_estimators: Number of trees in the Random Forest.
        rf_max_depth: Maximum tree depth for regularization (prevents overfitting).
        rf_min_samples_leaf: Minimum samples at each leaf node.
        rf_min_samples_split: Minimum samples required to split an internal node.
        random_state: Random seed for reproducibility.
        model_output_path: Destination path for saved model .pkl.
        metrics_output_path: Destination path for evaluation metrics JSON.

    Returns:
        Tuple of (trained_pipeline, metrics_dict).
    """
    X_train, y_train, X_val, y_val = load_datasets()
    print(f"Loaded {len(X_train)} training samples and {len(X_val)} validation samples.")
    print(f"Features: 22 canonical + 22 engineered = {len(ALL_FEATURE_NAMES)} total features.")

    # 1. Construct candidate pipelines
    rf_pipeline = Pipeline([
        ("features", TrafficFeatureTransformer()),
        ("classifier", RandomForestClassifier(
            n_estimators=rf_n_estimators,
            max_depth=rf_max_depth,
            min_samples_split=rf_min_samples_split,
            min_samples_leaf=rf_min_samples_leaf,
            max_features="sqrt",
            class_weight="balanced",
            random_state=random_state,
            n_jobs=-1,
        )),
    ])

    hgb_pipeline = Pipeline([
        ("features", TrafficFeatureTransformer()),
        ("classifier", HistGradientBoostingClassifier(
            max_iter=300,
            max_depth=5,
            learning_rate=0.08,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=random_state,
        )),
    ])

    # 2. 5-Fold Stratified Cross-Validation
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
    print("\nEvaluating 5-Fold Stratified Cross-Validation (Macro F1)...")

    rf_cv_scores = cross_val_score(rf_pipeline, X_train, y_train, cv=cv, scoring="f1_macro")
    print(f"  Random Forest:        {rf_cv_scores.mean():.4f} ± {rf_cv_scores.std():.4f}")

    hgb_cv_scores = cross_val_score(hgb_pipeline, X_train, y_train, cv=cv, scoring="f1_macro")
    print(f"  HistGradientBoosting: {hgb_cv_scores.mean():.4f} ± {hgb_cv_scores.std():.4f}")

    # 3. Model selection
    if model_choice == "rf":
        champion_pipeline = rf_pipeline
        champion_name = "RandomForest"
    elif model_choice == "hgb":
        champion_pipeline = hgb_pipeline
        champion_name = "HistGradientBoosting"
    else:  # "auto"
        if hgb_cv_scores.mean() > rf_cv_scores.mean():
            champion_pipeline = hgb_pipeline
            champion_name = "HistGradientBoosting"
        else:
            champion_pipeline = rf_pipeline
            champion_name = "RandomForest"

    print(f"\nChampion Model Selected: {champion_name}")

    # 4. Train champion model on full training set
    champion_pipeline.fit(X_train, y_train)

    # 5. Evaluate on train and validation sets
    y_train_pred = champion_pipeline.predict(X_train)
    y_val_pred = champion_pipeline.predict(X_val)

    train_acc = accuracy_score(y_train, y_train_pred)
    val_acc = accuracy_score(y_val, y_val_pred)
    val_f1 = f1_score(y_val, y_val_pred, average="macro", zero_division=0)
    conf_mat = confusion_matrix(y_val, y_val_pred, labels=champion_pipeline.classes_).tolist()
    report = classification_report(y_val, y_val_pred, output_dict=True, zero_division=0)

    # Traffic-aware plan distance metrics (evaluates adjacent plan correctness)
    y_val_num = np.array([int(p[1:]) for p in y_val])
    y_val_pred_num = np.array([int(p[1:]) for p in y_val_pred])
    plan_diffs = np.abs(y_val_num - y_val_pred_num)
    val_within_1_plan_acc = float(np.mean(plan_diffs <= 1))
    val_mean_plan_error = float(np.mean(plan_diffs))

    # 6. Extract Feature Importances across all 44 features
    clf = champion_pipeline.named_steps["classifier"]
    if hasattr(clf, "feature_importances_"):
        raw_importances = clf.feature_importances_
    else:
        # Permutation importance on transformed validation features for GBDT
        transformer = champion_pipeline.named_steps["features"]
        X_val_trans = transformer.transform(X_val)
        perm = permutation_importance(
            clf, X_val_trans, y_val, n_repeats=5, random_state=random_state, scoring="f1_macro"
        )
        raw_importances = np.maximum(0.0, perm.importances_mean)
        if raw_importances.sum() > 0:
            raw_importances = raw_importances / raw_importances.sum()

    feature_importances = {
        col: round(float(imp), 4)
        for col, imp in sorted(
            zip(ALL_FEATURE_NAMES, raw_importances),
            key=lambda x: x[1],
            reverse=True,
        )
    }

    metrics = {
        "model_type": champion_name,
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "rf_cv_macro_f1_mean": round(float(rf_cv_scores.mean()), 4),
        "rf_cv_macro_f1_std": round(float(rf_cv_scores.std()), 4),
        "hgb_cv_macro_f1_mean": round(float(hgb_cv_scores.mean()), 4),
        "hgb_cv_macro_f1_std": round(float(hgb_cv_scores.std()), 4),
        "train_accuracy": round(float(train_acc), 4),
        "val_accuracy": round(float(val_acc), 4),
        "val_within_1_plan_accuracy": round(val_within_1_plan_acc, 4),
        "val_mean_plan_error": round(val_mean_plan_error, 4),
        "val_macro_f1": round(float(val_f1), 4),
        "classes": list(champion_pipeline.classes_),
        "confusion_matrix": conf_mat,
        "feature_importances": feature_importances,
        "classification_report": report,
    }

    # 7. Save pipeline model artifact
    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(champion_pipeline, model_output_path)
    # Also save with explicit champion name
    alt_model_path = model_output_path.parent / f"{champion_name.lower()}.pkl"
    joblib.dump(champion_pipeline, alt_model_path)
    print(f"Model saved -> {model_output_path}")

    # 8. Save metrics JSON
    metrics_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved -> {metrics_output_path}")

    print("\n--- Model Validation Results ---")
    print(f"Model Type:     {champion_name}")
    print(f"Train Accuracy: {train_acc:.2%}")
    print(f"Val Accuracy:   {val_acc:.2%}")
    print(f"Val Macro F1:   {val_f1:.4f}")
    print(f"Train-Val Gap:  {abs(train_acc - val_acc):.2%}")
    print("\nTop 7 Most Important Features:")
    for feat, imp in list(feature_importances.items())[:7]:
        print(f"  {feat:25s}: {imp:.4f}")

    return champion_pipeline, metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train traffic signal ML model with regularized CV.")
    parser.add_argument("--model", type=str, default="auto", choices=["auto", "rf", "hgb"])
    parser.add_argument("--n_estimators", type=int, default=400)
    parser.add_argument("--max_depth", type=int, default=5)
    parser.add_argument("--min_samples_leaf", type=int, default=6)
    parser.add_argument("--min_samples_split", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train_model(
        model_choice=args.model,
        rf_n_estimators=args.n_estimators,
        rf_max_depth=args.max_depth,
        rf_min_samples_leaf=args.min_samples_leaf,
        rf_min_samples_split=args.min_samples_split,
        random_state=args.seed,
    )
