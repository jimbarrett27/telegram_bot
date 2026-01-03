from google.cloud import secretmanager
from functools import lru_cache
from dataclasses import dataclass

@dataclass
class GCPSecret:
    """
    Simple dataclass to manage the details of a GCP secret
    """

    project_id: str
    secret_id: str
    version: str

    def get_name(self, client: secretmanager.SecretManagerServiceClient):
        """
        Return the name necessary for fetching the secret content
        """
        return client.secret_version_path(self.project_id, self.secret_id, self.version)


def get_gcp_secret(gcp_secret: GCPSecret) -> str:
    """
    Fetches and decodes the content of a GCP secret
    """

    client = secretmanager.SecretManagerServiceClient()

    # Get the secret.
    response = client.access_secret_version(
        request={"name": gcp_secret.get_name(client)}
    )

    return response.payload.data.decode("UTF-8")


@lru_cache(maxsize=1)
def get_telegram_bot_key() -> str:
    """
    Fetches the token for the main telegram bot
    """

    secret = GCPSecret(
        project_id="personal-website-318015", secret_id="JIMMY_MAIN", version=2
    )

    return get_gcp_secret(secret)


@lru_cache(maxsize=1)
def get_telegram_user_id() -> int:
    """
    Fetches the token for the main telegram bot
    """

    secret = GCPSecret(
        project_id="personal-website-318015", secret_id="TELEGRAM_USER_ID", version=1
    )

    return int(get_gcp_secret(secret))

@lru_cache(maxsize=1)
def get_telegram_secret_token() -> str:
    """
    Fetches the token for the main telegram bot
    """

    secret = GCPSecret(
        project_id="personal-website-318015", secret_id="TELEGRAM_BOT_RESPONSE_TOKEN", version=1
    )

    return get_gcp_secret(secret)


@lru_cache(maxsize=1)
def get_mistral_api_key() -> str:
    """
    Fetches the token for the mistral api
    """

    secret = GCPSecret(
        project_id="personal-website-318015", secret_id="MISTRAL_API_KEY", version=1
    )

    return get_gcp_secret(secret)
