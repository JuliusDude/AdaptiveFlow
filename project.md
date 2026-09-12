# Predictive Urban Intersection Management — 3-Day Project Plan

## 1. Project Overview

### Working title
**Predictive Urban Intersection Management: Closed-Loop Adaptive Signal Control Using Supervised Machine Learning**

### Current project scope

Build a **working simulation-based prototype for one four-way urban intersection**. The prototype will simulate vehicles arriving from four approaches, derive traffic-state features, use a supervised machine-learning model to select a **discrete integer traffic-signal timing plan**, and evaluate whether the adaptive controller reduces traffic delay compared with a conventional fixed-time controller.

The project is intentionally **simulation-first** for the 3rd internal. Physical ESP32/LED hardware is not a dependency. If hardware becomes available later, it can be treated as an extension that reproduces the simulated signal state.

### Core research idea

The system follows:

```text
Traffic generation
      ↓
Python traffic simulator
      ↓
Traffic-state feature extraction
      ↓
Optimization of candidate signal plans
      ↓
Ground-truth "best" timing plan
      ↓
Supervised ML training
      ↓
ML predicts timing plan for unseen traffic
      ↓
Simulation evaluates controller
      ↓
Dashboard displays traffic + decisions + metrics
```

The central experimental question is:

> Can a supervised ML model use multiple traffic-state and signal-state features to select an integer-valued adaptive signal-timing plan that reduces average vehicle delay compared with a fixed-cycle controller?

---

## 2. Scope Decisions

### Included

- One four-legged intersection.
- Four approaches: North, South, East, West.
- Python-only traffic simulation.
- Discrete/integer traffic-signal timing plans.
- Supervised machine learning.
- Random Forest classifier as the initial model.
- Training data generated from simulation if an external dataset cannot be integrated quickly.
- Average vehicle delay as the primary optimization objective.
- Queue and throughput metrics for evaluation.
- Fixed-time baseline.
- Adaptive ML controller.
- Dashboard showing traffic state, queues, signal state, ML decision, and comparison metrics.
- Train/test separation so the model is evaluated on unseen traffic scenarios.

### Explicitly excluded from the 3-day core build

- Reinforcement learning.
- Full physical sensor network.
- ESP32/ESP8266 dependency.
- MQTT dependency.
- Multi-intersection coordination.
- Real-world hardware calibration.
- Computer vision.
- DHT11/MQ-2/PIR as direct ML inputs.
- Day-of-week modelling.
- Time-of-day modelling in the first model.
- Complex traffic-light optimization beyond the chosen discrete timing plans.
- SUMO.

SUMO was deliberately removed because its setup and Python/TraCI integration create unnecessary schedule risk for a three-day implementation.

---

# 3. Signal-Control Formulation

## 3.1 Recommended control structure

The ML model should choose the **green-time allocation for the next complete signal cycle**, rather than continuously changing the active phase.

The intersection uses two principal traffic phases:

### Phase A — North/South

- North: Green
- South: Green
- East: Red
- West: Red

### Phase B — East/West

- East: Green
- West: Green
- North: Red
- South: Red

Yellow and all-red clearance intervals should be represented in the simulator as fixed safety intervals.

## 3.2 Timing-plan classes

The model should not output arbitrary decimal values.

Instead, define a finite set of valid integer timing plans.

Initial candidate set:

| Plan | N/S Green | E/W Green |
|---|---:|---:|
| P1 | 15 s | 45 s |
| P2 | 20 s | 40 s |
| P3 | 25 s | 35 s |
| P4 | 30 s | 30 s |
| P5 | 35 s | 25 s |
| P6 | 40 s | 20 s |
| P7 | 45 s | 15 s |

These are **candidate plans**, not final values that must remain unchanged. The exact set can be adjusted after the simulator is working.

The ML target is therefore:

```text
P1 / P2 / P3 / P4 / P5 / P6 / P7
```

rather than:

