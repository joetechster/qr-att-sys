"""The department vocabulary courses are filed under.

A module rather than a model: departments change on the timescale of a
university restructure, not of a term, and a table would mean a migration, an
admin screen and a foreign key for nine rows that nobody edits. `roles.py` in
`apps.accounts` makes the same trade for the same reason.

Imports nothing, so `apps.accounts` can adopt this later for `StudentProfile`
without an import cycle.

Group labels carry the "Faculty of" prefix because two of the faculties share a
name with one of their own departments — an optgroup called "Computer Science"
holding an option called "Computer Science" reads like a bug.
"""
from __future__ import annotations


# Django's Select renders this shape as <optgroup> natively, and ChoiceField
# walks the nested groups when validating, so nothing has to reshape it.
DEPARTMENT_CHOICES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Faculty of Computer Science",
        (
            ("Cybersecurity", "Cybersecurity"),
            ("Software Engineering", "Software Engineering"),
            ("Computer Science", "Computer Science"),
        ),
    ),
    (
        "Faculty of Natural Sciences",
        (
            ("Microbiology and Biochemistry", "Microbiology and Biochemistry"),
        ),
    ),
    (
        "Faculty of Social Sciences",
        (
            ("Mass Communication", "Mass Communication"),
            ("International Relations", "International Relations"),
            ("Economics", "Economics"),
            ("Accounting", "Accounting"),
            ("Business Administration", "Business Administration"),
        ),
    ),
)

DEPARTMENTS_BY_FACULTY: dict[str, tuple[str, ...]] = {
    faculty: tuple(value for value, _ in options)
    for faculty, options in DEPARTMENT_CHOICES
}

DEPARTMENT_NAMES: tuple[str, ...] = tuple(
    name for names in DEPARTMENTS_BY_FACULTY.values() for name in names
)

_DEPARTMENT_LOOKUP = {name.casefold(): name for name in DEPARTMENT_NAMES}


def normalise_department(raw: str) -> str | None:
    """Canonical name for `raw`, or None if it is not a department.

    Case- and whitespace-insensitive because the CSV importer feeds this
    whatever the HOD typed into Excel, and "computer science" is not a different
    department from "Computer Science".
    """
    return _DEPARTMENT_LOOKUP.get((raw or "").strip().casefold())
