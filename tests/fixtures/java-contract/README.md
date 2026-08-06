# Java contract fixture snapshot

These immutable fixtures are owned by the Python test suite. They were generated from the Java
`dpp-datamodel/dpp4fun` implementation at commit
`9933d674ba27cd987f1bba731eb57b8dbb6bba95`. The original Java SHA-256 remains
in `sha256`; `pythonSnapshotSha256` protects the repository-owned LF-normalized copy. The root
`.gitattributes` keeps those bytes stable across operating systems.

Ordinary Python tests read only this directory. They do not require a Java checkout, Maven, parent
workspace evidence, or `docs/java-python-parity`. Regenerating or replacing the snapshot is a
separate cross-repository governance task; reviewing such a replacement must verify the source
commit, generator, fixture bytes, hashes, and expected outcomes before this directory is updated.
