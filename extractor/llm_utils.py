from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

from extractor.utils import extract_json_block

MODEL_NAME = "google/gemma-3-1b-it"

# Cache per device
_model_cache = {}

# Faster tensor ops on GPU
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True


def load_model_for_device(device: str):
    """
    Load model separately for each device (CPU/GPU).
    """
    if device in _model_cache:
        return _model_cache[device]

    print(f"[MODEL] Loading model on {device}...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.padding_side = "left" 
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float16 if device == "cuda" else torch.float32,
    ).to(device)

    model.eval()

    _model_cache[device] = (tokenizer, model)
    return tokenizer, model


def run_llm_batch(prompts, use_cpu: bool = False, max_new_tokens: int = 128):
    import torch

    device = "cpu" if use_cpu or not torch.cuda.is_available() else "cuda"
    tokenizer, model = load_model_for_device(device)

    try:
        inputs = tokenizer(
            prompts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=2048
        ).to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                repetition_penalty=1.05,
                pad_token_id=tokenizer.pad_token_id,
                max_time=30.0,  # stop long-running calls
            )

        # Slice the outputs to remove the prompt tokens
        new_tokens = outputs[:, inputs["input_ids"].shape[-1]:]
        decoded_outputs = tokenizer.batch_decode(new_tokens, skip_special_tokens=True)

        # Clean outputs
        cleaned_outputs = []
        for out in decoded_outputs:
            cleaned = extract_json_block(out)
            if cleaned.strip():
                cleaned_outputs.append(cleaned)
            else:
                cleaned_outputs.append(out.strip())

        return cleaned_outputs

    except (RuntimeError, KeyboardInterrupt) as e:
        if "CUDA" in str(e) and device == "cuda":
            print("[WARN] CUDA failure in batch, retrying on CPU...")
            torch.cuda.empty_cache()
            return run_llm_batch(prompts, use_cpu=True, max_new_tokens=max_new_tokens)
        print(f"[WARN] LLM call failed or timed out: {e}")
        raise