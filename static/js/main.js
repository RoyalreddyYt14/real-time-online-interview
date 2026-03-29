/* global io */

(function () {
  // Guard: this file may be included multiple times across templates.
  if (window.__rtInterviewDropdownInitialized) return;
  window.__rtInterviewDropdownInitialized = true;

  const root = document.getElementById("rtUserDropdownRoot");
  const toggleBtn = document.getElementById("rtUserToggle");
  const dropdownMenu = document.getElementById("rtDropdownMenu");

  const usernameEl = document.getElementById("rtUsername");

  const notifDot = document.getElementById("rtNotifDot");
  const notifCountEl = document.getElementById("rtNotifCount");

  const liveStatusBadge = document.getElementById("rtLiveStatusBadge");
  const liveTimerEl = document.getElementById("rtLiveTimer");
  const liveWarningsEl = document.getElementById("rtLiveWarnings");
  const liveConnectionBadge = document.getElementById("rtLiveConnectionBadge");
  const liveSection = document.getElementById("rtLiveSection");

  // Optional inline session panel (used by some interview pages like HR voice).
  const inlineStatusBadge = document.getElementById("rtInlineStatusBadge");
  const inlineTimerEl = document.getElementById("rtInlineTimer");
  const inlineWarningsEl = document.getElementById("rtInlineWarnings");
  const inlineConnectionBadge = document.getElementById("rtInlineConnectionBadge");

  const notificationsBtn = document.getElementById("rtNotificationsBtn");
  const supportBtn = document.getElementById("rtSupportBtn");

  const darkModeToggle = document.getElementById("rtDarkModeToggle");
  const toastContainer = document.getElementById("rtToastContainer");

  let notificationCount = 0;
  let lastWarningCount = 0;
  let lastInterviewStatus = null;

  function ensureGlobalLoader() {
    // Use existing page loader when present (dashboard/results templates).
    const existing = document.getElementById("loader");
    if (existing) return existing;

    // Fallback: create a lightweight loader overlay for templates that don't include it.
    let created = document.getElementById("rtGlobalLoader");
    if (created) return created;

    created = document.createElement("div");
    created.id = "rtGlobalLoader";
    created.innerHTML = `
      <div class="rt-global-loader-spinner"></div>
      <div class="rt-global-loader-text">Loading…</div>
    `;

    // Minimal styles inline so this works everywhere without extra CSS dependencies.
    created.style.position = "fixed";
    created.style.inset = "0";
    created.style.background = "rgba(255,255,255,0.92)";
    created.style.display = "flex";
    created.style.flexDirection = "column";
    created.style.justifyContent = "center";
    created.style.alignItems = "center";
    created.style.zIndex = "9999";
    created.style.transition = "opacity 0.25s ease";

    const style = document.createElement("style");
    style.textContent = `
      .rt-global-loader-spinner{
        width:50px;height:50px;border-radius:50%;
        border:5px solid rgba(0,0,0,0.12);
        border-top:5px solid #2563eb;
        animation: rtSpin 0.9s linear infinite;
      }
      .rt-global-loader-text{
        margin-top:14px;
        font: 700 14px/1.2 "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
        color:#0b2c4d;
      }
      @keyframes rtSpin{ to{ transform: rotate(360deg);} }
    `;
    document.head.appendChild(style);

    document.body.appendChild(created);
    return created;
  }

  function showPageLoader() {
    const loader = ensureGlobalLoader();
    loader.style.display = "flex";
    loader.style.opacity = "1";
    loader.setAttribute("data-visible", "true");
  }

  function hidePageLoader() {
    const loader = document.getElementById("rtGlobalLoader") || document.getElementById("loader");
    if (!loader) return;
    if (loader.id === "loader") {
      // Templates already implement a .hide class; use it when present.
      try {
        loader.classList.add("hide");
      } catch (e) {}
      return;
    }
    loader.style.opacity = "0";
    loader.style.display = "none";
  }

  function safeText(s) {
    return String(s ?? "");
  }

  function setHasNotifications(has) {
    if (!root) return;
    if (has) root.classList.add("rt-has-notifs");
    else root.classList.remove("rt-has-notifs");
  }

  function updateNotifBadge() {
    if (!notifCountEl) return;
    notifCountEl.textContent = String(notificationCount);
    setHasNotifications(notificationCount > 0);
  }

  function formatTimeLeft(timeLeftStr) {
    // Expecting MM:SS.
    if (!timeLeftStr) return "--:--";
    return safeText(timeLeftStr);
  }

  function setBadge(el, text, classes) {
    if (!el) return;
    el.textContent = text;

    // Replace badge classes deterministically.
    el.className = "rt-badge";
    if (classes && classes.length) el.classList.add(...classes);
  }

  function showToast(title, message, type) {
    if (!toastContainer) return;

    const toast = document.createElement("div");
    toast.className = "rt-toast";

    const icon = document.createElement("div");
    icon.className = "rt-toast-icon";
    icon.innerHTML =
      type === "danger"
        ? '<i class="fa-solid fa-triangle-exclamation"></i>'
        : '<i class="fa-solid fa-circle-info"></i>';

    const content = document.createElement("div");
    const titleEl = document.createElement("div");
    titleEl.className = "rt-toast-title";
    titleEl.textContent = safeText(title);

    const msgEl = document.createElement("div");
    msgEl.className = "rt-toast-msg";
    msgEl.textContent = safeText(message);

    content.appendChild(titleEl);
    content.appendChild(msgEl);

    toast.appendChild(icon);
    toast.appendChild(content);

    toastContainer.appendChild(toast);

    // Auto-remove.
    window.setTimeout(() => {
      try {
        toast.remove();
      } catch (e) {}
    }, 5500);
  }

  // Expose toast for simple template-driven UX without changing existing JS structure.
  window.__rtShowToast = showToast;

  function applyTheme(mode) {
    // mode: 'dark' | 'light'
    if (!darkModeToggle) {
      document.documentElement.dataset.theme = mode;
      return;
    }

    const isDark = mode === "dark";
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    darkModeToggle.checked = isDark;
  }

  function initTheme() {
    const saved = localStorage.getItem("rt_interview_theme");
    if (saved === "dark" || saved === "light") {
      applyTheme(saved);
      return;
    }

    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(prefersDark ? "dark" : "light");
  }

  function setupDropdown() {
    if (!root || !toggleBtn || !dropdownMenu) return;

    function openMenu() {
      root.classList.add("open");
      toggleBtn.setAttribute("aria-expanded", "true");
    }

    function closeMenu() {
      root.classList.remove("open");
      toggleBtn.setAttribute("aria-expanded", "false");
    }

    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (root.classList.contains("open")) closeMenu();
      else openMenu();
    });

    document.addEventListener("click", (e) => {
      if (!root.classList.contains("open")) return;
      if (root.contains(e.target)) return;
      closeMenu();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeMenu();
    });
  }

  function statusToBadge(status) {
    const s = safeText(status);
    if (s === "Active") return { text: "Active", classes: ["rt-badge-primary"] };
    if (s === "Waiting") return { text: "Waiting", classes: [] };
    if (s === "Completed") return { text: "Completed", classes: ["rt-badge-online"] };
    return { text: s, classes: [] };
  }

  function connectionToBadge(connection) {
    const c = safeText(connection);
    if (c === "Online" || c === "Stable") return ["rt-badge-online"];
    return ["rt-badge-offline"];
  }

  function handleSessionUpdate(data) {
    if (!data) return;

    const path = (window.location && window.location.pathname) ? window.location.pathname : "";
    const isInterviewPage =
      path === "/aptitude" ||
      path === "/technical" ||
      path === "/coding" ||
      path === "/hr";

    const status = safeText(data.status);
    const timeLeft = formatTimeLeft(data.time_left);
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    const connection = safeText(data.connection);

    if (usernameEl && usernameEl.textContent === "Guest" && data.user_name) {
      usernameEl.textContent = data.user_name;
    }

    // Status badge.
    const statusBadge = statusToBadge(status);
    setBadge(liveStatusBadge, statusBadge.text, statusBadge.classes);
    setBadge(inlineStatusBadge, statusBadge.text, statusBadge.classes);

    // Timer.
    if (liveTimerEl) liveTimerEl.textContent = timeLeft;
    if (inlineTimerEl) inlineTimerEl.textContent = timeLeft;

    // Warnings.
    const hasWarnings = warnings.length > 0;
    if (liveSection) {
      if (hasWarnings) liveSection.classList.add("rt-has-warnings");
      else liveSection.classList.remove("rt-has-warnings");
    }

    if (liveWarningsEl) {
      liveWarningsEl.textContent = hasWarnings ? warnings.join(" • ") : "None";
    }
    if (inlineWarningsEl) {
      inlineWarningsEl.textContent = hasWarnings ? warnings.join(" • ") : "None";
    }

    // Connection.
    if (liveConnectionBadge) {
      setBadge(liveConnectionBadge, connection || "Online", connectionToBadge(connection || "Online"));
    }
    if (inlineConnectionBadge) {
      setBadge(inlineConnectionBadge, connection || "Stable", connectionToBadge(connection || "Stable"));
    }

    // Notifications + toast for new alerts (use server-side warning_count delta).
    const currentWarningCount =
      typeof data.warning_count === "number"
        ? data.warning_count
        : hasWarnings
          ? 1
          : 0;

    if (currentWarningCount > lastWarningCount) {
      const delta = currentWarningCount - lastWarningCount;
      lastWarningCount = currentWarningCount;
      notificationCount += delta;
      updateNotifBadge();

      const message = hasWarnings ? warnings.join(", ") : "New warning detected.";
      showToast("Warning Alert", message, "danger");

      if (liveSection) {
        // Restart the flash animation on every new alert.
        liveSection.classList.remove("rt-warning-anim");
        // Force reflow so the animation reliably restarts.
        // eslint-disable-next-line no-unused-expressions
        liveSection.offsetWidth;
        liveSection.classList.add("rt-warning-anim");
        window.setTimeout(() => {
          liveSection.classList.remove("rt-warning-anim");
        }, 1350);
      }
    } else if (currentWarningCount === 0) {
      lastWarningCount = 0;
    }

    // Strict redirect: only when backend explicitly says interview_status === "completed".
    // (Dashboard/menus are excluded by isInterviewPage, so login/navigation won't bounce.)
    const interviewStatus = safeText(data.interview_status).toLowerCase();

    if (isInterviewPage && interviewStatus === "completed") {
      if (lastInterviewStatus !== "completed") {
        lastInterviewStatus = "completed";
        showToast("Interview Completed", "Redirecting to results...", "info");
        try {
          if (window.location.pathname !== "/results") {
            window.location.href = "/results";
          }
        } catch (e) {}
      }
    } else {
      // Reset marker when leaving completed state so future attempts can redirect correctly.
      if (lastInterviewStatus === "completed" && interviewStatus !== "completed") {
        lastInterviewStatus = null;
      }
    }
  }

  function setupNotifications() {
    if (notificationsBtn) {
      notificationsBtn.addEventListener("click", () => {
        // "Mark as read" UX: reset badge and show a toast.
        notificationCount = 0;
        updateNotifBadge();
        const text = liveWarningsEl && liveWarningsEl.textContent ? liveWarningsEl.textContent : "No warnings";
        showToast("Notifications", text, "info");
      });
    }

    if (supportBtn) {
      supportBtn.addEventListener("click", () => {
        // If the existing dashboard has a modal, try opening it; otherwise use a toast.
        const modalEl = document.getElementById("supportModal");
        if (modalEl && window.bootstrap && window.bootstrap.Modal) {
          const instance = window.bootstrap.Modal.getInstance(modalEl) || new window.bootstrap.Modal(modalEl);
          instance.show();
          return;
        }
        showToast("Support", "A support agent will be with you shortly (demo).", "info");
      });
    }
  }

  function setupDarkMode() {
    if (!darkModeToggle) return;
    initTheme();

    darkModeToggle.addEventListener("change", () => {
      const mode = darkModeToggle.checked ? "dark" : "light";
      localStorage.setItem("rt_interview_theme", mode);
      applyTheme(mode);
    });
  }

  function setupSocket() {
    if (typeof io === "undefined") return;

    let socket;
    try {
      socket = io({ transports: ["websocket", "polling"], withCredentials: true });
    } catch (e) {
      return;
    }

    socket.on("connect", () => {
      if (liveConnectionBadge) {
        setBadge(liveConnectionBadge, "Stable", ["rt-badge-online"]);
      }
      if (inlineConnectionBadge) {
        setBadge(inlineConnectionBadge, "Stable", ["rt-badge-online"]);
      }
    });

    socket.on("disconnect", () => {
      if (liveConnectionBadge) {
        setBadge(liveConnectionBadge, "Offline", ["rt-badge-offline"]);
      }
      if (inlineConnectionBadge) {
        setBadge(inlineConnectionBadge, "Offline", ["rt-badge-offline"]);
      }
    });

    socket.on("session_update", (payload) => {
      handleSessionUpdate(payload);
    });

    socket.on("connect_error", () => {
      if (liveConnectionBadge) {
        setBadge(liveConnectionBadge, "Offline", ["rt-badge-offline"]);
      }
    });
  }

  function isInterviewPagePath(path) {
    return (
      path === "/aptitude" ||
      path === "/technical" ||
      path === "/coding" ||
      path === "/hr"
    );
  }

  // If the user navigates away from an interview page, stop monitoring resources.
  window.addEventListener("pagehide", () => {
    try {
      const path = window.location && window.location.pathname ? window.location.pathname : "";
      if (!isInterviewPagePath(path)) return;
      // Best-effort; backend verifies session role.
      fetch("/interview/exit", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: "{}",
        keepalive: true,
      });
    } catch (e) {}
  });

  // UX polish: show a loader on navigation + form submits to avoid flicker.
  document.addEventListener("click", (e) => {
    try {
      const link = e.target && e.target.closest ? e.target.closest("a") : null;
      if (!link) return;

      const href = link.getAttribute && link.getAttribute("href");
      if (!href) return;
      if (href.startsWith("#")) return;
      if (href.startsWith("javascript:")) return;

      // Allow templates to opt-out if needed.
      if (link.getAttribute("data-no-loader") === "true") return;

      // Only show for same-origin navigations.
      if (href.startsWith("/")) showPageLoader();
    } catch (err) {}
  });

  document.addEventListener("submit", () => {
    showPageLoader();
  });

  window.addEventListener("load", () => {
    hidePageLoader();
  });

  setupDropdown();
  setupNotifications();
  setupDarkMode();
  setupSocket();
})();

