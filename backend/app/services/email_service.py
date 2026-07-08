import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

_PURPOSE_LABELS = {
    "register": "注册",
    "reset": "重置密码",
}


def send_verification_code(to_email: str, code: str, purpose: str = "register") -> bool:
    label = _PURPOSE_LABELS.get(purpose, "验证")
    sender = settings.smtp_from or settings.smtp_user
    subject = f"PageDrop {label}验证码"
    body = (
        f"您好，\n\n"
        f"您的 PageDrop {label}验证码是：\n\n"
        f"    {code}\n\n"
        f"验证码 {settings.verification_code_ttl_seconds // 60} 分钟内有效，请勿泄露给他人。\n\n"
        f"如果这不是您的操作，请忽略本邮件。\n\n"
        f"—— PageDrop"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"PageDrop <{sender}>"
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=12) as server:
            server.login(settings.smtp_user, settings.smtp_auth_code)
            server.sendmail(sender, [to_email], msg.as_string())
        return True
    except Exception as exc:
        print(f"[EMAIL] SMTP send failed: {type(exc).__name__}: {exc}")
        return False
