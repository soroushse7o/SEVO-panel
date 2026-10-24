"""
Pydantic models for request/response validation.
Replaces ad-hoc dict handling with type-safe contracts.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re
import uuid as uuid_lib


class LinkCreate(BaseModel):
    label: str = Field(default="This Server is Free", max_length=60)
    uuid: Optional[str] = None
    limit_value: float = 0
    limit_unit: str = "GB"
    max_connections: int = 0
    days_valid: int = 0
    custom_path: str = ""
    custom_sni: str = ""
    custom_host: str = ""
    custom_fp: str = "chrome"
    color: str = "#39ff14"
    flag: str = ""
    fragment: str = ""

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Remark is required")
        if not re.match(r"^[a-zA-Z0-9\-_. ]+$", v):
            raise ValueError("Label must contain only English letters, numbers, and: - _ . space")
        return v[:60]

    @field_validator("uuid")
    @classmethod
    def validate_uuid(cls, v: Optional[str]) -> Optional[str]:
        if v:
            try:
                uuid_lib.UUID(v)
            except ValueError:
                raise ValueError("Invalid UUID format")
        return v

    @field_validator("flag")
    @classmethod
    def validate_flag(cls, v: str) -> str:
        v = v.strip()[:2].upper()
        if v and not re.match(r"^[A-Z]{2}$", v):
            return ""
        return v


class LinkUpdate(BaseModel):
    active: Optional[bool] = None
    limit_value: Optional[float] = None
    limit_unit: Optional[str] = None
    reset_usage: bool = False
    label: Optional[str] = None
    max_connections: Optional[int] = None
    days_valid: Optional[int] = None
    custom_path: Optional[str] = None
    custom_sni: Optional[str] = None
    custom_host: Optional[str] = None
    custom_fp: Optional[str] = None
    color: Optional[str] = None
    flag: Optional[str] = None
    fragment: Optional[str] = None


class AddressCreate(BaseModel):
    address: str

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Address is required")
        import ipaddress
        try:
            ipaddress.ip_address(v.strip("[]"))
            return v
        except ValueError:
            pass
        try:
            ipaddress.ip_network(v.strip("[]"), strict=False)
            return v
        except ValueError:
            pass
        if not re.match(r"^[a-zA-Z0-9\-_.%:]+$", v):
            raise ValueError("Invalid address format")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v) or not re.search(r"[a-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("Password must contain uppercase, lowercase, and digit")
        return v


class BatchActionRequest(BaseModel):
    uids: list[str]
    action: str


class TelegramSettings(BaseModel):
    tg_bot_token: str = ""
    tg_chat_id: str = ""
    telegram_interval: str = "1"
    telegram_events: str = ""
    telegram_templates_en: str = ""
    telegram_templates_fa: str = ""
    telegram_lang: str = "en"
