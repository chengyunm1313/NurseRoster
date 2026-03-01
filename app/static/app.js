const state = {
  data: null,
  activeTab: "calendar",
  currentProjectId: null,
  selectedRuleId: null,
  selectedRuleVersionId: null,
  activeResource: "nurses",
  editingRecordId: null,
  selectedCell: null,
  currentJobId: null,
  jobEventSource: null,
};

const masterFieldMap = {
  nurses: [
    ["id", "員編"],
    ["name", "姓名"],
    ["department_id", "科別"],
    ["job_level_id", "職級"],
    ["skills", "技能（逗號分隔）"],
    ["status", "狀態"],
    ["notes", "備註"],
    ["active", "啟用（1/0）"],
  ],
  departments: [
    ["id", "代碼"],
    ["name", "名稱"],
    ["description", "說明"],
    ["active", "啟用（1/0）"],
  ],
  shift_codes: [
    ["id", "代碼"],
    ["name", "名稱"],
    ["start_time", "開始時間"],
    ["end_time", "結束時間"],
    ["color", "顏色"],
    ["active", "啟用（1/0）"],
  ],
  job_levels: [
    ["id", "代碼"],
    ["name", "名稱"],
    ["description", "說明"],
    ["active", "啟用（1/0）"],
  ],
  skill_codes: [
    ["id", "代碼"],
    ["name", "名稱"],
    ["description", "說明"],
    ["active", "啟用（1/0）"],
  ],
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.error?.message || "請求失敗");
  }
  return payload.data;
}

async function streamPost(path, body, handlers = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    throw new Error("串流請求失敗");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    while (buffer.includes("\n\n")) {
      const boundary = buffer.indexOf("\n\n");
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseSseBlock(rawEvent);
      if (!parsed) continue;
      const handler = handlers[parsed.event];
      if (handler) {
        handler(parsed.data);
      }
    }
  }
}

function parseSseBlock(block) {
  const lines = block.split("\n");
  let event = "message";
  const dataParts = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.replace("event:", "").trim();
    }
    if (line.startsWith("data:")) {
      dataParts.push(line.replace("data:", "").trim());
    }
  }
  if (!dataParts.length) return null;
  return { event, data: JSON.parse(dataParts.join("")) };
}

function $(selector) {
  return document.querySelector(selector);
}

function $$ (selector) {
  return Array.from(document.querySelectorAll(selector));
}

function formatDate(dateString) {
  return new Date(dateString).toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit", weekday: "short" });
}

function titleForTab(tab) {
  return {
    calendar: "行事曆排班總覽",
    rules: "規則維護",
    master: "資料維護",
    optimization: "最佳化排班",
    dsl: "DSL 測試頁",
    settings: "系統設定",
  }[tab];
}

async function loadBootstrap(projectId = null) {
  const projectQuery = projectId ? `?project_id=${projectId}&from_date=${$("#calendar-from").value || ""}&to_date=${$("#calendar-to").value || ""}` : "";
  state.data = await api(`/api/bootstrap${projectQuery}`);
  state.currentProjectId = state.data.project.id;
  state.selectedRuleId = state.selectedRuleId || state.data.rules[0]?.id || null;
  render();
}

function getUiState() {
  return {
    calendar_from: $("#calendar-from").value,
    calendar_to: $("#calendar-to").value,
    department_id: $("#calendar-department").value,
    coverage: JSON.parse($("#opt-coverage").value || "{}"),
  };
}

function render() {
  renderSidebar();
  renderCalendar();
  renderRules();
  renderMaster();
  renderOptimization();
  renderSettings();
}

function renderSidebar() {
  const projectSelect = $("#project-select");
  projectSelect.innerHTML = state.data.projects
    .map((project) => `<option value="${project.id}" ${project.id === state.currentProjectId ? "selected" : ""}>${project.name}</option>`)
    .join("");

  const auditList = $("#audit-log-list");
  auditList.innerHTML = state.data.audit_logs
    .map(
      (item) => `
        <div class="audit-item">
          <strong>${item.action}</strong>
          <div>${item.entity_type} / ${item.entity_id}</div>
          <div class="muted">${item.created_at}</div>
        </div>
      `,
    )
    .join("");
}

