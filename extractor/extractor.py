import json
import re
import os
import torch
import yaml
from math import ceil
from PyPDF2 import PdfReader
from extractor.llm_utils import run_llm_batch
from extractor.utils import extract_json_block

# Input validation + loader
def load_document(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input file does not exist: {path}")

    try:
        reader = PdfReader(path)
        print(f"Loading {path}: {len(reader.pages)} pages")
        text = ""
        for i, page in enumerate(reader.pages):
            try:
                text += page.extract_text() or ""
            except Exception as e:
                print(f"Warning: Failed on page {i+1} of {path}: {e}")
        return text
    except Exception as e:
        print(f"Error loading PDF {path}: {e}")
        return ""

# Prompt Builders
def build_zero_shot_prompt(doc_text: str) -> str:
    return f"""
Extract key data elements (KDEs) from the security requirements text.

Return a JSON array of objects, where each object represents a KDE.

Each KDE object must have:
- "name": A short, descriptive name (2-5 words)
- "requirements": An array of short requirement phrases

Rules:
- Output only valid JSON
- No explanations or additional text
- Focus on security controls and requirements

Text:
{doc_text}
"""

def build_few_shot_prompt(doc_text: str) -> str:
    return f"""
Extract security controls from the text.

Return ONLY valid JSON.

STRICT RULES:
- Output MUST start with '[' and end with ']'
- Output MUST be valid JSON (parsable by json.loads)
- Do NOT include any text before or after JSON
- Do NOT include explanations or markdown

STRUCTURE:
[
  {{
    "name": "string",
    "requirements": ["string"]
  }}
]

NAME RULES:
- 2–5 words ONLY
- lowercase ONLY
- NO sentences
- NO commands (curl, kubectl, etc.)
- NO URLs or variables
- MUST summarize (do NOT copy raw text)

REQUIREMENTS RULES:
- Short phrases
- No commands or long text

EXAMPLE:

Input:
"Ensure that the kubelet streaming connection idle timeout is not set to 0. Use configuration file or API."

Output:
[
  {{
    "name": "kubelet timeout configuration",
    "requirements": [
      "set streaming connection idle timeout",
      "ensure value is not zero"
    ]
  }}
]

EXTRACTION RULE:
- Extract the SECURITY CONTROL, not commands or examples

Text:
{doc_text}
"""

def build_cot_prompt(doc_text: str) -> str:
    return f"""
Extract key data elements (KDEs) from the security requirements text using step-by-step reasoning.

For each potential KDE, think through:
1. Is this a security control or requirement?
2. What is the core security principle?
3. What are the specific requirements?
4. How can I summarize this concisely?

Return ONLY a JSON array of KDE objects.

Each KDE object must have:
- "name": A short, descriptive name (2-5 words)
- "requirements": An array of short requirement phrases

Example reasoning (do not output this):
Text: "Ensure that the kubelet streaming connection idle timeout is not set to 0. Use configuration file or API."
Step 1: This is a security control about connection timeouts.
Step 2: Core principle is preventing idle connections.
Step 3: Requirements are setting timeout > 0, using config file or API.
Step 4: Name: "kubelet timeout configuration"

Output:
[
  {{
    "name": "kubelet timeout configuration",
    "requirements": [
      "set streaming connection idle timeout",
      "ensure value is not zero"
    ]
  }}
]

Rules:
- Output only valid JSON
- No explanations or reasoning in output
- Focus on security controls only

Text:
{doc_text}
"""

# Text preprocessing
def filter_relevant_text(doc_text: str) -> str:
    """
    Filter obvious junk but keep most meaningful text.
    """
    if not doc_text:
        return ""

    lines = []

    junk_keywords = [
        "table of contents",
        "appendix",
        "change history",
        "acknowledgements",
        "terms of use",
        "page",
    ]

    for line in doc_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Skip lines that match junk keywords
        if any(keyword.lower() in stripped.lower() for keyword in junk_keywords):
            continue

        # Skip lines that are mostly symbols (like --- or ===)
        if sum(c.isalnum() for c in stripped) / max(len(stripped), 1) < 0.3:
            continue

        # Keep everything else
        lines.append(stripped)

    # Fallback: if filtering removed everything, keep the original text
    if not lines:
        return doc_text.strip()

    return "\n".join(lines)


def clean_json(text: str) -> str:
    if not text:
        return ""

    text = text.strip()

    # remove code blocks
    if "```" in text:
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text

    # remove leading junk before JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    return text.strip()


def chunk_text(text: str, chunk_size: int = 1800, overlap: int = 100):

    if not text:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(text[start:end])

        # Move start forward but keep overlap
        start += chunk_size - overlap

    return chunks

# KDE Extraction
def extract_kdes(doc_text: str, prompt_fn, filename: str = ""):
    """
    Extract KDEs using JSON-first parsing, then convert to YAML-safe structure.
    """

    print(f"Original length: {len(doc_text)}")

    # Special handling for cis-r4.pdf - less aggressive filtering
    if "cis-r4" in filename.lower():
        print("[INFO] Detected cis-r4.pdf - using minimal filtering")
        filtered_text = doc_text.strip()
    else:
        print("[FILTER] Filtering text...")
        filtered_text = filter_relevant_text(doc_text)
    
    print(f"Filtered length: {len(filtered_text)}")

    if not filtered_text.strip():
        print("[WARN] Filter removed everything, falling back to raw text.")
        filtered_text = doc_text

    if not filtered_text.strip():
        print("[EMPTY] Document text is empty. Skipping extraction.")
        return [], "", ""

    chunks = chunk_text(filtered_text, chunk_size=800, overlap=50)
    batch_size = 16

    def batch_chunks(chunks, size):
        for i in range(0, len(chunks), size):
            yield chunks[i:i + size]

    all_kdes = []
    all_outputs = []
    last_prompt = ""

    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for batch_idx, chunk_batch in enumerate(batch_chunks(chunks, batch_size)):
        print(f"Processing batch {batch_idx+1}/{total_batches} ({len(chunk_batch)} chunks)...")

        prompts = []
        for chunk in chunk_batch:
            prompt = prompt_fn(chunk)
            if prompt.strip():
                prompts.append(prompt)
                last_prompt = prompt
            else:
                prompts.append(None)

        valid_prompts = [p for p in prompts if p is not None]

        # Run batch
        
        try:
            token_limit = 128
            outputs = run_llm_batch(valid_prompts, max_new_tokens=token_limit)
        except RuntimeError as e:
            if "CUDA" in str(e):
                print(f"[GPU] CUDA error on batch {batch_idx+1}, retrying on CPU...")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                try:
                    outputs = run_llm_batch(valid_prompts, use_cpu=True)
                except Exception as e2:
                    print(f"[ERROR] CPU retry failed for batch {batch_idx+1}: {e2}")
                    continue
            else:
                print(f"[ERROR] Runtime error on batch {batch_idx+1}: {e}")
                continue
        except Exception as e:
            print(f"[SKIP] Skipping bad batch {batch_idx+1}: {e}")
            continue

        # Process each chunk independently
        valid_iter = iter(outputs)

        for i, prompt in enumerate(prompts):
            chunk_num = batch_idx * batch_size + i + 1

            if prompt is None:
                continue

            try:
                raw_output = next(valid_iter)
            except StopIteration:
                print(f"[WARN] Output mismatch in chunk {chunk_num}")
                continue

            if len(raw_output) < 20:
                continue

            if "{" not in raw_output and "[" not in raw_output:
                continue

            if len(raw_output) > 3000:
                print(f"[WARN] Output too large in chunk {chunk_num}, skipping")
                continue

            if not raw_output or not raw_output.strip():
                print(f"[WARN] Empty output for chunk {chunk_num}")
                continue

            # CLEAN JSON (not YAML anymore)
            cleaned = raw_output.strip()
            cleaned = cleaned.replace("```json", "").replace("```", "")
            cleaned = extract_json_block(cleaned)

            if not cleaned.strip().startswith("["):
                match = re.search(r"\[.*\]", raw_output, re.DOTALL)
                if match:
                    cleaned = match.group(0)

            parsed = None

            # Try JSON parse
            try:
                parsed = json.loads(cleaned)

            except json.JSONDecodeError:
                print(f"[WARN] JSON parse error in chunk {chunk_num}, attempting recovery...")

                fixed = cleaned

                # basic fixes
                fixed = fixed.replace("'", '"')
                fixed = re.sub(r",\s*]", "]", fixed)  # trailing commas

                try:
                    parsed = json.loads(fixed)
                except:
                    continue

            
            # Normalize structure
            
            if isinstance(parsed, dict):
                parsed = [parsed]

            if not isinstance(parsed, list):
                print(f"[WARN] Invalid JSON structure in chunk {chunk_num}")
                continue

            all_outputs.append(cleaned)

            
            # Normalize KDEs
            
            for item in parsed:
                if not isinstance(item, dict):
                    continue

                name = item.get("name")
                reqs = item.get("requirements")

                # Normalize
                if isinstance(name, int):
                    name = str(name)

                if isinstance(reqs, str):
                    reqs = [reqs]

                if reqs is None:
                    reqs = []

                if not isinstance(reqs, list):
                    continue

                if name:
                    all_kdes.append({
                        "name": str(name).strip(),
                        "requirements": [
                            str(r).strip()[:120]   # trim long garbage
                            for r in reqs
                            if r and str(r).strip() not in ["None", "(none)"]
                        ]
                    })

    full_output = "\n".join(all_outputs)

    def is_valid_kde(name):
        if not name:
            return False

        # length filter
        if len(name.split()) > 6:
            return False

        bad_patterns = [
            "curl", "kubectl", "http", "${", "systemctl",
            "proxy/configz", "api/v1", "localhost"
        ]

        return not any(p in name.lower() for p in bad_patterns)

    all_kdes = [k for k in all_kdes if is_valid_kde(k["name"])]

    # Final cleanup
    final_kdes = clean_kdes(all_kdes)
    return final_kdes, last_prompt, full_output


def clean_kdes(kdes):
    """
    Normalize and deduplicate KDEs safely.
    Skips any malformed entries.
    """
    final = []
    seen = set()

    for item in kdes:
        # Only process dicts with name & requirements
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        reqs = item.get("requirements")
        if not isinstance(name, str) or not isinstance(reqs, list):
            continue

        name_norm = name.strip().lower()
        reqs_norm = [str(r).strip() for r in reqs if r is not None]

        # Deduplicate
        key = (name_norm, tuple(reqs_norm))
        if key in seen:
            continue
        seen.add(key)

        final.append({
            "name": name_norm,
            "requirements": reqs_norm
        })

    return final

# Save YAML
def save_yaml(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)

# Logging
def log_llm_output(llm_name, prompt, prompt_type, output, file_path):
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"""
*LLM Name*
{llm_name}

*Prompt Used*
{prompt}

*Prompt Type*
{prompt_type}

*LLM Output*
{output}

----------------------------------------
""")