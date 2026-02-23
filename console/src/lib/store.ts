import { create } from "zustand";
import { persist } from "zustand/middleware";
import { type AuthTokens, type User, api, configureAuth } from "./api";

// ---- Auth Slice ----
interface AuthState {
	user: User | null;
	accessToken: string | null;
	refreshToken: string | null;
	isAuthenticated: boolean;
	login: (email: string, password: string, totpCode?: string) => Promise<void>;
	logout: () => void;
	setTokens: (tokens: AuthTokens) => void;
	setUser: (user: User) => void;
}

export const useAuthStore = create<AuthState>()(
	persist(
		(set) => ({
			user: null,
			accessToken: null,
			refreshToken: null,
			isAuthenticated: false,

			login: async (email, password, totpCode) => {
				const tokens = await api.auth.login({
					email,
					password,
					totp_code: totpCode,
				});
				set({
					accessToken: tokens.access_token,
					refreshToken: tokens.refresh_token,
					isAuthenticated: true,
				});
				const user = await api.auth.me();
				set({ user });
			},

			logout: () => {
				set({
					user: null,
					accessToken: null,
					refreshToken: null,
					isAuthenticated: false,
				});
			},

			setTokens: (tokens) => {
				set({
					accessToken: tokens.access_token,
					refreshToken: tokens.refresh_token,
					isAuthenticated: true,
				});
			},

			setUser: (user) => {
				set({ user });
			},
		}),
		{
			name: "clawdbot-auth",
			partialize: (state) => ({
				accessToken: state.accessToken,
				refreshToken: state.refreshToken,
				isAuthenticated: state.isAuthenticated,
			}),
		},
	),
);

// ---- UI Slice ----
interface UIState {
	sidebarOpen: boolean;
	activeView: string;
	toggleSidebar: () => void;
	setSidebarOpen: (open: boolean) => void;
	setActiveView: (view: string) => void;
}

export const useUIStore = create<UIState>()((set) => ({
	sidebarOpen: true,
	activeView: "dashboard",

	toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
	setSidebarOpen: (open) => set({ sidebarOpen: open }),
	setActiveView: (view) => set({ activeView: view }),
}));

// ---- Wire auth store into API client ----
export function initializeAuthBridge() {
	configureAuth({
		getToken: () => useAuthStore.getState().accessToken,
		onRefresh: (tokens) => useAuthStore.getState().setTokens(tokens),
		onFailure: () => useAuthStore.getState().logout(),
	});
}
