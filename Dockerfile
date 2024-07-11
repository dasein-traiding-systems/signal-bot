FROM daseinji/python-pandas-numpy-scipy:1.0.1

LABEL Name="Dasein Signal Bot" Version=1.0.1
#LABEL org.opencontainers.image.source = "https://github.com/..."

#ARG srcDir=src
WORKDIR /app
COPY ./ .
COPY ./.env .env
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir logs
#ENV PYTHONPATH=${PYTHONPATH}:./tc/src
#COPY .env .env
ENTRYPOINT ["python","signal-bot.py"]