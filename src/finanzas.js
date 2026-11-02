// Smart Finance — atajo para HTTP Shortcuts (Android)
// Primera versión: registra un gasto en la base de datos Movimientos de Notion.
// El token se guarda en una variable global de HTTP Shortcuts llamada notion_token.

const MOVIMIENTOS = 'd77b034da9bd483ca6e44b045e205351';

const HEADERS = {
  'Authorization': 'Bearer ' + getVariable('notion_token'),
  'Notion-Version': '2022-06-28',
  'Content-Type': 'application/json',
};

const concepto = prompt('¿En qué lo gastaste?', '');
const importe = parseFloat(prompt('¿Cuánto?', ''));

// TODO: elegir cuenta y categoría
// TODO: validar el importe (con coma no funciona)

const r = sendHttpRequest('https://api.notion.com/v1/pages', {
  method: 'POST',
  headers: HEADERS,
  body: JSON.stringify({
    parent: { database_id: MOVIMIENTOS },
    properties: {
      'Concepto': { title: [{ text: { content: concepto } }] },
      'Tipo': { select: { name: 'Gasto' } },
      'Importe': { number: importe },
      'Fecha': { date: { start: new Date().toISOString() } },
    },
  }),
});

showToast(r.status === 'success' ? 'Gasto guardado' : 'Error: ' + r.response.body);
