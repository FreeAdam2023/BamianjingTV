/**
 * Play word pronunciation: tries audio URL first, falls back to browser TTS.
 */
export function playWordAudio(word: string, audioUrl?: string | null): void {
  if (audioUrl) {
    const audio = new Audio(audioUrl);
    audio.play().catch(() => {
      // Audio URL failed — fall back to TTS
      speakWord(word);
    });
    return;
  }
  speakWord(word);
}

function speakWord(word: string): void {
  if (typeof speechSynthesis === "undefined") return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(word);
  utterance.lang = "en-US";
  speechSynthesis.speak(utterance);
}
