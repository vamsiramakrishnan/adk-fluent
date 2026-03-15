/**
 * adk-fluent — Documentation UX Enhancements v2
 *
 * 1. Reading progress bar
 * 2. Hero diagram intersection observer
 * 3. Architecture diagram intersection observer
 * 4. Animated stat counters on hero
 * 5. Active TOC tracking (scroll spy)
 * 6. Smooth scroll-to-anchor
 */

(function () {
  "use strict";

  // ---- Reading progress bar ----

  function initReadingProgress() {
    var bar = document.createElement("div");
    bar.className = "reading-progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.prepend(bar);

    var ticking = false;
    function updateProgress() {
      var scrollTop = window.scrollY;
      var docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) {
        bar.style.width = "0%";
        return;
      }
      bar.style.width = Math.min((scrollTop / docHeight) * 100, 100) + "%";
    }

    window.addEventListener("scroll", function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          updateProgress();
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });

    updateProgress();
  }

  // ---- Intersection Observer for architecture diagrams ----

  function initDiagramObserver() {
    if (!("IntersectionObserver" in window)) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("diagram-visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.2 });

    document.querySelectorAll(".arch-diagram-wrapper").forEach(function (el) {
      observer.observe(el);
    });
  }

  // ---- Animated stat counters ----

  function initStatCounters() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (!("IntersectionObserver" in window)) return;

    var stats = document.querySelectorAll(".hero-stat .stat-number");
    if (stats.length === 0) return;

    var animated = false;
    var observer = new IntersectionObserver(function (entries) {
      if (animated) return;
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animated = true;
          observer.disconnect();
          animateCounters(stats);
        }
      });
    }, { threshold: 0.5 });

    stats.forEach(function (el) { observer.observe(el); });
  }

  function animateCounters(stats) {
    stats.forEach(function (el) {
      var text = el.textContent.trim();
      var num = parseInt(text, 10);
      if (isNaN(num) || num <= 0) return;

      var suffix = text.replace(String(num), "");
      var duration = 800;
      var start = performance.now();

      function tick(now) {
        var elapsed = now - start;
        var progress = Math.min(elapsed / duration, 1);
        // ease-out
        var eased = 1 - Math.pow(1 - progress, 3);
        var current = Math.round(eased * num);
        el.textContent = current + suffix;
        if (progress < 1) {
          requestAnimationFrame(tick);
        }
      }

      requestAnimationFrame(tick);
    });
  }

  // ---- Active TOC tracking (scroll spy) ----

  function initScrollSpy() {
    var tocLinks = document.querySelectorAll(".toc-tree a");
    if (tocLinks.length === 0) return;

    var headings = [];
    tocLinks.forEach(function (link) {
      var href = link.getAttribute("href");
      if (!href || href.charAt(0) !== "#") return;
      var target = document.getElementById(href.slice(1));
      if (target) {
        headings.push({ el: target, link: link });
      }
    });

    if (headings.length === 0) return;

    var ticking = false;
    function updateActive() {
      var scrollTop = window.scrollY + 100;
      var active = null;

      for (var i = headings.length - 1; i >= 0; i--) {
        if (headings[i].el.offsetTop <= scrollTop) {
          active = headings[i];
          break;
        }
      }

      tocLinks.forEach(function (link) { link.classList.remove("active"); });
      if (active) {
        active.link.classList.add("active");
      }
    }

    window.addEventListener("scroll", function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          updateActive();
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });

    updateActive();
  }

  // ---- Initialize ----

  function init() {
    initReadingProgress();
    initDiagramObserver();
    initStatCounters();
    initScrollSpy();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
