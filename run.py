import argparse
import os
import sys
import pandas as pd
from extractor.extractor import (
    load_documents,
    build_zero_shot_prompt,
    build_few_shot_prompt,
    build_cot_prompt,
    extract_kdes,
    save_yaml,
    log_llm_output
)
from extractor.comparator import compare_names, compare_full
from extractor.executor import (
    load_comparison_files,
    determine_differences_and_map,
    execute_kubescape,
    generate_csv
)

DEFAULT_INPUTS = [
    ("data/cis-r1.pdf", "data/cis-r1.pdf"),
    ("data/cis-r1.pdf", "data/cis-r2.pdf"),
    ("data/cis-r1.pdf", "data/cis-r3.pdf"),
    ("data/cis-r1.pdf", "data/cis-r4.pdf"),
    ("data/cis-r2.pdf", "data/cis-r2.pdf"),
    ("data/cis-r2.pdf", "data/cis-r3.pdf"),
    ("data/cis-r2.pdf", "data/cis-r4.pdf"),
    ("data/cis-r3.pdf", "data/cis-r3.pdf"),
    ("data/cis-r3.pdf", "data/cis-r4.pdf"),
]

PROMPTS = {
    "zero-shot": build_zero_shot_prompt,
    "few-shot": build_few_shot_prompt,
    "cot": build_cot_prompt,
}

DEFAULT_PROJECT_YAMLS = "project-yamls.zip"


def normalize_path(path: str) -> str:
    return os.path.normpath(path)


def parse_input_pairs_file(path: str):
    pairs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if "|" in raw:
                left, right = raw.split("|", 1)
            elif "," in raw:
                left, right = raw.split(",", 1)
            else:
                parts = raw.split()
                if len(parts) != 2:
                    raise ValueError(f"Invalid pair line: {raw}")
                left, right = parts
            pairs.append((normalize_path(left.strip()), normalize_path(right.strip())))
    return pairs


def build_input_pairs(args):
    if args.pairs_file:
        return parse_input_pairs_file(args.pairs_file)

    if args.pairs:
        if len(args.pairs) % 2 != 0:
            raise ValueError("--pairs requires an even number of file paths")
        return [
            (normalize_path(args.pairs[i]), normalize_path(args.pairs[i + 1]))
            for i in range(0, len(args.pairs), 2)
        ]

    return DEFAULT_INPUTS


def ensure_directories(output_dir: str):
    os.makedirs(os.path.join(output_dir, "yaml"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "comparisons"), exist_ok=True)


def preload_documents(input_pairs):
    loaded_docs = {}
    for file_path in sorted({f for pair in input_pairs for f in pair}):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Input file does not exist: {file_path}")
        loaded_docs[file_path] = load_documents(file_path, file_path)[0]
    return loaded_docs


def process_pairs(input_pairs, output_dir: str, project_yamls: str, skip_kubescape: bool):
    ensure_directories(output_dir)
    loaded_docs = preload_documents(input_pairs)

    print("Starting document processing...")
    start_time = pd.Timestamp.now()

    for file1, file2 in input_pairs:
        doc1 = loaded_docs[file1]
        doc2 = loaded_docs[file2]

        for name, prompt_fn in PROMPTS.items():
            parsed1, prompt1, output1 = extract_kdes(doc1, prompt_fn, file1)
            parsed2, prompt2, output2 = extract_kdes(doc2, prompt_fn, file2)

            base1 = os.path.basename(file1).replace(".pdf", "")
            base2 = os.path.basename(file2).replace(".pdf", "")
            yaml1 = os.path.join(output_dir, "yaml", f"{base1}-{name}-kdes.yaml")
            yaml2 = os.path.join(output_dir, "yaml", f"{base2}-{name}-kdes.yaml")

            if parsed1:
                save_yaml(parsed1, yaml1)
            if parsed2:
                save_yaml(parsed2, yaml2)

            if os.path.exists(yaml1) and os.path.exists(yaml2):
                compare_names(yaml1, yaml2, os.path.join(output_dir, "comparisons", f"{base1}_{base2}_{name}_names.txt"))
                compare_full(yaml1, yaml2, os.path.join(output_dir, "comparisons", f"{base1}_{base2}_{name}_full.txt"))

            if prompt1 and output1:
                log_llm_output("Gemma-3-1B", prompt1, name, output1, os.path.join(output_dir, "logs", "llm_logs.txt"))
            if prompt2 and output2:
                log_llm_output("Gemma-3-1B", prompt2, name, output2, os.path.join(output_dir, "logs", "llm_logs.txt"))

            names_file = os.path.join(output_dir, "comparisons", f"{base1}_{base2}_{name}_names.txt")
            full_file = os.path.join(output_dir, "comparisons", f"{base1}_{base2}_{name}_full.txt")
            log_file = os.path.join(output_dir, "logs", "llm_logs.txt")

            if os.path.exists(names_file) and os.path.exists(full_file):
                files = load_comparison_files(names_file, full_file, log_file)
                controls_file = determine_differences_and_map(files["names"], files["full"])

                if skip_kubescape:
                    print("Skipping Kubescape execution as requested.")
                elif os.path.exists(project_yamls):
                    df = execute_kubescape(controls_file, project_yamls)
                    csv_file = generate_csv(df, os.path.join(output_dir, f"kubescape_{base1}_{base2}_{name}_results.csv"))
                    print(f"Generated CSV: {csv_file}")
                else:
                    print(f"{project_yamls} not found, skipping Kubescape execution")

    end_time = pd.Timestamp.now()
    print(f"Processing completed in {end_time - start_time}")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Run PDF KDE extraction, comparison, and optional Kubescape evaluation."
    )
    parser.add_argument(
        "--pairs",
        nargs="+",
        help="Nine pairs of PDF paths: file1 file2 file3 file4 ..."
    )
    parser.add_argument(
        "--pairs-file",
        help="Path to a file containing one pair per line, separated by |, comma, or whitespace."
    )
    parser.add_argument(
        "--project-yamls",
        default=DEFAULT_PROJECT_YAMLS,
        help="Zip archive containing YAML files for Kubescape evaluation."
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Output directory root."
    )
    parser.add_argument(
        "--skip-kubescape",
        action="store_true",
        help="Skip Kubescape execution and only run extraction/comparison steps."
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    try:
        input_pairs = build_input_pairs(args)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if not input_pairs:
        print("Error: No PDF pairs were provided.")
        sys.exit(1)

    process_pairs(input_pairs, args.output_dir, args.project_yamls, args.skip_kubescape)


if __name__ == "__main__":
    main()