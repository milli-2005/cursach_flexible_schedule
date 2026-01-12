"""
Формы для приложения core.
Здесь определяем формы для ввода данных.
"""
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import UserProfile


class UserInvitationForm(forms.Form):
    """
    Форма для приглашения нового пользователя администратором.
    """
    username = forms.CharField(
        max_length=150,
        label="Имя пользователя",
        help_text="Латинские буквы, цифры и символы @/./+/-/_"
    )

    email = forms.EmailField(
        label="Email",
        help_text="На этот email будет отправлено приглашение"
    )

    first_name = forms.CharField(
        max_length=30,
        required=False,
        label="Имя"
    )

    last_name = forms.CharField(
        max_length=30,
        required=False,
        label="Фамилия"
    )

    ROLE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('manager', 'Менеджер'),
        ('planner', 'Планировщик'),
        ('admin', 'Администратор системы'),
    ]

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        label="Роль в системе",
        initial='employee'
    )

    department = forms.CharField(
        max_length=100,
        required=False,
        label="Отдел"
    )

    position = forms.CharField(
        max_length=100,
        required=False,
        label="Должность"
    )

    phone = forms.CharField(
        max_length=20,
        required=False,
        label="Телефон"
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Пользователь с таким именем уже существует.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email


class UserProfileForm(forms.ModelForm):
    """
    Форма для редактирования профиля пользователя.
    """

    class Meta:
        model = UserProfile
        fields = ['role', 'phone', 'department', 'position']