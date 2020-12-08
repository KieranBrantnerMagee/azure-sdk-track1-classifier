import csv
from functools import lru_cache
import io
from io import BytesIO
import json
import logging
import zipfile

import enchant
import exdown
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

from .constants import Language, LANGUAGE_REPO_MAP
from .tokenizers import tokenize_text

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

CACHE_BASE="Z:\\scratch\\" # "." #TODO: Swap this back in.
def get_corpus_for_package(repo:str, package:str, version:str, custom_repo_uri:str=None, use_cache:bool=False, use_raw_corpus_cache:bool=False):
    corpus = {}

    if use_cache:
        cache_name = CACHE_BASE + "trimmed_corpus_{}_{}_{}.cache".format(repo, package.replace('/', '_'), version) # The replace is for JS packages.
        try:
            with open(cache_name, 'r') as f:
                logging.getLogger(__name__).info("Found in trimmed cache {} {} {}".format(repo, package, version))
                return json.loads(f.read())
        except:
            pass

    package_zip_uri = "https://github.com/Azure/{}/archive/{}_{}.zip".format(repo, package, version)
    if custom_repo_uri:
        try:
            base_uri, custom_subpath = custom_repo_uri.split('/tree/') # There's no way to get a zip for a subfolder, so we have to get the whole repo then filter by the intended path.
            package_zip_uri = "{}/archive/master.zip".format(base_uri)
        except Exception as e:
            logging.getLogger(__name__).warning("Warning: Exception while parsing custom_repo_uri: {}".format(e))

    # Attempt to get custom repo uri + version from releases.
    # maybe go up a level and look for "tests" and "Samples" if nothing in local dir?

    logging.getLogger(__name__).info("Fetching {} {} {}".format(repo, package, version))
    # So that in testing we don't take ages.
    if use_raw_corpus_cache:
        raw_cache_name = CACHE_BASE + "corpus_{}_{}_{}.cache".format(repo, package.replace('/', '_'), version) # The replace is for JS packages.
        try:
            with open(raw_cache_name, 'rb') as f:
                version_zip = f.read()
                logging.getLogger(__name__).info("Found in cache {} {} {}".format(repo, package, version))
        except:
            version_zip = requests.get(package_zip_uri).content
            with open(raw_cache_name, 'wb') as f:
                f.write(version_zip)
    else:
        version_zip = requests.get(package_zip_uri).content

    if version_zip == b'404: Not Found':
        logging.getLogger(__name__).warning("No zip for URI: {}".format(package_zip_uri))
        corpus = {}
    else:
        with zipfile.ZipFile(BytesIO(version_zip), 'r') as zf:
            files = [n for n in zf.namelist() \
                        if not n.endswith('/') \
                            and is_acceptable_extension(n) \
                            and ((custom_repo_uri and custom_subpath in n) or (not custom_repo_uri and '/sdk/' in n and package in n.split('/sdk/')[-1])) \
                            and ('/samples/' in n or '/examples/' in n or '/tests/' in n or '/test/' in n or 'README' in n)] #TODO: The second part of above is very "rough", find the proper sdk/ path better+filter smarter; may want to add yaml and md to this.
            for file in files:
                body = zf.read(file)
                try:
                    corpus[file] = body.decode('UTF-8')
                except:
                    try:
                        corpus[file] = body.decode('unicode_escape')
                    except Exception as e:
                        logging.getLogger(__name__).warning("Unable to read corpus file: {}; {}".format(file, e))

    if use_cache:
        with open(cache_name, 'w') as f:
            f.write(json.dumps(corpus))

    return corpus

def get_apistubgen_tokens_for_package(package:str, version:str) -> set:
    # This requires an apistubgen file to be generated and named properly to be picked up.
    try:
        with open("./apistubgen/{}_{}.json") as f:
            return set([token for token_list in tokenize_apistubgen(json.loads(f.read())).values() for token in token_list])
    except IOError:
        return set()

# Helper function to do the corpus lookup and tokenization for a given list of package metadata.
# Also extracts version tokens seperately since we can use them for special heuristics.
def get_corpus_tokens_and_versions_for_package(metadata:list):
    corpus_files = {}
    tokens = set()
    versions = set()
    for (each, each_language) in metadata:
        raw_corpus = None
        last_exception = None

        version = each['VersionGA'] or each['VersionPreview']
        package = each['Package']
        custom_repo_path = None if each['New'] == 'true' else each['RepoPath'] # for new ones it's just the local path.  Should maybe be checking for "http<s>" as well?

        raw_corpus = get_corpus_for_package(LANGUAGE_REPO_MAP[each_language], package, version, custom_repo_path)

        corpus_files.update(raw_corpus)
        # If you have apistubgen, get that and build tokens.  If not, use the corpus files.
        stubgen_tokens = get_apistubgen_tokens_for_package(package, version) # If we have apistubgen, use it, otherwise fall back to unsupervised.
        tokens = tokens.union(stubgen_tokens or tokenize_text('\n'.join(raw_corpus.values())))
        versions = versions.union(set([package, version.split('-')[0]]))
    return corpus_files, tokens, versions