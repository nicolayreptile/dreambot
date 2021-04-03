import json
import logging
import os
import pickle
import re
import string
from datetime import datetime, timedelta
from typing import List

import dotenv
import httpx
from aiofile import async_open
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.redis import Redis

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


class Token:
    def __init__(self, access_token: str, expires_in: int, **kwargs):
        self.access_token = access_token
        self.expired_at = datetime.utcnow() + timedelta(seconds=expires_in)

    def serialize(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def deserialize(token: bytes):
        return pickle.loads(token)

    @property
    def valid(self):
        return self.expired_at > datetime.utcnow()


class GoogleApi:
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/forms',
        'https://www.googleapis.com/auth/script.projects'
    ]
    CREDENTIALS_FILE = 'credentials.json'
    SPREADSHEET_URL = 'https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}'
    AUTH_URI = 'https://accounts.google.com/o/oauth2/auth'
    TOKEN_URI = 'https://oauth2.googleapis.com/token'

    START_RANGE = 'A2:Z2'
    OFFSET = 2

    def __init__(self, redis: Redis):
        self.spreadsheet_url = GoogleApi.SPREADSHEET_URL.format(spreadsheet_id=os.environ.get('SPREADSHEET_ID'))
        self.scopes = ' '.join(GoogleApi.SCOPES)
        self.credentials_file = self.CREDENTIALS_FILE
        self.redis = redis
        self.code = os.environ.get('CODE')
        self.refresh_token = os.environ.get('REFRESH_TOKEN')
        self.client_id = os.environ.get('CLIENT_ID')
        self.client_secret = os.environ.get('CLIENT_SECRET')

    async def initialize(self, user: int):
        headers = await self.headers()
        url = '{base}/values/{range}:append'.format(base=self.spreadsheet_url, range=GoogleApi.START_RANGE)
        body = self.body(user, datetime.today().strftime('%Y.%m.%d %H:%M:%S'))
        params = {'valueInputOption': 'RAW'}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=body, params=params, headers=headers)
        content = json.loads(response.content)
        updated_range = content['updates']['updatedRange']
        row = re.search(r'\d+$', updated_range).group(0)
        await self.redis.set_row_for_user(user, int(row))

    @staticmethod
    def body(*args) -> dict:
        return {'values': [[arg for arg in args]]}

    async def headers(self) -> dict:
        token = await self.__token()
        headers = {'Authorization': f'Bearer {token}'}
        return headers

    async def __token(self) -> str:
        token = await self.redis.get_token()
        if token:
            token = Token.deserialize(token)
            if token.valid:
                return token.access_token
        token = await self._oauth2()
        return token.access_token

    async def write_cell(self, user: int, index: int, data: List[str]) -> httpx.Response:
        row = await self.redis.get_row_for_user(user)
        column = string.ascii_uppercase[index + self.OFFSET]
        range_ = f'{column}{row}'
        stringify_data = ', '.join(data)
        headers = await self.headers()
        data = self.body(stringify_data)
        params = {'valueInputOption': 'RAW'}
        url = '{base}/values/{range}/'.format(base=self.spreadsheet_url, range=range_)
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=data, params=params, headers=headers)
        return response

    async def _oauth2(self) -> Token:
        refresh_token = self.refresh_token
        if refresh_token:
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(GoogleApi.TOKEN_URI, data=data)
            data = json.loads(response.content)
            token = Token(**data)
            await self.redis.set_token(token.serialize())
            return token
        else:
            # TODO
            code = await self._oauth2_grants_access()

    async def _oauth2_grants_access(self):
        raise NotImplementedError
