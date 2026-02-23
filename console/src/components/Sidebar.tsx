"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
	LayoutDashboard,
	Wallet,
	Mail,
	CalendarDays,
	Users,
	Share2,
	Heart,
	BarChart3,
	PenTool,
	Shield,
	PanelLeftClose,
	PanelLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/lib/store";

const navItems = [
	{ href: "/", label: "Dashboard", icon: LayoutDashboard },
	{ href: "/finance", label: "Finance", icon: Wallet },
	{ href: "/email", label: "Email", icon: Mail },
	{ href: "/calendar", label: "Calendar", icon: CalendarDays },
	{ href: "/contacts", label: "Contacts", icon: Users },
	{ href: "/social", label: "Social", icon: Share2 },
	{ href: "/health", label: "Health", icon: Heart },
	{ href: "/productivity", label: "Productivity", icon: BarChart3 },
	{ href: "/content", label: "Content", icon: PenTool },
	{ href: "/security", label: "Security", icon: Shield },
] as const;

export default function Sidebar() {
	const pathname = usePathname();
	const { sidebarOpen, toggleSidebar } = useUIStore();

	return (
		<aside
			className={cn(
				"flex h-screen flex-col border-r border-neutral-800 bg-neutral-950 transition-all duration-200",
				sidebarOpen ? "w-60" : "w-16",
			)}
		>
			{/* Header */}
			<div className="flex h-14 items-center justify-between border-b border-neutral-800 px-4">
				{sidebarOpen && (
					<span className="text-sm font-semibold tracking-wide text-neutral-200">
						ClawdBot
					</span>
				)}
				<button
					type="button"
					onClick={toggleSidebar}
					className="rounded-md p-1.5 text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200"
				>
					{sidebarOpen ? (
						<PanelLeftClose className="h-4 w-4" />
					) : (
						<PanelLeft className="h-4 w-4" />
					)}
				</button>
			</div>

			{/* Navigation */}
			<nav className="flex-1 space-y-1 overflow-y-auto p-2">
				{navItems.map((item) => {
					const isActive =
						item.href === "/"
							? pathname === "/"
							: pathname.startsWith(item.href);
					return (
						<Link
							key={item.href}
							href={item.href}
							className={cn(
								"flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
								isActive
									? "bg-neutral-800 text-neutral-50"
									: "text-neutral-400 hover:bg-neutral-900 hover:text-neutral-200",
								!sidebarOpen && "justify-center px-0",
							)}
						>
							<item.icon className="h-4 w-4 shrink-0" />
							{sidebarOpen && <span>{item.label}</span>}
						</Link>
					);
				})}
			</nav>

			{/* Footer */}
			<div className="border-t border-neutral-800 p-3">
				{sidebarOpen && (
					<p className="text-xs text-neutral-500">
						ClawdBot v0.1.0
					</p>
				)}
			</div>
		</aside>
	);
}
