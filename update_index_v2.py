#!/usr/bin/env python3
import json
import re
from datetime import datetime

def generate_event_card_html(event):
    """Generate HTML card for event in index.html"""
    slug = event["slug"]
    date_display = event["dateDisplay"]
    title = event["name"]
    description = event["description"]
    region = event["region"]
    tags = event.get("tags", [])
    date_str = event["date"]
    date_end = event.get("dateEnd", "")

    # Determine prefecture
    pref = event["prefecture"]

    # Build tags string
    tags_str = ",".join(tags)

    # Build tags HTML
    tags_html = "\n                            ".join([f'<span class="tag">{tag}</span>' for tag in tags])

    # Check if no image
    image_html = '<div class="event-thumb event-no-image"></div>'

    # Add data-date-end if present
    date_end_attr = f' data-date-end="{date_end}"' if date_end else ''

    html = f'''<div class="event-card" data-tags="{tags_str}" data-status="upcoming" data-region="{region}" data-pref="{pref}" data-date="{date_str}"{date_end_attr} data-slug="{slug}">
                        {image_html}
                        <button class="fav-btn" onclick="toggleFav(event, '{slug}')" aria-label="行きたい">
                            <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                        </button>
                        <div class="swipe-hint"><div class="swipe-hint-icon"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></div></div>
                        <div class="event-card-body">
                        <div class="event-header">
                            <span class="event-date">{date_display}</span>
                        </div>
                        <h3 class="event-title">{title}</h3>
                        <p class="event-description">{description}</p>
                        <div class="event-meta-row">
                            <span class="event-region">{pref}</span>
                        </div>
                        <div class="event-tags">
                            {tags_html}
                        </div>
                        <a href="events/{slug}.html" class="event-link">詳細を見る</a>
                        </div>
                                            <div class="card-fav-bar" onclick="event.stopPropagation()"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg><span>行きたい</span></div>
</div>

'''

    return html

# Load events
with open('/sessions/serene-dreamy-galileo/repo/events.json', 'r', encoding='utf-8') as f:
    all_events = json.load(f)

# Filter to only upcoming events and sort by date
upcoming_events = [e for e in all_events if e["status"] == "upcoming"]
upcoming_events.sort(key=lambda e: e["date"])

# Read index.html
with open('/sessions/serene-dreamy-galileo/repo/index.html', 'r', encoding='utf-8') as f:
    index_content = f.read()

# Build all event cards in chronological order
all_cards_html = ""
from collections import defaultdict
events_by_month = defaultdict(list)
for e in upcoming_events:
    month_year = e["date"][:7]  # YYYY-MM
    events_by_month[month_year].append(e)

# Generate cards grouped by month
for month in sorted(events_by_month.keys()):
    month_obj = datetime.strptime(month, '%Y-%m')

    # Add month header comment
    all_cards_html += f"                    <!-- {month_obj.strftime('%B %Y')} -->\n"

    for event in sorted(events_by_month[month], key=lambda e: e["date"]):
        all_cards_html += generate_event_card_html(event)

# Find where to insert: right after the empty-state div
# Actually, let's look for the position right after the empty-state closing </div>
# and before the first event card month comment

# Find the empty-state closing div
empty_state_pattern = r'(</div>\n\s*<!-- March 2026 -->)'
match = re.search(empty_state_pattern, index_content)

if match:
    # Replace the empty-state closing </div> and month comment with new content
    # First, remove all existing event cards and rebuild
    # Find from empty-state to load-more-wrap

    start_pos = index_content.find('<div class="empty-state" id="emptyState">')
    end_pos = index_content.find('<div class="load-more-wrap"')

    if start_pos != -1 and end_pos != -1:
        # Keep the empty-state div, add event cards after it
        empty_state_end = index_content.find('</div>', start_pos) + 6  # +6 for </div>

        # Build the new grid content
        new_grid_content = index_content[:empty_state_end] + "\n" + all_cards_html + index_content[end_pos:]

        index_content = new_grid_content

        # Update event count
        event_count = len(upcoming_events)
        index_content = re.sub(
            r'<span class="event-count" id="eventCount">\d+件</span>',
            f'<span class="event-count" id="eventCount">{event_count}件</span>',
            index_content
        )

        # Save updated index.html
        with open('/sessions/serene-dreamy-galileo/repo/index.html', 'w', encoding='utf-8') as f:
            f.write(index_content)

        print(f"Successfully updated index.html with {event_count} event cards")
    else:
        print("Could not find grid boundaries")
else:
    print("Pattern not found")
