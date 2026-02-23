"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
	Shield,
	Monitor,
	ScrollText,
	KeyRound,
	Smartphone,
	CheckCircle2,
	XCircle,
	Loader2,
	AlertTriangle,
	LogOut,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
	AuditLogEntry,
	ActiveSession,
	TwoFactorStatus,
	ChangePasswordRequest,
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

// ---- Active sessions ----
function ActiveSessionsSection({
	sessions,
	onRevoke,
	revokingId,
}: {
	sessions: ActiveSession[];
	onRevoke: (id: string) => void;
	revokingId: string | null;
}) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<Monitor className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Active Sessions
				</h2>
				<span className="ml-auto rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
					{sessions.length} active
				</span>
			</div>
			{sessions.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No active sessions found.
				</p>
			) : (
				<div className="space-y-2">
					{sessions.map((session) => (
						<div
							key={session.id}
							className={`flex items-center justify-between rounded-md border px-3 py-2.5 ${
								session.is_current
									? "border-indigo-800 bg-indigo-950/20"
									: "border-neutral-800"
							}`}
						>
							<div className="min-w-0 flex-1">
								<div className="flex items-center gap-2">
									<Smartphone className="h-3.5 w-3.5 shrink-0 text-neutral-500" />
									<p className="truncate text-sm font-medium text-neutral-200">
										{session.user_agent}
									</p>
									{session.is_current && (
										<span className="shrink-0 rounded bg-indigo-900/50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-400">
											Current
										</span>
									)}
								</div>
								<p className="mt-0.5 text-xs text-neutral-500">
									{session.ip_address} &middot; Last active{" "}
									{new Date(session.last_active).toLocaleString([], {
										month: "short",
										day: "numeric",
										hour: "2-digit",
										minute: "2-digit",
									})}
								</p>
							</div>
							{!session.is_current && (
								<button
									type="button"
									onClick={() => onRevoke(session.id)}
									disabled={revokingId === session.id}
									className="ml-3 flex shrink-0 items-center gap-1 rounded-md bg-red-900/30 px-2.5 py-1.5 text-xs font-medium text-red-400 hover:bg-red-900/50 disabled:opacity-50"
								>
									{revokingId === session.id ? (
										<Loader2 className="h-3 w-3 animate-spin" />
									) : (
										<LogOut className="h-3 w-3" />
									)}
									Revoke
								</button>
							)}
						</div>
					))}
				</div>
			)}
		</div>
	);
}

