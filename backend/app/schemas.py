from datetime import datetime
from typing import Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

SECRET_WORDS = {
    "password",
    "senha",
    "token",
    "secret",
    "segredo",
    "authorization",
    "credential",
    "api_key",
}


def safe_key(value: str) -> str:
    if any(word in value.lower() for word in SECRET_WORDS):
        raise ValueError(
            "Campos de senha, token ou segredo não são aceitos; use credenciais externas."
        )
    return value


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(Input):
    username: str = Field(min_length=1, max_length=120)
    password: SecretStr


class UserInput(Input):
    username: str = Field(min_length=3, max_length=120, pattern=r"^[a-zA-Z0-9._@-]+$")
    password: SecretStr = Field(min_length=12, max_length=128)
    role: Literal["admin", "operator"] = "operator"


class PlatformConfig(Input):
    simulate_failure: bool = False


class FieldInput(Input):
    key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=120)
    field_type: Literal["text", "email", "integer", "select"] = "text"
    required: bool = True
    options: list[str] = Field(default_factory=list, max_length=30)

    _safe_key = field_validator("key")(safe_key)

    @model_validator(mode="after")
    def valid_options(self):
        if self.field_type == "select" and not self.options:
            raise ValueError("Um campo de seleção precisa de opções.")
        if any(not option or len(option) > 120 for option in self.options):
            raise ValueError("Opções precisam ter entre 1 e 120 caracteres.")
        if len(set(self.options)) != len(self.options):
            raise ValueError("Opções repetidas.")
        return self


class PlatformInput(Input):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    active: bool = True
    mode: Literal["simulation", "power_automate", "local_browser", "local_desktop"] = "simulation"
    config: PlatformConfig = Field(default_factory=PlatformConfig)
    fields: list[FieldInput] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_fields(self):
        if len({field.key for field in self.fields}) != len(self.fields):
            raise ValueError("Chaves de campos devem ser únicas.")
        return self


class ScreenContext(Input):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0, le=16000)
    height: int = Field(gt=0, le=16000)
    window: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def inside_screen(self):
        if self.x >= self.width or self.y >= self.height:
            raise ValueError("O ponto precisa estar dentro da resolução.")
        return self


class StepInput(Input):
    action: Literal[
        "open_page",
        "locate",
        "fill",
        "click",
        "click_point",
        "assert",
        "click_image",
        "click_button",
        "assert_image",
        "wait_image",
        "if_exists",
        "pause",
    ]
    locator: str = Field(default="", max_length=500)
    value: str = Field(default="", max_length=500)
    data_ref: str = Field(default="", max_length=80)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    success_condition: str = Field(default="", max_length=500)
    screen_context: ScreenContext | None = None
    button_text: str = Field(default="", max_length=120)
    reference_image_id: str | None = None
    confidence: float = Field(default=0.9, ge=0.7, le=0.99)
    on_match: Literal["finish_success", "skip_next", "continue"] = "finish_success"
    skip_steps: int = Field(default=1, ge=1, le=50)

    @model_validator(mode="after")
    def validate_action(self):
        if self.action in {"locate", "click", "assert"} and not self.locator:
            raise ValueError("Esta ação exige um seletor.")
        if self.action == "fill" and (not self.data_ref or self.value):
            raise ValueError("Preenchimentos usam referências de dados, sem valores literais.")
        if self.action == "assert" and not self.success_condition:
            raise ValueError("Informe a condição de sucesso.")
        if self.action == "click_point" and self.screen_context is None:
            raise ValueError("Informe ponto, resolução e janela.")
        if (
            self.action in {"click_image", "assert_image", "wait_image"}
            and not self.reference_image_id
        ):
            raise ValueError("Envie uma imagem de referência do botão.")
        if self.action == "if_exists" and not (self.locator or self.reference_image_id):
            raise ValueError("A condição precisa de seletor ou imagem.")
        if self.action == "click_button" and not self.button_text:
            raise ValueError("Informe o nome acessível do botão.")
        if self.action == "open_page":
            url = urlsplit(self.value)
            if (
                url.scheme not in {"http", "https"}
                or not url.hostname
                or url.username
                or url.password
            ):
                raise ValueError("Informe uma URL HTTP sem credenciais.")
            for key, _ in parse_qsl(url.query):
                safe_key(key)
        return self


