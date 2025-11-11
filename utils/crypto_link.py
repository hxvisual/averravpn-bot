import logging
from typing import Optional

import httpx

HAPP_CRYPTO_ENDPOINT = "https://crypto.happ.su/api.php"

logger = logging.getLogger(__name__)


async def encrypt_subscription_url(
    url: Optional[str],
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 10.0,
) -> Optional[str]:
    """Encrypt Marzban subscription link using Happ crypto API.

    Falls back to original URL if encryption fails.
    """
    if not url:
        return url

    payload = {"url": url}
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=timeout) as local_client:
                response = await local_client.post(HAPP_CRYPTO_ENDPOINT, json=payload)
        else:
            response = await client.post(
                HAPP_CRYPTO_ENDPOINT, json=payload, timeout=timeout
            )

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            if isinstance(data, dict):
                for key in (
                    "encrypted_link",
                    "url",
                    "encrypted",
                    "link",
                    "data",
                    "result",
                ):
                    value = data.get(key)
                    if isinstance(value, str) and value:
                        return value
            elif isinstance(data, str) and data:
                return data

        text = response.text.strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("Failed to encrypt subscription url via Happ API: %s", exc)

    return url

