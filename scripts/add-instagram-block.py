#!/usr/bin/env python3
"""Add Instagram block to detail pages for events with Instagram sourceUrls."""

import json
import re
from pathlib import Path

REPO = Path(__file__).parent.parent
EVENTS_JSON = REPO / "events.json"
EVENTS_DIR = REPO / "events"

IG_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>'

IG_SVG_SMALL = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>'

def extract_ig_handle(url):
    """Extract Instagram handle from URL."""
    m = re.search(r'instagram\.com/([^/?]+)', url)
    return m.group(1) if m else None

def make_ig_block(ig_url, handle):
    """Create the Instagram HTML block."""
    return f'''                <div class="detail-instagram-card">
                    <h3>{IG_SVG_SMALL} 公式Instagram</h3>
                    <a href="{ig_url}" target="_blank" rel="noopener" class="instagram-account-link">
                        {IG_SVG}
                        <span class="ig-gradient">@{handle}</span>
                    </a>
                </div>'''

def main():
    with open(EVENTS_JSON, 'r', encoding='utf-8') as f:
        events = json.load(f)
    
    ig_events = {}
    for ev in events:
        src = ev.get('sourceUrl', '')
        if 'instagram.com' in src:
            handle = extract_ig_handle(src)
            if handle:
                ig_events[ev['slug']] = (src, handle)
    
    print(f"Found {len(ig_events)} events with Instagram sourceUrls")
    
    added = 0
    skipped = 0
    for slug, (ig_url, handle) in ig_events.items():
        html_path = EVENTS_DIR / f"{slug}.html"
        if not html_path.exists():
            print(f"  SKIP (no HTML): {slug}")
            skipped += 1
            continue
        
        html = html_path.read_text(encoding='utf-8')
        
        # Check if already has instagram block
        if 'detail-instagram-card' in html:
            print(f"  SKIP (already has): {slug}")
            skipped += 1
            continue
        
        ig_block = make_ig_block(ig_url, handle)
        
        # Insert after the detail-info-card closing div (</div> after gcal-btn)
        # Find the sidebar section and insert after the info card
        # Look for the pattern: </div>\n                \n\n            </div> (end of info-card, then end of sidebar)
        
        # Strategy: Insert before the closing </div> of detail-sidebar
        # Find: </div>\n\n            <div class="affiliate-section"
        pattern = r'(</div>\s*\n\s*\n\s*</div>\s*\n\s*<div class="affiliate-section")'
        match = re.search(pattern, html)
        if match:
            replacement = f'</div>\n{ig_block}\n\n            </div>\n\n            <div class="affiliate-section"'
            html = html[:match.start()] + replacement + html[match.end():]
            html_path.write_text(html, encoding='utf-8')
            print(f"  ADDED: {slug} (@{handle})")
            added += 1
        else:
            # Try alternative pattern
            # Look for </div> right before </div> and <div class="affiliate-section"
            alt_pattern = r'(</div>\s*</div>\s*<div class="affiliate-section")'
            match2 = re.search(alt_pattern, html)
            if match2:
                replacement = f'</div>\n{ig_block}\n            </div>\n\n            <div class="affiliate-section"'
                html = html[:match2.start()] + replacement + html[match2.end():]
                html_path.write_text(html, encoding='utf-8')
                print(f"  ADDED (alt): {slug} (@{handle})")
                added += 1
            else:
                print(f"  FAILED (no pattern): {slug}")
                skipped += 1
    
    print(f"\nDone: {added} added, {skipped} skipped")

if __name__ == '__main__':
    main()
