"use client";

import { useEffect } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  RELEASE_NOTES,
  latestReleaseVersion,
} from "@/lib/platform/release-notes";
import { markReleaseSeen } from "@/lib/platform/onboarding";

export default function WhatsNewPage() {
  useEffect(() => {
    markReleaseSeen(latestReleaseVersion());
  }, []);

  return (
    <div>
      <PageHeader
        title="What's new"
        description="In-app release notes for Closed Beta — curated highlights, not a full git log."
        actions={
          <Button size="sm" variant="secondary" asChild>
            <Link href="/get-started">Get started</Link>
          </Button>
        }
      />

      <div className="space-y-4">
        {RELEASE_NOTES.map((note) => (
          <Card key={note.version}>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2">
                <span>{note.title}</span>
                <Badge tone="neutral">{note.version}</Badge>
                <span className="text-xs font-normal text-[var(--fg-muted)]">
                  {note.date}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {note.highlights.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
              {note.links?.length ? (
                <div className="flex flex-wrap gap-2">
                  {note.links.map((l) => (
                    <Button key={l.href} size="sm" variant="secondary" asChild>
                      <Link href={l.href}>{l.label}</Link>
                    </Button>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