```text
37.284 seconds
```

This makes the prediction problem a classification task and guarantees valid integer timings.

---

# 4. Definition of Input Features

The first model should use high-level traffic-state variables rather than raw sensor values.

## 4.1 Vehicle count

For each approach:

- `N_count`
- `S_count`
- `E_count`
- `W_count`

Definition:

> Number of vehicles currently inside the approach observation zone.

This is current traffic demand, not cumulative vehicles that have crossed the intersection.

---

## 4.2 Queue length

For each approach:

- `N_queue`
- `S_queue`
- `E_queue`
- `W_queue`

Definition:

> Number of vehicles currently stopped because they are waiting at the signal.

This is different from total vehicle count.

Example:

```text
North count = 20
North queue = 12
```

means 12 vehicles are stopped and 8 are still moving/approaching.

---

## 4.3 Arrival rate

For each approach:

- `N_arrival`
- `S_arrival`
- `E_arrival`
- `W_arrival`

Definition:

> Number of new vehicles entering an approach's observation zone during the previous 30 seconds, represented as vehicles per minute.

Formula:

```text
arrival_rate = arrivals_in_previous_30_seconds × 2
```

The 30-second window is an initial design choice and may be tuned after testing.

---

## 4.4 Average approach speed

For each approach:

- `N_speed`
- `S_speed`
- `E_speed`
- `W_speed`

Definition:

> Mean speed of vehicles within the observation zone over the previous 10 seconds.

This helps distinguish a large but dissipating queue from a large and highly congested queue.

---

## 4.5 Queue growth

For each approach:

- `N_queue_growth`
- `S_queue_growth`
- `E_queue_growth`
- `W_queue_growth`

Definition:

> Change in queue size over the previous 10 seconds.

Formula:

```text
queue_growth = current_queue - queue_10_seconds_ago
```

Interpretation:

- positive → queue is growing
- zero → stable
- negative → queue is shrinking

---

## 4.6 Current signal phase

Encode the active principal phase numerically:

```text
0 = N/S green
1 = E/W green
```

---

## 4.7 Elapsed phase time

Definition:

> Number of seconds for which the current principal phase has already been active.

This prevents the model from treating a phase that just started and a phase that has been active for 40 seconds as identical.

---

## 4.8 Initial feature vector

The first model therefore has 22 features:

### Demand — 4
- N_count
- S_count
- E_count
- W_count

### Congestion — 4
- N_queue
- S_queue
- E_queue
- W_queue

### Arrival dynamics — 4
- N_arrival
- S_arrival
- E_arrival
- W_arrival

### Speed — 4
- N_speed
- S_speed
- E_speed
- W_speed

### Queue dynamics — 4
- N_queue_growth
- S_queue_growth
- E_queue_growth
- W_queue_growth

### Signal state — 2
- current_phase
- elapsed_phase_time

---

# 5. Features Deliberately Excluded

The original CIA 1 architecture contains physical sensors such as ultrasonic sensors, PIR, DHT11 and MQ-2. For the simulation model, raw sensor readings should not be used simply to increase feature count.

## DHT11

Exclude from the initial ML model.

Temperature/humidity is not sufficiently justified as a direct predictor of optimal signal timing in the controlled simulation.

## MQ-2

Exclude from the initial ML model.

Gas concentration can be a future emissions-monitoring feature, but it should not be artificially made a signal-timing predictor.

## PIR

Exclude as a separate ML feature.

Its information should be transformed into higher-level traffic events such as vehicle arrivals.

## Raw ultrasonic distance

Exclude as a direct ML feature.

Use simulated sensing to derive higher-level variables such as vehicle presence, queue size, and arrival rate.

This preserves the conceptual separation:

```text
Physical sensors
      ↓
Traffic-state estimation
      ↓
ML features
      ↓
Signal controller
```

---

# 6. What "Best Timing" Means

The project needs a defensible training target.

