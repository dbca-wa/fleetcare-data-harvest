# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/azure-functions/python:4-python3.11
LABEL org.opencontainers.image.authors=asi@dbca.wa.gov.au
LABEL org.opencontainers.image.source=https://github.com/dbca-wa/fleetcare-data-harvest

ENV AzureWebJobsScriptRoot=/app \
  AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /app
ARG POETRY_VERSION=1.8.3
RUN pip install --no-cache-dir --root-user-action=ignore poetry==${POETRY_VERSION}
COPY poetry.lock pyproject.toml ./
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --only main
COPY function_app.py host.json  ./

# Create a non-root user to run the FleetcareTrackingData function app.
# We need to change ownership on a system directory and set the port
# used to a different one.
# https://github.com/Azure/azure-functions-docker/issues/424#issuecomment-1150324853
ARG UID=10001
ARG GID=10001
RUN groupadd -g ${GID} appuser \
  && useradd --no-create-home --no-log-init --uid ${UID} --gid ${GID} appuser
RUN chown -R appuser:appuser /azure-functions-host
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

USER appuser
