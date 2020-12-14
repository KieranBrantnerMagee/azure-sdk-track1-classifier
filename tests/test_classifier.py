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

    def test_classifier_save_load(self):
        is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "EventHubs")
        path = is_t1_classifier.save()
        is_t1_classifier = AzureSDKTrackClassifier.load(path)
        is_t1_classifier.is_t1('test')

from azureSDKTrackClassifier.helpers import get_apistubgen_tokens_for_package

class TestTokenizer(unittest.TestCase):
    def test_apistubgen_tokenizer(self):
        assert get_apistubgen_tokens_for_package('dotnet', 'Azure.Messaging.ServiceBus', '7.0.0')
        assert get_apistubgen_tokens_for_package('python', 'azure-servicebus', '7.0.0')

if __name__ == '__main__':
    unittest.main()
