/* Extract JavaScript definitions using Node's bundled Acorn parser. */
const fs = require('node:fs');
const acorn = require('internal/deps/acorn/acorn/dist/acorn');

const source = fs.readFileSync(0, 'utf8');
const tree = acorn.parse(source, { ecmaVersion: 'latest', sourceType: 'module', locations: true, allowAwaitOutsideFunction: true, allowReturnOutsideFunction: true });
const units = [];

function keyName(key) {
  if (!key) return '';
  if (key.type === 'Identifier' || key.type === 'PrivateIdentifier') return key.name;
  if (key.type === 'Literal') return String(key.value);
  if (key.type === 'MemberExpression') return `${keyName(key.object)}.${keyName(key.property)}`;
  return '';
}

function nameFor(node, parent) {
  if (node.id && node.id.name) return node.id.name;
  if (!parent) return '';
  if (parent.type === 'VariableDeclarator' && parent.init === node) return keyName(parent.id);
  if (parent.type === 'Property' && parent.value === node) return keyName(parent.key);
  if (parent.type === 'MethodDefinition' && parent.value === node) return keyName(parent.key);
  if (parent.type === 'AssignmentExpression' && parent.right === node) return keyName(parent.left);
  return '';
}

function visit(node, parent, scope) {
  if (!node || typeof node.type !== 'string') return;
  const isFunction = ['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'].includes(node.type);
  const isClass = ['ClassDeclaration', 'ClassExpression'].includes(node.type);
  let nextScope = scope;
  if (isFunction || isClass) {
    const label = nameFor(node, parent) || `callback [línea ${node.loc.start.line}]`;
    const qualified = [...scope, label].join('.');
    units.push({ line: node.loc.start.line, start: node.start, name: isFunction ? `${qualified}()` : qualified });
    nextScope = [...scope, label];
  }
  if (node.type === 'ObjectExpression') {
    const label = nameFor(node, parent);
    if (label) nextScope = [...scope, label];
  }
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach(child => visit(child, node, nextScope));
    else if (value && typeof value === 'object' && value.type) visit(value, node, nextScope);
  }
}
visit(tree, null, []);
units.sort((a, b) => a.start - b.start);
const totals = new Map();
for (const unit of units) totals.set(unit.name, (totals.get(unit.name) || 0) + 1);
const seen = new Map();
for (const unit of units) {
  const name = unit.name;
  if (totals.get(name) > 1) {
    const count = (seen.get(name) || 0) + 1;
    seen.set(name, count);
    unit.name += ` [línea ${unit.line}, ocurrencia ${count}]`;
  }
  delete unit.start;
}
process.stdout.write(JSON.stringify(units));
