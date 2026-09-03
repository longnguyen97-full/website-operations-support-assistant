import re
from pathlib import Path

SITES_DIR = Path("d:/LAB/do-an-tot-nghiep/dataset/sites")
fixed = 0

for server_file in SITES_DIR.glob("*/server.js"):
    content = server_file.read_text(encoding="utf-8")
    if "while(Date.now()" in content or "while (Date.now()" in content:
        # Match pattern: const start = Date.now(); while(...) { ... } next();
        new_content = re.sub(
            r"const start = Date\.now\(\);\s*while\s*\(Date\.now\(\)\s*-\s*start\s*<\s*(\d+)\)\s*\{[^}]*\}\s*next\(\);",
            r"setTimeout(next, \1);",
            content
        )
        if new_content != content:
            server_file.write_text(new_content, encoding="utf-8")
            fixed += 1

print(f"Fixed {fixed} server.js files from blocking while-loops to non-blocking setTimeout!")
