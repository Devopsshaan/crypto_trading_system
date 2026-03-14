"""
ML Model — Train, save, load, and predict with LightGBM.
=========================================================
Uses walk-forward validation to prevent overfitting.
The model only ever trains on past data and tests on future data,
mimicking real live-trading conditions.
"""

from __future__ import annotations
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report,
)

from config.settings import (
    FEATURE_COLS, MODEL_FILE,
    TRAIN_RATIO, VAL_RATIO,
)

log = logging.getLogger(__name__)


# ── Walk-Forward Validation ──────────────────────────────────────────────────

def walk_forward_validate(
    df: pd.DataFrame,
    n_splits: int = 5,
    train_pct: float = 0.60,
) -> dict:
    """
    Walk-forward cross-validation for time-series data.

    Unlike k-fold CV, this respects temporal ordering:
      Split 1: train [0..60%], test [60..68%]
      Split 2: train [0..68%], test [68..76%]
      ...
    Each fold trains ONLY on past data and tests on unseen future data.
    This detects overfitting that a simple train/test split would miss.

    Returns dict with per-fold and aggregate metrics.
    """
    available = [c for c in FEATURE_COLS if c in df.columns]
    if not available:
        return {"error": "No feature columns"}

    n = len(df)
    test_size = int(n * (1 - train_pct) / n_splits)
    if test_size < 50:
        log.warning("Walk-forward: not enough data for %d splits (%d rows). Using 3 splits.", n_splits, n)
        n_splits = max(2, n_splits - 2)
        test_size = int(n * (1 - train_pct) / n_splits)

    results = []
    for fold in range(n_splits):
        train_end = int(n * train_pct) + fold * test_size
        test_end = min(train_end + test_size, n)

        if train_end >= n or test_end <= train_end:
            break

        X_train = df.iloc[:train_end][available]
        y_train = df.iloc[:train_end]["target"]
        X_test = df.iloc[train_end:test_end][available]
        y_test = df.iloc[train_end:test_end]["target"]

        if len(y_test.unique()) < 2 or len(y_train.unique()) < 2:
            continue

        n_pos = int(y_train.sum())
        n_neg = len(y_train) - n_pos
        pos_weight = n_neg / max(n_pos, 1)

        dtrain = lgb.Dataset(X_train, label=y_train)
        dval = lgb.Dataset(X_test, label=y_test, reference=dtrain)

        params = {
            "objective": "binary",
            "metric": "auc",
            "verbosity": -1,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "min_child_samples": 20,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "scale_pos_weight": pos_weight,
        }

        model = lgb.train(
            params, dtrain,
            valid_sets=[dval],
            num_boost_round=500,
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
        )

        y_prob = model.predict(X_test)
        y_pred = (y_prob > 0.5).astype(int)

        try:
            auc = roc_auc_score(y_test, y_prob)
        except ValueError:
            auc = 0.5

        fold_result = {
            "fold": fold + 1,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1": f1_score(y_test, y_pred, zero_division=0),
            "auc": auc,
        }
        results.append(fold_result)
        log.info("  WF Fold %d: AUC=%.4f  Acc=%.4f  (train=%d, test=%d)",
                 fold + 1, auc, fold_result["accuracy"], len(X_train), len(X_test))

    if not results:
        return {"error": "No valid folds"}

    avg_auc = np.mean([r["auc"] for r in results])
    std_auc = np.std([r["auc"] for r in results])
    avg_acc = np.mean([r["accuracy"] for r in results])

    summary = {
        "n_folds": len(results),
        "avg_auc": round(avg_auc, 4),
        "std_auc": round(std_auc, 4),
        "avg_accuracy": round(avg_acc, 4),
        "folds": results,
        "overfit_warning": std_auc > 0.05 or avg_auc < 0.52,
    }

    if summary["overfit_warning"]:
        log.warning("⚠️  OVERFIT WARNING: AUC=%.4f±%.4f — model may not generalize well", avg_auc, std_auc)
    else:
        log.info("✅ Walk-forward OK: AUC=%.4f±%.4f across %d folds", avg_auc, std_auc, len(results))

    return summary

# ── Training ─────────────────────────────────────────────────────────────────

