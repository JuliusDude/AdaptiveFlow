"""Taste-Skill CSS Tokens and Styling for AdaptiveFlow Dashboard.

Applies anti-slop, high-end agency design principles from design-taste-frontend
and high-end-visual-design: Ethereal Dark Cockpit theme, double-bezel card architecture,
hairline strokes, and high-contrast monospace micro-typography.
"""

COCKPIT_CSS = """
<style>
/* --- Font & Global Palette Variables --- */
:root {
  --af-bg: #07090d;
  --af-surface-shell: rgba(255, 255, 255, 0.03);
  --af-surface-core: #0e1219;
  --af-border-hairline: rgba(255, 255, 255, 0.08);
  --af-border-glow: rgba(0, 240, 255, 0.2);
  --af-cyan: #00f0ff;
  --af-emerald: #10b981;
  --af-amber: #f59e0b;
  --af-crimson: #ef4444;
}

/* Streamlit Main Container Cleanup */
.block-container {
  padding-top: 1.5rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1380px !important;
}

/* Remove ugly default headers padding */
h1, h2, h3, h4 {
  letter-spacing: -0.02em;
  color: #f8fafc;
}

/* --- Double-Bezel Card Architecture --- */
.double-bezel-card {
  background: var(--af-surface-shell);
  border: 1px solid var(--af-border-hairline);
  border-radius: 20px;
  padding: 6px;
  margin-bottom: 1.25rem;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.double-bezel-card:hover {
  border-color: rgba(255, 255, 255, 0.14);
}
.double-bezel-inner {
  background: var(--af-surface-core);
  border-radius: 14px;
  padding: 18px 22px;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
}

/* Eyebrow Micro-Badges */
.eyebrow-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  font-family: 'SF Mono', 'JetBrains Mono', 'Roboto Mono', monospace;
  margin-bottom: 8px;
}
.eyebrow-cyan {
  background: rgba(0, 240, 255, 0.1);
  color: #38bdf8;
  border: 1px solid rgba(0, 240, 255, 0.25);
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

/* Custom Executive Stat Pill */
.stat-pill-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin: 10px 0 18px 0;
}
.stat-box {
  flex: 1;
  min-width: 140px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 12px 14px;
}
.stat-box .stat-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #94a3b8;
  font-weight: 600;
}
.stat-box .stat-val {
  font-size: 20px;
  font-weight: 800;
  color: #f1f5f9;
  margin-top: 2px;
  font-family: 'SF Mono', monospace;
}
.stat-box .stat-sub {
  font-size: 11px;
  margin-top: 2px;
  font-weight: 600;
}
.stat-sub.positive { color: #34d399; }
.stat-sub.negative { color: #f87171; }
.stat-sub.neutral { color: #94a3b8; }

/* Streamlit Button & Widget Polish */
div.stButton > button {
  border-radius: 12px !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em !important;
  transition: all 0.15s cubic-bezier(0.32, 0.72, 0, 1) !important;
}
div.stButton > button:active {
  transform: scale(0.98) !important;
}
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #0284c7, #0369a1) !important;
  border: 1px solid rgba(56, 189, 248, 0.4) !important;
  box-shadow: 0 4px 14px rgba(2, 132, 199, 0.3) !important;
}
div.stButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #0369a1, #075985) !important;
  box-shadow: 0 6px 18px rgba(2, 132, 199, 0.45) !important;
}

/* Metric card overrides */
[data-testid="stMetric"] {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 12px 16px;
}
[data-testid="stMetricLabel"] {
  font-size: 11px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
  color: #94a3b8 !important;
  font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
  font-size: 22px !important;
  font-weight: 800 !important;
  font-family: 'SF Mono', 'JetBrains Mono', monospace !important;
  color: #f8fafc !important;
}
</style>
"""
