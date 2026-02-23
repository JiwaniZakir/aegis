"use client";

import { useQuery } from "@tanstack/react-query";
import {
	BarChart,
	Bar,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	LineChart,
	Line,
} from "recharts";
import {
	BarChart3,
	Monitor,
	Clock,
	TrendingUp,
	FileText,
	ArrowUp,
	ArrowDown,
	Minus,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ProductivityMetrics, ProductivityWeeklyReport } from "@/lib/api";

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

// ---- Helper: minutes to hours string ----
function formatMinutes(minutes: number): string {
	const h = Math.floor(minutes / 60);
	const m = minutes % 60;
	if (h === 0) return `${m}m`;
	if (m === 0) return `${h}h`;
	return `${h}h ${m}m`;
}

// ---- Screen time summary cards ----
function ScreenTimeSummary({
	latest,
	metrics,
}: {
	latest: ProductivityMetrics | undefined;
	metrics: ProductivityMetrics[];
}) {
	const totalMinutes = metrics.reduce(
		(acc, m) => acc + m.screen_time_minutes,
		0,
	);
	const avgMinutes =
		metrics.length > 0 ? Math.round(totalMinutes / metrics.length) : 0;
	const productiveMinutes = metrics.reduce(
		(acc, m) => acc + m.productive_minutes,
		0,
	);
	const productivePercent =
		totalMinutes > 0 ? Math.round((productiveMinutes / totalMinutes) * 100) : 0;

	const avgScore =
		metrics.length > 0
			? Math.round(
					metrics.reduce((acc, m) => acc + m.score, 0) / metrics.length,
				)
			: 0;

	const getScoreColor = (s: number) => {
		if (s >= 80) return "text-emerald-400";
		if (s >= 60) return "text-yellow-400";
		return "text-red-400";
	};

	return (
		<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
			<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
				<div className="mb-1 flex items-center gap-2">
					<Monitor className="h-4 w-4 text-neutral-500" />
					<p className="text-xs text-neutral-500">Total Screen Time</p>
				</div>
				<p className="text-2xl font-bold text-neutral-50">
					{formatMinutes(totalMinutes)}
				</p>
				<p className="mt-0.5 text-xs text-neutral-500">
					Last {metrics.length} days
				</p>
			</div>
			<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
				<div className="mb-1 flex items-center gap-2">
					<Clock className="h-4 w-4 text-neutral-500" />
					<p className="text-xs text-neutral-500">Daily Average</p>
				</div>
				<p className="text-2xl font-bold text-neutral-50">
					{formatMinutes(avgMinutes)}
				</p>
				<p className="mt-0.5 text-xs text-neutral-500">per day</p>
			</div>
			<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
				<div className="mb-1 flex items-center gap-2">
					<TrendingUp className="h-4 w-4 text-neutral-500" />
					<p className="text-xs text-neutral-500">Productive</p>
				</div>
				<p className="text-2xl font-bold text-neutral-50">
					{productivePercent}%
				</p>
				<p className="mt-0.5 text-xs text-neutral-500">
					{formatMinutes(productiveMinutes)} total
				</p>
			</div>
			<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
				<div className="mb-1 flex items-center gap-2">
					<BarChart3 className="h-4 w-4 text-neutral-500" />
					<p className="text-xs text-neutral-500">Avg Score</p>
				</div>
				<p className={`text-2xl font-bold ${getScoreColor(avgScore)}`}>
					{avgScore}
					<span className="text-sm text-neutral-500">/100</span>
				</p>
				<p className="mt-0.5 text-xs text-neutral-500">
					Today: {latest?.score ?? "--"}
				</p>
			</div>
		</div>
	);
}

