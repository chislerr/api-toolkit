import json
import logging
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from apis.seo.schemas import RICH_RESULTS, FIX_SUGGESTIONS, match_rich_result_type
from core.ssrf import validate_url

logger = logging.getLogger("api.seo")


def _get_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        },
    )


async def _fetch_page(url: str) -> tuple[str, str]:
    validate_url(url)
    async with _get_client() as client:
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
        item["@type"] = item_type.rstrip("/").split("/")[-1]

    for prop in element.find_all(attrs={"itemprop": True}):
        parent_scope = prop.find_parent(attrs={"itemscope": True})
        if parent_scope and parent_scope != element:
            continue

        name = prop.get("itemprop")
        if not name:
            continue

        if prop.get("itemscope") is not None:
            value = _parse_microdata_item(prop)
        else:
            value = (
                prop.get("content")
                or prop.get("href")
                or prop.get("src")
                or prop.get("datetime")
                or prop.get_text(strip=True)
            )

        if name in item:
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
    og = {}
    for tag in soup.find_all("meta", attrs={"property": True}):
        prop = tag.get("property", "")
        if prop.startswith("og:") and tag.get("content"):
            og[prop] = tag["content"]
    return og


def _extract_twitter_card(soup: BeautifulSoup) -> dict:
    tc = {}
    for tag in soup.find_all("meta", attrs={"name": True}):
        name = tag.get("name", "")
        if name.startswith("twitter:") and tag.get("content"):
            tc[name] = tag["content"]
    return tc


def _extract_meta_tags(soup: BeautifulSoup) -> dict:
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


def _get_fix_suggestion(field: str) -> str:
    """Return a JSON-LD snippet showing how to fix a missing field."""
    return FIX_SUGGESTIONS.get(field, f'"{field}": "<add value>"')


def _validate_entity(entity: dict) -> dict:
    """Validate a schema.org entity against Rich Results requirements with fix suggestions."""
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
            errors.append({
                "field": field,
                "message": f"Missing required field '{field}'",
                "severity": "error",
                "fix": _get_fix_suggestion(field),
            })

    # Check recommended fields
    recommended = spec.get("recommended", [])
    for field in recommended:
        if not _has_field(entity, field):
            warnings.append({
                "field": field,
                "message": f"Missing recommended field '{field}'",
                "severity": "warning",
                "fix": _get_fix_suggestion(field),
            })

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
                            errors.append({
                                "field": f"{parent_key}.{field}",
                                "message": f"Missing required field '{parent_key}.{field}'",
                                "severity": "error",
                                "fix": _get_fix_suggestion(field),
                            })

    # Check FAQ special case
    if category == "FAQ" and "question_required" in spec:
        main_entity = entity.get("mainEntity", [])
        if isinstance(main_entity, list) and main_entity:
            sample = main_entity[0] if isinstance(main_entity[0], dict) else {}
            for field in spec["question_required"]:
                if not _has_field(sample, field):
                    errors.append({
                        "field": f"mainEntity[].{field}",
                        "message": f"FAQ question missing required field '{field}'",
                        "severity": "error",
                        "fix": _get_fix_suggestion(field),
                    })

    # Score: 1.0 = all required present, weighted (required=3x, recommended=1x)
    required_weight = 3
    total_weight = len(required) * required_weight + len(recommended)
    if total_weight > 0:
        error_penalty = len(errors) * required_weight
        warning_penalty = len(warnings)
        present_weight = total_weight - error_penalty - warning_penalty
        score = round(max(0, present_weight / total_weight), 2)
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
    """Extract ALL structured data from a URL with validation and fix suggestions."""
    html, final_url = await _fetch_page(url)
    return _extract_and_validate(html, final_url)


def _extract_and_validate(html: str, source_url: str) -> dict:
    """Core extraction + validation logic shared by URL and raw-HTML endpoints."""
    soup = BeautifulSoup(html, "lxml")

    json_ld_entities = _extract_json_ld(soup)
    microdata_entities = _extract_microdata(soup)
    open_graph = _extract_open_graph(soup)
    twitter_card = _extract_twitter_card(soup)
    meta_tags = _extract_meta_tags(soup)

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

    unique_types = list(dict.fromkeys(all_types))
    unique_eligible = list(dict.fromkeys(eligible_types))

    total_entities = len(json_ld_entities) + len(microdata_entities)

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
        "url": source_url,
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
        "source_url": source_url,
    }


