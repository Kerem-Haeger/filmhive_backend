from django.db import migrations
import os


def create_default_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    domain = os.environ.get("SITE_DOMAIN", "localhost:8000")
    name = os.environ.get("SITE_NAME", "localhost")
    site_id = int(os.environ.get("SITE_ID", 1))

    Site.objects.update_or_create(
        id=site_id,
        defaults={"domain": domain, "name": name},
    )


def remove_default_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    site_id = int(os.environ.get("SITE_ID", 1))
    try:
        Site.objects.get(id=site_id).delete()
    except Site.DoesNotExist:
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0001_initial"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(create_default_site, remove_default_site),
    ]
