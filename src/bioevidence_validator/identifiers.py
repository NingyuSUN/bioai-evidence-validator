"""Identifier grounders: check the identifiers a record cites against pinned reference releases.

A model writes identifiers that look right: an ontology ID whose label belongs to another term, an obsolete
term, a gene alias, a variant on the wrong genome build. These grounders look each one up in a pinned
release (an OBO ontology, the HGNC complete set, NCBI assembly reports) and say what is wrong in words an
agent can act on ("'T cell' is the name of CL:0000084"). They are offline and deterministic, and each
grounder's name carries the release it used, so a report records it.

Where identifiers are looked up:
- the statement's subject and object (`id`, `label`, `entity_type`);
- the statement's scope tokens (ontology terms only);
- evidence item locators written as `key=value` pairs separated by `;` (e.g. `cluster=3;gene=CD8A`), for
  the keys a grounder is given.

Rule codes (see `grounding`):
  BEV015 review  the reference cannot confirm the identifier (e.g. a gene outside the reference's species)
  BEV016 error   the identifier does not exist in the pinned release
  BEV017 error   the identifier and its label disagree, or a variant is on another genome build
  BEV023 error   the identifier is obsolete, withdrawn, or not its current name (previous symbol, alias)
  BEV024 error   the identifier is malformed, or of the wrong kind for its place (e.g. not a cell type)
"""
from __future__ import annotations

import csv
import difflib
import io
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import cache
from typing import Any

from .engine import Finding
from .grounding import finding

HUMAN = "NCBITaxon:9606"


def pairs(text: str | None) -> dict[str, str]:
    """`key=value` pairs separated by `;`; empty when the text is not written that way."""
    out = {}
    for part in (text or "").split(";"):
        key, sep, value = part.partition("=")
        if not sep or not key.strip():
            return {}
        out[key.strip()] = value.strip()
    return out


def _prefix(curie: str) -> str:
    return curie.partition(":")[0] if ":" in curie else ""


def _label_key(text: str) -> str:
    """Case, punctuation and a plain plural ("hepatocytes") do not change a label."""
    words = re.sub(r"[^0-9a-z]+", " ", text.casefold()).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)


