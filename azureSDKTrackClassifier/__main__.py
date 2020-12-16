import argparse
import glob
from io import BytesIO
import logging
import os
import sys
import zipfile

import numpy
import requests

from .classifier import AzureSDKTrackClassifier, Language
from .helpers import get_zip_uri_and_subpath_from_github_link, do_github_zip_request

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Predict whether a given document contains Track1 content.\n\n(Note: If an existing model is not loaded, a new model will be trained.)', prog='azureSDKTrackClassifier')
    parser.add_argument('text', type=str, help='The text to classify as containing T1 content')
    parser.add_argument('--language', default=None, type=str, help='Specify the language ({}) to tailor this classification for.  If unspecified, checks for all languages.'.format(', '.join([l.name for l in Language])))
    parser.add_argument('--service', default=None, type=str, help='Specify the service (any by name from Azure SDK release list, e.g. EventHubs) to tailor this classification for.  If unspecified, checks for all services.')
    
    parser.add_argument('--verbose', default=False, action='store_true', help='Enable this flag to produce verbose classification results, including text features as well as prediction.')
    parser.add_argument('--log-level', default=None, type=str, help='Specify log level (debug, info, warning, exception, error) to output alongside results.')

    parser.add_argument('--load-from-file', type=str, help='Load a cached model from a local file rather than training from scratch.  Specify the path with this argument.')
    parser.add_argument('--save-to-file', type=str, help='Save the model trained or used in this run to a file so it may be loaded again in the future.  Specify the path with this argument.')
    
    parser.add_argument('--load-from-blob', type=str, help='Load a cached model from an azure storage blob rather than training from scratch.  Specify the blob path with this argument.  Azure credentials must be provided by environment variables AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER respectively.')
    parser.add_argument('--save-to-blob', type=str, help='Save the model trained or used in this run to an azure storage blob so it may be loaded again in the future.  Specify the blob path with this argument.  Azure credentials must be provided by environment variables AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER respectively.')

    parser.add_argument('--input-is-path', default=False, action='store_true', help='Enable this flag to indicate that the primary text argument is a path to a file that should be read and predicted.')

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

    text = args.text
    multi_text = {}
    if args.input_is_path:
        path = args.text
        if os.path.isfile(path):
            with open(path) as f:
                text = f.read()
        elif os.path.isdir(path):
            input_path_glob = os.path.join(path,'*')
            for file_path in glob.glob(input_path_glob, recursive=True):
                with open(file_path) as f:
                    text = f.read()
                    multi_text[file_path] = text
        elif "github" in path:
            if path.endswith('.zip'):
                zip_uri, custom_subpath = path, ''
            else:
                zip_uri, custom_subpath = get_zip_uri_and_subpath_from_github_link(path)
            logging.getLogger(__name__).info("Getting input uri: " + zip_uri)
            input_zip = do_github_zip_request(zip_uri)
            if input_zip == b'404: Not Found': # This is a github-ism.
                logging.getLogger(__name__).warning("No zip for URI: {}".format(zip_uri))
                exit()
            with zipfile.ZipFile(BytesIO(input_zip), 'r') as zf:
                for file in [n for n in zf.namelist() if not n.endswith('/') and (custom_subpath in n)]:
                    body = zf.read(file)
                    try:
                        multi_text[file] = body.decode('UTF-8')
                    except:
                        try:
                            multi_text[file] = body.decode('unicode_escape')
                        except Exception as e:
                            logging.getLogger(__name__).warning("Unable to read input file: {}; {}".format(file, e))
        else:
            print("Provided input path is of no known type (local file, directory, or github repo or zip): {}".format(path))
            exit()

    with numpy.errstate(divide='ignore'): # Disable the divide by zero warning that can sometimes be emitted by the model during prediction.
        if multi_text:
            for path, text in multi_text.items():
                if args.verbose:
                    result = is_t1_classifier.is_t1_verbose(text)
                else:
                    result = is_t1_classifier.is_t1(text)
                print("{}: {}".format(path, result))
        else:
            if args.verbose:
                result = is_t1_classifier.is_t1_verbose(text)
            else:
                result = is_t1_classifier.is_t1(text)
            print(result)

    if args.save_to_file:
        is_t1_classifier.save(args.save_to_file)
    elif args.save_to_blob:
        CONN_STR = os.environ['AZURE_STORAGE_CONNECTION_STRING']
        CONTAINER = os.environ['AZURE_STORAGE_CONTAINER']
        is_t1_classifier.save_to_blob(CONN_STR, CONTAINER, args.save_to_blob)
