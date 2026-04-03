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
    "Organization": {
        "types": ["Organization", "Corporation", "LocalBusiness", "OnlineStore", "NGO", "GovernmentOrganization"],
        "required": ["name", "url"],
        "recommended": ["logo", "contactPoint", "sameAs", "description", "address", "founder", "numberOfEmployees"],
    },
    "Person": {
        "types": ["Person"],
        "required": ["name"],
        "recommended": ["url", "image", "jobTitle", "worksFor", "sameAs", "email", "telephone"],
    },
    "WebSite": {
        "types": ["WebSite"],
        "required": ["name", "url"],
        "recommended": ["description", "potentialAction", "publisher"],
    },
    "WebPage": {
        "types": ["WebPage", "AboutPage", "ContactPage", "CheckoutPage", "CollectionPage", "FAQPage", "ItemPage", "MedicalWebPage", "ProfilePage", "SearchResultsPage"],
        "required": ["name"],
        "recommended": ["description", "url", "breadcrumb", "mainContentOfPage", "author", "datePublished", "dateModified"],
    },
    "ItemList": {
        "types": ["ItemList"],
        "required": ["itemListElement"],
        "recommended": ["numberOfItems", "name", "description"],
    },
    "AggregateRating": {
        "types": ["AggregateRating"],
        "required": ["ratingValue", "bestRating", "ratingCount"],
        "recommended": ["reviewCount"],
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


# ─── Fix Suggestions ──────────────────────────────────────────────
# Each key is a field name. Value is a JSON-LD snippet showing how to add it.

FIX_SUGGESTIONS = {
    "headline": '"headline": "Your Article Title Here"',
    "image": '"image": "https://example.com/image.jpg"',
    "datePublished": '"datePublished": "2026-01-15T08:00:00+00:00"',
    "dateModified": '"dateModified": "2026-03-01T10:00:00+00:00"',
    "author": '"author": { "@type": "Person", "name": "John Doe" }',
    "description": '"description": "A brief description of the content"',
    "mainEntityOfPage": '"mainEntityOfPage": "https://example.com/page-url"',
    "name": '"name": "Your Item Name"',
    "url": '"url": "https://example.com"',
    "brand": '"brand": { "@type": "Brand", "name": "Brand Name" }',
    "offers": '"offers": { "@type": "Offer", "price": "29.99", "priceCurrency": "USD", "availability": "https://schema.org/InStock" }',
    "price": '"price": "29.99"',
    "priceCurrency": '"priceCurrency": "USD"',
    "availability": '"availability": "https://schema.org/InStock"',
    "aggregateRating": '"aggregateRating": { "@type": "AggregateRating", "ratingValue": "4.5", "bestRating": "5", "ratingCount": "120" }',
    "review": '"review": { "@type": "Review", "reviewRating": { "@type": "Rating", "ratingValue": "5" }, "author": { "@type": "Person", "name": "Jane" } }',
    "sku": '"sku": "SKU-12345"',
    "gtin": '"gtin": "0123456789012"',
    "recipeIngredient": '"recipeIngredient": ["2 cups flour", "1 cup sugar", "3 eggs"]',
    "recipeInstructions": '"recipeInstructions": [ { "@type": "HowToStep", "text": "Mix all ingredients." }, { "@type": "HowToStep", "text": "Bake at 350F for 30 min." } ]',
    "totalTime": '"totalTime": "PT1H"',
    "prepTime": '"prepTime": "PT15M"',
    "cookTime": '"cookTime": "PT45M"',
    "recipeYield": '"recipeYield": "8 servings"',
    "recipeCategory": '"recipeCategory": "Dessert"',
    "recipeCuisine": '"recipeCuisine": "American"',
    "nutrition": '"nutrition": { "@type": "NutritionInformation", "calories": "350 calories" }',
    "video": '"video": { "@type": "VideoObject", "name": "How to make it", "thumbnailUrl": "https://example.com/thumb.jpg", "uploadDate": "2026-01-01" }',
    "mainEntity": '"mainEntity": [ { "@type": "Question", "name": "Your question?", "acceptedAnswer": { "@type": "Answer", "text": "Your answer." } } ]',
    "acceptedAnswer": '"acceptedAnswer": { "@type": "Answer", "text": "The answer text." }',
    "step": '"step": [ { "@type": "HowToStep", "text": "Step 1 description" } ]',
    "startDate": '"startDate": "2026-06-15T19:00:00-07:00"',
    "endDate": '"endDate": "2026-06-15T22:00:00-07:00"',
    "location": '"location": { "@type": "Place", "name": "Venue Name", "address": "123 Main St, City" }',
    "performer": '"performer": { "@type": "Person", "name": "Performer Name" }',
    "organizer": '"organizer": { "@type": "Organization", "name": "Organizer Name", "url": "https://example.com" }',
    "eventStatus": '"eventStatus": "https://schema.org/EventScheduled"',
    "eventAttendanceMode": '"eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode"',
    "address": '"address": { "@type": "PostalAddress", "streetAddress": "123 Main St", "addressLocality": "City", "postalCode": "12345", "addressCountry": "US" }',
    "telephone": '"telephone": "+1-555-123-4567"',
    "openingHoursSpecification": '"openingHoursSpecification": { "@type": "OpeningHoursSpecification", "dayOfWeek": "Monday", "opens": "09:00", "closes": "17:00" }',
    "geo": '"geo": { "@type": "GeoCoordinates", "latitude": "40.7128", "longitude": "-74.0060" }',
    "priceRange": '"priceRange": "$$"',
    "itemReviewed": '"itemReviewed": { "@type": "Product", "name": "Product Name" }',
    "reviewRating": '"reviewRating": { "@type": "Rating", "ratingValue": "4", "bestRating": "5" }',
    "reviewBody": '"reviewBody": "Detailed review text goes here."',
    "itemListElement": '"itemListElement": [ { "@type": "ListItem", "position": 1, "name": "Item 1", "url": "https://example.com/1" } ]',
    "numberOfItems": '"numberOfItems": "5"',
    "thumbnailUrl": '"thumbnailUrl": "https://example.com/thumbnail.jpg"',
    "uploadDate": '"uploadDate": "2026-01-15"',
    "contentUrl": '"contentUrl": "https://example.com/video.mp4"',
    "duration": '"duration": "PT5M30S"',
    "embedUrl": '"embedUrl": "https://example.com/embed/video-id"',
    "interactionStatistic": '"interactionStatistic": { "@type": "InteractionCounter", "interactionType": "https://schema.org/WatchAction", "userInteractionCount": "1234" }',
    "operatingSystem": '"operatingSystem": "Android 10+"',
    "applicationCategory": '"applicationCategory": "GameApplication"',
    "provider": '"provider": { "@type": "Organization", "name": "Provider Name", "url": "https://example.com" }',
    "hasCourseInstance": '"hasCourseInstance": { "@type": "CourseInstance", "courseMode": "Online", "startDate": "2026-09-01" }',
    "courseCode": '"courseCode": "CS101"',
    "logo": '"logo": "https://example.com/logo.png"',
    "contactPoint": '"contactPoint": { "@type": "ContactPoint", "telephone": "+1-555-123-4567", "contactType": "customer service" }',
    "sameAs": '"sameAs": "https://twitter.com/example"',
    "founder": '"founder": { "@type": "Person", "name": "Founder Name" }',
    "numberOfEmployees": '"numberOfEmployees": "50"',
    "jobTitle": '"jobTitle": "Software Engineer"',
    "worksFor": '"worksFor": { "@type": "Organization", "name": "Company Name" }',
    "email": '"email": "contact@example.com"',
    "potentialAction": '"potentialAction": { "@type": "SearchAction", "target": "https://example.com/search?q={search_term_string}", "query-input": "required name=search_term_string" }',
    "publisher": '"publisher": { "@type": "Organization", "name": "Publisher Name", "logo": { "@type": "ImageObject", "url": "https://example.com/logo.png" } }',
    "breadcrumb": '"breadcrumb": { "@type": "BreadcrumbList", "itemListElement": [ { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://example.com" } ] }',
    "mainContentOfPage": '"mainContentOfPage": { "@type": "WebPageElement" }',
    "ratingValue": '"ratingValue": "4.5"',
    "bestRating": '"bestRating": "5"',
    "ratingCount": '"ratingCount": "120"',
    "reviewCount": '"reviewCount": "95"',
    "estimatedCost": '"estimatedCost": { "@type": "MonetaryAmount", "currency": "USD", "value": "50" }',
    "supply": '"supply": [ { "@type": "HowToSupply", "name": "Wood screws" } ]',
    "tool": '"tool": [ { "@type": "HowToTool", "name": "Screwdriver" } ]',
}
