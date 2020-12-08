import re

from .helpers import *
from .constants import Language, LANGUAGE_REPO_MAP
from .tokenizers import tokenize_apistubgen, tokenize_text

_DICTIONARY = enchant.Dict("en_US")


# Contains the metadata produced by training to allow for classification.  Is the "heavy lifting" behind the public classifier API.
# Should not be constructed directly; use `train_model` instead.
class _TrainedModel:
    def __init__(self, only_new_tokens:set, only_old_tokens:set, only_new_versions:set, only_old_versions:set):
        self._only_new_tokens = only_new_tokens
        self._only_old_tokens = only_old_tokens
        self._only_new_versions = only_new_versions
        self._only_old_versions = only_old_versions

        self._model = None # This gets populated incrementally once trained.

    def create_feature_vector(self, text:bytes) -> list:
        tokens = tokenize_text(text)
        found_new_tokens = self._only_new_tokens.intersection(tokens)
        found_old_tokens = self._only_old_tokens.intersection(tokens)
        found_new_versions = [v for v in self._only_new_versions if v in text]
        found_old_versions = [v for v in self._only_old_versions if v in text]
        # In theory we might consider normalizing this by the text length too, but gut-feel is that'd cause more bias than fix. (since "Density of T1 code" may be highly variable)
        # Similarly, I provide both the absolute and relative lengths since it's not "True" normalization, a lib can be big but only have part of it used often.
        return [len(found_new_tokens),
                len(found_old_tokens),
                len(found_new_tokens) / max(1,len(self._only_new_tokens)),
                len(found_old_tokens) / max(1,len(self._only_new_tokens)),
                len(found_new_versions),
                len(found_old_versions)]

    def _do_prediction(self, feature_vector:list) -> bool:
        """Internal function that makes the actual yes/no decision based on the feature vector"""
        # It's a bit dumb to do this like so as opposed to just up-weighting the ratio in the initial feature vector, this is to future proof when we re-add in the proper classifier
        # and _don't_ want to have mucked with the raw features in odd ways, even though it might be a nice human-comprehensable threshold. (more t1 tokens than t2, including version tokens which we upweight?)
        # Mostly, take this as the simple comparator below but with an added component looking for the presence of "version-identifiers" (package names/versions); TODO: should really be tuned.
        #return (feature_vector[2] + (feature_vector[2] / feature_vector[0]) * feature_vector[4] * 2) < (feature_vector[3] + (feature_vector[3] / feature_vector[1]) * feature_vector[5] * 2)
        return feature_vector[2] < feature_vector[3]

        #return "T1" == self._model.predict([feature_vector])[0] # TODO: This is very overfit right now.  Would likely be better when we get a more realistic training set. (false positives etc.)

    def classify(self, text:bytes) -> bool:
        v = self.create_feature_vector(text)
        return self._do_prediction(v)

    def classify_verbose(self, text:bytes) -> bool:
        v = self.create_feature_vector(text)
        return {'result':self._do_prediction(v),
                't2_token_count':v[0],
                't1_token_count':v[1],
                'percent_of_all_t2':v[2],
                'percent_of_all_t1':v[3],
                't2_version_count':v[4],
                't1_version_count':v[5]}


# Should arguably be the initializer of the _TrainedModel but this oddly feels cleaner. (with the model just being the exportable bits, and this is exclusively "Training")
def train_model(language : Language = None, service : str = None) -> _TrainedModel:
    """Returns a model trained to classify text as being T1 for the specified language or service.  None implies wildcard.
        Specifying include_verbose_classifier returns a function returning both the classification result and the features that lead to it."""  

    # Get releases metadata, extract T2 and T1 package versions to build training datasets.
    new_package_metadata = []
    old_package_metadata = []

    languages_to_fetch = [language] if language else LANGUAGE_REPO_MAP.keys()
    for each_language in languages_to_fetch:
        release_info = get_release_metadata(each_language)
        repo = LANGUAGE_REPO_MAP[each_language]

        services_to_fetch = [service] if service else release_info.keys()
        for each_service in services_to_fetch:
            new_package_metadata += [(e, each_language) for e in release_info[each_service] if e['New'].lower() == 'true']
            old_package_metadata += [(e, each_language) for e in release_info[each_service] if e['New'].lower() != 'true']

    # Get the old/new corpus files.
    new_corpus_files, new_tokens, new_versions = get_corpus_tokens_and_versions_for_package(new_package_metadata)
    old_corpus_files, old_tokens, old_versions = get_corpus_tokens_and_versions_for_package(old_package_metadata)

    # Use tokens to build t1/t2 intersection sets
    intersection = new_tokens.intersection(old_tokens)
    only_new_tokens = new_tokens - intersection - set([t for t in new_tokens if _DICTIONARY.check(t) or not re.search('[a-zA-Z]', t)]) # remove english words as that causes false positives as opposed to only looking at "tech terms", and remove punctuation-only noise.
    only_old_tokens = old_tokens - intersection - set([t for t in old_tokens if _DICTIONARY.check(t) or not re.search('[a-zA-Z]', t)]) # MAYBE TODO: Should only do this for non-apistubgenned files?  TODO: If you end up using this for language classification, disable punctuation removal.
    version_intersection = new_versions.intersection(old_versions)
    only_new_versions = new_versions - version_intersection
    only_old_versions = old_versions - version_intersection

    # Train classifier on old/new corpus files.  (TODO: Yes, this is highly overfitting, mostly here as PoC, as we improve the testcorpus (which we should incorporate once mature) and train this on real content we will get better false positive/negative representation, in the meantime we'll use a naive decision function that "mostly performs pretty well".) 
    # First, build training vectors, and the vectorizer we'll be exporting with our classifier. (we build our model incrementally)

    trained_model = _TrainedModel(only_new_tokens, only_old_tokens, only_new_versions, only_old_versions)

    training_vectors = []
    training_classes = []
    for (corpus, label) in [(new_corpus_files, "Not T1"), (old_corpus_files, "T1")]:
        for file, text in corpus.items():
            training_vectors.append(trained_model.create_feature_vector(text))
            training_classes.append(label)

    # Then actually train the model.
    should_score = True
    if should_score:
        scores = cross_val_score(RandomForestClassifier(max_depth=4, random_state=0), training_vectors, training_classes, cv=10)
        logging.getLogger(__name__).info("Accuracy: %0.2f (+/- %0.2f) N=%0.2f" % (scores.mean(), scores.std() * 2, len(training_vectors)/10))

    trained_model._model = RandomForestClassifier(max_depth=4, random_state=0)
    trained_model._model.fit(training_vectors, training_classes)

    return trained_model