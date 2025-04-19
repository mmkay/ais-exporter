FROM python:3.12-alpine

# Preventing Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE 1
# Preventing Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED 1

# create the app user
RUN addgroup -S aisexp && adduser -S aisexp -G aisexp

COPY ./dist/aisexporter-*-py3-none-any.whl /tmp/

# install aisexporter (including dependencies and requirements)
RUN \
  apk update && \
  apk add --no-cache --virtual .build-deps musl-dev gcc && \
  pip install pip -U --no-cache-dir && \
  pip install /tmp/aisexporter-*-py3-none-any.whl --no-cache-dir && \
  apk --purge del .build-deps && \
  rm -rf /tmp/aisexporter-*-py3-none-any.whl

# switch to non-root user
USER aisexp

WORKDIR /tmp

EXPOSE 9205

ENTRYPOINT ["python", "-m", "aisexporter"]
CMD ["--help"]
