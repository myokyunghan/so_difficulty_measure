"""
Scala Cognitive Complexity Calculator
=======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Scala)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Scala: if_expression
    - match (switch equivalent)           → Scala: match_expression (single +1, p.7)
    - for / for-yield                     → Scala: for_expression
    - while                               → Scala: while_expression
    - do-while                            → Scala: do_while_expression
    - catch                               → Scala: catch_clause (single +1, p.7)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Scala: if_expression as alternative of if_expression
    - else                                → Scala: block as alternative of if_expression

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - sequences of binary logical ops     → Scala: infix_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Not applicable in Scala:
    - goto, labeled break/continue        → Scala has no goto. scala.util.control.Breaks
                                            uses regular method calls (not language-level)
    - ternary operator                    → Scala uses if as expression

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, else if, else
    - match
    - for, while, do-while
    - catch
    - nested functions: lambda_expression, nested function_definition

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if                (NOT else if, NOT else)
    - match
    - for, while, do-while
    - catch

═══════════════════════════════════════════════════════════════════
Scala-specific notes
═══════════════════════════════════════════════════════════════════

  - if and match are EXPRESSIONS in Scala (return values):
      `val x = if (a) 1 else 0`
      `val y = x match { case 1 => "one"; case _ => "other" }`
    They are still treated as structural increments per the spec.
    Scala has no separate ternary operator — `if` serves that role.

  - match: single +1 for the entire match (per p.7 "Switches"). No additional
    increment per case_clause. Match guards (`case n if n > 0 =>`) do NOT
    add increments — they're part of the pattern matching.

  - for-comprehensions: `for (i <- xs) yield ...` and `for (i <- xs) { ... }`
    are both for_expression. Treated as +1 structural + nesting.
    Guards inside for-comprehensions (`for (i <- xs if i > 0)`) are part of
    the comprehension's pattern, no extra increment per spec.

  - try/catch: try block and finally block are ignored (p.7). The catch_clause
    contains a case_block of case_clauses. Per spec, one catch = +1 regardless
    of how many exception types are caught. Scala's case-based catch is treated
    as a single catch_clause = single +1 (matching multi-type catch behavior).

  - Logical operators: Scala uses `infix_expression` with `operator_identifier`
    children. && and || are detected by their text.

  - Lambdas: `(x: Int) => expr` and `x => { ... }`. Treated as nested method
    (no structural increment, increases nesting per p.9).

  - Nested function_definition (def inside def): nesting increment (p.9).

  - class/object/trait: walked recursively to find member functions.

  - Scala has no goto, no labeled break/continue at language level.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For snippets without function definitions:
    Wraps in `def __top__() = { ... }` and re-parses.

Dependencies: pip install tree-sitter tree-sitter-scala
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("scala")
    except Exception:
        pass
    try:
        import tree_sitter_scala as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-scala")


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
        self.results = []
        self.details = []

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

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback
        if not self.results:
            wrapped = "def __top__() = {\n" + self.source_code + "\n}"
            try:
                tree2 = self.parser.parse(bytes(wrapped, "utf-8"))
                if not tree2.root_node.has_error:
                    orig_src, orig_tree = self.source_code, self.tree
                    self.source_code = wrapped
                    self.tree = tree2
                    self.results = []
                    self._walk_top_level(tree2.root_node)
                    self.source_code = orig_src
                    self.tree = orig_tree
                    for r in self.results:
                        r["function"] = "<top-level>"
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
            if t == "function_definition":
                self._process_function(child)
            elif t in ("class_definition", "object_definition",
                       "trait_definition"):
                self._walk_class(child)
            elif t == "package_clause":
                # Skip package declarations
                pass
            elif t == "package_object":
                self._walk_class(child)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type == "function_definition":
                self._process_function(child)
            elif child.type in ("class_definition", "object_definition",
                                "trait_definition"):
                self._walk_class(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
            # body may be a block, a single expression, or directly a control-flow
            complexity = self._visit(body, 0)

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
        if t == "if_expression":
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: for / for-yield ──
        if t == "for_expression":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            # Visit enumerators (generators) for nested logic
            enums = node.child_by_field_name("enumerators")
            if enums:
                c += self._visit(enums, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while_expression":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── B1 structural: do-while ──
        if t == "do_while_expression":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── B1 structural: match (single +1, p.7) ──
        if t == "match_expression":
            inc = 1 + nesting
            self._add_detail(node, "match", 1, nesting)
            c = inc
            # Visit the value being matched
            value = node.child_by_field_name("value")
            if value:
                c += self._visit(value, nesting)
            # Visit case bodies (no additional increment per case)
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "case_clause":
                        # Visit only the case body (RHS), not the pattern
                        # Match guards do NOT add increments per spec
                        case_body = child.child_by_field_name("body")
                        if case_body:
                            if isinstance(case_body, list):
                                for cb in case_body:
                                    c += self._visit(cb, nesting + 1)
                            else:
                                c += self._visit(case_body, nesting + 1)
                        # Also visit any other body-tagged children
                        for sub in child.children:
                            fn = self._field_name(child, sub)
                            if fn == "body" and sub != case_body:
                                c += self._visit(sub, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_expression":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch (p.7) ──
        if t == "catch_clause":
            # Per spec: "a catch only adds one point to the Cognitive
            # Complexity score, no matter how many exception types are caught"
            # Scala's pattern-based catch with multiple cases is treated as
            # a single catch handler.
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            # Visit case bodies inside the catch's case_block
            for child in node.children:
                if child.type == "case_block":
                    for sub in child.children:
                        if sub.type == "case_clause":
                            case_body = sub.child_by_field_name("body")
                            if case_body:
                                c += self._visit(case_body, nesting + 1)
                            for grand in sub.children:
                                fn = self._field_name(sub, grand)
                                if fn == "body" and grand != case_body:
                                    c += self._visit(grand, nesting + 1)
            return c

        # ── finally: no increment (p.7) ──
        if t == "finally_clause":
            for child in node.children:
                if child.type == "block":
                    return self._visit_children(child, nesting)
            return 0

        # ── B1 fundamental: logical operators in infix_expression ──
        if t == "infix_expression":
            op_text = self._infix_operator(node)
            if op_text in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: lambda_expression → no increment, increases nesting (p.9) ──
        if t == "lambda_expression":
            c = 0
            # Visit body (everything after =>)
            for child in node.children:
                if child.type not in ("bindings", "binding", "identifier",
                                      "=>", "(", ")"):
                    c += self._visit(child, nesting + 1)
                elif child.type == "identifier":
                    # Could be the parameter (single param) or actually body
                    # Single-param lambdas: x => body
                    # If this identifier is followed by => then it's param
                    # Skip param identifier - in tree-sitter-scala, params come
                    # before => and body after
                    pass
            return c

        # ── B2: nested function_definition → nesting (p.9) ──
        if t == "function_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    # ── if / else if / else chain ──

    def _handle_if_chain(self, if_node, nesting, is_else_if):
        c = 0

        if is_else_if:
            # B1 hybrid: else if → +1, NO nesting penalty, increases nesting
            c += 1
            self._add_detail(if_node, "else if", 1, 0)
        else:
            # B1 structural: if → +1, receives nesting
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
            c += self._visit(consequence, nesting + 1)

        # alternative: if_expression (else if) or block/expression (else)
        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_expression":
                c += self._handle_if_chain(alt, nesting, is_else_if=True)
            else:
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit(alt, nesting + 1)

        return c

    # ── infix operator helper ──

    def _infix_operator(self, node):
        """Extract the operator text from an infix_expression."""
        op = node.child_by_field_name("operator")
        if op:
            return self._text(op)
        # Fallback: look for operator_identifier child
        for child in node.children:
            if child.type == "operator_identifier":
                return self._text(child)
        return ""

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
        if node.type != "infix_expression":
            return
        op_text = self._infix_operator(node)
        if op_text not in ("&&", "||"):
            return

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type == "infix_expression":
            lo = self._infix_operator(left)
            if lo in ("&&", "||"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "infix_expression":
            ro = self._infix_operator(right)
            if ro in ("&&", "||"):
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
            if fname.endswith((".scala", ".sc")):
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
    print("Scala Cognitive Complexity Calculator")
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