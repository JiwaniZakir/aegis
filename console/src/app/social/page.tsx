"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SocialPost, NewsHeadline } from "@/lib/api";
import { Share2, Newspaper, Send, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/page-header";
import { MetricCard } from "@/components/metric-card";
import { MetricCardSkeleton, TableSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";

export default function SocialPage() {
	const [postContent, setPostContent] = useState("");
	const [postPlatforms, setPostPlatforms] = useState<string[]>(["linkedin"]);

	const historyQuery = useQuery({
		queryKey: ["social", "history"],
		queryFn: () => api.social.getHistory({ limit: 20 }),
	});

	const engagementQuery = useQuery({
		queryKey: ["social", "engagement"],
		queryFn: () => api.social.getEngagement(30),
	});

	const newsQuery = useQuery({
		queryKey: ["social", "news"],
		queryFn: () => api.social.getNewsHeadlines({ limit: 10 }),
	});

	const postMutation = useMutation({
		mutationFn: () => api.social.post({ content: postContent, platforms: postPlatforms }),
		onSuccess: () => {
			setPostContent("");
			historyQuery.refetch();
		},
	});

	const posts = historyQuery.data ?? [];
	const engagement = engagementQuery.data as { likes?: number; comments?: number; impressions?: number } | undefined;
	const news = newsQuery.data ?? [];

	function togglePlatform(p: string) {
		setPostPlatforms((prev) =>
			prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
		);
	}

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Social" description="Post, engage, and stay informed" />

			{/* Engagement metrics */}
			<div className="grid gap-4 sm:grid-cols-3">
				{engagementQuery.isLoading ? (
					<>
						<MetricCardSkeleton />
						<MetricCardSkeleton />
						<MetricCardSkeleton />
					</>
				) : engagementQuery.isError ? (
					<div className="sm:col-span-3">
						<QueryError message="Failed to load engagement metrics." onRetry={() => engagementQuery.refetch()} />
					</div>
				) : engagement ? (
					<>
						<MetricCard label="Likes" value={String(engagement.likes ?? 0)} icon={Share2} />
						<MetricCard label="Comments" value={String(engagement.comments ?? 0)} icon={Share2} />
						<MetricCard label="Impressions" value={String(engagement.impressions ?? 0)} icon={Share2} />
					</>
				) : (
					<>
						<MetricCard label="Likes" value="--" icon={Share2} />
						<MetricCard label="Comments" value="--" icon={Share2} />
						<MetricCard label="Impressions" value="--" icon={Share2} />
					</>
				)}
			</div>

			<div className="grid gap-6 lg:grid-cols-3">
				{/* Quick Post + History */}
				<div className="space-y-6 lg:col-span-2">
					{/* Quick Post */}
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<Send className="h-4 w-4 text-muted-foreground" />
								Quick Post
							</CardTitle>
						</CardHeader>
						<CardContent>
							<div className="space-y-3">
								<textarea
									placeholder="What's on your mind?"
									value={postContent}
									onChange={(e) => setPostContent(e.target.value)}
									className="w-full resize-none rounded-lg border bg-transparent p-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
									rows={3}
								/>
								<div className="flex items-center justify-between">
									<div className="flex gap-2">
										{["linkedin", "x"].map((p) => (
											<Button
												key={p}
												variant={postPlatforms.includes(p) ? "default" : "outline"}
												size="sm"
												onClick={() => togglePlatform(p)}
											>
												{p === "linkedin" ? "LinkedIn" : "X"}
											</Button>
										))}
									</div>
									<Button
										size="sm"
										disabled={!postContent.trim() || postPlatforms.length === 0 || postMutation.isPending}
										onClick={() => postMutation.mutate()}
									>
										{postMutation.isPending ? "Posting..." : "Post"}
									</Button>
								</div>
							</div>
						</CardContent>
					</Card>

					{/* Post History */}
					{historyQuery.isLoading ? (
						<TableSkeleton rows={5} />
					) : historyQuery.isError ? (
						<QueryError message="Failed to load post history." onRetry={() => historyQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="text-base">Post History</CardTitle>
							</CardHeader>
							<CardContent>
								{posts.length === 0 ? (
									<p className="py-6 text-center text-sm text-muted-foreground">No posts yet.</p>
								) : (
									<div className="space-y-0">
										{posts.map((post: SocialPost, index: number) => (
											<div key={post.id}>
												{index > 0 && <Separator className="my-0" />}
												<div className="py-3">
													<div className="flex items-center gap-2 mb-1">
														<Badge variant="outline">{post.platform}</Badge>
														<span className="text-xs text-muted-foreground">
															{new Date(post.posted_at).toLocaleDateString([], { month: "short", day: "numeric" })}
														</span>
													</div>
													<p className="text-sm line-clamp-2">{post.content}</p>
													<div className="mt-2 flex gap-4 text-xs text-muted-foreground">
														<span>{post.likes} likes</span>
														<span>{post.comments} comments</span>
														<span>{post.impressions} impressions</span>
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

				{/* News */}
				<div>
					{newsQuery.isLoading ? (
						<TableSkeleton rows={5} />
					) : newsQuery.isError ? (
						<QueryError message="Failed to load news headlines." onRetry={() => newsQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2 text-base">
									<Newspaper className="h-4 w-4 text-muted-foreground" />
									News Headlines
								</CardTitle>
							</CardHeader>
							<CardContent>
								{news.length === 0 ? (
									<p className="py-6 text-center text-sm text-muted-foreground">No news available.</p>
								) : (
									<div className="space-y-0">
										{news.map((headline: NewsHeadline, index: number) => (
											<div key={headline.id}>
												{index > 0 && <Separator className="my-0" />}
												<div className="py-3">
													<p className="text-sm font-medium leading-snug">{headline.title}</p>
													<div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
														<span>{headline.source}</span>
														<span>·</span>
														<span>{new Date(headline.published_at).toLocaleDateString([], { month: "short", day: "numeric" })}</span>
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
			</div>
		</div>
	);
}
