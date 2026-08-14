# -*- coding: utf-8 -*-
"""
contact_extractor.py

Pipeline per domain:
    1. find_contact_url()  - find the real "Contact us" page (candidate paths + homepage scan)
    2. fetch_page()        - download the page HTML (with browser-like User-Agent)
    3. extract_contact_info() - extract emails / phones / whatsapp via Ollama LLM,
                                falling back to plain regex when Ollama is unavailable.

All results are cached in contacts.json (keyed by domain) so re-runs are instant.
"""
import os
import re
import json
import sys
import html as html_mod
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# Make the Windows console UTF-8 friendly (emoji in prints), never crash on odd codepages.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CONTACTS_FILE = "contacts.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en,fa;q=0.9,*;q=0.8",
}

# ---------------------------------------------------------------------------
# 1. Contact URL discovery
# ---------------------------------------------------------------------------

CONTACT_PATHS = [
    # English
    "/contact", "/contact-us", "/contactus", "/contact.html", "/contact-us.html",
    "/contact_us", "/contact-us/", "/contact/", "/pages/contact",
    "/about/contact", "/about/contact-us", "/about-us/contact",
    "/support", "/support/contact", "/support/contact-us", "/help/contact",
    # Common CMS paths
    "/node/contact", "/form/contact", "/kontakt",
    # Other languages
    "/en/contact", "/en/contact-us",
    "/fr/contact", "/fr/contactez-nous", "/fr/nous-contacter",
    "/de/kontakt", "/de/kontakt-aufnehmen",
    "/es/contacto", "/es/contactar",
    "/it/contatti", "/pt/contato", "/nl/contact", "/pl/kontakt",
    "/tr/iletisim", "/ru/kontakty", "/cs/kontakt", "/hu/kapcsolat",
    "/sv/kontakt", "/da/kontakt", "/no/kontakt", "/fi/yhteystiedot",
    "/fa/contact", "/ar/contact", "/zh/contact", "/ja/contact", "/ko/contact",
]

# Keywords used to recognise a "contact" URL (path) or link (href / link text).
CONTACT_KEYWORDS = (
    "contact", "kontakt", "contacto", "contactar", "contatti", "contato",
    "iletisim", "kontakty", "kapcsolat", "yhteystiedot", "kontakta",
    "contactez", "nous-contacter", "reach", "get-in-touch", "contact-us",
    # CJK + Persian / Arabic
    "联系", "联系我们", "お問い合わせ", "お問合せ", "문의", "咨询",
    "تماس", "ارتباط", "اتصال",
)

# Text keywords for link-text matching (any language).
TEXT_KEYWORDS = (
    "contact us", "contact", "get in touch", "reach us", "write us",
    "kontakt", "contacto", "contatti", "contato", "iletisim",
    "联系", "联系我们", "お問い合わせ", "문의", "تماس", "ارتباط",
)


def _looks_like_contact_url(url):
    """True if the path of `url` contains a contact-ish keyword."""
    path = urlparse(url).path.lower()
    for kw in CONTACT_KEYWORDS:
        if kw in path:
            return True
    return False


def _check_url(url, timeout=8):
    """
    Return (ok, final_url). Tries HEAD first (some servers reject HEAD -> GET).
    A URL counts as OK when the final status is < 400 AND the final URL still
    looks like a contact page (avoids soft-404 redirects back to the homepage).
    """
    try:
        resp = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=timeout)
    except requests.RequestException:
        return False, url
    if resp.status_code in (405, 501):
        try:
            resp = requests.get(url, headers=HEADERS, allow_redirects=True,
                                stream=True, timeout=timeout)
            resp.close()
        except requests.RequestException:
            return False, url
    if resp.status_code >= 400:
        return False, resp.url
    if not _looks_like_contact_url(resp.url):
        return False, resp.url
    return True, resp.url