// ---- App usage bar chart ----
function AppUsageChart({
	apps,
}: { apps: { name: string; minutes: number }[] }) {
	const sortedApps = [...apps].sort((a, b) => b.minutes - a.minutes).slice(0, 10);

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Monitor className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					App Usage Breakdown
				</h2>
			</div>
			{sortedApps.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No app usage data available.
				</p>
			) : (
				<div className="h-72">
					<ResponsiveContainer width="100%" height="100%">
						<BarChart
							data={sortedApps}
							layout="vertical"
							margin={{ left: 20 }}
						>
							<CartesianGrid
								strokeDasharray="3 3"
								stroke="#262626"
								horizontal={false}
							/>
							<XAxis
								type="number"
								stroke="#525252"
								tick={{ fill: "#737373", fontSize: 12 }}
								tickFormatter={(v: number) => formatMinutes(v)}
							/>
							<YAxis
								type="category"
								dataKey="name"
								stroke="#525252"
								tick={{ fill: "#a3a3a3", fontSize: 12 }}
								width={100}
							/>
							<Tooltip
								contentStyle={{
									backgroundColor: "#171717",
									border: "1px solid #262626",
									borderRadius: "8px",
									color: "#e5e5e5",
								}}
								formatter={(value: number) => [
									formatMinutes(value),
									"Usage",
								]}
							/>
							<Bar
								dataKey="minutes"
								fill="#6366f1"
								radius={[0, 4, 4, 0]}
							/>
						</BarChart>
					</ResponsiveContainer>
				</div>
			)}
		</div>
	);
}

// ---- Productivity trends line chart ----
function ProductivityTrendChart({
	data,
}: { data: ProductivityMetrics[] }) {
	const chartData = data.map((m) => ({
		date: m.date,
		score: m.score,
		productive_hours: Math.round((m.productive_minutes / 60) * 10) / 10,
		screen_hours: Math.round((m.screen_time_minutes / 60) * 10) / 10,
	}));

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<TrendingUp className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Productivity Trends (7 Days)
				</h2>
			</div>
			{chartData.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No trend data available.
				</p>
			) : (
				<div className="h-64">
					<ResponsiveContainer width="100%" height="100%">
						<LineChart data={chartData}>
							<CartesianGrid
								strokeDasharray="3 3"
								stroke="#262626"
							/>
							<XAxis
								dataKey="date"
								stroke="#525252"
								tick={{ fill: "#737373", fontSize: 12 }}
								tickFormatter={(v: string) =>
									new Date(v).toLocaleDateString([], {
										weekday: "short",
									})
								}
							/>
							<YAxis
								yAxisId="score"
								stroke="#525252"
								tick={{ fill: "#737373", fontSize: 12 }}
								domain={[0, 100]}
								orientation="left"
							/>
							<YAxis
								yAxisId="hours"
								stroke="#525252"
								tick={{ fill: "#737373", fontSize: 12 }}
								orientation="right"
								tickFormatter={(v: number) => `${v}h`}
							/>
							<Tooltip
								contentStyle={{
									backgroundColor: "#171717",
									border: "1px solid #262626",
									borderRadius: "8px",
									color: "#e5e5e5",
								}}
								labelFormatter={(label: string) =>
									new Date(label).toLocaleDateString()
								}
							/>
							<Line
								yAxisId="score"
								type="monotone"
								dataKey="score"
								stroke="#6366f1"
								strokeWidth={2}
								dot={{ fill: "#6366f1", r: 3 }}
								name="Score"
							/>
							<Line
								yAxisId="hours"
								type="monotone"
								dataKey="productive_hours"
								stroke="#22c55e"
								strokeWidth={2}
								dot={{ fill: "#22c55e", r: 3 }}
								name="Productive (hrs)"
							/>
							<Line
								yAxisId="hours"
								type="monotone"
								dataKey="screen_hours"
								stroke="#f59e0b"
								strokeWidth={2}
								strokeDasharray="5 5"
								dot={{ fill: "#f59e0b", r: 3 }}
								name="Screen Time (hrs)"
							/>
						</LineChart>
					</ResponsiveContainer>
				</div>
			)}
		</div>
	);
}

