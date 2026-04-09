"""
Fortran Cognitive Complexity Calculator
=========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Fortran)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if (block or single-line)           → Fortran: if_statement
    - select case                         → Fortran: select_case_statement
                                            (single +1, p.7)
    - do counted loop                     → Fortran: do_loop_statement with
                                            loop_control_expression
    - do labeled loop (old-style)         → Fortran: do_label_statement
    - do while                            → Fortran: do_loop_statement with
                                            a while_statement child
    - where (array masking)               → Fortran: where_statement
                                            Array equivalent of if; counted
                                            as structural +1
    - forall                              → Fortran: forall_statement
                                            Array iteration; counted as
                                            loop-equivalent +1

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Fortran: elseif_clause
    - else                                → Fortran: else_clause
    - elsewhere (where's else)            → Fortran: elsewhere_clause

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - goto LABEL                          → Fortran: keyword_statement
                                            with `goto` keyword
    - exit LABEL / cycle LABEL            → Fortran: keyword_statement
                                            with `exit` or `cycle` followed
                                            by an identifier (named loop)
    - sequences of binary logical ops     → Fortran: logical_expression with
                                            .and. / .or. / .eqv. / .neqv.
                                            operators
    - each method in a recursion cycle    → Not implemented

  Not applicable in Fortran:
    - try/catch                           → Fortran has no exception
                                            handling syntax. Errors are
                                            handled via integer status
                                            arguments (iostat=, stat=).
                                            No syntactic construct exists.
    - ternary                             → Fortran has no ternary operator.
                                            The intrinsic merge(t, f, mask)
                                            is a function, not control flow.
    - plain break/continue (no label)     → Fortran's `exit`/`cycle` without
                                            a label work like break/continue
                                            but apply to the innermost loop.
                                            Per spec, plain forms add no
                                            complexity.

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if (and elseif/else clauses)
    - select case
    - do (all forms: counted, while, labeled)
    - where, elsewhere
    - forall
    - nested subroutines/functions inside `internal_procedures`

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if (NOT elseif, NOT else)
    - select case
    - do (all forms)
    - where (NOT elsewhere)
    - forall

═══════════════════════════════════════════════════════════════════
Fortran-specific notes
═══════════════════════════════════════════════════════════════════

  - Fortran's logical operators are written between dots:
        .and.    .or.    .not.    .eqv.    .neqv.    .xor.
    Both `.and.` and `.or.` are sometimes (depending on compiler and
    standard) short-circuit, sometimes not. Per the spec, both contribute
    to fundamental logical operator sequences regardless of evaluation
    order. `.not.` is unary and not counted in sequences. `.eqv.` and
    `.neqv.` are logical equivalence operators — we count them as part
    of sequences (they're binary boolean operators).

  - Fortran has TWO if-statement forms:
        ! Block form
        if (cond) then
          stmts
        else if (cond2) then
          stmts
        else
          stmts
        end if
        ! Single-line form
        if (cond) statement
    Both produce `if_statement` nodes. The block form has `then` as a
    child token; single-line form does not. Both count as +1 structural.

  - Fortran's `do` loop has multiple forms:
        do i = 1, 10           ! counted (modern)
        do i = 1, 10, 2        ! counted with stride
        do while (cond)        ! while loop
        do                     ! infinite loop (with internal exit)
        do 100 i = 1, 10       ! labeled (old-style FORTRAN 77)
    All produce `do_loop_statement` (or `do_label_statement` for the
    old-style form). All are structural +1 with nesting.

  - `select case` is Fortran's switch. The `selector` is the discriminant,
    and each `case_statement` is a branch. Per p.7, the entire select
    case is +1 (single increment). Individual case branches do NOT add
    further increments.

  - `where` and `elsewhere` are Fortran's array conditionals. They mask
    array operations:
        where (a > 0)
          a = a * 2
        elsewhere
          a = 0
        end where
    We treat these like if/else: where = +1 structural with nesting,
    elsewhere = +1 hybrid.

  - `forall` is a parallel array constructor — it iterates over an index
    range and applies an assignment to each element. Treated as loop
    +1 structural with nesting.

  - `exit` and `cycle` are Fortran's break and continue. Without a
    label, they apply to the innermost loop and add no complexity (per
    spec). With a label (`exit OUTER`, `cycle INNER`), they jump to a
    named outer loop and count as fundamental +1.

  - `goto LABEL` is supported in Fortran. Per spec, +1 fundamental.

  - Fortran has nested procedures via `contains` blocks:
        subroutine outer
        contains
          subroutine inner
            ...
          end subroutine inner
        end subroutine outer
    Inner procedures appear inside `internal_procedures` nodes. We
    treat them as nested functions: visited at +1 nesting AND reported
    as separate function entries (mirroring how Pascal nested procedures
    are handled).

  - Modules contain procedures via `contains_statement`. Module-level
    procedures are reported with the module name as a prefix
    (e.g., `mymod::foo`).

  - The `block_construct` (Fortran 2008) is just a scoping block with
    optional local declarations — NOT a control flow construct. We
    visit its body without adding complexity.

  - The `associate` construct creates aliases for expressions. NOT
    control flow, just scoping. No increment.

  - `recursive` is a procedure attribute (`recursive function fact`).
    The procedure is still detected as a normal function/subroutine.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  Fortran source files always have a top-level `program`, `module`,
  `subroutine`, or `function`. The `program` block's body is treated
  as a function for complexity reporting.

Dependencies: pip install tree-sitter tree-sitter-fortran
"""
import os
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    """Prefer individual tree_sitter_fortran package because
    tree_sitter_language_pack may return a wrong/generic parser for
    fortran on some installations."""
    try:
        import tree_sitter_fortran as _mod
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
        _p = get_parser("fortran")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    raise ImportError("Install: pip install tree-sitter-fortran")
