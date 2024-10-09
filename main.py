import tempfile as tmp
import zipfile
import shutil
from pathlib import Path
from util.constants import REPO_ROOT
from telegram_bot.handle_request import bot_entrypoint
from gcp_util.secrets import get_telegram_secret_token, get_telegram_bot_key
import subprocess
import requests


import logging

LOGGER = logging.getLogger(__name__)

GCP_FUNCTION_ZIPFILE_NAME = "telegram_bot.zip"

try:
    import functions_framework  # type: ignore
    @functions_framework.http
    def main(request):
        """HTTP Cloud Function.
        Args:
            request (flask.Request): The request object.
            <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
        """
        
        if request.method != 'POST':
            LOGGER.error("Unauthorized request type")
            return '' 

        request_json = request.get_json()

        try:

            if request_json['X-Telegram-Bot-Api-Secret-Token'] != get_telegram_secret_token():
                LOGGER.error("Unauthorized request")
                return ''
        except KeyError as e:
            raise KeyError(f"{e}: {request_json}")
        bot_entrypoint(request_json)        

        return 'Hello!'
except (NameError, ImportError):
    print("Couldn't use the http function. Presumably running locally")

def create_gcp_function_zipfile():
    """
    Function to upload all of the cloud functions to blob storage, so that we can
    deploy the cloud function
    """
    tmpdir = Path(tmp.mkdtemp())

    zipfile_path = tmpdir / GCP_FUNCTION_ZIPFILE_NAME

    zipped = zipfile.ZipFile(  # pylint: disable=consider-using-with
        zipfile_path, "w", zipfile.ZIP_DEFLATED
    )

    # upload the relevant code directories
    for directory in ["telegram_bot", "gcp_util", "util"]:
        for f in (REPO_ROOT / directory).iterdir():
            if not str(f).endswith(".py"):
                continue
            zipped.write(str(f), f"{directory}/{f.name}")

    zipped.write(REPO_ROOT / "requirements.txt", "requirements.txt")
    zipped.write(REPO_ROOT / "main.py", "main.py")
    zipped.close()

    shutil.copy(zipfile_path, f'./build/{GCP_FUNCTION_ZIPFILE_NAME}')
    shutil.rmtree(tmpdir)

def deploy_cloud_function(function_name, runtime, entry_point, source_dir, region, project):
    # Build the gcloud command
    command = [
        "gcloud", "functions", "deploy", function_name,
        "--runtime", runtime,
        "--trigger-http",  # Assuming it's an HTTP-triggered function, modify as needed
        "--entry-point", entry_point,
        "--source", source_dir,
        "--region", region,
        "--project", project,
        "--gen2",
        "--allow-unauthenticated"
    ]
    
    # Run the gcloud command
    result = subprocess.run(command, capture_output=True, text=True)
    
    # Print the command output (or handle as needed)
    if result.returncode == 0:
        print("Function deployed successfully!")
    else:
        print(f"Failed to deploy function: {result.stderr}")

# Example usage
if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    LOGGER.info("Creating the GCP function zipfile")
    create_gcp_function_zipfile()
    LOGGER.info("Deploying the GCP function")
    deploy_cloud_function(
        function_name="telegram_bot",
        runtime="python312",  # Specify your Python version
        entry_point="main",  # The main function in your code
        source_dir=".",
        region="europe-west1",
        project="personal-website-318015",
    )
    LOGGER.info("Deleting the webhook")
    delete_webhook_url = f"https://api.telegram.org/bot{get_telegram_bot_key()}/setWebhook?url="
    resp = requests.get(delete_webhook_url)
    LOGGER.info(f"Response from deleting the webhook: {resp.text}")
    set_webhook_url = f"https://api.telegram.org/bot{get_telegram_bot_key()}/setWebhook?url=https://europe-west1-personal-website-318015.cloudfunctions.net/telegram_bot&secret_token={get_telegram_secret_token()}"
    resp = requests.get(set_webhook_url)
    LOGGER.info(f"Response from setting the webhook: {resp.text}")