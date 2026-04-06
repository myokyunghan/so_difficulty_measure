"""
Dart Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)

Installation:
  pip install tree-sitter-language-pack
  or:
  git clone https://github.com/UserNobody14/tree-sitter-dart.git
  cd tree-sitter-dart && pip install .

Dart AST notes:
  - Methods/functions are split into method_signature + function_body siblings
  - Logical operators use logical_and_expression / logical_or_expression
  - if_statement has consequence/alternative fields
"""
import os
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("dart")
    except Exception:
        pass
    try:
        import tree_sitter_dart as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-dart")


class CognitiveComplexityCalculator:
    def __init__(self, src):
        self.src = src
        self.results = []
        self.details = []
        try:
            self.p = create_parser()
            self.tree = self.p.parse(bytes(src, "utf-8"))
        except Exception:
            self.tree = None

    def _t(self, n):
        return "" if n is None else self.src[n.start_byte:n.end_byte]

    def _l(self, n):
        return n.start_point[0] + 1

    def _a(self, n, k, s, ne):
        l = self._l(n); t = s + ne
        self.details.append(
            f"  Line {l:>4}: +{t} ({k}: +{s} structural, +{ne} nesting)" if ne
            else f"  Line {l:>4}: +{t} ({k})")

    def _ar(self, d, i):
        self.details.append(f"          +{i} ({d})")

    def calculate(self):
        if self.tree is None:
            return []
        if not self.src.strip():
            return []
        self.results = []
        self._walk(self.tree.root_node)

        # 잘못 파싱된 함수 제거 (bare code에서 if/for/while 등이 함수명으로 잡히는 경우)
        _KEYWORDS = {"if", "else", "for", "while", "do", "switch", "case",
                      "try", "catch", "return", "break", "continue", "throw",
                      "class", "import", "var", "final", "const"}
        self.results = [r for r in self.results if r["function"] not in _KEYWORDS]

        # 함수를 못 찾은 경우: bare code를 가상 함수로 감싸서 재파싱
        if not self.results:
            wrapped = "void __top__() {\n" + self.src + "\n}"
            try:
                tree2 = self.p.parse(bytes(wrapped, "utf-8"))
                if not tree2.root_node.has_error:
                    self.results = []
                    self._walk(tree2.root_node)
                    for r in self.results:
                        r["function"] = "<top-level>"
                        r["start_line"] = max(1, r["start_line"] - 1)
                        r["end_line"] = max(1, r["end_line"] - 1)
            except Exception:
                pass

        return self.results

    def _walk(self, node):
        """Top-level: find functions/methods.
        Dart splits them into sibling pairs: method_signature + function_body
        """
        children = list(node.children)
        i = 0
        while i < len(children):
            ch = children[i]

            # class_definition -> walk class_body
            if ch.type == "class_definition":
                body = ch.child_by_field_name("body")
                if body:
                    self._walk(body)
                i += 1
                continue

            # method_signature / function_signature followed by function_body
            if ch.type in ("method_signature", "function_signature"):
                name = self._extract_name(ch)
                # Next sibling should be function_body
                if i + 1 < len(children) and children[i + 1].type == "function_body":
                    fb = children[i + 1]
                    self._process_function(name, ch, fb)
                    i += 2
                    continue
                i += 1
                continue

            # declaration > method_signature + function_body pattern
            if ch.type == "declaration":
                self._walk(ch)
                i += 1
                continue

            i += 1

    def _extract_name(self, sig_node):
        """Extract function name from method_signature or function_signature"""
        for ch in sig_node.children:
            if ch.type == "function_signature":
                return self._extract_name(ch)
            if ch.type == "identifier":
                return self._t(ch)
            if ch.type in ("getter_signature", "setter_signature"):
                nn = ch.child_by_field_name("name")
                if nn:
                    return self._t(nn)
                for sub in ch.children:
                    if sub.type == "identifier":
                        return self._t(sub)
        return "<anonymous>"

    def _process_function(self, name, sig_node, body_node):
        self.details = []
        c = 0
        # function_body contains: [async], block
        for ch in body_node.children:
            if ch.type == "block":
                c += self._vc(ch, 0)
        start = sig_node.start_point[0] + 1
        end = body_node.end_point[0] + 1
        self.results.append({
            "function": name,
            "complexity": c,
            "start_line": start,
            "end_line": end,
            "details": list(self.details),
        })

    def _vc(self, node, ne):
        total = 0
        for ch in node.children:
            total += self._v(ch, ne)
        return total

    def _v(self, node, ne):
        t = node.type

        # if
        if t == "if_statement":
            return self._handle_if(node, ne, True)

        # for, for-in
        if t in ("for_statement",):
            self._a(node, "for", 1, ne)
            c = 1 + ne
            body = node.child_by_field_name("body")
            if body:
                c += self._vc(body, ne + 1)
            return c

        # while
        if t == "while_statement":
            self._a(node, "while", 1, ne)
            c = 1 + ne
            body = node.child_by_field_name("body")
            if body:
                c += self._vc(body, ne + 1)
            return c

        # do-while
        if t == "do_statement":
            self._a(node, "do-while", 1, ne)
            c = 1 + ne
            body = node.child_by_field_name("body")
            if body:
                c += self._vc(body, ne + 1)
            return c

        # switch
        if t == "switch_statement":
            self._a(node, "switch", 1, ne)
            c = 1 + ne
            body = node.child_by_field_name("body")
            if body:
                c += self._vc(body, ne + 1)
            return c

        # catch
        if t == "catch_clause":
            self._a(node, "catch", 1, ne)
            c = 1 + ne
            body = node.child_by_field_name("body")
            if body:
                c += self._vc(body, ne + 1)
            return c

        # try (no increment)
        if t == "try_statement":
            return self._vc(node, ne)

        # finally (no increment)
        if t == "finally_clause":
            body = node.child_by_field_name("body")
            return self._vc(body, ne) if body else self._vc(node, ne)

        # ternary
        if t == "conditional_expression":
            self._a(node, "ternary", 1, ne)
            c = 1 + ne
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._v(cond, ne)
            cons = node.child_by_field_name("consequence")
            if cons:
                c += self._v(cons, ne + 1)
            alt = node.child_by_field_name("alternative")
            if alt:
                c += self._v(alt, ne + 1)
            return c

        # logical AND/OR (Dart uses separate node types)
        if t == "logical_and_expression":
            return self._handle_logical(node, ne)
        if t == "logical_or_expression":
            return self._handle_logical(node, ne)

        # break/continue with label
        if t in ("break_statement", "continue_statement"):
            # Check if has label identifier
            has_label = False
            for ch in node.children:
                if ch.type == "identifier":
                    has_label = True
                    break
            if has_label:
                kw = "break" if "break" in t else "continue"
                self._a(node, f"{kw} with label", 1, 0)
                return 1
            return 0

        # lambda / anonymous function
        if t == "function_expression":
            c = 0
            for ch in node.children:
                if ch.type == "function_body":
                    for sub in ch.children:
                        if sub.type == "block":
                            c += self._vc(sub, ne + 1)
            return c

        return self._vc(node, ne)

    def _handle_if(self, node, ne, is_first):
        c = 0
        if is_first:
            c += 1 + ne
            self._a(node, "if", 1, ne)
        else:
            c += 1
            self._a(node, "else if", 1, 0)

        # condition (inside parentheses, not a named field usually)
        for ch in node.children:
            if ch.type in ("logical_and_expression", "logical_or_expression",
                           "binary_expression"):
                c += self._v(ch, ne)

        # consequence
        cons = node.child_by_field_name("consequence")
        if cons:
            c += self._vc(cons, ne + 1)

        # alternative
        alt = node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_statement":
                c += self._handle_if(alt, ne, False)
            elif alt.type == "block":
                c += 1
                self._a(alt, "else", 1, 0)
                c += self._vc(alt, ne + 1)

        return c

    def _handle_logical(self, node, ne):
        """Dart uses logical_and_expression / logical_or_expression as separate types"""
        ops = []
        self._collect_logical(node, ops)
        if not ops:
            return self._vc(node, ne)
        c = 0
        prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                self._ar(
                    f"logical sequence '{op}'" if prev is None
                    else f"logical change to '{op}'", 1)
                prev = op
        return c

    def _collect_logical(self, node, ops):
        if node.type == "logical_and_expression":
            children = list(node.children)
            for ch in children:
                if ch.type in ("logical_and_expression", "logical_or_expression"):
                    self._collect_logical(ch, ops)
            ops.append("&&")
        elif node.type == "logical_or_expression":
            children = list(node.children)
            for ch in children:
                if ch.type in ("logical_and_expression", "logical_or_expression"):
                    self._collect_logical(ch, ops)
            ops.append("||")


def calculate_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return CognitiveComplexityCalculator(f.read()).calculate()


def calculate_source(source_code):
    return CognitiveComplexityCalculator(source_code).calculate()


def calculate_directory(dirpath):
    results = []
    for root, _, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith(".dart"):
                fpath = os.path.join(root, fname)
                try:
                    r = calculate_file(fpath)
                    for x in r:
                        x["file"] = fpath
                    results.extend(r)
                except Exception as e:
                    print(f"Error {fpath}: {e}")
    return results


def print_results(results, verbose=True):
    total = sum(r["complexity"] for r in results)
    for r in results:
        print(f"\n{'='*60}")
        if r.get("file"):
            print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose:
            for d in r.get("details", []):
                print(d)
    print(f"\n{'='*60}")
    print(f"Total: {total}, Functions: {len(results)}")
    if results:
        print(f"Average: {total/len(results):.1f}")