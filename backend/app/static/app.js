const API = "/api";
const $ = (id) => document.getElementById(id);
const state = { token: localStorage.getItem("campus_token") || "", user: null, page: "overview", courses: [], dashboard: null, draft: null, editing: false, dismissDemo: false, lastAnswer: null };
const titles = {
  overview: ["项目概览", "从课程经验入库到引用式问答，先跑通可验证的知识闭环。"],
  search: ["经验检索", "按课程、学期和关键词查找已发布且允许公开的经验与资料。"],
  qa: ["AI 问答", "仅检索已审核、许可有效的证据；每个来源都可以打开或追溯。"],
  submit: ["提交课程经验", "保存原始表达，再由 AI 整理成草稿；只有你确认后才会进入审核。"],
  mine: ["我的记录", "查看自己的原文、结构化草稿和当前审核状态。"],
  review: ["审核工作台", "审核员核查内容、隐私、来源和具体主张，再决定是否公开。"],
  sources: ["来源管理", "登记公开回答和资料的出处、适用范围、使用许可与转载关系。"],
  scoring: ["可信度评分", "解释 A/S/T/D 分项与排序；参考分表示证据质量，不是事实为真的概率。"],
  feedback: ["反馈与纠错", "反馈待审核，不会直接改写知识库。反馈处理属于 P1。"],
  admin: ["管理与交付", "维护账号角色、规则版本、日志和交付前核查项。"]
};
const roleLabels = { reader: "查询者", contributor: "贡献者", reviewer: "审核员", admin: "管理员" };
const statusLabels = { draft: "草稿", pending_review: "待审核", returned: "退回修改", rejected: "已拒绝", published: "已发布", withdrawn: "已下架", pending: "待确认", active: "有效", maintained: "维持原样", updated: "已更新", disputed: "标记争议", needs_more_evidence: "待补充证据" };
const permissionLabels = { link_only: "仅可展示链接", abstract_allowed: "允许摘要用于生成", full_text_allowed: "允许全文用于生成", pending: "待确认", prohibited: "禁止使用" };
const linkStatusLabels = { unchecked: "链接待核验", verified: "链接已核验", invalid: "链接失效", demo_placeholder: "演示占位链接", not_applicable: "内部记录" };

function esc(v) { return String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }
function prettyDate(s) { if (!s) return "日期未注明"; const d = new Date(s); return Number.isNaN(d.getTime()) ? esc(s) : d.toLocaleDateString("zh-CN", {year:"numeric",month:"2-digit",day:"2-digit"}); }
function roleHas(...roles) { return !!state.user && roles.some(r => (state.user.roles || []).includes(r)); }
function roleText() { return state.user ? (state.user.roles || []).map(r => roleLabels[r] || r).join(" / ") : "访客"; }
function tag(text, cls="gray") { return `<span class="tag ${cls}">${esc(text)}</span>`; }
function scoreClass(grade) { return grade === "较高" ? "" : grade === "中等" ? "medium" : grade === "较低" ? "low" : "none"; }
function scorePill(score, grade) { return score == null ? `<span class="score-pill none">${esc(grade || "不计分")}</span>` : `<span class="score-pill ${scoreClass(grade)}">${Number(score).toFixed(1)} · ${esc(grade)}</span>`; }
function toast(message, error=false) { const t = $("toast"); t.textContent = message; t.style.background = error ? "#962f24" : "#111214"; t.classList.add("show"); window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => t.classList.remove("show"), 3400); }
async function api(path, options={}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const method = String(options.method || "GET").toUpperCase();
  const url = API + path;
  window.dispatchEvent(new CustomEvent("campus:api-request", { detail: { phase: "start", path, method } }));
  let response;
  try {
    response = await window.fetch(url, {
      ...options,
      headers,
      cache: options.cache || "no-store",
      body: options.body && typeof options.body !== "string" && !(options.body instanceof FormData) ? JSON.stringify(options.body) : options.body
    });
  } catch (networkError) {
    let healthOk = false;
    try {
      const healthResponse = await window.fetch(`${API}/health`, { cache: "no-store" });
      healthOk = healthResponse.ok;
    } catch (_) { /* Health probe intentionally has no UI side effects. */ }
    const message = healthOk
      ? `接口 ${url} 连接失败，但 /api/health 可以访问。请查看运行 Uvicorn 的终端，检查该接口的异常。`
      : `无法连接本地后端接口 ${url}。请确认 Uvicorn 仍在运行，然后在新标签打开 ${window.location.origin}/api/health 检查服务。`;
    throw new Error(message);
  } finally {
    window.dispatchEvent(new CustomEvent("campus:api-request", { detail: { phase: "end", path, method } }));
  }
  let data = {};
  try { data = await response.json(); } catch (_) { data = {}; }
  if (!response.ok) throw new Error(data.detail || data.message || `接口 ${url} 返回 HTTP ${response.status}`);
  return data;
}
function setUser(user, token) {
  state.user = user || null;
  if (token !== undefined) {
    state.token = token || "";
    if (token) localStorage.setItem("campus_token", token); else localStorage.removeItem("campus_token");
  }
  renderHeader();
}
function renderHeader() {
  const indicator = $("user-indicator");
  if (state.user) {
    const first = (state.user.display_name || state.user.username || "用").slice(0,1);
    indicator.innerHTML = `<div class="avatar">${esc(first)}</div><div><strong>${esc(state.user.display_name || state.user.username)}</strong><small>${esc(roleText())}</small></div>`;
    $("login-open").classList.add("hidden"); $("logout-button").classList.remove("hidden");
  } else {
    indicator.innerHTML = `<div class="avatar">访</div><div><strong>访客</strong><small>可浏览公开内容</small></div>`;
    $("login-open").classList.remove("hidden"); $("logout-button").classList.add("hidden");
  }
  document.querySelectorAll(".nav-item").forEach(btn => {
    const p = btn.dataset.view;
    const gated = (p === "submit" || p === "mine") && !roleHas("contributor");
    const reviewer = p === "review" && !roleHas("reviewer", "admin");
    const admin = p === "admin" && !roleHas("admin");
    btn.classList.toggle("nav-restricted", gated || reviewer || admin);
  });
}
function setPageTitle() {
  const [title] = titles[state.page] || titles.overview;
  $("page-crumb").textContent = title;
  document.querySelectorAll(".nav-item").forEach(btn => btn.classList.toggle("active", btn.dataset.view === state.page));
}
function pageHeading(eyebrow, title, description, action="") {
  return `<div class="page-heading"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${action ? `<div class="heading-actions">${action}</div>` : ""}</div>`;
}
function cardHead(title, subtitle="", right="") { return `<div class="card-header"><div><h2 class="card-title">${esc(title)}</h2>${subtitle ? `<div class="card-subtitle">${esc(subtitle)}</div>` : ""}</div>${right}</div>`; }
function emptyState(title, detail, icon="⌕") { return `<div class="empty-state"><div class="empty-icon">${icon}</div><strong>${esc(title)}</strong><p>${esc(detail)}</p></div>`; }
function courseOptions(selected="") { return `<option value="">全部课程</option>` + state.courses.map(c => `<option value="${c.id}" ${String(selected)===String(c.id)?"selected":""}>${esc(c.name)} · ${esc(c.school)}</option>`).join(""); }
function statusTag(status) { const cls = status === "published" || status === "active" ? "green" : ["pending_review","pending"].includes(status) ? "amber" : ["rejected","withdrawn","prohibited"].includes(status) ? "red" : status === "returned" ? "purple" : "gray"; return tag(statusLabels[status] || status, cls); }
function sourceTypeLabel(t) { return ({student_experience:"学生经验",external_answer:"外部公开回答",official_document:"官方资料",other:"其他来源"})[t] || t; }

