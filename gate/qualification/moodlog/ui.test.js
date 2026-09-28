import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInContext, createContext } from 'node:vm';

// Owner-authored qualification input: copy beside the MoodLog candidate scripts.
// App behavior comes from those real scripts. This double models only the DOM
// operations used by MoodLog; browser checks remain necessary for native behavior.
class Element {
  constructor(tag, attributes = {}) {
    this.tagName = tag.toUpperCase();
    this.attributes = { ...attributes };
    this.children = [];
    this.listeners = new Map();
    this.value = '';
    this.style = { display: /display\s*:\s*([^;]+)/.exec(attributes.style ?? '')?.[1].trim() ?? '' };
    this.hidden = false;
    this.disabled = false;
    this.ownText = '';
    const classes = new Set();
    this.classList = {
      add: (...names) => names.forEach(name => classes.add(name)),
      remove: (...names) => names.forEach(name => classes.delete(name)),
      contains: name => classes.has(name)
    };
  }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  appendChild(child) { this.children.push(child); return child; }
  set textContent(value) { this.ownText = String(value); this.children = []; }
  get textContent() { return this.ownText + this.children.map(child => child.textContent).join(''); }
  set innerHTML(value) {
    assert.equal(value, '', 'UI must render user content as text, never HTML');
    this.children = []; this.ownText = '';
  }
  get innerHTML() { return this.textContent; }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener); this.listeners.set(type, listeners);
  }
  dispatch(type) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ type, target: this, currentTarget: this, preventDefault() {} });
    }
  }
  click() { if (!this.disabled) this.dispatch('click'); }
}

