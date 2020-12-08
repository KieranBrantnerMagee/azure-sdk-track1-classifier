import os

from azureSDKTrackClassifier import AzureSDKTrackClassifier, Language

is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "EventHubs")

# One can save into a file
path = is_t1_classifier.save()
is_t1_classifier = AzureSDKTrackClassifier.load(path)

# Or into a storage blob
CONN_STR = os.environ['AZURE_STORAGE_CONNECTION_STRING']
CONTAINER = os.environ['AZURE_STORAGE_CONTAINER']

path = is_t1_classifier.save_to_blob(CONN_STR, CONTAINER)
is_t1_classifier = AzureSDKTrackClassifier.load_from_blob(CONN_STR, CONTAINER, path)

is_t1_classifier.is_t1("test")