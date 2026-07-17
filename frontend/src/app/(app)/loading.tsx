import { DeskSkeleton } from "@/components/desk/primitives";

export default function AppLoading() {
  return (
    <div aria-live="polite">
      <DeskSkeleton variant="page" />
      <span className="sr-only">Loading workspace</span>
    </div>
  );
}
