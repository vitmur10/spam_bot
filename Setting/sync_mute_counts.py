from django.core.management.base import BaseCommand
from django.db.models import Count
from const import ActionLog, ChatMembership

class Command(BaseCommand):
    help = 'Синхронізує mute_count у ChatMembership з ActionLog'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Починаємо синхронізацію mute_count...")

        mute_actions = (
            ActionLog.objects
            .filter(action_type='user_muted', membership__isnull=False)
            .values('membership')
            .annotate(actual_mute_count=Count('id'))
        )

        updated = 0
        for entry in mute_actions:
            membership_id = entry['membership']
            actual_count = entry['actual_mute_count']

            try:
                membership = ChatMembership.objects.get(id=membership_id)
                if membership.mute_count != actual_count:
                    self.stdout.write(f"➡️  Оновлення ChatMembership ID {membership_id}: {membership.mute_count} → {actual_count}")
                    membership.mute_count = actual_count
                    membership.save()
                    updated += 1
            except ChatMembership.DoesNotExist:
                self.stdout.write(f"⚠️  ChatMembership ID {membership_id} не знайдено")

        self.stdout.write(f"✅ Синхронізацію завершено. Оновлено записів: {updated}")