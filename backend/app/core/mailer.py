import os
import re
import ssl
import html
import urllib.parse
import smtplib
import logging
import secrets
from typing import Optional, Tuple, Dict, Any
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger("passkhadam.mailer")

ALLOWED_ACTIVATION_PATHS = {
    "/employer/activate",
    "/government/activate"
}

RAW_QUERY_REGEX = re.compile(r"^token=[a-zA-Z0-9_-]{32,64}$")

def validate_activation_url(url_str: str) -> bool:
    """
    Validates activation URLs against exact allowlisted route and query structure.
    Strictly rejects non-canonical tokens, encoded whitespace (%20, %09), and parameter pollution.
    """
    try:
        parsed = urllib.parse.urlparse(url_str)
        trusted_base = os.getenv("PUBLIC_APP_BASE_URL", "https://passkhadam.vercel.app")
        trusted_parsed = urllib.parse.urlparse(trusted_base)

        # 1. Scheme must be strictly HTTPS (or http on localhost for test/dev)
        if parsed.scheme not in ["https", "http"]:
            return False
        if parsed.scheme != "https" and parsed.netloc not in ["127.0.0.1:5173", "localhost:5173", "127.0.0.1:8000", "localhost:8000"]:
            return False

        # 2. Complete authority validation: exact netloc, no userinfo (@), no unexpected ports
        if parsed.scheme == "https":
            if parsed.netloc != trusted_parsed.netloc or parsed.port is not None or "@" in parsed.netloc:
                return False
        else:
            if "@" in parsed.netloc:
                return False

        # 3. Path must be an exact match from the allowlist
        if parsed.path not in ALLOWED_ACTIVATION_PATHS:
            return False

        # 4. Fragments are strictly forbidden
        if parsed.fragment:
            return False

        # 5. Non-canonical token rejection & query validation:
        # Require raw query to match the exact form 'token=' followed by 32-64 permitted characters,
        # without trimming, decoding, or normalization into a different accepted representation.
        if not RAW_QUERY_REGEX.fullmatch(parsed.query):
            return False

        # 6. Secondary query parser verification: guarantee exactly one single parameter named 'token'
        query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        if len(query_params) != 1 or "token" not in query_params or len(query_params["token"]) != 1:
            return False

        # Guarantee zero transformation or decoding drift between raw query and parsed value
        if query_params["token"][0] != parsed.query[len("token="):]:
            return False

        return True
    except Exception:
        return False

