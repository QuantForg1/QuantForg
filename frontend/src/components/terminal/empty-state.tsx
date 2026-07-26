"use client";

import { memo } from "react";
import { DeskInlineEmpty } from "@/components/desk/inline-empty";

/** Calm empty surface for Terminal panels — never invent data. */
export const TerminalEmpty = memo(function TerminalEmpty({
  title,
  description,
  className,
  action,
}: {
  title: string;
  description?: string;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <DeskInlineEmpty
      title={title}
      description={description}
      className={className}
      action={action}
      minHeight="8rem"
    />
  );
});
