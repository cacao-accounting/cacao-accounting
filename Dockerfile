FROM node:current AS js
COPY package.json .
COPY yarn.lock .
RUN yarn

FROM python:slim

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED = 1
ENV DOCKERISED=True
ENV CACAO_ACCOUNTING=True

# Install dependencies in a layer
COPY requirements.txt /tmp/
RUN /usr/local/bin/python3 -m pip --no-cache-dir install -r /tmp/requirements.txt \
    && /usr/local/bin/python3 -m pip --no-cache-dir install pymysql waitress \
    && rm -rf /root/.cache/

# Copy and install app
COPY . /app
WORKDIR /app
RUN cp docker-entry-point.sh /usr/local/bin/docker-entry-point && chmod +x /usr/local/bin/docker-entry-point

# Install nodejs modules in the final docker image    
COPY --from=js node_modules /app/cacao_accounting/static/node_modules

RUN /usr/local/bin/python3 setup.py develop

# No ejecutar como root
RUN useradd cacao
USER cacao

EXPOSE 8080
ENTRYPOINT [ "/bin/sh" ]
CMD [ "docker-entry-point" ]
