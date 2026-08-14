# LeadReach 🎯

**Google Search → Unique Domains → Contact-Page Dashboard → Outreach**

LeadReach is a Windows desktop tool (Python + Selenium) that searches Google for a
keyword, extracts unique domains from the results, and generates an HTML dashboard
with the `/contact` page of every site — so you can open them all and reach out for
advertising / partnership purposes.

## How it works

1. You enter a **search term**, the **number of new links** to extract, and (optionally)
   your **Chrome profile path** so the search runs while logged in.
2. LeadReach opens Google, runs the search, and walks through result pages collecting
   unique domains — skipping:
   - domains already seen in previous runs (`seen_domains.txt`)
   - filtered domains (`filter.txt`, e.g. `wikipedia.org`, `youtube.com`)
   - links pointing back to Google/YouTube
3. It saves the new domains, writes a search log, and builds `dashboard.html` with a
   checkbox list of contact pages.

4. Open the dashboard in your browser and use **Open All** or **Open Selected** to open
   the `/contact` pages in new tabs.

## Requirements

- Windows
- Google Chrome (installed)
- Python 3.10+
- `chromedriver.exe` next to the script (auto-downloaded if missing)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python google_100_tabs.py
```

Follow the prompts:

- **How many NEW links to extract?** — number of unique domains to find (default 100).
- **Chrome profile path** — enter the path shown in `chrome://version/` **without** the
  trailing `\Default` (e.g. `C:\Users\You\AppData\Local\Google\Chrome\User Data`).
  The path is saved in `config.json` so you only enter it once.
- **Search term** — the keyword to search for.

When done, open `dashboard.html`.

## Configuration files

| File | Purpose |
|------|---------|
| `config.json` | Your saved Chrome profile path (git-ignored — copy from `config.example.json`) |
| `filter.txt` | Domains to exclude from results (one per line, `#` for comments) |
| `seen_domains.txt` | Domains already extracted in previous runs (auto-managed) |
| `log.txt` | Search log history (auto-managed) |
| `dashboard.html` | Generated contact-page dashboard (auto-managed) |

## Building the .exe (PyInstaller)

```bash
pip install pyinstaller
pyinstaller google_100_tabs.spec
```

The executable is written to `dist/google_100_tabs.exe`.

## Compliance notice

This tool is intended for **legitimate, permission-based outreach** (e.g. contacting
sites that publish a contact page for business inquiries). Before running campaigns:

- Respect **CAN-SPAM**, **GDPR**, and your local anti-spam laws.
- Only email sites that accept business inquiries; include a clear opt-out.
- Automated scraping of Google may violate Google's Terms of Service — use responsibly
  and at your own risk.

## License

[MIT](LICENSE)