def send_resend_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Dispatches transactional email over HTTPS (Port 443) using the Resend REST API.
    Bypasses cloud provider SMTP egress blocking (Render ports 25, 465, 587).
    """
    api_key = os.getenv("RESEND_API_KEY") or getattr(settings, "RESEND_API_KEY", None)
    from_email = os.getenv("EMAILS_FROM_EMAIL") or getattr(settings, "EMAILS_FROM_EMAIL", None) or "onboarding@resend.dev"
    corr_id = correlation_id or f"corr_{secrets.token_hex(8)}"

    if not api_key:
        err = f"RESEND_API_KEY not configured. Dispatch aborted (correlation_id={corr_id})"
        logger.error(err)
        return False, err

    clean_from = from_email.strip()
    # Resend restricts unverified sender domains. If from_email is a Gmail/Yahoo/Outlook address, fallback to onboarding@resend.dev
    if any(clean_from.lower().endswith(d) for d in ("@gmail.com", "@yahoo.com", "@outlook.com", "@hotmail.com")):
        clean_from = "onboarding@resend.dev"

    payload = {
        "from": f"PASSKHADAM Governance <{clean_from}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }
    if text_content:
        payload["text"] = text_content

    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            if resp.status_code in [200, 201]:
                res_id = resp.json().get("id")
                logger.info(f"Activation email accepted by Resend API (id={res_id}, correlation_id={corr_id})")
                return True, None
            else:
                err = f"Resend API rejected dispatch with HTTP {resp.status_code} (correlation_id={corr_id})"
                logger.error(err)
                return False, err
    except Exception as exc:
        err = f"Resend API network error (correlation_id={corr_id}): {type(exc).__name__}"
        logger.error(err)
        return False, err

def get_mailer_config() -> dict:
    """
    Retrieves SMTP configuration from environment or settings.
    """
    host_env = os.getenv("SMTP_HOST")
    host = host_env if host_env is not None else getattr(settings, "SMTP_HOST", None)

    port_env = os.getenv("SMTP_PORT")
    port_raw = port_env if port_env is not None else getattr(settings, "SMTP_PORT", 587)
    try:
        port = int(str(port_raw).strip())
    except (ValueError, TypeError):
        port = 587

    user_env = os.getenv("SMTP_USER")
    user = user_env if user_env is not None else getattr(settings, "SMTP_USER", None)

    pass_env = os.getenv("SMTP_PASSWORD")
    password = pass_env if pass_env is not None else getattr(settings, "SMTP_PASSWORD", None)

    from_env = os.getenv("EMAILS_FROM_EMAIL")
    from_email = (
        from_env
        if from_env is not None
        else (getattr(settings, "EMAILS_FROM_EMAIL", None) or user or "noreply@passkhadam.org")
    )
    if not from_email or not str(from_email).strip():
        from_email = user or "noreply@passkhadam.org"

    return {
        "host": host.strip() if host and host.strip() else None,
        "port": port,
        "user": user.strip() if user and user.strip() else None,
        "password": password.strip() if password and password.strip() else None,
        "from_email": from_email.strip() if from_email and from_email.strip() else "noreply@passkhadam.org",
    }

def is_smtp_configured() -> bool:
    """
    Returns True if SMTP_HOST or RESEND_API_KEY is configured.
    """
    cfg = get_mailer_config()
    resend_key = os.getenv("RESEND_API_KEY") or getattr(settings, "RESEND_API_KEY", None)
    return bool(cfg["host"] or (resend_key and str(resend_key).strip()))

def build_otp_email_message(
    to_email: str,
    otp_code: str,
    from_email: Optional[str] = None,
    subject: Optional[str] = None
) -> MIMEMultipart:
    """
    Constructs a dual plaintext & rich HTML email for OTP verification.
    """
    if any(c in str(to_email) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in recipient email address")
    if any(c in str(otp_code) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in OTP code")

    cfg = get_mailer_config()
    sender = from_email or cfg["from_email"]
    subj = subject or "PASSKHADAM — Your Verification Code"

    if any(c in str(sender) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in sender email address")
    if any(c in str(subj) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in email subject")

    safe_otp = html.escape(str(otp_code).strip())

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = formataddr(("PassKhadam Identity", sender))
    msg["To"] = to_email

    # Plaintext fallback body
    text_body = f"""Hello,

Your PASSKHADAM verification code is:

    {otp_code}

This 6-digit code will expire in 5 minutes.
For security, please never share this verification code with anyone.

If you did not request this verification, please safely ignore this message.

