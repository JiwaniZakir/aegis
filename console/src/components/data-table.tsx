"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";

export interface Column<T> {
	key: string;
	header: string;
	render?: (row: T) => React.ReactNode;
	className?: string;
}

interface DataTableProps<T> {
	columns: Column<T>[];
	data: T[];
	pageSize?: number;
	keyExtractor: (row: T) => string;
	emptyMessage?: string;
}

export function DataTable<T>({
	columns,
	data,
	pageSize = 10,
	keyExtractor,
	emptyMessage = "No data.",
}: DataTableProps<T>) {
	const [page, setPage] = useState(0);
	const totalPages = Math.max(1, Math.ceil(data.length / pageSize));
	const start = page * pageSize;
	const pageData = data.slice(start, start + pageSize);

	if (data.length === 0) {
		return (
			<p className="py-8 text-center text-sm text-muted-foreground">
				{emptyMessage}
			</p>
		);
	}

	return (
		<div className="space-y-3">
			<Table>
				<TableHeader>
					<TableRow>
						{columns.map((col) => (
							<TableHead key={col.key} className={col.className}>
								{col.header}
							</TableHead>
						))}
					</TableRow>
				</TableHeader>
				<TableBody>
					{pageData.map((row) => (
						<TableRow key={keyExtractor(row)}>
							{columns.map((col) => (
								<TableCell key={col.key} className={col.className}>
									{col.render
										? col.render(row)
										: String((row as Record<string, unknown>)[col.key] ?? "")}
								</TableCell>
							))}
						</TableRow>
					))}
				</TableBody>
			</Table>

			{totalPages > 1 && (
				<div className="flex items-center justify-between px-1">
					<p className="text-xs text-muted-foreground">
						{start + 1}–{Math.min(start + pageSize, data.length)} of{" "}
						{data.length}
					</p>
					<div className="flex items-center gap-1">
						<Button
							variant="ghost"
							size="sm"
							disabled={page === 0}
							onClick={() => setPage((p) => p - 1)}
						>
							<ChevronLeft className="h-4 w-4" />
						</Button>
						<span className="min-w-[3rem] text-center text-xs text-muted-foreground">
							{page + 1} / {totalPages}
						</span>
						<Button
							variant="ghost"
							size="sm"
							disabled={page >= totalPages - 1}
							onClick={() => setPage((p) => p + 1)}
						>
							<ChevronRight className="h-4 w-4" />
						</Button>
					</div>
				</div>
			)}
		</div>
	);
}
