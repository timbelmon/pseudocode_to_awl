#!/usr/bin/env python3
import sys, re
sys.setrecursionlimit(10000)

# ---------- keyword sets ----------
KW_AND = {"AND", "UND"}
KW_OR  = {"OR", "ODER"}
KW_NOT = {"NOT", "NICHT"}

SEC_MAP = {
    None:       "VAR",
    "VAR":      "VAR",
    "INPUT":    "VAR_INPUT",
    "OUTPUT":   "VAR_OUTPUT",
    "INOUT":    "VAR_IN_OUT",
    "TEMP":     "VAR_TEMP",
}

# ---------- helpers ----------
def strip_comment(line: str) -> str:
    return line.split("//", 1)[0]

def is_ident(tok: str) -> bool:
    if not tok: return False
    # allow quoted dotted symbols: "DB_HMI".Start.Flag
    if tok.startswith('"'):
        return bool(re.fullmatch(r'"[^"]+"(\.[A-Za-z_]\w*)*', tok))
    if tok[0].isdigit(): return False
    return bool(re.fullmatch(r'\w+(\.\w+)*', tok, flags=re.UNICODE))

def is_number(tok: str) -> bool:
    return bool(re.fullmatch(r'[+-]?\d+([.]\d+)?([eE][+-]?\d+)?', tok))

def is_real_like(tok: str) -> bool:
    return bool(re.search(r'[.eE]', tok))

# ---------- boolean tokenizer / parser ----------
def tokenize_bool(s: str):
    s = s.replace("(", " ( ").replace(")", " ) ")
    parts, buf, inq = [], [], False
    for ch in s:
        if ch == '"' and not inq:
            inq = True; buf.append(ch); continue
        if ch == '"' and inq:
            inq = False; buf.append(ch); continue
        if inq: buf.append(ch); continue
        buf.append(ch if not ch.isspace() else ' ')
    toks = [t for t in "".join(buf).split() if t]
    return toks

class BNode:
    def __init__(self, kind, a=None, b=None):
        self.kind, self.a, self.b = kind, a, b  # 'id','not','and','or'

def parse_bool(tokens):
    i = 0
    def peek(): return tokens[i] if i < len(tokens) else None
    def eat(x=None):
        nonlocal i
        if x is None:
            i += 1; return tokens[i-1]
        if i < len(tokens) and tokens[i] == x:
            i += 1; return x
        raise ValueError(f"Expected {x}, got {tokens[i] if i<len(tokens) else 'EOF'}")

    def p_expr():
        node = p_and()
        while True:
            t = peek()
            if t and t.upper() in KW_OR:
                eat(); node = BNode('or', node, p_and())
            else: break
        return node

    def p_and():
        node = p_not()
        while True:
            t = peek()
            if t and t.upper() in KW_AND:
                eat(); node = BNode('and', node, p_not())
            else: break
        return node

    def p_not():
        neg = False
        while True:
            t = peek()
            if t and t.upper() in KW_NOT:
                eat(); neg = not neg
            else: break
        node = p_primary()
        return BNode('not', node) if neg else node

    def p_primary():
        t = peek()
        if t == '(':
            eat('('); node = p_expr(); eat(')'); return node
        if t and is_ident(t):
            eat(); return BNode('id', t)
        raise ValueError(f"bad token: {t}")

    ast = p_expr()
    if i != len(tokens): raise ValueError("trailing tokens")
    return ast

# minimal-parentheses boolean emitter
def emit_bool(node, role='first', neg=False, out=None):
    if out is None: out = []
    def op(role, neg):
        return {'first':('AN' if neg else 'A'),
                'AND'  :('UN' if neg else 'U'),
                'OR'   :('ON' if neg else 'O')}[role]
    if node.kind == 'id':
        out.append(f"{op(role,neg):<5} {node.a}"); return out
    if node.kind == 'not':
        return emit_bool(node.a, role, not neg, out)
    if node.kind == 'and':
        emit_bool(node.a, role, neg, out)
        emit_bool(node.b, 'AND', False, out)
        return out
    if node.kind == 'or':
        if role == 'first':
            emit_bool(node.a, 'first', False, out)
            emit_bool(node.b, 'OR', False, out)
        else:
            out.append(op(role,neg)+"(")
            emit_bool(node.a, 'first', False, out)
            emit_bool(node.b, 'OR', False, out)
            out.append(")")
        return out
    raise ValueError(node.kind)

