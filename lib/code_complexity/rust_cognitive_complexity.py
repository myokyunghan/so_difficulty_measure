import os
import json
import subprocess

import pandas as pd
import numpy as np

from lib.utils.file_io import open_src, save_jsonl
import lib.code_complexity.parser_loader as ps


CALC_PARSER = ps.CALC_PARSER  # syntax 검증용

# rust-code-analysis-cli 바이너리 경로
# 설치: 
#   wget https://github.com/mozilla/rust-code-analysis/releases/download/v0.0.25/rust-code-analysis-linux-cli-x86_64.tar.gz
#   tar -xzf rust-code-analysis-linux-cli-x86_64.tar.gz
RCA_CLI = "/mnt/hdd/mghan/so_difficulty_measure/rust-code-analysis-cli"


def _run_rca(file_path):
    """rust-code-analysis-cli를 실행해 JSON 결과를 받아옴."""
    try:
        proc = subprocess.run(
            [RCA_CLI, "-m", "-p", file_path, "-O", "json"],
            capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return None


def _safe_get(d, *keys, default=None):
    """중첩된 dict에서 안전하게 값 추출"""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key)
        if d is None:
            return default
    return d


def _extract_function_metrics(node, results, parent_name=None, in_function=False):
    """RCA의 spaces 트리를 재귀 탐색하며 최상위 함수/메서드만 수집.
    중첩 함수는 부모의 cognitive.sum에 이미 포함되므로 스킵.
    """
    kind = node.get("kind", "")
    name = node.get("name", "<unknown>")
    is_function = kind in ("function", "method")
    
    # 함수 컨텍스트 밖에 있는 함수만 수집 (중첩 클로저/inner 함수 제외)
    if is_function and not in_function:
        metrics = node.get("metrics", {})
        results.append({
            "function_name":         name,
            "parent":                parent_name,
            "kind":                  kind,
            "start_line":            node.get("start_line"),
            "end_line":              node.get("end_line"),
            "cognitive_complexity":  _safe_get(metrics, "cognitive", "sum"),
            "cyclomatic_complexity": _safe_get(metrics, "cyclomatic", "sum"),
            "sloc":                  _safe_get(metrics, "loc", "sloc"),
            "ploc":                  _safe_get(metrics, "loc", "ploc"),
            "lloc":                  _safe_get(metrics, "loc", "lloc"),
            "cloc":                  _safe_get(metrics, "loc", "cloc"),
            "blank":                 _safe_get(metrics, "loc", "blank"),
            "halstead_volume":       _safe_get(metrics, "halstead", "volume"),
            "halstead_difficulty":   _safe_get(metrics, "halstead", "difficulty"),
            "halstead_effort":       _safe_get(metrics, "halstead", "effort"),
            "halstead_bugs":         _safe_get(metrics, "halstead", "bugs"),
            "mi_original":           _safe_get(metrics, "mi", "mi_original"),
            "mi_sei":                _safe_get(metrics, "mi", "mi_sei"),
        })
    
    # 자식으로 내려갈 때 컨텍스트 갱신
    if kind == "class":
        next_parent = name
        next_in_function = in_function
    elif is_function:
        next_parent = name
        next_in_function = True
    else:
        next_parent = parent_name
        next_in_function = in_function
    
    for child in node.get("spaces", []):
        _extract_function_metrics(child, results, next_parent, next_in_function)