async function refreshShared() {
  try { state.courses = await api("/courses"); } catch (_) { state.courses = []; }
  try { state.dashboard = await api("/dashboard"); } catch (_) { state.dashboard = null; }
  if (roleHas("reviewer", "admin")) {
    try { const q = await api("/review/queue"); $("review-count").textContent = q.results.length; } catch (_) { $("review-count").textContent = "!"; }
  } else $("review-count").textContent = "—";
}
async function renderPage() {
  setPageTitle();
  await refreshShared();
  const host = $("page-content");
  host.innerHTML = `<div class="card card-pad">正在加载页面…</div>`;
  try {
    switch (state.page) {
      case "overview": await renderOverview(host); break;
      case "search": await renderSearch(host); break;
      case "qa": await renderQA(host); break;
      case "submit": await renderSubmit(host); break;
      case "mine": await renderMine(host); break;
      case "review": await renderReview(host); break;
      case "sources": await renderSources(host); break;
      case "scoring": await renderScoring(host); break;
      case "feedback": await renderFeedback(host); break;
      case "admin": await renderAdmin(host); break;
      default: state.page = "overview"; await renderOverview(host);
    }
    applyPageSectionSurfaces(host);
  } catch (e) {
    host.innerHTML = pageHeading("请求出错", titles[state.page][0], "当前页面没有正常加载。请先检查后端连接，再重试。") +
      `<section class="request-error-band"><div class="notice danger"><span class="notice-icon">!</span><div>${esc(e.message)}</div></div><div class="request-error-actions"><button class="btn btn-primary" id="retry-page-load" type="button">重试此页面</button><a class="btn btn-quiet" href="/api/health" target="_blank" rel="noopener noreferrer">检查后端健康状态 ↗</a></div></section>`;
    const retry = $("retry-page-load");
    if (retry) retry.addEventListener("click", () => navigate(state.page));
  }
}
function applyPageSectionSurfaces(host) {
  host.dataset.page = state.page;
  const add = (selector, ...classes) => host.querySelectorAll(selector).forEach(el => el.classList.add(...classes));
  const addOne = (selector, ...classes) => { const el = host.querySelector(selector); if (el) el.classList.add(...classes); };
  switch (state.page) {
    case "search":
      addOne("#search-form", "surface-band", "surface-sand");
      addOne("#search-results", "surface-results");
      break;
    case "qa":
      addOne(".qa-input-card", "surface-band", "surface-sand");
      addOne(".qa-layout > .card:last-child", "surface-band", "surface-peach");
      break;
    case "submit":
      add(".grid.grid-2 > .card:first-child", "surface-band", "surface-sand");
      add(".grid.grid-2 > .card:last-child", "surface-band", "surface-sage");
      addOne("#draft-editor", "surface-band", "surface-peach");
      break;
    case "mine":
      addOne(":scope > .card", "surface-results");
      break;
    case "review":
      add(".review-card:nth-child(even)", "surface-row-sand");
      add(".review-card:nth-child(odd)", "surface-row-white");
      break;
    case "sources":
      const sourceForm = host.querySelector("#source-create-form");
      if (sourceForm && sourceForm.closest(".card")) sourceForm.closest(".card").classList.add("surface-band", "surface-sand");
      addOne(":scope > .card:last-child", "surface-results");
      break;
    case "scoring":
      addOne(":scope > .notice", "surface-band", "surface-peach");
      addOne(":scope > .card", "surface-results");
      add(".grid.grid-2 > .card:first-child", "surface-band", "surface-sage");
      add(".grid.grid-2 > .card:last-child", "surface-band", "surface-sand");
      break;
    case "feedback":
      add(".grid.grid-2 > .card:first-child", "surface-band", "surface-sand");
      add(".grid.grid-2 > .card:last-child", "surface-band", "surface-peach");
      break;
    case "admin":
      add(".grid.grid-2 > .card:first-child", "surface-band", "surface-sand");
      add(".grid.grid-2 > .card:last-child", "surface-band", "surface-sage");
      addOne(":scope > .card:last-child", "surface-band", "surface-peach");
      break;
    default:
      break;
  }
}

function navigate(page) { state.page = page; renderPage(); }

async function renderOverview(host) {
  const d = state.dashboard || { published_experiences: 0, pending_review: 0, active_sources: 0, courses: 0 };
  host.innerHTML = pageHeading(
    "CAMPUS MEMORY ARCHIVE",
    "经验，让下一届少走弯路。",
    "把分散的课程体验整理为可检索、可追溯、可持续更新的校园知识。",
    `<button class="btn btn-primary" data-go="submit">＋ 提交一条经验</button><button class="btn btn-quiet" data-go="qa">试用 AI 问答 ↗</button>`
  ) + `
  <section class="metric-strip" aria-label="知识库概况">
    <article class="metric-item"><div class="metric-top">已发布经验</div><div class="metric-value">${d.published_experiences}</div><div class="metric-foot">包含明确标注的合成演示数据</div></article>
    <article class="metric-item"><div class="metric-top">待审核</div><div class="metric-value">${d.pending_review}</div><div class="metric-foot">审核前不进入公开检索与 AI 上下文</div></article>
    <article class="metric-item"><div class="metric-top">可用证据来源</div><div class="metric-value">${d.active_sources}</div><div class="metric-foot">已按状态、许可和转载关系过滤</div></article>
    <article class="metric-item"><div class="metric-top">课程目录</div><div class="metric-value">${d.courses}</div><div class="metric-foot">覆盖多门课程与多个学期</div></article>
  </section>

  <section class="overview-workflow editorial-section" aria-labelledby="workflow-heading">
    <div class="editorial-heading">
      <div><div class="eyebrow">01 / THE KNOWLEDGE LIFECYCLE</div><h2 id="workflow-heading">从一段经验，到一个有依据的答案。</h2><p>首期围绕课程经验建立闭环。每一步保留状态、原文与来源关联。</p></div>
      ${tag("P0 · 首期核心", "gray")}
    </div>
    <div class="step-flow" role="list">
      <article class="step-item" role="listitem"><span class="step-number">01 <i>COLLECT</i></span><strong>提交原文</strong><p>保留原始表达，创建稳定记录 ID。</p></article>
      <article class="step-item" role="listitem"><span class="step-number">02 <i>ORGANIZE</i></span><strong>AI 整理草稿</strong><p>抽取难点、作业、考核与建议；缺失不猜。</p></article>
      <article class="step-item" role="listitem"><span class="step-number">03 <i>CONFIRM</i></span><strong>本人确认</strong><p>贡献者可修改字段，原文独立保存。</p></article>
      <article class="step-item" role="listitem"><span class="step-number">04 <i>REVIEW</i></span><strong>人工审核</strong><p>核查权限、隐私、重复与适用范围。</p></article>
      <article class="step-item" role="listitem"><span class="step-number">05 <i>PASS ON</i></span><strong>检索与问答</strong><p>回答绑定可追溯证据，并说明限制。</p></article>
    </div>
  </section>

  <section class="overview-lower editorial-section" aria-label="设计原则与演示数据说明">
    <div class="principles-panel">
      <div class="editorial-heading compact"><div><div class="eyebrow">02 / PRODUCT PRINCIPLES</div><h2>可信知识，从出处开始。</h2></div>${tag("需求 V1.0", "gray")}</div>
      <div class="principle-list">
        <div class="principle-row"><span class="principle-index">01</span><div><strong>原文与 AI 整理结果分开保存</strong><p>模型失败时仍保留提交内容；AI 输出需要贡献者确认。</p></div><span class="principle-mark" aria-hidden="true">↗</span></div>
        <div class="principle-row"><span class="principle-index">02</span><div><strong>权限过滤先于检索</strong><p>未审核、已下架或许可失效的内容不进入公开检索。</p></div><span class="principle-mark" aria-hidden="true">↗</span></div>
        <div class="principle-row"><span class="principle-index">03</span><div><strong>相关性与可信度分开计算</strong><p>查到相似材料，不等于材料足够可靠。</p></div><span class="principle-mark" aria-hidden="true">↗</span></div>
      </div>
    </div>
    <aside class="demo-disclosure">
      <div class="eyebrow">DATA DISCLOSURE</div>
      <div class="disclosure-marker"><span></span> 合成演示数据</div>
      <h2>先验证规则，再替换为获准资料。</h2>
      <p>内置课程、经验及 M1–M4 资料用于验证交互、过滤、评分和验收路径。example.org 链接为占位地址，不代表真实调查或已获授权的外部内容。</p>
      <div class="disclosure-actions"><button class="btn btn-quiet" data-go="scoring">查看可信度规则 ↗</button><button class="btn btn-quiet" data-go="search">浏览已发布经验 ↗</button></div>
    </aside>
  </section>`;
  host.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => navigate(b.dataset.go)));
}

