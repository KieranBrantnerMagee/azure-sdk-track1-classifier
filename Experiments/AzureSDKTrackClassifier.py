# NOTE:  This is the V1 classifier experiment, it differentiates between T1 and T2 of a single language+service by tokenization and token-differencing of the SDK code used for each respective service.
# It is replaced by AzureSDKTrackClassifierV2, but kept for posterity or if needed.

from enum import Enum

class Language(str, Enum):
    dotnet="dotnet"
    # TODO: Enable these as they are tested.
    python = "python"
    java = "java"
    js = "js"

# Note: Final version should likely not require specifying language or service.  This could be a sub-model within that, since we can infer from fixed lists.
class AzureSDKTrack1Classifier:
    def __init__(self, language : Language, service : str):
        self._classifier = train_classifier(language, service)

    def is_t1(text):
        return self._classifier(text)

# helpers
import requests
import csv
import zipfile
from io import BytesIO
from nltk.tokenize import WordPunctTokenizer
from functools import lru_cache

def is_markdown(contents:str, name:str=None):
    if name:
        return name.lower().endswith('.md')
    return False

def get_extension(name:str):
    try:
        return name.lower().split('/')[-1].split('.')[1]
    except:
        return None

def detect_acceptable_extension(name:str):
    if name:
        extension = get_extension(name)
        if extension in ('cs', 'py', 'ipynb', 'java', 'js', 'ts', 'md', 'txt'):
            return extension
    return None

@lru_cache
def get_release_metadata(language:Language):
    language = Language(language) # Basically an assert.
    releases = requests.get("https://raw.githubusercontent.com/Azure/azure-sdk/master/_data/releases/latest/{}-packages.csv".format(language.value)).text
    # Split by newline so it picks up header associations.
    reader = csv.DictReader(releases.split())
    info = {}
    for row in reader:
        try:
            info[row['ServiceName']].append(row)
        except:
            info[row['ServiceName']] = [row]
    return info

USE_CORPUS_CACHE=True
def get_corpus_for_package(repo:str, package:str, version:str, custom_repo_uri:str=None):
    corpus = {}

    package_zip_uri = "https://github.com/Azure/{}/archive/{}_{}.zip".format(repo, package, version)
    if custom_repo_uri:
        try:
            base_uri, custom_subpath = custom_repo_uri.split('/tree/')
            #package_zip_uri = "{}/archive/master.zip".format(base_uri)
        except:
            pass
    # Attempt to get custom repo uri + version from releases.
    # maybe go up a level and look for "tests" and "Samples" if nothing in local dir?

    # So that in testing we don't take ages.
    if USE_CORPUS_CACHE:
        cache_name = "corpus_{}_{}_{}.cache".format(repo, package, version)
        try:
            with open(cache_name, 'rb') as f:
                version_zip = f.read()
        except:
            version_zip = requests.get(package_zip_uri).content
            with open(cache_name, 'wb') as f:
                f.write(version_zip)
    else:
        version_zip = requests.get(package_zip_uri).content

    if version_zip == b'404: Not Found':
        # raise Exception("No zip for URI: {}".format(package_zip_uri))
        print("No zip for URI: {}".format(package_zip_uri))
        return {}

    with zipfile.ZipFile(BytesIO(version_zip), 'r') as zf:
        files = [n for n in zf.namelist() \
                    if not n.endswith('/') \
                        and detect_acceptable_extension(n) \
                        and ('/sdk/' in n and package in n.split('/sdk/')[-1])] #TODO: This is a total hack, find the proper sdk/ path better.
        for file in files:
            body = zf.read(file)
            corpus[file] = body
    return corpus

