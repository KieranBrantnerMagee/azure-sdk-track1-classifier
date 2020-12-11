import unittest

from azureSDKTrackClassifier import AzureSDKTrackClassifier, Language

# This is a terrible imitation of an actual tests file, but marginally better than not having one at all.  TODO: add more as the core API stabilizes.
class TestClassifier(unittest.TestCase):
    def test_classifier_e2e(self):
        is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "EventHubs")
        with open('./TestCorpus/dotnet/EventHubs/T1/test_t1_eh.txt', 'r') as f:
            assert is_t1_classifier.is_t1(f.read())
        with open('./TestCorpus/dotnet/EventHubs/T2/test_t2_eh.txt', 'r') as f:
            assert not is_t1_classifier.is_t1_verbose(f.read())['result']

if __name__ == '__main__':
    unittest.main()
