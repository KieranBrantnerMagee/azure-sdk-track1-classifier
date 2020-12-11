import os

from azureSDKTrackClassifier import AzureSDKTrackClassifier, Language

# TODO: stop using this sample as a playground and clean it up.
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    #is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "Storage")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, "Storage")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "ServiceBus")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, "ServiceBus")
    is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "EventHubs")
    is_t1_classifier.save()
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, "EventHubs")
    is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, None)
    #is_t1_classifier = AzureSDKTrackClassifier(Language.js, None)
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, None)
    #is_t1_classifier = AzureSDKTrackClassifier(None, None)
    is_t1_classifier.save()

    #is_t1_classifier = AzureSDKTrackClassifier.load('azureSDKTrackClassifier_None_None.model')

    language = Language.java
    #language = Language.dotnet
    #service = 'ServiceBus' # Thus far have ServiceBus, Storage, EventHubs for Java and Dotnet
    #service = 'Storage'
    service = 'EventHubs'
    

    for tier in ['T1', 'T2']:
        t1_folder = './TestCorpus/{}/{}/{}'.format(language.value, service, tier)
        for subdir, dirs, files in os.walk(t1_folder):
            for file in files:
                full_file_path = os.path.join(t1_folder, file)
                with open(full_file_path) as f:
                    is_t1 = is_t1_classifier.is_t1_verbose(f.read(), True)['result']
                    print("{}: {}\t({})\n".format(tier, "Correct" if( (is_t1 and tier == 'T1') or (not is_t1 and tier == 'T2')) else "Incorrect", full_file_path))

    exit()
