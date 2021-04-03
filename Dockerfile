FROM python:3.9
WORKDIR bot
COPY ./requirements.txt .
COPY ./questions_new.json .
COPY ./token.pickle .
COPY ./app ./app
COPY ./main.py .
RUN pip install -r ./requirements.txt
CMD python main.py