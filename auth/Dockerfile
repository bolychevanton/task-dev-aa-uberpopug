FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PROJECT_DIR=auth
ENV TERM xterm-256color

RUN apt-get install libpq-dev -y
RUN mkdir /$PROJECT_DIR
WORKDIR /$PROJECT_DIR
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN pip install -e /$PROJECT_DIR/

# Use an official Python runtime as a parent image
ENTRYPOINT ["python", "-u", "conflower/cli/__main__.py"]
CMD ["--help"]