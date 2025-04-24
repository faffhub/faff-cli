import pendulum
import tomli_w


from typing import Any


class TomlSerializer:

    @classmethod
    def serialize(cls, obj: Any) -> str:
        """
        Serializes a dataclass to a TOML string.
        This function handles nested dataclasses, lists, and dictionaries, and smells _ghastly_.
        XXX: Don't think about putting me in models.py though - models shouldn't worry about their
        representation as anything other than a pure dict.
        """
        from dataclasses import asdict

        def serialize_value(value):
            if isinstance(value, pendulum.DateTime):
                return value.to_iso8601_string()
            elif isinstance(value, pendulum.Date):
                return value.to_date_string()
            elif isinstance(value, dict):
                return {k: serialize_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [serialize_value(v) for v in value]
            else:
                return value

        def remove_none(obj):
            if isinstance(obj, dict):
                return {k: remove_none(v) for k, v in obj.items() if v is not None}
            elif isinstance(obj, list):
                return [remove_none(v) for v in obj]
            else:
                return obj

        # If obj is a dataclass, convert it to a dict
        if hasattr(obj, "__dataclass_fields__"):
            obj = asdict(obj)

        return tomli_w.dumps(
            remove_none(
                {k: serialize_value(v) for k, v in obj.items()}))