function resultCard(item, index) {
  const sourceInfo = `${sourceTypeLabel(item.source_type)}${item.course_name ? " · " + item.course_name : ""}${item.term ? " · " + item.term : ""}`;
  const tags = [item.demo_data ? tag("演示数据", "amber") : "", item.navigation_only ? tag("仅链接导航", "gray") : "", item.link_status === "demo_placeholder" ? tag("演示占位链接", "amber") : item.link_status === "unchecked" ? tag("链接待核验", "amber") : "", item.most_credible ? tag("最可信参考", "green") : ""].join("");
  return `<article class="result-item"><div class="result-top"><div><h3 class="result-title">${esc(item.title)}</h3><div class="result-meta"><span>${esc(sourceInfo)}</span><span>编号 ${esc(item.source_code || item.id)}</span></div></div><div class="tag-line">${tags}${item.score != null ? scorePill(item.score,item.grade) : tag("未评分", "gray")}</div></div><p class="result-excerpt">${esc((item.content_excerpt || "该来源未登记可显示的正文。").slice(0,500))}</p><div class="result-actions"><button class="btn btn-ghost btn-inline" data-source-details="${item.id}">查看详情</button>${item.url ? `<a class="btn btn-ghost btn-inline" href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">打开原始链接 ↗</a>` : ""}${item.scope_note ? `<span class="small muted">${esc(item.scope_note)}</span>` : ""}</div></article>`;
}
function bindSourceDetails(host) { host.querySelectorAll("[data-source-details]").forEach(b => b.addEventListener("click", async () => { try { const sources = await api("/sources"); const item = sources.results.find(x => String(x.id) === b.dataset.sourceDetails); if (item) showSourceDetail(item); else toast("来源详情不可用", true); } catch(e) { toast(e.message,true); } })); }
function showSourceDetail(item) {
  $("detail-content").innerHTML = `<div class="dialog-head"><div><div class="eyebrow">SOURCE TRACEABILITY</div><h2 style="margin:7px 0">${esc(item.title)}</h2><p>${esc(item.source_code)} · ${esc(sourceTypeLabel(item.source_type))}</p></div><button class="icon-close" data-close-detail>×</button></div>
  <div class="tag-line">${statusTag(item.status)}${tag(permissionLabels[item.permission] || item.permission, item.permission === "prohibited" ? "red" : item.permission === "pending" ? "amber" : "blue")}${item.demo_data ? tag("合成演示数据", "amber") : ""}${item.duplicate_of_code ? tag("转载归并至 " + item.duplicate_of_code, "purple") : ""}</div>
  <div class="detail-grid"><div class="detail-score"><span>A · 一致性</span><strong>${item.score_a == null ? "—" : item.score_a}</strong></div><div class="detail-score"><span>S · 可追溯</span><strong>${item.score_s == null ? "—" : item.score_s}</strong></div><div class="detail-score"><span>T · 时效性</span><strong>${item.score_t == null ? "—" : item.score_t}</strong></div><div class="detail-score"><span>D · 完整性</span><strong>${item.score_d == null ? "—" : item.score_d}</strong></div></div>
  <div class="subsection-title">内容 / 摘要</div><div class="policy-callout" style="white-space:pre-wrap">${esc(item.content_excerpt || "未登记正文")}</div>
  <div class="subsection-title">来源与范围</div><div class="policy-callout">作者：${esc(item.author || "未注明")}<br>学校 / 课程：${esc(item.school || "未注明")} / ${esc(item.course_name || "未指定")}<br>适用学期：${esc(item.term || "未注明")}<br>可信度：${item.score == null ? "不计分" : Number(item.score).toFixed(1) + "（" + esc(item.grade) + "）"}<br>链接状态：${esc(item.link_status_note || linkStatusLabels[item.link_status] || "未记录")}<br>限制：${esc((item.limitations || []).join("；") || "未记录")}<br>${item.url ? `原始链接：<a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.url)}</a>` : "内部记录以稳定记录 ID 定位。"}</div>
  <div class="form-footer"><button class="btn btn-primary" data-close-detail>关闭</button></div>`;
  $("detail-dialog").showModal(); $("detail-content").querySelectorAll("[data-close-detail]").forEach(b => b.addEventListener("click", () => $("detail-dialog").close()));
}

async function renderSearch(host) {
  host.innerHTML = pageHeading("KNOWLEDGE SEARCH", "经验检索", titles.search[1]) + `<div class="card"><form id="search-form" class="filters"><div class="field"><label class="field-label">课程</label><select class="select" id="search-course">${courseOptions()}</select></div><div class="field"><label class="field-label">学期</label><select class="select" id="search-term"><option value="">全部学期</option><option>2026春</option><option>2025秋</option><option>2024秋</option></select></div><div class="field"><label class="field-label">关键词</label><input class="input" id="search-query" placeholder="例如：期末复习、矩阵、树与图"></div><button class="btn btn-primary" type="submit">检索资料</button></form><div id="search-results"><div class="empty-state">正在读取已发布资料…</div></div></div><div class="spacer-20"></div><div class="notice"><span class="notice-icon">i</span><div>搜索结果只包含当前已发布且许可有效的记录。仅可展示链接的来源可作导航，但不作为 AI 问答证据，也不参与可信度评分。</div></div>`;
  const form = $("search-form"), resultsHost = $("search-results");
  async function doSearch() {
    resultsHost.innerHTML = `<div class="empty-state">正在检索…</div>`;
    const params = new URLSearchParams(); const course = $("search-course").value, term = $("search-term").value, q = $("search-query").value.trim();
    if (course) params.set("course_id", course); if (term) params.set("term", term); if (q) params.set("q", q);
    try {
      const data = await api(`/search?${params.toString()}`);
      resultsHost.innerHTML = `<div class="result-bar"><span>找到 <strong>${data.count}</strong> 条匹配记录</span><span>状态与权限过滤已启用</span></div>` + (data.results.length ? `<div class="result-list">${data.results.map(resultCard).join("")}</div>` : emptyState("没有找到匹配资料", "可尝试移除学期限制或使用更短关键词。未发布与已下架记录不会出现在这里。"));
      bindSourceDetails(resultsHost);
    } catch(e) { resultsHost.innerHTML = `<div class="notice danger">${esc(e.message)}</div>`; }
  }
  form.addEventListener("submit", e => { e.preventDefault(); doSearch(); });
  await doSearch();
}

async function renderQA(host) {
  host.innerHTML = pageHeading("RETRIEVAL AUGMENTED ANSWERS", "AI 问答", titles.qa[1]) + `<div class="qa-layout"><div class="card qa-input-card"><div class="eyebrow">ASK CAMPUS MEMORY</div><h2 style="margin:7px 0 8px;font-size:18px">你想了解哪门课程？</h2><p class="card-subtitle" style="margin:0 0 18px">问题尽量包含课程、学期或具体主题。当前无模型密钥时使用证据片段模板，不会声称已调用外部大模型。</p><form id="qa-form"><div class="field"><label class="field-label">问题</label><textarea class="textarea qa-question" id="qa-question" required minlength="3" placeholder="例如：线性代数期末复习可以怎么准备？"></textarea></div><div class="form-grid" style="margin-top:13px"><div class="field"><label class="field-label">课程（可选）</label><select class="select" id="qa-course">${courseOptions()}</select></div><div class="field"><label class="field-label">学期（可选）</label><select class="select" id="qa-term"><option value="">不指定</option><option>2026春</option><option>2025秋</option><option>2024秋</option></select></div></div><div class="form-footer"><button class="btn btn-primary" type="submit">检索证据并回答　→</button></div></form><div class="policy-callout" style="margin-top:14px">回答规则：只引用当前已审核且使用许可有效的内容。若无足够证据，系统应明确提示不足，而不是编造结论或引用。</div></div><div class="card"><div class="card-header"><div><h2 class="card-title">回答与引用</h2><div class="card-subtitle">引用源可定位；参考分附带分项依据。</div></div>${tag("RAG", "blue")}</div><div id="qa-result" class="card-body">${emptyState("等待提问", "提交问题后，这里会显示回答、证据来源与适用限制。", "✳")}</div></div></div>`;
  $("qa-form").addEventListener("submit", async e => {
    e.preventDefault(); const btn = e.currentTarget.querySelector("button[type=submit]"); btn.disabled = true; btn.textContent = "正在检索证据…";
    const q = $("qa-question").value.trim(), course = $("qa-course").value, term = $("qa-term").value;
    try {
      const result = await api("/qa", {method:"POST", body:{question:q,course_id:course?Number(course):null,term:term||null}});
      state.lastAnswer = result;
      const citationHTML = result.citations.length ? `<div class="subsection-title">引用来源（${result.citations.length}）</div>${result.citations.map((c,i)=>`<div class="citation-item"><div class="citation-title">[${i+1}] ${esc(c.title)} <span class="mono muted">${esc(c.source_code)}</span></div><div class="citation-meta"><span>${esc(sourceTypeLabel(c.source_type))}</span><span>${esc(c.course_name || "课程未注明")}</span><span>${esc(c.term || "学期未注明")}</span>${c.demo_data?`<span>${tag("演示数据","amber")}</span>`:""}</div><div style="margin-top:7px">${scorePill(c.score,c.grade)} ${c.most_credible?tag("最可信参考","green"):""}</div>${c.scope_note?`<p class="small muted">${esc(c.scope_note)}</p>`:""}<button class="btn btn-ghost btn-inline" data-cite-detail="${c.id}" style="margin-top:8px">展开评分依据</button></div>`).join("")}` : `<div class="notice warning" style="margin-top:13px">未找到足够的可用证据。系统没有生成无来源结论。</div>`;
      $("qa-result").innerHTML = `<div class="tag-line">${result.sufficiency === "supported"?tag("存在多条可用证据","green"):result.sufficiency === "limited"?tag("样本有限","amber"):result.sufficiency === "conflict"?tag("存在冲突","red"):tag("证据不足","gray")}${tag(result.model_mode === "configured-model"?"已配置模型":"证据模板模式", "blue")}</div><div class="qa-answer">${esc(result.answer)}</div><div class="notice" style="margin-top:12px"><span class="notice-icon">i</span><div>${esc(result.notice)} ${esc(result.demo_warning || "")}</div></div>${citationHTML}`;
      $("qa-result").querySelectorAll("[data-cite-detail]").forEach(b=>b.addEventListener("click",async()=>{try{const c=await api(`/sources/${b.dataset.citeDetail}`);showSourceDetail(c);}catch(e){toast(e.message,true);}}));
    } catch(err) { $("qa-result").innerHTML = `<div class="notice danger">${esc(err.message)}</div>`; }
    finally { btn.disabled = false; btn.textContent = "检索证据并回答　→"; }
  });
}