function buildDateRange() {
  const start = new Date($("#calendar-from").value);
  const end = new Date($("#calendar-to").value);
  const dates = [];
  const current = new Date(start);
  while (current <= end) {
    dates.push(current.toISOString().slice(0, 10));
    current.setDate(current.getDate() + 1);
  }
  return dates;
}

function renderCalendar() {
  const uiState = state.data.project.active_snapshot?.ui_state || {};
  const departments = state.data.departments;
  $("#calendar-from").value ||= uiState.calendar_from || "2026-01-01";
  $("#calendar-to").value ||= uiState.calendar_to || "2026-01-14";
  $("#calendar-department").innerHTML = departments
    .map((department) => `<option value="${department.id}" ${department.id === (uiState.department_id || departments[0]?.id) ? "selected" : ""}>${department.id}</option>`)
    .join("");
  $("#opt-from").value ||= $("#calendar-from").value;
  $("#opt-to").value ||= $("#calendar-to").value;
  $("#opt-coverage").value ||= JSON.stringify(uiState.coverage || {}, null, 2);

  const selectedDepartment = $("#calendar-department").value;
  const dates = buildDateRange();
  const nurses = state.data.nurses.filter((nurse) => !selectedDepartment || nurse.department_id === selectedDepartment);
  const assignmentMap = new Map(state.data.assignments.map((item) => [`${item.nurse_id}|${item.date}`, item]));
  const conflictMap = new Map();
  for (const conflict of state.data.conflicts) {
    if (conflict.nurse_id && conflict.date) {
      const key = `${conflict.nurse_id}|${conflict.date}`;
      conflictMap.set(key, (conflictMap.get(key) || 0) + 1);
    }
  }

  $("#calendar-summary").innerHTML = `
    <div class="summary-card"><div>顯示護理師</div><strong>${nurses.length}</strong></div>
    <div class="summary-card"><div>排班天數</div><strong>${dates.length}</strong></div>
    <div class="summary-card"><div>衝突數量</div><strong>${state.data.conflicts.length}</strong></div>
  `;

  $("#calendar-table").innerHTML = `
    <thead>
      <tr>
        <th class="nurse-cell">護理師</th>
        ${dates.map((date) => `<th class="calendar-slot">${formatDate(date)}</th>`).join("")}
      </tr>
    </thead>
    <tbody>
      ${nurses
        .map(
          (nurse) => `
            <tr>
              <td class="nurse-cell">
                <strong>${nurse.id}</strong><br />
                <span class="muted">${nurse.name}</span>
              </td>
              ${dates
                .map((date) => {
                  const assignment = assignmentMap.get(`${nurse.id}|${date}`);
                  const shift = assignment?.shift_code_id || "OFF";
                  const hasConflict = conflictMap.has(`${nurse.id}|${date}`);
                  return `
                    <td class="calendar-slot">
                      <button class="calendar-button" data-nurse-id="${nurse.id}" data-date="${date}">
                        <span class="shift-chip shift-${shift}">${shift}</span>
                        ${hasConflict ? '<span class="conflict-dot"></span>' : ""}
                      </button>
                    </td>
                  `;
                })
                .join("")}
            </tr>
          `,
        )
        .join("")}
    </tbody>
  `;

  $("#conflict-list").innerHTML =
    state.data.conflicts.length === 0
      ? '<div class="list-item"><p>目前沒有衝突。</p></div>'
      : state.data.conflicts
          .slice(0, 20)
          .map(
            (conflict) => `
              <div class="list-item">
                <h4>${conflict.date || conflict.department_id || "規則"}</h4>
                <p>${conflict.message}</p>
              </div>
            `,
          )
          .join("");

  $("#snapshot-list").innerHTML = state.data.snapshots
    .map(
      (snapshot) => `
        <div class="list-item">
          <h4>${snapshot.title}</h4>
          <p>${snapshot.created_at}</p>
          <button class="button secondary restore-snapshot" data-snapshot-id="${snapshot.id}">回復此快照</button>
        </div>
      `,
    )
    .join("");

  $$(".calendar-button").forEach((button) => {
    button.addEventListener("click", () => openDrawer(button.dataset.nurseId, button.dataset.date));
  });
  $$(".restore-snapshot").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/projects/${state.currentProjectId}/restore/${button.dataset.snapshotId}`, { method: "POST" });
      await loadBootstrap(state.currentProjectId);
    });
  });
}

function renderRules() {
  $("#rule-list").innerHTML = state.data.rules
    .map((rule) => {
      const active = rule.id === state.selectedRuleId;
      return `
        <div class="list-item ${active ? "selected" : ""}">
          <h4>${rule.title}</h4>
          <div class="rule-tag-row">
            <span class="mini-tag">${rule.scope_type}${rule.scope_id ? `:${rule.scope_id}` : ""}</span>
            <span class="mini-tag">${rule.rule_type}</span>
            <span class="mini-tag">P${rule.priority}</span>
            ${rule.validation_status ? `<span class="mini-tag">${rule.validation_status}</span>` : ""}
          </div>
          <p>${rule.reverse_text || "尚未有啟用版本"}</p>
          <button class="button secondary select-rule" data-rule-id="${rule.id}">選取</button>
        </div>
      `;
    })
    .join("");
  $$(".select-rule").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedRuleId = Number(button.dataset.ruleId);
      await loadRuleVersions();
    });
  });

  const selectedRule = state.data.rules.find((rule) => rule.id === state.selectedRuleId);
  if (selectedRule) {
    $("#rule-title").value = selectedRule.title;
    $("#rule-scope").value = selectedRule.scope_type;
    $("#rule-scope-id").value = selectedRule.scope_id || "";
    $("#rule-type").value = selectedRule.rule_type;
    $("#rule-priority").value = selectedRule.priority;
    $("#rule-dsl").value = selectedRule.dsl_text || "";
    $("#rule-reverse").textContent = selectedRule.reverse_text || "尚未有反向翻譯";
    $("#rule-validation").textContent = selectedRule.validation_status
      ? `${selectedRule.validation_status}：${(selectedRule.validation_report?.errors || []).concat(selectedRule.validation_report?.warnings || []).join(" / ") || "可採用"}`
      : "尚未建立版本";
  }
}

async function loadRuleVersions() {
  if (!state.selectedRuleId) return;
  const versions = await api(`/api/rules/${state.selectedRuleId}/versions`);
  $("#rule-version-list").innerHTML = versions
    .map(
      (version) => `
        <div class="list-item">
          <h4>版本 #${version.id}</h4>
          <p>${version.created_at}</p>
          <div class="meta-row">
            <span class="mini-tag">${version.validation_status}</span>
            <button class="button secondary activate-version" data-version-id="${version.id}">採用</button>
          </div>
        </div>
      `,
    )
    .join("");
  $$(".activate-version").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/rules/${state.selectedRuleId}/activate/${button.dataset.versionId}`, { method: "POST" });
      await loadBootstrap(state.currentProjectId);
      await loadRuleVersions();
    });
  });
}

