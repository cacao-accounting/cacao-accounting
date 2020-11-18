FROM node:current AS js
COPY package.json .
COPY yarn.lock .
RUN yarn

FROM python:slim
COPY . /app
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 
RUN pip --no-cache-dir install -r requirements.txt \
    && python setup.py develop \
    && rm -rf /root/.cache/
COPY --from=js node_modules /app/cacao_accounting/static/node_modules
ENV DOCKERISED=Yes
EXPOSE 8080

ENTRYPOINT [ "/bin/sh" ]
CMD [ "/app/entrypoint.sh" ]
