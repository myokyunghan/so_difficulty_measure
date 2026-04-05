"""
Swift Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)
Dependencies: pip install tree-sitter tree-sitter-swift
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("swift")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_swift as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-swift")


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
            if ch.type == "function_declaration": self._proc(ch)
            elif ch.type in ("class_declaration", "struct_declaration", "extension_declaration", "protocol_declaration"):
                self._wcls(ch)

    def _wcls(self, node):
        body = node.child_by_field_name("body")
        if body is None:
            for ch in node.children:
                if ch.type in ("class_body", "statements"): body = ch; break
        if body is None: return
        for ch in body.children:
            if ch.type == "function_declaration": self._proc(ch)
            elif ch.type in ("class_declaration", "struct_declaration"): self._wcls(ch)

    def _proc(self, fn):
        nn = fn.child_by_field_name("name")
        name = self._t(nn) if nn else None
        if not name:
            for ch in fn.children:
                if ch.type in ("simple_identifier",): name = self._t(ch); break
        if not name: name = "<anon>"
        self.details = []
        body = fn.child_by_field_name("body")
        c = 0
        if body:
            # function_body: { statements }
            for ch in body.children:
                if ch.type == "statements": c += self._vc(ch, 0)
        self.results.append({"function": name, "complexity": c,
            "start_line": fn.start_point[0]+1, "end_line": fn.end_point[0]+1,
            "details": list(self.details)})

    def _vc(self, n, ne):
        t = 0
        for ch in n.children: t += self._v(ch, ne)
        return t

    def _v(self, n, ne):
        t = n.type

        if t == "if_statement": return self._hif(n, ne, True)

        if t == "for_statement":
            self._a(n, "for", 1, ne); c = 1 + ne
            # body is {statements}
            for ch in n.children:
                if ch.type == "statements": c += self._vc(ch, ne+1)
            return c

        if t == "while_statement":
            self._a(n, "while", 1, ne); c = 1 + ne
            cond = n.child_by_field_name("condition")
            if cond: c += self._v(cond, ne)
            for ch in n.children:
                if ch.type == "statements": c += self._vc(ch, ne+1)
            return c

        if t == "repeat_while_statement":
            self._a(n, "repeat-while", 1, ne); c = 1 + ne
            for ch in n.children:
                if ch.type == "statements": c += self._vc(ch, ne+1)
            return c

        if t == "switch_statement":
            self._a(n, "switch", 1, ne); c = 1 + ne
            for ch in n.children:
                if ch.type == "switch_entry":
                    for sub in ch.children:
                        if sub.type == "statements": c += self._vc(sub, ne+1)
            return c

        if t == "do_statement":
            # Swift do-catch (try)
            return self._vc(n, ne)

        if t == "catch_block":
            self._a(n, "catch", 1, ne); c = 1 + ne
            for ch in n.children:
                if ch.type == "statements": c += self._vc(ch, ne+1)
            return c

        if t == "ternary_expression":
            self._a(n, "ternary", 1, ne); c = 1 + ne
            cond = n.child_by_field_name("condition")
            if cond: c += self._v(cond, ne)
            it = n.child_by_field_name("if_true")
            if it: c += self._v(it, ne+1)
            iff = n.child_by_field_name("if_false")
            if iff: c += self._v(iff, ne+1)
            return c

        if t == "conjunction_expression":
            return self._handle_conj_disj(n, ne, "&&")

        if t == "disjunction_expression":
            return self._handle_conj_disj(n, ne, "||")

        if t in ("closure_expression",):
            c = 0
            for ch in n.children:
                if ch.type == "statements": c += self._vc(ch, ne+1)
            return c

        return self._vc(n, ne)

    def _hif(self, n, ne, first):
        c = 0
        if first: c += 1 + ne; self._a(n, "if", 1, ne)
        else: c += 1; self._a(n, "else if", 1, 0)

        cond = n.child_by_field_name("condition")
        if cond: c += self._v(cond, ne)

        # Children: if, cond, {, statements, }, [else, if_statement/{...}]
        saw_body = False; saw_else = False
        for ch in n.children:
            if ch.type == "statements" and not saw_else:
                c += self._vc(ch, ne+1); saw_body = True
            elif ch.type == "else":
                saw_else = True
            elif saw_else:
                if ch.type == "if_statement":
                    c += self._hif(ch, ne, False)
                elif ch.type == "statements":
                    c += 1; self._a(ch, "else", 1, 0); c += self._vc(ch, ne+1)
                elif ch.type == "{":
                    pass
                elif ch.type == "}":
                    pass
                else:
                    pass
                saw_else = False
        return c

    def _handle_conj_disj(self, n, ne, op_char):
        ops = []
        self._collect_conj_disj(n, ops)
        if not ops: return self._vc(n, ne)
        c = 0; prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                self._ar(f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'", 1)
                prev = op
        return c

    def _collect_conj_disj(self, n, ops):
        if n.type == "conjunction_expression":
            lhs = n.child_by_field_name("lhs")
            if lhs and lhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj(lhs, ops)
            ops.append("&&")
            rhs = n.child_by_field_name("rhs")
            if rhs and rhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj(rhs, ops)
        elif n.type == "disjunction_expression":
            lhs = n.child_by_field_name("lhs")
            if lhs and lhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj(lhs, ops)
            ops.append("||")
            rhs = n.child_by_field_name("rhs")
            if rhs and rhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj(rhs, ops)


def calculate_file(fp):
    with open(fp, "r", encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code): return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    r = []
    for root, _, files in os.walk(d):
        for f in sorted(files):
            if f.endswith(".swift"):
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