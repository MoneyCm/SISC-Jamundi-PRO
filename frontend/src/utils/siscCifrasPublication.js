const normalizedSourceCodes = (sourceCodes = []) =>
  [...sourceCodes].map(String).sort();

export const siscCifrasSelectionKey = ({
  edition,
  periodStart,
  periodEnd,
  comparisonMode,
  sourceCodes,
}) => JSON.stringify({
  edition,
  periodStart,
  periodEnd,
  comparisonMode,
  sourceCodes: normalizedSourceCodes(sourceCodes),
});
