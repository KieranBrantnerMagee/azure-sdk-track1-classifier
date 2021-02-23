# This is the DocIndex Track1 document classifier.

The goal of this package is to provide a human-consumable model which attempts to predict whether a given document contains Track1 content which would need to be replaced.


## To run:

First, install the package. (Currently requires manual creation, not pushed to pypi)
`pip install azure-sdk-document-track-classifier.whl`

> Note: If you are a dev working on the package, it may be easier to directly install requirements via `pip install -r requirements.txt` or to do a local package install via `pip -e`

Second, consume the classifier. (64 bit python is recommended for training.)  Be aware that if one does not `load` an existing model file, it will begin training from scratch.  This will take time, and will create accompanying cache files.
```python
from azureSDKTrackClassifier import AzureSDKTrackClassifier
classifier = AzureSDKTrackClassifier() # Can optionally be passed language and service parameters to narrow the classification granularity.
is_t1 = classifier.is_t1("Arbitrary Text That You Want To Classify")
```

> Note: If one desires greater visibility into classification logic (Number of unique tokens found, % of total unique tokens represented, etc), consume the verbose classification API instead.

```python
is_t1_with_metadata = classifier.is_t1_verbose("Arbitrary Text That You Want To Classify And Get Metadata On")
```

> Note: This package can also be run from the command line.  Run command `python -m azureSDKTrackClassifier -h` for full usage information.


## Architecture:

- The final model architecture is a very simple two-class classifier.
- This model operates on metrics created by first tokenizing a corpus of T1 code and T2 code, and then performing set-intersection to determine which tokens are T1 only or T2 only, and their rate of occurance.
- This corpus is obtained by first scraping a package release index per-language, and then using the referenced code locations to extract representative snippets (samples, tests, since they most mirror what we intend to classify without spurious internal dependencies).
  > **Note:** If apistubgen files are present (requiring manual generation), those are used instead as they can be parsed far more easily than the raw code to extract only the most relevent strings.


## File structure:

### classifier.py
Contains the "public API" for this model, a class representing the model, trained on initialization, which can attempt to identify `is_t1(text)`
### model.py
Contains the actual training logic and implementation of the model itself.
### tokenizers.py
Contains the text processing used to tokenize various components of this model, such as the text used for training (and when querying on novel text).  A separate tokenizer exists for apistubgen files.
### helpers.py
Contains the assorted miscellaneous helper functions used elsewhere; file name parsers, corpus and metadata fetchers, etc.
### constants.py
Various enums (e.g. `Language`) and other invariants used in the model.
### settings.py
Like constants, but settings that can be modified at runtime. (e.g. cache path)
> **Note:** Above are the core files.  Below are ancillary.
## \_\_main\_\_.py
Contains logic for command-line runnability of this package.  (e.g. running via python -m azureSDKTrackClassifier)
## Tests
Unit/Integration tests for the model logic.
## Samples
Usage samples for the classifier
## TestCorpus
Contains various files that are being populated as the model is improved upon to give a more representative train/test set than hermetic code samples.  Should be organized as follows: `TestCorpus/{Language}/{Service}/[T1|T2]/{file}`
## Experiments
Historical experiments kept to check against model regressions as well as for novel approaches.
## ApiStubGen
Contains APIStubgen files named in the format of {language}_{service}_{version}.json which will be used, if present, instead of unsupervised training from automatically scraped repo files.


## Misc Implementation Notes:

