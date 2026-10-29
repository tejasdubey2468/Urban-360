/**
 * RAKSHA-FORCE — Demo Mock Authentication
 * ─────────────────────────────────────────
 * Frontend-only simulation for demo purposes. NOT secure authentication.
 * No credentials are sent to any API, and no Supabase Auth session is created.
 * Session lives in sessionStorage (current browser tab only).
 */
(function () {
  const STORAGE_KEY = 'urban360_demo_session';
  const DELAY_MS = 900; // simulated network/auth delay

  // Demo accounts with persistent Supabase UUIDs for consistent user association.
  const DEMO_ACCOUNTS = [
    { id: '09dca2fc-d7cb-45bc-9a5c-988e4178d8eb', email: 'citizen@urban360.demo',   password: 'Demo@123', role: 'citizen',      name: 'Citizen User',      dashboard: 'citizen.html' },
    { id: 'f1d9969c-51d6-4dfe-91ff-9f7b5d1c515c', email: 'officer@urban360.demo',   password: 'Demo@123', role: 'officer',      name: 'Officer User',      dashboard: 'admin.html' },
    { id: 'e3162188-bcc2-4d9e-8515-eaa54fbf9b9b', email: 'worker@urban360.demo',    password: 'Demo@123', role: 'field_worker', name: 'Field Worker',      dashboard: 'admin.html' },
    { id: 'e6dd5788-a0f6-4c1f-a793-92b21746ffc6', email: 'admin@urban360.demo',     password: 'Demo@123', role: 'administrator',name: 'Administrator',     dashboard: 'admin.html' },
  ];

  let current = null;

  function loadSession() {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const s = JSON.parse(raw);
      if (s && s.demoMode === true && s.email && s.role) return s;
    } catch (_) {
      // Malformed or cleared session — treat as unauthenticated
    }
    return null;
  }

  function saveSession(user) {
    const session = {
      id: user.id || ('demo-' + Math.random().toString(36).slice(2)),
      email: user.email,
      name: user.name,
      role: user.role,
      dashboard: user.dashboard,
      authenticatedAt: new Date().toISOString(),
      demoMode: true,
    };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    current = session;
    return session;
  }

  function clearSession() {
    sessionStorage.removeItem(STORAGE_KEY);
    current = null;
  }

  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  window.MockAuth = {
    /** Validate demo credentials locally and create a mock session. */
    async login(email, password) {
      if (!email || !password) {
        throw new Error('Please enter both email and password.');
      }
      const trimmed = String(email).trim();
      const account = DEMO_ACCOUNTS.find(
        a => a.email.toLowerCase() === trimmed.toLowerCase() && a.password === password
      );
      await delay(DELAY_MS);
      if (!account) {
        throw new Error('Invalid demo credentials.');
      }
      const user = {
        id: account.id || (account.email.split('@')[0] + '-demo-id'),
        email: account.email,
        name: account.name,
        role: account.role,
        dashboard: account.dashboard,
      };
      return saveSession(user);
    },

    /** Return the mock user object, or null when there is no valid session. */
    getCurrentUser() {
      if (current) return current;
      return loadSession();
    },

    /** True when a valid mock session exists. */
    isAuthenticated() {
      return !!this.getCurrentUser();
    },

    /** Role of the current mock user, or null. */
    getCurrentRole() {
      const user = this.getCurrentUser();
      return user ? user.role : null;
    },

    /** Clear the mock session so it cannot be reused. */
    async logout() {
      clearSession();
    },

    /** For demo documentation / debugging only. */
    getDemoAccounts() {
      return DEMO_ACCOUNTS.map(a => ({ email: a.email, role: a.role, dashboard: a.dashboard }));
    },
  };

  // Initialize current from any existing session on load
  current = loadSession();
})();