Observed signal timings cannot automatically be called optimal. If a dataset says a real intersection used 30 seconds of green, that does not prove 30 seconds was the best choice.

Therefore, for simulation-generated training data:

1. Generate a traffic scenario.
2. Evaluate every valid candidate timing plan.
3. Run the scenario under each plan.
4. Measure performance.
5. Select the valid plan with the lowest average vehicle delay.
6. Use that plan as the supervised-learning label.

Example:

```text
Scenario:
N = 12
S = 8
E = 21
W = 5

Evaluate:
P1 → 47.2 s average delay
P2 → 39.1 s
P3 → 31.8 s
P4 → 35.4 s
...

Best = P3
```

The training record becomes:

```text
[traffic features] → P3
```

---

# 7. Optimization Objective

## Primary objective

### Minimize average vehicle delay

Conceptually:

```text
average_vehicle_delay =
total_vehicle_delay / number_of_vehicles
```

The simulator should calculate delay for vehicles based on their movement through the intersection.

## Secondary evaluation metrics

Do not optimize only for delay without checking other outcomes.

Track:

1. Average vehicle delay.
2. Average queue length.
3. Maximum queue length.
4. Throughput.
5. Per-approach waiting/delay.
6. Evidence of starvation/fairness problems.

Signal safety constraints should be handled by the controller design, not learned by the model.

---

# 8. Fixed-Time Baseline

The ML system needs a baseline.

Initial baseline:

```text
N/S = 30 seconds
E/W = 30 seconds
```

with the same fixed yellow/all-red intervals used by the adaptive controller.

Every test scenario should be evaluated using:

### Controller A
Fixed-time baseline.

### Controller B
ML adaptive timing.

Compare:

```text
Average delay
Average queue
Maximum queue
Throughput
```

The main headline metric should be the change in average vehicle delay.

Percentage improvement:

```text
improvement =
((fixed_delay - ml_delay) / fixed_delay) × 100
```

Only report measured results produced by the simulator.

---

# 9. Python Simulator Design

## 9.1 Intersection

Use a simple four-way intersection:

```text
                 NORTH
                   ↓
                   │
                   │
WEST  →────────────┼────────────←  EAST
                   │
                   │
                   ↑
                 SOUTH
```

Each approach should contain:

- an incoming road segment
- vehicle spawning
- moving vehicles
- stopping behaviour
- queue formation
- signal-controlled intersection
- vehicle departure

## 9.2 Vehicle model

A vehicle can initially be represented with:

- unique ID
- approach
- position
- speed
- desired speed
- state: approaching / queued / moving / exited
- arrival time
- accumulated waiting time

Keep the physics simple.

We do not need a perfect real-world driving model.

The simulator's job is to generate internally consistent traffic dynamics for the ML experiment.

## 9.3 Simulation step

Use:

```text
Δt = 1 second
```

At every step:

1. Spawn vehicles according to traffic demand.
2. Update signal state.
3. Update vehicle movement.
4. Determine stopped/queued vehicles.
5. Calculate waiting time.
6. Remove vehicles that have passed through.
7. Record telemetry.

## 9.4 ML decision interval

Do not change the timing every second.

Initially evaluate the controller every:

```text
5 seconds
```

or at an appropriate cycle/phase decision boundary.

The exact mechanism should be finalized during implementation to avoid unsafe phase switching.

---

# 10. Training Data Generation

If an existing real-world dataset cannot be integrated quickly, generate the labelled dataset ourselves.

## 10.1 Scenario generation

Generate many traffic scenarios with different demand patterns.

Examples:

```text
Balanced:
N=10 S=10 E=10 W=10

North-heavy:
N=30 S=8 E=6 W=5

East-heavy:
N=6 S=5 E=35 W=8

Opposite-heavy:
N=30 S=25 E=5 W=5

Mixed:
N=18 S=7 E=22 W=11
```

Use randomized values within realistic ranges rather than a handful of fixed scenarios.