def call_rust_cognitive_complexity(file, lang, save_dir_for_src, save_dir_for_jsonl):
    file_path = f"{save_dir_for_src}/{file}"
    name      = os.path.basename(file_path)
    new_nm    = os.path.splitext(name)[0]
    new_file  = f"{new_nm}.jsonl"
    
    if not check_code(file_path, lang):
        return False
    
    rca_output = _run_rca(file_path)
    if rca_output is None:
        return False
    
    # 파일 전체 메트릭
    file_metrics = rca_output.get("metrics", {})
    file_summary = {
        "n_functions_total":   _safe_get(file_metrics, "nom", "functions"),
        "n_closures_total":    _safe_get(file_metrics, "nom", "closures"),
        "file_cognitive_sum":  _safe_get(file_metrics, "cognitive", "sum"),
        "file_cognitive_avg":  _safe_get(file_metrics, "cognitive", "average"),
        "file_cognitive_max":  _safe_get(file_metrics, "cognitive", "max"),
        "file_cyclomatic_sum": _safe_get(file_metrics, "cyclomatic", "sum"),
        "file_sloc":           _safe_get(file_metrics, "loc", "sloc"),
        "file_ploc":           _safe_get(file_metrics, "loc", "ploc"),
        "file_mi":             _safe_get(file_metrics, "mi", "mi_original"),
    }
    
    # 함수 단위 메트릭 수집
    func_metrics = []
    _extract_function_metrics(rca_output, func_metrics)
    
    # Fallback: 함수가 하나도 없으면 파일 전체를 한 행으로 처리
    # (top-level 스크립트, expression-only 스니펫 등)
    if not func_metrics:
        top_cog = _safe_get(file_metrics, "cognitive", "sum")
        if top_cog is None:
            return False  # 메트릭 자체를 못 뽑은 경우만 실패
        
        func_metrics = [{
            "function_name":         "<file_level>",
            "parent":                None,
            "kind":                  "unit",
            "start_line":            rca_output.get("start_line"),
            "end_line":              rca_output.get("end_line"),
            "cognitive_complexity":  top_cog,
            "cyclomatic_complexity": _safe_get(file_metrics, "cyclomatic", "sum"),
            "sloc":                  _safe_get(file_metrics, "loc", "sloc"),
            "ploc":                  _safe_get(file_metrics, "loc", "ploc"),
            "lloc":                  _safe_get(file_metrics, "loc", "lloc"),
            "cloc":                  _safe_get(file_metrics, "loc", "cloc"),
            "blank":                 _safe_get(file_metrics, "loc", "blank"),
            "halstead_volume":       _safe_get(file_metrics, "halstead", "volume"),
            "halstead_difficulty":   _safe_get(file_metrics, "halstead", "difficulty"),
            "halstead_effort":       _safe_get(file_metrics, "halstead", "effort"),
            "halstead_bugs":         _safe_get(file_metrics, "halstead", "bugs"),
            "mi_original":           _safe_get(file_metrics, "mi", "mi_original"),
            "mi_sei":                _safe_get(file_metrics, "mi", "mi_sei"),
        }]
    
    # 함수 단위 + 파일 요약 결합
    rows = [
        {
            "path":      file_path,
            "file_name": name,
            "language":  lang,
            **func_info,
            **file_summary,
        }
        for func_info in func_metrics
    ]
    
    save_jsonl(rows, f"{save_dir_for_jsonl}/{new_file}")
    return True


def check_code(file_path, lang):
    """syntax error 체크. RCA는 syntax error를 명시 안 함 → tree-sitter로 보조 검증."""
    if lang == "assembly":
        return True
    if lang not in CALC_PARSER:
        return True

    code = open_src(file_path)
    parser = CALC_PARSER[lang]()
    try:
        parser.timeout_micros = 5_000_000
    except (AttributeError, TypeError):
        pass

    try:
        tree = parser.parse(bytes(code, "utf-8"))
    except ValueError:
        return False

    return not tree.root_node.has_error


def calculate_cognitive_complexity(df, option_str):
    df["cognitive_complexity"] = np.log(df["cognitive_complexity"] + 1)

    if option_str == "mean":
        return df.groupby("id", as_index=False)["cognitive_complexity"].mean()
    elif option_str == "max":
        return df.groupby("id", as_index=False)["cognitive_complexity"].max()
    elif option_str == "std":
        return df.groupby("id", as_index=False)["cognitive_complexity"].std()
    elif option_str == "sum":
        return df.groupby("id", as_index=False)["cognitive_complexity"].sum()
    else:
        raise ValueError(f"Invalid option_str: {option_str}")