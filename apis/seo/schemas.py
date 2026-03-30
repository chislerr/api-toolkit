# Google Rich Results required and recommended fields per schema.org type.
# Based on https://developers.google.com/search/docs/appearance/structured-data
#
# "required" = must be present for Rich Result eligibility
# "recommended" = improves appearance but not required
# Sub-object requirements use nested keys (e.g. "offers_required")

RICH_RESULTS = {
    "Article": {
        "types": ["Article", "NewsArticle", "BlogPosting", "TechArticle", "ScholarlyArticle", "Report"],
        "required": ["headline", "image", "datePublished", "author"],
        "recommended": ["dateModified", "description", "mainEntityOfPage"],
    },
    "Product": {
        "types": ["Product", "IndividualProduct", "ProductModel"],
        "required": ["name", "image"],
        "recommended": ["description", "brand", "offers", "aggregateRating", "review", "sku", "gtin"],
        "offers_required": ["price", "priceCurrency", "availability"],
        "offers_recommended": ["url", "priceValidUntil", "itemCondition"],
    },
    "Recipe": {
        "types": ["Recipe"],
        "required": ["name", "image", "recipeIngredient", "recipeInstructions"],
        "recommended": ["totalTime", "nutrition", "video", "aggregateRating", "author", "prepTime", "cookTime", "recipeYield", "recipeCategory", "recipeCuisine"],
    },
    "FAQ": {
        "types": ["FAQPage"],
        "required": ["mainEntity"],
        "recommended": [],
        "question_required": ["name", "acceptedAnswer"],
    },
    "HowTo": {
        "types": ["HowTo"],
        "required": ["name", "step"],
        "recommended": ["image", "totalTime", "estimatedCost", "supply", "tool"],
    },
    "Event": {
        "types": ["Event", "BusinessEvent", "MusicEvent", "SportsEvent", "Festival"],
        "required": ["name", "startDate", "location"],
        "recommended": ["image", "description", "endDate", "offers", "performer", "organizer", "eventStatus", "eventAttendanceMode"],
    },
    "LocalBusiness": {
        "types": ["LocalBusiness", "Restaurant", "Store", "MedicalBusiness", "LegalService", "FinancialService"],
        "required": ["name", "address"],
        "recommended": ["telephone", "openingHoursSpecification", "image", "geo", "url", "priceRange"],
    },
    "Review": {
        "types": ["Review"],
        "required": ["itemReviewed", "reviewRating", "author"],
        "recommended": ["datePublished", "reviewBody", "name"],
    },
    "BreadcrumbList": {
        "types": ["BreadcrumbList"],
        "required": ["itemListElement"],
        "recommended": [],
    },
    "VideoObject": {
        "types": ["VideoObject"],
        "required": ["name", "description", "thumbnailUrl", "uploadDate"],
        "recommended": ["contentUrl", "duration", "embedUrl", "interactionStatistic"],
    },
    "SoftwareApplication": {
        "types": ["SoftwareApplication", "MobileApplication", "WebApplication"],
        "required": ["name", "offers"],
        "recommended": ["aggregateRating", "operatingSystem", "applicationCategory"],
    },
    "Course": {
        "types": ["Course"],
        "required": ["name", "description", "provider"],
        "recommended": ["offers", "hasCourseInstance", "courseCode"],
    },
}


def match_rich_result_type(schema_type: str) -> str | None:
    """Match a schema.org @type to a Rich Result category. Returns None if no match."""
    if isinstance(schema_type, list):
        for t in schema_type:
            result = match_rich_result_type(t)
            if result:
                return result
        return None

    for category, spec in RICH_RESULTS.items():
        if schema_type in spec["types"]:
            return category
    return None
