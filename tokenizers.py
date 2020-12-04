from helpers import *
from constants import Language

def tokenize_apistubgen(stub_json):
    # Ingest top level types.  May duplicate lower data, but is much more to-the-point.
    found_types = defaultdict(set)
    def _ingest_subtree(root):
        try:
            type_kind = root["Tags"]["TypeKind"] # Can be one of: enum, class, namespace, assembly, method
        except:
            type_kind = None
        found_types[type_kind].add(root["Text"]) # Note: may be worth looking at NavigationId as well in the future.
        for child in root["ChildItems"]:
            _ingest_subtree(child)

    _ingest_subtree(stub_json["Navigation"])

    # Now process the tree we just ingested.
    
    # Notes to self for parsing apistubgen:
    #
    # 0 -> "cancellationToken" in Value and all else None | (Parameter name?)
    # 0 -> DefinitionId and Value defined, as a module (Messaging) fully defined in #5 | (Module name?)
    # 0 -> DefinitionId and value defined, as an Enum constant name, where the definition is the enum constant path
    # 0 -> definitionId and value are the same, the enum path itself.
    #
    # 5 -> DefinitionId defined and value is an empty string -> enum option or enum itself? (e.g. ServiceBusSubQueue.Dead_Letter which has an accompanying non-null-value 0, same thing for ServiceBusSubQueue itself)
    # 5 -> Only DefinitionId defined (full function), all else None -> class method?  (e.g. ServiceBusClient.DisposeAsync() or ServiceBus.ServiceBusClient) | (Is this the actual long-form method/class/module itself?)
    # (Note, 5's have parens and param list in def. id if function, otherwise not.)
    #
    # 6 -> only value defined -> Type (e.g. CancellationToken, ValueTask)
    # 6 -> Both Value and DefinitionId defined -> Internal Type (e.g. ServiceBusClient, where the root definition is in a #5)
    # 6 -> NavigationId has full reference to a type, value is the text of that typename -> Internal type? (e.g. ServiceBusProcessor) | (It's either a return or parameter type, depending on placement?)
    #
    # 7 -> DefinitionId and Value defined (definitionID is full function and value is method name) -> method name. | (Is this the token of the methodname itself? also the property name for setters/getters?  refers to a #5.)
    # 7 -> Value defined and nothing else -> Weird dotnet keyword thing? (Never)
    #
    # Oddities:
    # - In dotnet, methods are 7s.  In python, they're 0s.
    # - Python has a 5 AND a 0 for each param.
    # - sometimes in python, 0s are whitespace.
    #
    # Broad conclusions:
    #
    # - Capture 0, 6, 7, and 8 "value" fields.  (these are the actual meaningful public tokens for a lib; classes, methods, parameters, constants.)
    #    - Always remember to trim and check the value for non-null.
    # - Don't capture 5s, they _could_ be useful, but are usually too verbose and are captured by 6/7/0.
    # - Don't capture 1-2, useful for advanced parsing but not as tokens.
    # - Don't capture 3-4 UNLESS doing language detection.
    # - Don't capture 9, it's just comments, numerals, Nones, and "..." placeholder strings.
    #
    # (if doing N-grams this changes a bit, but not too much.)

    class Kind(int, Enum):
        child_token = 0 # A bunch of things; parameter or module name or enum path. (or in python a method as well).  Always seems to be 'a token underneath a thing', thus child_token.
        null = 1 # Newline/"break"?
        whitespace = 2
        punctuation = 3
        keyword = 4 # e.g. class, or get, or public, etc.
        definition = 5 # This one's a bit weird, it kinda represents the "root reference" for top level stuff, methods, classes, modules.  Only DefinitionID is populated, with a fully qualified reference.
        type = 6 # both internal (e.g. ServiceBusClient), with associated NavigationId, or external (e.g. CancellationToken)
        property = 7 # A method is also a property, and is the most common type in some languages (dotnet).  Other languages have methods as 0s. (python)
        constant = 8 # e.g. \"Restoring\"
        comment=9 # Can also be e.g. "..." or certain constants e.g. numerals and Nones, in either case, ignore.


    for token in stub_json["Tokens"]:
        kind = Kind(token["Kind"]) # int
        value = token["Value"] # str
        definition_id = token.get("DefinitionId") # str
        navigate_to_id = token.get("NavigateToId") # str
        if kind in [Kind.child_token, Kind.type, Kind.property, Kind.constant] and value and value.strip():
            found_types[kind.name].add(value.strip())

    # This is an option if we find these are present. (e.g. azc0015) but they don't seem to be.
    #
    # for token in stub_json["Diagnostics"]:
    #     id = token["DiagnosticId"]
    #     found_types["DiagnosticId"].add(id)

    return found_types


tokenizer = WordPunctTokenizer() # NOTE: This is somewhat arbitrary outside it being convenient and giving acceptable punctuation handling for our needs.
def tokenize_text(text:str) -> set:
    return set(tokenizer.tokenize(text)) # Contemplated things like occurence filtering and the like, but this "seems workable" for the time being, if we added that we should go all the way to feature vectors and a full classifier.

