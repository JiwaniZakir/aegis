"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
	EmailDigest,
	EmailWeeklyReport,
	SpamAuditItem,
	AssignmentReminder,
} from "@/lib/api";
import {
	Mail,
	BarChart3,
	ShieldAlert,
	BookOpen,
	AlertTriangle,
	Clock,
	CheckCircle2,
	XCircle,
	ArrowUpCircle,
} from "lucide-react";

// ---- Skeleton ----
function SkeletonBlock({ className }: { className?: string }) {
	return (
		<div
			className={`animate-pulse rounded-lg border border-neutral-800 bg-neutral-900 p-5 ${className ?? ""}`}
		>
			<div className="h-5 w-40 rounded bg-neutral-800" />
			<div className="mt-4 h-48 rounded bg-neutral-800" />
		</div>
	);
}

// ---- Priority badge ----
function PriorityBadge({ priority }: { priority: EmailDigest["priority"] }) {
	const colors: Record<string, string> = {
		high: "bg-red-900/50 text-red-400",
		medium: "bg-yellow-900/50 text-yellow-400",
		low: "bg-neutral-800 text-neutral-400",
	};
	return (
		<span
			className={`rounded px-2 py-0.5 text-xs ${colors[priority] ?? colors.low}`}
		>
			{priority}
		</span>
	);
}

// ---- Email digest section ----
function DigestSection({ digests }: { digests: EmailDigest[] }) {
	const grouped = {
		high: digests.filter((d) => d.priority === "high"),
		medium: digests.filter((d) => d.priority === "medium"),
		low: digests.filter((d) => d.priority === "low"),
	};

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Mail className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Today&apos;s Email Digest
				</h2>
				<span className="ml-auto rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
					{digests.length} emails
				</span>
			</div>
			{digests.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No emails to show yet.
				</p>
			) : (
				<div className="space-y-4">
					{(["high", "medium", "low"] as const).map((priority) => {
						const items = grouped[priority];
						if (items.length === 0) return null;
						return (
							<div key={priority}>
								<p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
									{priority} Priority ({items.length})
								</p>
								<div className="space-y-2">
									{items.map((email) => (
										<div
											key={email.id}
											className="rounded-md border border-neutral-800 px-3 py-2.5"
										>
											<div className="flex items-start justify-between gap-3">
												<div className="min-w-0 flex-1">
													<div className="flex items-center gap-2">
														<p className="truncate text-sm font-medium text-neutral-200">
															{email.subject}
														</p>
														{email.action_required && (
															<span className="shrink-0 rounded bg-indigo-900/50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-400">
																Action Required
															</span>
														)}
													</div>
													<p className="mt-0.5 text-xs text-neutral-500">
														{email.sender}
													</p>
													<p className="mt-1 line-clamp-2 text-sm text-neutral-400">
														{email.summary}
													</p>
												</div>
												<div className="flex shrink-0 flex-col items-end gap-1">
													<PriorityBadge priority={email.priority} />
													<span className="text-[10px] text-neutral-600">
														{new Date(email.received_at).toLocaleTimeString([], {
															hour: "2-digit",
															minute: "2-digit",
														})}
													</span>
												</div>
											</div>
										</div>
									))}
								</div>
							</div>
						);
					})}
				</div>
			)}
		</div>
	);
}

// ---- Weekly report section ----
function WeeklyReportSection({ report }: { report: EmailWeeklyReport }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<BarChart3 className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Weekly Email Report
				</h2>
			</div>
			<p className="mb-4 text-xs text-neutral-500">
				{new Date(report.week_start).toLocaleDateString()} &mdash;{" "}
				{new Date(report.week_end).toLocaleDateString()}
			</p>

			{/* Stats grid */}
			<div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
				<div className="rounded-md border border-neutral-800 px-3 py-2.5 text-center">
					<p className="text-2xl font-bold text-neutral-50">
						{report.total_received}
					</p>
					<p className="text-xs text-neutral-500">Received</p>
				</div>
				<div className="rounded-md border border-neutral-800 px-3 py-2.5 text-center">
					<p className="text-2xl font-bold text-neutral-50">
						{report.total_sent}
					</p>
					<p className="text-xs text-neutral-500">Sent</p>
				</div>
				<div className="rounded-md border border-neutral-800 px-3 py-2.5 text-center">
					<p className="text-2xl font-bold text-neutral-50">
						{report.response_rate}%
					</p>
					<p className="text-xs text-neutral-500">Response Rate</p>
				</div>
				<div className="rounded-md border border-neutral-800 px-3 py-2.5 text-center">
					<p className="text-2xl font-bold text-neutral-50">
						{report.avg_response_time_minutes}m
					</p>
					<p className="text-xs text-neutral-500">Avg Response</p>
				</div>
			</div>

			{/* Top senders */}
			{report.top_senders.length > 0 && (
				<div>
					<p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
						Top Senders
					</p>
					<div className="space-y-1.5">
						{report.top_senders.map((s) => (
							<div
								key={s.sender}
								className="flex items-center justify-between text-sm"
							>
								<span className="truncate text-neutral-300">
									{s.sender}
								</span>
								<span className="shrink-0 text-neutral-500">
									{s.count} emails
								</span>
							</div>
						))}
					</div>
				</div>
			)}
		</div>
	);
}

