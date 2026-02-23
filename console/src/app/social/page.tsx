"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
	BarChart,
	Bar,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	Legend,
} from "recharts";
import {
	Share2,
	Send,
	TrendingUp,
	Newspaper,
	Loader2,
	ExternalLink,
	ThumbsUp,
	MessageSquare,
	Eye,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
	SocialPost,
	EngagementMetrics,
	NewsHeadline,
	QuickPostRequest,
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

// ---- Platform badge ----
function PlatformBadge({ platform }: { platform: "linkedin" | "x" }) {
	const styles: Record<string, string> = {
		linkedin: "bg-blue-900/50 text-blue-400",
		x: "bg-neutral-800 text-neutral-300",
	};
	const labels: Record<string, string> = {
		linkedin: "LinkedIn",
		x: "X",
	};
	return (
		<span className={`rounded px-2 py-0.5 text-xs ${styles[platform]}`}>
			{labels[platform]}
		</span>
	);
}

// ---- Post history list ----
function PostHistorySection({ posts }: { posts: SocialPost[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Share2 className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Post History
				</h2>
				<span className="ml-auto rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
					{posts.length} posts
				</span>
			</div>
			{posts.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No posts yet. Create one below.
				</p>
			) : (
				<div className="space-y-3">
					{posts.map((post) => (
						<div
							key={post.id}
							className="rounded-md border border-neutral-800 px-3 py-3"
						>
							<div className="mb-2 flex items-center justify-between">
								<PlatformBadge platform={post.platform} />
								<span className="text-xs text-neutral-500">
									{new Date(post.posted_at).toLocaleDateString([], {
										month: "short",
										day: "numeric",
										hour: "2-digit",
										minute: "2-digit",
									})}
								</span>
							</div>
							<p className="line-clamp-3 text-sm text-neutral-300">
								{post.content}
							</p>
							<div className="mt-2 flex items-center gap-4 text-xs text-neutral-500">
								<span className="flex items-center gap-1">
									<ThumbsUp className="h-3 w-3" />
									{post.likes.toLocaleString()}
								</span>
								<span className="flex items-center gap-1">
									<MessageSquare className="h-3 w-3" />
									{post.comments.toLocaleString()}
								</span>
								<span className="flex items-center gap-1">
									<Eye className="h-3 w-3" />
									{post.impressions.toLocaleString()}
								</span>
							</div>
						</div>
					))}
				</div>
			)}
		</div>
	);
}

// ---- Engagement chart ----
function EngagementChart({ data }: { data: EngagementMetrics[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<TrendingUp className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Engagement (30 Days)
				</h2>
			</div>
			{data.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No engagement data yet.
				</p>
			) : (
				<div className="h-64">
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
										month: "short",
										day: "numeric",
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
								labelFormatter={(label: string) =>
									new Date(label).toLocaleDateString()
								}
							/>
							<Legend
								wrapperStyle={{ color: "#a3a3a3", fontSize: 12 }}
							/>
							<Bar
								dataKey="likes"
								fill="#6366f1"
								radius={[2, 2, 0, 0]}
							/>
							<Bar
								dataKey="comments"
								fill="#22c55e"
								radius={[2, 2, 0, 0]}
							/>
							<Bar
								dataKey="impressions"
								fill="#f59e0b"
								radius={[2, 2, 0, 0]}
							/>
						</BarChart>
					</ResponsiveContainer>
				</div>
			)}
		</div>
	);
}

// ---- Quick post form ----
function QuickPostForm({
	onPost,
	isPending,
}: {
	onPost: (req: QuickPostRequest) => void;
	isPending: boolean;
}) {
	const [content, setContent] = useState("");
	const [platforms, setPlatforms] = useState<Set<"linkedin" | "x">>(
		new Set(["linkedin"]),
	);

	const togglePlatform = (p: "linkedin" | "x") => {
		setPlatforms((prev) => {
			const next = new Set(prev);
			if (next.has(p)) {
				if (next.size > 1) next.delete(p);
			} else {
				next.add(p);
			}
			return next;
		});
	};

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (!content.trim()) return;
		onPost({ content: content.trim(), platforms: Array.from(platforms) });
		setContent("");
	};

	return (
		<form
			onSubmit={handleSubmit}
			className="rounded-lg border border-neutral-800 bg-neutral-900 p-5"
		>
			<div className="mb-4 flex items-center gap-2">
				<Send className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Quick Post
				</h2>
			</div>
			<div className="space-y-4">
				<div>
					<label
						htmlFor="post-content"
						className="mb-1 block text-sm text-neutral-400"
					>
						Content
					</label>
					<textarea
						id="post-content"
						rows={4}
						value={content}
						onChange={(e) => setContent(e.target.value)}
						placeholder="What's on your mind?"
						className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
					/>
					<p className="mt-1 text-right text-xs text-neutral-500">
						{content.length} / 280
					</p>
				</div>
				<div>
					<p className="mb-2 text-sm text-neutral-400">
						Post to:
					</p>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => togglePlatform("linkedin")}
							className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
								platforms.has("linkedin")
									? "bg-blue-900/50 text-blue-400 ring-1 ring-blue-800"
									: "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
							}`}
						>
							LinkedIn
						</button>
						<button
							type="button"
							onClick={() => togglePlatform("x")}
							className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
								platforms.has("x")
									? "bg-neutral-700 text-neutral-200 ring-1 ring-neutral-600"
									: "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
							}`}
						>
							X (Twitter)
						</button>
					</div>
				</div>
				<button
					type="submit"
					disabled={isPending || !content.trim()}
					className="flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{isPending ? (
						<Loader2 className="h-4 w-4 animate-spin" />
					) : (
						<Send className="h-4 w-4" />
					)}
					Post
				</button>
			</div>
		</form>
	);
}

