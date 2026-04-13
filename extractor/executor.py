import ast
import os
import pandas as pd
import subprocess
import json
import tempfile
import zipfile
from extractor.llm_utils import run_llm_batch  # Assuming this is available for mapping

def parse_controls_text(raw_text):
    """Parse a raw controls file string into a list of control names."""
    raw_text = raw_text.strip()
    if not raw_text or raw_text == "NO DIFFERENCES FOUND":
        return []
    # Handle Python list-like or JSON list-like strings
    try:
        parsed = ast.literal_eval(raw_text)
        if isinstance(parsed, (list, tuple)):
            return [str(item).strip() for item in parsed if item is not None and str(item).strip()]
    except (ValueError, SyntaxError):
        pass
    # Fallback: parse one control per line
    controls = []
    for line in raw_text.splitlines():
        line = line.strip()
        if line:
            controls.append(line)
    return controls

# Function 1: Load the three TEXT files from Task-2
def load_comparison_files(names_file, full_file, log_file=None):
    """
    Load the comparison TEXT files.
    Assumes names_file and full_file are the two main comparison files.
    log_file is optional.
    """
    files = {}
    for name, path in [("names", names_file), ("full", full_file), ("log", log_file)]:
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                files[name] = f.read().strip()
        else:
            files[name] = None
    return files

# Function 2: Determine differences and map to Kubescape controls
def determine_differences_and_map(names_content, full_content, kubescape_controls_file="kubescape_controls.json"):
    """
    Check if there are differences in the two TEXT files.
    If differences, map to Kubescape controls using LLM or pattern matching.
    Output a TEXT file with controls or 'NO DIFFERENCES FOUND'.
    """
    # Check for differences
    has_differences = False
    if names_content and "NO DIFFERENCES" not in names_content:
        has_differences = True
    if full_content and "NO DIFFERENCES" not in full_content:
        has_differences = True

    if not has_differences:
        output_content = "NO DIFFERENCES FOUND"
    else:
        # Extract differences from content
        differences = extract_differences(names_content, full_content)
        # Map to Kubescape controls
        controls = map_to_kubescape_controls(differences, kubescape_controls_file)
        output_content = "\n".join(controls) if controls else "NO DIFFERENCES FOUND"

    # Write to TEXT file
    output_file = "kubescape_controls_to_run.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output_content)
    return output_file

def extract_differences(names_content, full_content):
    """Extract difference descriptions from the content."""
    differences = []
    if names_content:
        lines = names_content.split('\n')
        for line in lines:
            if line.strip() and not line.startswith("Names in") and not line.startswith("NO DIFFERENCES"):
                differences.append(line.strip())
    if full_content:
        lines = full_content.split('\n')
        for line in lines:
            if "requirements:" in line:
                differences.append(line.strip())
    return differences

def map_to_kubescape_controls(differences, controls_file):
    """Map differences to Kubescape controls using LLM."""
    if not differences:
        return []

    # Load known controls if file exists
    controls = []
    if os.path.exists(controls_file):
        with open(controls_file, 'r') as f:
            controls = json.load(f)

    # Use LLM to map
    prompt = f"""
    Map the following security differences to Kubescape control names.
    Differences: {differences}
    Known Kubescape controls: {controls}
    Return a list of matching control names, one per line.
    """
    response = run_llm_batch([prompt])[0]
    mapped_controls = [line.strip() for line in response.split('\n') if line.strip()]
    return mapped_controls

# Function 3: Execute Kubescape and return DataFrame
def execute_kubescape(controls_file, yaml_zip_path="project-yamls.zip"):
    """
    Run Kubescape on the YAML files based on controls_file.
    Return pandas DataFrame with scan results.
    """
    # Unzip if necessary
    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(yaml_zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Read controls
        controls = []
        if os.path.exists(controls_file):
            with open(controls_file, 'r', encoding='utf-8') as f:
                content = f.read()
                controls = parse_controls_text(content)

        # Build command - always scan all, filter results later
        cmd = ["kubescape", "scan", temp_dir, "--format", "json"]

        # Run command
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Kubescape failed: {result.stderr}")

        # Parse JSON output
        scan_data = json.loads(result.stdout)
        if not scan_data.get("results") and scan_data.get("controls"):
            scan_data = {
                "results": [{
                    "resourceID": "",
                    "controls": scan_data.get("controls", [])
                }],
                "summaryDetails": scan_data.get("summaryDetails", {})
            }

        summary_controls = scan_data.get("summaryDetails", {}).get("controls", {})

        # Extract relevant data into DataFrame
        # Kubescape returns results as a list of resources, each with controls
        rows = []
        available_control_names = set()
        for result_item in scan_data.get("results", []):
            for control in result_item.get("controls", []):
                control_name = control.get("name", "")
                if control_name:
                    available_control_names.add(control_name)

        if controls:
            valid_controls = [c for c in controls if c in available_control_names]
            if valid_controls:
                controls = valid_controls
            else:
                controls = []

        for result_item in scan_data.get("results", []):
            resource_id = result_item.get("resourceID", "")
            for control in result_item.get("controls", []):
                control_name = control.get("name", "")
                control_id = control.get("controlID")

                # Only include if specific controls were requested and matched
                if controls and control_name not in controls:
                    continue
                
                # Determine if control failed
                status = control.get("status", {})
                if isinstance(status, dict):
                    control_status = status.get("status", "")
                else:
                    control_status = str(status)

                compliance_score = 0
                if control_id and control_id in summary_controls:
                    compliance_score = summary_controls[control_id].get("complianceScore", 0)
                else:
                    compliance_score = control.get("complianceScore", 0)
                
                rows.append({
                    "FilePath": resource_id,
                    "Severity": control.get("severity", ""),
                    "Control name": control_name,
                    "Failed resources": 1 if control_status == "failed" else 0,
                    "All Resources": 1,
                    "Compliance score": compliance_score
                })
        
        df = pd.DataFrame(rows)
        return df

# Function 4: Generate CSV from DataFrame
def generate_csv(df, output_csv="kubescape_results.csv"):
    """
    Generate CSV file with specified headers from DataFrame.
    """
    df.to_csv(output_csv, index=False)
    return output_csv