// ---- Spam audit section ----
function SpamAuditSection({ items }: { items: SpamAuditItem[] }) {
	const actionColors: Record<string, string> = {
		unsubscribe: "bg-yellow-900/50 text-yellow-400",
		block: "bg-red-900/50 text-red-400",
		keep: "bg-emerald-900/50 text-emerald-400",
	};

	const actionIcons: Record<string, React.ReactNode> = {
		unsubscribe: <XCircle className="h-3.5 w-3.5" />,
		block: <ShieldAlert className="h-3.5 w-3.5" />,
		keep: <CheckCircle2 className="h-3.5 w-3.5" />,
	};

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<ShieldAlert className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Spam Audit & Unsubscribe Suggestions
				</h2>
			</div>
			{items.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					Inbox looks clean. No spam suggestions.
				</p>
			) : (
				<div className="space-y-2">
					{items.map((item) => (
						<div
							key={item.id}
							className="flex items-center justify-between rounded-md border border-neutral-800 px-3 py-2.5"
						>
							<div className="min-w-0 flex-1">
								<p className="truncate text-sm font-medium text-neutral-200">
									{item.subject}
								</p>
								<p className="text-xs text-neutral-500">
									{item.sender} &middot; {item.frequency}
								</p>
							</div>
							<span
								className={`flex shrink-0 items-center gap-1 rounded px-2 py-0.5 text-xs ${actionColors[item.suggested_action] ?? "bg-neutral-800 text-neutral-400"}`}
							>
								{actionIcons[item.suggested_action]}
								{item.suggested_action}
							</span>
						</div>
					))}
				</div>
			)}
		</div>
	);
}

// ---- Assignment reminders section ----
function AssignmentRemindersSection({
	reminders,
}: { reminders: AssignmentReminder[] }) {
	const upcoming = reminders.filter((r) => r.status === "upcoming");
	const overdue = reminders.filter((r) => r.status === "overdue");
	const submitted = reminders.filter((r) => r.status === "submitted");

	const statusColors: Record<string, string> = {
		upcoming: "bg-blue-900/50 text-blue-400",
		overdue: "bg-red-900/50 text-red-400",
		submitted: "bg-emerald-900/50 text-emerald-400",
	};

	const statusIcons: Record<string, React.ReactNode> = {
		upcoming: <Clock className="h-3.5 w-3.5" />,
		overdue: <AlertTriangle className="h-3.5 w-3.5" />,
		submitted: <CheckCircle2 className="h-3.5 w-3.5" />,
	};

	const platformColors: Record<string, string> = {
		canvas: "bg-orange-900/50 text-orange-400",
		blackboard: "bg-purple-900/50 text-purple-400",
		pearson: "bg-cyan-900/50 text-cyan-400",
	};

	const renderGroup = (label: string, items: AssignmentReminder[]) => {
		if (items.length === 0) return null;
		return (
			<div>
				<p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
					{label} ({items.length})
				</p>
				<div className="space-y-2">
					{items.map((item) => (
						<div
							key={item.id}
							className="flex items-center justify-between rounded-md border border-neutral-800 px-3 py-2.5"
						>
							<div className="min-w-0 flex-1">
								<div className="flex items-center gap-2">
									<p className="truncate text-sm font-medium text-neutral-200">
										{item.title}
									</p>
									<span
										className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] ${platformColors[item.platform] ?? "bg-neutral-800 text-neutral-400"}`}
									>
										{item.platform}
									</span>
								</div>
								<p className="mt-0.5 text-xs text-neutral-500">
									{item.course} &middot; Due{" "}
									{new Date(item.due_date).toLocaleDateString([], {
										month: "short",
										day: "numeric",
										hour: "2-digit",
										minute: "2-digit",
									})}
								</p>
							</div>
							<span
								className={`flex shrink-0 items-center gap-1 rounded px-2 py-0.5 text-xs ${statusColors[item.status]}`}
							>
								{statusIcons[item.status]}
								{item.status}
							</span>
						</div>
					))}
				</div>
			</div>
		);
	};

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<BookOpen className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Assignment Reminders
				</h2>
			</div>
			{reminders.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No upcoming assignments.
				</p>
			) : (
				<div className="space-y-4">
					{renderGroup("Overdue", overdue)}
					{renderGroup("Upcoming", upcoming)}
					{renderGroup("Submitted", submitted)}
				</div>
			)}
		</div>
	);
}

// ---- Main page ----
export default function EmailPage() {
	const digestsQuery = useQuery({
		queryKey: ["email", "digests"],
		queryFn: () => api.email.getDigests({ limit: 50 }),
	});

	const weeklyQuery = useQuery({
		queryKey: ["email", "weekly-report"],
		queryFn: () => api.email.getWeeklyReport(),
	});

	const spamQuery = useQuery({
		queryKey: ["email", "spam-audit"],
		queryFn: () => api.email.getSpamAudit(),
	});

	const assignmentsQuery = useQuery({
		queryKey: ["email", "assignments"],
		queryFn: () => api.email.getAssignmentReminders(),
	});

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<Mail className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">Email</h1>
			</div>

			{/* Email digest */}
			{digestsQuery.isLoading ? (
				<SkeletonBlock />
			) : (
				<DigestSection digests={digestsQuery.data ?? []} />
			)}

			{/* Weekly report */}
			{weeklyQuery.isLoading ? (
				<SkeletonBlock />
			) : weeklyQuery.data ? (
				<WeeklyReportSection report={weeklyQuery.data} />
			) : null}

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Spam audit */}
				{spamQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<SpamAuditSection items={spamQuery.data ?? []} />
				)}

				{/* Assignment reminders */}
				{assignmentsQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<AssignmentRemindersSection
						reminders={assignmentsQuery.data ?? []}
					/>
				)}
			</div>
		</div>
	);
}
