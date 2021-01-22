import argparse
import glob
from io import BytesIO
import logging
import math
from multiprocessing import Process, Queue
import os
import queue
import sys
import zipfile

import numpy
import requests

from .classifier import AzureSDKTrackClassifier, Language
from .helpers import get_zip_uri_and_subpath_from_github_link, do_github_zip_request, run_multiproc_classifier
from .settings import Settings
from .classifierV2 import extract_and_label_codefences


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Predict whether a given document contains Track1 content.\n\n(Note: If an existing model is not loaded, a new model will be trained.)', prog='azureSDKTrackClassifier')
    parser.add_argument('text', type=str, help='The text to classify as containing T1 content')
    parser.add_argument('--language', default=None, type=str, help='Specify the language ({}) to tailor this classification for.  If unspecified, checks for all languages.'.format(', '.join([l.name for l in Language])))
    parser.add_argument('--service', default=None, type=str, help='Specify the service (any by name from Azure SDK release list, e.g. EventHubs) to tailor this classification for.  If unspecified, checks for all services.')
    
    parser.add_argument('--verbose', default=False, action='store_true', help='Enable this flag to produce verbose classification results, including text features as well as prediction.')
    parser.add_argument('--log-level', default=None, type=str, help='Specify log level (debug, info, warning, exception, error) to output alongside results.')

    parser.add_argument('--load-from-file', type=str, help='Load a cached model from a local file rather than training from scratch.  Specify the path with this argument.')
    parser.add_argument('--save-to-file', type=str, help='Save the model trained or used in this run to a file so it may be loaded again in the future.  Specify the path with this argument.')
    
    parser.add_argument('--load-from-blob', type=str, help='Load a cached model from an azure storage blob rather than training from scratch.  Specify the blob path with this argument.  Azure credentials must be provided by environment variables AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER respectively. (connection string may also be a SAS signature connection string)')
    parser.add_argument('--save-to-blob', type=str, help='Save the model trained or used in this run to an azure storage blob so it may be loaded again in the future.  Specify the blob path with this argument.  Azure credentials must be provided by environment variables AZURE_STORAGE_CONNECTION_STRING and AZURE_STORAGE_CONTAINER respectively. (connection string may also be a SAS signature connection string)')

    parser.add_argument('--input-is-path', default=False, action='store_true', help='Enable this flag to indicate that the primary text argument is a path to a file that should be read and predicted.')

    parser.add_argument('--set-cache-path', type=str, default='.', help='This option specifies the location of the cache files pulled down to generate the model. (Training corpuses.)  By default this is the local directory.')
    parser.add_argument('--set-test-corpus-path', type=str, default='.', help='This option specifies the location of the test corpus tree used to supplement unsupervised model generation. (Test corpuses.)  By default this is the local directory.')
    parser.add_argument('--log-missing-training-to-file', type=str, default=None, help='This option logs all package-version-uri tuples found to be missing from unsupervised training to the specified file. (File is TSV-formatted with headers)')
    parser.add_argument('--set-parallelism', type=int, default=1, help='This option specifies the degree of parallelism (number of processes) to use when performing classification.  Default is no parallelism. (1 process, this script)  Warning: Not advised to use because of process start time overhead unless you have MANY (hundreds) files to parse.')
    parser.add_argument('--obey-code-fences', default=False, action='store_true', help='This option causes the classifier to try and examine only codefenced blocks.  If none exists, runs on the whole file.')

    args = parser.parse_args()

    # == Prepare settings ==
    if args.log_level:
        logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    if args.set_cache_path:
        Settings.CACHE_BASE_PATH = args.set_cache_path
    if args.set_test_corpus_path:
        Settings.TEST_CORPUS_BASE_PATH = args.set_test_corpus_path
    if args.log_missing_training_to_file:
        Settings.MISSING_TRAINING_LOG = args.log_missing_training_to_file
        with open(Settings.MISSING_TRAINING_LOG, 'w') as f: # Truncate log file for this run.
            f.write("package_zip_uri\trepo\tpackage\tversion") # Write headers for the file (CSV? might as well.)

    if args.load_from_file:
        is_t1_classifier = AzureSDKTrackClassifier.load(args.load_from_file)
    elif args.load_from_blob:
        CONN_STR = os.environ['AZURE_STORAGE_CONNECTION_STRING']
        CONTAINER = os.environ['AZURE_STORAGE_CONTAINER']
        is_t1_classifier = AzureSDKTrackClassifier.load_from_blob(CONN_STR, CONTAINER, args.load_from_blob)
    else:
        is_t1_classifier = AzureSDKTrackClassifier(args.language, args.service)

    # == Prepare or fetch inputs ==
    text = args.text
    multi_text = {} # For if we're provided an input with more than one file to classify. (A folder, github repo, etc.)
    if args.input_is_path:
        path = args.text
        if os.path.isfile(path):
            with open(path) as f:
                text = f.read()
        elif os.path.isdir(path):
            input_path_glob = os.path.join(path,'**')
            for file_path in glob.glob(input_path_glob, recursive=True):
                if not os.path.isdir(file_path):
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

    if args.obey_code_fences:
        if multi_text:
            for key in multi_text.keys():
                multi_text[key] = '\n'.join([e[0] for e in extract_and_label_codefences(multi_text[key])])
        else:
            text = '\n'.join([e[0] for e in extract_and_label_codefences(text)])

    # == Actually do classification ==
    summary_result = {'t1_documents':0,'total_documents':0}
    def increment_summary(result:dict):  # helper to keep track of state for printing a summary, mostly for multi-file classification.
        summary_result['t1_documents'] += int(result['result'])
        summary_result['total_documents'] += 1

    with numpy.errstate(divide='ignore'): # Disable the divide by zero warning that can sometimes be emitted by the model during prediction.
        # TODO: multiproc is almost never worth it unless you have truly huge #s of files.  Consider deprecating if that never becomes a use case, since it adds both this extra logic, the extra param, and the extra helper function.
        num_procs = args.set_parallelism
        if multi_text and num_procs and num_procs > 1: # run multi-file classification in parallel   
            work_keys = list(multi_text.keys())
            work_chunks = [work_keys[i:i+int(math.ceil(len(work_keys)/num_procs))] for i in range(0, len(work_keys), int(math.ceil(len(work_keys)/num_procs)))] # Breaks a list into even sized chunks.  The math.ceil handles off-by-one for odd vs. even length lists.

            result_queue = Queue()
            procs = [Process(target=run_multiproc_classifier, args=(is_t1_classifier, {k:multi_text[k] for k in work_chunks[i]}, result_queue, args.verbose)) for i in range(0,num_procs)]
            for p in procs:
                logging.getLogger(__name__).debug("Starting process: {}".format(p))
                p.start()

            while procs:
                try:
                    # Note: currently we do not use the result on this side of the process boundary, since printing it in the proc is both more immediate and sufficient.
                    # Leaving this here, however, in case we ever need to de-interlace or aggregate in some way.
                    res = result_queue.get(block=False)
                    increment_summary(res[1])
                except queue.Empty:
                    pass
                for p in procs:
                    p.join(timeout=0)
                    if p.exitcode is not None:
                        logging.getLogger(__name__).debug("Cleaning up process: {}".format(p))
                        procs.remove(p)

        elif multi_text: # Run non-parallel multi-file classification
            for path, text in multi_text.items():
                if args.verbose:
                    result = is_t1_classifier.is_t1_verbose(text)
                else:
                    result = is_t1_classifier.is_t1(text)
                increment_summary(result)
                print("{}: {}".format(path, result))
        else: # Classify a single text block.
            if args.verbose:
                result = is_t1_classifier.is_t1_verbose(text)
            else:
                result = is_t1_classifier.is_t1(text)
            increment_summary(result)
            print(result)

    # == Clean up ==
    if args.save_to_file:
        is_t1_classifier.save(args.save_to_file)
    elif args.save_to_blob:
        CONN_STR = os.environ['AZURE_STORAGE_CONNECTION_STRING']
        CONTAINER = os.environ['AZURE_STORAGE_CONTAINER']
        is_t1_classifier.save_to_blob(CONN_STR, CONTAINER, args.save_to_blob)

    print(f"\nSummary of results: {summary_result}") #TODO: put behind a flag.  Spurious for single-file scenario.
    sys.exit(summary_result.get('t1_documents', 0))