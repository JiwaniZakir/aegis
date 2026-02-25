"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";

const PUBLIC_PATHS = new Set(["/login"]);

export default function AuthGuard({ children }: { children: React.ReactNode }) {
	const router = useRouter();
	const pathname = usePathname();
	const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
	const [checked, setChecked] = useState(false);

	useEffect(() => {
		if (PUBLIC_PATHS.has(pathname)) {
			setChecked(true);
			return;
		}
		if (!isAuthenticated) {
			router.replace("/login");
		} else {
			setChecked(true);
		}
	}, [isAuthenticated, pathname, router]);

	if (PUBLIC_PATHS.has(pathname)) {
		return <>{children}</>;
	}

	if (!checked) {
		return (
			<div className="flex h-screen items-center justify-center bg-background">
				<div className="h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
			</div>
		);
	}

	return <>{children}</>;
}
