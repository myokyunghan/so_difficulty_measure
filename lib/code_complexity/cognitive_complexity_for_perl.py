"""
Perl Cognitive Complexity Calculator
======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Perl)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Perl: conditional_statement
                                            (with `if` keyword)
    - unless                              → Perl: conditional_statement
                                            (with `unless` keyword) — Perl
                                            negated-if; same as if
    - C-style for                         → Perl: cstyle_for_statement
    - foreach / for-in                    → Perl: for_statement (with
                                            `foreach`/`for` + variable + list)
    - while                               → Perl: loop_statement
                                            (with `while` keyword)
    - until                               → Perl: loop_statement
                                            (with `until` keyword) — negated
                                            while; same as while
    - do-while / do-until                 → Perl: postfix_loop_expression
                                            with do_expression
    - postfix if/unless                   → Perl: postfix_conditional_expression
    - postfix while/until                 → Perl: postfix_loop_expression
                                            (without do_expression)
    - postfix for                         → Perl: postfix_for_expression
    - ternary                             → Perl: conditional_expression

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - elsif                               → Perl: conditional_statement
                                            with field 'elsif'
    - else                                → Perl: conditional_statement
                                            with field 'else'

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - last LABEL / next LABEL / redo LABEL → Perl: loopex_expression with
                                            an explicit label child
    - goto                                → Perl: goto_expression
    - sequences of binary logical ops     → Perl: binary_expression with
                                            && / || / // operators
                                            AND lowprec_logical_expression
                                            with and / or operators
    - each method in a recursion cycle    → Not implemented

  Not applicable in Perl as syntactic constructs:
    - switch                              → Perl 5 has no switch (the
                                            given/when feature is
                                            experimental and rarely used).
                                            Idiomatic Perl uses if/elsif
                                            chains or hash dispatch.
    - try/catch                           → Perl uses `eval { ... }` plus
                                            `if ($@) { ... }` for error
                                            handling. eval is NOT detected
                                            as a try-catch handler; the
                                            following `if ($@)` IS counted
                                            as a regular if. The newer
                                            `Try::Tiny` and `feature 'try'`
                                            modules are not specially handled.

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if/unless, elsif, else
    - all loops (for, foreach, while, until, do-while)
    - all postfix forms (postfix if/unless/while/until/for)
    - ternary
    - nested subroutines (subroutine_declaration_statement,
                          anonymous_subroutine_expression)

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if/unless (NOT elsif, NOT else)
    - all loops, postfix loops, postfix if/unless/for, ternary

═══════════════════════════════════════════════════════════════════
Perl-specific notes
═══════════════════════════════════════════════════════════════════

  - Perl has TWO families of logical operators:
      • High precedence:  `&&`, `||`, `//` (defined-or)
      • Low precedence:   `and`, `or`, `xor`
    These differ only in operator precedence; both are short-circuit
    (except xor) and both contribute to logical operator sequences.
    The parser produces:
      - `binary_expression` for &&/||//
      - `lowprec_logical_expression` for and/or/xor
    We treat `xor` as NOT a control-flow operator (no short-circuit
    semantics).

  - Postfix forms are uniquely Perl-ish:
        return 1 if $x;            # postfix_conditional_expression
        return 1 unless $x;        # postfix_conditional_expression
        print $i++ while $i < 10;  # postfix_loop_expression
        print $_ for @list;        # postfix_for_expression
    Each is +1 structural with nesting, equivalent to its prefix form.

  - `unless` is `if not`. `until` is `while not`. They have identical
    cognitive complexity to their positive counterparts.

  - Perl's `do { ... } while/until cond` is a do-while loop. The parser
    represents it as a `postfix_loop_expression` whose first child is a
    `do_expression`. We detect this pattern.

  - `eval { ... }` is Perl's exception-trapping construct. It captures
    errors into `$@`. Per the spec's treatment of try (p.7), `eval` itself
    adds NO complexity — only the body is visited. The follow-up
    `if ($@) { ... }` IS counted as a normal if.

  - `last`, `next`, `redo` are Perl's break/continue/restart loop
    statements. With an explicit label (`last LOOP`), they are
    fundamental +1. Without a label, they're plain break/continue
    equivalents and don't add complexity.

  - `goto LABEL` and `goto &sub` are both `goto_expression`. Both count
    as +1 fundamental. Note: `goto &sub` is more like a tail call than
    a goto, but we treat it conservatively as goto.

  - Subroutines:
      • `sub f { ... }` — subroutine_declaration_statement
      • `sub { ... }` — anonymous_subroutine_expression
      • `package Foo;` declares a package; subsequent subs belong to it.
        The function name in the report is prefixed with the package.
      • Method invocation is via `->`, not via syntax — methods look
        like regular subs.

  - Perl has experimental `given/when` (basically a switch). Not
    detected by name in this calculator; if used, the `when` clauses
    would parse as separate statements and each `when (cond)` would
    likely look like an if from the spec's perspective.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  Perl scripts often have top-level code outside any sub. If no
  `subroutine_declaration_statement` is present, the entire file is
  treated as one `<main>` pseudo-function.

Dependencies: tree-sitter, plus tree-sitter-perl built from npm
"""
import os
import sys
import json
import ctypes
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("perl")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    so_paths = [
        os.path.join(os.path.dirname(__file__), "build", "perl.so"),
        os.path.join(os.path.dirname(__file__), "perl.so"),
        "/home/claude/build/perl.so",
    ]
    for so_path in so_paths:
        if os.path.exists(so_path):
            try:
                lib = ctypes.cdll.LoadLibrary(so_path)
                func = lib.tree_sitter_perl
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
        "Perl parser not found. Build from npm:\n"
        "  npm install --ignore-scripts tree-sitter-perl\n"
        "  gcc -shared -fPIC -O2 -I node_modules/tree-sitter-perl/src \\\n"
        "      node_modules/tree-sitter-perl/src/parser.c \\\n"
        "      node_modules/tree-sitter-perl/src/scanner.c \\\n"
        "      -o build/perl.so")


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

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    def _has_child_of_type(self, node, type_name):
        for c in node.children:
            if c.type == type_name:
                return True
        return False

    def _first_keyword(self, node):
        """Get the first keyword token of a node (e.g., 'if', 'unless',
        'while', 'until')."""
        for c in node.children:
            if c.type in ("if", "unless", "while", "until", "for",
                          "foreach", "elsif", "else"):
                return c.type
        return None

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        if self._parse_failed or self.tree is None:
            return self.results
        current_package = ""
        any_sub = False
        anon_subs_to_process = []  # collected anon subs from top-level

        for child in self.tree.root_node.children:
            t = child.type
            if t == "package_statement":
                # Extract package name
                name_node = child.child_by_field_name("name")
                current_package = self._text(name_node) if name_node else ""
            elif t == "subroutine_declaration_statement":
                any_sub = True
                self._process_function(child, current_package)
            else:
                # Look for anonymous subs assigned at top level:
                #   my $f = sub { ... };
                anon_info = self._find_anon_sub_assignments(child)
                anon_subs_to_process.extend(anon_info)

        for anon_node, anon_name in anon_subs_to_process:
            any_sub = True
            self._process_anon_sub(anon_node, anon_name)

        if not any_sub:
            # Bare code fallback: treat entire file as one function
            self.details = []
            complexity = 0
            for child in self.tree.root_node.children:
                complexity += self._visit(child, 0)
            if complexity > 0 or self.details:
                self.results.append({
                    "function": "<main>",
                    "complexity": complexity,
                    "start_line": 1,
                    "end_line": self.tree.root_node.end_point[0] + 1,
                    "details": list(self.details),
                })

        return self.results

    def _find_anon_sub_assignments(self, node):
        """Find `my $f = sub { ... }` or `$f = sub { ... }` patterns
        and return list of (anon_sub_node, name) tuples."""
        found = []

        def walk(n, in_func=False):
            if in_func:
                return  # Don't descend into function bodies
            t = n.type
            if t in ("subroutine_declaration_statement",
                     "anonymous_subroutine_expression"):
                if t == "anonymous_subroutine_expression":
                    return  # handled by parent assignment
                in_func = True
            if t == "assignment_expression":
                left = n.child_by_field_name("left")
                right = n.child_by_field_name("right")
                if right and right.type == "anonymous_subroutine_expression":
                    name = "<anonymous>"
                    if left:
                        # Try to extract a name from the LHS
                        name_text = self._text(left).strip()
                        if name_text:
                            name = name_text
                    found.append((right, name))
                    return
            for c in n.children:
                walk(c, in_func)

        walk(node)
        return found

    def _process_anon_sub(self, anon_node, name):
        """Process an anonymous_subroutine_expression as a top-level function."""
        self.details = []
        body = anon_node.child_by_field_name("body")
        complexity = 0
        if body:
            complexity = self._visit_children(body, 0)

        self.results.append({
            "function": name,
            "complexity": complexity,
            "start_line": anon_node.start_point[0] + 1,
            "end_line": anon_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_function(self, func_node, package=""):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"
        if package:
            func_name = f"{package}::{func_name}"

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

        # ── B1 structural: if / unless ──
        if t == "conditional_statement":
            return self._handle_if_chain(node, nesting)

        # ── B1 structural: loops ──
        if t == "cstyle_for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            block = node.child_by_field_name("block")
            if block:
                c += self._visit_children(block, nesting + 1)
            # Visit init/condition/iterator for nested logical ops, etc.
            for fname in ("initialiser", "condition", "iterator"):
                f = node.child_by_field_name(fname)
                if f:
                    c += self._visit(f, nesting)
            return c

        if t == "for_statement":
            # foreach my $x (@list) { ... }
            inc = 1 + nesting
            self._add_detail(node, "foreach", 1, nesting)
            c = inc
            block = node.child_by_field_name("block")
            if block:
                c += self._visit_children(block, nesting + 1)
            list_expr = node.child_by_field_name("list")
            if list_expr:
                c += self._visit(list_expr, nesting)
            return c

        if t == "loop_statement":
            # while / until
            kw = "while" if self._has_child_of_type(node, "while") else "until"
            inc = 1 + nesting
            self._add_detail(node, kw, 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            block = node.child_by_field_name("block")
            if block:
                c += self._visit_children(block, nesting + 1)
            return c

        # postfix_conditional_expression: removed (postfix forms not in
        # White Paper Appendix B). Just recurse without counting.
        if t == "postfix_conditional_expression":
            return self._visit_children(node, nesting)

        # postfix_loop_expression: do { } while/until is do-while (kept),
        # but plain `expr while cond` postfix is removed.
        if t == "postfix_loop_expression":
            has_do = False
            for child in node.children:
                if child.type == "do_expression":
                    has_do = True
                    break
            if not has_do:
                # Plain postfix while/until — removed
                return self._visit_children(node, nesting)
            # do-while form — kept (semantically equivalent to do-while)
            kw = "while" if self._has_child_of_type(node, "while") else "until"
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            for child in node.children:
                if child.type in ("while", "until"):
                    continue
                if child == cond:
                    continue
                if child.type == "do_expression":
                    for sub in child.children:
                        if sub.type == "block":
                            c += self._visit_children(sub, nesting + 1)
                else:
                    c += self._visit(child, nesting + 1)
            return c

        # postfix_for_expression: removed (postfix form).
        if t == "postfix_for_expression":
            return self._visit_children(node, nesting)

        # ── B1 structural: ternary ──
        if t == "conditional_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            cons = node.child_by_field_name("consequent")
            if cons:
                c += self._visit(cons, nesting + 1)
            alt = node.child_by_field_name("alternative")
            if alt:
                c += self._visit(alt, nesting + 1)
            return c

        # ── eval block: NO increment, visit body (like try, p.7) ──
        if t == "eval_expression":
            c = 0
            for child in node.children:
                if child.type == "eval":
                    continue
                if child.type == "block":
                    c += self._visit_children(child, nesting)
                else:
                    c += self._visit(child, nesting)
            return c

        # ── B1 fundamental: goto ──
        if t == "goto_expression":
            self._add_detail(node, "goto", 1, 0)
            return 1

        # ── B1 fundamental: last/next/redo with label ──
        if t == "loopex_expression":
            # loopex_expression has a `loopex` field with last/next/redo,
            # and optionally a `label` child for labeled forms.
            has_label = False
            kw = ""
            for child in node.children:
                fn = self._field_name(node, child)
                if fn == "loopex":
                    kw = child.type
                if child.type == "label":
                    has_label = True
            if has_label:
                self._add_detail(node, f"{kw} LABEL", 1, 0)
                return 1
            return 0

        # ── B1 fundamental: high-precedence logical ops (&&, ||, //) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and op.type in ("&&", "||", "//"):
                return self._handle_boolean(node, nesting,
                                              types=("binary_expression",),
                                              valid_ops=("&&", "||", "//"))
            return self._visit_children(node, nesting)

        # ── B1 fundamental: low-precedence logical ops (and, or) ──
        if t == "lowprec_logical_expression":
            op = node.child_by_field_name("operator")
            if op and op.type in ("and", "or"):
                return self._handle_boolean(node, nesting,
                                              types=("lowprec_logical_expression",),
                                              valid_ops=("and", "or"))
            return self._visit_children(node, nesting)

        # ── B2: nested subroutine definitions → nesting (p.9) ──
        if t == "subroutine_declaration_statement":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        if t == "anonymous_subroutine_expression":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / elsif / else chain ──

    def _handle_if_chain(self, if_node, nesting):
        """Perl conditional_statement structure:
            conditional_statement
              if/unless [keyword token]
              ( condition )
              block ['block' field]
              elsif [child node, recursively contains more elsif/else]
              else? [child node]
        elsif chains are NESTED: each elsif may contain another elsif or
        an else as its own child."""
        c = 0
        kw = "if" if self._has_child_of_type(if_node, "if") else "unless"
        inc = 1 + nesting
        self._add_detail(if_node, kw, 1, nesting)
        c += inc

        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        block = if_node.child_by_field_name("block")
        if block:
            c += self._visit_children(block, nesting + 1)

        # Process elsif/else chain (potentially nested inside each elsif)
        c += self._handle_else_chain(if_node, nesting)
        return c

    def _handle_else_chain(self, parent_node, nesting):
        """Recursively process elsif and else children. Each elsif may
        contain another elsif (nested) or an else.

        Note: the parser uses the same node type 'elsif' for both the
        wrapper node (containing condition + block + nested chain) AND
        the bare keyword token. We distinguish them by checking for
        children — keyword tokens are leaves."""
        c = 0
        for child in parent_node.children:
            t = child.type
            if t == "elsif" and child.child_count > 0:
                c += 1
                self._add_detail(child, "elsif", 1, 0)
                cond2 = child.child_by_field_name("condition")
                block2 = child.child_by_field_name("block")
                if cond2:
                    c += self._visit(cond2, nesting)
                if block2:
                    c += self._visit_children(block2, nesting + 1)
                # Recurse for further nested elsif/else inside this wrapper
                c += self._handle_else_chain(child, nesting)
            elif t == "else" and child.child_count > 0:
                c += 1
                self._add_detail(child, "else", 1, 0)
                block3 = child.child_by_field_name("block")
                if block3:
                    c += self._visit_children(block3, nesting + 1)
        return c

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting, types, valid_ops):
        ops = []
        self._collect_boolean_ops(node, ops, types, valid_ops)
        if not ops:
            return self._visit_children(node, nesting)

        c = 0
        prev = None
        for op in ops:
            # Normalize: && and 'and' both mean conjunction; || and 'or'
            # both mean disjunction. // (defined-or) is its own kind.
            if op in ("&&", "and"):
                norm = "&&"
            elif op in ("||", "or"):
                norm = "||"
            else:
                norm = op
            if prev is None or norm != prev:
                c += 1
                desc = (f"logical sequence '{op}'"
                        if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = norm
        return c

    def _collect_boolean_ops(self, node, ops, types, valid_ops):
        if node.type not in types:
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        if op_node.type not in valid_ops:
            return
        op_text = op_node.type

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type in types:
            lo = left.child_by_field_name("operator")
            if lo and lo.type in valid_ops:
                self._collect_boolean_ops(left, ops, types, valid_ops)

        ops.append(op_text)

        if right and right.type in types:
            ro = right.child_by_field_name("operator")
            if ro and ro.type in valid_ops:
                self._collect_boolean_ops(right, ops, types, valid_ops)


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
            if fname.endswith((".pl", ".pm", ".t", ".pod")):
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
    print("Perl Cognitive Complexity Calculator")
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
