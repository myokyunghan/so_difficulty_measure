"""
Tree-sitter Parser Loader
===========================
tree-sitter-language-pack을 우선 사용하고,
없으면 개별 언어 패키지로 fallback합니다.

설치 (둘 중 하나만 있으면 됨):
  pip install tree-sitter-language-pack    # 추천: 248개 언어 한 번에
  또는
  pip install tree-sitter-python tree-sitter-java ...  # 개별 설치

사용법:
  from parser_loader import get_parser
  parser = get_parser("python")
  tree = parser.parse(b"def hello(): pass")
"""

from tree_sitter import Parser

# tree-sitter-language-pack의 언어 이름 매핑
_PACK_NAMES = {
    "python": "python", "javascript": "javascript", "java": "java",
    "c#": "c_sharp", "c++": "cpp", "c": "c", "r": "r",
    "php": "php", "swift": "swift", "kotlin": "kotlin",
    "dart": "dart", "typescript": "typescript", "go": "go",
    "ruby": "ruby", "rust": "rust", "scala": "scala",
    "julia": "julia", "matlab": "matlab", "groovy": "groovy",
    "objective-c": "objc", "vb.net": "vb", "assembly": "asm",
    "haskell": "haskell", "delphi": "pascal", "lua": "lua",
    "perl": "perl", "prolog": "prolog", "fortran": "fortran",
    "f#": "fsharp", "solidity": "solidity",
}

# 개별 패키지 fallback 매핑: (module_name, init_function)
_INDIVIDUAL_PACKAGES = {
    "python": ("tree_sitter_python", "language"),
    "javascript": ("tree_sitter_javascript", "language"),
    "java": ("tree_sitter_java", "language"),
    "c#": ("tree_sitter_c_sharp", "language"),
    "c++": ("tree_sitter_cpp", "language"),
    "c": ("tree_sitter_c", "language"),
    "r": ("tree_sitter_r", "language"),
    "php": ("tree_sitter_php", "language_php"),
    "swift": ("tree_sitter_swift", "language"),
    "kotlin": ("tree_sitter_kotlin", "language"),
    "dart": ("tree_sitter_dart", "language"),
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "go": ("tree_sitter_go", "language"),
    "ruby": ("tree_sitter_ruby", "language"),
    "rust": ("tree_sitter_rust", "language"),
    "scala": ("tree_sitter_scala", "language"),
    "julia": ("tree_sitter_julia", "language"),
    "matlab": ("tree_sitter_matlab", "language"),
    "groovy": ("tree_sitter_groovy", "language"),
    "objective-c": ("tree_sitter_objc", "language"),
    "vb.net": ("tree_sitter_vb", "language"),
    "assembly": ("tree_sitter_asm", "language"),
    "haskell": ("tree_sitter_haskell", "language"),
    "delphi": ("tree_sitter_pascal", "language"),
    "lua": ("tree_sitter_lua", "language"),
    "perl": ("tree_sitter_perl", "language"),
    "prolog": ("tree_sitter_prolog", "language"),
    "fortran": ("tree_sitter_fortran", "language"),
    "f#": ("tree_sitter_fsharp", "language"),
    "solidity": ("tree_sitter_solidity", "language"),
}

# 캐시
_parsers = {}
_has_language_pack = None


def _check_language_pack():
    global _has_language_pack
    if _has_language_pack is None:
        try:
            from tree_sitter_language_pack import get_parser as _gp
            _has_language_pack = True
        except ImportError:
            _has_language_pack = False
    return _has_language_pack


def get_parser(lang: str) -> Parser:
    """
    언어에 맞는 tree-sitter Parser를 반환합니다.
    
    1순위: tree-sitter-language-pack (pip install tree-sitter-language-pack)
    2순위: 개별 tree-sitter 패키지 (pip install tree-sitter-python 등)
    
    Args:
        lang: 언어 이름 (예: "python", "java", "c++", "c#", "objective-c" 등)
    
    Returns:
        tree_sitter.Parser 객체
    
    Raises:
        ImportError: 해당 언어의 파서를 찾을 수 없을 때
    """
    if lang in _parsers:
        return _parsers[lang]

    parser = None

    # 1순위: tree-sitter-language-pack
    if _check_language_pack():
        pack_name = _PACK_NAMES.get(lang, lang)
        try:
            from tree_sitter_language_pack import get_parser as _pack_get_parser
            parser = _pack_get_parser(pack_name)
            _parsers[lang] = parser
            return parser
        except Exception:
            pass  # fallback to individual package

    # 2순위: 개별 패키지
    if lang in _INDIVIDUAL_PACKAGES:
        mod_name, init_func = _INDIVIDUAL_PACKAGES[lang]
        try:
            import importlib
            from tree_sitter import Language
            mod = importlib.import_module(mod_name)
            lang_obj = Language(getattr(mod, init_func)())
            parser = Parser(lang_obj)
            _parsers[lang] = parser
            return parser
        except (ImportError, ModuleNotFoundError):
            pass

    raise ImportError(
        f"No tree-sitter parser found for '{lang}'. Install one of:\n"
        f"  pip install tree-sitter-language-pack    (recommended, 248 languages)\n"
        f"  pip install {_INDIVIDUAL_PACKAGES.get(lang, ('tree-sitter-' + lang,))[0].replace('_', '-')}"
    )


def is_available(lang: str) -> bool:
    """해당 언어의 파서를 사용할 수 있는지 확인"""
    try:
        get_parser(lang)
        return True
    except ImportError:
        return False


def available_languages() -> list:
    """사용 가능한 언어 목록 반환"""
    return [lang for lang in _PACK_NAMES if is_available(lang)]