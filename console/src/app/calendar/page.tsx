"use client";

import { useQuery } from "@tanstack/react-query";
import {
	CalendarDays,
	Clock,
	MapPin,
	FileText,
	Sun,
	ListChecks,
	ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
	CalendarEvent,
	MeetingTranscription,
	DailyBriefing,
} from "@/lib/api";

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

// ---- Source badge ----
function SourceBadge({ source }: { source: "google" | "outlook" }) {
	const styles: Record<string, string> = {
		google: "bg-blue-900/50 text-blue-400",
		outlook: "bg-cyan-900/50 text-cyan-400",
	};
	const labels: Record<string, string> = {
		google: "Google",
		outlook: "Outlook",
	};
	return (
		<span className={`rounded px-1.5 py-0.5 text-[10px] ${styles[source]}`}>
			{labels[source]}
		</span>
	);
}

// ---- Time formatter ----
function formatTime(iso: string) {
	return new Date(iso).toLocaleTimeString([], {
		hour: "2-digit",
		minute: "2-digit",
	});
}

function formatDateShort(iso: string) {
	return new Date(iso).toLocaleDateString([], {
		weekday: "short",
		month: "short",
		day: "numeric",
	});
}

// ---- Today's timeline ----
function TodayTimeline({ events }: { events: CalendarEvent[] }) {
	const now = new Date();
	const todayStr = now.toISOString().slice(0, 10);
	const todayEvents = events
		.filter((e) => e.start.slice(0, 10) === todayStr)
		.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Clock className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Today&apos;s Schedule
				</h2>
				<span className="ml-auto rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
					{todayEvents.length} events
				</span>
			</div>
			{todayEvents.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No events scheduled for today.
				</p>
			) : (
				<div className="relative space-y-0">
					{/* Vertical line */}
					<div className="absolute left-[27px] top-2 bottom-2 w-px bg-neutral-800" />

					{todayEvents.map((event, idx) => {
						const startDate = new Date(event.start);
						const endDate = new Date(event.end);
						const isPast = endDate < now;
						const isCurrent = startDate <= now && endDate >= now;

						return (
							<div
								key={event.id}
								className="relative flex gap-4 py-2"
							>
								{/* Timeline dot */}
								<div className="flex w-14 shrink-0 flex-col items-center">
									<div
										className={`z-10 h-3 w-3 rounded-full border-2 ${
											isCurrent
												? "border-indigo-500 bg-indigo-500"
												: isPast
													? "border-neutral-600 bg-neutral-700"
													: "border-neutral-500 bg-neutral-900"
										}`}
									/>
								</div>
								{/* Event card */}
								<div
									className={`flex-1 rounded-md border px-3 py-2.5 ${
										isCurrent
											? "border-indigo-800 bg-indigo-950/30"
											: "border-neutral-800"
									} ${isPast ? "opacity-60" : ""}`}
								>
									<div className="flex items-center justify-between gap-2">
										<p className="text-sm font-medium text-neutral-200">
											{event.title}
										</p>
										<SourceBadge source={event.source} />
									</div>
									<p className="mt-0.5 text-xs text-neutral-500">
										{formatTime(event.start)} &ndash;{" "}
										{formatTime(event.end)}
									</p>
									{event.location && (
										<p className="mt-1 flex items-center gap-1 text-xs text-neutral-500">
											<MapPin className="h-3 w-3" />
											{event.location}
										</p>
									)}
								</div>
							</div>
						);
					})}
				</div>
			)}
		</div>
	);
}

// ---- Upcoming events (next 7 days, excluding today) ----
function UpcomingEventsSection({ events }: { events: CalendarEvent[] }) {
	const now = new Date();
	const todayStr = now.toISOString().slice(0, 10);
	const upcoming = events
		.filter((e) => e.start.slice(0, 10) > todayStr)
		.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());

	// Group by date
	const grouped: Record<string, CalendarEvent[]> = {};
	for (const event of upcoming) {
		const dateKey = event.start.slice(0, 10);
		if (!grouped[dateKey]) grouped[dateKey] = [];
		grouped[dateKey].push(event);
	}

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<CalendarDays className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Upcoming (Next 7 Days)
				</h2>
			</div>
			{upcoming.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No upcoming events this week.
				</p>
			) : (
				<div className="space-y-4">
					{Object.entries(grouped).map(([dateKey, dayEvents]) => (
						<div key={dateKey}>
							<p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
								{formatDateShort(dateKey)}
							</p>
							<div className="space-y-2">
								{dayEvents.map((event) => (
									<div
										key={event.id}
										className="flex items-center justify-between rounded-md border border-neutral-800 px-3 py-2"
									>
										<div className="min-w-0 flex-1">
											<div className="flex items-center gap-2">
												<p className="truncate text-sm font-medium text-neutral-200">
													{event.title}
												</p>
												<SourceBadge source={event.source} />
											</div>
											<p className="mt-0.5 text-xs text-neutral-500">
												{formatTime(event.start)} &ndash;{" "}
												{formatTime(event.end)}
												{event.location && (
													<>
														{" "}&middot;{" "}
														{event.location}
													</>
												)}
											</p>
										</div>
										<ChevronRight className="h-4 w-4 shrink-0 text-neutral-600" />
									</div>
								))}
							</div>
						</div>
					))}
				</div>
			)}
		</div>
	);
}

