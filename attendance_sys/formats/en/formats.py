"""Day-first date formats for the whole project.

Django 5 removed `USE_L10N`, so localisation is always on and the `DATE_FORMAT`
settings are ignored — a format module reached through `FORMAT_MODULE_PATH` is
the supported way to override the locale's own formats. `LANGUAGE_CODE` is
"en-us", which resolves to locale `en_US`; Django falls back to the `en`
package, so this file covers it.
"""

DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
TIME_FORMAT = "H:i"
YEAR_MONTH_FORMAT = "m/Y"
MONTH_DAY_FORMAT = "d/m"

FIRST_DAY_OF_WEEK = 1  # Monday

DATE_INPUT_FORMATS = [
    "%d/%m/%Y",
    "%d/%m/%y",
    "%Y-%m-%d",
]
# The ISO entries are not optional: <input type="datetime-local"> posts
# "2026-08-09T14:30", and the lecture form relies on it.
DATETIME_INPUT_FORMATS = [
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
]
TIME_INPUT_FORMATS = [
    "%H:%M",
    "%H:%M:%S",
]
