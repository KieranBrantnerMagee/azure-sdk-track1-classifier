import csv
from functools import lru_cache
import io
from io import BytesIO
import json
import logging
import os
from typing import Tuple
import zipfile

import enchant
import exdown
import requests

from .constants import Language, LANGUAGE_REPO_MAP
from .settings import Settings
from .tokenizers import tokenize_text, tokenize_apistubgen


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


_DICTIONARY = enchant.Dict("en_US")
def check_in_english_dictionary(word:str) -> bool:
    try:
        return _DICTIONARY.check(word)
    except Exception as e:
        logging.getLogger(__name__).warning("Warning: Exception while checking english dictionary for string '{}': {}".format(word, e))
        return False

def do_github_zip_request(zip_uri):
    # Does the actual request, along with some heuristics in case the main branch is main or master.
    version_zip = requests.get(zip_uri).content
    if version_zip == b'404: Not Found' and 'master.zip' in zip_uri: # This is a github-ism.
        version_zip = requests.get(zip_uri.replace('master.zip', 'main.zip')).content
    return version_zip

def locate_and_fetch_github_repo_zip_and_subpath(repo:str, package:str, version:str, custom_repo_uri:str=None, use_raw_corpus_cache:bool=False) -> Tuple(bytes, str): # returns the zip in bytes, and if needed, the custom subpath to look under within it.
    package_zip_uri = "https://github.com/Azure/{}/archive/{}_{}.zip".format(repo, package, version)
    if custom_repo_uri == 'NA':
        custom_repo_uri = None
    custom_subpath = None
    # NOTE: This assumes all repos are github.
    if custom_repo_uri: # TODO: Is this check safe given the filters above?  (meant to catch the 'NAs' in some release metadata, such as dotnet.)
        logging.getLogger(__name__).info("Using custom repository URI: {}".format(custom_repo_uri))
        try:
            package_zip_uri, custom_subpath = get_zip_uri_and_subpath_from_github_link(custom_repo_uri) # Parse the raw link into a downloadable zip, and the subpath we need to extract from it.

            logging.getLogger(__name__).info("Successfully converted custom repository URI into package zip: {} (custom_subpath: {})".format(package_zip_uri, custom_subpath))

        except Exception as e:
            # Something went wrong, so let's _try_ to fall back to the normal pattern, and report the warning for diagnosis in either case.
            logging.getLogger(__name__).warning("Warning: Exception while parsing custom_repo_uri: {}".format(e))

    # Attempt to get custom repo uri + version from releases.
    # TODO: maybe go up a directory level and look for "tests" and "Samples" if nothing in local dir?  May be more trouble than worth in the long run, apistubgen may be better for the one-offs that are structured this weird, but worth keeping in mind.
    logging.getLogger(__name__).info("Fetching {} {} {}".format(repo, package, version))
    # So that in testing we don't take ages, cache intermediate results.
    if use_raw_corpus_cache:
        raw_cache_name = os.path.join(Settings.CACHE_BASE_PATH, "corpus_{}_{}_{}.cache".format(repo, package.replace('/', '_'), version)) # The replace is for JS packages.
        try:
            with open(raw_cache_name, 'rb') as f:
                version_zip = f.read()
                logging.getLogger(__name__).info("Found in cache {} {} {}".format(repo, package, version))
        except:
            version_zip = do_github_zip_request(package_zip_uri)
            with open(raw_cache_name, 'wb') as f:
                f.write(version_zip)
    else:
        version_zip = do_github_zip_request(package_zip_uri)

    return version_zip, custom_subpath

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


def get_corpus_for_package(repo:str, package:str, version:str, custom_repo_uri:str=None, use_cache:bool=True, use_raw_corpus_cache:bool=False) -> dict:
    """Fetches a dict of 'public interface code' files (samples, tests, readme, representative samples you'd see in public documentation) from a specified
    repo, package, and version. (for Azure SDK packages on github)."""
    corpus = {}

    if not package or not version:
        logging.getLogger(__name__).warning("Cannot fetch corpus for null package ({})/version ({}) for {} (custom_repo_uri:{})".format(package, version, repo, custom_repo_uri))
        return {}

    if use_cache:
        cache_name = os.path.join(Settings.CACHE_BASE_PATH, "trimmed_corpus_{}_{}_{}.cache".format(repo, package.replace('/', '_'), version)) # The replace is for JS packages.
        try:
            with open(cache_name, 'r') as f:
                logging.getLogger(__name__).info("Found in trimmed cache {} {} {}".format(repo, package, version))
                return json.loads(f.read())
        except:
            pass

    version_zip, custom_subpath = locate_and_fetch_github_repo_zip_and_subpath(repo, package, version, custom_repo_uri, use_raw_corpus_cache)

    if version_zip == b'404: Not Found': # This is a github-ism.
        logging.getLogger(__name__).warning("No zip for URI: {} (repo: {} package: {} version: {})".format(package_zip_uri, repo, package, version))
        if Settings.MISSING_TRAINING_LOG: # If desired, log missing corpuses to file for triage.
            with open(Settings.MISSING_TRAINING_LOG, 'a') as f:
                f.write("{}\t{}\t{}\t{}".format(package_zip_uri, repo, package, version))
        corpus = {}
    else:
        with zipfile.ZipFile(BytesIO(version_zip), 'r') as zf:
            files = [n for n in zf.namelist() \
                        if not n.endswith('/') \
                            and is_acceptable_extension(n) \
                            and ((custom_subpath is not None and custom_subpath in n) \
                                or (custom_subpath is None and '/sdk/' in n and package in n.split('/sdk/')[-1])) \
                            and any([k in n for k in ['/samples/', '/examples/', '/tests/', '/test/', 'README']])] 
                     # TODO: The second part of above is very "rough", find the proper sdk/ path better+filter smarter; may want to add yaml and md to this.
                     # TODO: We may want to adjust this to take n.lower().contains('samples/') as well for situations like this if ends up not being an outlier. https://github.com/Azure/azure-cosmos-dotnet-v3/tree/releases/4.0.0-preview3/Microsoft.Azure.Cosmos.Samples
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


