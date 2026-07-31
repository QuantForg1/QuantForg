import { BrandMark } from "@/components/brand/brand-logo";
import { Skeleton } from "@/components/ui/skeleton";

export default function Loading() {
  return (
    <div
      className="mx-auto flex w-full max-w-[1600px] flex-col items-center gap-6 p-6"
      aria-busy="true"
      aria-live="polite"
    >
      <BrandMark size={48} className="opacity-90" />
      <div className="w-full space-y-4">
        <Skeleton className="mx-auto h-8 w-48" />
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
      <span className="sr-only">Loading QuantForg</span>
    </div>
  );
}
