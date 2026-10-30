"""Full passport lifecycle against a DPP repository and registry.

Creates a test passport, validates it, saves it, reads it back, updates it, reads the
previous version, registers it, and finally deletes it from the repository.

Run it (services must be running, see the README):

    python examples/consumer_lifecycle.py

Set DPP_REPO_BASE_URL and DPP_REGISTRY_BASE_URL to use other services. The registry
record is not removed (the registry API has no delete), so use disposable services.
"""

import json
from datetime import UTC, datetime
from uuid import uuid4

from dpp_sdk import Dpp4FunJsonCodec, DppHeader, Granularity, validate_dpp4fun
from dpp_sdk.clients import (
    DppRegistryClient,
    DppRepoClient,
    DppRepresentation,
    RegisterDppRequest,
)
from dpp_sdk.dpp4fun import ChairCharacteristics, Dpp4Fun, Nameplate


def run_consumer_workflow(repository_url: str, registry_url: str) -> dict[str, object]:
    token = uuid4().hex
    passport = Dpp4Fun.create(
        DppHeader(
            digital_product_passport_id=f"urn:example:dpp:{token}",
            unique_product_identifier=f"urn:example:product:{token}",
            granularity=Granularity.ITEM,
            last_updated=datetime.now(UTC),
            dpp_status="active",
            economic_operator_id="urn:example:operator:demo",
        ),
        Nameplate.create(manufacturerName="Example Furniture"),
        ChairCharacteristics.create(color="blue"),
    )

    report = validate_dpp4fun(passport)
    if not report.is_valid:
        raise ValueError(report.issues)

    codec = Dpp4FunJsonCodec()
    full_json = codec.to_json(passport)
    compressed_json = codec.to_compressed_json(passport)
    passport_id = passport.header.digital_product_passport_id
    if passport_id is None:
        raise ValueError("the test passport requires a DPP identifier")

    repository_created = False
    result: dict[str, object] = {}
    with DppRepoClient(repository_url) as repository, DppRegistryClient(registry_url) as registry:
        try:
            created = repository.create_dpp(json.loads(full_json), DppRepresentation.FULL)
            repository_created = True
            passport_id = created.digital_product_passport_id or passport_id

            full_response = repository.read_dpp_by_id(passport_id, DppRepresentation.FULL)
            stored = codec.from_json_and_validate(json.dumps(full_response.payload))
            history_at = datetime.now(UTC)

            nameplate = stored.typed_aspect(Nameplate)
            if nameplate is None:
                raise ValueError("the stored passport has no nameplate aspect")
            updated = stored.with_updates(
                header=stored.header.with_updates(last_updated=datetime.now(UTC)),
                aspects=(nameplate.with_field("manufacturerName", "Example Furniture Ltd."),),
            )
            updated_report = validate_dpp4fun(updated)
            if not updated_report.is_valid:
                raise ValueError(updated_report.issues)

            updated_full = json.loads(codec.to_json(updated))
            repository.update_dpp_by_id(
                passport_id,
                {"elements": updated_full["elements"]},
                DppRepresentation.FULL,
            )

            verified_response = repository.read_dpp_by_id(passport_id, DppRepresentation.FULL)
            verified = codec.from_json_and_validate(json.dumps(verified_response.payload))

            history_response = repository.read_dpp_version_by_id_and_date(
                passport_id, history_at, DppRepresentation.FULL
            )
            historical = codec.from_json_and_validate(json.dumps(history_response.payload))
            historical_nameplate = historical.typed_aspect(Nameplate)
            if (
                historical_nameplate is None
                or historical_nameplate.field("manufacturerName").value != "Example Furniture"
            ):
                raise ValueError("the historical read did not return the original version")

            registration = registry.post_new_dpp_to_registry(
                RegisterDppRequest(
                    unique_product_identifier=verified.header.unique_product_identifier,
                    digital_product_passport_id=passport_id,
                    unique_economic_operator_identifier=verified.header.economic_operator_id,
                    dpp_api_endpoint=f"{repository_url}/v1/dpps",
                )
            )
            result |= {
                "passport_id": passport_id,
                "full_json": full_json,
                "compressed_json": compressed_json,
                "updated_manufacturer": verified.typed_aspect(Nameplate)
                .field("manufacturerName")
                .value,
                "historical_passport": historical,
                "registration_id": registration.registration_id,
            }
        finally:
            if repository_created:
                deleted = repository.delete_dpp_by_id(passport_id)
                result["repository_cleanup_status"] = deleted.status_code

    return result


if __name__ == "__main__":
    import os

    outcome = run_consumer_workflow(
        os.environ.get("DPP_REPO_BASE_URL", "http://localhost:8080"),
        os.environ.get("DPP_REGISTRY_BASE_URL", "http://localhost:8081"),
    )
    print("Passport:", outcome["passport_id"])
    print("Updated manufacturer:", outcome["updated_manufacturer"])
    print("Registration:", outcome["registration_id"])
    print("Repository cleanup:", outcome["repository_cleanup_status"])
