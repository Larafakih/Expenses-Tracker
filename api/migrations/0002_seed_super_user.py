import os

from django.contrib.auth.hashers import make_password
from django.db import migrations

USERNAME = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
EMAIL = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "Admin12345!")


def create_super_user(apps, schema_editor):
    User = apps.get_model("api", "User")

    if User.objects.filter(username=USERNAME).exists():
        return

    User.objects.create(
        username=USERNAME,
        email=EMAIL,
        password=make_password(PASSWORD),
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


def delete_super_user(apps, schema_editor):
    User = apps.get_model("api", "User")
    User.objects.filter(username=USERNAME, is_superuser=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_super_user, delete_super_user),
    ]