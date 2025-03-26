FROM registry.access.redhat.com/ubi9/ubi-minimal:9.4

RUN microdnf update -y --nodocs --best --refresh \
    && microdnf clean all

ENV TINI_VERSION v0.19.0
ENV TINI_SUBREAPER=1
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/bin/tini
RUN chmod +x /usr/bin/tini

WORKDIR /app

COPY ./cacao_accounting/static/package.json /app/cacao_accounting/static/package.json
RUN microdnf install -y --nodocs --best nodejs npm && cd /app/cacao_accounting/static && npm install --ignore-scripts && cd /app \
    && rm -rf /root/.cache/pip && rm -rf /tmp && microdnf remove -y --best nodejs* npm \
    && microdnf clean all

COPY requirements.txt /app/requirements.txt
RUN microdnf install -y --nodocs --best --refresh python3.12 python3.12-cryptography python3.12-pip python3.12-psycopg2 \
    && /usr/bin/python3.12 --version \
    && /usr/bin/python3.12 -m pip --no-cache-dir install -r /app/requirements.txt \
    && rm -rf /root/.cache/pip && rm -rf /tmp && microdnf remove -y --best python3.12-pip \
    && microdnf clean all

COPY . /app

WORKDIR /app

RUN chmod +x docker-entry-point.sh

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV FLASK_APP="cacao_accounting"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHON_CPU_COUNT=4
ENV OCI_CONTAINER=1

EXPOSE 8080
ENTRYPOINT [ "/usr/bin/tini", "--", "/app/docker-entry-point.sh" ]
CMD ["/bin/sh"]
