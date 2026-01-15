# core/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from .models import UserProfile

class UserInvitationForm(forms.Form):
    # ... (остаётся как было)
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
        ('studio_admin', 'Администратор студии'),
        ('manager', 'Руководитель'),
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

# Новая форма для редактирования профиля
class UserProfileEditForm(forms.ModelForm):
    """
    Форма для редактирования профиля пользователя (без роли).
    """
    class Meta:
        model = UserProfile
        fields = ['phone', 'department', 'position'] # Убрали role
        labels = {
            'phone': 'Телефон',
            'department': 'Отдел',
            'position': 'Должность',
        }
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
        }

# Оставим SetPasswordForm как есть, если используется
class CustomSetPasswordForm(SetPasswordForm):
    """
    Кастомная форма для смены пароля, наследуется от SetPasswordForm.
    Можно добавить стили Bootstrap.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['new_password1', 'new_password2']:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})