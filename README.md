# LeadReach 🎯

**Google Search → Unique Domains → Contact-Page Dashboard → Outreach**

LeadReach is a Windows desktop tool (Python + Selenium) that searches Google for a
keyword, extracts unique domains from the results, and generates an HTML dashboard
with the **real "Contact us" page** of every site — plus emails, phones and WhatsApp
numbers where available — so you can open them all and reach out for advertising /
partnership purposes.

## How it works

1. You enter a **search term**, the **number of new links** to extract, and (once)
   your **Chrome profile path** so the search runs while logged in.
2. LeadReach opens Google, runs the search, and walks through result pages collecting
   unique domains — skipping:
   - domains already seen in previous runs (`seen_domains.txt`)
   - filtered domains (`filter.txt`, e.g. `wikipedia.org`, `youtube.com`)
   - links pointing back to Google/YouTube
3. It saves the new domains, writes a search log, and **enriches** each domain:
   - finds the real contact page (candidate paths → homepage scan → `/contact` fallback)
   - extracts emails / phones / WhatsApp / Telegram from that page
     (via a local **Ollama** LLM, falling back to regex if Ollama is off)
   - caches everything in `contacts.json` so re-runs are instant
4. It builds `dashboard.html` with a checkbox list of contact pages, contact info
   badges, and buttons: **Open All**, **Open Selected**, **Find Contact Pages** and
   **Extract Emails** (the last two need the dashboard server, see below).

## Requirements

- Windows
- Google Chrome (installed)
- Python 3.10+
- `chromedriver.exe` next to the script (auto-downloaded if missing)
- **Optional:** [Ollama](https://ollama.com) for smarter contact extraction
  (without it, extraction falls back to plain regex)

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
  You are asked **only once**; afterwards the saved profile is used automatically.
- **Search term** — the keyword to search for.

When done, open `dashboard.html`.

## Contact enrichment (Ollama)

Enrichment runs automatically after each search. By default it tries a local Ollama
server; if Ollama is not running it falls back to regex extraction, so the pipeline
never breaks.

### Setting up Ollama (optional but recommended)

1. Install Ollama from <https://ollama.com> and start it (it runs locally on
   `http://localhost:11434` — nothing is sent to the internet).
2. Download a model once:

   ```bash
   ollama pull qwen2.5:7b
   ```

3. Configure the model in `config.json` (copy from `config.example.json`):

   ```json
   "llm": {
     "provider": "ollama",
     "host": "http://localhost:11434",
     "model": "qwen2.5:7b",
     "enabled": true
   }
   ```

   Set `"enabled": false` to always use the regex fallback.

## Dashboard server (Find Contact Pages / Extract Emails buttons)

The dashboard is a static HTML file, so the two enrichment buttons need a tiny local
server to answer them. Start it in a second terminal:

```bash
python dashboard_server.py          # http://127.0.0.1:8765/
```

Then open `http://127.0.0.1:8765/` (or open `dashboard.html` directly — the page will
reach the server over `127.0.0.1:8765` on its own). Click **Find Contact Pages** to
locate the real contact URL of every row, then **Extract Emails** to pull emails /
phones / WhatsApp. Results are cached into `contacts.json`. The server binds to
`127.0.0.1` only, so it is never reachable from the network.

## Configuration files

| File | Purpose |
|------|---------|
| `config.json` | Your saved Chrome profile path + Ollama settings (git-ignored — copy from `config.example.json`) |
| `config.example.json` | Template for `config.json` (safe to commit) |
| `filter.txt` | Domains to exclude from results (one per line, `#` for comments) |
| `seen_domains.txt` | Domains already extracted in previous runs (auto-managed) |
| `log.txt` | Search log history (auto-managed) |
| `contacts.json` | Contact info cache: contact URL, emails, phones, WhatsApp per domain (auto-managed) |
| `dashboard.html` | Generated contact-page dashboard (auto-managed) |

## Building the .exe (PyInstaller)

```bash
pip install pyinstaller
pyinstaller google_100_tabs.spec
```

The executable is written to `dist/google_100_tabs.exe`. Run it from a folder that
also contains `config.json` and `chromedriver.exe` (both auto-created / downloadable).

## Compliance notice

This tool is intended for **legitimate, permission-based outreach** (e.g. contacting
sites that publish a contact page for business inquiries). Before running campaigns:

- Respect **CAN-SPAM**, **GDPR**, and your local anti-spam laws.
- Only email sites that accept business inquiries; include a clear opt-out.
- Automated scraping of Google may violate Google's Terms of Service — use responsibly
  and at your own risk.

## License

[MIT](LICENSE)
