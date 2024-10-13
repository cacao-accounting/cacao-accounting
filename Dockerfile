# https://quay.io/repository/cacaoaccounting/cacaoaccounting
FROM registry.access.redhat.com/ubi9/ubi-minimal:9.4 AS js
RUN microdnf install -y nodejs npm
WORKDIR /usr/app
COPY ./cacao_accounting/static/package.json /usr/app/package.json
RUN npm install --ignore-scripts

FROM registry.access.redhat.com/ubi9/ubi-minimal:9.4
COPY . /app
COPY --from=js /usr/app/node_modules /app/cacao_accounting/static/node_modules
COPY requirements.txt /tmp/

WORKDIR /app

RUN microdnf update -y --nodocs --best \
    # Python 3.12 and binary libraries.
    # https://www.python.org/downloads/release/python-3120/
    && microdnf install -y --nodocs --best --refresh python3.12 python3.12-cryptography python3.12-pip python3.12-psycopg2 \
    && microdnf clean all \
    && /usr/bin/python3.12 --version \
    && chmod +x docker-entry-point.sh \
    && /usr/bin/python3.12 -m pip --no-cache-dir install -r /tmp/requirements.txt \
    # Support for MariaDB is considered experimental.
    # && /usr/bin/python3.12 -m pip --no-cache-dir install mariadb \
    && rm -rf /root/.cache/pip && rm -rf /tmp && microdnf remove -y --best python3.12-pip

ENV FLASK_APP="cacao_accounting"
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHON_CPU_COUNT=4
ENV OCI_CONTAINER=1

EXPOSE 8080

ENTRYPOINT [ "/bin/sh" ]

CMD [ "/app/docker-entry-point.sh" ]