function renderMaster() {
  $$(".resource-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.resource === state.activeResource);
  });
  renderMasterTable();
  renderMasterForm();
}

function renderMasterTable() {
  const resource = state.activeResource;
  const items = state.data[resource];
  if (!items) return;
  const columns = Array.from(
    new Set(
      items.flatMap((item) =>
        Object.keys(item).filter((key) => !["created_at", "updated_at", "department_name", "job_level_name"].includes(key)),
      ),
    ),
  );
  $("#master-table").innerHTML = `
    <table class="data-table">
      <thead>
        <tr>${columns.map((column) => `<th>${column}</th>`).join("")}<th>操作</th></tr>
      </thead>
      <tbody>
        ${items
          .map(
            (item) => `
              <tr>
                ${columns
                  .map((column) => `<td>${Array.isArray(item[column]) ? item[column].join(", ") : item[column] ?? ""}</td>`)
                  .join("")}
                <td>
                  <button class="button secondary edit-resource" data-id="${item.id}">編輯</button>
                  <button class="button danger delete-resource" data-id="${item.id}">刪除</button>
                </td>
              </tr>
            `,
          )
          .join("")}
      </tbody>
    </table>
  `;
  $$(".edit-resource").forEach((button) => {
    button.addEventListener("click", () => {
      state.editingRecordId = button.dataset.id;
      renderMasterForm();
    });
  });
  $$(".delete-resource").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/${resource}/${button.dataset.id}`, { method: "DELETE" });
      state.editingRecordId = null;
      await loadBootstrap(state.currentProjectId);
    });
  });
}

function renderMasterForm() {
  const resource = state.activeResource;
  const fields = masterFieldMap[resource];
  const item = state.data[resource].find((entry) => entry.id === state.editingRecordId) || {};
  $("#master-form-title").textContent = state.editingRecordId ? `編輯 ${state.editingRecordId}` : "新增資料";
  $("#master-form").innerHTML = fields
    .map(([field, label]) => {
      const value = Array.isArray(item[field]) ? item[field].join(", ") : item[field] ?? (field === "active" ? 1 : "");
      return `
        <label class="field ${field === "notes" ? "field-full" : ""}">
          <span>${label}</span>
          <input name="${field}" value="${String(value).replaceAll('"', "&quot;")}" />
        </label>
      `;
    })
    .join("");
}

function renderOptimization() {
  if (!state.currentJobId) {
    $("#opt-status").textContent = "尚未開始最佳化。";
  }
}

function renderSettings() {
  $("#setting-llm-mode").value = state.data.settings.llm_mode || "fallback";
  $("#setting-model").value = state.data.settings.openai_model || "gpt-4.1-mini";
}

function openDrawer(nurseId, date) {
  state.selectedCell = { nurseId, date };
  const nurse = state.data.nurses.find((item) => item.id === nurseId);
  const assignment = state.data.assignments.find((item) => item.nurse_id === nurseId && item.date === date);
  $("#drawer-context").innerHTML = `<strong>${nurse.id} ${nurse.name}</strong><br />${date}`;
  $("#drawer-shift").innerHTML = state.data.shift_codes
    .map((shift) => `<option value="${shift.id}" ${shift.id === (assignment?.shift_code_id || "OFF") ? "selected" : ""}>${shift.id} ${shift.name}</option>`)
    .join("");
  $("#drawer-note").value = assignment?.note || "";
  $("#calendar-drawer").classList.remove("hidden");
}

function closeDrawer() {
  $("#calendar-drawer").classList.add("hidden");
}

async function saveDrawer() {
  if (!state.selectedCell) return;
  await api("/api/schedule/assignments", {
    method: "PUT",
    body: JSON.stringify({
      project_id: state.currentProjectId,
      changes: [
        {
          nurse_id: state.selectedCell.nurseId,
          date: state.selectedCell.date,
          shift_code: $("#drawer-shift").value,
          note: $("#drawer-note").value,
        },
      ],
      snapshot_title: `手動調整 ${state.selectedCell.date}`,
      ui_state: getUiState(),
    }),
  });
  closeDrawer();
  await loadBootstrap(state.currentProjectId);
}

async function handleRuleCreate() {
  const created = await api("/api/rules", {
    method: "POST",
    body: JSON.stringify({
      title: $("#rule-title").value,
      scope_type: $("#rule-scope").value,
      scope_id: $("#rule-scope-id").value || null,
      rule_type: $("#rule-type").value,
      priority: Number($("#rule-priority").value || 100),
    }),
  });
  state.selectedRuleId = created.id;
  await loadBootstrap(state.currentProjectId);
  await loadRuleVersions();
}

async function handleRuleGenerate() {
  if (!state.selectedRuleId) {
    await handleRuleCreate();
  }
  $("#rule-stream").textContent = "";
  $("#rule-validation").textContent = "轉譯中...";
  $("#rule-reverse").textContent = "";
  await streamPost(`/api/rules/${state.selectedRuleId}/versions:from_nl`, {
    text: $("#rule-nl").value,
    scope_type: $("#rule-scope").value,
    scope_id: $("#rule-scope-id").value || null,
    rule_type: $("#rule-type").value,
  }, {
    token(data) {
      $("#rule-stream").textContent += data.chunk;
    },
    validation(data) {
      $("#rule-validation").textContent = `${data.status}：${[...(data.errors || []), ...(data.warnings || [])].join(" / ") || "可採用"}`;
    },
    reverse(data) {
      $("#rule-reverse").textContent = data.text;
    },
    async result() {
      await loadBootstrap(state.currentProjectId);
      await loadRuleVersions();
    },
  });
}

async function handleRuleValidate() {
  if (!state.selectedRuleId) {
    await handleRuleCreate();
  }
  const result = await api(`/api/rules/${state.selectedRuleId}/versions:from_dsl`, {
    method: "POST",
    body: JSON.stringify({
      dsl_text: $("#rule-dsl").value,
      source_nl: $("#rule-nl").value,
    }),
  });
  $("#rule-reverse").textContent = result.reverse_text;
  await loadBootstrap(state.currentProjectId);
  await loadRuleVersions();
}

async function handleOptimizationStart() {
  const coverage = JSON.parse($("#opt-coverage").value || "{}");
  const job = await api("/api/optimization/jobs", {
    method: "POST",
    body: JSON.stringify({
      project_id: state.currentProjectId,
      period: { from: $("#opt-from").value, to: $("#opt-to").value },
      solver: { time_limit_sec: Number($("#opt-time-limit").value || 30), seed: Number($("#opt-seed").value || 7) },
      weights: { multiplier: Number($("#opt-multiplier").value || 1) },
      coverage,
      snapshot_title: "最佳化結果",
    }),
  });
  state.currentJobId = job.id;
  subscribeJobStream(job.id);
}

function subscribeJobStream(jobId) {
  if (state.jobEventSource) {
    state.jobEventSource.close();
  }
  $("#opt-log").textContent = "";
  const eventSource = new EventSource(`/api/optimization/jobs/${jobId}/stream`);
  state.jobEventSource = eventSource;
  eventSource.addEventListener("progress", (event) => {
    const payload = JSON.parse(event.data);
    $("#opt-progress-bar").style.width = `${payload.progress}%`;
    $("#opt-status").textContent = `${payload.progress}% ${payload.message}`;
  });
  eventSource.addEventListener("log", (event) => {
    const payload = JSON.parse(event.data);
    $("#opt-log").textContent += `${payload.message}\n`;
    $("#opt-log").scrollTop = $("#opt-log").scrollHeight;
  });
  eventSource.addEventListener("result", async (event) => {
    const payload = JSON.parse(event.data);
    $("#opt-progress-bar").style.width = "100%";
    $("#opt-status").textContent = payload.message || payload.status;
    $("#opt-summary").textContent = JSON.stringify(payload.result_summary || {}, null, 2);
    eventSource.close();
    await loadBootstrap(state.currentProjectId);
  });
  eventSource.addEventListener("error", (event) => {
    if (event.data) {
      const payload = JSON.parse(event.data);
      $("#opt-summary").textContent = JSON.stringify(payload, null, 2);
    }
  });
}

async function handleOptimizationCancel() {
  if (!state.currentJobId) return;
  await api(`/api/optimization/jobs/${state.currentJobId}/cancel`, { method: "POST" });
}

async function handleOptimizationApply() {
  if (!state.currentJobId) return;
  await api(`/api/optimization/jobs/${state.currentJobId}/apply`, { method: "POST" });
  await loadBootstrap(state.currentProjectId);
}

async function handleDslRun() {
  $("#dsl-stream").textContent = "";
  $("#dsl-validation").textContent = "測試中...";
  $("#dsl-reverse").textContent = "";
  await streamPost("/api/dsl/test", {
    text: $("#dsl-nl").value,
    scope_type: $("#rule-scope").value,
    scope_id: $("#rule-scope-id").value || null,
    rule_type: $("#rule-type").value,
  }, {
    token(data) {
      $("#dsl-stream").textContent += data.chunk;
      $("#dsl-input").value = $("#dsl-stream").textContent;
    },
    validation(data) {
      $("#dsl-validation").textContent = `${data.status}：${[...(data.errors || []), ...(data.warnings || [])].join(" / ") || "可採用"}`;
    },
    reverse(data) {
      $("#dsl-reverse").textContent = data.text;
    },
  });
}

async function handleDslValidate() {
  await streamPost("/api/dsl/test", { dsl_text: $("#dsl-input").value }, {
    validation(data) {
      $("#dsl-validation").textContent = `${data.status}：${[...(data.errors || []), ...(data.warnings || [])].join(" / ") || "可採用"}`;
    },
    reverse(data) {
      $("#dsl-reverse").textContent = data.text;
    },
  });
}

async function handleSettingsSave() {
  await api("/api/settings", {
    method: "POST",
    body: JSON.stringify({
      llm_mode: $("#setting-llm-mode").value,
      openai_model: $("#setting-model").value,
      openai_api_key: $("#setting-api-key").value,
    }),
  });
  $("#setting-result").textContent = "設定已儲存。若未填 API Key，系統會自動使用 fallback。";
  $("#setting-api-key").value = "";
  await loadBootstrap(state.currentProjectId);
}

async function handleMasterSave() {
  const resource = state.activeResource;
  const formData = new FormData($("#master-form"));
  const payload = Object.fromEntries(formData.entries());
  if (resource === "nurses") {
    payload.skills = (payload.skills || "").split(",").map((item) => item.trim()).filter(Boolean);
  }
  payload.active = Number(payload.active || 1);
  if (state.editingRecordId) {
    await api(`/api/${resource}/${state.editingRecordId}`, { method: "PUT", body: JSON.stringify(payload) });
  } else {
    await api(`/api/${resource}`, { method: "POST", body: JSON.stringify(payload) });
  }
  state.editingRecordId = null;
  await loadBootstrap(state.currentProjectId);
}

function bindEvents() {
  $$(".nav-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab;
      $$(".nav-tab").forEach((item) => item.classList.toggle("active", item === button));
      $$(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${state.activeTab}`));
      $("#topbar-title").textContent = titleForTab(state.activeTab);
    });
  });

  $("#project-select").addEventListener("change", async (event) => {
    await loadBootstrap(Number(event.target.value));
  });
  $("#calendar-refresh").addEventListener("click", async () => loadBootstrap(state.currentProjectId));
  $("#calendar-save-snapshot").addEventListener("click", async () => {
    await api(`/api/projects/${state.currentProjectId}/snapshots`, {
      method: "POST",
      body: JSON.stringify({ title: "手動快照", ui_state: getUiState() }),
    });
    await loadBootstrap(state.currentProjectId);
  });
  $("#drawer-close").addEventListener("click", closeDrawer);
  $("#drawer-save").addEventListener("click", saveDrawer);

  $("#rule-create").addEventListener("click", handleRuleCreate);
  $("#rule-delete").addEventListener("click", async () => {
    if (!state.selectedRuleId) return;
    await api(`/api/rules/${state.selectedRuleId}`, { method: "DELETE" });
    state.selectedRuleId = null;
    await loadBootstrap(state.currentProjectId);
  });
  $("#rule-generate").addEventListener("click", handleRuleGenerate);
  $("#rule-validate").addEventListener("click", handleRuleValidate);

  $$(".resource-tab").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeResource = button.dataset.resource;
      state.editingRecordId = null;
      renderMaster();
    });
  });
  $("#master-save").addEventListener("click", handleMasterSave);
  $("#master-reset").addEventListener("click", () => {
    state.editingRecordId = null;
    renderMasterForm();
  });

  $("#opt-start").addEventListener("click", handleOptimizationStart);
  $("#opt-cancel").addEventListener("click", handleOptimizationCancel);
  $("#opt-apply").addEventListener("click", handleOptimizationApply);

  $("#dsl-run").addEventListener("click", handleDslRun);
  $("#dsl-validate").addEventListener("click", handleDslValidate);
  $("#setting-save").addEventListener("click", handleSettingsSave);
}

async function boot() {
  bindEvents();
  await loadBootstrap();
  await loadRuleVersions();
}

boot().catch((error) => {
  console.error(error);
  alert(error.message || "初始化失敗");
});
