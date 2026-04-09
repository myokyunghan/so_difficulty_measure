"""
Java Cognitive Complexity Calculator (with hang protection)
============================================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.

Hang protection added in this version:
  1. sys.setrecursionlimit raised to handle legitimately deep ASTs
     (long boolean chains, deeply nested ifs).
  2. Visitor recursion depth cap as a hard safety net (raises a
     controlled exception instead of hanging on pathological inputs).
  3. Bare-code fallback only triggers if the original parse was clean
     — re-parsing already-broken source can produce surprising trees
     and waste time.
  4. Iterative collection of long &&/|| chains (avoids deep Python
     recursion on `a && b && c && ... && z`).

Dependencies: pip install tree-sitter tree-sitter-java
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


# Raise Python's default recursion limit. tree-sitter ASTs for long
# boolean chains or deeply-nested expressions can be hundreds of levels
# deep, beyond Python's default 1000.
sys.setrecursionlimit(10000)

# Hard cap on visitor recursion to prevent runaway recursion on
# pathological inputs (e.g., parser quirks producing deeply nested errors).
_MAX_VISITOR_DEPTH = 5000


def create_parser():
    """Prefer individual tree_sitter_java package because
    tree_sitter_language_pack may return a wrong/generic parser for
    java on some installations."""
    try:
        import tree_sitter_java as _mod
        _p = Parser(Language(_mod.language()))
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except ImportError:
        pass
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("java")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    raise ImportError("Install: pip install tree-sitter-java")
class _RecursionGuard(Exception):
    """Raised when visitor recursion exceeds the safety cap."""
    pass


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        try:
            self.tree = self.parser.parse(bytes(source_code, "utf-8"))
            self._parse_failed = False
        except ValueError:
            # tree-sitter native timeout fired — input is too pathological
            # for the parser (e.g., a non-Java file passed to the Java parser).
            self.tree = None
            self._parse_failed = True
        self.results = []
        self.details = []
        self._depth = 0  # current visitor recursion depth

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
                f"+{structural} structural, +{nesting} nesting)"
            )
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, description, increment):
        self.details.append(f"          +{increment} ({description})")

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        if self._parse_failed or self.tree is None:
            # Parse timed out — return empty results without trying fallback
            return self.results
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback (Stack Overflow snippets 등)
        # IMPORTANT: only attempt fallback if the original parse was clean.
        # Re-parsing broken code can waste time and produce odd trees.

        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            if child.type in ("class_declaration", "interface_declaration",
                              "enum_declaration", "record_declaration"):
                self._walk_class(child)
            elif child.type == "method_declaration":
                self._process_function(child)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type in ("method_declaration", "constructor_declaration"):
                self._process_function(child)
            elif child.type in ("class_declaration", "interface_declaration",
                                "enum_declaration", "record_declaration"):
                self._walk_class(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
            try:
                self._depth = 0
                complexity = self._visit_children(body, 0)
            except _RecursionGuard:
                self.details.append(
                    f"  [WARNING] visitor recursion limit reached "
                    f"({_MAX_VISITOR_DEPTH}); complexity may be incomplete")
            except RecursionError:
                self.details.append(
                    "  [WARNING] Python recursion limit reached; "
                    "complexity may be incomplete")

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
        # Recursion safety check
        self._depth += 1
        if self._depth > _MAX_VISITOR_DEPTH:
            self._depth -= 1
            raise _RecursionGuard()
        try:
            return self._visit_impl(node, nesting)
        finally:
            self._depth -= 1

    def _visit_impl(self, node, nesting):
        t = node.type

        # ── B1 structural: if ──
        if t == "if_statement":
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: for ──
        if t in ("for_statement", "enhanced_for_statement"):
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
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
            if body:
                c += self._visit_children(body, nesting + 1)
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
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: switch (single +1, p.7) ──
        if t == "switch_expression":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "switch_block":
                    for group in child.children:
                        if group.type == "switch_block_statement_group":
                            c += self._visit_children(group, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            return self._visit_children(node, nesting)

        # ── try-with-resources: no increment, no nesting change ──
        if t == "try_with_resources_statement":
            return self._visit_children(node, nesting)

        # ── B1 structural: catch (single, p.7) ──
        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── finally: no increment, no nesting change (p.7) ──
        if t == "finally_clause":
            c = 0
            for child in node.children:
                if child.type == "block":
                    c += self._visit_children(child, nesting)
            return c

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

        # ── B1 fundamental: binary logical operators (p.7-8) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B1 fundamental: break LABEL / continue LABEL (p.8) ──
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

        # ── B2: lambda → no structural increment, increments nesting (p.9) ──
        if t == "lambda_expression":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: anonymous class → no structural increment, increments nesting ──
        if t == "object_creation_expression":
            for child in node.children:
                if child.type == "class_body":
                    c = 0
                    for member in child.children:
                        if member.type in ("method_declaration",
                                           "constructor_declaration"):
                            body = member.child_by_field_name("body")
                            if body:
                                c += self._visit_children(body, nesting + 1)
                        else:
                            c += self._visit(member, nesting + 1)
                    return c
            return self._visit_children(node, nesting)

        # ── labeled_statement: unwrap, no increment for the label ──
        if t == "labeled_statement":
            c = 0
            for child in node.children:
                if child.type not in ("identifier", ":"):
                    c += self._visit(child, nesting)
            return c

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── switch labels (case/default): no increment ──
        if t in ("switch_label",):
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

        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_statement":
                c += self._handle_if_chain(alt, nesting, is_else_if=True)
            elif alt.type == "block":
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit_children(alt, nesting + 1)

        return c

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting):
        ops = []
        # Iterative traversal to avoid Python recursion on long chains
        self._collect_boolean_ops_iterative(node, ops)

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

    def _collect_boolean_ops_iterative(self, root, ops):
        """Iterative in-order traversal of a binary_expression chain.
        Avoids deep Python recursion on `a && b && c && ... && z`."""
        stack = [(root, False)]
        while stack:
            node, visited_left = stack.pop()
            if node is None or node.type != "binary_expression":
                continue
            op_node = node.child_by_field_name("operator")
            if op_node is None:
                continue
            op_text = self._text(op_node)
            if op_text not in ("&&", "||"):
                continue

            if not visited_left:
                stack.append((node, True))
                left = node.child_by_field_name("left")
                if left and left.type == "binary_expression":
                    lo = left.child_by_field_name("operator")
                    if lo and self._text(lo) in ("&&", "||"):
                        stack.append((left, False))
            else:
                ops.append(op_text)
                right = node.child_by_field_name("right")
                if right and right.type == "binary_expression":
                    ro = right.child_by_field_name("operator")
                    if ro and self._text(ro) in ("&&", "||"):
                        stack.append((right, False))


# ── Public API ──

def calculate_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    calc = CognitiveComplexityCalculator(source)
    return calc.calculate()


def calculate_source(source_code: str):
    calc = CognitiveComplexityCalculator(source_code)
    return calc.calculate()


def calculate_directory(dirpath: str):
    all_results = []
    for root, dirs, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith(".java"):
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
    print("Java Cognitive Complexity Calculator (with hang protection)")
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
