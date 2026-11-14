export const ALLOWED_AUDIO = ["wav", "mp3", "m4a", "ogg", "flac"];
export const MAX_AUDIO_BYTES = 25 * 1024 * 1024;

/** The same checks the API makes, so a bad file is refused before it is uploaded. */
export function validateAudioFile(file: File): string | undefined {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED_AUDIO.includes(ext)) return "Not a supported audio file. Use wav, mp3, m4a, ogg or flac.";
  if (file.size > MAX_AUDIO_BYTES) return "Larger than 25 MB.";
  return undefined;
}
