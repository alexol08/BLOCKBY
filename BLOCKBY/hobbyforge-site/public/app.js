const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const SOURCING_DATA_VERSION = "exact-prices-only-v1";

const state = {
  profile: loadLocal("blockyby.profile", null),
  messages: loadLocal("blockyby.messages", []),
  brief: loadLocal("blockyby.brief", null),
  sourcing: loadLocal("blockyby.sourcing", null),
  instructions: loadLocal("blockyby.instructions", null),
  currentPage: 0,
  projects: []
};

if (state.sourcing && state.sourcing.dataVersion !== SOURCING_DATA_VERSION) {
  state.sourcing = null;
  localStorage.removeItem("blockyby.sourcing");
}

function loadLocal(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function saveLocal(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function nl2br(value) {
  return escapeHtml(value).replace(/\n/g, "<br>");
}

function listFromText(value) {
  return String(value || "")
    .split(/[,\n;\u2022]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatMoney(value, currency = "EUR") {
  const amount = Number(value || 0);
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function isHttpUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function renderProductLink(url, label, verified) {
  if (!isHttpUrl(url)) {
    return `<span class="source-link disabled">${escapeHtml(label)} unavailable</span>`;
  }
  return `
    <a class="source-link ${verified ? "verified" : "needs-review"}" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">
      ${escapeHtml(label)}
    </a>
  `;
}

function sourcePriceLabel(source) {
  if (source.priceConfidence === "unknown" || !Number(source.unitPrice || 0)) {
    return escapeHtml(source.priceText || "Exact supplier/API price not available");
  }
  return `${formatMoney(source.unitPrice, source.currency || "EUR")} <span class="muted-inline">exact supplier/API price</span>`;
}

function sourceShippingLabel(source) {
  if (source.shippingConfidence === "unknown" || !Number(source.shippingEstimate || 0)) {
    return escapeHtml(source.shippingText || "Confirm on supplier page");
  }
  return `${formatMoney(source.shippingEstimate, source.currency || "EUR")} <span class="muted-inline">${escapeHtml(source.shippingConfidence || "exact")}</span>`;
}

function sourceTotalLabel(source) {
  if (source.priceConfidence === "unknown" || !Number(source.totalPriceEstimate || 0)) {
    return "Not available";
  }
  if (source.shippingConfidence === "unknown") {
    return `${formatMoney(source.totalPriceEstimate, source.currency || "EUR")} before shipping`;
  }
  return formatMoney(source.totalPriceEstimate, source.currency || "EUR");
}

function toast(message, type = "ok") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast show ${type}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    el.className = "toast";
  }, 3200);
}

async function api(path, body = undefined) {
  const options = body === undefined
    ? { method: "GET" }
    : {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body)
      };

  const response = await fetch(path, options);
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!response.ok) {
    const detail = data.detail || data.error || data.raw || response.statusText;
    const message = typeof detail === "string" ? detail : (detail.error || JSON.stringify(detail, null, 2));
    const error = new Error(message);
    error.data = data;
    throw error;
  }

  return data;
}

function setBusy(button, busy, text = null) {
  if (!button) return;
  if (busy) {
    button.dataset.oldText = button.textContent;
    button.textContent = text || "Working...";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.oldText || button.textContent;
    button.disabled = false;
  }
}

function currentProfileFromForm() {
  return {
    id: state.profile?.id,
    name: $("#profileName").value.trim() || "Local hobbyist",
    skills: listFromText($("#profileSkills").value),
    tools: listFromText($("#profileTools").value),
    materials: listFromText($("#profileMaterials").value),
    stock: listFromText($("#profileMaterials").value),
    shippingAddress: $("#profileAddress").value.trim(),
    notes: $("#profileNotes").value.trim()
  };
}

