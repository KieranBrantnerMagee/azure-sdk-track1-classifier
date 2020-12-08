from enum import Enum

# Note: if adding a new language, remember to add a corrosponding entry to the LANGUAGE_REPO_MAP.
# TODO: If feeling motivated, add an automatic check that the two are in parity at import-time. (e.g. at the bottom of this file.)
class Language(str, Enum):
    dotnet = "dotnet"
    python = "python"
    java = "java"
    js = "js"

LANGUAGE_REPO_MAP = {Language.dotnet:'azure-sdk-for-net', Language.js:'azure-sdk-for-js', Language.java:'azure-sdk-for-java', Language.python:'azure-sdk-for-python'}