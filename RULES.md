# 📜 Project Development Rules & Guidelines

> **MANDATE:** These rules are strict, non-negotiable operational guidelines for all development workflows on this project. Every task and code change must strictly comply with the rules outlined below.

---

## 1. 🚫 Do Not Overengineer
* **Keep It Simple & Focused (KISS):** Build only what is needed to fulfill the immediate requirements.
* **Avoid Premature Abstraction:** Do not create speculative wrappers, overly generic patterns, or unnecessary architectural layers until concrete requirements demand them.
* **Direct Solutions:** Prefer straightforward, readable, and maintainable solutions over overly clever or complex designs.

---

## 2. 🧩 Dissect Problems into Small Tasks & Track in `TASKS.md`
* **Atomic Decomposition:** Always break complex requirements and features down into granular, actionable sub-tasks before starting implementation.
* **Maintain `TASKS.md`:**
  * Document all planned sub-tasks in `TASKS.md`.
  * Update task statuses (e.g., `- [ ]` to `- [x]`) immediately upon completion of each individual step.
* **Mandatory Pre-transition Verification:** Test and verify each sub-task thoroughly. Ensure there are no regressions, broken logic, or syntax/runtime errors before advancing to the next task.

---

## 3. ⚖️ Strict Adherence to `RULES.md`
* **Non-negotiable Compliance:** Always consult and strictly follow the principles documented in `RULES.md`.
* **Self-Correction:** If an approach conflicts with any rule here, stop immediately, adjust the strategy, and align with these guidelines before proceeding.

---

## 4. ⚙️ Working Code is the Highest Priority (No Broken Logic)
* **Zero Broken Logic:** Functional correctness and stability take absolute precedence over everything else.
* **End-to-End Validation:** Never leave code in a broken, half-implemented, or unverified state.
* **Defensive & Robust Code:** Ensure edge cases, error conditions, and core workflows are properly handled and verified.

---

## 5. 🔄 Commit and Push After Each Step (When Needed)
* **Atomic Commits:** Make clean, logical git commits after each verified task/step.
* **Descriptive Messages:** Write clear, concise commit messages reflecting the specific change made.
* **Push Synchronized State:** Push commits to the remote repository after significant steps or when checkpoints are reached to ensure progress is tracked and safely backed up.
