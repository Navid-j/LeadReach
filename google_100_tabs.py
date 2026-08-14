# -*- coding: utf-8 -*-
import time
import os
import sys
import re
import json
import requests
import zipfile
import io
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from urllib.parse import urlparse
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from contact_extractor import enrich_contacts

# ========== SETTINGS ==========
SEEN_FILE = "seen_domains.txt"
LOG_FILE = "log.txt"
FILTER_FILE = "filter.txt"
CONFIG_FILE = "config.json"
DASHBOARD_FILE = "dashboard.html"
CONTACTS_FILE = "contacts.json"

# Default domains written to filter.txt on first run (edit the file to customize)
DEFAULT_FILTERS = [
    "wikipedia.org",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "telegram.com",
]

# ========== FUNCTIONS ==========

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.getcwd()

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

def get_chrome_profile():
    config = load_config()
    saved = config.get('chrome_profile')
    if saved and os.path.exists(saved) and config.get('profile_confirmed'):
        print(f"Using saved Chrome profile: {saved}")
        return saved
    if saved and os.path.exists(saved):
        print(f"Saved Chrome profile path: {saved}")
        use_saved = input("Use this profile? (yes/no): ").strip().lower()
        if use_saved == 'yes':
            config['profile_confirmed'] = True
            save_config(config)
            return saved
        print("OK, let's set a new profile.\n")
    
    print("\n" + "="*60)
    print("CHROME PROFILE SETUP")
    print("="*60)
    print("\nIMPORTANT: Close all Chrome windows before continuing!")
    print("\nTo find your Chrome profile path:")
    print("1. Open Chrome and go to: chrome://version/")
    print("2. Find 'Profile Path' (e.g., C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data\\Default)")
    print("3. Copy the path WITHOUT the '\\Default' at the end")
    print("   Example: C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data")
    print("="*60)
    
    while True:
        profile_path = input("\nEnter Chrome profile path: ").strip()
        if os.path.exists(profile_path):
            config['chrome_profile'] = profile_path
            config['profile_confirmed'] = True
            save_config(config)
            return profile_path
        else:
            print(f"Path does not exist: {profile_path}")
            retry = input("Try again? (yes/no): ").strip().lower()
            if retry != 'yes':
                return None

def get_num_links():
    while True:
        try:
            num = input("How many NEW links to extract? (default 100): ").strip()
            if not num:
                return 100
            num = int(num)
            if num > 0:
                return num
            print("Please enter a positive number.")
        except ValueError:
            print("Invalid input. Enter a number.")

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen(new_domains):
    with open(SEEN_FILE, 'a', encoding='utf-8') as f:
        for domain in new_domains:
            f.write(domain + '\n')

