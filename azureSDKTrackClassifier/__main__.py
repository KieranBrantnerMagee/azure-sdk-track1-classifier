import argparse
import logging
import os
import sys

from .classifier import AzureSDKTrackClassifier

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Predict whether a given document contains Track1 content', prog='azureSDKTrackClassifier')
    parser.add_argument('text', type=str, help='The text to classify as containing T1 content')
    parser.add_argument('--language', default=None, type=str, help='Specify the language to tailor this classification for.  If unspecified, checks for all languages.')
    parser.add_argument('--service', default=None, type=str, help='Specify the service to tailor this classification for.  If unspecified, checks for all services.')

    parser.add_argument('--verbose', default=False, action='store_true', help='Enable this flag to produce verbose classification results, including text features as well as prediction.')
    parser.add_argument('--log-level', default=None, type=str, help='Specify log level (debug, info, warning, exception, error) to output alongside results')

    parser.add_argument('--load-from-file', type=str, help='Load a cached model from a local file rather than training from scratch.  Specify the path with this argument.')
    parser.add_argument('--save-to-file', type=str, help='Save the model trained or used in this run to a file so it may be loaded again in the future.  Specify the path with this argument.')
    
    parser.add_argument('--load-from-blob', type=str, help='Load a cached model from an azure storage blob rather than training from scratch.  Specify the blob path with this argument.  Azure credentials must be provided by environment variables AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER respectively.')
    parser.add_argument('--save-to-blob', type=str, help='Save the model trained or used in this run to an azure storage blob so it may be loaded again in the future.  Specify the blob path with this argument.  Azure credentials must be provided by environment variables AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER respectively.')

    args = parser.parse_args()

    if args.log_level:
        logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    if args.load_from_file:
        is_t1_classifier = AzureSDKTrackClassifier.load(args.load_from_file)
    elif args.load_from_blob:
        CONN_STR = os.environ['AZURE_STORAGE_CONNECTION_STRING']
        CONTAINER = os.environ['AZURE_STORAGE_CONTAINER']
        is_t1_classifier = AzureSDKTrackClassifier.load_from_blob(CONN_STR, CONTAINER, args.load_from_blob)
    else:
        is_t1_classifier = AzureSDKTrackClassifier(args.language, args.service)

    if args.verbose:
        result = is_t1_classifier.is_t1_verbose(args.text)
    else:
        result = is_t1_classifier.is_t1(args.text)

    print(result)

    if args.save_to_file:
        is_t1_classifier.save(args.save_to_file)
    elif args.save_to_blob:
        CONN_STR = os.environ['AZURE_STORAGE_CONNECTION_STRING']
        CONTAINER = os.environ['AZURE_STORAGE_CONTAINER']
        is_t1_classifier.save_to_blob(CONN_STR, CONTAINER, args.save_to_blob)
