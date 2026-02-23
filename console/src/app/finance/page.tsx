"use client";

import { useQuery } from "@tanstack/react-query";
import {
	AreaChart,
	Area,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
} from "recharts";
import { Wallet, TrendingDown, CreditCard, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { Account, Transaction, Subscription, SpendingTrend } from "@/lib/api";

function AccountCard({ account }: { account: Account }) {
	const formatted = new Intl.NumberFormat("en-US", {
		style: "currency",
		currency: "USD",
	}).format(account.balance);

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
			<div className="flex items-center justify-between">
				<p className="text-sm text-neutral-400">{account.institution}</p>
				<span className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
					{account.type}
				</span>
			</div>
			<p className="mt-1 text-sm font-medium text-neutral-200">
				{account.name}
			</p>
			<p className="mt-2 text-xl font-semibold text-neutral-50">
				{formatted}
			</p>
			<p className="mt-1 text-xs text-neutral-500">
				Synced {new Date(account.last_synced).toLocaleDateString()}
			</p>
		</div>
	);
}

function SpendingChart({ data }: { data: SpendingTrend[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<TrendingDown className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Spending Trend
				</h2>
			</div>
			<div className="h-64">
				<ResponsiveContainer width="100%" height="100%">
					<AreaChart data={data}>
						<defs>
							<linearGradient
								id="spendGradient"
								x1="0"
								y1="0"
								x2="0"
								y2="1"
							>
								<stop
									offset="5%"
									stopColor="#6366f1"
									stopOpacity={0.3}
								/>
								<stop
									offset="95%"
									stopColor="#6366f1"
									stopOpacity={0}
								/>
							</linearGradient>
						</defs>
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
							tickFormatter={(v: number) => `$${v}`}
						/>
						<Tooltip
							contentStyle={{
								backgroundColor: "#171717",
								border: "1px solid #262626",
								borderRadius: "8px",
								color: "#e5e5e5",
							}}
							formatter={(value: number) => [
								`$${value.toFixed(2)}`,
								"Spent",
							]}
							labelFormatter={(label: string) =>
								new Date(label).toLocaleDateString()
							}
						/>
						<Area
							type="monotone"
							dataKey="amount"
							stroke="#6366f1"
							fillOpacity={1}
							fill="url(#spendGradient)"
						/>
					</AreaChart>
				</ResponsiveContainer>
			</div>
		</div>
	);
}

function TransactionsTable({
	transactions,
}: { transactions: Transaction[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<CreditCard className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Recent Transactions
				</h2>
			</div>
			<div className="overflow-x-auto">
				<table className="w-full text-sm">
					<thead>
						<tr className="border-b border-neutral-800 text-left text-neutral-500">
							<th className="pb-2 pr-4 font-medium">Date</th>
							<th className="pb-2 pr-4 font-medium">
								Description
							</th>
							<th className="pb-2 pr-4 font-medium">Category</th>
							<th className="pb-2 text-right font-medium">
								Amount
							</th>
						</tr>
					</thead>
					<tbody className="divide-y divide-neutral-800/50">
						{transactions.map((tx) => (
							<tr key={tx.id}>
								<td className="py-2 pr-4 text-neutral-400">
									{new Date(tx.date).toLocaleDateString()}
								</td>
								<td className="py-2 pr-4 text-neutral-200">
									{tx.description}
								</td>
								<td className="py-2 pr-4">
									<span className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
										{tx.category}
									</span>
								</td>
								<td
									className={`py-2 text-right font-medium ${
										tx.amount < 0
											? "text-red-400"
											: "text-emerald-400"
									}`}
								>
									{tx.amount < 0 ? "-" : "+"}$
									{Math.abs(tx.amount).toFixed(2)}
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>
		</div>
	);
}

function SubscriptionList({
	subscriptions,
}: { subscriptions: Subscription[] }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<RefreshCw className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Subscriptions
				</h2>
			</div>
			<div className="space-y-3">
				{subscriptions.map((sub) => (
					<div
						key={sub.id}
						className="flex items-center justify-between rounded-md border border-neutral-800 px-3 py-2"
					>
						<div>
							<p className="text-sm font-medium text-neutral-200">
								{sub.name}
							</p>
							<p className="text-xs text-neutral-500">
								{sub.frequency} &middot; Next:{" "}
								{new Date(sub.next_charge).toLocaleDateString()}
							</p>
						</div>
						<p className="text-sm font-semibold text-neutral-100">
							${sub.amount.toFixed(2)}
						</p>
					</div>
				))}
				{subscriptions.length === 0 && (
					<p className="text-center text-sm text-neutral-500">
						No subscriptions detected.
					</p>
				)}
			</div>
		</div>
	);
}

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

export default function FinancePage() {
	const snapshotQuery = useQuery({
		queryKey: ["finance", "snapshot"],
		queryFn: () => api.finance.getSnapshot(),
	});

	const transactionsQuery = useQuery({
		queryKey: ["finance", "transactions"],
		queryFn: () => api.finance.getTransactions({ limit: 20 }),
	});

	const spendingQuery = useQuery({
		queryKey: ["finance", "spending-trend"],
		queryFn: () => api.finance.getSpendingTrend(30),
	});

	const subscriptionsQuery = useQuery({
		queryKey: ["finance", "subscriptions"],
		queryFn: () => api.finance.getSubscriptions(),
	});

	const snapshot = snapshotQuery.data;
	const loading =
		snapshotQuery.isLoading ||
		transactionsQuery.isLoading ||
		spendingQuery.isLoading;

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<Wallet className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">Finance</h1>
			</div>

			{/* Balance overview */}
			{loading ? (
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					{Array.from({ length: 4 }).map((_, i) => (
						<div
							key={`skel-${i.toString()}`}
							className="animate-pulse rounded-lg border border-neutral-800 bg-neutral-900 p-4"
						>
							<div className="h-4 w-20 rounded bg-neutral-800" />
							<div className="mt-3 h-6 w-28 rounded bg-neutral-800" />
						</div>
					))}
				</div>
			) : snapshot ? (
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{snapshot.accounts.map((account) => (
						<AccountCard key={account.id} account={account} />
					))}
				</div>
			) : (
				<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-8 text-center">
					<p className="text-sm text-neutral-500">
						Connect your accounts to see balances.
					</p>
				</div>
			)}

			{/* Spending chart */}
			{spendingQuery.isLoading ? (
				<SkeletonBlock />
			) : spendingQuery.data && spendingQuery.data.length > 0 ? (
				<SpendingChart data={spendingQuery.data} />
			) : null}

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Transactions */}
				{transactionsQuery.isLoading ? (
					<SkeletonBlock />
				) : transactionsQuery.data &&
					transactionsQuery.data.length > 0 ? (
					<TransactionsTable transactions={transactionsQuery.data} />
				) : (
					<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-8 text-center">
						<p className="text-sm text-neutral-500">
							No transactions yet.
						</p>
					</div>
				)}

				{/* Subscriptions */}
				{subscriptionsQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<SubscriptionList
						subscriptions={subscriptionsQuery.data ?? []}
					/>
				)}
			</div>
		</div>
	);
}
