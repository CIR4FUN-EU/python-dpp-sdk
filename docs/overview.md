# SDK overview

## Purpose and scope

`dpp-sdk` is a reusable Python client library for DPP models, semantic validation, DPP4Fun JSON,
and synchronous repository and registry clients. It does not implement services, persistence,
Docker, Spring, or internal Java routes.

## Architecture and package boundaries

![Python SDK package boundaries](architecture/python-sdk-overview.svg)

*Diagram: applications use reusable core models directly or use the furniture aggregate. Generic
clients are independent of either model package; the optional Java-services demo consumes the
installed SDK rather than becoming part of it.*

`dpp_sdk.core` owns reusable immutable models, structural constraints, and core semantic
validation. `dpp_sdk.dpp4fun` builds on core and owns the furniture aggregate, its semantic
validation, and flat/nested JSON mapping. `dpp_sdk.clients` owns synchronous generic HTTP clients,
client payload DTOs, and client error boundaries; applications supply a codec and validator to
`DppRepoClient` for typed repository values.

## Supported concepts

The SDK supports model construction, explicit semantic validation, JSON serialization and mapping,
immutable replacements through `with_updates()`, repository CRUD/read operations, fine-grained
element operations, and registry registration. The clients call public service APIs only; they do
not run, configure, or persist those services.

## Intentional exclusions and limitations

This repository does not provide a repository or registry server, persistence, lifecycle storage,
Docker or Spring runtime behavior, PostgreSQL integration, Postman/Swagger artifacts, internal Java
routes, authentication, retries, caching, pagination, or registry read-back/cleanup operations.
The Java-services demo is optional compatibility evidence and is not an SDK dependency.

## Prerequisites

Use Python 3.11 or newer. Docker and Compose are required only for the separate
[Java-services demo](../examples/java-services-demo/README.md).

## Reading order and next steps

Start with [SDK usage](usage.md). Use the [model guide](model-guide.md) for fields and JSON/null
semantics, the [validation guide](validation-guide.md) and [validation-rule reference]
(validation-rules.md) for validation/codec behavior, and the [clients guide]
(../src/dpp_sdk/clients/README.md) for request/response payloads and errors. Use
[RELEASING.md](../RELEASING.md) for development and release validation.
