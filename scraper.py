import json
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

LEDGER_FILE = 'seen_jobs.json'
TRACKR_URL = 'https://app.the-trackr.com/uk-finance/graduate-programmes'

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r') as file:
            return json.load(file)
    return []

def save_ledger(seen_urls):
    with open(LEDGER_FILE, 'w') as file:
        json.dump(seen_urls, file, indent=2)

def parse_date(date_str):
    try:
        return datetime.strptime(date_str.strip(), '%d %b %y')
    except Exception:
        return None

def extract_direct_application_url(desc_page, target_url):
    """
    Explicitly captures the direct external application URL.
    If target_url is an external job board, returns target_url.
    If target_url is an internal Trackr page, extracts the external apply link,
    or falls back to the direct Trackr page URL.
    """
    if target_url.startswith('http') and 'the-trackr.com' not in target_url:
        return target_url
    
    # Check for direct external apply links on the Trackr page
    apply_selectors = [
        'a[href*="greenhouse.io"]',
        'a[href*="grnh.se"]',
        'a[href*="myworkdayjobs.com"]',
        'a[href*="lever.co"]',
        'a[href*="smartrecruiters.com"]',
        'a[href*="tal.net"]',
        'a[href*="pinpointhq.com"]',
        'a[href*="bamboohr.com"]',
        'a:has-text("Apply")',
        'a:has-text("Apply Now")'
    ]
    for sel in apply_selectors:
        try:
            loc = desc_page.locator(sel).first
            if loc.count() > 0:
                href = loc.get_attribute('href')
                if href and href.startswith('http') and 'the-trackr.com' not in href:
                    return href
        except Exception:
            continue
    
    return target_url

def scrape_new_jobs():
    seen_urls = load_ledger()
    new_jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(TRACKR_URL, wait_until='networkidle')
        
        # Wait for table rows to load
        page.wait_for_selector('table tbody tr')
        rows = page.locator('table tbody tr').all()
        
        candidates = []
        for row in rows:
            # Programme link is in column 3 (nth-child(3))
            link_locator = row.locator('td:nth-child(3) a')
            if link_locator.count() > 0:
                job_url = link_locator.first.get_attribute('href')
                title = link_locator.first.inner_text().strip()
                
                # Company is in column 2 (nth-child(2))
                company_locator = row.locator('td:nth-child(2)')
                company = company_locator.inner_text().strip() if company_locator.count() > 0 else "Unknown"
                
                # Opening date is in column 4 (nth-child(4))
                date_locator = row.locator('td:nth-child(4)')
                open_date = date_locator.inner_text().strip() if date_locator.count() > 0 else ""
                
                if job_url:
                    dt = parse_date(open_date)
                    candidates.append({
                        'company': company,
                        'title': title,
                        'url': job_url,
                        'open_date': open_date,
                        'datetime': dt
                    })

        # Identify latest jobs based on the latest opening date on Trackr
        valid_dates = [c['datetime'] for c in candidates if c['datetime'] is not None]
        if valid_dates:
            latest_date = max(valid_dates)
            latest_jobs = [c for c in candidates if c['datetime'] == latest_date]
        else:
            latest_jobs = candidates[:5]

        for job in latest_jobs:
            job_url = job['url']
            if job_url not in seen_urls:
                target_url = job_url if job_url.startswith('http') else f"https://app.the-trackr.com{job_url}"
                
                # Navigate to the specific job page to get the full description
                desc_page = browser.new_page()
                try:
                    desc_page.goto(target_url, timeout=30000, wait_until='networkidle')
                    # Wait for asynchronous single-page app rendering to settle
                    desc_page.wait_for_timeout(2000)
                    
                    # Grab the entire inner_text() of the main page body or main job container
                    description = ""
                    for selector in [
                        '[data-automation-id="jobPostingDescription"]',
                        '[data-automation-id="job-posting-details"]',
                        '#job-description',
                        '.job-description',
                        '[data-qa="job-description"]',
                        'main',
                        'article',
                        '[role="main"]',
                        'body'
                    ]:
                        try:
                            loc = desc_page.locator(selector).first
                            if loc.count() > 0:
                                txt = loc.inner_text().strip()
                                if len(txt) > len(description):
                                    description = txt
                        except Exception:
                            continue
                    
                    if not description:
                        description = desc_page.locator('body').inner_text().strip()
                        
                    application_url = extract_direct_application_url(desc_page, target_url)
                except Exception as e:
                    print(f"Error fetching description from {target_url}: {e}")
                    description = ""
                    application_url = target_url
                finally:
                    desc_page.close()
                
                new_jobs.append({
                    'title': job['title'],
                    'company': job['company'],
                    'open_date': job['open_date'],
                    'url': target_url,
                    'application_url': application_url,
                    'job_url': application_url,
                    'description': description
                })
                seen_urls.append(job_url)
                
        browser.close()
        save_ledger(seen_urls)
        
    return new_jobs

def dispatch_tailored_application(job_title, company, description, application_url, cv_md, cl_md):
    """
    Passes job metadata and tailored Markdown directly into dispatch_application in dispatch.py.
    """
    from dispatch import dispatch_application
    return dispatch_application(
        job_title=job_title,
        company=company,
        job_description=description,
        job_url=application_url,
        cv_md=cv_md,
        cl_md=cl_md
    )

if __name__ == '__main__':
    # In Antigravity, this output is passed directly to the LLM node
    jobs = scrape_new_jobs()
    print(f"Scraping complete. Found {len(jobs)} new roles.")
    for j in jobs:
        print(f"- {j['company']}: {j['title']} ({j['open_date']})")
        print(f"  Application URL: {j['application_url']}")