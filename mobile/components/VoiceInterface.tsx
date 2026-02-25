import { useEffect, useRef, useCallback } from "react";
import { View, Text, Pressable, StyleSheet, Animated } from "react-native";
import { Audio } from "expo-av";
import * as Speech from "expo-speech";
import { useVoiceStore } from "../lib/store";
import { apiClient } from "../lib/api";

const ACCENT = "#6C63FF";
const ACCENT_DIM = "#4A42CC";
const RECORDING_COLOR = "#EF4444";
const TEXT_PRIMARY = "#EEEEF0";
const TEXT_SECONDARY = "#8E8EA0";
const DARK_BG = "#0A0A0F";

const NUM_BARS = 12;

export function VoiceInterface() {
  const isRecording = useVoiceStore((s) => s.isRecording);
  const isPlaying = useVoiceStore((s) => s.isPlaying);
  const isTranscribing = useVoiceStore((s) => s.isTranscribing);
  const setRecording = useVoiceStore((s) => s.setRecording);
  const setTranscribing = useVoiceStore((s) => s.setTranscribing);
  const setPlaying = useVoiceStore((s) => s.setPlaying);
  const setTranscript = useVoiceStore((s) => s.setTranscript);
  const setLastResponse = useVoiceStore((s) => s.setLastResponse);

  const error = useVoiceStore((s) => s.error);
  const setError = useVoiceStore((s) => s.setError);

  const recordingRef = useRef<Audio.Recording | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const barAnims = useRef(
    Array.from({ length: NUM_BARS }, () => new Animated.Value(0.3))
  ).current;

  // Pulse animation for the mic button while recording
  useEffect(() => {
    if (isRecording) {
      const pulse = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.15,
            duration: 600,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 600,
            useNativeDriver: true,
          }),
        ])
      );
      pulse.start();
      return () => pulse.stop();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording, pulseAnim]);

  // Waveform bar animation while recording or playing
  useEffect(() => {
    if (isRecording || isPlaying) {
      const animations = barAnims.map((anim, i) =>
        Animated.loop(
          Animated.sequence([
            Animated.timing(anim, {
              toValue: 0.5 + Math.random() * 0.5,
              duration: 200 + Math.random() * 300,
              useNativeDriver: true,
              delay: i * 40,
            }),
            Animated.timing(anim, {
              toValue: 0.2 + Math.random() * 0.3,
              duration: 200 + Math.random() * 300,
              useNativeDriver: true,
            }),
          ])
        )
      );
      const composite = Animated.parallel(animations);
      composite.start();
      return () => composite.stop();
    } else {
      barAnims.forEach((anim) => {
        Animated.timing(anim, {
          toValue: 0.3,
          duration: 300,
          useNativeDriver: true,
        }).start();
      });
    }
  }, [isRecording, isPlaying, barAnims]);

  const startRecording = useCallback(async () => {
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) {
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );

      recordingRef.current = recording;
      setRecording(true);
    } catch (err) {
      console.error("Failed to start recording:", err);
    }
  }, [setRecording]);

  const stopRecording = useCallback(async () => {
    if (!recordingRef.current) return;

    try {
      setRecording(false);
      setTranscribing(true);

      await recordingRef.current.stopAndUnloadAsync();

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: false,
      });

      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      if (!uri) {
        setTranscribing(false);
        return;
      }

      // Send audio to backend for STT (Whisper API)
      const transcriptResult = await apiClient.transcribeAudio(uri);
      setTranscript(transcriptResult.text);
      setTranscribing(false);

      // Send transcript to backend for processing and get response
      const responseResult = await apiClient.processVoiceQuery(transcriptResult.text);
      setLastResponse(responseResult.text);

      // Play TTS: prefer backend audio_url, fall back to expo-speech on-device TTS
      if (responseResult.audio_url) {
        await playResponse(responseResult.audio_url);
      } else if (responseResult.text) {
        await speakResponse(responseResult.text);
      }
    } catch (err) {
      console.error("Failed to process recording:", err);
      setTranscribing(false);
      setError(
        err instanceof Error ? err.message : "Failed to process voice input. Please try again."
      );
    }
  }, [setRecording, setTranscribing, setTranscript, setLastResponse, setError]);

  const playResponse = useCallback(
    async (audioUrl: string) => {
      try {
        setPlaying(true);

        const { sound } = await Audio.Sound.createAsync(
          { uri: audioUrl },
          { shouldPlay: true }
        );

        soundRef.current = sound;

        sound.setOnPlaybackStatusUpdate((status) => {
          if (status.isLoaded && status.didJustFinish) {
            setPlaying(false);
            sound.unloadAsync();
            soundRef.current = null;
          }
        });
      } catch (err) {
        console.error("Failed to play response audio:", err);
        setPlaying(false);
      }
    },
    [setPlaying]
  );

  const speakResponse = useCallback(
    async (text: string) => {
      try {
        setPlaying(true);

        // Stop any in-progress speech before starting new utterance
        await Speech.stop();

        Speech.speak(text, {
          language: "en-US",
          pitch: 1.0,
          rate: 0.95,
          onDone: () => {
            setPlaying(false);
          },
          onError: () => {
            console.error("expo-speech TTS error");
            setPlaying(false);
          },
          onStopped: () => {
            setPlaying(false);
          },
        });
      } catch (err) {
        console.error("Failed to speak response:", err);
        setPlaying(false);
      }
    },
    [setPlaying]
  );

  const handleMicPress = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  const statusLabel = isRecording
    ? "Listening..."
    : isTranscribing
      ? "Transcribing..."
      : isPlaying
        ? "Speaking..."
        : "Tap to speak";

  const isActive = isRecording || isPlaying;

  return (
    <View style={styles.container}>
      {/* Waveform Visualization */}
      <View style={styles.waveformContainer}>
        {barAnims.map((anim, i) => (
          <Animated.View
            key={i}
            style={[
              styles.waveformBar,
              {
                backgroundColor: isRecording ? RECORDING_COLOR : ACCENT,
                transform: [{ scaleY: anim }],
              },
            ]}
          />
        ))}
      </View>

      {/* Mic Button */}
      <Animated.View style={[styles.micButtonOuter, { transform: [{ scale: pulseAnim }] }]}>
        <Pressable
          style={[
            styles.micButton,
            isRecording && styles.micButtonRecording,
          ]}
          onPress={handleMicPress}
          disabled={isTranscribing || isPlaying}
        >
          <View style={styles.micIconContainer}>
            {isRecording ? (
              <View style={styles.stopIcon} />
            ) : (
              <View style={styles.micIcon}>
                <View style={styles.micHead} />
                <View style={styles.micStem} />
                <View style={styles.micBase} />
              </View>
            )}
          </View>
        </Pressable>
      </Animated.View>

      {/* Status Label */}
      <Text style={[styles.statusLabel, isActive && styles.statusLabelActive]}>
        {statusLabel}
      </Text>

      {/* Error Display */}
      {error && (
        <Pressable onPress={() => setError(null)} style={styles.errorContainer}>
          <Text style={styles.errorText}>{error}</Text>
          <Text style={styles.errorDismiss}>Tap to dismiss</Text>
        </Pressable>
      )}

      {/* Stop Speaking Button */}
      {isPlaying && (
        <Pressable
          style={styles.stopSpeakingButton}
          onPress={() => {
            Speech.stop();
            soundRef.current?.stopAsync();
            setPlaying(false);
          }}
        >
          <Text style={styles.stopSpeakingText}>Stop Speaking</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    paddingVertical: 12,
  },

  // Waveform
  waveformContainer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    height: 48,
    gap: 4,
    marginBottom: 20,
  },
  waveformBar: {
    width: 4,
    height: 40,
    borderRadius: 2,
  },

  // Mic Button
  micButtonOuter: {
    marginBottom: 16,
  },
  micButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: ACCENT,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: ACCENT,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 8,
  },
  micButtonRecording: {
    backgroundColor: RECORDING_COLOR,
    shadowColor: RECORDING_COLOR,
  },
  micIconContainer: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  stopIcon: {
    width: 20,
    height: 20,
    borderRadius: 3,
    backgroundColor: "#FFFFFF",
  },
  micIcon: {
    alignItems: "center",
  },
  micHead: {
    width: 12,
    height: 16,
    borderRadius: 6,
    backgroundColor: "#FFFFFF",
  },
  micStem: {
    width: 2,
    height: 6,
    backgroundColor: "#FFFFFF",
    marginTop: 2,
  },
  micBase: {
    width: 16,
    height: 2,
    borderRadius: 1,
    backgroundColor: "#FFFFFF",
    marginTop: 1,
  },

  // Status
  statusLabel: {
    fontSize: 14,
    color: TEXT_SECONDARY,
    fontWeight: "600",
  },
  statusLabelActive: {
    color: TEXT_PRIMARY,
  },

  // Error
  errorContainer: {
    marginTop: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: "#2D1418",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#EF444440",
    alignItems: "center",
    maxWidth: 280,
  },
  errorText: {
    fontSize: 13,
    color: "#EF4444",
    textAlign: "center",
    lineHeight: 18,
  },
  errorDismiss: {
    fontSize: 11,
    color: TEXT_SECONDARY,
    marginTop: 4,
  },

  // Stop Speaking
  stopSpeakingButton: {
    marginTop: 12,
    paddingHorizontal: 20,
    paddingVertical: 8,
    backgroundColor: "#222230",
    borderRadius: 20,
  },
  stopSpeakingText: {
    fontSize: 13,
    color: TEXT_SECONDARY,
    fontWeight: "600",
  },
});
