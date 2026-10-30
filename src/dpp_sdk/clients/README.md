# DPP SDK clients module

`DppRepoClient` and `DppRegistryClient` call an EN 18222 repository and registry over HTTP. They
send and return plain JSON and do not build or validate passport models; use the codecs in
`dpp_sdk.core` or `dpp_sdk.dpp4fun` for that.

- [HTTP clients guide](../../../docs/clients-guide.md): every method, error, and option.
- [Decode a response into a typed passport](../../../docs/clients-guide.md#decode-a-response-into-a-typed-passport).
- [Contributing](../../../CONTRIBUTING.md): tests and checks for this module.
