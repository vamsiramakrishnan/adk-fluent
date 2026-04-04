/**
 * adk-fluent — Version Switcher
 *
 * Reads /versions.json and renders a dropdown in the sidebar header.
 * Each entry in versions.json has: { version, url, preferred? }
 *
 * The current version is detected from the <meta name="adk-version"> tag
 * injected by conf.py, or falls back to the page's Sphinx version.
 */

(function () {
  "use strict";

  // Resolve versions.json relative to the site root.
  // Works whether docs are at /adk-fluent/latest/, /adk-fluent/v0.13.5/, or /adk-fluent/.
  var VERSIONS_URL = (function () {
    var base = document.querySelector('link[rel="canonical"]');
    if (base) {
      var href = base.getAttribute("href");
      var match = href.match(/(\/adk-fluent\/)/);
      if (match) return match[1] + "versions.json";
    }
    // Fallback: detect from current URL
    var path = window.location.pathname;
    var siteMatch = path.match(/(\/adk-fluent\/)/);
    return (siteMatch ? siteMatch[1] : "/") + "versions.json";
  })();

  function getCurrentVersion() {
    var meta = document.querySelector('meta[name="adk-version"]');
    if (meta) return meta.getAttribute("content");
    // Fallback: try the Sphinx version from the page title
    var match = document.title.match(/v(\d+\.\d+\.\d+)/);
    return match ? match[1] : null;
  }

  function createSwitcher(versions, currentVersion) {
    var container = document.createElement("div");
    container.className = "version-switcher";

    var button = document.createElement("button");
    button.className = "version-switcher__button";
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-label", "Select documentation version");

    var currentEntry = versions.find(function (v) {
      return v.version === currentVersion;
    });
    var label = currentEntry
      ? currentEntry.version + (currentEntry.preferred ? " (latest)" : "")
      : currentVersion || "unknown";
    button.innerHTML =
      '<span class="version-switcher__label">v' + label + "</span>" +
      '<svg class="version-switcher__chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">' +
      '<path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>' +
      "</svg>";

    var menu = document.createElement("ul");
    menu.className = "version-switcher__menu";
    menu.setAttribute("role", "listbox");
    menu.style.display = "none";

    versions.forEach(function (v) {
      var item = document.createElement("li");
      item.setAttribute("role", "option");
      if (v.version === currentVersion) {
        item.setAttribute("aria-selected", "true");
      }

      var link = document.createElement("a");
      link.href = v.url;
      link.className = "version-switcher__item";
      if (v.version === currentVersion) {
        link.classList.add("version-switcher__item--active");
      }

      var versionText = "v" + v.version;
      if (v.preferred) versionText += " (latest)";
      if (v.prerelease) versionText += " (dev)";
      link.textContent = versionText;

      item.appendChild(link);
      menu.appendChild(item);
    });

    // Toggle dropdown
    button.addEventListener("click", function (e) {
      e.stopPropagation();
      var expanded = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!expanded));
      menu.style.display = expanded ? "none" : "block";
    });

    // Close on outside click
    document.addEventListener("click", function () {
      button.setAttribute("aria-expanded", "false");
      menu.style.display = "none";
    });

    // Close on Escape
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        button.setAttribute("aria-expanded", "false");
        menu.style.display = "none";
      }
    });

    container.appendChild(button);
    container.appendChild(menu);
    return container;
  }

  function insertSwitcher(switcher) {
    // Try to insert into Furo's sidebar brand area
    var brand = document.querySelector(".sidebar-brand");
    if (brand) {
      brand.parentNode.insertBefore(switcher, brand.nextSibling);
      return;
    }
    // Fallback: insert after the sidebar logo
    var logo = document.querySelector(".sidebar-logo-container");
    if (logo) {
      logo.parentNode.insertBefore(switcher, logo.nextSibling);
      return;
    }
    // Last resort: prepend to sidebar scroll area
    var sidebar = document.querySelector(".sidebar-scroll");
    if (sidebar) {
      sidebar.prepend(switcher);
    }
  }

  function init() {
    var currentVersion = getCurrentVersion();

    fetch(VERSIONS_URL)
      .then(function (res) {
        if (!res.ok) throw new Error("versions.json not found");
        return res.json();
      })
      .then(function (versions) {
        if (!Array.isArray(versions) || versions.length === 0) return;
        var switcher = createSwitcher(versions, currentVersion);
        insertSwitcher(switcher);
      })
      .catch(function () {
        // versions.json not deployed yet — silently skip.
        // This is expected during local development.
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
