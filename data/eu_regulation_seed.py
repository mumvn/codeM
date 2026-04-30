import re

REGULATION_NAME = "EU AI Act / DORA Module (EUR-Lex OJ:L_202401689)"
SOURCE_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689"


def extract_article_blocks(source_text: str):
    pattern = re.compile(r"(Article\s+\d+[a-zA-Z]?)\s*[:\-]?\s*(.+?)(?=Article\s+\d+[a-zA-Z]?|$)", re.S)
    return [(m.group(1).strip(), " ".join(m.group(2).split())) for m in pattern.finditer(source_text or "")]


def map_article_to_requirements(article_ref: str, text: str, idx: int):
    obligations = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        low = s.lower()
        if any(x in low for x in ["shall", "must", "required to"]):
            obligations.append(s.strip())
    if not obligations:
        obligations = [text[:240].strip()]
    reqs = []
    for i, obligation in enumerate(obligations[:2], start=1):
        rid = f"EU-AIDORA-{idx:03d}-{i}"
        reqs.append({
            "requirement_id": rid,
            "regulation_name": REGULATION_NAME,
            "article_reference": article_ref,
            "requirement_title": f"{article_ref} obligation {i}",
            "requirement_summary": obligation[:220],
            "source_excerpt": obligation[:500],
            "responsible_party": "Compliance Officer",
            "compliance_objective": "Maintain regulatory conformity and evidence of control execution.",
            "control_domain": "Governance",
            "evidence_required": "Policy records, control logs, approvals, and monitoring evidence.",
            "implementation_guidance": "Translate legal obligation into control procedures and assign accountable owners.",
            "deadline_or_frequency": "Quarterly review",
            "risk_impact": "high",
            "status": "open",
            "reviewer_role": "risk_officer",
            "approver_role": "compliance_officer",
            "comments": "",
        })
    return reqs


def build_seed_requirements():
    # Curated summary sample aligned to EU AI governance + DORA obligations.
    synthetic_source = """
    Article 9 Risk management system. Providers shall establish, implement, document and maintain a risk management system.
    Article 10 Data and data governance. Training, validation and testing datasets shall be relevant, representative and free of errors as far as possible.
    Article 12 Record-keeping. High-risk AI systems shall be designed and developed with capabilities enabling automatic logging of events.
    Article 14 Human oversight. High-risk AI systems shall be designed with appropriate human-machine interface tools.
    Article 15 Accuracy robustness and cybersecurity. High-risk AI systems shall achieve an appropriate level of accuracy, robustness and cybersecurity.
    Article 17 Quality management system. Providers shall put in place a quality management system ensuring compliance.
    Article 19 CE marking and conformity declaration. Providers shall draw up technical documentation and EU declaration of conformity.
    Article 23 Authorized representatives. Providers established outside the Union shall appoint an authorized representative.
    Article 26 Obligations of deployers. Deployers shall use AI systems in accordance with instructions and monitor operation.
    Article 72 Reporting of serious incidents. Providers shall report serious incidents and malfunctioning to competent authorities.
    """
    rows = []
    for idx, (article_ref, body) in enumerate(extract_article_blocks(synthetic_source), start=1):
        rows.extend(map_article_to_requirements(article_ref, body, idx))
    return rows


def build_all_articles():
    rows = []
    domains = [
        "Governance", "Risk Management", "ICT Security", "Incident Management",
        "Third-Party / Vendor Management", "Data Protection", "Reporting",
        "Audit and Evidence", "Business Continuity / Operational Resilience",
        "Access Control", "Documentation Obligations", "AI Governance",
        "Model Risk Management", "Transparency and Explainability", "Human Oversight",
    ]
    for i in range(1, 114):
        rows.append({
            "article_id": f"ART-{i:03d}",
            "article_number": i,
            "article_reference": f"Article {i}",
            "title": f"EU AI/DORA Article {i}",
            "summary": f"Structured compliance representation for Article {i}.",
            "control_domain": domains[(i - 1) % len(domains)],
        })
    return rows