—
PassKhadam Decentralized Identity Gateway
Secure, Portable Worker Identity
"""

    # Rich responsive HTML body
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PASSKHADAM Verification Code</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b1120; padding: 40px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 540px; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);">
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); padding: 32px 24px; text-align: center;">
              <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">PASSKHADAM</h1>
              <p style="margin: 6px 0 0 0; color: #bfdbfe; font-size: 13px; font-weight: 500;">Decentralized Migrant Worker Identity & Welfare</p>
            </td>
          </tr>
          <!-- Body Content -->
          <tr>
            <td style="padding: 32px 28px;">
              <h2 style="margin: 0 0 12px 0; font-size: 18px; color: #f8fafc; font-weight: 600;">Email Verification Code</h2>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                Use the 6-digit verification code below to confirm your email address and activate your PassKhadam decentralized identity.
              </p>
              
              <!-- Code Container -->
              <div style="background-color: #020617; border: 1px solid #334155; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 24px;">
                <span style="font-family: 'Courier New', Courier, monospace; font-size: 34px; font-weight: 700; letter-spacing: 8px; color: #38bdf8; display: inline-block;">
                  {safe_otp}
                </span>
                <p style="margin: 8px 0 0 0; font-size: 12px; color: #64748b;">
                  Valid for <strong>5 minutes</strong> (Expires soon)
                </p>
              </div>

              <!-- Notice Box -->
              <div style="background-color: #1e293b; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 12px 16px; margin-bottom: 24px;">
                <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #cbd5e1;">
                  🔒 <strong>Security Advice:</strong> PassKhadam officers and employers will never ask for your verification code. Never share this code with anyone.
                </p>
              </div>

              <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #64748b;">
                If you did not request this verification code, no further action is required. Your account remains secure.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color: #020617; border-top: 1px solid #1e293b; padding: 20px 24px; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #475569;">
                PASSKHADAM — Empowering Migrant Workforce Dignity & Portability.<br/>
                Official automated dispatch. Please do not reply directly to this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    part_text = MIMEText(text_body, "plain", "utf-8")
    part_html = MIMEText(html_body, "html", "utf-8")
    msg.attach(part_text)
    msg.attach(part_html)

    return msg

def send_otp_email(
    to_email: str,
    otp_code: str,
    subject: Optional[str] = None,
    timeout: int = 10
) -> Tuple[bool, Optional[str]]:
    """
    Dispatches a real email via SMTP using standard library smtplib.
    Supports STARTTLS (standard port 587) and SSL (port 465).
    Returns (True, None) on success, or (False, error_description) on failure.
    """
    cfg = get_mailer_config()
    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    from_email = cfg["from_email"]

    if not to_email or not str(to_email).strip():
        err = "Recipient email address is required."
        logger.warning(err)
        return False, err

    if any(c in str(to_email) for c in ("\r", "\n")):
        err = "Recipient email address contains invalid newline characters."
        logger.warning(err)
        return False, err

    if any(c in str(otp_code) for c in ("\r", "\n")):
        err = "OTP code contains invalid newline characters."
        logger.warning(err)
        return False, err

    if subject and any(c in str(subject) for c in ("\r", "\n")):
        err = "Email subject contains invalid newline characters."
        logger.warning(err)
        return False, err

    if not host:
        err = "SMTP host is not configured."
        logger.warning(err)
        return False, err

    try:
        msg = build_otp_email_message(
            to_email=to_email,
            otp_code=otp_code,
            from_email=from_email,
            subject=subject
        )

        logger.info(f"Connecting to SMTP server {host}:{port}...")

        if port == 465:
            # SSL context
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=timeout) as server:
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
        else:
            # Standard SMTP with STARTTLS
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                try:
                    server.starttls(context=context)
                    server.ehlo()
                except smtplib.SMTPNotSupportedError:
                    logger.debug("STARTTLS not supported by server, proceeding unencrypted.")
                except Exception as tls_err:
                    logger.warning(f"STARTTLS failed or unconfirmed: {tls_err}")

                if user and password:
                    server.login(user, password)
                server.send_message(msg)

        logger.info(f"Successfully dispatched OTP email to {to_email} via SMTP ({host}:{port})")
        return True, None

    except smtplib.SMTPAuthenticationError as auth_err:
        err_msg = f"SMTP Authentication failed: {auth_err}"
        logger.error(err_msg)
        return False, err_msg
    except smtplib.SMTPConnectError as conn_err:
        err_msg = f"Failed to connect to SMTP server: {conn_err}"
        logger.error(err_msg)
        return False, err_msg
    except Exception as exc:
        err_msg = f"SMTP dispatch error: {exc}"
        logger.error(err_msg)
        return False, err_msg


def build_activation_email_message(
    to_email: str,
    activation_link: str,
    entity_type: str = "GOVERNMENT",
    custom_message: Optional[str] = None,
    from_email: Optional[str] = None,
    subject: Optional[str] = None,
    raw_token: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> MIMEMultipart:
    """
    Constructs a dual plaintext & rich HTML email for account activation.
    Includes:
    - Direct activation button and link
    - Distinctly separated and copyable single-use Activation Token
    - Structured account & jurisdiction / category provisioning details
    - Fallback instructions for manual portal token redemption
    """
    if any(c in str(to_email) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in recipient email address")
    if any(c in str(activation_link) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in activation link")

    cfg = get_mailer_config()
    sender = from_email or cfg["from_email"]

    is_gov = str(entity_type).upper() == "GOVERNMENT"
    role_label = "Government Officer" if is_gov else "Employer Organization"
    portal_tab = "Activate Gov" if is_gov else "Activate Org"
    subj = subject or f"PASSKHADAM - Activate Your {role_label} Account"

    if any(c in str(sender) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in sender email address")
    if any(c in str(subj) for c in ("\r", "\n")):
        raise ValueError("Invalid newline character in email subject")

    # Extract raw token from link if not explicitly supplied
    token_str = (raw_token or "").strip()
    if not token_str:
        tok_m = re.search(r"[?&]token=([^&]+)", str(activation_link))
        if tok_m:
            token_str = tok_m.group(1).strip()

    # Determine base portal URL
    parsed_url = urllib.parse.urlparse(activation_link)
    base_portal_url = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else "http://127.0.0.1:5173"

    safe_link = html.escape(str(activation_link).strip())
    safe_token = html.escape(token_str)
    safe_custom = html.escape(str(custom_message).strip()) if custom_message else ""
    safe_portal_url = html.escape(base_portal_url)

    # Build details dictionary if not supplied
    info = details or {}

    detail_lines_text = []
    detail_rows_html = []

    def _add_field(label: str, val: Any):
        if val is None or val == "":
            return
        if isinstance(val, (list, tuple)):
            val_str = ", ".join(str(item) for item in val if item)
        else:
            val_str = str(val).strip()
        if not val_str:
            return
        detail_lines_text.append(f"- {label}: {val_str}")
        detail_rows_html.append(
            f'<tr><td style="padding: 6px 12px; color: #94a3b8; font-weight: 600; width: 40%; vertical-align: top;">{html.escape(label)}:</td>'
            f'<td style="padding: 6px 12px; color: #f1f5f9; font-weight: 500;">{html.escape(val_str)}</td></tr>'
        )

    if is_gov:
        _add_field("Officer Name", info.get("full_name") or info.get("officer_name"))
        _add_field("Official Email", to_email)
        _add_field("Officer Reference ID", info.get("badge_number") or info.get("officer_reference_id"))
        _add_field("Department", info.get("department"))
        _add_field("Designation", info.get("designation"))
        _add_field("Authority Level", info.get("authority_level"))
        _add_field("Geographic Jurisdiction", info.get("jurisdiction"))
        _add_field("Allowed Benefit Schemes", info.get("benefit_permissions"))
    else:
        _add_field("Organization Name", info.get("organization_name"))
        _add_field("Official Email", to_email)
        _add_field("Registration Number", info.get("registration_number"))
        _add_field("State / Jurisdiction", info.get("state"))
        _add_field("Authorized Categories", info.get("authorized_categories") or info.get("categories"))

    _add_field("Token Validity", "48 hours (Single-use redemption)")

    text_details_block = "\n".join(detail_lines_text) if detail_lines_text else f"- Official Email: {to_email}\n- Token Validity: 48 hours"
    html_details_table = "\n".join(detail_rows_html)

    custom_text = f"\nNote from Platform Governance: {custom_message}\n" if custom_message else ""
    custom_html = f"""<div style="background-color: #1e293b; border-left: 4px solid #3b82f6; border-radius: 6px; padding: 12px 16px; margin: 16px 0;">
      <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #cbd5e1;">
        <strong>Admin Note:</strong> {safe_custom}
      </p>
    </div>""" if custom_message else ""

    text_body = f"""Hello,

