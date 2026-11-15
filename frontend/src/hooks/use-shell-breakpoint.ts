"use client";

import { useEffect, useState } from "react";

/** Shell chrome treats viewports below 1024px as mobile / compact desk. */
export const SHELL_MOBILE_MQ = "(max-width: 1023px)";

export function useShellBreakpoint(): { isShellMobile: boolean } {
  const [isShellMobile, setIsShellMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(SHELL_MOBILE_MQ);
    const apply = () => setIsShellMobile(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);

  return { isShellMobile };
}