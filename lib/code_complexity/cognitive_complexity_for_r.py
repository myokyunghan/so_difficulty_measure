"""
R Cognitive Complexity Calculator
==================================
Based on: G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and
Evaluation." In TechDebt '18, ICSE, Gothenburg, Sweden.
https://doi.org/10.1145/3194164.3194186

Build tree-sitter-r:
  git clone https://github.com/r-lib/tree-sitter-r.git
  cd tree-sitter-r
  gcc -shared -fPIC -o /tmp/tree_sitter_r.so src/parser.c src/scanner.c -I src/

Set R_TREESITTER_LIB env var to the .so path, or default /tmp/tree_sitter_r.so
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("r")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_r as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-r")


class CognitiveComplexityCalculator:
    def __init__(self, source_code):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
        self.results = []
        self.details = []

    def _text(self, node):
        if node is None: return ""
        return self.source_code[node.start_byte:node.end_byte]

    def _line(self, node):
        return node.start_point[0] + 1

    def _add_detail(self, node, kind, structural, nesting):
        line = self._line(node)
        total = structural + nesting
        if nesting > 0:
            self.details.append(f"  Line {line:>4}: +{total} ({kind}: +{structural} structural, +{nesting} nesting)")
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, desc, inc):
        self.details.append(f"          +{inc} ({desc})")

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            if child.type == "binary_operator":
                op = child.child_by_field_name("operator")
                if op and self._text(op) in ("<-", "=", "<<-"):
                    rhs = child.child_by_field_name("rhs")
                    if rhs and rhs.type == "function_definition":
                        lhs = child.child_by_field_name("lhs")
                        name = self._text(lhs) if lhs else "<anonymous>"
                        self._process_function(rhs, name)

    def _process_function(self, func_node, func_name):
        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = self._visit_children(body, 0) if body else 0
        self.results.append({
            "function": func_name, "complexity": complexity,
            "start_line": func_node.start_point[0]+1, "end_line": func_node.end_point[0]+1,
            "details": list(self.details),
        })

    def _visit_children(self, node, nesting):
        return sum(self._visit(ch, nesting) for ch in node.children)

    def _visit(self, node, nesting):
        t = node.type

        if t == "if_statement":
            return self._handle_if_chain(node, nesting, is_first=True)

        if t == "for_statement":
            self._add_detail(node, "for", 1, nesting)
            c = 1 + nesting
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting+1)
            return c

        if t == "while_statement":
            self._add_detail(node, "while", 1, nesting)
            c = 1 + nesting
            cond = node.child_by_field_name("condition")
            if cond: c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting+1)
            return c

        if t == "repeat_statement":
            self._add_detail(node, "repeat", 1, nesting)
            c = 1 + nesting
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting+1)
            return c

        if t == "binary_operator":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_logical(node, nesting)
            return self._visit_children(node, nesting)

        if t == "call":
            fn = node.child_by_field_name("function")
            fn_name = self._text(fn) if fn else ""
            if fn_name == "switch":
                self._add_detail(node, "switch", 1, nesting)
                c = 1 + nesting
                args = node.child_by_field_name("arguments")
                if args: c += self._visit_children(args, nesting+1)
                return c
            if fn_name == "tryCatch":
                return self._handle_trycatch(node, nesting)
            return self._visit_children(node, nesting)

        if t == "function_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting+1)
            return c

        return self._visit_children(node, nesting)

    def _handle_trycatch(self, node, nesting):
        c = 0
        args = node.child_by_field_name("arguments")
        if not args: return 0
        for child in args.children:
            if child.type == "argument":
                name_n = child.child_by_field_name("name")
                val_n = child.child_by_field_name("value")
                arg_name = self._text(name_n) if name_n else ""
                if arg_name in ("error","warning","message","condition"):
                    self._add_detail(child, f"tryCatch {arg_name}", 1, nesting)
                    c += 1 + nesting
                    if val_n and val_n.type == "function_definition":
                        hbody = val_n.child_by_field_name("body")
                        if hbody: c += self._visit_children(hbody, nesting+1)
                    elif val_n:
                        c += self._visit(val_n, nesting+1)
                else:
                    if val_n: c += self._visit(val_n, nesting)
                    else:
                        for sub in child.children:
                            if sub.type not in ("(",")",","): c += self._visit(sub, nesting)
        return c

    def _handle_if_chain(self, if_node, nesting, is_first=True):
        c = 0
        if is_first:
            self._add_detail(if_node, "if", 1, nesting)
            c += 1 + nesting
        else:
            self._add_detail(if_node, "else if", 1, 0)
            c += 1

        cond = if_node.child_by_field_name("condition")
        if cond: c += self._visit(cond, nesting)

        cons = if_node.child_by_field_name("consequence")
        if cons: c += self._visit_children(cons, nesting+1)

        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_statement":
                c += self._handle_if_chain(alt, nesting, is_first=False)
            elif alt.type == "braced_expression":
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit_children(alt, nesting+1)
            else:
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit(alt, nesting+1)
        return c

    def _handle_logical(self, node, nesting):
        ops = []
        self._collect_logical_ops(node, ops)
        if not ops: return self._visit_children(node, nesting)
        c, prev = 0, None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                desc = f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'"
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_logical_ops(self, node, ops):
        if node.type != "binary_operator": return
        op = node.child_by_field_name("operator")
        if not op: return
        op_text = self._text(op)
        if op_text not in ("&&","||"): return
        left = node.child_by_field_name("lhs")
        if left and left.type == "binary_operator":
            lop = left.child_by_field_name("operator")
            if lop and self._text(lop) in ("&&","||"):
                self._collect_logical_ops(left, ops)
        ops.append(op_text)
        right = node.child_by_field_name("rhs")
        if right and right.type == "binary_operator":
            rop = right.child_by_field_name("operator")
            if rop and self._text(rop) in ("&&","||"):
                self._collect_logical_ops(right, ops)

# ── Public API ──
def calculate_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f: source = f.read()
    return CognitiveComplexityCalculator(source).calculate()

def calculate_source(source_code):
    return CognitiveComplexityCalculator(source_code).calculate()

def calculate_directory(dirpath):
    all_results = []
    for root, dirs, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith((".R",".r")):
                fpath = os.path.join(root, fname)
                try:
                    results = calculate_file(fpath)
                    for r in results: r["file"] = fpath
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error processing {fpath}: {e}")
    return all_results

def print_results(results, verbose=True):
    total = 0
    for r in results:
        total += r["complexity"]
        print(f"\n{'='*60}")
        if r.get("file"): print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose and r["details"]:
            print("Details:")
            for d in r["details"]: print(d)
    print(f"\n{'='*60}")
    print(f"Total: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")

if __name__ == "__main__":
    test_code = '''
simple_function <- function() {
  x <- 10
}

sum_of_primes <- function(max_val) {
  total <- 0
  for (i in 1:max_val) {
    is_prime <- TRUE
    for (j in 2:(i-1)) {
      if (i %% j == 0) {
        is_prime <- FALSE
        break
      }
    }
    if (is_prime) {
      total <- total + i
    }
  }
  total
}

complex_example <- function(a, b, c) {
  if (a && b) {
    for (i in 1:c) {
      if (i > 10) {
        return(i)
      } else if (i > 5) {
        next
      } else {
        print(i)
      }
    }
  } else if (c > 0) {
    switch(c, a = 1, b = 2, 0)
  }
}

boolean_logic <- function(a, b, c, d) {
  if (a && b && c) {
    return(TRUE)
  } else if (a || b || c) {
    return(FALSE)
  } else if (a && b || c && d) {
    return(TRUE)
  } else {
    return(FALSE)
  }
}

try_example <- function() {
  tryCatch({
    if (TRUE) stop("error")
  }, error = function(e) {
    if (inherits(e, "simpleError")) message(e)
  })
}

while_example <- function(x) {
  while (x > 0) { x <- x - 1 }
}

repeat_example <- function(x) {
  repeat {
    x <- x - 1
    if (x <= 0) break
  }
}

nested_func <- function() {
  inner <- function() {
    if (TRUE) print("nested")
  }
  inner()
}
'''
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    print("R Cognitive Complexity Calculator")
    print("Based on Campbell 2018 (ICSE TechDebt '18)")
    print("=" * 60)
    results = calculate_source(test_code)
    print_results(results)

    print("\n--- Non-code test ---")
    r2 = calculate_source('Error in eval(expr, envir, enclos)')
    print(f"Log text: functions={len(r2)}, complexity={sum(x['complexity'] for x in r2)}")