_LOGICAL_OPS = frozenset([
    "\\.and\\.", "\\.or\\.", "\\.eqv\\.", "\\.neqv\\.", "\\.xor\\.",
    ".and.", ".or.", ".eqv.", ".neqv.", ".xor.",
])


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

    def _has_child_of_type(self, node, type_name):
        for c in node.children:
            if c.type == type_name:
                return True
        return False

    def _find_child(self, node, type_name):
        for c in node.children:
            if c.type == type_name:
                return c
        return None

    def _named_children(self, node):
        return [c for c in node.children if c.is_named]

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
            if t == "program":
                # The program itself is a function-like entity
                self._process_program(child, prefix)
            elif t == "module":
                self._walk_module(child)
            elif t == "subroutine":
                self._process_function(child, prefix, "subroutine")
            elif t == "function":
                self._process_function(child, prefix, "function")

    def _walk_module(self, module_node):
        # Get module name
        mod_name = ""
        for child in module_node.children:
            if child.type == "module_statement":
                name_node = self._find_child(child, "name")
                if name_node:
                    mod_name = self._text(name_node)
                break
        prefix = f"{mod_name}::" if mod_name else ""

        # Walk internal_procedures
        for child in module_node.children:
            if child.type == "internal_procedures":
                for sub in child.children:
                    if sub.type == "subroutine":
                        self._process_function(sub, prefix, "subroutine")
                    elif sub.type == "function":
                        self._process_function(sub, prefix, "function")

    def _extract_proc_name(self, proc_node):
        """Get the procedure name from a function/subroutine node."""
        for child in proc_node.children:
            if child.type in ("subroutine_statement", "function_statement"):
                name_node = self._find_child(child, "name")
                if name_node:
                    return self._text(name_node)
        return "<anonymous>"

    def _process_program(self, program_node, prefix):
        """Process a `program` block."""
        # Get program name
        name = ""
        for child in program_node.children:
            if child.type == "program_statement":
                name_node = self._find_child(child, "name")
                if name_node:
                    name = self._text(name_node)
                break
        if not name:
            name = "<program>"
        full_name = f"{prefix}{name}"

        self.details = []
        complexity = 0
        nested = []

        for child in program_node.children:
            t = child.type
            if t in ("program_statement", "end_program_statement"):
                continue
            if t == "internal_procedures":
                # Collect nested procs to process after the program
                for sub in child.children:
                    if sub.type in ("subroutine", "function"):
                        nested.append(sub)
                continue
            complexity += self._visit(child, 0)

        self.results.append({
            "function": full_name,
            "complexity": complexity,
            "start_line": program_node.start_point[0] + 1,
            "end_line": program_node.end_point[0] + 1,
            "details": list(self.details),
        })

        for n in nested:
            self._process_function(n, prefix, n.type)

    def _process_function(self, func_node, prefix, kind):
        """Process a subroutine or function. Recursively handles
        nested procedures inside `internal_procedures`."""
        name = self._extract_proc_name(func_node)
        full_name = f"{prefix}{name}"

        self.details = []
        complexity = 0
        nested = []

        for child in func_node.children:
            t = child.type
            if t in ("subroutine_statement", "function_statement",
                     "end_subroutine_statement", "end_function_statement"):
                continue
            if t == "internal_procedures":
                # Collect nested procs to process after the parent
                for sub in child.children:
                    if sub.type in ("subroutine", "function"):
                        nested.append(sub)
                continue
            complexity += self._visit(child, 0)

        self.results.append({
            "function": full_name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

        # Process nested procs as separate entries
        for n in nested:
            self._process_function(n, prefix, n.type)

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
            return self._handle_if(node, nesting)

        # ── B1 structural: select case (p.7 single +1) ──
        if t == "select_case_statement":
            inc = 1 + nesting
            self._add_detail(node, "select case", 1, nesting)
            c = inc
            for child in node.children:
                ct = child.type
                if ct in ("selectcase", "selector",
                          "end_select_statement"):
                    continue
                if ct == "case_statement":
                    # Visit case body at +1 nesting (case body, not the label)
                    for sub in child.children:
                        if sub.type in ("case", "default", "(", ")",
                                        "case_value_range_list"):
                            continue
                        c += self._visit(sub, nesting + 1)
                else:
                    c += self._visit(child, nesting)
            return c

        # ── B1 structural: do (all forms) ──
        if t == "do_loop_statement":
            return self._handle_do(node, nesting)

        if t == "do_label_statement":
            inc = 1 + nesting
            self._add_detail(node, "do (labeled)", 1, nesting)
            return inc

        # where_statement / forall_statement: removed (language-specific,
        # not in White Paper Appendix B). Just recurse without counting.
        if t in ("where_statement", "forall_statement"):
            return self._visit_children(node, nesting)

        # ── B1 fundamental: keyword_statement (goto, exit/cycle LABEL) ──
        if t == "keyword_statement":
            return self._handle_keyword(node, nesting)

        # ── B1 fundamental: logical operators (.and., .or., .eqv., .neqv.) ──
        if t == "logical_expression":
            op = node.child_by_field_name("operator")
            if op and op.type in _LOGICAL_OPS:
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── block_construct: just scoping, no complexity ──
        if t == "block_construct":
            c = 0
            for child in node.children:
                if child.type in ("block", "end_block_construct_statement"):
                    continue
                c += self._visit(child, nesting)
            return c

        # ── associate: just scoping (alias creation), no complexity ──
        if t == "associate_statement":
            c = 0
            for child in node.children:
                if child.type in ("associate", "(", ")", "association",
                                  "end_associate_statement"):
                    continue
                c += self._visit(child, nesting)
            return c

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if statement (block or single-line) ──

    def _handle_if(self, if_node, nesting):
        c = 0
        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        # Visit condition for nested logical ops
        for child in if_node.children:
            if child.type == "parenthesized_expression":
                c += self._visit(child, nesting)
                break

        # Walk children: visit body statements at nesting+1, handle
        # elseif/else clauses with hybrid increments
        for child in if_node.children:
            t = child.type
            if t in ("if", "then", "parenthesized_expression",
                     "end_if_statement"):
                continue
            if t == "elseif_clause":
                c += 1
                self._add_detail(child, "else if", 1, 0)
                # Visit elseif's condition and body
                for sub in child.children:
                    st = sub.type
                    if st in ("elseif", "then"):
                        continue
                    if st == "parenthesized_expression":
                        c += self._visit(sub, nesting)
                        continue
                    c += self._visit(sub, nesting + 1)
            elif t == "else_clause":
                c += 1
                self._add_detail(child, "else", 1, 0)
                for sub in child.children:
                    if sub.type == "else":
                        continue
                    c += self._visit(sub, nesting + 1)
            else:
                # Body statement of the then-branch
                c += self._visit(child, nesting + 1)
        return c

    # ── do loop (counted, while, infinite, labeled) ──

    def _handle_do(self, do_node, nesting):
        # Distinguish do-while from counted do
        is_while = self._has_child_of_type(do_node, "while_statement")
        kind = "do while" if is_while else "do"

        c = 0
        inc = 1 + nesting
        self._add_detail(do_node, kind, 1, nesting)
        c += inc

        for child in do_node.children:
            t = child.type
            if t in ("do", "loop_control_expression",
                     "block_label_start_expression",
                     "end_do_loop_statement"):
                continue
            if t == "while_statement":
                # Visit the condition for nested logical ops
                for sub in child.children:
                    if sub.type == "parenthesized_expression":
                        c += self._visit(sub, nesting)
                continue
            c += self._visit(child, nesting + 1)
        return c

    # ── where / elsewhere ──

    def _handle_where(self, where_node, nesting):
        c = 0
        inc = 1 + nesting
        self._add_detail(where_node, "where", 1, nesting)
        c += inc

        # Visit condition
        for child in where_node.children:
            if child.type == "parenthesized_expression":
                c += self._visit(child, nesting)
                break

        for child in where_node.children:
            t = child.type
            if t in ("where", "parenthesized_expression",
                     "end_where_statement"):
                continue
            if t == "elsewhere_clause":
                c += 1
                self._add_detail(child, "elsewhere", 1, 0)
                for sub in child.children:
                    if sub.type == "elsewhere":
                        continue
                    c += self._visit(sub, nesting + 1)
            else:
                c += self._visit(child, nesting + 1)
        return c

    # ── keyword statements (goto, exit, cycle, return, etc.) ──

    def _handle_keyword(self, node, nesting):
        # First child is the keyword
        kw = None
        for child in node.children:
            if child.type in ("goto", "exit", "cycle", "return",
                              "continue", "stop", "pause"):
                kw = child.type
                break
        if kw is None:
            return 0

        if kw == "goto":
            # +1 fundamental (goto LABEL)
            self._add_detail(node, "goto", 1, 0)
            return 1

        if kw in ("exit", "cycle"):
            # Check for an identifier (label) after the keyword. Plain
            # exit/cycle (no label) doesn't add complexity.
            has_label = False
            for child in node.children:
                if child.type == "identifier":
                    has_label = True
                    break
            if has_label:
                self._add_detail(node, f"{kw} LABEL", 1, 0)
                return 1
            return 0

        # return, continue, stop, pause: no increment
        return 0

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting):
        ops = []
        self._collect_boolean_ops(node, ops)
        if not ops:
            return self._visit_children(node, nesting)

        c = 0
        prev = None
        for op in ops:
            # Normalize operator names by stripping escapes and dots
            norm = op.replace("\\", "").replace(".", "")
            if prev is None or norm != prev:
                c += 1
                clean_op = "." + norm + "."
                desc = (f"logical sequence '{clean_op}'"
                        if prev is None
                        else f"logical change to '{clean_op}'")
                self._add_detail_raw(desc, 1)
                prev = norm
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "logical_expression":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        if op_node.type not in _LOGICAL_OPS:
            return
        op_text = op_node.type

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type == "logical_expression":
            lo = left.child_by_field_name("operator")
            if lo and lo.type in _LOGICAL_OPS:
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "logical_expression":
            ro = right.child_by_field_name("operator")
            if ro and ro.type in _LOGICAL_OPS:
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
            if fname.lower().endswith((".f", ".for", ".f77", ".f90",
                                        ".f95", ".f03", ".f08", ".ftn")):
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
    print("Fortran Cognitive Complexity Calculator")
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
