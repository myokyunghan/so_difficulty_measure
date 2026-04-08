"""
F# Cognitive Complexity Calculator
====================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for F#)
═══════════════════════════════════════════════════════════════════

F# is a multi-paradigm language in the ML family, running on .NET. It
combines functional programming (pattern matching, immutability,
discriminated unions) with object-oriented features (classes, members).
Most F# constructs are expressions, not statements.

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → F#: if_expression
    - match (pattern matching)            → F#: match_expression
                                            (single +1, p.7)
    - for                                 → F#: for_expression
                                            Both `for i = 1 to 10` (counted)
                                            and `for x in xs` (iterator)
    - while                               → F#: while_expression
    - try / try-with                      → F#: try_expression with `with`
                                            clause (single +1 per p.7)
                                            A try/finally without with is
                                            just cleanup, no increment.

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - elif                                → F#: elif_expression
    - else                                → F#: the `else` part of an
                                            if_expression

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - sequences of binary logical ops     → F#: infix_expression with
                                            && / || operators
    - each method in a recursion cycle    → Not implemented

  Not applicable in F# as syntactic constructs:
    - goto                                → F# has no goto
    - break, continue, return             → No break/continue; `return`
                                            in a computation expression is
                                            a keyword but not control flow
                                            in the imperative sense
    - switch fall-through                 → F# match has no fall-through

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, elif, else branches
    - match branches (rule bodies)
    - for, while
    - try body, with branches (exception handler bodies), finally body
    - fun expression (lambda) → nested function (p.9)
    - nested let bindings: function definitions inside let-in
      (declaration_expression)
    - member bodies inside type definitions

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if (NOT elif, NOT else)
    - match
    - for, while
    - try-with (the whole try/with counts once)

═══════════════════════════════════════════════════════════════════
F#-specific notes
═══════════════════════════════════════════════════════════════════

  - F# uses `&&` and `||` for short-circuit boolean operators, same as
    C#/Java/etc. Both contribute to fundamental logical operator
    sequences. F# also has `not` (unary) and the less common bitwise
    logical operators (`&&&`, `|||`, etc.) which are NOT counted as
    boolean sequences.

  - F#'s `if` is an expression (always produces a value), so `else` is
    usually required unless the if returns `unit`. Unlike C-family
    languages, F#'s if-then without else is valid only when the then
    branch has unit type. We still count else as hybrid when present.

  - F# uses `elif` (not `else if`) as a single keyword. The parser
    produces an `elif_expression` node directly under the parent
    `if_expression`.

  - `match expr with | pat1 -> e1 | pat2 -> e2 | ...` is F#'s pattern
    matching. This is the main switch-equivalent in F# (the `switch`
    keyword doesn't exist). Per p.7, the entire match is +1 (single
    increment), regardless of how many rules there are.

  - Match rules may have guards (`| pat when cond -> body`). We do NOT
    count the when-guard as an extra increment — the match already
    captures the branching complexity. This matches how the spec treats
    switch/case: case labels with extra conditions don't each add +1.
    However, if the when-guard contains logical operator sequences
    (&& / ||), those DO count as fundamental increments.

  - `try ... with ... `: F#'s exception handling. The `with` clause is
    pattern matching on exception values:
        try expr with
        | :? SomeException -> handler1
        | ex -> handler2
    Per p.7's catch rule, the entire try/with is +1 structural with
    nesting. Individual with-rules are NOT counted separately.

  - `try ... finally ... `: cleanup, not catching. No increment (neither
    the try nor the finally adds complexity by itself).

  - Lambdas: `fun x -> body` produces a `fun_expression`. Per p.9,
    lambdas count as nested functions — they add nesting but no
    structural increment.

  - Local function definitions via `let` inside another function body
    produce a `declaration_expression` containing a
    `function_or_value_defn` and an `in` body. Nested function bindings
    get +1 nesting for their body (p.9).

  - `|>` (pipe operator) is an infix operator, not control flow. It's
    sugar for function application — we don't count it.

  - Computation expressions (`seq { ... }`, `async { ... }`, list
    comprehensions `[ for x in xs do ... ]`) use `for`/`if` expressions
    inside them. The inner control flow counts normally; the
    computation expression itself adds no complexity.

  - F# has TWO module forms: `named_module` (`module Foo = ...`) and
    `anonymous_module` (just declarations). We handle both.

  - Class members: `type Foo() = member this.Bar x = ...`. Each
    `member_defn` inside a type is processed as a separate function.

═══════════════════════════════════════════════════════════════════
Extension: Top-level let bindings
═══════════════════════════════════════════════════════════════════

  Top-level `let` bindings with a function declaration left side
  (e.g., `let f x = ...`) are processed as functions. Top-level `let`
  bindings with a value declaration left side (e.g., `let x = ...`)
  whose body is a fun_expression are also processed as functions.
  Pure value bindings (constants) are not reported.

Dependencies: tree-sitter, plus tree-sitter-fsharp built from npm
"""
import os
import sys
import json
import ctypes
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("fsharp")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    so_paths = [
        os.path.join(os.path.dirname(__file__), "build", "fsharp.so"),
        os.path.join(os.path.dirname(__file__), "fsharp.so"),
        "/home/claude/build/fsharp.so",
    ]
    for so_path in so_paths:
        if os.path.exists(so_path):
            try:
                lib = ctypes.cdll.LoadLibrary(so_path)
                func = lib.tree_sitter_fsharp
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
        "F# parser not found. Build from npm:\n"
        "  npm install --ignore-scripts tree-sitter-fsharp\n"
        "  gcc -shared -fPIC -O2 \\\n"
        "      -I node_modules/tree-sitter-fsharp/fsharp/src \\\n"
        "      node_modules/tree-sitter-fsharp/fsharp/src/parser.c \\\n"
        "      node_modules/tree-sitter-fsharp/fsharp/src/scanner.c \\\n"
        "      -o build/fsharp.so")


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

    def _find_child(self, node, type_name):
        for c in node.children:
            if c.type == type_name:
                return c
        return None

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        if self._parse_failed or self.tree is None:
            return self.results
        self._walk_top_level(self.tree.root_node, "")
        return self.results

    def _walk_top_level(self, node, prefix):
        for child in node.children:
            t = child.type
            if t in ("named_module", "anonymous_module", "namespace"):
                name_prefix = prefix
                for sub in child.children:
                    fn = self._field_name(child, sub)
                    if fn == "name":
                        mod_name = self._text(sub)
                        name_prefix = (f"{prefix}{mod_name}::"
                                        if mod_name else prefix)
                        break
                self._walk_module_body(child, name_prefix)
            elif t == "value_declaration":
                self._process_value_declaration(child, prefix)
            elif t == "type_definition":
                self._walk_type_definition(child, prefix)

    def _walk_module_body(self, module_node, prefix):
        for child in module_node.children:
            t = child.type
            if t == "value_declaration":
                self._process_value_declaration(child, prefix)
            elif t == "type_definition":
                self._walk_type_definition(child, prefix)
            elif t in ("named_module", "anonymous_module"):
                nested_prefix = prefix
                for sub in child.children:
                    fn = self._field_name(child, sub)
                    if fn == "name":
                        mod_name = self._text(sub)
                        nested_prefix = f"{prefix}{mod_name}::"
                        break
                self._walk_module_body(child, nested_prefix)

    def _walk_type_definition(self, type_node, prefix):
        type_name = ""
        for sub in type_node.children:
            if sub.type == "anon_type_defn":
                for sub2 in sub.children:
                    if sub2.type == "type_name":
                        for sub3 in sub2.children:
                            fn = self._field_name(sub2, sub3)
                            if fn == "type_name":
                                type_name = self._text(sub3)
                                break
                        break

                for sub2 in sub.children:
                    if sub2.type == "type_extension_elements":
                        for elem in sub2.children:
                            if elem.type == "member_defn":
                                self._process_member_defn(
                                    elem, f"{prefix}{type_name}.")

    def _process_value_declaration(self, vd_node, prefix):
        for child in vd_node.children:
            if child.type == "function_or_value_defn":
                self._process_function_or_value(child, prefix)

    def _process_function_or_value(self, defn_node, prefix):
        name = None
        body = None
        is_function = False

        for child in defn_node.children:
            t = child.type
            if t == "function_declaration_left":
                is_function = True
                ident = self._find_child(child, "identifier")
                if ident:
                    name = self._text(ident)
            elif t == "value_declaration_left":
                ident_pat = self._find_child(child, "identifier_pattern")
                if ident_pat:
                    name = self._extract_simple_name(ident_pat)
            else:
                fn = self._field_name(defn_node, child)
                if fn == "body":
                    body = child

        if name is None:
            name = "<anonymous>"
        full_name = f"{prefix}{name}"

        is_fun_value = (body is not None and body.type == "fun_expression")

        if is_function or is_fun_value:
            self.details = []
            complexity = 0
            if body is not None:
                if body.type == "fun_expression":
                    # Skip the fun keyword and arguments; visit the body
                    # at nesting 0 (the lambda IS the function).
                    for sub in body.children:
                        if sub.type in ("fun", "->", "argument_patterns"):
                            continue
                        complexity += self._visit(sub, 0)
                else:
                    complexity += self._visit(body, 0)

            self.results.append({
                "function": full_name,
                "complexity": complexity,
                "start_line": defn_node.start_point[0] + 1,
                "end_line": defn_node.end_point[0] + 1,
                "details": list(self.details),
            })

    def _extract_simple_name(self, ident_pattern_node):
        lio = self._find_child(ident_pattern_node, "long_identifier_or_op")
        if lio:
            return self._text(lio)
        return self._text(ident_pattern_node)

    def _process_member_defn(self, member_node, prefix):
        mpd = self._find_child(member_node, "method_or_prop_defn")
        if mpd is None:
            return

        name = "<anonymous>"
        for child in mpd.children:
            fn = self._field_name(mpd, child)
            if fn == "name":
                for sub in child.children:
                    sfn = self._field_name(child, sub)
                    if sfn == "method":
                        name = self._text(sub)
                        break
                if name == "<anonymous>":
                    idents = [c for c in child.children
                              if c.type == "identifier"]
                    if idents:
                        name = self._text(idents[-1])

        # Find body: the first named child after `=`
        body = None
        equals_found = False
        for child in mpd.children:
            if child.type == "=":
                equals_found = True
                continue
            if equals_found and child.is_named:
                body = child
                break

        full_name = f"{prefix}{name}"
        self.details = []
        complexity = 0
        if body is not None:
            complexity = self._visit(body, 0)

        self.results.append({
            "function": full_name,
            "complexity": complexity,
            "start_line": member_node.start_point[0] + 1,
            "end_line": member_node.end_point[0] + 1,
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
            return self._handle_if(node, nesting)

        # ── B1 structural: match (single +1, p.7) ──
        if t == "match_expression":
            return self._handle_match(node, nesting)

        # ── B1 structural: for (both numeric and iterator forms) ──
        if t == "for_expression":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            for child in node.children:
                ct = child.type
                if ct in ("for", "in", "=", "to", "do", "downto",
                          "identifier", "identifier_pattern"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while_expression":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            visited_cond = False
            for child in node.children:
                ct = child.type
                if ct in ("while", "do"):
                    continue
                if not visited_cond:
                    c += self._visit(child, nesting)
                    visited_cond = True
                else:
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: try-with / try-finally ──
        if t == "try_expression":
            return self._handle_try(node, nesting)

        # ── B1 fundamental: logical operators (&&, ||) ──
        if t == "infix_expression":
            return self._handle_infix(node, nesting)

        # ── B2: lambda → nesting (p.9) ──
        if t == "fun_expression":
            c = 0
            for child in node.children:
                if child.type in ("fun", "->", "argument_patterns"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B2: nested let binding (declaration_expression) ──
        if t == "declaration_expression":
            c = 0
            for child in node.children:
                if child.type == "function_or_value_defn":
                    c += self._visit_nested_defn(child, nesting)
                else:
                    c += self._visit(child, nesting)
            return c

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    def _visit_nested_defn(self, defn_node, nesting):
        """Visit a nested let binding's body at +1 nesting (p.9)."""
        c = 0
        body = None
        for child in defn_node.children:
            fn = self._field_name(defn_node, child)
            if fn == "body":
                body = child
                break
        if body is not None:
            if body.type == "fun_expression":
                for sub in body.children:
                    if sub.type in ("fun", "->", "argument_patterns"):
                        continue
                    c += self._visit(sub, nesting + 1)
            else:
                c += self._visit(body, nesting + 1)
        return c

    # ── if / elif / else handling ──

    def _handle_if(self, if_node, nesting):
        c = 0
        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        guard = if_node.child_by_field_name("guard")
        if guard:
            c += self._visit(guard, nesting)

        then_branch = if_node.child_by_field_name("then")
        if then_branch:
            c += self._visit(then_branch, nesting + 1)

        # elif branches
        for child in if_node.children:
            if child.type == "elif_expression":
                c += 1
                self._add_detail(child, "elif", 1, 0)
                eg = child.child_by_field_name("guard")
                if eg:
                    c += self._visit(eg, nesting)
                et = child.child_by_field_name("then")
                if et:
                    c += self._visit(et, nesting + 1)

        else_branch = if_node.child_by_field_name("else")
        if else_branch is not None:
            c += 1
            self._add_detail(else_branch, "else", 1, 0)
            c += self._visit(else_branch, nesting + 1)

        return c

    # ── match expression handling ──

    def _handle_match(self, match_node, nesting):
        inc = 1 + nesting
        self._add_detail(match_node, "match", 1, nesting)
        c = inc

        for child in match_node.children:
            t = child.type
            if t in ("match", "with"):
                continue
            if t == "rules":
                for rule_child in child.children:
                    if rule_child.type == "rule":
                        c += self._visit_match_rule(rule_child, nesting + 1)
            else:
                c += self._visit(child, nesting)
        return c

    def _visit_match_rule(self, rule_node, nesting):
        c = 0
        guard = rule_node.child_by_field_name("guard")
        if guard is not None:
            c += self._visit(guard, nesting)

        body = rule_node.child_by_field_name("block")
        if body is not None:
            c += self._visit(body, nesting)
        return c

    # ── try / with / finally handling ──

    def _handle_try(self, try_node, nesting):
        has_with = False
        has_finally = False
        for child in try_node.children:
            if child.type == "with":
                has_with = True
            elif child.type == "finally":
                has_finally = True

        c = 0
        if has_with:
            inc = 1 + nesting
            self._add_detail(try_node, "try-with", 1, nesting)
            c += inc

        section = "try"
        for child in try_node.children:
            t = child.type
            if t == "try":
                section = "try"
                continue
            if t == "with":
                section = "with"
                continue
            if t == "finally":
                section = "finally"
                continue
            if section == "try":
                c += self._visit(child, nesting)
            elif section == "with":
                if t == "rules":
                    for rule_child in child.children:
                        if rule_child.type == "rule":
                            c += self._visit_match_rule(rule_child,
                                                          nesting + 1)
                else:
                    c += self._visit(child, nesting + 1)
            else:  # finally
                c += self._visit(child, nesting)
        return c

    # ── Infix expression handling ──

    def _handle_infix(self, node, nesting):
        op = self._find_child(node, "infix_op")
        op_text = ""
        if op is not None:
            op_text = self._text(op).strip()

        if op_text in ("&&", "||"):
            return self._handle_boolean(node, nesting)
        return self._visit_children(node, nesting)

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
        op_node = self._find_child(node, "infix_op")
        if op_node is None:
            return
        op_text = self._text(op_node).strip()
        if op_text not in ("&&", "||"):
            return

        operands = [c for c in node.children
                    if c.is_named and c.type != "infix_op"]
        if len(operands) < 2:
            return
        left, right = operands[0], operands[-1]

        if left.type == "infix_expression":
            lo = self._find_child(left, "infix_op")
            if lo and self._text(lo).strip() in ("&&", "||"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right.type == "infix_expression":
            ro = self._find_child(right, "infix_op")
            if ro and self._text(ro).strip() in ("&&", "||"):
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
            if fname.endswith((".fs", ".fsi", ".fsx", ".fsscript")):
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
    print("F# Cognitive Complexity Calculator")
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
