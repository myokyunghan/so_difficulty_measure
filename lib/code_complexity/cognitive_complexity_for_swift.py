"""
Swift Cognitive Complexity Calculator
=======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
  - SonarSource. "Cognitive Complexity" v1.7, 29 August 2023.

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Swift)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Swift: if_statement
    - switch                              → Swift: switch_statement (single +1, p.7)
    - for-in                              → Swift: for_statement
    - while                               → Swift: while_statement
    - repeat-while (do-while equiv)       → Swift: repeat_while_statement
    - do-catch (try-catch equiv)          → Swift: catch_block (+1 per catch, p.7)
    - ternary operator                    → Swift: ternary_expression
    - guard                               → Swift: guard_statement (like if, structural)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Swift: if_statement as alternative of if_statement
    - else                                → Swift: braced body as alternative of if_statement

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - sequences of logical operators      → Swift: conjunction_expression (&&),
                                                    disjunction_expression (||)
    - each method in a recursion cycle    → Not implemented

  Not applicable in Swift:
    - goto, labeled break/continue        → Swift has no goto
    - #if preprocessor                    → Swift #if exists but not in tree-sitter-swift AST

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else if, else, guard, ternary
    - switch, for, while, repeat-while
    - catch
    - nested functions: lambda_literal (closure), nested function_declaration

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, guard, ternary      (NOT else if, NOT else)
    - switch, for, while, repeat-while
    - catch

═══════════════════════════════════════════════════════════════════
Swift-specific notes
═══════════════════════════════════════════════════════════════════

  - do { } catch { }: Swift's try-catch equivalent. do block = no increment
    (like try, p.7). Each catch_block = +1 structural.
  - guard: treated like if (structural increment + nesting penalty).
    The else clause of guard is mandatory but doesn't get additional +1.
  - Swift logical operators: && → conjunction_expression, || → disjunction_expression
    (separate AST node types, not binary_expression)
  - Closures (lambda_literal): no structural increment, increases nesting (p.9)
  - Nested functions: function_declaration inside another function body,
    no structural increment, increases nesting (p.9)

Dependencies: pip install tree-sitter tree-sitter-swift
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    """Prefer individual tree_sitter_swift package because
    tree_sitter_language_pack may return a wrong/generic parser for
    swift on some installations."""
    try:
        import tree_sitter_swift as _mod
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
        _p = get_parser("swift")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    raise ImportError("Install: pip install tree-sitter-swift")
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
        for child in node.children:
            if child.type == "function_declaration":
                self._process_function(child)
            elif child.type in ("class_declaration", "struct_declaration",
                                "enum_declaration", "protocol_declaration",
                                "extension_declaration"):
                self._walk_class(child)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type == "function_declaration":
                self._process_function(child)
            elif child.type in ("class_declaration", "struct_declaration",
                                "enum_declaration", "extension_declaration"):
                self._walk_class(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"
        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
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

        # ── B1 structural: guard (like if) ──
        if t == "guard_statement":
            inc = 1 + nesting
            self._add_detail(node, "guard", 1, nesting)
            c = inc
            # Visit condition for logical operators
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            # Visit else body (mandatory in guard)
            for child in node.children:
                if child.type in ("statements", "{", "}", "guard", "else"):
                    continue
                if child == cond:
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: for ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            # Visit body (statements between { })
            for child in node.children:
                if child.type == "statements":
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while_statement":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            for child in node.children:
                if child.type == "statements":
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B1 structural: repeat-while (do-while equivalent) ──
        if t == "repeat_while_statement":
            inc = 1 + nesting
            self._add_detail(node, "repeat-while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            for child in node.children:
                if child.type == "statements":
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B1 structural: switch (single +1, p.7) ──
        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "switch_entry":
                    # No additional increment for case/default
                    for sub in child.children:
                        if sub.type == "statements":
                            c += self._visit_children(sub, nesting + 1)
            return c

        # ── do-catch: do block = no increment (like try, p.7) ──
        if t == "do_statement":
            c = 0
            for child in node.children:
                if child.type == "catch_block":
                    c += self._handle_catch(child, nesting)
                elif child.type == "statements":
                    c += self._visit_children(child, nesting)
                elif child.type not in ("do", "{", "}"):
                    c += self._visit(child, nesting)
            return c

        # ── B1 structural: ternary ──
        if t == "ternary_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            if_true = node.child_by_field_name("if_true")
            if if_true:
                c += self._visit(if_true, nesting + 1)
            if_false = node.child_by_field_name("if_false")
            if if_false:
                c += self._visit(if_false, nesting + 1)
            return c

        # ── B1 fundamental: logical operators ──
        if t in ("conjunction_expression", "disjunction_expression"):
            return self._handle_boolean(node, nesting)

        # ── B2: lambda_literal (closure) → nesting (p.9) ──
        if t == "lambda_literal":
            c = 0
            for child in node.children:
                if child.type == "statements":
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B2: nested function_declaration → nesting (p.9) ──
        if t == "function_declaration":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

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

        # Walk children: before 'else' = consequence, after 'else' = alternative
        children = list(if_node.children)
        else_idx = None
        for i, child in enumerate(children):
            if child.type == "else":
                else_idx = i
                break

        # Consequence: statements before else
        for child in children[:else_idx] if else_idx else children:
            if child.type == "statements":
                c += self._visit_children(child, nesting + 1)

        # Alternative: after else keyword
        if else_idx is not None:
            after_else = children[else_idx + 1:]
            for child in after_else:
                if child.type == "if_statement":
                    c += self._handle_if_chain(child, nesting, is_else_if=True)
                    break
                elif child.type == "statements":
                    c += 1
                    self._add_detail(child, "else", 1, 0)
                    c += self._visit_children(child, nesting + 1)
                    break
            else:
                # Empty else block (no statements node): just +1 for else
                has_braces = any(ch.type == "{" for ch in after_else)
                if has_braces:
                    c += 1
                    # Find a node for line number
                    for ch in after_else:
                        if ch.type == "{":
                            self._add_detail(ch, "else", 1, 0)
                            break

        return c

    # ── catch handler ──

    def _handle_catch(self, catch_node, nesting):
        inc = 1 + nesting
        self._add_detail(catch_node, "catch", 1, nesting)
        c = inc
        for child in catch_node.children:
            if child.type == "statements":
                c += self._visit_children(child, nesting + 1)
        return c

    # ── Logical operator sequences (p.7-8) ──

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
                desc = (f"logical sequence '{op}'" if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type == "conjunction_expression":
            lhs = node.child_by_field_name("lhs")
            rhs = node.child_by_field_name("rhs")
            if lhs and lhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_boolean_ops(lhs, ops)
            ops.append("&&")
            if rhs and rhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_boolean_ops(rhs, ops)
        elif node.type == "disjunction_expression":
            lhs = node.child_by_field_name("lhs")
            rhs = node.child_by_field_name("rhs")
            if lhs and lhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_boolean_ops(lhs, ops)
            ops.append("||")
            if rhs and rhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_boolean_ops(rhs, ops)


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
            if fname.endswith(".swift"):
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
    print("Swift Cognitive Complexity Calculator")
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
