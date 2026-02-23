import { View, Text, ScrollView, StyleSheet } from "react-native";
import { VoiceInterface } from "../components/VoiceInterface";
import { useVoiceStore } from "../lib/store";

const DARK_BG = "#0A0A0F";
const CARD_BG = "#16161F";
const TEXT_PRIMARY = "#EEEEF0";
const TEXT_SECONDARY = "#8E8EA0";
const ACCENT = "#6C63FF";

export default function VoiceScreen() {
  const transcript = useVoiceStore((s) => s.transcript);
  const response = useVoiceStore((s) => s.lastResponse);
  const isTranscribing = useVoiceStore((s) => s.isTranscribing);

  return (
    <View style={styles.container}>
      {/* Transcript Area */}
      <ScrollView style={styles.transcriptArea} contentContainerStyle={styles.transcriptContent}>
        {transcript ? (
          <View style={styles.messageBubble}>
            <Text style={styles.messageLabel}>You</Text>
            <Text style={styles.messageText}>{transcript}</Text>
          </View>
        ) : (
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>Ask ClawdBot anything</Text>
            <Text style={styles.emptySubtitle}>
              Tap the microphone to start speaking. Ask about your finances, schedule, health
              metrics, or anything else.
            </Text>
          </View>
        )}

        {isTranscribing && (
          <View style={styles.statusRow}>
            <Text style={styles.statusText}>Transcribing...</Text>
          </View>
        )}

        {response && (
          <View style={[styles.messageBubble, styles.responseBubble]}>
            <Text style={[styles.messageLabel, { color: ACCENT }]}>ClawdBot</Text>
            <Text style={styles.messageText}>{response}</Text>
          </View>
        )}
      </ScrollView>

      {/* Voice Interface */}
      <View style={styles.voiceArea}>
        <VoiceInterface />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: DARK_BG,
  },
  transcriptArea: {
    flex: 1,
  },
  transcriptContent: {
    padding: 20,
    paddingBottom: 40,
  },
  emptyState: {
    alignItems: "center",
    justifyContent: "center",
    paddingTop: 80,
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: 22,
    fontWeight: "700",
    color: TEXT_PRIMARY,
    marginBottom: 12,
    textAlign: "center",
  },
  emptySubtitle: {
    fontSize: 15,
    color: TEXT_SECONDARY,
    textAlign: "center",
    lineHeight: 22,
  },
  messageBubble: {
    backgroundColor: CARD_BG,
    borderRadius: 14,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: "#222230",
  },
  responseBubble: {
    borderColor: "#2A2A4A",
  },
  messageLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: TEXT_SECONDARY,
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  messageText: {
    fontSize: 16,
    color: TEXT_PRIMARY,
    lineHeight: 24,
  },
  statusRow: {
    alignItems: "center",
    paddingVertical: 8,
  },
  statusText: {
    fontSize: 13,
    color: ACCENT,
    fontWeight: "600",
  },
  voiceArea: {
    paddingBottom: 40,
    paddingTop: 12,
    backgroundColor: DARK_BG,
    borderTopWidth: 1,
    borderTopColor: "#1A1A24",
  },
});
