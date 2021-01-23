FROM node:current AS js
COPY package.json .
COPY yarn.lock .
RUN yarn

FROM python:3.8-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED = 1
ENV DOCKERISED=Yes

# Install dependencies in a layer
COPY requirements.txt /tmp/
RUN pip --no-cache-dir install -r /tmp/requirements.txt \
    && rm -rf /root/.cache/

# Copy and install app
COPY . /app
WORKDIR /app

RUN python setup.py develop 

# Install nodejs modules in the final docker image    
COPY --from=js node_modules /app/cacao_accounting/static/node_modules

EXPOSE 8080
ENTRYPOINT [ "/bin/sh" ]
CMD [ "/app/entrypoint.sh" ]
