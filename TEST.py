import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv
load_dotenv()
# Cargar las rutas desde las variables de entorno
credenciales_path = os.environ.get('GMAIL_CREDENTIALS_JSON')
token_path = os.environ.get('GMAIL_TOKEN_JSON')
print(token_path, credenciales_path)
creds = None
import webbrowser
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

# Si el token ya existe, lo usa para saltar el login gráfico
if os.path.exists(token_path):
    creds = Credentials.from_authorized_user_file(token_path, ['https://googleapis.com'])

# Si no hay token o no es válido, pide iniciar sesión en el navegador
if not creds or not creds.valid:
    webbrowser.register(
        'windows-default',
        None,
        webbrowser.BackgroundBrowser('/mnt/c/Windows/explorer.exe')
    )
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            credenciales_path,
            SCOPES
        )

        creds = flow.run_local_server(
            port=0,
            browser='windows-default'
        )

    # Aquí se crea el archivo gmail_token.json automáticamente
    with open(token_path, 'w') as token:
        token.write(creds.to_json())