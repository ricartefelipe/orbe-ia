"""Expected failures of the reading desk."""


class OrbeError(Exception):
    """Failure the desk can explain to the caller."""


class MissingOpenAIKey(OrbeError):
    """The operation needs the OpenAI key and none is configured."""


class UnreadableDossier(OrbeError):
    """The upload cannot be indexed."""


class InvalidQuestion(OrbeError):
    """The question cannot be sent to the desk."""


class ModelCallFailed(OrbeError):
    """The model did not return a usable answer."""
