const BASE_URL =
	process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ApiResponse<T> {
	data: T;
	message?: string;
}

interface ApiError {
	detail: string;
	status: number;
}

// ---- Auth types ----
interface LoginRequest {
	email: string;
	password: string;
	totp_code?: string;
}

interface AuthTokens {
	access_token: string;
	refresh_token: string;
	token_type: string;
}

interface User {
	id: string;
	email: string;
	created_at: string;
}

// ---- Finance types ----
interface Account {
	id: string;
	name: string;
	type: string;
	balance: number;
	institution: string;
	last_synced: string;
}

interface Transaction {
	id: string;
	account_id: string;
	date: string;
	description: string;
	amount: number;
	category: string;
	merchant: string;
}

interface SpendingTrend {
	date: string;
	amount: number;
}

interface Subscription {
	id: string;
	name: string;
	amount: number;
	frequency: string;
	next_charge: string;
}

interface FinanceSnapshot {
	total_balance: number;
	monthly_spending: number;
	spending_trend: SpendingTrend[];
	accounts: Account[];
}

// ---- Email types ----
interface EmailDigest {
	id: string;
	subject: string;
	sender: string;
	summary: string;
	priority: "high" | "medium" | "low";
	received_at: string;
	action_required: boolean;
}

// ---- Calendar types ----
interface CalendarEvent {
	id: string;
	title: string;
	start: string;
	end: string;
	location?: string;
	source: "google" | "outlook";
}

// ---- Contacts types ----
interface Contact {
	id: string;
	name: string;
	email?: string;
	phone?: string;
	relationship: string;
	last_contact: string;
	interaction_count: number;
}

interface ContactEdge {
	from: string;
	to: string;
	strength: number;
}

interface ContactGraph {
	nodes: Contact[];
	edges: ContactEdge[];
}

// ---- Social types ----
interface SocialPost {
	id: string;
	platform: "linkedin" | "x";
	content: string;
	posted_at: string;
	likes: number;
	comments: number;
	impressions: number;
}

// ---- Content types ----
interface ContentDraft {
	id: string;
	topic: string;
	platform: "linkedin" | "x";
	tone: string;
	content: string;
	status: "draft" | "scheduled" | "published";
	created_at: string;
	scheduled_for?: string;
}

interface GenerateContentRequest {
	topic: string;
	platform: "linkedin" | "x";
	tone: string;
}

interface EngagementMetrics {
	date: string;
	likes: number;
	comments: number;
	impressions: number;
}

// ---- Health types ----
interface HealthMetrics {
	date: string;
	steps: number;
	calories_consumed: number;
	calories_burned: number;
	protein_g: number;
	carbs_g: number;
	fat_g: number;
	sleep_hours: number;
	sleep_quality: number;
	heart_rate_avg: number;
}

interface HealthGoals {
	daily_protein_target_g: number;
	daily_calorie_limit: number;
	daily_step_goal: number;
	sleep_target_hours: number;
}

// ---- Productivity types ----
interface ProductivityMetrics {
	date: string;
	screen_time_minutes: number;
	productive_minutes: number;
	top_apps: { name: string; minutes: number }[];
	score: number;
}

// ---- Briefing types ----
interface DailyBriefing {
	date: string;
	summary: string;
	calendar_events: CalendarEvent[];
	finance_snapshot: FinanceSnapshot;
	email_highlights: EmailDigest[];
	health_summary: HealthMetrics;
	content_status: {
		posts_scheduled: number;
		posts_published_today: number;
	};
	action_items: string[];
}

// ---- Email extended types ----
interface EmailWeeklyReport {
	week_start: string;
	week_end: string;
	total_received: number;
	total_sent: number;
	top_senders: { sender: string; count: number }[];
	response_rate: number;
	avg_response_time_minutes: number;
}

interface SpamAuditItem {
	id: string;
	sender: string;
	subject: string;
	frequency: string;
	suggested_action: "unsubscribe" | "block" | "keep";
}

interface AssignmentReminder {
	id: string;
	title: string;
	course: string;
	platform: "canvas" | "blackboard" | "pearson";
	due_date: string;
	status: "upcoming" | "overdue" | "submitted";
}

// ---- Social extended types ----
interface QuickPostRequest {
	content: string;
	platforms: ("linkedin" | "x")[];
}

interface QuickPostResponse {
	posted: { platform: string; post_id: string }[];
}

interface NewsHeadline {
	id: string;
	title: string;
	source: string;
	url: string;
	published_at: string;
	summary: string;
}

// ---- Calendar extended types ----
interface MeetingTranscription {
	id: string;
	event_id: string;
	title: string;
	date: string;
	duration_minutes: number;
	summary: string;
	key_points: string[];
	action_items: string[];
}

// ---- Productivity extended types ----
interface ProductivityWeeklyReport {
	week_start: string;
	week_end: string;
	total_screen_time_minutes: number;
	total_productive_minutes: number;
	avg_score: number;
	most_used_apps: { name: string; minutes: number }[];
	trend: "improving" | "declining" | "stable";
	summary: string;
}