def find_contact_url(domain, protocol="https", progress=None):
    """
    Step 1: find the real contact page of a domain.
    Returns (contact_url, method) where method is one of:
        "candidate" - found from the candidate path list
        "homepage"  - found by scanning the homepage for a contact link
        "fallback"  - nothing found, /contact is our best guess
    """
    if progress:
        progress(f"[{domain}] finding contact page...")

    # 1a. Try all candidate paths IN PARALLEL; pick the first success in list order.
    candidates = [f"{protocol}://{domain}{path}" for path in CONTACT_PATHS]
    hits = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(_check_url, u): i for i, u in enumerate(candidates)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                ok, final_url = fut.result()
            except Exception:
                continue
            if ok:
                hits.append((i, final_url))
    if hits:
        _, final_url = min(hits, key=lambda h: h[0])
        if progress:
            progress(f"[{domain}] contact page: {final_url} (candidate)")
        return final_url, "candidate"

    # 1b. Scan the homepage for a contact link (handles custom paths like /kontakt-oss).
    # NOTE: the homepage itself is NOT a contact URL, so we fetch it directly
    # instead of using _check_url() (which demands a contact-looking path).
    homepage = f"{protocol}://{domain}/"
    try:
        resp = requests.get(homepage, headers=HEADERS, allow_redirects=True, timeout=12)
        if resp.status_code < 400:
            link = _find_contact_link_in_html(resp.text, resp.url)
            if link:
                if progress:
                    progress(f"[{domain}] contact page: {link} (homepage)")
                return link, "homepage"
    except requests.RequestException:
        pass

    # 1c. Fallback: keep the old behaviour.
    if progress:
        progress(f"[{domain}] no contact page found, falling back to /contact")
    return f"{protocol}://{domain}/contact", "fallback"


_ANCHOR_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',
                        re.IGNORECASE | re.DOTALL)


def _find_contact_link_in_html(home_html, base_url):
    """Look for the most promising contact link in the homepage HTML."""
    best = None
    best_score = 0
    for href, inner in _ANCHOR_RE.findall(home_html):
        href = href.strip()
        if not href.startswith(("http", "/", "./", "../")):
            continue
        if "mailto:" in href or "tel:" in href:
            continue
        score = 0
        hl = href.lower()
        if any(kw in hl for kw in CONTACT_KEYWORDS):
            score += 2
        text = re.sub(r"<[^>]+>", "", inner)
        text = html_mod.unescape(text).strip().lower()
        if any(kw in text for kw in TEXT_KEYWORDS):
            score += 3
        if score > best_score:
            best_score = score
            best = urljoin(base_url, href)
    if best and best_score >= 3:
        # Only trust it when it looks like a contact link (href or text matched).
        return best
    return None


# ---------------------------------------------------------------------------
# 2. Page fetching
# ---------------------------------------------------------------------------

