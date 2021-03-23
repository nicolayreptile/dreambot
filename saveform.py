import logging
import json

from app.data.docs import Doc


logging.basicConfig(level=logging.DEBUG)


def main():
    doc = Doc()
    service = doc.get_service('script', 'v1')
    body = {
        "function": "main",
        "devMode": True,
        "parameters": doc.FORM_URL
    }
    response = service.scripts().run(scriptId=doc.SCRIPT_ID, body=body).execute()
    form = response['response']['result']
    form = json.dumps(form, indent=4, sort_keys=True, ensure_ascii=False).encode('utf-8').decode()
    with open('questions.json', 'w') as f:
        f.write(form)


if __name__ == '__main__':
    main()
