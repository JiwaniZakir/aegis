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
import { Heart, Footprints, Moon, Brain } from "lucide-react";
import { api } from "@/lib/api";
import type { HealthMetrics, HealthGoals } from "@/lib/api";

function MacroProgressBar({
	label,
	current,
	target,
	unit,
	color,
}: {
	label: string;
	current: number;
	target: number;
	unit: string;
	color: string;
}) {
	const pct = Math.min((current / target) * 100, 100);
	const isOver = current > target;

	return (
		<div>
			<div className="mb-1 flex items-center justify-between text-sm">
				<span className="text-neutral-300">{label}</span>
				<span className={isOver ? "text-red-400" : "text-neutral-400"}>
					{current.toLocaleString()} / {target.toLocaleString()} {unit}
				</span>
			</div>
			<div className="h-2.5 overflow-hidden rounded-full bg-neutral-800">
				<div
					className="h-full rounded-full transition-all duration-500"
					style={{
						width: `${pct}%`,
						backgroundColor: isOver ? "#ef4444" : color,
					}}
				/>
			</div>
		</div>
	);
}

function StepChart({ data }: { data: HealthMetrics[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Footprints className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Steps (7 Days)
				</h2>
			</div>
			<div className="h-56">
				<ResponsiveContainer width="100%" height="100%">
					<BarChart data={data}>
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
							stroke="#525252"
							tick={{ fill: "#737373", fontSize: 12 }}
						/>
						<Tooltip
							contentStyle={{
								backgroundColor: "#171717",
								border: "1px solid #262626",
								borderRadius: "8px",
								color: "#e5e5e5",
							}}
							formatter={(value: number) => [
								value.toLocaleString(),
								"Steps",
							]}
							labelFormatter={(label: string) =>
								new Date(label).toLocaleDateString()
							}
						/>
						<Bar
							dataKey="steps"
							fill="#22c55e"
							radius={[4, 4, 0, 0]}
						/>
					</BarChart>
				</ResponsiveContainer>
			</div>
		</div>
	);
}

function SleepChart({ data }: { data: HealthMetrics[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Moon className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Sleep (7 Days)
				</h2>
			</div>
			<div className="h-56">
				<ResponsiveContainer width="100%" height="100%">
					<LineChart data={data}>
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
							stroke="#525252"
							tick={{ fill: "#737373", fontSize: 12 }}
							domain={[0, 12]}
							tickFormatter={(v: number) => `${v}h`}
						/>
						<Tooltip
							contentStyle={{
								backgroundColor: "#171717",
								border: "1px solid #262626",
								borderRadius: "8px",
								color: "#e5e5e5",
							}}
							formatter={(value: number) => [
								`${value.toFixed(1)}h`,
								"Sleep",
							]}
							labelFormatter={(label: string) =>
								new Date(label).toLocaleDateString()
							}
						/>
						<Line
							type="monotone"
							dataKey="sleep_hours"
							stroke="#8b5cf6"
							strokeWidth={2}
							dot={{ fill: "#8b5cf6", r: 3 }}
						/>
					</LineChart>
				</ResponsiveContainer>
			</div>
		</div>
	);
}

function ProductivityScoreCard({
	score,
}: { score: number | undefined }) {
	const displayScore = score ?? 0;
	const getColor = (s: number) => {
		if (s >= 80) return "text-emerald-400";
		if (s >= 60) return "text-yellow-400";
		return "text-red-400";
	};

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-3 flex items-center gap-2">
				<Brain className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Productivity Score
				</h2>
			</div>
			<div className="flex items-center justify-center py-6">
				<span
					className={`text-5xl font-bold ${getColor(displayScore)}`}
				>
					{displayScore}
				</span>
				<span className="ml-1 text-lg text-neutral-500">/100</span>
			</div>
		</div>
	);
}

function SkeletonBlock() {
	return (
		<div className="animate-pulse rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="h-5 w-40 rounded bg-neutral-800" />
			<div className="mt-4 h-48 rounded bg-neutral-800" />
		</div>
	);
}

export default function HealthPage() {
	const metricsQuery = useQuery({
		queryKey: ["health", "metrics", 7],
		queryFn: () => api.health.getMetrics({ days: 7 }),
	});

	const goalsQuery = useQuery({
		queryKey: ["health", "goals"],
		queryFn: () => api.health.getGoals(),
	});

	const latestQuery = useQuery({
		queryKey: ["health", "latest"],
		queryFn: () => api.health.getLatest(),
	});

	const productivityQuery = useQuery({
		queryKey: ["productivity", "latest"],
		queryFn: () => api.productivity.getLatest(),
	});

	const latest = latestQuery.data;
	const goals = goalsQuery.data;
	const metrics = metricsQuery.data ?? [];
	const loading = metricsQuery.isLoading || goalsQuery.isLoading;

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<Heart className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">Health</h1>
			</div>

			{/* Macro tracking */}
			{loading ? (
				<SkeletonBlock />
			) : latest && goals ? (
				<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
					<h2 className="mb-4 text-lg font-semibold text-neutral-100">
						Today&apos;s Macros
					</h2>
					<div className="space-y-4">
						<MacroProgressBar
							label="Calories"
							current={latest.calories_consumed}
							target={goals.daily_calorie_limit}
							unit="kcal"
							color="#f59e0b"
						/>
						<MacroProgressBar
							label="Protein"
							current={latest.protein_g}
							target={goals.daily_protein_target_g}
							unit="g"
							color="#22c55e"
						/>
						<MacroProgressBar
							label="Steps"
							current={latest.steps}
							target={goals.daily_step_goal}
							unit=""
							color="#6366f1"
						/>
						<MacroProgressBar
							label="Sleep"
							current={latest.sleep_hours}
							target={goals.sleep_target_hours}
							unit="hrs"
							color="#8b5cf6"
						/>
					</div>
				</div>
			) : (
				<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-8 text-center">
					<p className="text-sm text-neutral-500">
						No health data available yet.
					</p>
				</div>
			)}

			{/* Charts */}
			<div className="grid gap-6 lg:grid-cols-2">
				{metricsQuery.isLoading ? (
					<>
						<SkeletonBlock />
						<SkeletonBlock />
					</>
				) : (
					<>
						{metrics.length > 0 && <StepChart data={metrics} />}
						{metrics.length > 0 && <SleepChart data={metrics} />}
					</>
				)}
			</div>

			{/* Productivity score */}
			<div className="grid gap-6 lg:grid-cols-3">
				<ProductivityScoreCard
					score={productivityQuery.data?.score}
				/>
				{latest && (
					<>
						<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
							<h3 className="mb-2 text-sm font-semibold text-neutral-200">
								Heart Rate (Avg)
							</h3>
							<p className="text-3xl font-bold text-neutral-50">
								{latest.heart_rate_avg}{" "}
								<span className="text-lg text-neutral-500">
									bpm
								</span>
							</p>
						</div>
						<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
							<h3 className="mb-2 text-sm font-semibold text-neutral-200">
								Sleep Quality
							</h3>
							<p className="text-3xl font-bold text-neutral-50">
								{latest.sleep_quality}
								<span className="text-lg text-neutral-500">
									%
								</span>
							</p>
						</div>
					</>
				)}
			</div>
		</div>
	);
}
