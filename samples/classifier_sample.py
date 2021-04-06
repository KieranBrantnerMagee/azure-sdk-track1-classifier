import glob
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
    os.environ["API_VIEW_API_KEY"]=''
    os.environ["API_VIEW_COSMOS_CONNECTION_STRING"]=''
    os.environ["API_VIEW_STORAGE_CONNECTION_STRING"]=''
    from azureSDKTrackClassifier.settings import Settings
    Settings.API_VIEW_GENERATION_URI = 'https://packageindexapiview.azurewebsites.net/AutoReview/UploadAutoReview?language=All&closed=false&automatic=true'
    is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "EventHubs")
    is_t1_classifier.save()
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, "EventHubs")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, None)
    #is_t1_classifier = AzureSDKTrackClassifier(Language.js, None)
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, None)
    #is_t1_classifier = AzureSDKTrackClassifier(None, None)
    #is_t1_classifier.save()
    exit()

    is_t1_classifier = AzureSDKTrackClassifier.load('azureSDKTrackClassifier_None_None.model')

    from azureSDKTrackClassifier.classifierV2 import _extract_and_label_codefences
    with open('./TestCorpus/uncategorized/dotnet_twilio_t2.txt') as f:
        raw_text = f.read()
        res = is_t1_classifier.is_t1_verbose(raw_text, True)
        print(res)
        print("=========================  CODEFENCE EXTRACTED =====================")
        targeted_content = _extract_and_label_codefences(raw_text, 'dotnet_twilio.md')
        text = '\n'.join([e[0] for e in targeted_content])
        res = is_t1_classifier.is_t1_verbose(text, True)
        print(res)
    exit()

    #language = Language.java
    #language = Language.dotnet

    #service = 'ServiceBus' # Thus far have ServiceBus, Storage, EventHubs for Java and Dotnet
    #service = 'Storage'
    #service = 'EventHubs'

    language = None # the language test file to run against, None for all.
    service = None # the service test file to run against, None for all.
    
    test_corpus_glob = './TestCorpus/*/*/*/*'
    for file_path in glob.glob(test_corpus_glob, recursive=True):
        path_base, path_language, path_service, path_tier, file_name = os.path.normpath(file_path).split(os.sep)
        if (language and language != Language(path_language)) or (service and service != path_service):
            continue
        with open(file_path) as f:
            is_t1 = is_t1_classifier.is_t1_verbose(f.read(), True)
            print("{}: {}\t({})".format(path_tier, "Correct" if( (is_t1['result'] and path_tier == 'T1') or (not is_t1['result'] and path_tier == 'T2')) else "Incorrect", file_path))
            print("\t{}: {}\t({})\n".format(path_tier, "ML:  " + ("Correct" if( (is_t1['ml_result'] and path_tier == 'T1') or (not is_t1['ml_result'] and path_tier == 'T2')) else "Incorrect") + " " + str(is_t1['ml_result_probability']), file_path))

    exit()
