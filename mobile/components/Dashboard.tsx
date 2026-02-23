import { View, Text, StyleSheet } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../lib/api";

const CARD_BG = "#16161F";
const TEXT_PRIMARY = "#EEEEF0";
const TEXT_SECONDARY = "#8E8EA0";
const ACCENT = "#6C63FF";
const SUCCESS = "#34D399";
const WARNING = "#FBBF24";
const DANGER = "#EF4444";

interface FinancialSnapshot {
  total_balance: number;
  monthly_spend: number;
  monthly_budget: number;
  recent_transactions: Array<{
    description: string;
    amount: number;
    date: string;
  }>;
}

interface CalendarEvent {
  title: string;
  start_time: string;
  end_time: string;
  location?: string;
}

export function Dashboard() {
  return (
    <View style={styles.container}>
      <FinanceSection />
      <CalendarSection />
    </View>
  );
}

function FinanceSection() {
  const { data, isLoading } = useQuery<FinancialSnapshot>({
    queryKey: ["finance-snapshot"],
    queryFn: () => apiClient.getFinanceSnapshot(),
  });

  const spendPercent = data
    ? Math.round((data.monthly_spend / data.monthly_budget) * 100)
    : 0;

  const spendColor = spendPercent > 90 ? DANGER : spendPercent > 70 ? WARNING : SUCCESS;

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Financial Snapshot</Text>
      <View style={styles.card}>
        {isLoading ? (
          <Text style={styles.loadingText}>Loading financial data...</Text>
        ) : data ? (
          <>
            <View style={styles.financeRow}>
              <View style={styles.financeMetric}>
                <Text style={styles.financeLabel}>Total Balance</Text>
                <Text style={[styles.financeValue, { color: SUCCESS }]}>
                  ${data.total_balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </Text>
              </View>
              <View style={styles.financeMetric}>
                <Text style={styles.financeLabel}>Monthly Spend</Text>
                <Text style={[styles.financeValue, { color: spendColor }]}>
                  ${data.monthly_spend.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </Text>
                <Text style={styles.financeBudget}>
                  of ${data.monthly_budget.toLocaleString("en-US")} budget
                </Text>
              </View>
            </View>

            {/* Spend Progress Bar */}
            <View style={styles.progressContainer}>
              <View style={styles.progressBg}>
                <View
                  style={[
                    styles.progressFill,
                    {
                      width: `${Math.min(spendPercent, 100)}%`,
                      backgroundColor: spendColor,
                    },
                  ]}
                />
              </View>
              <Text style={[styles.progressLabel, { color: spendColor }]}>
                {spendPercent}%
              </Text>
            </View>

            {/* Recent Transactions */}
            {data.recent_transactions.length > 0 && (
              <View style={styles.transactionsList}>
                <Text style={styles.subLabel}>Recent</Text>
                {data.recent_transactions.slice(0, 3).map((tx, idx) => (
                  <View key={idx} style={styles.transactionRow}>
                    <Text style={styles.transactionDesc} numberOfLines={1}>
                      {tx.description}
                    </Text>
                    <Text
                      style={[
                        styles.transactionAmount,
                        { color: tx.amount < 0 ? DANGER : SUCCESS },
                      ]}
                    >
                      {tx.amount < 0 ? "-" : "+"}$
                      {Math.abs(tx.amount).toFixed(2)}
                    </Text>
                  </View>
                ))}
              </View>
            )}
          </>
        ) : (
          <Text style={styles.emptyText}>No financial data available</Text>
        )}
      </View>
    </View>
  );
}

function CalendarSection() {
  const { data, isLoading } = useQuery<CalendarEvent[]>({
    queryKey: ["calendar-today"],
    queryFn: () => apiClient.getTodayEvents(),
  });

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Today's Schedule</Text>
      <View style={styles.card}>
        {isLoading ? (
          <Text style={styles.loadingText}>Loading calendar...</Text>
        ) : data && data.length > 0 ? (
          data.map((event, idx) => (
            <View
              key={idx}
              style={[styles.eventRow, idx < data.length - 1 && styles.eventRowBorder]}
            >
              <View style={styles.eventTimeline}>
                <View style={styles.eventDot} />
                {idx < data.length - 1 && <View style={styles.eventLine} />}
              </View>
              <View style={styles.eventContent}>
                <Text style={styles.eventTitle}>{event.title}</Text>
                <Text style={styles.eventTime}>
                  {formatTime(event.start_time)} - {formatTime(event.end_time)}
                </Text>
                {event.location && (
                  <Text style={styles.eventLocation}>{event.location}</Text>
                )}
              </View>
            </View>
          ))
        ) : (
          <Text style={styles.emptyText}>No events scheduled today</Text>
        )}
      </View>
    </View>
  );
}

function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

const styles = StyleSheet.create({
  container: {
    gap: 0,
  },
  section: {
    marginBottom: 24,
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
  },

  // Finance
  financeRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  financeMetric: {
    flex: 1,
  },
  financeLabel: {
    fontSize: 12,
    color: TEXT_SECONDARY,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  financeValue: {
    fontSize: 22,
    fontWeight: "800",
  },
  financeBudget: {
    fontSize: 11,
    color: TEXT_SECONDARY,
    marginTop: 2,
  },

  // Progress Bar
  progressContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
  },
  progressBg: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#222230",
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 3,
  },
  progressLabel: {
    fontSize: 12,
    fontWeight: "700",
    minWidth: 36,
    textAlign: "right",
  },

  // Transactions
  transactionsList: {
    borderTopWidth: 1,
    borderTopColor: "#222230",
    paddingTop: 12,
  },
  subLabel: {
    fontSize: 11,
    color: TEXT_SECONDARY,
    fontWeight: "600",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  transactionRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 6,
  },
  transactionDesc: {
    flex: 1,
    fontSize: 14,
    color: TEXT_PRIMARY,
    marginRight: 12,
  },
  transactionAmount: {
    fontSize: 14,
    fontWeight: "700",
  },

  // Calendar Events
  eventRow: {
    flexDirection: "row",
    paddingBottom: 16,
  },
  eventRowBorder: {},
  eventTimeline: {
    width: 24,
    alignItems: "center",
    paddingTop: 4,
  },
  eventDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: ACCENT,
  },
  eventLine: {
    width: 2,
    flex: 1,
    backgroundColor: "#2A2A4A",
    marginTop: 4,
  },
  eventContent: {
    flex: 1,
    paddingLeft: 12,
  },
  eventTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: TEXT_PRIMARY,
    marginBottom: 4,
  },
  eventTime: {
    fontSize: 13,
    color: ACCENT,
    fontWeight: "500",
  },
  eventLocation: {
    fontSize: 12,
    color: TEXT_SECONDARY,
    marginTop: 2,
  },
});