- Approaches for a consolidated model:
  - Primary approach: Create a new model trained all up on t1 vs t2.
  - Backup approach: Run constituent models, generate feature vector from results. (should they be 3 class, or simply "not t1?"  the latter seems smarter, but may be worth finding out if that's sufficient.)
    - feature vector: (individual: [#t1, #t2, % of t2 list found, % of t1 list found,  group: perhaps just concat individual?)

- If a consolidated model is insufficient, layer submodels as so:
  - Have a "determine which language" model, largely derived similar to the others, but can be punctuation based as well, especially for non-python languages.  Python may require ngrams, since it is near-english.
  - Similarly can have a "Determine which service" model, done via token frequencies or cross-intersections much as we do T1 vs T2. (e.g. "these tokens are unique to this service among all python services, whether t1 or t2.")

- For integrating apistubgen:
  - integrate it at the tokenization step.  can start with naive BOW, and simultaneously build ngrams to play around with.  2 or so may be biggest functionally we can get without syntax-aware parsing on the input side too.
  - Primarily serves as an "if we have this, great!" way to improve signal noise ratio rather than using the unsupervized tokenization over the repository.

- If improving markdown parsing is needed:
  - do not resolve markdown import links or anything like that.  Will be presented as distinct docs.
  - If we end up not needing to split code from markdown files, exdown dependency will not be needed.

- Caching logic: (regardless of when doing comparison at language vs. service vs. T<1,2> level)
  - we store cache at the per-file level so that we can build the slices however we want.  (Note: if you're a dev, enabling use_cache and use_raw_cache in helpers.py may speed your iteration loop by storing local copies of intermediate results)
  - trimmed cache is after reducing the full SDK zip into just the files representing the external interfaces (tests, samples, etc)

- When adding a new language
  - Simply update the enum and repo-mapping dict in the constants.py file.  
  - If the language repository has a repo/file naming convention where the relevent external interfaces wouldn't be captured looking for "/tests/" "/test/" "/samples/" or "/examples/" then update the filter function in `get_corpus_for_package`

## Troubleshooting:

- Enable logging on the command line via `--log-level debug` (or at the desired level)
- Enable logging in your calling program via `logging.basicConfig(level=logging.INFO)`
- > Note: Numpy SHOULD NOT be at 19.4, it breaks windows.

## TODO:

-! check that js stubgen takes just the files.

- is there any way to make model training incremental. (I wonder if we can do a token blacklist, since a lot of the issue is old false positive.)

-? low-signal denoising (Get bigger corpus of low threshold items, then upsample the hell out of them in model training.) (May also be interesting to make a cutoff on low-signal items in unsupervised corpus; e.g. "must be seen >once"; although this may drastically lower signal as well.)

- Continue exploring java-storage-blob weirdness.  Current problem seems to be that while we have V11 legacy, V8 legacy isn't in table, but it seems like a good example of "highly ambiguous" to iterate on.
- (low pri) Investigate steps to use this for language/service tagging as well.
- (low pri) have logging use a common logger name to be properly enabled/disabled by name, and put the function name into the log string.

- Questions for Jon: (most pressing problem running into thus far: versions not in table/that I don't have data for.  Followed by, snippets that are effectively entirely ambiguous. )
  -(new) Followup on low-signal items: Any gut-feel for if a manual cutoff (e.g. ignore over this threshold) would be useful?  Or still high variance.  May be easier to tell after testing with codefence bits.
  -(new) Followup on perf investigation:  I'm not seeing the same perf hit.  Are you running per doc?  Per repo? loading model from file?  I'm seeing sub-second wall-clock times.  I added multiproc to classification but process start overhead dominates such that it's basically not worth it.
    - Now what IS slow, is starting up the python interpreter each time you shell out. (but even that's only like 2-3 seconds)  Curious for how you're doing that
    - if all else fails, can look at making async.
  - Some versions with documentation aren't on the release table.  See below.
    - Service bus 2.0.0 not on table?   https://docs.microsoft.com/en-us/dotnet/api/overview/azure/service-bus
    - Similarly for java storage blob, while we have V11 legacy, V8 legacy isn't in table. https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-java-legacy
    - Same with service bus 1.0.0 for java https://docs.microsoft.com/en-us/java/api/overview/azure/servicebus?view=azure-java-stable
  - Some top level tags don't seem to exist, ala 'https://codeload.github.com/Azure/azure-sdk-for-net/zip/Microsoft.Azure.Storage.Blob_11.2.2'
  - MIT license?
  - What's the deal with the empty package strings in the js package list? (e.g. Active Directory B2C)

- Long term goals to polish and improve:
  - Populate missing or under-present services from tables 
    - Populate apistubgen for any services with bad signal/noise.
    - (lower pri) Investigate additional "RepoPath" fallback, if local folder in alt location is empty of useful code, maybe fall back again to root? This may be risky, as it may ingest logic we don't want.  May be better to just get apistubgen for ones that aren't covered.
  - Get larger labeled test data and optimize results/train model more precisely
    - See if any way to improve version heuristics to give better precision.
    - See if adding n-grams gives better precision for otherwise ambiguous results.
    - Determine if layered or consolidated model is better.  (In other words, If "one size fits all" model does not work well, try determining e.g. Language or Service first, then run targeted classifier.)

### Future Experiments:

- Try culling seen tokens by occurance rate if not using apistubgen (to filter out things like random strings that only appear once), and adding some concept of "total # seen including duplicates" into the feature vector; e.g.  found_old_tokens: {'ae9d', 'localPath', 'localFile', 'FileWriter', '8b34', '47e6', '260e', 'bea2'} (from URL segments)
- Should I be normalizing feature vectors by text length?  Given that relevant content can be sparse within total text it seems like potentially unnecessary bias introduction, but might be worth a try. (e.g. it'd be nice if we knew we were working on "only code specifically in t1 or t2 for this service", at least without a MUCH bigger training corpus.)
- Should I be splitting up code segments from markdown or parsing the whole file?  Or glomming code segments under a certain size together?  How to aggregate child results if we go that way?
    - Should labeled codefences be run on the corrospondent model or the global model?
- Should I create a long feature vector of submodels, or a master model?
