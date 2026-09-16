import os
import json
from datetime import datetime
from google import genai
from playwright.sync_api import sync_playwright
from dispatch import dispatch_application

# Setup Gemini AI
client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))

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
    """Explicitly captures the direct external application URL."""
    if target_url.startswith('http') and 'the-trackr.com' not in target_url:
        return target_url
    
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

def tailor_document(template_path, job_description, company):
    with open(template_path, 'r') as file:
        template_content = file.read()
        
    prompt = f"""
    You are an expert technical career advisor.
    Target Company: {company}
    Job Description: {job_description}
    
    Template:
    {template_content}
    
    INSTRUCTIONS:
    - Rewrite ONLY the text contained within the square brackets [...] to align with the role.
    - DO NOT alter, add, or remove a single character outside the brackets.
    - IMPORTANT: You must completely delete the square brackets `[` and `]` from your final output so the tailored text blends seamlessly into the document. Do not leave any brackets behind.
    - Return ONLY the clean, final text in Markdown format.
    """
    
    # A robust list of standard fallback models to try if the API is busy
    models_to_try = [
        'gemini-3.5-flash',
        'gemini-3.6-flash',
    ]
    
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text.replace("```markdown", "").replace("```", "").strip()
        except Exception as e:
            print(f"Warning: {model_name} failed ({e}). Falling back to next model...")
            
    # If the server is totally down, return the raw template so the pipeline still emails you
    print("Error: All models are currently overloaded. Returning original template.")
    return template_content

def scrape_new_jobs():
    seen_urls = load_ledger()
    new_jobs_processed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(TRACKR_URL, wait_until='networkidle')
        
        # Wait for table rows to load using your real Trackr selectors
        page.wait_for_selector('table tbody tr')
        rows = page.locator('table tbody tr').all()
        
        candidates = []
        for row in rows:
            link_locator = row.locator('td:nth-child(3) a')
            if link_locator.count() > 0:
                job_url = link_locator.first.get_attribute('href')
                title = link_locator.first.inner_text().strip()
                
                company_locator = row.locator('td:nth-child(2)')
                company = company_locator.inner_text().strip() if company_locator.count() > 0 else "Unknown"
                
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

        # Filter for latest jobs
        valid_dates = [c['datetime'] for c in candidates if c['datetime'] is not None]
        if valid_dates:
            latest_date = max(valid_dates)
            latest_jobs = [c for c in candidates if c['datetime'] == latest_date]
        else:
            latest_jobs = candidates[:5]

        for job in latest_jobs:
            job_url = job['url']
            
            # Only process if we haven't seen this specific job URL before
            if job_url not in seen_urls:
                target_url = job_url if job_url.startswith('http') else f"https://app.the-trackr.com{job_url}"
                
                desc_page = browser.new_page()
                try:
                    desc_page.goto(target_url, timeout=30000, wait_until='networkidle')
                    desc_page.wait_for_timeout(2000)
                    
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
                
                # 1. AI Processing Node
                print(f"Tailoring documents for {job['company']}...")
                tailored_cv = tailor_document('Bradley Kingswell CV Example.md', description, job['company'])
                tailored_cl = tailor_document('BK Cover Letter Example.md', description, job['company'])
                
                # 2. Dispatch Node
                print(f"Dispatching email for {job['company']}...")
                dispatch_application(
                    job_title=job['title'],
                    company=job['company'],
                    job_description=description,
                    job_url=application_url,
                    cv_md=tailored_cv,
                    cl_md=tailored_cl
                )
                
                # 3. Add to Ledger so we don't process it again tomorrow
                seen_urls.append(job_url)
                new_jobs_processed += 1
                
        browser.close()
        save_ledger(seen_urls)
        return new_jobs_processed

if __name__ == '__main__':
    jobs_processed = scrape_new_jobs()
    print(f"Daily pipeline execution complete. Processed {jobs_processed} new roles.")
