"""
Haskell Cognitive Complexity Calculator
=========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

NOTE: This module's docstring uses raw strings to allow Haskell lambda
syntax (backslash followed by patterns) without Python escape conflicts.
"""
__doc__ = r"""
═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Haskell)
═══════════════════════════════════════════════════════════════════

Haskell is a pure functional language with no imperative control flow.
The traditional Cognitive Complexity constructs are mapped to Haskell's
expression-based equivalents:

B1. Increments
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if (if-then-else expression)        → Haskell: conditional
    - case-of                             → Haskell: case (single +1, p.7)
    - guards                              → Haskell: guards on a match
    - list comprehension generator        → Haskell: generator inside
                                            list_comprehension. A generator
                                            iterates over a list (analogous
                                            to a for-each loop).

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - additional guards                   → Each guard after the first.
                                            Multi-guard matches are like
                                            if/elif chains.

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - sequences of binary logical ops     → Haskell: infix expressions with
                                            && / || operators
    - each method in a recursion cycle    → Not implemented

  Not applicable in Haskell:
    - goto                                → Haskell has no goto
    - break LABEL, continue LABEL         → Haskell has no labeled break
    - traditional for/while/do loops      → Haskell uses recursion; no
                                            syntactic construct to detect.
    - try/catch                           → Exception handling is via
                                            library functions (catch, handle,
                                            try, bracket). No syntactic
                                            construct exists; not detected.
    - else (as a separate increment)      → Haskell's if-then-else is an
                                            expression where else is always
                                            present. The conditional itself
                                            counts as +1; no separate else.
    - switch fall-through                 → Haskell case has no fall-through.
    - ternary                             → Haskell if-then-else IS the
                                            ternary; counted once.

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if (conditional)
    - case
    - guards
    - generators (list comprehension)
    - lambda (\x -> ...)                  → nested function (p.9)
    - let-in local binds                  → each local binding is a
                                            nested function (p.9)
    - where local binds                   → each where binding is a
                                            nested function (p.9)

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if (conditional)
    - case
    - guards (the FIRST guard receives nesting; subsequent ones do not)
    - generator (the FIRST generator receives nesting; subsequent ones
                 inside the same comprehension do not, similar to else if)

═══════════════════════════════════════════════════════════════════
Haskell-specific notes
═══════════════════════════════════════════════════════════════════

  - Haskell functions can have multiple equations via pattern matching:
        factorial 0 = 1
        factorial n = n * factorial (n - 1)
    These appear as separate `function` nodes with the same `name`. We
    group them together as a single function for reporting, summing the
    complexity of all equations. The act of pattern matching itself does
    NOT add complexity (it's similar to function dispatch, not a control
    structure inside one function).

  - Guards within a match (`f x | g1 = e1 | g2 = e2 | otherwise = e3`)
    are multi-way conditionals. The first guard is +1 structural (with
    nesting penalty); each additional guard is +1 hybrid (no nesting
    penalty). The `otherwise` keyword is just a name for `True` and is
    treated as the last guard.

  - List comprehensions: `[e | x <- xs, y <- ys, p x y]`
    Each `<-` generator is treated as a (for-each) loop. The first
    generator gets +1 structural with nesting; subsequent generators
    are nested loops too. Filter qualifiers (boolean expressions) are
    treated as ifs inside the comprehension scope.

  - case-of: equivalent to switch. Single +1 for the entire case
    expression (per p.7), regardless of how many alternatives. Each
    alternative may itself have guards, which DO count.

  - lambda: treated as a nested function — no structural increment,
    but increases nesting (p.9).

  - let-in / where: local binds are nested functions. Their bodies are
    visited at +1 nesting.

  - do-notation: `do { x <- e1; e2 }` is sugar for monadic bind. The do
    block itself does NOT add complexity, but the statements inside are
    visited normally so any if/case/guards within count.

  - Haskell has no traditional loops. Recursion is the standard
    looping mechanism but cannot be reliably auto-detected as a loop
    construct from the AST alone.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  Top-level expressions and bindings are processed as part of the file's
  declarations. Every Haskell file is a module of declarations.

Dependencies: pip install tree-sitter tree-sitter-haskell
"""
import os
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("haskell")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    try:
        import tree_sitter_haskell as _mod
        _p = Parser(Language(_mod.language()))
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-haskell")


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
        if self._parse_failed or self.tree is None:
            return self.results
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        # Find the declarations node
        declarations = None
        for child in node.children:
            if child.type == "declarations":
                declarations = child
                break
        if declarations is None:
            return

        # Group function equations by name (pattern matching produces
        # multiple `function` nodes with the same `name`).
        grouped = []
        seen_names = {}
        for child in declarations.children:
            t = child.type
            if t == "function":
                name_node = child.child_by_field_name("name")
                fname = self._text(name_node) if name_node else "<anonymous>"
                if fname in seen_names:
                    grouped[seen_names[fname]][1].append(child)
                else:
                    seen_names[fname] = len(grouped)
                    grouped.append((fname, [child]))
            elif t == "bind":
                name_node = child.child_by_field_name("name")
                fname = self._text(name_node) if name_node else "<anonymous>"
                grouped.append((fname, [child]))
            elif t in ("class", "instance"):
                self._walk_class_or_instance(child)
            # signatures, data_type, type_synomym, etc. add no complexity

        for fname, nodes in grouped:
            self._process_function(fname, nodes)

    def _walk_class_or_instance(self, node):
        # class_declarations / instance_declarations
        decl_field = node.child_by_field_name("declarations")
        if decl_field is None:
            return
        # Group functions by name within the class/instance
        grouped = []
        seen_names = {}
        class_name = ""
        name_node = node.child_by_field_name("name")
        if name_node:
            class_name = self._text(name_node)

        for child in decl_field.children:
            if child.type == "function":
                name_node = child.child_by_field_name("name")
                # Function name might be inside an `infix` or `prefix_id`
                fname = self._extract_function_name(child)
                if fname in seen_names:
                    grouped[seen_names[fname]][1].append(child)
                else:
                    seen_names[fname] = len(grouped)
                    grouped.append((fname, [child]))
            elif child.type == "bind":
                name_node = child.child_by_field_name("name")
                fname = self._text(name_node) if name_node else "<anonymous>"
                grouped.append((fname, [child]))

        for fname, nodes in grouped:
            display = f"{class_name}.{fname}" if class_name else fname
            self._process_function(display, nodes)

    def _extract_function_name(self, func_node):
        """Extract function name, handling infix definitions like `x == y`."""
        name_node = func_node.child_by_field_name("name")
        if name_node:
            return self._text(name_node)
        # Check for infix-style definition: first child is `infix` or `prefix_id`
        for child in func_node.children:
            if child.type == "infix":
                # The operator is the function name
                op = child.child_by_field_name("operator")
                if op:
                    return self._text(op)
            elif child.type == "prefix_id":
                return self._text(child)
        return "<anonymous>"

    def _process_function(self, name, nodes):
        """Process one function (which may consist of multiple equations
        from pattern matching). Sum complexity across all equations."""
        self.details = []
        complexity = 0
        for node in nodes:
            complexity += self._process_one_equation(node)

        first = nodes[0]
        last = nodes[-1]
        self.results.append({
            "function": name,
            "complexity": complexity,
            "start_line": first.start_point[0] + 1,
            "end_line": last.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_one_equation(self, node):
        """Process a single function equation (function or bind node).
        Guards are not in spec — visit each match plainly."""
        c = 0
        for child in node.children:
            t = child.type
            if t == "match":
                c += self._visit(child, 0)
            elif t == "local_binds":
                c += self._visit_local_binds(child, 0)
        return c

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    def _visit_local_binds(self, node, nesting):
        """Visit a `local_binds` node (let or where bindings).
        Each bind is a nested function (B2: nesting+1)."""
        c = 0
        for child in node.children:
            if child.type in ("bind", "function"):
                # Visit the bind body at +1 nesting
                for sub in child.children:
                    if sub.type == "match":
                        c += self._visit(sub, nesting + 1)
                    elif sub.type == "local_binds":
                        c += self._visit_local_binds(sub, nesting + 1)
            elif child.type == "signature":
                pass  # type signatures, no complexity
        return c

    # ── Node visitors ──

    def _visit_children(self, node, nesting):
        total = 0
        for child in node.children:
            total += self._visit(child, nesting)
        return total

    def _visit(self, node, nesting):
        t = node.type

        # ── match: contains either an expression body or guards ──
        if t == "match":
            return self._handle_match(node, nesting)

        # ── B1 structural: if (conditional) ──
        if t == "conditional":
            inc = 1 + nesting
            self._add_detail(node, "if", 1, nesting)
            c = inc
            # Visit if/then/else parts
            if_part = node.child_by_field_name("if")
            then_part = node.child_by_field_name("then")
            else_part = node.child_by_field_name("else")
            if if_part:
                c += self._visit(if_part, nesting)  # condition
            if then_part:
                c += self._visit(then_part, nesting + 1)
            if else_part:
                c += self._visit(else_part, nesting + 1)
            return c

        # ── B1 structural: case (single +1, p.7) ──
        if t == "case":
            inc = 1 + nesting
            self._add_detail(node, "case", 1, nesting)
            c = inc
            # Visit the scrutinee expression and alternatives
            for child in node.children:
                if child.type in ("case", "of"):
                    continue
                if child.type == "alternatives":
                    for sub in child.children:
                        if sub.type == "alternative":
                            c += self._visit_alternative(sub, nesting + 1)
                else:
                    # The scrutinee expression
                    c += self._visit(child, nesting)
            return c

        # list_comprehension: removed (generator/filter not in spec).
        # Just recurse — any if/case inside will still be counted normally.
        if t == "list_comprehension":
            return self._visit_children(node, nesting)

        # ── B1 fundamental: logical operators ──
        if t == "infix":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: lambda → nesting (p.9) ──
        if t == "lambda":
            c = 0
            for child in node.children:
                t2 = child.type
                if t2 in ("\\", "->", "patterns"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B2: let-in → local binds are nested functions ──
        if t == "let_in":
            c = 0
            binds = node.child_by_field_name("binds")
            if binds:
                c += self._visit_local_binds(binds, nesting)
            expr = node.child_by_field_name("expression")
            if expr:
                c += self._visit(expr, nesting)
            return c

        # ── do block: visit statements at same nesting ──
        if t == "do":
            c = 0
            for child in node.children:
                if child.type == "do":
                    continue
                c += self._visit(child, nesting)
            return c

        # ── alternative (case branch) is handled via _visit_alternative ──
        if t == "alternative":
            return self._visit_alternative(node, nesting)

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── match handling (function body or where bind body) ──

    def _handle_match(self, node, nesting):
        """A match is the body of a function equation.
        Guards are removed (not in spec). The body expression is visited
        at the given nesting level."""
        c = 0
        for child in node.children:
            t = child.type
            if t in ("guards", "|", "=", "where"):
                continue
            if t == "local_binds":
                c += self._visit_local_binds(child, nesting)
                continue
            fn = self._field_name(node, child)
            if fn == "expression":
                c += self._visit(child, nesting)
        return c

    def _handle_guards(self, node, nesting):
        """Removed: guards are not in White Paper Appendix B."""
        return 0

    def _visit_alternative(self, alt_node, nesting):
        """A case alternative: pattern -> expr.
        Guards (`| cond1 -> expr1 | cond2 -> expr2`) are removed
        (not in White Paper Appendix B). All match children are visited
        as plain expressions at the given nesting."""
        c = 0
        for child in alt_node.children:
            t = child.type
            fn = self._field_name(alt_node, child)
            if fn == "pattern":
                continue
            if t in ("->", "where"):
                continue
            if t == "local_binds":
                c += self._visit_local_binds(child, nesting)
                continue
            c += self._visit(child, nesting)
        return c

    def _handle_match_as_nth_guard(self, match_node, nesting, guard_index):
        """Process a match that's part of a multi-guard alternative.
        guard_index 0 = first guard (structural +1+nesting),
        guard_index >0 = additional guard (hybrid +1)."""
        c = 0
        has_guards = False
        for child in match_node.children:
            if child.type == "guards":
                has_guards = True
                # Override the guard processing for this match
                guard_count = 0
                for guard_child in child.children:
                    if guard_child.type == "boolean":
                        guard_count += 1
                        if guard_count == 1 and guard_index == 0:
                            inc = 1 + nesting
                            self._add_detail(guard_child, "guard", 1, nesting)
                            c += inc
                        else:
                            self._add_detail(guard_child,
                                             "guard (additional)", 1, 0)
                            c += 1
                        c += self._visit_children(guard_child, nesting)

        body_nesting = nesting + 1 if has_guards else nesting

        for child in match_node.children:
            t = child.type
            if t in ("guards", "|", "=", "->", "where"):
                continue
            if t == "local_binds":
                c += self._visit_local_binds(child, body_nesting)
                continue
            fn = self._field_name(match_node, child)
            if fn == "expression":
                c += self._visit(child, body_nesting)

        return c

    # ── List comprehension ──

    def _handle_list_comprehension(self, node, nesting):
        """A list comprehension: [expr | qualifier, qualifier, ...]
        Each `<-` generator is a for-each loop. The first generator gets
        structural +1 with nesting; subsequent ones get +1 hybrid (no
        nesting penalty), similar to else-if. Filter qualifiers (boolean
        expressions) are treated as ifs."""
        c = 0
        # Find the qualifiers and the result expression
        qualifiers = None
        result_expr = None
        for child in node.children:
            if child.type == "qualifiers":
                qualifiers = child
            elif child.type not in ("[", "]", "|"):
                fn = self._field_name(node, child)
                if fn == "expression":
                    result_expr = child

        if qualifiers is None:
            return self._visit_children(node, nesting)

        # Walk qualifiers
        gen_count = 0
        comp_nesting = nesting
        for child in qualifiers.children:
            if child.type == "generator":
                gen_count += 1
                if gen_count == 1:
                    inc = 1 + comp_nesting
                    self._add_detail(child, "generator", 1, comp_nesting)
                    c += inc
                else:
                    self._add_detail(child, "generator (additional)", 1, 0)
                    c += 1
                # Visit the generator's source expression
                expr = child.child_by_field_name("expression")
                if expr:
                    c += self._visit(expr, comp_nesting)
                # Each generator increases nesting for subsequent qualifiers
                comp_nesting += 1
            elif child.type == "boolean":
                # Filter: like an if inside the comprehension
                inc = 1 + comp_nesting
                self._add_detail(child, "filter", 1, comp_nesting)
                c += inc
                # Visit the filter expression for logical operators
                c += self._visit_children(child, comp_nesting)

        # Visit the result expression at the deepest comp nesting
        if result_expr:
            c += self._visit(result_expr, comp_nesting)

        return c

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

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
        if node.type != "infix":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        op_text = self._text(op_node)
        if op_text not in ("&&", "||"):
            return

        left = node.child_by_field_name("left_operand")
        right = node.child_by_field_name("right_operand")

        if left and left.type == "infix":
            lo = left.child_by_field_name("operator")
            if lo and self._text(lo) in ("&&", "||"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "infix":
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
            if fname.endswith((".hs", ".lhs")):
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
    print("Haskell Cognitive Complexity Calculator")
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
