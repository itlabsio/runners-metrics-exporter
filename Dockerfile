FROM python:3.6-slim

WORKDIR /app

COPY ./requirements.txt requirements.txt
COPY ./README.md README.md
COPY ./LICENSE LICENSE

RUN pip3 install -r requirements.txt \
    && chown -R nobody /app

COPY ./main.py main.py

USER nobody

EXPOSE 8000

CMD [ "python3", "/app/main.py"]
