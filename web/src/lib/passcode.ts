const KEY = "samaritan.upload.passcode";

/** The demo passcode lives in sessionStorage only, so it is never part of the JS bundle or persisted. */
export function getStoredPasscode(): string {
  try {
    return window.sessionStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function setStoredPasscode(value: string) {
  try {
    window.sessionStorage.setItem(KEY, value);
  } catch {
    // Session storage may be blocked; the passcode is then asked for again next time.
  }
}

export function clearStoredPasscode() {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
