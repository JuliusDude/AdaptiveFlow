"""Impeccable Taste-Skill CSS Design Tokens and Styling for AdaptiveFlow.

Enforces zero-emoji minimalist aesthetic from design-taste-frontend,
high-end-visual-design, and gpt-taste:
- Pure geometric indicators, laser-crisp typography, and double-bezel architecture.
- Linear-tier OLED surfaces (#06080c, #0d1117, #131722).
- Micro-monospaced metric pills with calibrated status glows.
"""

COCKPIT_CSS = """
<style>
/* --- Font & Global Palette Tokens --- */
:root {
  --af-bg: #06080c;
  --af-surface-shell: rgba(255, 255, 255, 0.025);
  --af-surface-core: #0c1017;
  --af-border-subtle: rgba(255, 255, 255, 0.07);
  --af-border-hover: rgba(255, 255, 255, 0.16);
  --af-cyan: #00f0ff;
  --af-cyan-dim: rgba(0, 240, 255, 0.12);
  --af-emerald: #10b981;
  --af-amber: #f59e0b;
  --af-crimson: #ef4444;
}

/* Base Body & Container Architecture */
.block-container {
  padding-top: 1.25rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1400px !important;
}

h1, h2, h3, h4, h5, h6 {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  letter-spacing: -0.03em !important;
  font-weight: 700 !important;
  color: #f8fafc !important;
}

/* Precision Double-Bezel Architecture */
.double-bezel-card {
  background: var(--af-surface-shell);
  border: 1px solid var(--af-border-subtle);
  border-radius: 20px;
  padding: 5px;
  margin-bottom: 1.25rem;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.double-bezel-card:hover {
  border-color: var(--af-border-hover);
}
.double-bezel-inner {
  background: var(--af-surface-core);
  border-radius: 15px;
  padding: 16px 20px;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
}

/* Linear-Tier Micro-Eyebrows (No Emojis) */
.eyebrow-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-family: 'SF Mono', 'JetBrains Mono', 'Roboto Mono', monospace;
  margin-bottom: 6px;
}
.eyebrow-cyan {
  background: var(--af-cyan-dim);
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.25);
}
.eyebrow-emerald {
  background: rgba(16, 185, 129, 0.1);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.25);
}
.eyebrow-amber {
  background: rgba(245, 158, 11, 0.1);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.25);
}
.eyebrow-purple {
  background: rgba(168, 85, 247, 0.1);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.25);
}

/* Geometric Status LED Pips */
.led-pip {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}
.led-pip.cyan {
  background: #00f0ff;
  box-shadow: 0 0 8px #00f0ff;
}
.led-pip.green {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}
.led-pip.amber {
  background: #f59e0b;
  box-shadow: 0 0 8px #f59e0b;
}
.led-pip.red {
  background: #ef4444;
  box-shadow: 0 0 8px #ef4444;
}

/* Streamlit Button Overrides */
div.stButton > button {
  border-radius: 10px !important;
  font-size: 12px !important;
  font-weight: 700 !important;
  letter-spacing: 0.04em !important;
  text-transform: uppercase !important;
  transition: all 0.15s cubic-bezier(0.32, 0.72, 0, 1) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  background: rgba(255, 255, 255, 0.04) !important;
  color: #e2e8f0 !important;
}
div.stButton > button:hover {
  background: rgba(255, 255, 255, 0.09) !important;
  border-color: rgba(255, 255, 255, 0.22) !important;
  color: #fff !important;
}
div.stButton > button:active {
  transform: scale(0.97) !important;
}
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #0284c7, #0369a1) !important;
  border: 1px solid rgba(56, 189, 248, 0.4) !important;
  box-shadow: 0 4px 14px rgba(2, 132, 199, 0.3) !important;
  color: #fff !important;
}

/* Metric Display Overrides */
[data-testid="stMetric"] {
  background: rgba(255, 255, 255, 0.02) !important;
  border: 1px solid rgba(255, 255, 255, 0.06) !important;
  border-radius: 14px !important;
  padding: 12px 16px !important;
}
[data-testid="stMetricLabel"] {
  font-size: 10px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.12em !important;
  color: #94a3b8 !important;
  font-weight: 700 !important;
  font-family: 'SF Mono', 'JetBrains Mono', monospace !important;
}
[data-testid="stMetricValue"] {
  font-size: 22px !important;
  font-weight: 800 !important;
  font-family: 'SF Mono', 'JetBrains Mono', monospace !important;
  color: #f8fafc !important;
}

/* Clean Form Headers */
.hud-header-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 10px;
}
.hud-tag {
  font-family: 'SF Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
  letter-spacing: 0.08em;
}
</style>
"""
