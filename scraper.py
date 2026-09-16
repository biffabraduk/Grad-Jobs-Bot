import os
import json
import google.generativeai as genai
from playwright.sync_api import sync_playwright
from dispatch import dispatch_application

# Setup Gemini AI
genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

LEDGER_FILE = 'seen_jobs.json'
TRACKR_URL = 'https://app.the-trackr.com/uk-finance/graduate-programmes'

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r') as file:
            return json.load(file)
    return []

def save_ledger(seen_urls):
    with open(LEDGER_FILE, 'w') as file:
        json.dump(seen_urls, file)

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
    response = model.generate_content(prompt)
    
    # This strips out any markdown code formatting the LLM might try to apply
    return response.text.replace("```markdown", "").replace("```", "").strip()

def scrape_new_jobs():
    seen_urls = load_ledger()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(TRACKR_URL)
        
        # Using the Trackr selectors you mapped out during your local test
        page.wait_for_selector('.job-card-selector') 
        listings = page.locator('.job-card-selector').all()
        
        for listing in listings:
            job_url = listing.locator('a.job-link').get_attribute('href')
            
            if job_url not in seen_urls:
                title = listing.locator('.job-title').inner_text()
                company = listing.locator('.company-name').inner_text()
                
                # Navigate to the specific job page to get the full description
                desc_page = browser.new_page()
                
                # Handle both relative Trackr URLs and external direct links
                target_url = job_url if job_url.startswith('http') else f"https://app.the-trackr.com{job_url}"
                desc_page.goto(target_url)
                
                # Grabbing the entire body text to ensure the email doesn't just get a short snippet
                description = desc_page.locator('body').inner_text() 
                desc_page.close()
                
                # 1. AI Processing Node
                print(f"Tailoring documents for {company}...")
                tailored_cv = tailor_document('Bradley Kingswell CV Example.md', description, company)
                tailored_cl = tailor_document('BK Cover Letter Example.md', description, company)
                
                # 2. Dispatch Node
                print(f"Dispatching email for {company}...")
                dispatch_application(title, company, description, target_url, tailored_cv, tailored_cl)
                
                # 3. Add to Ledger
                seen_urls.append(job_url)
                
        browser.close()
        save_ledger(seen_urls)

if __name__ == '__main__':
    scrape_new_jobs()
    print("Daily pipeline execution complete.")
