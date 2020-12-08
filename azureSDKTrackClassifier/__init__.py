from ._version import VERSION
__version__ = VERSION

from .classifier import AzureSDKTrackClassifier, Language

__all__ = [
    'AzureSDKTrackClassifier',
    'Language'
]