// ---- Security types ----
interface AuditLogEntry {
	id: string;
	timestamp: string;
	action: string;
	resource: string;
	ip_address: string;
	user_agent: string;
	status: "success" | "failure";
}

interface ActiveSession {
	id: string;
	ip_address: string;
	user_agent: string;
	created_at: string;
	last_active: string;
	is_current: boolean;
}

interface TwoFactorStatus {
	enabled: boolean;
	method: "totp" | "none";
	last_verified: string | null;
}

interface ChangePasswordRequest {
	current_password: string;
	new_password: string;
}

// ---- Export all types ----
export type {
	ApiResponse,
	ApiError,
	LoginRequest,
	AuthTokens,
	User,
	Account,
	Transaction,
	SpendingTrend,
	Subscription,
	FinanceSnapshot,
	EmailDigest,
	EmailWeeklyReport,
	SpamAuditItem,
	AssignmentReminder,
	CalendarEvent,
	MeetingTranscription,
	Contact,
	ContactEdge,
	ContactGraph,
	SocialPost,
	QuickPostRequest,
	QuickPostResponse,
	NewsHeadline,
	ContentDraft,
	GenerateContentRequest,
	EngagementMetrics,
	HealthMetrics,
	HealthGoals,
	ProductivityMetrics,
	ProductivityWeeklyReport,
	DailyBriefing,
	AuditLogEntry,
	ActiveSession,
	TwoFactorStatus,
	ChangePasswordRequest,
};

// ---- Token management ----
let getAccessToken: (() => string | null) | null = null;
let onTokenRefresh: ((tokens: AuthTokens) => void) | null = null;
let onAuthFailure: (() => void) | null = null;

export function configureAuth(config: {
	getToken: () => string | null;
	onRefresh: (tokens: AuthTokens) => void;
	onFailure: () => void;
}) {
	getAccessToken = config.getToken;
	onTokenRefresh = config.onRefresh;
	onAuthFailure = config.onFailure;
}

// ---- Core fetch wrapper ----
class ApiClientError extends Error {
	status: number;
	detail: string;

	constructor(status: number, detail: string) {
		super(detail);
		this.name = "ApiClientError";
		this.status = status;
		this.detail = detail;
	}
}

async function apiFetch<T>(
	path: string,
	options: RequestInit = {},
): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		...(options.headers as Record<string, string>),
	};

	const token = getAccessToken?.();
	if (token) {
		headers.Authorization = `Bearer ${token}`;
	}

	const response = await fetch(`${BASE_URL}${path}`, {
		...options,
		headers,
	});

	if (!response.ok) {
		if (response.status === 401) {
			onAuthFailure?.();
		}
		const errorBody = await response.json().catch(() => ({
			detail: response.statusText,
		}));
		throw new ApiClientError(
			response.status,
			(errorBody as { detail?: string }).detail ?? "Request failed",
		);
	}

	if (response.status === 204) {
		return undefined as T;
	}

	return response.json() as Promise<T>;
}

