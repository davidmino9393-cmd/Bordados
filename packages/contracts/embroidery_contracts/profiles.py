"""Configured profile catalogue, independent of worker/physical calibration."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import ContractModel, Identifier, NonEmpty, PositiveMM, Versioned

ColorLimit = Annotated[int, Field(ge=1, le=256)]


class MachineProfile(ContractModel):
    profile_id: Identifier
    profile_version: Identifier
    label: NonEmpty
    hoop_profile_ids: tuple[Identifier, ...]
    max_colors: ColorLimit
    calibration_status: Literal["proposed", "physically_calibrated"]
    calibration_record_id: Identifier | None = None

    @model_validator(mode="after")
    def calibrated_evidence(self):
        if self.calibration_status == "physically_calibrated" and self.calibration_record_id is None:
            raise ValueError("A calibrated machine profile needs physical evidence")
        return self


class HoopProfile(ContractModel):
    profile_id: Identifier
    profile_version: Identifier
    label: NonEmpty
    width_mm: PositiveMM
    height_mm: PositiveMM
    jef_hoop_code: Annotated[int, Field(ge=0)]


class FabricProfile(ContractModel):
    profile_id: Identifier
    profile_version: Identifier
    label: NonEmpty
    calibration_status: Literal["proposed", "physically_calibrated"]
    calibration_record_id: Identifier | None = None

    @model_validator(mode="after")
    def calibrated_evidence(self):
        if self.calibration_status == "physically_calibrated" and self.calibration_record_id is None:
            raise ValueError("A calibrated fabric profile needs physical evidence")
        return self


class ProviderAvailability(ContractModel):
    provider_id: Literal["openai", "ollama"]
    available: bool
    unavailable_reason: NonEmpty | None = None

    @model_validator(mode="after")
    def availability_reason(self):
        if not self.available and self.unavailable_reason is None:
            raise ValueError("Unavailable providers require a reason")
        if self.available and self.unavailable_reason is not None:
            raise ValueError("Available providers cannot have an unavailable reason")
        return self


class ThreadProfile(ContractModel):
    profile_id: Identifier
    profile_version: Identifier
    label: NonEmpty


class UploadLimits(ContractModel):
    max_bytes: Annotated[int, Field(gt=0)]
    max_decoded_pixels: Annotated[int, Field(gt=0)]
    accepted_mime_types: tuple[Literal["image/png", "image/jpeg", "image/svg+xml"], ...]


class ProfileCatalog(Versioned):
    catalog_version: Identifier
    machines: tuple[MachineProfile, ...]
    hoops: tuple[HoopProfile, ...]
    fabrics: tuple[FabricProfile, ...]
    thread_profiles: tuple[ThreadProfile, ...]
    max_colors: ColorLimit
    providers: tuple[ProviderAvailability, ...]
    upload_limits: UploadLimits

    @model_validator(mode="after")
    def consistent_references(self):
        for collection in (self.machines, self.hoops, self.fabrics, self.thread_profiles):
            ids = [item.profile_id for item in collection]
            if len(set(ids)) != len(ids):
                raise ValueError("Profile identifiers must be unique within each catalogue family")
        hoop_ids = {hoop.profile_id for hoop in self.hoops}
        if any(not set(machine.hoop_profile_ids).issubset(hoop_ids) or machine.max_colors > self.max_colors for machine in self.machines):
            raise ValueError("Machine compatibility references and color limits must match catalogue")
        if len({item.provider_id for item in self.providers}) != len(self.providers):
            raise ValueError("Provider entries must be unique")
        return self
