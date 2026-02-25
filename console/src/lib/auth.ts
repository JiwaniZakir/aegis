"use client";

import { useAuthStore } from "./store";

/**
 * Check if the user is currently authenticated.
 * Uses the Zustand auth store which persists tokens to localStorage.
 */
export function useIsAuthenticated(): boolean {
	return useAuthStore((s) => s.isAuthenticated);
}

/**
 * Get the current access token (or null if not authenticated).
 */
export function useAccessToken(): string | null {
	return useAuthStore((s) => s.accessToken);
}

/**
 * Login action — delegates to the store's login method.
 */
export function useLogin() {
	return useAuthStore((s) => s.login);
}

/**
 * Logout action — clears tokens and redirects to login.
 */
export function useLogout() {
	const logout = useAuthStore((s) => s.logout);
	return () => {
		logout();
		if (typeof window !== "undefined") {
			window.location.href = "/login";
		}
	};
}
