import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";
import AppShell from "@/components/app-shell";
import { ErrorBoundary } from "@/components/error-boundary";

export const metadata: Metadata = {
	title: "Aegis Console",
	description: "Personal intelligence platform dashboard",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en" className="dark" suppressHydrationWarning>
			<body className="antialiased">
				<Providers>
					<AppShell>
						<ErrorBoundary>{children}</ErrorBoundary>
					</AppShell>
				</Providers>
			</body>
		</html>
	);
}
