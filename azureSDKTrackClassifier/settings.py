
# Distinct from constants as we modify them at runtime.
class Settings:
    # Used for identifying where to store cache files during training.  (Technically not truly constant, since set as a command line arg, but then is constant after-the-fact.)
    CACHE_BASE_PATH="Z:\\scratch\\" # "." #TODO: Swap this back in.

    # Determines where cache, test, and apistubgen files are looked for and stored.
    TEST_CORPUS_BASE_PATH = "."

    # If specified, logs missing unsupervised training corpus zips not able to be fetched from the authoritative release-version lists in helpers.
    MISSING_TRAINING_LOG = None