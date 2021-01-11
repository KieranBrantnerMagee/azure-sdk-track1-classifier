import io

from azureSDKTrackClassifier.constants import Language
from azureSDKTrackClassifier.helpers import is_markdown, is_code, is_yaml

import exdown

def extract_and_label_codefences(text:str, service:str=None, language:str=None):
    targeted_content = []
    seen_blocks = set()
    for known_language, md_language in {Language.python : "python", \
                                        Language.java : "java", \
                                        Language.js : "js", \
                                        Language.dotnet : "csharp"}.items(): #TODO: If you end up using this long-term, make this mapping a constant and tie it into the new-language-validation in the constants file.
        blocks = exdown.from_buffer(io.StringIO(text), syntax_filter=md_language)
        for block in blocks:
            if block not in seen_blocks:
                targeted_content.append((block[0], known_language, service))
                seen_blocks.add(block)
    # Make sure we get untagged blocks too.
    blocks = exdown.from_buffer(io.StringIO(text))
    for block in blocks:
        if block not in seen_blocks:
            targeted_content.append((block[0], language, service))
            seen_blocks.add(block)
    return targeted_content

# NOTE: This is a WIP as part of creating a generalized classifier, that attempts to do the proper per language and service detection as well as relevent content extraction.
# This is less relevent if we decide to just treat everything as "raw text", or if we end up having no need for a layered/mosaic model.
def _classify(text:str, name:str=None, service:str=None, language:Language=None):
    """Takes the input text (and optional filename) and makes a best effort to extract/label the code content needed for classification.  
       E.g. a markdown file has codeblocks extracted and labeled with language, and a code file is extracted in its entirety and labeled accordingly."""
    targeted_content = []

    # First let's extract what metadata we can, as well as target our classification to important bits (code)
    if is_markdown(text, name):
        # Try to extract code blocks.
        targeted_content += _extract_and_label_codefences(text)
        #  TODO: May want to refine this (e.g. don't run code-specific models on non-code)
        #  If none, or if code blocks don't do anything, fall back to treating whole thing as text.
        # if not targeted_content:
        #     targeted_content.append((text, language, service))

    # Treat as code as long as it's one of the languages we expect to deal with
    elif is_code(text, name):
        targeted_content.append((text, language or is_code(text, name), service))

    # We also want to handle yaml, but we don't do anything special with that.
    elif is_yaml(text, name):
        targeted_content.append((text, language, service)) #TODO: Might want to do something custom for yaml in the future.
    
    # otherwise short circuit out. ( e.g. json, etc)
    else:
        # Maybe should treat it as raw text, parse whole thing?
        # TODO: figure this out.
        targeted_content.append((text, language, service))

    # TODO: If sdk/language aren't specified, try to determine them.
    # If we know what they are with high confidence, use the targeted model, otherwise use a generic model. (Maybe run both anyhow and make sure they agree or mosaic)

    return targeted_content
