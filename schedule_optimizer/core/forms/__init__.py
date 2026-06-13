"""Django-формы для приглашения пользователей, редактирования профиля и настройки сотрудников."""

# core/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from ..models import UserProfile
import re
from ..models import Employee, WorkoutType



class UserInvitationForm(forms.ModelForm):
    """Описывает форму Django: поля, проверки и подготовку данных пользователя."""
    username = forms.CharField(max_length=150, label="Имя пользователя")
    email = forms.EmailField(label="Email")
    first_name = forms.CharField(max_length=150, label="Имя")
    last_name = forms.CharField(max_length=150, label="Фамилия", required=False)
    patronymic = forms.CharField(max_length=150, required=False, label="Отчество")
    phone = forms.CharField(max_length=20, label="Телефон")
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, label="Роль")

    class Meta:
        """Класс группирует данные и поведение для своей части проекта."""
        model = UserProfile
        fields = ['role', 'phone', 'patronymic']

    def clean_patronymic(self):
        """Проверяет и нормализует значение поля формы перед сохранением данных."""
        return self.cleaned_data['patronymic'].strip() or ''

    def clean_username(self):
        """Проверяет и нормализует значение поля формы перед сохранением данных."""
        username = self.cleaned_data['username'].strip()
        if not username:
            raise forms.ValidationError("Имя пользователя обязательно.")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Пользователь с таким именем уже существует.")
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            raise forms.ValidationError("Имя пользователя может содержать только латинские буквы, цифры, _ и -.")
        return username

    def clean_email(self):
        """Проверяет и нормализует значение поля формы перед сохранением данных."""
        email = self.cleaned_data['email'].strip()
        if not email:
            raise forms.ValidationError("Email обязателен.")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email

    def clean_first_name(self):
        """Проверяет и нормализует значение поля формы перед сохранением данных."""
        name = self.cleaned_data['first_name'].strip()
        if not name:
            raise forms.ValidationError("Имя обязательно.")
        if not re.match(r'^[а-яА-ЯёЁ\s]+$', name):
            raise forms.ValidationError("Имя должно содержать только русские буквы.")
        return name

    def clean_last_name(self):
        """Проверяет и нормализует значение поля формы перед сохранением данных."""
        name = self.cleaned_data['last_name'].strip()
        if name and not re.match(r'^[а-яА-ЯёЁ\s]+$', name):
            raise forms.ValidationError("Фамилия должна содержать только русские буквы.")
        return name

    def clean_phone(self):
        """Проверяет и нормализует значение поля формы перед сохранением данных."""
        phone = self.cleaned_data['phone'].strip()
        if not phone:
            raise forms.ValidationError("Телефон обязателен.")
        cleaned = re.sub(r'[^\d+]', '', phone)
        if not re.match(r'^(\+7|8)\d{10}$', cleaned):
            raise forms.ValidationError("Неверный формат телефона. Пример: +7 999 123-45-67")
        if cleaned.startswith('8'):
            cleaned = '+7' + cleaned[1:]
        return cleaned

    def clean_role(self):
        """Проверяет и нормализует значение поля формы перед сохранением данных."""
        role = self.cleaned_data['role']
        if not role:
            raise forms.ValidationError("Роль обязательна.")
        return role


# class UserProfileEditForm(forms.ModelForm):
#     """
#     Форма для редактирования профиля пользователя.
#     Теперь включает только актуальные поля: телефон и должность.
#     """
#     class Meta:
#         model = UserProfile
#         # Убираем 'department', так как его больше нет в модели
#         fields = ['phone', 'position']
#         labels = {
#             'phone': 'Телефон',
#             'position': 'Должность',
#         }
#         widgets = {
#             'phone': forms.TextInput(attrs={'class': 'form-control'}),
#             'position': forms.Select(attrs={'class': 'form-select'}), # Используем Select для выпадающего списка
#         }



# Оставим SetPasswordForm как есть, если используется
class CustomSetPasswordForm(SetPasswordForm):
    """
    Кастомная форма для смены пароля, наследуется от SetPasswordForm.
    Можно добавить стили Bootstrap.
    """
    def __init__(self, *args, **kwargs):
        """Выполняет вспомогательное действие внутри своей части проекта."""
        super().__init__(*args, **kwargs)
        for field_name in ['new_password1', 'new_password2']:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})


from django import forms
from ..models import Employee, WorkoutType

class EmployeeAdminForm(forms.ModelForm):
    """Описывает форму Django: поля, проверки и подготовку данных пользователя."""
    workout_types = forms.ModelMultipleChoiceField(
        queryset=WorkoutType.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        label="Направления, которые ведёт",
        required=False
    )

    class Meta:
        """Класс группирует данные и поведение для своей части проекта."""
        model = Employee
        fields = ['workout_types']
class UserProfileEditForm(forms.ModelForm):
    """Описывает форму Django: поля, проверки и подготовку данных пользователя."""
    class Meta:
        """Класс группирует данные и поведение для своей части проекта."""
        model = UserProfile
        fields = ['phone', 'patronymic', 'avatar']
        labels = {
            'phone': 'Телефон',
            'patronymic': 'Отчество',
            'avatar': 'Аватар',
        }
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 999 123-45-67'}),
            'patronymic': forms.TextInput(attrs={'class': 'form-control'}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
