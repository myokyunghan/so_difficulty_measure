"""
Scala Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)
Dependencies: pip install tree-sitter tree-sitter-scala

"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("scala")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_scala as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-scala")


class CognitiveComplexityCalculator:
    def __init__(self, src):
        self.src = src; self.parser = create_parser()
        self.tree = self.parser.parse(bytes(src, "utf-8"))
        self.results = []; self.details = []
    def _t(self, n): return "" if n is None else self.src[n.start_byte:n.end_byte]
    def _l(self, n): return n.start_point[0]+1
    def _a(self, n, k, s, ne):
        l=self._l(n); t=s+ne
        self.details.append(f"  Line {l:>4}: +{t} ({k}: +{s} structural, +{ne} nesting)" if ne else f"  Line {l:>4}: +{t} ({k})")
    def _ar(self, d, i): self.details.append(f"          +{i} ({d})")

    def calculate(self):
        self.results = []
        self._walk(self.tree.root_node)
        return self.results

    def _walk(self, node):
        for ch in node.children:
            if ch.type in ("function_definition"): self._proc(ch)
            elif ch.type in ("class_definition","object_definition","trait_definition"): self._wcls(ch)

    def _wcls(self, node):
        body = node.child_by_field_name("body")
        if body is None:
            for ch in node.children:
                if ch.type in ("declaration_list","class_body","body"): body=ch; break
        if body is None: return
        for ch in body.children:
            if ch.type in ("function_definition"): self._proc(ch)
            elif ch.type in ("class_definition","object_definition","trait_definition"): self._wcls(ch)

    def _proc(self, fn):
        name = None
        nn=fn.child_by_field_name("name")
        if nn: name=self._t(nn)
        if not name: name = "<anonymous>"
        self.details = []
        body = fn.child_by_field_name("body")
        c = self._vc(body, 0) if body else 0
        self.results.append({"function":name,"complexity":c,"start_line":fn.start_point[0]+1,"end_line":fn.end_point[0]+1,"details":list(self.details)})

    def _vc(self, n, ne):
        t=0
        for ch in n.children: t+=self._v(ch, ne)
        return t

    def _v(self, n, ne):
        t = n.type
        if t == "if_expression": return self._hif(n, ne, True)
        if t in ("for_expression","while_expression"):
            label=t.split("_")[0]
            self._a(n,label,1,ne); c=1+ne
            body=n.child_by_field_name("body")
            if body: c+=self._vc(body,ne+1) if body.type=="block" else self._v(body,ne+1)
            return c
        if t=="match_expression":
            self._a(n,"match",1,ne); c=1+ne
            body=n.child_by_field_name("body")
            if body: c+=self._vc(body,ne+1)
            return c
        if t=="catch_clause":
            self._a(n,"catch",1,ne); c=1+ne
            body=n.child_by_field_name("body")
            if body: c+=self._vc(body,ne+1)
            else: c+=self._vc(n,ne+1)
            return c
        if t=="try_expression": return self._vc(n,ne)
        if t=="finally_clause":
            body=n.child_by_field_name("body")
            return self._vc(body,ne) if body else self._vc(n,ne)



        if t in ("binary_expression","infix_expression"): return self._hbin(n,ne)
        if t=="parenthesized_expression": return self._vc(n,ne)
        if t=="lambda_expression":
            body=n.child_by_field_name("body")
            return self._vc(body,ne+1) if body else self._vc(n,ne+1)
        if t in ("case_clause","case_block"): return self._vc(n,ne)
        return self._vc(n, ne)

    def _hif(self, n, ne, first):
        c=0
        if first: c+=1+ne; self._a(n,"if",1,ne)
        else: c+=1; self._a(n,"else if",1,0)
        cond=n.child_by_field_name("condition")
        if cond: c+=self._v(cond, ne)
        cons=n.child_by_field_name("consequence")
        if cons: c+=self._vc(cons, ne+1) if cons.type in ("block","indented_block") else self._v(cons,ne+1)
        alt=n.child_by_field_name("alternative")
        if alt:
            if alt.type=="if_expression": c+=self._hif(alt,ne,False)
            elif alt.type in ("block","indented_block"):
                c+=1; self._a(alt,"else",1,0); c+=self._vc(alt,ne+1)
            else: c+=1; self._a(alt,"else",1,0); c+=self._v(alt,ne+1)
        return c

    def _hbin(self, n, ne):
        ops=[]; self._cops(n, ops)
        if not ops: return self._vc(n, ne)
        c=0; prev=None
        for op in ops:
            if prev is None or op!=prev:
                c+=1; self._ar(f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'", 1)
                prev=op
        return c
    def _cops(self, n, ops):
        if n.type != "binary_expression": return
        op=n.child_by_field_name("operator")
        if not op: return
        ot=self._t(op)
        if ot not in ("&&","||"): return
        left=n.child_by_field_name("left"); right=n.child_by_field_name("right")
        if left and left.type=="binary_expression":
            lo=left.child_by_field_name("operator")
            if lo and self._t(lo) in ("&&","||"): self._cops(left, ops)
        ops.append(ot)
        if right and right.type=="binary_expression":
            ro=right.child_by_field_name("operator")
            if ro and self._t(ro) in ("&&","||"): self._cops(right, ops)

def calculate_file(fp):
    with open(fp,"r",encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code):
    return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    r=[]
    for root,_,files in os.walk(d):
        for f in sorted(files):
            if any(f.endswith(e) for e in (".scala")):
                p=os.path.join(root,f)
                try:
                    res=calculate_file(p)
                    for x in res: x["file"]=p
                    r.extend(res)
                except Exception as e: print(f"Error {p}: {e}")
    return r
def print_results(results, verbose=True):
    total=sum(r["complexity"] for r in results)
    for r in results:
        print(f"\n{'='*60}")
        if r.get("file"): print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose:
            for d in r.get("details",[]): print(d)
    print(f"\n{'='*60}\nTotal: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")