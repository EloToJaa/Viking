from pydantic import ConfigDict, JsonValue, RootModel


class VikingResponse(RootModel[JsonValue]):
    """Validated JSON returned by a Viking API endpoint."""

    model_config = ConfigDict(strict=True)
