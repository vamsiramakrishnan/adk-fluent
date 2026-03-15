/**
 * adk-fluent — Documentation UX Enhancements
 *
 * 1. Reading progress bar
 * 2. Smooth theme transition support
 * 3. Hero diagram intersection observer
 * 4. Smooth scroll-to-anchor
 */

(function () {
  "use strict";

  // ---- Reading progress bar ----

  function initReadingProgress() {
    const bar = document.createElement("div");
    bar.className = "reading-progress";
    bar.setAttribute("aria-hidden", "true");
    document.body.prepend(bar);

    function updateProgress() {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      if (docHeight <= 0) {
        bar.style.width = "0%";
        return;
      }
      const progress = Math.min((scrollTop / docHeight) * 100, 100);
      bar.style.width = progress + "%";
    }

    // Use passive listener + rAF for smooth performance
    let ticking = false;
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
    // Respect reduced motion preference
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const observer = new IntersectionObserver(function (entries) {
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

  // ---- Initialize ----

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initReadingProgress();
      initDiagramObserver();
    });
  } else {
    initReadingProgress();
    initDiagramObserver();
  }
})();
