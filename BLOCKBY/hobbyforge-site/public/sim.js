(function () {
  const sim = {
    canvas: null,
    ctx: null,
    data: null,
    mode: "block",
    drag: false,
    last: { x: 0, y: 0 },
    view: { rotX: -0.55, rotY: 0.75, zoom: 1, panX: 0, panY: 0 }
  };

  const $ = (selector) => document.querySelector(selector);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setInfo(html) {
    const panel = $("#assetInfo");
    if (panel) panel.innerHTML = html;
  }

  function stat(label, value) {
    return `<div class="asset-stat"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
  }

  function clearCanvas() {
    const { canvas, ctx } = sim;
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const g = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
    g.addColorStop(0, "#fffaf0");
    g.addColorStop(1, "#ead7bd");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.strokeStyle = "rgba(92, 60, 32, 0.08)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 32) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 32) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
    ctx.restore();
  }

  function roundRect(ctx, x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.arcTo(x + w, y, x + w, y + h, rr);
    ctx.arcTo(x + w, y + h, x, y + h, rr);
    ctx.arcTo(x, y + h, x, y, rr);
    ctx.arcTo(x, y, x + w, y, rr);
    ctx.closePath();
  }

  function drawCard(ctx, x, y, w, h, title, subtitle, options = {}) {
    ctx.save();
    ctx.shadowColor = "rgba(64,38,18,0.14)";
    ctx.shadowBlur = 20;
    ctx.shadowOffsetY = 8;
    ctx.fillStyle = options.fill || "#fff8ec";
    ctx.strokeStyle = options.stroke || "rgba(139,94,52,0.45)";
    ctx.lineWidth = 2;
    roundRect(ctx, x, y, w, h, 18);
    ctx.fill();
    ctx.shadowColor = "transparent";
    ctx.stroke();
    ctx.fillStyle = "#2d2118";
    ctx.textAlign = "center";
    ctx.font = "800 17px system-ui";
    ctx.fillText(String(title || "Block").slice(0, 24), x + w / 2, y + 31);
    ctx.fillStyle = "#766555";
    ctx.font = "600 12px system-ui";
    ctx.fillText(String(subtitle || "").slice(0, 32), x + w / 2, y + 55);
    ctx.restore();
  }

  function arrow(ctx, x1, y1, x2, y2, label = "") {
    ctx.save();
    ctx.strokeStyle = "#5f7f52";
    ctx.fillStyle = "#5f7f52";
    ctx.lineWidth = 4;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();

    const angle = Math.atan2(y2 - y1, x2 - x1);
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - 12 * Math.cos(angle - 0.5), y2 - 12 * Math.sin(angle - 0.5));
    ctx.lineTo(x2 - 12 * Math.cos(angle + 0.5), y2 - 12 * Math.sin(angle + 0.5));
    ctx.closePath();
    ctx.fill();

    if (label) {
      ctx.fillStyle = "#385a32";
      ctx.font = "800 13px system-ui";
      ctx.textAlign = "center";
      ctx.fillText(label, (x1 + x2) / 2, (y1 + y2) / 2 - 10);
    }
    ctx.restore();
  }

  function componentKind(component) {
    const ref = String(component.ref || "").toUpperCase();
    const value = String(component.value || component.lib || "").toLowerCase();
    if (/^(BT|BATT|J|USB|PWR)/.test(ref) || value.includes("battery") || value.includes("usb") || value.includes("power")) return "power";
    if (/^(U|IC|A)/.test(ref) || value.includes("esp") || value.includes("arduino") || value.includes("mcu") || value.includes("micro")) return "controller";
    if (/^(R|C|L)/.test(ref)) return "passive";
    if (/^(D|LED)/.test(ref) || value.includes("led") || value.includes("display")) return "output";
    if (/^(SW|S|K)/.test(ref) || value.includes("switch") || value.includes("button") || value.includes("sensor")) return "input";
    if (/^(Q|M|DRV)/.test(ref) || value.includes("driver")) return "driver";
    return "other";
  }

  function parseSchematic(text, name = "schematic") {
    const components = [];
    const wires = [];
    const labels = [];

    const symbolRegex = /\(symbol\s+\(lib_id\s+"([^"]+)"\)([\s\S]*?)(?=\n\s*\((?:symbol|wire|label|junction)|\n\s*\)\s*$)/g;
    let match;
    while ((match = symbolRegex.exec(text))) {
      const lib = match[1];
      const body = match[2];
      const at = body.match(/\(at\s+([-\d.]+)\s+([-\d.]+)/);
      const ref = body.match(/\(property\s+"Reference"\s+"([^"]+)"/);
      const value = body.match(/\(property\s+"Value"\s+"([^"]+)"/);
      components.push({
        lib,
        ref: ref ? ref[1] : lib.split(":").pop(),
        value: value ? value[1] : lib,
        x: at ? Number(at[1]) : 0,
        y: at ? Number(at[2]) : 0
      });
    }

    const wireRegex = /\(wire\s+\(pts\s+\(xy\s+([-\d.]+)\s+([-\d.]+)\)\s+\(xy\s+([-\d.]+)\s+([-\d.]+)\)\)\)/g;
    while ((match = wireRegex.exec(text))) {
      wires.push({ x1: Number(match[1]), y1: Number(match[2]), x2: Number(match[3]), y2: Number(match[4]) });
    }

    const labelRegex = /\(label\s+"([^"]+)"\s+\(at\s+([-\d.]+)\s+([-\d.]+)/g;
    while ((match = labelRegex.exec(text))) {
      labels.push({ text: match[1], x: Number(match[2]), y: Number(match[3]) });
    }

    if (!components.length) {
      const refs = Array.from(new Set((text.match(/\b(?:R|C|L|D|LED|U|IC|J|SW|Q)\d+\b/gi) || []).map((value) => value.toUpperCase())));
      refs.forEach((ref, index) => {
        components.push({ ref, value: ref, lib: "legacy/plain", x: 20 + (index % 5) * 24, y: 20 + Math.floor(index / 5) * 18 });
      });
    }

    const groups = { power: [], controller: [], input: [], driver: [], output: [], passive: [], other: [] };
    components.forEach((component) => groups[componentKind(component)].push(component));

    const checks = [];
    const allText = text.toLowerCase();
    if (!/(gnd|ground)/.test(allText)) checks.push("No obvious ground label found.");
    if (!/(3v3|5v|vcc|power|vbat)/.test(allText)) checks.push("No obvious power label found.");
    if (!components.length) checks.push("No components were detected by the lightweight parser.");
    if (!wires.length) checks.push("No wires were detected by the lightweight parser.");

    return { type: "schematic", name, text, components, wires, labels, groups, checks };
  }

  function renderSchematicBlock(data) {
    const { ctx, canvas } = sim;
    clearCanvas();
    const blocks = [
      { id: "power", title: "Power", items: data.groups.power, subtitle: "supply / connectors", fill: "#fff3dd" },
      { id: "controller", title: "Controller", items: data.groups.controller, subtitle: "MCU / logic", fill: "#f2f8e9" },
      { id: "input", title: "Inputs", items: data.groups.input, subtitle: "sensors / switches", fill: "#fff8ec" },
      { id: "driver", title: "Drivers", items: data.groups.driver, subtitle: "transistors / modules", fill: "#fff8ec" },
      { id: "output", title: "Outputs", items: data.groups.output, subtitle: "LEDs / display", fill: "#fff8ec" },
      { id: "passive", title: "Passives", items: data.groups.passive, subtitle: "R / C / L", fill: "#fff8ec" },
      { id: "other", title: "Other", items: data.groups.other, subtitle: "uncategorised", fill: "#fff8ec" }
    ].filter((block) => block.items.length);

    if (!blocks.length) {
      ctx.fillStyle = "#766555";
      ctx.font = "700 22px system-ui";
      ctx.textAlign = "center";
      ctx.fillText("No schematic blocks detected", canvas.width / 2, canvas.height / 2);
      return;
    }

    const boxW = 210;
    const boxH = 86;
    const gapX = 72;
    const gapY = 70;
    const centerX = canvas.width / 2 + sim.view.panX;
    const startY = 88 + sim.view.panY;

    const positions = {};
    const power = blocks.find((b) => b.id === "power");
    const controller = blocks.find((b) => b.id === "controller") || blocks[0];
    const inputs = blocks.filter((b) => ["input", "passive"].includes(b.id));
    const outputs = blocks.filter((b) => ["driver", "output", "other"].includes(b.id));

    let y = startY;
    if (power) {
      positions[power.id] = { x: centerX - boxW / 2, y };
      y += boxH + gapY;
    }
    positions[controller.id] = { x: centerX - boxW / 2, y };

    inputs.forEach((block, index) => {
      positions[block.id] = { x: centerX - boxW - gapX - (index % 2) * 12, y: y + (index - (inputs.length - 1) / 2) * (boxH + 22) };
    });
    outputs.forEach((block, index) => {
      positions[block.id] = { x: centerX + gapX, y: y + (index - (outputs.length - 1) / 2) * (boxH + 22) };
    });

    ctx.save();
    if (power) arrow(ctx, centerX, positions[power.id].y + boxH, centerX, positions[controller.id].y - 8, "power");
    inputs.forEach((block) => arrow(ctx, positions[block.id].x + boxW, positions[block.id].y + boxH / 2, positions[controller.id].x - 8, positions[controller.id].y + boxH / 2, "signal"));
    outputs.forEach((block) => arrow(ctx, positions[controller.id].x + boxW, positions[controller.id].y + boxH / 2, positions[block.id].x - 8, positions[block.id].y + boxH / 2, "control"));

    blocks.forEach((block) => {
      const pos = positions[block.id];
      if (!pos) return;
      const refs = block.items.map((item) => item.ref).slice(0, 6).join(", ");
      drawCard(ctx, pos.x, pos.y, boxW, boxH, block.title, refs || block.subtitle, { fill: block.fill });
    });
    ctx.restore();
  }

  function schematicBounds(data) {
    const points = [];
    data.components.forEach((c) => points.push([c.x, c.y]));
    data.wires.forEach((w) => { points.push([w.x1, w.y1]); points.push([w.x2, w.y2]); });
    data.labels.forEach((l) => points.push([l.x, l.y]));
    if (!points.length) return { minX: 0, minY: 0, maxX: 100, maxY: 100 };
    return {
      minX: Math.min(...points.map((p) => p[0])),
      minY: Math.min(...points.map((p) => p[1])),
      maxX: Math.max(...points.map((p) => p[0])),
      maxY: Math.max(...points.map((p) => p[1]))
    };
  }

  function renderSchematicRaw(data) {
    const { ctx, canvas } = sim;
    clearCanvas();
    const b = schematicBounds(data);
    const w = Math.max(1, b.maxX - b.minX);
    const h = Math.max(1, b.maxY - b.minY);
    const scale = Math.min((canvas.width - 160) / w, (canvas.height - 160) / h) * sim.view.zoom;
    const ox = canvas.width / 2 - ((b.minX + b.maxX) / 2) * scale + sim.view.panX;
    const oy = canvas.height / 2 - ((b.minY + b.maxY) / 2) * scale + sim.view.panY;
    const sx = (x) => x * scale + ox;
    const sy = (y) => y * scale + oy;

    ctx.save();
    ctx.strokeStyle = "#5f7f52";
    ctx.lineWidth = 3;
    data.wires.forEach((wire) => {
      ctx.beginPath();
      ctx.moveTo(sx(wire.x1), sy(wire.y1));
      ctx.lineTo(sx(wire.x2), sy(wire.y2));
      ctx.stroke();
    });

    data.components.forEach((component) => {
      drawCard(ctx, sx(component.x) - 48, sy(component.y) - 28, 96, 56, component.ref, component.value, { fill: "#fffaf0" });
    });

    ctx.fillStyle = "#8b5e34";
    ctx.font = "800 14px system-ui";
    data.labels.forEach((label) => ctx.fillText(label.text, sx(label.x) + 6, sy(label.y) - 6));
    ctx.restore();
  }

  function renderSchematic(data) {
    if (sim.mode === "raw") renderSchematicRaw(data);
    else renderSchematicBlock(data);
  }

  function parsePcb(text, name = "pcb") {
    const rects = [];
    const lines = [];
    const footprints = [];

    let match;
    const rectRegex = /\(gr_rect\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)/g;
    while ((match = rectRegex.exec(text))) {
      rects.push({ x1: Number(match[1]), y1: Number(match[2]), x2: Number(match[3]), y2: Number(match[4]) });
    }

    const lineRegex = /\(gr_line\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+\(end\s+([-\d.]+)\s+([-\d.]+)\)/g;
    while ((match = lineRegex.exec(text))) {
      lines.push({ x1: Number(match[1]), y1: Number(match[2]), x2: Number(match[3]), y2: Number(match[4]) });
    }

    const fpRegex = /\(footprint\s+"([^"]+)"([\s\S]*?)(?=\n\s*\(footprint|\n\s*\)\s*$)/g;
    while ((match = fpRegex.exec(text))) {
      const body = match[2];
      const at = body.match(/\(at\s+([-\d.]+)\s+([-\d.]+)/);
      const ref = body.match(/\(fp_text\s+reference\s+"([^"]+)"/);
      footprints.push({ lib: match[1], ref: ref ? ref[1] : match[1].split(":").pop(), x: at ? Number(at[1]) : 0, y: at ? Number(at[2]) : 0 });
    }

    const points = [];
    rects.forEach((r) => { points.push([r.x1, r.y1]); points.push([r.x2, r.y2]); });
    lines.forEach((l) => { points.push([l.x1, l.y1]); points.push([l.x2, l.y2]); });
    footprints.forEach((f) => points.push([f.x, f.y]));
    const bounds = points.length ? {
      minX: Math.min(...points.map((p) => p[0])),
      minY: Math.min(...points.map((p) => p[1])),
      maxX: Math.max(...points.map((p) => p[0])),
      maxY: Math.max(...points.map((p) => p[1]))
    } : { minX: 0, minY: 0, maxX: 80, maxY: 50 };

    return { type: "pcb", name, text, rects, lines, footprints, bounds };
  }

  function renderPcb(data) {
    const { ctx, canvas } = sim;
    clearCanvas();
    const b = data.bounds;
    const w = Math.max(1, b.maxX - b.minX);
    const h = Math.max(1, b.maxY - b.minY);
    const scale = Math.min((canvas.width - 180) / w, (canvas.height - 180) / h) * sim.view.zoom;
    const ox = canvas.width / 2 - ((b.minX + b.maxX) / 2) * scale + sim.view.panX;
    const oy = canvas.height / 2 - ((b.minY + b.maxY) / 2) * scale + sim.view.panY;
    const sx = (x) => x * scale + ox;
    const sy = (y) => y * scale + oy;

    ctx.save();
    const boardX = sx(b.minX);
    const boardY = sy(b.minY);
    const boardW = w * scale;
    const boardH = h * scale;
    ctx.fillStyle = "#5f7f52";
    ctx.strokeStyle = "#385a32";
    ctx.lineWidth = 4;
    roundRect(ctx, boardX, boardY, boardW, boardH, 22);
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = "#e7c894";
    ctx.lineWidth = 3;
    data.lines.forEach((line) => {
      ctx.beginPath();
      ctx.moveTo(sx(line.x1), sy(line.y1));
      ctx.lineTo(sx(line.x2), sy(line.y2));
      ctx.stroke();
    });

    data.footprints.forEach((fp) => {
      drawCard(ctx, sx(fp.x) - 48, sy(fp.y) - 28, 96, 56, fp.ref, fp.lib.split(":").pop(), { fill: "#fff8ec", stroke: "#e7c894" });
    });
    ctx.restore();
  }

  function parseAsciiStl(text) {
    const triangles = [];
    const vertexRegex = /vertex\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)/g;
    let verts = [];
    let match;
    while ((match = vertexRegex.exec(text))) {
      verts.push([Number(match[1]), Number(match[2]), Number(match[3])]);
      if (verts.length === 3) {
        triangles.push(verts);
        verts = [];
      }
    }
    return triangles;
  }

  function parseBinaryStl(buffer) {
    const view = new DataView(buffer);
    if (buffer.byteLength < 84) return [];
    const count = view.getUint32(80, true);
    const triangles = [];
    let offset = 84;
    for (let i = 0; i < count && offset + 50 <= buffer.byteLength; i += 1) {
      offset += 12;
      const tri = [];
      for (let v = 0; v < 3; v += 1) {
        tri.push([view.getFloat32(offset, true), view.getFloat32(offset + 4, true), view.getFloat32(offset + 8, true)]);
        offset += 12;
      }
      triangles.push(tri);
      offset += 2;
    }
    return triangles;
  }

  function normalizeTriangles(triangles) {
    const pts = triangles.flat();
    if (!pts.length) return triangles;
    const mins = [0, 1, 2].map((i) => Math.min(...pts.map((p) => p[i])));
    const maxs = [0, 1, 2].map((i) => Math.max(...pts.map((p) => p[i])));
    const center = [0, 1, 2].map((i) => (mins[i] + maxs[i]) / 2);
    const span = Math.max(...[0, 1, 2].map((i) => maxs[i] - mins[i]), 1);
    return triangles.map((tri) => tri.map((p) => [(p[0] - center[0]) / span, (p[1] - center[1]) / span, (p[2] - center[2]) / span]));
  }

  function parseStl(buffer, name = "model.stl") {
    const decoder = new TextDecoder("utf-8");
    const head = decoder.decode(buffer.slice(0, Math.min(buffer.byteLength, 400)));
    let triangles = [];
    if (/solid/i.test(head) && /facet|vertex/i.test(head)) {
      triangles = parseAsciiStl(decoder.decode(buffer));
    }
    if (!triangles.length) triangles = parseBinaryStl(buffer);
    const normalized = normalizeTriangles(triangles);
    return { type: "stl", name, triangles: normalized, originalTriangleCount: triangles.length };
  }

  function projectPoint(p) {
    const { rotX, rotY, zoom, panX, panY } = sim.view;
    let [x, y, z] = p;
    const cy = Math.cos(rotY), sy = Math.sin(rotY);
    const cx = Math.cos(rotX), sx = Math.sin(rotX);
    const x1 = x * cy + z * sy;
    const z1 = -x * sy + z * cy;
    const y1 = y * cx - z1 * sx;
    const z2 = y * sx + z1 * cx;
    const scale = 520 * zoom / (2.2 + z2);
    return [sim.canvas.width / 2 + x1 * scale + panX, sim.canvas.height / 2 - y1 * scale + panY, z2];
  }

  function renderStl(data) {
    const { ctx } = sim;
    clearCanvas();
    const tris = data.triangles.slice(0, 18000).map((tri) => {
      const pts = tri.map(projectPoint);
      const depth = pts.reduce((sum, p) => sum + p[2], 0) / 3;
      return { pts, depth };
    }).sort((a, b) => a.depth - b.depth);

    ctx.save();
    tris.forEach((tri) => {
      const [[x1, y1], [x2, y2], [x3, y3]] = tri.pts;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.lineTo(x3, y3);
      ctx.closePath();
      const shade = Math.max(205, Math.min(250, 230 + tri.depth * 24));
      ctx.fillStyle = `rgb(${shade}, ${Math.max(180, shade - 26)}, ${Math.max(130, shade - 66)})`;
      ctx.strokeStyle = "rgba(64,38,18,0.12)";
      ctx.fill();
      ctx.stroke();
    });
    ctx.restore();
  }

  function renderHome() {
    clearCanvas();
    const { ctx, canvas } = sim;
    ctx.save();
    ctx.textAlign = "center";
    ctx.fillStyle = "#3f2717";
    ctx.font = "900 34px system-ui";
    ctx.fillText("Simulation Lab", canvas.width / 2, canvas.height / 2 - 38);
    ctx.fillStyle = "#766555";
    ctx.font = "650 18px system-ui";
    ctx.fillText("Load a schematic, PCB, or STL. Schematics open as readable block diagrams by default.", canvas.width / 2, canvas.height / 2 + 2);
    ctx.restore();
  }

  function render() {
    if (!sim.data) return renderHome();
    if (sim.data.type === "schematic") return renderSchematic(sim.data);
    if (sim.data.type === "pcb") return renderPcb(sim.data);
    if (sim.data.type === "stl") return renderStl(sim.data);
    renderHome();
  }

  async function loadAssetFile(file) {
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (lower.endsWith(".stl")) {
      const data = parseStl(await file.arrayBuffer(), file.name);
      sim.data = data;
      setInfo(`
        <h4>${escapeHtml(data.name)}</h4>
        ${stat("Type", "STL model")}
        ${stat("Triangles", data.originalTriangleCount)}
        <p>Drag to rotate. Wheel to zoom. This is a lightweight viewer for demo use.</p>
      `);
    } else if (lower.endsWith(".kicad_pcb") || lower.endsWith(".pcb")) {
      const data = parsePcb(await file.text(), file.name);
      sim.data = data;
      $("#exportPcbStlBtn").disabled = false;
      setInfo(`
        <h4>${escapeHtml(data.name)}</h4>
        ${stat("Type", "PCB")}
        ${stat("Footprints", data.footprints.length)}
        ${stat("Edge lines", data.lines.length + data.rects.length)}
        <p>The PCB viewer extracts a simple board outline and footprint cards. Export creates a simple board/component STL.</p>
      `);
    } else {
      const data = parseSchematic(await file.text(), file.name);
      sim.data = data;
      $("#exportPcbStlBtn").disabled = true;
      setInfo(`
        <h4>${escapeHtml(data.name)}</h4>
        ${stat("Type", "Schematic")}
        ${stat("Components", data.components.length)}
        ${stat("Wires", data.wires.length)}
        ${stat("Labels", data.labels.length)}
        <h4>Checks</h4>
        <ul>${(data.checks.length ? data.checks : ["Basic checks passed."]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        <p>Use block mode to avoid spaghetti. Use raw mode to debug exact file coordinates.</p>
      `);
    }
    render();
  }

  async function loadSample(path, name) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Could not load ${path}`);
    const blob = await response.blob();
    await loadAssetFile(new File([blob], name));
  }

  function pcbToStl(data) {
    const b = data.bounds;
    const thickness = 1.6;
    const z0 = 0;
    const z1 = thickness;
    const x0 = b.minX, x1 = b.maxX, y0 = b.minY, y1 = b.maxY;
    const faces = [];
    function tri(a, b, c) { faces.push([a, b, c]); }
    const p000 = [x0, y0, z0], p100 = [x1, y0, z0], p110 = [x1, y1, z0], p010 = [x0, y1, z0];
    const p001 = [x0, y0, z1], p101 = [x1, y0, z1], p111 = [x1, y1, z1], p011 = [x0, y1, z1];
    tri(p000, p100, p110); tri(p000, p110, p010);
    tri(p001, p111, p101); tri(p001, p011, p111);
    tri(p000, p001, p101); tri(p000, p101, p100);
    tri(p100, p101, p111); tri(p100, p111, p110);
    tri(p110, p111, p011); tri(p110, p011, p010);
    tri(p010, p011, p001); tri(p010, p001, p000);

    data.footprints.forEach((fp) => {
      const size = 4;
      const ax0 = fp.x - size, ax1 = fp.x + size, ay0 = fp.y - size, ay1 = fp.y + size, az0 = z1, az1 = z1 + 2;
      const a = [ax0, ay0, az0], b2 = [ax1, ay0, az0], c = [ax1, ay1, az0], d = [ax0, ay1, az0];
      const e = [ax0, ay0, az1], f = [ax1, ay0, az1], g = [ax1, ay1, az1], h = [ax0, ay1, az1];
      tri(a, b2, c); tri(a, c, d); tri(e, g, f); tri(e, h, g);
      tri(a, e, f); tri(a, f, b2); tri(b2, f, g); tri(b2, g, c);
      tri(c, g, h); tri(c, h, d); tri(d, h, e); tri(d, e, a);
    });

    const lines = ["solid blockyby_pcb_export"];
    faces.forEach((face) => {
      lines.push("  facet normal 0 0 0", "    outer loop");
      face.forEach((p) => lines.push(`      vertex ${p[0].toFixed(3)} ${p[1].toFixed(3)} ${p[2].toFixed(3)}`));
      lines.push("    endloop", "  endfacet");
    });
    lines.push("endsolid blockyby_pcb_export");
    return lines.join("\n");
  }

  function exportPcbStl() {
    if (!sim.data || sim.data.type !== "pcb") return;
    const stl = pcbToStl(sim.data);
    const url = URL.createObjectURL(new Blob([stl], { type: "model/stl" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "blockyby-pcb-export.stl";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function boot() {
    sim.canvas = $("#simCanvas");
    if (!sim.canvas) return;
    sim.ctx = sim.canvas.getContext("2d");
    renderHome();

    $("#assetInput")?.addEventListener("change", (event) => loadAssetFile(event.target.files[0]));
    $("#sampleSchematicBtn")?.addEventListener("click", () => loadSample("/samples/demo.kicad_sch", "demo.kicad_sch"));
    $("#samplePcbBtn")?.addEventListener("click", () => loadSample("/samples/demo.kicad_pcb", "demo.kicad_pcb"));
    $("#sampleStlBtn")?.addEventListener("click", () => loadSample("/samples/demo-cube.stl", "demo-cube.stl"));
    $("#exportPcbStlBtn")?.addEventListener("click", exportPcbStl);
    $("#simMode")?.addEventListener("change", (event) => { sim.mode = event.target.value; render(); });

    sim.canvas.addEventListener("mousedown", (event) => {
      sim.drag = true;
      sim.last = { x: event.clientX, y: event.clientY };
    });
    window.addEventListener("mouseup", () => { sim.drag = false; });
    window.addEventListener("mousemove", (event) => {
      if (!sim.drag) return;
      const dx = event.clientX - sim.last.x;
      const dy = event.clientY - sim.last.y;
      sim.last = { x: event.clientX, y: event.clientY };
      if (sim.data?.type === "stl") {
        sim.view.rotY += dx * 0.01;
        sim.view.rotX += dy * 0.01;
      } else {
        sim.view.panX += dx;
        sim.view.panY += dy;
      }
      render();
    });
    sim.canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      const factor = event.deltaY < 0 ? 1.08 : 0.92;
      sim.view.zoom = Math.max(0.25, Math.min(5, sim.view.zoom * factor));
      render();
    }, { passive: false });
  }

  window.BlockybySim = { boot, loadAssetFile, render, parseSchematic, parsePcb, parseStl };
})();
