/* Campus Memory motion system — subtle, state-aware, accessibility-first. */
(() => {
  "use strict";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  let observer;
  let requestCount = 0;
  let showTimer = 0;
  let progressNode;
  let progressLabel;

  function ensureProgress() {
    if (progressNode) return;
    const main = $(".main-area");
    const topbar = $(".topbar");
    if (!main) return;
    progressNode = document.createElement("div");
    progressNode.className = "motion-request-progress";
    progressNode.setAttribute("role", "status");
    progressNode.setAttribute("aria-live", "polite");
    progressNode.innerHTML = '<span class="motion-request-bar" aria-hidden="true"></span><span class="motion-request-label">正在处理请求…</span>';
    progressLabel = $(".motion-request-label", progressNode);
    if (topbar && topbar.parentNode === main) topbar.insertAdjacentElement("afterend", progressNode);
    else main.prepend(progressNode);
  }

  function requestMessage(path, method) {
    if (path.includes("/qa")) return "正在检索证据并整理回答…";
    if (path.includes("/search")) return "正在检索已审核且许可有效的资料…";
    if (path.includes("/confirm")) return "正在保存确认结果并提交审核…";
    if (path.includes("/review/") || path.includes("/unpublish")) return "正在更新审核状态…";
    if (path.includes("/experiences") && method !== "GET") return "正在保存原文并整理经验字段…";
    if (path.includes("/sources") && method !== "GET") return "正在保存来源与使用权限…";
    return method !== "GET" ? "正在安全保存更改…" : "正在读取资料…";
  }

  function installRequestFeedback() {
    document.addEventListener("campus:api-request", event => {
      const detail = event.detail || {};
      if (detail.phase === "start") {
        ensureProgress();
        requestCount += 1;
        if (progressLabel) progressLabel.textContent = requestMessage(detail.path || "", detail.method || "GET");
        if (requestCount === 1) {
          window.clearTimeout(showTimer);
          showTimer = window.setTimeout(() => {
            if (requestCount > 0 && progressNode) progressNode.classList.add("is-active");
          }, 170);
        }
        return;
      }
      if (detail.phase === "end") {
        requestCount = Math.max(0, requestCount - 1);
        if (requestCount === 0) {
          window.clearTimeout(showTimer);
          if (progressNode) progressNode.classList.remove("is-active");
        }
      }
    });
  }

  function reveal(el, index = 0) {
    if (!(el instanceof HTMLElement) || el.dataset.motionEnhanced === "true") return;
    el.dataset.motionEnhanced = "true";
    el.classList.add("motion-reveal");
    el.style.setProperty("--motion-delay", `${Math.min(index * 45, 180)}ms`);
    if (reduceMotion.matches || !("IntersectionObserver" in window)) {
      el.classList.add("is-visible");
      return;
    }
    el.dataset.motionRepeat = "true";
    if (!observer) {
      observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) entry.target.classList.add("is-visible");
          else if (entry.target.dataset.motionRepeat === "true") entry.target.classList.remove("is-visible");
        });
      }, { threshold: 0.12, rootMargin: "0px 0px -28px 0px" });
    }
    observer.observe(el);
  }

  function animateMetric(el) {
    if (!(el instanceof HTMLElement) || el.dataset.motionCounted === "true") return;
    const raw = el.textContent.trim();
    if (!/^\d+(?:\.\d+)?$/.test(raw)) return;
    el.dataset.motionCounted = "true";
    const target = Number(raw);
    if (reduceMotion.matches || target <= 0) return;
    const started = performance.now();
    const duration = 560;
    function frame(now) {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Number.isInteger(target) ? String(Math.round(target * eased)) : (target * eased).toFixed(1);
      if (progress < 1) requestAnimationFrame(frame);
      else el.textContent = raw;
    }
    requestAnimationFrame(frame);
  }

  function enhance(root = document) {
    const host = $("#page-content", root) || (root.id === "page-content" ? root : null);
    if (host) {
      const topLevel = $$(":scope > .page-heading, :scope > section, :scope > .grid, :scope > .qa-layout, :scope > .card, :scope > .notice", host);
      topLevel.forEach((el, i) => reveal(el, i));
      $$(".step-item, .principle-row", host).forEach((el, i) => reveal(el, i));
      $$(".result-item, .citation-item, .status-row, .detail-score, .data-table tbody > tr", host).forEach((el, i) => reveal(el, Math.min(i, 4)));
      $$(".metric-value", host).forEach(animateMetric);
    }
    const detail = $("#detail-content", root);
    if (detail) $$(".detail-score, .policy-callout, .subsection-title", detail).forEach((el, i) => reveal(el, i));
  }


  function installSidebarToggle() {
    const shell = $(".app-shell");
    const toggle = $("#sidebar-toggle");
    const backdrop = $("#sidebar-backdrop");
    const sidebar = $("#app-sidebar");
    if (!shell || !toggle || !sidebar) return;
    const mobileQuery = window.matchMedia("(max-width: 850px)");
    const STORAGE_KEY = "campus_sidebar_collapsed";

    function setButtonState() {
      const mobile = mobileQuery.matches;
      const open = mobile ? shell.classList.contains("mobile-nav-open") : !shell.classList.contains("sidebar-collapsed");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", mobile ? (open ? "关闭导航栏" : "打开导航栏") : (open ? "收起导航栏" : "展开导航栏"));
      toggle.title = mobile ? (open ? "关闭导航栏" : "打开导航栏") : (open ? "收起导航栏" : "展开导航栏");
      if (backdrop) backdrop.tabIndex = mobile && open ? 0 : -1;
      if (mobile && !open) {
        sidebar.setAttribute("aria-hidden", "true");
        sidebar.setAttribute("inert", "");
      } else {
        sidebar.removeAttribute("aria-hidden");
        sidebar.removeAttribute("inert");
      }
    }
    function closeMobileNav() {
      shell.classList.remove("mobile-nav-open");
      document.body.classList.remove("campus-nav-open");
      setButtonState();
    }
    function onModeChange() {
      if (mobileQuery.matches) {
        shell.classList.remove("sidebar-collapsed");
        closeMobileNav();
      } else {
        closeMobileNav();
        shell.classList.toggle("sidebar-collapsed", localStorage.getItem(STORAGE_KEY) === "true");
        setButtonState();
      }
    }
    toggle.addEventListener("click", () => {
      if (mobileQuery.matches) {
        const willOpen = !shell.classList.contains("mobile-nav-open");
        shell.classList.toggle("mobile-nav-open", willOpen);
        document.body.classList.toggle("campus-nav-open", willOpen);
        setButtonState();
        if (willOpen) {
          const firstNav = $("#main-nav .nav-item");
          if (firstNav) window.setTimeout(() => firstNav.focus({ preventScroll: true }), 40);
        }
      } else {
        const willCollapse = !shell.classList.contains("sidebar-collapsed");
        shell.classList.toggle("sidebar-collapsed", willCollapse);
        localStorage.setItem(STORAGE_KEY, String(willCollapse));
        setButtonState();
      }
    });
    if (backdrop) backdrop.addEventListener("click", closeMobileNav);
    sidebar.querySelectorAll("[data-view]").forEach(item => item.addEventListener("click", () => {
      if (mobileQuery.matches) closeMobileNav();
    }));
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && shell.classList.contains("mobile-nav-open")) {
        closeMobileNav();
        toggle.focus({ preventScroll: true });
      }
    });
    if (typeof mobileQuery.addEventListener === "function") mobileQuery.addEventListener("change", onModeChange);
    else mobileQuery.addListener(onModeChange);
    onModeChange();
  }

  function boot() {
    document.documentElement.classList.add("motion-enabled");
    installSidebarToggle();
    installRequestFeedback();
    const host = $("#page-content");
    if (host && "MutationObserver" in window) {
      const mutationObserver = new MutationObserver(records => {
        if (records.some(record => record.addedNodes && record.addedNodes.length)) requestAnimationFrame(() => enhance(document));
      });
      mutationObserver.observe(host, { childList: true, subtree: true });
    }
    const detail = $("#detail-content");
    if (detail && "MutationObserver" in window) {
      const detailObserver = new MutationObserver(() => requestAnimationFrame(() => enhance(detail)));
      detailObserver.observe(detail, { childList: true, subtree: true });
    }
    document.addEventListener("click", event => {
      const btn = event.target instanceof Element ? event.target.closest(".btn, .nav-item") : null;
      if (!btn || btn.disabled || reduceMotion.matches) return;
      btn.classList.remove("motion-pressed");
      requestAnimationFrame(() => {
        btn.classList.add("motion-pressed");
        window.setTimeout(() => btn.classList.remove("motion-pressed"), 160);
      });
    }, { passive: true });
    $$("dialog").forEach(dialog => {
      dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    });
    enhance(document);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();


/* CAMPUS_PAGE_MOTION_V2: consistent page entrance and scroll reset.
   This addon is independent of the existing scroll-reveal implementation. */
(() => {
  "use strict";

  const start = () => {
    const page = document.getElementById("page-content");
    if (!page || page.dataset.campusPageMotionV2 === "true") return;
    page.dataset.campusPageMotionV2 = "true";
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let previousHeading = null;
    let previousPage = null;
    let pendingFrame = 0;

    function resetScroll() {
      const scroller = document.scrollingElement || document.documentElement;
      const oldBehavior = scroller.style.scrollBehavior;
      scroller.style.scrollBehavior = "auto";
      window.scrollTo(0, 0);
      scroller.scrollTop = 0;
      scroller.style.scrollBehavior = oldBehavior;
    }

    // Clicking a navigation item starts a fresh page; do not inherit scroll.
    // Capture phase runs before the existing application's click handler.
    document.addEventListener("click", event => {
      const element = event.target instanceof Element ? event.target : null;
      const button = element && element.closest("#main-nav [data-view], [data-go]");
      if (button && !button.disabled) resetScroll();
    }, true);

    function onPageRendered() {
      const heading = page.querySelector(":scope > .page-heading");
      if (!heading || heading === previousHeading) return;
      previousHeading = heading;

      const activeNav = document.querySelector("#main-nav .nav-item.active[data-view]");
      const activePage = activeNav ? activeNav.dataset.view : "";
      if (activePage !== previousPage) {
        resetScroll();
        previousPage = activePage;
      }

      // All pages animate when opened. No IntersectionObserver is required
      // for page content to become visible.
      page.classList.remove("campus-page-enter-v2");
      if (!reducedMotion.matches) {
        void page.offsetWidth; // restart the animation on repeated visits
        page.classList.add("campus-page-enter-v2");
      }
    }

    // Existing app.js replaces #page-content children on navigation.
    // Observe direct-child replacements, not nested table/row updates.
    const observer = new MutationObserver(records => {
      if (!records.some(record => record.target === page && record.type === "childList")) return;
      cancelAnimationFrame(pendingFrame);
      pendingFrame = requestAnimationFrame(onPageRendered);
    });
    observer.observe(page, { childList: true });
    onPageRendered();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
