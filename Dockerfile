FROM node:current AS js
COPY package.json .
COPY yarn.lock .
RUN yarn

FROM python:slim
COPY . /app
WORKDIR /app
RUN pip --no-cache-dir install -r requirements.txt \
    && python setup.py develop \
    && rm -rf /root/.cache/ && cacaoctl
COPY --from=js node_modules /app/cacao_accounting/static/node_modules
ENV DOCKERISED=Yes

ENTRYPOINT [ "/bin/sh" ]
CMD [ "/app/entrypoint.sh" ]
