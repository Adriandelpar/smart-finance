// Smart Finance — atajo para HTTP Shortcuts (Android)
// Registra gastos, ingresos y transferencias en Notion.
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

// ---------- utilidades ----------

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

// Si cancelas cualquier pregunta, el atajo se cierra sin guardar nada
function obligatorio(valor) {
  if (valor === null || valor === undefined || valor === '') abortAll();
  return valor;
}

function elegir(titulo, opciones) {
  return obligatorio(showSelection(opciones, titulo));
}

function elegirCuenta(pregunta, excluir) {
  const opciones = {};
  query(DB.cuentas, { property: 'Activa', checkbox: { equals: true } })
    .forEach(function (c) { if (c.id !== excluir) opciones[c.id] = etiqueta(c); });
  return elegir(pregunta, opciones);
}

function elegirCategoria(tipo) {
  const opciones = {};
  query(DB.categorias, { property: 'Tipo', select: { equals: tipo } })
    .forEach(function (c) { opciones[c.id] = etiqueta(c); });
  return elegir(tipo === 'Gasto' ? 'Tipo de gasto' : 'Tipo de ingreso', opciones);
}

function rel(id) { return id ? { relation: [{ id: id }] } : { relation: [] }; }

// ---------- flujos ----------

function gasto() {
  return {
    concepto: obligatorio(prompt('¿En qué lo gastaste?', '')),
    tipo: 'Gasto',
    importe: parseFloat(obligatorio(prompt('¿Cuánto?', ''))),
    cuenta: elegirCuenta('¿Desde qué cuenta?'),
    categoria: elegirCategoria('Gasto'),
  };
}

function ingreso() {
  return {
    concepto: obligatorio(prompt('¿De dónde viene el dinero?', '')),
    tipo: 'Ingreso',
    importe: parseFloat(obligatorio(prompt('¿Cuánto has recibido?', ''))),
    cuenta: elegirCuenta('¿A qué cuenta entra?'),
    categoria: elegirCategoria('Ingreso'),
  };
}

// Una transferencia no es gasto ni ingreso: resta en la cuenta de origen
// (fórmula Monto) y suma en la de destino (rollup Σ Recibido).
function transferencia() {
  const origen = elegirCuenta('¿Desde qué cuenta sale?');
  const destino = elegirCuenta('¿A qué cuenta va?', origen);
  return {
    concepto: prompt('Concepto (opcional)', 'Transferencia') || 'Transferencia',
    tipo: 'Transferencia',
    importe: parseFloat(obligatorio(prompt('¿Cuánto mueves?', ''))),
    cuenta: origen,
    destino: destino,
  };
}

// ---------- programa principal ----------

const accion = elegir('Smart Finance', {
  gasto: '⬇️ Registrar un gasto',
  ingreso: '⬆️ Registrar un ingreso',
  transferencia: '🔄 Registrar una transferencia',
});

const mov = accion === 'gasto' ? gasto() : accion === 'ingreso' ? ingreso() : transferencia();

// TODO: pagos recurrentes (suscripciones y deudas)
// TODO: validar el importe (con coma no funciona)

api('POST', 'pages', {
  parent: { database_id: DB.movimientos },
  properties: {
    'Concepto': { title: [{ text: { content: mov.concepto } }] },
    'Tipo': { select: { name: mov.tipo } },
    'Importe': { number: mov.importe },
    'Fecha': { date: { start: new Date().toISOString() } },
    'Cuenta': rel(mov.cuenta),
    'Cuenta destino': rel(mov.destino),
    'Categoría': rel(mov.categoria),
  },
});

showToast('✅ Guardado');
