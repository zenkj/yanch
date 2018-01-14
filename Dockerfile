FROM python:3.6

WORKDIR /yanch

COPY . /yanch

RUN pip install -r requirements.txt

CMD cd /yanch && python yanch.py