function experienceEditor(exp) {
  return `<div id="draft-editor" class="card card-pad" style="margin-top:18px"><div class="section-title-row"><div><h2>AI 整理草稿 · #EXP-${exp.id}</h2><p>原文单独保存；下面字段可以编辑。没有在原文中提到的信息不要补猜。</p></div>${statusTag(exp.status)}</div><div class="notice success" style="margin-bottom:15px"><span class="notice-icon">✓</span><div>原文已先行保存。抽取模式：${esc(exp.ai_mode === "configured-model" ? "已配置模型" : exp.ai_mode === "演示数据" ? "演示数据" : "规则回退")}。确认前不会公开。</div></div>${exp.privacy_warnings?.length?`<div class="notice warning" style="margin-bottom:15px"><span class="notice-icon">!</span><div>隐私检查提示：${esc(exp.privacy_warnings.join("、"))}。请先在上方“继续编辑经验”中修订文本；首次提交快照会保留，检测到风险的内容无法发布。</div></div>`:""}<div class="policy-callout" style="margin-bottom:14px"><strong>当前文本（只读于此处；可从“我的记录”进入修订）</strong><br>${esc(exp.raw_text)}</div><form id="draft-edit-form"><div class="form-grid"><div class="field"><label class="field-label">学习难点</label><textarea class="textarea small" name="difficulty">${esc(exp.difficulty)}</textarea></div><div class="field"><label class="field-label">作业情况</label><textarea class="textarea small" name="assignments">${esc(exp.assignments)}</textarea></div><div class="field"><label class="field-label">考核信息</label><textarea class="textarea small" name="assessment">${esc(exp.assessment)}</textarea></div><div class="field"><label class="field-label">备考建议</label><textarea class="textarea small" name="advice">${esc(exp.advice)}</textarea></div></div><div class="form-footer"><button class="btn btn-ghost" type="button" id="save-draft">保存字段</button><button class="btn btn-primary" type="submit">我已核对，提交审核　→</button></div></form></div>`;
}
async function renderSubmit(host) {
  if (!roleHas("contributor")) {
    host.innerHTML = pageHeading("CONTRIBUTE", "提交课程经验", titles.submit[1]) + `<div class="card card-pad">${emptyState("请先使用贡献者账号登录", "提交和修改记录需要贡献者权限。点击右上角登录，并选择贡献者演示账号。", "＋")}<div class="form-footer"><button class="btn btn-primary" id="submit-login">登录为贡献者</button></div></div>`;
    $("submit-login").addEventListener("click",()=>openLogin("contributor_demo")); return;
  }
  const edit = state.draft;
  host.innerHTML = pageHeading("CONTRIBUTE EXPERIENCE", edit ? "继续编辑经验" : "提交一条课程经验", titles.submit[1]) + `<div class="grid grid-2"><div class="card card-pad"><div class="section-title-row"><h2>经验原文</h2>${tag("原文保留", "green")}</div><form id="submit-form"><div class="field"><label class="field-label">课程</label><select class="select" name="course_id" required>${state.courses.filter(c=>c.name).map(c=>`<option value="${c.id}" ${edit && String(edit.course_id)===String(c.id)?"selected":""}>${esc(c.name)} · ${esc(c.school)}</option>`).join("")}</select></div><div class="field" style="margin-top:13px"><label class="field-label">经历学期</label><input class="input" name="term" required placeholder="例如：2026春" value="${esc(edit?.term || "")}" ${edit?"readonly":""}></div><div class="field" style="margin-top:13px"><label class="field-label">${edit?"当前文本修订（至少8字）":"经验原文（至少8字）"}</label><textarea class="textarea" name="raw_text" required minlength="8" placeholder="写下你对课程难点、作业、考核与复习的实际体验。不要填写未经确认的具体考试安排。">${esc(edit?.raw_text || "")}</textarea><div class="field-hint">${edit?"修订后重新运行AI整理；首次提交快照单独保留，不会被覆盖。公开前会检查可能的邮箱和手机号。":"原文会先保存，再尝试AI抽取。如果模型不可用，原文仍会保留。请勿提交个人联系方式。"}</div></div>${!edit?`<div class="field" style="margin-top:13px"><label class="field-label">公开署名方式</label><select class="select" name="author_visibility"><option value="anonymous" selected>匿名展示（默认）</option><option value="display_name">显示账户昵称</option></select></div>`:""}<div class="form-footer"><button class="btn btn-primary" type="submit">${edit?"保存修订文本并重新整理":"保存原文并整理　→"}</button></div></form></div><div><div class="card card-pad"><div class="section-title-row"><h2>提交前须知</h2>${tag("P0", "blue")}</div><div class="status-list"><div class="status-row"><span class="status-dot"></span><div><strong>原文与AI字段分开保存</strong><p>模型整理的是草稿，不覆盖你的真实表达。</p></div></div><div class="status-row"><span class="status-dot"></span><div><strong>本人确认后才进入审核</strong><p>你可以修改抽取结果；未确认内容不会公开。</p></div></div><div class="status-row"><span class="status-dot"></span><div><strong>发布由审核员决定</strong><p>审核通过后才进入公开搜索与问答。</p></div></div></div></div><div class="notice warning" style="margin-top:14px"><span class="notice-icon">!</span><div>请勿提交私人群聊、未经授权的个人笔记、敏感个人信息或未经证实的指控。演示内容需明确标注。</div></div></div></div>${edit?experienceEditor(edit):`<div id="editor-mount"></div>`}`;
  const form = $("submit-form");
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    try {
      let response;
      if (state.draft) {
        response = await api(`/experiences/${state.draft.id}`, {method:"PATCH",body:{raw_text:data.raw_text,difficulty:state.draft.difficulty,assignments:state.draft.assignments,assessment:state.draft.assessment,advice:state.draft.advice}});
        toast("当前文本已保存并重新整理；首次提交快照仍保留。");
        state.draft = response.experience;
      } else {
        response = await api("/experiences", {method:"POST",body:{course_id:Number(data.course_id),term:data.term,raw_text:data.raw_text,author_visibility:data.author_visibility||"anonymous"}});
        state.draft = response.experience; state.editing = false;
        form.querySelector('button[type="submit"]').disabled = true;
        form.querySelector('button[type="submit"]').textContent = "原文已保存";
        toast("原文已保存，AI 整理草稿已生成。");
      }
      const mount = $("editor-mount"); if (mount) mount.innerHTML = experienceEditor(state.draft); else await renderSubmit($("page-content"));
      bindDraftEditor();
    } catch(err) { toast(err.message,true); }
  });
  if (edit) bindDraftEditor();
}
function bindDraftEditor() {
  const form = $("draft-edit-form"); if (!form || !state.draft) return;
  const readFields = () => ({difficulty:form.elements.difficulty.value, assignments:form.elements.assignments.value, assessment:form.elements.assessment.value, advice:form.elements.advice.value});
  $("save-draft").addEventListener("click", async ()=>{try{const data=await api(`/experiences/${state.draft.id}`,{method:"PATCH",body:readFields()});state.draft=data.experience;toast("字段已保存，原文保持不变。");await renderSubmit($("page-content"));}catch(e){toast(e.message,true);}});
  form.addEventListener("submit",async e=>{e.preventDefault();try{const data=await api(`/experiences/${state.draft.id}/confirm`,{method:"POST",body:{...readFields(),confirm:true}});state.draft=null;toast("已送审，未审核前不会公开。");await renderPage();}catch(err){toast(err.message,true);}});
}

