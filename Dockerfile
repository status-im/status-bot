FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Folder is required only for status-backend and not the code
RUN rm -rf data-dir
# In case if the scripts are ran locally instead of with Docker
RUN rm -rf uploads
# Independent scripts
CMD ["sh", "-c", "python upload.py & python download.py"]
