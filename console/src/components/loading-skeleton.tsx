"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function MetricCardSkeleton() {
	return (
		<Card>
			<CardContent className="p-5">
				<div className="flex items-center justify-between">
					<Skeleton className="h-4 w-24" />
					<Skeleton className="h-8 w-8 rounded-lg" />
				</div>
				<Skeleton className="mt-3 h-7 w-32" />
			</CardContent>
		</Card>
	);
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
	return (
		<Card>
			<CardHeader>
				<Skeleton className="h-5 w-40" />
			</CardHeader>
			<CardContent className="space-y-3">
				{Array.from({ length: rows }).map((_, i) => (
					<div key={`skel-${i}`} className="flex items-center gap-3">
						<Skeleton className="h-4 flex-1" />
						<Skeleton className="h-4 w-20" />
						<Skeleton className="h-4 w-16" />
					</div>
				))}
			</CardContent>
		</Card>
	);
}

export function ChartSkeleton() {
	return (
		<Card>
			<CardHeader>
				<Skeleton className="h-5 w-32" />
			</CardHeader>
			<CardContent>
				<Skeleton className="h-48 w-full rounded-lg" />
			</CardContent>
		</Card>
	);
}

export function PageSkeleton() {
	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<Skeleton className="h-8 w-48" />
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				<MetricCardSkeleton />
				<MetricCardSkeleton />
				<MetricCardSkeleton />
				<MetricCardSkeleton />
			</div>
			<div className="grid gap-6 lg:grid-cols-2">
				<ChartSkeleton />
				<TableSkeleton />
			</div>
		</div>
	);
}
