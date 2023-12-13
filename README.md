# Azure Function: Fleetcare tracking data harvest

This is a basic Azure Function to harvest Fleetcare tracking data into a
database, triggered by a BlobTrigger event.

# Documentation references

Azure Functions developer guide:
https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference?tabs=blob

Azure Functions Python developer guide:
https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python?tabs=asgi%2Capplication-level&pivots=python-mode-decorators

Develop Azure Functions locally using Core Tools:
https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=linux%2Cisolated-process%2Cnode-v4%2Cpython-v2%2Chttp-trigger%2Ccontainer-apps&pivots=programming-language-python

Azure Functions Core Tools reference:
https://learn.microsoft.com/en-us/azure/azure-functions/functions-core-tools-reference?tabs=v2

Create a Python Python from the command line:
https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-cli-python?tabs=linux%2Cbash%2Cazure-cli&pivots=python-mode-configuration

Azure blob storage trigger for Azure Functions:
https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-storage-blob-trigger?tabs=python-v2%2Cin-process&pivots=programming-language-python


# Local development

Install the Azure Functions Core Tools, as per the links above.

Create and activate a local Python virtualenv (currently tested in Python 3.10),
then install the packages in `requirements.txt`. Create a `local.settings.json`
file to configure function, containing the following values:

```json
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsFeatureFlags": "EnableWorkerIndexing",
    "AzureWebJobsStorage": "<CONNECTION STRING FROM STORAGE ACCOUNT>",
    "DATABASE_URL": "<DATABASE CONNECTION STRING>",
    "STORAGE_CONNECTION_STRING": "<CONNECTION STRING FROM STORAGE ACCOUNT>"
  }
}
```

Make changes and run the function locally using `func start`.

Publish the function to Azure using `func azure functionapp publish <APP_NAME>`:
https://learn.microsoft.com/en-us/azure/azure-functions/functions-core-tools-reference?tabs=v2#func-azure-functionapp-publish
