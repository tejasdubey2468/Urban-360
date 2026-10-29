/**
 * RAKSHA-FORCE — Shared frontend client
 * Uses Supabase for auth/session/realtime and backend APIs for writes.
 */
(function () {
  const URL = "https://zjkaoyvztgzdwofgqjjh.supabase.co";
  const KEY = "sb_publishable_QMDzSanJPFXdn-j_r73uww_EbI0rIAo";
  const API_BASE = window.RAKSHA_API_BASE || "";

  let _client = null;

  function sb() {
    if (!_client) {
      _client = window.supabase.createClient(URL, KEY, { auth: { persistSession: true } });
    }
    return _client;
  }

  async function getAccessToken() {
    const { data } = await sb().auth.getSession();
    return data.session?.access_token || null;
  }

  async function api(path, options = {}) {
    const { auth = false, json, headers = {}, ...rest } = options;
    const finalHeaders = { ...headers };

    if (json !== undefined) {
      finalHeaders["Content-Type"] = "application/json";
    }

    if (auth) {
      const token = await getAccessToken();
      if (token) {
        finalHeaders.Authorization = `Bearer ${token}`;
      }
    }

    const baseUrl = (API_BASE || "").replace(/\/$/, "");
    const normalizedPath = path.startsWith("/") ? path : `/${path}`;
    const url = `${baseUrl}${normalizedPath}`;

    const response = await fetch(url, {
      ...rest,
      headers: finalHeaders,
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch (_) {
      payload = null;
    }

    if (!response.ok) {
      throw new Error(payload?.detail || payload?.error || `Request failed (${response.status})`);
    }

    return payload;
  }

  async function login(email, password) {
    const data = await api("/api/auth/login", {
      method: "POST",
      json: { email, password },
    });

    await sb().auth.setSession({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    });

    return data;
  }

  async function register(payload) {
    const body = {
      email: payload.email,
      password: payload.password,
      full_name: payload.full_name,
      phone: payload.phone || "",
      role: payload.role || "citizen",
    };
    const headers = {};

    if (payload.admin_secret) {
      headers["X-Admin-Secret"] = payload.admin_secret;
    }

    await api("/api/auth/register", {
      method: "POST",
      json: body,
      headers,
    });

    return login(payload.email, payload.password);
  }

  async function logout() {
    try {
      await api("/api/auth/logout", { method: "POST", auth: true });
    } catch (_) {}
    return sb().auth.signOut();
  }

  window.RF = {
    client: () => sb(),
    api,
    login,
    register,
    logout,

    // Compatibility helpers
    signIn: (email, password) => sb().auth.signInWithPassword({ email, password }),
    signUp: (email, password, meta) => sb().auth.signUp({ email, password, options: { data: meta } }),
    signOut: () => sb().auth.signOut(),
    getSession: () => sb().auth.getSession(),

    // Backend-backed writes (optional_auth on backend — works without JWT for demo)
    createIncident: (data) => api("/api/incidents", { method: "POST", json: data }),
    createSOS: (data) => api("/api/sos", { method: "POST", json: data, auth: true }),
    registerVolunteer: (data) => api("/api/volunteers", { method: "POST", json: data }),

    // Image upload via FastAPI backend to Supabase Storage (incident-images bucket)
    uploadImage: async (file) => {
      if (!file) throw new Error('No file selected.');
      if (typeof file === 'string' && (file.startsWith('http://') || file.startsWith('https://'))) {
        return file;
      }
      const MAX_SIZE = 5 * 1024 * 1024; // 5MB
      const ALLOWED = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp'];

      if (file.size && file.size > MAX_SIZE) {
        throw new Error('Image must be under 5 MB.');
      }
      if (file.type && !ALLOWED.includes(file.type.toLowerCase())) {
        throw new Error('Only JPG, PNG, WebP images are allowed.');
      }

      const baseUrl = (API_BASE || "").replace(/\/$/, "");
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${baseUrl}/api/incidents/upload`, {
        method: 'POST',
        body: formData,
      });

      let payload = null;
      try {
        payload = await response.json();
      } catch (_) {}

      if (!response.ok) {
        throw new Error(payload?.detail || payload?.error || `Image upload failed (${response.status})`);
      }

      if (!payload?.url) {
        throw new Error('Server did not return a valid image URL.');
      }

      return payload.url;
    },
    saveGPS: ({ lat, lng, context, accuracy }) =>
      api("/api/gps", {
        method: "POST",
        auth: true,
        json: {
          latitude: lat,
          longitude: lng,
          page_context: context || "unknown",
          accuracy: accuracy || null,
        },
      }),
    upsertGPSLocation: ({ latitude, longitude, page_context, accuracy }) =>
      api("/api/gps", {
        method: "POST",
        auth: true,
        json: {
          latitude,
          longitude,
          page_context: page_context || "unknown",
          accuracy: accuracy || null,
        },
      }),

    // Backend-backed incident reads & status updates.
    // Handles both real JWT and demo users, always returning array of incident records.
    listIncidentsAPI: async (filters = {}) => {
      const params = new URLSearchParams();
      if (filters.status) params.append("status", filters.status);
      if (filters.type) params.append("type", filters.type);
      if (filters.priority) params.append("priority", filters.priority);
      if (filters.userId) params.append("userId", filters.userId);
      if (filters.reporterName) params.append("reporter_name", filters.reporterName);
      if (filters.limit) params.append("limit", filters.limit);
      if (filters.my) params.append("my", filters.my);
      const res = await api(`/api/incidents?${params.toString()}`, { method: "GET", auth: true });
      if (Array.isArray(res)) return res;
      if (Array.isArray(res?.incidents)) return res.incidents;
      return [];
    },
    getIncidentAPI: (id) => api(`/api/incidents/${id}`, { method: "GET", auth: true }),
    updateIncidentStatusAPI: (id, patch) =>
      api(`/api/incidents/${id}`, { method: "PATCH", json: patch, auth: true }),

    // Reads and realtime stay on Supabase for speed (demo-safe, no JWT required).
    fetchIncidents: (filters = {}) => {
      let q = sb().from("incident_reports").select("*").order("priority").order("created_at", { ascending: false }).limit(filters.limit || 50);
      if (filters.status) q = q.eq("status", filters.status);
      if (filters.type) q = q.eq("emergency_type", filters.type);
      if (filters.priority) q = q.eq("priority", filters.priority);
      if (filters.userId) q = q.eq("user_id", filters.userId);
      return q;
    },
    updateIncident: (id, patch) => sb().from("incident_reports").update({ ...patch, updated_at: new Date().toISOString() }).eq("id", id),
    fetchTeams: () => sb().from("teams").select("*").order("name"),
    updateTeam: (id, patch) => sb().from("teams").update(patch).eq("id", id),
    fetchResources: () => sb().from("resources").select("*").order("name"),
    fetchAlerts: (active = true) => {
      let q = sb().from("area_alerts").select("*").order("created_at", { ascending: false });
      if (active) q = q.eq("active", true);
      return q;
    },
    createAlert: (data) => sb().from("area_alerts").insert([{ ...data, active: true }]).select().single(),
    fetchMessages: (incidentId) => sb().from("incident_messages").select("*").eq("incident_id", incidentId).order("created_at"),
    sendMessage: (data) => sb().from("incident_messages").insert([data]),
    upsertProfile: (data) => sb().from("profiles").upsert(data),
    subscribeIncidents: (cb) =>
      sb().channel("rt-incidents").on("postgres_changes", { event: "*", schema: "public", table: "incident_reports" }, cb).subscribe(),
    subscribeSOS: (cb) =>
      sb().channel("rt-sos").on("postgres_changes", { event: "INSERT", schema: "public", table: "sos_alerts" }, cb).subscribe(),
    subscribeMessages: (incidentId, cb) =>
      sb().channel(`rt-msgs-${incidentId}`).on("postgres_changes", { event: "INSERT", schema: "public", table: "incident_messages", filter: `incident_id=eq.${incidentId}` }, cb).subscribe(),
    unsubscribe: (channel) => sb().removeChannel(channel),
  };
})();
