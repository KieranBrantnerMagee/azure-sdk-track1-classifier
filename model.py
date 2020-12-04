from helpers import *
from constants import Language, LANGUAGE_REPO_MAP
from tokenizers import tokenize_apistubgen, tokenize_text

# english_words = set([word.lower() for word in words.words()]) Note: switched to using pyEnchant for spell checking instead, keeping this just in case results regress.
dictionary = enchant.Dict("en_US")
def train_classifier(language : Language = None, service : str = None):
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
    # If you have apistubgen, get that and build tokens.  If not, use the corpus files.
    def _get_corpus_and_tokens_for_package(metadata:list):
        corpus_files = {}
        tokens = set()
        for (each, each_language) in metadata:
            raw_corpus = get_corpus_for_package(LANGUAGE_REPO_MAP[each_language], each['Package'], each['VersionGA'] or each['VersionPreview'], each['RepoPath'])
            corpus_files.update(raw_corpus)
            stubgen_tokens = get_apistubgen_tokens_for_package(each['Package'], each['VersionGA'] or each['VersionPreview']) # If we have apistubgen, use it, otherwise fall back to unsupervised.
            tokens = tokens.union(stubgen_tokens or tokenize_text('\n'.join(raw_corpus.values())))
        return corpus_files, tokens

    new_corpus_files, new_tokens = _get_corpus_and_tokens_for_package(new_package_metadata)
    old_corpus_files, old_tokens = _get_corpus_and_tokens_for_package(old_package_metadata)

    # Use tokens to build t1/t2 intersection sets, and the feature-vectorizer we'll export alongside our classifier.
    intersection = new_tokens.intersection(old_tokens)
    only_new_tokens = new_tokens - intersection - set([t for t in new_tokens if dictionary.check(t)]) # remove english words as that causes false positives as opposed to only looking at "tech terms"
    only_old_tokens = old_tokens - intersection - set([t for t in old_tokens if dictionary.check(t)]) # MAYBE TODO: Should only do this for non-apistubgenned files?

    def _create_feature_vector(text:bytes) -> list:
        tokens = tokenize_text(text)
        found_new_tokens = only_new_tokens.intersection(tokens)
        found_old_tokens = only_old_tokens.intersection(tokens)
        # In theory we might consider normalizing this by the text length too, but gut-feel is that'd cause more bias than fix. (since "Density of T1 code" may be highly variable)
        # Similarly, I provide both the absolute and relative lengths since it's not "True" normalization, a lib can be big but only have part of it used often.
        return [len(found_new_tokens), len(found_old_tokens), len(found_new_tokens) / len(only_new_tokens), len(found_old_tokens) / len(only_old_tokens)]

    # Train classifier on old/new corpus files.  (TODO: Yes, this is highly overfitting, as we test this on real content we can build a standalone train/test corpus that will give better false positive/negative representation.) 
    # First, build training vectors.
    training_vectors = []
    training_classes = []
    for (corpus, label) in [(new_corpus_files, "Not T1"), (old_corpus_files, "T1")]:
        for file, text in corpus.items():
            training_vectors.append(_create_feature_vector(text))
            training_classes.append(label)

    # Then actually train the model.
    should_score = True
    if should_score:
        scores = cross_val_score(RandomForestClassifier(max_depth=4, random_state=0), training_vectors, training_classes, cv=10)
        logging.getLogger(__name__).info("Accuracy: %0.2f (+/- %0.2f) N=%0.2f" % (scores.mean(), scores.std() * 2, len(training_vectors)/10))

    model = RandomForestClassifier(max_depth=4, random_state=0)
    model.fit(training_vectors, training_classes)

    def _classify(text:bytes) -> bool:
        v = _create_feature_vector(text)
        return True if v[2] < v[3] else False
        # return True if "T1" == model.predict([v])[0] else False # TODO: This is very overfit right now.  Would likely be better when we get a more realistic training set. (false positives etc.)

    return _classify


# This is a WIP as part of creating a generalized classifier, that attempts to do the proper per language and service detection as well as relevent content extraction.
# This is less relevent if we decide to just treat everything as "raw text".
def _classify(text, name=None, service=None, language=None):
    targeted_content = []

    # First let's extract what metadata we can, as well as target our classification to important bits (code)
    if is_markdown(text, name):
        # Try to extract code blocks.
        seen_blocks = set()
        for known_language, md_language in {Language.python : "python", \
                                        Language.java : "java", \
                                        Language.js : "js", \
                                        Language.dotnet : "csharp"}:
            blocks = exdown.from_buffer(io.StringIO(text), syntax_filter=md_language)
            for block in blocks:
                if block not in seen_blocks:
                    targeted_content.append((block, known_language, service))
                    seen_blocks.add(block)
        # Make sure we get untagged blocks too.
        blocks = exdown.from_buffer(io.StringIO(text))
        for block in blocks:
            if block not in seen_blocks:
                targeted_content.append((block, language, service))
                seen_blocks.add(block)
        # If none, or if code blocks don't do anything, fall back to treating whole thing as text.  TODO: May want to refine this (e.g. don't run code-specific models on non-code)
        if not seen_blocks:
            targeted_content.append((text, language, service))

    # Treat as code as long as it's one of the languages we expect to deal with
    elif is_code(text, name):
        targeted_content.append((text, language or is_code(text, name), service))

    # We also want to handle yaml, but we don't do anything special with that.
    elif is_yaml(text, name):
        targeted_content.append((text, language, service)) #TODO: Might want to do something custom for yaml in the future.
    
    # otherwise short circuit out. ( e.g. json, etc)
    else:
        # Maybe should treat it as raw text, parse whole thing?
        pass

    # If sdk/language aren't specified, try to determine them.
    # If we know what they are with high confidence, use the targeted model, otherwise use a generic model. (Maybe run both anyhow and make sure they agree or mosaic)
