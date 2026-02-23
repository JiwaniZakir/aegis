import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
	title: "ClawdBot Console",
	description: "Personal intelligence platform dashboard",
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en" className="dark">
			<body className="bg-neutral-950 text-neutral-50 antialiased">
				<Providers>
					<div className="flex h-screen overflow-hidden">
						<Sidebar />
						<main className="flex-1 overflow-y-auto p-6">
							{children}
						</main>
					</div>
				</Providers>
			</body>
		</html>
	);
}
