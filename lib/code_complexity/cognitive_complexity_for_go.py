"""
Go Cognitive Complexity Calculator
===================================
Based on Campbell 2018 (ICSE TechDebt '18)

Go specifics:
- No ternary operator
- No try/catch (use error returns)
- select statement (treated like switch)
- Labeled break/continue
- Short variable declarations in if conditions

Dependencies: pip install tree-sitter tree-sitter-go
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("go")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_go as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-go")


class CognitiveComplexityCalculator:
    def __init__(self, source_code):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
        self.results = []; self.details = []

    def _text(self, n):
        return "" if n is None else self.source_code[n.start_byte:n.end_byte]
    def _line(self, n): return n.start_point[0] + 1
    def _add(self, n, kind, s, nest):
        l = self._line(n); t = s + nest
        self.details.append(f"  Line {l:>4}: +{t} ({kind}: +{s} structural, +{nest} nesting)" if nest else f"  Line {l:>4}: +{t} ({kind})")
    def _raw(self, d, i): self.details.append(f"          +{i} ({d})")

    def calculate(self):
        self.results = []
        for ch in self.tree.root_node.children:
            if ch.type in ('function_declaration', 'method_declaration'):
                self._proc(ch)
        return self.results

    def _proc(self, fn):
        name_node = fn.child_by_field_name('name')
        name = self._text(name_node) if name_node else '<anon>'
        self.details = []
        body = fn.child_by_field_name('body')
        c = self._vc(body, 0) if body else 0
        self.results.append({'function': name, 'complexity': c,
            'start_line': fn.start_point[0]+1, 'end_line': fn.end_point[0]+1,
            'details': list(self.details)})

    def _vc(self, n, nest):
        t = 0
        for ch in n.children: t += self._v(ch, nest)
        return t

    def _v(self, n, nest):
        t = n.type

        if t == 'if_statement':
            return self._if(n, nest, True)

        if t == 'for_statement':
            self._add(n, 'for', 1, nest); c = 1 + nest
            body = n.child_by_field_name('body')
            if body: c += self._vc(body, nest+1)
            return c

        if t in ('expression_switch_statement', 'type_switch_statement'):
            self._add(n, 'switch', 1, nest); c = 1 + nest
            body = n.child_by_field_name('body')
            if body: c += self._vc(body, nest+1)
            return c

        if t == 'select_statement':
            self._add(n, 'select', 1, nest); c = 1 + nest
            body = n.child_by_field_name('body')
            if body: c += self._vc(body, nest+1)
            return c

        if t == 'goto_statement':
            self._add(n, 'goto', 1, 0); return 1

        if t in ('break_statement', 'continue_statement'):
            has_label = any(ch.type == 'label_name' for ch in n.children)
            if has_label:
                kw = 'break' if 'break' in t else 'continue'
                self._add(n, f'{kw} with label', 1, 0); return 1
            return 0

        if t == 'labeled_statement':
            c = 0
            for ch in n.children:
                if ch.type not in ('label_name', ':'): c += self._v(ch, nest)
            return c

        if t == 'binary_expression':
            return self._bin(n, nest)

        if t == 'func_literal':
            body = n.child_by_field_name('body')
            return self._vc(body, nest+1) if body else 0

        if t in ('communication_case', 'expression_case', 'default_case', 'type_case'):
            return self._vc(n, nest)

        return self._vc(n, nest)

    def _if(self, n, nest, first):
        c = 0
        if first:
            c += 1 + nest; self._add(n, 'if', 1, nest)
        else:
            c += 1; self._add(n, 'else if', 1, 0)

        cond = n.child_by_field_name('condition')
        if cond: c += self._v(cond, nest)
        cons = n.child_by_field_name('consequence')
        if cons: c += self._vc(cons, nest+1)
        alt = n.child_by_field_name('alternative')
        if alt:
            if alt.type == 'if_statement':
                c += self._if(alt, nest, False)
            elif alt.type == 'block':
                c += 1; self._add(alt, 'else', 1, 0)
                c += self._vc(alt, nest+1)
        return c

    def _bin(self, n, nest):
        ops = []; self._ops(n, ops)
        if not ops: return self._vc(n, nest)
        c = 0; prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1; self._raw(f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'", 1)
                prev = op
        return c

    def _ops(self, n, ops):
        if n.type != 'binary_expression': return
        op = n.child_by_field_name('operator')
        if not op: return
        ot = self._text(op)
        if ot not in ('&&', '||'): return
        left = n.child_by_field_name('left')
        if left and left.type == 'binary_expression':
            lo = left.child_by_field_name('operator')
            if lo and self._text(lo) in ('&&', '||'): self._ops(left, ops)
        ops.append(ot)
        right = n.child_by_field_name('right')
        if right and right.type == 'binary_expression':
            ro = right.child_by_field_name('operator')
            if ro and self._text(ro) in ('&&', '||'): self._ops(right, ops)


def calculate_file(fp):
    with open(fp, "r", encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code):
    return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    r = []
    for root, _, files in os.walk(d):
        for f in sorted(files):
            if f.endswith('.go'):
                p = os.path.join(root, f)
                try:
                    res = calculate_file(p)
                    for x in res: x['file'] = p
                    r.extend(res)
                except Exception as e: print(f"Error {p}: {e}")
    return r
def print_results(results, verbose=True):
    total = sum(r['complexity'] for r in results)
    for r in results:
        print(f"\n{'='*60}")
        if r.get('file'): print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose:
            for d in r.get('details', []): print(d)
    print(f"\n{'='*60}\nTotal: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")