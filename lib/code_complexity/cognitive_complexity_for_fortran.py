"""
Fortran Cognitive Complexity Calculator
========================================
SonarSource Cognitive Complexity 화이트페이퍼 규칙에 따라
Fortran 소스코드의 함수/서브루틴별 인지 복잡도를 계산합니다.

규칙:
1. Structural increment (+1):
   - if, else if, else, select case, do, do while
   - goto, exit LABEL, cycle LABEL
   - 논리 연산자 시퀀스 전환 (.and., .or.)

2. Nesting increment (+nesting_level):
   - if, select case, do, do while이 중첩될 때
   - else if / else는 nesting penalty 없음

3. Nesting level 증가:
   - if, select case, do, do while

의존성: pip install tree-sitter tree-sitter-fortran
"""

import tree_sitter_fortran as ts_f
from tree_sitter import Language, Parser
import os
import json
import sys


F_LANGUAGE = Language(ts_f.language())


def create_parser():
    parser = Parser(F_LANGUAGE)
    return parser


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
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
                f"  Line {line:>4}: +{total} ({kind}: +{structural} structural, +{nesting} nesting)"
            )
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, description, increment):
        self.details.append(f"          +{increment} ({description})")

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            if child.type in ("subroutine", "function"):
                self._process_function(child)
            elif child.type == "program":
                self._process_function(child)
            elif child.type == "module":
                # module 내부의 함수/서브루틴
                for sub in child.children:
                    if sub.type in ("subroutine", "function"):
                        self._process_function(sub)
                    elif sub.type == "internal_procedures":
                        for item in sub.children:
                            if item.type in ("subroutine", "function"):
                                self._process_function(item)

    def _get_func_name(self, func_node):
        """함수/서브루틴 이름 추출"""
        # subroutine_statement 또는 function_statement에서 name 필드 찾기
        for child in func_node.children:
            if child.type in ("subroutine_statement", "function_statement", "program_statement"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    return self._text(name_node)
                # fallback: name 타입 자식 찾기
                for sub in child.children:
                    if sub.type == "name":
                        return self._text(sub)
        return "<anonymous>"

    def _process_function(self, func_node):
        func_name = self._get_func_name(func_node)

        self.details = []
        complexity = self._visit_body(func_node, 0)

        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _visit_body(self, node, nesting):
        """함수 본문의 statements를 순회 (선언문 등은 건너뜀)"""
        total = 0
        skip_types = (
            "subroutine_statement", "function_statement", "program_statement",
            "end_subroutine_statement", "end_function_statement", "end_program_statement",
            "implicit_statement", "variable_declaration", "use_statement",
            "comment", "include_statement",
        )
        for child in node.children:
            if child.type in skip_types:
                continue
            total += self._visit(child, nesting)
        return total

    def _visit_children(self, node, nesting):
        total = 0
        for child in node.children:
            total += self._visit(child, nesting)
        return total

    def _visit(self, node, nesting):
        t = node.type

        # ── if statement ──
        if t == "if_statement":
            return self._handle_if(node, nesting)

        # ── do loop (일반 do, do while 포함) ──
        if t == "do_loop_statement":
            return self._handle_do_loop(node, nesting)

        # ── select case ──
        if t == "select_case_statement":
            inc = 1 + nesting
            self._add_detail(node, "select case", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "case_statement":
                    c += self._visit_case_body(child, nesting + 1)
            return c

        # ── keyword_statement: goto, exit, cycle ──
        if t == "keyword_statement":
            return self._handle_keyword_statement(node)

        # ── logical_expression (.and., .or.) ──
        if t == "logical_expression":
            return self._handle_logical(node, nesting)

        # ── 기타: 자식 재귀 ──
        return self._visit_children(node, nesting)

    def _handle_if(self, if_node, nesting):
        c = 0

        # if: +1 structural + nesting penalty
        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        # condition (parenthesized_expression 안의 논리 연산자)
        for child in if_node.children:
            if child.type == "parenthesized_expression":
                c += self._visit_children(child, nesting)
                break

        # if body (then ~ elseif/else/endif 사이의 statements)
        in_body = False
        for child in if_node.children:
            if child.type == "then":
                in_body = True
                continue
            if child.type in ("elseif_clause", "else_clause", "end_if_statement"):
                in_body = False
            if in_body:
                c += self._visit(child, nesting + 1)

        # elseif / else
        for child in if_node.children:
            if child.type == "elseif_clause":
                c += self._handle_elseif(child, nesting)
            elif child.type == "else_clause":
                c += self._handle_else(child, nesting)

        return c

    def _handle_elseif(self, elseif_node, nesting):
        c = 0
        c += 1
        self._add_detail(elseif_node, "else if", 1, 0)

        # condition
        for child in elseif_node.children:
            if child.type == "parenthesized_expression":
                c += self._visit_children(child, nesting)
                break

        # body (then 이후의 statements)
        in_body = False
        for child in elseif_node.children:
            if child.type == "then":
                in_body = True
                continue
            if in_body:
                c += self._visit(child, nesting + 1)

        return c

    def _handle_else(self, else_node, nesting):
        c = 0
        c += 1
        self._add_detail(else_node, "else", 1, 0)

        # body (else 키워드 이후)
        past_else = False
        for child in else_node.children:
            if child.type == "else":
                past_else = True
                continue
            if past_else:
                c += self._visit(child, nesting + 1)

        return c

    def _handle_do_loop(self, do_node, nesting):
        # do while인지 확인
        has_while = any(child.type == "while_statement" for child in do_node.children)
        label = "do while" if has_while else "do"

        inc = 1 + nesting
        self._add_detail(do_node, label, 1, nesting)
        c = inc

        # body: do ~ end do 사이의 statements
        skip_types = (
            "do", "block_label_start_expression", "loop_control_expression",
            "while_statement", "end_do_loop_statement",
        )
        for child in do_node.children:
            if child.type in skip_types:
                continue
            c += self._visit(child, nesting + 1)

        return c

    def _visit_case_body(self, case_node, nesting):
        """case_statement 내부의 statements만 처리"""
        c = 0
        past_paren = False
        for child in case_node.children:
            if child.type in ("case", "default", "(", ")", "case_value_range_list"):
                continue
            if child.type == ")":
                past_paren = True
                continue
            # case 키워드와 값 이후의 statements만 처리
            if child.type not in ("case", "default", "(", ")", "case_value_range_list",
                                   "end_select_statement"):
                c += self._visit(child, nesting)
        return c

    def _handle_keyword_statement(self, node):
        """goto, exit LABEL, cycle LABEL 처리"""
        children = [ch for ch in node.children]

        # goto
        if any(ch.type == "goto" for ch in children):
            self._add_detail(node, "goto", 1, 0)
            return 1

        # exit / cycle with label
        has_exit = any(ch.type == "exit" for ch in children)
        has_cycle = any(ch.type == "cycle" for ch in children)
        has_label = any(ch.type == "identifier" for ch in children)

        if has_exit and has_label:
            self._add_detail(node, "exit with label", 1, 0)
            return 1
        if has_cycle and has_label:
            self._add_detail(node, "cycle with label", 1, 0)
            return 1

        return 0

    def _handle_logical(self, node, nesting):
        """논리 연산자 (.and., .or.) 시퀀스 처리"""
        ops = []
        self._collect_logical_ops(node, ops)

        if not ops:
            return self._visit_children(node, nesting)

        c = 0
        prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                desc = f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'"
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_logical_ops(self, node, ops):
        if node.type != "logical_expression":
            return

        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return

        op_text = self._text(op_node).lower()
        if op_text not in (".and.", ".or."):
            return

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type == "logical_expression":
            left_op = left.child_by_field_name("operator")
            if left_op and self._text(left_op).lower() in (".and.", ".or."):
                self._collect_logical_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "logical_expression":
            right_op = right.child_by_field_name("operator")
            if right_op and self._text(right_op).lower() in (".and.", ".or."):
                self._collect_logical_ops(right, ops)


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
            if fname.endswith((".f90", ".f95", ".f03", ".f08", ".f", ".for", ".fpp")):
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
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
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

    test_code = '''
! Expected: 0
subroutine simple()
  implicit none
  integer :: x
  x = 10
end subroutine simple

! Expected: 7
subroutine sum_of_primes(max_val, total)
  implicit none
  integer, intent(in) :: max_val
  integer, intent(out) :: total
  integer :: i, j
  logical :: is_prime
  total = 0
  do i = 1, max_val                              ! +1 (do)
    is_prime = .true.
    do j = 2, i - 1                              ! +2 (do, nesting=1)
      if (mod(i, j) == 0) then                   ! +3 (if, nesting=2)
        is_prime = .false.
        exit                                      ! no label, no increment
      end if
    end do
    if (is_prime) then                            ! +1 (if — back to nesting=1... wait, this is at nesting=1)
      total = total + i
    end if
  end do
end subroutine sum_of_primes

! Expected: 1
subroutine get_words(number)
  implicit none
  integer, intent(in) :: number
  select case (number)                            ! +1 (select case)
    case (1)
      print *, 'one'
    case (2)
      print *, 'a couple'
    case default
      print *, 'lots'
  end select
end subroutine get_words

! Expected: 9
subroutine boolean_logic(a, b, c, d)
  implicit none
  logical, intent(in) :: a, b, c, d
  if (a .and. b .and. c) then                    ! +1 (if) +1 (.and.)
    return
  else if (a .or. b .or. c) then                 ! +1 (else if) +1 (.or.)
    return
  else if (a .and. b .or. c .and. d) then        ! +1 (else if) +1(.and.) +1(.or.) +1(.and.)
    return
  else                                            ! +1 (else)
    return
  end if
end subroutine boolean_logic

! Expected: 3
subroutine labeled_loop()
  implicit none
  integer :: i, j
  outer: do i = 1, 10                            ! +1 (do)
    inner: do j = 1, 10                          ! +2 (do, nesting=1)
      if (i == j) then                           ! +3 (if, nesting=2)
        exit outer                               ! +1 (exit with label)
      end if
    end do inner
  end do outer
end subroutine labeled_loop

! Expected: 1
subroutine do_while_example(x)
  implicit none
  integer, intent(inout) :: x
  do while (x > 0)                               ! +1 (do while)
    x = x - 1
  end do
end subroutine do_while_example

! Expected: 1
subroutine goto_example()
  implicit none
  goto 100                                        ! +1 (goto)
  100 continue
end subroutine goto_example
'''

    print("Fortran Cognitive Complexity Calculator")
    print("Based on SonarSource Cognitive Complexity specification")
    print("=" * 60)

    results = calculate_source(test_code)
    print_results(results, verbose=True)

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