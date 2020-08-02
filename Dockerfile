FROM python:alpine
ENV LANG C.UTF-8

# Cache layer with dependencies
COPY requirements.txt /
RUN apk add --virtual --update --no-cache musl-dev gcc libffi-dev \
    && pip --no-cache-dir install -r requirements.txt \
    && rm -rf /root/.cache/ \
    && apk del --no-network musl-dev gcc libffi-dev 

# App layer
ADD . /app
WORKDIR /app
RUN apk add --virtual --update --no-cache yarn \
    && python setup.py install \
    # We need yarn to include third party javascritp
    && yarn && yarn cache clean --all \
    # Make the final image smaller
    && apk del --no-network yarn

ENTRYPOINT [ "python", "/app/wsgi.py"]