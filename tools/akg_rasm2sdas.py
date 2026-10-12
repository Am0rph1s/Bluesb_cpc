#!/usr/bin/env python3
"""akg_rasm2sdas.py - Conversor RASM/Disark (Arkos Tracker 3) -> sdasz80.

Determinista i pur (mateixa entrada = mateixa sortida). Regles:
 1. Blocs de definicio de macros Disark (IFNDEF dkXX..MACRO..ENDM..ENDIF):
    eliminats (nomes metadata per Disark; mai referenciats).
 2. Les 4 macros reals (ReadTrack, ApplyTrailingEffects, PlayInstrument,
    ChannelSubcodes, 1 param): EXPANDIDES als punts d'invocacio (args
    literals 1/2/3) amb substitucio {param}->valor. Res de .macro.
 3. Invocacions Disark soles en linia (dkws/dkwe/dkps/dkpe/dkbs/dkbe/dknr3
    [(void)] [:]): eliminades (no generen codi en RASM modern).
 4. REPEAT n,var,ini..REND: desenrotllat (substitucio {var}); els `if'
    minusculs ({var} ==/!= N) s'avaluen aqui.
 5. Per linia: db/dw -> .db/.dw; db "str" -> bytes; label nu -> amb ':';
    X equ Y -> X = Y; #hex -> 0xhex; %bin -> 0bbin; $ (no hex) -> .;
    IFDEF/IFNDEF/ELSE/ENDIF (qualsevol caixa) -> .ifdef/.ifndef/.else/.endif;
    IF -> .if; assert -> ELIMINAT (es verifica a build.py amb FATALs);
    include -> .include.
Origen: players/playerAkg de l'Arkos Tracker 3 (MIT, veure tools/akg/).
"""
import re
import sys

DK_MACROS = ('dkws', 'dkwe', 'dkps', 'dkpe', 'dkbs', 'dkbe', 'dknr3')

# Mnemomics Z80 (un mot nu d'aquests es INSTRUCCIO, mai label).
Z80_MNEMO = ('adc', 'add', 'and', 'bit', 'call', 'ccf', 'cp', 'cpd', 'cpdr',
             'cpi', 'cpir', 'cpl', 'daa', 'dec', 'di', 'djnz', 'ei', 'ex', 'exx',
             'halt', 'im', 'in', 'inc', 'ind', 'indr', 'ini', 'inir', 'jp', 'jr',
             'ld', 'ldd', 'lddr', 'ldi', 'ldir', 'neg', 'nop', 'or', 'otdr',
             'otir', 'out', 'outd', 'outi', 'pop', 'push', 'res', 'ret', 'reti',
             'retn', 'rl', 'rla', 'rlc', 'rlca', 'rld', 'rr', 'rra', 'rrc',
             'rrca', 'rrd', 'rst', 'sbc', 'scf', 'set', 'sla', 'sll', 'sra',
             'srl', 'sub', 'xor')

# Registers/condicions: mai porten #.
NO_HASH_WORD = ('a', 'b', 'c', 'd', 'e', 'h', 'l', 'af', 'bc', 'de', 'hl',
                'sp', 'ix', 'iy', "af'", "bc'", "de'", "hl'", 'ixh', 'ixl',
                'iyh', 'iyl', 'i', 'r', 'nz', 'z', 'nc', 'po', 'pe', 'p', 'm')
# Salts: operands sempre labels/condicions (mai #). bit/set/res: el 1r
# operand (num. bit) va be nu; rst/im: idem.
JUMP_MNEMO = ('jp', 'jr', 'call', 'djnz', 'ret')
BIT_MNEMO = ('bit', 'set', 'res')
BARE_MNEMO = ('rst', 'im')


def fix_token(t):
    """#hex -> 0xhex; %bin -> decimal (sdas no te 0b); $ (no hex) -> ."""
    t = re.sub(r'#([0-9A-Fa-f]+)', r'0x\1', t)
    # sdas NO te prefix binari (0b peta): passa a decimal.
    t = re.sub(r'%([01]+)', lambda m: str(int(m.group(1), 2)), t)
    t = re.sub(r'\$(?![0-9A-Fa-f])', '.', t)
    return t


