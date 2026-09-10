"""Operator entry point for the reviewed, resumable native document migration."""

from django.core.management.base import BaseCommand, CommandError

from suite_identity.document_inventory import indexed_inventory

from core.services import docs_migration


class Command(BaseCommand):
    help = "Plan, stage, compare and finalize native Docs migration with private receipts."

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            choices=["plan", "stage", "compare", "activate", "rollback", "discard", "status"],
        )
        for name in ("inventory", "plan", "placements", "attachment", "native-receipt", "output"):
            parser.add_argument("--" + name)
        parser.add_argument("--confirm-frozen", action="store_true")

    def handle(self, *args, **options):
        action = options["action"]
        required = {
            "plan": ("inventory", "output"),
            "stage": ("inventory", "plan"),
            "compare": ("inventory", "plan", "output"),
            "activate": ("inventory", "plan", "attachment", "native_receipt", "output"),
            "rollback": ("inventory", "plan", "attachment", "native_receipt", "output"),
            "discard": ("inventory", "plan", "native_receipt", "output"),
            "status": ("output",),
        }[action]
        if any(not options[key] for key in required):
            raise CommandError(
                "Required: " + ", ".join("--" + key.replace("_", "-") for key in required)
            )
        if action in {"stage", "activate", "rollback", "discard"} and not options["confirm_frozen"]:
            raise CommandError("Suspend Docs mutation services and pass --confirm-frozen.")
        if action == "plan":
            counts = docs_migration.plan(
                options["inventory"], options["output"], options["placements"]
            )
        elif action == "stage":
            counts = {"document": docs_migration.stage(options["inventory"], options["plan"])}
        elif action == "compare":
            counts = docs_migration.compare(
                options["inventory"], options["plan"], options["output"]
            )
        elif action == "discard":
            counts = docs_migration.discard(*(options[key] for key in required))
        elif action in {"activate", "rollback"}:
            counts = docs_migration.finalize(
                *(options[key] for key in required), rollback=action == "rollback"
            )
        else:
            with indexed_inventory(options["output"]) as (_db, _checkpoint, receipt):
                counts = receipt["counts"]
        self.stdout.write(f"{action}: {dict(counts)}")
