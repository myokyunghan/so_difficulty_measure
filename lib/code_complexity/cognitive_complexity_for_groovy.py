"""
Groovy Cognitive Complexity Calculator
========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Groovy)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Groovy: if_statement
    - switch                              → Groovy: switch_expression (single +1, p.7)
    - for (classic)                       → Groovy: for_statement
    - for-each / for-in                   → Groovy: enhanced_for_statement
    - while                               → Groovy: while_statement
    - do while                            → Groovy: do_statement
    - catch                               → Groovy: catch_clause
    - ternary operator                    → Groovy: ternary_expression

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Groovy: if_statement as alternative
    - else                                → Groovy: block / closure as alternative

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - break LABEL, continue LABEL         → Groovy: break/continue with identifier
    - sequences of binary logical ops     → Groovy: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Ignored (p.6 "Ignore shorthand"):
    - Safe navigation (?.)                → No increment (typically parses as ERROR)
    - Elvis operator (?:)                 → No increment

  Not applicable in Groovy:
    - goto                                → Groovy has no goto

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else if, else, ternary
    - switch
    - for (classic and enhanced), while, do while
    - catch
    - nested functions: closure (when used as nested function),
                        lambda_expression, nested method/function definitions

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary       (NOT else if, NOT else)
    - switch
    - for, while, do while
    - catch

═══════════════════════════════════════════════════════════════════
Groovy-specific notes
═══════════════════════════════════════════════════════════════════

  - The tree-sitter-groovy grammar uses the AST node `closure` for both
    actual closures (`{ x -> ... }`) AND for the body of if/for/while
    branches in many parses. We disambiguate using ID tracking:
      • A `closure` reached via if/for/while/catch consequence/body
        (possibly through an `expression_statement` wrapper) → "body closure"
        → just visit children at the same nesting (caller already added 1)
      • A `closure` reached anywhere else → real closure → nesting+1

  - In Groovy DSL idioms like `items.each { x -> ... }`, the trailing
    closure is the `body` field of `method_invocation`. This closure IS a
    nested function, so it correctly gets nesting+1.

  - Switch: `switch_expression` (not statement) with `switch_block_statement_group`
    children containing label + body statements. Single +1 (p.7).

  - Top-level scripts: Groovy files can contain bare statements or
    `def f() { ... }` functions outside any class. We process both
    `function_definition` and bare statements via the bare-code fallback.

  - Safe navigation (`?.`) and Elvis (`?:`) often parse as ERROR. We
    silently ignore ERROR nodes per the "shorthand" exclusion (p.6).

═══════════════════════════════════════════════════════════════════
Known parser limitation
═══════════════════════════════════════════════════════════════════

  tree-sitter-groovy mis-parses `if`-statements that appear directly
  inside an explicit-parameter lambda body inside a closure. For example:

      items.each { x -> if (x > 0) { ... } }     // 'if' parses as method call!

  In this form, the parser treats `if` as a method name, the condition as
  arguments, and the braces as a trailing closure. The if_statement is
  not generated, so its complexity will be undercounted. The implicit-`it`
  form parses correctly:

      items.each { if (it > 0) { ... } }         // works correctly

  This is a parser bug, not a calculator bug. There is no clean workaround.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For scripts without function/method definitions, the calculator wraps
  the source in a dummy class+method, then re-parses.

Dependencies: pip install tree-sitter tree-sitter-groovy
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("groovy")
    except Exception:
        pass
    try:
        import tree_sitter_groovy as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-groovy")


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
        self.results = []
        self.details = []
        # IDs of closure nodes that should be treated as bodies, not nested funcs
        self._body_closures = set()

    # ── Helpers ──

    def _text(self, node):
        if node is None:
            return ""
        return self.source_code[node.start_byte:node.end_byte]

    def _line(self, node):
        return node.start_point[0] + 1

    def _add_detail(self, node, kind, structural, nesting):
        line = self._line(node)
        total = structural + nesting
        if nesting > 0:
            self.details.append(
                f"  Line {line:>4}: +{total} ({kind}: "
                f"+{structural} structural, +{nesting} nesting)")
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, description, increment):
        self.details.append(f"          +{increment} ({description})")

    def _mark_body_closure(self, body_node):
        """If body_node is `expression_statement > closure` (or just a closure),
        mark the inner closure as a body so it doesn't add nesting again."""
        if body_node is None:
            return
        node = body_node
        while node.type == "expression_statement":
            inner = None
            for c in node.children:
                if c.type not in (";",):
                    inner = c
                    break
            if inner is None:
                return
            node = inner
        if node.type == "closure":
            self._body_closures.add(id(node))

    def _visit_body(self, body_node, nesting):
        """Visit a control-flow body, handling expression_statement>closure
        wrappers transparently."""
        if body_node is None:
            return 0
        self._mark_body_closure(body_node)
        # Unwrap expression_statement wrapper
        node = body_node
        while node.type == "expression_statement":
            inner = None
            for c in node.children:
                if c.type not in (";",):
                    inner = c
                    break
            if inner is None:
                break
            node = inner
        # Now visit. If it's a block/closure, visit children directly.
        # Otherwise visit as a single statement.
        if node.type in ("block", "closure"):
            return self._visit_children(node, nesting)
        return self._visit(node, nesting)

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback
        if not self.results:
            wrapped = "class __Top__ { void __top__() {\n" + self.source_code + "\n} }"
            try:
                tree2 = self.parser.parse(bytes(wrapped, "utf-8"))
                if not tree2.root_node.has_error:
                    orig_src, orig_tree = self.source_code, self.tree
                    self.source_code = wrapped
                    self.tree = tree2
                    self.results = []
                    self._body_closures = set()
                    self._walk_top_level(tree2.root_node)
                    self.source_code = orig_src
                    self.tree = orig_tree
                    for r in self.results:
                        r["function"] = "<script>"
                        r["start_line"] = max(1, r["start_line"] - 1)
                        r["end_line"] = max(1, r["end_line"] - 1)
                        r["details"] = [
                            re.sub(
                                r"  Line\s+(\d+):",
                                lambda m: f"  Line {max(1, int(m.group(1)) - 1):>4}:",
                                d,
                            ) if d.startswith("  Line ") else d
                            for d in r["details"]
                        ]
            except Exception:
                pass

        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            t = child.type
            if t in ("class_declaration", "interface_declaration",
                     "enum_declaration", "record_declaration"):
                self._walk_class(child)
            elif t in ("method_declaration", "function_definition"):
                self._process_function(child)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            t = child.type
            if t in ("method_declaration", "constructor_declaration",
                     "function_definition"):
                self._process_function(child)
            elif t in ("class_declaration", "interface_declaration",
                       "enum_declaration", "record_declaration"):
                self._walk_class(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        self.details = []
        self._body_closures = set()
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
            if body.type == "closure":
                self._body_closures.add(id(body))
            complexity = self._visit_children(body, 0)

        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    # ── Node visitors ──

    def _visit_children(self, node, nesting):
        total = 0
        for child in node.children:
            total += self._visit(child, nesting)
        return total

    def _visit(self, node, nesting):
        t = node.type

        # ── B1 structural: if ──
        if t == "if_statement":
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: classic for ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            c += self._visit_body(body, nesting + 1)
            return c

        # ── B1 structural: enhanced for (for-each / for-in) ──
        if t == "enhanced_for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            c += self._visit_body(body, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while_statement":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            c += self._visit_body(body, nesting + 1)
            return c

        # ── B1 structural: do-while ──
        if t == "do_statement":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            c += self._visit_body(body, nesting + 1)
            return c

        # ── B1 structural: switch (single +1, p.7) ──
        if t == "switch_expression":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "switch_block_statement_group":
                        for sub in child.children:
                            if sub.type in ("switch_label", ":"):
                                continue
                            c += self._visit(sub, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch (p.7) ──
        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            c += self._visit_body(body, nesting + 1)
            return c

        # ── finally: no increment (p.7) ──
        if t == "finally_clause":
            for child in node.children:
                if child.type in ("block", "closure"):
                    return self._visit_children(child, nesting)
            return 0

        # ── B1 structural: ternary ──
        if t == "ternary_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            consequence = node.child_by_field_name("consequence")
            if consequence:
                c += self._visit(consequence, nesting + 1)
            alt = node.child_by_field_name("alternative")
            if alt:
                c += self._visit(alt, nesting + 1)
            return c

        # ── B1 fundamental: logical operators (p.7-8) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B1 fundamental: break/continue LABEL (p.8) ──
        if t == "break_statement":
            for child in node.children:
                if child.type == "identifier":
                    self._add_detail(node, "break to label", 1, 0)
                    return 1
            return 0

        if t == "continue_statement":
            for child in node.children:
                if child.type == "identifier":
                    self._add_detail(node, "continue to label", 1, 0)
                    return 1
            return 0

        # ── B2: closure → nesting (p.9), unless marked as control-flow body ──
        if t == "closure":
            if id(node) in self._body_closures:
                return self._visit_children(node, nesting)
            c = 0
            for child in node.children:
                if child.type in ("{", "}"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B2: lambda_expression (x -> body) → nesting (p.9) ──
        if t == "lambda_expression":
            c = 0
            seen_arrow = False
            for child in node.children:
                if child.type == "->":
                    seen_arrow = True
                    continue
                if seen_arrow:
                    c += self._visit(child, nesting + 1)
            return c

        # ── B2: nested method/function definitions → nesting (p.9) ──
        if t in ("method_declaration", "function_definition",
                 "constructor_declaration"):
            c = 0
            body = node.child_by_field_name("body")
            if body:
                if body.type == "closure":
                    self._body_closures.add(id(body))
                c += self._visit_children(body, nesting + 1)
            return c

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── ERROR (e.g. ?., ?:): silently ignore (p.6 "Ignore shorthand") ──
        if t == "ERROR":
            return 0

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / else if / else chain ──

    def _handle_if_chain(self, if_node, nesting, is_else_if):
        c = 0

        if is_else_if:
            c += 1
            self._add_detail(if_node, "else if", 1, 0)
        else:
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc

        # condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_body(consequence, nesting + 1)

        # alternative: if_statement (else if) or block/closure (else)
        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_statement":
                c += self._handle_if_chain(alt, nesting, is_else_if=True)
            else:
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit_body(alt, nesting + 1)

        return c

    # ── Boolean operator sequences (p.7-8) ──

    def _handle_boolean(self, node, nesting):
        ops = []
        self._collect_boolean_ops(node, ops)
        if not ops:
            return self._visit_children(node, nesting)

        c = 0
        prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                desc = (f"logical sequence '{op}'"
                        if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "binary_expression":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        op_text = self._text(op_node)
        if op_text not in ("&&", "||"):
            return

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type == "binary_expression":
            lo = left.child_by_field_name("operator")
            if lo and self._text(lo) in ("&&", "||"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "binary_expression":
            ro = right.child_by_field_name("operator")
            if ro and self._text(ro) in ("&&", "||"):
                self._collect_boolean_ops(right, ops)


# ── Public API ──

def calculate_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return CognitiveComplexityCalculator(f.read()).calculate()


def calculate_source(source_code: str):
    return CognitiveComplexityCalculator(source_code).calculate()


def calculate_directory(dirpath: str):
    all_results = []
    for root, dirs, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith((".groovy", ".gradle")):
                fpath = os.path.join(root, fname)
                try:
                    results = calculate_file(fpath)
                    for r in results:
                        r["file"] = fpath
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error processing {fpath}: {e}")
    return all_results


def print_results(results, verbose=True):
    total = 0
    for r in results:
        total += r["complexity"]
        print(f"\n{'='*60}")
        fname = r.get("file", "")
        if fname:
            print(f"File: {fname}")
        print(f"Function: {r['function']} "
              f"(lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose and r["details"]:
            print("Details:")
            for d in r["details"]:
                print(d)

    print(f"\n{'='*60}")
    print(f"Total Cognitive Complexity: {total}")
    print(f"Number of functions: {len(results)}")
    if results:
        print(f"Average per function: {total / len(results):.1f}")


if __name__ == "__main__":
    print("Groovy Cognitive Complexity Calculator")
    print("SonarSource Specification v1.7 (29 August 2023)")
    print("=" * 60)

    if len(sys.argv) > 1:
        path = sys.argv[1]
        verbose = "-v" in sys.argv or "--verbose" in sys.argv

        if os.path.isdir(path):
            results = calculate_directory(path)
        elif os.path.isfile(path):
            results = calculate_file(path)
        else:
            print(f"Not found: {path}")
            sys.exit(1)

        if "--json" in sys.argv:
            output = [{
                "file": r.get("file", ""),
                "function": r["function"],
                "complexity": r["complexity"],
                "start_line": r["start_line"],
                "end_line": r["end_line"],
            } for r in results]
            print(json.dumps(output, indent=2))
        else:
            print_results(results, verbose)