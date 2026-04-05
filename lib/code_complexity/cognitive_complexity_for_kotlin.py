"""
Kotlin Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)
Dependencies: pip install tree-sitter tree-sitter-kotlin
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("kotlin")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_kotlin as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-kotlin")


class CognitiveComplexityCalculator:
    def __init__(self, src):
        self.src=src; self.p = create_parser(); self.tree=self.p.parse(bytes(src,"utf-8"))
        self.results=[]; self.details=[]
    def _t(self,n): return "" if n is None else self.src[n.start_byte:n.end_byte]
    def _l(self,n): return n.start_point[0]+1
    def _a(self,n,k,s,ne):
        l=self._l(n);t=s+ne
        self.details.append(f"  Line {l:>4}: +{t} ({k}: +{s} structural, +{ne} nesting)" if ne else f"  Line {l:>4}: +{t} ({k})")
    def _ar(self,d,i): self.details.append(f"          +{i} ({d})")

    def calculate(self):
        self.results=[]
        self._walk(self.tree.root_node)
        return self.results
    def _walk(self,node):
        for ch in node.children:
            if ch.type=="function_declaration": self._proc(ch)
            elif ch.type in ("class_declaration","object_declaration","interface_declaration"): self._wcls(ch)
    def _wcls(self,node):
        body=node.child_by_field_name("body")
        if body is None:
            for ch in node.children:
                if ch.type in ("class_body","enum_class_body"): body=ch; break
        if body is None: return
        for ch in body.children:
            if ch.type=="function_declaration": self._proc(ch)
            elif ch.type in ("class_declaration","object_declaration"): self._wcls(ch)
    def _proc(self,fn):
        nn=fn.child_by_field_name("name"); name=self._t(nn) if nn else "<anon>"
        self.details=[]
        # Kotlin: function_body -> block
        body=None
        for ch in fn.children:
            if ch.type=="function_body":
                for sub in ch.children:
                    if sub.type=="block": body=sub; break
                break
        c=self._vc(body,0) if body else 0
        self.results.append({"function":name,"complexity":c,"start_line":fn.start_point[0]+1,"end_line":fn.end_point[0]+1,"details":list(self.details)})

    def _vc(self,n,ne):
        t=0
        for ch in n.children: t+=self._v(ch,ne)
        return t
    def _v(self,n,ne):
        t=n.type
        if t=="if_expression": return self._hif(n,ne,True)
        if t in ("for_statement","while_statement"):
            self._a(n,t.split("_")[0],1,ne); c=1+ne
            body=n.child_by_field_name("body")
            if body: c+=self._vc(body,ne+1)
            return c
        if t=="do_while_statement":
            self._a(n,"do-while",1,ne); c=1+ne
            body=n.child_by_field_name("body")
            if body: c+=self._vc(body,ne+1)
            return c
        if t=="when_expression":
            self._a(n,"when",1,ne); c=1+ne
            for ch in n.children:
                if ch.type=="when_entry":
                    c+=self._vc(ch,ne+1)
            return c
        if t=="catch_block":
            self._a(n,"catch",1,ne); c=1+ne
            body=n.child_by_field_name("body")
            if body: c+=self._vc(body,ne+1)
            else: c+=self._vc(n,ne+1)
            return c
        if t=="try_expression": return self._vc(n,ne)
        if t=="finally_block":
            body=n.child_by_field_name("body")
            return self._vc(body,ne) if body else self._vc(n,ne)
        if t=="binary_expression": return self._hbin(n,ne)
        if t=="conjunction_expression":
            # a && b && c
            ops=[]; self._cops_kt(n,ops,"&&")
            if ops:
                c=0; prev=None
                for op in ops:
                    if prev is None or op!=prev: c+=1; self._ar(f"logical sequence \'{op}\'",1); prev=op
                return c
            return self._vc(n,ne)
        if t=="disjunction_expression":
            ops=[]; self._cops_kt(n,ops,"||")
            if ops:
                c=0; prev=None
                for op in ops:
                    if prev is None or op!=prev: c+=1; self._ar(f"logical sequence \'{op}\'",1); prev=op
                return c
            return self._vc(n,ne)
        if t=="lambda_literal":
            c=0
            for ch in n.children:
                if ch.type in ("statements","block"): c+=self._vc(ch,ne+1)
            return c
        if t=="parenthesized_expression": return self._vc(n,ne)
        return self._vc(n,ne)

    def _hif(self,n,ne,first):
        c=0
        if first: c+=1+ne; self._a(n,"if",1,ne)
        else: c+=1; self._a(n,"else if",1,0)
        # condition
        cond=n.child_by_field_name("condition")
        if cond: c+=self._v(cond,ne)
        # Find consequence and alternative by position
        # Children: if, (, cond, ), block, [else, if_expression/block]
        children=list(n.children)
        blocks=[]; saw_else=False
        for ch in children:
            if ch.type=="else": saw_else=True; continue
            if ch.type in ("block",) and not saw_else:
                c+=self._vc(ch,ne+1)
            elif saw_else:
                if ch.type=="if_expression": c+=self._hif(ch,ne,False)
                elif ch.type=="block": c+=1; self._a(ch,"else",1,0); c+=self._vc(ch,ne+1)
                saw_else=False
        return c

    def _hbin(self,n,ne):
        ops=[]; self._cops(n,ops)
        if not ops: return self._vc(n,ne)
        c=0; prev=None
        for op in ops:
            if prev is None or op!=prev: c+=1; self._ar(f"logical sequence \'{op}\'" if prev is None else f"logical change to \'{op}\'",1); prev=op
        return c
    def _cops(self,n,ops):
        if n.type!="binary_expression": return
        op=n.child_by_field_name("operator")
        if not op: return
        ot=self._t(op)
        if ot not in ("&&","||"): return
        left=n.child_by_field_name("left"); right=n.child_by_field_name("right")
        if left and left.type=="binary_expression":
            lo=left.child_by_field_name("operator")
            if lo and self._t(lo) in ("&&","||"): self._cops(left,ops)
        ops.append(ot)
        if right and right.type=="binary_expression":
            ro=right.child_by_field_name("operator")
            if ro and self._t(ro) in ("&&","||"): self._cops(right,ops)
    def _cops_kt(self,n,ops,op_val):
        # Kotlin conjunction/disjunction are separate node types, not binary_expression
        if n.type in ("conjunction_expression","disjunction_expression"):
            for ch in n.children:
                if ch.type in ("conjunction_expression","disjunction_expression"):
                    self._cops_kt(ch,ops,self._t(ch.children[1]) if len(ch.children)>1 else op_val)
            ops.append(op_val)

def calculate_file(fp):
    with open(fp,"r",encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code): return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    r=[]
    for root,_,files in os.walk(d):
        for f in sorted(files):
            if f.endswith((".kt",".kts")):
                p=os.path.join(root,f)
                try: res=calculate_file(p); [x.update(file=p) for x in res]; r.extend(res)
                except Exception as e: print(f"Error {p}: {e}")
    return r
def print_results(results, verbose=True):
    total=sum(r["complexity"] for r in results)
    for r in results:
        print(f"\n" + "="*60)
        if r.get("file"): print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose:
            for d in r.get("details",[]): print(d)
    print("\n" + "="*60 + f"\nTotal: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")