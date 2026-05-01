#!/usr/bin/env python3
"""
Rebuild the event cards and JSON-LD in index.html from events.json
This script:
1. Reads events.json
2. Separates events into upcoming and past based on status
3. Regenerates event cards for both sections
4. Updates the JSON-LD structured data
5. Updates event counts
6. Preserves all other HTML unchanged
"""

import json
import re
from datetime import datetime
import os
import sys

def load_events_json(json_file):
    """Load and parse events.json"""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_date_display(event):
    """Format date for display in the card"""
    if 'dateDisplay' in event and event['dateDisplay']:
        return event['dateDisplay']

    date = event['date']
    if 'dateEnd' in event and event['dateEnd'] and event['dateEnd'] != event['date']:
        return f"{date.replace('-', '.')}-{event['dateEnd'].split('-')[2]}"
    return date.replace('-', '.')

def get_region_display(event):
    """Get region display name for the card"""
    return event.get('prefecture', '')

def generate_tags_html(tags):
    """Generate HTML for event tags"""
    if not tags:
        return ''
    tag_html = '\n                            '.join(
        f'<span class="tag">{tag}</span>' for tag in tags[:3]
    )
    return f'\n                            {tag_html}'

def generate_event_card(event):
    """Generate a single event card HTML"""
    slug = event['slug']
    tags = ','.join(event.get('tags', []))
    status = event.get('status', 'upcoming')
    region = event.get('region', '')
    pref = event.get('prefecture', '')
    date = event['date']
    date_end = event.get('dateEnd', '')
    date_display = format_date_display(event)

    # Build data attributes
    data_attrs = [
        f'data-tags="{tags}"' if tags else '',
        f'data-status="{status}"',
        f'data-region="{region}"' if region else '',
        f'data-pref="{pref}"' if pref else '',
        f'data-date="{date}"',
    ]
    if date_end:
        data_attrs.append(f'data-date-end="{date_end}"')
    added_date = event.get('addedDate', '')
    if added_date:
        data_attrs.append(f'data-added-date="{added_date}"')
    data_attrs.append(f'data-slug="{slug}"')

    data_str = ' '.join([d for d in data_attrs if d])

    # Generate thumbnail HTML - check for imageUrl
    image_url = event.get('imageUrl', '')
    if image_url:
        thumb_html = f'<img src="{image_url}" alt="{event["name"]}" class="event-thumb" loading="lazy" onerror="this.outerHTML=\'<div class=&quot;event-thumb event-no-image&quot;></div>\'">'
    else:
        thumb_html = '<div class="event-thumb event-no-image"></div>'

    # Build the card (entire card is clickable via data-slug; no inner detail link)
    card_html = f'''<div class="event-card" {data_str}>
                        {thumb_html}
                        <button class="fav-btn" onclick="toggleFav(event, '{slug}')" aria-label="行きたい">
                            <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                        </button>
                        <div class="swipe-hint"><div class="swipe-hint-icon"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></div></div>
                        <div class="event-card-body">
                        <div class="event-header">
                            <span class="event-date">{date_display}</span>
                            <span class="event-status"></span>
                        </div>
                        <h3 class="event-title">{event['name']}</h3>
                        <p class="event-description">{event.get('description', '')}</p>
                        <div class="event-meta-row">
                            <span class="event-region">{get_region_display(event)}</span>
                        </div>
                        </div>
                                            <div class="card-fav-bar" onclick="event.stopPropagation()"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg><span>行きたい</span></div>
</div>
'''
    return card_html

