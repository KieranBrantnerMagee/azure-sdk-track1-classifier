from collections import defaultdict
import csv
from functools import lru_cache
import io
from io import BytesIO
import json
import logging
import zipfile

import enchant
import exdown
from nltk.tokenize import WordPunctTokenizer
from nltk.corpus import words
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

from constants import Language

def get_extension(name:str):
    try:
        return name.lower().split('/')[-1].split('.')[1]
    except:
        return None

def is_acceptable_extension(name:str):
    if name:
        extension = get_extension(name)
        if extension in ('cs', 'py', 'ipynb', 'java', 'js', 'ts', 'md', 'txt', 'yaml'):
            return extension
    return None

def is_code(contents:str, name:str=None):
    # Determines if a file contains code or not. (Or at least, one of the languages we recognize)
    # This and below takes contents because may want to extrapolate if an extension isn't defined, or if it's an ad-hoc snippet.
    try:
        language = {'cs':Language.dotnet, \
                    'js':Language.js, \
                    'java':Language.java, \
                    'python':Language.python}[get_extension(name)]
        return language
    except KeyError as e:
        return False

def is_yaml(contents:str, name:str=None):
    if name:
        return name.lower().endswith('.yaml')
    return False

def is_markdown(contents:str, name:str=None):
    if name:
        return name.lower().endswith('.md')
    return False

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

def get_corpus_for_package(repo:str, package:str, version:str, custom_repo_uri:str=None, use_corpus_cache:bool=True):
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
    if use_corpus_cache:
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
        logging.getLogger(__name__).warning("No zip for URI: {}".format(package_zip_uri))
        return {}

    with zipfile.ZipFile(BytesIO(version_zip), 'r') as zf:
        files = [n for n in zf.namelist() \
                    if not n.endswith('/') \
                        and is_acceptable_extension(n) \
                        and ('/sdk/' in n and package in n.split('/sdk/')[-1]) \
                        and ('/samples/' in n or '/examples/' in n or '/tests/' in n)] #TODO: The above is a total hack, find the proper sdk/ path better+filter smarter; may want to add yaml and md to this.
        for file in files:
            body = zf.read(file).decode('UTF-8')
            corpus[file] = body
    return corpus

def get_apistubgen_tokens_for_package(package:str, version:str) -> set:
    # This requires an apistubgen file to be generated and named properly to be picked up.
    try:
        with open("./apistubgen/{}_{}.json") as f:
            return set([token for token_list in tokenize_apistubgen(json.loads(f.read())).values() for token in token_list])
    except IOError:
        return set()