## 10.2 Ground-truth generation

For each scenario:

```text
for each candidate timing plan:
    run simulation
    calculate average delay
select plan with minimum delay
save features + selected plan
```

This creates the supervised dataset.

## 10.3 Dataset split

Do not randomly leak nearly identical states into both training and test data.

Use scenario-level separation:

```text
Training: 70%
Validation: 15%
Test: 15%
```

The test scenarios must remain unseen during training.

---

# 11. Machine Learning Model

## Initial model

Use:

**Random Forest Classifier**

Why:

- appropriate for multiclass classification
- handles nonlinear relationships
- relatively little preprocessing
- fast to train
- interpretable through feature importance
- practical for a three-day project

Potential implementation:

```text
scikit-learn
RandomForestClassifier
```

## Model input

22 traffic/signal features.

## Model output

One of:

```text
P1
P2
P3
P4
P5
P6
P7
```

## Important evaluation

Report:

- accuracy
- macro F1 if useful
- confusion matrix
- feature importance
- controller-level performance on unseen scenarios

Model accuracy alone is not enough.

The most important question is:

> Does the ML controller actually reduce traffic delay?

---

# 12. Important Experimental Design

The optimizer is used to create training labels.

The trained ML model then attempts to reproduce the optimizer's decisions quickly.

This distinction must be maintained:

```text
Optimizer
= creates ground truth

ML model
= learns the mapping

Simulator
= evaluates the learned controller
```

Do not claim that the Random Forest itself directly discovered the mathematical optimum.

---

# 13. Dashboard

The dashboard should be intentionally simple.

Recommended implementation:

**Streamlit**

## Dashboard sections

### A. Intersection visualization

Display:

- four approaches
- current signal state
- approximate vehicles
- queue sizes

### B. Live traffic state

Example:

```text
North    18 vehicles    Queue: 12
South     9 vehicles    Queue:  5
East     21 vehicles    Queue: 18
West      4 vehicles    Queue:  2
```

### C. Current signal

```text
Current phase: N/S GREEN
Elapsed: 18 s
```

### D. ML recommendation

```text
Recommended plan: P5

N/S GREEN: 35 s
E/W GREEN: 25 s
```

### E. Performance comparison

```text
                 Fixed       ML
Avg delay        XX.X        XX.X
Avg queue        XX.X        XX.X
Throughput       XXX         XXX
```

### F. Optional charts

- queue length over time
- average delay comparison
- traffic arrivals
- selected timing plans

Do not overbuild the dashboard before the underlying simulation and ML system work.

---

# 14. Suggested Project Structure

```text
traffic-intersection-ml/
│
├── README.md
├── project.md
├── discussions.md
├── requirements.txt
│
├── src/
│   ├── simulator/
│   │   ├── intersection.py
│   │   ├── vehicle.py
│   │   ├── signal.py
│   │   ├── traffic_generator.py
│   │   └── metrics.py
│   │
│   ├── features/
│   │   └── feature_engineering.py
│   │
│   ├── optimization/
│   │   └── timing_optimizer.py
│   │
│   ├── ml/
│   │   ├── train.py
│   │   ├── predict.py
│   │   └── evaluate.py
│   │
│   └── dashboard/
│       └── app.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── generated/
│
├── models/
│   └── random_forest.pkl
│
├── results/
│   ├── metrics/
│   └── figures/
│
└── notebooks/
```

Do not create every file immediately. Build incrementally.

---

# 15. Three-Day Execution Plan

## DAY 1 — Simulator + Labelled Dataset

### Goal

By the end of Day 1:

> A four-way Python intersection can generate traffic, form queues, operate signals, measure delay, and evaluate timing plans.

### Phase 1 — Project skeleton

Create:

- repository/project directory
- Python environment
- requirements
- module structure

Install only necessary packages initially:

```text
numpy
pandas
scikit-learn
streamlit
matplotlib
joblib
```

