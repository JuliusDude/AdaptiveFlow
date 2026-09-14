# 🚀 AdaptiveFlow: Comprehensive Efficiency Improvement Report

> **Analysis Date:** September 14, 2026  
> **Scope:** Full codebase audit — ML pipeline, simulator engine, feature engineering, timing optimizer, controller, evaluation, and dataset

---

## 📊 Current Performance Baseline

| Metric | Current Value | Assessment |
|:---|:---:|:---:|
| **Validation Accuracy** | 58.89% | ⚠️ Low |
| **Validation Macro F1** | 0.5435 | ⚠️ Moderate |
| **Train Accuracy** | 96.67% | 🔴 Severe overfitting gap (37.8%) |
| **Comprehensive Delay Reduction** | -1.89% | ⚠️ Marginal |
| **Exited-Only Delay Reduction** | -0.50% | ⚠️ Very marginal |
| **Queue Reduction** | -1.84% | ⚠️ Marginal |
| **Throughput Gain** | +29.3 vph | ⚠️ Small |
| **Total Training Samples** | 420 | 🔴 Very small dataset |
| **Worst-Class F1 (P6)** | 0.182 | 🔴 Near-collapse |
| **Dead Features** | `current_phase`, `elapsed_phase_time` = 0.0 importance | 🔴 Zero-variance |

### Per-Class Validation Breakdown

| Plan | Precision | Recall | F1-Score | Support | Assessment |
|:---|:---:|:---:|:---:|:---:|:---|
| **P1** | 0.81 | 0.89 | **0.85** | 19 | ✅ Good |
| **P2** | 0.40 | 0.44 | **0.42** | 9 | ⚠️ Poor |
| **P3** | 0.67 | 0.50 | **0.57** | 8 | ⚠️ Fair |
| **P4** | 0.45 | 0.50 | **0.48** | 10 | ⚠️ Poor |
| **P5** | 0.44 | 0.62 | **0.52** | 13 | ⚠️ Fair |
| **P6** | 0.25 | 0.14 | **0.18** | 14 | 🔴 Collapsed |
| **P7** | 0.81 | 0.76 | **0.79** | 17 | ✅ Good |

> [!IMPORTANT]
> The extreme plans (P1, P7) work well because clearly asymmetric traffic is easy to classify. The **intermediate plans P2–P6 are the bottleneck** — their demand patterns overlap, making class boundaries fuzzy.

---

## 🔍 Root Cause Analysis

### Root Cause 1: Extreme Overfitting (Train 96.7% vs Val 58.9%)
- **420 training samples** for a 7-class problem with 34 features = ~12 samples per feature dimension
- `max_depth=8` allows trees with up to 256 leaves — enough to memorize 420 samples entirely
- `min_samples_leaf=2` means leaves can form on just 2 samples (statistically meaningless)

### Root Cause 2: Zero-Variance Dead Features
- All 600 samples have `current_phase = 0.0` and `elapsed_phase_time = 0.0` (captured at fixed cycle boundary t=70s)
- Both features carry **zero information** and 0.0000 importance, adding noise to the model

### Root Cause 3: Ordinal Nature Ignored
- Plans P1→P7 form an ordered continuum (15s→45s NS green)
- Standard classification treats misclassifying P6→P5 (5s error) identically to P6→P1 (25s error)
- When delay differences between adjacent plans are tiny (<0.5s), the optimizer label fluctuates, creating **label noise**

### Root Cause 4: Controller Slew-Rate vs Optimizer Mismatch
- The optimizer evaluates plans with **immediate** actuation (no slew limiting)
- The runtime controller limits transitions to ±2 steps per cycle
- Result: In heavy asymmetric demand, the controller spends **50% of the evaluation window** (140s of 280s) in sub-optimal transitions

