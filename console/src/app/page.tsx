"use client";

import { useQuery } from "@tanstack/react-query";
import {
	CalendarDays,
	DollarSign,
	Footprints,
	Flame,
	FileText,
	Clock,
} from "lucide-react";
import { api } from "@/lib/api";
import type { CalendarEvent } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { MetricCardSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";
import { Skeleton } from "@/components/ui/skeleton";
import { RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";
import { ChartContainer, type ChartConfig } from "@/components/ui/chart";

function EventRow({ event }: { event: CalendarEvent }) {
	const time = new Date(event.start).toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
	});
	return (
		<div className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted">
			<Clock className="h-4 w-4 shrink-0 text-muted-foreground" />
			<div className="min-w-0 flex-1">
				<p className="truncate text-sm font-medium">{event.title}</p>
				{event.location && (
					<p className="truncate text-xs text-muted-foreground">{event.location}</p>
				)}
			</div>
			<span className="shrink-0 text-xs text-muted-foreground">{time}</span>
		</div>
	);
}

export default function DashboardPage() {
	const briefingQuery = useQuery({
		queryKey: ["briefing", "today"],
		queryFn: () => api.briefing.getToday(),
	});

	const briefing = briefingQuery.data;
	const financeSnap = briefing?.finance_snapshot;
	const healthSummary = briefing?.health_summary;
	const calendarEvents = briefing?.calendar_events ?? [];
	const contentStatus = briefing?.content_status;

	const fmt = (n: number) =>
		new Intl.NumberFormat("en-US", {
			style: "currency",
			currency: "USD",
			maximumFractionDigits: 0,
		}).format(n);

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Dashboard" description="Your morning overview" />

			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{briefingQuery.isLoading ? (
					<>
						<MetricCardSkeleton />
						<MetricCardSkeleton />
						<MetricCardSkeleton />
						<MetricCardSkeleton />
					</>
				) : briefingQuery.isError ? (
					<div className="sm:col-span-2 lg:col-span-4">
						<QueryError message="Failed to load briefing data." onRetry={() => briefingQuery.refetch()} />
					</div>
				) : (
					<>
						<MetricCard
							label="Total Balance"
							value={financeSnap ? fmt(financeSnap.total_balance) : "--"}
							icon={DollarSign}
							trend={
								financeSnap
									? { value: fmt(financeSnap.monthly_spending), positive: financeSnap.monthly_spending < 3000 }
									: undefined
							}
						/>
						<MetricCard
							label="Steps Today"
							value={healthSummary ? healthSummary.steps.toLocaleString() : "--"}
							icon={Footprints}
						/>
						<MetricCard
							label="Calories"
							value={healthSummary ? `${healthSummary.calories_consumed.toLocaleString()} kcal` : "--"}
							icon={Flame}
						/>
						<MetricCard
							label="Posts Today"
							value={contentStatus ? `${contentStatus.posts_published_today} / ${contentStatus.posts_scheduled}` : "--"}
							icon={FileText}
						/>
					</>
				)}
			</div>

			<div className="grid gap-6 lg:grid-cols-3">
				<Card>
					<CardHeader>
						<CardTitle className="text-base">Morning Briefing</CardTitle>
					</CardHeader>
					<CardContent>
						{briefing ? (
							<div className="space-y-4">
								<p className="text-sm leading-relaxed text-muted-foreground">
									{briefing.summary}
								</p>
								{briefing.action_items.length > 0 && (
									<div>
										<p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
											Action Items
										</p>
										<ul className="space-y-1.5">
											{briefing.action_items.map((item) => (
												<li key={item} className="flex items-start gap-2 text-sm">
													<span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground" />
													{item}
												</li>
											))}
										</ul>
									</div>
								)}
							</div>
						) : briefingQuery.isLoading ? (
							<div className="space-y-2">
								<Skeleton className="h-4 w-full" />
								<Skeleton className="h-4 w-3/4" />
								<Skeleton className="h-4 w-5/6" />
							</div>
						) : briefingQuery.isError ? (
							<QueryError message="Failed to load morning briefing." onRetry={() => briefingQuery.refetch()} />
						) : (
							<p className="py-4 text-center text-sm text-muted-foreground">
								Briefing not yet generated for today.
							</p>
						)}
					</CardContent>
				</Card>

				<Card>
					<CardHeader>
						<div className="flex items-center gap-2">
							<CalendarDays className="h-4 w-4 text-muted-foreground" />
							<CardTitle className="text-base">Today&apos;s Events</CardTitle>
						</div>
					</CardHeader>
					<CardContent>
						{calendarEvents.length > 0 ? (
							<div className="space-y-1">
								{calendarEvents.map((event) => (
									<EventRow key={event.id} event={event} />
								))}
							</div>
						) : (
							<p className="py-4 text-center text-sm text-muted-foreground">
								{briefingQuery.isLoading ? "Loading events..." : "No events today."}
							</p>
						)}
					</CardContent>
				</Card>

				{/* Health Goals */}
				<Card>
					<CardHeader>
						<div className="flex items-center gap-2">
							<Footprints className="h-4 w-4 text-muted-foreground" />
							<CardTitle className="text-base">Health Goals</CardTitle>
						</div>
					</CardHeader>
					<CardContent>
						{healthSummary ? (() => {
							const stepsGoal = 10000;
							const caloriesLimit = 1900;
							const stepsPct = Math.min(Math.round((healthSummary.steps / stepsGoal) * 100), 100);
							const caloriesPct = Math.min(Math.round((healthSummary.calories_consumed / caloriesLimit) * 100), 100);
							const radialData = [
								{ name: "Calories", value: caloriesPct, fill: "var(--color-calories)" },
								{ name: "Steps", value: stepsPct, fill: "var(--color-steps)" },
							];
							const healthGoalsConfig: ChartConfig = {
								steps: { label: "Steps", color: "hsl(142, 71%, 45%)" },
								calories: { label: "Calories", color: "hsl(24, 95%, 53%)" },
							};
							return (
								<div className="space-y-3">
									<ChartContainer config={healthGoalsConfig} className="mx-auto aspect-square max-h-[180px]">
										<RadialBarChart
											cx="50%"
											cy="50%"
											innerRadius="30%"
											outerRadius="90%"
											data={radialData}
											startAngle={90}
											endAngle={-270}
										>
											<PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
											<RadialBar
												background
												dataKey="value"
												cornerRadius={6}
											/>
										</RadialBarChart>
									</ChartContainer>
									<div className="space-y-1.5 text-sm">
										<div className="flex items-center justify-between">
											<div className="flex items-center gap-2">
												<div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "hsl(142, 71%, 45%)" }} />
												<span className="text-muted-foreground">Steps</span>
											</div>
											<span className="font-medium tabular-nums">
												{healthSummary.steps.toLocaleString()} / {stepsGoal.toLocaleString()}
											</span>
										</div>
										<div className="flex items-center justify-between">
											<div className="flex items-center gap-2">
												<div className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "hsl(24, 95%, 53%)" }} />
												<span className="text-muted-foreground">Calories</span>
											</div>
											<span className="font-medium tabular-nums">
												{healthSummary.calories_consumed.toLocaleString()} / {caloriesLimit.toLocaleString()}
											</span>
										</div>
									</div>
								</div>
							);
						})() : (
							<p className="py-4 text-center text-sm text-muted-foreground">
								{briefingQuery.isLoading ? "Loading..." : "No health data yet."}
							</p>
						)}
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
