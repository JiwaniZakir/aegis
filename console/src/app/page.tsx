"use client";

import { useQuery } from "@tanstack/react-query";
import {
	CalendarDays,
	DollarSign,
	Footprints,
	Flame,
	FileText,
	ArrowUpRight,
	ArrowDownRight,
	Clock,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
	DailyBriefing,
	CalendarEvent,
	FinanceSnapshot,
	HealthMetrics,
} from "@/lib/api";

function StatCard({
	label,
	value,
	icon: Icon,
	trend,
}: {
	label: string;
	value: string;
	icon: React.ComponentType<{ className?: string }>;
	trend?: { value: string; positive: boolean };
}) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<div className="flex items-center justify-between">
				<p className="text-sm text-neutral-400">{label}</p>
				<Icon className="h-4 w-4 text-neutral-500" />
			</div>
			<p className="mt-2 text-2xl font-semibold text-neutral-50">{value}</p>
			{trend && (
				<div className="mt-1 flex items-center gap-1 text-xs">
					{trend.positive ? (
						<ArrowUpRight className="h-3 w-3 text-emerald-500" />
					) : (
						<ArrowDownRight className="h-3 w-3 text-red-500" />
					)}
					<span
						className={
							trend.positive ? "text-emerald-500" : "text-red-500"
						}
					>
						{trend.value}
					</span>
				</div>
			)}
		</div>
	);
}

function CalendarEventRow({ event }: { event: CalendarEvent }) {
	const time = new Date(event.start).toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
	});
	return (
		<div className="flex items-center gap-3 rounded-md border border-neutral-800 px-3 py-2">
			<Clock className="h-4 w-4 shrink-0 text-neutral-500" />
			<div className="min-w-0 flex-1">
				<p className="truncate text-sm font-medium text-neutral-200">
					{event.title}
				</p>
				{event.location && (
					<p className="truncate text-xs text-neutral-500">
						{event.location}
					</p>
				)}
			</div>
			<span className="shrink-0 text-xs text-neutral-400">{time}</span>
		</div>
	);
}

function BriefingSection({ briefing }: { briefing: DailyBriefing }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<h2 className="mb-3 text-lg font-semibold text-neutral-100">
				Morning Briefing
			</h2>
			<p className="text-sm leading-relaxed text-neutral-300">
				{briefing.summary}
			</p>
			{briefing.action_items.length > 0 && (
				<div className="mt-4">
					<h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
						Action Items
					</h3>
					<ul className="space-y-1">
						{briefing.action_items.map((item) => (
							<li
								key={item}
								className="text-sm text-neutral-300 before:mr-2 before:text-neutral-600 before:content-['\u2022']"
							>
								{item}
							</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
}

function SkeletonCard() {
	return (
		<div className="animate-pulse rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<div className="h-4 w-24 rounded bg-neutral-800" />
			<div className="mt-3 h-7 w-32 rounded bg-neutral-800" />
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

	const formatCurrency = (n: number) =>
		new Intl.NumberFormat("en-US", {
			style: "currency",
			currency: "USD",
			maximumFractionDigits: 0,
		}).format(n);

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<h1 className="text-2xl font-bold text-neutral-50">Dashboard</h1>

			{/* Stat cards */}
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{briefingQuery.isLoading ? (
					<>
						<SkeletonCard />
						<SkeletonCard />
						<SkeletonCard />
						<SkeletonCard />
					</>
				) : (
					<>
						<StatCard
							label="Total Balance"
							value={
								financeSnap
									? formatCurrency(financeSnap.total_balance)
									: "--"
							}
							icon={DollarSign}
							trend={
								financeSnap
									? {
											value: formatCurrency(
												financeSnap.monthly_spending,
											),
											positive:
												financeSnap.monthly_spending < 3000,
										}
									: undefined
							}
						/>
						<StatCard
							label="Steps Today"
							value={
								healthSummary
									? healthSummary.steps.toLocaleString()
									: "--"
							}
							icon={Footprints}
						/>
						<StatCard
							label="Calories"
							value={
								healthSummary
									? `${healthSummary.calories_consumed.toLocaleString()} kcal`
									: "--"
							}
							icon={Flame}
						/>
						<StatCard
							label="Posts Today"
							value={
								contentStatus
									? `${contentStatus.posts_published_today} / ${contentStatus.posts_scheduled}`
									: "--"
							}
							icon={FileText}
						/>
					</>
				)}
			</div>

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Briefing */}
				{briefing ? (
					<BriefingSection briefing={briefing} />
				) : briefingQuery.isLoading ? (
					<div className="animate-pulse rounded-lg border border-neutral-800 bg-neutral-900 p-5">
						<div className="h-5 w-40 rounded bg-neutral-800" />
						<div className="mt-4 space-y-2">
							<div className="h-4 w-full rounded bg-neutral-800" />
							<div className="h-4 w-3/4 rounded bg-neutral-800" />
							<div className="h-4 w-5/6 rounded bg-neutral-800" />
						</div>
					</div>
				) : (
					<div className="flex items-center justify-center rounded-lg border border-neutral-800 bg-neutral-900 p-8">
						<p className="text-sm text-neutral-500">
							Briefing not yet generated for today.
						</p>
					</div>
				)}

				{/* Calendar */}
				<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
					<div className="mb-3 flex items-center gap-2">
						<CalendarDays className="h-4 w-4 text-neutral-400" />
						<h2 className="text-lg font-semibold text-neutral-100">
							Today&apos;s Events
						</h2>
					</div>
					{calendarEvents.length > 0 ? (
						<div className="space-y-2">
							{calendarEvents.map((event) => (
								<CalendarEventRow key={event.id} event={event} />
							))}
						</div>
					) : (
						<p className="py-4 text-center text-sm text-neutral-500">
							{briefingQuery.isLoading
								? "Loading events..."
								: "No events today."}
						</p>
					)}
				</div>
			</div>
		</div>
	);
}
