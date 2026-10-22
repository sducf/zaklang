import argparse
import json
import urllib.request
from pathlib import Path

SPEC_PATH = Path("spec/zak-core-v0.1.md")
PROMPT_PATH = Path("zakbench/prompts/zak_prompt.txt")
LIMIT = 1200


def extract_sections(text):
    spec = text.split("## zak_spec", 1)[1].split(
        "## zak_examples", 1
    )[0].strip()

    examples = text.split("## zak_examples", 1)[1].strip()

    return spec, examples


def count_tokens(endpoint, content):
    payload = json.dumps({
        "content": content,
        "add_special": False,
    }).encode("utf-8")

    request = urllib.request.Request(
        endpoint.rstrip("/") + "/tokenize",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    return len(result["tokens"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model-id", required=True)
    args = parser.parse_args()

    text = SPEC_PATH.read_text(encoding="utf-8")
    template = PROMPT_PATH.read_text(encoding="utf-8")

    spec, examples = extract_sections(text)

    if "{{zak_spec}}" not in template:
        raise ValueError("Missing zak_spec placeholder")

    if "{{zak_examples}}" not in template:
        raise ValueError("Missing zak_examples placeholder")

    # Measure the language reference as inserted into ZakBench.
    reference = (
        "Zak Language Specification:\n"
        + spec
        + "\n\nZak Examples:\n"
        + examples
    )

    count = count_tokens(args.endpoint, reference)

    print(f"Model ID: {args.model_id}")
    print(f"Reference tokens: {count}")
    print(f"Token limit: {LIMIT}")
    print("PASS" if count < LIMIT else "FAIL")

    if count >= LIMIT:
        raise SystemExit(1)


if __name__ == "__main__":
    main()