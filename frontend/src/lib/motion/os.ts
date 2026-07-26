"use client";

/**
 * RC2 motion constants — single language for Framer Motion desks.
 * Keep in sync with CSS tokens in globals.css (180–220ms).
 */
export const OS_EASE = [0.2, 0.8, 0.2, 1] as const;
export const OS_EASE_OUT = [0.16, 1, 0.3, 1] as const;
export const OS_DURATION = 0.2;
export const OS_DURATION_FAST = 0.16;
export const OS_DURATION_SLOW = 0.22;

export const osTransition = {
  duration: OS_DURATION,
  ease: OS_EASE,
} as const;

export const osTransitionFast = {
  duration: OS_DURATION_FAST,
  ease: OS_EASE,
} as const;

export const osTransitionOut = {
  duration: OS_DURATION,
  ease: OS_EASE_OUT,
} as const;