Add other dependencies only when required.

### Phase 2 — Build vehicle simulation

Implement:

- vehicle creation
- movement
- speed
- stopping
- queue
- intersection exit

### Phase 3 — Build signal controller

Implement:

- N/S green
- E/W green
- yellow
- all-red
- timing plans

### Phase 4 — Implement metrics

At minimum:

- total vehicles
- exited vehicles
- waiting time
- average delay
- average queue
- maximum queue
- throughput

### Phase 5 — Timing optimizer

Implement:

```text
scenario
    ↓
evaluate P1...P7
    ↓
lowest average delay
    ↓
best plan
```

### Phase 6 — Generate dataset

Generate a sufficiently large set of varied scenarios.

Target is not a specific number initially; generate enough to support a train/test split and meaningful validation.

### Day 1 checkpoint

Must have:

```text
Traffic simulation ✓
Signal simulation ✓
Metrics ✓
Timing optimizer ✓
Training dataset ✓
```

If the simulator is taking too long, simplify vehicle physics rather than sacrificing the rest of the pipeline.

---

# DAY 2 — Machine Learning + Evaluation

### Goal

By the end of Day 2:

> A trained ML model predicts timing plans for unseen traffic states and the adaptive controller can be compared with fixed timing.

### Phase 1 — Dataset inspection

Check:

- missing values
- class balance
- feature ranges
- duplicate/leaky scenarios
- target distribution

### Phase 2 — Train Random Forest

Pipeline:

```text
dataset
 ↓
train/validation/test split
 ↓
Random Forest
 ↓
validation
 ↓
freeze model
```

Save model with `joblib`.

### Phase 3 — Model evaluation

Generate:

- accuracy
- confusion matrix
- feature importance
- classification report

### Phase 4 — Closed-loop ML controller

Connect:

```text
simulator
 ↓
features
 ↓
ML model
 ↓
timing plan
 ↓
simulator
```

The controller must actually affect the simulated traffic.

### Phase 5 — Baseline comparison

Run identical unseen traffic scenarios through:

```text
Fixed controller
```

and:

```text
ML controller
```

Collect results.

### Phase 6 — Robustness checks

Try:

- balanced traffic
- one-direction-heavy traffic
- opposing-direction-heavy traffic
- rapidly changing demand
- low traffic
- high traffic

### Day 2 checkpoint

Must have:

```text
Trained ML model ✓
Unseen-test evaluation ✓
Closed-loop ML controller ✓
Fixed baseline ✓
Comparative metrics ✓
```

---

# DAY 3 — Dashboard + Integration + Presentation

### Goal

By the end of Day 3:

> One coherent demonstration runs from traffic generation through ML decision to measurable performance output.

### Phase 1 — Streamlit dashboard

Implement:

- intersection state
- vehicles
- queues
- signal
- ML timing recommendation
- metrics

### Phase 2 — Integrate simulation

Dashboard should be able to start/reset a simulation and display the controller's behaviour.

### Phase 3 — Comparison view

Show:

```text
Fixed Timing vs ML Adaptive
```

with measured metrics.

### Phase 4 — Visualizations

Add only useful charts:

- queue over time
- average delay
- throughput
- selected timing plans

### Phase 5 — Final experiments

Run a fixed set of reproducible scenarios.

Save the results.

### Phase 6 — Presentation material

Prepare:

1. Problem statement.
2. Existing limitations.
3. Research gap.
4. Proposed architecture.
5. Simulation design.
6. Feature definitions.
7. ML methodology.
8. Optimization/label-generation methodology.
9. Fixed vs adaptive results.
10. Limitations and future hardware integration.

### Day 3 checkpoint

```text
End-to-end demo ✓
Results ✓
Dashboard ✓
Figures ✓
Presentation ✓
```

---

# 16. Priority / Cut Strategy

Three days means we need a strict priority order.

## Tier 1 — Absolutely required