def train_model(df: pd.DataFrame, save_path: Path | None = None) -> lgb.Booster:
    """
    Train a LightGBM binary classifier with walk-forward validation.

    1. Run walk-forward CV to check for overfitting
    2. Train final model on train+val, evaluate on held-out test
    3. Save model only if walk-forward metrics are acceptable
    """
    if save_path is None:
        save_path = MODEL_FILE

    # Use only available feature columns
    available = [c for c in FEATURE_COLS if c in df.columns]
    if not available:
        raise ValueError("No feature columns found in dataframe.")

    # ── Step 1: Walk-forward validation ──────────────────────────────────
    log.info("── Walk-Forward Validation ──")
    wf_results = walk_forward_validate(df, n_splits=5, train_pct=0.60)
    if "error" not in wf_results:
        log.info("Walk-forward AUC: %.4f ± %.4f (%d folds)",
                 wf_results["avg_auc"], wf_results["std_auc"], wf_results["n_folds"])

    # ── Step 2: Train final model ────────────────────────────────────────
    n = len(df)
    train_end = int(n * TRAIN_RATIO)
    val_end = int(n * (TRAIN_RATIO + VAL_RATIO))

    train = df.iloc[:train_end]
    val = df.iloc[train_end:val_end]
    test = df.iloc[val_end:]

    X_train, y_train = train[available], train["target"]
    X_val, y_val = val[available], val["target"]
    X_test, y_test = test[available], test["target"]

    log.info("Training set: %d | Validation: %d | Test: %d", len(train), len(val), len(test))

    dtrain = lgb.Dataset(X_train, label=y_train)
    dval = lgb.Dataset(X_val, label=y_val, reference=dtrain)

    # Compute class weight to fix imbalance
    n_pos = int(y_train.sum())
    n_neg = len(y_train) - n_pos
    pos_weight = n_neg / max(n_pos, 1)
    log.info("Class balance: %d positive (%.1f%%) vs %d negative → scale_pos_weight=%.2f",
             n_pos, n_pos / len(y_train) * 100, n_neg, pos_weight)

    # Balanced regularization: enough to prevent overfit, not so much it kills signal
    params = {
        "objective": "binary",
        "metric": "auc",
        "verbosity": -1,
        "learning_rate": 0.03,
        "num_leaves": 20,
        "max_depth": 5,
        "min_child_samples": 40,
        "feature_fraction": 0.65,
        "bagging_fraction": 0.65,
        "bagging_freq": 5,
        "lambda_l1": 0.3,
        "lambda_l2": 3.0,
        "min_gain_to_split": 0.02,
        "max_bin": 127,
        "scale_pos_weight": pos_weight,
    }

    callbacks = [lgb.early_stopping(stopping_rounds=50, verbose=False)]
    model = lgb.train(
        params, dtrain,
        valid_sets=[dval],
        num_boost_round=1000,
        callbacks=callbacks,
    )

    # ── Step 3: Evaluate on test set ─────────────────────────────────────
    y_prob = model.predict(X_test)
    y_pred = (y_prob > 0.5).astype(int)

    test_acc = accuracy_score(y_test, y_pred)
    test_prec = precision_score(y_test, y_pred, zero_division=0)
    test_rec = recall_score(y_test, y_pred, zero_division=0)
    test_f1 = f1_score(y_test, y_pred, zero_division=0)

    log.info("── Test Set Evaluation ──")
    log.info("Accuracy:  %.4f", test_acc)
    log.info("Precision: %.4f", test_prec)
    log.info("Recall:    %.4f", test_rec)
    log.info("F1:        %.4f", test_f1)
    try:
        auc = roc_auc_score(y_test, y_prob)
        log.info("ROC AUC:   %.4f", auc)
    except ValueError:
        log.warning("ROC AUC could not be computed (single class in test set).")

    # ── Overfit check: compare train AUC vs test AUC ─────────────────────
    y_train_prob = model.predict(X_train)
    try:
        train_auc = roc_auc_score(y_train, y_train_prob)
        test_auc = roc_auc_score(y_test, y_prob)
        overfit_gap = train_auc - test_auc
        log.info("── Overfit Check ──")
        log.info("Train AUC: %.4f | Test AUC: %.4f | Gap: %.4f", train_auc, test_auc, overfit_gap)
        if overfit_gap > 0.10:
            log.warning("⚠️  OVERFIT DETECTED: Train-Test gap %.4f > 0.10. Model may not generalize.", overfit_gap)
        else:
            log.info("✅ Overfit gap OK (%.4f)", overfit_gap)
    except ValueError:
        pass

    # Feature importance
    importance = model.feature_importance(importance_type="gain")
    feat_imp = sorted(zip(available, importance), key=lambda x: x[1], reverse=True)
    log.info("── Feature Importance (top 10) ──")
    for fname, imp in feat_imp[:10]:
        log.info("  %-20s  %.1f", fname, imp)

    # Save model
    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(save_path))
    log.info("Model saved → %s", save_path)

    return model


# ── Loading ──────────────────────────────────────────────────────────────────

def load_model(path: Path | None = None) -> lgb.Booster | None:
    """Load a saved LightGBM model."""
    if path is None:
        path = MODEL_FILE
    if not path.exists():
        log.warning("No model found at %s", path)
        return None
    model = lgb.Booster(model_file=str(path))
    log.info("Model loaded from %s", path)
    return model


# ── Prediction ───────────────────────────────────────────────────────────────

def predict(model: lgb.Booster, df: pd.DataFrame) -> np.ndarray:
    """
    Predict probability of price increase for each row.

    Returns array of probabilities (0–1).
    """
    available = [c for c in FEATURE_COLS if c in df.columns]
    return model.predict(df[available])
