/** Launch-lock display helpers — backend is source of truth. */

export function isExecutionBlockingLock(item: Record<string, unknown> | null | undefined): boolean {
  if (item == null) return false;
  if (item.passed) return false;
  if (item.blocks_execution === false) return false;
  return true;
}

export function firstBlockingLock(
  items: Array<Record<string, unknown>>,
  fromApi?: Record<string, unknown> | null,
): Record<string, unknown> | null {
  if (fromApi && Object.keys(fromApi).length > 0 && fromApi.key) {
    return fromApi;
  }
  return items.find((item) => isExecutionBlockingLock(item)) ?? null;
}
