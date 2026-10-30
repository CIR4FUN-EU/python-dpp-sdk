# DPP SDK core module

`dpp_sdk.core` holds the general passport model (`DigitalProductPassport`, `DppHeader`, and five
DataElement types), FULL and COMPRESSED JSON conversion (`DppJsonCodec`), and validation
(`DppValidator`, `DataFormatValidator`, `IdentifierValidator`). It does not depend on DPP4Fun or
the HTTP clients.

- [Model guide](../../../docs/model-guide.md): build, read, edit, validate, and convert passports.
- [Building your own profile](../../../docs/extending.md): use Core for other product groups.
- [Standards alignment and validation rules](../../../docs/conformance.md).
- [Contributing](../../../CONTRIBUTING.md): tests and checks for this module.
