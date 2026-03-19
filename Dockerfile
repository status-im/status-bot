FROM python:3.12-slim

WORKDIR /app
COPY . .
# In case if the scripts are ran locally instead of with Docker
RUN rm -rf uploads

RUN pip install --no-cache-dir -r requirements.txt \
    && if [ -f bot/requirements.txt ]; then pip install --no-cache-dir -r bot/requirements.txt; fi

ENTRYPOINT ["python", "monitor.py"]
CMD []
