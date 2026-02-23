import { useAuthStore } from "./store";

/**
 * ClawdBot API client for mobile.
 *
 * All requests go through the Cloudflare Tunnel to the backend FastAPI server.
 * JWT tokens are managed via the auth store and attached to every request.
 */

// In development, this should point to your local backend.
// In production, this is the Cloudflare Tunnel URL.
const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "https://api.clawdbot.local";

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: Record<string, unknown> | FormData;
  headers?: Record<string, string>;
  skipAuth?: boolean;
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface TranscriptResult {
  text: string;
  confidence: number;
}

interface VoiceQueryResult {
  text: string;
  audio_url: string | null;
}

interface DailyBriefing {
  summary: string;
  highlights: string[];
  generated_at: string;
}

interface FinancialSnapshot {
  total_balance: number;
  monthly_spend: number;
  monthly_budget: number;
  recent_transactions: Array<{
    description: string;
    amount: number;
    date: string;
  }>;
}

interface CalendarEvent {
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
}

interface HealthMetrics {
  calories: number | null;
  protein_g: number | null;
  steps: number | null;
  sleep_hours: number | null;
  heart_rate_avg: number | null;
  date: string;
}

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const store = useAuthStore.getState();
  const refreshToken = store.refreshToken;

  if (!refreshToken) {
    store.logout();
    return null;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      store.logout();
      return null;
    }

    const data: TokenPair = await response.json();
    store.setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    store.logout();
    return null;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {}, skipAuth = false } = options;

  const store = useAuthStore.getState();
  let accessToken = store.accessToken;

  const requestHeaders: Record<string, string> = {
    ...headers,
  };

  if (!skipAuth && accessToken) {
    requestHeaders["Authorization"] = `Bearer ${accessToken}`;
  }

  if (body && !(body instanceof FormData)) {
    requestHeaders["Content-Type"] = "application/json";
  }

  const fetchOptions: RequestInit = {
    method,
    headers: requestHeaders,
  };

  if (body) {
    fetchOptions.body = body instanceof FormData ? body : JSON.stringify(body);
  }

  let response = await fetch(`${API_BASE_URL}${path}`, fetchOptions);

  // If we get a 401, try refreshing the token once
  if (response.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      requestHeaders["Authorization"] = `Bearer ${newToken}`;
      fetchOptions.headers = requestHeaders;
      response = await fetch(`${API_BASE_URL}${path}`, fetchOptions);
    }
  }

  if (!response.ok) {
    const errorBody = await response.text();
    throw new ApiError(response.status, errorBody);
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  // --- Auth ---
  async login(email: string, password: string): Promise<TokenPair> {
    return request<TokenPair>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password },
      skipAuth: true,
    });
  },

  // --- Daily Briefing ---
  async getDailyBriefing(): Promise<DailyBriefing> {
    return request<DailyBriefing>("/api/v1/insights/daily-briefing");
  },

  // --- Finance ---
  async getFinanceSnapshot(): Promise<FinancialSnapshot> {
    return request<FinancialSnapshot>("/api/v1/finance/snapshot");
  },

  // --- Calendar ---
  async getTodayEvents(): Promise<CalendarEvent[]> {
    return request<CalendarEvent[]>("/api/v1/calendar/today");
  },

  // --- Health ---
  async getHealthMetrics(): Promise<HealthMetrics> {
    return request<HealthMetrics>("/api/v1/health/today");
  },

  // --- Voice ---
  async transcribeAudio(audioUri: string): Promise<TranscriptResult> {
    const formData = new FormData();
    formData.append("audio", {
      uri: audioUri,
      type: "audio/m4a",
      name: "recording.m4a",
    } as unknown as Blob);

    return request<TranscriptResult>("/api/v1/voice/transcribe", {
      method: "POST",
      body: formData,
    });
  },

  async processVoiceQuery(text: string): Promise<VoiceQueryResult> {
    return request<VoiceQueryResult>("/api/v1/voice/query", {
      method: "POST",
      body: { text },
    });
  },

  // --- Content ---
  async getContentQueue(): Promise<
    Array<{
      id: string;
      platform: string;
      content: string;
      scheduled_at: string;
      status: string;
    }>
  > {
    return request("/api/v1/content/queue");
  },

  // --- Productivity ---
  async getProductivitySummary(): Promise<{
    screen_time_minutes: number;
    productive_minutes: number;
    top_apps: Array<{ name: string; minutes: number }>;
  }> {
    return request("/api/v1/productivity/today");
  },
};

export { ApiError };
export type {
  TokenPair,
  TranscriptResult,
  VoiceQueryResult,
  DailyBriefing,
  FinancialSnapshot,
  CalendarEvent,
  HealthMetrics,
};