# ---------- arithmetic / comparisons ----------
def tokenize_expr(s: str):
    s = s.replace("(", " ( ").replace(")", " ) ")
    s = re.sub(r'([+\-*/<>]=|==|!=|[+\-*/<>])', r' \1 ', s)
    toks = [t for t in s.split() if t]
    # merge quoted identifiers if split
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t.startswith('"'):
            q = [t]; i += 1
            while i < len(toks) and not toks[i].endswith('"'):
                q.append(toks[i]); i += 1
            if i < len(toks):
                q.append(toks[i]); i += 1
            out.append(" ".join(q))
            continue
        out.append(t); i += 1
    return out

PREC = {'u-':3, '*':2, '/':2, '+':1, '-':1}
CMP  = {'==':'EQ', '!=':'NE', '<':'LT', '<=':'LE', '>':'GT', '>=':'GE'}

def to_rpn(tokens):
    out, ops = [], []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == '(':
            ops.append(t)
        elif t == ')':
            while ops and ops[-1] != '(':
                out.append(ops.pop())
            if not ops: raise ValueError("mismatched )")
            ops.pop()
        elif t in ('+','-','*','/'):
            if t == '-' and (i == 0 or tokens[i-1] in ('+','-','*','/','(','==','!=','<','<=','>','>=')):
                t = 'u-'
            while ops and ops[-1] in PREC and PREC[ops[-1]] >= PREC.get(t,0):
                out.append(ops.pop())
            ops.append(t)
        elif t in CMP:
            while ops: out.append(ops.pop())
            ops.append(t)
        else:
            out.append(t)
        i += 1
    while ops:
        out.append(ops.pop())
    return out

def emit_arith_or_cmp(lhs, rhs_tokens):
    rpn = to_rpn(rhs_tokens)

    # choose INT vs REAL ops if any literal looks real
    is_real = any(is_number(t) and is_real_like(t) for t in rhs_tokens)
    add = '+R' if is_real else '+I'
    sub = '-R' if is_real else '-I'
    mul = '*R' if is_real else '*I'
    div = '/R' if is_real else '/I'

    # comparison opcode map + invert for swapped operands
    CMP  = {'==':'EQ', '!=':'NE', '<':'LT', '<=':'LE', '>':'GT', '>=':'GE'}
    AWL  = lambda k: {'EQ':'==', 'NE':'<>', 'LT':'<', 'LE':'<=', 'GT':'>', 'GE':'>='}[k] + ('R' if is_real else 'I')
    INV  = {'LT':'GT', 'LE':'GE', 'GT':'LT', 'GE':'LE', 'EQ':'EQ', 'NE':'NE'}

    # Stack entries: 'ACC' (current accumulator) or plain operand strings
    stack, out = [], []

    for t in rpn:
        if t in ('+','-','*','/','u-'):
            if t == 'u-':
                x = stack.pop()
                # Only support unary minus on non-ACC operands for simplicity
                # (common use: -Var or -5). If needed, extend with temp load.
                out += [("L     0.0" if is_real else "L     0"),
                        f"L     {x}",
                        sub]
                stack.append('ACC')
                continue

            b = stack.pop()
            a = stack.pop()

            # Load sequence: if 'a' is ACC, just load 'b'; else load a,b
            if a == 'ACC' and b == 'ACC':
                # ACC (a) op ACC (b) shouldn't happen for well-formed RPN; treat as error
                return f"// unsupported (ACC op ACC): {lhs} = {' '.join(rhs_tokens)}"
            elif a == 'ACC':
                out.append(f"L     {b}")
                out.append({'+' : add, '-' : sub, '*' : mul, '/' : div}[t])
            elif b == 'ACC':
                # ACC is right operand (rare in typical RPN chains) — need to reorder:
                # compute: a (op) ACC == (ACC (swap-op) a)
                # Only safe for commutable ops (+,*) but for (-,/), we must actually load both.
                # Easiest correct approach: load a, then load a second time ACC? Can't.
                # So for '-' and '/' we must do full reload path: L a; L 0; <swap>; then combine with ACC not possible.
                # To avoid complexity, force normal load order for these cases:
                out += [f"L     {a}",  # clobbers ACC, but 'b' was ACC (lost) -> this case shouldn't appear with our RPN
                        f"L     {0 if not is_real else 0.0}"]
                return f"// unsupported order (right ACC) in {' '.join(rhs_tokens)}"
            else:
                out += [f"L     {a}", f"L     {b}",
                        {'+' : add, '-' : sub, '*' : mul, '/' : div}[t]]

            stack.append('ACC')

        elif t in ('==','!=','<','<=','>','>='):
            b = stack.pop()
            a = stack.pop()

            # Prefer ACC as left operand; if ACC is right, swap + invert compare
            cmpk = CMP[t]
            if a == 'ACC' and b != 'ACC':
                # ACC (a) <cmp> b
                out.append(f"L     {b}")
                out.append(AWL(cmpk))
                out.append(f"=     {lhs}")
                return "\n".join(out)

            if b == 'ACC' and a != 'ACC':
                # a <cmp> ACC  ==>  ACC <inv(cmp)> a
                out.append(f"L     {a}")
                out.append(AWL(INV[cmpk]))
                out.append(f"=     {lhs}")
                return "\n".join(out)

            # Neither side is ACC: load both
            out += [f"L     {a}", f"L     {b}", AWL(cmpk), f"=     {lhs}"]
            return "\n".join(out)

        else:
            # operand
            stack.append(t)

    # No comparison: arithmetic result in ACC → just store
    if not out:
        # trivial move
        return f"L     {rhs_tokens[0]}\nT     {lhs}"
    out.append(f"T     {lhs}")
    return "\n".join(out)

