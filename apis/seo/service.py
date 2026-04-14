import json
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from apis.seo.schemas import FIX_SUGGESTIONS, RICH_RESULTS, match_rich_result_type
from core.fetch import fetch_html

logger = logging.getLogger("api.seo")


async def _fetch_page(url: str) -> tuple[str, str]:
    fetched = await fetch_html(url, timeout=20.0)
    return fetched.html, fetched.final_url


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    entities: list[dict] = []

    def flatten(node: object) -> list[dict]:
        if isinstance(node, list):
            flat: list[dict] = []
            for item in node:
                flat.extend(flatten(item))
            return flat
        if not isinstance(node, dict):
            return []
        result = flatten(node.get("@graph", [])) if "@graph" in node else [node]
        main_entity = node.get("mainEntity")
        if isinstance(main_entity, (list, dict)):
            result.extend(flatten(main_entity))
        return result

    for script in soup.find_all("script", type="application/ld+json"):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        raw = raw.removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        entities.extend(flatten(data))

    return [entity for entity in entities if isinstance(entity, dict) and entity.get("@type")]


def _extract_microdata(soup: BeautifulSoup) -> list[dict]:
    items = []
    for scope in soup.find_all(attrs={"itemscope": True}):
        if scope.find_parent(attrs={"itemscope": True}):
            continue
        item = _parse_microdata_item(scope)
        if item:
            items.append(item)
    return items


def _parse_microdata_item(element) -> dict:
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


def _extract_meta_tags(soup: BeautifulSoup, source_url: str) -> dict:
    def meta(names):
        for name in names:
            tag = soup.find("meta", attrs={"name": name}) or soup.find(
                "meta", attrs={"property": name}
            )
            if tag and tag.get("content"):
                return tag["content"]
        return ""

    canonical = ""
    link = soup.find("link", rel="canonical")
    if link and link.get("href"):
        canonical = urljoin(source_url, link["href"])

    return {
        "title": soup.title.string.strip() if soup.title and soup.title.string else "",
        "description": meta(["description"]),
        "canonical": canonical,
        "robots": meta(["robots"]),
        "language": soup.find("html").get("lang", "") if soup.find("html") else "",
    }


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_value(item) for item in value.values())
    return True


def _has_field(entity: dict, field: str) -> bool:
    values = [entity]
    for part in field.split("."):
        next_values = []
        for value in values:
            if isinstance(value, list):
                next_values.extend(value)
                continue
            if isinstance(value, dict) and part in value:
                next_values.append(value[part])
        if not next_values:
            return False
        values = next_values
    return any(_has_value(value) for value in values)


def _get_fix_suggestion(field: str) -> str:
    return FIX_SUGGESTIONS.get(field, f'"{field}": "<add value>"')


def _validate_entity(entity: dict) -> dict:
    schema_type = entity.get("@type", "")
    category = match_rich_result_type(schema_type)
    if not category:
        return {"type": schema_type, "rich_result_category": None, "errors": [], "warnings": [], "score": None}

    spec = RICH_RESULTS[category]
    errors = []
    warnings = []

    for field in spec.get("required", []):
        if not _has_field(entity, field):
            errors.append({"field": field, "message": f"Missing required field '{field}'", "severity": "error", "fix": _get_fix_suggestion(field)})
    for field in spec.get("recommended", []):
        if not _has_field(entity, field):
            warnings.append({"field": field, "message": f"Missing recommended field '{field}'", "severity": "warning", "fix": _get_fix_suggestion(field)})

    for key, fields in spec.items():
        if not key.endswith("_required"):
            continue
        parent = key.replace("_required", "")
        if _has_field(entity, parent):
            for field in fields:
                nested = f"{parent}.{field}"
                if not _has_field(entity, nested):
                    errors.append({"field": nested, "message": f"Missing required field '{nested}'", "severity": "error", "fix": _get_fix_suggestion(field)})
    for key, fields in spec.items():
        if not key.endswith("_recommended"):
            continue
        parent = key.replace("_recommended", "")
        if _has_field(entity, parent):
            for field in fields:
                nested = f"{parent}.{field}"
                if not _has_field(entity, nested):
                    warnings.append({"field": nested, "message": f"Missing recommended field '{nested}'", "severity": "warning", "fix": _get_fix_suggestion(field)})

    if category == "FAQ" and _has_field(entity, "mainEntity"):
        questions = entity.get("mainEntity") or []
        if not isinstance(questions, list):
            questions = [questions]
        for index, question in enumerate([q for q in questions if isinstance(q, dict)]):
            if not _has_field(question, "name"):
                errors.append({"field": f"mainEntity[{index}].name", "message": "FAQ question is missing 'name'", "severity": "error", "fix": _get_fix_suggestion("name")})
            if not _has_field(question, "acceptedAnswer"):
                errors.append({"field": f"mainEntity[{index}].acceptedAnswer", "message": "FAQ question is missing 'acceptedAnswer'", "severity": "error", "fix": _get_fix_suggestion("acceptedAnswer")})
            elif not _has_field(question, "acceptedAnswer.text"):
                errors.append({"field": f"mainEntity[{index}].acceptedAnswer.text", "message": "FAQ answer is missing 'text'", "severity": "error", "fix": _get_fix_suggestion("acceptedAnswer")})

    required_weight = 3
    total_weight = len(spec.get("required", [])) * required_weight + len(spec.get("recommended", []))
    score = 1.0 if total_weight == 0 else round(max(0, (total_weight - len(errors) * required_weight - len(warnings)) / total_weight), 2)
    return {"type": schema_type, "rich_result_category": category, "errors": errors, "warnings": warnings, "score": score}


