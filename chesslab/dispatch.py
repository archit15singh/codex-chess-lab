"""Resolve an actor brief completely before starting its dispatch clock."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from .position_trial import launch, write_new


def dispatch(directory, template, runtime, python):
    directory = directory.resolve(strict=True)
    manifest = json.loads((directory / 'manifest.json').read_text())
    for field in ('desired_model', 'desired_reasoning'):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            raise ValueError('model and effort required before dispatch clock starts')
    python = python.absolute()  # Preserve a venv executable's path through symlinks.
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError('executable Python required before dispatch clock starts')
    dispatcher_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    text = template.read_text()
    if text.startswith('PRIVATE TEMPLATE ONLY.'):
        text = text.split('\n', 1)[1]
    values = {'CHOSEN_UCI_MOVE': '<your UCI choice>', 'TRIAL_ID': directory.name,
              'PNG_ABSOLUTE_PATH': manifest['image_path'],
              'PLAYER_JSON_ABSOLUTE_PATH': manifest['player_path'],
              'EXACT_ATTACHMENT_PATHS_OR_NONE': str(directory / 'attachment.json'),
              'TRIAL_DIRECTORY_ABSOLUTE_PATH': str(directory),
              'INITIAL_RESPONSE_ABSOLUTE_PATH': str(directory / 'initial-response.json'),
              'FINAL_RESPONSE_ABSOLUTE_PATH': str(directory / 'final-response.json'),
              'PYTHON_ABSOLUTE_PATH': str(python.absolute()),
              'SUBMISSION_RUNTIME_ABSOLUTE_PATH': str(runtime.resolve(strict=True))}
    times = {'LAUNCH_RECORDED_AT_UTC', 'DEADLINE_UTC'}
    tokens = set(re.findall(r'\{\{([^{}]+)\}\}', text))
    if tokens - values.keys() - times:
        raise ValueError('unresolved brief placeholders; dispatch clock not started')
    if not times <= tokens:
        raise ValueError('brief requires launch time and deadline; dispatch clock not started')
    if (directory / 'actor-brief.txt').exists() or (directory / 'dispatch.json').exists():
        raise FileExistsError('actor dispatch already prepared')
    frozen = json.loads((runtime / 'manifest.json').read_text())['files']
    for relative, expected in frozen.items():
        if hashlib.sha256((runtime / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('submission snapshot changed')
    if frozen.get('chesslab/position_trial.py') != manifest['source_sha256']:
        raise ValueError('submission snapshot differs from prepared mechanics')
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    checked = text
    for key in times:
        checked = checked.replace('{{' + key + '}}', '')
    if '{{' in checked:
        raise ValueError('incomplete brief placeholder; dispatch clock not started')
    launched = launch(directory)
    text = text.replace('{{LAUNCH_RECORDED_AT_UTC}}', launched['dispatch_requested_at'])
    text = text.replace('{{DEADLINE_UTC}}', launched['deadline'])
    brief = directory / 'actor-brief.txt'
    with brief.open('x') as stream:
        stream.write(text)
    record = {'brief': str(brief), 'brief_sha256': hashlib.sha256(text.encode()).hexdigest(),
              'deadline': launched['deadline'], 'desired_model': manifest['desired_model'],
              'desired_reasoning': manifest['desired_reasoning'],
              'dispatcher_sha256': dispatcher_sha}
    write_new(directory / 'dispatch.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--template', required=True, type=Path)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--python', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(dispatch(args.directory, args.template, args.runtime, args.python), indent=2))


if __name__ == '__main__':
    main()
