import re

with open('config.json', 'r', encoding='utf-8') as f:
    text = f.read()

lines = text.split('\n')
out_lines = []
for line in lines:
    clean_line = line.strip()
    if clean_line == '{' or clean_line == '}':
        continue
    if '"target_urls":' in clean_line:
        out_lines.append("target_urls:")
        continue
    if '"keywords":' in clean_line:
        out_lines.append("keywords:")
        continue
    if clean_line in (']', '],'):
        continue
        
    if not clean_line:
        continue
        
    is_commented = clean_line.startswith('//')
    
    m = re.search(r'"([^"]+)"', clean_line)
    if m:
        val = m.group(1)
        prefix = "# - " if is_commented else "- "
        out_lines.append(f"  {prefix}\"{val}\"")

with open('config.yml', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines) + '\n')
