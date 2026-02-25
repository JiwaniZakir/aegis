"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { EmailDigest, SpamAuditItem, AssignmentReminder } from "@/lib/api";
import { Mail, BarChart3, ShieldAlert, BookOpen, AlertTriangle, Clock, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { MetricCardSkeleton, TableSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";

export default function EmailPage() {
	const digestQuery = useQuery({
		queryKey: ["email", "digest"],
		queryFn: () => api.email.getDigest(),
	});

	const weeklyQuery = useQuery({
		queryKey: ["email", "weekly"],
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

	const digest = digestQuery.data;
	const weekly = weeklyQuery.data;
	const emails = (digest as { emails?: EmailDigest[] } | undefined)?.emails ?? (Array.isArray(digest) ? digest : []) as EmailDigest[];
	const highPriority = emails.filter((e) => e.priority === "high");
	const mediumPriority = emails.filter((e) => e.priority === "medium");
	const lowPriority = emails.filter((e) => e.priority === "low");

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Email" description="Digests, reports, and assignments" />

			{/* Metric cards */}
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{weeklyQuery.isLoading ? (
					<>
						<MetricCardSkeleton />
						<MetricCardSkeleton />
						<MetricCardSkeleton />
						<MetricCardSkeleton />
					</>
				) : weeklyQuery.isError ? (
					<div className="sm:col-span-2 lg:col-span-4">
						<QueryError message="Failed to load email weekly report." onRetry={() => weeklyQuery.refetch()} />
					</div>
				) : weekly ? (
					<>
						<MetricCard label="Received" value={String(weekly.total_received)} icon={Mail} />
						<MetricCard label="Sent" value={String(weekly.total_sent)} icon={Mail} />
						<MetricCard label="Response Rate" value={`${weekly.response_rate}%`} icon={BarChart3} />
						<MetricCard label="Avg Response" value={`${weekly.avg_response_time_minutes}m`} icon={Clock} />
					</>
				) : (
					<>
						<MetricCard label="Received" value="--" icon={Mail} />
						<MetricCard label="Sent" value="--" icon={Mail} />
						<MetricCard label="Response Rate" value="--" icon={BarChart3} />
						<MetricCard label="Avg Response" value="--" icon={Clock} />
					</>
				)}
			</div>

			{/* Email Digest */}
			{digestQuery.isLoading ? (
				<TableSkeleton rows={5} />
			) : digestQuery.isError ? (
				<QueryError message="Failed to load email digest." onRetry={() => digestQuery.refetch()} />
			) : (
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2 text-base">
							<Mail className="h-4 w-4 text-muted-foreground" />
							Today&apos;s Email Digest
							<Badge variant="secondary" className="ml-auto">{emails.length} emails</Badge>
						</CardTitle>
					</CardHeader>
					<CardContent>
						{emails.length === 0 ? (
							<p className="py-4 text-center text-sm text-muted-foreground">No emails to show yet.</p>
						) : (
							<div className="space-y-4">
								{([
									{ label: "High Priority", items: highPriority },
									{ label: "Medium Priority", items: mediumPriority },
									{ label: "Low Priority", items: lowPriority },
								] as const).map(({ label, items }) => {
									if (items.length === 0) return null;
									return (
										<div key={label}>
											<p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
												{label} ({items.length})
											</p>
											<div className="space-y-2">
												{items.map((email) => (
													<div key={email.id} className="rounded-lg border p-3 transition-colors hover:bg-muted/50">
														<div className="flex items-start justify-between gap-3">
															<div className="min-w-0 flex-1">
																<div className="flex items-center gap-2">
																	<p className="truncate text-sm font-medium">{email.subject}</p>
																	{email.action_required && <Badge variant="default" className="text-[10px]">Action Required</Badge>}
																</div>
																<p className="mt-0.5 text-xs text-muted-foreground">{email.sender}</p>
																<p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{email.summary}</p>
															</div>
															<div className="flex shrink-0 flex-col items-end gap-1">
																<Badge variant={email.priority === "high" ? "destructive" : "secondary"}>
																	{email.priority}
																</Badge>
																<span className="text-[10px] text-muted-foreground">
																	{new Date(email.received_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
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
					</CardContent>
				</Card>
			)}

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Spam Audit */}
				{spamQuery.isLoading ? (
					<TableSkeleton rows={4} />
				) : spamQuery.isError ? (
					<QueryError message="Failed to load spam audit." onRetry={() => spamQuery.refetch()} />
				) : (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<ShieldAlert className="h-4 w-4 text-muted-foreground" />
								Spam Audit
							</CardTitle>
						</CardHeader>
						<CardContent>
							{(spamQuery.data ?? []).length === 0 ? (
								<p className="py-4 text-center text-sm text-muted-foreground">Inbox looks clean.</p>
							) : (
								<div className="space-y-2">
									{(spamQuery.data ?? []).map((item: SpamAuditItem) => (
										<div key={item.id} className="flex items-center justify-between rounded-lg border p-3">
											<div className="min-w-0 flex-1">
												<p className="truncate text-sm font-medium">{item.subject}</p>
												<p className="text-xs text-muted-foreground">{item.sender} · {item.frequency}</p>
											</div>
											<Badge variant={item.suggested_action === "block" ? "destructive" : item.suggested_action === "keep" ? "secondary" : "outline"}>
												{item.suggested_action === "unsubscribe" && <XCircle className="mr-1 h-3 w-3" />}
												{item.suggested_action === "block" && <ShieldAlert className="mr-1 h-3 w-3" />}
												{item.suggested_action === "keep" && <CheckCircle2 className="mr-1 h-3 w-3" />}
												{item.suggested_action}
											</Badge>
										</div>
									))}
								</div>
							)}
						</CardContent>
					</Card>
				)}

				{/* Assignments */}
				{assignmentsQuery.isLoading ? (
					<TableSkeleton rows={4} />
				) : assignmentsQuery.isError ? (
					<QueryError message="Failed to load assignment reminders." onRetry={() => assignmentsQuery.refetch()} />
				) : (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<BookOpen className="h-4 w-4 text-muted-foreground" />
								Assignment Reminders
							</CardTitle>
						</CardHeader>
						<CardContent>
							{(assignmentsQuery.data ?? []).length === 0 ? (
								<p className="py-4 text-center text-sm text-muted-foreground">No upcoming assignments.</p>
							) : (
								<div className="space-y-2">
									{(assignmentsQuery.data ?? []).map((item: AssignmentReminder) => (
										<div key={item.id} className="flex items-center justify-between rounded-lg border p-3">
											<div className="min-w-0 flex-1">
												<div className="flex items-center gap-2">
													<p className="truncate text-sm font-medium">{item.title}</p>
													<Badge variant="outline" className="text-[10px]">{item.platform}</Badge>
												</div>
												<p className="mt-0.5 text-xs text-muted-foreground">
													{item.course} · Due {new Date(item.due_date).toLocaleDateString([], { month: "short", day: "numeric" })}
												</p>
											</div>
											<Badge variant={item.status === "overdue" ? "destructive" : item.status === "submitted" ? "secondary" : "outline"}>
												{item.status === "overdue" && <AlertTriangle className="mr-1 h-3 w-3" />}
												{item.status === "upcoming" && <Clock className="mr-1 h-3 w-3" />}
												{item.status === "submitted" && <CheckCircle2 className="mr-1 h-3 w-3" />}
												{item.status}
											</Badge>
										</div>
									))}
								</div>
							)}
						</CardContent>
					</Card>
				)}
			</div>
		</div>
	);
}
