"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AuditLogEntry, ActiveSession, ChangePasswordRequest } from "@/lib/api";
import { Shield, Activity, AlertTriangle, Key, Lock, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { PageHeader } from "@/components/page-header";
import { TableSkeleton } from "@/components/loading-skeleton";
import { QueryError } from "@/components/query-error";
import { DataTable, type Column } from "@/components/data-table";

export default function SecurityPage() {
	const queryClient = useQueryClient();
	const [currentPassword, setCurrentPassword] = useState("");
	const [newPassword, setNewPassword] = useState("");
	const [passwordMsg, setPasswordMsg] = useState("");

	const auditQuery = useQuery({
		queryKey: ["security", "audit-log"],
		queryFn: () => api.security.getAuditLog({ limit: 50 }),
	});

	const sessionsQuery = useQuery({
		queryKey: ["security", "sessions"],
		queryFn: () => api.security.getActiveSessions(),
	});

	const failedQuery = useQuery({
		queryKey: ["security", "failed-logins"],
		queryFn: () => api.security.getFailedLogins({ limit: 10 }),
	});

	const twoFactorQuery = useQuery({
		queryKey: ["security", "2fa"],
		queryFn: () => api.security.getTwoFactorStatus(),
	});

	const revokeMutation = useMutation({
		mutationFn: (id: string) => api.security.revokeSession(id),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["security", "sessions"] }),
	});

	const passwordMutation = useMutation({
		mutationFn: (body: ChangePasswordRequest) => api.security.changePassword(body),
		onSuccess: () => {
			setCurrentPassword("");
			setNewPassword("");
			setPasswordMsg("Password changed successfully.");
		},
		onError: (err: Error) => setPasswordMsg(err.message),
	});

	const auditEntries = (auditQuery.data as { entries?: AuditLogEntry[] } | undefined)?.entries ?? [];
	const sessions = sessionsQuery.data ?? [];
	const failedLogins = failedQuery.data ?? [];
	const twoFactor = twoFactorQuery.data;

	const auditColumns: Column<AuditLogEntry>[] = [
		{
			key: "timestamp",
			header: "Time",
			className: "text-xs tabular-nums text-muted-foreground",
			render: (e) => new Date(e.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
		},
		{ key: "action", header: "Action", render: (e) => <span className="font-medium">{e.action}</span> },
		{ key: "resource", header: "Resource", className: "text-muted-foreground" },
		{ key: "ip_address", header: "IP", className: "tabular-nums text-muted-foreground" },
		{
			key: "status",
			header: "Status",
			render: (e) => (
				<Badge variant={e.status === "failure" ? "destructive" : "secondary"}>{e.status}</Badge>
			),
		},
	];

	return (
		<div className="mx-auto max-w-6xl space-y-6">
			<PageHeader title="Security" description="Audit logs, sessions, and account security" />

			<div className="grid gap-6 lg:grid-cols-3">
				{/* Main content - 2 cols */}
				<div className="space-y-6 lg:col-span-2">
					{/* Active Sessions */}
					{sessionsQuery.isLoading ? (
						<TableSkeleton rows={3} />
					) : sessionsQuery.isError ? (
						<QueryError message="Failed to load active sessions." onRetry={() => sessionsQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2 text-base">
									<Activity className="h-4 w-4 text-muted-foreground" />
									Active Sessions
								</CardTitle>
							</CardHeader>
							<CardContent>
								{sessions.length === 0 ? (
									<p className="py-4 text-center text-sm text-muted-foreground">No sessions found.</p>
								) : (
									<div className="space-y-0">
										{sessions.map((session: ActiveSession, index: number) => (
											<div key={session.id}>
												{index > 0 && <Separator className="my-0" />}
												<div className="flex items-center gap-3 py-3">
													<div className="min-w-0 flex-1">
														<p className="text-sm font-medium">
															{session.ip_address || "Unknown IP"}
															{session.is_current && <Badge variant="default" className="ml-2 text-[10px]">Current</Badge>}
														</p>
														<p className="truncate text-xs text-muted-foreground">
															{session.user_agent || "Unknown device"}
														</p>
														<p className="text-xs text-muted-foreground">
															Last active: {new Date(session.last_active).toLocaleString()}
														</p>
													</div>
													{!session.is_current && (
														<Button
															variant="ghost"
															size="sm"
															className="shrink-0 text-destructive hover:text-destructive"
															disabled={revokeMutation.isPending}
															onClick={() => revokeMutation.mutate(session.id)}
														>
															<Trash2 className="h-4 w-4" />
														</Button>
													)}
												</div>
											</div>
										))}
									</div>
								)}
							</CardContent>
						</Card>
					)}

					{/* Audit Log */}
					{auditQuery.isLoading ? (
						<TableSkeleton rows={8} />
					) : auditQuery.isError ? (
						<QueryError message="Failed to load audit log." onRetry={() => auditQuery.refetch()} />
					) : (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2 text-base">
									<Shield className="h-4 w-4 text-muted-foreground" />
									Audit Log
									<Badge variant="secondary" className="ml-auto">
										{(auditQuery.data as { total?: number } | undefined)?.total ?? auditEntries.length} total
									</Badge>
								</CardTitle>
							</CardHeader>
							<CardContent>
								<DataTable<AuditLogEntry>
									columns={auditColumns}
									data={auditEntries}
									pageSize={15}
									keyExtractor={(e) => e.id}
									emptyMessage="No audit entries."
								/>
							</CardContent>
						</Card>
					)}
				</div>

				{/* Sidebar - 1 col */}
				<div className="space-y-6">
					{/* 2FA Status */}
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<Key className="h-4 w-4 text-muted-foreground" />
								Two-Factor Auth
							</CardTitle>
						</CardHeader>
						<CardContent>
							{twoFactorQuery.isLoading ? (
								<div className="h-12 animate-pulse rounded bg-muted" />
							) : twoFactorQuery.isError ? (
								<QueryError message="Failed to load 2FA status." onRetry={() => twoFactorQuery.refetch()} />
							) : twoFactor ? (
								<div className="flex items-center gap-3">
									<div className={`h-3 w-3 rounded-full ${twoFactor.enabled ? "bg-emerald-500" : "bg-red-500"}`} />
									<div>
										<p className="text-sm font-medium">
											{twoFactor.enabled ? "Enabled" : "Disabled"}
										</p>
										<p className="text-xs text-muted-foreground">
											{twoFactor.enabled ? `Method: ${twoFactor.method}` : "Consider enabling TOTP"}
										</p>
									</div>
								</div>
							) : (
								<p className="text-sm text-muted-foreground">Unable to load 2FA status.</p>
							)}
						</CardContent>
					</Card>

					{/* Failed Logins */}
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<AlertTriangle className="h-4 w-4 text-muted-foreground" />
								Failed Logins
							</CardTitle>
						</CardHeader>
						<CardContent>
							{failedQuery.isLoading ? (
								<div className="space-y-2">
									{Array.from({ length: 3 }).map((_, i) => (
										<div key={`skel-${i}`} className="h-8 animate-pulse rounded bg-muted" />
									))}
								</div>
							) : failedQuery.isError ? (
								<QueryError message="Failed to load login history." onRetry={() => failedQuery.refetch()} />
							) : failedLogins.length === 0 ? (
								<p className="py-4 text-center text-sm text-muted-foreground">No failed logins.</p>
							) : (
								<div className="space-y-2">
									{failedLogins.slice(0, 5).map((entry: AuditLogEntry) => (
										<div key={entry.id} className="rounded-lg border p-2">
											<p className="text-xs font-medium">{entry.ip_address || "Unknown IP"}</p>
											<p className="text-[10px] text-muted-foreground">
												{new Date(entry.timestamp).toLocaleString()}
											</p>
										</div>
									))}
								</div>
							)}
						</CardContent>
					</Card>

					{/* Change Password */}
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2 text-base">
								<Lock className="h-4 w-4 text-muted-foreground" />
								Change Password
							</CardTitle>
						</CardHeader>
						<CardContent>
							<form
								className="space-y-3"
								onSubmit={(e) => {
									e.preventDefault();
									setPasswordMsg("");
									if (newPassword.length < 12) {
										setPasswordMsg("Password must be at least 12 characters.");
										return;
									}
									passwordMutation.mutate({ current_password: currentPassword, new_password: newPassword });
								}}
							>
								<div className="space-y-1.5">
									<Label htmlFor="current-pw" className="text-xs">Current Password</Label>
									<Input
										id="current-pw"
										type="password"
										value={currentPassword}
										onChange={(e) => setCurrentPassword(e.target.value)}
										required
									/>
								</div>
								<div className="space-y-1.5">
									<Label htmlFor="new-pw" className="text-xs">New Password</Label>
									<Input
										id="new-pw"
										type="password"
										value={newPassword}
										onChange={(e) => setNewPassword(e.target.value)}
										required
										minLength={12}
									/>
								</div>
								{passwordMsg && (
									<p className={`text-xs ${passwordMsg.includes("success") ? "text-emerald-500" : "text-destructive"}`}>
										{passwordMsg}
									</p>
								)}
								<Button
									type="submit"
									size="sm"
									className="w-full"
									disabled={passwordMutation.isPending}
								>
									{passwordMutation.isPending ? "Updating..." : "Update Password"}
								</Button>
							</form>
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
