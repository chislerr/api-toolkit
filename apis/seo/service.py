import json
import logging
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

from apis.seo.schemas import RICH_RESULTS, match_rich_result_type

logger = logging.getLogger("api.seo")

_client = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            },
        )
    return _client


async def _fetch_page(url: str) -> tuple[str, str]:
    client = _get_client()
    response = await client.get(url)
    response.raise_for_status()
    return response.text, str(response.url)


# ─── JSON-LD Extraction ─────────────────────────────────────────


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    """Extract all JSON-LD blocks, unwrap @graph, return flat list of entities."""
    entities = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(data, dict):
            if "@graph" in data:
                graph = data["@graph"]
                if isinstance(graph, list):
                    entities.extend(graph)
                else:
                    entities.append(graph)
            else:
                entities.append(data)
        elif isinstance(data, list):
            entities.extend(data)

    return [e for e in entities if isinstance(e, dict) and e.get("@type")]


# ─── Microdata Extraction ────────────────────────────────────────


def _extract_microdata(soup: BeautifulSoup) -> list[dict]:
    """Extract microdata from itemscope/itemprop attributes."""
    items = []

    for scope in soup.find_all(attrs={"itemscope": True}):
        # Skip nested scopes (handled by parent)
        if scope.find_parent(attrs={"itemscope": True}):
            continue

        item = _parse_microdata_item(scope)
        if item:
            items.append(item)

    return items


def _parse_microdata_item(element) -> dict:
    """Recursively parse a microdata itemscope element."""
    item = {}

    item_type = element.get("itemtype", "")
    if item_type:
        # Extract type name from URL (e.g. https://schema.org/Product → Product)
        item["@type"] = item_type.rstrip("/").split("/")[-1]

    for prop in element.find_all(attrs={"itemprop": True}):
        # Skip properties that belong to a nested scope
        parent_scope = prop.find_parent(attrs={"itemscope": True})
        if parent_scope and parent_scope != element:
            continue

        name = prop.get("itemprop")
        if not name:
            continue

        # Check if this property is itself a scope
        if prop.get("itemscope") is not None:
            value = _parse_microdata_item(prop)
        else:
            # Extract value from content, href, src, or text
            value = (
                prop.get("content")
                or prop.get("href")
                or prop.get("src")
                or prop.get("datetime")
                or prop.get_text(strip=True)
            )

        if name in item:
            # Convert to list for multiple values
            existing = item[name]
            if isinstance(existing, list):
                existing.append(value)
            else:
                item[name] = [existing, value]
        else:
            item[name] = value

    return item


# ─── Open Graph & Twitter Card Extraction ────────────────────────


def _extract_open_graph(soup: BeautifulSoup) -> dict:
    """Extract all og:* meta properties."""
    og = {}
    for tag in soup.find_all("meta", attrs={"property": True}):
        prop = tag.get("property", "")
        if prop.startswith("og:") and tag.get("content"):
            og[prop] = tag["content"]
    return og


def _extract_twitter_card(soup: BeautifulSoup) -> dict:
    """Extract all twitter:* meta properties."""
    tc = {}
    for tag in soup.find_all("meta", attrs={"name": True}):
        name = tag.get("name", "")
        if name.startswith("twitter:") and tag.get("content"):
            tc[name] = tag["content"]
    return tc


def _extract_meta_tags(soup: BeautifulSoup) -> dict:
    """Extract standard meta tags."""

    def meta(names):
        for n in names:
            tag = soup.find("meta", attrs={"name": n}) or soup.find(
                "meta", attrs={"property": n}
            )
            if tag and tag.get("content"):
                return tag["content"]
        return ""

    canonical = ""
    link = soup.find("link", rel="canonical")
    if link and link.get("href"):
        canonical = link["href"]

    return {
        "title": (
            soup.title.string.strip() if soup.title and soup.title.string else ""
        ),
        "description": meta(["description"]),
        "canonical": canonical,
        "robots": meta(["robots"]),
        "language": soup.find("html").get("lang", "") if soup.find("html") else "",
    }


# ─── Validation ──────────────────────────────────────────────────


def _validate_entity(entity: dict) -> dict:
    """Validate a schema.org entity against Rich Results requirements."""
    schema_type = entity.get("@type", "")
    category = match_rich_result_type(schema_type)

    if not category:
        return {
            "type": schema_type,
            "rich_result_category": None,
            "errors": [],
            "warnings": [],
            "score": None,
        }

    spec = RICH_RESULTS[category]
    errors = []
    warnings = []

    # Check required fields
    required = spec.get("required", [])
    for field in required:
        if not _has_field(entity, field):
            errors.append(f"Missing required field '{field}'")

    # Check recommended fields
    recommended = spec.get("recommended", [])
    for field in recommended:
        if not _has_field(entity, field):
            warnings.append(f"Missing recommended field '{field}'")

    # Check nested requirements (e.g. offers_required for Product)
    for key, sub_fields in spec.items():
        if key.endswith("_required") and isinstance(sub_fields, list):
            parent_key = key.replace("_required", "")
            parent = entity.get(parent_key)
            if parent:
                if isinstance(parent, list):
                    parent = parent[0] if parent else {}
                if isinstance(parent, dict):
                    for field in sub_fields:
                        if not _has_field(parent, field):
                            errors.append(
                                f"Missing required field '{parent_key}.{field}'"
                            )

    # Check FAQ special case
    if category == "FAQ" and "question_required" in spec:
        main_entity = entity.get("mainEntity", [])
        if isinstance(main_entity, list) and main_entity:
            sample = main_entity[0] if isinstance(main_entity[0], dict) else {}
            for field in spec["question_required"]:
                if not _has_field(sample, field):
                    errors.append(f"FAQ question missing required field '{field}'")

    # Score: 1.0 = all required present, reduced by missing fields
    total_checks = len(required) + len(recommended)
    if total_checks > 0:
        present = total_checks - len(errors) - len(warnings)
        score = round(max(0, present / total_checks), 2)
    else:
        score = 1.0

    return {
        "type": schema_type,
        "rich_result_category": category,
        "errors": errors,
        "warnings": warnings,
        "score": score,
    }


