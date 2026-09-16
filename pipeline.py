import os
import json
from scraper import scrape_new_jobs
from dispatch import dispatch_application

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_role_descriptions():
    # Cache path in scratch or fallback to live extraction
    desc_file = '/Users/bradleykingswell/.gemini/antigravity/brain/ac4fc065-e9b1-4cd8-8a30-1bd78421fae3/scratch/all_3_roles.json'
    if os.path.exists(desc_file):
        with open(desc_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {item['company']: item['description'] for item in data}
    return {}

def run_pipeline():
    print("="*60)
    print("Starting Grad Jobs Automation Pipeline")
    print("="*60)
    
    # 1. Scrape latest new jobs from Trackr
    print("\n[Step 1] Extracting latest jobs from Trackr...")
    jobs = scrape_new_jobs()
    print(f"Scraper returned {len(jobs)} new roles.")
    
    # Store scraped descriptions by company
    scraped_descriptions = {j['company']: j['description'] for j in jobs}
    cached_descriptions = get_role_descriptions()

    print("\n[Step 2] Dispatching tailored applications with full descriptions...")
    roles_to_dispatch = [
        {
            "company": "Equiteq",
            "title": "Analyst - Investment Banking M&A",
            "url": "https://equiteq.careers.hibob.com/jobs/a7e3bf9f-8a0e-44d6-a25a-f1d7293ce3aa?utm_source=Trackr&utm_medium=tracker&utm_campaign=UK_Finance_2027",
            "cl_file": "BK Cover Letter - Equiteq.md",
            "cv_file": "Bradley Kingswell CV - Equiteq.md"
        },
        {
            "company": "Wintermute",
            "title": "Wintermute Trader Assessment Day",
            "url": "https://jobs.lever.co/wintermute-trading/61f162a0-b51b-44ed-b2b9-9d7260eee6f2?utm_source=Trackr&utm_medium=tracker&utm_campaign=UK_Finance_2027&lever-source=Trackr",
            "cl_file": "BK Cover Letter - Wintermute.md",
            "cv_file": "Bradley Kingswell CV - Wintermute.md"
        },
        {
            "company": "London Stock Exchange Group",
            "title": "Business Graduate Programme 2027",
            "url": "https://lseg.wd3.myworkdayjobs.com/en-US/Graduate_Careers/details/Business-Analyst-Graduate-Programme-_R0123408-2?utm_source=Trackr&utm_medium=tracker&utm_campaign=UK_Finance_2027&source=Trackr&q=%22graduate+programme%22&locationCountry=29247e57dbaf46fb855b224e03170bc7",
            "cl_file": "BK Cover Letter - LSEG.md",
            "cv_file": "Bradley Kingswell CV - LSEG.md"
        }
    ]

    for role in roles_to_dispatch:
        cl_path = os.path.join(WORKSPACE_DIR, role['cl_file'])
        cv_path = os.path.join(WORKSPACE_DIR, role['cv_file'])
        
        if os.path.exists(cl_path) and os.path.exists(cv_path):
            print(f"\nDispatching application for {role['company']} ({role['title']})...")
            with open(cl_path, 'r', encoding='utf-8') as f:
                cl_md = f.read()
            with open(cv_path, 'r', encoding='utf-8') as f:
                cv_md = f.read()

            # Ensure full description is passed
            full_description = scraped_descriptions.get(role['company']) or cached_descriptions.get(role['company']) or f"Application for {role['company']} - {role['title']}."
            print(f"  Description length: {len(full_description)} characters")
                
            dispatch_application(
                job_title=role['title'],
                company=role['company'],
                job_description=full_description,
                job_url=role['url'],
                cv_md=cv_md,
                cl_md=cl_md
            )
            print(f"Successfully dispatched: GET A JOB BRADLEY: {role['company']} - {role['title']}")

    print("\nPipeline execution complete!")

if __name__ == '__main__':
    run_pipeline()
