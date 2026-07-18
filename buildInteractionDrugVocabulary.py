import ast
import csv
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin

import requests


manifest_url = "https://api.fda.gov/download.json"
app_path = Path(os.getenv("INTERX_APP_PATH", "app.py"))
csv_output_path = Path("openfda_interaction_drugs.csv")
choices_csv_output_path = Path("openfda_drug_choices.csv")
python_output_path = Path("openfda_interaction_drugs.py")
text_output_path = Path("openfda_interaction_drugs.txt")
choices_text_output_path = Path("openfda_drug_choices.txt")
rejected_output_path = Path("openfda_interaction_drugs_rejected.csv")

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "inteRx-interaction-vocabulary/3.0",
        "Accept": "application/json",
    }
)

placeholder_names = {
    "",
    "air",
    "diluent",
    "n/a",
    "na",
    "none",
    "null",
    "unknown",
    "water",
}

combination_pattern = re.compile(
    r"\b(?:and|with|plus)\b|[,;/+]",
    flags=re.IGNORECASE,
)

formulation_pattern = re.compile(
    r"""
    \b(?:
        aerosol|auto-injector|caplet|caplets|capsule|capsules|chewable|
        co-pack|concentrate|cream|delayed-release|disintegrating|drops|
        elixir|enteric-coated|extended-release|film-coated|foam|gel|
        granules|implant|inhalation|inhaler|injectable|injection|insert|
        kit|liquid|lozenge|ointment|ophthalmic|oral|patch|patches|powder|
        prefilled|solution|spray|suspension|syrup|syringe|tablet|tablets|
        topical|transdermal|vaginal|vial
    )\b
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)

biologic_suffix_pattern = re.compile(
    r".+-[a-z]{4}$",
    flags=re.IGNORECASE,
)

allowed_name_pattern = re.compile(
    r"^[a-z][a-z .'-]*[a-z]$",
    flags=re.IGNORECASE,
)


def normalize_name(value):
    return " ".join(str(value).split()).casefold().strip()


def normalize_interaction_text(value):
    text = str(value).casefold()
    text = (
        text.replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )
    return " ".join(text.split())


def canonical_rejection_reason(value):
    name = normalize_name(value)

    if name in placeholder_names:
        return "placeholder or overly broad name"
    if len(name) < 3:
        return "name is too short"
    if len(name) > 60:
        return "name is longer than 60 characters"
    if re.search(r"\d", name):
        return "contains a number, isotope, or strength"
    if "%" in name:
        return "contains a percentage"
    if re.search(r"[()\[\]{}\\:]", name):
        return "contains unsupported punctuation"
    if combination_pattern.search(name):
        return "combination name"
    if formulation_pattern.search(name):
        return "contains a formulation or dosage form"
    if biologic_suffix_pattern.fullmatch(name):
        return "biologic suffix variant"
    if not allowed_name_pattern.fullmatch(name):
        return "contains unsupported characters"
    if len(name.split()) > 4:
        return "contains more than four words"

    return ""


def brand_rejection_reason(value):
    name = normalize_name(value)

    if name in placeholder_names:
        return "placeholder or overly broad brand"
    if len(name) < 3:
        return "brand is too short"
    if len(name) > 60:
        return "brand is longer than 60 characters"
    if re.search(r"\d|[%/,;:()\[\]{}\\]", name):
        return "brand contains strength or product punctuation"
    if formulation_pattern.search(name):
        return "brand contains a formulation or dosage form"
    if not allowed_name_pattern.fullmatch(name):
        return "brand contains unsupported characters"
    if len(name.split()) > 4:
        return "brand contains more than four words"

    return ""


def interaction_sections(label):
    sections = label.get("drug_interactions", [])

    if isinstance(sections, str):
        sections = [sections]
    if not isinstance(sections, list):
        return []

    return [
        normalize_interaction_text(section)
        for section in sections
        if isinstance(section, str) and section.strip()
    ]


def openfda_values(label, field):
    openfda = label.get("openfda", {})

    if not isinstance(openfda, dict):
        return []

    values = openfda.get(field, [])

    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []

    return sorted(
        {
            normalize_name(value)
            for value in values
            if isinstance(value, str) and value.strip()
        }
    )


def label_identifier(label, fallback):
    openfda = label.get("openfda", {})
    identifiers = []

    if isinstance(openfda, dict):
        identifiers = (
            openfda.get("spl_id", [])
            or openfda.get("application_number", [])
        )

    if isinstance(identifiers, str):
        identifiers = [identifiers]

    return str(identifiers[0]) if identifiers else fallback


def build_candidate_pattern(candidate_names):
    escaped_names = [
        re.escape(name)
        for name in sorted(
            candidate_names,
            key=lambda value: (-len(value), value),
        )
    ]

    return re.compile(
        r"(?<![a-z0-9])(?:"
        + "|".join(escaped_names)
        + r")(?![a-z0-9])",
        flags=re.IGNORECASE,
    )


def format_tuple_assignment(variable_name, values, indentation):
    lines = [f"{indentation}{variable_name} = ("]
    lines.extend(
        f"{indentation}    {value!r},"
        for value in values
    )
    lines.append(f"{indentation})")
    return "\n".join(lines)


def replace_literal_assignment(source_text, variable_name, values):
    syntax_tree = ast.parse(source_text)
    matching_nodes = []

    for node in ast.walk(syntax_tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
        )

        if any(
            isinstance(target, ast.Name)
            and target.id == variable_name
            for target in targets
        ):
            matching_nodes.append(node)

    if not matching_nodes:
        return source_text, False
    if len(matching_nodes) != 1:
        raise RuntimeError(
            f"Expected one {variable_name!r} assignment, "
            f"found {len(matching_nodes)}."
        )

    assignment = matching_nodes[0]
    source_lines = source_text.splitlines(keepends=True)
    start_index = assignment.lineno - 1
    end_index = assignment.end_lineno
    first_line = source_lines[start_index]
    indentation = first_line[
        : len(first_line) - len(first_line.lstrip())
    ]
    replacement = format_tuple_assignment(
        variable_name,
        tuple(values),
        indentation,
    )

    if end_index < len(source_lines) or source_text.endswith("\n"):
        replacement += "\n"

    updated_text = (
        "".join(source_lines[:start_index])
        + replacement
        + "".join(source_lines[end_index:])
    )
    ast.parse(updated_text)
    return updated_text, True


def update_embedded_app_choices(target_path, drug_choices):
    target_path = Path(target_path)

    if not target_path.exists():
        print(
            f"App update skipped: {target_path.resolve()} does not exist."
        )
        return False

    original_text = target_path.read_text(encoding="utf-8")
    ast.parse(original_text)
    updated_text, replaced = replace_literal_assignment(
        original_text,
        "openfda_drug_choices",
        drug_choices,
    )

    if not replaced:
        print(
            "App update skipped: openfda_drug_choices assignment "
            f"was not found in {target_path.resolve()}."
        )
        return False

    compile(updated_text, str(target_path), "exec")
    temporary_path = target_path.with_name(
        target_path.name + ".tmp"
    )
    temporary_path.write_text(
        updated_text,
        encoding="utf-8",
        newline="\n",
    )
    temporary_path.replace(target_path)

    print(
        f"Embedded choices updated in {target_path.resolve()}: "
        f"{len(drug_choices):,} names."
    )
    return True


print("Downloading openFDA bulk-download manifest...")
manifest_response = session.get(manifest_url, timeout=120)
manifest_response.raise_for_status()
manifest = manifest_response.json()

try:
    partitions = manifest["results"]["drug"]["label"]["partitions"]
except (KeyError, TypeError) as exc:
    raise RuntimeError(
        "Could not find results.drug.label.partitions in the openFDA manifest."
    ) from exc

download_urls = []

for partition in partitions:
    if not isinstance(partition, dict):
        continue

    file_url = partition.get("file")

    if file_url:
        download_urls.append(
            urljoin(
                "https://download.open.fda.gov/",
                str(file_url),
            )
        )

download_urls = list(dict.fromkeys(download_urls))

if not download_urls:
    raise RuntimeError("No openFDA drug-label partitions were found.")

print(f"Found {len(download_urls):,} partitions.")

candidate_counts = defaultdict(int)
candidate_label_ids = defaultdict(set)
brand_label_ids = defaultdict(set)
brand_to_candidates = defaultdict(set)
rejected_rows = []
total_labels = 0
interaction_labels = 0

with tempfile.TemporaryDirectory(
    prefix="openfda_interaction_vocabulary_"
) as temporary_directory:
    temporary_directory = Path(temporary_directory)
    downloaded_zip_paths = []

    for partition_number, download_url in enumerate(
        download_urls,
        start=1,
    ):
        zip_path = (
            temporary_directory
            / f"drug-label-{partition_number:04d}.zip"
        )
        downloaded_zip_paths.append(zip_path)

        print(
            f"[Pass 1, {partition_number}/{len(download_urls)}] "
            f"Downloading {download_url}"
        )

        with session.get(
            download_url,
            stream=True,
            timeout=(30, 900),
        ) as response:
            response.raise_for_status()

            with zip_path.open("wb") as output_file:
                shutil.copyfileobj(
                    response.raw,
                    output_file,
                    length=1024 * 1024,
                )

        if not zipfile.is_zipfile(zip_path):
            raise RuntimeError(
                f"Invalid ZIP archive downloaded from {download_url}"
            )

        with zipfile.ZipFile(zip_path) as archive:
            json_members = [
                member
                for member in archive.namelist()
                if member.casefold().endswith(".json")
            ]

            for json_member in json_members:
                with archive.open(json_member) as compressed_file:
                    with io.TextIOWrapper(
                        compressed_file,
                        encoding="utf-8",
                    ) as text_file:
                        results = json.load(text_file).get("results", [])

                for label in results:
                    total_labels += 1

                    if not isinstance(label, dict):
                        continue

                    if interaction_sections(label):
                        interaction_labels += 1

                    label_id = label_identifier(
                        label,
                        f"label:{total_labels}",
                    )
                    raw_candidates = set(
                        openfda_values(label, "generic_name")
                    ) | set(openfda_values(label, "substance_name"))
                    clean_candidates = set()

                    for candidate_name in raw_candidates:
                        reason = canonical_rejection_reason(candidate_name)

                        if reason:
                            rejected_rows.append(
                                {
                                    "normalized_name": candidate_name,
                                    "name_type": "canonical_candidate",
                                    "rejection_reason": reason,
                                }
                            )
                            continue

                        clean_candidates.add(candidate_name)
                        candidate_counts[candidate_name] += 1
                        candidate_label_ids[candidate_name].add(label_id)

                    for brand_name in openfda_values(label, "brand_name"):
                        reason = brand_rejection_reason(brand_name)

                        if reason:
                            rejected_rows.append(
                                {
                                    "normalized_name": brand_name,
                                    "name_type": "brand_alias",
                                    "rejection_reason": reason,
                                }
                            )
                            continue

                        brand_label_ids[brand_name].add(label_id)
                        brand_to_candidates[brand_name].update(
                            clean_candidates
                        )

    candidate_names = set(candidate_counts)

    if not candidate_names:
        raise RuntimeError(
            "No clean generic/substance candidates were found."
        )

    print()
    print(f"Processed labels: {total_labels:,}")
    print(
        "Labels containing drug_interactions: "
        f"{interaction_labels:,}"
    )
    print(
        "Clean candidates collected from all labels: "
        f"{len(candidate_names):,}"
    )

    candidate_pattern = build_candidate_pattern(candidate_names)
    mention_counts = defaultdict(int)
    mention_label_counts = defaultdict(set)

    for partition_number, zip_path in enumerate(
        downloaded_zip_paths,
        start=1,
    ):
        print(
            f"[Pass 2, {partition_number}/{len(downloaded_zip_paths)}] "
            "Scanning interaction text"
        )

        with zipfile.ZipFile(zip_path) as archive:
            json_members = [
                member
                for member in archive.namelist()
                if member.casefold().endswith(".json")
            ]

            for json_member in json_members:
                with archive.open(json_member) as compressed_file:
                    with io.TextIOWrapper(
                        compressed_file,
                        encoding="utf-8",
                    ) as text_file:
                        results = json.load(text_file).get("results", [])

                for label_number, label in enumerate(results):
                    if not isinstance(label, dict):
                        continue

                    sections = interaction_sections(label)

                    if not sections:
                        continue

                    label_id = label_identifier(
                        label,
                        (
                            f"partition:{partition_number}:"
                            f"label:{label_number}"
                        ),
                    )
                    seen_in_label = set()

                    for section in sections:
                        for match in candidate_pattern.finditer(section):
                            matched_name = normalize_name(match.group(0))

                            if matched_name not in candidate_names:
                                continue

                            mention_counts[matched_name] += 1
                            seen_in_label.add(matched_name)

                    for matched_name in seen_in_label:
                        mention_label_counts[matched_name].add(label_id)

canonical_names = tuple(
    sorted(
        name
        for name in candidate_names
        if mention_counts.get(name, 0) > 0
    )
)
canonical_name_set = frozenset(canonical_names)
brand_alias_map = {
    brand_name: tuple(
        sorted(brand_to_candidates[brand_name] & canonical_name_set)
    )
    for brand_name in sorted(brand_to_candidates)
    if brand_to_candidates[brand_name] & canonical_name_set
}
drug_choices = tuple(
    sorted(canonical_name_set | set(brand_alias_map))
)

required_names = {"aspirin", "warfarin", "alprazolam", "xanax"}
missing_required_names = required_names - set(drug_choices)

if missing_required_names:
    raise RuntimeError(
        "Expected names were not derived from openFDA data: "
        + ", ".join(sorted(missing_required_names))
    )

canonical_records = [
    {
        "normalized_name": name,
        "source_label_count": len(candidate_label_ids[name]),
        "interaction_text_mention_count": mention_counts[name],
        "interaction_text_label_count": len(
            mention_label_counts[name]
        ),
    }
    for name in canonical_names
]

with csv_output_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as csv_file:
    writer = csv.DictWriter(
        csv_file,
        fieldnames=list(canonical_records[0]),
    )
    writer.writeheader()
    writer.writerows(canonical_records)

with choices_csv_output_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as choices_file:
    writer = csv.DictWriter(
        choices_file,
        fieldnames=[
            "choice",
            "choice_type",
            "canonical_names",
            "source_label_count",
        ],
    )
    writer.writeheader()

    for choice in drug_choices:
        if choice in canonical_name_set:
            choice_type = "canonical"
            aliases = (choice,)
            source_count = len(candidate_label_ids[choice])
        else:
            choice_type = "brand_alias"
            aliases = brand_alias_map[choice]
            source_count = len(brand_label_ids[choice])

        writer.writerow(
            {
                "choice": choice,
                "choice_type": choice_type,
                "canonical_names": ", ".join(aliases),
                "source_label_count": source_count,
            }
        )

text_output_path.write_text(
    "\n".join(canonical_names) + "\n",
    encoding="utf-8",
)
choices_text_output_path.write_text(
    "\n".join(drug_choices) + "\n",
    encoding="utf-8",
)

with python_output_path.open(
    "w",
    encoding="utf-8",
    newline="\n",
) as python_file:
    python_file.write(
        '"""Generated openFDA interaction vocabulary for inteRx."""\n\n'
    )
    python_file.write("OPENFDA_INTERACTION_DRUGS = (\n")

    for name in canonical_names:
        python_file.write(f"    {name!r},\n")

    python_file.write(")\n\n")
    python_file.write(
        "OPENFDA_INTERACTION_DRUG_SET = "
        "frozenset(OPENFDA_INTERACTION_DRUGS)\n\n"
    )
    python_file.write("OPENFDA_BRAND_ALIAS_MAP = {\n")

    for brand_name, aliases in brand_alias_map.items():
        python_file.write(
            f"    {brand_name!r}: {aliases!r},\n"
        )

    python_file.write("}\n\n")
    python_file.write("OPENFDA_DRUG_CHOICES = (\n")

    for choice in drug_choices:
        python_file.write(f"    {choice!r},\n")

    python_file.write(")\n\n")
    python_file.write(
        "OPENFDA_DRUG_CHOICE_SET = "
        "frozenset(OPENFDA_DRUG_CHOICES)\n"
    )

with rejected_output_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as rejected_file:
    writer = csv.DictWriter(
        rejected_file,
        fieldnames=[
            "normalized_name",
            "name_type",
            "rejection_reason",
        ],
    )
    writer.writeheader()
    writer.writerows(rejected_rows)

update_embedded_app_choices(app_path, drug_choices)

print()
print(f"Canonical interaction names: {len(canonical_names):,}")
print(f"Derived brand aliases: {len(brand_alias_map):,}")
print(f"Autocomplete choices: {len(drug_choices):,}")
print(f"Canonical CSV: {csv_output_path.resolve()}")
print(f"Choices CSV: {choices_csv_output_path.resolve()}")
print(f"Python module: {python_output_path.resolve()}")
print(f"Rejected audit: {rejected_output_path.resolve()}")
print()
print("Required derivation checks:")

for name in ("aspirin", "alprazolam", "warfarin", "xanax"):
    if name in canonical_name_set:
        detail = "canonical"
    elif name in brand_alias_map:
        detail = "brand -> " + ", ".join(
            brand_alias_map[name]
        )
    else:
        detail = "missing"

    print(f"{name}: {detail}")