def _entities(record: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    statement = record["statement"]
    for role in ("subject", "object"):
        yield f"$.statement.{role}", statement[role]


# Ontologies (OBO format)

@dataclass
class Term:
    id: str
    name: str = ""
    synonyms: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    obsolete: bool = False
    replaced_by: list[str] = field(default_factory=list)
    consider: list[str] = field(default_factory=list)
    disjoint: list[str] = field(default_factory=list)
    relations: list[tuple[str, str]] = field(default_factory=list)  # (relation, target): relationship, intersection_of
    short_labels: list[str] = field(default_factory=list)  # gene names of a protein term: PRO short labels, gene-based synonyms


class Ontology:
    """The terms of one pinned OBO release: names, exact synonyms, `is_a` parents, obsoletion, disjointness, and
    the relations that logical definitions use (e.g. `has plasma membrane part` a protein)."""

    def __init__(self, terms: dict[str, Term], prefix: str, version: str):
        self.terms, self.prefix, self.version = terms, prefix, version
        self._labels: dict[str, list[str]] = {}
        for term in terms.values():
            if not term.obsolete:
                for key in dict.fromkeys(_label_key(text) for text in [term.name, *term.synonyms]):
                    self._labels.setdefault(key, []).append(term.id)
        self._names = {_label_key(t.name): t.id for t in terms.values() if not t.obsolete and _prefix(t.id) == prefix}

    @classmethod
    def from_obo(cls, data: bytes) -> Ontology:
        terms: dict[str, Term] = {}
        header: dict[str, str] = {}
        term: Term | None = None
        in_header = True
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            if line.startswith("["):
                in_header, term = False, None
                if line == "[Term]":
                    term = Term("")
                continue
            tag, _, value = line.partition(": ")
            if in_header:
                header.setdefault(tag, value)
            elif term is not None and tag:
                value = value.split(" ! ", 1)[0].strip()
                if tag == "id":
                    term.id = value
                    terms[value] = term
                elif tag == "name":
                    term.name = value
                elif tag == "synonym" and (match := re.match(r'"((?:[^"\\]|\\.)*)" (\w+)', value)):
                    text = match.group(1).replace('\\"', '"')
                    if match.group(2) == "EXACT":
                        term.synonyms.append(text)
                    if "PRO-short-label" in value or "Gene-based" in value:
                        term.short_labels.append(text)
                elif tag == "is_a":
                    term.parents.append(value.split()[0])
                elif tag == "is_obsolete":
                    term.obsolete = value == "true"
                elif tag == "replaced_by":
                    term.replaced_by.append(value)
                elif tag == "consider":
                    term.consider.append(value)
                elif tag == "disjoint_from":
                    term.disjoint.append(value)
                elif tag in ("relationship", "intersection_of") and len(value.split()) == 2:
                    pair = (value.split()[0], value.split()[1])
                    if pair not in term.relations:
                        term.relations.append(pair)
        # `ontology: cl` or `ontology: cl/cl-basic`; a release file may also hold a few terms of other ontologies
        prefix = header.get("ontology", "").split("/")[0].upper()
        version = header.get("data-version", "") or header.get("date", "")
        return cls(terms, prefix, version)

    def describe(self, curie: str) -> str:
        term = self.terms.get(curie)
        return f"{curie} ({term.name})" if term and term.name else curie

    def ancestors(self, curie: str) -> frozenset[str]:
        """The term and every `is_a` ancestor."""
        return self._ancestors(curie)

    @cache  # noqa: B019 - one instance per pinned release, kept for the process
    def _ancestors(self, curie: str) -> frozenset[str]:
        term = self.terms.get(curie)
        found = {curie}
        for parent in term.parents if term else []:
            found |= self._ancestors(parent)
        return frozenset(found)

    def related(self, a: str, b: str) -> bool:
        """The same term, or one is an ancestor of the other."""
        return a in self.ancestors(b) or b in self.ancestors(a)

    def disjoint(self, a: str, b: str) -> bool:
        """Declared disjoint: some ancestor of one is `disjoint_from` some ancestor of the other."""
        mine, theirs = self.ancestors(a), self.ancestors(b)
        return any(d in theirs for x in mine if x in self.terms for d in self.terms[x].disjoint) or             any(d in mine for x in theirs if x in self.terms for d in self.terms[x].disjoint)

    def by_label(self, label: str) -> list[str]:
        return self._labels.get(_label_key(label), [])

    def hint(self, label: str | None) -> str:
        """A suggestion for a label: the term it names, else the closest names."""
        if not label:
            return ""
        exact = self.by_label(label)
        if exact:
            return f" {label!r} is the name of {self.describe(exact[0])}."
        close = difflib.get_close_matches(_label_key(label), list(self._names), n=3, cutoff=0.75)
        return (" Closest names: " + "; ".join(self.describe(self._names[c]) for c in close) + ".") if close else ""


class OntologyGrounder:
    """Ontology terms cited by a record: they exist, are current, match their labels and are of the right kind.

    `roots` maps an entity type (or a locator key) to the terms its identifiers must descend from, e.g.
    `{"cell_type": ["CL:0000000"]}`; an identifier from another ontology is then the wrong kind (BEV024).
    """

    def __init__(self, ontologies: Iterable[Ontology], roots: Mapping[str, Iterable[str]] | None = None,
                 locator_keys: Iterable[str] = ()):
        self.ontologies = {o.prefix: o for o in ontologies}
        self.roots = {kind: tuple(ids) for kind, ids in (roots or {}).items()}
        self.keys = tuple(locator_keys)
        self.name = "ontology:" + ",".join(f"{o.prefix}@{o.version}" for o in self.ontologies.values())

    def check(self, record: dict[str, Any]) -> list[Finding]:
        out = []
        for path, entity in _entities(record):
            out += self._term(record, entity["id"], entity["label"], entity["entity_type"], path + ".id", path + ".label")
        for index, token in enumerate(record["statement"]["scope"]):
            out += self._term(record, token, None, None, f"$.statement.scope[{index}]")
        for index, item in enumerate(record["evidence_items"]):
            located = pairs(item["locator"])
            for key in self.keys:
                if key in located:
                    out += self._term(record, located[key], None, key, f"$.evidence_items[{index}].locator")
        return out

    def _term(self, record: dict[str, Any], curie: str, label: str | None, kind: str | None, path: str,
              label_path: str = "") -> list[Finding]:
        roots = self.roots.get(kind or "")
        if roots and _prefix(curie) not in {_prefix(r) for r in roots}:
            owner = self.ontologies.get(_prefix(roots[0]))
            wanted = " or ".join(sorted({_prefix(r) for r in roots}))
            return [finding(record, "BEV024", f"A {kind} must be a {wanted} term; {curie!r} is not."
                                              f"{owner.hint(label) if owner else ''}", path)]
        ontology = self.ontologies.get(_prefix(curie))
        if ontology is None:
            return []
        term = ontology.terms.get(curie)
        if term is None:
            return [finding(record, "BEV016", f"{curie} is not in the pinned {ontology.prefix} release "
                                              f"({ontology.version}).{ontology.hint(label)}", path)]
        if term.obsolete:
            replacement = term.replaced_by or term.consider
            advice = (" Use " + " or ".join(ontology.describe(r) for r in replacement) + "." if replacement
                      else ontology.hint(label))
            return [finding(record, "BEV023", f"{ontology.describe(curie)} is obsolete in the pinned {ontology.prefix} "
                                              f"release.{advice}", path)]
        out = []
        if label is not None and curie not in ontology.by_label(label):
            out.append(finding(record, "BEV017", f"The label {label!r} is not the name of {curie} ({term.name!r})."
                                                 f"{ontology.hint(label)}", label_path or path))
        if roots and not any(r in ontology.ancestors(curie) for r in roots):
            under = " or ".join(ontology.describe(r) for r in roots)
            out.append(finding(record, "BEV024", f"{ontology.describe(curie)} is not a {kind}: it is not under {under}.",
                               path))
        return out


# Genes (HGNC complete set)

class Genes:
    """Approved human gene symbols and identifiers from a pinned HGNC complete set (TSV)."""

    def __init__(self, rows: Iterable[dict[str, str]], version: str = ""):
        self.version = version
        self.by_id: dict[str, dict[str, str]] = {}
        self.approved: dict[str, str] = {}
        self.folded: dict[str, str] = {}
        self.renamed: dict[str, list[str]] = {}
        for row in rows:
            symbol = row["symbol"]
            self.by_id[row["hgnc_id"]] = row
            self.approved[symbol] = row["hgnc_id"]
            self.folded.setdefault(symbol.casefold(), symbol)
            for column in ("prev_symbol", "alias_symbol"):
                for old in filter(None, (row.get(column) or "").strip('"').split("|")):
                    self.renamed.setdefault(old, []).append(symbol)

    @classmethod
    def from_hgnc(cls, data: bytes, version: str = "") -> Genes:
        return cls(csv.DictReader(io.StringIO(data.decode("utf-8")), delimiter="\t"), version)

    def problem(self, symbol: str) -> tuple[str, str] | None:
        """(rule code, message) for a symbol that is not an approved one."""
        if symbol in self.approved:
            return None
        current = sorted(set(self.renamed.get(symbol, [])))
        if current:
            return "BEV023", (f"{symbol} is not an approved HGNC symbol; it is a previous symbol or alias of "
                              + " / ".join(current) + ".")
        if symbol.casefold() in self.folded:
            return "BEV023", f"{symbol} is not an approved HGNC symbol; the approved symbol is {self.folded[symbol.casefold()]}."
        close = difflib.get_close_matches(symbol, list(self.approved), n=3, cutoff=0.8)
        return "BEV016", f"{symbol} is not an HGNC gene symbol." + (f" Closest: {', '.join(close)}." if close else "")


class GeneGrounder:
    """Human gene symbols and HGNC identifiers cited by a record are current and consistent."""

    def __init__(self, genes: Genes, locator_keys: Iterable[str] = ("gene",), entity_types: Iterable[str] = ("gene",)):
        self.genes = genes
        self.keys, self.types = tuple(locator_keys), set(entity_types)
        self.name = f"genes:HGNC@{genes.version}"

    def check(self, record: dict[str, Any]) -> list[Finding]:
        taxa = {t for t in record["statement"]["scope"] if t.startswith("NCBITaxon:")}
        if taxa and HUMAN not in taxa:
            return [finding(record, "BEV015", f"HGNC names human genes; this record is scoped to {', '.join(sorted(taxa))}, "
                                              "so its gene symbols are not checked.", "$.statement.scope")]
        out = []
        for path, entity in _entities(record):
            if entity["entity_type"] in self.types or entity["id"].startswith("HGNC:"):
                out += self._entity(record, entity, path)
        for index, item in enumerate(record["evidence_items"]):
            located = pairs(item["locator"])
            for key in self.keys:
                if key in located and (problem := self.genes.problem(located[key])):
                    out.append(finding(record, problem[0], problem[1], f"$.evidence_items[{index}].locator"))
        return out

    def _entity(self, record: dict[str, Any], entity: dict[str, Any], path: str) -> list[Finding]:
        if entity["id"].startswith("HGNC:"):
            row = self.genes.by_id.get(entity["id"])
            if row is None:
                return [finding(record, "BEV016", f"{entity['id']} is not in the pinned HGNC set.", path + ".id")]
            if entity["label"] != row["symbol"]:
                return [finding(record, "BEV017", f"The label {entity['label']!r} is not the symbol of {entity['id']} "
                                                  f"({row['symbol']}).", path + ".label")]
            return []
        problem = self.genes.problem(entity["label"])
        return [finding(record, problem[0], problem[1], path + ".label")] if problem else []


# Variants (HGVS on RefSeq sequences, NCBI assembly reports)

HGVS = re.compile(r"^(?P<ac>(?P<kind>N[CGMRPTW]|X[MRP])_\d+)(?:\.(?P<version>\d+))?:(?P<type>[cgmnpr])\.(?P<rest>\S+)$")
BUILD = re.compile(r"^(GRCh3[78]|GRCm3[89]|hg19|hg38|CanFam\d+(?:\.\d+)?|UU_Cfam_GSD_1\.0|Dog10K_Boxer_Tasha)$")
ALIASES = {"hg19": "GRCh37", "hg38": "GRCh38"}


class Assemblies:
    """RefSeq chromosome sequences (accession.version → build, name, length) from NCBI assembly reports."""

    def __init__(self, sequences: dict[str, tuple[str, str, int]]):
        self.sequences = sequences
        self.version = "+".join(sorted({build for build, _, _ in sequences.values()}))

    @classmethod
    def from_reports(cls, reports: Iterable[bytes]) -> Assemblies:
        sequences = {}
        for data in reports:
            text = data.decode("utf-8")
            match = re.search(r"^# Assembly name:\s*(\S+)", text, re.M)
            # Human patch suffixes are aliases of their major build. A decimal
            # in CanFam3.1 (or UU_Cfam_GSD_1.0) is part of the assembly identity.
            build = re.sub(r"\.p\d+$", "", match.group(1) if match else "")
            for line in text.splitlines():
                cells = line.split("\t")
                if line.startswith("#") or len(cells) < 9 or cells[6] == "na":
                    continue
                sequences[cells[6]] = (build, cells[0], int(cells[8]) if cells[8].isdigit() else 0)
        return cls(sequences)


class VariantGrounder:
    """HGVS variant descriptions: well formed, versioned, on a real sequence of the record's genome build."""

    def __init__(self, assemblies: Assemblies, locator_keys: Iterable[str] = ("variant", "hgvs"),
                 entity_types: Iterable[str] = ("variant",)):
        self.assemblies = assemblies
        self.keys, self.types = tuple(locator_keys), set(entity_types)
        self.name = f"variants:{assemblies.version}"

    def check(self, record: dict[str, Any]) -> list[Finding]:
        registered = {build for build, _, _ in self.assemblies.sequences.values()}
        builds = {ALIASES.get(t, t) for t in record["statement"]["scope"] if BUILD.fullmatch(t) or t in registered}
        cited: list[tuple[str, str]] = []
        for path, entity in _entities(record):
            if entity["entity_type"] in self.types:
                text = entity["id"] if HGVS.match(entity["id"]) else entity["label"]
                cited.append((path + (".id" if text == entity["id"] else ".label"), text))
        for index, item in enumerate(record["evidence_items"]):
            located = pairs(item["locator"])
            cited += [(f"$.evidence_items[{index}].locator", located[k]) for k in self.keys if k in located]
        out, seen = [], set()
        for path, text in cited:
            match = HGVS.match(text)
            if match is None:
                out.append(finding(record, "BEV024", f"{text!r} is not an HGVS description on a RefSeq sequence "
                                                     "(e.g. NC_000007.14:g.140753336A>T).", path))
                continue
            if match["version"] is None:
                out.append(finding(record, "BEV024", f"{match['ac']} has no version; HGVS needs a versioned accession.",
                                   path))
                continue
            if match["kind"] != "NC":
                continue  # transcripts and proteins: form checked only
            accession = f"{match['ac']}.{match['version']}"
            if accession not in self.assemblies.sequences:
                known = sorted(a for a in self.assemblies.sequences if a.startswith(match["ac"] + "."))
                advice = f" Pinned versions: {', '.join(known)}." if known else ""
                out.append(finding(record, "BEV016", f"{accession} is not a sequence of the pinned assemblies.{advice}", path))
                continue
            build, name, length = self.assemblies.sequences[accession]
            seen.add(build)
            if builds and build not in builds:
                out.append(finding(record, "BEV017", f"{accession} (chromosome {name}) is on {build}, but the record is "
                                                     f"scoped to {', '.join(sorted(builds))}.", path))
            position = re.match(r"(\d+)", match["rest"])
            if match["type"] == "g" and position and length and int(position.group(1)) > length:
                out.append(finding(record, "BEV016", f"Position {position.group(1)} is beyond the end of chromosome "
                                                     f"{name} on {build} ({length} bp).", path))
        if len(seen) > 1 and not builds:
            out.append(finding(record, "BEV017", "The record cites variants on more than one genome build: "
                                                 + ", ".join(sorted(seen)) + ".", "$.statement.scope"))
        return out