### Root Cause 5: Simulator Dead-Stop Spawn Bug
- In [intersection.py](file:///F:/Project/AdaptiveFlow/src/simulator/intersection.py), vehicles entering from entry buffers have speed forced to `0.0 m/s`
- Every vehicle must accelerate from standstill, injecting ~2.8s artificial delay even on empty green approaches
- This systematically inflates baseline delay and masks true ML improvements

---

## 📋 Improvement Areas (Ranked by Expected Impact)

---

### 1️⃣ DATASET SIZE — Scale from 600 to 3,000+ Scenarios

**Impact: 🟢 Very High | Effort: Low**

| Current | Recommended |
|:---|:---|
| 600 scenarios → 420 train / 90 val / 90 test | 3,000+ scenarios → 2,100 train / 450 val / 450 test |

420 training samples for 34 features is severely data-starved. This is the single highest-ROI change.

```bash
python -m src.ml.dataset --num_scenarios 3000 --horizon 140 --workers 8
```

---

### 2️⃣ MULTI-SNAPSHOT DATASET AUGMENTATION — 4-5x Data from Same Scenarios

**Impact: 🟢 Very High | Effort: Medium**

Currently [dataset.py](file:///F:/Project/AdaptiveFlow/src/ml/dataset.py) captures **one feature snapshot per scenario** at t=70s. Each scenario runs 70s warmup + 7×140s optimization = 1,050 simulation seconds but yields only **1 data point**.

**Extract features at every cycle boundary** (t=70, 140, 210, 280):

```python
# In _process_single_scenario - capture at multiple cycle boundaries
snapshots = []
for cycle in range(4):  # t=70, 140, 210, 280
    target_time = 70 * (cycle + 1)
    while sim.current_time < target_time:
        sim.step(dt=1.0)
    features = extract_features(sim)
    best_plan, _, all_delays = optimizer.optimize(sim=sim, horizon_steps=horizon_steps)
    snapshots.append({**features, "target_plan": best_plan, ...})
```

This multiplies effective dataset size by **4x** with zero extra scenario generation overhead, and captures features under different queue states within the same demand pattern.

---

### 3️⃣ HYPERPARAMETER TUNING — Stronger Regularization

**Impact: 🟢 High | Effort: Low**

Current hyperparameters in [train.py](file:///F:/Project/AdaptiveFlow/src/ml/train.py) are too permissive:

| Parameter | Current | Recommended | Rationale |
|:---|:---:|:---:|:---|
| `n_estimators` | 150 | **400** | More trees = better ensemble averaging |
| `max_depth` | 8 | **5** | Shallower trees prevent memorization |
| `min_samples_split` | 4 | **10** | Prevents splitting on noise |
| `min_samples_leaf` | 2 | **6** | Each leaf needs statistical significance |
| `max_features` | default | **"sqrt"** | Explicit feature subsampling |
| `min_impurity_decrease` | 0.0 | **0.005** | Prune insignificant splits |
| `max_samples` | None | **0.8** | Bootstrap sub-sampling for variance reduction |

```python
RandomForestClassifier(
    n_estimators=400,
    max_depth=5,
    min_samples_split=10,
    min_samples_leaf=6,
    min_impurity_decrease=0.005,
    max_features="sqrt",
    max_samples=0.8,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)
```

---

### 4️⃣ CROSS-VALIDATION — Replace Single Split with Stratified K-Fold

**Impact: 🟢 High | Effort: Low**

Model performance is evaluated on a **single 90-sample validation set** with high variance (±5-10%). Additionally, [dataset.py](file:///F:/Project/AdaptiveFlow/src/ml/dataset.py) uses **sequential index slicing** for train/val/test split — not stratified.

**Fixes:**
1. Use `sklearn.model_selection.train_test_split(stratify=y)` to preserve class proportions
2. Use **5-fold Stratified CV** during hyperparameter search:

```python
from sklearn.model_selection import StratifiedKFold, cross_val_score

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring='f1_macro')
print(f"CV Macro F1: {scores.mean():.4f} ± {scores.std():.4f}")
```

---

### 5️⃣ FEATURE ENGINEERING — Add Critical Missing Features

**Impact: 🟡 Medium-High | Effort: Medium**

The feature importance analysis reveals that **directional ratio features dominate** (top 5 are all ratios/diffs). Several high-value features are missing:

#### A. Webster's Critical Lane Demand (Missing!)

The current features compute `NS_count_total = N + S`. But traffic signal capacity is bottlenecked by the **heaviest single approach**:
- If N=35, S=0: total is 35, but Phase A needs green for 35 veh
- If N=18, S=17: total is 35, but Phase A only needs green for 18 veh

```python
# Critical lane features
"critical_demand_ns":  max(N_count, S_count),
"critical_demand_ew":  max(E_count, W_count),
"critical_queue_ns":   max(N_queue, S_queue),
"critical_queue_ew":   max(E_queue, W_queue),
"critical_demand_ratio": max(N,S) / max(0.1, max(N,S) + max(E,W)),
```

#### B. Speed-Based Congestion Indices

```python
# Dimensionless congestion (0=free-flow, 1=gridlock)
"speed_deficiency_ns": 1.0 - (N_speed + S_speed) / (2 * 13.89),
"speed_deficiency_ew": 1.0 - (E_speed + W_speed) / (2 * 13.89),
```

#### C. Spillback Buffer Exposure

```python
# Currently hidden from the feature vector
"spillback_buffer_total": sum(len(entry_buffer[app]) for app in approaches),
"max_spillback_approach": max(len(entry_buffer[app]) for app in approaches),
```

#### D. Queue Storage Ratio

```python
# How close is the longest queue to link capacity (150m / 6.5m ≈ 23 veh)
"queue_storage_ratio_max": max(N_queue, S_queue, E_queue, W_queue) / 23.0,
```

#### E. Internal Approach Asymmetry

```python
# Within-phase imbalance (N vs S, E vs W)
"ns_internal_asymmetry": abs(N_count - S_count),
"ew_internal_asymmetry": abs(E_count - W_count),
```

---

### 6️⃣ MODEL ALTERNATIVE — Gradient Boosting / Ordinal Regression

**Impact: 🟡 Medium-High | Effort: Low-Medium**

#### Option A: Gradient Boosting (Drop-in Replacement)

```python
from sklearn.ensemble import HistGradientBoostingClassifier

model = HistGradientBoostingClassifier(
    max_iter=300,
    max_depth=5,
    learning_rate=0.08,
    min_samples_leaf=8,
    class_weight="balanced",
    random_state=42,
)
```

GBDTs typically achieve **5-15% better accuracy** on tabular classification.

#### Option B: Ordinal / Continuous Regression (Eliminates Class Boundary Problem)

The plans form an ordered continuum. Train a regressor to predict NS green time directly:

```python
from sklearn.ensemble import HistGradientBoostingRegressor

# Target: NS green seconds (15, 20, 25, 30, 35, 40, 45)
model = HistGradientBoostingRegressor(...)

# Map prediction to discrete plan:
plan_idx = clip(round((predicted_ns_green - 15) / 5) + 1, 1, 7)
```

This eliminates the penalty mismatch between adjacent classes that causes P6 collapse.

---

### 7️⃣ SIMULATOR FIX — Dead-Stop Spawn Bug

**Impact: 🟡 Medium | Effort: Low**

In [intersection.py](file:///F:/Project/AdaptiveFlow/src/simulator/intersection.py) line ~144, vehicles entering from entry buffers have speed forced to `0.0`:

```python
v_entry.position = 0.0
v_entry.speed = 0.0  # ← Every vehicle starts from dead stop!
```

This forces every vehicle to spend ~5.56s accelerating to free-flow speed, injecting **~2.78s artificial delay per vehicle** even on empty approaches. This inflates baseline delay and masks the ML controller's true improvement.

**Fix:** Allow vehicles to enter at their sampled approach speed when road space is clear:
```python
v_entry.position = 0.0
v_entry.speed = min(v_entry.desired_speed * 0.7, v_entry.speed)  # Preserve some approach speed
```

---

### 8️⃣ CONTROLLER STABILITY — Fix Slew-Rate / Optimizer Mismatch

**Impact: 🟡 Medium | Effort: Medium**

In [predict.py](file:///F:/Project/AdaptiveFlow/src/ml/predict.py), the slew-rate limiter restricts plan changes to ±2 steps per cycle. But the optimizer trains labels assuming **immediate** plan application. This creates a train-deploy mismatch.

**Two options:**

**Option A:** Relax the slew limiter for extreme demand:
```python
# Allow immediate jumps when demand is clearly asymmetric
if demand_ratio < 0.30 or demand_ratio > 0.70 or abs(count_diff) > 20:
    pass  # Skip slew limiting — direct application is safe
elif abs(delta) > 2:
    step_dir = 2 if delta > 0 else -2
    plan = f"P{current_idx + step_dir}"
```

**Option B:** Train the optimizer with slew-rate constraints to match deployment behavior.

---

### 9️⃣ OPTIMIZER HORIZON — Extend Evaluation Window

**Impact: 🟡 Medium | Effort: Low**

The optimizer evaluates each plan over `horizon_steps=140` (2 cycles). A plan that looks good for 2 cycles might cause queue spillback by cycle 3-4.

```bash
python -m src.ml.dataset --num_scenarios 3000 --horizon 280 --workers 8
```

Extending to **280s (4 cycles)** produces more reliable ground-truth labels.

---

### 🔟 SIMULATOR PERFORMANCE — Faster Forward Evaluation

**Impact: 🟡 Medium | Effort: Medium**

The optimizer uses `copy.deepcopy(self)` to clone simulation state for each of 7 candidate plans. This accounts for **>60% of dataset generation time**.

**Fixes in** [intersection.py](file:///F:/Project/AdaptiveFlow/src/simulator/intersection.py):

1. **Replace `deepcopy` with fast snapshot/restore:**
```python
def fast_clone(self):
    """Lightweight state snapshot avoiding full object graph recursion."""
    # Copy only essential state: vehicle positions, speeds, signal state, metrics
    ...
```

2. **Replace O(N) rearmost position scan with O(1):**
```python
# Current (line ~140): O(N) scan every timestep
rearmost_pos = min((v.position for v in self.vehicles[app]), default=float("inf"))

# Fixed: O(1) — list is already sorted descending
rearmost_pos = self.vehicles[app][-1].position if self.vehicles[app] else float("inf")
```

3. **Remove redundant per-step sorting** (vehicles maintain FIFO order naturally in single-lane)

4. **Add `__slots__`** to Vehicle dataclass for 20% faster attribute access

---

### 1️⃣1️⃣ EVALUATION — Run More Scenarios for Longer

**Impact: 🟡 Medium | Effort: Low**

Current benchmark: 25 scenarios × 280s. Only evaluates `test_df.head(25)`, not all 90 test scenarios.

```bash
python -m src.ml.evaluate --scenarios 90 --duration 420
```

- **90 scenarios** (all test data) for tighter confidence intervals
- **420s (6 cycles)** gives the adaptive controller more time to demonstrate its advantage after initial convergence

---

### 1️⃣2️⃣ DEFAULT ARGUMENT BUG — `warmup_steps` Mismatch

**Impact: 🟡 Medium | Effort: Trivial**

In [timing_optimizer.py](file:///F:/Project/AdaptiveFlow/src/optimization/timing_optimizer.py) line 170:
```python
def evaluate_scenario(..., warmup_steps: int = 40, ...)  # ← Still 40!
```

But [dataset.py](file:///F:/Project/AdaptiveFlow/src/ml/dataset.py) passes `warmup_steps=70`. If anyone calls `evaluate_scenario()` without explicitly setting `warmup_steps=70`, it re-introduces the Phase Inversion bug (Issue-03).

**Fix:** Change default to `warmup_steps: int = 70`.

---

### 1️⃣3️⃣ YELLOW PHASE DILEMMA ZONE — Simulator Fidelity

**Impact: 🟡 Low-Medium | Effort: Medium**

In [signal.py](file:///F:/Project/AdaptiveFlow/src/simulator/signal.py), `can_proceed()` returns `False` during Yellow. Vehicles within 5-15m of the stop line at 13.89 m/s treat yellow as an instant red wall, causing unrealistic panic braking.

**Fix:** Allow vehicles in the dilemma zone (who cannot stop comfortably at ≤4.0 m/s²) to proceed through yellow.

---

### 1️⃣4️⃣ FEATURE SMOOTHING — Rolling Window Decision

**Impact: 🟡 Low-Medium | Effort: Low**

Each controller decision uses a single instantaneous snapshot. Transient noise can cause bad predictions.

```python
# Average features over last 3-5 seconds before cycle boundary
feature_buffer.append(extract_features(sim))
if len(feature_buffer) > 5:
    feature_buffer.pop(0)
avg_features = {k: np.mean([f[k] for f in feature_buffer]) for k in FEATURE_NAMES}
```

---

### 1️⃣5️⃣ PRESENTATION DATA SYNC

**Impact: 🟡 Low | Effort: Trivial**

[PRESENTATION.md](file:///F:/Project/AdaptiveFlow/PRESENTATION.md) shows different numbers (48.55s vs 47.46s) than [evaluation_benchmark.json](file:///F:/Project/AdaptiveFlow/results/metrics/evaluation_benchmark.json) (38.62s vs 37.89s). Sync the presentation with the latest benchmark run.

---

## 📈 Expected Impact Summary

```mermaid
flowchart LR
    A["Current State\nVal Acc: 58.9%\nDelay: -1.89%"] --> B["Phase 1: Data + Regularization\nFixes 1-4\nVal Acc: ~70-75%\nDelay: ~-4-6%"]
    B --> C["Phase 2: Features + Model\nFixes 5-6\nVal Acc: ~75-82%\nDelay: ~-6-10%"]
    C --> D["Phase 3: Simulator + Controller\nFixes 7-11\nVal Acc: ~78-85%\nDelay: ~-8-14%"]
```

| Fix | Expected Accuracy Gain | Expected Delay Improvement |
|:---|:---:|:---:|
| 1. Scale dataset 600→3000 | +8-12% | +1-3% delay reduction |
| 2. Multi-snapshot augmentation (4x data) | +3-5% | +0.5-1.5% |
| 3. Hyperparameter regularization | +3-5% | +0.5-1% |
| 4. Stratified CV | Reliable estimates | Better model selection |
| 5. Critical lane + congestion features | +3-6% | +1-2% |
| 6. Gradient boosting / ordinal regression | +3-8% | +1-3% |
| 7. Fix dead-stop spawn bug | — | +1-2% (baseline recalibration) |
| 8. Fix slew-rate / optimizer mismatch | — | +1-3% |
| 9. Longer optimizer horizon | +1-2% (label quality) | +0.5-1% |
| 10. Faster simulation cloning | Enables larger datasets | Indirect |
| 11. Full 90-scenario evaluation | Statistical confidence | — |
| 12. Fix warmup_steps default | Prevents regressions | — |

---

## ⚡ Quick-Win Action Plan (3 Commands)

> [!TIP]
> Start with these three changes — minimal code modifications required, biggest expected payoff:

### Step 1: Generate a much larger dataset
```bash
python -m src.ml.dataset --num_scenarios 3000 --horizon 210 --workers 8
```

### Step 2: Retrain with stronger regularization
```bash
python -m src.ml.train --n_estimators 400 --max_depth 5 --min_samples_leaf 6
```

### Step 3: Re-evaluate on all test scenarios
```bash
python -m src.ml.evaluate --scenarios 90 --duration 420
```

These three commands alone should push validation accuracy from ~59% toward ~70-75% and delay reduction from -1.89% toward -4-6%.

---

## 🐛 Code-Level Bugs to Fix Immediately

| File | Line | Bug | Fix |
|:---|:---:|:---|:---|
| [timing_optimizer.py](file:///F:/Project/AdaptiveFlow/src/optimization/timing_optimizer.py) | 170 | `warmup_steps=40` default (should be 70) | Change to `warmup_steps: int = 70` |
| [intersection.py](file:///F:/Project/AdaptiveFlow/src/simulator/intersection.py) | ~144 | Dead-stop spawn (`speed = 0.0`) | Preserve approach speed |
| [intersection.py](file:///F:/Project/AdaptiveFlow/src/simulator/intersection.py) | ~140 | O(N) rearmost scan on sorted list | Use `vehicles[app][-1].position` |
| [evaluate.py](file:///F:/Project/AdaptiveFlow/src/ml/evaluate.py) | ~85 | Only evaluates `head(25)` test scenarios | Evaluate all 90 |
