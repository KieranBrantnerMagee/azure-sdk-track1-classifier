from enum import Enum
import pickle

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError

from .model import train_model
from .constants import Language


class AzureSDKTrackClassifier: # Someone with more sense than me can rename this to just Track1Classifier or something.
    """ Provides an API for classifying text as containing T1 azure sdk content. """

    def __init__(self, language : Language = None, service : str = None):
        """ Initialize the model, training with the specified constraints of language and service.  
            If None are provided, this acts as a wildcard and trains for all languages or all services respectively.
            
            Pretrained models may be saved and loaded to save training time."""
        self._language, self._service = language, service
        self._trained_model = train_model(language, service)

    def is_t1(self, text:str) -> bool:
        """ Classify given text as containing T1 content """
        return self._trained_model.classify(text)

    def is_t1_verbose(self, text:str, extra_verbosity:bool=False) -> dict:
        """ Classify given text as containing T1 content, returning a dictionary containing not only the result but supplementary metadata used for classification. 

            extra_verbosity outputs to logging the new and old tokens that were detected.
        """
        return self._trained_model.classify_verbose(text, extra_verbosity)

    def save(self, path:str = None) -> str:
        """ Saves the model to a file.
            The file will be located at the path parameter if provided, otherwise, in the local directory."""
        path = path or 'azureSDKTrackClassifier_{}_{}.model'.format(self._language, self._service)
        with open(path, 'wb') as f:
            pickle.dump(self, f)
            return path

    @staticmethod
    def load(path:str) -> "AzureSDKTrackClassifier":
        """ Loads the model from a file located at the specified path."""
        with open(path, 'rb') as f:
            return pickle.load(f)

    def save_to_blob(self, connection_string:str, container:str, path:str = None) -> str:
        """ Saves the model to an azure storage blob.
            The file will be located at the container and path parameter if provided, otherwise, in the root of the container."""
        path = path or 'azureSDKTrackClassifier_{}_{}.model'.format(self._language, self._service)
        if 'sig=' in connection_string and 'AccountKey=' not in connection_string: # SAS signature.
            service_client = BlobServiceClient(connection_string)
        else:
            service_client = BlobServiceClient.from_connection_string(conn_str=connection_string)
        try:
            service_client.create_container(container)
        except ResourceExistsError:
            pass
        blob_client = service_client.get_blob_client(container, path)
        blob_client.upload_blob(pickle.dumps(self), overwrite=True)
        return path

    @staticmethod
    def load_from_blob(connection_string:str, container:str, path:str) -> "AzureSDKTrackClassifier":
        """ Loads the model from an azure storage blob located at the specified path."""
        if 'sig=' in connection_string and 'AccountKey=' not in connection_string: # SAS signature.
            service_client = BlobServiceClient(connection_string)
        else:
            service_client = BlobServiceClient.from_connection_string(conn_str=connection_string)
        blob_client = service_client.get_blob_client(container, path)
        return pickle.loads(blob_client.download_blob().content_as_bytes())
