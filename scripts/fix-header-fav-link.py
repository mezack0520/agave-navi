#!/usr/bin/env python3
"""Fix header fav-link in all event HTML pages.

Replaces the old <a href="/listing.html" class="fav-link"> block
with the new <a href="../ikitai.html" class="ikitai-blob-btn"> block.
Also updates the JS reference from favCount to ikitaiBadge.
"""

import glob
import re

OLD_LINK = r'<a href="/listing\.html" class="fav-link" id="favLink">\s*<span class="fav-icon">.*?</span>\s*\u884c\u304d\u305f\u3044\s*<span class="fav-count" id="favCount">0</span>\s*</a>'

NEW_LINK = """<div class="header-actions">
      <a href="../ikitai.html" class="ikitai-blob-btn" id="ikitaiBlobBtn">
        <span class="blob-bg"></span>
        <svg class="ikitai-heart" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        <span class="ikitai-label">\u884c\u304d\u305f\u3044</span>
        <span class="ikitai-badge" id="ikitaiBadge"></span>
      </a>
    </div>"""

files = glob.glob("events/*.html")
fixed = 0

for f in files:
    with open(f, "r", encoding="utf-8") as fh:
        html = fh.read()

    new_html, count = re.subn(OLD_LINK, NEW_LINK, html, flags=re.DOTALL)

    if count > 0:
        # Also fix JS: getElementById('favCount') -> getElementById('ikitaiBadge')
        new_html = new_html.replace("getElementById('favCount')", "getElementById('ikitaiBadge')")
        new_html = new_html.replace('getElementById("favCount")', 'getElementById("ikitaiBadge")')
        # Fix .innerText = favs.length -> .textContent = favs.length || ''
        new_html = new_html.replace(".innerText = favs.length", ".textContent = favs.length || ''")

        with open(f, "w", encoding="utf-8") as fh:
            fh.write(new_html)
        fixed += 1
        print(f"Fixed: {f}")
    else:
        print(f"Skipped (no match): {f}")

print(f"\nDone. Fixed {fixed} files.")
