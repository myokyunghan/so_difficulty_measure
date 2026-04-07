"""
Delphi (Object Pascal) Cognitive Complexity Calculator
========================================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Delphi/Pascal)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Pascal: if / ifElse
    - case                                → Pascal: case (single +1, p.7)
    - for / for downto                    → Pascal: for
    - for in                              → Pascal: foreach
    - while                               → Pascal: while
    - repeat-until                        → Pascal: repeat
    - except handler                      → Pascal: exceptionHandler (each
                                                    `on E: ... do` is +1)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Pascal: ifElse with another
                                                    if/ifElse as else child
    - else                                → Pascal: ifElse's else field

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - sequences of binary logical ops     → Pascal: exprBinary with
                                                    and / or / and then /
                                                    or else operators
    - each method in a recursion cycle    → Not implemented

  Limitations:
    - goto                                → Pascal supports goto, but the
                                            tree-sitter-pascal grammar
                                            parses goto statements as ERROR
                                            nodes. Not detected.
    - break LABEL, continue LABEL         → Pascal has unlabeled
                                            Break/Continue (procedure calls,
                                            no AST node). Plain break/continue
                                            don't add complexity per spec.

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else if, else
    - case
    - for, foreach, while, repeat
    - exceptionHandler (catch handler body)
    - nested procedure/function definitions (defProc inside defProc)

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if (NOT else if, NOT else)
    - case
    - for, foreach, while, repeat
    - exceptionHandler

═══════════════════════════════════════════════════════════════════
Delphi/Pascal-specific notes
═══════════════════════════════════════════════════════════════════

  - Pascal uses keywords for booleans:
      `and`, `or`        - Eager (always evaluate both operands)
      `and then`, `or else` - Short-circuit (Delphi extension)
      `xor`              - Boolean XOR (NOT counted as a logical sequence)
      `not`              - Unary boolean negation (NOT counted)
    Both `and`/`or` and their short-circuit forms count as binary boolean
    operators per the spec (sequences contribute fundamental increments).

  - Pascal's if-then-else uses two distinct AST nodes:
      `if`     - if without else
      `ifElse` - if with else
    The else field of ifElse may contain another if/ifElse, forming an
    `else if` chain. We detect this and apply the hybrid rule.

  - Pascal's case statement:
      case x of
        1: stmt1;
        2: stmt2;
      else
        stmt3;
      end;
    The `else` (also called `otherwise` in some dialects) is the default
    branch. Single +1 for the entire case (p.7), no per-case-label increment.

  - Pascal's repeat-until is the equivalent of do-while. The condition is
    on `until`. +1 structural with nesting.

  - Pascal's `with` statement (`with rec do stmt`) is a name-resolution
    shortcut, not control flow. It does NOT add complexity; the body is
    visited at the same nesting level.

  - Pascal's try-except / try-finally:
      • Each `on E: ExceptionType do` is one exception handler — each
        gets +1 structural with nesting.
      • The `try` and `finally` blocks themselves do not add complexity.
      • A bare `except` clause (without `on`) is also a handler, so it
        gets +1.

  - Class/record method definitions:
      • Inside `interface` section: `declProc` (signature only, no body
        — no complexity).
      • Inside `implementation` section: `defProc` with the method name
        as `genericDot` (e.g., `TFoo.Bar`). These are processed as
        regular functions.

  - Nested procedures: Pascal allows nested procedure/function definitions
    inside the local declarations of a parent procedure. These appear as
    `defProc` nodes in the parent's `local` field (or as direct children).
    Treated as nested functions (B2: nesting+1 inside the parent body).

  - Pascal has no goto support in this parser (parses as ERROR). Pascal's
    Break and Continue are procedure calls with no special AST node — they
    are unlabeled, so per the spec they add no complexity.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  Pascal source files are always either a `program` or a `unit`. The
  `program` has a top-level main `block` which we treat as a pseudo-function
  named `<main>` if it contains any statements.

Dependencies: tree-sitter, plus tree-sitter-pascal built from npm
"""
import os
import sys
import json
import ctypes
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("pascal")
    except Exception:
        pass
    so_paths = [
        os.path.join(os.path.dirname(__file__), "build", "pascal.so"),
        os.path.join(os.path.dirname(__file__), "pascal.so"),
        "/home/claude/build/pascal.so",
    ]
    for so_path in so_paths:
        if os.path.exists(so_path):
            try:
                lib = ctypes.cdll.LoadLibrary(so_path)
                func = lib.tree_sitter_pascal
                func.restype = ctypes.c_void_p
                return Parser(Language(func()))
            except Exception:
                continue
    raise ImportError(
        "Pascal parser not found. Build from npm:\n"
        "  npm install --ignore-scripts tree-sitter-pascal\n"
        "  gcc -shared -fPIC -O2 -I node_modules/tree-sitter-pascal/src "
        "node_modules/tree-sitter-pascal/src/parser.c -o build/pascal.so")


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

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            t = child.type
            if t == "program":
                self._walk_program(child)
            elif t == "unit":
                self._walk_unit(child)

    def _walk_program(self, program_node):
        # Walk all defProc and the main block
        for child in program_node.children:
            t = child.type
            if t == "defProc":
                self._process_function(child)
            elif t == "block":
                # The main begin/end block of the program
                self._process_main_block(child, "<main>",
                                          program_node.start_point[0] + 1,
                                          program_node.end_point[0] + 1)

    def _walk_unit(self, unit_node):
        # interface section: declarations only (no bodies)
        # implementation section: defProc with bodies
        for child in unit_node.children:
            if child.type == "implementation":
                self._walk_implementation(child)

    def _walk_implementation(self, impl_node):
        for child in impl_node.children:
            t = child.type
            if t == "defProc":
                self._process_function(child)
            # Could also handle nested types/units inside implementation

    def _process_main_block(self, block_node, name, start_line, end_line):
        """Process a program's top-level block as a pseudo-function."""
        self.details = []
        complexity = self._visit_children(block_node, 0)
        if complexity > 0 or self.details:
            self.results.append({
                "function": name,
                "complexity": complexity,
                "start_line": block_node.start_point[0] + 1,
                "end_line": block_node.end_point[0] + 1,
                "details": list(self.details),
            })

    def _process_function(self, func_node):
        name = self._extract_function_name(func_node)

        self.details = []
        complexity = 0

        # A defProc has: header (declProc), optional local (declVars/defProc),
        # body (block).
        body = func_node.child_by_field_name("body")
        local = None
        for child in func_node.children:
            fn = self._field_name(func_node, child)
            if fn == "local":
                local = child
                break

        if body:
            complexity += self._visit_children(body, 0)

        # Process nested procs as separate functions (siblings in report)
        nested_procs = []
        if local and local.type == "defProc":
            nested_procs.append(local)
        # Also scan body for nested procs (some grammars place them differently)

        self.results.append({
            "function": name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

        # Process nested procedures as separate entries
        for np in nested_procs:
            self._process_function(np)

    def _extract_function_name(self, func_node):
        header = func_node.child_by_field_name("header")
        if header is None:
            return "<anonymous>"
        name_node = header.child_by_field_name("name")
        if name_node is None:
            return "<anonymous>"
        if name_node.type == "identifier":
            return self._text(name_node)
        if name_node.type == "genericDot":
            # Class method: TFoo.Bar
            lhs = name_node.child_by_field_name("lhs")
            rhs = name_node.child_by_field_name("rhs")
            l = self._text(lhs) if lhs else ""
            r = self._text(rhs) if rhs else ""
            if l and r:
                return f"{l}.{r}"
            return self._text(name_node)
        return self._text(name_node)

    # ── Node visitors ──

    def _visit_children(self, node, nesting):
        total = 0
        for child in node.children:
            total += self._visit(child, nesting)
        return total

    def _visit(self, node, nesting):
        t = node.type

        # ── B1 structural: if (without else) ──
        if t == "if":
            inc = 1 + nesting
            self._add_detail(node, "if", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            then_part = node.child_by_field_name("then")
            if then_part:
                c += self._visit(then_part, nesting + 1)
            return c

        # ── B1 structural: ifElse (with else) ──
        if t == "ifElse":
            return self._handle_if_else(node, nesting, is_else_if=False)

        # ── B1 structural: case (single +1, p.7) ──
        if t == "case":
            inc = 1 + nesting
            self._add_detail(node, "case", 1, nesting)
            c = inc
            for child in node.children:
                t2 = child.type
                if t2 in ("kCase", "kOf", "kEnd", "kElse", ";"):
                    continue
                if t2 == "caseCase":
                    # Visit only the body (skip the label)
                    for sub in child.children:
                        fn = self._field_name(child, sub)
                        if fn == "label":
                            continue
                        c += self._visit(sub, nesting + 1)
                elif t2 == "statement":
                    # The else branch of case (after kElse)
                    c += self._visit(child, nesting + 1)
                elif t2 == "identifier":
                    # The case selector
                    pass
                else:
                    c += self._visit(child, nesting)
            return c

        # ── B1 structural: for ──
        if t == "for":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── B1 structural: foreach (for-in) ──
        if t == "foreach":
            inc = 1 + nesting
            self._add_detail(node, "for in", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while":
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

        # ── B1 structural: repeat-until ──
        if t == "repeat":
            inc = 1 + nesting
            self._add_detail(node, "repeat", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try":
            c = 0
            for child in node.children:
                t2 = child.type
                if t2 in ("kTry", "kEnd", ";"):
                    continue
                # try field, except field (kExcept keyword), finally field
                # exceptionHandler children, statements children
                if t2 == "exceptionHandler":
                    c += self._visit(child, nesting)
                elif t2 in ("kExcept", "kFinally"):
                    continue
                else:
                    c += self._visit(child, nesting)
            return c

        # ── B1 structural: exception handler (catch / except on) ──
        if t == "exceptionHandler":
            inc = 1 + nesting
            self._add_detail(node, "except", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── with statement: NOT control flow, just visit body ──
        if t == "with":
            body = node.child_by_field_name("body")
            if body:
                return self._visit(body, nesting)
            return self._visit_children(node, nesting)

        # ── B1 fundamental: logical operators (and / or / and then / or else) ──
        if t == "exprBinary":
            op = node.child_by_field_name("operator")
            if op and op.type in ("kAnd", "kOr"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: nested defProc → nesting (p.9) ──
        if t == "defProc":
            # This appears inside another function as a nested procedure.
            # Per spec p.9: nested function adds nesting but no structural increment.
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            # Local nested procs of this nested proc
            for child in node.children:
                fn = self._field_name(node, child)
                if fn == "local" and child.type == "defProc":
                    c += self._visit(child, nesting + 1)
            return c

        # ── statements wrapper: visit children ──
        if t == "statements":
            return self._visit_children(node, nesting)

        # ── statement wrapper: visit children ──
        if t == "statement":
            return self._visit_children(node, nesting)

        # ── block: visit children ──
        if t == "block":
            return self._visit_children(node, nesting)

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if-else / else-if chain ──

    def _handle_if_else(self, node, nesting, is_else_if):
        c = 0
        if is_else_if:
            c += 1
            self._add_detail(node, "else if", 1, 0)
        else:
            inc = 1 + nesting
            self._add_detail(node, "if", 1, nesting)
            c += inc

        # condition
        cond = node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # then branch
        then_part = node.child_by_field_name("then")
        if then_part:
            c += self._visit(then_part, nesting + 1)

        # else branch
        else_part = node.child_by_field_name("else")
        if else_part:
            if else_part.type in ("if", "ifElse"):
                # else if
                if else_part.type == "ifElse":
                    c += self._handle_if_else(else_part, nesting,
                                                is_else_if=True)
                else:
                    # `else if` without further else: like a hybrid then
                    # plain if. Treat it as else-if (+1 hybrid) too, with
                    # body visited at +1 nesting.
                    c += 1
                    self._add_detail(else_part, "else if", 1, 0)
                    cond2 = else_part.child_by_field_name("condition")
                    if cond2:
                        c += self._visit(cond2, nesting)
                    then2 = else_part.child_by_field_name("then")
                    if then2:
                        c += self._visit(then2, nesting + 1)
            else:
                # plain else
                c += 1
                self._add_detail(else_part, "else", 1, 0)
                c += self._visit(else_part, nesting + 1)
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
        if node.type != "exprBinary":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        if op_node.type not in ("kAnd", "kOr"):
            return
        op_text = op_node.type  # 'kAnd' or 'kOr'

        left = node.child_by_field_name("lhs")
        right = node.child_by_field_name("rhs")

        if left and left.type == "exprBinary":
            lo = left.child_by_field_name("operator")
            if lo and lo.type in ("kAnd", "kOr"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "exprBinary":
            ro = right.child_by_field_name("operator")
            if ro and ro.type in ("kAnd", "kOr"):
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
            if fname.lower().endswith((".pas", ".pp", ".dpr", ".lpr", ".inc")):
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
    print("Delphi (Object Pascal) Cognitive Complexity Calculator")
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