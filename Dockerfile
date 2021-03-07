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
RUN pip --no-cache-dir install -r /tmp/requirements.txt \
    && rm -rf /root/.cache/

# Copy and install app
COPY . /app
WORKDIR /app

RUN python setup.py develop
RUN cacaoctl --version && cacaoctl version

# Install nodejs modules in the final docker image    
COPY --from=js node_modules /app/cacao_accounting/static/node_modules

# No ejecutar como root
RUN useradd cacao
USER cacao

EXPOSE 8080
ENTRYPOINT [ "/bin/sh" ]
CMD [ "/app/entrypoint.sh" ]
