import os
import tempfile

from extractor.extractor import (
    build_zero_shot_prompt,
    build_few_shot_prompt,
    build_cot_prompt,
    chunk_text,
    extract_kdes,
    load_document,
    log_llm_output,
    save_yaml
)


def test_load_documents():
    # Test with existing files (assuming data exists)
    try:
        doc1 = load_document("data/cis-r1.pdf")
        assert len(doc1) > 0
    except FileNotFoundError:
        # If files don't exist, test error handling
        try:
            load_document("nonexistent.pdf")
            assert False, "Should raise FileNotFoundError"
        except FileNotFoundError:
            pass


def test_build_zero_shot_prompt():
    text = "Passwords must be 8 characters"
    prompt = build_zero_shot_prompt(text)
    assert isinstance(prompt, str)
    assert "JSON array" in prompt
    assert text in prompt
    assert "name" in prompt
    assert "requirements" in prompt


def test_build_few_shot_prompt():
    text = "Passwords must be 8 characters"
    prompt = build_few_shot_prompt(text)
    assert isinstance(prompt, str)
    assert "few shot" in prompt or "EXAMPLE" in prompt  # Based on content
    assert text in prompt
    assert "name" in prompt
    assert "requirements" in prompt


def test_build_cot_prompt():
    text = "Passwords must be 8 characters"
    prompt = build_cot_prompt(text)
    assert isinstance(prompt, str)
    assert "step-by-step" in prompt.lower() or "step 1" in prompt
    assert text in prompt
    assert "name" in prompt
    assert "requirements" in prompt


def test_chunking():
    text = "A" * 10000
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_extraction():
    # Test with mock data since LLM might not be available
    result, prompt, output = extract_kdes("Passwords must be 8 chars", build_zero_shot_prompt)
    assert isinstance(result, list)
    assert isinstance(prompt, str)
    assert isinstance(output, str)


def test_yaml_save():
    data = [{"name": "test", "requirements": ["req"]}]
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        filename = f.name
    try:
        save_yaml(data, filename)
        assert os.path.exists(filename)
        # Optionally, check content
        with open(filename, "r") as f:
            content = f.read()
            assert "name" in content
            assert "requirements" in content
    finally:
        os.unlink(filename)


def test_logging():
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        filename = f.name
    try:
        log_llm_output("test_llm", "test_prompt", "zero-shot", "test_output", filename)
        assert os.path.exists(filename)
        with open(filename, "r") as f:
            content = f.read()
            assert "*LLM Name*" in content
            assert "test_llm" in content
            assert "*Prompt Used*" in content
            assert "test_prompt" in content
            assert "*Prompt Type*" in content
            assert "zero-shot" in content
            assert "*LLM Output*" in content
            assert "test_output" in content
    finally:
        os.unlink(filename)