# ---------- declaration shortcuts ----------
def try_declaration(s: str):
    """
    Forms:
      int X
      int X = 12
      input int Speed = 100
      output bool Ready
      temp real R = 0.0
      var dint Cnt
    """
    m = re.match(r'^(?:(input|output|inout|temp|var)\s+)?(int|dint|real|bool)\s+([A-Za-z_]\w*)(?:\s*=\s*(.+))?$',
                 s, flags=re.IGNORECASE | re.UNICODE)
    if not m: return None
    sec, typ, name, val = m.groups()
    sec = SEC_MAP[sec.upper()] if sec else SEC_MAP[None]
    typ = typ.upper()
    if val is None:
        val = {"INT":"0", "DINT":"0", "REAL":"0.0", "BOOL":"FALSE"}[typ]
    if typ == "BOOL":
        v = val.strip().lower()
        val = "TRUE" if v in ("1","true","wahr","yes","ja","on") else "FALSE"
    return f"{sec} {name} : {typ} := {val};"

# ---------- dispatcher ----------
def transpile_line(line: str) -> str:
    s = strip_comment(line).strip().rstrip(";")
    if not s: return ""
    # declarations first
    decl = try_declaration(s)
    if decl: return decl
    if "=" not in s: return f"// skip: {s}"
    lhs, rhs = [x.strip() for x in s.split("=", 1)]

    # boolean?
    if re.search(r"\b(AND|OR|NOT|UND|ODER|NICHT)\b", rhs, flags=re.IGNORECASE) or re.search(r'[()]', rhs):
        try:
            toks = tokenize_bool(rhs)
            # if math/comparison tokens exist, fall through to arithmetic
            if any(t in ('+','-','*','/','==','!=','<','<=','>','>=') for t in toks):
                raise ValueError
            ast = parse_bool(toks)
            out = []; emit_bool(ast, 'first', False, out); out.append(f"=     {lhs}")
            return "\n".join(out)
        except Exception:
            pass

    # arithmetic / comparison
    try:
        toks = tokenize_expr(rhs)
        return emit_arith_or_cmp(lhs, toks)
    except Exception:
        return f"// unsupported: {lhs} = {rhs}"

if __name__ == "__main__":
    lines = [l for l in sys.stdin.read().splitlines() if l.strip()]
    print("\n\n".join(transpile_line(l) for l in lines))
