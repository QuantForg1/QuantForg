"use client";

import { memo } from "react";
import { DeskInlineEmpty } from "@/components/desk/inline-empty";

export const CounselEmpty = memo(function CounselEmpty({
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
    />
  );
});
