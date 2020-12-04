from enum import Enum
from model import train_classifier
from constants import Language

class AzureSDKTrack1Classifier: # Someone with more sense than me can rename this to just Track1Classifier or something.
    def __init__(self, language : Language, service : str):
        self._classifier = train_classifier(language, service)

    def is_t1(self, text:str):
        return self._classifier(text)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    #is_t1_classifier = AzureSDKTrack1Classifier(Language.dotnet, "ServiceBus")
    is_t1_classifier = AzureSDKTrack1Classifier(Language.dotnet, "EventHubs")
    with open('./TestCorpus/EventHubs/T1/test_t1_eh.txt', 'r') as f:
        print("SHOULD BE T1")
        print(is_t1_classifier.is_t1(f.read()))
    with open('./TestCorpus/EventHubs/T2/test_t2_eh.txt', 'r') as f:
        print("SHOULD BE NOT T1")
        print(is_t1_classifier.is_t1(f.read()))
    #is_t1_classifier = AzureSDKTrack1Classifier(Language.dotnet, "Storage")

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