async function renderMine(host) {
  if (!roleHas("contributor")) {host.innerHTML=pageHeading("MY RECORDS","我的记录",titles.mine[1])+`<div class="card card-pad">${emptyState("需要贡献者权限","登录贡献者账号后才能查看个人记录。","▤")}<div class="form-footer"><button class="btn btn-primary" id="mine-login">登录为贡献者</button></div></div>`;$("mine-login").addEventListener("click",()=>openLogin("contributor_demo"));return;}
  const data=await api("/experiences/mine");
  host.innerHTML=pageHeading("MY EXPERIENCE RECORDS","我的记录",titles.mine[1],`<button class="btn btn-primary" id="new-experience">＋ 新建经验</button>`)+`<div class="card"><div class="result-bar"><span>共 ${data.results.length} 条个人记录</span><span>原文与抽取字段分开保存</span></div>${data.results.length?`<div class="result-list">${data.results.map(exp=>`<article class="result-item"><div class="result-top"><div><h3 class="result-title">${esc(exp.course_name)} · ${esc(exp.term)}</h3><div class="result-meta"><span>#EXP-${exp.id}</span><span>更新于 ${prettyDate(exp.updated_at)}</span></div></div><div class="tag-line">${statusTag(exp.status)}${exp.demo_data?tag("演示记录","amber"):""}</div></div><p class="result-excerpt">${esc(exp.raw_text)}</p>${exp.review_reason?`<div class="notice warning" style="margin-top:10px">处理意见：${esc(exp.review_reason)}</div>`:""}<div class="result-actions">${["draft","returned"].includes(exp.status)?`<button class="btn btn-primary btn-inline" data-edit-exp="${exp.id}">继续编辑 / 重新送审</button>`:""}<button class="btn btn-ghost btn-inline" data-view-exp="${exp.id}">查看结构化字段</button></div><div id="exp-details-${exp.id}" class="hidden policy-callout" style="margin-top:12px">难点：${esc(exp.difficulty)}<br>作业：${esc(exp.assignments)}<br>考核：${esc(exp.assessment)}<br>建议：${esc(exp.advice)}</div></article>`).join("")}</div>`:emptyState("你还没有提交记录","从“提交经验”开始，先保存真实原文，再确认 AI 整理结果。","＋")}</div>`;
  $("new-experience").addEventListener("click",()=>{state.draft=null;navigate("submit")});
  host.querySelectorAll("[data-view-exp]").forEach(b=>b.addEventListener("click",()=>{$(`exp-details-${b.dataset.viewExp}`).classList.toggle("hidden")}));
  host.querySelectorAll("[data-edit-exp]").forEach(b=>b.addEventListener("click",async()=>{try{state.draft=await api(`/experiences/${b.dataset.editExp}`);navigate("submit");}catch(e){toast(e.message,true);}}));
}

async function renderReview(host) {
  if (!roleHas("reviewer","admin")) {host.innerHTML=pageHeading("REVIEW WORKBENCH","审核工作台",titles.review[1])+`<div class="card card-pad">${emptyState("审核权限受限","请登录审核员或管理员账号。后端会再次检查权限，前端隐藏按钮不作为安全控制。","✓")}<div class="form-footer"><button class="btn btn-primary" id="review-login">登录审核员</button></div></div>`;$("review-login").addEventListener("click",()=>openLogin("reviewer_demo"));return;}
  const data=await api("/review/queue");
  host.innerHTML=pageHeading("REVIEW WORKBENCH","审核工作台",titles.review[1],tag(`${data.results.length} 条待审核`,data.results.length?"amber":"green"))+`<div class="notice" style="margin-bottom:16px"><span class="notice-icon">i</span><div>审核通过时需要填写具体“主张/主题组”，用于区分哪些资料可以互相佐证。转载不增加独立来源数；审核员不能审核本人提交的内容。</div></div><div class="grid">${data.results.length?data.results.map(exp=>`<div class="card card-pad review-card" data-review-id="${exp.id}"><div class="section-title-row"><div><h2 style="margin:0;font-size:15px">${esc(exp.course_name)} · ${esc(exp.term)}</h2><p>#EXP-${exp.id} · 提交者 ${esc(exp.submitter_name)} · ${prettyDate(exp.created_at)}</p></div>${statusTag(exp.status)}</div><div class="subsection-title">当前文本 / 原始提交快照已保留</div><div class="policy-callout" style="white-space:pre-wrap">${esc(exp.raw_text)}</div>${exp.privacy_warnings?.length?`<div class="notice warning" style="margin-top:10px"><span class="notice-icon">!</span><div>隐私检查提示：${esc(exp.privacy_warnings.join("、"))}。请先要求贡献者修订，系统会阻止直接发布。</div></div>`:""}<div class="subsection-title">AI整理字段（贡献者已确认）</div><div class="grid grid-2"><div class="policy-callout">难点：${esc(exp.difficulty)}</div><div class="policy-callout">作业：${esc(exp.assignments)}</div><div class="policy-callout">考核：${esc(exp.assessment)}</div><div class="policy-callout">建议：${esc(exp.advice)}</div></div><div class="form-grid" style="margin-top:14px"><div class="field"><label class="field-label">主张 / 主题组（通过时必填）</label><input class="input review-claim" placeholder="例如：线性代数-期末复习方法"></div><div class="field"><label class="field-label">处理理由（退回/拒绝必填）</label><input class="input review-reason" placeholder="说明审核结论与依据"></div></div><div class="grid grid-2" style="margin-top:11px"><label class="checkline"><input type="checkbox" class="review-conflict">该主张存在尚未解决的实质性冲突（会降低一致性分并禁止“最可信参考”标签）</label><label class="checkline"><input type="checkbox" class="review-major-change">已知重大课程变化（时效分T=30，并限制适用范围）</label></div><div class="form-footer"><button class="btn btn-success btn-inline" data-review-action="approve">通过并发布</button><button class="btn btn-ghost btn-inline" data-review-action="return">退回修改</button><button class="btn btn-danger btn-inline" data-review-action="reject">拒绝</button></div></div>`).join(""):emptyState("审核队列为空","新的提交只有在贡献者确认后才会进入这里。","✓")}</div>`;
  host.querySelectorAll("[data-review-action]").forEach(btn=>btn.addEventListener("click",async()=>{
    const card=btn.closest(".review-card"), id=card.dataset.reviewId, action=btn.dataset.reviewAction;
    const reason=card.querySelector(".review-reason").value.trim(), claim_group=card.querySelector(".review-claim").value.trim(), unresolved_conflict=card.querySelector(".review-conflict").checked, major_course_change=card.querySelector(".review-major-change").checked;
    if(action!=="approve"&&!reason){toast("退回或拒绝必须填写理由。",true);return;}
    if(action==="approve"&&claim_group.length<2){toast("请填写该记录支持的具体主张/主题组。",true);return;}
    if(!confirm(({approve:"确定审核通过并公开该经验？",return:"确定退回该经验？",reject:"确定拒绝该经验？"})[action]))return;
    try{await api(`/experiences/${id}/review`,{method:"POST",body:{action,reason,claim_group,unresolved_conflict,major_course_change}});toast("审核结果已记录。");await renderReview(host);await refreshShared();}catch(e){toast(e.message,true);}
  }));
}

