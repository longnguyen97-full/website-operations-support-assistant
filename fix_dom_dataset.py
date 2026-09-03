import json
from pathlib import Path

METADATA_FILE = Path("d:/LAB/do-an-tot-nghiep/dataset/metadata.json")
SITES_DIR = Path("d:/LAB/do-an-tot-nghiep/dataset/sites")

with open(METADATA_FILE, encoding="utf-8") as f:
    meta = json.load(f)

fixed = 0
for m in meta:
    if m.get("fault_category") == "MISSING_DOM":
        sid = m["site_id"]
        html_file = SITES_DIR / sid / "public" / "index.html"
        if not html_file.exists():
            continue
        html = html_file.read_text(encoding="utf-8")
        tpl = m.get("base_template", "")

        # Only inject if not already injected
        if "REMOVED" not in html and "display:none" not in html.replace(" ", ""):
            if "ecommerce" in tpl and 'id="checkout-btn"' in html:
                html = html.replace('<button id="checkout-btn"', '<!-- REMOVED BUTTON --><button id="checkout-btn" style="display:none;" disabled')
                fixed += 1
            elif "dashboard" in tpl and 'id="add-user-btn"' in html:
                html = html.replace('<button id="add-user-btn"', '<!-- REMOVED BUTTON --><button id="add-user-btn" style="display:none;" disabled')
                fixed += 1
            elif "blog" in tpl and 'class="nav-menu"' in html:
                html = html.replace('<nav class="nav-menu"', '<!-- REMOVED NAV --><nav class="nav-menu" style="display:none;"')
                fixed += 1
            html_file.write_text(html, encoding="utf-8")

print(f"[✓] Đã bổ sung chính xác kịch bản thiếu DOM cho {fixed} website!")
