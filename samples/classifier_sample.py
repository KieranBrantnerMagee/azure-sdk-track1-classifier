from azureSDKTrackClassifier import AzureSDKTrackClassifier, Language

# TODO: stop using this sample as a playground and clean it up.
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    #is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "Storage")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, "Storage")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "ServiceBus")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, "ServiceBus")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, "EventHubs")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.java, "EventHubs")
    #is_t1_classifier = AzureSDKTrackClassifier(Language.dotnet, None)
    #is_t1_classifier = AzureSDKTrackClassifier(Language.js, None)
    is_t1_classifier = AzureSDKTrackClassifier(None, None)

    #path = is_t1_classifier.save()
    #is_t1_classifier = AzureSDKTrackClassifier.load(path)

    #TODO: Restructure test folder to be <language>/<service>/<tier>/<arbitrary_filename> and make this automagic now that we have too many.
    
    #with open('./TestCorpus/EventHubs/T1/test_t1_eh.txt', 'r') as f:
    #with open('./TestCorpus/ServiceBus/T1/test_t1_sb.txt', 'r') as f:
    #with open('./TestCorpus/Storage/T1/test_t1_blob.txt', 'r') as f:
    with open('./TestCorpus/Storage/T1/java_t1_blob.txt', 'r') as f:
    #with open('./TestCorpus/ServiceBus/T1/java_t1_sb.txt', 'r') as f:
    #with open('./TestCorpus/EventHubs/T1/java_t1_eh.txt', 'r') as f:
        print("Should be T1: {}".format(is_t1_classifier.is_t1_verbose(f.read())))
    #with open('./TestCorpus/EventHubs/T2/test_t2_eh.txt', 'r') as f:
    #with open('./TestCorpus/ServiceBus/T2/test_t2_sb.txt', 'r') as f:
    #with open('./TestCorpus/Storage/T2/test_t2_blob.txt', 'r') as f:
    with open('./TestCorpus/Storage/T2/java_t2_blob.txt', 'r') as f:
    #with open('./TestCorpus/ServiceBus/T2/java_t2_sb.txt', 'r') as f:
    #with open('./TestCorpus/EventHubs/T2/java_t2_eh.txt', 'r') as f:
        print("Should not be T1: {}".format(is_t1_classifier.is_t1_verbose(f.read())))

    # Keeping this around in case I need to get all corpuses for training the generalized model.
    #
    # for language in [Language.dotnet, Language.js, Language.java, Language.python]:
    #     try:
    #         info = get_release_metadata(language)
    #     except Exception as e:
    #         print(e)
    #     for packages_for_service in info.values():
    #         for each in packages_for_service:
    #             try:
    #                 print("Getting corpus for: " + str(language.value) + " : " + each['Package'])
    #                 get_corpus_for_package(language_repo_map[language], each['Package'], each['VersionGA'] or each['VersionPreview'], each['RepoPath'])
    #             except Exception as e:
    #                 print(e)

    exit()
