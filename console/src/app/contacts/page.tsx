"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { Users, UserPlus, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";

const NetworkGraph = dynamic(
	() => import("@/components/network-graph").then((m) => ({ default: m.NetworkGraph })),
	{ ssr: false },
);

export default function ContactsPage() {
	const [centerId, setCenterId] = useState("");

	const outreachQuery = useQuery({
		queryKey: ["contacts", "outreach"],
		queryFn: () => api.contacts.getSuggestOutreach(10),
	});

	const graphQuery = useQuery({
		queryKey: ["contacts", "graph", centerId],
		queryFn: () => api.contacts.getGraph(centerId, 2),
		enabled: !!centerId,
	});

	const outreach = outreachQuery.data ?? [];

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Contacts" description="Relationship graph and outreach suggestions" />

			<div className="grid gap-6 lg:grid-cols-3">
				{/* Outreach suggestions */}
				<div className="lg:col-span-2">
					{outreachQuery.isLoading ? (
						<TableSkeleton rows={6} />
					) : outreachQuery.isError ? (
						<QueryError message="Failed to load outreach suggestions." onRetry={() => outreachQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2 text-base">
									<UserPlus className="h-4 w-4 text-muted-foreground" />
									Outreach Suggestions
								</CardTitle>
							</CardHeader>
							<CardContent>
								{outreach.length === 0 ? (
									<p className="py-6 text-center text-sm text-muted-foreground">
										No outreach suggestions at this time.
									</p>
								) : (
									<div className="space-y-0">
										{outreach.map((contact, index) => (
											<div key={contact.id}>
												{index > 0 && <Separator className="my-0" />}
												<div
													className="flex items-center gap-3 py-3 cursor-pointer rounded-lg px-2 transition-colors hover:bg-muted"
													onClick={() => setCenterId(contact.id)}
												>
													<div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium">
														{contact.name.charAt(0).toUpperCase()}
													</div>
													<div className="min-w-0 flex-1">
														<p className="truncate text-sm font-medium">{contact.name}</p>
														<p className="text-xs text-muted-foreground">
															{contact.relationship}
															{contact.email && ` · ${contact.email}`}
														</p>
													</div>
													<div className="flex shrink-0 flex-col items-end gap-1">
														<Badge variant="secondary" className="text-[10px]">
															{contact.interaction_count} interactions
														</Badge>
														<span className="flex items-center gap-1 text-[10px] text-muted-foreground">
															<Clock className="h-3 w-3" />
															{contact.last_contact
																? new Date(contact.last_contact).toLocaleDateString([], { month: "short", day: "numeric" })
																: "Never"}
														</span>
													</div>
												</div>
											</div>
										))}
									</div>
								)}
							</CardContent>
						</Card>
					)}
				</div>

				{/* Graph viewer */}
				<div>
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<Users className="h-4 w-4 text-muted-foreground" />
								Network Graph
							</CardTitle>
						</CardHeader>
						<CardContent>
							{graphQuery.isError ? (
								<QueryError message="Failed to load network graph." onRetry={() => graphQuery.refetch()} />
							) : centerId && graphQuery.data ? (
								<div className="space-y-3">
									<p className="text-xs text-muted-foreground">
										{graphQuery.data.nodes?.length ?? 0} nodes · {graphQuery.data.edges?.length ?? 0} edges
									</p>
									<NetworkGraph
										nodes={graphQuery.data.nodes ?? []}
										edges={graphQuery.data.edges ?? []}
									/>
								</div>
							) : (
								<p className="py-6 text-center text-sm text-muted-foreground">
									Select a contact to view their network graph.
								</p>
							)}
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
