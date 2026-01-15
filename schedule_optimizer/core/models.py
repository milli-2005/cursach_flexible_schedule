# core/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    """
    Расширенный профиль пользователя.
    Связывается со стандартной моделью User через OneToOne.
    """
    # Роли пользователей
    ROLE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('studio_admin', 'Администратор'),
        ('manager', 'Руководитель'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    department = models.CharField(max_length=100, blank=True, verbose_name="Отдел")
    position = models.CharField(max_length=100, blank=True, verbose_name="Должность")

    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)



@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class Employee(models.Model):
    """
    Модель сотрудника с дополнительными атрибутами для планирования.
    """
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='employee_profile')

    # Рабочие параметры
    max_hours_per_week = models.IntegerField(default=40, verbose_name="Макс. часов в неделю")
    min_hours_per_week = models.IntegerField(default=20, verbose_name="Мин. часов в неделю")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Часовая ставка")

    # Квалификация
    qualifications = models.TextField(blank=True, verbose_name="Квалификации")

    # Предпочтения
    preferred_shifts = models.TextField(blank=True, verbose_name="Предпочитаемые смены")
    unavailable_days = models.TextField(blank=True, verbose_name="Невозможные дни")

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return f"{self.user_profile.user.get_full_name() or self.user_profile.user.username}"

class Shift(models.Model):
    """
    Модель смены (тип смены).
    """
    SHIFT_TYPES = [
        ('morning', 'Утренняя'),
        ('day', 'Дневная'),
        ('evening', 'Вечерняя'),
        ('night', 'Ночная'),
        ('special', 'Особая'),
    ]

    name = models.CharField(max_length=100, verbose_name="Название смены")
    shift_type = models.CharField(max_length=20, choices=SHIFT_TYPES, default='day')
    start_time = models.TimeField(verbose_name="Время начала")
    end_time = models.TimeField(verbose_name="Время окончания")
    required_employees = models.IntegerField(default=1, verbose_name="Требуемое количество сотрудников")

    class Meta:
        verbose_name = "Смена"
        verbose_name_plural = "Смены"

    def __str__(self):
        return f"{self.name} ({self.get_shift_type_display()})"

class Schedule(models.Model):
    """
    Модель графика работы на определенный период.
    """
    name = models.CharField(max_length=200, verbose_name="Название графика")
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(verbose_name="Дата окончания")

    # Статус графика
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('pending', 'На согласовании'),
        ('approved', 'Утвержден'),
        ('published', 'Опубликован'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Создатель")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "График работы"
        verbose_name_plural = "Графики работы"

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

class ShiftAssignment(models.Model):
    """
    Назначение сотрудника на конкретную смену в конкретный день.
    """
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="Сотрудник")
    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, verbose_name="Смена")
    date = models.DateField(verbose_name="Дата")

    # Статус назначения
    STATUS_CHOICES = [
        ('scheduled', 'Запланировано'),
        ('confirmed', 'Подтверждено'),
        ('completed', 'Выполнено'),
        ('cancelled', 'Отменено'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Фактически отработанные часы (заполняется постфактум)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Факт. часы")

    class Meta:
        verbose_name = "Назначение на смену"
        verbose_name_plural = "Назначения на смены"
        unique_together = ['employee', 'date']  # Сотрудник не может быть в две смены в один день

    def __str__(self):
        return f"{self.employee} - {self.shift} ({self.date})"

class TimeOffRequest(models.Model):
    """
    Заявка на отгул/отпуск.
    """
    REQUEST_TYPES = [
        ('vacation', 'Отпуск'),
        ('sick', 'Больничный'),
        ('personal', 'Личные обстоятельства'),
        ('other', 'Другое'),
    ]

    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Утверждено'),
        ('rejected', 'Отклонено'),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="Сотрудник")
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='personal')
    start_date = models.DateField(verbose_name="Дата начала")
    end_date = models.DateField(verbose_name="Дата окончания")
    reason = models.TextField(verbose_name="Причина")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    class Meta:
        verbose_name = "Заявка на отгул"
        verbose_name_plural = "Заявки на отгул"

    def __str__(self):
        return f"{self.employee} - {self.get_request_type_display()} ({self.start_date} - {self.end_date})"

class ShiftSwapRequest(models.Model):
    """
    Заявка на обмен сменами между сотрудниками.
    """
    from_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='swap_requests_sent')
    to_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='swap_requests_received')
    shift_assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, verbose_name="Смена для обмена")
    reason = models.TextField(verbose_name="Причина обмена")

    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved_by_employee', 'Одобрено сотрудником'),
        ('approved_by_manager', 'Одобрено менеджером'),
        ('completed', 'Завершено'),
        ('rejected', 'Отклонено'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Заявка на обмен сменой"
        verbose_name_plural = "Заявки на обмен сменами"

    def __str__(self):
        return f"Обмен: {self.from_employee} -> {self.to_employee}"

class OptimizationRule(models.Model):
    """
    Правило для алгоритма оптимизации.
    """
    RULE_TYPES = [
        ('legal', 'Законодательное'),
        ('business', 'Бизнес-правило'),
        ('preference', 'Предпочтение'),
    ]

    name = models.CharField(max_length=200, verbose_name="Название правила")
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, default='business')
    description = models.TextField(verbose_name="Описание правила")

    # Параметры правила
    min_employees_per_shift = models.IntegerField(null=True, blank=True, verbose_name="Мин. сотрудников в смену")
    max_employees_per_shift = models.IntegerField(null=True, blank=True, verbose_name="Макс. сотрудников в смену")
    max_consecutive_shifts = models.IntegerField(null=True, blank=True, verbose_name="Макс. смен подряд")
    min_rest_hours = models.IntegerField(null=True, blank=True, verbose_name="Мин. часов отдыха между сменами")

    is_active = models.BooleanField(default=True, verbose_name="Активно")
    priority = models.IntegerField(default=1, verbose_name="Приоритет")

    class Meta:
        verbose_name = "Правило оптимизации"
        verbose_name_plural = "Правила оптимизации"
        ordering = ['priority', 'rule_type']

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"