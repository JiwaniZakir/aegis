"use client";

import { useQuery } from "@tanstack/react-query";
import {
	DollarSign,
	CreditCard,
	RefreshCw,
	Building2,
	Landmark,
	Wallet,
} from "lucide-react";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { MetricCardSkeleton, TableSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";
import {
	Card,
	CardContent,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { PieChart, Pie, Cell } from "recharts";
import {
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
	type ChartConfig,
} from "@/components/ui/chart";

function formatCurrency(n: number) {
	return new Intl.NumberFormat("en-US", {
		style: "currency",
		currency: "USD",
		minimumFractionDigits: 2,
	}).format(n);
}

function formatCurrencyShort(n: number) {
	return new Intl.NumberFormat("en-US", {
		style: "currency",
		currency: "USD",
		maximumFractionDigits: 0,
	}).format(n);
}

function accountIcon(type: string) {
	switch (type.toLowerCase()) {
		case "checking":
		case "savings":
			return Landmark;
		case "credit":
			return CreditCard;
		case "investment":
		case "brokerage":
			return Wallet;
		default:
			return Building2;
	}
}

export default function FinancePage() {
	const balancesQuery = useQuery({
		queryKey: ["finance", "balances"],
		queryFn: () => api.finance.getBalances(),
	});

	const transactionsQuery = useQuery({
		queryKey: ["finance", "transactions"],
		queryFn: () => api.finance.getTransactions({ limit: 20 }),
	});

	const subscriptionsQuery = useQuery({
		queryKey: ["finance", "subscriptions"],
		queryFn: () => api.finance.getSubscriptions(),
	});

	const balances = balancesQuery.data;
	const transactions = transactionsQuery.data;
	const subscriptions = subscriptionsQuery.data;

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Finance" description="Account balances and spending" />

			{/* Metric cards */}
			<div className="grid gap-4 sm:grid-cols-2">
				{balancesQuery.isLoading || subscriptionsQuery.isLoading ? (
					<>
						<MetricCardSkeleton />
						<MetricCardSkeleton />
					</>
				) : balancesQuery.isError || subscriptionsQuery.isError ? (
					<div className="sm:col-span-2">
						<QueryError message="Failed to load financial overview." onRetry={() => { balancesQuery.refetch(); subscriptionsQuery.refetch(); }} />
					</div>
				) : (
					<>
						<MetricCard
							label="Total Balance"
							value={
								balances
									? formatCurrencyShort(balances.total_balance)
									: "--"
							}
							icon={DollarSign}
						/>
						<MetricCard
							label="Monthly Subscriptions"
							value={
								subscriptions
									? formatCurrency(subscriptions.total_monthly)
									: "--"
							}
							icon={RefreshCw}
						/>
					</>
				)}
			</div>

			{/* Accounts */}
			{balancesQuery.isLoading ? (
				<TableSkeleton rows={3} />
			) : balancesQuery.isError ? (
				<QueryError message="Failed to load accounts." onRetry={() => balancesQuery.refetch()} />
			) : balances && balances.accounts.length > 0 ? (
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Building2 className="h-4 w-4 text-muted-foreground" />
							Accounts
						</CardTitle>
					</CardHeader>
					<CardContent>
						<div className="space-y-0">
							{balances.accounts.map((account, index) => {
								const Icon = accountIcon(account.type);
								return (
									<div key={`${account.name}-${account.institution}`}>
										{index > 0 && <Separator className="my-0" />}
										<div className="flex items-center gap-3 py-3">
											<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
												<Icon className="h-4 w-4 text-muted-foreground" />
											</div>
											<div className="min-w-0 flex-1">
												<p className="truncate text-sm font-medium">
													{account.name}
												</p>
												<p className="text-xs text-muted-foreground">
													{account.institution} · {account.type}
												</p>
											</div>
											<p className="shrink-0 text-sm font-semibold tabular-nums">
												{formatCurrency(account.balance)}
											</p>
										</div>
									</div>
								);
							})}
						</div>
						{balances.last_synced && (
							<p className="mt-2 text-xs text-muted-foreground">
								Last synced {new Date(balances.last_synced).toLocaleString()}
							</p>
						)}
					</CardContent>
				</Card>
			) : (
				<Card>
					<CardContent className="flex items-center justify-center py-12">
						<p className="text-sm text-muted-foreground">
							Connect your accounts to see balances.
						</p>
					</CardContent>
				</Card>
			)}

			{/* Spending by Category */}
			{transactions && transactions.transactions.length > 0 && (() => {
				const CHART_COLORS = [
					"hsl(var(--chart-1))",
					"hsl(var(--chart-2))",
					"hsl(var(--chart-3))",
					"hsl(var(--chart-4))",
					"hsl(var(--chart-5))",
				];
				const categoryTotals = transactions.transactions
					.filter((tx) => tx.amount < 0)
					.reduce<Record<string, number>>((acc, tx) => {
						const cat = tx.category || "Other";
						acc[cat] = (acc[cat] ?? 0) + Math.abs(tx.amount);
						return acc;
					}, {});
				const pieData = Object.entries(categoryTotals)
					.map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }))
					.sort((a, b) => b.value - a.value);
				const spendingChartConfig: ChartConfig = Object.fromEntries(
					pieData.map(({ name }, i) => [
						name,
						{ label: name, color: CHART_COLORS[i % CHART_COLORS.length] },
					])
				);
				return pieData.length > 0 ? (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<CreditCard className="h-4 w-4 text-muted-foreground" />
								Spending by Category
							</CardTitle>
						</CardHeader>
						<CardContent>
							<ChartContainer config={spendingChartConfig} className="mx-auto aspect-square max-h-[300px]">
								<PieChart>
									<ChartTooltip content={<ChartTooltipContent hideLabel formatter={(value) => formatCurrency(Number(value))} />} />
									<Pie
										data={pieData}
										dataKey="value"
										nameKey="name"
										cx="50%"
										cy="50%"
										outerRadius={100}
										label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
									>
										{pieData.map((entry, index) => (
											<Cell
												key={entry.name}
												fill={CHART_COLORS[index % CHART_COLORS.length]}
											/>
										))}
									</Pie>
								</PieChart>
							</ChartContainer>
						</CardContent>
					</Card>
				) : null;
			})()}

			{/* Transactions + Subscriptions */}
			<div className="grid gap-6 lg:grid-cols-3">
				{/* Transactions - takes 2 cols */}
				<div className="lg:col-span-2">
					{transactionsQuery.isLoading ? (
						<TableSkeleton rows={8} />
					) : transactionsQuery.isError ? (
						<QueryError message="Failed to load transactions." onRetry={() => transactionsQuery.refetch()} />
					) : transactions && transactions.transactions.length > 0 ? (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2">
									<CreditCard className="h-4 w-4 text-muted-foreground" />
									Recent Transactions
								</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="overflow-x-auto">
									<table className="w-full text-sm">
										<thead>
											<tr className="border-b text-left">
												<th className="pb-3 pr-4 text-xs font-medium text-muted-foreground">
													Date
												</th>
												<th className="pb-3 pr-4 text-xs font-medium text-muted-foreground">
													Description
												</th>
												<th className="pb-3 pr-4 text-xs font-medium text-muted-foreground">
													Category
												</th>
												<th className="pb-3 text-right text-xs font-medium text-muted-foreground">
													Amount
												</th>
											</tr>
										</thead>
										<tbody>
											{transactions.transactions.map((tx) => (
												<tr
													key={tx.id}
													className="border-b border-border/50 transition-colors hover:bg-muted/30"
												>
													<td className="py-3 pr-4 text-muted-foreground tabular-nums">
														{new Date(tx.date).toLocaleDateString([], {
															month: "short",
															day: "numeric",
														})}
													</td>
													<td className="py-3 pr-4 font-medium">
														<div>
															{tx.description}
															{tx.account_name && (
																<span className="ml-1.5 text-xs text-muted-foreground">
																	{tx.account_name}
																</span>
															)}
														</div>
													</td>
													<td className="py-3 pr-4">
														<Badge variant="secondary">
															{tx.category}
														</Badge>
													</td>
													<td
														className={`py-3 text-right font-medium tabular-nums ${
															tx.amount < 0
																? "text-red-500"
																: "text-emerald-500"
														}`}
													>
														{tx.amount < 0 ? "-" : "+"}
														{formatCurrency(Math.abs(tx.amount))}
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
								<p className="mt-3 text-xs text-muted-foreground">
									Showing {transactions.transactions.length} of {transactions.count} transactions
								</p>
							</CardContent>
						</Card>
					) : (
						<Card>
							<CardContent className="flex items-center justify-center py-12">
								<p className="text-sm text-muted-foreground">
									No transactions yet.
								</p>
							</CardContent>
						</Card>
					)}
				</div>

				{/* Subscriptions - takes 1 col */}
				<div>
					{subscriptionsQuery.isLoading ? (
						<TableSkeleton rows={4} />
					) : subscriptionsQuery.isError ? (
						<QueryError message="Failed to load subscriptions." onRetry={() => subscriptionsQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2">
									<RefreshCw className="h-4 w-4 text-muted-foreground" />
									Subscriptions
								</CardTitle>
							</CardHeader>
							<CardContent>
								{subscriptions && subscriptions.recurring.length > 0 ? (
									<div className="space-y-0">
										{subscriptions.recurring.map((sub, index) => (
											<div key={`${sub.description}-${sub.amount}`}>
												{index > 0 && <Separator className="my-0" />}
												<div className="py-3">
													<div className="flex items-center justify-between">
														<p className="text-sm font-medium">
															{sub.description}
														</p>
														<p className="text-sm font-semibold tabular-nums">
															{formatCurrency(sub.amount)}
														</p>
													</div>
													<div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
														<span>{sub.frequency}</span>
														<span>·</span>
														<span>
															Next: {new Date(sub.next_date).toLocaleDateString([], {
																month: "short",
																day: "numeric",
															})}
														</span>
													</div>
												</div>
											</div>
										))}
										<Separator />
										<div className="flex items-center justify-between pt-3">
											<p className="text-sm font-medium text-muted-foreground">
												Monthly Total
											</p>
											<p className="text-sm font-semibold tabular-nums">
												{formatCurrency(subscriptions.total_monthly)}
											</p>
										</div>
									</div>
								) : (
									<p className="py-6 text-center text-sm text-muted-foreground">
										No subscriptions detected.
									</p>
								)}
							</CardContent>
						</Card>
					)}
				</div>
			</div>
		</div>
	);
}
