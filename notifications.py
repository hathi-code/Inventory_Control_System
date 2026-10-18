import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Reads the .env file in your project root and loads its values
# into environment variables, so os.getenv() below can find them.
load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# SMS support (Twilio) was designed for but is disabled in this deployment —
# trial-account phone number provisioning was blocked by regional carrier
# verification requirements. The functions below are left in place so the
# multi-channel design is still visible/documented; they are simply not
# called from notify_admin_of_pending_order / notify_order_decision.
#
# TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
# TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
# ADMIN_PHONE_NUMBER = os.getenv("ADMIN_PHONE_NUMBER")


def send_approval_email(order):
    """Sends an email to the admin when an order needs approval.
    Fire-and-forget: any failure here is caught and logged, never
    allowed to crash the calling code (the agent pipeline)."""
    subject = f"Approval needed: {order.sku} purchase order"
    body = (
        f"A purchase order requires your approval.\n\n"
        f"SKU: {order.sku}\n"
        f"Quantity: {order.quantity_ordered}\n"
        f"Order value: Rs.{order.order_value}\n"
        f"Reason: {order.reason}\n\n"
        f"Log in to the dashboard to approve or reject this order."
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = ADMIN_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.send_message(msg)
        print(f"[notifications] Approval email sent for order {order.sku}")
    except Exception as e:
        print(f"[notifications] FAILED to send approval email: {e}")


# def send_approval_sms(order):
#     """Sends an SMS to the admin when an order needs approval.
#     Disabled — see note above."""
#     try:
#         from twilio.rest import Client
#         client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
#         client.messages.create(
#             body=(
#                 f"Approval needed: {order.sku}, qty {order.quantity_ordered}, "
#                 f"value Rs.{order.order_value}"
#             ),
#             from_=TWILIO_FROM_NUMBER,
#             to=ADMIN_PHONE_NUMBER,
#         )
#         print(f"[notifications] Approval SMS sent for order {order.sku}")
#     except Exception as e:
#         print(f"[notifications] FAILED to send approval SMS: {e}")


def notify_admin_of_pending_order(order):
    """Single entry point used by the rest of the app. Call this one
    function whenever an order needs human approval. Email is the
    active channel; SMS (Twilio) is disabled — see note above."""
    send_approval_email(order)
    # send_approval_sms(order)


def notify_order_decision(order, decision):
    """Notifies the admin that a decision (approve/reject) has been
    made on an order — a confirmation notification, separate from
    the original approval-needed alert above.
    'decision' should be the string 'approved' or 'rejected'."""
    subject = f"Order {decision}: {order.sku}"
    body = (
        f"The following purchase order has been {decision}.\n\n"
        f"SKU: {order.sku}\n"
        f"Quantity: {order.quantity_ordered}\n"
        f"Order value: Rs.{order.order_value}\n"
        f"Reviewed by: {order.reviewed_by}\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = ADMIN_EMAIL

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
            server.send_message(msg)
        print(f"[notifications] Decision email sent for order {order.sku} ({decision})")
    except Exception as e:
        print(f"[notifications] FAILED to send decision email: {e}")

    # try:
    #     from twilio.rest import Client
    #     client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    #     client.messages.create(
    #         body=f"Order {decision}: {order.sku}, qty {order.quantity_ordered}",
    #         from_=TWILIO_FROM_NUMBER,
    #         to=ADMIN_PHONE_NUMBER,
    #     )
    #     print(f"[notifications] Decision SMS sent for order {order.sku} ({decision})")
    # except Exception as e:
    #     print(f"[notifications] FAILED to send decision SMS: {e}")