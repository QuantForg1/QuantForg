/** Persist OS chrome preferences (sidebar collapse / width). Presentation only. */

const KEY = "qf.shell.chrome.v1";

export type ShellChromeState = {
  collapsed: boolean;
  width: number;
};

export const SHELL_SIDEBAR_MIN = 200;
export const SHELL_SIDEBAR_MAX = 300;
export const SHELL_SIDEBAR_DEFAULT = 240;
export const SHELL_SIDEBAR_COLLAPSED = 56;

const DEFAULT: ShellChromeState = {
  collapsed: false,
  width: SHELL_SIDEBAR_DEFAULT,
};

export function loadShellChrome(): ShellChromeState {
  if (typeof window === "undefined") return DEFAULT;
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULT;
    const parsed = JSON.parse(raw) as Partial<ShellChromeState>;
    const width = Number(parsed.width);
    return {
      collapsed: Boolean(parsed.collapsed),
      width: Number.isFinite(width)
        ? Math.min(SHELL_SIDEBAR_MAX, Math.max(SHELL_SIDEBAR_MIN, width))
        : SHELL_SIDEBAR_DEFAULT,
    };
  } catch {
    return DEFAULT;
  }
}

export function saveShellChrome(state: ShellChromeState) {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* quota */
  }
}