async def check_rich_results(url: str) -> dict:
    """Check which Google Rich Result types a page qualifies for."""
    html, final_url = await _fetch_page(url)
    return _check_rich_results_from_html(html, final_url)


def _check_rich_results_from_html(html: str, source_url: str) -> dict:
    """Core Rich Results check shared by URL and raw-HTML endpoints."""
    soup = BeautifulSoup(html, "lxml")

    json_ld_entities = _extract_json_ld(soup)
    microdata_entities = _extract_microdata(soup)
    all_entities = json_ld_entities + microdata_entities

    found_categories = {}
    for entity in all_entities:
        schema_type = entity.get("@type", "")
        category = match_rich_result_type(schema_type)
        if category and category not in found_categories:
            found_categories[category] = entity

    eligible = []
    not_eligible = []

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
        "url": source_url,
        "eligible": eligible,
        "not_eligible": not_eligible,
        "summary": {
            "eligible_count": len(eligible),
            "total_types_checked": len(checked_categories),
            "types_checked": checked_categories,
        },
        "source_url": source_url,
    }


async def validate_raw_html(html: str) -> dict:
    """Validate structured data from raw HTML string (no URL fetch)."""
    return _extract_and_validate(html, "(raw html)")


async def compute_health_score(url: str) -> dict:
    """Compute an overall structured data health score (0-100) with breakdown and top fixes."""
    html, final_url = await _fetch_page(url)
    return _compute_health_from_html(html, final_url)


def _compute_health_from_html(html: str, source_url: str) -> dict:
    """Core health score computation shared by URL and raw-HTML endpoints."""
    soup = BeautifulSoup(html, "lxml")

    json_ld_entities = _extract_json_ld(soup)
    microdata_entities = _extract_microdata(soup)
    open_graph = _extract_open_graph(soup)
    twitter_card = _extract_twitter_card(soup)

    all_entities = json_ld_entities + microdata_entities

    # Rich Results check
    found_categories = {}
    for entity in all_entities:
        schema_type = entity.get("@type", "")
        category = match_rich_result_type(schema_type)
        if category and category not in found_categories:
            found_categories[category] = entity

    eligible_count = 0
    total_errors = 0
    total_warnings = 0
    all_fixes = []

    for category, entity in found_categories.items():
        validation = _validate_entity(entity)
        total_errors += len(validation["errors"])
        total_warnings += len(validation["warnings"])

        if len(validation["errors"]) == 0:
            eligible_count += 1

        # Collect top fixes (from errors first, then warnings)
        for issue in validation["errors"]:
            if issue["fix"] and issue["fix"] not in all_fixes:
                all_fixes.append(issue["fix"])
        for issue in validation["warnings"]:
            if issue["fix"] and issue["fix"] not in all_fixes:
                all_fixes.append(issue["fix"])

    # Also collect fixes from non-found categories (these are the most impactful)
    checked_categories = list(RICH_RESULTS.keys())
    for category in checked_categories:
        if category not in found_categories:
            spec = RICH_RESULTS[category]
            for field in spec.get("required", []):
                fix = _get_fix_suggestion(field)
                if fix and fix not in all_fixes:
                    all_fixes.append(fix)

    # Score calculation (0-100)
    #   30 pts: has any structured data
    #   30 pts: Rich Results eligibility ratio
    #   20 pts: has Open Graph tags
    #   10 pts: has Twitter Card tags
    #   10 pts: no critical errors
    score = 0
    has_sd = bool(json_ld_entities or microdata_entities)
    if has_sd:
        score += 30

    if checked_categories:
        rich_ratio = eligible_count / len(checked_categories)
        score += int(30 * rich_ratio)

    if open_graph:
        og_fields = len(open_graph)
        og_score = min(1.0, og_fields / 4)  # og:title, og:description, og:image, og:type
        score += int(20 * og_score)

    if twitter_card:
        score += 10

    if total_errors == 0 and has_sd:
        score += 10

    score = min(100, score)

    # Grade
    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "url": source_url,
        "score": score,
        "grade": grade,
        "breakdown": {
            "structured_data_present": has_sd,
            "json_ld_count": len(json_ld_entities),
            "microdata_count": len(microdata_entities),
            "has_open_graph": bool(open_graph),
            "has_twitter_card": bool(twitter_card),
            "rich_results_eligible": eligible_count,
            "rich_results_total": len(checked_categories),
            "critical_errors": total_errors,
            "warnings": total_warnings,
        },
        "top_fixes": all_fixes[:10],
        "source_url": source_url,
    }
