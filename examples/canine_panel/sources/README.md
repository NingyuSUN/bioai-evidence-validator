# Frozen canine reference slices

Seven snapshots preserve their original bytes. Six are official NCBI EFetch
interval FASTA responses with retrieval receipts. The seventh is a producer
receipt containing 23 ROSY reference slices; only six are used in this example.
The files are named by SHA-256. `../provenance.json` records exact accessions,
retrieval URLs, timestamps, original paths and the parent panel commit.

AGRN uses Dog10K_Boxer_Tasha; the other five use UU_Cfam_GSD_1.0. The custom
target reference is identified by its exact whole-FASTA SHA-256, rather than
assuming it equals an unmodified public assembly. The validator re-hashes each
snapshot and embedded sequence, but trusts the producer receipt's assertion
about the whole genome. No raw sample reads or clinical labels are included.

NCBI's [molecular data policy](https://www.ncbi.nlm.nih.gov/home/about/policies/)
places no restrictions on use or distribution of its molecular database data,
while preserving possible submitter intellectual property claims. NCBI does not
transfer unrestricted third-party rights. The repository's Apache-2.0 license
applies to authored scripts and metadata; it does not relicense submitted source
sequences. Please acknowledge NCBI and the assembly providers identified in the
original FASTA headers. No full paper text is redistributed in this example.
