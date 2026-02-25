import { View, Text, ScrollView, StyleSheet } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { HealthBridge } from "../components/HealthBridge";
import { apiClient } from "../lib/api";

const DARK_BG = "#0A0A0F";
const CARD_BG = "#16161F";
const TEXT_PRIMARY = "#EEEEF0";
const TEXT_SECONDARY = "#8E8EA0";
const ACCENT = "#6C63FF";
const SUCCESS = "#34D399";
const WARNING = "#FBBF24";

export default function HealthScreen() {
  const { data: health, isLoading } = useQuery({
    queryKey: ["health-today"],
    queryFn: () => apiClient.getHealthMetrics(),
  });

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Health Data Sync */}
      <Text style={styles.sectionTitle}>Apple Health Sync</Text>
      <HealthBridge />

      {/* Server-side Health Metrics */}
      <Text style={styles.sectionTitle}>Today's Metrics</Text>
      <View style={styles.card}>
        {isLoading ? (
          <Text style={styles.loadingText}>Loading health data...</Text>
        ) : health ? (
          <View style={styles.metricsGrid}>
            <MetricCard
              label="Calories"
              value={health.calories !== null ? String(health.calories) : "--"}
              target="1,900"
              color={WARNING}
            />
            <MetricCard
              label="Protein"
              value={health.protein_g !== null ? `${health.protein_g}g` : "--"}
              target="175g"
              color={SUCCESS}
            />
            <MetricCard
              label="Steps"
              value={health.steps !== null ? health.steps.toLocaleString() : "--"}
              target="10,000"
              color={ACCENT}
            />
            <MetricCard
              label="Sleep"
              value={health.sleep_hours !== null ? `${health.sleep_hours}h` : "--"}
              target="8h"
              color="#A78BFA"
            />
            <MetricCard
              label="Heart Rate"
              value={
                health.heart_rate_avg !== null ? `${health.heart_rate_avg} bpm` : "--"
              }
              target="resting"
              color="#EF4444"
            />
          </View>
        ) : (
          <Text style={styles.emptyText}>No health data available yet. Sync from Apple Health above.</Text>
        )}
      </View>
    </ScrollView>
  );
}

function MetricCard({
  label,
  value,
  target,
  color,
}: {
  label: string;
  value: string;
  target: string;
  color: string;
}) {
  return (
    <View style={styles.metricItem}>
      <Text style={[styles.metricValue, { color }]}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricTarget}>/ {target}</Text>
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
  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: TEXT_PRIMARY,
    marginBottom: 12,
  },
  card: {
    backgroundColor: CARD_BG,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: "#222230",
    marginBottom: 24,
  },
  loadingText: {
    color: TEXT_SECONDARY,
    fontSize: 14,
    textAlign: "center",
  },
  emptyText: {
    color: TEXT_SECONDARY,
    fontSize: 14,
    textAlign: "center",
    fontStyle: "italic",
    lineHeight: 20,
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
});
