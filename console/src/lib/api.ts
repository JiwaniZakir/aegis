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
	expires_in: number;
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

interface BalancesResponse {
	accounts: { name: string; type: string; balance: number; institution: string }[];
	total_balance: number;
	last_synced: string;
}

interface TransactionsResponse {
	transactions: {
		id: string;
		date: string;
		description: string;
		amount: number;
		category: string;
		merchant: string | null;
		account_name: string;
	}[];
	count: number;
	limit: number;
	offset: number;
}

interface SubscriptionsResponse {
	recurring: {
		description: string;
		amount: number;
		frequency: string;
		next_date: string;
		category: string;
	}[];
	total_monthly: number;
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
	finance_snapshot: {
		total_balance: number;
		monthly_spending: number;
	};
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
	BalancesResponse,
	TransactionsResponse,
	SubscriptionsResponse,
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

export { ApiClientError };

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
// All paths match the actual backend router definitions.
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
		logout(refreshToken?: string) {
			return apiFetch<void>("/api/v1/auth/logout", {
				method: "POST",
				body: JSON.stringify({ refresh_token: refreshToken ?? null }),
			});
		},
		me() {
			return apiFetch<User>("/api/v1/auth/me");
		},
	},

	// Finance — matches backend/app/api/v1/finance.py
	finance: {
		getBalances() {
			return apiFetch<BalancesResponse>("/api/v1/finance/balances");
		},
		getTransactions(params?: { limit?: number; offset?: number }) {
			const query = new URLSearchParams();
			if (params?.limit) query.set("limit", String(params.limit));
			if (params?.offset) query.set("offset", String(params.offset));
			const qs = query.toString();
			return apiFetch<TransactionsResponse>(
				`/api/v1/finance/transactions${qs ? `?${qs}` : ""}`,
			);
		},
		getSubscriptions() {
			return apiFetch<SubscriptionsResponse>("/api/v1/finance/subscriptions");
		},
		getPortfolio() {
			return apiFetch<{ holdings: object[]; total_value: number }>(
				"/api/v1/finance/portfolio",
			);
		},
		getPortfolioBrief() {
			return apiFetch<{ total_value: number; top_holdings: object[]; daily_change_pct: number }>(
				"/api/v1/finance/portfolio/brief",
			);
		},
		checkAffordability(body: { item: string; estimated_cost: number }) {
			return apiFetch<{ affordable: boolean; analysis: string }>(
				"/api/v1/finance/affordability",
				{ method: "POST", body: JSON.stringify(body) },
			);
		},
	},

	// Email — matches backend/app/api/v1/email.py
	email: {
		getDigest() {
			return apiFetch<{ emails: EmailDigest[]; generated_at: string }>(
				"/api/v1/email/digest",
			);
		},
		getWeeklyReport() {
			return apiFetch<EmailWeeklyReport>("/api/v1/email/weekly");
		},
		getSpamAudit() {
			return apiFetch<SpamAuditItem[]>("/api/v1/email/spam-audit");
		},
		getAssignmentReminders() {
			return apiFetch<AssignmentReminder[]>("/api/v1/assignments/reminders");
		},
		getUpcomingAssignments() {
			return apiFetch<object[]>("/api/v1/assignments/upcoming");
		},
		getOverdueAssignments() {
			return apiFetch<object[]>("/api/v1/assignments/overdue");
		},
	},

	// Calendar — matches backend/app/api/v1/calendar.py
	calendar: {
		getTodayEvents() {
			return apiFetch<CalendarEvent[]>("/api/v1/calendar/today");
		},
		getEvents(params?: { days?: number }) {
			const qs = params?.days ? `?days=${params.days}` : "";
			return apiFetch<{ events: CalendarEvent[]; count: number; days: number }>(
				`/api/v1/calendar/events${qs}`,
			);
		},
		getMeetingSummary(meetingId: string) {
			return apiFetch<MeetingTranscription>(
				`/api/v1/meetings/${meetingId}/summary`,
			);
		},
	},

	// Contacts — matches backend/app/api/v1/calendar.py (contacts are in calendar router)
	contacts: {
		getGraph(centerId: string, depth?: number) {
			const query = new URLSearchParams({ center_id: centerId });
			if (depth) query.set("depth", String(depth));
			return apiFetch<ContactGraph>(
				`/api/v1/contacts/graph?${query.toString()}`,
			);
		},
		getSuggestOutreach(limit?: number) {
			const qs = limit ? `?limit=${limit}` : "";
			return apiFetch<Contact[]>(`/api/v1/contacts/suggest-outreach${qs}`);
		},
		create(body: { name: string; source: string; email?: string; phone?: string }) {
			return apiFetch<Contact>("/api/v1/contacts", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		getShortestPath(fromId: string, toId: string) {
			return apiFetch<{ path: object[]; hops: number }>(
				`/api/v1/contacts/shortest-path?from_id=${encodeURIComponent(fromId)}&to_id=${encodeURIComponent(toId)}`,
			);
		},
	},

	// Social — matches backend/app/api/v1/social.py
	social: {
		post(body: { content: string; platforms: string[] }) {
			return apiFetch<{ results: object[] }>("/api/v1/social/post", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		postLinkedIn(body: { content: string }) {
			return apiFetch<object>("/api/v1/social/linkedin", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		postX(body: { content: string }) {
			return apiFetch<object>("/api/v1/social/x", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		getHistory(params?: { platform?: string; limit?: number }) {
			const query = new URLSearchParams();
			if (params?.platform) query.set("platform", params.platform);
			if (params?.limit) query.set("limit", String(params.limit));
			const qs = query.toString();
			return apiFetch<SocialPost[]>(
				`/api/v1/social/history${qs ? `?${qs}` : ""}`,
			);
		},
		getEngagement(days?: number) {
			const qs = days ? `?days=${days}` : "";
			return apiFetch<EngagementMetrics>(`/api/v1/social/engagement${qs}`);
		},
		getNewsHeadlines(params?: { limit?: number }) {
			const qs = params?.limit ? `?limit=${params.limit}` : "";
			return apiFetch<NewsHeadline[]>(`/api/v1/news/headlines${qs}`);
		},
		searchNews(q: string) {
			return apiFetch<NewsHeadline[]>(
				`/api/v1/news/search?q=${encodeURIComponent(q)}`,
			);
		},
	},

	// Content — matches backend/app/api/v1/content.py
	content: {
		generate(body: GenerateContentRequest) {
			return apiFetch<ContentDraft>("/api/v1/content/generate", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		getDrafts(platform?: string) {
			const qs = platform ? `?platform=${platform}` : "";
			return apiFetch<ContentDraft[]>(`/api/v1/content/drafts${qs}`);
		},
		publishDraft(postId: string) {
			return apiFetch<ContentDraft>("/api/v1/content/publish", {
				method: "POST",
				body: JSON.stringify({ post_id: postId }),
			});
		},
		ingest(body: { text: string; source?: string; title?: string }) {
			return apiFetch<{ id: string; chunks: number }>("/api/v1/content/ingest", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
	},

	// Health — matches backend/app/api/v1/health.py (prefix: /health-data/)
	health: {
		getSummary() {
			return apiFetch<HealthMetrics>("/api/v1/health-data/summary");
		},
		getTrends(params?: { days?: number }) {
			const qs = params?.days ? `?days=${params.days}` : "";
			return apiFetch<{ trends: HealthMetrics[]; days: number }>(
				`/api/v1/health-data/trends${qs}`,
			);
		},
		getGoals() {
			return apiFetch<HealthGoals>("/api/v1/health-data/goals");
		},
		getWeekly() {
			return apiFetch<object>("/api/v1/health-data/weekly");
		},
		getMacros() {
			return apiFetch<object>("/api/v1/health-data/macros");
		},
		getRecommendations() {
			return apiFetch<object>("/api/v1/health-data/recommendations");
		},
		ingestAppleHealth(body: object) {
			return apiFetch<object>("/api/v1/health-data/apple", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
		generateGroceryList(body: object) {
			return apiFetch<object>("/api/v1/health-data/grocery-list", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
	},

	// Productivity — matches backend/app/api/v1/health.py (productivity section)
	productivity: {
		getSummary() {
			return apiFetch<ProductivityMetrics>("/api/v1/productivity/summary");
		},
		getDaily() {
			return apiFetch<ProductivityMetrics>("/api/v1/productivity/daily");
		},
		getTrends() {
			return apiFetch<ProductivityMetrics[]>("/api/v1/productivity/trends");
		},
		getWeekly() {
			return apiFetch<ProductivityWeeklyReport>("/api/v1/productivity/weekly");
		},
		getAppUsage() {
			return apiFetch<{ name: string; minutes: number }[]>(
				"/api/v1/productivity/app-usage",
			);
		},
		ingestScreenTime(body: object) {
			return apiFetch<object>("/api/v1/productivity/screen-time", {
				method: "POST",
				body: JSON.stringify(body),
			});
		},
	},

	// Briefing — matches backend/app/api/v1/calendar.py (briefing section)
	briefing: {
		getToday() {
			return apiFetch<DailyBriefing>("/api/v1/briefing/today");
		},
	},

	// Security — matches backend/app/api/v1/security.py (new router)
	security: {
		getAuditLog(params?: { limit?: number; offset?: number }) {
			const query = new URLSearchParams();
			if (params?.limit) query.set("limit", String(params.limit));
			if (params?.offset) query.set("offset", String(params.offset));
			const qs = query.toString();
			return apiFetch<{ entries: AuditLogEntry[]; total: number }>(
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
		getFailedLogins(params?: { limit?: number }) {
			const qs = params?.limit ? `?limit=${params.limit}` : "";
			return apiFetch<AuditLogEntry[]>(
				`/api/v1/security/failed-logins${qs}`,
			);
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
