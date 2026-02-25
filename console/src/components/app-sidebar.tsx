"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
	LayoutDashboard,
	DollarSign,
	Mail,
	CalendarDays,
	Users,
	Share2,
	Heart,
	Timer,
	FileText,
	Shield,
	LogOut,
	Moon,
	Sun,
} from "lucide-react";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
	{ href: "/", label: "Dashboard", icon: LayoutDashboard },
	{ href: "/finance", label: "Finance", icon: DollarSign },
	{ href: "/email", label: "Email", icon: Mail },
	{ href: "/calendar", label: "Calendar", icon: CalendarDays },
	{ href: "/contacts", label: "Contacts", icon: Users },
	{ href: "/social", label: "Social", icon: Share2 },
	{ href: "/health", label: "Health", icon: Heart },
	{ href: "/productivity", label: "Productivity", icon: Timer },
	{ href: "/content", label: "Content", icon: FileText },
	{ href: "/security", label: "Security", icon: Shield },
];

export default function AppSidebar() {
	const pathname = usePathname();
	const logout = useAuthStore((s) => s.logout);
	const [collapsed, setCollapsed] = useState(false);
	const [dark, setDark] = useState(true);

	useEffect(() => {
		const isDark = document.documentElement.classList.contains("dark");
		setDark(isDark);
	}, []);

	function toggleTheme() {
		const next = !dark;
		setDark(next);
		document.documentElement.classList.toggle("dark", next);
	}

	function handleLogout() {
		logout();
		window.location.href = "/login";
	}

	return (
		<aside
			className={cn(
				"flex h-screen flex-col border-r border-border bg-card transition-all duration-200",
				collapsed ? "w-16" : "w-56",
			)}
		>
			{/* Logo */}
			<div className="flex h-14 items-center gap-2 px-4">
				<button
					type="button"
					onClick={() => setCollapsed(!collapsed)}
					className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-foreground text-background text-sm font-bold"
				>
					C
				</button>
				{!collapsed && (
					<span className="text-sm font-semibold tracking-tight">Aegis</span>
				)}
			</div>

			<Separator />

			{/* Navigation */}
			<nav className="flex-1 space-y-1 overflow-y-auto p-2">
				{NAV_ITEMS.map((item) => {
					const isActive =
						pathname === item.href ||
						(item.href !== "/" && pathname.startsWith(item.href));
					return (
						<Link
							key={item.href}
							href={item.href}
							className={cn(
								"flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
								isActive
									? "bg-accent text-accent-foreground font-medium"
									: "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
							)}
						>
							<item.icon className="h-4 w-4 shrink-0" />
							{!collapsed && <span>{item.label}</span>}
						</Link>
					);
				})}
			</nav>

			<Separator />

			{/* Footer controls */}
			<div className="space-y-1 p-2">
				<Button
					variant="ghost"
					size="sm"
					className="w-full justify-start gap-3 text-muted-foreground"
					onClick={toggleTheme}
				>
					{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
					{!collapsed && <span>{dark ? "Light Mode" : "Dark Mode"}</span>}
				</Button>
				<Button
					variant="ghost"
					size="sm"
					className="w-full justify-start gap-3 text-muted-foreground hover:text-destructive"
					onClick={handleLogout}
				>
					<LogOut className="h-4 w-4" />
					{!collapsed && <span>Sign Out</span>}
				</Button>
			</div>
		</aside>
	);
}
