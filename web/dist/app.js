// src/app.ts
var locationPositions = {
  residential_district: [0.18, 0.23],
  factory_district: [0.8, 0.22],
  downtown: [0.49, 0.27],
  community_clinic: [0.2, 0.72],
  riverfront_park: [0.74, 0.72],
  town_hall: [0.5, 0.58]
};
var agentColors = [
  "#b74747",
  "#2c76a3",
  "#b67224",
  "#2c8064",
  "#765a99"
];
var eventLabels = {
  public_announcement: "公共公告",
  information_treatment: "实验信息",
  weather_event: "天气事件",
  community_event: "社区事件",
  public_service_update: "公共服务",
  environment_update: "环境动态",
  economic_update: "经济动态",
  school_event: "学校事件",
  civic_event: "市政事件",
  business_update: "商业动态",
  infrastructure_event: "基础设施",
  employment_event: "就业动态",
  election_opening: "投票开放",
  movement: "移动",
  public_statement: "公开发言",
  private_message: "私下交流",
  inspection: "调查",
  secret_ballot: "秘密投票"
};
var memoryLabels = {
  episodic: "经历",
  semantic: "知识",
  social: "社交"
};
var conditionLabels = {
  baseline: "基线组",
  placebo: "安慰剂组",
  employment_evidence: "就业证据组",
  pollution_evidence: "污染证据组"
};
var required = (id) => {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element;
};
var canvas = required("world-canvas");
var context = canvas.getContext("2d");
if (!context) {
  throw new Error("Canvas 2D is unavailable.");
}
var conditionSelect = required("condition-select");
var timeline = required("timeline");
var speedSelect = required("speed-select");
var agentList = required("agent-list");
var eventFeed = required("event-feed");
var agentDetail = required("agent-detail");
var importInput = required("import-input");
var importButton = required("import-button");
var demoButton = required("demo-button");
var bundle;
var demoBundle;
var selectedCondition = 0;
var frameIndex = 0;
var selectedAgentId = "";
var timer = null;
var renderedAgentPoints = [];
var escapeHtml = (value) => String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
var formatInteger = (value) => new Intl.NumberFormat("zh-CN").format(value);
var formatRunTime = (value) => {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("zh-CN");
};
var condition = () => bundle.conditions[selectedCondition];
var run = () => condition().run;
var timeLabel = (index) => run().config.metadata.time_unit === "day" ? `第 ${index} 天` : `第 ${index} 轮`;
var currentState = () => {
  if (frameIndex === 0) {
    return run().snapshots[0];
  }
  return run().turns[frameIndex - 1].state_after;
};
var currentTurn = () => {
  if (frameIndex === 0) {
    return null;
  }
  return run().turns[frameIndex - 1];
};
var agentById = (agentId) => run().scenario.agents.find((agent) => agent.agent_id === agentId) ?? run().scenario.agents[0];
var locationById = (locationId) => run().scenario.locations.find((location) => location.location_id === locationId) ?? run().scenario.locations[0];
var agentColor = (agentId) => {
  const index = run().scenario.agents.findIndex((agent) => agent.agent_id === agentId);
  return agentColors[Math.max(0, index) % agentColors.length];
};
var initials = (name) => name.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
var actionSummary = (turn) => {
  if (!turn) {
    return "世界已初始化";
  }
  const agent = agentById(turn.agent_id);
  if (!turn.result) {
    const period = run().config.metadata.time_unit === "day" ? "本日" : "本轮";
    return `${agent.name} ${period}等待`;
  }
  const label = turn.result.accepted ? "已执行" : "被拒绝";
  return `${agent.name} · ${turn.result.request.action_type} · ${label}`;
};
var voteRecords = () => run().turns.flatMap((turn, turnIndex) => {
  const result = turn.result;
  if (!result?.accepted || result.request.action_type !== "vote") {
    return [];
  }
  const rawReason = result.request.parameters.reason;
  return [
    {
      turn,
      turnIndex,
      agent: agentById(turn.agent_id),
      candidate: String(result.request.parameters.candidate ?? "未记录"),
      reason: typeof rawReason === "string" ? rawReason.trim() : "",
      eventId: result.events[0]?.event_id ?? ""
    }
  ];
});
var allVisibleEvents = () => currentState().events;
var resizeCanvas = () => {
  const rectangle = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.round(rectangle.width * ratio));
  const height = Math.max(1, Math.round(rectangle.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  drawWorld();
};
var drawRoundedRectangle = (x, y, width, height, radius) => {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
};
var drawWorld = () => {
  if (!bundle) {
    return;
  }
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#dbe8d5";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "#77b8d2";
  context.lineWidth = Math.max(34, width * 0.055);
  context.lineCap = "round";
  context.beginPath();
  context.moveTo(width * 0.02, height * 0.47);
  context.bezierCurveTo(width * 0.28, height * 0.37, width * 0.7, height * 0.86, width * 1.02, height * 0.68);
  context.stroke();
  const town = locationPositions.town_hall;
  context.strokeStyle = "#aaa99f";
  context.lineWidth = 6;
  context.lineCap = "butt";
  for (const [locationId, position] of Object.entries(locationPositions)) {
    if (locationId === "town_hall") {
      continue;
    }
    context.beginPath();
    context.moveTo(town[0] * width, town[1] * height);
    context.lineTo(position[0] * width, position[1] * height);
    context.stroke();
  }
  for (const location of run().scenario.locations) {
    const [normalizedX, normalizedY] = locationPositions[location.location_id] ?? [0.5, 0.5];
    const x = normalizedX * width;
    const y = normalizedY * height;
    const buildingWidth = Math.max(92, Math.min(132, width * 0.16));
    const buildingHeight = 48;
    context.fillStyle = location.location_id === "factory_district" ? "#8f8178" : location.location_id === "town_hall" ? "#d7c6a1" : "#f7f7f1";
    context.strokeStyle = "#53616a";
    context.lineWidth = 1.5;
    drawRoundedRectangle(x - buildingWidth / 2, y - buildingHeight / 2, buildingWidth, buildingHeight, 4);
    context.fill();
    context.stroke();
    context.fillStyle = "#25333c";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.font = '600 11px "Segoe UI", "Microsoft YaHei", sans-serif';
    context.fillText(location.name, x, y);
  }
  const state = currentState();
  const groups = new Map;
  for (const [agentId, locationId] of Object.entries(state.agent_locations)) {
    const group = groups.get(locationId) ?? [];
    group.push(agentId);
    groups.set(locationId, group);
  }
  renderedAgentPoints = [];
  const activeAgent = currentTurn()?.agent_id;
  for (const [locationId, agentIds] of groups) {
    const [normalizedX, normalizedY] = locationPositions[locationId] ?? [0.5, 0.5];
    const centerX = normalizedX * width;
    const centerY = normalizedY * height + 48;
    agentIds.forEach((agentId, index) => {
      const spread = agentIds.length === 1 ? 0 : 36;
      const angle = -Math.PI / 2 + index / Math.max(1, agentIds.length) * Math.PI * 2;
      const x = centerX + Math.cos(angle) * spread;
      const y = centerY + Math.sin(angle) * spread * 0.55;
      renderedAgentPoints.push({ agentId, x, y });
      if (agentId === selectedAgentId || agentId === activeAgent) {
        context.beginPath();
        context.arc(x, y, 18, 0, Math.PI * 2);
        context.fillStyle = agentId === activeAgent ? "#fff1b8" : "#ffffff";
        context.fill();
        context.strokeStyle = "#24313a";
        context.lineWidth = 2;
        context.stroke();
      }
      context.beginPath();
      context.arc(x, y, 13, 0, Math.PI * 2);
      context.fillStyle = agentColor(agentId);
      context.fill();
      context.strokeStyle = "#ffffff";
      context.lineWidth = 2;
      context.stroke();
      context.fillStyle = "#ffffff";
      context.font = '700 8px "Segoe UI", sans-serif';
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(initials(agentById(agentId).name), x, y + 0.5);
    });
  }
};
var renderAgentList = () => {
  const state = currentState();
  agentList.replaceChildren(...run().scenario.agents.map((agent) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `agent-row${agent.agent_id === selectedAgentId ? " selected" : ""}`;
    button.innerHTML = `
        <span class="agent-swatch" style="background:${agentColor(agent.agent_id)}"></span>
        <span class="agent-copy">
          <strong>${escapeHtml(agent.name)}</strong>
          <span>${escapeHtml(locationById(state.agent_locations[agent.agent_id]).name)}</span>
        </span>
      `;
    button.addEventListener("click", () => {
      selectedAgentId = agent.agent_id;
      showTab("agent");
      render();
    });
    return button;
  }));
};
var renderEventFeed = () => {
  const events = allVisibleEvents();
  const votesByEventId = new Map(voteRecords().map((record) => [record.eventId, record]));
  const activeEventId = currentTurn()?.result?.events[0]?.event_id ?? "";
  eventFeed.replaceChildren(...events.slice().reverse().map((event) => {
    const item = document.createElement("li");
    item.className = `event-item${event.is_public ? "" : " private"}${event.event_id === activeEventId ? " active" : ""}`;
    const actor = event.actor_id ? agentById(event.actor_id).name : "Game Master";
    const vote = votesByEventId.get(event.event_id);
    const voteSummary = vote ? `
            <div class="event-vote-summary">
              <strong>投给 ${escapeHtml(vote.candidate)}</strong>
              <span>${escapeHtml(vote.reason || "该运行未记录投票理由")}</span>
            </div>
          ` : "";
    item.innerHTML = `
          <div class="event-meta">
            <span class="event-type">${escapeHtml(eventLabels[event.event_type] ?? event.event_type)}</span>
            <span>${timeLabel(event.round_index)} · ${escapeHtml(actor)}</span>
          </div>
          <p>${escapeHtml(event.content)}</p>
          ${voteSummary}
        `;
    return item;
  }));
};
var renderVoteDetail = () => {
  const container = required("vote-detail");
  const records = voteRecords();
  const activeTurn = currentTurn();
  required("vote-tab-count").textContent = String(records.length);
  const missingCount = records.filter((record) => !record.reason).length;
  const notice = missingCount ? `
      <div class="vote-notice">
        其中 ${missingCount} 张选票来自旧记录，原始 JSON 没有保存理由。
        页面不会代替 Agent 编写解释。
      </div>
    ` : "";
  const entries = records.map((record) => {
    const candidateClass = record.candidate === "Alice" ? "alice" : record.candidate === "Bob" ? "bob" : "unknown";
    const activeClass = activeTurn === record.turn ? " active" : "";
    return `
        <article class="vote-entry${activeClass}">
          <header>
            <div>
              <strong>${escapeHtml(record.agent.name)}</strong>
              <span>${timeLabel(record.turn.round_index)}</span>
            </div>
            <span class="candidate-chip ${candidateClass}">
              ${escapeHtml(record.candidate)}
            </span>
          </header>
          <p class="${record.reason ? "vote-reason" : "vote-reason missing"}">
            ${escapeHtml(record.reason || "此运行未记录投票理由")}
          </p>
        </article>
      `;
  }).join("");
  container.innerHTML = `
    <div class="vote-heading">
      <div>
        <h3>最终投票与理由</h3>
        <p>${records.length} 张已记录选票</p>
      </div>
    </div>
    ${notice}
    <div class="vote-list">
      ${entries || '<p class="vote-empty">当前运行没有有效选票。</p>'}
    </div>
  `;
};
var renderAgentDetail = () => {
  const state = currentState();
  const agent = agentById(selectedAgentId);
  const location = locationById(state.agent_locations[agent.agent_id]);
  const relationships = state.relationships[agent.agent_id] ?? {};
  const currentRound = state.round_index;
  const memories = (run().memory_state[agent.agent_id]?.records ?? []).filter((memory) => memory.round_index <= currentRound).slice(-6).reverse();
  const relationshipLines = Object.entries(relationships).sort((left, right) => right[1] - left[1]).map(([targetId, value]) => `
        <div class="relation-line">
          ${escapeHtml(agentById(targetId).name)}
          <strong>${value.toFixed(2)}</strong>
        </div>
      `).join("");
  const memoryLines = memories.map((memory) => `
        <div class="memory-line">
          <span class="memory-tag">${escapeHtml(memoryLabels[memory.memory_type])}</span>
          ${escapeHtml(memory.content)}
        </div>
      `).join("");
  agentDetail.innerHTML = `
    <header>
      <div class="agent-avatar" style="background:${agentColor(agent.agent_id)}">
        ${initials(agent.name)}
      </div>
      <div>
        <h3>${escapeHtml(agent.name)}</h3>
        <p>${escapeHtml(agent.role)} · ${escapeHtml(location.name)}</p>
      </div>
    </header>
    <div class="detail-section">
      <h4>目标</h4>
      <p>${escapeHtml(agent.goal)}</p>
    </div>
    <div class="detail-section">
      <h4>背景</h4>
      <p>${escapeHtml(agent.attributes.background ?? "—")}</p>
    </div>
    <div class="detail-section">
      <h4>关系</h4>
      ${relationshipLines || "<p>尚无社会互动</p>"}
    </div>
    <div class="detail-section">
      <h4>当前可见记忆</h4>
      ${memoryLines || "<p>尚无当前轮次记忆</p>"}
    </div>
  `;
};
var renderModelDetail = () => {
  const container = required("model-detail");
  const source = condition().source;
  const usage = source?.model_usage;
  const turn = currentTurn();
  const modelName = usage?.model ?? run().config.model_name ?? "无模型调用";
  const summary = `
    <div class="model-summary">
      <div>
        <span>模型</span>
        <strong title="${escapeHtml(modelName)}">${escapeHtml(modelName)}</strong>
      </div>
      <div>
        <span>API 请求</span>
        <strong>${formatInteger(usage?.request_count ?? 0)}</strong>
      </div>
      <div>
        <span>总 token</span>
        <strong>${formatInteger(usage?.total_tokens ?? 0)}</strong>
      </div>
      <div>
        <span>实验 seed</span>
        <strong>${run().config.seed}</strong>
      </div>
    </div>
  `;
  if (source?.kind !== "live") {
    container.innerHTML = `
      ${summary}
      <div class="trace-block">
        <h4>脚本演示</h4>
        <p>当前数据没有调用语言模型，因此没有 Prompt 或模型响应。</p>
      </div>
    `;
    return;
  }
  if (!turn) {
    container.innerHTML = `
      ${summary}
      <div class="trace-block">
        <h4>Live Run</h4>
        <p>${escapeHtml(source.run_id ?? "")}</p>
        <p>${escapeHtml(formatRunTime(source.run_at))}</p>
      </div>
      <div class="trace-block">
        <p>沿时间线前进一步，可查看该回合的 Prompt、模型回答和 GM 判定。</p>
      </div>
    `;
    return;
  }
  const agent = agentById(turn.agent_id);
  const trace = source.controller_traces?.[turn.agent_id];
  const calls = (trace?.calls ?? []).filter((call) => call.round_index === turn.round_index);
  const result = turn.result;
  const statusClass = result ? result.accepted ? "accepted" : "rejected" : "";
  const statusText = result ? result.accepted ? "GM 已接受" : "GM 已拒绝" : "Agent 本轮等待";
  const callBlocks = calls.map((call, index) => `
        <div class="trace-block">
          <h4>模型请求 ${index + 1}</h4>
          ${call.error ? `<p class="trace-status rejected">${escapeHtml(call.error)}</p>` : ""}
          <p><strong>原始响应</strong></p>
          <pre>${escapeHtml(call.raw_response)}</pre>
          <p><strong>解析动作</strong></p>
          <pre>${escapeHtml(JSON.stringify(call.parsed_action, null, 2))}</pre>
          <details>
            <summary>查看发送给模型的 Prompt</summary>
            <pre>${escapeHtml(call.prompt)}</pre>
          </details>
        </div>
      `).join("");
  container.innerHTML = `
    ${summary}
    <div class="trace-block">
      <h4>${timeLabel(turn.round_index)} · ${escapeHtml(agent.name)}</h4>
      <p class="trace-status ${statusClass}">${statusText}</p>
      <p>${escapeHtml(result?.reason ?? "该 Agent 没有提交动作。")}</p>
    </div>
    ${callBlocks || `
        <div class="trace-block">
          <p>这一回合没有保存模型调用，Agent 可能选择了等待。</p>
        </div>
      `}
  `;
};
var renderConditionBars = () => {
  const container = required("condition-bars");
  container.replaceChildren(...bundle.conditions.map((item) => {
    const aliceVotes = item.metrics.candidate_tally.Alice ?? 0;
    const bobVotes = item.metrics.candidate_tally.Bob ?? 0;
    const totalVotes = aliceVotes + bobVotes;
    const eligibleVoters = item.metrics.eligible_voters ?? item.run.scenario.agents.length;
    const unvoted = item.metrics.unvoted_count ?? Math.max(0, eligibleVoters - totalVotes);
    const denominator = Math.max(1, eligibleVoters);
    const aliceShare = aliceVotes / denominator;
    const bobShare = bobVotes / denominator;
    const unvotedShare = unvoted / denominator;
    const block = document.createElement("div");
    block.className = "condition-result";
    block.innerHTML = `
        <header>
          <strong>${escapeHtml(item.label)}</strong>
          <span>A ${aliceVotes} · B ${bobVotes} · 未 ${unvoted}</span>
        </header>
        <div class="stacked-bar" aria-label="${escapeHtml(item.label)} Alice ${aliceVotes}票，Bob ${bobVotes}票，未投票 ${unvoted}人">
          <span class="alice-bar" style="width:${aliceShare * 100}%"></span>
          <span class="bob-bar" style="width:${bobShare * 100}%"></span>
          <span class="not-voted-bar" style="width:${unvotedShare * 100}%"></span>
        </div>
        <div class="bar-legend">
          <span>Alice ${aliceVotes}</span>
          <span>Bob ${bobVotes}</span>
          <span>未投 ${unvoted}</span>
        </div>
      `;
    return block;
  }));
};
var renderMetrics = () => {
  const metrics = condition().metrics;
  required("accepted-actions").textContent = String(metrics.accepted_actions);
  required("relationship-edges").textContent = String(metrics.relationship_edges);
  required("manipulation-check").textContent = metrics.manipulation_check_passed ? "通过" : "未通过";
  const validation = required("validation-status");
  validation.textContent = metrics.manipulation_check_passed ? "操纵检查通过" : "操纵检查失败";
  validation.classList.toggle("pass", metrics.manipulation_check_passed);
};
var render = () => {
  const state = currentState();
  const turn = currentTurn();
  timeline.value = String(frameIndex);
  required("step-label").textContent = `步骤 ${frameIndex}/${run().turns.length}`;
  required("round-label").textContent = timeLabel(state.round_index);
  required("active-action").textContent = actionSummary(turn);
  renderAgentList();
  renderEventFeed();
  renderAgentDetail();
  renderModelDetail();
  renderVoteDetail();
  renderMetrics();
  drawWorld();
};
var stopPlayback = () => {
  if (timer !== null) {
    window.clearInterval(timer);
    timer = null;
  }
};
var stepForward = () => {
  if (frameIndex >= run().turns.length) {
    stopPlayback();
    return;
  }
  frameIndex += 1;
  render();
};
var startPlayback = () => {
  stopPlayback();
  if (frameIndex >= run().turns.length) {
    frameIndex = 0;
  }
  timer = window.setInterval(stepForward, Number(speedSelect.value));
};
var switchCondition = (index) => {
  stopPlayback();
  selectedCondition = index;
  frameIndex = 0;
  selectedAgentId = run().scenario.agents[0].agent_id;
  timeline.max = String(run().turns.length);
  render();
};
var showTab = (tab) => {
  const eventsSelected = tab === "events";
  const agentSelected = tab === "agent";
  const modelSelected = tab === "model";
  const voteSelected = tab === "vote";
  required("events-tab").classList.toggle("active", eventsSelected);
  required("agent-tab").classList.toggle("active", agentSelected);
  required("model-tab").classList.toggle("active", modelSelected);
  required("vote-tab").classList.toggle("active", voteSelected);
  required("events-tab").setAttribute("aria-selected", String(eventsSelected));
  required("agent-tab").setAttribute("aria-selected", String(agentSelected));
  required("model-tab").setAttribute("aria-selected", String(modelSelected));
  required("vote-tab").setAttribute("aria-selected", String(voteSelected));
  required("events-panel").classList.toggle("hidden", !eventsSelected);
  required("agent-panel").classList.toggle("hidden", !agentSelected);
  required("model-panel").classList.toggle("hidden", !modelSelected);
  required("vote-panel").classList.toggle("hidden", !voteSelected);
};
var isRecord = (value) => typeof value === "object" && value !== null && !Array.isArray(value);
var validateLivePayload = (value, fileName) => {
  if (!isRecord(value)) {
    throw new Error(`${fileName}: 顶层内容必须是 JSON 对象。`);
  }
  const runValue = value.run;
  const metricsValue = value.metrics;
  const tracesValue = value.controller_traces;
  const usageValue = value.model_usage;
  if (typeof value.run_id !== "string" || typeof value.run_at !== "string" || !isRecord(runValue) || !isRecord(metricsValue) || !isRecord(tracesValue) || !isRecord(usageValue)) {
    throw new Error(`${fileName}: 不是 Riverbend Live Run 文件。`);
  }
  const scenario = runValue.scenario;
  const config = runValue.config;
  if (!isRecord(scenario) || !isRecord(config) || !Array.isArray(scenario.agents) || scenario.agents.length === 0 || !Array.isArray(scenario.locations) || scenario.locations.length === 0 || !Array.isArray(runValue.turns) || runValue.turns.length === 0 || !Array.isArray(runValue.snapshots) || runValue.snapshots.length === 0 || !isRecord(runValue.final_state) || !isRecord(runValue.memory_state)) {
    throw new Error(`${fileName}: run 字段缺少场景、回合或状态。`);
  }
  if (typeof config.condition !== "string" || typeof config.seed !== "number" || metricsValue.condition !== config.condition || !isRecord(metricsValue.candidate_tally)) {
    throw new Error(`${fileName}: 实验条件或指标不一致。`);
  }
  if (typeof usageValue.model !== "string" || typeof usageValue.request_count !== "number" || typeof usageValue.total_tokens !== "number") {
    throw new Error(`${fileName}: 缺少模型或 token 用量记录。`);
  }
  return value;
};
var buildLiveBundle = (entries) => {
  const ordered = entries.slice().sort((left, right) => left.payload.run_at.localeCompare(right.payload.run_at));
  const usedNames = new Set;
  const conditions = ordered.map(({ fileName, payload }, index) => {
    const conditionName = payload.run.config.condition;
    let uniqueName = conditionName;
    if (usedNames.has(uniqueName)) {
      uniqueName = `${conditionName}_${payload.run_id}`;
    }
    usedNames.add(uniqueName);
    const time = formatRunTime(payload.run_at).split(" ").at(-1);
    return {
      name: uniqueName,
      label: `API · ${conditionLabels[conditionName] ?? conditionName}` + `${time ? ` · ${time}` : ` · 运行 ${index + 1}`}`,
      run: payload.run,
      metrics: payload.metrics,
      source: {
        kind: "live",
        file_name: fileName,
        run_id: payload.run_id,
        run_at: payload.run_at,
        controller_traces: payload.controller_traces,
        model_usage: payload.model_usage
      }
    };
  });
  const summaries = {};
  for (const item of conditions) {
    const alice = item.metrics.candidate_tally.Alice ?? 0;
    const bob = item.metrics.candidate_tally.Bob ?? 0;
    const total = alice + bob;
    summaries[item.name] = {
      runs: 1,
      candidate_tally: { Alice: alice, Bob: bob },
      candidate_shares: {
        Alice: total ? alice / total : 0,
        Bob: total ? bob / total : 0
      },
      all_manipulation_checks_passed: item.metrics.manipulation_check_passed,
      mean_acceptance_rate: item.metrics.acceptance_rate ?? item.metrics.accepted_actions / Math.max(1, item.metrics.accepted_actions + item.metrics.rejected_actions)
    };
  }
  return {
    generated_at: ordered.at(-1)?.payload.run_at ?? new Date().toISOString(),
    mode: "live_api_import",
    disclaimer: "这些数据来自本机保存的 DeepSeek API 实验结果；网页只做本地读取和回放，不会再次调用 API 或上传文件。",
    conditions,
    experiment_plan: {
      base_seed: conditions[0]?.run.config.seed ?? 0,
      repetitions_per_condition: 1,
      runs: conditions.map((item) => ({
        run_id: item.source?.run_id,
        condition: item.run.config.condition,
        seed: item.run.config.seed
      }))
    },
    experiment_summary: {
      unit_note: "Imported DeepSeek API runs.",
      conditions: summaries
    }
  };
};
var applyBundle = (nextBundle) => {
  stopPlayback();
  bundle = nextBundle;
  selectedCondition = 0;
  frameIndex = 0;
  conditionSelect.replaceChildren(...bundle.conditions.map((item, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = item.label;
    return option;
  }));
  conditionSelect.disabled = false;
  selectedAgentId = run().scenario.agents[0].agent_id;
  timeline.max = String(run().turns.length);
  required("agent-count").textContent = String(run().scenario.agents.length);
  const liveMode = bundle.mode === "live_api_import";
  required("run-mode").textContent = liveMode ? "DeepSeek API 实验回放" : "确定性多 Agent 社会模拟";
  required("experiment-title").textContent = liveMode ? "已导入的 API 实验" : "四组演示结果";
  required("experiment-subtitle").textContent = liveMode ? "真实模型行动、GM 判定与最终选票" : "脚本数据仅用于验证流程";
  required("data-disclaimer").textContent = bundle.disclaimer;
  required("data-time").textContent = formatRunTime(bundle.generated_at);
  if (liveMode) {
    const usages = bundle.conditions.map((item) => item.source?.model_usage).filter((usage) => Boolean(usage));
    const requests = usages.reduce((total, usage) => total + usage.request_count, 0);
    const tokens = usages.reduce((total, usage) => total + usage.total_tokens, 0);
    required("plan-summary").textContent = `${bundle.conditions.length} 个 API 运行 · ` + `${formatInteger(requests)} 次请求 · ` + `${formatInteger(tokens)} tokens`;
  } else {
    required("plan-summary").textContent = `${bundle.experiment_plan.runs.length} 个计划运行 · ` + `种子 ${bundle.experiment_plan.base_seed} · 顺序已平衡`;
  }
  demoButton.classList.toggle("hidden", !liveMode);
  renderConditionBars();
  showTab("events");
  resizeCanvas();
  render();
};
var importLiveRuns = async (files) => {
  if (!files.length) {
    return;
  }
  importButton.disabled = true;
  const validation = required("validation-status");
  validation.textContent = "读取中";
  validation.classList.remove("pass");
  try {
    const entries = await Promise.all(Array.from(files).map(async (file) => {
      let parsed;
      try {
        parsed = JSON.parse(await file.text());
      } catch {
        throw new Error(`${file.name}: JSON 无法解析。`);
      }
      return {
        fileName: file.name,
        payload: validateLivePayload(parsed, file.name)
      };
    }));
    applyBundle(buildLiveBundle(entries));
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    validation.textContent = "导入失败";
    required("active-action").textContent = message;
    console.error(error);
  } finally {
    importButton.disabled = false;
    importInput.value = "";
  }
};
var bindControls = () => {
  importButton.addEventListener("click", () => importInput.click());
  importInput.addEventListener("change", () => {
    if (importInput.files) {
      importLiveRuns(importInput.files);
    }
  });
  demoButton.addEventListener("click", () => applyBundle(demoBundle));
  required("play-button").addEventListener("click", startPlayback);
  required("pause-button").addEventListener("click", stopPlayback);
  required("step-button").addEventListener("click", () => {
    stopPlayback();
    stepForward();
  });
  required("reset-button").addEventListener("click", () => {
    stopPlayback();
    frameIndex = 0;
    render();
  });
  timeline.addEventListener("input", () => {
    stopPlayback();
    frameIndex = Number(timeline.value);
    render();
  });
  speedSelect.addEventListener("change", () => {
    if (timer !== null) {
      startPlayback();
    }
  });
  conditionSelect.addEventListener("change", () => {
    switchCondition(Number(conditionSelect.value));
  });
  required("events-tab").addEventListener("click", () => showTab("events"));
  required("agent-tab").addEventListener("click", () => showTab("agent"));
  required("model-tab").addEventListener("click", () => showTab("model"));
  required("vote-tab").addEventListener("click", () => showTab("vote"));
  canvas.addEventListener("click", (event) => {
    const rectangle = canvas.getBoundingClientRect();
    const x = event.clientX - rectangle.left;
    const y = event.clientY - rectangle.top;
    const nearest = renderedAgentPoints.map((point) => ({
      ...point,
      distance: Math.hypot(point.x - x, point.y - y)
    })).sort((left, right) => left.distance - right.distance)[0];
    if (nearest && nearest.distance <= 26) {
      selectedAgentId = nearest.agentId;
      showTab("agent");
      render();
    }
  });
  window.addEventListener("resize", resizeCanvas);
  new ResizeObserver(resizeCanvas).observe(canvas);
};
var initialize = async () => {
  const embedded = document.getElementById("demo-data");
  if (embedded?.textContent) {
    bundle = JSON.parse(embedded.textContent);
  } else {
    const response = await fetch("/data/demo_bundle.json", {
      cache: "no-store"
    });
    if (!response.ok) {
      throw new Error(`Demo data request failed: ${response.status}`);
    }
    bundle = await response.json();
  }
  demoBundle = {
    ...bundle,
    conditions: bundle.conditions.map((condition2) => ({
      ...condition2,
      source: condition2.source ?? { kind: "demo" }
    }))
  };
  bindControls();
  applyBundle(demoBundle);
};
initialize().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  required("run-mode").textContent = "世界数据载入失败";
  required("validation-status").textContent = "错误";
  required("active-action").textContent = message;
  console.error(error);
});
