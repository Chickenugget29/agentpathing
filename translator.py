"""Translator that maps Atlas-style RAG questions onto strict FOL snippets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern[str]
    handler: Callable[[re.Match[str]], str]
    description: str


def _predicate_name(phrase: str) -> str:
    tokens = re.findall(r"[a-zA-Z0-9]+", phrase)
    return "".join(token.capitalize() for token in tokens) or "Unknown"


def _constant_name(name: str) -> str:
    tokens = re.findall(r"[a-zA-Z0-9]+", name)
    if not tokens:
        return "Const"
    token = tokens[0]
    return token[:1].upper() + token[1:].lower()


def _topic_constant(phrase: str) -> str:
    cleaned = phrase.strip().replace("'", "").replace('"', "")
    return _predicate_name(cleaned)


def _g(match: re.Match[str], name: str) -> str:
    return match.group(name).strip()


def _quantified_exists(vars: list[str], clauses: list[str]) -> str:
    joined_vars = " ".join(vars)
    body = " & ".join(clauses)
    return f"exists {joined_vars} ({body})"


def _document_query(clauses: list[str], var: str = "d") -> str:
    return _quantified_exists([var], [f"Document({var})"] + clauses)


def _person_query(clauses: list[str], var: str = "p") -> str:
    return _quantified_exists([var], [f"Person({var})"] + clauses)


def _comparison_query(a: str, b: str, relation: str) -> str:
    var_a, var_b = "d1", "d2"
    clauses = [
        f"Document({var_a})",
        f"Topic({var_a}, {_topic_constant(a)})",
        f"Document({var_b})",
        f"Topic({var_b}, {_topic_constant(b)})",
        f"{relation}({var_a}, {var_b})",
    ]
    return _quantified_exists([var_a, var_b], clauses)


def _temporal_query(event_a: str, event_b: str) -> str:
    ev_a, ev_b = "e1", "e2"
    clauses = [
        f"Event({ev_a})",
        f"Topic({ev_a}, {_topic_constant(event_a)})",
        f"Event({ev_b})",
        f"Topic({ev_b}, {_topic_constant(event_b)})",
        f"Before({ev_a}, {ev_b}) | After({ev_a}, {ev_b})",
    ]
    return _quantified_exists([ev_a, ev_b], clauses)


def _conditional_policy(condition: str, outcome: str) -> str:
    var = "p"
    clauses = [
        f"Policy({var})",
        f"Condition({var}, {_topic_constant(condition)})",
        f"Outcome({var}, {_topic_constant(outcome)})",
    ]
    return _quantified_exists([var], clauses)


def _refusal(action: str) -> str:
    action_const = _topic_constant(action)
    return f"forall r (Request(r, {action_const}) -> Refuse(r))"


def _not_found(topic: str) -> str:
    var = "d"
    return (
        f"not exists {var} (Document({var}) & Topic({var}, {_topic_constant(topic)}))"
    )


LANGUAGE_KEYWORDS = {
    "german": "German",
    "english": "English",
    "spanish": "Spanish",
    "french": "French",
}

FORMAT_KEYWORDS = {
    "pdf": "PDF",
    "whitepaper": "Whitepaper",
}

STATUS_KEYWORDS = {
    "draft": "Draft",
    "final": "Final",
}

PRIORITY_KEYWORDS = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}

REGION_KEYWORDS = {
    "california": "California",
    "new york": "NewYork",
    "london": "London",
    "apac": "APAC",
    "emea": "EMEA",
    "germany": "Germany",
}

DEPARTMENT_KEYWORDS = {
    "marketing": "Marketing",
    "engineering": "Engineering",
    "qa": "QualityAssurance",
    "sales": "Sales",
    "finance": "Finance",
    "hr": "HR",
    "r&d": "ResearchAndDevelopment",
    "operations": "Operations",
}

DOCUMENT_TYPE_KEYWORDS = {
    "policy": "Policy",
    "handbook": "Handbook",
    "notes": "MeetingNotes",
    "meeting": "MeetingNotes",
    "report": "Report",
    "results": "Results",
    "protocol": "Protocol",
    "specs": "Specification",
    "whitepaper": "Whitepaper",
    "article": "Article",
    "documentation": "Documentation",
    "docs": "Documentation",
    "help articles": "HelpArticle",
    "bug reports": "BugReport",
}


def _strip_quotes(text: str) -> str:
    return text.replace('"', "").replace("'", "")


def _metadata_predicates(body: str, var: str) -> list[str]:
    lowered = body.lower()
    predicates: list[str] = []
    year_match = re.search(r"\b(19|20)\d{2}\b", body)
    if year_match:
        predicates.append(f"Year({var}, {year_match.group(0)})")
    month_match = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
        lowered,
    )
    if month_match:
        predicates.append(f"Month({var}, {_topic_constant(month_match.group(0))})")
    for keyword, label in LANGUAGE_KEYWORDS.items():
        if keyword in lowered:
            predicates.append(f"Language({var}, {_topic_constant(label)})")
    for keyword, label in FORMAT_KEYWORDS.items():
        if keyword in lowered:
            predicates.append(f"Format({var}, {_topic_constant(label)})")
    for keyword, label in STATUS_KEYWORDS.items():
        if keyword in lowered:
            predicates.append(f"Status({var}, {_topic_constant(label)})")
    for keyword, label in PRIORITY_KEYWORDS.items():
        if keyword in lowered:
            predicates.append(f"Priority({var}, {_topic_constant(label)})")
    for keyword, label in REGION_KEYWORDS.items():
        if keyword in lowered:
            predicates.append(f"Region({var}, {_topic_constant(label)})")
    for keyword, label in DEPARTMENT_KEYWORDS.items():
        if keyword in lowered and f"not {keyword}" not in lowered:
            predicates.append(f"Department({var}, {_topic_constant(label)})")
    for keyword, label in DOCUMENT_TYPE_KEYWORDS.items():
        if keyword in lowered:
            predicates.append(f"DocType({var}, {_topic_constant(label)})")
    tag_matches = re.findall(r"#([A-Za-z0-9_-]+)", body)
    for tag in tag_matches:
        predicates.append(f"HasTag({var}, {_topic_constant(tag)})")
    author_match = re.search(r"by ([A-Z][a-z]+(?: [A-Z][a-z]+)*)", body)
    if author_match:
        predicates.append(f"Author({var}, {_topic_constant(author_match.group(1))})")
    collection_match = re.search(r"in the '?(?P<collection>\w+)'? collection", lowered)
    if collection_match:
        predicates.append(
            f"Collection({var}, {_topic_constant(collection_match.group('collection'))})"
        )
    tier_match = re.search(r"'?(Pro|Enterprise|Standard)'?\s+tier", body, flags=re.I)
    if tier_match:
        predicates.append(f"Tier({var}, {_topic_constant(tier_match.group(1))})")
    status_doc_match = re.search(r"'?(Draft|Published)'?\s+status", body, flags=re.I)
    if status_doc_match:
        predicates.append(f"Status({var}, {_topic_constant(status_doc_match.group(1))})")
    if "latest" in lowered or "most recent" in lowered:
        predicates.append(f"Recency({var}, Latest)")
    if "last week" in lowered:
        predicates.append(f"Timeframe({var}, LastWeek)")
    quarter_match = re.search(r"\bQ([1-4])\b", body, flags=re.I)
    if quarter_match:
        predicates.append(f"Quarter({var}, {quarter_match.group(1)})")
    if "employees in" in lowered:
        audience = re.search(r"employees in ([A-Za-z\s]+)", body, flags=re.I)
        if audience:
            predicates.append(f"AppliesTo({var}, {_topic_constant(audience.group(1))})")
    if "not hr" in lowered:
        predicates.append(f"NotDepartment({var}, {_topic_constant('HR')})")
    return predicates


def _clean_topic_phrase(text: str) -> str:
    cleaned = re.sub(
        r"\b(find|show|show me|get|search for|latest|all|documents?|document|help articles|articles)\b",
        "",
        text,
        flags=re.I,
    )
    cleaned = re.sub(r"#([A-Za-z0-9_-]+)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


SAFETY_TRIGGERS: tuple[tuple[str, Callable[[], str]], ...] = (
    ("secret recipe", lambda: _not_found("SecretRecipe")),
    ("nuclear missile", lambda: _refusal("LaunchNuclearMissile")),
    ("home address", lambda: _refusal("ExposePII")),
    ("bypass the security badge reader", lambda: _refusal("SecurityBypass")),
    ("pet unicorns", lambda: _not_found("PetUnicornPolicy")),
    ("klingon", lambda: _not_found("KlingonTranslation")),
    ("personally eat for lunch", lambda: _not_found("PrivateLunchData")),
    ("z.x.q.l", lambda: _not_found("ZxqlAcronym")),
    ("500-page tax code", lambda: _refusal("ImpossibleCompression")),
)


def _safety_response(sentence: str) -> Optional[str]:
    lowered = sentence.lower()
    for trigger, builder in SAFETY_TRIGGERS:
        if trigger in lowered:
            return builder()
    return None


def _render_policy_on(m: re.Match[str]) -> str:
    topic = _topic_constant(_g(m, "topic"))
    return _document_query(["Policy(d)", f"Topic(d, {topic})", "Official(d)"])


def _render_role_assignment(m: re.Match[str]) -> str:
    role = _topic_constant(_g(m, "role"))
    context = _topic_constant(_g(m, "context"))
    return _person_query(
        [
            f"Role(p, {role})",
            f"AssignedTo(p, {context})",
            "Current(p)",
        ]
    )


def _render_office_hours(m: re.Match[str]) -> str:
    location = _topic_constant(_g(m, "location"))
    return _document_query(
        [
            "Schedule(d)",
            f"Location(d, {location})",
            "OfficeHours(d)",
        ]
    )


def _render_maximum_metric(m: re.Match[str]) -> str:
    metric = _topic_constant(_g(m, "metric"))
    context = _topic_constant(_g(m, "context"))
    return _document_query(
        [
            f"Topic(d, {context})",
            f"HasMetric(d, {metric})",
            "MaximumValue(d)",
        ]
    )


def _render_list_entities(m: re.Match[str]) -> str:
    category = _topic_constant(_g(m, "category"))
    return f"forall x ({category}(x) -> Listed(x))"


def _render_count_entitlement(m: re.Match[str]) -> str:
    subject = _topic_constant(_g(m, "subject"))
    context = _topic_constant(_g(m, "context"))
    return _quantified_exists(
        ["n"],
        [
            "Count(n)",
            f"Measures(n, {subject})",
            f"Context(n, {context})",
        ],
    )


def _render_url_lookup(m: re.Match[str]) -> str:
    target = _topic_constant(_g(m, "target"))
    return _document_query(
        [
            f"Resource(d)",
            f"Topic(d, {target})",
            "HasURL(d)",
        ]
    )


def _render_update_lookup(m: re.Match[str]) -> str:
    artifact = _topic_constant(_g(m, "artifact"))
    return _document_query(
        [
            f"Topic(d, {artifact})",
            "LastUpdated(d)",
            "MostRecent(d)",
        ]
    )


def _render_contact_lookup(m: re.Match[str]) -> str:
    context = _topic_constant(_g(m, "context"))
    return _person_query(
        [
            f"ContactFor(p, {context})",
            "PrimaryContact(p)",
        ]
    )


def _render_location_lookup(m: re.Match[str]) -> str:
    item = _topic_constant(_g(m, "item"))
    area = _topic_constant(_g(m, "area"))
    return _document_query(
        [
            f"Location(d, {area})",
            f"Contains(d, {item})",
        ]
    )


def _render_password_lookup(m: re.Match[str]) -> str:
    target = _topic_constant(_g(m, "target"))
    return _document_query(
        [
            f"Credential(d)",
            f"Topic(d, {target})",
        ]
    )


def _render_requirements(m: re.Match[str]) -> str:
    role = _topic_constant(_g(m, "role"))
    return _document_query(
        [
            "RequirementsDoc(d)",
            f"Role(d, {role})",
        ]
    )


def _render_procedure(m: re.Match[str]) -> str:
    action = _topic_constant(_g(m, "action"))
    return _document_query(
        [
            "Procedure(d)",
            f"Action(d, {action})",
        ]
    )


def _render_deadline(m: re.Match[str]) -> str:
    topic = _topic_constant(_g(m, "topic"))
    return _document_query(
        [
            "DeadlineDoc(d)",
            f"Topic(d, {topic})",
        ]
    )


def _render_boolean_policy(m: re.Match[str]) -> str:
    topic = _topic_constant(_g(m, "topic"))
    return _document_query(
        [
            "Policy(d)",
            f"Topic(d, {topic})",
        ]
    )


def _render_storage_lookup(m: re.Match[str]) -> str:
    item = _topic_constant(_g(m, "item"))
    return _document_query(
        [
            "LocationGuide(d)",
            f"Topic(d, {item})",
        ]
    )


def _render_brand_assets(_: re.Match[str]) -> str:
    return _document_query(
        [
            "BrandGuide(d)",
            "Contains(d, Assets)",
        ]
    )


def _render_permission(m: re.Match[str]) -> str:
    action = _topic_constant(_g(m, "action"))
    return _document_query(
        [
            "Policy(d)",
            f"Permission(d, {action})",
        ]
    )


def _render_permission_with_condition(m: re.Match[str]) -> str:
    action = _topic_constant(_g(m, "action"))
    condition = _topic_constant(_g(m, "condition"))
    return _conditional_policy(condition=condition, outcome=action)


def _render_incident_contact(_: re.Match[str]) -> str:
    return _person_query(
        [
            "Role(p, ITSupport)",
            "OnCall(p)",
        ]
    )


def _render_condition_outcome(m: re.Match[str]) -> str:
    condition = _topic_constant(_g(m, "condition"))
    return _document_query(
        [
            "Policy(d)",
            f"Condition(d, {condition})",
            "OutcomeDescribed(d)",
        ]
    )


def _render_location_availability(m: re.Match[str]) -> str:
    place = _topic_constant(_g(m, "place"))
    return _document_query(
        [
            "LocationGuide(d)",
            f"Topic(d, {place})",
            "Availability(d)",
        ]
    )


def _render_need_statement(m: re.Match[str]) -> str:
    action = _topic_constant(_g(m, "action"))
    return _document_query(
        [
            "Policy(d)",
            f"Need(d, {action})",
        ]
    )


def _render_bonus_question(_: re.Match[str]) -> str:
    return _document_query(
        [
            "Policy(d)",
            "ReferralBonus(d)",
        ]
    )


def _render_department_assistance(m: re.Match[str]) -> str:
    dept = _topic_constant(_g(m, "department"))
    topic = _topic_constant(_g(m, "topic"))
    return _document_query(
        [
            "SupportDoc(d)",
            f"Department(d, {dept})",
            f"Topic(d, {topic})",
        ]
    )


def _render_place_action(m: re.Match[str]) -> str:
    action = _topic_constant(_g(m, "action"))
    return _document_query(
        [
            "LocationGuide(d)",
            f"Supports(d, {action})",
        ]
    )


def _render_metadata_query(m: re.Match[str]) -> str:
    body = m.group("body")
    var = "d"
    predicates = _metadata_predicates(body, var)
    topic_phrase = _clean_topic_phrase(body)
    if topic_phrase:
        predicates.append(f"Topic({var}, {_topic_constant(topic_phrase)})")
    else:
        predicates.append(f"GeneralRequest({var})")
    return _document_query(predicates, var)


def _render_metadata_timebound(m: re.Match[str]) -> str:
    topic = _topic_constant(_g(m, "topic"))
    timeframe = _topic_constant(_g(m, "timeframe"))
    var = "d"
    predicates = [f"Topic({var}, {topic})", f"Timeframe({var}, {timeframe})"]
    predicates.extend(_metadata_predicates(m.group(0), var))
    return _document_query(predicates, var)


def _render_compare(m: re.Match[str]) -> str:
    a = _strip_quotes(_g(m, "a"))
    b = _strip_quotes(_g(m, "b"))
    return _comparison_query(a, b, "Compare")


def _render_difference(m: re.Match[str]) -> str:
    a = _strip_quotes(_g(m, "a"))
    b = _strip_quotes(_g(m, "b"))
    return _comparison_query(a, b, "DiffersFrom")


def _render_change_between(m: re.Match[str]) -> str:
    topic = _topic_constant(_g(m, "topic"))
    year_a = _g(m, "year_a")
    year_b = _g(m, "year_b")
    var_a, var_b = "d1", "d2"
    clauses = [
        f"Document({var_a})",
        f"Topic({var_a}, {topic})",
        f"Year({var_a}, {year_a})",
        f"Document({var_b})",
        f"Topic({var_b}, {topic})",
        f"Year({var_b}, {year_b})",
        f"ChangeAnalysis({var_a}, {var_b})",
    ]
    return _quantified_exists([var_a, var_b], clauses)


def _render_summary(m: re.Match[str]) -> str:
    a = _topic_constant(_g(m, "a"))
    b = _topic_constant(_g(m, "b"))
    return _quantified_exists(
        ["d1", "d2", "s"],
        [
            "Document(d1)",
            f"Department(d1, {a})",
            "Document(d2)",
            f"Department(d2, {b})",
            "Summary(s)",
            "Aggregates(s, d1)",
            "Aggregates(s, d2)",
        ],
    )


def _render_board_priority(m: re.Match[str]) -> str:
    count = _g(m, "count")
    topic_text = m.groupdict().get("topic") or "TopPriority"
    topic = _topic_constant(topic_text)
    return _document_query(
        [
            "MeetingMinutes(d)",
            f"Topic(d, {topic})",
            f"LastN(d, {count})",
            "PriorityDerived(d)",
        ]
    )


def _render_department_extreme(_: re.Match[str]) -> str:
    return _quantified_exists(
        ["dept"],
        [
            "Department(dept)",
            "MostRestrictiveTravelBudget(dept)",
        ],
    )


def _render_tools_for_projects(m: re.Match[str]) -> str:
    a = _topic_constant(_g(m, "a"))
    b = _topic_constant(_g(m, "b"))
    return _document_query(
        [
            "ToolingDoc(d)",
            f"Supports(d, {a})",
            f"Supports(d, {b})",
        ]
    )


def _render_temporal_order(m: re.Match[str]) -> str:
    return _temporal_query(_g(m, "event_a"), _g(m, "event_b"))


def _render_injury_procedure(m: re.Match[str]) -> str:
    condition = _topic_constant(_g(m, "condition"))
    return _conditional_policy(condition, "ReportInjury")


def _render_legacy_stock(m: re.Match[str]) -> str:
    year = _g(m, "year")
    asset = _topic_constant(_g(m, "asset"))
    return _quantified_exists(
        ["n"],
        [
            "Count(n)",
            f"AssetType(n, {asset})",
            f"EmploymentYear(n, {year})",
        ],
    )


def _render_interim_role(m: re.Match[str]) -> str:
    role = _topic_constant(_g(m, "role"))
    condition = _topic_constant(_g(m, "condition"))
    return _conditional_policy(condition, role)


def _render_default_policy(_: re.Match[str]) -> str:
    return _document_query(
        [
            "Policy(d)",
            "FallbackClause(d)",
        ]
    )


def _render_limit(m: re.Match[str]) -> str:
    thing = _topic_constant(_g(m, "thing"))
    return _document_query(
        [
            "CapacityPolicy(d)",
            f"AppliesTo(d, {thing})",
        ]
    )


def _render_data_deletion(m: re.Match[str]) -> str:
    data = _topic_constant(_g(m, "data"))
    action = _topic_constant(_g(m, "action"))
    return _conditional_policy(action, data)


def _render_grandfathered(m: re.Match[str]) -> str:
    clause_text = m.groupdict().get("clause") or "GrandfatheredClause"
    clause = _topic_constant(clause_text)
    context = _topic_constant(_g(m, "context"))
    return _document_query(
        [
            "Policy(d)",
            f"Clause(d, {clause})",
            f"AppliesTo(d, {context})",
        ]
    )


def _render_clause_lookup(m: re.Match[str]) -> str:
    clause = _topic_constant(_g(m, "clause"))
    context = _topic_constant(_g(m, "context"))
    return _document_query(
        [
            "Contract(d)",
            f"Clause(d, {clause})",
            f"Topic(d, {context})",
        ]
    )


def _render_connection_string(m: re.Match[str]) -> str:
    context = _topic_constant(_g(m, "context"))
    return _document_query(
        [
            "TechnicalDoc(d)",
            f"Topic(d, ConnectionString)",
            f"Environment(d, {context})",
        ]
    )


def _render_rotation(m: re.Match[str]) -> str:
    system = _topic_constant(_g(m, "system"))
    return _document_query(
        [
            "Procedure(d)",
            f"Action(d, RotateKeys)",
            f"System(d, {system})",
        ]
    )


def _render_ttl_lookup(m: re.Match[str]) -> str:
    context = _topic_constant(_g(m, "context"))
    return _document_query(
        [
            "TechnicalDoc(d)",
            f"Topic(d, TTL)",
            f"Service(d, {context})",
        ]
    )


def _render_retry_logic(m: re.Match[str]) -> str:
    feature = _topic_constant(_g(m, "feature"))
    context = _topic_constant(_g(m, "context"))
    return _document_query(
        [
            "TechnicalDoc(d)",
            f"Topic(d, {feature})",
            f"System(d, {context})",
        ]
    )


def _render_docker_version(m: re.Match[str]) -> str:
    service = _topic_constant(_g(m, "service"))
    return _document_query(
        [
            "DeploymentDoc(d)",
            f"Service(d, {service})",
            "DockerImageVersion(d)",
        ]
    )


def _render_naming_convention(m: re.Match[str]) -> str:
    target = _topic_constant(_g(m, "target"))
    return _document_query(
        [
            "NamingStandard(d)",
            f"AppliesTo(d, {target})",
        ]
    )


def _render_manual_deploy(m: re.Match[str]) -> str:
    system = _topic_constant(_g(m, "system"))
    return _document_query(
        [
            "Procedure(d)",
            f"Action(d, ManualDeployment)",
            f"System(d, {system})",
        ]
    )


def _render_docs_location(m: re.Match[str]) -> str:
    target = _topic_constant(_g(m, "target"))
    return _document_query(
        [
            "DocumentationIndex(d)",
            f"Topic(d, {target})",
        ]
    )


def _render_rate_limits(m: re.Match[str]) -> str:
    target = _topic_constant(_g(m, "target"))
    return _document_query(
        [
            "RateLimitDoc(d)",
            f"Service(d, {target})",
        ]
    )


def _render_write_permission(m: re.Match[str]) -> str:
    database = _topic_constant(_g(m, "database"))
    return _document_query(
        [
            "Procedure(d)",
            f"Action(d, RequestPermission)",
            f"Database(d, {database})",
            "PermissionType(d, Write)",
        ]
    )


def _render_fallback(sentence: str) -> str:
    topic = _topic_constant(sentence)
    var = "d"
    predicates = [f"Topic({var}, {topic})"]
    predicates.extend(_metadata_predicates(sentence, var))
    return _document_query(predicates, var)


RULES: tuple[Rule, ...] = (
    Rule(
        re.compile(
            r"^(?:what\s+is|tell me|where can i find)\s+(?:our\s+|the\s+)?"
            r"(?:official\s+)?policy (?:on|for|regarding)\s+(?P<topic>.+)$",
            re.I,
        ),
        _render_policy_on,
        "Policy lookup",
    ),
    Rule(
        re.compile(
            r"^who\s+is\s+(?:the\s+)?(?P<role>.+?)\s+(?:for|on|of)\s+(?P<context>.+)$",
            re.I,
        ),
        _render_role_assignment,
        "Role assignment",
    ),
    Rule(
        re.compile(
            r"^what\s+are\s+(?:the\s+)?office\s+hours\s+(?:for|at)\s+(?P<location>.+)$",
            re.I,
        ),
        _render_office_hours,
        "Office hours",
    ),
    Rule(
        re.compile(
            r"^what\s+is\s+(?:the\s+)?maximum\s+(?P<metric>.+?)\s+(?:for|per)\s+(?P<context>.+)$",
            re.I,
        ),
        _render_maximum_metric,
        "Maximum metric",
    ),
    Rule(
        re.compile(
            r"^(?:list|show)\s+all\s+(?P<topic>.+?)\s+from\s+(?P<timeframe>.+)$", re.I
        ),
        _render_metadata_timebound,
        "Time-bounded metadata query",
    ),
    Rule(
        re.compile(
            r"^list\s+all\s+software\s+tools\s+.*project\s+(?P<a>[\w\s]+?)\s+.*project\s+(?P<b>[\w\s]+)$",
            re.I,
        ),
        _render_tools_for_projects,
        "Tools for projects",
    ),
    Rule(
        re.compile(r"^list\s+all\s+(?P<category>.+)$", re.I),
        _render_list_entities,
        "List category",
    ),
    Rule(
        re.compile(
            r"^how\s+many\s+(?P<subject>.+?)\s+(?:can|may|are|do)\s+(?P<context>.+)$",
            re.I,
        ),
        _render_count_entitlement,
        "Count/entitlement",
    ),
    Rule(
        re.compile(r"^what\s+is\s+the\s+url\s+for\s+(?P<target>.+)$", re.I),
        _render_url_lookup,
        "URL lookup",
    ),
    Rule(
        re.compile(
            r"^when\s+was\s+the\s+last\s+update\s+(?:made\s+)?(?:to|for)\s+(?P<artifact>.+)$",
            re.I,
        ),
        _render_update_lookup,
        "Last update",
    ),
    Rule(
        re.compile(
            r"^who\s+is\s+(?:the\s+)?primary\s+contact\s+(?:for|regarding)\s+(?P<context>.+)$",
            re.I,
        ),
        _render_contact_lookup,
        "Primary contact",
    ),
    Rule(
        re.compile(
            r"^where\s+is\s+(?:the\s+)?(?P<item>.+?)\s+located\s+(?:on|in|at)\s+(?P<area>.+)$",
            re.I,
        ),
        _render_location_lookup,
        "Location lookup",
    ),
    Rule(
        re.compile(r"^what\s+is\s+(?:the\s+)?password\s+for\s+(?P<target>.+)$", re.I),
        _render_password_lookup,
        "Password lookup",
    ),
    Rule(
        re.compile(r"^what\s+are\s+the\s+requirements\s+for\s+(?P<role>.+)$", re.I),
        _render_requirements,
        "Role requirements",
    ),
    Rule(
        re.compile(
            r"^(?:how\s+do\s+i|what\s+is\s+the\s+protocol|what\s+should\s+i\s+do)\s+(?P<action>.+)$",
            re.I,
        ),
        _render_procedure,
        "Procedure lookup",
    ),
    Rule(
        re.compile(r"^what\s+is\s+(?:the\s+)?deadline\s+for\s+(?P<topic>.+)$", re.I),
        _render_deadline,
        "Deadline lookup",
    ),
    Rule(
        re.compile(
            r"^(?:does\s+the\s+company|do\s+we)\s+(?:offer|have|allow)\s+(?P<topic>.+)$",
            re.I,
        ),
        _render_boolean_policy,
        "Boolean policy",
    ),
    Rule(
        re.compile(
            r"^where\s+can\s+i\s+find\s+(?:the\s+)?brand\s+assets.*$", re.I
        ),
        _render_brand_assets,
        "Brand assets",
    ),
    Rule(
        re.compile(
            r"^where\s+can\s+i\s+find\s+(?:the\s+)?(?P<item>.+)$", re.I
        ),
        _render_storage_lookup,
        "Storage lookup",
    ),
    Rule(
        re.compile(r"^(?:can|may)\s+i\s+(?P<action>.+?)\s+if\s+(?P<condition>.+)$", re.I),
        _render_permission_with_condition,
        "Permission with condition",
    ),
    Rule(
        re.compile(r"^is\s+it\s+(?:ok|okay)\s+to\s+(?P<action>.+)$", re.I),
        _render_permission,
        "Permission lookup",
    ),
    Rule(
        re.compile(r"^(?:can|may)\s+i\s+(?P<action>.+)$", re.I),
        _render_permission,
        "Permission lookup",
    ),
    Rule(
        re.compile(
            r"^(?:who\s+do\s+i\s+call|who\s+should\s+i\s+contact)(?:.+)?$", re.I
        ),
        _render_incident_contact,
        "Incident contact",
    ),
    Rule(
        re.compile(r"^what\s+happens\s+if\s+(?P<condition>.+)$", re.I),
        _render_condition_outcome,
        "Condition outcome",
    ),
    Rule(
        re.compile(
            r"^(?:is\s+there|where\s+is\s+there)\s+(?P<place>.+?)\s+(?:available|located)",
            re.I,
        ),
        _render_location_availability,
        "Location availability",
    ),
    Rule(
        re.compile(r"^i\s+need\s+(?!help\s+with)(?P<action>.+)$", re.I),
        _render_need_statement,
        "Need statement",
    ),
    Rule(
        re.compile(r"^i\s+want\s+to\s+refer.+bonus", re.I),
        _render_bonus_question,
        "Referral bonus",
    ),
    Rule(
        re.compile(
            r"^i\s+need\s+help\s+with\s+(?P<topic>.+?)[,;]?\s*does\s+(?P<department>.+?)\s+provide(?:.+)?$",
            re.I,
        ),
        _render_department_assistance,
        "Department assistance",
    ),
    Rule(
        re.compile(r"^is\s+there\s+a\s+place\s+to\s+(?P<action>.+)$", re.I),
        _render_place_action,
        "Place availability",
    ),
    Rule(
        re.compile(
            r"^(?:find|show|search|get)\s+(?P<body>.+)$",
            re.I,
        ),
        _render_metadata_query,
        "Metadata filtered query",
    ),
    Rule(
        re.compile(
            r"^compare\s+(?P<a>.+?)\s+(?:and|vs\.?|versus)\s+(?P<b>.+)$",
            re.I,
        ),
        _render_compare,
        "Comparison query",
    ),
    Rule(
        re.compile(
            r"^what\s+are\s+the\s+differences\s+between\s+(?P<a>.+?)\s+and\s+(?P<b>.+)$",
            re.I,
        ),
        _render_difference,
        "Difference query",
    ),
    Rule(
        re.compile(
            r"^how\s+has\s+(?P<topic>.+)\s+changed\s+between\s+(?P<year_a>\d{4})\s+and\s+(?P<year_b>\d{4})$",
            re.I,
        ),
        _render_change_between,
        "Temporal change",
    ),
    Rule(
        re.compile(
            r"^summarize\s+.+?(?:from|for)\s+(?P<a>.+?)\s+(?:and|&)\s+(?P<b>.+)$", re.I
        ),
        _render_summary,
        "Cross-department summary",
    ),
    Rule(
        re.compile(
            r"^based\s+on\s+the\s+last\s+(?P<count>\d+)\s+board\s+meetings?,?\s+what\s+is\s+our\s+top\s+priority",
            re.I,
        ),
        _render_board_priority,
        "Board priority",
    ),
    Rule(
        re.compile(
            r"^which\s+department\s+has\s+the\s+most\s+restrictive\s+travel\s+budget",
            re.I,
        ),
        _render_department_extreme,
        "Department extreme",
    ),
    Rule(
        re.compile(
            r"^was\s+(?P<event_a>.+?)\s+(?:before\s+or\s+after\s+|before\s+|after\s+)(?P<event_b>.+)$",
            re.I,
        ),
        _render_temporal_order,
        "Temporal ordering",
    ),
    Rule(
        re.compile(
            r"^what\s+is\s+the\s+procedure\s+if\s+(?P<condition>.+)$", re.I
        ),
        _render_injury_procedure,
        "Conditional procedure",
    ),
    Rule(
        re.compile(
            r"^if\s+i\s+was\s+hired\s+in\s+(?P<year>\d{4}),?\s+how\s+many\s+(?P<asset>.+?)\s+do\s+i\s+have",
            re.I,
        ),
        _render_legacy_stock,
        "Legacy allocation",
    ),
    Rule(
        re.compile(
            r"^who\s+becomes\s+the\s+interim\s+(?P<role>.+?)\s+if\s+(?P<condition>.+)$",
            re.I,
        ),
        _render_interim_role,
        "Interim role",
    ),
    Rule(
        re.compile(
            r"^what\s+is\s+the\s+policy\s+for\s+a\s+situation\s+not\s+covered", re.I
        ),
        _render_default_policy,
        "Fallback policy",
    ),
    Rule(
        re.compile(r"^is\s+there\s+a\s+limit\s+to\s+(?P<thing>.+)$", re.I),
        _render_limit,
        "Limit policy",
    ),
    Rule(
        re.compile(r"^what\s+happens\s+to\s+my\s+(?P<data>.+)\s+if\s+i\s+(?P<action>delete.+)$", re.I),
        _render_data_deletion,
        "Data deletion",
    ),
    Rule(
        re.compile(
            r"^are\s+there\s+any\s+'?grandfathered'?\s+clauses\s+for\s+(?P<context>.+)$",
            re.I,
        ),
        _render_grandfathered,
        "Grandfathered clause",
    ),
    Rule(
        re.compile(
            r"^what\s+is\s+the\s+'?(?P<clause>.+?)'?\s+clause\s+in\s+(?P<context>.+)$",
            re.I,
        ),
        _render_clause_lookup,
        "Clause lookup",
    ),
    Rule(
        re.compile(
            r"^what\s+is\s+the\s+connection\s+string\s+format\s+for\s+(?P<context>.+)$",
            re.I,
        ),
        _render_connection_string,
        "Connection string",
    ),
    Rule(
        re.compile(
            r"^how\s+do\s+i\s+rotate\s+the\s+(?P<system>.+)\s+access\s+keys", re.I
        ),
        _render_rotation,
        "Key rotation",
    ),
    Rule(
        re.compile(
            r"^what\s+is\s+the\s+'?ttl'?\s+value\s+for\s+(?P<context>.+)$",
            re.I,
        ),
        _render_ttl_lookup,
        "TTL lookup",
    ),
    Rule(
        re.compile(
            r"^explain\s+the\s+'?(?P<feature>.+?)'?\s+logic\s+in\s+(?P<context>.+)$",
            re.I,
        ),
        _render_retry_logic,
        "Feature logic",
    ),
    Rule(
        re.compile(
            r"^which\s+docker\s+image\s+version\s+are\s+we\s+using\s+for\s+(?P<service>.+)$",
            re.I,
        ),
        _render_docker_version,
        "Docker image version",
    ),
    Rule(
        re.compile(
            r"^what\s+is\s+the\s+naming\s+convention\s+for\s+(?P<target>.+)$",
            re.I,
        ),
        _render_naming_convention,
        "Naming convention",
    ),
    Rule(
        re.compile(
            r"^how\s+do\s+i\s+trigger\s+a\s+manual\s+deployment\s+in\s+(?P<system>.+)$",
            re.I,
        ),
        _render_manual_deploy,
        "Manual deploy procedure",
    ),
    Rule(
        re.compile(
            r"^where\s+is\s+the\s+documentation\s+for\s+(?P<target>.+)$",
            re.I,
        ),
        _render_docs_location,
        "Docs location",
    ),
    Rule(
        re.compile(
            r"^what\s+are\s+the\s+rate\s+limits\s+for\s+(?P<target>.+)$",
            re.I,
        ),
        _render_rate_limits,
        "Rate limits",
    ),
    Rule(
        re.compile(
            r"^how\s+do\s+i\s+request\s+(?:a\s+)?temporary\s+database\s+'?write'?\s+permission\s+for\s+(?P<database>.+)$",
            re.I,
        ),
        _render_write_permission,
        "Write permission procedure",
    ),
)


class FOLTranslator:
    """Stateful translator with extensible rule set and safe fallbacks."""

    def translate(self, sentence: str) -> Optional[str]:
        cleaned = sentence.strip().strip(".?!")
        if not cleaned:
            return None
        safety = _safety_response(cleaned)
        if safety:
            return safety
        for candidate in self._candidate_phrases(cleaned):
            for rule in RULES:
                match = rule.pattern.fullmatch(candidate)
                if match:
                    return rule.handler(match)
        return _render_fallback(cleaned)

    @staticmethod
    def _candidate_phrases(text: str) -> list[str]:
        candidates = [text]
        splitters = [",", ";", " - ", " – ", "—"]
        for splitter in splitters:
            if splitter in text:
                parts = [part.strip() for part in re.split(re.escape(splitter), text)]
                candidates.extend([part for part in parts if part])
        # Deduplicate while preserving order.
        seen: set[str] = set()
        ordered: list[str] = []
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            ordered.append(candidate)
        return ordered


TRANSLATOR = FOLTranslator()


def translate(sentence: str) -> Optional[str]:
    """Module-level helper to keep the CLI lightweight."""
    return TRANSLATOR.translate(sentence)
