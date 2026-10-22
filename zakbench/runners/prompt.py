"""Build benchmark prompts from task.json and the templates in zakbench/prompts/.

Only task.json is read. hidden_tests.json never reaches a prompt.
"""

import json
from pathlib import Path
import re

from spec.count_tokens import extract_sections

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'zakbench' / 'tasks'
PROMPTS = ROOT / 'zakbench' / 'prompts'
SPECS = ROOT / 'spec'

# The templates in zakbench/prompts/ are version 1. Bump this when they change.
PROMPT_VERSION = '1'

TASK_ID = re.compile(r'[a-z0-9_]+\Z')
FENCE = re.compile(r'```[^\n]*\n(.*?)```', re.DOTALL)
LANGUAGE_NAMES = {'zak': 'Zak', 'python': 'Python'}


def load_task(task_id):
    """Read the model-visible task definition. Raises ValueError for an unknown id."""
    path = TASKS / task_id / 'task.json'
    if not TASK_ID.fullmatch(task_id) or not path.is_file():
        raise ValueError(f'unknown task: {task_id}')
    return json.loads(path.read_text(encoding='utf-8'))


def build_prompt(task, language, spec_version=None):
    """Fill the language's template. Both languages get the same task fields."""
    if language == 'zak':
        spec_path = SPECS / f'zak-core-v{spec_version}.md'
        if spec_version is None or not spec_path.is_file():
            raise ValueError(f'unknown Zak spec version: {spec_version}')
        spec, examples = extract_sections(spec_path.read_text(encoding='utf-8'))
        template = (PROMPTS / 'zak_prompt.txt').read_text(encoding='utf-8')
        template = template.replace('{{zak_spec}}', spec).replace('{{zak_examples}}', examples)
    elif language == 'python':
        template = (PROMPTS / 'python_prompt.txt').read_text(encoding='utf-8')
    else:
        raise ValueError("language must be 'zak' or 'python'")

    inputs = '\n'.join(f"{item['name']}: {item['type']}" for item in task['inputs']) or 'none'
    fields = {
        'task_prompt': task['prompt'],
        'function_name': task['functionName'],
        'inputs': inputs,
        'output_type': task['outputType'],
    }
    for name, value in fields.items():
        template = template.replace('{{' + name + '}}', value)
    return template


def repair_prompt(language, feedback):
    """Follow-up message after a failed attempt, worded the same for both languages."""
    return (f'Your previous solution did not pass.\n\n{feedback}\n\n'
            f'Write the corrected solution in {LANGUAGE_NAMES[language]}.\n\n'
            'Return only the code required to solve the task.\n'
            'Do not include explanations or Markdown.\n')


def extract_code(completion):
    """Take the first fenced code block if the model used one, otherwise the whole reply."""
    match = FENCE.search(completion)
    return (match.group(1) if match else completion).strip()
