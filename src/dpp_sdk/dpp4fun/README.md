# DPP SDK DPP4Fun module

`dpp_sdk.dpp4fun` is a typed view over a core passport for the DPP4Fun furniture profile (D4.1):
19 aspects, six product types, reusable composites, unit-safe quantities, profile validation
(`validate_dpp4fun()`), and `Dpp4FunJsonCodec`. The bundled
`semantic/dpp4fun-semantic-profile-v1.json` describes all 488 fields; Python reads that packaged
copy at runtime.

- [Model guide](../../../docs/model-guide.md#build-a-dpp4fun-passport): build, read, edit, and validate.
- [DPP4Fun field reference](../../../docs/dpp4fun-fields.md): every field name per aspect.
- [Standards alignment and validation rules](../../../docs/conformance.md): D4.1 source conflicts.
- [Contributing](../../../CONTRIBUTING.md): tests and checks for this module.
