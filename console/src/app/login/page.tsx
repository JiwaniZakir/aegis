"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuthStore } from "@/lib/store";
import { ApiClientError } from "@/lib/api";

export default function LoginPage() {
	const router = useRouter();
	const login = useAuthStore((s) => s.login);
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [totpCode, setTotpCode] = useState("");
	const [showTotp, setShowTotp] = useState(false);
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(false);

	async function handleSubmit(e: React.FormEvent) {
		e.preventDefault();
		setError("");
		setLoading(true);

		try {
			await login(email, password, totpCode || undefined);
			router.replace("/");
		} catch (err) {
			if (err instanceof ApiClientError) {
				if (err.detail === "TOTP code required") {
					setShowTotp(true);
					setError("");
				} else {
					setError(err.detail);
				}
			} else {
				setError("An unexpected error occurred");
			}
		} finally {
			setLoading(false);
		}
	}

	return (
		<div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-zinc-50 to-zinc-100 dark:from-zinc-950 dark:to-zinc-900">
			<Card className="w-full max-w-sm border-0 shadow-xl backdrop-blur-xl bg-white/80 dark:bg-zinc-900/80">
				<CardHeader className="space-y-1 text-center">
					<div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-2xl bg-foreground">
						<span className="text-lg font-bold text-background">C</span>
					</div>
					<CardTitle className="text-xl font-semibold tracking-tight">
						Aegis
					</CardTitle>
					<p className="text-sm text-muted-foreground">
						Sign in to your personal intelligence platform
					</p>
				</CardHeader>
				<CardContent>
					<form onSubmit={handleSubmit} className="space-y-4">
						<div className="space-y-2">
							<Label htmlFor="email">Email</Label>
							<Input
								id="email"
								type="email"
								placeholder="you@example.com"
								value={email}
								onChange={(e) => setEmail(e.target.value)}
								required
								autoFocus
								autoComplete="email"
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="password">Password</Label>
							<Input
								id="password"
								type="password"
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								required
								autoComplete="current-password"
							/>
						</div>
						{showTotp && (
							<div className="space-y-2">
								<Label htmlFor="totp">Authenticator Code</Label>
								<Input
									id="totp"
									type="text"
									inputMode="numeric"
									placeholder="000000"
									maxLength={6}
									value={totpCode}
									onChange={(e) => setTotpCode(e.target.value)}
									autoFocus
								/>
							</div>
						)}
						{error && (
							<p className="text-sm text-destructive">{error}</p>
						)}
						<Button type="submit" className="w-full" disabled={loading}>
							{loading ? "Signing in..." : "Sign In"}
						</Button>
					</form>
				</CardContent>
			</Card>
		</div>
	);
}
