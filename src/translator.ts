export type BNode = { kind: 'id' | 'not' | 'and' | 'or', a?: BNode | string, b?: BNode };

function tokenizeBool(s: string): string[] {
  s = s.replace(/\(/g, ' ( ').replace(/\)/g, ' ) ');
  const parts: string[] = [];
  let buf: string[] = [];
  let inq = false;
  for (const ch of s) {
    if (ch === '"' && !inq) { inq = true; buf.push(ch); continue; }
    if (ch === '"' && inq) { inq = false; buf.push(ch); continue; }
    if (inq) { buf.push(ch); continue; }
    buf.push(ch.match(/\s/) ? ' ' : ch);
  }
  return buf.join('').split(/\s+/).filter(Boolean);
}

function parseBool(tokens: string[]): BNode {
  let i = 0;
  function peek(): string | null { return i < tokens.length ? tokens[i] : null; }
  function eat(x?: string): string {
    if (x === undefined) return tokens[i++];
    if (tokens[i] === x) { i++; return x; }
    throw new Error('expected ' + x);
  }
  function p_expr(): BNode {
    let node = p_and();
    while (true) {
      const t = peek();
      if (t && (t.toUpperCase() === 'OR' || t.toUpperCase() === 'ODER')) {
        eat(); node = { kind: 'or', a: node, b: p_and() };
      } else break;
    }
    return node;
  }
  function p_and(): BNode {
    let node = p_not();
    while (true) {
      const t = peek();
      if (t && (t.toUpperCase() === 'AND' || t.toUpperCase() === 'UND')) {
        eat(); node = { kind: 'and', a: node, b: p_not() };
      } else break;
    }
    return node;
  }
  function p_not(): BNode {
    let neg = false;
    while (true) {
      const t = peek();
      if (t && (t.toUpperCase() === 'NOT' || t.toUpperCase() === 'NICHT')) {
        eat(); neg = !neg;
      } else break;
    }
    const node = p_primary();
    return neg ? { kind: 'not', a: node } : node;
  }
  function p_primary(): BNode {
    const t = peek();
    if (t === '(') { eat('('); const node = p_expr(); eat(')'); return node; }
    if (t) { eat(); return { kind: 'id', a: t }; }
    throw new Error('bad token');
  }
  const ast = p_expr();
  if (i !== tokens.length) throw new Error('trailing tokens');
  return ast;
}

function op(role: 'first' | 'AND' | 'OR', neg: boolean): string {
  return { 'first': neg ? 'AN' : 'A', 'AND': neg ? 'UN' : 'U', 'OR': neg ? 'ON' : 'O' }[role];
}

function emitBool(node: BNode, role: 'first' | 'AND' | 'OR' = 'first', neg = false, out: string[] = []): string[] {
  if (node.kind === 'id') {
    out.push(`${op(role, neg).padEnd(5)} ${node.a}`);
    return out;
  }
  if (node.kind === 'not') {
    return emitBool(node.a as BNode, role, !neg, out);
  }
  if (node.kind === 'and') {
    emitBool(node.a as BNode, role, neg, out);
    emitBool(node.b as BNode, 'AND', false, out);
    return out;
  }
  if (node.kind === 'or') {
    if (role === 'first') {
      emitBool(node.a as BNode, 'first', false, out);
      emitBool(node.b as BNode, 'OR', neg, out);
    } else {
      emitBool(node.a as BNode, role, neg, out);
      emitBool(node.b as BNode, 'OR', neg, out);
    }
    return out;
  }
  return out;
}

export function pseudocodeToAwl(input: string): string {
  const lines = input.split(/\r?\n/);
  const result: string[] = [];
  for (const raw of lines) {
    let line = raw.replace(/\/\/.*$/, '').trim();
    if (!line) continue;
    if (!line.includes('=')) { result.push(`// unsupported: ${line}`); continue; }
    const [lhs, rhs] = line.split('=').map(s => s.trim());
    try {
      const tokens = tokenizeBool(rhs);
      const ast = parseBool(tokens);
      const awl: string[] = [];
      emitBool(ast, 'first', false, awl);
      awl.push(`=     ${lhs}`);
      result.push(awl.join('\n'));
    } catch {
      result.push(`// unsupported: ${line}`);
    }
  }
  return result.join('\n');
}

export function awlToPseudocode(input: string): string {
  const lines = input.split(/\r?\n/);
  const result: string[] = [];
  let block: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) continue;
    block.push(line);
    if (line.startsWith('=')) {
      const lhs = line.slice(1).trim();
      let expr = '';
      for (let i = 0; i < block.length - 1; i++) {
        const parts = block[i].trim().split(/\s+/);
        if (parts.length < 2) continue;
        const [opCode, ...rest] = parts;
        const id = rest.join(' ');
        const neg = opCode.endsWith('N');
        const term = (neg ? 'NOT ' : '') + id;
        if (opCode.startsWith('A') && expr === '') {
          expr = term;
        } else if (opCode.startsWith('U') || (opCode.startsWith('A') && expr !== '')) {
          expr += ` AND ${term}`;
        } else if (opCode.startsWith('O')) {
          expr += ` OR ${term}`;
        }
      }
      result.push(`${lhs} = ${expr}`);
      block = [];
    }
  }
  return result.join('\n');
}
