import os

files_to_export = [
    'walkie.py',
    'indexer.py',
    'token_lint.py',
    'tests/test_patching.py',
    'tests/test_loop.py',
    '.agents/skills/ai_consult/SKILL.md',
    '.agents/skills/llm_loop/SKILL.md'
]

output_dir = 'export_for_review'
os.makedirs(output_dir, exist_ok=True)
for f in os.listdir(output_dir):
    os.remove(os.path.join(output_dir, f))

full_content = []
for filepath in files_to_export:
    if os.path.exists(filepath):
        full_content.append(f'\n\n### FILE: {filepath} ###\n')
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                full_content.append(f'{i+1:04d}: {line.rstrip()}')

chunk_size = 400
chunks = [full_content[i:i + chunk_size] for i in range(0, len(full_content), chunk_size)]

for i, chunk in enumerate(chunks):
    chunk_text = '\n'.join(chunk)
    out_path = os.path.join(output_dir, f'codebase_part_{i+1}.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(chunk_text)

print(f'Exported {len(chunks)} chunks with line numbers.')
