import smtplib
from email.message import EmailMessage
import markdown2
import pdfkit
import os

def _to_pdf(md_content):
    html = markdown2.markdown(md_content)
    styled_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
    color: #1a1a1a;
    margin: 15mm;
  }}
  center, div[align="center"], p[align="center"] {{
    text-align: center;
    display: block;
    margin-bottom: 15px;
  }}
  h1, h2, h3, strong {{
    color: #111827;
  }}
  a {{
    color: #2563eb;
    text-decoration: none;
  }}
</style>
</head>
<body>
{html}
</body>
</html>"""
    try:
        return pdfkit.from_string(styled_html, False)
    except Exception:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(styled_html)
            pdf = page.pdf(margin={'top': '12mm', 'bottom': '12mm', 'left': '12mm', 'right': '12mm'})
            browser.close()
            return pdf

def dispatch_application(job_title, company, job_description, job_url, cv_md, cl_md):
    # 1. Convert tailored Markdown files to clean PDFs
    cv_pdf = _to_pdf(cv_md)
    cl_pdf = _to_pdf(cl_md)
    
    # 2. Construct the Email
    msg = EmailMessage()
    msg['Subject'] = f"GET A JOB BRADLEY: {company} - {job_title}"
    msg['From'] = "getajobbradley@gmail.com"
    msg['To'] = "bmkingswell@icloud.com"
    
    # Bundle the direct application link into the email body
    email_body = f"""New Graduate Role Found:
    
Title: {job_title}
Company: {company}

Direct Apply Link: {job_url}

Description:
{job_description}
"""
    msg.set_content(email_body)
    
    # 3. Attach your newly generated CV and Cover Letter
    msg.add_attachment(cv_pdf, maintype='application', subtype='pdf', filename=f"BK CV {company}.pdf")
    msg.add_attachment(cl_pdf, maintype='application', subtype='pdf', filename=f"BK Cover Letter {company}.pdf")
    
    # 4. Send the Email via Google's secure SMTP servers
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        gmail_password = os.environ.get('GMAIL_APP_PASSWORD')
        smtp.login('getajobbradley@gmail.com', gmail_password)
        smtp.send_message(msg)
