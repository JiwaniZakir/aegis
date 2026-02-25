import { useEffect } from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { View, StyleSheet } from "react-native";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

const DARK_BG = "#0A0A0F";
const HEADER_BG = "#111118";
const ACCENT = "#6C63FF";

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <View style={styles.container}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: {
              backgroundColor: HEADER_BG,
            },
            headerTintColor: "#FFFFFF",
            headerTitleStyle: {
              fontWeight: "700",
              fontSize: 18,
            },
            contentStyle: {
              backgroundColor: DARK_BG,
            },
            animation: "slide_from_right",
          }}
        >
          <Stack.Screen
            name="index"
            options={{
              title: "Aegis",
              headerLargeTitle: true,
            }}
          />
          <Stack.Screen
            name="voice"
            options={{
              title: "Voice Assistant",
              presentation: "modal",
            }}
          />
          <Stack.Screen
            name="health"
            options={{
              title: "Health",
            }}
          />
        </Stack>
      </View>
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: DARK_BG,
  },
});