// ---- API methods ----
export const api = {
	// Auth
	auth: {
		login(body: LoginRequest) {
			return apiFetch<AuthTokens>("/api/v1/auth/login", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		refresh(refreshToken: string) {
			return apiFetch<AuthTokens>("/api/v1/auth/refresh", {
				method: "POST",
				body: JSON.stringify({ refresh_token: refreshToken }),
			});
		},
		me() {
			return apiFetch<User>("/api/v1/auth/me");
		},
	},

	// Finance
	finance: {
		getSnapshot() {
			return apiFetch<FinanceSnapshot>("/api/v1/finance/snapshot");
		},
		getAccounts() {
			return apiFetch<Account[]>("/api/v1/finance/accounts");
		},
		getTransactions(params?: { limit?: number; offset?: number }) {
			const query = new URLSearchParams();
			if (params?.limit) query.set("limit", String(params.limit));
			if (params?.offset) query.set("offset", String(params.offset));
			const qs = query.toString();
			return apiFetch<Transaction[]>(
				`/api/v1/finance/transactions${qs ? `?${qs}` : ""}`,
			);
		},
		getSpendingTrend(days?: number) {
			const qs = days ? `?days=${days}` : "";
			return apiFetch<SpendingTrend[]>(
				`/api/v1/finance/spending-trend${qs}`,
			);
		},
		getSubscriptions() {
			return apiFetch<Subscription[]>("/api/v1/finance/subscriptions");
		},
	},

	// Email
	email: {
		getDigests(params?: { limit?: number }) {
			const qs = params?.limit ? `?limit=${params.limit}` : "";
			return apiFetch<EmailDigest[]>(`/api/v1/email/digests${qs}`);
		},
		getWeeklyReport() {
			return apiFetch<EmailWeeklyReport>("/api/v1/email/weekly-report");
		},
		getSpamAudit() {
			return apiFetch<SpamAuditItem[]>("/api/v1/email/spam-audit");
		},
		getAssignmentReminders() {
			return apiFetch<AssignmentReminder[]>("/api/v1/email/assignment-reminders");
		},
	},

	// Calendar
	calendar: {
		getEvents(params?: { start?: string; end?: string }) {
			const query = new URLSearchParams();
			if (params?.start) query.set("start", params.start);
			if (params?.end) query.set("end", params.end);
			const qs = query.toString();
			return apiFetch<CalendarEvent[]>(
				`/api/v1/calendar/events${qs ? `?${qs}` : ""}`,
			);
		},
		getMeetingTranscriptions(params?: { limit?: number }) {
			const qs = params?.limit ? `?limit=${params.limit}` : "";
			return apiFetch<MeetingTranscription[]>(
				`/api/v1/calendar/transcriptions${qs}`,
			);
		},
	},

	// Contacts
	contacts: {
		getGraph() {
			return apiFetch<ContactGraph>("/api/v1/contacts/graph");
		},
		search(q: string) {
			return apiFetch<Contact[]>(
				`/api/v1/contacts/search?q=${encodeURIComponent(q)}`,
			);
		},
		getOutreachSuggestions() {
			return apiFetch<Contact[]>("/api/v1/contacts/outreach-suggestions");
		},
	},

	// Social
	social: {
		getPosts(params?: { platform?: string; limit?: number }) {
			const query = new URLSearchParams();
			if (params?.platform) query.set("platform", params.platform);
			if (params?.limit) query.set("limit", String(params.limit));
			const qs = query.toString();
			return apiFetch<SocialPost[]>(
				`/api/v1/social/posts${qs ? `?${qs}` : ""}`,
			);
		},
		quickPost(body: QuickPostRequest) {
			return apiFetch<QuickPostResponse>("/api/v1/social/quick-post", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		getEngagementMetrics(days?: number) {
			const qs = days ? `?days=${days}` : "";
			return apiFetch<EngagementMetrics[]>(
				`/api/v1/social/engagement${qs}`,
			);
		},
		getNewsHeadlines(params?: { limit?: number }) {
			const qs = params?.limit ? `?limit=${params.limit}` : "";
			return apiFetch<NewsHeadline[]>(`/api/v1/social/news${qs}`);
		},
	},

	// Content
	content: {
		generate(body: GenerateContentRequest) {
			return apiFetch<ContentDraft>("/api/v1/content/generate", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		getDrafts() {
			return apiFetch<ContentDraft[]>("/api/v1/content/drafts");
		},
		publishDraft(id: string) {
			return apiFetch<ContentDraft>(`/api/v1/content/drafts/${id}/publish`, {
				method: "POST",
			});
		},
		getHistory() {
			return apiFetch<ContentDraft[]>("/api/v1/content/history");
		},
		getEngagementMetrics(days?: number) {
			const qs = days ? `?days=${days}` : "";
			return apiFetch<EngagementMetrics[]>(
				`/api/v1/content/engagement${qs}`,
			);
		},
	},

	// Health
	health: {
		getMetrics(params?: { days?: number }) {
			const qs = params?.days ? `?days=${params.days}` : "";
			return apiFetch<HealthMetrics[]>(`/api/v1/health/metrics${qs}`);
		},
		getGoals() {
			return apiFetch<HealthGoals>("/api/v1/health/goals");
		},
		getLatest() {
			return apiFetch<HealthMetrics>("/api/v1/health/latest");
		},
	},

	// Productivity
	productivity: {
		getMetrics(params?: { days?: number }) {
			const qs = params?.days ? `?days=${params.days}` : "";
			return apiFetch<ProductivityMetrics[]>(
				`/api/v1/productivity/metrics${qs}`,
			);
		},
		getLatest() {
			return apiFetch<ProductivityMetrics>("/api/v1/productivity/latest");
		},
		getWeeklyReport() {
			return apiFetch<ProductivityWeeklyReport>(
				"/api/v1/productivity/weekly-report",
			);
		},
	},

	// Briefing
	briefing: {
		getToday() {
			return apiFetch<DailyBriefing>("/api/v1/briefing/today");
		},
		getByDate(date: string) {
			return apiFetch<DailyBriefing>(`/api/v1/briefing/${date}`);
		},
	},

	// Security
	security: {
		getAuditLog(params?: { limit?: number; offset?: number }) {
			const query = new URLSearchParams();
			if (params?.limit) query.set("limit", String(params.limit));
			if (params?.offset) query.set("offset", String(params.offset));
			const qs = query.toString();
			return apiFetch<AuditLogEntry[]>(
				`/api/v1/security/audit-log${qs ? `?${qs}` : ""}`,
			);
		},
		getActiveSessions() {
			return apiFetch<ActiveSession[]>("/api/v1/security/sessions");
		},
		revokeSession(id: string) {
			return apiFetch<void>(`/api/v1/security/sessions/${id}`, {
				method: "DELETE",
			});
		},
		getTwoFactorStatus() {
			return apiFetch<TwoFactorStatus>("/api/v1/security/2fa/status");
		},
		changePassword(body: ChangePasswordRequest) {
			return apiFetch<void>("/api/v1/security/change-password", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
	},
};