def generate_past_event_card(event):
    """Generate a past event card (with event-ended class)"""
    slug = event['slug']
    date_display = format_date_display(event)

    # Generate thumbnail HTML - check for imageUrl
    image_url = event.get('imageUrl', '')
    if image_url:
        thumb_html = f'<img src="{image_url}" alt="{event["name"]}" class="event-thumb" loading="lazy" onerror="this.outerHTML=\'<div class=&quot;event-thumb event-no-image&quot;></div>\'">'
    else:
        thumb_html = '<div class="event-thumb event-no-image"></div>'

    card_html = f'''<div class="event-card event-ended" data-slug="{slug}" onclick="window.location.href='events/{slug}.html'" style="cursor:pointer">
                        {thumb_html}
                        <button class="fav-btn" onclick="toggleFav(event, '{slug}')" aria-label="行きたい">
                            <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                        </button>
                        <div class="swipe-hint"><div class="swipe-hint-icon"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></div></div>
                        <div class="event-card-body">
                        <div class="event-header">
                            <span class="event-date">{date_display}</span>
                            <span class="event-status"></span>
                        </div>
                        <h3 class="event-title">{event['name']}</h3>
                        <p class="event-description">{event.get('description', '')}</p>
                        <div class="event-meta-row">
                            <span class="event-region">{get_region_display(event)}</span>
                        </div>
                        </div>
                                            <div class="card-fav-bar" onclick="event.stopPropagation()"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg><span>行きたい</span></div>
</div>
'''
    return card_html

def generate_jsonld_schema(upcoming_events):
    """Generate JSON-LD structured data"""
    items = []
    for i, event in enumerate(upcoming_events[:100], 1):  # Limit to 100 items for schema.org
        item = {
            "@type": "ListItem",
            "position": i,
            "item": {
                "@type": "Event",
                "name": event['name'],
                "startDate": event['date'],
                "location": {
                    "@type": "Place",
                    "name": event.get('location', ''),
                    "address": {
                        "@type": "PostalAddress",
                        "addressRegion": f"{event.get('prefecture', '')}県"
                    }
                },
                "url": f"https://agave-navi.com/events/{event['slug']}.html",
                "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode"
            }
        }
        if 'dateEnd' in event and event.get('dateEnd'):
            item['item']['endDate'] = event['dateEnd']
        items.append(item)

    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "アガベ・塊根植物イベント一覧 2026",
        "description": "全国のアガベ・塊根植物・多肉植物・珍奇植物・ビザールプランツの即売会・マルシェ・展示会情報",
        "numberOfItems": len(items),
        "itemListElement": items
    }
    return schema

