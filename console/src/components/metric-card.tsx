"use client";

import { Card, CardContent } from "@/components/ui/card";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";

interface MetricCardProps {
	label: string;
	value: string;
	icon: React.ComponentType<{ className?: string }>;
	trend?: { value: string; positive: boolean };
}

export function MetricCard({ label, value, icon: Icon, trend }: MetricCardProps) {
	return (
		<Card className="transition-all duration-200 hover:shadow-md">
			<CardContent className="p-5">
				<div className="flex items-center justify-between">
					<p className="text-sm font-medium text-muted-foreground">{label}</p>
					<div className="rounded-lg bg-muted p-2">
						<Icon className="h-4 w-4 text-muted-foreground" />
					</div>
				</div>
				<p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
				{trend && (
					<div className="mt-1 flex items-center gap-1 text-xs">
						{trend.positive ? (
							<ArrowUpRight className="h-3 w-3 text-emerald-500" />
						) : (
							<ArrowDownRight className="h-3 w-3 text-red-500" />
						)}
						<span className={trend.positive ? "text-emerald-500" : "text-red-500"}>
							{trend.value}
						</span>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
