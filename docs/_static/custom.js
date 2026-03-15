/**
 * adk-fluent — Documentation UX Enhancements
 *
 * 1. Reading progress bar
 * 2. Smooth theme transition support
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

  // ---- Initialize ----

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReadingProgress);
  } else {
    initReadingProgress();
  }
})();
