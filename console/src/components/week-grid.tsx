"use client";

import type { CalendarEvent } from "@/lib/api";
import { MapPin } from "lucide-react";

interface WeekGridProps {
	events: CalendarEvent[];
}

function startOfWeek(date: Date): Date {
	const d = new Date(date);
	const day = d.getDay();
	// Shift so Monday = 0
	const diff = (day + 6) % 7;
	d.setDate(d.getDate() - diff);
	d.setHours(0, 0, 0, 0);
	return d;
}

function isSameDay(a: Date, b: Date): boolean {
	return (
		a.getFullYear() === b.getFullYear() &&
		a.getMonth() === b.getMonth() &&
		a.getDate() === b.getDate()
	);
}

const SOURCE_COLORS: Record<string, string> = {
	google: "bg-blue-500/15 border-blue-500/25 text-blue-700 dark:text-blue-400",
	outlook: "bg-violet-500/15 border-violet-500/25 text-violet-700 dark:text-violet-400",
};

export function WeekGrid({ events }: WeekGridProps) {
	const today = new Date();
	const monday = startOfWeek(today);

	const days = Array.from({ length: 7 }, (_, i) => {
		const d = new Date(monday);
		d.setDate(monday.getDate() + i);
		return d;
	});

	// Group events by day
	const eventsByDay = new Map<number, CalendarEvent[]>();
	for (const day of days) {
		eventsByDay.set(day.getDate(), []);
	}
	for (const event of events) {
		const eventDate = new Date(event.start);
		for (const day of days) {
			if (isSameDay(eventDate, day)) {
				eventsByDay.get(day.getDate())?.push(event);
				break;
			}
		}
	}

	// Sort events within each day by start time
	for (const [key, dayEvents] of eventsByDay) {
		eventsByDay.set(
			key,
			dayEvents.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime()),
		);
	}

	return (
		<div className="grid grid-cols-7 gap-px rounded-lg border bg-border overflow-hidden">
			{days.map((day) => {
				const isToday = isSameDay(day, today);
				const dayEvents = eventsByDay.get(day.getDate()) ?? [];

				return (
					<div
						key={day.toISOString()}
						className={`flex min-h-[220px] flex-col bg-card p-2 ${isToday ? "bg-accent/40" : ""}`}
					>
						{/* Day header */}
						<div className="mb-2 flex items-baseline gap-1">
							<span className="text-xs font-medium text-muted-foreground">
								{day.toLocaleDateString([], { weekday: "short" })}
							</span>
							<span
								className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
									isToday
										? "bg-primary text-primary-foreground"
										: "text-foreground"
								}`}
							>
								{day.getDate()}
							</span>
						</div>

						{/* Events */}
						<div className="flex flex-1 flex-col gap-1">
							{dayEvents.length === 0 && (
								<p className="mt-2 text-center text-[10px] text-muted-foreground/60">
									No events
								</p>
							)}
							{dayEvents.map((event) => {
								const start = new Date(event.start);
								const end = new Date(event.end);
								const colorClass =
									SOURCE_COLORS[event.source] ??
									"bg-muted border-border text-foreground";

								return (
									<div
										key={event.id}
										className={`rounded-md border px-1.5 py-1 ${colorClass}`}
									>
										<p className="truncate text-[11px] font-medium leading-tight">
											{event.title}
										</p>
										<p className="text-[10px] tabular-nums opacity-75">
											{start.toLocaleTimeString([], {
												hour: "2-digit",
												minute: "2-digit",
											})}
											{" - "}
											{end.toLocaleTimeString([], {
												hour: "2-digit",
												minute: "2-digit",
											})}
										</p>
										{event.location && (
											<p className="flex items-center gap-0.5 truncate text-[10px] opacity-60">
												<MapPin className="h-2.5 w-2.5 shrink-0" />
												{event.location}
											</p>
										)}
									</div>
								);
							})}
						</div>
					</div>
				);
			})}
		</div>
	);
}