def load_filters():
    if not os.path.exists(FILTER_FILE):
        try:
            with open(FILTER_FILE, 'w', encoding='utf-8') as f:
                f.write("# Domains to exclude from results (one per line).\n")
                f.write("# Lines starting with # are ignored.\n")
                for domain in DEFAULT_FILTERS:
                    f.write(domain + "\n")
            print(f"Created {FILTER_FILE} with {len(DEFAULT_FILTERS)} default filters. "
                  "Edit the file to add or remove domains.")
        except Exception as e:
            print(f"Warning: could not create {FILTER_FILE}: {e}")
    filters = set()
    if os.path.exists(FILTER_FILE):
        with open(FILTER_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    filters.add(line.lower())
    return filters

def is_filtered(domain, filters):
    if not filters:
        return False
    domain = domain.lower()
    for f in filters:
        if f in domain or domain in f:
            return True
    return False

def get_domain_from_url(url):
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        if ':' in domain:
            domain = domain.split(':')[0]
        return domain
    except:
        return None

def get_query():
    q = input("Enter search term: ").strip()
    if not q:
        print("Empty term. Exiting.")
        sys.exit()
    return q

def get_chrome_version():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version, _ = winreg.QueryValueEx(key, "version")
        winreg.CloseKey(key)
        return version
    except:
        return None

def download_chromedriver(version):
    CDN_URLS = [
        "https://registry.npmmirror.com/mirrors/chromedriver/",
        "https://chromedriver.storage.googleapis.com/",
    ]
    for cdn in CDN_URLS:
        try:
            download_url = f"{cdn}{version}/chromedriver-win64.zip"
            print(f"Downloading from: {download_url}")
            response = requests.get(download_url, timeout=30)
            if response.status_code == 200:
                zip_file = zipfile.ZipFile(io.BytesIO(response.content))
                for file_name in zip_file.namelist():
                    if file_name.endswith("chromedriver.exe"):
                        driver_path = os.path.join(os.getcwd(), "chromedriver.exe")
                        with open(driver_path, 'wb') as f:
                            f.write(zip_file.read(file_name))
                        os.chmod(driver_path, 0o755)
                        print("ChromeDriver downloaded successfully.")
                        return driver_path
        except Exception as e:
            print(f"Failed: {e}")
            continue
    return None

def setup_driver(profile_path):
    options = Options()
    options.add_experimental_option("detach", True)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--start-maximized")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    
    if profile_path and os.path.exists(profile_path):
        print(f"Using Chrome profile: {profile_path}")
        options.add_argument(f"user-data-dir={profile_path}")
        options.add_argument(f"profile-directory=Default")
    else:
        print("Using default Chrome profile (no login).")
    
    local_driver = os.path.join(os.getcwd(), "chromedriver.exe")
    if os.path.exists(local_driver):
        service = Service(local_driver)
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    
    print("chromedriver.exe not found. Downloading...")
    chrome_version = get_chrome_version()
    if chrome_version:
        major_version = ".".join(chrome_version.split(".")[:3])
        print(f"Chrome version: {chrome_version}")
        driver_path = download_chromedriver(major_version)
        if driver_path and os.path.exists(driver_path):
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            return driver
    
    print("\nERROR: Could not find chromedriver.exe")
    input("Press Enter to exit...")
    sys.exit(1)

def check_login_status(driver):
    try:
        driver.get("https://accounts.google.com/")
        time.sleep(2)
        if "accounts.google.com" in driver.current_url and "login" in driver.current_url.lower():
            print("\nWARNING: You are NOT logged into Google!")
            print("Login to get more search results.")
            choice = input("Continue anyway? (yes/no): ").strip().lower()
            if choice != 'yes':
                print("Please login to Chrome manually, then run the program again.")
                sys.exit(1)
        else:
            print("\nSUCCESS: You are logged into Google!")
            return True
    except Exception as e:
        print(f"Could not verify login status: {e}")
        return False

def get_total_results(driver):
    try:
        stats = driver.find_element(By.ID, "result-stats")
        text = stats.text
        match = re.search(r'[\d,]+', text)
        if match:
            return match.group().replace(',', '')
    except:
        try:
            stats = driver.find_element(By.CSS_SELECTOR, "div#result-stats")
            text = stats.text
            match = re.search(r'[\d,]+', text)
            if match:
                return match.group().replace(',', '')
        except:
            pass
    return None

def extract_links_from_page(driver, seen_domains, filters, num_needed):
    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='http']")
    new_links = []
    new_domains = []
    for link in links:
        href = link.get_attribute("href")
        if href and href.startswith("http") and "google.com" not in href:
            if "youtube.com" not in href:
                domain = get_domain_from_url(href)
                if domain and domain not in seen_domains and not is_filtered(domain, filters):
                    new_links.append(href)
                    new_domains.append(domain)
                    seen_domains.add(domain)
                    if len(new_links) >= num_needed:
                        break
    return new_links, new_domains

def go_to_next_page(driver):
    try:
        next_button = driver.find_element(By.ID, "pnnext")
        next_button.click()
        time.sleep(2)
        return True
    except NoSuchElementException:
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a#pnnext")
            next_button.click()
            time.sleep(2)
            return True
        except:
            return False

def fetch_new_links_unlimited(driver, query, num_links, seen_domains, filters):
    print("Opening Google...")
    driver.get("https://www.google.com")
    time.sleep(2)
    
    search = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
    search.clear()
    search.send_keys(query)
    search.submit()
    print("Search submitted. Loading results...")
    time.sleep(3)
    
    total_results = get_total_results(driver)
    if total_results:
        print(f"Total results found: {total_results}")
    else:
        print("Total results: Could not detect")
    
    new_links = []
    new_domains = []
    page_num = 1
    
    while len(new_links) < num_links:
        print(f"\n--- Page {page_num} ---")
        
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        
        page_links, page_domains = extract_links_from_page(driver, seen_domains, filters, num_links - len(new_links))
        new_links.extend(page_links)
        new_domains.extend(page_domains)
        
        print(f"Found {len(page_links)} new links on page {page_num} (total new: {len(new_links)}/{num_links})")
        
        if len(new_links) >= num_links:
            print(f"\n✅ Reached target of {num_links} new links!")
            break
        
        print("Going to next page...")
        if not go_to_next_page(driver):
            print("\n❌ No more pages available. End of search results.")
            break
        
        page_num += 1
    
    print(f"\nTotal new links extracted: {len(new_links)} from {page_num} pages.")
    return new_links, new_domains, page_num