def _extract_and_validate(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    json_ld_entities = _extract_json_ld(soup)
    microdata_entities = _extract_microdata(soup)
    open_graph = _extract_open_graph(soup)
    twitter_card = _extract_twitter_card(soup)
    meta_tags = _extract_meta_tags(soup, source_url)

    validated_json_ld = []
    validated_microdata = []
    all_types = []
    all_errors = 0
    all_warnings = 0
    eligible_types = []

    for entity in json_ld_entities:
        validation = _validate_entity(entity)
        validated_json_ld.append({**entity, "_validation": validation})
        schema_type = entity.get("@type", "unknown")
        all_types.extend(schema_type if isinstance(schema_type, list) else [schema_type])
        all_errors += len(validation["errors"])
        all_warnings += len(validation["warnings"])
        if validation["rich_result_category"] and not validation["errors"]:
            eligible_types.append(validation["rich_result_category"])

    for entity in microdata_entities:
        validation = _validate_entity(entity)
        validated_microdata.append({**entity, "_validation": validation})
        all_types.extend(entity.get("@type") if isinstance(entity.get("@type"), list) else [entity.get("@type", "unknown")])
        all_errors += len(validation["errors"])
        all_warnings += len(validation["warnings"])
        if validation["rich_result_category"] and not validation["errors"]:
            eligible_types.append(validation["rich_result_category"])

    scored_entities = [
        entity.get("_validation", {}).get("score")
        for entity in validated_json_ld + validated_microdata
        if entity.get("_validation", {}).get("score") is not None
    ]
    overall_score = round(sum(scored_entities) / len(scored_entities), 2) if scored_entities else 0.0

    return {
        "url": source_url,
        "json_ld": validated_json_ld,
        "microdata": validated_microdata,
        "open_graph": open_graph,
        "twitter_card": twitter_card,
        "meta_tags": meta_tags,
        "summary": {
            "total_entities": len(json_ld_entities) + len(microdata_entities),
            "types_found": list(dict.fromkeys(all_types)),
            "rich_results_eligible": list(dict.fromkeys(eligible_types)),
            "overall_score": overall_score,
            "critical_errors": all_errors,
            "warnings": all_warnings,
        },
        "source_url": source_url,
    }


async def extract_structured_data(url: str) -> dict:
    html, final_url = await _fetch_page(url)
    return _extract_and_validate(html, final_url)


def _entity_field_status(category: str, entity: dict) -> tuple[list[str], list[str], list[str]]:
    spec = RICH_RESULTS[category]
    present = []
    missing = []
    recommended_missing = []
    for field in spec.get("required", []):
        (present if _has_field(entity, field) else missing).append(field)
    for field in spec.get("recommended", []):
        if not _has_field(entity, field):
            recommended_missing.append(field)
    for key, fields in spec.items():
        if key.endswith("_required") and _has_field(entity, key.replace("_required", "")):
            for field in fields:
                nested = f"{key.replace('_required', '')}.{field}"
                (present if _has_field(entity, nested) else missing).append(nested)
        if key.endswith("_recommended") and _has_field(entity, key.replace("_recommended", "")):
            for field in fields:
                nested = f"{key.replace('_recommended', '')}.{field}"
                if not _has_field(entity, nested):
                    recommended_missing.append(nested)
    return present, missing, recommended_missing


def _check_rich_results_from_html(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    entities = _extract_json_ld(soup) + _extract_microdata(soup)
    found_categories = {}
    for entity in entities:
        category = match_rich_result_type(entity.get("@type", ""))
        if category and category not in found_categories:
            found_categories[category] = entity

    eligible = []
    not_eligible = []
    for category, entity in found_categories.items():
        present, missing, recommended_missing = _entity_field_status(category, entity)
        entry = {"type": category, "fields_present": present, "fields_missing": missing, "fields_recommended": recommended_missing}
        if not missing:
            entry["status"] = "eligible"
            eligible.append(entry)
        else:
            entry["status"] = "missing_required"
            not_eligible.append(entry)

    checked_categories = list(RICH_RESULTS.keys())
    for category in checked_categories:
        if category not in found_categories:
            not_eligible.append({"type": category, "status": "not_found", "fields_present": [], "fields_missing": RICH_RESULTS[category].get("required", []), "fields_recommended": RICH_RESULTS[category].get("recommended", [])})

    return {
        "url": source_url,
        "eligible": eligible,
        "not_eligible": not_eligible,
        "summary": {"eligible_count": len(eligible), "total_types_checked": len(checked_categories), "types_checked": checked_categories},
        "source_url": source_url,
    }


async def check_rich_results(url: str) -> dict:
    html, final_url = await _fetch_page(url)
    return _check_rich_results_from_html(html, final_url)


async def validate_raw_html(html: str) -> dict:
    return _extract_and_validate(html, "(raw html)")


def _compute_health_from_html(html: str, source_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    json_ld_entities = _extract_json_ld(soup)
    microdata_entities = _extract_microdata(soup)
    open_graph = _extract_open_graph(soup)
    twitter_card = _extract_twitter_card(soup)
    meta_tags = _extract_meta_tags(soup, source_url)

    all_entities = json_ld_entities + microdata_entities
    validations = [_validate_entity(entity) for entity in all_entities]
    relevant = [validation for validation in validations if validation["rich_result_category"]]
    relevant_categories = list(dict.fromkeys([validation["rich_result_category"] for validation in relevant]))
    eligible_count = len([validation for validation in relevant if not validation["errors"]])
    total_errors = sum(len(validation["errors"]) for validation in relevant)
    total_warnings = sum(len(validation["warnings"]) for validation in relevant)
    average_schema_score = round(sum(validation["score"] for validation in relevant) / len(relevant), 2) if relevant else 0.0
    eligibility_ratio = eligible_count / len(relevant) if relevant else 0.0

    og_fields = sum(1 for key in ("og:title", "og:description", "og:image", "og:type") if open_graph.get(key))
    twitter_fields = sum(1 for key in ("twitter:card", "twitter:title", "twitter:description", "twitter:image") if twitter_card.get(key))
    meta_fields = sum(1 for key in ("title", "description", "canonical", "language") if meta_tags.get(key))

    score = round(
        average_schema_score * 40
        + eligibility_ratio * 25
        + min(1.0, og_fields / 4) * 15
        + min(1.0, twitter_fields / 4) * 10
        + min(1.0, meta_fields / 4) * 10
    )
    score = min(100, score)

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

    top_fixes = []
    for validation in relevant:
        for issue in validation["errors"] + validation["warnings"]:
            fix = issue.get("fix")
            if fix and fix not in top_fixes:
                top_fixes.append(fix)
    if not relevant_categories:
        top_fixes.extend(
            [
                'Add a JSON-LD entity that matches the page type.',
                _get_fix_suggestion("headline"),
                _get_fix_suggestion("name"),
            ]
        )
    if not open_graph:
        top_fixes.extend([_get_fix_suggestion("image"), _get_fix_suggestion("description")])
    if "twitter:card" not in twitter_card:
        top_fixes.append('"twitter:card": "summary_large_image"')
    if not meta_tags.get("canonical"):
        top_fixes.append('Add <link rel="canonical" href="https://example.com/page" />')

    deduped_fixes = []
    for fix in top_fixes:
        if fix not in deduped_fixes:
            deduped_fixes.append(fix)

    return {
        "url": source_url,
        "score": score,
        "grade": grade,
        "breakdown": {
            "structured_data_present": bool(all_entities),
            "json_ld_count": len(json_ld_entities),
            "microdata_count": len(microdata_entities),
            "has_open_graph": bool(open_graph),
            "has_twitter_card": bool(twitter_card),
            "rich_results_eligible": eligible_count,
            "rich_results_total": len(relevant),
            "critical_errors": total_errors,
            "warnings": total_warnings,
        },
        "top_fixes": deduped_fixes[:10],
        "source_url": source_url,
    }


async def compute_health_score(url: str) -> dict:
    html, final_url = await _fetch_page(url)
    return _compute_health_from_html(html, final_url)
