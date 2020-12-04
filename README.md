# This is the DocIndex Track1 document classifier.

The goal of this package is to provide a human-consumable model which attempts to predict whether a given document contains Track1 content which would need to be replaced.

## To run:

First, install requirements
`pip install -r requirements.txt`

Second, consume the classifier.
```python
from AzureSDKTrackClassifierV2 import AzureSDKTrack1Classifier
classifier = AzureSDKTrack1Classifier() # Can optionally be passed language and service parameters to narrow the classification granularity.
is_t1 = classifier.is_t1("Arbitrary Text That You Want To Classify")
```

## Architecture:

- The final model architecture is a very simple two-class classifier.
- This model operates on metrics created by first tokenizing a corpus of T1 code and T2 code, and then performing set-intersection to determine which tokens are T1 only or T2 only, and their rate of occurance.
- This corpus is obtained by first scraping a package release index per-language, and then using the referenced code locations to extract representative snippets (samples, tests, since they most mirror what we intend to classify without spurious internal dependencies).
  > **Note:** If apistubgen files are present (requiring manual generation), those are used instead as they can be parsed far more easily than the raw code to extract only the most relevent strings.


## File structure:

### AzureSDKTrackClassifierV2.py
Contains the "public API" for this model, a class representing the model, trained on initialization, which can attempt to identify `is_t1(text)`
### model.py
Contains the actual training and implementation of the model itself.
### tokenizers.py
Contains the text processing used to tokenize various components of this model, such as the text used for training (and when querying on novel text).  A separate tokenizer exists for apistubgen files.
### helpers.py
Contains the assorted miscellaneous helper functions used elsewhere; file name parsers, corpus and metadata fetchers, etc.
### constants.py
Various enums (e.g. `Language`) and other invariants used in the model.
> **Note:** Above are the core files.  Below are ancillary.
## TestCorpus
Contains various files that are being populated as the model is improved upon to give a more representative train/test set than hermetic code samples.  Should be organized as follows: `TestCorpus/<Service>/<T1|T2>/<file>`
## Experiments
Historical experiments kept to check against model regressions as well as for novel approaches.


## TODO:
- some tags don't seem to exist, ala 'https://codeload.github.com/Azure/azure-sdk-for-net/zip/Microsoft.Azure.Storage.Blob_11.2.2'
	- Fall back to using "RepoPath" if present, if local folder in alt location is empty, maybe fall back again to root?
- organizing by "ServiceName" but e.g. see "keyvault" under "Storage", does this mean what I think it means?
- (low pri) coerce the file structure into a proper python module/package.

## Misc Implementation Notes:
- If a consolidated model is needed, approaches:
  - Run constituent models, generate feature vector from results. (should they be 3 class, or simply "not t1?"  the latter seems smarter, but may be worth finding out if that's sufficient.)
    - feature vector: (individual: [#t1, #t2, % of t2 list found, % of t1 list found,  group: perhaps just concat individual?)
  - Create a new model trained all up on t1 vs t2.

- when integrating apistubgen:
  - do it at the tokenization step.  can start with naive BOW, and simultaneously build ngrams to play around with.  2 or so may be biggest functionally we can get without syntax-aware parsing on the input side too.

- When improving markdown parsing:
  - do not resolve markdown import links or anything like that.  Will be presented as distinct docs.


## Future Experiments:
- Should I be splitting up code segments from markdown or parsing the whole file?  Or glomming code segments under a certain size together?  How to aggregate child results if we go that way?
- Should I create a long feature vector of submodels, or a master model.