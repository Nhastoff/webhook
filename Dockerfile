FROM python:3.12

WORKDIR /usr/src/app

RUN pip install poetry

COPY . .

RUN poetry config virtualenvs.create false --local && poetry install --no-dev

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
