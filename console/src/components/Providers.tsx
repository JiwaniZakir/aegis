"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useRef, useEffect } from "react";
import { initializeAuthBridge } from "@/lib/store";

function makeQueryClient() {
	return new QueryClient({
		defaultOptions: {
			queries: {
				staleTime: 60 * 1000,
				retry: 1,
				refetchOnWindowFocus: false,
			},
		},
	});
}

let browserQueryClient: QueryClient | undefined;

function getQueryClient() {
	if (typeof window === "undefined") {
		return makeQueryClient();
	}
	if (!browserQueryClient) {
		browserQueryClient = makeQueryClient();
	}
	return browserQueryClient;
}

export default function Providers({ children }: { children: ReactNode }) {
	const queryClient = getQueryClient();
	const initialized = useRef(false);

	useEffect(() => {
		if (!initialized.current) {
			initializeAuthBridge();
			initialized.current = true;
		}
	}, []);

	return (
		<QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
	);
}
