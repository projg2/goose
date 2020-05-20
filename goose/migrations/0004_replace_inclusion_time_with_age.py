# (c) 2020 Michał Górny
# 2-clause BSD license

# Generated by Django 3.0.6 on 2020-05-20 13:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('goose', '0003_add_ip'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='count',
            name='unique_count',
        ),
        migrations.RemoveField(
            model_name='count',
            name='inclusion_time',
        ),
        migrations.AddField(
            model_name='count',
            name='age',
            field=models.IntegerField(default=0,
                                      help_text='Age of data'),
        ),
        migrations.AddConstraint(
            model_name='count',
            constraint=models.UniqueConstraint(fields=('value', 'age'),
                                               name='unique_count'),
        ),
    ]
