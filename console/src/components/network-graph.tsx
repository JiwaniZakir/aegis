"use client";

import { useEffect, useRef } from "react";

interface NetworkNode {
	id: string;
	name: string;
	relationship: string;
	interaction_count: number;
}

interface NetworkEdge {
	from: string;
	to: string;
	strength: number;
}

interface NetworkGraphProps {
	nodes: NetworkNode[];
	edges: NetworkEdge[];
}

export function NetworkGraph({ nodes, edges }: NetworkGraphProps) {
	const containerRef = useRef<HTMLDivElement>(null);
	const networkRef = useRef<InstanceType<
		typeof import("vis-network/standalone").Network
	> | null>(null);

	useEffect(() => {
		if (!containerRef.current || nodes.length === 0) return;

		let destroyed = false;

		async function init() {
			const { Network, DataSet } = await import("vis-network/standalone");

			if (destroyed || !containerRef.current) return;

			const visNodes = new DataSet(
				nodes.map((n) => ({
					id: n.id,
					label: n.name,
					shape: "dot" as const,
					size: 10 + Math.min(n.interaction_count, 20),
					color: {
						background: "#3b82f6",
						border: "#2563eb",
					},
				})),
			);

			const visEdges = new DataSet(
				edges.map((e, i) => ({
					id: `edge-${i}`,
					from: e.from,
					to: e.to,
					width: Math.max(1, e.strength * 3),
					color: {
						color: "#94a3b8",
						opacity: 0.6,
					},
				})),
			);

			const options = {
				physics: {
					enabled: true,
					solver: "forceAtlas2Based" as const,
					forceAtlas2Based: {
						gravitationalConstant: -30,
						centralGravity: 0.005,
						springLength: 100,
						springConstant: 0.08,
						damping: 0.4,
					},
					stabilization: {
						iterations: 150,
					},
				},
				nodes: {
					font: {
						color: "hsl(var(--foreground))",
						size: 12,
					},
					borderWidth: 2,
				},
				edges: {
					smooth: {
						enabled: true,
						type: "continuous",
						roundness: 0.5,
					},
				},
				interaction: {
					hover: true,
					tooltipDelay: 200,
					zoomView: true,
					dragView: true,
				},
			};

			networkRef.current = new Network(
				containerRef.current!,
				{ nodes: visNodes, edges: visEdges },
				options,
			);
		}

		init();

		return () => {
			destroyed = true;
			if (networkRef.current) {
				networkRef.current.destroy();
				networkRef.current = null;
			}
		};
	}, [nodes, edges]);

	return (
		<div
			ref={containerRef}
			className="rounded-lg border"
			style={{ height: 400 }}
		/>
	);
}
