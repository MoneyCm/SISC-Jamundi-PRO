const CORE_PERIOD_SOURCES = ['POLICIA_SEMANAL', 'INSPECCIONES_RNMC'];

const latestCutoff = (sources = []) => sources
  .map((source) => source?.last_cutoff_date)
  .filter(Boolean)
  .sort()
  .at(-1);

export const latestSiscCifrasCutoff = (
  sources = [],
  fallbackDate = new Date().toISOString().slice(0, 10),
) => {
  const coreSources = sources.filter((source) => CORE_PERIOD_SOURCES.includes(source?.code));
  return latestCutoff(coreSources) || latestCutoff(sources) || fallbackDate;
};

export const suggestedSiscCifrasPeriod = (
  sources = [],
  edition = 'weekly',
  fallbackDate = new Date().toISOString().slice(0, 10),
) => {
  const endIso = latestSiscCifrasCutoff(sources, fallbackDate);
  const end = new Date(`${endIso}T12:00:00`);
  const start = new Date(end);

  if (edition === 'monthly') start.setDate(1);
  else if (edition === 'semester') {
    start.setDate(1);
    start.setMonth(start.getMonth() - 5);
  } else if (edition === 'annual') {
    start.setMonth(0, 1);
  }
  else start.setDate(start.getDate() - 6);

  return { start: start.toISOString().slice(0, 10), end: endIso };
};

export const institutionalSiscCifrasPeriods = (sources = [], fallbackDate) => {
  const cutoff = latestSiscCifrasCutoff(sources, fallbackDate);
  const cutoffYear = Number(cutoff.slice(0, 4));
  const firstSemesterYear = cutoff >= `${cutoffYear}-06-30` ? cutoffYear : cutoffYear - 1;
  const secondSemesterYear = cutoff >= `${cutoffYear}-12-31` ? cutoffYear : cutoffYear - 1;
  const closedYear = cutoff >= `${cutoffYear}-12-31` ? cutoffYear : cutoffYear - 1;

  return [
    {
      id: 'first_semester',
      edition: 'semester',
      label: `Enero a junio de ${firstSemesterYear}`,
      start: `${firstSemesterYear}-01-01`,
      end: `${firstSemesterYear}-06-30`,
    },
    {
      id: 'second_semester',
      edition: 'semester',
      label: `Julio a diciembre de ${secondSemesterYear}`,
      start: `${secondSemesterYear}-07-01`,
      end: `${secondSemesterYear}-12-31`,
    },
    {
      id: 'closed_year',
      edition: 'annual',
      label: `Año completo ${closedYear}`,
      start: `${closedYear}-01-01`,
      end: `${closedYear}-12-31`,
    },
  ];
};
