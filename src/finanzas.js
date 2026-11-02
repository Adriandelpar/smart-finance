// Smart Finance — atajo para HTTP Shortcuts (Android)
// Registra un gasto en Notion eligiendo cuenta y categoría.
// El token se guarda en una variable global de HTTP Shortcuts llamada notion_token.

const DB = {
  cuentas:     'f9254c6213a740ad9bb2f18b01ad98c1',
  categorias:  '54af8712b04145e8b0356ac0b7e7423d',
  movimientos: 'd77b034da9bd483ca6e44b045e205351',
};

const HEADERS = {
  'Authorization': 'Bearer ' + getVariable('notion_token'),
  'Notion-Version': '2022-06-28',
  'Content-Type': 'application/json',
};

function api(method, path, body) {
  const options = { method: method, headers: HEADERS };
  if (body) options.body = JSON.stringify(body);
  const r = sendHttpRequest('https://api.notion.com/v1/' + path, options);
  if (r.status !== 'success') {
    showToast('Error: ' + (r.response ? r.response.body : r.networkError));
    abortAll();
  }
  return JSON.parse(r.response.body);
}

// Las listas se leen de Notion en cada ejecución: si añades una cuenta
// o categoría nueva en Notion, aparece sola en el móvil.
function query(db, filter) {
  const body = { page_size: 100 };
  if (filter) body.filter = filter;
  return api('POST', 'databases/' + db + '/query', body).results;
}

function titulo(page) {
  return page.properties.Nombre.title.map(function (t) { return t.plain_text; }).join('');
}

function etiqueta(page) {
  const emoji = page.icon && page.icon.type === 'emoji' ? page.icon.emoji + ' ' : '';
  return emoji + titulo(page);
}

function elegirCuenta(pregunta) {
  const opciones = {};
  query(DB.cuentas, { property: 'Activa', checkbox: { equals: true } })
    .forEach(function (c) { opciones[c.id] = etiqueta(c); });
  return showSelection(opciones, pregunta);
}

function elegirCategoria() {
  const opciones = {};
  query(DB.categorias, { property: 'Tipo', select: { equals: 'Gasto' } })
    .forEach(function (c) { opciones[c.id] = etiqueta(c); });
  return showSelection(opciones, 'Tipo de gasto');
}

const concepto = prompt('¿En qué lo gastaste?', '');
const importe = parseFloat(prompt('¿Cuánto?', ''));
const cuenta = elegirCuenta('¿Desde qué cuenta?');
const categoria = elegirCategoria();

// TODO: ingresos y transferencias
// TODO: validar el importe (con coma no funciona)

api('POST', 'pages', {
  parent: { database_id: DB.movimientos },
  properties: {
    'Concepto': { title: [{ text: { content: concepto } }] },
    'Tipo': { select: { name: 'Gasto' } },
    'Importe': { number: importe },
    'Fecha': { date: { start: new Date().toISOString() } },
    'Cuenta': { relation: [{ id: cuenta }] },
    'Categoría': { relation: [{ id: categoria }] },
  },
});

showToast('Gasto guardado');
