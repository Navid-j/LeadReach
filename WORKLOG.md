# WORKLOG — progress tracker

> This file is the checkpoint for the LeadReach "contact enrichment" feature.
> If work gets interrupted (e.g. laptop shutdown), read this file first to know
> exactly where things stand and what to do next. Update it after every step.

## Status: IN PROGRESS

Feature: **LLM contact enrichment** — find each domain's real "Contact us" page
and extract emails / phones / WhatsApp, shown on the dashboard.

### Steps done

- [x] `contact_extractor.py` (new): pipeline per domain —
      1. `find_contact_url()` candidate paths → homepage scan → `/contact` fallback
      2. `fetch_page()` with browser User-Agent
      3. `extract_contact_info()` — Ollama LLM (JSON) with regex fallback
      Results cached in `contacts.json` keyed by domain.
- [x] `dashboard_server.py` (new): local server (default port 8765) serving
      `dashboard.html` + `POST /api/find-contacts` `{"domain", "find_email"}`.
      Caches each result into `contacts.json`.
- [x] `config.example.json`: added `llm` block (provider ollama, host, model, enabled)
      + `profile_confirmed` flag.
- [x] `google_100_tabs.py`: `main()` calls `enrich_contacts(new_domains, ...)` before
      `build_dashboard(...)`; dashboard rows show method badge
      (✓ contact / ~ found / ? guess) + 📧 emails, 📞 phones, 💬 WhatsApp.
- [x] Dashboard buttons "Find Contact Pages" / "Extract Emails" + JS calling the
      server. Tested end-to-end against the live server.
- [x] Dashboard UI polish: animated spinner in the status bar while a job runs
      (green ✅ only when it finishes); Select-all / Deselect-all moved to a small
      toolbar above the list; footer now says "made for Navid".
- [x] Chrome profile question is now asked **once** (`profile_confirmed` flag in
      `config.json`); subsequent runs use the saved profile silently.
- [x] README.md rewritten: documents enrichment, Ollama setup, dashboard server,
      `contacts.json`, config table.
- [x] Cleanup: removed `dashboard_preview.html`, `LICENSE.chromedriver`,
      `THIRD_PARTY_NOTICES.chromedriver`; all three + `dashboard.html` are
      git-ignored.
- [x] `.gitignore`: ignores `contacts.json`, `dashboard_preview.html`,
      chromedriver license files.
- [x] Committed the feature (clean commit, no personal data).
- [x] `update.bat` (new): git pull + pip install + optional exe rebuild.
      Works from repo root or from `dist\`. Requires a git clone with a remote
      (origin = https://github.com/Navid-j/LeadReach.git). Run it AFTER pushing.

### Next steps / decisions (ask the user)

- [x] **Update mechanism (v1)** — `update.bat` decided on: git-pull based,
      lightweight. Caveat: works only on machines with a git clone + remote;
      the exe itself needs a rebuild after pull (scripted in the bat).
- [ ] Decide: bundle `dashboard_server.py` as its own exe in the .spec file?
      (google_100_tabs exe already picks up `contact_extractor` via import.)
- [ ] Rebuild `dist/google_100_tabs.exe` when a new build is wanted
      (the old Jul-24 exe was deleted; it predated the enrichment feature).

### How to test manually

```bash
python dashboard_server.py          # terminal 1 — starts on http://127.0.0.1:8765/
python google_100_tabs.py           # terminal 2 — or regenerate dashboard with sample data
# open http://127.0.0.1:8765/ → click "Find Contact Pages" then "Extract Emails"
```
