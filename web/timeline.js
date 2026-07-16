/**
 * Starship mission timeline — elastic spacing + smooth animated marker.
 *
 * Usage:
 *   const timeline = initTimeline(document.getElementById("timeline"));
 *   // on every websocket message:
 *   timeline.update(state);   // state = { milestones, t_seconds, server_time }
 *
 * How the "zoom by density" effect works
 * ----------------------------------------
 * Instead of placing milestones at a position proportional to their raw
 * time (which would squash 8 events that happen within 200s near liftoff
 * into a few pixels, and waste huge empty space on the 600s gap before
 * deploy), each gap between consecutive milestones is mapped through
 * sqrt(dt). sqrt is concave, so small gaps get proportionally MORE pixels
 * per second than large gaps — dense clusters visually spread out,
 * long quiet stretches visually compress. No manual per-event tuning
 * needed; it falls out of the data automatically.
 */

function buildElasticScale(milestones, { minGap = 36, gapScale = 6, gapPower = 0.5 } = {}) {
  const sorted = [...milestones].sort((a, b) => a.time - b.time);
  const points = [];
  let vx = 0;
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0) {
      const dt = Math.max(1, sorted[i].time - sorted[i - 1].time);
      vx += minGap + gapScale * Math.pow(dt, gapPower);
    }
    points.push({ ...sorted[i], vx });
  }
  return { points, totalVx: vx || 1 };
}

// Continuous time -> virtual-x, interpolating within whichever segment
// the given time falls in (clamped at both ends of the mission).
function timeToVx(points, t) {
  if (t <= points[0].time) return points[0].vx;
  if (t >= points[points.length - 1].time) return points[points.length - 1].vx;
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    if (t >= a.time && t <= b.time) {
      const frac = (t - a.time) / (b.time - a.time || 1);
      return a.vx + frac * (b.vx - a.vx);
    }
  }
  return points[points.length - 1].vx;
}