def split_operands(s):
    """Parteix operands per comes de nivell 0 (respecta parens)."""
    parts, depth, cur = [], 0, ''
    in_str = False
    for ch in s:
        if ch == '"':
            in_str = not in_str
        if not in_str:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == ',' and depth == 0:
                parts.append(cur)
                cur = ''
                continue
        cur += ch
    parts.append(cur)
    return parts


def hash_operand(op):
    """Afegeix # a un operand immediat (symbol/nombre, no parens/registre).
    `(ix|iy + EXPR)' (sencer) -> `EXPR(ix|iy)' (sdas no admet `(ix+d)',
    vist 12/10/26: peta fins i tot amb `(5)(iy)'). `(grup)' sencer = mem.
    (quiet); text darrere del parentesi = immediat -> #."""
    t = op.strip()
    if not t:
        return op
    m = re.match(r'^\(\s*(ix|iy)\s*\+\s*(.+)\)$', t, re.I)
    if m:
        return op.replace(t, '%s(%s)' % (m.group(2).strip(), m.group(1).lower()))
    if re.search(r'\(\s*(ix|iy)\b', t, re.I):
        raise ValueError('indexat ix/iy no suportat: %s' % t[:80])
    if t.startswith('('):
        depth = 0
        close = -1
        for i, ch in enumerate(t):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    close = i
                    break
        if close == len(t) - 1:
            return op  # (grup) sencer: (hl), (SYM), (SYM+1)... quiet
        return op.replace(t, '#' + t, 1)
    m = re.match(r'^[+-]?([A-Za-z_][A-Za-z0-9_]*|0[xX][0-9A-Fa-f]+|\d+)', t)
    if not m or m.group(1).lower() in NO_HASH_WORD:
        return op
    return op.replace(t, '#' + t, 1)


def fix_instruction(indent, s):
    """Reescriu una linia d'instruccio/etiqueta a sintaxi sdas."""
    # Meitats IX/IY: sdas NO les suporta (ni ld ixl,c ni ld a,iyl).
    # S'emeten com a opcode cru (byte-identic al RASM; verificat via
    # desassemblador de l'emu). Qualsevol altra forma -> FATAL.
    m = re.match(r'^(ld)\s+([^,]+?)\s*,\s*(.+?)\s*$', s, re.I)
    if m:
        d, v = m.group(2).strip().lower(), m.group(3).strip().lower()
        raw = None
        if (d, v) == ('ixl', 'c'):
            raw = (0xDD, 0x69)
        elif (d, v) == ('c', 'ixl'):
            raw = (0xDD, 0x4D)
        elif (d, v) == ('iyl', 'a'):
            raw = (0xFD, 0x6F)
        elif (d, v) == ('a', 'iyl'):
            raw = (0xFD, 0x7D)
        elif d in ('ixl', 'iyl'):
            mn = re.match(r'^(?:0x[0-9a-f]+|\d+)$', v, re.I)
            if mn:
                raw = ((0xDD if d == 'ixl' else 0xFD), 0x2E, int(v, 0) & 0xFF)
        if raw is not None:
            return indent + '.db %s' % ', '.join('0x%02X' % b for b in raw)
        if 'ixh' in d or 'ixl' in d or 'iyh' in d or 'iyl' in d or \
           'ixh' in v or 'ixl' in v or 'iyh' in v or 'iyl' in v:
            raise ValueError('meitat IX/IY no mapejada: %s' % s[:80])
    # `out (c),0' no existeix a sdas (ni nu ni amb #): opcode cru ED 71.
    if re.match(r'^out\s+\(c\)\s*,\s*0\s*$', s, re.I):
        return indent + '.db 0xED, 0x71'
    # `Label: instr' -> label intacta + instruccio reprocessada.
    # (`Label: db/dw' -> .db/.dw amb token-fix, no com a instruccio!)
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$', s)
    if m:
        sub = m.group(2).strip()
        md = re.match(r'^(db|dw)\s+(.*)$', sub, re.I)
        if md:
            return indent + m.group(1) + ': .' + md.group(1).lower() + ' ' + fix_token(md.group(2))
        return indent + m.group(1) + ': ' + fix_instruction('', sub).strip()
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*$', s)
    if m:
        return indent + s
    # `Label db/dw dades' (RASM, sense dos punts) -> `Label: .db/.dw'.
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s+(db|dw)\s+(.*)$', s, re.I)
    if m and m.group(1).lower() not in ('db', 'dw'):
        return indent + m.group(1) + ': .' + m.group(2).lower() + ' ' + m.group(3)
    # `Label MNEMONIC args' (RASM, sense dos punts) -> `Label: ...'.
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\b(.*)$', s)
    if m and m.group(1).lower() not in Z80_MNEMO and m.group(2).lower() in Z80_MNEMO:
        return indent + m.group(1) + ': ' + fix_instruction('', (m.group(2) + m.group(3)).strip()).strip()
    m = re.match(r'^([A-Za-z_][A-Za-z0-9_.]*)\s+(.*)$', s)
    if not m:
        return indent + s  # ni mnemonic ni res conegut: tal qual
    mn, rest = m.group(1).lower(), m.group(2)
    if mn in JUMP_MNEMO or mn in BARE_MNEMO:
        return indent + m.group(1) + ' ' + rest
    ops = split_operands(rest)
    if mn in BIT_MNEMO and ops:
        ops = [ops[0]] + [hash_operand(o) for o in ops[1:]]
    else:
        ops = [hash_operand(o) for o in ops]
    return indent + m.group(1) + ' ' + ','.join(ops)


