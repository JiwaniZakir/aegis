import { create } from "zustand";

/**
 * Auth store - manages JWT tokens and authentication state.
 */
interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setTokens: (access: string, refresh: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,

  setTokens: (access, refresh) =>
    set({
      accessToken: access,
      refreshToken: refresh,
      isAuthenticated: true,
    }),

  logout: () =>
    set({
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    }),
}));

/**
 * Voice store - manages voice recording/transcription/playback state.
 */
interface VoiceState {
  isRecording: boolean;
  isTranscribing: boolean;
  isPlaying: boolean;
  transcript: string | null;
  lastResponse: string | null;
  error: string | null;

  setRecording: (recording: boolean) => void;
  setTranscribing: (transcribing: boolean) => void;
  setPlaying: (playing: boolean) => void;
  setTranscript: (text: string) => void;
  setLastResponse: (text: string) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useVoiceStore = create<VoiceState>((set) => ({
  isRecording: false,
  isTranscribing: false,
  isPlaying: false,
  transcript: null,
  lastResponse: null,
  error: null,

  setRecording: (recording) => set({ isRecording: recording, error: null }),
  setTranscribing: (transcribing) => set({ isTranscribing: transcribing }),
  setPlaying: (playing) => set({ isPlaying: playing }),
  setTranscript: (text) => set({ transcript: text }),
  setLastResponse: (text) => set({ lastResponse: text }),
  setError: (error) => set({ error, isRecording: false, isTranscribing: false }),
  reset: () =>
    set({
      isRecording: false,
      isTranscribing: false,
      isPlaying: false,
      transcript: null,
      lastResponse: null,
      error: null,
    }),
}));
