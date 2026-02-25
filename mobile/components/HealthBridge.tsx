import { useState, useCallback, useEffect } from "react";
import { View, Text, Pressable, StyleSheet, Platform, ActivityIndicator } from "react-native";
import { apiClient } from "../lib/api";
import type { AppleHealthPayload } from "../lib/api";

const CARD_BG = "#16161F";
const TEXT_PRIMARY = "#EEEEF0";
const TEXT_SECONDARY = "#8E8EA0";
const ACCENT = "#6C63FF";
const SUCCESS = "#34D399";
const DANGER = "#EF4444";

/**
 * Dynamically import react-native-health only on iOS.
 * On Android or in Expo Go, HealthKit is unavailable.
 */
let AppleHealthKit: typeof import("react-native-health").default | null = null;
let HealthKitPermissions: import("react-native-health").HealthKitPermissions | null = null;

if (Platform.OS === "ios") {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const rnHealth = require("react-native-health");
    AppleHealthKit = rnHealth.default;
    HealthKitPermissions = {
      permissions: {
        read: [
          rnHealth.HealthKitPermissions
            ? "Steps"
            : "Steps",
        ],
      },
    } as import("react-native-health").HealthKitPermissions;
  } catch {
    // react-native-health not linked or unavailable (e.g., Expo Go)
    AppleHealthKit = null;
  }
}

interface HealthBridgeProps {
  /** Compact mode hides the detailed metric cards */
  compact?: boolean;
}

interface SyncedData {
  steps: number | null;
  heartRateSamples: Array<{ value: number; timestamp: string }>;
  sleepHours: number | null;
  activeEnergy: number | null;
}

const LAST_SYNC_KEY = "aegis_health_last_sync";