async function renderSources(host) {
  if (!roleHas("admin","reviewer")) {host.innerHTML=pageHeading("SOURCE REGISTRY","来源管理",titles.sources[1])+`<div class="card card-pad">${emptyState("来源管理需要授权角色","查询者不能登记或修改来源许可。","↗")}<div class="form-footer"><button class="btn btn-primary" id="source-login">登录管理员</button></div></div>`;$("source-login").addEventListener("click",()=>openLogin("admin_demo"));return;}
  const data=await api("/sources");
  state.sourceData = data.results;
  const formHTML=roleHas("admin")?`<div class="card card-pad" style="margin-bottom:16px"><div class="section-title-row"><div><h2>登记已有回答 / 公开资料</h2><p>先登记真实出处与适用范围，再核查内容许可；不得把“可访问链接”当作“获准处理正文”。</p></div>${tag("FR-07 · P0","blue")}</div><form id="source-create-form"><div class="form-grid"><div class="field span-2"><label class="field-label">标题</label><input class="input" name="title" required minlength="2"></div><div class="field"><label class="field-label">来源类型</label><select class="select" name="source_type"><option value="external_answer">外部公开回答</option><option value="official_document">官方资料</option><option value="student_experience">学生经验</option><option value="other">其他</option></select></div><div class="field"><label class="field-label">课程（可选）</label><select class="select" name="course_id">${courseOptions()}</select></div><div class="field"><label class="field-label">作者 / 发布机构</label><input class="input" name="author" placeholder="若未知请如实留空"></div><div class="field"><label class="field-label">机构（补充）</label><input class="input" name="organization"></div><div class="field span-2"><label class="field-label">原始 URL / 记录定位</label><input class="input" name="url" type="url" placeholder="https://…"></div><div class="field"><label class="field-label">适用学期</label><input class="input" name="term" placeholder="未知就留空"></div><div class="field"><label class="field-label">主张 / 主题组</label><input class="input" name="claim_group" required placeholder="例如：线性代数-期末复习方法"></div><div class="field"><label class="field-label">发布时间（可选）</label><input class="input" name="published_at" type="date"></div><div class="field"><label class="field-label">经历时间（优先用于时效评分）</label><input class="input" name="experience_date" type="date"></div><div class="field span-2"><label class="field-label">允许使用的正文 / 摘要</label><textarea class="textarea" name="content_excerpt" placeholder="只有获准使用的内容才能填写进可检索正文；仅可展示链接的资料不要复制其正文。"></textarea></div><div class="field"><label class="field-label">内容使用权限</label><select class="select" name="permission"><option value="pending">待确认（默认安全）</option><option value="link_only">仅可展示链接</option><option value="abstract_allowed">允许摘要用于检索生成</option><option value="full_text_allowed">允许全文用于检索生成</option><option value="prohibited">禁止使用</option></select></div><div class="field"><label class="field-label">转载归并到来源 ID（可选）</label><input class="input" name="duplicate_of_id" type="number" min="1" placeholder="例如：对应原始来源ID"></div></div><div class="grid grid-2" style="margin-top:12px"><label class="checkline"><input type="checkbox" name="author_verified">作者 / 机构身份可核验</label><label class="checkline"><input type="checkbox" name="official">来源为官方资料</label><label class="checkline"><input type="checkbox" name="current_official_fact">当前有效官方资料直接支持正式事实</label><label class="checkline"><input type="checkbox" name="major_course_change">已知重大课程变化（T=30并限制适用范围）</label><label class="checkline"><input type="checkbox" name="unresolved_conflict">存在未解决的实质性冲突</label><label class="checkline"><input type="checkbox" name="has_concrete_scenario">正文包含具体场景</label><label class="checkline"><input type="checkbox" name="has_actionable_detail">正文包含可执行步骤或细节</label><label class="checkline span-2"><input type="checkbox" name="confirm_reviewed">我已核查作者、出处、适用范围和内容使用许可（摘要/全文权限必选）</label></div><div class="form-footer"><button class="btn btn-primary" type="submit">登记来源</button></div></form></div>`:"";
  host.innerHTML=pageHeading("SOURCE REGISTRY","来源管理",titles.sources[1])+formHTML+`<div class="card"><div class="card-header"><div><h2 class="card-title">来源目录</h2><div class="card-subtitle">包括已获准来源、仅链接、转载归并及管理员待处理项。</div></div>${tag(`${data.results.length} 条`,"gray")}</div><div class="result-list">${data.results.length?data.results.map(s=>`<article class="result-item"><div class="result-top"><div><h3 class="result-title">${esc(s.title)}</h3><div class="result-meta"><span class="mono">${esc(s.source_code)}</span><span>${esc(sourceTypeLabel(s.source_type))}</span><span>${esc(s.course_name||"未指定课程")}</span></div></div><div class="tag-line">${statusTag(s.status)}${tag(permissionLabels[s.permission]||s.permission,s.permission==="prohibited"?"red":s.permission==="pending"?"amber":"blue")}${s.url?tag(linkStatusLabels[s.link_status]||"链接状态未知",s.link_status==="invalid"?"red":s.link_status==="verified"?"green":"amber"):""}${s.demo_data?tag("演示", "amber"):""}</div></div><p class="result-excerpt">${esc((s.content_excerpt||"未登记正文").slice(0,300))}</p><div class="result-actions"><button class="btn btn-ghost btn-inline" data-source-details="${s.id}">详情 / 评分</button>${s.duplicate_of_code?tag("转载 → "+s.duplicate_of_code,"purple"):""}${roleHas("admin")?`<select class="select permission-select" data-permission-id="${s.id}" style="max-width:200px;padding:6px;font-size:10px"><option value="link_only" ${s.permission==="link_only"?"selected":""}>仅链接</option><option value="abstract_allowed" ${s.permission==="abstract_allowed"?"selected":""}>允许摘要</option><option value="full_text_allowed" ${s.permission==="full_text_allowed"?"selected":""}>允许全文</option><option value="pending" ${s.permission==="pending"?"selected":""}>待确认</option><option value="prohibited" ${s.permission==="prohibited"?"selected":""}>禁止</option></select><button class="btn btn-ghost btn-inline" data-save-permission="${s.id}">更新许可</button>${s.url?`<select class="select link-status-select" data-link-status-id="${s.id}" style="max-width:170px;padding:6px;font-size:10px"><option value="unchecked" ${s.link_status==="unchecked"?"selected":""}>待核验</option><option value="verified" ${s.link_status==="verified"?"selected":""}>链接有效</option><option value="invalid" ${s.link_status==="invalid"?"selected":""}>链接失效</option></select><button class="btn btn-ghost btn-inline" data-save-link-status="${s.id}">更新链接状态</button>`:""}`:""}</div></article>`).join(""):emptyState("还没有来源","管理员可以登记已获准的外部回答、官方资料或来源链接。","↗")}</div><div class="table-foot">来源用途规则：待确认或禁止来源不会进入问答；仅链接资料只用于导航，不参与内容评分；转载应指向原始来源，不重复计分。</div></div>`;
  if(roleHas("admin")) $("source-create-form").addEventListener("submit",async e=>{e.preventDefault();const f=e.currentTarget;const fd=new FormData(f);const body={};for(const [k,v] of fd.entries())body[k]=v;body.course_id=body.course_id?Number(body.course_id):null;body.duplicate_of_id=body.duplicate_of_id?Number(body.duplicate_of_id):null;for(const k of ["author_verified","official","current_official_fact","major_course_change","unresolved_conflict","has_concrete_scenario","has_actionable_detail","confirm_reviewed"])body[k]=f.elements[k].checked;body.experience_date=body.experience_date||null;body.published_at=body.published_at||null;try{await api("/sources",{method:"POST",body});toast("来源已登记。");await renderSources(host);}catch(err){toast(err.message,true);}});
  bindSourceDetails(host);
  host.querySelectorAll("[data-save-permission]").forEach(b=>b.addEventListener("click",async()=>{const id=b.dataset.savePermission,sel=host.querySelector(`[data-permission-id="${id}"]`);const reason=prompt("请说明许可变更依据（必填）", "已核查来源权限状态");if(!reason)return;const body={permission:sel.value,reason};if(["abstract_allowed","full_text_allowed"].includes(sel.value)){const record=(state.sourceData||[]).find(x=>String(x.id)===String(id));const excerpt=prompt("请确认已获准用于检索生成的正文/摘要（不是仅可访问的网页全文）。若没有获准内容，请取消。",record?.content_excerpt||"");if(!excerpt)return;body.content_excerpt=excerpt;body.confirm_reviewed=true;}try{await api(`/sources/${id}/permission`,{method:"PUT",body});toast("来源许可已更新，检索会应用新状态。");await renderSources(host);}catch(err){toast(err.message,true);}}));
  host.querySelectorAll("[data-save-link-status]").forEach(b=>b.addEventListener("click",async()=>{const id=b.dataset.saveLinkStatus,sel=host.querySelector(`[data-link-status-id="${id}"]`);const reason=prompt("请记录人工核验依据（必填；标记无效后该来源会退出公开搜索与AI问答）",sel.value==="verified"?"管理员已打开并核验原始链接":sel.value==="invalid"?"管理员核查发现链接失效":"重新核验链接状态");if(!reason)return;try{await api(`/sources/${id}/link-status`,{method:"PUT",body:{link_status:sel.value,reason}});toast("链接状态已更新。公开检索会应用新状态。");await renderSources(host);}catch(err){toast(err.message,true);}}));
}

