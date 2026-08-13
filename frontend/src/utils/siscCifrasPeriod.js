const CORE_PERIOD_SOURCES = ['POLICIA_SEMANAL', 'INSPECCIONES_RNMC'];

const latestCutoff = (sources = []) => sources
  .map((source) => source?.last_cutoff_date)
  .filter(Boolean)
  .sort()
  .at(-1);

export const suggestedSiscCifrasPeriod = (
  sources = [],
  edition = 'weekly',
  fallbackDate = new Date().toISOString().slice(0, 10),
) => {
  const coreSources = sources.filter((source) => CORE_PERIOD_SOURCES.includes(source?.code));
  const endIso = latestCutoff(coreSources) || latestCutoff(sources) || fallbackDate;
  const end = new Date(`${endIso}T12:00:00`);
  const start = new Date(end);

  if (edition === 'monthly') start.setDate(1);
  else start.setDate(start.getDate() - 6);

  return { start: start.toISOString().slice(0, 10), end: endIso };
};