language_repo_map = {Language.dotnet:'azure-sdk-for-net', Language.js:'azure-sdk-for-js', Language.java:'azure-sdk-for-java', Language.python:'azure-sdk-for-python'}
def train_classifier(language : Language, service : str):
    # Get releases metadata, extract T2 and T1 package versions and fetch relevant corpuses.
    release_info = get_release_metadata(language)
    repo = language_repo_map[language]
    if Language(language) != Language.dotnet:
        raise NotImplemented("Only dotnet has been tested thus far.")

    new_package_metadata = [e for e in release_info[service] if e['New'].lower() == 'true']
    old_package_metadata = [e for e in release_info[service] if e['New'].lower() != 'true']

    new_corpus_files = {}
    for each in new_package_metadata:
        new_corpus_files.update(get_corpus_for_package(repo, each['Package'], each['VersionGA'] or each['VersionPreview'], each['RepoPath']))
    old_corpus_files = {}
    for each in old_package_metadata:
        old_corpus_files.update(get_corpus_for_package(repo, each['Package'], each['VersionGA'] or each['VersionPreview'], each['RepoPath']))
    
    # Split corpuses into train and test.  Combine train into a single file since we're tokenizing anyway, we still need granular test for evaluation.
    # Note: Should use nltk cross-val for this but wanted to play with corpus selection for experimentation, e.g. only tests/samples since they're more representative than "all stuff".
    def in_train(index, name):
        return ('/samples/' in name or '/examples/' in name or '/tests/' in name) and index % 10 != 0

    def in_test(index, name):
        return ('/samples/' in name or '/examples/' in name or '/tests/' in name) and index % 10 == 0

    new_train_corpus = b"\n".join([file for index, (name, file) in enumerate(new_corpus_files.items()) if in_train(index,name)])
    old_train_corpus = b"\n".join([file for index, (name, file) in enumerate(old_corpus_files.items()) if in_train(index,name)])
    
    new_test_files = {name:file for index, (name, file) in enumerate(new_corpus_files.items()) if in_test(index, name)}
    old_test_files = {name:file for index, (name, file) in enumerate(old_corpus_files.items()) if in_test(index, name)}
    
    # Do the actual tokenization, determine T1/T2 only tokens.
    tokenizer = WordPunctTokenizer() # NOTE: This is somewhat arbitrary outside it being convenient and giving acceptable punctuation handling for our needs.
    def tokenize(text):
        return set(tokenizer.tokenize(text.decode('utf-8'))) # Contemplated things like occurence filtering and the like, but this "seems workable" for the time being, if we added that we should go all the way to feature vectors and a full classifier.

    new_tokens = tokenize(new_train_corpus)
    old_tokens = tokenize(old_train_corpus)
    intersection = new_tokens.intersection(old_tokens)
    only_new_tokens = new_tokens - intersection
    only_old_tokens = old_tokens - intersection

    found_new_tokens = None # Terrible hack to let me exfiltrate these for eval.
    found_old_tokens = None
    def is_t1(text): # The actual classifier we export.
        tokens = tokenize(text)
        found_new_tokens = only_new_tokens.intersection(tokens)
        found_old_tokens = only_old_tokens.intersection(tokens)
        return len(found_new_tokens) < len(found_old_tokens) # because 0 effort.  TODO: Upgrade to a random forest, turn token lists into token-identifier based feature vecotrs if needed; _at least_ treat it as a threshold/confidence. rather than just >

    # Finally, evaluate our criterea.
    wrong_t2 = []
    right_t2 = []
    for name,file in new_test_files.items():
        if not is_t1(file):
            right_t2.append((name, found_new_tokens, found_old_tokens, file))
        else:
            wrong_t2.append((name, found_new_tokens, found_old_tokens, file))

    wrong_t1 = []
    right_t1 = []
    for name,file in old_test_files.items():
        if is_t1(file):
            right_t1.append((name, found_new_tokens, found_old_tokens, file))
        else:
            wrong_t1.append((name, found_new_tokens, found_old_tokens, file))

    print("t1_accuracy: {} t2_accuracy: {}".format(len(right_t1) / (len(right_t1)+len(wrong_t1)), len(right_t2) / (len(right_t2)+len(wrong_t2))))
    return is_t1

if __name__ == "__main__":
    #is_t1_classifier = AzureSDKTrack1Classifier(Language.dotnet, "ServiceBus")
    #is_t1_classifier = AzureSDKTrack1Classifier(Language.dotnet, "EventHubs")
    is_t1_classifier = AzureSDKTrack1Classifier(Language.dotnet, "Storage")
    # for language in [Language.dotnet, Language.js, Language.java, Language.python]:
    #     try:
    #         info = get_release_metadata(language)
    #     except Exception as e:
    #         print(e)
    #     for packages_for_service in info.values():
    #         for each in packages_for_service:
    #             try:
    #                 print("Getting corpus for: " + str(language.value) + " : " + each['Package'])
    #                 get_corpus_for_package(language_repo_map[language], each['Package'], each['VersionGA'] or each['VersionPreview'], each['RepoPath'])
    #             except Exception as e:
    #                 print(e)

    exit()

