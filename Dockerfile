FROM python:3.7-alpine
ADD . /code
WORKDIR /code
RUN pip install pipenv

EXPOSE 80
CMD ["pipenv", "run", "python", "mensa.py", "-p", "80"]
