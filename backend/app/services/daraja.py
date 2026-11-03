from base64 import b64encode
from datetime import datetime
import httpx
from ..core.config import get_settings


class DarajaNotConfigured(Exception):
    pass


class DarajaResponseError(Exception):
    pass


def _phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("0"): return "254" + digits[1:]
    if digits.startswith("254"): return digits
    return digits


def initiate_stk(*, phone_number: str, amount: int, account_reference: str, description: str) -> dict:
    settings = get_settings()
    required = [settings.daraja_consumer_key, settings.daraja_consumer_secret, settings.daraja_passkey, settings.daraja_shortcode, settings.daraja_callback_url, settings.daraja_callback_secret]
    if not all(required): raise DarajaNotConfigured("Daraja credentials and callback URL are not configured")
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    credentials = b64encode(f"{settings.daraja_consumer_key}:{settings.daraja_consumer_secret}".encode()).decode()
    with httpx.Client(base_url=settings.daraja_base_url, timeout=20) as client:
        token_response = client.get("/oauth/v1/generate?grant_type=client_credentials", headers={"Authorization": f"Basic {credentials}"})
        token_response.raise_for_status()
        try:
            token = token_response.json()["access_token"]
        except (KeyError, TypeError, ValueError) as error:
            raise DarajaResponseError("Daraja did not return an access token") from error
        password = b64encode(f"{settings.daraja_shortcode}{settings.daraja_passkey}{stamp}".encode()).decode()
        response = client.post("/mpesa/stkpush/v1/processrequest", headers={"Authorization": "Bearer " + token}, json={"BusinessShortCode": settings.daraja_shortcode, "Password": password, "Timestamp": stamp, "TransactionType": "CustomerPayBillOnline", "Amount": amount, "PartyA": _phone(phone_number), "PartyB": settings.daraja_shortcode, "PhoneNumber": _phone(phone_number), "CallBackURL": settings.daraja_callback_url, "AccountReference": account_reference, "TransactionDesc": description})
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError as error:
            raise DarajaResponseError("Daraja returned an invalid STK response") from error
        if str(data.get("ResponseCode")) != "0" or not data.get("CheckoutRequestID"):
            raise DarajaResponseError(data.get("ResponseDescription") or "Daraja rejected the STK request")
        return data
