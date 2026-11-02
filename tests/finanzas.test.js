// Tests del script sin móvil ni Notion: se simulan las funciones de
// HTTP Shortcuts (prompt, showSelection, sendHttpRequest...) y las
// respuestas de la API de Notion, y se ejecuta el script en un sandbox.
//
//   npm test

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SCRIPT = fs.readFileSync(path.join(__dirname, '..', 'src', 'finanzas.js'), 'utf8');

const t = (s) => ({ title: [{ plain_text: s }] });
const DATOS = {
  f9254c6213a740ad9bb2f18b01ad98c1: [ // Cuentas
    { id: 'c1', icon: { type: 'emoji', emoji: '💳' }, properties: { Nombre: t('Débito') } },
    { id: 'c2', icon: { type: 'emoji', emoji: '💵' }, properties: { Nombre: t('Efectivo') } },
  ],
  '54af8712b04145e8b0356ac0b7e7423d': [ // Categorías
    { id: 'k1', properties: { Nombre: t('Comida') } },
  ],
  '172d96c31ec24dea841a60253251b069': [ // Suscripciones
    { id: 's1', properties: { Nombre: t('Netflix'), Importe: { number: 12.99 },
      Cuenta: { relation: [{ id: 'c1' }] }, 'Categoría': { relation: [{ id: 'k1' }] } } },
  ],
  '3787922069074996af6b818819beb350': [ // Deudas
    { id: 'd1', properties: { Nombre: t('Coche'), Cuota: { number: 150 }, Pendiente: { formula: { number: 2000 } },
      Cuenta: { relation: [] }, 'Categoría': { relation: [{ id: 'k1' }] } } },
    { id: 'd2', properties: { Nombre: t('Pagada'), Cuota: { number: 5 }, Pendiente: { formula: { number: 0 } } } },
  ],
};

// Ejecuta el script respondiendo a las preguntas con `respuestas`, en orden.
function ejecutar(respuestas) {
  const cola = [...respuestas];
  const res = { creado: null, toasts: [], selecciones: [], abortado: false };
  const ctx = {
    JSON, Math, Date, Object, String, parseFloat, isNaN,
    getVariable: () => 'ntn_test',
    showSelection: (opciones, titulo) => { res.selecciones.push({ titulo, opciones }); return cola.shift(); },
    prompt: () => cola.shift(),
    showToast: (m) => res.toasts.push(m),
    showDialog: (m) => res.toasts.push(m),
    abortAll: () => { throw { abort: true }; },
    sendHttpRequest: (url, o) => {
      const ruta = url.split('/v1/')[1];
      let body;
      if (ruta.endsWith('/query')) body = { results: DATOS[ruta.split('/')[1]] };
      else if (ruta === 'pages') { res.creado = JSON.parse(o.body).properties; body = { id: 'nuevo' }; }
      else body = { properties: { Nombre: t('Débito'), Saldo: { formula: { number: 87.5 } } } };
      return { status: 'success', response: { body: JSON.stringify(body) } };
    },
  };
  try { vm.runInNewContext(SCRIPT, ctx); } catch (e) { if (!e.abort) throw e; res.abortado = true; }
  return res;
}

const ids = (rel) => rel.relation.map((r) => r.id);

test('gasto único con coma decimal', () => {
  const r = ejecutar(['gasto', 'unico', 'Hamburguesa', '12,50', 'c1', 'k1']);
  assert.strictEqual(r.creado.Tipo.select.name, 'Gasto');
  assert.strictEqual(r.creado.Importe.number, 12.5);
  assert.deepStrictEqual(ids(r.creado.Cuenta), ['c1']);
  assert.deepStrictEqual(ids(r.creado['Categoría']), ['k1']);
  assert.match(r.toasts.at(-1), /Débito: 87,50 €/);
});

test('importe inválido vuelve a preguntar', () => {
  const r = ejecutar(['gasto', 'unico', 'Café', 'abc', '1,20', 'c2', 'k1']);
  assert.strictEqual(r.creado.Importe.number, 1.2);
});

test('suscripción rellena cuenta y categoría sola', () => {
  const r = ejecutar(['gasto', 'recurrente', 'ss1', '12,99']);
  assert.strictEqual(r.creado.Concepto.title[0].text.content, 'Netflix');
  assert.deepStrictEqual(ids(r.creado.Cuenta), ['c1']);
  assert.deepStrictEqual(ids(r.creado['Suscripción']), ['s1']);
});

test('deuda sin cuenta pregunta la cuenta y se enlaza', () => {
  const r = ejecutar(['gasto', 'recurrente', 'dd1', '150', 'c2']);
  assert.deepStrictEqual(ids(r.creado.Deuda), ['d1']);
  assert.deepStrictEqual(ids(r.creado.Cuenta), ['c2']);
});

test('las deudas ya pagadas no aparecen', () => {
  const r = ejecutar(['gasto', 'recurrente', null]);
  const opciones = r.selecciones.find((s) => s.titulo.includes('pago')).opciones;
  assert.ok(opciones.dd1);
  assert.ok(!opciones.dd2);
});

test('ingreso', () => {
  const r = ejecutar(['ingreso', 'Nómina', '800', 'c1', 'k1']);
  assert.strictEqual(r.creado.Tipo.select.name, 'Ingreso');
  assert.strictEqual(r.creado.Importe.number, 800);
});

test('transferencia: el destino no ofrece la cuenta de origen', () => {
  const r = ejecutar(['transferencia', 'c1', 'c2', '', '20']);
  const destino = r.selecciones.find((s) => s.titulo.includes('va')).opciones;
  assert.ok(!destino.c1);
  assert.deepStrictEqual(ids(r.creado['Cuenta destino']), ['c2']);
  assert.strictEqual(r.creado.Concepto.title[0].text.content, 'Transferencia');
});

test('cancelar no guarda nada', () => {
  const r = ejecutar(['gasto', null]);
  assert.ok(r.abortado);
  assert.strictEqual(r.creado, null);
});
