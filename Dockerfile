FROM mwader/static-ffmpeg:6.1.1 AS ffmpeg

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_RETRIES=10 \
    PIP_TIMEOUT=60

WORKDIR /app

COPY --from=ffmpeg /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /ffprobe /usr/local/bin/ffprobe

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

ENTRYPOINT ["echolens"]
CMD ["scan"]
