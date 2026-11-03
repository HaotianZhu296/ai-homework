// Behaviour for login.html, register.html, forgot-password.html and reset-password.html.
(function () {
  const REMEMBER_KEY = "moodRecipesEmail";
  const msgEl = document.getElementById("form-msg");
  const params = new URLSearchParams(location.search);

  /** Only allow same-site relative redirects after login. */
  function nextUrl() {
    const next = params.get("next") || "/";
    return next.startsWith("/") && !next.startsWith("//") ? next : "/";
  }

  // Carry ?next= across the login / register / forgot links.
  document.querySelectorAll("a[data-keep-next]").forEach((a) => {
    if (params.get("next")) {
      const url = new URL(a.href, location.origin);
      url.searchParams.set("next", nextUrl());
      a.href = url.pathname + url.search;
    }
  });

  function showMessage(text, kind = "error", html = false) {
    if (html) msgEl.innerHTML = text;
    else msgEl.textContent = text;
    msgEl.className = `form-msg ${kind}`;
  }

  function hideMessage() {
    msgEl.className = "form-msg hidden";
  }

  function errorText(body, fallback) {
    const detail = body && body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      // FastAPI validation errors: [{loc, msg}]
      return detail
        .map((d) => {
          const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : "";
          const msg = String(d.msg || "").replace(/^Value error, /, "");
          return field === "email" ? "Please enter a valid email address." : msg;
        })
        .join(" ");
    }
    return fallback;
  }

  async function postJSON(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
      credentials: "same-origin",
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(errorText(body, "Something went wrong. Please try again."));
    return body;
  }

  function bindForm(form, handler) {
    const button = form.querySelector('button[type="submit"]');
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideMessage();
      button.disabled = true;
      try {
        await handler();
      } catch (err) {
        showMessage(err instanceof Error ? err.message : "Something went wrong.");
      } finally {
        button.disabled = false;
      }
    });
  }

  const value = (id) => document.getElementById(id).value;

  function checkPasswords() {
    if (value("password").length < 8) throw new Error("Password must be at least 8 characters.");
    if (value("password") !== value("confirm")) throw new Error("Passwords do not match.");
  }

  // ---- login ----
  const loginForm = document.getElementById("login-form");
  if (loginForm) {
    try {
      const saved = localStorage.getItem(REMEMBER_KEY);
      if (saved) {
        document.getElementById("email").value = saved;
        document.getElementById("remember").checked = true;
      }
    } catch {}
    if (params.get("reset") === "1") showMessage("Password updated. Log in with your new password.", "ok");

    bindForm(loginForm, async () => {
      const email = value("email").trim();
      const remember = document.getElementById("remember").checked;
      if (!email || !value("password")) throw new Error("Enter your email and password.");
      await postJSON("/api/auth/login", { email, password: value("password"), remember });
      try {
        if (remember) localStorage.setItem(REMEMBER_KEY, email);
        else localStorage.removeItem(REMEMBER_KEY);
      } catch {}
      location.href = nextUrl();
    });
  }

  // ---- register ----
  const registerForm = document.getElementById("register-form");
  if (registerForm) {
    bindForm(registerForm, async () => {
      checkPasswords();
      await postJSON("/api/auth/register", { email: value("email").trim(), password: value("password") });
      location.href = nextUrl();
    });
  }

  // ---- forgot password ----
  const forgotForm = document.getElementById("forgot-form");
  if (forgotForm) {
    bindForm(forgotForm, async () => {
      const email = value("email").trim();
      if (!email) throw new Error("Enter your email.");
      const body = await postJSON("/api/auth/forgot", { email });
      const text = document.createElement("span");
      text.textContent = body.message;
      let html = text.innerHTML;
      if (body.dev_reset_link) {
        // Local development without SMTP: show the link that would have been emailed.
        const a = document.createElement("a");
        a.href = body.dev_reset_link;
        a.textContent = "Open reset link";
        a.id = "dev-reset-link";
        html += `<br><br><small>Dev mode (no email server configured):</small><br>${a.outerHTML}`;
      }
      showMessage(html, "ok", true);
    });
  }

  // ---- reset password ----
  const resetForm = document.getElementById("reset-form");
  if (resetForm) {
    const token = params.get("token") || "";
    const intro = document.getElementById("reset-intro");
    (async () => {
      const check = token ? await postJSON("/api/auth/reset/check", { token }).catch(() => ({ valid: false })) : { valid: false };
      if (!check.valid) {
        intro.textContent = "";
        showMessage('This reset link is invalid or has expired. <a href="/forgot-password.html">Request a new one</a>.', "error", true);
        return;
      }
      intro.textContent = `Choose a new password for ${check.email}.`;
      resetForm.classList.remove("hidden");
      document.getElementById("password").focus();
    })();

    bindForm(resetForm, async () => {
      checkPasswords();
      await postJSON("/api/auth/reset", { token, password: value("password") });
      location.href = "/login.html?reset=1";
    });
  }
})();