// ---- Audit log table ----
function AuditLogSection({ entries }: { entries: AuditLogEntry[] }) {
	const statusColors: Record<string, string> = {
		success: "bg-emerald-900/50 text-emerald-400",
		failure: "bg-red-900/50 text-red-400",
	};

	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<ScrollText className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Audit Log
				</h2>
			</div>
			{entries.length === 0 ? (
				<p className="text-center text-sm text-neutral-500">
					No audit log entries.
				</p>
			) : (
				<div className="overflow-x-auto">
					<table className="w-full text-sm">
						<thead>
							<tr className="border-b border-neutral-800 text-left text-neutral-500">
								<th className="pb-2 pr-4 font-medium">Time</th>
								<th className="pb-2 pr-4 font-medium">Action</th>
								<th className="pb-2 pr-4 font-medium">Resource</th>
								<th className="pb-2 pr-4 font-medium">IP</th>
								<th className="pb-2 font-medium">Status</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-neutral-800/50">
							{entries.map((entry) => (
								<tr key={entry.id}>
									<td className="py-2 pr-4 text-neutral-400">
										{new Date(entry.timestamp).toLocaleString([], {
											month: "short",
											day: "numeric",
											hour: "2-digit",
											minute: "2-digit",
										})}
									</td>
									<td className="py-2 pr-4 text-neutral-200">
										{entry.action}
									</td>
									<td className="py-2 pr-4">
										<span className="rounded bg-neutral-800 px-2 py-0.5 text-xs text-neutral-400">
											{entry.resource}
										</span>
									</td>
									<td className="py-2 pr-4 font-mono text-xs text-neutral-500">
										{entry.ip_address}
									</td>
									<td className="py-2">
										<span
											className={`rounded px-2 py-0.5 text-xs ${statusColors[entry.status] ?? "bg-neutral-800 text-neutral-400"}`}
										>
											{entry.status}
										</span>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				</div>
			)}
		</div>
	);
}

// ---- 2FA status ----
function TwoFactorSection({ status }: { status: TwoFactorStatus }) {
	return (
		<div className="rounded-lg border border-neutral-800 bg-neutral-900 p-5">
			<div className="mb-4 flex items-center gap-2">
				<KeyRound className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Two-Factor Authentication
				</h2>
			</div>
			<div className="flex items-center gap-3">
				{status.enabled ? (
					<>
						<div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-900/30">
							<CheckCircle2 className="h-5 w-5 text-emerald-400" />
						</div>
						<div>
							<p className="text-sm font-medium text-emerald-400">
								Enabled
							</p>
							<p className="text-xs text-neutral-500">
								Method: {status.method.toUpperCase()}
								{status.last_verified && (
									<>
										{" "}&middot; Last verified{" "}
										{new Date(status.last_verified).toLocaleDateString()}
									</>
								)}
							</p>
						</div>
					</>
				) : (
					<>
						<div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-900/30">
							<AlertTriangle className="h-5 w-5 text-red-400" />
						</div>
						<div>
							<p className="text-sm font-medium text-red-400">
								Not Enabled
							</p>
							<p className="text-xs text-neutral-500">
								Enable 2FA for stronger account protection.
							</p>
						</div>
					</>
				)}
			</div>
		</div>
	);
}

// ---- Password change form ----
function PasswordChangeForm({
	onSubmit,
	isPending,
	isSuccess,
	error,
}: {
	onSubmit: (req: ChangePasswordRequest) => void;
	isPending: boolean;
	isSuccess: boolean;
	error: Error | null;
}) {
	const [currentPassword, setCurrentPassword] = useState("");
	const [newPassword, setNewPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [validationError, setValidationError] = useState<string | null>(null);

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		setValidationError(null);

		if (newPassword.length < 12) {
			setValidationError("New password must be at least 12 characters.");
			return;
		}
		if (newPassword !== confirmPassword) {
			setValidationError("Passwords do not match.");
			return;
		}
		if (newPassword === currentPassword) {
			setValidationError(
				"New password must be different from current password.",
			);
			return;
		}
		onSubmit({
			current_password: currentPassword,
			new_password: newPassword,
		});
		setCurrentPassword("");
		setNewPassword("");
		setConfirmPassword("");
	};

	return (
		<form
			onSubmit={handleSubmit}
			className="rounded-lg border border-neutral-800 bg-neutral-900 p-5"
		>
			<div className="mb-4 flex items-center gap-2">
				<Shield className="h-4 w-4 text-neutral-400" />
				<h2 className="text-lg font-semibold text-neutral-100">
					Change Password
				</h2>
			</div>
			<div className="space-y-4">
				<div>
					<label
						htmlFor="current-password"
						className="mb-1 block text-sm text-neutral-400"
					>
						Current Password
					</label>
					<input
						id="current-password"
						type="password"
						value={currentPassword}
						onChange={(e) => setCurrentPassword(e.target.value)}
						required
						className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
					/>
				</div>
				<div>
					<label
						htmlFor="new-password"
						className="mb-1 block text-sm text-neutral-400"
					>
						New Password
					</label>
					<input
						id="new-password"
						type="password"
						value={newPassword}
						onChange={(e) => setNewPassword(e.target.value)}
						required
						minLength={12}
						className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
					/>
					<p className="mt-1 text-xs text-neutral-500">
						Minimum 12 characters
					</p>
				</div>
				<div>
					<label
						htmlFor="confirm-password"
						className="mb-1 block text-sm text-neutral-400"
					>
						Confirm New Password
					</label>
					<input
						id="confirm-password"
						type="password"
						value={confirmPassword}
						onChange={(e) => setConfirmPassword(e.target.value)}
						required
						minLength={12}
						className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-200 placeholder-neutral-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
					/>
				</div>

				{/* Status messages */}
				{validationError && (
					<div className="flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400">
						<XCircle className="h-4 w-4 shrink-0" />
						{validationError}
					</div>
				)}
				{error && (
					<div className="flex items-center gap-2 rounded-md bg-red-900/20 px-3 py-2 text-sm text-red-400">
						<XCircle className="h-4 w-4 shrink-0" />
						{error.message}
					</div>
				)}
				{isSuccess && (
					<div className="flex items-center gap-2 rounded-md bg-emerald-900/20 px-3 py-2 text-sm text-emerald-400">
						<CheckCircle2 className="h-4 w-4 shrink-0" />
						Password changed successfully.
					</div>
				)}

				<button
					type="submit"
					disabled={
						isPending ||
						!currentPassword ||
						!newPassword ||
						!confirmPassword
					}
					className="flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
				>
					{isPending ? (
						<Loader2 className="h-4 w-4 animate-spin" />
					) : (
						<Shield className="h-4 w-4" />
					)}
					Update Password
				</button>
			</div>
		</form>
	);
}

// ---- Main page ----
export default function SecurityPage() {
	const queryClient = useQueryClient();
	const [revokingId, setRevokingId] = useState<string | null>(null);

	const sessionsQuery = useQuery({
		queryKey: ["security", "sessions"],
		queryFn: () => api.security.getActiveSessions(),
	});

	const auditQuery = useQuery({
		queryKey: ["security", "audit-log"],
		queryFn: () => api.security.getAuditLog({ limit: 50 }),
	});

	const twoFactorQuery = useQuery({
		queryKey: ["security", "2fa"],
		queryFn: () => api.security.getTwoFactorStatus(),
	});

	const revokeMutation = useMutation({
		mutationFn: (id: string) => {
			setRevokingId(id);
			return api.security.revokeSession(id);
		},
		onSuccess: () => {
			setRevokingId(null);
			queryClient.invalidateQueries({
				queryKey: ["security", "sessions"],
			});
		},
		onError: () => {
			setRevokingId(null);
		},
	});

	const passwordMutation = useMutation({
		mutationFn: (req: ChangePasswordRequest) =>
			api.security.changePassword(req),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["security", "audit-log"],
			});
		},
	});

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<div className="flex items-center gap-3">
				<Shield className="h-6 w-6 text-neutral-400" />
				<h1 className="text-2xl font-bold text-neutral-50">
					Security & Audit
				</h1>
			</div>

			<div className="grid gap-6 lg:grid-cols-2">
				{/* Active sessions */}
				{sessionsQuery.isLoading ? (
					<SkeletonBlock />
				) : (
					<ActiveSessionsSection
						sessions={sessionsQuery.data ?? []}
						onRevoke={(id) => revokeMutation.mutate(id)}
						revokingId={revokingId}
					/>
				)}

				{/* 2FA + Password */}
				<div className="space-y-6">
					{/* 2FA status */}
					{twoFactorQuery.isLoading ? (
						<SkeletonBlock />
					) : twoFactorQuery.data ? (
						<TwoFactorSection status={twoFactorQuery.data} />
					) : null}

					{/* Password change */}
					<PasswordChangeForm
						onSubmit={(req) => passwordMutation.mutate(req)}
						isPending={passwordMutation.isPending}
						isSuccess={passwordMutation.isSuccess}
						error={passwordMutation.error}
					/>
				</div>
			</div>

			{/* Audit log */}
			{auditQuery.isLoading ? (
				<SkeletonBlock />
			) : (
				<AuditLogSection entries={auditQuery.data ?? []} />
			)}
		</div>
	);
}
