from enum import Enum

class Language(str, Enum):
    dotnet="dotnet"
    # TODO: Enable these as they are tested.
    python = "python"
    java = "java"
    js = "js"

LANGUAGE_REPO_MAP = {Language.dotnet:'azure-sdk-for-net', Language.js:'azure-sdk-for-js', Language.java:'azure-sdk-for-java', Language.python:'azure-sdk-for-python'}