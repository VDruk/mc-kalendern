# MC Kalendern Tools

## fb-event-tool.py

Extracts event data from Facebook event pages and checks for duplicates against `events.js`.

### Setup (one time)

```bash
pip install selenium requests beautifulsoup4
```

You also need Chrome or Chromium installed on your machine.

### Usage

**Extract a single event:**
```bash
python fb-event-tool.py extract https://www.facebook.com/events/1267483558130059/
```

**Extract multiple events:**
```bash
python fb-event-tool.py extract URL1 URL2 URL3
```

**Process URLs from a file:**
```bash
python fb-event-tool.py batch urls.txt
```

**Find only NEW events (not already in calendar):**
```bash
python fb-event-tool.py check-new urls.txt
```

**Download cover images too:**
```bash
python fb-event-tool.py extract URL --download-images
```

**Run Chrome visible (not headless) for debugging:**
```bash
python fb-event-tool.py extract URL   # visible by default
python fb-event-tool.py extract URL --headless  # headless mode
```

**Add event directly to events.js (Type 1 card):**
```bash
python fb-event-tool.py extract "https://fb.com/events/123" --add --back-image ads/event-back-2026-05-16.jpg
```
The tool will show a preview and ask for confirmation before writing to events.js.

**Save output to file:**
```bash
python fb-event-tool.py check-new urls.txt --output new-events.json
```

### URL file format

One URL per line. Lines starting with `#` are ignored:

```
# MC events to check - March 2026
https://www.facebook.com/events/1267483558130059/
https://www.facebook.com/events/1919105001975075/

# These are from Triumph Stockholm
https://www.facebook.com/events/839357122492882/
```

### What it does

1. Opens each Facebook event URL in Chrome
2. Clicks "See more" to expand the description
3. Extracts: name, date, location, organizer, description, cover image
4. Guesses the event type (Show, Körning, Träff, Fest, Racing)
5. Guesses the SMC region from the location (100+ Swedish cities mapped)
6. Generates a ready-to-paste JSON block for events.js
7. Checks for duplicates against your existing events
8. Optionally downloads the cover image to ads/
9. With `--add`: writes the event directly into events.js (sorted by date, with confirmation)

### Tips

- **Always quote URLs** that contain special characters (like `?`, `&`, `[`, `]`):
  ```bash
  python fb-event-tool.py extract "https://www.facebook.com/events/123?active_tab=about"
  ```
  Without quotes, zsh/bash will try to interpret `[]{}?` as glob patterns and fail.

- **Close Chrome** before running the tool. If Chrome is already open, Selenium sometimes cannot start a new session.

- The tool uses a clean Chrome profile (no login). Facebook public events are visible without being logged in.

### Notes

- It waits 3-4 seconds per page to let Facebook render
- Date parsing can be tricky with Facebook's relative dates ("Saturday at 11 AM").
  If the tool can't figure out the date, it outputs "MANUAL_ENTRY_NEEDED"
- The description and type guessing are best-effort. Always review the output.
- The dedup uses name similarity + date matching. It shows "POSSIBLE DUPLICATES" when it finds similar events.

### File structure

```
tools/
  fb-event-tool.py      # Main tool
  requirements.txt      # Python dependencies
  README.md             # This file
```