async function renderScoring(host) {
  const data=await api("/credibility");
  const rows=data.results;
  host.innerHTML=pageHeading("EVIDENCE QUALITY", "可信度评分表", titles.scoring[1], `<button class="btn btn-ghost" id="score-refresh">重新计算</button>`)+`<div class="notice" style="margin-bottom:16px"><span class="notice-icon">◎</span><div><strong>${esc(data.formula)}</strong><br>${esc(data.note)} 当前规则版本：${esc(data.rule_version)}。</div></div><div class="card"><div class="card-header"><div><h2 class="card-title">同类资料排序</h2><div class="card-subtitle">转载不算独立来源；主张范围不同的资料不会互相增加 A 维度分。</div></div>${tag("A/S/T/D", "blue")}</div><div class="table-wrap"><table class="data-table"><thead><tr><th>来源</th><th>A 一致性</th><th>S 可追溯</th><th>T 时效</th><th>D 完整</th><th>总分 C</th><th>结论</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.source_code||r.id)} · ${esc(r.title)}</strong><div class="small muted" style="margin-top:5px">${esc(r.course_name||"")} ${esc(r.term||"")}</div>${r.duplicate_of_id?`<div style="margin-top:5px">${tag("转载已归并","purple")}</div>`:""}</td><td>${r.score_a==null?"—":r.score_a}</td><td>${r.score_s==null?"—":r.score_s}</td><td>${r.score_t==null?"—":r.score_t}</td><td>${r.score_d==null?"—":r.score_d}</td><td>${r.score==null?"—":`<strong>${Number(r.score).toFixed(1)}</strong><div class="score-bar"><span style="width:${Math.max(0,Math.min(100,r.score))}%"></span></div>`}</td><td>${scorePill(r.score,r.grade)}${r.most_credible?`<div style="margin-top:6px">${tag("最可信参考","green")}</div>`:""}<div class="small muted" style="margin-top:5px;max-width:230px">${esc((r.limitations||[]).join("；"))}</div></td></tr>`).join("")}</tbody></table></div><div class="table-foot">M1–M4 是需求文档中的合成演示例子。M1=87.5、M2=81.0、M4=57.0；M3 是 M2 的转载，不额外计分。评分日固定为 2026-10-14 的示例结果；新来源采用实际评分日。</div></div><div class="spacer-20"></div><div class="grid grid-2"><div class="card card-pad"><h2 class="card-title">四个评分维度</h2><div class="status-list" style="margin-top:13px"><div class="status-row"><span class="status-dot"></span><div><strong>A · 多来源一致性（40%）</strong><p>独立来源数量与冲突状态；复制转载不增加佐证数量。</p></div></div><div class="status-row"><span class="status-dot"></span><div><strong>S · 来源可追溯性（25%）</strong><p>可定位出处、作者/机构标识、来源类型与许可状态。</p></div></div><div class="status-row"><span class="status-dot"></span><div><strong>T · 时效性（20%）</strong><p>优先使用经历时间，其次发布时间；未知日期按30分处理。</p></div></div><div class="status-row"><span class="status-dot"></span><div><strong>D · 内容完整性（15%）</strong><p>课程、经历学期、具体场景和可执行细节。</p></div></div></div></div><div class="card card-pad"><h2 class="card-title">标签限制</h2><div class="status-list" style="margin-top:13px"><div class="status-row"><span class="status-dot"></span><div><strong>较高：80–100</strong><p>至少两份独立来源相互支持，或当前有效官方资料直接支持正式事实，且无重大冲突。单条主观经验最多为中等。</p></div></div><div class="status-row"><span class="status-dot"></span><div><strong>最可信参考</strong><p>至少两个独立候选、最高分≥60、无重大冲突且关键依据齐全。只表示当前候选的相对排序。</p></div></div><div class="status-row"><span class="status-dot"></span><div><strong>暂不评分</strong><p>来源缺失、权限不足或适用范围不清时，不强行生成数字评分。</p></div></div></div></div></div>`;
  $("score-refresh").addEventListener("click",()=>renderScoring(host));
}

async function renderFeedback(host) {
  if (!state.user) {host.innerHTML=pageHeading("FEEDBACK LOOP","反馈与纠错",titles.feedback[1])+`<div class="card card-pad">${emptyState("请登录后提交反馈","P1反馈功能需要可识别账号；反馈经审核后才可处理知识库。","◇")}<div class="form-footer"><button class="btn btn-primary" id="feedback-login">登录</button></div></div>`;$("feedback-login").addEventListener("click",()=>openLogin("reader_demo"));return;}
  const data=await api("/feedback");
  host.innerHTML=pageHeading("FEEDBACK LOOP","反馈与纠错",titles.feedback[1])+`<div class="grid grid-2"><div class="card card-pad"><div class="section-title-row"><h2>提交纠错反馈</h2>${tag("P1", "amber")}</div><form id="feedback-form"><div class="form-grid"><div class="field"><label class="field-label">目标类型</label><select class="select" name="target_type"><option value="experience">课程经验</option><option value="answer">AI回答</option><option value="source">外部来源</option></select></div><div class="field"><label class="field-label">目标 ID</label><input class="input" name="target_id" type="number" min="1" required></div><div class="field span-2"><label class="field-label">问题类型</label><select class="select" name="category"><option value="outdated">资料过时</option><option value="incorrect">内容错误</option><option value="irrelevant_citation">引用不相关</option><option value="privacy">隐私问题</option><option value="other">其他</option></select></div><div class="field span-2"><label class="field-label">描述</label><textarea class="textarea" name="description" required minlength="5" placeholder="说明哪里过时/错误、适用范围，以及可供审核的理由或出处。"></textarea></div></div><div class="form-footer"><button class="btn btn-primary" type="submit">提交反馈</button></div></form><div class="policy-callout" style="margin-top:13px">反馈会生成 ID 与状态。未经审核的反馈不会直接修改内容；处理结果将留痕。</div></div><div class="card"><div class="card-header"><div><h2 class="card-title">${roleHas("reviewer","admin")?"待处理反馈":"我的反馈"}</h2><div class="card-subtitle">${data.results.length} 条记录</div></div></div><div class="result-list">${data.results.length?data.results.map(f=>`<article class="result-item"><div class="result-top"><div><h3 class="result-title">${esc(f.feedback_code)} · ${esc(f.category)}</h3><div class="result-meta">${esc(f.target_type)} #${f.target_id} · ${prettyDate(f.created_at)}</div></div>${statusTag(f.status)}</div><p class="result-excerpt">${esc(f.description)}</p>${f.handling_note?`<div class="policy-callout" style="margin-top:8px">处理意见：${esc(f.handling_note)}</div>`:""}${roleHas("reviewer","admin")&&f.status==="pending"?`<div class="result-actions"><select class="select" data-feedback-state="${f.id}" style="max-width:180px"><option value="maintained">维持原样</option><option value="updated">已更新</option><option value="disputed">标记争议</option><option value="withdrawn">下架</option><option value="needs_more_evidence">待补证</option></select><input class="input" data-feedback-note="${f.id}" placeholder="处理理由（必填）" style="max-width:240px"><button class="btn btn-primary btn-inline" data-handle-feedback="${f.id}">处理</button></div>`:""}</article>`).join(""):emptyState("暂无反馈记录","有过时或引用不匹配的资料时，可在此提交给审核人员。","◇")}</div></div></div>`;
  $("feedback-form").addEventListener("submit",async e=>{e.preventDefault();const form=e.currentTarget;const fd=new FormData(form);const body=Object.fromEntries(fd.entries());body.target_id=Number(body.target_id);try{const result=await api("/feedback",{method:"POST",body});toast(`反馈已记录：${result.feedback_code}`);await renderFeedback(host);}catch(err){toast(err.message,true);}});
  host.querySelectorAll("[data-handle-feedback]").forEach(b=>b.addEventListener("click",async()=>{const id=b.dataset.handleFeedback,st=host.querySelector(`[data-feedback-state="${id}"]`).value,note=host.querySelector(`[data-feedback-note="${id}"]`).value.trim();if(!note){toast("请填写处理理由。",true);return;}try{await api(`/feedback/${id}`,{method:"PATCH",body:{status:st,handling_note:note}});toast("反馈处理已记录。");await renderFeedback(host);}catch(e){toast(e.message,true);}}));
}

async function renderAdmin(host) {
  if (!roleHas("admin")) {host.innerHTML=pageHeading("ADMIN & DELIVERY","管理与交付",titles.admin[1])+`<div class="card card-pad">${emptyState("管理员权限受限","角色维护、规则变更和完整操作日志仅管理员可访问。","⚙")}<div class="form-footer"><button class="btn btn-primary" id="admin-login">登录管理员</button></div></div>`;$("admin-login").addEventListener("click",()=>openLogin("admin_demo"));return;}
  const [users, config, metrics] = await Promise.all([api("/admin/users"),api("/admin/scoring-config"),api("/admin/metrics")]);
  host.innerHTML=pageHeading("ADMIN & DELIVERY","管理与交付",titles.admin[1])+`<div class="grid grid-3"><div class="card metric-card"><div class="metric-top">已发布经验</div><div class="metric-value">${metrics.published_experiences}</div><div class="metric-foot">聚合统计 · 不含个人排名</div></div><div class="card metric-card"><div class="metric-top">待审核经验</div><div class="metric-value">${metrics.pending_review}</div><div class="metric-foot">正式验收前需完成P0核心队列。</div></div><div class="card metric-card"><div class="metric-top">待处理反馈 <span class="tag amber">P1</span></div><div class="metric-value">${metrics.feedback_pending}</div><div class="metric-foot">反馈统计和知识缺口分析属于后续扩展。</div></div></div><div class="spacer-20"></div><div class="grid grid-2"><div class="card card-pad"><div class="section-title-row"><h2>用户角色</h2>${tag("FR-10", "blue")}</div><p class="card-subtitle" style="margin:0 0 12px">权限在后端校验。同一账号可有多个角色；不能审核自己提交的记录。</p><div class="result-list">${users.results.map(u=>`<div class="permission-row"><div><strong>${esc(u.display_name)}</strong><div class="small muted mono">${esc(u.username)}</div></div><div class="pill-list">${u.roles.map(r=>tag(roleLabels[r]||r,"gray")).join("")}</div><button class="btn btn-ghost btn-inline" data-edit-roles="${u.id}">修改角色</button></div>`).join("")}</div></div><div class="card card-pad"><div class="section-title-row"><h2>可信度评分权重</h2>${tag(config.version,"blue")}</div><p class="card-subtitle" style="margin:0 0 14px">默认须与需求文档一致。变更会记录规则版本，旧结果需按原规则版本复算。</p><form id="score-config-form"><div class="form-grid">${["A","S","T","D"].map(k=>`<div class="field"><label class="field-label">${k} 权重</label><input class="input" type="number" min="0" max="1" step="0.01" name="${k}" value="${config.weights[k]}" required></div>`).join("")}</div><div class="policy-callout" style="margin-top:12px">公式：C = A×wA + S×wS + T×wT + D×wD。默认权重 0.40 / 0.25 / 0.20 / 0.15。</div><div class="form-footer"><button class="btn btn-primary" type="submit">保存新规则版本</button></div></form></div></div><div class="spacer-20"></div><div class="card card-pad"><div class="section-title-row"><div><h2>维护检查与日志</h2><p>近似重复及过期复核只给出候选，不自动合并或删除原文。</p></div><div class="heading-actions"><button id="maintenance-run" class="btn btn-ghost">生成维护候选（P1）</button><button id="logs-load" class="btn btn-ghost">查看操作日志</button></div></div><div id="maintenance-output" class="small muted">等待执行。</div><div class="divider"></div><div class="section-title-row"><h2>交付检查清单</h2>${tag("NFR-10 / AT-15", "amber")}</div><div class="status-list"><div class="status-row"><span class="status-dot"></span><div><strong>本地运行</strong><p>FastAPI + SQLite + 浏览器原生前端；生产/云端使用环境变量连接服务和数据库。</p></div>${tag("可本地验证","green")}</div><div class="status-row"><span class="status-dot"></span><div><strong>AI服务配置</strong><p>未配置AI_BASE_URL / AI_API_KEY / AI_MODEL时会降级到规则抽取与证据模板，不会假称调用大模型。</p></div>${tag("按环境","gray")}</div><div class="status-row"><span class="status-dot"></span><div><strong>云端 Demo、CodeArts、许可证与开源说明</strong><p>仍需按赛事账号与正式要求实施，并保存真实部署地址、构建记录和测试结果。</p></div>${tag("部署阶段","amber")}</div></div><div id="logs-output"></div></div>`;
  host.querySelectorAll("[data-edit-roles]").forEach(b=>b.addEventListener("click",async()=>{const u=users.results.find(x=>String(x.id)===b.dataset.editRoles);const raw=prompt(`为 ${u.display_name} 输入角色（逗号分隔：reader,contributor,reviewer,admin）`,u.roles.join(","));if(raw===null)return;const roles=raw.split(",").map(x=>x.trim()).filter(Boolean);try{await api(`/admin/users/${u.id}/roles`,{method:"PATCH",body:{roles}});toast("角色已更新并记录日志。");await renderAdmin(host);}catch(e){toast(e.message,true);}}));
  $("score-config-form").addEventListener("submit",async e=>{e.preventDefault();const fd=new FormData(e.currentTarget);const body=Object.fromEntries([...fd.entries()].map(([k,v])=>[k,Number(v)]));try{const result=await api("/admin/scoring-config",{method:"PUT",body});toast(`评分规则已更新：${result.version}`);await renderAdmin(host);}catch(err){toast(err.message,true);}});
  $("maintenance-run").addEventListener("click",async()=>{try{const d=await api("/admin/maintenance/candidates");$("maintenance-output").innerHTML=d.results.length?`<div class="table-wrap" style="margin-top:12px"><table class="data-table"><thead><tr><th>类型</th><th>来源</th><th>候选说明</th></tr></thead><tbody>${d.results.map(r=>`<tr><td>${esc(r.type)}</td><td>${esc(r.source_code)}${r.other_source_code?" / "+esc(r.other_source_code):""}</td><td>${esc(r.reason)}${r.similarity?" 相似度："+r.similarity:""}</td></tr>`).join("")}</tbody></table></div>`:emptyState("未发现候选","当前规则没有发现相似或过期资料。","✓");}catch(e){toast(e.message,true);}});
  $("logs-load").addEventListener("click",async()=>{try{const d=await api("/admin/logs");$("logs-output").innerHTML=`<div class="subsection-title">操作日志（${d.operation_logs.length}）</div><div class="table-wrap"><table class="data-table"><thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>目标</th><th>细节</th></tr></thead><tbody>${d.operation_logs.map(l=>`<tr><td>${prettyDate(l.created_at)}</td><td>${l.actor_id||"系统"}</td><td>${esc(l.action)}</td><td>${esc(l.target_type)} #${esc(l.target_id)}</td><td>${esc(JSON.stringify(l.details))}</td></tr>`).join("")}</tbody></table></div><div class="subsection-title">审核记录（${d.review_logs.length}）</div><div class="table-wrap"><table class="data-table"><thead><tr><th>时间</th><th>审核员</th><th>经验ID</th><th>动作</th><th>理由</th></tr></thead><tbody>${d.review_logs.map(l=>`<tr><td>${prettyDate(l.created_at)}</td><td>${l.reviewer_id}</td><td>${l.experience_id}</td><td>${esc(l.action)}</td><td>${esc(l.reason)}</td></tr>`).join("")}</tbody></table></div>`;}catch(e){toast(e.message,true);}});
}

function openLogin(username) {
  if (username) $("login-username").value = username;
  $("login-error").textContent = "";
  $("login-dialog").showModal();
}
async function tryRestoreUser() {
  if (!state.token) return;
  try { const user = await api("/auth/me"); setUser(user, state.token); } catch (_) { setUser(null, ""); }
}

// Global event wiring
$("main-nav").addEventListener("click", e => { const btn = e.target.closest("[data-view]"); if (btn) navigate(btn.dataset.view); });
$("login-open").addEventListener("click",()=>openLogin());
$("logout-button").addEventListener("click",()=>{setUser(null,"");state.draft=null;toast("已退出登录。");renderPage();});
$("login-close").addEventListener("click",()=>$("login-dialog").close());
document.querySelectorAll("[data-user]").forEach(btn=>btn.addEventListener("click",()=>{$("login-username").value=btn.dataset.user;$("login-password").value="demo123!";}));
$("login-form").addEventListener("submit",async e=>{e.preventDefault();try{const result=await api("/auth/login",{method:"POST",body:{username:$("login-username").value.trim(),password:$("login-password").value}});setUser(result.user,result.access_token);$("login-dialog").close();toast(`欢迎，${result.user.display_name}。`);await renderPage();}catch(err){$("login-error").textContent=err.message;}});
$("dismiss-banner").addEventListener("click",()=>$("demo-banner").classList.add("hidden"));
window.addEventListener("keydown",e=>{if(e.key==="Escape"&&$("detail-dialog").open)$("detail-dialog").close();});

(async function init(){
  try { await api("/health"); } catch (_) { $("page-content").innerHTML = `<div class="card card-pad"><h1>本地服务未启动</h1><p>请根据项目 README 在 backend 目录运行服务，然后刷新此页面。</p></div>`; return; }
  await tryRestoreUser(); renderHeader(); await renderPage();
})();
