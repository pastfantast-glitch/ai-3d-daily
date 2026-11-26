// Live reserve inventory is distinct from the Collector's historical snapshot.
export function sourceInventory(operations, sourceId) {
  if (!operations || operations.reserve_complete !== true || !Array.isArray(operations.reserve)) return null;
  const supply = operations.source_supply?.find(row => row.source_id === sourceId);
  if (!supply || !Number.isInteger(supply.reserve) || supply.reserve < 0) return null;
  const rows = operations.reserve.filter(row => row.source_id === sourceId);
  return {total: rows.length, pending: supply.reserve,
    unavailable: rows.filter(row => row.state === 'source_unavailable').length,
    checkedAt: operations.checked_at};
}