function app(storage, denyAccess = false) {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  const elements = new Map();
  for (const match of html.matchAll(/<(\w+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)) {
    const attributes = Object.fromEntries([...match[2].matchAll(/([\w-]+)="([^"]*)"/g)].map(x => [x[1], x[2]]));
    const element = new Element(match[1], attributes);
    element.disabled = /\bdisabled\b/.test(match[2]);
    const end = html.indexOf(`</${match[1]}>`, match.index + match[0].length);
    const text = end < 0 ? '' : html.slice(match.index + match[0].length, end);
    if (!/\bid=/.test(text)) element.textContent = text.replace(/<[^>]*>/g, '').trim();
    elements.set(match[3], element);
  }
  const buttons = [...html.matchAll(/<button\b[^>]*data-mood="([^"]+)"[^>]*>/g)].map(match =>
    new Element('button', { 'data-mood': match[1], 'aria-pressed': 'false' }));
  const warnings = [];
  const document = {
    readyState: 'complete',
    getElementById(id) { assert.ok(elements.has(id), `Missing DOM element: ${id}`); return elements.get(id); },
    querySelectorAll(selector) { assert.equal(selector, '.mood-buttons button'); return buttons; },
    createElement(tag) { return new Element(tag); },
    addEventListener() { throw new Error('Unexpected document listener in ready DOM'); }
  };
  const window = { document }; Object.defineProperty(window, 'localStorage', { get() { if (denyAccess) throw Error('Storage access denied'); return storage; } });
  const context = createContext({ document, window, console: { warn: (...args) => warnings.push(args), log() {}, error() {} } });
  const scripts = [...html.matchAll(/<script\b[^>]*src="([^"]+)"[^>]*>/g)].map(match => match[1]);
  assert.ok(scripts.includes('index.js'), 'Test must execute the real UI entrypoint');
  for (const filename of scripts) {
    assert.match(filename, /^[\w.-]+\.js$/, 'Only local app scripts are allowed');
    runInContext(readFileSync(new URL(filename, import.meta.url), 'utf8'), context, { filename, timeout: 1000 });
  }
  return {
    buttons, warnings, visibleText: () => [...elements.values()].filter(x => !x.hidden && x.style.display !== "none").map(x => x.textContent).join(" "),
    get: id => document.getElementById(id),
    select(mood) { const button = buttons.find(x => x.getAttribute('data-mood') === mood); assert.ok(button); button.click(); },
    note(value) { const input = document.getElementById('note-input'); input.value = value; input.dispatch('input'); },
    rows: () => document.getElementById('history-list').children
  };
}

test('real UI selects all five moods and maintains accessible pressed state', () => {
  const ui = app();
  assert.deepEqual(ui.buttons.map(x => x.getAttribute('data-mood')), ['Great', 'Good', 'Okay', 'Low', 'Rough']);
  assert.equal(ui.get('save-btn').disabled, true);
  for (const mood of ['Great', 'Good', 'Okay', 'Low', 'Rough']) {
    ui.select(mood);
    assert.equal(ui.get('selection-message').textContent, `Selected: ${mood}`);
    assert.equal(ui.buttons.filter(x => x.getAttribute('aria-pressed') === 'true').length, 1);
    assert.equal(ui.buttons.find(x => x.getAttribute('data-mood') === mood).getAttribute('aria-pressed'), 'true');
    assert.equal(ui.get('save-btn').disabled, false);
  }
});

test('real UI counts notes, enforces 120 characters, saves text and resets controls', () => {
  const ui = app();
  assert.equal(ui.get('note-input').getAttribute('maxlength'), '120');
  ui.select('Good');
  ui.note('x'.repeat(121));
  assert.equal(ui.get('note-counter').textContent, '121 / 120');
  assert.equal(ui.get('save-btn').disabled, true);
  ui.get('save-btn').click();
  assert.equal(ui.rows()[0].textContent, 'No entries yet.');
  ui.note('<img src=x onerror=alert(1)>');
  ui.get('save-btn').click();
  const row = ui.rows()[0];
  assert.equal(row.children[0].tagName, 'STRONG');
  assert.match(row.children[0].textContent, /^Good - .+/);
  assert.ok(!row.children[0].textContent.includes('Invalid Date'));
  assert.equal(row.children[1].textContent, 'Note: <img src=x onerror=alert(1)>');
  assert.equal(row.children[1].children.length, 0);
  assert.equal(ui.get('note-input').value, '');
  assert.equal(ui.get('note-counter').textContent, '0 / 120');
  assert.equal(ui.get('save-btn').disabled, true);
  assert.ok(ui.buttons.every(x => x.getAttribute('aria-pressed') === 'false'));
});

test('real UI saves without a note, keeps newest five entries and clears history', () => {
  const ui = app();
  ui.select('Okay'); ui.get('save-btn').click();
  assert.equal(ui.rows()[0].children[1].textContent, 'No note.');
  for (let i = 0; i < 6; i++) {
    ui.select('Great'); ui.note(`Entry ${i}`); ui.get('save-btn').click();
  }
  assert.equal(ui.rows().length, 5);
  assert.deepEqual(ui.rows().map(x => x.children[1].textContent), ['Note: Entry 5', 'Note: Entry 4', 'Note: Entry 3', 'Note: Entry 2', 'Note: Entry 1']);
  ui.get('clear-btn').click();
  assert.equal(ui.rows().length, 1);
  assert.equal(ui.rows()[0].textContent, 'No entries yet.');
  assert.equal(ui.get('selection-message').textContent, 'History cleared.');
});

function memoryStorage() {
  const entries = new Map();
  return { getItem: key => entries.get(key) ?? null, setItem: (key, value) => entries.set(key, String(value)), removeItem: key => entries.delete(key) };
}

test('integration: save and clear survive fresh UI instances', () => {
  const storage = memoryStorage();
  const first = app(storage); first.select('Good'); first.note('persist me'); first.get('save-btn').click();
  const expected = first.rows().map(x => x.textContent);
  const second = app(storage);
  assert.deepEqual(second.rows().map(x => x.textContent), expected);
  second.select('Okay'); second.get('save-btn').click();
  assert.equal(app(storage).rows().length, 2);
  second.get('clear-btn').click();
  assert.equal(app(storage).rows()[0].textContent, 'No entries yet.');
});

test('integration: newest five persist and malformed storage is safe', () => {
  const storage = memoryStorage(); const first = app(storage);
  for (let i = 0; i < 6; i++) { first.select('Great'); first.note(`Stored ${i}`); first.get('save-btn').click(); }
  assert.deepEqual(app(storage).rows().map(x => x.children[1].textContent), ['Note: Stored 5','Note: Stored 4','Note: Stored 3','Note: Stored 2','Note: Stored 1']);
  storage.setItem('moodlog_history', '{invalid');
  assert.equal(app(storage).rows()[0].textContent, 'No entries yet.');
});

test('integration: denied storage preserves controls and reports save and clear failures', () => {
  const warning = /unavailable|not.{0,12}(saved|persist)|memory|fail|unable/i;
  for (const denyAccess of [true, false]) {
    const storage = { getItem() { return null; }, setItem() { throw Error('quota'); }, removeItem() { throw Error('denied'); } };
    const ui = app(storage, denyAccess);
    ui.select('Low'); ui.note('in memory'); ui.get('save-btn').click();
    assert.match(ui.rows()[0].textContent, /Low.*in memory/);
    assert.match(ui.visibleText(), warning, 'Visible warning must survive the selection reset after a failed save');
    ui.get('clear-btn').click();
    assert.equal(ui.rows()[0].textContent, 'No entries yet.');
    assert.match(ui.visibleText(), warning, 'Visible warning must describe failed persisted clearing');
  }
});