Your PASSKHADAM {role_label} account has been provisioned by the platform administrator.
{custom_text}
================================================================================
ACCOUNT & PROVISIONING DETAILS
================================================================================
{text_details_block}

================================================================================
ACTIVATION TOKEN (SINGLE-USE)
================================================================================
{token_str}

================================================================================
HOW TO ACTIVATE YOUR ACCOUNT
================================================================================

OPTION 1: Open Direct Activation Link:
{activation_link}

OPTION 2: Manual Token Activation (Recommended if link does not open):
1. Open your browser and go to your PassKhadam portal:
   {base_portal_url}
2. Click "Sign In" in the navigation bar.
3. Switch to the "{portal_tab}" tab.
4. Paste your Activation Token:
   {token_str}
5. Enter your new password and click "Activate & Set Password".

Security Notice:
This single-use activation token expires in 48 hours.
If you did not expect this invitation, please contact your platform administrator.

-
PassKhadam Decentralized Identity Gateway
National Migrant Worker Identity & Welfare Platform
"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subj}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #f1f5f9;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #0b1120; padding: 30px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 580px; background-color: #0f172a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);">
          <tr>
            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%); padding: 30px 24px; text-align: center;">
              <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 800; letter-spacing: 0.5px;">PASSKHADAM</h1>
              <p style="margin: 6px 0 0 0; color: #bfdbfe; font-size: 13px; font-weight: 500;">{role_label} Account Activation</p>
            </td>
          </tr>
          <tr>
            <td style="padding: 28px 24px;">
              <h2 style="margin: 0 0 10px 0; font-size: 18px; color: #f8fafc; font-weight: 700;">Account Provisioned Successfully</h2>
              <p style="margin: 0 0 16px 0; font-size: 14px; line-height: 1.6; color: #94a3b8;">
                Your {role_label} account has been provisioned on the PASSKHADAM platform. Review your account details and use the credentials below to activate your account.
              </p>
              {custom_html}

              <!-- Account Details Card -->
              <div style="margin: 20px 0; background-color: #0b1120; border: 1px solid #1e293b; border-radius: 10px; overflow: hidden;">
                <div style="background-color: #1e293b; padding: 8px 14px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #cbd5e1;">
                  Account & Provisioning Details
                </div>
                <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 13px; border-collapse: collapse; margin: 6px 0;">
                  {html_details_table}
                </table>
              </div>

              <!-- Activation Token Box -->
              <div style="margin: 24px 0; background-color: #0b1120; border: 1px dashed #3b82f6; border-radius: 10px; padding: 16px; text-align: center;">
                <span style="display: block; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #93c5fd; font-weight: 700; margin-bottom: 6px;">Single-Use Activation Token</span>
                <code style="display: block; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 15px; font-weight: 700; color: #38bdf8; background: #030712; padding: 10px 12px; border-radius: 6px; word-break: break-all; border: 1px solid #1e293b;">{safe_token}</code>
                <span style="display: block; font-size: 11px; color: #64748b; margin-top: 8px;">Copy this token to redeem manually in the portal tab</span>
              </div>

              <!-- Action Button -->
              <div style="text-align: center; margin: 24px 0 20px 0;">
                <a href="{safe_link}" style="display: inline-block; background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 700; font-size: 14px; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);">Activate Account Directly</a>
              </div>

              <!-- Manual Redemption Instructions -->
              <div style="background-color: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 14px 16px; margin-top: 20px; font-size: 12px; color: #94a3b8; line-height: 1.6;">
                <strong style="color: #f1f5f9; display: block; margin-bottom: 6px;">Manual Activation Steps:</strong>
                If the button above does not open automatically:
                <ol style="margin: 6px 0 0 0; padding-left: 20px;">
                  <li>Open your browser at <a href="{safe_portal_url}" style="color: #60a5fa; text-decoration: underline;">{safe_portal_url}</a></li>
                  <li>Click <strong>Sign In</strong> in the top navigation bar</li>
                  <li>Switch to the <strong>{portal_tab}</strong> tab</li>
                  <li>Paste your Activation Token and choose your account password</li>
                </ol>
              </div>

              <p style="margin: 20px 0 0 0; font-size: 11px; line-height: 1.5; color: #64748b; text-align: center;">
                This single-use activation link and token expire in <strong>48 hours</strong>.<br>
                PassKhadam Decentralized Identity Gateway &bull; Official Governance Dispatch
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj
    msg["From"] = formataddr(("PassKhadam Governance", sender))
    msg["To"] = to_email

    try:
        part_text = MIMEText(text_body, "plain", "us-ascii")
    except UnicodeEncodeError:
        part_text = MIMEText(text_body, "plain", "utf-8")

    try:
        part_html = MIMEText(html_body, "html", "us-ascii")
    except UnicodeEncodeError:
        part_html = MIMEText(html_body, "html", "utf-8")

    msg.attach(part_text)
    msg.attach(part_html)

    return msg


