# Prompts for KDE Extraction

## Zero-Shot Prompt

```
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
```

## Few-Shot Prompt

```
Extract security controls from the text.

Return ONLY valid JSON.

STRICT RULES:
- Output MUST start with '[' and end with ']'
- Output MUST be valid JSON (parsable by json.loads)
- Do NOT include any text before or after JSON
- Do NOT include explanations or markdown

STRUCTURE:
[
  {
    "name": "string",
    "requirements": ["string"]
  }
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
  {
    "name": "kubelet timeout configuration",
    "requirements": [
      "set streaming connection idle timeout",
      "ensure value is not zero"
    ]
  }
]

EXTRACTION RULE:
- Extract the SECURITY CONTROL, not commands or examples

Text:
{doc_text}
```

## Chain-of-Thought Prompt

```
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
  {
    "name": "kubelet timeout configuration",
    "requirements": [
      "set streaming connection idle timeout",
      "ensure value is not zero"
    ]
  }
]

Rules:
- Output only valid JSON
- No explanations or reasoning in output
- Focus on security controls only

Text:
{doc_text}
```