// =======================
// VOICE RECOGNITION FIX
// =======================
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = () => {
        console.log("🎤 Voice started");
    };

    recognition.onresult = (event) => {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            transcript += event.results[i][0].transcript;
        }

        console.log("User said:", transcript);

        // 👉 OPTIONAL: auto-fill input box
        let input = document.querySelector("#answerBox");
        if (input) {
            input.value = transcript;
        }
    };

    recognition.onerror = (event) => {
        console.error("Voice error:", event.error);
    };

    // 👉 OPTIONAL: start automatically
    // recognition.start();

} else {
    console.log("❌ Speech Recognition not supported");
}

// =========================
// 🎤 VOICE INPUT FUNCTION (HR ROUND)
// =========================
// function startVoice() {
//     const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

//     if (!SpeechRecognition) {
//         alert("Voice not supported on this device. Please type your answer.");
//         return;
//     }

//     const recognition = new SpeechRecognition();
//     recognition.lang = "en-US";

//     recognition.onstart = () => {
//         console.log("🎤 Listening...");
//     };

//     recognition.onresult = (event) => {
//         const text = event.results[0][0].transcript;

//         // Put voice text into textarea
//         const textarea = document.querySelector("textarea");
//         if (textarea) {
//             textarea.value = text;
//         }
//     };

//     recognition.start();
// }