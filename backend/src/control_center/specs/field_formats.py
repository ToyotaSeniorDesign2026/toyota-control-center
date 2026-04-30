from __future__ import annotations

from typing import Any, Annotated
from pydantic import Field
from datetime import date, timedelta
from uuid import UUID
from pydantic import (
    AnyUrl,
    AwareDatetime,
    ByteSize,
    EmailStr,
    JsonValue,
    Secret,
    SecretBytes,
    SecretStr,
)


__all__ = ["FORMAT_REGISTRY"]

CronStr = Annotated[str, Field(pattern=r"^(@(daily|hourly|weekly|monthly|yearly|reboot)|(\S+\s+){4}\S+)$")]
FORMAT_REGISTRY: dict[str, Any] = {
    "email": EmailStr,
    "cron": CronStr,
    "uri": AnyUrl,
    "datetime": AwareDatetime,
    "date": date,
    "duration": timedelta,
    "bytesize": ByteSize,
    "json": JsonValue,
    "secret": Secret,
    "secret_string": SecretStr,
    "secret_bytes": SecretBytes,
}
