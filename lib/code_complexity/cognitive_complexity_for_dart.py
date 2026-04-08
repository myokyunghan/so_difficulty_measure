"""
Dart Cognitive Complexity Calculator
======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
  - SonarSource. "Cognitive Complexity" v1.7, 29 August 2023.

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Dart)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Dart: if_statement
    - switch                              → Dart: switch_statement (single +1, p.7)
    - for, for-in                         → Dart: for_statement
    - while, do-while                     → Dart: while_statement, do_statement
    - catch                               → Dart: catch_clause (+1, p.7)
    - ternary operator                    → Dart: conditional_expression

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Dart: if_statement as alternative
    - else                                → Dart: block as alternative

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - break LABEL, continue LABEL         → Dart: break_statement/continue_statement with identifier
    - sequences of logical operators      → Dart: logical_and_expression (&&),
                                                    logical_or_expression (||)
    - each method in a recursion cycle    → Not implemented

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else if, else, ternary
    - switch, for, while, do-while
    - catch
    - nested functions: function_expression (closures)

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary       (NOT else if, NOT else)
    - switch, for, while, do-while
    - catch

═══════════════════════════════════════════════════════════════════
Dart-specific notes
═══════════════════════════════════════════════════════════════════

  - Dart methods: method_signature + function_body are siblings in class_body
    (not nested). The calculator pairs them together.
  - Dart logical operators: && → logical_and_expression, || → logical_or_expression
    (separate AST node types like Swift, not binary_expression).
  - function_expression (closures): () { ... } or () => expr.
    No structural increment, increases nesting (p.9).
  - break LABEL / continue LABEL: Dart supports labeled break/continue.
    break_statement with identifier child → +1 fundamental (p.8).
  - try/finally: no increment (p.7).
  - Null-aware operators (??, ?.): ignored (p.6 "Ignore shorthand").

Dependencies: pip install tree-sitter
              tree-sitter-dart built from npm: npm install --ignore-scripts tree-sitter-dart
              then: gcc -shared -fPIC -O2 -I src src/parser.c src/scanner.c -o dart.so
"""
import os
import re
import sys
import json
import ctypes
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("dart")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    so_paths = [
        os.path.join(os.path.dirname(__file__), "build", "dart.so"),
        os.path.join(os.path.dirname(__file__), "dart.so"),
        "/home/claude/build/dart.so",
    ]
    for so_path in so_paths:
        if os.path.exists(so_path):
            try:
                lib = ctypes.cdll.LoadLibrary(so_path)
                func = lib.tree_sitter_dart
                func.restype = ctypes.c_void_p
                _p = Parser(Language(func()))
                try:
                    _p.timeout_micros = 5_000_000
                except (AttributeError, TypeError):
                    pass
                return _p
            except Exception:
                continue
    raise ImportError(
        "Dart parser not found. Build from npm:\n"
        "  npm install --ignore-scripts tree-sitter-dart\n"
        "  gcc -shared -fPIC -O2 -I node_modules/tree-sitter-dart/src "
        "node_modules/tree-sitter-dart/src/parser.c "
        "node_modules/tree-sitter-dart/src/scanner.c -o build/dart.so")


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        try:

            self.tree = self.parser.parse(bytes(source_code, "utf-8"))

            self._parse_failed = False

        except ValueError:

            self.tree = None

            self._parse_failed = True
        self.results = []
        self.details = []

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
        if self._parse_failed or self.tree is None:
            return self.results
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback
        return self.results

    def _walk_top_level(self, node):
        """Find top-level functions and classes.
        Dart top-level: function_signature + function_body as siblings."""
        children = list(node.children)
        i = 0
        while i < len(children):
            child = children[i]
            if child.type == "function_signature":
                # Next sibling should be function_body
                if i + 1 < len(children) and children[i + 1].type == "function_body":
                    self._process_function_pair(child, children[i + 1])
                    i += 2
                    continue
            elif child.type == "class_definition":
                self._walk_class(child)
            elif child.type in ("enum_declaration",):
                pass
            i += 1

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        children = list(body.children)
        i = 0
        while i < len(children):
            child = children[i]
            if child.type == "method_signature":
                # Next sibling should be function_body
                if i + 1 < len(children) and children[i + 1].type == "function_body":
                    sig = child
                    # Extract name from function_signature inside method_signature
                    name_node = None
                    for sub in sig.children:
                        if sub.type == "function_signature":
                            name_node = sub.child_by_field_name("name")
                            break
                        elif sub.type == "getter_signature":
                            name_node = sub.child_by_field_name("name")
                            break
                        elif sub.type == "setter_signature":
                            name_node = sub.child_by_field_name("name")
                            break
                    func_name = self._text(name_node) if name_node else "<anonymous>"
                    self._process_function_body(func_name, sig, children[i + 1])
                    i += 2
                    continue
            elif child.type == "class_definition":
                self._walk_class(child)
            i += 1

    def _process_function_pair(self, sig_node, body_node):
        name_node = sig_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"
        self._process_function_body(func_name, sig_node, body_node)

    def _process_function_body(self, func_name, sig_node, body_node):
        self.details = []
        complexity = 0
        # function_body contains block or => expression
        for child in body_node.children:
            if child.type == "block":
                complexity = self._visit_children(child, 0)
                break
            elif child.type not in ("=>", ";"):
                complexity = self._visit(child, 0)
        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": sig_node.start_point[0] + 1,
            "end_line": body_node.end_point[0] + 1,
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

        # ── B1 structural: for ──
        if t == "for_statement":
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
        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── switch labels: no increment ──
        if t in ("switch_label",):
            return 0

        # ── try: no increment (p.7) ──
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
            # catch_clause sibling is a block
            return c

        # ── finally: no increment (p.7) ──
        if t == "finally_clause":
            for child in node.children:
                if child.type == "block":
                    return self._visit_children(child, nesting)
            return 0

        # ── B1 structural: ternary ──
        if t == "conditional_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            # Visit children for nested expressions
            for child in node.children:
                if child.type in ("?", ":"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B1 fundamental: logical operators ──
        if t == "logical_and_expression":
            return self._handle_boolean_dart(node, nesting)
        if t == "logical_or_expression":
            return self._handle_boolean_dart(node, nesting)

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

        # ── B2: function_expression (closure) → nesting (p.9) ──
        if t == "function_expression":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── block inside try/catch: visit with catch nesting ──
        if t == "block":
            # Check if previous sibling was catch_clause
            if node.parent and node.parent.type == "try_statement":
                prev = None
                for child in node.parent.children:
                    if child == node:
                        if prev and prev.type == "catch_clause":
                            return self._visit_children(node, nesting + 1)
                        break
                    prev = child
            return self._visit_children(node, nesting)

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

    # ── Dart logical operator sequences (p.7-8) ──

    def _handle_boolean_dart(self, node, nesting):
        ops = []
        self._collect_dart_ops(node, ops)
        if not ops:
            return self._visit_children(node, nesting)
        c = 0
        prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                desc = (f"logical sequence '{op}'" if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_dart_ops(self, node, ops):
        if node.type == "logical_and_expression":
            for child in node.children:
                if child.type in ("logical_and_expression", "logical_or_expression"):
                    self._collect_dart_ops(child, ops)
                elif child.type == "&&":
                    ops.append("&&")
        elif node.type == "logical_or_expression":
            for child in node.children:
                if child.type in ("logical_and_expression", "logical_or_expression"):
                    self._collect_dart_ops(child, ops)
                elif child.type == "||":
                    ops.append("||")


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
            if fname.endswith(".dart"):
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
    print("Dart Cognitive Complexity Calculator")
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
            print(json.dumps([{"file": r.get("file",""), "function": r["function"],
                               "complexity": r["complexity"], "start_line": r["start_line"],
                               "end_line": r["end_line"]} for r in results], indent=2))
        else:
            print_results(results, verbose)