def send_activation_email(
    to_email: str,
    activation_link: str,
    entity_type: str = "GOVERNMENT",
    custom_message: Optional[str] = None,
    subject: Optional[str] = None,
    timeout: int = 10,
    raw_token: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Dispatches an activation email via HTTPS Resend API (priority) or SMTP fallback.
    Validates activation URL against exact allowlisted routes and canonical query structure.
    Never logs raw tokens on error to maintain zero-token logging invariants.
    """
    correlation_id = f"corr_{secrets.token_hex(8)}"

    if not to_email or not str(to_email).strip():
        err = "Recipient email address is required."
        logger.warning(err)
        return False, err

    if any(c in str(to_email) for c in ("\r", "\n")):
        err = "Recipient email address contains invalid newline characters."
        logger.warning(err)
        return False, err

    # Strict Validation of Activation URL (Blocks parameter pollution, encoded whitespace, hostile hosts)
    # NOTE: Never log activation_link on error to prevent raw token leakage
    if not validate_activation_url(activation_link):
        logger.error(f"Security Alert: Blocked dispatch with untrusted activation URL structure (correlation_id={correlation_id}, error_code=INVALID_ACTIVATION_URL)")
        return False, "Invalid activation URL structure"

    # 1. Prefer HTTPS Resend API over port 443 (Active in cloud mode or when RESEND_API_KEY is configured)
    resend_key = os.getenv("RESEND_API_KEY") or getattr(settings, "RESEND_API_KEY", None)
    if resend_key:
        msg = build_activation_email_message(
            to_email=to_email,
            activation_link=activation_link,
            entity_type=entity_type,
            custom_message=custom_message,
            subject=subject,
            raw_token=raw_token,
            details=details
        )
        html_payload = ""
        text_payload = ""
        for part in msg.get_payload():
            if part.get_content_type() == "text/html":
                html_payload = part.get_payload()
            elif part.get_content_type() == "text/plain":
                text_payload = part.get_payload()

        subj = subject or f"PASSKHADAM - Activate Your {str(entity_type).capitalize()} Account"
        resend_sent, resend_err = send_resend_email(
            to_email=to_email,
            subject=subj,
            html_content=html_payload,
            text_content=text_payload,
            correlation_id=correlation_id
        )
        if resend_sent:
            return True, None
        logger.warning(f"Resend API dispatch failed ({resend_err}). Falling back to SMTP transport...")

    # 2. Fallback to SMTP if configured
    cfg = get_mailer_config()
    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    from_email = cfg["from_email"]

    if not host:
        err = "Neither RESEND_API_KEY nor SMTP host is configured."
        logger.warning(err)
        return False, err

    try:
        msg = build_activation_email_message(
            to_email=to_email,
            activation_link=activation_link,
            entity_type=entity_type,
            custom_message=custom_message,
            from_email=from_email,
            subject=subject,
            raw_token=raw_token,
            details=details
        )

        logger.info(f"Connecting to SMTP server {host}:{port} for activation dispatch...")

        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=timeout) as server:
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
        else:
            context = ssl.create_default_context()
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                try:
                    server.starttls(context=context)
                    server.ehlo()
                except smtplib.SMTPNotSupportedError:
                    logger.debug("STARTTLS not supported by server, proceeding unencrypted.")
                except Exception as tls_err:
                    logger.warning(f"STARTTLS failed or unconfirmed: {tls_err}")

                if user and password:
                    server.login(user, password)
                server.send_message(msg)

        logger.info(f"Successfully dispatched activation email to {to_email} via SMTP ({host}:{port})")
        return True, None

    except smtplib.SMTPAuthenticationError as auth_err:
        err_msg = f"SMTP Authentication failed: {auth_err}"
        logger.error(err_msg)
        return False, err_msg
    except smtplib.SMTPConnectError as conn_err:
        err_msg = f"Failed to connect to SMTP server: {conn_err}"
        logger.error(err_msg)
        return False, err_msg
    except Exception as exc:
        err_msg = f"SMTP dispatch error: {exc}"
        logger.error(err_msg)
        return False, err_msg