def rebuild_index(html_file, events_json_file):
    """Main function to rebuild index.html"""

    # Load data
    events = load_events_json(events_json_file)

    # Separate upcoming and past events
    upcoming_events = [e for e in events if e.get('status') == 'upcoming']
    past_events = [e for e in events if e.get('status') == 'past']

    # Sort by date
    upcoming_events.sort(key=lambda e: e['date'])
    past_events.sort(key=lambda e: e['date'], reverse=True)

    # Load HTML
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Generate new event cards HTML
    upcoming_cards = '\n'.join([generate_event_card(e) for e in upcoming_events])
    past_cards = '\n'.join([generate_past_event_card(e) for e in past_events])

    # Replace upcoming events section
    # Match from "<!-- March 2026 -->" or similar comment to "</div><!-- /eventsGrid -->"
    upcoming_pattern = r'(\s+<!-- (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4} -->\s*\n)?<div class="event-card".*?(?=\s*</div><!-- /eventsGrid -->)'

    # More robust approach: find the exact markers and replace everything between them
    upcoming_start_marker = '<div class="events-grid" id="eventsGrid">'
    upcoming_end_marker = '</div><!-- /eventsGrid -->'
    upcoming_start_pos = html_content.find(upcoming_start_marker)
    upcoming_end_pos = html_content.find(upcoming_end_marker, upcoming_start_pos)

    if upcoming_start_pos == -1 or upcoming_end_pos == -1:
        print("ERROR: Could not find upcoming events section markers")
        return False

    # Keep the empty state div and comments
    before_cards = html_content[upcoming_start_pos:upcoming_start_pos + len(upcoming_start_marker)]

    # Find where the first card starts (after the empty state)
    empty_state_end = html_content.find('</div>', upcoming_start_pos + len(upcoming_start_marker))
    empty_state_end = html_content.find('</div>', empty_state_end + 1)  # Skip the nested divs

    # Include empty state and month comments
    content_before_first_card = html_content[upcoming_start_pos + len(upcoming_start_marker):empty_state_end + 5]
    content_before_first_card = content_before_first_card.rstrip()

    # Find the actual first card
    first_card_start = html_content.find('<!-- ', empty_state_end)
    if first_card_start == -1 or first_card_start > upcoming_end_pos:
        first_card_start = html_content.find('<div class="event-card"', empty_state_end)

    # Build new upcoming section
    new_upcoming_section = f'''{before_cards}
                    <div class="empty-state" id="emptyState">
                        <svg class="empty-state-icon" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" stroke-linecap="round" stroke-linejoin="round"></path></svg>
                        <p class="empty-state-title">行きたいイベントがまだありません</p>
                        <p class="empty-state-desc">気になるイベントのハートボタンをタップすると<br>ここに表示されます</p>
                    </div>
                    {upcoming_cards}
                '''

    # Replace the section
    html_content = html_content[:upcoming_start_pos] + new_upcoming_section + html_content[upcoming_end_pos:]

    # Now handle past events section
    past_start_marker = '<div class="events-grid past-events" id="pastEventsGrid">'
    past_end_pattern = r'</div><!-- /pastEventsGrid -->'

    past_start_pos = html_content.find(past_start_marker)
    # Find the closing tag more carefully
    past_grid_start = past_start_pos + len(past_start_marker)
    past_div_count = 1
    pos = past_grid_start
    while past_div_count > 0 and pos < len(html_content):
        next_open = html_content.find('<div', pos)
        next_close = html_content.find('</div>', pos)

        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            past_div_count += 1
            pos = next_open + 1
        else:
            past_div_count -= 1
            pos = next_close + 6

    past_end_pos = pos

    if past_start_pos == -1:
        print("ERROR: Could not find past events section markers")
        return False

    new_past_section = f'''{past_start_marker}
                    {past_cards}
                '''

    html_content = html_content[:past_start_pos] + new_past_section + html_content[past_end_pos:]

    # Update event counts
    upcoming_count = len(upcoming_events)
    past_count = len(past_events)

    # Update the main event count in the heading
    html_content = re.sub(
        r'<span class="event-count" id="eventCount">\d+件</span>',
        f'<span class="event-count" id="eventCount">{upcoming_count}件</span>',
        html_content
    )

    # Update JSON-LD schema
    jsonld_schema = generate_jsonld_schema(upcoming_events)
    jsonld_str = json.dumps(jsonld_schema, ensure_ascii=False, indent=2)

    # Find and replace JSON-LD
    jsonld_pattern = r'<script type="application/ld\+json">\s*\{[\s\S]*?\}\s*</script>'
    jsonld_replacement = f'''<script type="application/ld+json">
    {jsonld_str}
    </script>'''

    html_content = re.sub(jsonld_pattern, jsonld_replacement, html_content)

    # Write back to file
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✓ Rebuilt index.html")
    print(f"  - {upcoming_count} upcoming events")
    print(f"  - {past_count} past events")
    print(f"  - Updated JSON-LD schema with {len(upcoming_events[:100])} items")

    return True

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)

    html_file = os.path.join(project_dir, 'index.html')
    events_json_file = os.path.join(project_dir, 'events.json')

    if not os.path.exists(html_file):
        print(f"ERROR: {html_file} not found")
        sys.exit(1)

    if not os.path.exists(events_json_file):
        print(f"ERROR: {events_json_file} not found")
        sys.exit(1)

    success = rebuild_index(html_file, events_json_file)
    sys.exit(0 if success else 1)
