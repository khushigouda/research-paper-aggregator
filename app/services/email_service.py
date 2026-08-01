import os
import sys
import html
import re
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import markdown

# Ensure root folder is in python path
root_dir = str(Path(__file__).parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(override=True)


def send_email(subject: str, body_text: str, body_html: str = None, recipients: list = None):
    """
    Sends an email using HTTP API (Resend / SendGrid - HTTPS port 443) or Gmail SMTP.
    HTTP APIs are recommended for Render Free Tier where outbound SMTP ports are blocked.
    """
    load_dotenv(override=True)
    my_email = os.getenv("MY_EMAIL")
    app_password = os.getenv("APP_PASSWORD")
    resend_api_key = os.getenv("RESEND_API_KEY")
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY")

    if recipients is None:
        if not my_email:
            raise ValueError("MY_EMAIL environment variable is not set in your .env file")
        recipients = [my_email]
    
    recipients = [r for r in recipients if r is not None]
    if not recipients:
        raise ValueError("No valid recipients provided")

    # 1. Try Resend HTTP REST API (HTTPS port 443 - Works on Render Free Tier)
    if resend_api_key:
        print("[EmailService] Sending email via Resend HTTP API...")
        try:
            import requests
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": os.getenv("FROM_EMAIL", "onboarding@resend.dev"),
                    "to": recipients,
                    "subject": subject,
                    "text": body_text,
                    "html": body_html or body_text
                },
                timeout=15
            )
            if resp.status_code in [200, 201, 202]:
                print("✅ Email dispatched successfully via Resend HTTP API.")
                return True
            else:
                print(f"⚠️ Resend HTTP API error ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"⚠️ Resend HTTP API failed: {e}")

    # 2. Try SendGrid HTTP REST API (HTTPS port 443)
    if sendgrid_api_key:
        print("[EmailService] Sending email via SendGrid HTTP API...")
        try:
            import requests
            resp = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {sendgrid_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "personalizations": [{"to": [{"email": r} for r in recipients]}],
                    "from": {"email": my_email},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": body_html or body_text}]
                },
                timeout=15
            )
            if resp.status_code in [200, 202]:
                print("✅ Email dispatched successfully via SendGrid HTTP API.")
                return True
            else:
                print(f"⚠️ SendGrid HTTP API error ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"⚠️ SendGrid HTTP API failed: {e}")

    # 3. Fallback to standard SMTP (Gmail)
    if not my_email or not app_password:
        raise ValueError("MY_EMAIL and APP_PASSWORD environment variables are required for SMTP.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = my_email
    msg["To"] = ", ".join(recipients)
    
    part1 = MIMEText(body_text, "plain")
    msg.attach(part1)
    
    if body_html:
        part2 = MIMEText(body_html, "html")
        msg.attach(part2)
    
    return smtplib_send_email(my_email, app_password, recipients, msg)


def smtplib_send_email(my_email: str, app_password: str, recipients: list, msg: MIMEMultipart):
    import smtplib
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(my_email, app_password)
            smtp.sendmail(my_email, recipients, msg.as_string())
            print("✅ Email dispatched successfully via STARTTLS (port 587)")
            return True
    except Exception as err587:
        print(f"⚠️ Port 587 STARTTLS failed ({err587}). Trying SSL port 465 fallback...")
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
                smtp.login(my_email, app_password)
                smtp.sendmail(my_email, recipients, msg.as_string())
                print("✅ Email dispatched successfully via SSL (port 465)")
                return True
        except Exception as err465:
            print(f"❌ SMTP failed: {err465}")
            print("💡 Tip: Render Free Tier blocks outbound SMTP ports 25, 465, 587.")
            print("To send emails on Render Free Tier, get a free API key from Resend.com (3,000 free emails/mo) and set RESEND_API_KEY in Render environment variables!")
            raise err465


def _wrap_in_email_template(html_body_content: str) -> str:
    """
    Wraps raw HTML content inside a minimal, highly-readable email template.
    Uses modest typography, soft gray dividers, clean link styling, and small headings.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            max-width: 580px;
            margin: 0 auto;
            padding: 24px 16px;
            background-color: #ffffff;
        }}
        h1 {{
            font-size: 20px;
            font-weight: 700;
            color: #111827;
            margin-top: 0;
            margin-bottom: 12px;
            line-height: 1.3;
        }}
        h2 {{
            font-size: 16px;
            font-weight: 600;
            color: #111827;
            margin-top: 20px;
            margin-bottom: 8px;
            line-height: 1.35;
        }}
        h3 {{
            font-size: 14px;
            font-weight: 600;
            color: #374151;
            margin-top: 16px;
            margin-bottom: 6px;
            line-height: 1.35;
        }}
        p {{
            font-size: 14px;
            margin: 8px 0;
            color: #374151;
        }}
        strong {{
            font-weight: 600;
            color: #111827;
        }}
        em {{
            font-style: italic;
            color: #6b7280;
        }}
        a {{
            color: #2563eb;
            text-decoration: none;
            font-weight: 500;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        ul, ol {{
            margin: 8px 0 12px 20px;
            padding: 0;
            font-size: 14px;
            color: #374151;
        }}
        li {{
            margin-bottom: 4px;
        }}
        blockquote {{
            margin: 12px 0;
            padding: 8px 12px;
            border-left: 3px solid #e5e7eb;
            color: #4b5563;
            background-color: #f9fafb;
            font-size: 14px;
        }}
        hr {{
            border: none;
            border-top: 1px solid #f3f4f6;
            margin: 20px 0;
        }}
        .greeting {{
            font-size: 15px;
            font-weight: 600;
            color: #111827;
            margin-bottom: 8px;
        }}
        .introduction {{
            font-size: 14px;
            color: #4b5563;
            margin-bottom: 16px;
        }}
        .article-link {{
            display: inline-block;
            margin-top: 6px;
            color: #2563eb;
            font-size: 13px;
            font-weight: 500;
        }}
    </style>
</head>
<body>
{html_body_content}
</body>
</html>"""


def clean_equations(text: str) -> str:
    """
    Strips raw LaTeX math notation, equations, and dollar-delimited formulas ($...$, $$...$$)
    so text renders cleanly as plain text without broken math code in HTML emails.
    """
    if not text:
        return ""
    # Remove block math $$ ... $$
    text = re.sub(r'\$\$(.*?)\$\$', r'\1', text, flags=re.DOTALL)
    # Remove inline math $ ... $
    text = re.sub(r'\$(.*?)\$', r'\1', text)
    # Convert common LaTeX macros
    text = re.sub(r'\\mathbb\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\mathcal\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\mathbf\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', text)
    # Strip remaining LaTeX commands
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    return text


def markdown_to_html(markdown_text: str) -> str:
    """
    Converts a Markdown string into clean, minimal HTML wrapped in the email template.
    Strips raw LaTeX equations before rendering to guarantee clean email display.
    """
    cleaned_md = clean_equations(markdown_text)
    converted_html = markdown.markdown(cleaned_md, extensions=['extra', 'nl2br'])
    return _wrap_in_email_template(converted_html)


def digest_to_html(digest_response) -> str:
    """
    Converts a research digest response object (Pydantic EmailDigestPayload,
    EmailDigestResponse, or raw Markdown text) into structured minimal HTML.
    """
    # 1. Prefer complete body_markdown if available
    body_md = getattr(digest_response, 'body_markdown', None)
    if body_md and isinstance(body_md, str) and body_md.strip():
        return markdown_to_html(body_md)

    # 2. Check for object with to_markdown() method
    if hasattr(digest_response, 'to_markdown') and callable(getattr(digest_response, 'to_markdown')):
        return markdown_to_html(digest_response.to_markdown())

    # 3. Build from structured attributes (greeting, intro_summary / introduction, articles)
    greeting_text = getattr(digest_response, 'greeting', '')
    intro_text = getattr(digest_response, 'intro_summary', '')
    articles_list = getattr(digest_response, 'articles', [])

    if not greeting_text and hasattr(digest_response, 'introduction'):
        intro_obj = getattr(digest_response, 'introduction')
        greeting_text = getattr(intro_obj, 'greeting', '')
    
    if not intro_text and hasattr(digest_response, 'introduction'):
        intro_obj = getattr(digest_response, 'introduction')
        intro_text = getattr(intro_obj, 'introduction', '')

    if articles_list or greeting_text or intro_text:
        html_parts = []
        if greeting_text:
            g_html = markdown.markdown(str(greeting_text), extensions=['extra', 'nl2br'])
            html_parts.append(f'<div class="greeting">{g_html}</div>')
        if intro_text:
            i_html = markdown.markdown(str(intro_text), extensions=['extra', 'nl2br'])
            html_parts.append(f'<div class="introduction">{i_html}</div>')
        
        if html_parts:
            html_parts.append('<hr>')

        for article in articles_list:
            title = getattr(article, 'title', 'Untitled Paper')
            summary = getattr(article, 'summary', '')
            url = getattr(article, 'url', '#')

            html_parts.append(f'<h2>{html.escape(title)}</h2>')
            if summary:
                s_html = markdown.markdown(str(summary), extensions=['extra', 'nl2br'])
                html_parts.append(f'<div>{s_html}</div>')
            if url and url != '#':
                html_parts.append(f'<p><a href="{html.escape(url)}" class="article-link">Read Full Paper →</a></p>')
            html_parts.append('<hr>')

        return _wrap_in_email_template('\n'.join(html_parts))

    # 4. Fallback for plain string inputs
    return markdown_to_html(str(digest_response))


def send_email_to_self(subject: str, body: str, body_html: str = None):
    """
    Helper function to send an email to the configured MY_EMAIL.
    """
    load_dotenv(override=True)
    my_email = os.getenv("MY_EMAIL")
    if not my_email:
        raise ValueError("MY_EMAIL environment variable is not set. Please set it in your .env file.")
    send_email(subject, body, body_html=body_html, recipients=[my_email])


if __name__ == "__main__":
    load_dotenv(override=True)
    my_email = os.getenv("MY_EMAIL")
    app_password = os.getenv("APP_PASSWORD")

    sample_md = "## Test Digest\nHey Khushi,\nHere is your test summary."
    sample_html = markdown_to_html(sample_md)

    if my_email and app_password:
        print(f"[EmailService] Sending test email to: {my_email}")
        send_email_to_self("Test Email from EmailService", sample_md, body_html=sample_html)
        print("✅ Email Service Test: SUCCESS")
    else:
        print("ℹ️ Email Service Test: Skipped (MY_EMAIL or APP_PASSWORD missing in .env)")
