from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, alias_generator=to_camel
    )

    def model_dump(self, **kwargs):
        """Use Pydantic's built-in serialization with camelCase keys."""
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)
