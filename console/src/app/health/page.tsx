"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Heart, Footprints, Flame, Moon, Dumbbell, Activity } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { MetricCardSkeleton, ChartSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";
import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts";
import {
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
	type ChartConfig,
} from "@/components/ui/chart";

function ProgressBar({ value, max, label, color }: { value: number; max: number; label: string; color: string }) {
	const pct = Math.min((value / max) * 100, 100);
	return (
		<div className="space-y-1.5">
			<div className="flex items-center justify-between text-sm">
				<span className="text-muted-foreground">{label}</span>
				<span className="tabular-nums font-medium">
					{value.toLocaleString()} / {max.toLocaleString()}
				</span>
			</div>
			<div className="h-2 w-full overflow-hidden rounded-full bg-muted">
				<div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
			</div>
		</div>
	);
}

export default function HealthPage() {
	const summaryQuery = useQuery({
		queryKey: ["health", "summary"],
		queryFn: () => api.health.getSummary(),
	});

	const goalsQuery = useQuery({
		queryKey: ["health", "goals"],
		queryFn: () => api.health.getGoals(),
	});

	const trendsQuery = useQuery({
		queryKey: ["health", "trends", 7],
		queryFn: () => api.health.getTrends({ days: 7 }),
	});

	const summary = summaryQuery.data;
	const goals = goalsQuery.data;
	const trends = trendsQuery.data;
	const trendData = (trends as { trends?: object[] } | undefined)?.trends ?? (Array.isArray(trends) ? trends : []);

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Health" description="Metrics, goals, and trends" />

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
						<QueryError message="Failed to load health summary." onRetry={() => summaryQuery.refetch()} />
					</div>
				) : summary ? (
					<>
						<MetricCard label="Steps" value={summary.steps?.toLocaleString() ?? "--"} icon={Footprints} />
						<MetricCard label="Calories" value={`${summary.calories_consumed ?? 0} kcal`} icon={Flame} />
						<MetricCard label="Sleep" value={`${summary.sleep_hours ?? 0}h`} icon={Moon} />
						<MetricCard label="Heart Rate" value={`${summary.heart_rate_avg ?? 0} bpm`} icon={Activity} />
					</>
				) : (
					<>
						<MetricCard label="Steps" value="--" icon={Footprints} />
						<MetricCard label="Calories" value="--" icon={Flame} />
						<MetricCard label="Sleep" value="--" icon={Moon} />
						<MetricCard label="Heart Rate" value="--" icon={Activity} />
					</>
				)}
			</div>

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Goals progress */}
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2 text-base">
							<Dumbbell className="h-4 w-4 text-muted-foreground" />
							Daily Goals
						</CardTitle>
					</CardHeader>
					<CardContent>
						{summaryQuery.isLoading || goalsQuery.isLoading ? (
							<div className="space-y-4">
								{Array.from({ length: 4 }).map((_, i) => (
									<div key={`skel-${i}`} className="space-y-1.5">
										<div className="h-4 w-full animate-pulse rounded bg-muted" />
										<div className="h-2 w-full animate-pulse rounded bg-muted" />
									</div>
								))}
							</div>
						) : goalsQuery.isError || summaryQuery.isError ? (
							<QueryError message="Failed to load goals." onRetry={() => { goalsQuery.refetch(); summaryQuery.refetch(); }} />
						) : summary && goals ? (
							<div className="space-y-4">
								<ProgressBar
									value={summary.calories_consumed ?? 0}
									max={goals.daily_calorie_limit}
									label="Calories"
									color="bg-orange-500"
								/>
								<ProgressBar
									value={summary.protein_g ?? 0}
									max={goals.daily_protein_target_g}
									label="Protein"
									color="bg-blue-500"
								/>
								<ProgressBar
									value={summary.steps ?? 0}
									max={goals.daily_step_goal}
									label="Steps"
									color="bg-emerald-500"
								/>
								<ProgressBar
									value={summary.sleep_hours ?? 0}
									max={goals.sleep_target_hours}
									label="Sleep (hours)"
									color="bg-purple-500"
								/>
							</div>
						) : (
							<p className="py-6 text-center text-sm text-muted-foreground">No health data available.</p>
						)}
					</CardContent>
				</Card>

				{/* Macro breakdown */}
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2 text-base">
							<Flame className="h-4 w-4 text-muted-foreground" />
							Macro Breakdown
						</CardTitle>
					</CardHeader>
					<CardContent>
						{summaryQuery.isLoading ? (
							<div className="space-y-3">
								{Array.from({ length: 3 }).map((_, i) => (
									<div key={`skel-${i}`} className="h-12 animate-pulse rounded-lg bg-muted" />
								))}
							</div>
						) : summaryQuery.isError ? (
							<QueryError message="Failed to load macro data." onRetry={() => summaryQuery.refetch()} />
						) : summary ? (
							<div className="space-y-3">
								{[
									{ label: "Protein", value: `${summary.protein_g ?? 0}g`, color: "bg-blue-500" },
									{ label: "Carbs", value: `${summary.carbs_g ?? 0}g`, color: "bg-amber-500" },
									{ label: "Fat", value: `${summary.fat_g ?? 0}g`, color: "bg-red-500" },
								].map((macro) => (
									<div key={macro.label} className="flex items-center gap-3 rounded-lg border p-3">
										<div className={`h-3 w-3 rounded-full ${macro.color}`} />
										<span className="text-sm text-muted-foreground">{macro.label}</span>
										<span className="ml-auto text-sm font-semibold tabular-nums">{macro.value}</span>
									</div>
								))}
								<div className="flex items-center justify-between pt-2 text-sm">
									<span className="text-muted-foreground">Calories Burned</span>
									<span className="font-semibold tabular-nums">{summary.calories_burned ?? 0} kcal</span>
								</div>
								<div className="flex items-center justify-between text-sm">
									<span className="text-muted-foreground">Sleep Quality</span>
									<span className="font-semibold tabular-nums">{summary.sleep_quality ?? 0}/10</span>
								</div>
							</div>
						) : (
							<p className="py-6 text-center text-sm text-muted-foreground">No data available.</p>
						)}
					</CardContent>
				</Card>
			</div>

			{/* 7-Day Trends */}
			{trendsQuery.isLoading ? (
				<ChartSkeleton />
			) : trendsQuery.isError ? (
				<QueryError message="Failed to load health trends." onRetry={() => trendsQuery.refetch()} />
			) : trendData.length > 0 ? (() => {
				const trendChartConfig: ChartConfig = {
					steps: { label: "Steps", color: "hsl(221, 83%, 53%)" },
					calories_consumed: { label: "Calories", color: "hsl(24, 95%, 53%)" },
					sleep_hours: { label: "Sleep (hrs)", color: "hsl(270, 60%, 55%)" },
				};
				const chartData = (trendData as Array<{ date?: string; steps?: number; calories_consumed?: number; sleep_hours?: number }>).map((d) => ({
					...d,
					day: d.date
						? new Date(d.date).toLocaleDateString([], { weekday: "short" })
						: "",
				}));
				return (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<Activity className="h-4 w-4 text-muted-foreground" />
								7-Day Trends
							</CardTitle>
						</CardHeader>
						<CardContent>
							<ChartContainer config={trendChartConfig} className="h-[300px] w-full">
								<LineChart data={chartData}>
									<CartesianGrid strokeDasharray="3 3" />
									<XAxis dataKey="day" />
									<YAxis yAxisId="left" />
									<YAxis yAxisId="right" orientation="right" />
									<ChartTooltip content={<ChartTooltipContent />} />
									<Line yAxisId="left" type="monotone" dataKey="steps" stroke="var(--color-steps)" strokeWidth={2} dot={false} />
									<Line yAxisId="right" type="monotone" dataKey="calories_consumed" stroke="var(--color-calories_consumed)" strokeWidth={2} dot={false} />
									<Line yAxisId="right" type="monotone" dataKey="sleep_hours" stroke="var(--color-sleep_hours)" strokeWidth={2} dot={false} />
								</LineChart>
							</ChartContainer>
						</CardContent>
					</Card>
				);
			})() : null}
		</div>
	);
}
