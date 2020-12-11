from azureSDKTrackClassifier import AzureSDKTrackClassifier, Language

is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet)

with open('./TestCorpus/dotnet/EventHubs/T1/test_t1_eh.txt', 'r') as f:
    print("Should be T1: {}".format(is_t1_classifier.is_t1_verbose(f.read())))
with open('./TestCorpus/dotnet/EventHubs/T2/test_t2_eh.txt', 'r') as f:
    print("Should not be T1: {}".format(is_t1_classifier.is_t1_verbose(f.read())))