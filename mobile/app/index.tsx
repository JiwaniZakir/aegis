import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Dashboard } from "../components/Dashboard";
import { apiClient } from "../lib/api";

const DARK_BG = "#0A0A0F";
const CARD_BG = "#16161F";
const ACCENT = "#6C63FF";
const TEXT_PRIMARY = "#EEEEF0";
const TEXT_SECONDARY = "#8E8EA0";
const SUCCESS = "#34D399";
const WARNING = "#FBBF24";

export default function HomeScreen() {
  const router = useRouter();

  const { data: briefing, isLoading: briefingLoading } = useQuery({
    queryKey: ["daily-briefing"],
    queryFn: () => apiClient.getDailyBriefing(),
  });

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Morning Briefing Card */}
      <View style={styles.briefingCard}>
        <View style={styles.briefingHeader}>
          <Text style={styles.briefingIcon}>{"[ briefing ]"}</Text>
          <Text style={styles.briefingTitle}>Morning Briefing</Text>
        </View>
        {briefingLoading ? (
          <Text style={styles.briefingPlaceholder}>Loading briefing...</Text>
        ) : (
          <Text style={styles.briefingSummary}>
            {briefing?.summary ?? "No briefing available yet. Check back after 6:00 AM."}
          </Text>
        )}
        {briefing?.highlights && briefing.highlights.length > 0 && (
          <View style={styles.highlights}>
            {briefing.highlights.map((item: string, idx: number) => (
              <View key={idx} style={styles.highlightRow}>
                <Text style={styles.bulletDot}>{"\u2022"}</Text>
                <Text style={styles.highlightText}>{item}</Text>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* Quick Actions */}
      <Text style={styles.sectionTitle}>Quick Actions</Text>
      <View style={styles.actionsRow}>
        <Pressable
          style={[styles.actionButton, { backgroundColor: ACCENT }]}
          onPress={() => router.push("/voice")}
        >
          <Text style={styles.actionIcon}>MIC</Text>
          <Text style={styles.actionLabel}>Voice</Text>
        </Pressable>

        <Pressable style={[styles.actionButton, { backgroundColor: "#1E3A5F" }]}>
          <Text style={styles.actionIcon}>$</Text>
          <Text style={styles.actionLabel}>Finance</Text>
        </Pressable>

        <Pressable style={[styles.actionButton, { backgroundColor: "#2D1B4E" }]}>
          <Text style={styles.actionIcon}>CAL</Text>
          <Text style={styles.actionLabel}>Calendar</Text>
        </Pressable>
      </View>

      {/* Dashboard Summary */}
      <Dashboard />

      {/* Health Metrics Summary */}
      <Text style={styles.sectionTitle}>Health Today</Text>
      <HealthSummary />
    </ScrollView>
  );
}

function HealthSummary() {
  const { data: health, isLoading } = useQuery({
    queryKey: ["health-today"],
    queryFn: () => apiClient.getHealthMetrics(),
  });

  if (isLoading) {
    return (
      <View style={styles.healthCard}>
        <Text style={styles.loadingText}>Loading health data...</Text>
      </View>
    );
  }

  const metrics = [
    {
      label: "Calories",
      value: health?.calories ?? "--",
      target: "1,900",
      color: WARNING,
    },
    {
      label: "Protein",
      value: health?.protein_g ?? "--",
      target: "175g",
      color: SUCCESS,
    },
    {
      label: "Steps",
      value: health?.steps ?? "--",
      target: "10,000",
      color: ACCENT,
    },
    {
      label: "Sleep",
      value: health?.sleep_hours ? `${health.sleep_hours}h` : "--",
      target: "8h",
      color: "#A78BFA",
    },
  ];

  return (
    <View style={styles.healthCard}>
      <View style={styles.metricsGrid}>
        {metrics.map((metric) => (
          <View key={metric.label} style={styles.metricItem}>
            <Text style={[styles.metricValue, { color: metric.color }]}>
              {String(metric.value)}
            </Text>
            <Text style={styles.metricLabel}>{metric.label}</Text>
            <Text style={styles.metricTarget}>/ {metric.target}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: DARK_BG,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },

  // Briefing Card
  briefingCard: {
    backgroundColor: CARD_BG,
    borderRadius: 16,
    padding: 20,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: "#222230",
  },
  briefingHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 12,
  },
  briefingIcon: {
    fontSize: 10,
    color: ACCENT,
    marginRight: 8,
    fontWeight: "600",
  },
  briefingTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: TEXT_PRIMARY,
  },
  briefingPlaceholder: {
    fontSize: 14,
    color: TEXT_SECONDARY,
    fontStyle: "italic",
  },
  briefingSummary: {
    fontSize: 15,
    color: TEXT_PRIMARY,
    lineHeight: 22,
  },
  highlights: {
    marginTop: 12,
  },
  highlightRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 6,
  },
  bulletDot: {
    color: ACCENT,
    fontSize: 14,
    marginRight: 8,
    marginTop: 1,
  },
  highlightText: {
    fontSize: 14,
    color: TEXT_SECONDARY,
    flex: 1,
    lineHeight: 20,
  },

  // Section Title
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: TEXT_PRIMARY,
    marginBottom: 12,
  },

  // Quick Actions
  actionsRow: {
    flexDirection: "row",
    gap: 12,
    marginBottom: 24,
  },
  actionButton: {
    flex: 1,
    borderRadius: 14,
    padding: 16,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 90,
  },
  actionIcon: {
    fontSize: 22,
    color: "#FFFFFF",
    fontWeight: "800",
    marginBottom: 6,
  },
  actionLabel: {
    fontSize: 13,
    color: "#FFFFFF",
    fontWeight: "600",
  },

  // Health
  healthCard: {
    backgroundColor: CARD_BG,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: "#222230",
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  metricItem: {
    width: "45%",
    alignItems: "center",
    paddingVertical: 8,
  },
  metricValue: {
    fontSize: 28,
    fontWeight: "800",
  },
  metricLabel: {
    fontSize: 13,
    color: TEXT_PRIMARY,
    fontWeight: "600",
    marginTop: 4,
  },
  metricTarget: {
    fontSize: 11,
    color: TEXT_SECONDARY,
    marginTop: 2,
  },
  loadingText: {
    color: TEXT_SECONDARY,
    fontSize: 14,
    textAlign: "center",
  },
});
