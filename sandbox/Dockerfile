# Minimal prebuilt Python runtime for the SD-21 sandbox. -H
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONNOUSERSITE=1

# Preinstall pytest for future test formats; no pip installs during execution. -H
RUN python -m pip install --no-cache-dir pytest==8.4.2 \
    && mkdir -p /job /opt/runner \
    && chmod 755 /job /opt/runner

COPY grade.py /opt/runner/grade.py

USER 65532:65532
WORKDIR /job

CMD ["python", "-I", "/opt/runner/grade.py"]