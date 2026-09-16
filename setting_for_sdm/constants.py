class CONSTANTS:
    verbose_loading = False
    all_topics_list = list(range(0, 50))

    languages_from2020to2022=[  "python",   "javascript",   "java",     "c#",       "c++",
                                "c",        "r",            "php",      "swift",    "kotlin",
                                "dart",     "typescript",   "go",       "ruby",     "rust",
                                "scala",    "julia",        "matlab",   "groovy",   "objective-c",
                                "vb.net",   "assembly",     "haskell",  "delphi",   "lua",
                                "perl",     "prolog",       "fortran",  "f#",       "solidity"]

    LANG_INFO = {
        # lizard 지원 언어
        'python':      ('py',    'python'),
        'javascript':  ('js',    'javascript'),
        'java':        ('java',  'java'),
        'c#':          ('cs',    'csharp'),
        'c++':         ('cpp',   'cpp'),
        'c':           ('c',     'c'),
        'r':           ('r',     'r'),
        'php':         ('php',   'php'),
        'swift':       ('swift', 'swift'),
        'kotlin':      ('kt',    'kotlin'),
        'typescript':  ('ts',    'typescript'),
        'go':          ('go',    'go'),
        'ruby':        ('rb',    'ruby'),
        'rust':        ('rs',    'rust'),
        'scala':       ('scala', 'scala'),
        'objective-c': ('m',     'objectivec'),
        'lua':         ('lua',   'lua'),
        'perl':        ('pl',    'perl'),
        'fortran':     ('f90',   'fortran'),
        'solidity':    ('sol',   'solidity'),
        
        'dart':        ('dart',   None),
        'julia':       ('jl',     None),
        'matlab':      ('m',      None), 
        'groovy':      ('groovy', None),
        'vb.net':      ('vb',     None),
        'assembly':    ('asm',    None),
        'haskell':     ('hs',     None),
        'delphi':      ('pas',    None),
        'prolog':      ('pl',     None), 
        'f#':          ('fs',     None),
    }

    RCA_SUPPORTED_LANGS = {
    "python":     "py",
    "javascript": "js",
    "typescript": "ts",
    "c++":        "cpp",
    "c":          "c",
    "rust":       "rs",
    }

    CYCLOMATIC_COMPLEXITY_SUPPORTED_LANGS = {
        'python':      'py',    
        'javascript':  'js',    
        'java':        'java',  
        'c#':          'cs',    
        'c++':         'cpp',   
        'c':           'c',     
        'r':           'r',     
        'php':         'php',   
        'swift':       'swift', 
        'kotlin':      'kt',    
        'typescript':  'ts',    
        'go':          'go',    
        'ruby':        'rb',    
        'rust':        'rs',    
        'scala':       'scala', 
        'objective-c': 'm',     
        'lua':         'lua',   
        'perl':        'pl',    
        'fortran':     'f90',   
        'solidity':    'sol',   
    }

    COGNITIVE_COMPLEXITY_SUPPORTED_LANGS = {
        # lizard 지원 언어
        'python':      'py',    
        'javascript':  'js',    
        'java':        'java',  
        'c#':          'cs',    
        'c++':         'cpp',   
        'c':           'c',     
        'r':           'r',     
        'php':         'php',   
        'swift':       'swift', 
        'kotlin':      'kt',    
        'typescript':  'ts',    
        'go':          'go',    
        'ruby':        'rb',    
        'rust':        'rs',    
        'scala':       'scala', 
        'objective-c': 'm',     
        'lua':         'lua',   
        'perl':        'pl',    
        'fortran':     'f90',   
        'solidity':    'sol',   
        'dart':        'dart',  
        'julia':       'jl',    
        'matlab':      'm',     
        'groovy':      'groovy',
        'vb.net':      'vb',    
        'assembly':    'asm',   
        'haskell':     'hs',    
        'delphi':      'pas',   
        'prolog':      'pl',    
        'f#':          'fs',    
    }


    # src_extend = {
    #     'python'      : 'py',
    #     'javascript'  : 'js',
    #     'java'        : 'java',
    #     'c#'          : 'cs',
    #     'c++'         : 'cpp',
    #     'c'           : 'c',
    #     'r'           : 'r',
    #     'php'         : 'php',
    #     'swift'       : 'swift',
    #     'kotlin'      : 'kt',
    #     'dart'        : 'dart',
    #     'typescript'  : 'ts',
    #     'go'          : 'go',
    #     'ruby'        : 'rb',
    #     'rust'        : 'rs',
    #     'scala'       : 'scala',
    #     'julia'       : 'jl',  
    #     'matlab'      : 'm',    
    #     'groovy'      : 'groovy',   
    #     'objective-c' : 'm',
    #     'vb.net'      : 'vb',
    #     'assembly'    : 'asm',
    #     'haskell'     : 'hs', 
    #     'delphi'      : 'pas',    
    #     'lua'         : 'lua',    
    #     'perl'        : 'pl',     
    #     'prolog'      : 'pl',       
    #     'fortran'     : 'f90',
    #     'f#'          : 'fs',       
    #     'solidity'    : 'sol',      
    # }
    

    
    codebert_languages = ["python", "java", "javascript", "php", "ruby", "go"]

    language_map = {
        "python": "Python",
        "javascript": "JavaScript",
        "java": "Java",
        "c#": "C#",
        "c++": "C++",

        "c": "C",
        "r": "R",
        "php": "PHP",
        "swift": "Swift",
        "kotlin": "Kotlin",

        "dart": "Dart",
        "typescript": "TypeScript",
        "go": "Go",
        "ruby": "Ruby",
        "rust": "Rust",

        "scala": "Scala",
        "julia": "Julia",
        "matlab": "MATLAB",
        "groovy": "Groovy",
        "objective-c": "Objective-C",

        "vb.net": "Visual Basic .NET",
        "assembly": "Assembly",
        "haskell": "Haskell",

        # CSV에 Delphi라는 값은 없음
        "delphi": None,

        "lua": "Lua",
        "perl": "Perl",
        "prolog": "Prolog",
        "fortran": "Fortran",
        "f#": "F#",
        "solidity": "Solidity"
    }
    
    DIFF_DICT = {'Difficulty Level : Basic':        '<Difficulty Level>0</Difficulty Level>' ,
            'Difficulty Level : Intermediate':  '<Difficulty Level>1</Difficulty Level>', 
            'Difficulty Level : Advanced':      '<Difficulty Level>2</Difficulty Level>'}

