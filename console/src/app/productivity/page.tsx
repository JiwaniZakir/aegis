"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Timer, Monitor, TrendingUp, BarChart3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { MetricCardSkeleton, TableSkeleton, ChartSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import {
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
	type ChartConfig,
} from "@/components/ui/chart";

function formatMinutes(minutes: number) {
	const h = Math.floor(minutes / 60);
	const m = minutes % 60;
	return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function ProductivityPage() {
	const summaryQuery = useQuery({
		queryKey: ["productivity", "summary"],
		queryFn: () => api.productivity.getSummary(),
	});

	const trendsQuery = useQuery({
		queryKey: ["productivity", "trends"],
		queryFn: () => api.productivity.getTrends(),
	});

	const weeklyQuery = useQuery({
		queryKey: ["productivity", "weekly"],
		queryFn: () => api.productivity.getWeekly(),
	});

	const appUsageQuery = useQuery({
		queryKey: ["productivity", "app-usage"],
		queryFn: () => api.productivity.getAppUsage(),
	});

	const summary = summaryQuery.data;
	const weekly = weeklyQuery.data;
	const appUsage = appUsageQuery.data ?? [];
	const trends = trendsQuery.data ?? [];

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Productivity" description="Screen time, focus, and app usage" />

			{/* Metric cards */}
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{summaryQuery.isLoading ? (
					<>
						<MetricCardSkeleton />
						<MetricCardSkeleton />
						<MetricCardSkeleton />
						<MetricCardSkeleton />
					</>
				) : summaryQuery.isError ? (
					<div className="sm:col-span-2 lg:col-span-4">
						<QueryError message="Failed to load productivity summary." onRetry={() => summaryQuery.refetch()} />
					</div>
				) : summary ? (
					<>
						<MetricCard
							label="Screen Time"
							value={formatMinutes(summary.screen_time_minutes ?? 0)}
							icon={Monitor}
						/>
						<MetricCard
							label="Productive Time"
							value={formatMinutes(summary.productive_minutes ?? 0)}
							icon={Timer}
						/>
						<MetricCard
							label="Productive %"
							value={
								summary.screen_time_minutes
									? `${Math.round(((summary.productive_minutes ?? 0) / summary.screen_time_minutes) * 100)}%`
									: "--"
							}
							icon={TrendingUp}
						/>
						<MetricCard
							label="Focus Score"
							value={String(summary.score ?? 0)}
							icon={BarChart3}
							trend={
								summary.score
									? { value: `${summary.score}/100`, positive: summary.score >= 60 }
									: undefined
							}
						/>
					</>
				) : (
					<>
						<MetricCard label="Screen Time" value="--" icon={Monitor} />
						<MetricCard label="Productive Time" value="--" icon={Timer} />
						<MetricCard label="Productive %" value="--" icon={TrendingUp} />
						<MetricCard label="Focus Score" value="--" icon={BarChart3} />
					</>
				)}
			</div>

			<div className="grid gap-6 lg:grid-cols-2">
				{/* App Usage */}
				{appUsageQuery.isLoading ? (
					<TableSkeleton rows={8} />
				) : appUsageQuery.isError ? (
					<QueryError message="Failed to load app usage." onRetry={() => appUsageQuery.refetch()} />
				) : (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<Monitor className="h-4 w-4 text-muted-foreground" />
								App Usage
							</CardTitle>
						</CardHeader>
						<CardContent>
							{appUsage.length === 0 ? (
								<p className="py-6 text-center text-sm text-muted-foreground">No app usage data.</p>
							) : (
								<div className="space-y-3">
									{appUsage.slice(0, 10).map((app: { name: string; minutes: number }, index: number) => {
										const maxMinutes = appUsage[0]?.minutes ?? 1;
										const pct = (app.minutes / maxMinutes) * 100;
										return (
											<div key={app.name} className="space-y-1">
												<div className="flex items-center justify-between text-sm">
													<span className="truncate">{app.name}</span>
													<span className="shrink-0 tabular-nums text-muted-foreground">
														{formatMinutes(app.minutes)}
													</span>
												</div>
												<div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
													<div
														className="h-full rounded-full bg-blue-500 transition-all"
														style={{ width: `${pct}%` }}
													/>
												</div>
											</div>
										);
									})}
								</div>
							)}
						</CardContent>
					</Card>
				)}

				{/* Weekly Report */}
				{weeklyQuery.isLoading ? (
					<ChartSkeleton />
				) : weeklyQuery.isError ? (
					<QueryError message="Failed to load weekly report." onRetry={() => weeklyQuery.refetch()} />
				) : weekly ? (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<TrendingUp className="h-4 w-4 text-muted-foreground" />
								Weekly Report
							</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="space-y-4">
								<div className="flex items-center gap-2">
									<Badge variant={weekly.trend === "improving" ? "default" : weekly.trend === "declining" ? "destructive" : "secondary"}>
										{weekly.trend ?? "stable"}
									</Badge>
									<span className="text-xs text-muted-foreground">
										{weekly.week_start && weekly.week_end
											? `${new Date(weekly.week_start).toLocaleDateString([], { month: "short", day: "numeric" })} - ${new Date(weekly.week_end).toLocaleDateString([], { month: "short", day: "numeric" })}`
											: "This week"}
									</span>
								</div>
								<div className="grid grid-cols-2 gap-3">
									<div className="rounded-lg border p-3 text-center">
										<p className="text-2xl font-semibold tabular-nums">
											{formatMinutes(weekly.total_screen_time_minutes ?? 0)}
										</p>
										<p className="text-xs text-muted-foreground">Total Screen Time</p>
									</div>
									<div className="rounded-lg border p-3 text-center">
										<p className="text-2xl font-semibold tabular-nums">
											{formatMinutes(weekly.total_productive_minutes ?? 0)}
										</p>
										<p className="text-xs text-muted-foreground">Productive Time</p>
									</div>
								</div>
								<div className="flex items-center justify-between text-sm">
									<span className="text-muted-foreground">Average Score</span>
									<span className="font-semibold tabular-nums">{weekly.avg_score ?? 0}/100</span>
								</div>
								{weekly.summary && (
									<p className="text-sm text-muted-foreground">{weekly.summary}</p>
								)}
								{weekly.most_used_apps && weekly.most_used_apps.length > 0 && (
									<div>
										<p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Top Apps</p>
										<div className="flex flex-wrap gap-2">
											{weekly.most_used_apps.map((app: { name: string; minutes: number }) => (
												<Badge key={app.name} variant="secondary">
													{app.name} ({formatMinutes(app.minutes)})
												</Badge>
											))}
										</div>
									</div>
								)}
							</div>
						</CardContent>
					</Card>
				) : (
					<Card>
						<CardContent className="flex items-center justify-center py-12">
							<p className="text-sm text-muted-foreground">No weekly report available.</p>
						</CardContent>
					</Card>
				)}
			</div>

			{/* Daily Screen Time Chart */}
			{trendsQuery.isLoading ? (
				<ChartSkeleton />
			) : trendsQuery.isError ? (
				<QueryError message="Failed to load productivity trends." onRetry={() => trendsQuery.refetch()} />
			) : Array.isArray(trends) && trends.length > 0 ? (() => {
				const screenTimeConfig: ChartConfig = {
					productive: { label: "Productive", color: "hsl(142, 71%, 45%)" },
					non_productive: { label: "Non-Productive", color: "hsl(220, 9%, 65%)" },
				};
				const barData = (trends as Array<{ date?: string; screen_time_minutes?: number; productive_minutes?: number }>).map((d) => ({
					date: d.date
						? new Date(d.date).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })
						: "",
					productive: d.productive_minutes ?? 0,
					non_productive: Math.max(0, (d.screen_time_minutes ?? 0) - (d.productive_minutes ?? 0)),
				}));
				return (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<BarChart3 className="h-4 w-4 text-muted-foreground" />
								Daily Screen Time
							</CardTitle>
						</CardHeader>
						<CardContent>
							<ChartContainer config={screenTimeConfig} className="h-[300px] w-full">
								<BarChart data={barData}>
									<CartesianGrid strokeDasharray="3 3" />
									<XAxis dataKey="date" />
									<YAxis tickFormatter={(v: number) => `${Math.round(v / 60)}h`} />
									<ChartTooltip content={<ChartTooltipContent formatter={(value) => formatMinutes(Number(value))} />} />
									<Bar dataKey="productive" stackId="screen" fill="var(--color-productive)" radius={[0, 0, 0, 0]} />
									<Bar dataKey="non_productive" stackId="screen" fill="var(--color-non_productive)" radius={[4, 4, 0, 0]} />
								</BarChart>
							</ChartContainer>
						</CardContent>
					</Card>
				);
			})() : null}
		</div>
	);
}