export function HealthBridge({ compact = false }: HealthBridgeProps) {
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncedData, setSyncedData] = useState<SyncedData | null>(null);
  const [healthKitAvailable, setHealthKitAvailable] = useState<boolean | null>(null);

  // Check HealthKit availability on mount
  useEffect(() => {
    if (Platform.OS !== "ios") {
      setHealthKitAvailable(false);
      return;
    }

    if (!AppleHealthKit) {
      setHealthKitAvailable(false);
      return;
    }

    const permissions = {
      permissions: {
        read: [
          "StepCount" as const,
          "HeartRate" as const,
          "SleepAnalysis" as const,
          "ActiveEnergyBurned" as const,
        ],
        write: [],
      },
    };

    AppleHealthKit.initHealthKit(permissions, (err: string) => {
      if (err) {
        console.error("HealthKit initialization error:", err);
        setHealthKitAvailable(false);
        return;
      }
      setHealthKitAvailable(true);
    });
  }, []);

  const readHealthData = useCallback((): Promise<SyncedData> => {
    return new Promise((resolve, reject) => {
      if (!AppleHealthKit) {
        reject(new Error("HealthKit not available"));
        return;
      }

      const now = new Date();
      const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const options = {
        startDate: startOfDay.toISOString(),
        endDate: now.toISOString(),
      };

      const data: SyncedData = {
        steps: null,
        heartRateSamples: [],
        sleepHours: null,
        activeEnergy: null,
      };

      let completed = 0;
      const totalQueries = 4;

      function checkDone() {
        completed++;
        if (completed >= totalQueries) {
          resolve(data);
        }
      }

      // Steps
      AppleHealthKit!.getStepCount(options, (err: string, results: { value: number }) => {
        if (!err && results) {
          data.steps = Math.round(results.value);
        }
        checkDone();
      });

      // Heart Rate
      AppleHealthKit!.getHeartRateSamples(
        options,
        (err: string, results: Array<{ value: number; startDate: string }>) => {
          if (!err && results) {
            data.heartRateSamples = results.map((s) => ({
              value: Math.round(s.value),
              timestamp: s.startDate,
            }));
          }
          checkDone();
        }
      );

      // Sleep
      AppleHealthKit!.getSleepSamples(
        options,
        (err: string, results: Array<{ startDate: string; endDate: string }>) => {
          if (!err && results && results.length > 0) {
            let totalMinutes = 0;
            for (const sample of results) {
              const start = new Date(sample.startDate).getTime();
              const end = new Date(sample.endDate).getTime();
              totalMinutes += (end - start) / (1000 * 60);
            }
            data.sleepHours = Math.round((totalMinutes / 60) * 10) / 10;
          }
          checkDone();
        }
      );

      // Active Energy
      AppleHealthKit!.getActiveEnergyBurned(
        options,
        (err: string, results: Array<{ value: number }>) => {
          if (!err && results && results.length > 0) {
            data.activeEnergy = Math.round(
              results.reduce((sum, r) => sum + r.value, 0)
            );
          }
          checkDone();
        }
      );
    });
  }, []);

  const syncHealthData = useCallback(async () => {
    setIsSyncing(true);
    setSyncError(null);

    try {
      const healthData = await readHealthData();
      setSyncedData(healthData);

      const payload: AppleHealthPayload = {
        steps: healthData.steps,
        heart_rate_samples: healthData.heartRateSamples,
        sleep_hours: healthData.sleepHours,
        active_energy_kcal: healthData.activeEnergy,
        recorded_at: new Date().toISOString(),
      };

      await apiClient.submitAppleHealthData(payload);

      const syncTime = new Date().toISOString();
      setLastSync(syncTime);
    } catch (err) {
      console.error("Health sync failed:", err);
      setSyncError(
        err instanceof Error ? err.message : "Failed to sync health data"
      );
    } finally {
      setIsSyncing(false);
    }
  }, [readHealthData]);

  // HealthKit not available UI
  if (healthKitAvailable === false) {
    return (
      <View style={styles.container}>
        <View style={styles.card}>
          <Text style={styles.unavailableTitle}>HealthKit Unavailable</Text>
          <Text style={styles.unavailableText}>
            {Platform.OS !== "ios"
              ? "Apple HealthKit is only available on iOS devices."
              : "HealthKit could not be initialized. Make sure the app has been built with native modules (not Expo Go) and HealthKit permissions are configured."}
          </Text>
        </View>
      </View>
    );
  }

  // Loading state while checking availability
  if (healthKitAvailable === null) {
    return (
      <View style={styles.container}>
        <View style={[styles.card, styles.loadingCard]}>
          <ActivityIndicator color={ACCENT} size="small" />
          <Text style={styles.loadingText}>Connecting to HealthKit...</Text>
        </View>
      </View>
    );
  }

  const formatLastSync = (iso: string): string => {
    try {
      const date = new Date(iso);
      return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } catch {
      return iso;
    }
  };

  if (compact) {
    return (
      <View style={styles.container}>
        <Pressable
          style={[styles.compactSyncButton, isSyncing && styles.syncButtonDisabled]}
          onPress={syncHealthData}
          disabled={isSyncing}
        >
          {isSyncing ? (
            <ActivityIndicator color="#FFFFFF" size="small" />
          ) : (
            <Text style={styles.compactSyncText}>Sync Health</Text>
          )}
        </Pressable>
        {lastSync && (
          <Text style={styles.compactLastSync}>
            Last sync: {formatLastSync(lastSync)}
          </Text>
        )}
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <View style={styles.headerRow}>
          <Text style={styles.title}>Apple Health Bridge</Text>
          <View
            style={[
              styles.statusDot,
              { backgroundColor: healthKitAvailable ? SUCCESS : DANGER },
            ]}
          />
        </View>

        {/* Sync Button */}
        <Pressable
          style={[styles.syncButton, isSyncing && styles.syncButtonDisabled]}
          onPress={syncHealthData}
          disabled={isSyncing}
        >
          {isSyncing ? (
            <View style={styles.syncButtonContent}>
              <ActivityIndicator color="#FFFFFF" size="small" />
              <Text style={styles.syncButtonText}>Syncing...</Text>
            </View>
          ) : (
            <Text style={styles.syncButtonText}>Sync Now</Text>
          )}
        </Pressable>

        {/* Last Sync Timestamp */}
        {lastSync && (
          <Text style={styles.lastSyncText}>
            Last synced at {formatLastSync(lastSync)}
          </Text>
        )}

        {/* Error Display */}
        {syncError && (
          <Pressable onPress={() => setSyncError(null)} style={styles.errorContainer}>
            <Text style={styles.errorText}>{syncError}</Text>
            <Text style={styles.errorDismiss}>Tap to dismiss</Text>
          </Pressable>
        )}

        {/* Synced Metrics Display */}
        {syncedData && (
          <View style={styles.metricsContainer}>
            <MetricRow
              label="Steps"
              value={syncedData.steps !== null ? syncedData.steps.toLocaleString() : "--"}
              color={ACCENT}
            />
            <MetricRow
              label="Heart Rate (avg)"
              value={
                syncedData.heartRateSamples.length > 0
                  ? `${Math.round(
                      syncedData.heartRateSamples.reduce((s, r) => s + r.value, 0) /
                        syncedData.heartRateSamples.length
                    )} bpm`
                  : "--"
              }
              color={DANGER}
            />
            <MetricRow
              label="Sleep"
              value={syncedData.sleepHours !== null ? `${syncedData.sleepHours}h` : "--"}
              color="#A78BFA"
            />
            <MetricRow
              label="Active Energy"
              value={
                syncedData.activeEnergy !== null ? `${syncedData.activeEnergy} kcal` : "--"
              }
              color={SUCCESS}
            />
          </View>
        )}
      </View>
    </View>
  );
}

function MetricRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <View style={styles.metricRow}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, { color }]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  card: {
    backgroundColor: CARD_BG,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: "#222230",
  },
  loadingCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  loadingText: {
    color: TEXT_SECONDARY,
    fontSize: 14,
  },

  // Header
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 16,
  },
  title: {
    fontSize: 16,
    fontWeight: "700",
    color: TEXT_PRIMARY,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },

  // Sync Button
  syncButton: {
    backgroundColor: ACCENT,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },
  syncButtonDisabled: {
    opacity: 0.6,
  },
  syncButtonContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  syncButtonText: {
    fontSize: 15,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  lastSyncText: {
    fontSize: 12,
    color: TEXT_SECONDARY,
    textAlign: "center",
    marginBottom: 12,
  },

  // Compact
  compactSyncButton: {
    backgroundColor: ACCENT,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  compactSyncText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  compactLastSync: {
    fontSize: 11,
    color: TEXT_SECONDARY,
    textAlign: "center",
    marginTop: 6,
  },

  // Error
  errorContainer: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    backgroundColor: "#2D1418",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#EF444440",
    alignItems: "center",
    marginBottom: 12,
  },
  errorText: {
    fontSize: 13,
    color: DANGER,
    textAlign: "center",
    lineHeight: 18,
  },
  errorDismiss: {
    fontSize: 11,
    color: TEXT_SECONDARY,
    marginTop: 4,
  },

  // Metrics
  metricsContainer: {
    borderTopWidth: 1,
    borderTopColor: "#222230",
    paddingTop: 14,
    gap: 12,
  },
  metricRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  metricLabel: {
    fontSize: 14,
    color: TEXT_SECONDARY,
    fontWeight: "500",
  },
  metricValue: {
    fontSize: 16,
    fontWeight: "700",
  },

  // Unavailable
  unavailableTitle: {
    fontSize: 15,
    fontWeight: "700",
    color: TEXT_PRIMARY,
    marginBottom: 8,
  },
  unavailableText: {
    fontSize: 13,
    color: TEXT_SECONDARY,
    lineHeight: 20,
  },
});
