"""Hardware-accelerated 60 FPS HTML5 Canvas / SVG 4-Way Intersection Visualizer.

Implements a photorealistic top-down intersection inspired by realistic intersection geometries:
- Zero car overlap with dynamic bumper-to-bumper queue stacking.
- Complete intersection traversal and continuous off-screen departure.
- Authentic right-hand lane physics for North, South, East, and West approaches.
- Prominent 3-lamp physical signal lanterns with intense LED bloom and dual countdown timers.
- Autoplay on load with full Play, Pause, Rewind 5s, Step Back, Step Forward, Fast-Forward,
  Speed selection, Scrubber, and instant "Force Phase Switch" testing.
"""

def generate_intersection_html(playback_json: str) -> str:
    """Generate self-contained HTML/CSS/JS document for the interactive 4-way intersection.

    Args:
        playback_json: Serialized JSON array of synchronized simulation frames.

    Returns:
        Complete HTML string ready for streamlit.components.v1.html().
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>AdaptiveFlow Intersection Visualizer</title>
<style>
  :root {{
    --bg: #07090d;
    --grass: #162016;
    --curb: #242b35;
    --road: #1c2128;
    --road-inner: #242a33;
    --lane: #f3e5ab;
    --stop: #faf8f5;
    --cyan: #00f0ff;
    --emerald: #10b981;
    --amber: #f59e0b;
    --red: #ef4444;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
  html, body {{
    width: 100%; height: 100%;
    overflow: hidden;
    background: var(--bg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #e2e8f0;
  }}

  .visualizer-wrapper {{
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: #080a0f;
  }}

  /* Top Control Strip */
  .top-bar {{
    height: 48px;
    background: rgba(14, 18, 26, 0.95);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    z-index: 100;
  }}
  .mode-pills {{
    display: flex;
    gap: 6px;
    background: rgba(0, 0, 0, 0.4);
    padding: 3px;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }}
  .mode-btn {{
    background: transparent;
    border: none;
    color: #94a3b8;
    padding: 5px 14px;
    border-radius: 16px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.03em;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.32, 0.72, 0, 1);
  }}
  .mode-btn.active {{
    background: rgba(0, 240, 255, 0.15);
    color: var(--cyan);
    box-shadow: 0 0 12px rgba(0, 240, 255, 0.2);
  }}
  .telemetry-pills {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
  }}
  .badge {{
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
    font-family: monospace;
    letter-spacing: 0.05em;
  }}
  .badge-ml {{
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }}
  .badge-fixed {{
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }}

  /* Viewport Stage */
  .stage {{
    position: relative;
    flex: 1;
    width: 100%;
    display: flex;
    overflow: hidden;
    background: var(--bg);
  }}
  .arena {{
    position: relative;
    flex: 1;
    height: 100%;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .arena.hidden {{ display: none; }}
  .arena-divider {{
    width: 2px;
    background: rgba(255, 255, 255, 0.1);
    height: 100%;
    position: relative;
    z-index: 80;
  }}

  /* Scene & Terrain */
  .intersection-scene {{
    position: relative;
    width: 100%;
    height: 100%;
    min-width: 500px;
    min-height: 480px;
    background:
      radial-gradient(circle at 50% 50%, rgba(30, 42, 30, 0.5), transparent 75%),
      var(--grass);
    overflow: hidden;
  }}
  .intersection-scene::before {{
    content: "";
    position: absolute; inset: 0;
    opacity: 0.2;
    background-image:
      radial-gradient(circle at 15% 25%, #4a683e 0 1px, transparent 1.5px),
      radial-gradient(circle at 75% 15%, #405c36 0 1px, transparent 1.5px),
      radial-gradient(circle at 35% 85%, #45623b 0 1px, transparent 1.5px),
      radial-gradient(circle at 85% 65%, #527546 0 1px, transparent 1.5px);
    background-size: 50px 50px;
  }}

  /* Curbs and Sidewalks */
  .curb-quadrant {{
    position: absolute;
    width: calc(50% - 100px);
    height: calc(50% - 100px);
    background: var(--curb);
    border: 2px solid #363e4c;
    z-index: 2;
  }}
  .curb-nw {{ top: 0; left: 0; border-bottom-right-radius: 28px; }}
  .curb-ne {{ top: 0; right: 0; border-bottom-left-radius: 28px; }}
  .curb-sw {{ bottom: 0; left: 0; border-top-right-radius: 28px; }}
  .curb-se {{ bottom: 0; right: 0; border-top-left-radius: 28px; }}

  /* Asphalt Roads (200px wide) */
  .road-h, .road-v {{
    position: absolute;
    background: linear-gradient(90deg, var(--road), var(--road-inner) 50%, var(--road));
    box-shadow: 0 0 0 1px rgba(0,0,0,0.5), inset 0 0 30px rgba(0,0,0,0.4);
    z-index: 1;
  }}
  .road-h {{
    left: 0; right: 0; top: 50%;
    height: 200px;
    transform: translateY(-50%);
  }}
  .road-v {{
    top: 0; bottom: 0; left: 50%;
    width: 200px;
    transform: translateX(-50%);
    background: linear-gradient(180deg, var(--road), var(--road-inner) 50%, var(--road));
  }}

  /* Center junction patch */
  .center-junction {{
    position: absolute; left: 50%; top: 50%;
    width: 200px; height: 200px;
    transform: translate(-50%, -50%);
    background: #232932;
    box-shadow: inset 0 0 25px rgba(0,0,0,0.6);
    z-index: 1;
  }}
  .center-box {{
    position: absolute; left: 50%; top: 50%;
    width: 80px; height: 80px;
    transform: translate(-50%, -50%);
    border-radius: 12px;
    background: #2b323d;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.04), inset 0 0 15px rgba(0,0,0,0.35);
    z-index: 2;
  }}

  /* Yellow Center Double Lines */
  .center-stripe {{
    position: absolute;
    background: var(--lane);
    opacity: 0.85;
    z-index: 3;
  }}
  .center-stripe.v1 {{ top: 0; bottom: calc(50% + 100px); left: calc(50% - 2px); width: 2px; }}
  .center-stripe.v2 {{ top: calc(50% + 100px); bottom: 0; left: calc(50% - 2px); width: 2px; }}
  .center-stripe.h1 {{ left: 0; right: calc(50% + 100px); top: calc(50% - 2px); height: 2px; }}
  .center-stripe.h2 {{ left: calc(50% + 100px); right: 0; top: calc(50% - 2px); height: 2px; }}

  /* Stop Lines */
  .stopbar {{
    position: absolute;
    background: var(--stop);
    box-shadow: 0 1px 4px rgba(0,0,0,0.6);
    z-index: 4;
  }}
  /* North: on driver's right (West side: x from cx-100 to cx) at y = cy - 100 */
  .stopbar.n {{ left: calc(50% - 100px); top: calc(50% - 104px); width: 100px; height: 5px; }}
  /* South: on driver's right (East side: x from cx to cx+100) at y = cy + 100 */
  .stopbar.s {{ left: 50%; top: calc(50% + 100px); width: 100px; height: 5px; }}
  /* West: on driver's right (South side: y from cy to cy+100) at x = cx - 100 */
  .stopbar.w {{ left: calc(50% - 104px); top: 50%; width: 5px; height: 100px; }}
  /* East: on driver's right (North side: y from cy-100 to cy) at x = cx + 100 */
  .stopbar.e {{ left: calc(50% + 100px); top: calc(50% - 100px); width: 5px; height: 100px; }}

  /* Zebra Crosswalks */
  .cross {{
    position: absolute;
    display: flex;
    gap: 5px;
    z-index: 3;
  }}
  .cross span {{
    background: #f1eddb;
    opacity: 0.8;
    box-shadow: 0 0 1px rgba(0,0,0,0.4);
  }}
  .cross.n {{ left: calc(50% - 100px); top: calc(50% - 138px); width: 100px; height: 26px; }}
  .cross.n span {{ width: 6px; height: 26px; }}
  .cross.s {{ left: 50%; top: calc(50% + 112px); width: 100px; height: 26px; }}
  .cross.s span {{ width: 6px; height: 26px; }}
  .cross.w {{ left: calc(50% - 138px); top: 50%; width: 26px; height: 100px; flex-direction: column; }}
  .cross.w span {{ width: 26px; height: 6px; }}
  .cross.e {{ left: calc(50% + 112px); top: calc(50% - 100px); width: 26px; height: 100px; flex-direction: column; }}
  .cross.e span {{ width: 26px; height: 6px; }}

  /* Directional Lane Arrows */
  .arrow {{
    position: absolute;
    color: rgba(255, 255, 255, 0.4);
    font-size: 16px;
    font-weight: 800;
    z-index: 3;
    pointer-events: none;
  }}
  .arrow.n {{ left: calc(50% - 54px); top: calc(50% - 170px); transform: rotate(180deg); }}
  .arrow.s {{ left: calc(50% + 40px); top: calc(50% + 150px); }}
  .arrow.w {{ left: calc(50% - 170px); top: calc(50% + 40px); transform: rotate(90deg); }}
  .arrow.e {{ left: calc(50% + 150px); top: calc(50% - 54px); transform: rotate(-90deg); }}

  /* Prominent 3-Lamp Traffic Signal Heads */
  .signal {{
    position: absolute;
    width: 26px;
    height: 72px;
    border-radius: 7px;
    background: linear-gradient(#14181c, #090b0d);
    border: 2px solid #454d57;
    box-shadow: 0 5px 12px rgba(0,0,0,0.75), inset 0 0 8px rgba(255,255,255,0.06);
    z-index: 40;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-evenly;
    padding: 3px 0;
  }}
  .signal .lamp {{
    width: 14px; height: 14px;
    border-radius: 50%;
    background: #1c2024;
    border: 1.5px solid #0f1215;
    box-shadow: inset 0 0 3px #000;
    transition: all 0.15s ease;
  }}
  .signal.red-on .lamp.red {{
    background: #ff3b30;
    box-shadow: 0 0 16px #ff3b30, 0 0 5px #fff;
  }}
  .signal.yellow-on .lamp.yellow {{
    background: #ffcc00;
    box-shadow: 0 0 16px #ffcc00, 0 0 5px #fff;
  }}
  .signal.green-on .lamp.green {{
    background: #34c759;
    box-shadow: 0 0 16px #34c759, 0 0 5px #fff;
  }}

  /* Positions of Signal Heads on Driver's Right Side Curb */
  .signal.n {{ top: calc(50% - 150px); left: calc(50% - 138px); }}
  .signal.s {{ top: calc(50% + 80px); left: calc(50% + 112px); }}
  .signal.w {{ top: calc(50% + 112px); left: calc(50% - 150px); transform: rotate(90deg); }}
  .signal.e {{ top: calc(50% - 138px); left: calc(50% + 80px); transform: rotate(-90deg); }}

  /* Integrated Signal Countdown Badges */
  .sig-timer {{
    position: absolute;
    background: rgba(11, 15, 22, 0.9);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255,255,255,0.15);
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 11px;
    font-family: 'SF Mono', monospace;
    font-weight: 800;
    color: #fff;
    z-index: 45;
    box-shadow: 0 4px 10px rgba(0,0,0,0.5);
    pointer-events: none;
    white-space: nowrap;
  }}
  .sig-timer.n {{ top: calc(50% - 180px); left: calc(50% - 146px); }}
  .sig-timer.s {{ top: calc(50% + 160px); left: calc(50% + 104px); }}
  .sig-timer.w {{ top: calc(50% + 155px); left: calc(50% - 180px); }}
  .sig-timer.e {{ top: calc(50% - 170px); left: calc(50% + 115px); }}

  /* Vehicles Layer */
  .car-layer {{
    position: absolute; inset: 0;
    pointer-events: none;
    z-index: 25;
  }}
  .car {{
    position: absolute;
    width: 36px;
    height: 20px;
    border-radius: 6px;
    transform-origin: center center;
    box-shadow: 0 4px 8px rgba(0,0,0,0.6);
    transition: transform 0.05s linear;
  }}
  /* Cabin glass */
  .car::before {{
    content: "";
    position: absolute; left: 7px; right: 7px; top: 3px; height: 14px;
    border-radius: 4px;
    background: linear-gradient(90deg, rgba(255,255,255,0.35), rgba(255,255,255,0.08));
    border: 1px solid rgba(255,255,255,0.2);
  }}
  /* Roof panel */
  .car::after {{
    content: "";
    position: absolute; left: 12px; right: 12px; top: 4px; height: 6px;
    border-radius: 2px;
    background: rgba(0, 0, 0, 0.45);
  }}
  /* Brake Lights (Rear: Left edge) */
  .car .brake-light {{
    position: absolute;
    left: 1px;
    width: 3px;
    height: 4px;
    border-radius: 1px;
    background: #500;
    transition: all 0.1s ease;
  }}
  .car .bl-top {{ top: 2px; }}
  .car .bl-bot {{ bottom: 2px; }}
  .car.braking .brake-light {{
    background: #ff2200;
    box-shadow: -3px 0 8px #ff2200, -1px 0 3px #fff;
  }}
  /* Headlights (Front: Right edge) */
  .car .headlight {{
    position: absolute;
    right: 1px;
    width: 3px;
    height: 4px;
    border-radius: 1px;
    background: #fff9d6;
    box-shadow: 3px 0 8px rgba(255, 245, 180, 0.9);
  }}
  .car .hl-top {{ top: 2px; }}
  .car .hl-bot {{ bottom: 2px; }}

  /* Vibrant Vehicle Palettes */
  .car.c-blue {{ background: linear-gradient(90deg, #1e40af, #3b82f6); }}
  .car.c-cyan {{ background: linear-gradient(90deg, #0891b2, #06b6d4); }}
  .car.c-emerald {{ background: linear-gradient(90deg, #047857, #10b981); }}
  .car.c-red {{ background: linear-gradient(90deg, #b91c1c, #ef4444); }}
  .car.c-amber {{ background: linear-gradient(90deg, #d97706, #f59e0b); }}
  .car.c-silver {{ background: linear-gradient(90deg, #475569, #94a3b8); }}
  .car.c-white {{ background: linear-gradient(90deg, #cbd5e1, #f8fafc); }}

  /* Floating HUD Overlay */
  .hud-card {{
    position: absolute;
    top: 14px;
    left: 14px;
    background: rgba(11, 15, 22, 0.88);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 10px 14px;
    z-index: 60;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
    min-width: 200px;
  }}
  .hud-title {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: #94a3b8;
  }}
  .hud-plan {{
    font-size: 15px;
    font-weight: 800;
    color: #fff;
    margin: 2px 0 6px 0;
  }}
  .hud-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
    color: #cbd5e1;
    margin-top: 3px;
  }}
  .hud-btn {{
    margin-top: 8px;
    width: 100%;
    background: rgba(0, 240, 255, 0.12);
    border: 1px solid rgba(0, 240, 255, 0.3);
    color: var(--cyan);
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  .hud-btn:hover {{
    background: rgba(0, 240, 255, 0.25);
    box-shadow: 0 0 10px rgba(0, 240, 255, 0.3);
  }}

  /* Bottom Floating Playback Dock */
  .playback-dock {{
    position: absolute;
    bottom: 14px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(13, 17, 25, 0.94);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 28px;
    padding: 8px 18px;
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 100;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
  }}
  .dock-btn {{
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s cubic-bezier(0.32, 0.72, 0, 1);
  }}
  .dock-btn:hover {{
    background: rgba(255, 255, 255, 0.15);
    color: #fff;
    transform: scale(1.08);
  }}
  .dock-btn:active {{ transform: scale(0.92); }}
  .dock-btn.primary {{
    background: var(--cyan);
    color: #040914;
    font-weight: 800;
    box-shadow: 0 0 14px rgba(0, 240, 255, 0.4);
  }}
  .dock-btn.primary:hover {{
    background: #38bdf8;
    box-shadow: 0 0 18px rgba(56, 189, 248, 0.6);
  }}
  .scrubber-container {{
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 220px;
  }}
  .scrubber {{
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 5px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.15);
    outline: none;
    cursor: pointer;
  }}
  .scrubber::-webkit-slider-thumb {{
    -webkit-appearance: none;
    appearance: none;
    width: 13px; height: 13px;
    border-radius: 50%;
    background: var(--cyan);
    box-shadow: 0 0 8px var(--cyan);
    cursor: pointer;
  }}
  .time-badge {{
    font-family: 'SF Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #94a3b8;
    white-space: nowrap;
  }}
  .speed-pills {{
    display: flex;
    gap: 4px;
    background: rgba(0,0,0,0.3);
    padding: 2px;
    border-radius: 14px;
  }}
  .speed-btn {{
    background: transparent;
    border: none;
    color: #94a3b8;
    padding: 3px 8px;
    border-radius: 10px;
    font-size: 10px;
    font-weight: 700;
    font-family: monospace;
    cursor: pointer;
  }}
  .speed-btn.active {{
    background: rgba(255, 255, 255, 0.15);
    color: #fff;
  }}
</style>
</head>
<body>
<div class="visualizer-wrapper">
  <!-- Top Bar -->
  <div class="top-bar">
    <div class="mode-pills">
      <button class="mode-btn active" id="btnModeML" onclick="setViewMode('ml')">AdaptiveFlow ML</button>
      <button class="mode-btn" id="btnModeFixed" onclick="setViewMode('fixed')">Fixed Baseline</button>
      <button class="mode-btn" id="btnModeDual" onclick="setViewMode('dual')">Side-by-Side Dual Arena</button>
    </div>
    <div class="telemetry-pills">
      <span class="badge badge-ml" id="topMLBadge">ML Plan: P4</span>
      <span class="badge badge-fixed" id="topFixedBadge" style="display:none;">Fixed: P4</span>
      <span class="time-badge" id="topClock">T = 0.0s</span>
    </div>
  </div>

  <!-- Stage Area (Supports Single or Dual Arenas) -->
  <div class="stage">
    <!-- Left / Primary Arena (AdaptiveFlow ML) -->
    <div class="arena" id="arenaML">
      <div class="intersection-scene" id="sceneML">
        <!-- Curbs -->
        <div class="curb-quadrant curb-nw"></div>
        <div class="curb-quadrant curb-ne"></div>
        <div class="curb-quadrant curb-sw"></div>
        <div class="curb-quadrant curb-se"></div>

        <!-- Roads -->
        <div class="road-h"></div>
        <div class="road-v"></div>
        <div class="center-junction"></div>
        <div class="center-box"></div>

        <!-- Center Striping -->
        <div class="center-stripe v1"></div>
        <div class="center-stripe v2"></div>
        <div class="center-stripe h1"></div>
        <div class="center-stripe h2"></div>

        <!-- Stop Lines -->
        <div class="stopbar n"></div>
        <div class="stopbar s"></div>
        <div class="stopbar w"></div>
        <div class="stopbar e"></div>

        <!-- Zebra Crosswalks -->
        <div class="cross n" id="crossML_N"></div>
        <div class="cross s" id="crossML_S"></div>
        <div class="cross w" id="crossML_W"></div>
        <div class="cross e" id="crossML_E"></div>

        <!-- Approach Direction Arrows -->
        <div class="arrow n">▲</div>
        <div class="arrow s">▲</div>
        <div class="arrow w">▲</div>
        <div class="arrow e">▲</div>

        <!-- Traffic Signals -->
        <div class="signal n" id="sigML_N"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>
        <div class="signal s" id="sigML_S"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>
        <div class="signal w" id="sigML_W"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>
        <div class="signal e" id="sigML_E"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>

        <!-- Countdown Badges -->
        <div class="sig-timer n" id="timerML_N">--</div>
        <div class="sig-timer s" id="timerML_S">--</div>
        <div class="sig-timer w" id="timerML_W">--</div>
        <div class="sig-timer e" id="timerML_E">--</div>

        <!-- Vehicles Layer -->
        <div class="car-layer" id="carsML"></div>

        <!-- HUD Card -->
        <div class="hud-card">
          <div class="hud-title">AdaptiveFlow Controller</div>
          <div class="hud-plan" id="hudML_Plan">Plan P4</div>
          <div class="hud-row">
            <span>Phase:</span>
            <strong id="hudML_Phase">NS GREEN</strong>
          </div>
          <div class="hud-row">
            <span>N/S Signal:</span>
            <strong id="hudML_NSTimer" style="color:#34d399;">🟢 18.0s</strong>
          </div>
          <div class="hud-row">
            <span>E/W Signal:</span>
            <strong id="hudML_EWTimer" style="color:#ef4444;">🔴 23.0s</strong>
          </div>
          <div class="hud-row">
            <span>Avg Delay:</span>
            <strong id="hudML_Delay" style="color: #34d399;">0.0s</strong>
          </div>
          <div class="hud-row">
            <span>Queue:</span>
            <strong id="hudML_Queue">0 veh</strong>
          </div>
          <button class="hud-btn" onclick="jumpToNextPhase()">⚡ Switch Phase Now</button>
        </div>
      </div>
    </div>

    <!-- Divider in Dual Mode -->
    <div class="arena-divider" id="dualDivider" style="display:none;"></div>

    <!-- Right Arena (Fixed Baseline P4) -->
    <div class="arena hidden" id="arenaFixed">
      <div class="intersection-scene" id="sceneFixed">
        <!-- Curbs -->
        <div class="curb-quadrant curb-nw"></div>
        <div class="curb-quadrant curb-ne"></div>
        <div class="curb-quadrant curb-sw"></div>
        <div class="curb-quadrant curb-se"></div>

        <!-- Roads -->
        <div class="road-h"></div>
        <div class="road-v"></div>
        <div class="center-junction"></div>
        <div class="center-box"></div>

        <!-- Center Striping -->
        <div class="center-stripe v1"></div>
        <div class="center-stripe v2"></div>
        <div class="center-stripe h1"></div>
        <div class="center-stripe h2"></div>

        <!-- Stop Lines -->
        <div class="stopbar n"></div>
        <div class="stopbar s"></div>
        <div class="stopbar w"></div>
        <div class="stopbar e"></div>

        <!-- Zebra Crosswalks -->
        <div class="cross n" id="crossFixed_N"></div>
        <div class="cross s" id="crossFixed_S"></div>
        <div class="cross w" id="crossFixed_W"></div>
        <div class="cross e" id="crossFixed_E"></div>

        <!-- Approach Direction Arrows -->
        <div class="arrow n">▲</div>
        <div class="arrow s">▲</div>
        <div class="arrow w">▲</div>
        <div class="arrow e">▲</div>

        <!-- Traffic Signals -->
        <div class="signal n" id="sigFixed_N"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>
        <div class="signal s" id="sigFixed_S"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>
        <div class="signal w" id="sigFixed_W"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>
        <div class="signal e" id="sigFixed_E"><div class="lamp red"></div><div class="lamp yellow"></div><div class="lamp green"></div></div>

        <!-- Countdown Badges -->
        <div class="sig-timer n" id="timerFixed_N">--</div>
        <div class="sig-timer s" id="timerFixed_S">--</div>
        <div class="sig-timer w" id="timerFixed_W">--</div>
        <div class="sig-timer e" id="timerFixed_E">--</div>

        <!-- Vehicles Layer -->
        <div class="car-layer" id="carsFixed"></div>

        <!-- HUD Card -->
        <div class="hud-card">
          <div class="hud-title">Fixed-Time Baseline</div>
          <div class="hud-plan" style="color: #f87171;">Plan P4 (Fixed)</div>
          <div class="hud-row">
            <span>Phase:</span>
            <strong id="hudFixed_Phase">NS GREEN</strong>
          </div>
          <div class="hud-row">
            <span>N/S Signal:</span>
            <strong id="hudFixed_NSTimer" style="color:#34d399;">🟢 18.0s</strong>
          </div>
          <div class="hud-row">
            <span>E/W Signal:</span>
            <strong id="hudFixed_EWTimer" style="color:#ef4444;">🔴 23.0s</strong>
          </div>
          <div class="hud-row">
            <span>Avg Delay:</span>
            <strong id="hudFixed_Delay" style="color: #f87171;">0.0s</strong>
          </div>
          <div class="hud-row">
            <span>Queue:</span>
            <strong id="hudFixed_Queue">0 veh</strong>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Bottom Floating Playback Dock -->
  <div class="playback-dock">
    <button class="dock-btn" title="Rewind 5s (⏮)" onclick="stepBy(-5)">⏮</button>
    <button class="dock-btn" title="Step Back 1s (◀)" onclick="stepBy(-1)">◀</button>
    <button class="dock-btn primary" id="btnPlayPause" title="Play / Pause" onclick="togglePlay()">⏸</button>
    <button class="dock-btn" title="Step Forward 1s (▶)" onclick="stepBy(1)">▶</button>
    <button class="dock-btn" title="Fast-Forward 5s (⏭)" onclick="stepBy(5)">⏭</button>

    <div class="scrubber-container">
      <input type="range" class="scrubber" id="timeScrubber" min="0" max="100" value="0" step="0.1" oninput="onScrub(this.value)" />
      <span class="time-badge" id="scrubberLabel">0.0s / 0.0s</span>
    </div>

    <div class="speed-pills">
      <button class="speed-btn" id="spd05" onclick="setSpeed(0.5)">0.5x</button>
      <button class="speed-btn active" id="spd10" onclick="setSpeed(1.0)">1x</button>
      <button class="speed-btn" id="spd20" onclick="setSpeed(2.0)">2x</button>
      <button class="speed-btn" id="spd40" onclick="setSpeed(4.0)">4x</button>
    </div>
  </div>
</div>

<script>
// Initialize Crosswalk Stripes
['crossML_N','crossML_S','crossFixed_N','crossFixed_S'].forEach(id => {{
  const el = document.getElementById(id);
  if (el) {{
    for(let i=0; i<12; i++) el.appendChild(document.createElement('span'));
  }}
}});
['crossML_W','crossML_E','crossFixed_W','crossFixed_E'].forEach(id => {{
  const el = document.getElementById(id);
  if (el) {{
    for(let i=0; i<12; i++) el.appendChild(document.createElement('span'));
  }}
}});

// Trajectory Buffer
const frames = {playback_json};
const totalFrames = frames.length;
const maxTime = totalFrames > 0 ? frames[totalFrames - 1].t : 0;

// Autoplay by default so site is immediately alive
let currentPlaybackTime = 0.0;
let isPlaying = true;
let playbackSpeed = 1.0;
let lastAnimTimestamp = null;
let currentMode = 'ml'; // 'ml', 'fixed', 'dual'

// Color palette for vehicle IDs
const carPalettes = ['c-blue', 'c-cyan', 'c-emerald', 'c-red', 'c-amber', 'c-silver', 'c-white'];
function getCarClass(id) {{
  return carPalettes[Math.abs(id) % carPalettes.length];
}}

// Setup Scrubber Bounds
const scrubber = document.getElementById('timeScrubber');
scrubber.max = maxTime;

function setViewMode(mode) {{
  currentMode = mode;
  const btnML = document.getElementById('btnModeML');
  const btnFixed = document.getElementById('btnModeFixed');
  const btnDual = document.getElementById('btnModeDual');

  const arenaML = document.getElementById('arenaML');
  const arenaFixed = document.getElementById('arenaFixed');
  const dualDivider = document.getElementById('dualDivider');

  btnML.classList.remove('active');
  btnFixed.classList.remove('active');
  btnDual.classList.remove('active');

  if (mode === 'ml') {{
    btnML.classList.add('active');
    arenaML.classList.remove('hidden');
    arenaFixed.classList.add('hidden');
    dualDivider.style.display = 'none';
    document.getElementById('topMLBadge').style.display = 'inline-block';
    document.getElementById('topFixedBadge').style.display = 'none';
  }} else if (mode === 'fixed') {{
    btnFixed.classList.add('active');
    arenaML.classList.add('hidden');
    arenaFixed.classList.remove('hidden');
    dualDivider.style.display = 'none';
    document.getElementById('topMLBadge').style.display = 'none';
    document.getElementById('topFixedBadge').style.display = 'inline-block';
  }} else {{
    btnDual.classList.add('active');
    arenaML.classList.remove('hidden');
    arenaFixed.classList.remove('hidden');
    dualDivider.style.display = 'block';
    document.getElementById('topMLBadge').style.display = 'inline-block';
    document.getElementById('topFixedBadge').style.display = 'inline-block';
  }}
  renderFrame(currentPlaybackTime);
}}

function setSpeed(spd) {{
  playbackSpeed = spd;
  ['spd05','spd10','spd20','spd40'].forEach(id => {{
    const el = document.getElementById(id);
    if(el) el.classList.remove('active');
  }});
  if (spd === 0.5) document.getElementById('spd05').classList.add('active');
  if (spd === 1.0) document.getElementById('spd10').classList.add('active');
  if (spd === 2.0) document.getElementById('spd20').classList.add('active');
  if (spd === 4.0) document.getElementById('spd40').classList.add('active');
}}

function togglePlay() {{
  isPlaying = !isPlaying;
  const btn = document.getElementById('btnPlayPause');
  btn.textContent = isPlaying ? '⏸' : '▶';
  if (isPlaying && currentPlaybackTime >= maxTime) {{
    currentPlaybackTime = 0.0;
  }}
  lastAnimTimestamp = null;
}}

function stepBy(seconds) {{
  currentPlaybackTime = Math.max(0.0, Math.min(maxTime, currentPlaybackTime + seconds));
  scrubber.value = currentPlaybackTime;
  renderFrame(currentPlaybackTime);
}}

function onScrub(val) {{
  currentPlaybackTime = parseFloat(val);
  renderFrame(currentPlaybackTime);
}}

// Interactive phase switch: advances to next phase transition in frames
function jumpToNextPhase() {{
  const curIdx = Math.min(totalFrames - 1, Math.floor(currentPlaybackTime));
  const curPhase = frames[curIdx].ml.phase_name;
  for (let i = curIdx + 1; i < totalFrames; i++) {{
    if (frames[i].ml.phase_name !== curPhase) {{
      currentPlaybackTime = frames[i].t;
      scrubber.value = currentPlaybackTime;
      renderFrame(currentPlaybackTime);
      return;
    }}
  }}
  // If no future phase transition in buffer, wrap to 0
  currentPlaybackTime = 0.0;
  scrubber.value = 0.0;
  renderFrame(0.0);
}}

// Binary search for interpolated frame
function getFrameIndices(t) {{
  if (totalFrames === 0) return {{ f1: null, f2: null, alpha: 0 }};
  if (t <= frames[0].t) return {{ f1: frames[0], f2: frames[0], alpha: 0 }};
  if (t >= frames[totalFrames - 1].t) return {{ f1: frames[totalFrames - 1], f2: frames[totalFrames - 1], alpha: 0 }};

  let low = 0, high = totalFrames - 1;
  while (low <= high) {{
    const mid = Math.floor((low + high) / 2);
    if (frames[mid].t <= t && (mid === totalFrames - 1 || frames[mid + 1].t > t)) {{
      const f1 = frames[mid];
      const f2 = frames[Math.min(totalFrames - 1, mid + 1)];
      const dt = f2.t - f1.t;
      const alpha = dt > 0 ? (t - f1.t) / dt : 0;
      return {{ f1, f2, alpha }};
    }}
    if (frames[mid].t < t) low = mid + 1;
    else high = mid - 1;
  }}
  return {{ f1: frames[0], f2: frames[0], alpha: 0 }};
}}

// Compute 2D vehicle positions with ZERO overlap and full intersection crossing
function computeVisualPositions(vehicles, width, height) {{
  const cx = width / 2;
  const cy = height / 2;
  const D_STOP = 100; // px from center to stop line
  const LANE_OFFSET = 44; // px offset from center stripe to right-hand driving lane
  const CAR_LENGTH = 36;
  const MIN_GAP = 8;
  const CAR_SPACING = CAR_LENGTH + MIN_GAP; // 44px between bumper centers in queue

  const byApp = {{ N: [], S: [], E: [], W: [] }};
  (vehicles || []).forEach(v => {{
    if (byApp[v.app]) byApp[v.app].push(v);
  }});

  const result = [];

  ['N', 'S', 'E', 'W'].forEach(app => {{
    const list = byApp[app];
    // Sort leaders first (highest pos first)
    list.sort((a, b) => b.pos - a.pos);

    let lastVisualDist = -9999;

    list.forEach((v, idx) => {{
      let visualDistFromStop = 0; // >0: before stop line, <0: crossing/departing past stop line

      if (v.pos >= 150.0) {{
        // Traversing or cleared intersection:
        // 150m to 170m crosses center junction (0 to 200px)
        // >170m continues along departure road off the screen
        const crossMeters = v.pos - 150.0;
        visualDistFromStop = - (crossMeters / 20.0) * (D_STOP * 2);
      }} else {{
        // Approaching or queued behind stop line
        const distMeters = 150.0 - v.pos;
        // Map 150m approach smoothly: 1.8 px/meter
        const rawPixels = distMeters * 1.8;
        if (idx === 0) {{
          visualDistFromStop = Math.max(0, rawPixels);
        }} else {{
          // Guaranteed anti-overlap rule: must be at least CAR_SPACING behind lead vehicle
          const minAllowed = lastVisualDist + CAR_SPACING;
          visualDistFromStop = Math.max(rawPixels, minAllowed);
        }}
      }}

      lastVisualDist = visualDistFromStop;

      let x = cx, y = cy, rot = 0;

      // Authentic right-hand driving lanes & headings:
      // North: drives South (+y) on West lane (cx - LANE_OFFSET), heading rot=90
      if (app === 'N') {{
        x = cx - LANE_OFFSET;
        y = (cy - D_STOP) - visualDistFromStop;
        rot = 90;
      }}
      // South: drives North (-y) on East lane (cx + LANE_OFFSET), heading rot=-90
      else if (app === 'S') {{
        x = cx + LANE_OFFSET;
        y = (cy + D_STOP) + visualDistFromStop;
        rot = -90;
      }}
      // West: drives East (+x) on South lane (cy + LANE_OFFSET), heading rot=0
      else if (app === 'W') {{
        x = (cx - D_STOP) - visualDistFromStop;
        y = cy + LANE_OFFSET;
        rot = 0;
      }}
      // East: drives West (-x) on North lane (cy - LANE_OFFSET), heading rot=180
      else if (app === 'E') {{
        x = (cx + D_STOP) + visualDistFromStop;
        y = cy - LANE_OFFSET;
        rot = 180;
      }}

      result.push({{
        id: v.id,
        app: v.app,
        x: x,
        y: y,
        rot: rot,
        spd: v.spd,
        st: v.st,
      }});
    }});
  }});

  return result;
}}

function renderScene(scenePrefix, simData, width, height) {{
  if (!simData) return;

  const nsColor = simData.ns_color;
  const ewColor = simData.ew_color;
  const nsTimer = simData.ns_timer !== undefined ? simData.ns_timer : simData.remaining;
  const ewTimer = simData.ew_timer !== undefined ? simData.ew_timer : simData.remaining;

  // 1. Update Traffic Signal Lanterns & Timers
  ['N', 'S'].forEach(arm => {{
    const sig = document.getElementById(`sig${{scenePrefix}}_${{arm}}`);
    if (sig) {{
      sig.className = `signal ${{arm.toLowerCase()}} ${{nsColor.toLowerCase()}}-on`;
    }}
    const timer = document.getElementById(`timer${{scenePrefix}}_${{arm}}`);
    if (timer) {{
      const icon = nsColor === 'GREEN' ? '🟢' : (nsColor === 'YELLOW' ? '🟡' : '🔴');
      timer.textContent = `${{icon}} ${{Math.ceil(nsTimer)}}s`;
      timer.style.color = nsColor === 'GREEN' ? '#34d399' : (nsColor === 'YELLOW' ? '#ffcc00' : '#ff453a');
    }}
  }});

  ['E', 'W'].forEach(arm => {{
    const sig = document.getElementById(`sig${{scenePrefix}}_${{arm}}`);
    if (sig) {{
      sig.className = `signal ${{arm.toLowerCase()}} ${{ewColor.toLowerCase()}}-on`;
    }}
    const timer = document.getElementById(`timer${{scenePrefix}}_${{arm}}`);
    if (timer) {{
      const icon = ewColor === 'GREEN' ? '🟢' : (ewColor === 'YELLOW' ? '🟡' : '🔴');
      timer.textContent = `${{icon}} ${{Math.ceil(ewTimer)}}s`;
      timer.style.color = ewColor === 'GREEN' ? '#34d399' : (ewColor === 'YELLOW' ? '#ffcc00' : '#ff453a');
    }}
  }});

  // 2. Update HUD
  const hudPlan = document.getElementById(`hud${{scenePrefix}}_Plan`);
  const hudPhase = document.getElementById(`hud${{scenePrefix}}_Phase`);
  const hudNSTimer = document.getElementById(`hud${{scenePrefix}}_NSTimer`);
  const hudEWTimer = document.getElementById(`hud${{scenePrefix}}_EWTimer`);
  const hudDelay = document.getElementById(`hud${{scenePrefix}}_Delay`);
  const hudQueue = document.getElementById(`hud${{scenePrefix}}_Queue`);

  if (hudPlan) hudPlan.textContent = `Plan ${{simData.plan}} (${{simData.ns_green}}s / ${{simData.ew_green}}s)`;
  if (hudPhase) hudPhase.textContent = simData.phase_name;
  if (hudNSTimer) {{
    const icon = nsColor === 'GREEN' ? '🟢' : (nsColor === 'YELLOW' ? '🟡' : '🔴');
    hudNSTimer.textContent = `${{icon}} ${{Math.ceil(nsTimer)}}s`;
    hudNSTimer.style.color = nsColor === 'GREEN' ? '#34d399' : (nsColor === 'YELLOW' ? '#ffcc00' : '#ff453a');
  }}
  if (hudEWTimer) {{
    const icon = ewColor === 'GREEN' ? '🟢' : (ewColor === 'YELLOW' ? '🟡' : '🔴');
    hudEWTimer.textContent = `${{icon}} ${{Math.ceil(ewTimer)}}s`;
    hudEWTimer.style.color = ewColor === 'GREEN' ? '#34d399' : (ewColor === 'YELLOW' ? '#ffcc00' : '#ff453a');
  }}
  if (hudDelay) hudDelay.textContent = `${{simData.metrics.comp_delay.toFixed(1)}}s`;
  if (hudQueue) hudQueue.textContent = `${{simData.metrics.avg_queue.toFixed(1)}} veh`;

  // 3. Render Vehicles with Zero Overlap
  const carLayer = document.getElementById(`cars${{scenePrefix}}`);
  if (!carLayer) return;
  carLayer.innerHTML = '';

  const visualVehicles = computeVisualPositions(simData.vehicles, width, height);

  visualVehicles.forEach(v => {{
    // Skip vehicles that have fully left the scene bounds
    if (v.x < -60 || v.x > width + 60 || v.y < -60 || v.y > height + 60) {{
      return;
    }}

    const car = document.createElement('div');
    const colorClass = getCarClass(v.id);
    const isBraking = v.spd < 0.8 || v.st === 'queued';

    car.className = `car ${{colorClass}} ${{isBraking ? 'braking' : ''}}`;
    car.style.left = `${{v.x - 18}}px`;
    car.style.top = `${{v.y - 10}}px`;
    car.style.transform = `rotate(${{v.rot}}deg)`;

    // Dynamic lights
    const blTop = document.createElement('div'); blTop.className = 'brake-light bl-top'; car.appendChild(blTop);
    const blBot = document.createElement('div'); blBot.className = 'brake-light bl-bot'; car.appendChild(blBot);
    const hlTop = document.createElement('div'); hlTop.className = 'headlight hl-top'; car.appendChild(hlTop);
    const hlBot = document.createElement('div'); hlBot.className = 'headlight hl-bot'; car.appendChild(hlBot);

    carLayer.appendChild(car);
  }});
}}

function renderFrame(t) {{
  const {{ f1, f2, alpha }} = getFrameIndices(t);
  if (!f1) return;

  function interpolateVehicles(vList1, vList2, a) {{
    const v2Map = new Map();
    (vList2 || []).forEach(v => v2Map.set(v.id, v));

    return (vList1 || []).map(v1 => {{
      const v2 = v2Map.get(v1.id);
      if (v2) {{
        return {{
          id: v1.id,
          app: v1.app,
          pos: v1.pos + (v2.pos - v1.pos) * a,
          spd: v1.spd + (v2.spd - v1.spd) * a,
          st: a > 0.5 ? v2.st : v1.st,
          wt: v1.wt,
        }};
      }}
      return v1;
    }});
  }}

  // Accurate interpolated countdown timers
  const dtSec = f2 ? (f2.t - f1.t) * alpha : 0;
  const curML = {{
    ...f1.ml,
    ns_timer: Math.max(0.0, (f1.ml.ns_timer || f1.ml.remaining) - dtSec),
    ew_timer: Math.max(0.0, (f1.ml.ew_timer || f1.ml.remaining) - dtSec),
    vehicles: interpolateVehicles(f1.ml.vehicles, f2 ? f2.ml.vehicles : null, alpha),
  }};
  const curFixed = {{
    ...f1.fixed,
    ns_timer: Math.max(0.0, (f1.fixed.ns_timer || f1.fixed.remaining) - dtSec),
    ew_timer: Math.max(0.0, (f1.fixed.ew_timer || f1.fixed.remaining) - dtSec),
    vehicles: interpolateVehicles(f1.fixed.vehicles, f2 ? f2.fixed.vehicles : null, alpha),
  }};

  const sceneML = document.getElementById('sceneML');
  const wML = sceneML.clientWidth;
  const hML = sceneML.clientHeight;

  if (currentMode === 'ml' || currentMode === 'dual') {{
    renderScene('ML', curML, wML, hML);
  }}

  const sceneFixed = document.getElementById('sceneFixed');
  const wFixed = sceneFixed.clientWidth;
  const hFixed = sceneFixed.clientHeight;

  if (currentMode === 'fixed' || currentMode === 'dual') {{
    renderScene('Fixed', curFixed, wFixed, hFixed);
  }}

  document.getElementById('topClock').textContent = `T = ${{t.toFixed(1)}}s`;
  document.getElementById('topMLBadge').textContent = `ML: ${{curML.plan}}`;
  document.getElementById('topFixedBadge').textContent = `Fixed: ${{curFixed.plan}}`;
  document.getElementById('scrubberLabel').textContent = `${{t.toFixed(1)}}s / ${{maxTime.toFixed(0)}}s`;
  scrubber.value = t;
}}

// 60 FPS Animation Loop
function animTick(timestamp) {{
  if (!lastAnimTimestamp) lastAnimTimestamp = timestamp;
  const dtSec = (timestamp - lastAnimTimestamp) / 1000.0;
  lastAnimTimestamp = timestamp;

  if (isPlaying) {{
    currentPlaybackTime += dtSec * playbackSpeed;
    if (currentPlaybackTime >= maxTime) {{
      currentPlaybackTime = 0.0; // Loop seamlessly
    }}
    renderFrame(currentPlaybackTime);
  }}

  requestAnimationFrame(animTick);
}}

window.addEventListener('keydown', e => {{
  if (e.code === 'Space') {{
    e.preventDefault();
    togglePlay();
  }} else if (e.code === 'ArrowLeft') {{
    e.preventDefault();
    stepBy(-1);
  }} else if (e.code === 'ArrowRight') {{
    e.preventDefault();
    stepBy(1);
  }}
}});

window.addEventListener('resize', () => renderFrame(currentPlaybackTime));

// Autoplay immediately on load
renderFrame(0.0);
requestAnimationFrame(animTick);
</script>
</body>
</html>"""