// ---- Meeting transcriptions ----
function TranscriptionsSection({
	transcriptions,
}: { transcriptions: MeetingTranscription[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<FileText className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Recent Meeting Transcriptions
				</h2>
			</div>
			{transcriptions.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No meeting transcriptions available.
				</p>
			) : (
				<div className="space-y-3">
					{transcriptions.map((t) => (
						<div
							key={t.id}
							className="rounded-md border border-neutral-800 px-3 py-3"
						>
							<div className="mb-2 flex items-center justify-between">
								<p className="text-sm font-medium text-neutral-200">
									{t.title}
								</p>
								<span className="text-xs text-neutral-500">
									{new Date(t.date).toLocaleDateString([], {
										month: "short",
										day: "numeric",
									})}{" "}
									&middot; {t.duration_minutes}min
								</span>
							</div>
							<p className="mb-2 text-sm text-neutral-400">
								{t.summary}
							</p>
							{t.key_points.length > 0 && (
								<div className="mb-2">
									<p className="mb-1 text-xs font-semibold text-neutral-500">
										Key Points
									</p>
									<ul className="space-y-0.5">
										{t.key_points.map((point, i) => (
											<li
												key={`kp-${t.id}-${i.toString()}`}
												className="flex items-start gap-1.5 text-xs text-neutral-400"
											>
												<span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-neutral-600" />
												{point}
											</li>
										))}
									</ul>
								</div>
							)}
							{t.action_items.length > 0 && (
								<div>
									<p className="mb-1 text-xs font-semibold text-neutral-500">
										Action Items
									</p>
									<ul className="space-y-0.5">
										{t.action_items.map((item, i) => (
											<li
												key={`ai-${t.id}-${i.toString()}`}
												className="flex items-start gap-1.5 text-xs text-indigo-400"
											>
												<ListChecks className="mt-0.5 h-3 w-3 shrink-0" />
												{item}
											</li>
										))}
									</ul>
								</div>
							)}
						</div>
					))}
				</div>
			)}
		</div>
	);
}

// ---- Daily briefing section ----
function BriefingSection({ briefing }: { briefing: DailyBriefing }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Sun className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Daily Briefing
				</h2>
				<span className="ml-auto text-xs text-neutral-500">
					{new Date(briefing.date).toLocaleDateString([], {
						weekday: "long",
						month: "long",
						day: "numeric",
					})}
				</span>
			</div>
			<p className="mb-4 text-sm leading-relaxed text-neutral-300">
				{briefing.summary}
			</p>

			{/* Quick stats */}
			<div className="mb-4 grid grid-cols-3 gap-3">
				<div className="rounded-md border border-neutral-800 px-3 py-2 text-center">
					<p className="text-lg font-bold text-neutral-50">
						{briefing.calendar_events.length}
					</p>
					<p className="text-xs text-neutral-500">Events</p>
				</div>
				<div className="rounded-md border border-neutral-800 px-3 py-2 text-center">
					<p className="text-lg font-bold text-neutral-50">
						{briefing.email_highlights.length}
					</p>
					<p className="text-xs text-neutral-500">Emails</p>
				</div>
				<div className="rounded-md border border-neutral-800 px-3 py-2 text-center">
					<p className="text-lg font-bold text-neutral-50">
						{briefing.content_status.posts_published_today}
					</p>
					<p className="text-xs text-neutral-500">Posts</p>
				</div>
			</div>

			{/* Action items */}
			{briefing.action_items.length > 0 && (
				<div>
					<p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
						Action Items
					</p>
					<ul className="space-y-1">
						{briefing.action_items.map((item, i) => (
							<li
								key={`action-${i.toString()}`}
								className="flex items-start gap-1.5 text-sm text-neutral-300"
							>
								<ListChecks className="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-400" />
								{item}
							</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
}

// ---- Main page ----
export default function CalendarPage() {
	// Get today + 7 days of events
	const now = new Date();
	const weekFromNow = new Date(now);
	weekFromNow.setDate(weekFromNow.getDate() + 7);

	const eventsQuery = useQuery({
		queryKey: ["calendar", "events"],
		queryFn: () =>
			api.calendar.getEvents({
				start: now.toISOString().slice(0, 10),
				end: weekFromNow.toISOString().slice(0, 10),
			}),
	});

	const transcriptionsQuery = useQuery({
		queryKey: ["calendar", "transcriptions"],
		queryFn: () => api.calendar.getMeetingTranscriptions({ limit: 5 }),
	});

	const briefingQuery = useQuery({
		queryKey: ["briefing", "today"],
		queryFn: () => api.briefing.getToday(),
	});

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<CalendarDays className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">
					Calendar & Meetings
				</h1>
			</div>

			{/* Daily briefing */}
			{briefingQuery.isLoading ? (
				<SkeletonBlock />
			) : briefingQuery.data ? (
				<BriefingSection briefing={briefingQuery.data} />
			) : null}

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Today's timeline */}
				{eventsQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<TodayTimeline events={eventsQuery.data ?? []} />
				)}

				{/* Upcoming events */}
				{eventsQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<UpcomingEventsSection events={eventsQuery.data ?? []} />
				)}
			</div>

			{/* Meeting transcriptions */}
			{transcriptionsQuery.isLoading ? (
				<SkeletonBlock />
			) : (
				<TranscriptionsSection
					transcriptions={transcriptionsQuery.data ?? []}
				/>
			)}
		</div>
	);
}
