"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ContentDraft } from "@/lib/api";
import { FileText, Sparkles, Send, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";

export default function ContentPage() {
	const queryClient = useQueryClient();
	const [topic, setTopic] = useState("");
	const [platform, setPlatform] = useState<"linkedin" | "x">("linkedin");
	const [tone, setTone] = useState("professional");

	const draftsQuery = useQuery({
		queryKey: ["content", "drafts"],
		queryFn: () => api.content.getDrafts(),
	});

	const generateMutation = useMutation({
		mutationFn: () => api.content.generate({ topic, platform, tone }),
		onSuccess: () => {
			setTopic("");
			queryClient.invalidateQueries({ queryKey: ["content", "drafts"] });
		},
	});

	const publishMutation = useMutation({
		mutationFn: (postId: string) => api.content.publishDraft(postId),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["content", "drafts"] });
		},
	});

	const drafts = draftsQuery.data ?? [];
	const draftItems = drafts.filter((d: ContentDraft) => d.status === "draft");
	const scheduled = drafts.filter((d: ContentDraft) => d.status === "scheduled");
	const published = drafts.filter((d: ContentDraft) => d.status === "published");

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Content" description="Generate and publish thought-leadership posts" />

			<div className="grid gap-6 lg:grid-cols-3">
				{/* Generate form */}
				<div>
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<Sparkles className="h-4 w-4 text-muted-foreground" />
								Generate Post
							</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="space-y-4">
								<div className="space-y-2">
									<Label htmlFor="topic">Topic</Label>
									<Input
										id="topic"
										placeholder="e.g. AI in fintech"
										value={topic}
										onChange={(e) => setTopic(e.target.value)}
									/>
								</div>
								<div className="space-y-2">
									<Label>Platform</Label>
									<div className="flex gap-2">
										{(["linkedin", "x"] as const).map((p) => (
											<Button
												key={p}
												variant={platform === p ? "default" : "outline"}
												size="sm"
												onClick={() => setPlatform(p)}
											>
												{p === "linkedin" ? "LinkedIn" : "X"}
											</Button>
										))}
									</div>
								</div>
								<div className="space-y-2">
									<Label>Tone</Label>
									<div className="flex flex-wrap gap-2">
										{["professional", "casual", "thought_leader"].map((t) => (
											<Button
												key={t}
												variant={tone === t ? "default" : "outline"}
												size="sm"
												onClick={() => setTone(t)}
											>
												{t.replace("_", " ")}
											</Button>
										))}
									</div>
								</div>
								<Button
									className="w-full"
									disabled={!topic.trim() || generateMutation.isPending}
									onClick={() => generateMutation.mutate()}
								>
									{generateMutation.isPending ? "Generating..." : "Generate"}
								</Button>
								{generateMutation.isError && (
									<p className="text-sm text-destructive">
										{(generateMutation.error as Error).message}
									</p>
								)}
							</div>
						</CardContent>
					</Card>
				</div>

				{/* Drafts */}
				<div className="lg:col-span-2">
					{draftsQuery.isLoading ? (
						<TableSkeleton rows={4} />
					) : draftsQuery.isError ? (
						<QueryError message="Failed to load content drafts." onRetry={() => draftsQuery.refetch()} />
					) : (
						<div className="space-y-6">
							{/* Draft items */}
							{draftItems.length > 0 && (
								<Card>
									<CardHeader>
										<CardTitle className="flex items-center gap-2 text-base">
											<FileText className="h-4 w-4 text-muted-foreground" />
											Drafts
											<Badge variant="secondary" className="ml-auto">{draftItems.length}</Badge>
										</CardTitle>
									</CardHeader>
									<CardContent>
										<div className="space-y-0">
											{draftItems.map((draft: ContentDraft, index: number) => (
												<div key={draft.id}>
													{index > 0 && <Separator className="my-0" />}
													<div className="py-3">
														<div className="flex items-center gap-2 mb-1">
															<Badge variant="outline">{draft.platform}</Badge>
															<Badge variant="secondary">{draft.tone}</Badge>
															<span className="text-xs text-muted-foreground">
																{new Date(draft.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
															</span>
														</div>
														<p className="text-sm font-medium mb-1">{draft.topic}</p>
														<p className="text-sm text-muted-foreground line-clamp-2">{draft.content}</p>
														<Button
															size="sm"
															variant="outline"
															className="mt-2"
															disabled={publishMutation.isPending}
															onClick={() => publishMutation.mutate(draft.id)}
														>
															<Send className="mr-1 h-3 w-3" />
															Publish
														</Button>
													</div>
												</div>
											))}
										</div>
									</CardContent>
								</Card>
							)}

							{/* Scheduled */}
							{scheduled.length > 0 && (
								<Card>
									<CardHeader>
										<CardTitle className="flex items-center gap-2 text-base">
											<Clock className="h-4 w-4 text-muted-foreground" />
											Scheduled
											<Badge variant="secondary" className="ml-auto">{scheduled.length}</Badge>
										</CardTitle>
									</CardHeader>
									<CardContent>
										<div className="space-y-0">
											{scheduled.map((draft: ContentDraft, index: number) => (
												<div key={draft.id}>
													{index > 0 && <Separator className="my-0" />}
													<div className="py-3">
														<div className="flex items-center gap-2 mb-1">
															<Badge variant="outline">{draft.platform}</Badge>
															{draft.scheduled_for && (
																<span className="text-xs text-muted-foreground">
																	Scheduled for {new Date(draft.scheduled_for).toLocaleDateString()}
																</span>
															)}
														</div>
														<p className="text-sm line-clamp-2">{draft.content}</p>
													</div>
												</div>
											))}
										</div>
									</CardContent>
								</Card>
							)}

							{/* Published */}
							{published.length > 0 && (
								<Card>
									<CardHeader>
										<CardTitle className="text-base">Published ({published.length})</CardTitle>
									</CardHeader>
									<CardContent>
										<div className="space-y-0">
											{published.slice(0, 5).map((draft: ContentDraft, index: number) => (
												<div key={draft.id}>
													{index > 0 && <Separator className="my-0" />}
													<div className="py-3">
														<div className="flex items-center gap-2 mb-1">
															<Badge variant="outline">{draft.platform}</Badge>
															<span className="text-xs text-muted-foreground">
																{new Date(draft.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
															</span>
														</div>
														<p className="text-sm line-clamp-2 text-muted-foreground">{draft.content}</p>
													</div>
												</div>
											))}
										</div>
									</CardContent>
								</Card>
							)}

							{drafts.length === 0 && (
								<Card>
									<CardContent className="flex items-center justify-center py-12">
										<p className="text-sm text-muted-foreground">No content yet. Generate your first post.</p>
									</CardContent>
								</Card>
							)}
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
