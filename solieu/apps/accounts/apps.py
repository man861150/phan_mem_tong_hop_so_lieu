from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Tài khoản"

    def ready(self):
        # Roles live on User.role. Group is unused. Axes logs are hidden;
        # lockouts are shown from accounts.admin.AccessAttemptAdmin.
        from axes.models import AccessFailureLog, AccessLog
        from django.contrib import admin
        from django.contrib.auth.models import Group

        if admin.site.is_registered(Group):
            admin.site.unregister(Group)
        for model in (AccessLog, AccessFailureLog):
            if admin.site.is_registered(model):
                admin.site.unregister(model)
