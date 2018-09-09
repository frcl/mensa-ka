FROM python:3.7
ADD . /code
WORKDIR /code
RUN pip install pipenv
RUN pipenv sync

EXPOSE 80
CMD ["pipenv", "run", "python", "mensa.py", "-p", "80"]
