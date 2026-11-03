// Shared header for index.html and favorites.html: shows the signed-in user or login links.
window.MoodSession = (function () {
  const pill =
    "rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:border-orange-300 hover:bg-orange-50";
  const activePill =
    "rounded-full border border-orange-300 bg-orange-100 px-3 py-1.5 text-sm font-medium text-orange-800 shadow-sm";

  let current = null;

  async function load() {
    try {
      const res = await fetch("/api/auth/me", { credentials: "same-origin" });
      current = (await res.json()).user;
    } catch {
      current = null;
    }
    return current;
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
    location.href = "/";
  }

  function loginUrl() {
    return `/login.html?next=${encodeURIComponent(location.pathname + location.search)}`;
  }

  /** Renders nav links into #nav. `page` is "home" or "favorites". */
  function renderNav(page) {
    const nav = document.getElementById("nav");
    nav.innerHTML = "";
    const link = (href, text, cls) => {
      const a = document.createElement("a");
      a.href = href;
      a.textContent = text;
      a.className = cls;
      nav.appendChild(a);
      return a;
    };
    if (current) {
      if (page !== "home") link("/", "Home", pill);
      const email = document.createElement("span");
      email.id = "nav-email";
      email.className = "max-w-[14rem] truncate text-sm text-slate-600";
      email.textContent = current.email;
      nav.appendChild(email);
      link("/favorites.html", "Favorites", page === "favorites" ? activePill : pill);
      const out = document.createElement("button");
      out.type = "button";
      out.id = "btn-logout";
      out.textContent = "Log out";
      out.className = pill;
      out.addEventListener("click", logout);
      nav.appendChild(out);
    } else {
      link(loginUrl(), "Log in", pill);
      link(`/register.html?next=${encodeURIComponent(location.pathname)}`, "Register", activePill);
    }
  }

  return {
    load,
    renderNav,
    loginUrl,
    get user() {
      return current;
    },
  };
})();
