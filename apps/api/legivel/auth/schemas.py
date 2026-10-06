import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field

RoleName = Literal["admin", "reviewer", "reader"]
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def check_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.match(email):
        raise ValueError("e-mail inválido")
    return email


EmailAddress = Annotated[str, AfterValidator(check_email)]


class LoginIn(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=256)


class TwoFactorIn(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class SetupIn(BaseModel):
    email: EmailAddress
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: RoleName
    permissions: list[str]
    email_verified: bool
    pending_email: str | None
    two_factor_enabled: bool


class LoginOut(BaseModel):
    status: Literal["ok", "two_factor"]
    user: UserOut | None = None


class ForgotIn(BaseModel):
    email: EmailAddress


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=256)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class InvitationPreview(BaseModel):
    email: str
    role: RoleName
    expires_at: datetime


class AcceptInviteIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class EmailChangeIn(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=256)


class DeliveryOut(BaseModel):
    emailed: bool
    link: str | None = None
    detail: str


class TwoFactorSetupOut(BaseModel):
    secret: str
    uri: str
    qr_svg: str


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]


class PasswordIn(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class SessionOut(BaseModel):
    id: int
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class AccountOut(BaseModel):
    id: int
    email: str
    name: str
    role: RoleName
    is_active: bool
    email_verified: bool
    two_factor_enabled: bool
    locked: bool
    last_login_at: datetime | None
    created_at: datetime
    sessions: int


class AccountUpdateIn(BaseModel):
    role: RoleName | None = None
    is_active: bool | None = None
    unlock: bool = False


class InvitationIn(BaseModel):
    email: EmailAddress
    role: RoleName = "reader"


class InvitationOut(BaseModel):
    id: int
    email: str
    role: RoleName
    state: str
    created_at: datetime
    expires_at: datetime
    invited_by: str | None


class InvitationCreated(DeliveryOut):
    invitation: InvitationOut