function fillProfileForm(profile) {
  if (!profile) return;
  $("#profileName").value = profile.name || "Local hobbyist";
  $("#profileSkills").value = (profile.skills || []).join(", ");
  $("#profileTools").value = (profile.tools || []).join(", ");
  $("#profileMaterials").value = [...(profile.materials || []), ...(profile.stock || [])]
    .filter((value, index, array) => array.indexOf(value) === index)
    .join(", ");
  $("#profileAddress").value = profile.shippingAddress || "";
  $("#profileNotes").value = profile.notes || "";
}

function renderProfileResult(data) {
  if (!data) {
    $("#profileResult").innerHTML = "No profile saved yet.";
    return;
  }
  $("#profileResult").innerHTML = `
    <strong>${escapeHtml(data.name || "Local hobbyist")}</strong>
    <div class="pill-row">
      ${(data.skills || []).map((skill) => `<span class="pill">${escapeHtml(skill)}</span>`).join("") || `<span class="pill warn">No skills yet</span>`}
    </div>
    <p><strong>Tools:</strong> ${escapeHtml((data.tools || []).join(", ") || "none added")}</p>
    <p><strong>Materials/stock:</strong> ${escapeHtml([...(data.materials || []), ...(data.stock || [])].join(", ") || "none added")}</p>
  `;
}

async function checkHealth() {
  try {
    const data = await api("/api/health");
    $("#serverDot").className = "status-dot ok";
    $("#serverStatus").textContent = data.aiEnabled ? "Python + AI ready" : "Python fallback ready";
    $("#serverSub").textContent = data.aiEnabled ? `Model: ${data.model}` : "No API key; local demo agents active";
  } catch (error) {
    $("#serverDot").className = "status-dot bad";
    $("#serverStatus").textContent = "Server unavailable";
    $("#serverSub").textContent = error.message;
  }
}

async function testApi() {
  const button = $("#testApiBtn");
  setBusy(button, true, "Testing...");
  try {
    const data = await api("/api/ai/test", { ping: "Blockyby UI test" });
    toast(data.ok ? "API test completed." : "API test returned an error.", data.ok ? "ok" : "warn");
    $("#profileResult").innerHTML = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
    checkHealth();
  }
}

