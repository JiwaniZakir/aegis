"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CalendarEvent } from "@/lib/api";
import { CalendarDays, Clock, LayoutGrid, List, MapPin } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";
import { WeekGrid } from "@/components/week-grid";

function groupByDate(events: CalendarEvent[]) {
	const groups: Record<string, CalendarEvent[]> = {};
	for (const event of events) {
		const date = new Date(event.start).toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
		if (!groups[date]) groups[date] = [];
		groups[date].push(event);
	}
	return groups;
}

export default function CalendarPage() {
	const [view, setView] = useState<"list" | "week">("list");

	const todayQuery = useQuery({
		queryKey: ["calendar", "today"],
		queryFn: () => api.calendar.getTodayEvents(),
	});

	const eventsQuery = useQuery({
		queryKey: ["calendar", "events", 7],
		queryFn: () => api.calendar.getEvents({ days: 7 }),
	});

	const todayEvents = todayQuery.data ?? [];
	const upcomingEvents = eventsQuery.data?.events ?? [];
	const grouped = groupByDate(upcomingEvents);
	const now = new Date();

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-start justify-between">
				<PageHeader title="Calendar" description="Today's schedule and upcoming events" />
				<div className="flex items-center gap-1">
					<Button
						variant={view === "list" ? "default" : "ghost"}
						size="sm"
						onClick={() => setView("list")}
					>
						<List className="h-4 w-4 mr-1" />
						List
					</Button>
					<Button
						variant={view === "week" ? "default" : "ghost"}
						size="sm"
						onClick={() => setView("week")}
					>
						<LayoutGrid className="h-4 w-4 mr-1" />
						Week
					</Button>
				</div>
			</div>

			{/* Week grid view */}
			{view === "week" && (
				eventsQuery.isLoading ? (
					<TableSkeleton rows={6} />
				) : eventsQuery.isError ? (
					<QueryError message="Failed to load calendar events." onRetry={() => eventsQuery.refetch()} />
				) : (
					<WeekGrid events={upcomingEvents} />
				)
			)}

			{/* List view: Today's schedule + Upcoming events */}
			{view === "list" && (
				<>
					{/* Today's schedule */}
					{todayQuery.isLoading ? (
						<TableSkeleton rows={4} />
					) : todayQuery.isError ? (
						<QueryError message="Failed to load today's events." onRetry={() => todayQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2 text-base">
									<CalendarDays className="h-4 w-4 text-muted-foreground" />
									Today&apos;s Schedule
									<Badge variant="secondary" className="ml-auto">{todayEvents.length} events</Badge>
								</CardTitle>
							</CardHeader>
							<CardContent>
								{todayEvents.length === 0 ? (
									<p className="py-6 text-center text-sm text-muted-foreground">No events today.</p>
								) : (
									<div className="space-y-1">
										{todayEvents.map((event) => {
											const start = new Date(event.start);
											const end = new Date(event.end);
											const isPast = end < now;
											const isCurrent = start <= now && end >= now;
											return (
												<div
													key={event.id}
													className={`flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted ${
														isCurrent ? "bg-accent border border-border" : isPast ? "opacity-50" : ""
													}`}
												>
													<div className={`h-2 w-2 shrink-0 rounded-full ${isCurrent ? "bg-emerald-500 animate-pulse" : isPast ? "bg-muted-foreground" : "bg-blue-500"}`} />
													<div className="min-w-0 flex-1">
														<p className="truncate text-sm font-medium">{event.title}</p>
														{event.location && (
															<p className="flex items-center gap-1 text-xs text-muted-foreground">
																<MapPin className="h-3 w-3" />
																{event.location}
															</p>
														)}
													</div>
													<div className="flex shrink-0 items-center gap-2">
														<Badge variant="outline" className="text-[10px]">{event.source}</Badge>
														<span className="text-xs tabular-nums text-muted-foreground">
															{start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
															{" - "}
															{end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
														</span>
													</div>
												</div>
											);
										})}
									</div>
								)}
							</CardContent>
						</Card>
					)}

					{/* Upcoming events */}
					{eventsQuery.isLoading ? (
						<TableSkeleton rows={6} />
					) : eventsQuery.isError ? (
						<QueryError message="Failed to load upcoming events." onRetry={() => eventsQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2 text-base">
									<Clock className="h-4 w-4 text-muted-foreground" />
									Next 7 Days
								</CardTitle>
							</CardHeader>
							<CardContent>
								{upcomingEvents.length === 0 ? (
									<p className="py-6 text-center text-sm text-muted-foreground">No upcoming events.</p>
								) : (
									<div className="space-y-4">
										{Object.entries(grouped).map(([date, events]) => (
											<div key={date}>
												<p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">{date}</p>
												<div className="space-y-1">
													{events.map((event) => (
														<div key={event.id} className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-muted">
															<Clock className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
															<div className="min-w-0 flex-1">
																<p className="truncate text-sm font-medium">{event.title}</p>
																{event.location && (
																	<p className="text-xs text-muted-foreground">{event.location}</p>
																)}
															</div>
															<span className="shrink-0 text-xs tabular-nums text-muted-foreground">
																{new Date(event.start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
															</span>
														</div>
													))}
												</div>
											</div>
										))}
									</div>
								)}
							</CardContent>
						</Card>
					)}
				</>
			)}
		</div>
	);
}
