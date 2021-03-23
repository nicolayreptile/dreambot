import os
import pickle
import logging
import dotenv
import json
from typing import List

from aiofile import async_open

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


dotenv.load_dotenv()


class Doc:

    SPREADSHEET_ID: str
    FORM_URL: str
    SCRIPT_ID: str
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/forms',
              'https://www.googleapis.com/auth/script.projects']
    FILENAME = 'questions_new.json'

    def __init__(self):
        self.SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        self.FORM_URL = os.environ.get('FORM_URL')
        self.SCRIPT_ID = os.environ.get('SCRIPT_ID')

    def write(self, values: List[str]):
        service = self.get_service('sheets', 'v4')
        body = {'values': [values]}
        range_name = 'A2:Z2'
        result = service.spreadsheets().values().append(spreadsheetId=self.SPREADSHEET_ID,
                                                        range=range_name,
                                                        valueInputOption='RAW',
                                                        body=body).execute()
        return result

    async def form(self, redis):
        form = await redis.get_form()
        if form:
            return form
        service = self.get_service('script', 'v1')
        body = {
            "function": "main",
            "devMode": True,
            "parameters": self.FORM_URL
        }
        response = service.scripts().run(scriptId=self.SCRIPT_ID, body=body).execute()
        if not response['done']:
            logging.fatal(msg='Не удалось загрузить вопросы')
            return None
        form = response['response']['result']
        await redis.set_from(form)
        return form

    async def get_data(self):
        async with async_open(self.FILENAME, 'r') as f:
            data = await f.read()
        data = json.loads(data)
        return data


    def get_service(self, service_name: str, version: str):
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        service = build(service_name, version, credentials=creds, cache_discovery=False)
        return service