def split_code_comment(ln):
    """Separa codi/comentari (';' fora de strings)."""
    in_str = False
    for i, ch in enumerate(ln):
        if ch == '"':
            in_str = not in_str
        elif ch == ';' and not in_str:
            return ln[:i], ln[i:]
    return ln, ''


def eval_int(expr, symbols, context):
    """Avalua una expressio entera d'assemblador (==,!=,>,<,>=,<=,+,-,*,/,
    parens, unari). Simbols desconeguts -> FATAL (sorollos, no silently)."""
    import ast
    import operator as op
    ops = {ast.Eq: op.eq, ast.NotEq: op.ne, ast.Gt: op.gt, ast.Lt: op.lt,
           ast.GtE: op.ge, ast.LtE: op.le, ast.Add: op.add, ast.Sub: op.sub,
           ast.Mult: op.mul, ast.Div: op.floordiv, ast.Mod: op.mod,
           ast.USub: op.neg, ast.UAdd: op.pos, ast.BitOr: op.or_,
           ast.BitAnd: op.and_, ast.BitXor: op.xor, ast.LShift: op.lshift,
           ast.RShift: op.rshift, ast.Invert: op.inv}

    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in symbols:
                raise ValueError('simbol desconegut a .if: %s (%s)' % (node.id, context[:70]))
            return symbols[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in ops:
            return int(ops[type(node.ops[0])](ev(node.left), ev(node.comparators[0])))
        if isinstance(node, ast.Expression):
            return ev(node.body)
        raise ValueError('expressio no suportada a .if: %s (%s)' % (expr[:60], context[:70]))

    tree = ast.parse(expr, mode='eval')
    # Noms amb $ o `.`: no valids en .if (FATAL si n'hi ha: cal estendre).
    return ev(tree)


def eval_braces(s, symbols, context):
    """Avalua {expr} (p.ex. {1 + 7} despres de substituir el param de macro).
    FATAL si refereix simbols (caldria valor d'adreca)."""
    def rep(m):
        return str(eval_int(m.group(1), symbols, context))
    return re.sub(r'\{([^{}]+)\}', rep, s)


def convert(text, module='akgconv'):
    lines = text.split('\n')
    # Pre-verificacio: els if/else/endif MINUSCULS nomes poden ser dins
    # REPEAT o MACRO (s'avaluen/expandeixen aqui); fora serien perduts.
    in_rep = in_macro = 0
    for ln in lines:
        s = ln.strip()
        if re.match(r'REPEAT\b', s, re.I):
            in_rep += 1
        elif re.match(r'REND\b', s, re.I):
            in_rep -= 1
        elif re.match(r'MACRO\b', s, re.I):
            in_macro += 1
        elif re.match(r'ENDM\b', s, re.I):
            in_macro -= 1
        elif in_rep == 0 and in_macro == 0 and re.match(r'(if|else|endif)\b', s) and not re.match(r'(IF|ELSE|ENDIF)\b', s):
            raise ValueError('if/else/endif minuscul fora de REPEAT/MACRO: %s' % s[:80])
    out = []
    i = 0
    n = len(lines)
    # -- 1. Treu blocs IFNDEF dkXX..ENDIF (definicions Disark). --
    cleaned = []
    while i < n:
        s = lines[i].strip()
        m = re.match(r'IFNDEF\s+(dk\w+)\s*$', s, re.I)
        if m and m.group(1).lower() in DK_MACROS:
            depth = 1
            i += 1
            while i < n and depth:
                t = lines[i].strip()
                if re.match(r'IFN?DEF\b', t, re.I):
                    depth += 1
                elif re.match(r'ENDIF\b', t, re.I):
                    depth -= 1
                i += 1
            continue
        cleaned.append(lines[i])
        i += 1
    # -- 2. Recull les 4 macros reals. --
    macros = {}
    body = []
    in_macro = None
    rest = []
    for ln in cleaned:
        s = ln.strip()
        m = re.match(r'MACRO\s+(\w+)\s+(\w+)\s*$', s, re.I)
        if m and m.group(1) not in [x.upper() for x in DK_MACROS]:
            assert in_macro is None
            in_macro = (m.group(1), m.group(2))
            body = []
            continue
        if re.match(r'ENDM\b', s, re.I):
            assert in_macro is not None, ln
            macros[in_macro[0].upper()] = (in_macro[1], body)
            in_macro = None
            continue
        if in_macro is not None:
            body.append(ln)
        else:
            rest.append(ln)
    assert in_macro is None
    # -- 3. Expandeix invocacions (fora de definicions). --
    expanded = []
    for ln in rest:
        code, _ = split_code_comment(ln)
        m = re.match(r'^\s*([A-Za-z_]\w*)\s+(\S+)\s*$', code)
        if m and m.group(1).upper() in macros:
            param, mbody = macros[m.group(1).upper()]
            arg = m.group(2)
            assert '{' not in arg and '}' not in arg, 'macro amb arg no literal: %s' % ln[:80]
            for bl in mbody:
                bl2 = bl.replace('{%s}' % param, arg).replace('{%s}' % param.lower(), arg)
                expanded.append(eval_braces(bl2, {}, 'macro %s' % m.group(1)))
            continue
        expanded.append(ln)
    # -- 4. Desenrotlla REPEAT. --
    unrolled = []
    i = 0
    while i < len(expanded):
        s = expanded[i].strip()
        m = re.match(r'REPEAT\s+(\d+)\s*,\s*(\w+)\s*,\s*(\d+)\s*$', s, re.I)
        if not m:
            unrolled.append(expanded[i])
            i += 1
            continue
        count, var, start = int(m.group(1)), m.group(2), int(m.group(3))
        j = i + 1
        depth = 1
        rbody = []
        while j < len(expanded):
            t = expanded[j].strip()
            if re.match(r'REPEAT\b', t, re.I):
                depth += 1
            elif re.match(r'REND\b', t, re.I):
                depth -= 1
                if not depth:
                    break
            rbody.append(expanded[j])
            j += 1
        assert depth == 0, 'REPEAT sense REND'
        for v in range(start, start + count):
            # Pila: [outer_skipping, any_taken]. `else'/`elseif' prenen la
            # branca si outer inclou i cap anterior s'ha pres.
            stack = []
            skipping = False

            def do_if(cond):
                outer = skipping
                took = (not outer) and cond
                stack.append([outer, took])
                return outer or not cond

            for bl in rbody:
                bs = bl.strip()
                mi = re.match(r'if\s+\{%s\}\s*(==|!=)\s*(\d+)\s*(;.*)?$' % var, bs, re.I)
                if mi is None:
                    mi = re.match(r'if\s+%s\s*(==|!=)\s*(\d+)\s*(;.*)?$' % var, bs, re.I)
                if mi:
                    skipping = do_if((v == int(mi.group(2))) == (mi.group(1) == '=='))
                    continue
                mi = re.match(r'elseif\s+\{%s\}\s*(==|!=)\s*(\d+)\s*(;.*)?$' % var, bs, re.I)
                if mi is None:
                    mi = re.match(r'elseif\s+%s\s*(==|!=)\s*(\d+)\s*(;.*)?$' % var, bs, re.I)
                if mi and stack:
                    outer, anyt = stack[-1]
                    cond = (v == int(mi.group(2))) == (mi.group(1) == '==')
                    took = (not outer) and not anyt and cond
                    stack[-1][1] = anyt or took
                    skipping = outer or not took
                    continue
                if re.match(r'else\b', bs, re.I) and stack and not re.match(r'ELSE\b', bs):
                    # `else' minuscul (el MAJUSCUL es d'un IFDEF: passa tal qual).
                    outer, anyt = stack[-1]
                    stack[-1][1] = True
                    skipping = outer or anyt
                    continue
                if re.match(r'endif\b', bs, re.I) and stack and not re.match(r'ENDIF\b', bs):
                    outer, _ = stack.pop()
                    skipping = outer
                    continue
                if not skipping:
                    unrolled.append(eval_braces(bl.replace('{%s}' % var, str(v)), {}, 'repeat'))
        i = j + 1
    # -- 5/6. Regles per linia + AVALUACIO de condicionals.
    # sdas .if amb valors NO funciona (vist 12/10/26: sempre cert!), aixi que
    # el conversor avalua TOTS els IFDEF/IFNDEF/IF/ELSE/ENDIF aqui (semantica
    # seqüencial: nomes el codi pres genera sortida). sdas rep codi lineal.
    # predefined: simbols predefinits (p.ex. futura playerconfig). Buit ara.
    asserts = []
    final = []
    symbols = {}
    aliases = {}  # X = <expr amb labels>: no avaluable, pero DEFINIT
    labels_seen = set()
    stack = []  # marcs {parent, cond}
    taken = True
    decisions = []  # auditoria (profunditat, directiva, resultat)

    def is_defined(name):
        return name in symbols or name in aliases or name in labels_seen

    for ln in unrolled:
        code, comment = split_code_comment(ln)
        s = code.strip()
        if not s:
            if taken:
                final.append(ln)
            continue
        # Invocacio Disark sola: fora. Amb codi darrere: treu el prefix i
        # reprocessa el codi (p.ex. `dknr3 (void): ld de,4`).
        m = re.match(r'^(%s)\s*(\(void\))?\s*:\s*(.*)$' % '|'.join(DK_MACROS), s, re.I)
        if m:
            if not m.group(3):
                continue
            code = code[:len(code) - len(code.lstrip())] + m.group(3)
            s = m.group(3)
            # (cau a les regles de sota: db/dw/label/instruccio...)
        # assert: fora (es verifica a build.py amb FATALs).
        if re.match(r'assert\b', s, re.I):
            asserts.append(s)
            continue
        # --- Condicionals: avaluar, no emetre. ---
        m = re.match(r'^(IFDEF|IFNDEF)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', s, re.I)
        if m:
            cond = is_defined(m.group(2))
            if m.group(1).lower() == 'ifndef':
                cond = not cond
            stack.append({'parent': taken, 'cond': cond, 'any': taken and cond})
            taken = taken and cond
            decisions.append((len(stack), m.group(1).upper() + ' ' + m.group(2), taken))
            continue
        m = re.match(r'^IF\s+(.+)$', s, re.I)
        if m:
            expr = fix_token(m.group(1)).strip()
            cond = bool(eval_int(expr, symbols, s))
            stack.append({'parent': taken, 'cond': cond, 'any': taken and cond})
            taken = taken and cond
            decisions.append((len(stack), 'IF ' + expr + ' = %s' % cond, taken))
            continue
        m = re.match(r'^ELSEIF\s+(.+)$', s, re.I)
        if m:
            assert stack, 'ELSEIF sense IF: %s' % s[:80]
            expr = fix_token(m.group(1)).strip()
            cond = bool(eval_int(expr, symbols, s))
            fr = stack[-1]
            took = fr['parent'] and cond and not fr['any']
            fr['any'] = fr['any'] or took
            fr['cond'] = cond
            taken = took
            decisions.append((len(stack), 'ELSEIF ' + expr + ' = %s' % cond, taken))
            continue
        if re.match(r'^ELSE\b', s, re.I):
            assert stack, 'ELSE sense IF: %s' % s[:80]
            fr = stack[-1]
            taken = fr['parent'] and not fr['any']
            fr['any'] = True
            decisions.append((len(stack), 'ELSE', taken))
            continue
        if re.match(r'^ENDIF\b', s, re.I):
            assert stack, 'ENDIF sense IF: %s' % s[:80]
            fr = stack.pop()
            taken = fr['parent']
            continue
        if not taken:
            continue
        # RASM `:' separa sentencies. Nomes n'hi ha UNA al player
        # (`L: nop : add hl,bc', placeholder automodificat de 2B): parteix
        # en label + 2 sentencies (reprocessades). Futur: FATAL sorollos.
        ncolon = sum(1 for ch in code if ch == ':')
        if ncolon >= 2:
            m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*:\s*(.+)$', code)
            if not m:
                raise ValueError('linia multi-colon no suportada: %s' % s[:80])
            labels_seen.add(m.group(1))
            final.append(m.group(1) + ':')
            for stmt in (m.group(2), m.group(3)):
                ss = stmt.strip()
                md = re.match(r'^(db|dw)\s+(.*)$', ss, re.I)
                if md:
                    final.append('    .%s %s' % (md.group(1).lower(), fix_token(md.group(2))))
                else:
                    final.append(fix_instruction('                ', fix_token(ss)))
            final[-1] += comment
            continue
        # --- Nomes codi pres a partir d'aqui: registra labels. ---
        m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:', code)
        if m:
            labels_seen.add(m.group(1))
        else:
            m = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s+(db|dw|equ)\b', code, re.I)
            if m:
                labels_seen.add(m.group(1))
        # db "str" -> bytes.
        m = re.match(r'^(db)\s+"([^"]*)"\s*$', s, re.I)
        if m:
            vals = ', '.join('0x%02X' % c for c in m.group(2).encode('latin1'))
            final.append('    .db %s%s' % (vals, comment))
            continue
        # db/dw -> .db/.dw (amb token-fix: hi pot haver #hex/%bin).
        m = re.match(r'^(db|dw)\s+(.*)$', s, re.I)
        if m:
            final.append('    .%s %s%s' % (m.group(1).lower(), fix_token(m.group(2)), comment))
            continue
        # Tokens fixats adalt (fix_token es global al modul).
        # Label nu -> amb ':' (pero MAI un mnemonic: `ldi' sol es instruccio,
        # vist 12/10/26: colonificar-lo crea labels duplicats il.legals).
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', s) and s.lower() not in Z80_MNEMO:
            if taken:
                labels_seen.add(s)
            final.append(s + ':' + comment)
            continue
        # X equ Y -> X = Y (despres s'avalua i s'emet).
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s+equ\s+(.*)$', s, re.I)
        if m:
            s = '%s = %s' % (m.group(1), m.group(2))
        # X = expr (pres): avalua al diccionari; si te labels/desconeguts,
        # desa com a alias (definit pero no avaluable; FATAL si cal el valor).
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$', s)
        if m:
            try:
                symbols[m.group(1)] = eval_int(fix_token(m.group(2)).strip(), symbols, s)
            except ValueError:
                aliases[m.group(1)] = m.group(2).strip()
        m = re.match(r'^include\s+(.*)$', s, re.I)
        if m:
            final.append('.include %s%s' % (m.group(1), comment))
            continue
        # Conserva indentacio original si n'hi havia + reescriu operands.
        indent = code[:len(code) - len(code.lstrip())]
        final.append(fix_instruction(indent, fix_token(s)) + comment)
    # Verificacio final sorollosa: res de RASM ha de sobreviure. (El `#'
    # es LEGITIM a sdas (immediats), no es comprova; l'assemblatge ho valida.)
    txt = '\n'.join(final)
    for pat in (r'^\s*(MACRO|ENDM|REPEAT|REND)\b',
                r'%([01]{2,})', r'\bdk\w+\b', r'\{|\}'):
        bad = [l for l in final if re.search(pat, l.split(';')[0], re.I)]
        assert not bad, (pat, bad[:3])
    head = ['    .module %s' % module, '    .area _CODE']
    # `.area _DATA' buida OBLIGATORIA: sense ella el linker peta (rc=1,
    # "No definition of area _DATA"). Buida = 0 bytes; el build talla el
    # BIN a fi de CODE (cap cua de zeros).
    tail = ['    .area _DATA']
    return '\n'.join(head + final + tail) + '\n', asserts, decisions


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, 'rb').read().decode('latin1')
    out, asserts, decisions = convert(text)
    open(dst, 'w').write(out)
    print('convertit: %d asserts eliminats:' % len(asserts))
    for a in asserts:
        print('  ASSERT: %s' % a[:110])
    print('condicionals de nivell 0/1 (auditoria):')
    for depth, what, took in decisions:
        if depth <= 1:
            print('  [%s] %s' % ('PREN' if took else 'SALTA', what[:100]))


if __name__ == '__main__':
    main()
