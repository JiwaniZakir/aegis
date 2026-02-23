"use client";

import { useQuery } from "@tanstack/react-query";
import { useRef, useEffect, useState, useCallback } from "react";
import { Users, Search, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import type { Contact, ContactGraph } from "@/lib/api";

function ContactGraphVisualization({ graph }: { graph: ContactGraph }) {
	const containerRef = useRef<HTMLDivElement>(null);
	const networkRef = useRef<unknown>(null);

	useEffect(() => {
		if (!containerRef.current || graph.nodes.length === 0) return;

		let destroyed = false;

		async function initNetwork() {
			const vis = await import("vis-network/standalone");

			if (destroyed || !containerRef.current) return;

			const nodes = new vis.DataSet(
				graph.nodes.map((node) => ({
					id: node.id,
					label: node.name,
					title: `${node.relationship} - Last contact: ${new Date(node.last_contact).toLocaleDateString()}`,
					color: {
						background: "#3f3f46",
						border: "#6366f1",
						highlight: {
							background: "#4f46e5",
							border: "#818cf8",
						},
					},
					font: { color: "#e5e5e5", size: 12 },
				})),
			);

			const edges = new vis.DataSet(
				graph.edges.map((edge, index) => ({
					id: `edge-${index}`,
					from: edge.from,
					to: edge.to,
					value: edge.strength,
					color: { color: "#404040", highlight: "#6366f1" },
				})),
			);

			const options = {
				physics: {
					stabilization: { iterations: 100 },
					barnesHut: {
						gravitationalConstant: -3000,
						springLength: 150,
					},
				},
				interaction: {
					hover: true,
					tooltipDelay: 200,
				},
				nodes: {
					shape: "dot" as const,
					size: 16,
					borderWidth: 2,
				},
				edges: {
					smooth: {
						enabled: true,
						type: "continuous",
						roundness: 0.5,
					},
				},
			};

			const network = new vis.Network(
				containerRef.current,
				{ nodes, edges },
				options,
			);
			networkRef.current = network;
		}

		initNetwork();

		return () => {
			destroyed = true;
			if (
				networkRef.current &&
				typeof (networkRef.current as { destroy: () => void }).destroy ===
					"function"
			) {
				(networkRef.current as { destroy: () => void }).destroy();
			}
		};
	}, [graph]);

	return (
		<div
			ref={containerRef}
			className="h-[500px] w-full rounded-lg border border-neutral-800 bg-neutral-900"
		/>
	);
}

function ContactSearchBar({
	onSearch,
}: { onSearch: (query: string) => void }) {
	const [value, setValue] = useState("");

	const handleSubmit = useCallback(
		(e: React.FormEvent) => {
			e.preventDefault();
			onSearch(value);
		},
		[value, onSearch],
	);

	return (
		<form onSubmit={handleSubmit} className="flex gap-2">
			<div className="relative flex-1">
				<Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
				<input
					type="text"
					placeholder="Search contacts..."
					value={value}
					onChange={(e) => setValue(e.target.value)}
					className="w-full rounded-md border border-neutral-800 bg-neutral-900 py-2 pl-10 pr-4 text-sm text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
				/>
			</div>
			<button
				type="submit"
				className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
			>
				Search
			</button>
		</form>
	);
}

function OutreachSidebar({ contacts }: { contacts: Contact[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<UserPlus className="h-4 w-4 text-neutral-400" />
				<h2 className="text-sm font-semibold text-neutral-200">
					Outreach Suggestions
				</h2>
			</div>
			<div className="space-y-3">
				{contacts.map((contact) => (
					<div
						key={contact.id}
						className="rounded-md border border-neutral-800 px-3 py-2"
					>
						<p className="text-sm font-medium text-neutral-200">
							{contact.name}
						</p>
						<p className="text-xs text-neutral-500">
							{contact.relationship}
						</p>
						<p className="mt-1 text-xs text-neutral-400">
							Last contact:{" "}
							{new Date(
								contact.last_contact,
							).toLocaleDateString()}
						</p>
					</div>
				))}
				{contacts.length === 0 && (
					<p className="text-center text-xs text-neutral-500">
						No suggestions available.
					</p>
				)}
			</div>
		</div>
	);
}

export default function ContactsPage() {
	const [searchQuery, setSearchQuery] = useState("");

	const graphQuery = useQuery({
		queryKey: ["contacts", "graph"],
		queryFn: () => api.contacts.getGraph(),
	});

	const searchResults = useQuery({
		queryKey: ["contacts", "search", searchQuery],
		queryFn: () => api.contacts.search(searchQuery),
		enabled: searchQuery.length > 0,
	});

	const outreachQuery = useQuery({
		queryKey: ["contacts", "outreach"],
		queryFn: () => api.contacts.getOutreachSuggestions(),
	});

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<Users className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">
					Contacts
				</h1>
			</div>

			<ContactSearchBar onSearch={setSearchQuery} />

			{/* Search results */}
			{searchQuery && searchResults.data && (
				<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
					<h2 className="mb-3 text-sm font-semibold text-neutral-200">
						Search Results ({searchResults.data.length})
					</h2>
					<div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
						{searchResults.data.map((contact) => (
							<div
								key={contact.id}
								className="rounded-md border border-neutral-800 p-3"
							>
								<p className="text-sm font-medium text-neutral-200">
									{contact.name}
								</p>
								<p className="text-xs text-neutral-500">
									{contact.email}
								</p>
								<p className="text-xs text-neutral-500">
									{contact.relationship} &middot;{" "}
									{contact.interaction_count} interactions
								</p>
							</div>
						))}
					</div>
				</div>
			)}

			<div className="grid gap-6 lg:grid-cols-[1fr_300px]">
				{/* Graph */}
				<div>
					{graphQuery.isLoading ? (
						<div className="flex h-[500px] items-center justify-center rounded-lg border border-neutral-800 bg-neutral-900">
							<p className="text-sm text-neutral-500">
								Loading contact graph...
							</p>
						</div>
					) : graphQuery.data &&
						graphQuery.data.nodes.length > 0 ? (
						<ContactGraphVisualization graph={graphQuery.data} />
					) : (
						<div className="flex h-[500px] items-center justify-center rounded-lg border border-neutral-800 bg-neutral-900">
							<p className="text-sm text-neutral-500">
								No contact data available.
							</p>
						</div>
					)}
				</div>

				{/* Outreach suggestions */}
				<OutreachSidebar contacts={outreachQuery.data ?? []} />
			</div>
		</div>
	);
}
