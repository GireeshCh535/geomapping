#!/usr/bin/env python3
"""
Insert Gujarat and Maharashtra CRZ layers using insert_masterplan_layer with
correct on-disk paths and the same line-layer exclusions as other CRZ states.

Problem this fixes
------------------
`air_funnel_insert_commands.sh` uses::

    --data-dir "data/crz/Gujarat CRZ layers_processed"
    --data-dir "data/crz/Maharashtra CRZ layers_processed"

In this repository the GeoJSON folders live directly under ``data/`` (there is
no ``data/crz/`` directory), so those paths fail with "Data directory does not
exist". This command resolves, in order:

  1. ``data/<folder name>/``
  2. ``data/crz/<folder name>/``

Line-only layers (HTL, LTL, CRZ boundary) are excluded so the DB layer stays
polygon-centric, matching Diu/Karaikal/Tamil Nadu CRZ insert patterns.

Usage::

    python manage.py insert_gujarat_maharashtra_crz_layers --delete-existing
    python manage.py insert_gujarat_maharashtra_crz_layers --only gujarat
"""

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

# Substrings matched against each file's basename (same mechanism as --exclude on insert_masterplan_layer).
_CRZ_LINE_EXCLUDE = (
    "High Tide Line",
    "Low Tide Line",
    "CRZ (Coastal Regulation Zone) Boundary",
)

_SPECS = (
    {
        "key": "gujarat",
        "city_slug": "gujarat_crz",
        "layer_name": "Gujarat CRZ Layer",
        "layer_slug": "gujarat_crz_layer",
        "folder": "Gujarat CRZ layers_processed",
        "authority": "Gujarat Coastal Zone Management Authority",
    },
    {
        "key": "maharashtra",
        "city_slug": "maharashtra_crz",
        "layer_name": "Maharashtra CRZ Layer",
        "layer_slug": "maharashtra_crz_layer",
        "folder": "Maharashtra CRZ layers_processed",
        "authority": "Maharashtra Coastal Zone Management Authority",
    },
)


def _resolve_data_dir(folder: str) -> Path:
    base = Path(settings.BASE_DIR)
    candidates = (
        base / "data" / folder,
        base / "data" / "crz" / folder,
    )
    for path in candidates:
        if path.is_dir():
            return path
    tried = "\n".join(f"  - {p}" for p in candidates)
    raise CommandError(
        f'CRZ folder "{folder}" not found. Tried:\n{tried}\n'
        "Copy the processed GeoJSON directory into one of these locations."
    )


class Command(BaseCommand):
    help = (
        "Insert Gujarat and Maharashtra CRZ layers (correct data/ vs data/crz/ paths; "
        "excludes HTL, LTL, and CRZ boundary line files)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-existing",
            action="store_true",
            help="Delete existing layer rows before re-import (passed to insert_masterplan_layer).",
        )
        parser.add_argument(
            "--only",
            choices=["gujarat", "maharashtra"],
            help="Import a single state only.",
        )
        parser.add_argument(
            "--min-zoom",
            type=int,
            default=8,
            help="Minimum zoom (default: 8).",
        )
        parser.add_argument(
            "--max-zoom",
            type=int,
            default=18,
            help="Maximum zoom (default: 18).",
        )

    def handle(self, *args, **options):
        only = options.get("only")
        exclude = ",".join(_CRZ_LINE_EXCLUDE)
        verbosity = options.get("verbosity", 1)

        for spec in _SPECS:
            if only and spec["key"] != only:
                continue

            data_dir = _resolve_data_dir(spec["folder"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n=== {spec['layer_name']} → {data_dir} ===\n"
                )
            )

            call_command(
                "insert_masterplan_layer",
                city_slug=spec["city_slug"],
                layer_name=spec["layer_name"],
                layer_slug=spec["layer_slug"],
                data_dir=str(data_dir),
                authority=spec["authority"],
                min_zoom=options["min_zoom"],
                max_zoom=options["max_zoom"],
                delete_existing=options["delete_existing"],
                exclude=exclude,
                verbosity=verbosity,
            )

        self.stdout.write(
            self.style.SUCCESS("\n✅ Gujarat/Maharashtra CRZ insert command finished.")
        )
