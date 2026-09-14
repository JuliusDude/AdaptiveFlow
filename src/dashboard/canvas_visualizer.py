"""Hardware-accelerated 60 FPS HTML5 Canvas / SVG 4-Way Intersection Visualizer.

Implements a photorealistic top-down intersection inspired by modern design systems
and realistic intersection geometries, driven by true vehicle physics and ML signal timing.
Supports full Play, Pause, Rewind, Forward, Timeline Scrubbing, Speed Controls, and
Side-by-Side Dual Arena comparative inspection.
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
    --grass: #1b261a;
    --grass2: #243323;
    --road: #1f2329;
    --road2: #181b20;
    --lane: #eedb96;
    --stop: #f5f2e8;
    --cyan: #00f0ff;
    --emerald: #10b981;
    --amber: #ffbd2e;
    --red: #ff453a;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; user-select: none; }}
  html, body {{
    width: 100%; height: 100%;
    overflow: hidden;
    background: var(--bg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #e2e8f0;
  }}

  /* Outer container */
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

  /* Viewport Canvas Stage */
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

  /* Intersection Scene Graphics */
  .intersection-scene {{
    position: relative;
    width: 100%;
    height: 100%;
    min-width: 500px;
    min-height: 480px;
    background:
      radial-gradient(circle at 50% 50%, rgba(24, 32, 40, 0.4), transparent 70%),
      var(--grass);
    overflow: hidden;
  }}

  /* Terrain texture dots */
  .intersection-scene::before {{
    content: "";
    position: absolute; inset: 0;
    opacity: 0.18;
    background-image:
      radial-gradient(circle at 14% 32%, #688a54 0 1px, transparent 1.5px),
      radial-gradient(circle at 68% 14%, #5b794a 0 1px, transparent 1.5px),
      radial-gradient(circle at 36% 82%, #648251 0 1px, transparent 1.5px),
      radial-gradient(circle at 84% 61%, #72965c 0 1px, transparent 1.5px);
    background-size: 52px 61px, 71px 67px, 64px 49px, 79px 53px;
  }}

  /* Sidewalks & Curbstone */
  .curb-quadrant {{
    position: absolute;
    width: calc(50% - 90px);
    height: calc(50% - 90px);
    background: #1e2329;
    border: 2px solid #323842;
    z-index: 2;
  }}
  .curb-nw {{ top: 0; left: 0; border-bottom-right-radius: 24px; }}
  .curb-ne {{ top: 0; right: 0; border-bottom-left-radius: 24px; }}
  .curb-sw {{ bottom: 0; left: 0; border-top-right-radius: 24px; }}
  .curb-se {{ bottom: 0; right: 0; border-top-left-radius: 24px; }}

  /* Asphalt roads */
  .road-h, .road-v {{
    position: absolute;
    background: linear-gradient(90deg, var(--road2), var(--road) 50%, var(--road2));
    box-shadow: 0 0 0 1px rgba(0,0,0,0.4), inset 0 0 24px rgba(0,0,0,0.3);
    z-index: 1;
  }}
  .road-h {{
    left: 0; right: 0; top: 50%;
    height: 180px;
    transform: translateY(-50%);
  }}
  .road-v {{
    top: 0; bottom: 0; left: 50%;
    width: 180px;
    transform: translateX(-50%);
    background: linear-gradient(180deg, var(--road2), var(--road) 50%, var(--road2));
  }}

  /* Center junction patch */
  .center-junction {{
    position: absolute; left: 50%; top: 50%;
    width: 180px; height: 180px;
    transform: translate(-50%, -50%);
    background: #252a32;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
    z-index: 1;
  }}
  .center-box {{
    position: absolute; left: 50%; top: 50%;
    width: 70px; height: 70px;
    transform: translate(-50%, -50%);
    border-radius: 10px;
    background: #2c323c;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.04), inset 0 0 12px rgba(0,0,0,0.3);
    z-index: 2;
  }}

  /* Dashed lane dividers */
  .dashline {{
    position: absolute;
    opacity: 0.65;
    z-index: 3;
  }}
  .dashline.h {{
    left: 0; right: 0; height: 2px;
    background: repeating-linear-gradient(90deg, var(--lane) 0 16px, transparent 16px 32px);
  }}
  .dashline.v {{
    top: 0; bottom: 0; width: 2px;
    background: repeating-linear-gradient(180deg, var(--lane) 0 16px, transparent 16px 32px);
  }}
  .dashline.h.top {{ top: calc(50% - 45px); }}
  .dashline.h.bot {{ top: calc(50% + 45px); }}
  .dashline.v.left {{ left: calc(50% - 45px); }}
  .dashline.v.right {{ left: calc(50% + 45px); }}

  /* Yellow Center Double Lines */
  .center-stripe {{
    position: absolute;
    background: var(--lane);
    opacity: 0.85;
    z-index: 3;
  }}
  .center-stripe.v1 {{ top: 0; bottom: calc(50% + 90px); left: calc(50% - 2px); width: 2px; }}
  .center-stripe.v2 {{ top: calc(50% + 90px); bottom: 0; left: calc(50% - 2px); width: 2px; }}
  .center-stripe.h1 {{ left: 0; right: calc(50% + 90px); top: calc(50% - 2px); height: 2px; }}
  .center-stripe.h2 {{ left: calc(50% + 90px); right: 0; top: calc(50% - 2px); height: 2px; }}

  /* Stop bars */
  .stopbar {{
    position: absolute;
    background: var(--stop);
    box-shadow: 0 1px 3px rgba(0,0,0,0.5);
    z-index: 4;
  }}
  .stopbar.n {{ left: 50%; top: calc(50% - 95px); width: 90px; height: 5px; }}
  .stopbar.s {{ left: calc(50% - 90px); top: calc(50% + 90px); width: 90px; height: 5px; }}
  .stopbar.w {{ left: calc(50% - 95px); top: 50%; width: 5px; height: 90px; }}
  .stopbar.e {{ left: calc(50% + 90px); top: calc(50% - 90px); width: 5px; height: 90px; }}

  /* Zebra Crosswalks */
  .cross {{
    position: absolute;
    display: flex;
    gap: 4px;
    z-index: 3;
  }}
  .cross span {{
    background: #f1eddb;
    opacity: 0.75;
    box-shadow: 0 0 1px rgba(0,0,0,0.4);
  }}
  .cross.n {{ left: 50%; top: calc(50% - 125px); width: 90px; height: 24px; }}
  .cross.n span {{ width: 5px; height: 24px; }}
  .cross.s {{ left: calc(50% - 90px); top: calc(50% + 101px); width: 90px; height: 24px; }}
  .cross.s span {{ width: 5px; height: 24px; }}
  .cross.w {{ left: calc(50% - 125px); top: 50%; width: 24px; height: 90px; flex-direction: column; }}
  .cross.w span {{ width: 24px; height: 5px; }}
  .cross.e {{ left: calc(50% + 101px); top: calc(50% - 90px); width: 24px; height: 90px; flex-direction: column; }}
  .cross.e span {{ width: 24px; height: 5px; }}

  /* Directional Lane Arrows */
  .arrow {{
    position: absolute;
    color: rgba(255, 255, 255, 0.35);
    font-size: 18px;
    font-weight: bold;
    z-index: 3;
    pointer-events: none;
  }}
  .arrow.n {{ left: calc(50% + 20px); top: calc(50% - 160px); transform: rotate(180deg); }}
  .arrow.s {{ left: calc(50% - 35px); top: calc(50% + 140px); }}
  .arrow.w {{ left: calc(50% - 160px); top: calc(50% + 20px); transform: rotate(90deg); }}
  .arrow.e {{ left: calc(50% + 140px); top: calc(50% - 35px); transform: rotate(-90deg); }}

  /* Physical 3-Lamp Traffic Signal Heads */
  .signal {{
    position: absolute;
    width: 20px;
    height: 54px;
    border-radius: 6px;
    background: linear-gradient(#1c2024, #0d0f12);
    border: 1.5px solid #383f47;
    box-shadow: 0 4px 10px rgba(0,0,0,0.6), inset 0 0 6px rgba(255,255,255,0.06);
    z-index: 30;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-evenly;
    padding: 2px 0;
  }}
  .signal .lamp {{
    width: 10px; height: 10px;
    border-radius: 50%;
    background: #23272c;
    border: 1px solid #111417;
    box-shadow: inset 0 0 2px #000;
    transition: all 0.15s ease;
  }}
  .signal.red-on .lamp.red {{ background: var(--red); box-shadow: 0 0 12px var(--red), 0 0 4px #fff; }}
  .signal.yellow-on .lamp.yellow {{ background: var(--amber); box-shadow: 0 0 12px var(--amber), 0 0 4px #fff; }}
  .signal.green-on .lamp.green {{ background: var(--emerald); box-shadow: 0 0 12px var(--emerald), 0 0 4px #fff; }}

  /* Signal Positions on Intersection Corners */
  .signal.n {{ top: calc(50% - 145px); left: calc(50% + 96px); }}
  .signal.s {{ top: calc(50% + 95px); left: calc(50% - 116px); }}
  .signal.w {{ top: calc(50% + 95px); left: calc(50% - 145px); transform: rotate(90deg); }}
  .signal.e {{ top: calc(50% - 145px); left: calc(50% + 95px); transform: rotate(-90deg); }}

  /* Floating Signal Countdown Badges */
  .sig-timer {{
    position: absolute;
    background: rgba(15, 20, 26, 0.85);
    backdrop-filter: blur(6px);
    border: 1px solid rgba(255,255,255,0.12);
    padding: 1px 6px;
    border-radius: 6px;
    font-size: 10px;
    font-family: monospace;
    font-weight: 700;
    color: #fff;
    z-index: 35;
    pointer-events: none;
  }}
  .sig-timer.n {{ top: calc(50% - 165px); left: calc(50% + 88px); }}
  .sig-timer.s {{ top: calc(50% + 155px); left: calc(50% - 120px); }}
  .sig-timer.w {{ top: calc(50% + 145px); left: calc(50% - 165px); }}
  .sig-timer.e {{ top: calc(50% - 175px); left: calc(50% + 115px); }}

  /* Vehicles */
  .car-layer {{
    position: absolute; inset: 0;
    pointer-events: none;
    z-index: 20;
  }}
  .car {{
    position: absolute;
    width: 38px;
    height: 19px;
    border-radius: 6px;
    transform-origin: center center;
    box-shadow: 0 3px 6px rgba(0,0,0,0.5);
    transition: transform 0.05s linear;
  }}
  /* Windshield & Cabin Glass */
  .car::before {{
    content: "";
    position: absolute; left: 7px; right: 7px; top: 3px; height: 13px;
    border-radius: 4px;
    background: linear-gradient(90deg, rgba(255,255,255,0.35), rgba(255,255,255,0.08));
    border: 1px solid rgba(255,255,255,0.18);
  }}
  /* Roof panel */
  .car::after {{
    content: "";
    position: absolute; left: 12px; right: 12px; top: 4px; height: 6px;
    border-radius: 2px;
    background: rgba(0, 0, 0, 0.4);
  }}
  /* Dynamic Brake Lights */
  .car .brake-light {{
    position: absolute;
    left: 1px;
    width: 3px;
    height: 4px;
    border-radius: 1px;
    background: #600;
    transition: all 0.15s ease;
  }}
  .car .bl-top {{ top: 2px; }}
  .car .bl-bot {{ bottom: 2px; }}
  .car.braking .brake-light {{
    background: #ff2200;
    box-shadow: -2px 0 6px #ff2200;
  }}
  /* Headlights */
  .car .headlight {{
    position: absolute;
    right: 1px;
    width: 3px;
    height: 4px;
    border-radius: 1px;
    background: #fff9d6;
    box-shadow: 2px 0 6px rgba(255, 245, 180, 0.8);
  }}
  .car .hl-top {{ top: 2px; }}
  .car .hl-bot {{ bottom: 2px; }}

  /* Car Color Variants */
  .car.c-blue {{ background: linear-gradient(90deg, #1e3a8a, #3b82f6); }}
  .car.c-cyan {{ background: linear-gradient(90deg, #0e7490, #06b6d4); }}
  .car.c-emerald {{ background: linear-gradient(90deg, #065f46, #10b981); }}
  .car.c-red {{ background: linear-gradient(90deg, #991b1b, #ef4444); }}
  .car.c-amber {{ background: linear-gradient(90deg, #b45309, #f59e0b); }}
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
    z-index: 50;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
    min-width: 190px;
  }}
  .hud-title {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: #94a3b8;
  }}
  .hud-plan {{
    font-size: 16px;
    font-weight: 800;
    color: #fff;
    margin: 2px 0 6px 0;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .hud-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11px;
    color: #cbd5e1;
    margin-top: 3px;
  }}
  .hud-dot {{
    width: 7px; height: 7px;
    border-radius: 50%;
    display: inline-block;
  }}

  /* Bottom Floating Playback Dock */
  .playback-dock {{
    position: absolute;
    bottom: 14px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(13, 17, 25, 0.92);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 28px;
    padding: 8px 18px;
    display: flex;
    align-items: center;
    gap: 12px;
    z-index: 100;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.5);
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
    font-family: monospace;
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
    background: rgba(255, 255, 255, 0.12);
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

        <!-- Lane Dashes -->
        <div class="dashline h top"></div>
        <div class="dashline h bot"></div>
        <div class="dashline v left"></div>
        <div class="dashline v right"></div>

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

        <!-- Approach Arrows -->
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
            <span>Remaining:</span>
            <strong id="hudML_Remaining">18.0s</strong>
          </div>
          <div class="hud-row">
            <span>Avg Delay:</span>
            <strong id="hudML_Delay" style="color: #34d399;">0.0s</strong>
          </div>
          <div class="hud-row">
            <span>Queue:</span>
            <strong id="hudML_Queue">0 veh</strong>
          </div>
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

        <!-- Lane Dashes -->
        <div class="dashline h top"></div>
        <div class="dashline h bot"></div>
        <div class="dashline v left"></div>
        <div class="dashline v right"></div>

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

        <!-- Approach Arrows -->
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
            <span>Remaining:</span>
            <strong id="hudFixed_Remaining">18.0s</strong>
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
    <button class="dock-btn primary" id="btnPlayPause" title="Play / Pause" onclick="togglePlay()">▶</button>
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
// --- Initialize Crosswalk Bars ---
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

// --- Trajectory Data ---
const frames = {playback_json};
const totalFrames = frames.length;
const maxTime = totalFrames > 0 ? frames[totalFrames - 1].t : 0;

// Playback state
let currentPlaybackTime = 0.0;
let isPlaying = false;
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

// Find interpolated frame index
function getFrameIndices(t) {{
  if (totalFrames === 0) return {{ f1: null, f2: null, alpha: 0 }};
  if (t <= frames[0].t) return {{ f1: frames[0], f2: frames[0], alpha: 0 }};
  if (t >= frames[totalFrames - 1].t) return {{ f1: frames[totalFrames - 1], f2: frames[totalFrames - 1], alpha: 0 }};

  // Binary search for efficiency
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

// Map 1D meters [0, 170] to 2D pixel coordinates inside the scene
// 0m = approach entry, 150m = stop line, 170m = exit
function mapMetersToCoords(app, pos, width, height) {{
  const cx = width / 2;
  const cy = height / 2;
  const laneOffset = 22; // px offset from center stripe to lane center

  // Distance from stop line in meters
  const distFromStop = 150.0 - pos;
  // Visual scale: 150m mapped to available approach half-span
  const approachSpan = Math.min(width, height) * 0.42;
  const pxPerMeter = (approachSpan - 45) / 150.0;

  let x = cx, y = cy, rot = 0;

  if (app === 'N') {{
    // Moves South (downwards, +y)
    x = cx + laneOffset;
    y = (cy - 95) - (distFromStop * pxPerMeter);
    rot = 90;
  }} else if (app === 'S') {{
    // Moves North (upwards, -y)
    x = cx - laneOffset;
    y = (cy + 95) + (distFromStop * pxPerMeter);
    rot = -90;
  }} else if (app === 'E') {{
    // Moves West (leftwards, -x)
    y = cy - laneOffset;
    x = (cx + 95) + (distFromStop * pxPerMeter);
    rot = 180;
  }} else if (app === 'W') {{
    // Moves East (rightwards, +x)
    y = cy + laneOffset;
    x = (cx - 95) - (distFromStop * pxPerMeter);
    rot = 0;
  }}

  return {{ x, y, rot }};
}}

function renderScene(scenePrefix, simData, width, height) {{
  if (!simData) return;

  // 1. Update Traffic Signal Lamps
  const nsColor = simData.ns_color;
  const ewColor = simData.ew_color;

  ['N', 'S'].forEach(arm => {{
    const sig = document.getElementById(`sig${{scenePrefix}}_${{arm}}`);
    if (sig) {{
      sig.className = `signal ${{arm.toLowerCase()}} ${{nsColor.toLowerCase()}}-on`;
    }}
    const timer = document.getElementById(`timer${{scenePrefix}}_${{arm}}`);
    if (timer) {{
      timer.textContent = `${{Math.ceil(simData.remaining)}}s`;
      timer.style.color = nsColor === 'GREEN' ? '#34d399' : (nsColor === 'YELLOW' ? '#ffbd2e' : '#ff453a');
    }}
  }});

  ['E', 'W'].forEach(arm => {{
    const sig = document.getElementById(`sig${{scenePrefix}}_${{arm}}`);
    if (sig) {{
      sig.className = `signal ${{arm.toLowerCase()}} ${{ewColor.toLowerCase()}}-on`;
    }}
    const timer = document.getElementById(`timer${{scenePrefix}}_${{arm}}`);
    if (timer) {{
      timer.textContent = `${{Math.ceil(simData.remaining)}}s`;
      timer.style.color = ewColor === 'GREEN' ? '#34d399' : (ewColor === 'YELLOW' ? '#ffbd2e' : '#ff453a');
    }}
  }});

  // 2. Update HUD
  const hudPlan = document.getElementById(`hud${{scenePrefix}}_Plan`);
  const hudPhase = document.getElementById(`hud${{scenePrefix}}_Phase`);
  const hudRemaining = document.getElementById(`hud${{scenePrefix}}_Remaining`);
  const hudDelay = document.getElementById(`hud${{scenePrefix}}_Delay`);
  const hudQueue = document.getElementById(`hud${{scenePrefix}}_Queue`);

  if (hudPlan) hudPlan.textContent = `Plan ${{simData.plan}} (${{simData.ns_green}}s / ${{simData.ew_green}}s)`;
  if (hudPhase) hudPhase.textContent = simData.phase_name;
  if (hudRemaining) hudRemaining.textContent = `${{simData.remaining.toFixed(1)}}s`;
  if (hudDelay) hudDelay.textContent = `${{simData.metrics.comp_delay.toFixed(1)}}s`;
  if (hudQueue) hudQueue.textContent = `${{simData.metrics.avg_queue.toFixed(1)}} veh`;

  // 3. Render Vehicles
  const carLayer = document.getElementById(`cars${{scenePrefix}}`);
  if (!carLayer) return;

  // Clear previous DOM vehicles
  carLayer.innerHTML = '';

  simData.vehicles.forEach(v => {{
    const coords = mapMetersToCoords(v.app, v.pos, width, height);

    // Skip cars off canvas view
    if (coords.x < -60 || coords.x > width + 60 || coords.y < -60 || coords.y > height + 60) {{
      return;
    }}

    const car = document.createElement('div');
    const colorClass = getCarClass(v.id);
    const isBraking = v.spd < 0.8 || v.st === 'queued';

    car.className = `car ${{colorClass}} ${{isBraking ? 'braking' : ''}}`;
    car.style.left = `${{coords.x - 19}}px`;
    car.style.top = `${{coords.y - 9.5}}px`;
    car.style.transform = `rotate(${{coords.rot}}deg)`;

    // Add lights
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

  // Interpolate vehicle positions smoothly
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

  const curML = {{
    ...f1.ml,
    vehicles: interpolateVehicles(f1.ml.vehicles, f2 ? f2.ml.vehicles : null, alpha),
  }};
  const curFixed = {{
    ...f1.fixed,
    vehicles: interpolateVehicles(f1.fixed.vehicles, f2 ? f2.fixed.vehicles : null, alpha),
  }};

  // Measure scene dimensions
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

  // Update Top Badges & Scrubber Label
  document.getElementById('topClock').textContent = `T = ${{t.toFixed(1)}}s`;
  document.getElementById('topMLBadge').textContent = `ML: ${{curML.plan}}`;
  document.getElementById('topFixedBadge').textContent = `Fixed: ${{curFixed.plan}}`;
  document.getElementById('scrubberLabel').textContent = `${{t.toFixed(1)}}s / ${{maxTime.toFixed(0)}}s`;
  scrubber.value = t;
}}

// 60 FPS Smooth Animation Loop
function animTick(timestamp) {{
  if (!lastAnimTimestamp) lastAnimTimestamp = timestamp;
  const dtSec = (timestamp - lastAnimTimestamp) / 1000.0;
  lastAnimTimestamp = timestamp;

  if (isPlaying) {{
    currentPlaybackTime += dtSec * playbackSpeed;
    if (currentPlaybackTime >= maxTime) {{
      currentPlaybackTime = maxTime;
      isPlaying = false;
      document.getElementById('btnPlayPause').textContent = '▶';
    }}
    renderFrame(currentPlaybackTime);
  }}

  requestAnimationFrame(animTick);
}}

// Keyboard Shortcuts (Space: Play/Pause, Left: Step Back, Right: Step Forward)
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

// Initial render
renderFrame(0.0);
requestAnimationFrame(animTick);
</script>
</body>
</html>"""