class AutomationInput(Input):
    name: str = Field(min_length=1, max_length=120)
    steps: list[StepInput] = Field(min_length=1, max_length=50)


class EmployeeInput(Input):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    department: str = Field(min_length=1, max_length=120)
    employee_id: str = Field(min_length=1, max_length=60)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str):
        return value.lower()


class TargetInput(Input):
    platform_id: str
    fields: dict[str, str | int] = Field(default_factory=dict, max_length=30)


class RequestInput(Input):
    employee: EmployeeInput
    targets: list[TargetInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_targets(self):
        if len({target.platform_id for target in self.targets}) != len(self.targets):
            raise ValueError("Plataformas repetidas na solicitação.")
        return self


class CallbackInput(Input):
    execution_id: str = Field(max_length=36)
    event_id: str = Field(min_length=1, max_length=120)
    external_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9._:-]+$")
    status: Literal["running", "succeeded", "failed"]
    step: int | None = Field(default=None, ge=1, le=50)
    result_code: (
        Literal["account_created", "already_exists", "destination_rejected", "execution_error"]
        | None
    ) = None


class RunInput(Input):
    employee: EmployeeInput | None = None
    fields: dict[str, str | int] = Field(default_factory=dict, max_length=30)


class StepTestInput(Input):
    step: StepInput
    start_url: str = Field(default="", max_length=500)
    preview_only: bool = True
    employee: EmployeeInput | None = None
    fields: dict[str, str | int] = Field(default_factory=dict, max_length=30)

    @field_validator("start_url")
    @classmethod
    def validate_start(cls, value):
        if value:
            StepInput(action="open_page", value=value)
        return value


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence: int
    step: int | None
    level: str
    message: str
    created_at: datetime


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserRead(Output):
    id: str
    username: str
    role: Literal["admin", "operator"]
    active: bool


class SessionRead(Output):
    user: UserRead
    csrf_token: str


class FieldRead(FieldInput):
    id: str
    position: int


class PlatformRead(Output):
    id: str
    name: str
    description: str
    active: bool
    mode: Literal["simulation", "local_browser", "local_desktop", "power_automate"]
    config: PlatformConfig
    created_at: datetime
    fields: list[FieldRead]


class StepRead(StepInput):
    position: int


class AutomationRead(Output):
    id: str
    platform_id: str
    name: str
    version: int
    status: Literal["draft", "validated", "archived"]
    created_at: datetime
    steps: list[StepRead]


class ValidationRead(Output):
    automation: AutomationRead
    warnings: list[str]


class ExecutionRead(Output):
    id: str
    request_id: str
    platform_id: str
    platform_name: str
    mode: str
    status: Literal["queued", "dispatching", "running", "succeeded", "failed", "cancelled"]
    attempts: int
    external_id: str | None
    result: dict
    error_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    can_retry: bool
    awaiting_operator: bool = False
    cancel_requested: bool = False


class StepTestRead(Output):
    id: str
    platform_id: str
    mode: str
    status: str
    preview_only: bool
    result: dict
    error_code: str | None
    created_at: datetime
    finished_at: datetime | None


class RequestRead(Output):
    id: str
    employee: EmployeeInput
    status: Literal["queued", "running", "succeeded", "partially_succeeded", "failed"]
    requested_by: str
    created_at: datetime
    executions: list[ExecutionRead]


class AuditRead(Output):
    id: str
    actor_id: str | None
    action: str
    resource_id: str
    details: dict
    created_at: datetime


class ImageRead(Output):
    id: str
    width: int
    height: int


class CallbackRead(Output):
    accepted: bool
    replayed: bool