// ---- Weekly report section ----
function WeeklyReportSection({
	report,
}: { report: ProductivityWeeklyReport }) {
	const trendIcons: Record<string, React.ReactNode> = {
		improving: <ArrowUp className="h-4 w-4 text-emerald-400" />,
		declining: <ArrowDown className="h-4 w-4 text-red-400" />,
		stable: <Minus className="h-4 w-4 text-yellow-400" />,
	};

	const trendColors: Record<string, string> = {
		improving: "text-emerald-400",
		declining: "text-red-400",
		stable: "text-yellow-400",
	};

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<FileText className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Weekly Report
				</h2>
				<div className="ml-auto flex items-center gap-1">
					{trendIcons[report.trend]}
					<span
						className={`text-xs font-medium capitalize ${trendColors[report.trend]}`}
					>
						{report.trend}
					</span>
				</div>
			</div>
			<p className="mb-3 text-xs text-neutral-500">
				{new Date(report.week_start).toLocaleDateString()} &mdash;{" "}
				{new Date(report.week_end).toLocaleDateString()}
			</p>

			{/* Summary stats */}
			<div className="mb-4 grid grid-cols-3 gap-3">
				<div className="rounded-md border border-neutral-800 px-3 py-2 text-center">
					<p className="text-lg font-bold text-neutral-50">
						{formatMinutes(report.total_screen_time_minutes)}
					</p>
					<p className="text-xs text-neutral-500">Screen Time</p>
				</div>
				<div className="rounded-md border border-neutral-800 px-3 py-2 text-center">
					<p className="text-lg font-bold text-neutral-50">
						{formatMinutes(report.total_productive_minutes)}
					</p>
					<p className="text-xs text-neutral-500">Productive</p>
				</div>
				<div className="rounded-md border border-neutral-800 px-3 py-2 text-center">
					<p className="text-lg font-bold text-neutral-50">
						{report.avg_score}
					</p>
					<p className="text-xs text-neutral-500">Avg Score</p>
				</div>
			</div>

			{/* Summary text */}
			<p className="mb-4 text-sm leading-relaxed text-neutral-300">
				{report.summary}
			</p>

			{/* Most used apps */}
			{report.most_used_apps.length > 0 && (
				<div>
					<p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
						Most Used Apps
					</p>
					<div className="space-y-1.5">
						{report.most_used_apps.map((app) => (
							<div
								key={app.name}
								className="flex items-center justify-between text-sm"
							>
								<span className="text-neutral-300">{app.name}</span>
								<span className="text-neutral-500">
									{formatMinutes(app.minutes)}
								</span>
							</div>
						))}
					</div>
				</div>
			)}
		</div>
	);
}

// ---- Main page ----
export default function ProductivityPage() {
	const metricsQuery = useQuery({
		queryKey: ["productivity", "metrics", 7],
		queryFn: () => api.productivity.getMetrics({ days: 7 }),
	});

	const latestQuery = useQuery({
		queryKey: ["productivity", "latest"],
		queryFn: () => api.productivity.getLatest(),
	});

	const weeklyQuery = useQuery({
		queryKey: ["productivity", "weekly-report"],
		queryFn: () => api.productivity.getWeeklyReport(),
	});

	const metrics = metricsQuery.data ?? [];
	const latest = latestQuery.data;
	const loading = metricsQuery.isLoading || latestQuery.isLoading;

	// Aggregate all app usage from latest
	const appUsage = latest?.top_apps ?? [];

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<BarChart3 className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">
					Productivity
				</h1>
			</div>

			{/* Screen time summary */}
			{loading ? (
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					{Array.from({ length: 4 }).map((_, i) => (
						<div
							key={`skel-${i.toString()}`}
							className="animate-pulse rounded-lg border border-neutral-800 bg-neutral-900 p-4"
						>
							<div className="h-4 w-20 rounded bg-neutral-800" />
							<div className="mt-3 h-6 w-28 rounded bg-neutral-800" />
						</div>
					))}
				</div>
			) : (
				<ScreenTimeSummary latest={latest} metrics={metrics} />
			)}

			<div className="grid gap-6 lg:grid-cols-2">
				{/* App usage */}
				{loading ? (
					<SkeletonBlock />
				) : (
					<AppUsageChart apps={appUsage} />
				)}

				{/* Productivity trends */}
				{metricsQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<ProductivityTrendChart data={metrics} />
				)}
			</div>

			{/* Weekly report */}
			{weeklyQuery.isLoading ? (
				<SkeletonBlock />
			) : weeklyQuery.data ? (
				<WeeklyReportSection report={weeklyQuery.data} />
			) : null}
		</div>
	);
}