def build_dashboard(links, domains, query, contacts=None, filename=DASHBOARD_FILE):
    """ساخت فایل HTML با دکمه‌های Open All و Open Selected و نمایش Search Term"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    contacts = contacts or {}

    contact_links = []
    for link in links:
        parsed = urlparse(link)
        protocol = parsed.scheme if parsed.scheme else "https"
        domain = get_domain_from_url(link)
        if domain:
            info = contacts.get(domain, {})
            contact_links.append(info.get("contact_url") or f"{protocol}://{domain}/contact")
        else:
            contact_links.append(link)  # fallback
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Dashboard</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            padding: 20px;
            background: #f5f5f5;
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .info {{
            background: #fff;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
        }}
        .info-left p {{
            margin: 5px 0;
            color: #555;
        }}
        .info-right {{
            background: #e3f2fd;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            color: #0d47a1;
        }}
        .controls {{
            margin: 20px 0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }}
        button {{
            padding: 12px 30px;
            font-size: 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        #openAll {{
            background: #4CAF50;
            color: white;
        }}
        #openAll:hover {{
            background: #45a049;
            transform: scale(1.02);
        }}
        #openSelected {{
            background: #FF9800;
            color: white;
        }}
        #openSelected:hover {{
            background: #F57C00;
            transform: scale(1.02);
        }}
        #selectAll {{
            background: #2196F3;
            color: white;
        }}
        #selectAll:hover {{
            background: #1976D2;
        }}
        #deselectAll {{
            background: #9E9E9E;
            color: white;
        }}
        #deselectAll:hover {{
            background: #757575;
        }}
        #findContacts {{
            background: #7e57c2;
            color: white;
        }}
        #findContacts:hover {{
            background: #673ab7;
        }}
        #extractEmails {{
            background: #26a69a;
            color: white;
        }}
        #extractEmails:hover {{
            background: #00897b;
        }}
        #counter {{
            padding: 10px 20px;
            background: #fff;
            border-radius: 5px;
            font-weight: bold;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-left: auto;
        }}
        .link-list {{
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 15px;
            max-height: 600px;
            overflow-y: auto;
        }}
        .link-item {{
            display: flex;
            align-items: center;
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
            transition: background 0.2s;
        }}
        .link-item:hover {{
            background: #f9f9f9;
        }}
        .link-item input[type="checkbox"] {{
            margin-right: 15px;
            width: 18px;
            height: 18px;
            cursor: pointer;
        }}
        .link-item a {{
            color: #1a73e8;
            text-decoration: none;
            font-size: 14px;
            word-break: break-all;
        }}
        .link-item a:hover {{
            text-decoration: underline;
        }}
        .badge {{
            margin-left: 10px;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: bold;
        }}
        .badge.ok {{
            background: #e8f5e9;
            color: #2e7d32;
        }}
        .badge.warn {{
            background: #fff8e1;
            color: #f57f17;
        }}
        .badge.err {{
            background: #ffebee;
            color: #c62828;
        }}
        .meta {{
            margin-top: 3px;
            font-size: 12px;
            color: #555;
            word-break: break-all;
        }}
        .link-number {{
            color: #999;
            font-size: 12px;
            margin-right: 10px;
            min-width: 35px;
        }}
        .footer {{
            margin-top: 20px;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
        .warning {{
            background: #fff3cd;
            color: #856404;
            padding: 12px;
            border-radius: 5px;
            margin: 15px 0;
            border-left: 4px solid #ffc107;
        }}
        .status-bar {{
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 10px 15px;
            background: #e8f5e9;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .status-bar span {{
            font-weight: bold;
        }}
        .list-toolbar {{
            margin: 10px 0 6px;
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        .mini-btn {{
            padding: 4px 12px;
            font-size: 12px;
            border: 1px solid #ccc;
            border-radius: 12px;
            background: #fafafa;
            color: #555;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .mini-btn:hover {{
            background: #eee;
        }}
        .spinner {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid #ccc;
            border-top-color: #4CAF50;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            vertical-align: middle;
            margin-right: 6px;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <h1>📋 Link Dashboard</h1>
    
    <div class="info">
        <div class="info-left">
            <p><strong>Search Term:</strong> {query}</p>
            <p><strong>Generated:</strong> {timestamp}</p>
            <p><strong>Total Links:</strong> {len(contact_links)}</p>
            <p><strong>Status:</strong> Ready to open (Contact pages)</p>
        </div>
        <div class="info-right">
            🔍 {query}
        </div>
    </div>
    
    <div class="warning">
        ⚠️ <strong>Note:</strong> Opening many tabs at once may slow down your browser.
        Allow pop-ups for this page if prompted.
    </div>
    
    <div class="controls">
        <button id="openAll">🚀 Open All</button>
        <button id="openSelected">✅ Open Selected</button>
        <button id="findContacts">🔎 Find Contact Pages</button>
        <button id="extractEmails">📧 Extract Emails</button>
        <span id="counter">Selected: 0 / {len(links)}</span>
    </div>
    
    <div class="status-bar" id="statusBar">
        <span>💡 Tip:</span> Check the boxes next to links you want to open, then click "Open Selected".
    </div>
    
    <div class="list-toolbar">
        <button id="selectAll" class="mini-btn">✓ Select all</button>
        <button id="deselectAll" class="mini-btn">✗ Deselect all</button>
    </div>
    
    <div class="link-list" id="linkList">
'''

    for idx, (contact_url, domain) in enumerate(zip(contact_links, domains), 1):
        display_name = domain if domain else contact_url[:50]
        info = contacts.get(domain, {}) if domain else {}
        method_badge = ""
        method = info.get("method", "")
        if method == "candidate":
            method_badge = "<span class='badge ok'>✓ contact</span>"
        elif method == "homepage":
            method_badge = "<span class='badge warn'>~ found</span>"
        elif method == "fallback":
            method_badge = "<span class='badge err'>? guess</span>"

        emails = info.get("emails", []) or []
        email_txt = ", ".join(emails[:3]) if emails else "—"
        phone_txt = ", ".join(info.get("phones", [])[:2]) or ""
        wa_txt = info.get("whatsapp") or ""
        meta_parts = []
        if emails:
            meta_parts.append(f"📧 {email_txt}")
        if phone_txt:
            meta_parts.append(f"📞 {phone_txt}")
        if wa_txt:
            meta_parts.append(f"💬 WhatsApp: {wa_txt}")
        meta_html = "<div class='meta'>" + " · ".join(meta_parts) + "</div>" if meta_parts else ""

        html_content += f'''
        <div class="link-item" data-domain="{domain if domain else ''}">
            <input type="checkbox" class="link-checkbox" data-url="{contact_url}">
            <span class="link-number">{idx}.</span>
            <a href="{contact_url}" target="_blank" class="link-url">{display_name}</a>{method_badge}
            {meta_html}
        </div>
'''

    html_content += f'''
    </div>
    
    <div class="footer">
        Dashboard generated by Google Link Extractor &amp; Opener<br>
        {timestamp}
    </div>
    
    <script>
        // Open all links
        document.getElementById('openAll').addEventListener('click', function() {{
            var links = document.querySelectorAll('#linkList a');
            var count = 0;
            for (var i = 0; i < links.length; i++) {{
                window.open(links[i].href, '_blank');
                count++;
            }}
            alert('Opened ' + count + ' tabs!');
        }});
        
        // Open selected links only
        document.getElementById('openSelected').addEventListener('click', function() {{
            var checkboxes = document.querySelectorAll('.link-checkbox:checked');
            if (checkboxes.length === 0) {{
                alert('Please select at least one link to open.');
                return;
            }}
            var count = 0;
            for (var i = 0; i < checkboxes.length; i++) {{
                window.open(checkboxes[i].getAttribute('data-url'), '_blank');
                count++;
            }}
            alert('Opened ' + count + ' selected tabs!');
        }});
        
        // Select all checkboxes
        document.getElementById('selectAll').addEventListener('click', function() {{
            var checkboxes = document.querySelectorAll('.link-checkbox');
            for (var i = 0; i < checkboxes.length; i++) {{
                checkboxes[i].checked = true;
            }}
            updateCounter();
        }});
        
        // Deselect all checkboxes
        document.getElementById('deselectAll').addEventListener('click', function() {{
            var checkboxes = document.querySelectorAll('.link-checkbox');
            for (var i = 0; i < checkboxes.length; i++) {{
                checkboxes[i].checked = false;
            }}
            updateCounter();
        }});
        
        // Update counter when checkbox changes
        document.addEventListener('change', function(e) {{
            if (e.target && e.target.className === 'link-checkbox') {{
                updateCounter();
            }}
        }});
        
        function updateCounter() {{
            var checkboxes = document.querySelectorAll('.link-checkbox:checked');
            document.getElementById('counter').innerHTML = 'Selected: ' + checkboxes.length + ' / {len(links)}';
        }}
        
        // Initialize counter
        updateCounter();

        // ===== Contact enrichment (requires dashboard_server.py on port 8765) =====
        // When opened as file:// we must call the local server over http;
        // when served by dashboard_server.py we are same-origin.
        var API_BASE = (location.protocol === 'file:') ? 'http://127.0.0.1:8765' : '';

        function setStatusBar(text, isError, busy) {{
            var bar = document.getElementById('statusBar');
            var icon = busy
                ? '<span class="spinner"></span>'
                : '<span>' + (isError ? '⚠️' : '✅') + '</span> ';
            bar.innerHTML = icon + text;
            bar.style.background = isError ? '#ffebee' : (busy ? '#fff8e1' : '#e8f5e9');
        }}

        function callContactApi(domain, findEmail, cb) {{
            fetch(API_BASE + '/api/find-contacts', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ domain: domain, find_email: findEmail }})
            }}).then(function (r) {{ return r.json(); }}).then(cb).catch(function () {{
                cb({{ status: 'error', note: 'server offline' }});
            }});
        }}

        function updateRow(item, info) {{
            var urlEl = item.querySelector('a.link-url');
            if (info.contact_url && info.contact_url !== urlEl.getAttribute('href')) {{
                urlEl.setAttribute('href', info.contact_url);
                var cb = item.querySelector('.link-checkbox');
                if (cb) cb.setAttribute('data-url', info.contact_url);
            }}
            var method = info.method || '';
            var cls = 'err', label = '? guess';
            if (method === 'candidate') {{ cls = 'ok'; label = '✓ contact'; }}
            else if (method === 'homepage') {{ cls = 'warn'; label = '~ found'; }}
            var badge = item.querySelector('.badge');
            if (!badge) {{
                badge = document.createElement('span');
                badge.className = 'badge';
                urlEl.parentNode.insertBefore(badge, urlEl.nextSibling);
            }}
            badge.className = 'badge ' + cls;
            badge.textContent = label;
            var parts = [];
            var emails = (info.emails || []).slice(0, 3);
            var phones = (info.phones || []).slice(0, 2);
            if (emails.length) parts.push('📧 ' + emails.join(', '));
            if (phones.length) parts.push('📞 ' + phones.join(', '));
            if (info.whatsapp) parts.push('💬 WhatsApp: ' + info.whatsapp);
            var meta = item.querySelector('.meta');
            if (parts.length) {{
                if (!meta) {{
                    meta = document.createElement('div');
                    meta.className = 'meta';
                    item.appendChild(meta);
                }}
                meta.innerHTML = parts.join(' · ');
            }}
        }}

        function runContactJob(findEmail, label) {{
            var items = document.querySelectorAll('.link-item');
            var total = items.length;
            if (!total) return;
            var done = 0, failed = 0;
            setStatusBar(label + '... 0/' + total, false, true);
            for (var i = 0; i < items.length; i++) {{
                (function (item) {{
                    var domain = item.getAttribute('data-domain');
                    if (!domain) {{ done++; checkDone(); return; }}
                    callContactApi(domain, findEmail, function (info) {{
                        done++;
                        if (!info || info.status === 'error') failed++;
                        else if (info.domain) updateRow(item, info);
                        checkDone();
                    }});
                }})(items[i]);
            }}
            function checkDone() {{
                setStatusBar(label + '... ' + done + '/' + total +
                    (failed ? ' (' + failed + ' failed)' : ''), false, true);
                if (done === total) {{
                    setStatusBar(label + ' complete — ' +
                        (total - failed) + '/' + total + ' updated.');
                }}
            }}
        }}

        document.getElementById('findContacts').addEventListener('click', function () {{
            runContactJob(false, 'Finding contact pages');
        }});
        document.getElementById('extractEmails').addEventListener('click', function () {{
            runContactJob(true, 'Extracting emails & phones');
        }});
    </script>
</body>
</html>
'''
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✅ Dashboard created with /contact links: {filename}")
    return os.path.abspath(filename)

def write_log(query, num_links_requested, new_domains, pages_checked, filters_used):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write(f"SEARCH LOG - {timestamp}\n")
        f.write("="*70 + "\n")
        f.write(f"Search Term: {query}\n")
        f.write(f"Links Requested: {num_links_requested}\n")
        f.write(f"New Domains Found: {len(new_domains)}\n")
        f.write(f"Pages Checked: {pages_checked}\n")
        f.write(f"Filters Applied: {len(filters_used)} domains\n")
        if filters_used:
            f.write(f"Filtered Domains: {', '.join(filters_used)}\n")
        f.write("-"*70 + "\n")
        f.write("NEW DOMAINS:\n")
        for idx, domain in enumerate(new_domains, 1):
            f.write(f"{idx}. {domain}\n")
        f.write("="*70 + "\n\n")

def main():
    print("="*70)
    print("GOOGLE LINK EXTRACTOR & OPENER (DASHBOARD MODE)")
    print("="*70)
    
    filters = load_filters()
    if filters:
        print(f"Loaded {len(filters)} domain filters: {', '.join(filters)}")
    else:
        print("No domain filters loaded.")
    
    seen_domains = load_seen()
    print(f"Previously seen domains: {len(seen_domains)}")
    
    num_links = get_num_links()
    print(f"Will extract exactly {num_links} NEW domains.")
    
    profile_path = get_chrome_profile()
    if profile_path:
        print(f"Profile path set: {profile_path}")
    else:
        print("No profile path set. Using default.")
    
    query = get_query()
    
    try:
        driver = setup_driver(profile_path)
        
        login_ok = check_login_status(driver)
        if login_ok:
            print("Login confirmed. Results may be better.")
        else:
            print("Proceeding without login.")
        
        new_links, new_domains, pages_checked = fetch_new_links_unlimited(
            driver, query, num_links, seen_domains, filters
        )
        
        print("\n" + "="*70)
        print("FINAL REPORT")
        print("="*70)
        print(f"Search Term: {query}")
        print(f"Links Requested: {num_links}")
        print(f"New Domains Found: {len(new_domains)}")
        print(f"Pages Checked: {pages_checked}")
        if len(new_domains) < num_links:
            print("⚠️ Could not find enough new domains. Reached end of search results.")
        print("="*70)
        
        if new_domains:
            # ذخیره دامنه‌ها در فایل seen
            save_seen(new_domains)
            print(f"\n✅ Saved {len(new_domains)} new domains to {SEEN_FILE}")
            
            # ذخیره لاگ
            write_log(query, num_links, new_domains, pages_checked, filters)
            print(f"✅ Log saved to {LOG_FILE}")
            
            # ساخت داشبورد HTML
            # ابتدا اطلاعات تماس (صفحه تماس + ایمیل/تلفن) را با Ollama استخراج می‌کنیم
            config = load_config()
            llm_config = config.get("llm", {})
            contacts = enrich_contacts(new_domains, llm_config=llm_config)

            dashboard_path = build_dashboard(new_links, new_domains, query, contacts=contacts)
            
            print("\n" + "="*70)
            print("🎯 DASHBOARD READY")
            print("="*70)
            print(f"📍 File location: {dashboard_path}")
            print("\n📌 Instructions:")
            print("1. Open the dashboard.html file in your browser.")
            print("2. Click 'Open All Links' to open all sites in new tabs.")
            print("3. If you want to open specific sites, use the checkboxes.")
            print("4. Tabs will stay open even after closing this script.")
            print("5. You can bookmark this page for future use.")
            print("="*70)
        else:
            print("\nNo new domains found. Dashboard not created.")
        
        # بستن مرورگر ربات (کاربر از داشبورد استفاده می‌کند)
        driver.quit()
        print("\n✅ Selenium browser closed.")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure Google Chrome is installed")
        print("2. Close ALL Chrome windows before running")
        print("3. Check your internet connection")
        print("4. If chromedriver download failed, download it manually")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()