def _has_field(entity: dict, field: str) -> bool:
    """Check if a field exists and has a non-empty value."""
    val = entity.get(field)
    if val is None or val == "" or val == []:
        return False
    return True


# ─── Main Service Functions ──────────────────────────────────────


async def extract_structured_data(url: str) -> dict:
    """Extract ALL structured data from a URL with validation."""
    html, final_url = await _fetch_page(url)
    soup = BeautifulSoup(html, "lxml")

    # Extract everything
    json_ld_entities = _extract_json_ld(soup)
    microdata_entities = _extract_microdata(soup)
    open_graph = _extract_open_graph(soup)
    twitter_card = _extract_twitter_card(soup)
    meta_tags = _extract_meta_tags(soup)

    # Validate JSON-LD entities
    validated_json_ld = []
    all_types = []
    all_errors = 0
    all_warnings = 0
    eligible_types = []

    for entity in json_ld_entities:
        validation = _validate_entity(entity)
        entity_result = {**entity, "_validation": validation}
        validated_json_ld.append(entity_result)

        schema_type = entity.get("@type", "unknown")
        if isinstance(schema_type, list):
            all_types.extend(schema_type)
        else:
            all_types.append(schema_type)

        all_errors += len(validation["errors"])
        all_warnings += len(validation["warnings"])

        if (
            validation["rich_result_category"]
            and len(validation["errors"]) == 0
        ):
            eligible_types.append(validation["rich_result_category"])

    # Validate microdata entities too
    validated_microdata = []
    for entity in microdata_entities:
        validation = _validate_entity(entity)
        entity_result = {**entity, "_validation": validation}
        validated_microdata.append(entity_result)

        schema_type = entity.get("@type", "unknown")
        all_types.append(schema_type)
        all_errors += len(validation["errors"])
        all_warnings += len(validation["warnings"])

        if (
            validation["rich_result_category"]
            and len(validation["errors"]) == 0
        ):
            eligible_types.append(validation["rich_result_category"])

    # Deduplicate types
    unique_types = list(dict.fromkeys(all_types))
    unique_eligible = list(dict.fromkeys(eligible_types))

    total_entities = len(json_ld_entities) + len(microdata_entities)

    # Overall score
    if total_entities > 0:
        entity_scores = []
        for e in validated_json_ld + validated_microdata:
            s = e.get("_validation", {}).get("score")
            if s is not None:
                entity_scores.append(s)
        overall_score = (
            round(sum(entity_scores) / len(entity_scores), 2)
            if entity_scores
            else 0.0
        )
    else:
        overall_score = 0.0

    return {
        "url": final_url,
        "json_ld": validated_json_ld,
        "microdata": validated_microdata,
        "open_graph": open_graph,
        "twitter_card": twitter_card,
        "meta_tags": meta_tags,
        "summary": {
            "total_entities": total_entities,
            "types_found": unique_types,
            "rich_results_eligible": unique_eligible,
            "overall_score": overall_score,
            "critical_errors": all_errors,
            "warnings": all_warnings,
        },
        "source_url": final_url,
    }


async def check_rich_results(url: str) -> dict:
    """Check which Google Rich Result types a page qualifies for."""
    html, final_url = await _fetch_page(url)
    soup = BeautifulSoup(html, "lxml")

    json_ld_entities = _extract_json_ld(soup)
    microdata_entities = _extract_microdata(soup)
    all_entities = json_ld_entities + microdata_entities

    # Map found entities to Rich Result categories
    found_categories = {}
    for entity in all_entities:
        schema_type = entity.get("@type", "")
        category = match_rich_result_type(schema_type)
        if category and category not in found_categories:
            found_categories[category] = entity

    eligible = []
    not_eligible = []

    # Check found types
    for category, entity in found_categories.items():
        spec = RICH_RESULTS[category]
        required = spec.get("required", [])
        recommended = spec.get("recommended", [])

        fields_present = [f for f in required if _has_field(entity, f)]
        fields_missing = [f for f in required if not _has_field(entity, f)]
        fields_recommended = [f for f in recommended if not _has_field(entity, f)]

        entry = {
            "type": category,
            "fields_present": fields_present,
            "fields_missing": fields_missing,
            "fields_recommended": fields_recommended,
        }

        if not fields_missing:
            entry["status"] = "eligible"
            eligible.append(entry)
        else:
            entry["status"] = "missing_required"
            not_eligible.append(entry)

    # Check types not found on page at all
    checked_categories = list(RICH_RESULTS.keys())
    for category in checked_categories:
        if category not in found_categories:
            not_eligible.append(
                {
                    "type": category,
                    "status": "not_found",
                    "fields_present": [],
                    "fields_missing": RICH_RESULTS[category].get("required", []),
                    "fields_recommended": RICH_RESULTS[category].get(
                        "recommended", []
                    ),
                }
            )

    return {
        "url": final_url,
        "eligible": eligible,
        "not_eligible": not_eligible,
        "summary": {
            "eligible_count": len(eligible),
            "total_types_checked": len(checked_categories),
            "types_checked": checked_categories,
        },
        "source_url": final_url,
    }