export function initTimeline(container) {
  const RING_OUTER = 10;
  const RING_STROKE = 3;
  const RING_INNER = RING_OUTER - RING_STROKE; // player marker matches this
  const TRACK_Y = 40;
  const PADDING = 60;

  container.innerHTML = `
    <div class="tl-scroll">
      <svg class="tl-svg" preserveAspectRatio="none"></svg>
    </div>
    <div class="tl-next-label"></div>
  `;
  const scrollEl = container.querySelector(".tl-scroll");
  const svg = container.querySelector(".tl-svg");
  const nextLabel = container.querySelector(".tl-next-label");

  let scale = null;       // { points, totalVx }
  let latestState = null; // last message from the server
  let receivedAtMs = 0;   // client Date.now() when latestState arrived
  let rafId = null;
  let lastEstT = null;    // most recently rendered "current" time, for UI sync

  // ---- Debug / manual time override -------------------------------------
  // When debugTime !== null, the timeline ignores live server data and
  // uses this instead. debugPlaying lets it auto-advance for scrubbing
  // through the whole mission without dragging by hand.
  let debugTime = null;
  let debugPlaying = false;
  let debugSpeed = 1;
  let lastFrameMs = null;

  function render() {
    if (!scale) return;
    const { points, totalVx } = scale;
    const width = totalVx + PADDING * 2;
    const height = 112;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);

    // Estimate "now" between server ticks so the marker glides instead
    // of jumping every 500ms — unless a manual debug time is active,
    // in which case that always wins.
    let estT;
    if (debugTime !== null) {
      estT = debugTime;
    } else if (latestState) {
      const elapsedSinceUpdate = (Date.now() - receivedAtMs) / 1000;
      estT = latestState.t_seconds + elapsedSinceUpdate;
    } else {
      estT = points[0].time;
    }
    lastEstT = estT;
    const markerVx = timeToVx(points, estT) + PADDING;

    let svgParts = [];
    svgParts.push(
      `<line x1="${PADDING}" y1="${TRACK_Y}" x2="${width - PADDING}" y2="${TRACK_Y}"
             stroke="var(--tl-line, #e6edf3)" stroke-width="2" opacity="0.35" />`
    );

    let nextMilestone = null;
    let lastLabelX = -Infinity;
    const MIN_LABEL_GAP = 46; // px between label centers before we skip one

    for (const p of points) {
      const x = p.vx + PADDING;
      const passed = p.time <= estT;
      if (!passed && !nextMilestone) nextMilestone = p;

      if (passed) {
        svgParts.push(
          `<circle cx="${x}" cy="${TRACK_Y}" r="${RING_INNER}" fill="var(--tl-line, #e6edf3)" opacity="0.9">
             <title>${escapeXml(p.name)}</title>
           </circle>`
        );
      } else {
        svgParts.push(
          `<circle cx="${x}" cy="${TRACK_Y}" r="${RING_OUTER}" fill="none"
                   stroke="var(--tl-line, #e6edf3)" stroke-width="${RING_STROKE}" opacity="0.55">
             <title>${escapeXml(p.name)}</title>
           </circle>`
        );
      }

      // In dense clusters, skip labels that would overlap the previous
      // one; the circle + hover tooltip (<title>) are still there.
      const showLabel = x - lastLabelX >= MIN_LABEL_GAP;
      if (showLabel) {
        lastLabelX = x;
        const [line1, line2, line3] = wrapLabel(p.name);
        svgParts.push(
          `<text x="${x}" y="${TRACK_Y + 24}" font-size="9" fill="var(--tl-label, #7d8590)"
                 text-anchor="middle">
             <tspan x="${x}" dy="0">${escapeXml(line1)}</tspan>
             ${line2 ? `<tspan x="${x}" dy="11">${escapeXml(line2)}</tspan>` : ""}
             ${line3 ? `<tspan x="${x}" dy="11">${escapeXml(line3)}</tspan>` : ""}
           </text>`
        );
      }
    }

    // Player marker — sized to nest inside a hollow ring.
    svgParts.push(
      `<circle cx="${markerVx}" cy="${TRACK_Y}" r="${RING_INNER}" fill="var(--tl-marker, #58a6ff)" />`
    );

    svg.innerHTML = svgParts.join("");

    // Keep the marker roughly centered in the visible viewport.
    const viewportWidth = scrollEl.clientWidth;
    const targetScroll = Math.max(0, markerVx - viewportWidth / 2);
    scrollEl.scrollTo({ left: targetScroll, behavior: "auto" });

    if (nextMilestone) {
      const remaining = nextMilestone.time - estT;
      nextLabel.textContent =
        remaining >= 0
          ? `Next: ${nextMilestone.name} in ${formatSeconds(remaining)}`
          : `Next: ${nextMilestone.name}`;
    } else {
      nextLabel.textContent = "";
    }
  }

  function loop() {
    const now = performance.now();
    if (debugPlaying && debugTime !== null && scale) {
      if (lastFrameMs !== null) {
        const dt = (now - lastFrameMs) / 1000;
        const maxT = scale.points[scale.points.length - 1].time;
        debugTime = Math.min(maxT, debugTime + dt * debugSpeed);
        if (debugTime >= maxT) debugPlaying = false; // auto-stop at end of mission
      }
      lastFrameMs = now;
    } else {
      lastFrameMs = null;
    }
    render();
    rafId = requestAnimationFrame(loop);
  }

  function update(state) {
    if (!state || !state.milestones) return;
    const list = Array.isArray(state.milestones)
      ? state.milestones
      : state.milestones.CountdownMilestones || [];
    if (list.length === 0) return;

    // Only rebuild the elastic scale if the milestone set actually changed
    // (cheap identity check on length + first/last time is enough here).
    if (!scale || scale.points.length !== list.length) {
      scale = buildElasticScale(list);
    }

    latestState = state;
    receivedAtMs = Date.now();

    if (!rafId) loop();
  }

  function destroy() {
    if (rafId) cancelAnimationFrame(rafId);
  }

  // ---- Debug API ----------------------------------------------------------
  function setDebugTime(t) {
    debugTime = t;
    if (!rafId) loop(); // in case update() was never called with live data yet
  }
  function clearDebugTime() {
    debugTime = null;
    debugPlaying = false;
  }
  function setDebugPlaying(playing, speed = 1) {
    debugPlaying = playing;
    debugSpeed = speed;
    lastFrameMs = null;
  }
  function isDebugPlaying() {
    return debugPlaying;
  }
  function getEstimatedTime() {
    return lastEstT;
  }
  function getTimeBounds() {
    if (!scale) return null;
    return { min: scale.points[0].time, max: scale.points[scale.points.length - 1].time };
  }

  return {
    update,
    destroy,
    setDebugTime,
    clearDebugTime,
    setDebugPlaying,
    isDebugPlaying,
    getEstimatedTime,
    getTimeBounds,
  };
}

// Splits a milestone name onto at most three lines, breaking on word
// boundaries, instead of truncating with "...". Falls back to fewer
// lines if the name already fits.
function wrapLabel(name, maxLineLen = 6) {
  const words = name.split(" ");
  let lines = ["", "", ""];
  for (const w of words) {
    let placed = false;
    for (let i = 0; i < lines.length; i++) {
      if (!lines[i] || (lines[i] + " " + w).trim().length <= maxLineLen) {
        lines[i] = (lines[i] + " " + w).trim();
        placed = true;
        break;
      }
    }
    if (!placed) {
      // Every line is full — overflow onto the last line rather than
      // silently dropping the word.
      lines[lines.length - 1] = (lines[lines.length - 1] + " " + w).trim();
    }
  }
  return lines;
}

function formatSeconds(s) {
  const abs = Math.abs(Math.round(s));
  const hh = Math.floor(abs / 3600);
  const mm = String(Math.floor((abs % 3600) / 60)).padStart(2, "0");
  const ss = String(abs % 60).padStart(2, "0");
  if (hh > 0) {
    return `${hh}:${mm}:${ss}`;
  }
  return `${mm}:${ss}`;
}

function escapeXml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;",
  }[c]));
}