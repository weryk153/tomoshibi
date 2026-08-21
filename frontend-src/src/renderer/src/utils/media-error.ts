/**
 * Turn a getUserMedia / getDisplayMedia rejection into something a person can act on.
 *
 * These paths used to put the exception straight into the toast title
 * (`啟動失敗: NotReadableError: x`), which tells the user the browser's internal
 * name and nothing about what to do. The DOMException `name` distinguishes three
 * situations whose remedies are completely different — no permission, no device,
 * device busy — so it is worth splitting them.
 */
export type MediaErrorKind = 'denied' | 'notFound' | 'inUse' | 'unknown';

export function classifyMediaError(error: unknown): MediaErrorKind {
  const name = (error as { name?: string } | null)?.name;
  switch (name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'denied';
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'notFound';
    case 'NotReadableError':
    case 'AbortError':
      return 'inUse';
    default:
      return 'unknown';
  }
}

const CAMERA_KEYS: Record<MediaErrorKind, string> = {
  denied: 'settings.general.cameraDenied',
  notFound: 'settings.general.cameraNotFound',
  inUse: 'settings.general.cameraInUse',
  unknown: 'settings.general.cameraFailed',
};

export function cameraErrorKey(error: unknown): string {
  return CAMERA_KEYS[classifyMediaError(error)];
}

/**
 * Whether a screen-capture rejection is really just the user closing the picker.
 *
 * getDisplayMedia rejects with NotAllowedError both when permission is refused
 * and when the user simply cancels the "choose what to share" dialog. Cancelling
 * is a normal action, not a failure — showing a red error toast for it tells
 * people they broke something when they only changed their mind.
 */
export function isScreenPickerDismissed(error: unknown): boolean {
  return classifyMediaError(error) === 'denied';
}

const MICROPHONE_KEYS: Partial<Record<MediaErrorKind, string>> = {
  denied: 'error.micDenied',
  notFound: 'error.micNotFound',
  inUse: 'error.micInUse',
};

/**
 * Message key for a microphone failure, or null when the cause is not a
 * permission/device problem.
 *
 * Voice input starts through MicVAD, which calls getUserMedia — so a denied
 * permission surfaces here as a DOMException, and that is by far the most
 * common way voice input fails. But the same call can also fail for reasons
 * with no actionable name (the onnxruntime model failing to load, a wasm
 * problem). Returning null for those lets the caller keep showing the raw
 * error, which is the only diagnostic available — better than replacing it
 * with a generic sentence that helps nobody.
 */
export function microphoneErrorKey(error: unknown): string | null {
  return MICROPHONE_KEYS[classifyMediaError(error)] ?? null;
}
