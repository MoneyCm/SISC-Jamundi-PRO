const saveBlob = (filename, blob) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
};

const csvCell = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`;

export const downloadCsvFile = (filename, headers, rows) => {
    const body = [headers, ...rows].map((row) => row.map(csvCell).join(';')).join('\n');
    saveBlob(filename, new Blob([`\uFEFF${body}`], { type: 'text/csv;charset=utf-8' }));
};

export const downloadJsonFile = (filename, payload) => {
    const body = JSON.stringify(payload, null, 2);
    saveBlob(filename, new Blob([body], { type: 'application/json;charset=utf-8' }));
};

export const downloadXlsxFile = async (filename, sheets) => {
    const xlsxModule = await import('xlsx');
    const XLSX = xlsxModule.default || xlsxModule;
    const workbook = XLSX.utils.book_new();

    sheets.forEach(({ name, rows = [] }) => {
        const worksheet = Array.isArray(rows[0])
            ? XLSX.utils.aoa_to_sheet(rows)
            : XLSX.utils.json_to_sheet(rows);
        XLSX.utils.book_append_sheet(workbook, worksheet, name.slice(0, 31));
    });

    XLSX.writeFile(workbook, filename, { compression: true });
};
