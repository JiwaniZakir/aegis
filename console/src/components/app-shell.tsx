"use client";

import { usePathname } from "next/navigation";
import AuthGuard from "@/components/auth-guard";
import AppSidebar from "@/components/app-sidebar";
import { Toaster } from "@/components/ui/sonner";

const NO_SHELL_PATHS = new Set(["/login"]);

export default function AppShell({ children }: { children: React.ReactNode }) {
	const pathname = usePathname();

	if (NO_SHELL_PATHS.has(pathname)) {
		return (
			<AuthGuard>
				{children}
				<Toaster />
			</AuthGuard>
		);
	}

	return (
		<AuthGuard>
			<div className="flex h-screen overflow-hidden">
				<AppSidebar />
				<main className="flex-1 overflow-y-auto p-6">{children}</main>
			</div>
			<Toaster />
		</AuthGuard>
	);
}
