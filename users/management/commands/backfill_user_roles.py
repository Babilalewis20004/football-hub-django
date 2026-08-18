from django.core.management.base import BaseCommand

from users.models import CustomUser
from users.signals import VALID_ROLES, apply_role_group

DEFAULT_ROLE = "reader"


class Command(BaseCommand):
    """
    Safety net for two situations that a plain `role` field default can't
    cover on its own:

    1. A user whose `role` value isn't one of CustomUser.ROLE_CHOICES at
       all (e.g. bad data from before validation existed, or a value from
       a role that's since been renamed/removed). These are reset to the
       Reader default - never left as-is, and never assumed to be some
       other role.
    2. A user whose `role` field is valid but whose Group membership never
       got synced to it - e.g. any account created/edited before the
       role<->Group sync (users.signals.sync_role_group) existed. Their
       `role` is left untouched; only their Group membership is repaired
       to match it.

    Existing users with a valid, recognised role are never overwritten -
    only reset to Reader if their stored role isn't recognised at all.
    Idempotent and safe to re-run on every deploy (wired into
    docker/entrypoint.sh alongside `setup_roles`), the same pattern this
    project already uses for seeding the role Groups themselves.
    """

    help = (
        "Assign the Reader role to any user with an unrecognized `role` value, "
        "and ensure every user's Group membership matches their role field."
    )

    def handle(self, *args, **kwargs):
        reset_count = 0
        synced_count = 0

        for user in CustomUser.objects.all():
            if user.role not in VALID_ROLES:
                self.stdout.write(
                    f"  {user.username}: unrecognized role {user.role!r} -> {DEFAULT_ROLE!r}"
                )
                user.role = DEFAULT_ROLE
                user.save(update_fields=["role"])
                reset_count += 1
                continue

            if apply_role_group(user):
                self.stdout.write(
                    f"  {user.username}: Group membership synced to existing role {user.role!r}"
                )
                synced_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill complete: {reset_count} user(s) reset to Reader, "
                f"{synced_count} user(s) had Group membership synced."
            )
        )
