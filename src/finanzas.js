// =====================================================================
//  Smart Finance — atajo para HTTP Shortcuts (Android)
//  Registra gastos, ingresos, transferencias y pagos recurrentes
//  en las bases de datos de Notion "Smart Finance".
//
//  Requisitos en HTTP Shortcuts:
//    - Una variable global de tipo "Constant" llamada  notion_token
//      con el secreto de tu integración de Notion (empieza por ntn_).
// =====================================================================

// IDs de las bases de datos de Notion (no hace falta tocarlos)
const DB = {
  cuentas:       'f9254c6213a740ad9bb2f18b01ad98c1',
  categorias:    '54af8712b04145e8b0356ac0b7e7423d',
  suscripciones: '172d96c31ec24dea841a60253251b069',
  deudas:        '3787922069074996af6b818819beb350',
  movimientos:   'd77b034da9bd483ca6e44b045e205351',
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
    const detalle = r.response ? r.response.body : r.networkError;
    showDialog('No he podido hablar con Notion:\n\n' + detalle, '❌ Error');
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
  const p = page.properties.Nombre || page.properties.Concepto;
  return p.title.map(function (t) { return t.plain_text; }).join('');
}

function etiqueta(page) {
  const emoji = page.icon && page.icon.type === 'emoji' ? page.icon.emoji + ' ' : '';
  return emoji + titulo(page);
}

function primeraRelacion(page, prop) {
  const p = page.properties[prop];
  return p && p.relation && p.relation.length ? p.relation[0].id : null;
}

function euros(n) {
  return n.toFixed(2).replace('.', ',') + ' €';
}

// Si cancelas cualquier pregunta, el atajo se cierra sin guardar nada
function obligatorio(valor) {
  if (valor === null || valor === undefined || valor === '') abortAll();
  return valor;
}

function elegir(titulo, opciones) {
  return obligatorio(showSelection(opciones, titulo));
}

function pedirImporte(pregunta, sugerido) {
  while (true) {
    const txt = obligatorio(prompt(pregunta, sugerido ? String(sugerido).replace('.', ',') : ''));
    const n = parseFloat(String(txt).replace(/\s|€/g, '').replace(',', '.'));
    if (!isNaN(n) && n > 0) return Math.round(n * 100) / 100;
    showToast('Escribe un número mayor que 0, por ejemplo 12,50');
  }
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

function gastoRecurrente() {
  const opciones = {};
  const paginas = {};
  query(DB.suscripciones, { property: 'Activa', checkbox: { equals: true } }).forEach(function (s) {
    opciones['s' + s.id] = '🔁 ' + titulo(s) + ' · ' + euros(s.properties.Importe.number || 0);
    paginas['s' + s.id] = s;
  });
  query(DB.deudas).forEach(function (d) {
    const pendiente = d.properties.Pendiente.formula.number;
    if (pendiente !== null && pendiente <= 0) return; // deuda ya pagada
    opciones['d' + d.id] = '💸 ' + titulo(d) + ' · ' + euros(d.properties.Cuota.number || 0);
    paginas['d' + d.id] = d;
  });
  if (Object.keys(opciones).length === 0) {
    showDialog('Todavía no tienes suscripciones activas ni deudas en Notion. Añádelas allí primero.', 'Nada que pagar');
    abortAll();
  }

  const clave = elegir('¿Qué pago estás realizando?', opciones);
  const pagina = paginas[clave];
  const esSuscripcion = clave[0] === 's';
  const sugerido = esSuscripcion ? pagina.properties.Importe.number : pagina.properties.Cuota.number;

  return {
    concepto: titulo(pagina),
    tipo: 'Gasto',
    importe: pedirImporte('¿Cuánto has pagado?', sugerido),
    cuenta: primeraRelacion(pagina, 'Cuenta') || elegirCuenta('¿Desde qué cuenta?'),
    categoria: primeraRelacion(pagina, 'Categoría') || elegirCategoria('Gasto'),
    suscripcion: esSuscripcion ? pagina.id : null,
    deuda: esSuscripcion ? null : pagina.id,
  };
}

function gastoUnico() {
  return {
    concepto: obligatorio(prompt('¿En qué lo gastaste?', '')),
    tipo: 'Gasto',
    importe: pedirImporte('¿Cuánto?'),
    cuenta: elegirCuenta('¿Desde qué cuenta?'),
    categoria: elegirCategoria('Gasto'),
  };
}

function ingreso() {
  return {
    concepto: obligatorio(prompt('¿De dónde viene el dinero?', '')),
    tipo: 'Ingreso',
    importe: pedirImporte('¿Cuánto has recibido?'),
    cuenta: elegirCuenta('¿A qué cuenta entra?'),
    categoria: elegirCategoria('Ingreso'),
  };
}

function transferencia() {
  const origen = elegirCuenta('¿Desde qué cuenta sale?');
  const destino = elegirCuenta('¿A qué cuenta va?', origen);
  return {
    concepto: prompt('Concepto (opcional)', 'Transferencia') || 'Transferencia',
    tipo: 'Transferencia',
    importe: pedirImporte('¿Cuánto mueves?'),
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

let mov;
if (accion === 'gasto') {
  const clase = elegir('¿Qué tipo de gasto es?', { unico: '🧾 Único', recurrente: '🔁 Recurrente' });
  mov = clase === 'unico' ? gastoUnico() : gastoRecurrente();
} else if (accion === 'ingreso') {
  mov = ingreso();
} else {
  mov = transferencia();
}

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
    'Suscripción': rel(mov.suscripcion),
    'Deuda': rel(mov.deuda),
  },
});

// Mensaje final con el saldo actualizado de la cuenta
let aviso = '✅ Guardado: ' + mov.tipo.toLowerCase() + ' de ' + euros(mov.importe);
try {
  const cuenta = api('GET', 'pages/' + mov.cuenta);
  const saldo = cuenta.properties.Saldo.formula.number;
  aviso += '\n' + titulo(cuenta) + ': ' + euros(saldo || 0);
} catch (e) { /* si falla esto, el movimiento ya está guardado */ }
showToast(aviso);
