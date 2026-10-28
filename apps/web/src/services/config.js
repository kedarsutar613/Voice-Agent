// VITE_* values are public build-time configuration. Never put secrets here.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api/v1"
).replace(/\/+$/, "");
const VOICE_WS_URL = import.meta.env.VITE_VOICE_WS_URL || "";

export function voiceSocketUrl(
  ticket,
  apiBaseUrl = API_BASE_URL,
  override = VOICE_WS_URL,
) {
  const url = new URL(
    override || `${apiBaseUrl.replace(/\/+$/, "")}/voice/ws`,
    window.location.origin,
  );
  if (url.protocol === "https:") url.protocol = "wss:";
  else if (url.protocol === "http:") url.protocol = "ws:";
  url.searchParams.set("ticket", ticket);
  return url.toString();
}
