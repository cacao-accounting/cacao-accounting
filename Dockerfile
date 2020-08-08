FROM node:current AS js
COPY package.json .
COPY yarn.lock .
RUN yarn && ls node_modules

FROM python:slim
COPY . /app
COPY --from=js node_modules/* /app/cacao_accounting/static/js/
RUN ls /app/cacao_accounting/static/js/
WORKDIR /app
RUN pip --no-cache-dir install -r requirements.txt \
    && python setup.py develop \
    && rm -rf /root/.cache/ 

CMD [ "python", "/app/wsgi.py"]