1. Traffic simulator.
2. Signal controller.
3. Vehicle delay calculation.
4. Candidate timing evaluation.
5. Dataset generation.
6. Random Forest.
7. ML prediction.
8. Fixed-vs-ML comparison.

## Tier 2 — Strongly recommended

9. Queue metrics.
10. Throughput.
11. Feature importance.
12. Streamlit dashboard.
13. Charts.

## Tier 3 — Only if time remains

14. Animated vehicles.
15. More sophisticated vehicle behaviour.
16. Time-of-day feature.
17. Hardware LEDs.
18. MQTT.
19. ESP32 integration.
20. Additional ML models.

If Tier 1 is not complete, **do not work on Tier 3**.

---

# 17. Time-of-Day Feature

Time-of-day is deliberately deferred.

First build:

```text
traffic state → timing
```

Then optionally test:

```text
traffic state + time of day → timing
```

This lets us determine experimentally whether time provides useful predictive information.

Do not add day-of-week initially.

---

# 18. Hardware Extension

If ESP32 + LEDs become available, hardware can be added after the simulation works.

The ESP32 does not need to perform ML.

Potential extension:

```text
Python controller
      ↓
Wi-Fi/MQTT
      ↓
ESP32
      ↓
LED traffic signal
```

This should be presented as a physical demonstration of the controller output, not as the foundation of the ML experiment.

---

# 19. Existing Dataset Strategy

Existing traffic datasets were investigated before deciding to generate training data ourselves.

Potentially relevant sources include:

- Kolkata/Webel More single-intersection traffic data.
- Real-world intersection datasets containing traffic volume, queue and signal information.
- Traffic-flow datasets designed for signal-timing optimization.
- Signal/loop-detector datasets.

However, the central requirement is not merely traffic data. We need reliable labels for:

```text
traffic state → best timing plan
```

Observed historical signal timing does not automatically constitute an optimal label.

Therefore:

### Preferred approach

Use existing data if it can be integrated rapidly and legitimately.

### Reliable fallback

Generate scenarios in our simulator and derive labels by evaluating all candidate timing plans using average vehicle delay.

The fallback is not a weakness if the methodology is clearly documented.

---

# 20. Claims We Can and Cannot Make

## We can claim

- We implemented a Python-based intersection simulation.
- We formulated adaptive signal timing as supervised multiclass classification.
- We generated ground-truth timing labels through delay-based optimization.
- We trained a Random Forest classifier.
- We tested the model on unseen simulated traffic scenarios.
- We compared ML adaptive control against fixed-time control.
- We measured delay, queue, throughput and related metrics.

## We cannot claim without evidence

- Real-world traffic improvement.
- City-scale deployment.
- Weather robustness.
- Hardware sensing accuracy.
- Real-world mixed-traffic validation.
- Superiority over state-of-the-art traffic-control systems.
- That the model is universally optimal.
- That the physical IoT architecture has been implemented.

The original CIA 1 is a literature review/problem statement/proposed architecture and contains no experimental model results yet, so the 3rd-internal implementation should clearly distinguish proposed architecture from experimentally demonstrated results.

---

# 21. Final Demonstration Narrative

The demonstration should tell one simple story:

### Step 1

Traffic arrives at four approaches.

### Step 2

The simulator calculates:

- vehicle count
- queue
- arrival rate
- speed
- queue growth
- signal state

### Step 3

The ML model receives those features.

### Step 4

It selects a valid integer timing plan.

Example:

```text
N/S = 35 s
E/W = 25 s
```

### Step 5

The simulator applies that plan.

### Step 6

Traffic performance is measured.

### Step 7

The dashboard compares adaptive ML control with fixed-time control.

The final message is:

> **The model learns from simulated traffic states to select discrete signal-timing strategies associated with minimum average vehicle delay, then applies those strategies to unseen traffic conditions and evaluates the resulting traffic performance.**