def get_zip_uri_and_subpath_from_github_link(custom_repo_uri:str)->tuple:
    """Parse the raw github link into a downloadable zip, and the subpath we need to extract from it to get the directory represented in the original link."""
    if '/tree/releases/' in custom_repo_uri:
        base_uri, tag_and_subpath = custom_repo_uri.split('/tree/releases/', 1) # There's no way to get a zip for a subfolder, so we have to get the whole repo then filter by the intended path.
        tag = tag_and_subpath.split('/', 1)[0] # The commit tag is always the first item after the tree specifier.
        package_zip_uri = "{}/archive/releases/{}.zip".format(base_uri, tag)
        try:
            custom_subpath = tag_and_subpath.split('/', 1)[1]
        except IndexError:
            custom_subpath = ''

    elif '/tree/' in custom_repo_uri:
        base_uri, tag_and_subpath = custom_repo_uri.split('/tree/', 1) # There's no way to get a zip for a subfolder, so we have to get the whole repo then filter by the intended path.
        tag = tag_and_subpath.split('/', 1)[0] # The commit tag is always the first item after the tree specifier.
        package_zip_uri = "{}/archive/{}.zip".format(base_uri, tag)
        try:
            custom_subpath = tag_and_subpath.split('/', 1)[1]
        except IndexError:
            custom_subpath = ''
    
    else: # it's linking to the root of a repo if one of the above isn't present.
        package_zip_uri = "{}/archive/master.zip".format(custom_repo_uri)
        custom_subpath = ''

    return package_zip_uri, custom_subpath

# Experimental feature to perform stub-generation on the fly by requesting it from a stub gen server.
FETCH_AND_BACKFILL_MISSING_STUBGEN=False
def get_apistubgen_tokens_for_package(language:Language, package:str, version:str, group_id:str, custom_repo_uri:str) -> set:
    language = Language(language)
    # This requires an apistubgen file to be generated and named properly to be picked up.
    try:
        with open("./ApiStubGen/{}_{}_{}.json".format(language.value, package, version)) as f:
            logging.getLogger(__name__).info("Found apistubgen file for {} {} {};".format(language, package, version))
            return set([token for token_list in tokenize_apistubgen(json.loads(f.read())).values() for token in token_list])
    except IOError:
        if FETCH_AND_BACKFILL_MISSING_STUBGEN:
            # First, get the actual package.
            if language == Language.dotnet: #TODO: The various "per-language" functionality should be consolidated one place to make it easy to add new languages.
                package = requests.get(f"https://www.nuget.org/api/v2/package/{package}/{version}").content
            elif language == Language.js:
                package, _ = locate_and_fetch_github_repo_zip_and_subpath(repo, package, version, custom_repo_uri)
            elif language == Language.python:
                packages_page = requests.get(f"https://pypi.org/project/{package}/{version}/#files")
                package_uri = re.findall("(http[^\>]+\.whl)", packages_page.text)[0]
                package = requests.get(package_uri).content
            elif language == Language.java:
                group_id = group_id.replace('.', '/')
                package = requests.get(f"https://search.maven.org/remotecontent?filepath={group_id}/{package}/{version}/{package}-{version}-sources.jar").content
            # TODO: Pass the package to the apistubgen endpoint to have it be processed, save the result to the location specified here, then return the parsed token set.
        else:
            return set()


# Helper function to do the corpus lookup and tokenization for a given list of package metadata.
# Also extracts version tokens seperately since we can use them for special heuristics.
def get_corpus_files_tokens_and_versions_for_package(metadata:list) -> tuple:
    corpus_files = {}
    tokens = set()
    versions = set()
    for (each, each_language) in metadata:
        raw_corpus = None
        last_exception = None

        version = each['VersionGA'] or each['VersionPreview']
        package = each['Package']
        custom_repo_path = each['RepoPath'] if each['RepoPath'].startswith('http') else None # If RepoPath is a uri instead of just a package name, use that instead. (this can be e.g. historical or nonstandard repos)
        group_id = each.get('GroupId') # This is java specific as of 2/6/2021, only needed for fetching the package from maven for auto-api-stub-genification.

        raw_corpus = get_corpus_for_package(LANGUAGE_REPO_MAP[each_language], package, version, custom_repo_path)

        corpus_files.update(raw_corpus)
        # If you have apistubgen, get that and build tokens.  If not, use the corpus files.
        stubgen_tokens = get_apistubgen_tokens_for_package(each_language, package, version, group_id, custom_repo_path) # If we have apistubgen, use it, otherwise fall back to unsupervised.
        tokens = tokens.union(stubgen_tokens or tokenize_text('\n'.join(raw_corpus.values())))

        versions.add(package)
        for version_id in [each['VersionGA'], each['VersionPreview']]:
            if version_id:
                versions.add(version_id.split('-')[0])

    return corpus_files, tokens, versions


# Helper function used for parallelizing __main__ classifier evaluation.
def run_multiproc_classifier(is_t1_classifier:"AzureSDKTrackClassifier", multi_text:dict, queue:"Queue", verbose:bool):
    for path, text in multi_text.items():
        if verbose:
            result = is_t1_classifier.is_t1_verbose(text)
        else:
            result = is_t1_classifier.is_t1(text)
        print("{}: {}".format(path, result))
        queue.put((path, result))