// ---- News headlines ----
function NewsFeedSection({ headlines }: { headlines: NewsHeadline[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Newspaper className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					News Headlines
				</h2>
			</div>
			{headlines.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No news articles available.
				</p>
			) : (
				<div className="space-y-3">
					{headlines.map((headline) => (
						<a
							key={headline.id}
							href={headline.url}
							target="_blank"
							rel="noopener noreferrer"
							className="group block rounded-md border border-neutral-800 px-3 py-2.5 transition-colors hover:border-neutral-700 hover:bg-neutral-800/50"
						>
							<div className="flex items-start justify-between gap-2">
								<div className="min-w-0 flex-1">
									<p className="text-sm font-medium text-neutral-200 group-hover:text-neutral-100">
										{headline.title}
									</p>
									<p className="mt-0.5 text-xs text-neutral-500">
										{headline.source} &middot;{" "}
										{new Date(headline.published_at).toLocaleDateString([], {
											month: "short",
											day: "numeric",
										})}
									</p>
									<p className="mt-1 line-clamp-2 text-xs text-neutral-400">
										{headline.summary}
									</p>
								</div>
								<ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0 text-neutral-600 group-hover:text-neutral-400" />
							</div>
						</a>
					))}
				</div>
			)}
		</div>
	);
}

// ---- Main page ----
export default function SocialPage() {
	const queryClient = useQueryClient();

	const postsQuery = useQuery({
		queryKey: ["social", "posts"],
		queryFn: () => api.social.getPosts({ limit: 20 }),
	});

	const engagementQuery = useQuery({
		queryKey: ["social", "engagement"],
		queryFn: () => api.social.getEngagementMetrics(30),
	});

	const newsQuery = useQuery({
		queryKey: ["social", "news"],
		queryFn: () => api.social.getNewsHeadlines({ limit: 10 }),
	});

	const postMutation = useMutation({
		mutationFn: (req: QuickPostRequest) => api.social.quickPost(req),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["social", "posts"] });
			queryClient.invalidateQueries({
				queryKey: ["social", "engagement"],
			});
		},
	});

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<Share2 className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">Social</h1>
			</div>

			{/* Post history */}
			{postsQuery.isLoading ? (
				<SkeletonBlock />
			) : (
				<PostHistorySection posts={postsQuery.data ?? []} />
			)}

			{/* Engagement chart */}
			{engagementQuery.isLoading ? (
				<SkeletonBlock />
			) : (
				<EngagementChart data={engagementQuery.data ?? []} />
			)}

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Quick post */}
				<QuickPostForm
					onPost={(req) => postMutation.mutate(req)}
					isPending={postMutation.isPending}
				/>

				{/* News */}
				{newsQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<NewsFeedSection headlines={newsQuery.data ?? []} />
				)}
			</div>
		</div>
	);
}