def fetch_page(url, timeout=12):
    """Download page HTML; returns str or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, allow_redirects=True,
                            timeout=timeout)
        if resp.status_code < 400:
            return resp.text
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# 3. Extraction: LLM first, regex fallback
# ---------------------------------------------------------------------------

def strip_html_to_text(html_str, max_chars=4000):
    """Rough HTML -> visible text. Keeps the start (nav) and end (footer)."""
    text = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html_str)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|section|footer|address)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if len(text) > max_chars:
        half = max_chars // 2
        text = text[:half] + "\n...[middle omitted]...\n" + text[-half:]
    return text


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def regex_extract(text):
    """Cheap, offline extraction. The LLM is smarter, this is just a fallback."""
    emails = sorted(set(EMAIL_RE.findall(text)))
    # Prefer obvious business addresses.
    preferred = None
    for e in emails:
        local = e.split("@")[0].lower()
        if any(k in local for k in ("contact", "info", "sales", "hello", "support")):
            preferred = e
            break
    if preferred is None and emails:
        preferred = emails[0]

    phones = []
    for m in re.finditer(r"(?:\+?\d[\d\s\-().]{7,}\d)", text):
        p = m.group().strip()
        if p not in phones and len(re.sub(r"\D", "", p)) >= 8:
            phones.append(p)
        if len(phones) >= 5:
            break

    whatsapp = None
    m = re.search(r"wa\.me/(?:message/)?([0-9+]+)", text, re.IGNORECASE)
    if m:
        whatsapp = m.group(1)

    telegram = None
    m = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    if m:
        telegram = m.group(1)

    return {
        "is_contact_page": True,
        "emails": emails[:8],
        "preferred_email": preferred,
        "phones": phones,
        "whatsapp": whatsapp,
        "telegram": telegram,
        "has_contact_form": "form" in text.lower() or "فرم" in text,
        "note": "regex fallback",
    }


SYSTEM_PROMPT = (
    "You are a contact-information extractor. You receive the visible text of a "
    "webpage that may be written in ANY language (English, Persian, Arabic, German, "
    "Turkish, Chinese, Japanese, ...). Extract contact details.\n"
    "Respond with ONLY a JSON object, no commentary, with exactly these keys:\n"
    '{"is_contact_page": bool, "emails": [string], "preferred_email": string|null, '
    '"phones": [string], "whatsapp": string|null, "telegram": string|null, '
    '"socials": [string], "has_contact_form": bool, "note": string}\n'
    "Rules:\n"
    "- emails: real email addresses only; decode obfuscation like 'info [at] site [dot] com'.\n"
    "- preferred_email: the best address for business outreach (sales/contact/info), "
    "or null if unclear.\n"
    "- phones: full numbers, international format preferred. whatsapp/telegram: "
    "handles only if a real link/handle exists.\n"
    "- is_contact_page: false if this page is NOT a contact page (e.g. 404, landing, "
    "blog post).\n"
    "- note: one short sentence in English about the page (e.g. 'only a form, no direct email')."
)


def call_ollama(model, page_text, host="http://localhost:11434", timeout=180):
    """Ask Ollama to extract contact info as JSON."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "PAGE URL: (see context)\n\nPAGE TEXT:\n" + page_text},
        ],
        "stream": False,
        "format": "json",
        "options": {"num_ctx": 4096, "temperature": 0},
    }
    resp = requests.post(f"{host}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    content = data["message"]["content"]
    result = json.loads(content)
    # Normalise missing keys.
    defaults = {
        "is_contact_page": True, "emails": [], "preferred_email": None,
        "phones": [], "whatsapp": None, "telegram": None, "socials": [],
        "has_contact_form": False, "note": "",
    }
    for k, v in defaults.items():
        result.setdefault(k, v)
    return result


def ollama_available(host="http://localhost:11434"):
    try:
        r = requests.get(f"{host}/api/tags", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def extract_contact_info(url, html_str, llm_config=None):
    """Step 3: LLM extraction when available, otherwise regex."""
    text = strip_html_to_text(html_str)
    llm_config = llm_config or {}
    host = llm_config.get("host", "http://localhost:11434")
    model = llm_config.get("model", "qwen2.5:7b")
    if llm_config.get("enabled", True):
        try:
            if ollama_available(host):
                return call_ollama(model, text, host=host)
        except Exception:
            pass  # fall through to regex
    return regex_extract(text)


# ---------------------------------------------------------------------------
# 4. Per-domain pipeline + cache
# ---------------------------------------------------------------------------

def load_contacts():
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_contacts(contacts):
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False)


def process_domain(domain, llm_config, protocol="https", find_email=True):
    """
    Run the pipeline for one domain -> dict to store in the cache.
    find_email=False skips page download + extraction (fast, no LLM) and
    only locates the contact URL — used for the dashboard's phase-1 button.
    """
    contact_url, method = find_contact_url(domain, protocol=protocol)
    info = {
        "domain": domain,
        "contact_url": contact_url,
        "method": method,
        "status": "ok",
    }
    if not find_email:
        info.update({
            "emails": [], "phones": [], "whatsapp": None, "telegram": None,
            "has_contact_form": False, "note": "email extraction skipped",
        })
        return info
    page_html = fetch_page(contact_url)
    if page_html is None:
        info["status"] = "fetch_failed"
        info["note"] = "could not fetch contact page"
        return info
    extracted = extract_contact_info(contact_url, page_html, llm_config)
    info.update(extracted)
    return info


def enrich_contacts(domains, llm_config=None, max_workers=4):
    """
    Run the pipeline for every domain not yet in the cache.
    Returns the full contacts dict (old + new).
    """
    contacts = load_contacts()
    todo = [d for d in domains if d not in contacts]
    if not todo:
        return contacts

    print(f"\n🔍 Enriching contact info for {len(todo)} new domain(s)...")

    def run(domain):
        try:
            return process_domain(domain, llm_config)
        except Exception as e:
            return {"domain": domain, "status": "error", "note": str(e),
                    "contact_url": f"https://{domain}/contact", "method": "fallback"}

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(run, d): d for d in todo}
        for fut in as_completed(futures):
            info = fut.result()
            contacts[info["domain"]] = info
            done += 1
            emails = ", ".join(info.get("emails", [])[:2]) or "-"
            print(f"  [{done}/{len(todo)}] {info['domain']} -> {emails}")

    save_contacts(contacts)
    print(f"✅ Contact info cached in {CONTACTS_FILE}")
    return contacts
