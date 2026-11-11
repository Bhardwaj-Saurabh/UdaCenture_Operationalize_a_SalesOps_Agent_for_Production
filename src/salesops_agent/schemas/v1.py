"""Version 1 of the tool input schemas."""

from pydantic import BaseModel

SCHEMA_VERSION = "v1"


class AccountLookupInput(BaseModel):
    account_name_or_id: str


class ListOpenOpportunitiesInput(BaseModel):
    stage: str | None = None


class SummarizePipelineInput(BaseModel):
    pass


class InternalDataInput(BaseModel):
    query: str


class DraftEmailInput(BaseModel):
    account_name_or_id: str
    purpose: str


class CrmAnalysisInput(BaseModel):
    code: str


class SendEmailInput(BaseModel):
    to: str
    subject: str
    body: str
