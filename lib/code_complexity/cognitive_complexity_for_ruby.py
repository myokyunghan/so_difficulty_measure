"""
Ruby Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)
Dependencies: pip install tree-sitter tree-sitter-ruby
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("ruby")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_ruby as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-ruby")


class CognitiveComplexityCalculator:
    def __init__(self, src):
        self.src = src; self.p = create_parser()
        self.tree = self.p.parse(bytes(src, "utf-8"))
        self.results = []; self.details = []

    def _t(self, n): return "" if n is None else self.src[n.start_byte:n.end_byte]
    def _l(self, n): return n.start_point[0]+1
    def _a(self, n, k, s, ne):
        l=self._l(n); t=s+ne
        self.details.append(f"  Line {l:>4}: +{t} ({k}: +{s} structural, +{ne} nesting)" if ne else f"  Line {l:>4}: +{t} ({k})")
    def _ar(self, d, i): self.details.append(f"          +{i} ({d})")

    def calculate(self):
        self.results = []
        self._walk(self.tree.root_node)
        return self.results

    def _walk(self, node):
        for ch in node.children:
            if ch.type in ("method", "singleton_method"): self._proc(ch)
            elif ch.type in ("class", "module"): self._wcls(ch)

    def _wcls(self, node):
        body = node.child_by_field_name("body")
        if body is None: return
        for ch in body.children:
            if ch.type in ("method", "singleton_method"): self._proc(ch)
            elif ch.type in ("class", "module"): self._wcls(ch)

    def _proc(self, fn):
        nn = fn.child_by_field_name("name")
        name = self._t(nn) if nn else "<anon>"
        self.details = []
        body = fn.child_by_field_name("body")
        c = self._vc(body, 0) if body else 0
        self.results.append({"function": name, "complexity": c,
            "start_line": fn.start_point[0]+1, "end_line": fn.end_point[0]+1,
            "details": list(self.details)})

    def _vc(self, n, ne):
        t = 0
        for ch in n.children: t += self._v(ch, ne)
        return t

    def _v(self, n, ne):
        t = n.type

        if t == "if": return self._hif(n, ne)
        if t == "unless": return self._hunless(n, ne)
        if t == "if_modifier":
            self._a(n, "if modifier", 1, ne); return 1 + ne
        if t == "unless_modifier":
            self._a(n, "unless modifier", 1, ne); return 1 + ne

        if t in ("while", "until"):
            self._a(n, t, 1, ne); c = 1 + ne
            cond = n.child_by_field_name("condition")
            if cond: c += self._v(cond, ne)
            body = n.child_by_field_name("body")
            if body: c += self._vc(body, ne+1)
            return c

        if t == "for":
            self._a(n, "for", 1, ne); c = 1 + ne
            body = n.child_by_field_name("body")
            if body: c += self._vc(body, ne+1)
            return c

        if t == "case":
            self._a(n, "case", 1, ne); c = 1 + ne
            for ch in n.children:
                if ch.type == "when":
                    body = ch.child_by_field_name("body")
                    if body: c += self._vc(body, ne+1)
                elif ch.type == "else":
                    c += 1; self._a(ch, "else", 1, 0)
                    for sub in ch.children:
                        if sub.type not in ("else",): c += self._v(sub, ne+1)
            return c

        if t == "begin": return self._vc(n, ne)  # try equivalent
        if t == "rescue":
            self._a(n, "rescue", 1, ne); c = 1 + ne
            body = n.child_by_field_name("body")
            if body: c += self._vc(body, ne+1)
            else:
                then = n.child_by_field_name("then")
                if then: c += self._vc(then, ne+1)
            return c
        if t == "ensure":
            for ch in n.children:
                if ch.type not in ("ensure",): return self._v(ch, ne)
            return 0

        if t == "conditional":  # ternary
            self._a(n, "ternary", 1, ne); c = 1 + ne
            cond = n.child_by_field_name("condition")
            if cond: c += self._v(cond, ne)
            cons = n.child_by_field_name("consequence")
            if cons: c += self._v(cons, ne+1)
            alt = n.child_by_field_name("alternative")
            if alt: c += self._v(alt, ne+1)
            return c

        if t == "binary":
            return self._hbin(n, ne)

        if t in ("do_block", "block", "lambda"):
            c = 0; body = n.child_by_field_name("body")
            if body: c += self._vc(body, ne+1)
            return c

        return self._vc(n, ne)

    def _hif(self, n, ne):
        c = 1 + ne; self._a(n, "if", 1, ne)
        cond = n.child_by_field_name("condition")
        if cond: c += self._v(cond, ne)
        cons = n.child_by_field_name("consequence")
        if cons: c += self._vc(cons, ne+1)
        alt = n.child_by_field_name("alternative")
        if alt:
            if alt.type == "elsif": c += self._helsif(alt, ne)
            elif alt.type == "else":
                c += 1; self._a(alt, "else", 1, 0)
                for ch in alt.children:
                    if ch.type not in ("else",): c += self._v(ch, ne+1)
        return c

    def _hunless(self, n, ne):
        c = 1 + ne; self._a(n, "unless", 1, ne)
        cond = n.child_by_field_name("condition")
        if cond: c += self._v(cond, ne)
        cons = n.child_by_field_name("consequence")
        if cons: c += self._vc(cons, ne+1)
        alt = n.child_by_field_name("alternative")
        if alt and alt.type == "else":
            c += 1; self._a(alt, "else", 1, 0)
            for ch in alt.children:
                if ch.type not in ("else",): c += self._v(ch, ne+1)
        return c

    def _helsif(self, n, ne):
        c = 1; self._a(n, "elsif", 1, 0)
        cond = n.child_by_field_name("condition")
        if cond: c += self._v(cond, ne)
        cons = n.child_by_field_name("consequence")
        if cons: c += self._vc(cons, ne+1)
        alt = n.child_by_field_name("alternative")
        if alt:
            if alt.type == "elsif": c += self._helsif(alt, ne)
            elif alt.type == "else":
                c += 1; self._a(alt, "else", 1, 0)
                for ch in alt.children:
                    if ch.type not in ("else",): c += self._v(ch, ne+1)
        return c

    def _hbin(self, n, ne):
        ops = []; self._cops(n, ops)
        if not ops: return self._vc(n, ne)
        c = 0; prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1; self._ar(f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'", 1)
                prev = op
        return c

    def _cops(self, n, ops):
        if n.type != "binary": return
        op = n.child_by_field_name("operator")
        if not op: return
        ot = self._t(op)
        if ot not in ("&&", "||", "and", "or"): return
        left = n.child_by_field_name("left")
        if left and left.type == "binary":
            lo = left.child_by_field_name("operator")
            if lo and self._t(lo) in ("&&", "||", "and", "or"): self._cops(left, ops)
        ops.append(ot)
        right = n.child_by_field_name("right")
        if right and right.type == "binary":
            ro = right.child_by_field_name("operator")
            if ro and self._t(ro) in ("&&", "||", "and", "or"): self._cops(right, ops)


def calculate_file(fp):
    with open(fp, "r", encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code): return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    r = []
    for root, _, files in os.walk(d):
        for f in sorted(files):
            if f.endswith(".rb"):
                p = os.path.join(root, f)
                try: res = calculate_file(p); [x.update(file=p) for x in res]; r.extend(res)
                except Exception as e: print(f"Error {p}: {e}")
    return r
def print_results(results, verbose=True):
    total = sum(r["complexity"] for r in results)
    for r in results:
        print(f"\n{'='*60}")
        if r.get("file"): print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose:
            for d in r.get("details", []): print(d)
    print(f"\n{'='*60}\nTotal: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")