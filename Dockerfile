FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg
WORKDIR /app
COPY requirements.txt .
RUN pip install --root-user-action=ignore -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:80", "--timeout", "60", "guitar_tab_transcriber:app"]
