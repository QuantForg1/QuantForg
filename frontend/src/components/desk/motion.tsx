"use client";

import { memo, type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";
import { OS_DURATION, OS_EASE, osTransition } from "@/lib/motion/os";

export const PageMotion = memo(function PageMotion({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={cn("space-y-[var(--space-5)]", className)}
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={osTransition}
    >
      {children}
    </motion.div>
  );
});

export const StaggerGrid = memo(function StaggerGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduce ? false : "hidden"}
      animate="show"
      variants={{
        hidden: {},
        show: {
          transition: { staggerChildren: reduce ? 0 : 0.04 },
        },
      }}
    >
      {children}
    </motion.div>
  );
});

export const StaggerItem = memo(function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: 6 },
        show: { opacity: 1, y: 0 },
      }}
      transition={{ duration: OS_DURATION, ease: OS_EASE }}
    >
      {children}
    </motion.div>
  );
});
