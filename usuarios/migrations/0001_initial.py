import usuarios.models
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Usuario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='correo')),
                ('nombre', models.CharField(max_length=150)),
                ('rol', models.CharField(choices=[('ANALISTA_CARTERA', 'Analista de Cartera'), ('ADMINISTRADOR', 'Administrador')], max_length=20)),
                ('is_active', models.BooleanField(default=True, verbose_name='activo')),
                ('must_change_password', models.BooleanField(default=True, verbose_name='debe cambiar la contraseña')),
            ],
            options={
                'verbose_name': 'usuario',
                'verbose_name_plural': 'usuarios',
            },
            managers=[
                ('objects', usuarios.models.UsuarioManager()),
            ],
        ),
    ]
