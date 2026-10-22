"""Standard Infosys enterprise QE assessment framework (5 pillars, 25 focus areas).

New engagements receive a copy of this template; each engagement can then edit
its own pillars, focus areas, maturity scale and scoring rules.
"""
from __future__ import annotations

DEFAULT_SETTINGS: dict = {
    "scale": [
        {"label": "Initial", "description": "Ad hoc and person-dependent. No defined practice or evidence."},
        {"label": "Managed", "description": "Practised in some teams. Inconsistent, largely manual, little measurement."},
        {"label": "Defined", "description": "Documented standard followed by most teams, with some tooling and metrics."},
        {"label": "Measured", "description": "Consistent and tool-enforced across the entity. Data drives decisions."},
        {"label": "Optimized", "description": "Continuously improved, automated and predictive. A reference for others."},
    ],
    "thresholds": {"gap": 2.25, "strong": 3.25},
    "weighting": "apps",  # apps | equal
}

# (key, name, short, target, [(name, description, guiding question, recommendation, horizon)])
FRAMEWORK: list[tuple[str, str, str, float, list[tuple[str, str, str, str, str]]]] = [
    ("eng", "QE Engineering", "Engineering", 3.5, [
        ("Testability & Quality-by-Design", "Requirements testability, risk-based design and end-to-end traceability",
         "How are acceptance criteria and test conditions agreed before build, and can a requirement be traced to its tests and defects?",
         "Embed risk-based test design and requirement-to-test traceability for priority journeys", "next"),
        ("End-to-End, API & Integration Quality", "System, API, contract, integration and critical-journey validation",
         "Which critical journeys (book, pay, board) are validated end to end, and how are API contracts with partners tested?",
         "Stand up contract testing for core APIs and an automated critical-journey regression pack", "next"),
        ("Automation Engineering", "UI/API automation, reusable frameworks and pipeline execution",
         "What share of regression is automated, on which frameworks, and does it run in the pipeline on every change?",
         "Converge on a reusable automation framework and run regression in CI on every merge", "next"),
        ("Performance, Accessibility & Resilience", "Performance engineering, accessibility, reliability and recovery",
         "When was peak-season load last tested, and how is WCAG accessibility verified?",
         "Institutionalize peak-season performance baselines and WCAG 2.2 AA checks per release", "now"),
        ("Environment, Data & Virtualization", "Ephemeral environments, synthetic/masked data and service virtualization",
         "How long does it take to get a stable test environment and compliant test data, and how are third-party dependencies stubbed?",
         "Introduce masked/synthetic test data and service virtualization for payment and partner dependencies", "next"),
    ]),
    ("del", "QE Delivery Management", "Delivery", 3.5, [
        ("Quality Planning & Forecasting", "Scope, effort, capacity, dependencies and quality-risk planning",
         "How is test scope, effort and capacity estimated per PI, and how are quality risks surfaced in planning?",
         "Add quality-risk planning and test capacity forecasting to PI planning", "now"),
        ("Test Orchestration & Flow", "Execution flow, blockers, regression coordination and feedback cycles",
         "Where does test execution stall today, and how are regression cycles coordinated across ARTs?",
         "Map test flow across ARTs and remove the top three execution blockers", "now"),
        ("Defect Intelligence & RCA", "Triage, ageing, leakage, root-cause analysis and prevention",
         "How are defects triaged and aged, what is escaped-defect leakage to production, and is root cause analysed?",
         "Track defect leakage and run monthly RCA reviews with prevention actions", "now"),
        ("Quality Observability & Insights", "Coverage, trends, escaped defects and release-quality dashboards",
         "Which quality dashboards exist today, who uses them, and do they show coverage, trends and escaped defects?",
         "Publish a shared quality dashboard with coverage, trend and leakage KPIs per entity", "now"),
        ("Release Confidence Management", "Exit criteria, residual risk, evidence and release recommendation",
         "What exit criteria decide a release, and how is residual risk communicated to the business?",
         "Define evidence-based exit criteria and a standard release-readiness recommendation", "now"),
    ]),
    ("gov", "Quality Governance", "Governance", 3.5, [
        ("Enterprise QE Strategy & Operating Model", "Enterprise, product, ART and platform quality accountabilities",
         "Is there an enterprise QE strategy, and who is accountable for quality at enterprise, product and ART level?",
         "Define the enterprise QE operating model with clear quality accountabilities", "now"),
        ("Engineering Standards & Guardrails", "Common lifecycle, minimum controls, patterns and tailored standards",
         "Is there a common test lifecycle and a minimum set of controls that all teams follow?",
         "Publish minimum QE standards and tailored guardrails by delivery type", "now"),
        ("Automated Quality Gates", "Policy-as-code, evidence-based controls and stage approvals",
         "Which pipeline stages have enforced quality gates, and can a release proceed when a gate fails?",
         "Implement policy-as-code quality gates in CI/CD for priority applications", "next"),
        ("Quality Risk, Assurance & Compliance", "Assurance reviews, control evidence and exception governance",
         "How is test evidence retained for audit (e.g. PCI for payments), and how are exceptions approved?",
         "Standardize assurance evidence and exception governance, starting with PCI-scoped systems", "next"),
        ("Portfolio, Partner & Value Governance", "Portfolio insights, supplier accountability and outcome tracking",
         "How are vendor testing commitments measured, and is QE spend linked to business outcomes?",
         "Introduce partner quality SLAs and QE value tracking at portfolio level", "later"),
    ]),
    ("tal", "QE Talent & Enablement", "Talent", 3.0, [
        ("Modern QE Roles & Skill Architecture", "Role expectations, proficiency levels and T-shaped capabilities",
         "Which QE roles exist today, and are proficiency expectations defined for each?",
         "Define modern QE role profiles and T-shaped skill expectations", "now"),
        ("Capability Intelligence & Gap Analysis", "Skills inventory, capability heatmaps and priority gaps",
         "Is there a current skills inventory for QE practitioners, and where are the critical gaps?",
         "Run a QE skills inventory and build a capability heatmap", "now"),
        ("Continuous Learning & Enablement", "QE onboarding, academies, coaching and hands-on upskilling",
         "How are new QE practitioners onboarded, and what upskilling exists for automation and AI?",
         "Launch a QE academy with role-based learning paths", "next"),
        ("Knowledge, Assets & InnerSource", "Playbooks, accelerators, reusable assets and contribution model",
         "Are frameworks, accelerators and playbooks shared across teams, or rebuilt per project?",
         "Create an InnerSource catalogue of reusable QE assets", "next"),
        ("QE CoE, Guilds & Expert Communities", "Communities of practice, specialist enablement and coaching",
         "Is there a QE community of practice, and how are specialists (performance, security) shared?",
         "Stand up a lean QE CoE with guilds for automation, performance and AI", "next"),
    ]),
    ("fut", "Future-Ready QE", "Future-Ready", 3.0, [
        ("Continuous Quality Engineering", "Shift-left/right, in-sprint automation and continuous verification",
         "How much testing happens in-sprint, and is production feedback used to refine tests?",
         "Shift testing in-sprint with continuous verification in the pipeline", "later"),
        ("AI-Augmented & Agentic QE", "GenAI-assisted design, autonomous agents and self-healing automation",
         "Are GenAI tools used today for test design, scripting or maintenance, and under what guardrails?",
         "Pilot GenAI-assisted test design and self-healing automation on one ART", "next"),
        ("Predictive Quality Intelligence", "Change-impact analysis, defect prediction and risk-based test selection",
         "Is change-impact analysis used to select tests, or is regression run in full every time?",
         "Introduce change-impact-based test selection using code and defect history", "later"),
        ("Production Quality & Observability", "Telemetry, SLOs, synthetic monitoring and production feedback",
         "What telemetry and SLOs exist for customer journeys, and is synthetic monitoring in place?",
         "Define SLOs and synthetic monitoring for critical customer journeys", "next"),
        ("Autonomous Resilience Engineering", "Chaos experiments, recovery validation and adaptive optimization",
         "Have failover and recovery been tested for critical services during peak periods?",
         "Run controlled resilience experiments on critical services", "later"),
    ]),
]

