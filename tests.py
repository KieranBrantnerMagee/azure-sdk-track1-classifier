from AzureSDKTrackClassifierV2 import AzureSDKTrack1Classifier, Language

# This is a terrible imitation of an actual tests file, but marginally better than not having one at all.  TODO: add more as the core API stabilizes.
def test_classifier_e2e():
    is_t1_classifier = AzureSDKTrack1Classifier(Language.dotnet, "EventHubs")
    with open('./TestCorpus/EventHubs/T1/test_t1_eh.txt', 'r') as f:
        assert is_t1_classifier.is_t1(f.read())
    with open('./TestCorpus/EventHubs/T2/test_t2_eh.txt', 'r') as f:
        assert not is_t1_classifier.is_t1(f.read())