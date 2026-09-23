# Data attribution and provenance

`vbo-dogs.json` is adapted from the **Vertebrate Breed Ontology**, by the
VBO contributors / Monarch Initiative:
https://github.com/monarch-initiative/vertebrate-breed-ontology

Release: v2026-04-15. Upstream commit: `8364a3ec538d529bdd3efcf3af8401b98f48fb4f`.
Source license: **Creative Commons Attribution 4.0 International**,
https://creativecommons.org/licenses/by/4.0/ .
The upstream license declaration is in
https://github.com/monarch-initiative/vertebrate-breed-ontology/blob/8364a3ec538d529bdd3efcf3af8401b98f48fb4f/README.md#license .

Changes: select non-obsolete descendants of Dog breed along explicit is_a edges;
retain IDs, names, EXACT synonyms, parents, and source line numbers; convert to JSON;
sort terms and deduplicate synonyms. No breed names or ontology IDs were invented.
Derived reference queries retain this attribution and license. Project Python code
remains Apache-2.0; this third-party data is distributed under CC BY 4.0.
No endorsement by the VBO contributors is implied.

`manifest.json` records original and transformed byte counts/hashes and retrieval time.
`../prepare_source.py` reproduces this adaptation from the exact upstream source.
