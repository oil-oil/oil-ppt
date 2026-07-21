(() => {
  "use strict";
  const W = 1920;
  const H = 1080;
  const slides = [...document.querySelectorAll(".oil-slide")];
  const isPreview = document.body.dataset.oilMode === "preview";
  const stage = document.querySelector(isPreview ? ".slide-preview-stage" : ".deck-stage");
  const shell = document.querySelector(isPreview ? ".slide-preview-shell" : ".deck-stage-shell");
  const counter = document.querySelector(".deck-counter");
  const progress = document.querySelector(".progress-bar");
  const overview = document.querySelector("[data-deck-overview]");
  const overviewGrid = document.querySelector("[data-deck-overview-grid]");
  const overviewToggle = document.querySelector("[data-deck-overview-toggle]");
  const overviewClose = document.querySelector("[data-deck-overview-close]");
  const originalSlides = new Map();
  let overviewOpenerState = null;
  let overviewOpen = false;
  let index = 0;

  function scaleStage() {
    if (!stage || !shell) return;
    const width = shell.clientWidth || window.innerWidth;
    const height = shell.clientHeight || window.innerHeight;
    const scale = Math.min(width / W, height / H);
    stage.style.transform = `translate(-50%, -50%) scale(${scale})`;
    stage.dataset.scale = String(scale);
  }

  function overflows(el) {
    const widthOverflow = el.scrollWidth > el.clientWidth + 1;
    const heightOverflow = el.dataset.fitHeight !== undefined
      && el.scrollHeight > el.clientHeight + 1;
    return widthOverflow || heightOverflow;
  }

  function fitText(el) {
    const computed = getComputedStyle(el);
    const start = Number.parseFloat(el.dataset.fitStart || computed.fontSize);
    const declaredMinimum = Number.parseFloat(el.dataset.minSize || "");
    const min = Number.isFinite(declaredMinimum)
      ? Math.min(start, Math.max(12, declaredMinimum))
      : Math.max(18, Math.floor(start * .7));
    if (!Number.isFinite(start) || !Number.isFinite(min)) return;
    el.dataset.fitStart = String(start);
    el.style.fontSize = `${start}px`;
    let size = start;
    while (overflows(el) && size > min) {
      size = Math.max(min, size - 1);
      el.style.fontSize = `${size}px`;
    }
  }

  function checkTextBudget(el) {
    const max = Number.parseInt(el.dataset.maxChars || "", 10);
    if (!Number.isFinite(max)) return;
    const length = (el.textContent || "").replace(/\s+/g, "").length;
    if (length > max) {
      el.dataset.validationStatus = "warning";
      el.dataset.warningReason = "text-budget";
      el.dataset.textMetrics = `${length}/${max}`;
    }
  }

  function checkSpaceUse(safe) {
    const mode = safe.dataset.layoutCheck;
    if (!mode) return;
    const slide = safe.closest(".oil-slide");
    const items = [...(slide || safe).querySelectorAll("[data-layout]")].filter(el => el.getClientRects().length && getComputedStyle(el).display !== "none");
    if (!items.length) { safe.dataset.validationStatus = "warning"; safe.dataset.warningReason = "underused"; return; }
    const base = safe.getBoundingClientRect();
    const rects = items.map(el => el.getBoundingClientRect());
    const left = Math.min(...rects.map(r => r.left));
    const right = Math.max(...rects.map(r => r.right));
    const top = Math.min(...rects.map(r => r.top));
    const bottom = Math.max(...rects.map(r => r.bottom));
    const spanW = (right - left) / base.width;
    const spanH = (bottom - top) / base.height;
    const area = rects.reduce((sum, r) => sum + Math.max(0, r.width) * Math.max(0, r.height), 0) / (base.width * base.height);
    const threshold = mode === "minimal" ? { w: .45, h: .30, a: .08 } : { w: .68, h: .55, a: .20 };
    if (spanW < threshold.w || spanH < threshold.h || area < threshold.a) {
      safe.dataset.validationStatus = "warning";
      safe.dataset.warningReason = "underused";
      safe.dataset.spaceMetrics = `${spanW.toFixed(2)},${spanH.toFixed(2)},${area.toFixed(2)}`;
    }
  }

  function checkTitleOrphan(el) {
    if (el.dataset.orphanOk !== undefined || !el.getClientRects().length) return;
    const chars = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const value = node.nodeValue || "";
      for (let i = 0; i < value.length; i += 1) {
        if (/\s/.test(value[i])) continue;
        const range = document.createRange();
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        const rect = range.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) chars.push({ value: value[i], top: rect.top });
      }
    }
    const lines = [];
    chars.forEach(char => {
      let line = lines.find(item => Math.abs(item.top - char.top) < 2);
      if (!line) { line = { top: char.top, values: [] }; lines.push(line); }
      line.values.push(char.value);
    });
    lines.sort((a, b) => a.top - b.top);
    const last = lines[lines.length - 1];
    if (lines.length > 1 && last && last.values.length === 1 && /[\u3400-\u9fff]/.test(last.values[0])) {
      el.dataset.validationStatus = "warning";
      el.dataset.warningReason = "title-orphan";
      el.dataset.textMetrics = `last-line:${last.values[0]}`;
    }
  }

  function checkCopyFlow(flow) {
    const title = [...flow.children].find(node => node.matches?.("[data-copy-title]"));
    const body = [...flow.children].find(node => node.matches?.("[data-copy-body]"));
    if (!title || !body || !title.textContent.trim() || !body.textContent.trim()) return;
    if (body.previousElementSibling !== title) return;
    if (!title.getClientRects().length || !body.getClientRects().length) return;
    const gap = body.getBoundingClientRect().top - title.getBoundingClientRect().bottom;
    if (gap > 72) {
      flow.dataset.validationStatus = "warning";
      flow.dataset.warningReason = "copy-gap";
      flow.dataset.copyMetrics = `gap:${Math.round(gap)}`;
    }
  }

  function validateLayout() {
    document.querySelectorAll("[data-validation-status], [data-warning-reason], [data-text-metrics], [data-space-metrics], [data-copy-metrics]").forEach(el => {
      delete el.dataset.validationStatus;
      delete el.dataset.warningReason;
      delete el.dataset.textMetrics;
      delete el.dataset.spaceMetrics;
      delete el.dataset.copyMetrics;
    });
    document.querySelectorAll("[data-fit]").forEach(fitText);
    document.querySelectorAll("[data-max-chars]").forEach(checkTextBudget);
    document.querySelectorAll("h1").forEach(checkTitleOrphan);
    document.querySelectorAll("[data-copy-flow]").forEach(checkCopyFlow);
    document.querySelectorAll(".slide-safe").forEach(checkSpaceUse);
    document.documentElement.dataset.oilValidated = "ok";
    document.documentElement.dataset.oilWarnings = String(document.querySelectorAll('[data-validation-status="warning"]').length);
  }

  function renderNextPreview() {
    const host = document.querySelector(".next-preview");
    if (!host) return;
    const next = slides[index + 1];
    host.hidden = !next;
    if (!next) return;
    const title = host.querySelector(".next-preview-title");
    title.textContent = next.dataset.title || next.dataset.slideId || "下一页";
  }

  function show(target) {
    index = Math.max(0, Math.min(slides.length - 1, target));
    slides.forEach((slide, i) => {
      slide.classList.toggle("active", i === index);
      slide.setAttribute("aria-hidden", i === index ? "false" : "true");
    });
    if (counter) counter.textContent = `${index + 1} / ${slides.length}`;
    if (progress) progress.style.width = `${((index + 1) / slides.length) * 100}%`;
    renderNextPreview();
    updateOverviewCurrent();
  }

  function updateOverviewCurrent() {
    if (!overviewGrid) return;
    overviewGrid.querySelectorAll("[data-deck-overview-slide]").forEach((button, i) => {
      const current = i === index;
      if (current) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
      button.classList.toggle("is-current", current);
      button.closest(".deck-overview-card")?.classList.toggle("is-current", current);
    });
  }

  function restoreSlides() {
    if (!stage) return;
    slides.forEach(slide => {
      const saved = originalSlides.get(slide);
      if (!saved) return;
      slide.className = saved.className;
      slide.style.cssText = saved.style;
      if (saved.ariaHidden === null) slide.removeAttribute("aria-hidden");
      else slide.setAttribute("aria-hidden", saved.ariaHidden);
      slide.inert = saved.inert;
      if (saved.inertAttribute === null) slide.removeAttribute("inert");
      else slide.setAttribute("inert", saved.inertAttribute);
      stage.appendChild(slide);
    });
    originalSlides.clear();
    if (overviewToggle && overviewOpenerState) {
      overviewToggle.inert = overviewOpenerState.inert;
      if (overviewOpenerState.inertAttribute === null) overviewToggle.removeAttribute("inert");
      else overviewToggle.setAttribute("inert", overviewOpenerState.inertAttribute);
    }
    overviewOpenerState = null;
    overviewGrid?.replaceChildren();
  }

  function closeOverview() {
    if (!overview || !overviewOpen) return;
    overviewOpen = false;
    overview.hidden = true;
    overview.setAttribute("aria-hidden", "true");
    document.body.classList.remove("deck-overview-open");
    overviewToggle?.setAttribute("aria-expanded", "false");
    restoreSlides();
    show(index);
    overviewToggle?.focus();
  }

  function openOverview() {
    if (!overview || !overviewGrid || !stage || overviewOpen || isPreview) return;
    overviewOpen = true;
    if (overviewToggle) {
      overviewOpenerState = { inert: Boolean(overviewToggle.inert), inertAttribute: overviewToggle.getAttribute("inert") };
      overviewToggle.inert = true;
    }
    slides.forEach((slide, i) => {
      originalSlides.set(slide, { className: slide.className, style: slide.style.cssText, ariaHidden: slide.getAttribute("aria-hidden"), inert: Boolean(slide.inert), inertAttribute: slide.getAttribute("inert") });
      const card = document.createElement("article");
      card.className = "deck-overview-card";
      const visual = document.createElement("div");
      visual.className = "deck-overview-visual";
      visual.appendChild(slide);
      const caption = document.createElement("span");
      caption.className = "deck-overview-caption";
      caption.textContent = `${i + 1}. ${slide.dataset.title || slide.dataset.slideId || "未命名"}`;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "deck-overview-hit";
      button.dataset.deckOverviewSlide = String(i);
      button.setAttribute("aria-label", `第 ${i + 1} 页：${slide.dataset.title || slide.dataset.slideId || "未命名"}`);
      button.addEventListener("click", () => { go(i); closeOverview(); });
      card.append(visual, caption, button);
      overviewGrid.appendChild(card);
      slide.setAttribute("aria-hidden", "true");
      slide.inert = true;
    });
    overview.hidden = false;
    overview.setAttribute("aria-hidden", "false");
    document.body.classList.add("deck-overview-open");
    overviewToggle?.setAttribute("aria-expanded", "true");
    updateOverviewCurrent();
    requestAnimationFrame(() => { sizeOverviewSlides(); overviewClose?.focus(); });
  }

  function sizeOverviewSlides() {
    if (!overviewOpen || !overviewGrid) return;
    overviewGrid.querySelectorAll(".deck-overview-visual").forEach(visual => {
      const slide = visual.querySelector(".oil-slide");
      const width = visual.getBoundingClientRect().width;
      if (slide && width) slide.style.transform = `scale(${width / W})`;
    });
  }

  function routeIndex() {
    const id = decodeURIComponent(location.hash.replace(/^#\/?/, ""));
    const found = slides.findIndex(slide => slide.dataset.slideId === id);
    return found >= 0 ? found : 0;
  }

  function go(target) {
    const next = Math.max(0, Math.min(slides.length - 1, target));
    const id = slides[next]?.dataset.slideId;
    if (!id) return;
    if (next === index && location.hash === `#/${encodeURIComponent(id)}`) return;
    history.pushState({}, "", `#/${encodeURIComponent(id)}`);
    show(next);
  }

  function initDeck() {
    if (isPreview) {
      show(0);
      return;
    }
    show(routeIndex());
    if (!location.hash && slides[0]?.dataset.slideId) history.replaceState({}, "", `#/${encodeURIComponent(slides[0].dataset.slideId)}`);
    addEventListener("hashchange", () => show(routeIndex()));
    addEventListener("popstate", () => show(routeIndex()));
    addEventListener("keydown", event => {
      if (event.key === "Escape" && overviewOpen) { event.preventDefault(); closeOverview(); return; }
      const editable = event.target instanceof Element && event.target.closest("input, textarea, select, [contenteditable]");
      if (editable || event.metaKey || event.ctrlKey || event.altKey) return;
      if (overviewOpen && event.key === "Tab") {
        const focusable = [...overview.querySelectorAll("[data-deck-overview-close], [data-deck-overview-slide]")];
        const first = focusable[0], last = focusable[focusable.length - 1];
        if (first && last && (document.activeElement === last && !event.shiftKey || document.activeElement === first && event.shiftKey || !overview.contains(document.activeElement))) {
          event.preventDefault();
          (event.shiftKey ? last : first).focus();
        }
        return;
      }
      if (event.key.toLowerCase() === "o") { event.preventDefault(); overviewOpen ? closeOverview() : openOverview(); return; }
      if (overviewOpen) return;
      if (["ArrowRight", "ArrowDown", "PageDown", " "].includes(event.key)) { event.preventDefault(); go(index + 1); }
      if (["ArrowLeft", "ArrowUp", "PageUp"].includes(event.key)) { event.preventDefault(); go(index - 1); }
      if (event.key === "Home") { event.preventDefault(); go(0); }
      if (event.key === "End") { event.preventDefault(); go(slides.length - 1); }
      if (event.key.toLowerCase() === "f") {
        if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
        else document.exitFullscreen?.();
      }
      if (event.key.toLowerCase() === "n") document.body.classList.toggle("hide-next");
    });
    let touchX = 0;
    stage?.addEventListener("touchstart", event => { touchX = event.touches[0]?.clientX || 0; }, { passive: true });
    stage?.addEventListener("touchend", event => {
      const dx = (event.changedTouches[0]?.clientX || 0) - touchX;
      if (Math.abs(dx) > 50) dx < 0 ? go(index + 1) : go(index - 1);
    }, { passive: true });
    const clickNav = document.body.dataset.clickNav === "true";
    if (clickNav) addEventListener("click", event => {
      if (overviewOpen || event.target.closest(".deck-counter, .next-preview, .deck-overview, .deck-overview-toggle, a, button, input, textarea, select, [contenteditable]")) return;
      if (window.getSelection()?.toString()) return;
      go(event.clientX < window.innerWidth / 2 ? index - 1 : index + 1);
    });
  }

  function setupTabs() {
    document.querySelectorAll("[data-oil-tabs]").forEach(group => {
      const tabs = [...group.querySelectorAll("[data-tab]")];
      const panels = [...group.querySelectorAll("[data-tab-panel]")];
      const activate = id => {
        tabs.forEach(tab => tab.setAttribute("aria-selected", tab.dataset.tab === id ? "true" : "false"));
        panels.forEach(panel => { panel.hidden = panel.dataset.tabPanel !== id; });
        validateLayout();
      };
      tabs.forEach(tab => tab.addEventListener("click", () => activate(tab.dataset.tab)));
      if (tabs[0]) activate(tabs.find(tab => tab.getAttribute("aria-selected") === "true")?.dataset.tab || tabs[0].dataset.tab);
    });
  }

  document.documentElement.dataset.oilValidated = "pending";
  overviewToggle?.addEventListener("click", openOverview);
  overviewClose?.addEventListener("click", closeOverview);
  addEventListener("beforeprint", closeOverview);
  scaleStage();
  setupTabs();
  initDeck();
  validateLayout();
  addEventListener("resize", () => { scaleStage(); sizeOverviewSlides(); validateLayout(); });
  const fontsReady = document.fonts?.ready || Promise.resolve();
  fontsReady.then(() => requestAnimationFrame(() => { validateLayout(); renderNextPreview(); }));
})();