# Pairs of focus-area keys whose scores should move together. When the first is
# rated 3+ but the second is 2 or lower, the analyst flags a conflicting signal.
CONFLICT_RULES: list[tuple[str, str, str]] = [
    ("eng3", "eng5", "Automation maturity is likely capped by environment and test-data constraints."),
    ("gov3", "gov2", "Quality gates exist but the standards behind them are weak, so gates may check the wrong things."),
    ("del5", "del3", "Release confidence is rated higher than defect intelligence supports."),
    ("fut2", "eng3", "AI-augmented ambitions run ahead of the automation foundation."),
    ("del4", "eng1", "Dashboards exist but requirement traceability is weak, so coverage figures may be overstated."),
    ("gov1", "tal1", "A QE strategy exists but the roles and skills to deliver it are not yet defined."),
]


def apply_template(engagement, session) -> None:  # noqa: ANN001
    """Create the standard pillars and focus areas for a new engagement."""
    from .models import FocusArea, Pillar

    for pi, (key, name, short, target, fas) in enumerate(FRAMEWORK):
        pillar = Pillar(engagement_id=engagement.id, key=key, name=name, short=short, target=target,
                        weight=1.0, color=pi, position=pi)
        session.add(pillar)
        session.flush()
        for j, (fname, desc, q, rec, h) in enumerate(fas):
            session.add(FocusArea(engagement_id=engagement.id, pillar_id=pillar.id, key=f"{key}{j + 1}", name=fname,
                                  description=desc, question=q, recommendation=rec, horizon=h, position=j))
