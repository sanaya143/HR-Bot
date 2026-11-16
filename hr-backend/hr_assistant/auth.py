"""Identity always comes from a verified token (or the dev header), never from chat text.
The React app signs in with Google and sends the ID token as a Bearer token."""


class AuthError(Exception):
    pass


def resolve_email(settings, authorization: str | None, x_dev_user: str | None) -> str:
    if settings.auth_mode == "dev":
        if not x_dev_user:
            raise AuthError("Dev mode: send the X-Dev-User header")
        return x_dev_user.lower()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(token, g_requests.Request(), getattr(settings, "google_client_id", ""))
    except Exception as e:      # noqa: BLE001
        raise AuthError("Invalid or expired token") from e
    if not claims.get("email_verified"):
        raise AuthError("Email not verified")
    return claims["email"].lower()