async function saveProfile() {
  const button = $("#saveProfileBtn");
  setBusy(button, true, "Saving...");
  try {
    const result = await api("/api/profile", currentProfileFromForm());
    state.profile = result.profile;
    saveLocal("blockyby.profile", state.profile);
    renderProfileResult(state.profile);
    toast("Profile saved.");
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

async function importProfile() {
  const button = $("#importProfileBtn");
  setBusy(button, true, "Extracting...");
  try {
    const result = await api("/api/profile/import", {
      sourceType: $("#importSourceType").value,
      url: $("#importUrl").value,
      text: $("#importText").value
    });
    const profile = result.extracted;
    fillProfileForm(profile);
    $("#profileResult").innerHTML = `
      <strong>Extracted profile</strong>
      <p>Confidence: ${Math.round(Number(result.confidence || 0) * 100)}%</p>
      <pre>${escapeHtml(JSON.stringify(profile, null, 2))}</pre>
    `;
    toast("Profile text extracted. Review it, then save.");
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

function renderMessages() {
  const log = $("#chatLog");
  if (!state.messages.length) {
    log.innerHTML = `<div class="empty-state">No discussion yet. Ask the planning agent to validate your idea.</div>`;
    return;
  }
  log.innerHTML = state.messages.map((message) => `
    <div class="chat-message ${escapeHtml(message.role)}">
      <strong>${message.role === "user" ? "You" : "Planning agent"}</strong>
      <div>${nl2br(message.content)}</div>
    </div>
  `).join("");
  log.scrollTop = log.scrollHeight;
}

function renderBrief() {
  const out = $("#briefOutput");
  const brief = state.brief;
  if (!brief) {
    out.className = "brief-card empty-state";
    out.innerHTML = "No brief yet. Start by refining an idea.";
    return;
  }
  out.className = "brief-card";
  const score = Math.round(Number(brief.feasibilityScore || 0) * 100);
  out.innerHTML = `
    <div class="item-top">
      <h3>${escapeHtml(brief.projectName || "Project brief")}</h3>
      <span class="pill ${brief.safe ? "ok" : "bad"}">${brief.safe ? "safe" : "blocked"}</span>
    </div>
    <p>${escapeHtml(brief.summary || "")}</p>
    <div class="brief-grid">
      <div class="stat"><span>Feasibility</span><strong>${score}%</strong></div>
      <div class="stat"><span>Strategy</span><strong>${escapeHtml(brief.costStrategy || "balanced")}</strong></div>
    </div>
    <h4>Core requirements</h4>
    <ul>${(brief.coreRequirements || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h4>Compatibility checklist</h4>
    <ul>${(brief.compatibilityChecklist || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <h4>Questions</h4>
    <ul>${(brief.questions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    ${brief._aiError ? `<p class="pill warn">AI fallback used: ${escapeHtml(brief._aiError)}</p>` : ""}
  `;
}

async function refineProject() {
  const idea = $("#projectIdea").value.trim();
  const userText = $("#chatInput").value.trim() || "Please validate this project and suggest the next best step.";
  if (!idea) {
    toast("Add a project idea first.", "warn");
    return;
  }

  const button = $("#refineBtn");
  setBusy(button, true, "Refining...");
  try {
    const profile = currentProfileFromForm();
    state.messages.push({ role: "user", content: userText });
    renderMessages();
    const result = await api("/api/project/refine", {
      profile,
      idea,
      messages: state.messages,
      budgetQuality: Number($("#budgetSlider").value),
      ownedOptimisation: true
    });
    state.brief = result;
    state.messages.push({ role: "assistant", content: result.reply || result.summary || "Brief generated." });
    saveLocal("blockyby.messages", state.messages);
    saveLocal("blockyby.brief", state.brief);
    renderMessages();
    renderBrief();
    toast(result.safe ? "Project brief generated." : "Safety gate blocked this idea.", result.safe ? "ok" : "warn");
    $("#chatInput").value = "";
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

function renderSourceCandidates(item) {
  const sources = item.sourceCandidates || [];
  if (!sources.length) {
    return `
      <div class="source-card unverified">
        <h4>No verified source yet</h4>
        <p>This item cannot be checked out until the backend finds or verifies a source candidate.</p>
      </div>
    `;
  }

  return sources.map((source, index) => `
    <div class="source-card ${source.verificationStatus === "verified" ? "" : "unverified"} ${index === Number(item.selectedSourceIndex || 0) ? "selected" : ""}">
      <div class="item-top">
        <h4>${escapeHtml(source.productName || "Source candidate")}</h4>
        <span class="pill ${source.verificationStatus === "verified" ? "ok" : source.verificationStatus === "needs_review" ? "warn" : "bad"}">
          ${escapeHtml(source.verificationStatus === "verified" ? (source.priceConfidence === "exact" ? "price verified" : "link verified") : (source.verificationStatus || "unverified"))}
        </span>
      </div>
      <p>${escapeHtml(source.description || "No description supplied.")}</p>
      <div class="source-actions">
        ${renderProductLink(source.productUrl, source.sourceType === "supplier_search" ? "Open supplier search" : "Open product", source.productUrlVerified)}
        ${source.datasheetUrl ? renderProductLink(source.datasheetUrl, "Datasheet", source.datasheetUrlVerified) : ""}
      </div>
      <dl>
        <dt>Supplier</dt><dd>${escapeHtml(source.supplier || "Unknown")}</dd>
        <dt>Manufacturer</dt><dd>${escapeHtml(source.manufacturer || "Unknown")}</dd>
        <dt>Part number</dt><dd>${escapeHtml(source.manufacturerPartNumber || source.supplierPartNumber || "Unknown")}</dd>
        <dt>Price</dt><dd>${sourcePriceLabel(source)}</dd>
        <dt>Shipping</dt><dd>${sourceShippingLabel(source)}</dd>
        <dt>Total</dt><dd>${escapeHtml(sourceTotalLabel(source))}</dd>
        <dt>Stock</dt><dd>${escapeHtml(String(source.stockAvailable ?? "Check supplier page"))}</dd>
        <dt>Link check</dt><dd>${escapeHtml(source.verificationMessage || source.linkVerification?.product?.message || "No link check recorded.")}</dd>
        <dt>Source</dt><dd>${escapeHtml(source.sourceType || "unknown")}</dd>
        <dt>Evidence</dt><dd>${escapeHtml(source.evidenceNotes || "Found by sourcing agent.")}</dd>
      </dl>
    </div>
  `).join("");
}

function renderSourcing() {
  const out = $("#sourcingOutput");
  const plan = state.sourcing;
  if (!plan) {
    out.className = "empty-state";
    out.innerHTML = "No sourcing plan yet.";
    return;
  }

  if (!plan.safe) {
    out.className = "result-box";
    out.innerHTML = `
      <h3>Sourcing blocked</h3>
      <p>${escapeHtml(plan.summary || "The safety gate blocked sourcing.")}</p>
    `;
    return;
  }

  const verification = plan.verificationSummary || {};
  out.className = "";
  out.innerHTML = `
    <div class="sourcing-summary">
      <div class="item-top">
        <h3>Bill of materials</h3>
        <span class="pill ${verification.checkoutReady ? "ok" : verification.linksReady ? "warn" : "bad"}">${verification.checkoutReady ? "checkout ready" : verification.linksReady ? "links verified, prices needed" : "needs review"}</span>
      </div>
      <p>${escapeHtml(plan.summary || "")}</p>
      <div class="pill-row">
        <span class="pill ok">${verification.verifiedCount ?? 0} links verified</span>
        <span class="pill ${verification.unverifiedCount ? "warn" : "ok"}">${verification.unverifiedCount ?? 0} unverified</span>
        <span class="pill">Exact supplier total: ${formatMoney(plan.estimatedTotal, plan.currency || "EUR")}</span>
        <span class="pill ${verification.unknownPriceCount ? "warn" : "ok"}">${verification.unknownPriceCount ?? 0} need price check</span>
        <span class="pill">${escapeHtml(verification.sourceMode || "source verification")}</span>
      </div>
      <h4>Compatibility notes</h4>
      <ul>${(plan.compatibilityNotes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
    </div>
    <div class="bom-list">
      ${(plan.items || []).map((item) => `
        <article class="bom-item ${item.verificationStatus !== "verified" && item.sourceStatus !== "owned" ? "blocked" : ""}">
          <div>
            <div class="item-top">
              <span class="item-title">${escapeHtml(item.name)}</span>
              <span class="pill ${item.sourceStatus === "owned" ? "ok" : item.verificationStatus === "verified" ? "ok" : "warn"}">${escapeHtml(item.sourceStatus === "owned" ? "owned" : item.verificationStatus === "verified" ? "link verified" : item.verificationStatus)}</span>
            </div>
            <p class="item-meta">
              Category: ${escapeHtml(item.category)}<br>
              Qty: ${escapeHtml(item.quantity)} - ${item.pricingStatus === "exact" ? "exact supplier/API price available" : "exact supplier price needed"}<br>
              ${escapeHtml(item.compatibilityNotes || "")}
            </p>
            <label class="inline-check">
              <input type="checkbox" data-item-id="${escapeHtml(item.id)}" class="item-select" ${item.selected && item.orderable ? "checked" : ""} ${!item.orderable ? "disabled" : ""} />
              Include in mock order
            </label>
          </div>
          <div class="source-grid">
            ${renderSourceCandidates(item)}
          </div>
        </article>
      `).join("")}
    </div>
  `;

  $$(".item-select").forEach((box) => {
    box.addEventListener("change", () => {
      const item = state.sourcing.items.find((part) => part.id === box.dataset.itemId);
      if (item) item.selected = box.checked;
      saveLocal("blockyby.sourcing", state.sourcing);
    });
  });
}

async function sourceProject() {
  if (!state.brief) {
    toast("Generate a project brief first.", "warn");
    return;
  }
  const button = $("#sourceBtn");
  setBusy(button, true, "Sourcing...");
  try {
    const result = await api("/api/sourcing", {
      profile: currentProfileFromForm(),
      brief: state.brief,
      idea: $("#projectIdea").value,
      budgetQuality: Number($("#budgetSlider").value)
    });
    state.sourcing = result;
    saveLocal("blockyby.sourcing", state.sourcing);
    renderSourcing();
    toast(result.safe ? "Verified sourcing plan generated." : "Sourcing blocked by safety gate.", result.safe ? "ok" : "warn");
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

function canCheckout(items) {
  const problems = [];
  for (const item of items) {
    if (item.sourceStatus === "owned") continue;
    if (item.verificationStatus !== "verified") problems.push(`${item.name}: not verified`);
    if (!item.sourceCandidates || !item.sourceCandidates.length) problems.push(`${item.name}: no source candidate`);
    if (item.selectedSourceIndex < 0) problems.push(`${item.name}: no source selected`);
    const selected = (item.sourceCandidates || [])[item.selectedSourceIndex];
    if (!selected?.productUrlVerified || !isHttpUrl(selected?.productUrl)) {
      problems.push(`${item.name}: selected product link did not pass verification`);
    }
    if (selected?.priceConfidence !== "exact" || !Number(selected?.unitPrice || 0)) {
      problems.push(`${item.name}: selected source needs exact supplier/API pricing`);
    }
  }
  return { ok: problems.length === 0, problems };
}

async function createMockOrder() {
  if (!state.sourcing) {
    toast("Generate sourcing first.", "warn");
    return;
  }
  const selected = (state.sourcing.items || []).filter((item) => item.selected && item.orderable && item.sourceStatus !== "owned");
  const check = canCheckout(selected);
  if (!check.ok) {
    $("#orderOutput").innerHTML = `
      <h3>Cart needs review</h3>
      <ul>${check.problems.map((problem) => `<li>${escapeHtml(problem)}</li>`).join("")}</ul>
    `;
    toast("Cart needs source verification before checkout.", "warn");
    return;
  }

  const button = $("#orderBtn");
  setBusy(button, true, "Creating...");
  try {
    const result = await api("/api/order", { items: selected, currency: state.sourcing.currency || "EUR" });
    $("#orderOutput").innerHTML = `
      <h3>Mock order created</h3>
      <p>${escapeHtml(result.order.message)}</p>
      <p><strong>ID:</strong> ${escapeHtml(result.order.id)} - <strong>Total:</strong> ${formatMoney(result.order.estimatedTotal, result.order.currency)}</p>
    `;
    toast("Mock order created.");
  } catch (error) {
    $("#orderOutput").innerHTML = `<pre>${escapeHtml(JSON.stringify(error.data || error.message, null, 2))}</pre>`;
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

function renderDiagram(diagram) {
  if (!diagram || !Array.isArray(diagram.nodes)) {
    return `<div class="empty-state">No diagram available for this page.</div>`;
  }
  const nodes = diagram.nodes || [];
  const edges = diagram.edges || [];
  const callouts = diagram.callouts || [];
  const byId = Object.fromEntries(nodes.map((node) => [node.id, node]));

  return `
    <svg class="step-diagram" viewBox="0 0 430 260" role="img" aria-label="${escapeHtml(diagram.title || "Instruction diagram")}">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L7,3 z" fill="#5f7f52"></path>
        </marker>
      </defs>
      <rect x="8" y="8" width="414" height="244" rx="24" class="diagram-bg"></rect>
      ${edges.map((edge) => {
        const from = byId[edge.from];
        const to = byId[edge.to];
        if (!from || !to) return "";
        const x1 = Number(from.x) + 55;
        const y1 = Number(from.y) + 28;
        const x2 = Number(to.x) + 55;
        const y2 = Number(to.y) + 28;
        return `
          <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="diagram-wire"></line>
          <text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 8}" text-anchor="middle" class="diagram-label">${escapeHtml(edge.label)}</text>
        `;
      }).join("")}
      ${nodes.map((node) => `
        <g>
          <rect x="${Number(node.x)}" y="${Number(node.y)}" width="110" height="56" rx="14" class="diagram-node"></rect>
          <text x="${Number(node.x) + 55}" y="${Number(node.y) + 32}" text-anchor="middle" class="diagram-node-text">${escapeHtml(String(node.label || "").slice(0, 18))}</text>
        </g>
      `).join("")}
      ${callouts.map((callout) => `<text x="${Number(callout.x)}" y="${Number(callout.y)}" class="diagram-callout">${escapeHtml(callout.text)}</text>`).join("")}
    </svg>
  `;
}

function renderInstructions() {
  const out = $("#bookOutput");
  const book = state.instructions;
  if (!book) {
    out.className = "book-view empty-state";
    out.innerHTML = "No instruction book yet.";
    return;
  }
  if (!book.safe) {
    out.className = "book-view result-box";
    out.innerHTML = `<h3>${escapeHtml(book.title || "Instructions blocked")}</h3><p>${escapeHtml(book.intro || "")}</p>`;
    return;
  }

  const pages = book.pages || [];
  if (!pages.length) {
    out.className = "book-view empty-state";
    out.innerHTML = "The instruction book has no pages yet.";
    return;
  }
  state.currentPage = Math.max(0, Math.min(state.currentPage, pages.length - 1));
  const page = pages[state.currentPage];
  out.className = "book-view";
  out.innerHTML = `
    <article class="book-page">
      <div class="book-top">
        <div>
          <span class="page-number">Page ${escapeHtml(page.pageNumber)} of ${pages.length}</span>
          <h3>${escapeHtml(page.title)}</h3>
          <p>${escapeHtml(page.purpose)}</p>
        </div>
        <span class="pill">${escapeHtml(page.animationCue || "diagram")}</span>
      </div>
      ${renderDiagram(page.diagram)}
      <div class="book-lists">
        <div><h4>Parts</h4><ul>${(page.partsNeeded || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>
        <div><h4>Actions</h4><ul>${(page.actions || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>
        <div><h4>Checks</h4><ul>${(page.checks || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>
      </div>
      <div class="result-box"><strong>Help prompt:</strong> ${escapeHtml(page.helpPrompt || "Ask for help with this page.")}</div>
    </article>
  `;
}

async function generateInstructions() {
  if (!state.brief || !state.sourcing) {
    toast("Generate the brief and sourcing plan first.", "warn");
    return;
  }
  const button = $("#instructionsBtn");
  setBusy(button, true, "Generating...");
  try {
    const result = await api("/api/instructions", {
      profile: currentProfileFromForm(),
      brief: state.brief,
      sourcing: state.sourcing
    });
    state.instructions = result;
    state.currentPage = 0;
    saveLocal("blockyby.instructions", state.instructions);
    renderInstructions();
    toast(result.safe ? "Instruction book generated." : "Instructions blocked by safety gate.", result.safe ? "ok" : "warn");
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

async function saveProject() {
  if (!state.brief) {
    toast("Create a project brief first.", "warn");
    return;
  }
  const button = $("#saveProjectBtn");
  setBusy(button, true, "Saving...");
  try {
    const result = await api("/api/projects", {
      title: state.brief.projectName || "Untitled project",
      brief: state.brief,
      sourcing: state.sourcing || {},
      instructions: state.instructions || {},
      visibility: "private"
    });
    toast("Project saved locally.");
    await loadProjects();
    return result;
  } catch (error) {
    toast(error.message, "bad");
  } finally {
    setBusy(button, false);
  }
}

async function loadProjects() {
  try {
    const data = await api("/api/projects");
    state.projects = data.projects || [];
    renderProjects();
  } catch (error) {
    toast(error.message, "bad");
  }
}

function renderProjects() {
  const out = $("#libraryOutput");
  if (!state.projects.length) {
    out.className = "library-grid empty-state";
    out.innerHTML = "No saved projects yet.";
    return;
  }
  out.className = "library-grid";
  out.innerHTML = state.projects.map((project) => `
    <article class="project-card">
      <div class="item-top">
        <h3>${escapeHtml(project.title)}</h3>
        <span class="pill">${escapeHtml(project.visibility || "private")}</span>
      </div>
      <p>${escapeHtml(project.brief?.summary || "No summary")}</p>
      <div class="pill-row">
        <span class="pill">${escapeHtml(project.id)}</span>
        <span class="pill">${escapeHtml(project.updatedAt || project.createdAt || "")}</span>
      </div>
    </article>
  `).join("");
}

async function runDemoFlow() {
  $("#projectIdea").value = "A desk plant monitor with an ESP32, moisture sensor, simple enclosure, and status LEDs.";
  $("#chatInput").value = "Validate this as a hackathon demo and make the first version realistic.";
  if (!state.profile) {
    fillSampleProfile();
    await saveProfile();
  }
  await refineProject();
  await sourceProject();
  await generateInstructions();
  document.getElementById("bookSection").scrollIntoView({ behavior: "smooth" });
}

function fillSampleProfile() {
  $("#profileName").value = "Hackathon maker";
  $("#profileSkills").value = "Python, basic electronics, CAD, 3D printing";
  $("#profileTools").value = "Multimeter, breadboard, 3D printer, calipers, laptop";
  $("#profileMaterials").value = "PLA filament, jumper wires, LEDs, resistors, M3 screws";
  $("#profileAddress").value = "";
  $("#profileNotes").value = "Prefer safe low-voltage electronics and parts that are easy to explain to judges.";
}

function updateBudgetLabel() {
  const value = Number($("#budgetSlider").value);
  const label = value < 30 ? "Cheap-first" : value > 70 ? "Best-quality" : "Balanced";
  $("#budgetLabel").textContent = `${label} (${value})`;
}

function bindNav() {
  $$('button[data-target]').forEach((button) => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.target);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      $$(".nav-link").forEach((link) => link.classList.toggle("active", link === button));
    });
  });
}

function bindEvents() {
  bindNav();
  $("#testApiBtn").addEventListener("click", testApi);
  $("#saveProfileBtn").addEventListener("click", saveProfile);
  $("#fillProfileBtn").addEventListener("click", () => { fillSampleProfile(); toast("Sample profile filled."); });
  $("#clearProfileBtn").addEventListener("click", () => { fillProfileForm({ name: "Local hobbyist", skills: [], tools: [], materials: [], stock: [] }); toast("Profile form cleared.", "warn"); });
  $("#importProfileBtn").addEventListener("click", importProfile);
  $("#refineBtn").addEventListener("click", refineProject);
  $("#clearChatBtn").addEventListener("click", () => { state.messages = []; saveLocal("blockyby.messages", []); renderMessages(); });
  $("#sourceBtn").addEventListener("click", sourceProject);
  $("#orderBtn").addEventListener("click", createMockOrder);
  $("#instructionsBtn").addEventListener("click", generateInstructions);
  $("#prevPageBtn").addEventListener("click", () => { state.currentPage -= 1; renderInstructions(); });
  $("#nextPageBtn").addEventListener("click", () => { state.currentPage += 1; renderInstructions(); });
  $("#saveProjectBtn").addEventListener("click", saveProject);
  $("#loadProjectsBtn").addEventListener("click", loadProjects);
  $("#quickDemoBtn").addEventListener("click", runDemoFlow);
  $("#budgetSlider").addEventListener("input", updateBudgetLabel);
}

function boot() {
  bindEvents();
  fillProfileForm(state.profile || null);
  renderProfileResult(state.profile);
  renderMessages();
  renderBrief();
  renderSourcing();
  renderInstructions();
  updateBudgetLabel();
  checkHealth();
  loadProjects();
  if (window.BlockybySim) window.BlockybySim.boot();
}

boot();
