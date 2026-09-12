"""Model training pipeline for supervised Random Forest signal timing classifier."""

import argparse
import json
from pathlib import Path
from typing import Dict, Any, Tuple
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from src.features.feature_engineering import FEATURE_NAMES


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
    n_estimators: int = 100,
    max_depth: int = 12,
    random_state: int = 42,
    model_output_path: Path = MODEL_DIR / "random_forest.pkl",
    metrics_output_path: Path = RESULTS_DIR / "training_metrics.json",
) -> Tuple[RandomForestClassifier, Dict[str, Any]]:
    """Train RandomForestClassifier, evaluate on validation set, and save artifacts.

    Args:
        n_estimators: Number of trees in the forest.
        max_depth: Maximum tree depth.
        random_state: Random state for reproducibility.
        model_output_path: Destination path for saved model .pkl.
        metrics_output_path: Destination path for evaluation metrics JSON.

    Returns:
        Tuple of (trained_model, metrics_dict).
    """
    X_train, y_train, X_val, y_val = load_datasets()

    print(f"Training Random Forest on {len(X_train)} samples with 22 features...")
    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_split=4,
        random_state=random_state,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    # Predictions
    y_train_pred = clf.predict(X_train)
    y_val_pred = clf.predict(X_val)

    train_acc = accuracy_score(y_train, y_train_pred)
    val_acc = accuracy_score(y_val, y_val_pred)
    val_f1 = f1_score(y_val, y_val_pred, average="macro", zero_division=0)
    conf_mat = confusion_matrix(y_val, y_val_pred, labels=clf.classes_).tolist()
    report = classification_report(y_val, y_val_pred, output_dict=True, zero_division=0)

    # Feature importances
    feature_importances = {
        col: round(float(imp), 4)
        for col, imp in sorted(
            zip(FEATURE_NAMES, clf.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )
    }

    metrics = {
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "train_accuracy": round(float(train_acc), 4),
        "val_accuracy": round(float(val_acc), 4),
        "val_macro_f1": round(float(val_f1), 4),
        "classes": list(clf.classes_),
        "confusion_matrix": conf_mat,
        "feature_importances": feature_importances,
        "classification_report": report,
    }

    # Save model artifact
    model_output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, model_output_path)
    print(f"Model saved -> {model_output_path}")

    # Save metrics JSON
    metrics_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved -> {metrics_output_path}")

    print("\n--- Model Validation Results ---")
    print(f"Train Accuracy: {train_acc:.2%}")
    print(f"Val Accuracy:   {val_acc:.2%}")
    print(f"Val Macro F1:   {val_f1:.4f}")
    print("\nTop 5 Most Important Features:")
    for feat, imp in list(feature_importances.items())[:5]:
        print(f"  {feat:20s}: {imp:.4f}")

    return clf, metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Random Forest traffic signal model.")
    parser.add_argument("--n_estimators", type=int, default=100)
    parser.add_argument("--max_depth", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    train_model(n_estimators=args.n_estimators, max_depth=args.max_depth, random_state=args.seed)
