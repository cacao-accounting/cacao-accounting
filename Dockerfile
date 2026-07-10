FROM registry.access.redhat.com/ubi9/ubi-minimal:9.8-1782797275 AS frontend

RUN microdnf install -y --nodocs --best nodejs npm \
    && microdnf clean all

WORKDIR /build
COPY cacao_accounting/static/package.json cacao_accounting/static/package-lock.json ./
RUN npm install --omit=dev --ignore-scripts

FROM registry.access.redhat.com/ubi9/ubi-minimal:9.8-1782797275 AS python-builder

RUN microdnf install -y --nodocs --best --refresh \
       python3.12 python3.12-pip \
    && microdnf clean all

WORKDIR /build
COPY requirements.txt .
RUN /usr/bin/python3.12 -m pip --no-cache-dir install --prefix=/install -r requirements.txt

FROM registry.access.redhat.com/ubi9/ubi-minimal:9.8-1782797275

RUN microdnf update -y --nodocs --best --refresh \
    && microdnf clean all

ENV TINI_VERSION=v0.19.0
ENV TINI_SUBREAPER=1
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/bin/tini
RUN chmod +x /usr/bin/tini

RUN microdnf install -y --nodocs --best --refresh \
       python3.12 python3.12-cryptography \
       pango libxml2 libxslt \
    && microdnf clean all

COPY --from=python-builder /install/lib/python3.12/site-packages /usr/lib/python3.12/site-packages
COPY --from=python-builder /install/bin /usr/local/bin

RUN useradd -r -s /bin/false appuser

WORKDIR /app

COPY ./cacao_accounting /app/cacao_accounting
COPY --from=frontend /build/node_modules /app/cacao_accounting/static/node_modules
COPY docker-entry-point.sh /app/docker-entry-point.sh
RUN chmod +x /app/docker-entry-point.sh

USER appuser

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV FLASK_APP="cacao_accounting"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHON_CPU_COUNT=4
ENV OCI_CONTAINER=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD /usr/bin/python3.12 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/docker-entry-point.sh"]
CMD ["/bin/sh"]
