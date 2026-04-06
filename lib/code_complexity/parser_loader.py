
from lib.code_complexity.cognitive_complexity_for_c import (
    create_parser as create_c_parser,
    calculate_file as calculate_file_for_c
)
from lib.code_complexity.cognitive_complexity_for_cpp import (
    create_parser as create_cpp_parser,
    calculate_file as calculate_file_for_cpp
)
from lib.code_complexity.cognitive_complexity_for_csharp import (
    create_parser as create_csharp_parser,
    calculate_file as calculate_file_for_csharp
)
from lib.code_complexity.cognitive_complexity_for_fortran import (
    create_parser as create_fortran_parser,
    calculate_file as calculate_file_for_fortran
)
from lib.code_complexity.cognitive_complexity_for_java import (
    create_parser as create_java_parser,
    calculate_file as calculate_file_for_java
)
from lib.code_complexity.cognitive_complexity_for_javascript import (
    create_parser as create_javascript_parser,
    calculate_file as calculate_file_for_javascript
)
from lib.code_complexity.cognitive_complexity_for_python import (
    create_parser as create_python_parser,
    calculate_file as calculate_file_for_python
)
from lib.code_complexity.cognitive_complexity_for_r import (
    create_parser as create_r_parser,
    calculate_file as calculate_file_for_r
)
from lib.code_complexity.cognitive_complexity_for_rust import (
    create_parser as create_rust_parser,
    calculate_file as calculate_file_for_rust
)

# ── 추가된 21개 언어 ──
from lib.code_complexity.cognitive_complexity_for_php import (
    create_parser as create_php_parser,
    calculate_file as calculate_file_for_php
)
from lib.code_complexity.cognitive_complexity_for_swift import (
    create_parser as create_swift_parser,
    calculate_file as calculate_file_for_swift
)
from lib.code_complexity.cognitive_complexity_for_kotlin import (
    create_parser as create_kotlin_parser,
    calculate_file as calculate_file_for_kotlin
)
from lib.code_complexity.cognitive_complexity_for_dart import (
    create_parser as create_dart_parser,
    calculate_file as calculate_file_for_dart
)
from lib.code_complexity.cognitive_complexity_for_typescript import (
    create_parser as create_typescript_parser,
    calculate_file as calculate_file_for_typescript
)
from lib.code_complexity.cognitive_complexity_for_go import (
    create_parser as create_go_parser,
    calculate_file as calculate_file_for_go
)
from lib.code_complexity.cognitive_complexity_for_ruby import (
    create_parser as create_ruby_parser,
    calculate_file as calculate_file_for_ruby
)
from lib.code_complexity.cognitive_complexity_for_scala import (
    create_parser as create_scala_parser,
    calculate_file as calculate_file_for_scala
)
from lib.code_complexity.cognitive_complexity_for_julia import (
    create_parser as create_julia_parser,
    calculate_file as calculate_file_for_julia
)
from lib.code_complexity.cognitive_complexity_for_matlab import (
    create_parser as create_matlab_parser,
    calculate_file as calculate_file_for_matlab
)
from lib.code_complexity.cognitive_complexity_for_groovy import (
    create_parser as create_groovy_parser,
    calculate_file as calculate_file_for_groovy
)
from lib.code_complexity.cognitive_complexity_for_objective_c import (
    create_parser as create_objective_c_parser,
    calculate_file as calculate_file_for_objective_c
)
from lib.code_complexity.cognitive_complexity_for_vbnet import (
    create_parser as create_vbnet_parser,
    calculate_file as calculate_file_for_vbnet
)
from lib.code_complexity.cognitive_complexity_for_assembly import (
    create_parser as create_assembly_parser,
    calculate_file as calculate_file_for_assembly
)
from lib.code_complexity.cognitive_complexity_for_haskell import (
    create_parser as create_haskell_parser,
    calculate_file as calculate_file_for_haskell
)
from lib.code_complexity.cognitive_complexity_for_delphi import (
    create_parser as create_delphi_parser,
    calculate_file as calculate_file_for_delphi
)
from lib.code_complexity.cognitive_complexity_for_lua import (
    create_parser as create_lua_parser,
    calculate_file as calculate_file_for_lua
)
from lib.code_complexity.cognitive_complexity_for_perl import (
    create_parser as create_perl_parser,
    calculate_file as calculate_file_for_perl
)
from lib.code_complexity.cognitive_complexity_for_prolog import (
    create_parser as create_prolog_parser,
    calculate_file as calculate_file_for_prolog
)
from lib.code_complexity.cognitive_complexity_for_fsharp import (
    create_parser as create_fsharp_parser,
    calculate_file as calculate_file_for_fsharp
)
from lib.code_complexity.cognitive_complexity_for_solidity import (
    create_parser as create_solidity_parser,
    calculate_file as calculate_file_for_solidity
)

CALC_FUNC = {
    'python':       calculate_file_for_python,
    'javascript':   calculate_file_for_javascript,
    'java':         calculate_file_for_java,
    'c#':           calculate_file_for_csharp,
    'c++':          calculate_file_for_cpp,
    'c':            calculate_file_for_c,
    'r':            calculate_file_for_r,
    'php':          calculate_file_for_php,
    'swift':        calculate_file_for_swift,
    'kotlin':       calculate_file_for_kotlin,
    'dart':         calculate_file_for_dart,
    'typescript':   calculate_file_for_typescript,
    'go':           calculate_file_for_go,
    'ruby':         calculate_file_for_ruby,
    'rust':         calculate_file_for_rust,
    'scala':        calculate_file_for_scala,
    'julia':        calculate_file_for_julia,
    'matlab':       calculate_file_for_matlab,
    'groovy':       calculate_file_for_groovy,
    'objective-c':  calculate_file_for_objective_c,
    'vb.net':       calculate_file_for_vbnet,
    'assembly':     calculate_file_for_assembly,
    'haskell':      calculate_file_for_haskell,
    'delphi':       calculate_file_for_delphi,
    'lua':          calculate_file_for_lua,
    'perl':         calculate_file_for_perl,
    'prolog':       calculate_file_for_prolog,
    'fortran':      calculate_file_for_fortran,
    'f#':           calculate_file_for_fsharp,
    'solidity':     calculate_file_for_solidity,
}

CALC_PARSER = {
    'python':       create_python_parser,
    'javascript':   create_javascript_parser,
    'java':         create_java_parser,
    'c#':           create_csharp_parser,
    'c++':          create_cpp_parser,
    'c':            create_c_parser,
    'r':            create_r_parser,
    'php':          create_php_parser,
    'swift':        create_swift_parser,
    'kotlin':       create_kotlin_parser,
    'dart':         create_dart_parser,
    'typescript':   create_typescript_parser,
    'go':           create_go_parser,
    'ruby':         create_ruby_parser,
    'rust':         create_rust_parser,
    'scala':        create_scala_parser,
    'julia':        create_julia_parser,
    'matlab':       create_matlab_parser,
    'groovy':       create_groovy_parser,
    'objective-c':  create_objective_c_parser,
    'vb.net':       create_vbnet_parser,
    'assembly':     create_assembly_parser,
    'haskell':      create_haskell_parser,
    'delphi':       create_delphi_parser,
    'lua':          create_lua_parser,
    'perl':         create_perl_parser,
    'prolog':       create_prolog_parser,
    'fortran':      create_fortran_parser,
    'f#':           create_fsharp_parser,
    'solidity':     create_solidity_parser,
}