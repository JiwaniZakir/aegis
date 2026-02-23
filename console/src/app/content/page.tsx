"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
	PenTool,
	Send,
	FileText,
	TrendingUp,
	Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ContentDraft, GenerateContentRequest } from "@/lib/api";

function GenerateForm({
	onGenerate,
	isLoading,
}: {
	onGenerate: (req: GenerateContentRequest) => void;
	isLoading: boolean;
}) {
	const [topic, setTopic] = useState("");
	const [platform, setPlatform] = useState<"linkedin" | "x">("linkedin");
	const [tone, setTone] = useState("professional");

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (!topic.trim()) return;
		onGenerate({ topic: topic.trim(), platform, tone });
	};

	return (
		<form
			onSubmit={handleSubmit}
			className="rounded-lg border border-neutral-800 bg-neutral-900 p-5"
		>
			<div className="mb-4 flex items-center gap-2">
				<PenTool className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Generate New Post
				</h2>
			</div>
			<div className="space-y-4">
				<div>
					<label
						htmlFor="topic"
						className="mb-1 block text-sm text-neutral-400"
					>
						Topic
					</label>
					<input
						id="topic"
						type="text"
						value={topic}
						onChange={(e) => setTopic(e.target.value)}
						placeholder="e.g., AI trends in fintech, personal productivity..."
						className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
					/>
				</div>
				<div className="grid gap-4 sm:grid-cols-2">
					<div>
						<label
							htmlFor="platform"
							className="mb-1 block text-sm text-neutral-400"
						>
							Platform
						</label>
						<select
							id="platform"
							value={platform}
							onChange={(e) =>
								setPlatform(
									e.target.value as "linkedin" | "x",
								)
							}
							className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
						>
							<option value="linkedin">LinkedIn</option>
							<option value="x">X (Twitter)</option>
						</select>
					</div>
					<div>
						<label
							htmlFor="tone"
							className="mb-1 block text-sm text-neutral-400"
						>
							Tone
						</label>
						<select
							id="tone"
							value={tone}
							onChange={(e) => setTone(e.target.value)}
							className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
						>
							<option value="professional">Professional</option>
							<option value="conversational">
								Conversational
							</option>
							<option value="thought-leader">
								Thought Leader
							</option>
							<option value="technical">Technical</option>
							<option value="storytelling">Storytelling</option>
						</select>
					</div>
				</div>
				<button
					type="submit"
					disabled={isLoading || !topic.trim()}
					className="flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
				>
					{isLoading ? (
						<Loader2 className="h-4 w-4 animate-spin" />
					) : (
						<PenTool className="h-4 w-4" />
					)}
					Generate
				</button>
			</div>
		</form>
	);
}

function DraftCard({
	draft,
	onPublish,
	isPublishing,
}: {
	draft: ContentDraft;
	onPublish: (id: string) => void;
	isPublishing: boolean;
}) {
	const statusColors: Record<string, string> = {
		draft: "bg-yellow-900/50 text-yellow-400",
		scheduled: "bg-blue-900/50 text-blue-400",
		published: "bg-emerald-900/50 text-emerald-400",
	};

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<div className="mb-2 flex items-center justify-between">
				<div className="flex items-center gap-2">
					<span
						className={`rounded px-2 py-0.5 text-xs ${statusColors[draft.status] ?? "bg-neutral-800 text-neutral-400"}`}
					>
						{draft.status}
					</span>
					<span className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
						{draft.platform}
					</span>
				</div>
				<span className="text-xs text-neutral-500">
					{new Date(draft.created_at).toLocaleDateString()}
				</span>
			</div>
			<p className="mb-1 text-sm font-medium text-neutral-200">
				{draft.topic}
			</p>
			<p className="line-clamp-3 text-sm text-neutral-400">
				{draft.content}
			</p>
			{draft.status === "draft" && (
				<button
					type="button"
					onClick={() => onPublish(draft.id)}
					disabled={isPublishing}
					className="mt-3 flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
				>
					{isPublishing ? (
						<Loader2 className="h-3 w-3 animate-spin" />
					) : (
						<Send className="h-3 w-3" />
					)}
					Publish
				</button>
			)}
		</div>
	);
}

function EngagementChart({
	data,
}: {
	data: { date: string; likes: number; comments: number; impressions: number }[];
}) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<TrendingUp className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Engagement (30 Days)
				</h2>
			</div>
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
					</BarChart>
				</ResponsiveContainer>
			</div>
		</div>
	);
}

export default function ContentPage() {
	const queryClient = useQueryClient();
	const [publishingId, setPublishingId] = useState<string | null>(null);

	const draftsQuery = useQuery({
		queryKey: ["content", "drafts"],
		queryFn: () => api.content.getDrafts(),
	});

	const historyQuery = useQuery({
		queryKey: ["content", "history"],
		queryFn: () => api.content.getHistory(),
	});

	const engagementQuery = useQuery({
		queryKey: ["content", "engagement"],
		queryFn: () => api.content.getEngagementMetrics(30),
	});

	const generateMutation = useMutation({
		mutationFn: (req: GenerateContentRequest) => api.content.generate(req),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["content", "drafts"] });
		},
	});

	const publishMutation = useMutation({
		mutationFn: (id: string) => {
			setPublishingId(id);
			return api.content.publishDraft(id);
		},
		onSuccess: () => {
			setPublishingId(null);
			queryClient.invalidateQueries({ queryKey: ["content", "drafts"] });
			queryClient.invalidateQueries({
				queryKey: ["content", "history"],
			});
		},
		onError: () => {
			setPublishingId(null);
		},
	});

	const drafts = draftsQuery.data ?? [];
	const history = historyQuery.data ?? [];
	const engagement = engagementQuery.data ?? [];

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<PenTool className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">
					Content Engine
				</h1>
			</div>

			{/* Generate form */}
			<GenerateForm
				onGenerate={(req) => generateMutation.mutate(req)}
				isLoading={generateMutation.isPending}
			/>

			{/* Drafts */}
			<div>
				<div className="mb-3 flex items-center gap-2">
					<FileText className="h-4 w-4 text-neutral-400" />
					<h2 className="text-lg font-semibold text-neutral-100">
						Drafts
					</h2>
				</div>
				{drafts.length > 0 ? (
					<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
						{drafts.map((draft) => (
							<DraftCard
								key={draft.id}
								draft={draft}
								onPublish={(id) => publishMutation.mutate(id)}
								isPublishing={publishingId === draft.id}
							/>
						))}
					</div>
				) : (
					<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-8 text-center">
						<p className="text-sm text-neutral-500">
							No drafts yet. Generate a post above.
						</p>
					</div>
				)}
			</div>

			{/* Engagement */}
			{engagement.length > 0 && <EngagementChart data={engagement} />}

			{/* Publishing history */}
			{history.length > 0 && (
				<div>
					<div className="mb-3 flex items-center gap-2">
						<Send className="h-4 w-4 text-neutral-400" />
						<h2 className="text-lg font-semibold text-neutral-100">
							Publishing History
						</h2>
					</div>
					<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
						{history.map((post) => (
							<DraftCard
								key={post.id}
								draft={post}
								onPublish={() => {}}
								isPublishing={false}
							/>
						))}
					</div>
				</div>
			)}
		</div>
	);
}
