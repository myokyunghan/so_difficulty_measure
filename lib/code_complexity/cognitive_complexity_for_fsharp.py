"""
F# Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)

Installation: git clone https://github.com/ionide/tree-sitter-fsharp.git && cd tree-sitter-fsharp && pip install .

If tree-sitter parser is not available, calculate_source/calculate_file
will return an empty list (no functions found).
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("fsharp")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_fsharp as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-fsharp")


class CognitiveComplexityCalculator:
    def __init__(self, src):
        self.src = src; self.results = []; self.details = []
        try:
            self.p = create_parser()
            self.tree = self.p.parse(bytes(src, "utf-8"))
        except (ImportError, Exception):
            self.tree = None

    def _t(self, n): return "" if n is None else self.src[n.start_byte:n.end_byte]
    def _l(self, n): return n.start_point[0]+1
    def _a(self, n, k, s, ne):
        l=self._l(n); t=s+ne
        self.details.append(f"  Line {l:>4}: +{t} ({k}: +{s} structural, +{ne} nesting)" if ne else f"  Line {l:>4}: +{t} ({k})")
    def _ar(self, d, i): self.details.append(f"          +{i} ({d})")

    def calculate(self):
        if self.tree is None:
            return []
        self.results = []
        self._walk(self.tree.root_node, 0)
        return self.results

    def _walk(self, node, depth):
        if depth > 5: return
        func_types = {"function_definition", "function_declaration", "method_declaration",
                      "method_definition", "function", "subroutine", "procedure_definition"}
        for ch in node.children:
            if ch.type in func_types: self._proc(ch)
            elif ch.child_count > 0 and ch.type not in ("ERROR",): self._walk(ch, depth+1)

    def _proc(self, fn):
        name = "<anon>"
        nn = fn.child_by_field_name("name")
        if nn: name = self._t(nn)
        else:
            for ch in fn.children:
                if ch.type in ("identifier", "simple_identifier"): name = self._t(ch); break
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
        if "if" in t and ("statement" in t or "expression" in t):
            self._a(n, "if", 1, ne); c = 1 + ne
            body = n.child_by_field_name("body") or n.child_by_field_name("consequence")
            if body: c += self._vc(body, ne+1)
            alt = n.child_by_field_name("alternative")
            if alt:
                if "if" in alt.type: c += 1; self._a(alt, "else if", 1, 0); c += self._vc(alt, ne+1)
                else: c += 1; self._a(alt, "else", 1, 0); c += self._vc(alt, ne+1)
            return c
        if ("for" in t or "while" in t or "loop" in t) and ("statement" in t or "expression" in t):
            self._a(n, t.split("_")[0], 1, ne); c = 1 + ne
            body = n.child_by_field_name("body")
            if body: c += self._vc(body, ne+1)
            return c
        if "catch" in t or "rescue" in t or "except" in t:
            self._a(n, "catch", 1, ne); c = 1 + ne
            body = n.child_by_field_name("body")
            if body: c += self._vc(body, ne+1)
            return c
        if "try" in t and "statement" in t: return self._vc(n, ne)
        if "switch" in t or "match" in t:
            self._a(n, "switch", 1, ne); return 1 + ne + self._vc(n, ne+1)
        if t in ("binary_expression", "binary_operator", "binary", "infix"):
            op = n.child_by_field_name("operator")
            if op and self._t(op) in ("&&", "||", "and", "or"):
                self._ar(f"logical '{self._t(op)}'", 1); return 1
        return self._vc(n, ne)

def calculate_file(fp):
    with open(fp, "r", encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code): return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    exts = ('.fs', '.fsx')
    r = []
    for root, _, files in os.walk(d):
        for f in sorted(files):
            if any(f.endswith(e) for e in exts):
                p = os.path.join(root, f)
                try: res = calculate_file(p); [x.update(file=p) for x in res]; r.extend(res)
                except Exception as e: print(f"Error {p}: {e}")
    return r
def print_results(results, verbose=True):
    total = sum(r["complexity"] for r in results)
    for r in results:
        print("\n" + "="*60)
        f = r.get("file", "")
        if f: print(f"File: {f}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose:
            for d in r.get("details", []): print(d)
    print("\n" + "="*60)
    print(f"Total: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")