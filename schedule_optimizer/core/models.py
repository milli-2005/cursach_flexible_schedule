"""Модели базы данных: пользователи, сотрудники, графики, смены, заявки, чат и правила."""
# core/models.py

from django.db import models

from django.db.models import Q

from django.contrib.auth.models import User

from django.db.models.signals import post_save

from django.dispatch import receiver

from django.utils import timezone  #Для рассчета времени смены пароля


class UserProfile(models.Model):

    """
    Расширенный профиль пользователя.

    Связывается со стандартной моделью User через OneToOne.

    """
    ROLE_CHOICES = [

        ('employee', 'Сотрудник'),

        ('manager', 'Руководитель'),

    ]


    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')

    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")


    patronymic = models.CharField(

        max_length=150,

        blank=True,

        verbose_name="Отчество"

    )


    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Аватар')


    # Поле для хранения времени приглашения/сброса пароля

    invitation_timestamp = models.DateTimeField(null=True, blank=True, verbose_name="Время приглашения/сброса пароля")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Профиль пользователя"

        verbose_name_plural = "Профили пользователей"


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f"{self.user.username} ({self.get_role_display()})"




    def is_temporary_password_expired(self, timeout_minutes=5):

        """
        Проверяет, истёк ли срок действия временного пароля.

        :param timeout_minutes: Время в минутах, после которого пароль становится недействительным.

        :return: True, если срок действия истёк, False в противном случае.

        """
        if not self.invitation_timestamp:

            # Если временная метка не установлена, считаем, что пароль не временный или срок не ограничен

            return False

        expiration_time = self.invitation_timestamp + timezone.timedelta(minutes=timeout_minutes)

        return timezone.now() > expiration_time




@receiver(post_save, sender=User)

def save_user_profile(sender, instance, **kwargs):

    """Сохраняет связанный профиль пользователя после сохранения стандартного User."""
    if hasattr(instance, 'profile'):

        instance.profile.save()





# Глобальные константы для всей студии

WORKOUT_DURATION_MINUTES = 50

TRAINER_RATE_PER_SESSION = 400.00

ADMIN_RATE_PER_DAY = 1500.00




class WorkoutType(models.Model):

    """
    Тип группового занятия (тренировки).

    Например: Stretch Basic, Deep Stretch, Yoga.

    Все занятия длятся 50 минут и оплачиваются по фиксированной ставке.

    """
    CATEGORY_CHOICES = [

        ('calm', 'Спокойные'),

        ('cardio', 'Кардио'),

        ('strength', 'Силовые'),

        ('dance', 'Танцы'),

        ('other', 'Другое'),

    ]


    name = models.CharField(max_length=100, verbose_name="Название занятия")

    description = models.TextField(blank=True, verbose_name="Описание")

    category = models.CharField(

        max_length=20,

        choices=CATEGORY_CHOICES,

        default='other',

        verbose_name='Категория занятия'

    )


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Тип занятия"

        verbose_name_plural = "Типы занятий"


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return self.name


    @property

    def duration_minutes(self):

        """Возвращает длительность занятия как константу."""
        return WORKOUT_DURATION_MINUTES


    @property

    def rate_per_session(self):

        """Возвращает ставку за занятие как константу."""
        return TRAINER_RATE_PER_SESSION





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

    is_substitute = models.BooleanField(

        default=False,

        verbose_name="В пуле подменных тренеров"

    )

    substitute_priority = models.PositiveSmallIntegerField(

        default=50,

        verbose_name="Приоритет подмены"

    )


    # направления:

    workout_types = models.ManyToManyField(

        'WorkoutType',

        blank=True,

        verbose_name="Направления, которые ведёт"

    )


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        name = ' '.join(p for p in (self.user_profile.user.last_name, self.user_profile.user.first_name) if p)

        return name or self.user_profile.user.username





class HourRateChange(models.Model):

    """
    �?стория изменений часовой ставки.

    Старые смены считаются по ставке, которая действовала на момент их начала.

    """
    rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Часовая ставка")

    effective_from = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="Действует с")

    changed_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='hour_rate_changes',

        verbose_name="Кто изменил",

    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "�?зменение часовой ставки"

        verbose_name_plural = "�?стория изменения часовой ставки"

        ordering = ['-effective_from', '-id']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        who = self.changed_by.username if self.changed_by_id else "system"

        return f"{self.rate} ₽/ч с {self.effective_from:%Y-%m-%d %H:%M} ({who})"




@receiver(post_save, sender=UserProfile)

def create_employee_for_user_profile(sender, instance, created, **kwargs):

    """Создает запись сотрудника при создании нового профиля пользователя."""
    if created:

        Employee.objects.get_or_create(user_profile=instance)




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

        ('approved', 'Утвержден')

    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Создатель")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "График работы"

        verbose_name_plural = "Графики работы"


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f"{self.name} ({self.start_date} - {self.end_date})"




class ScheduleVersion(models.Model):

    """
    Версия графика (снимок на момент сохранения).

    """
    schedule = models.ForeignKey(

        Schedule,

        on_delete=models.CASCADE,

        related_name='versions',

        verbose_name="График",

    )

    version_number = models.PositiveIntegerField(verbose_name="Номер версии")

    schedule_name = models.CharField(max_length=200, verbose_name="Название графика в версии")

    created_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='created_schedule_versions',

        verbose_name="Кто создал версию",

    )

    change_source = models.CharField(

        max_length=30,

        blank=True,

        verbose_name="�?сточник изменения",

        help_text="create, update, restore",

    )

    change_note = models.CharField(

        max_length=255,

        blank=True,

        verbose_name="Комментарий к версии",

    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания версии")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Версия графика"

        verbose_name_plural = "Версии графиков"

        ordering = ['-version_number', '-id']

        constraints = [

            models.UniqueConstraint(

                fields=['schedule', 'version_number'],

                name='unique_schedule_version_number',

            )

        ]


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f"{self.schedule.name} v{self.version_number}"




class ScheduleVersionAssignment(models.Model):

    """
    Снимок одной ячейки расписания для конкретной версии графика.

    """
    schedule_version = models.ForeignKey(

        ScheduleVersion,

        on_delete=models.CASCADE,

        related_name='assignments',

        verbose_name="Версия графика",

    )

    employee = models.ForeignKey(

        UserProfile,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        verbose_name="Сотрудник",

    )

    workout_type = models.ForeignKey(

        WorkoutType,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        verbose_name="Тип занятия",

    )

    date = models.DateField(verbose_name="Дата")

    start_time = models.TimeField(verbose_name="Время начала")

    end_time = models.TimeField(verbose_name="Время окончания")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Снимок смены версии"

        verbose_name_plural = "Снимки смен версий"

        ordering = ['date', 'start_time', 'id']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f"v{self.schedule_version.version_number}: {self.date} {self.start_time}"




class ShiftAssignment(models.Model):

    """
    Назначение сотрудника на конкретное занятие в конкретный день и время.

    """
    # Связь с графиком

    schedule = models.ForeignKey('Schedule', on_delete=models.CASCADE, related_name='assignments')


    # Сотрудник, которого назначают

    employee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name="Сотрудник")


    # Тип занятия (для тренеров) или просто "Работа" (для администраторов)

    workout_type = models.ForeignKey(

        WorkoutType,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        verbose_name="Тип занятия"

    )


    


    # Временные рамки

    date = models.DateField(verbose_name="Дата")

    start_time = models.TimeField(verbose_name="Время начала")

    end_time = models.TimeField(verbose_name="Время окончания", null=True, blank=True)


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

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Назначение на занятие"

        verbose_name_plural = "Назначения на занятия"

        unique_together = ['employee', 'date', 'start_time']  # Сотрудник не может быть в двух местах одновременно


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        # Единственный, правильный метод __str__

        end_time_str = self.end_time.strftime('%H:%M') if self.end_time else '??:??'

        name = ' '.join(p for p in (self.employee.user.last_name, self.employee.user.first_name) if p) or self.employee.user.username

        return f"{name} - {self.workout_type or 'Работа'} ({self.date} {self.start_time.strftime('%H:%M')}-{end_time_str})"

    #вычисляет продолжительность смены в часах

    def get_duration(self):

        """Вычисляет длительность смены в часах по времени начала и окончания."""
        from datetime import datetime, date

        # Создаём "фиктивную" дату (01.01.0001), чтобы превратить время в полноценный datetime

        start = datetime.combine(date.min, self.start_time)  # -> datetime(1, 1, 1, 9, 0)

        end = datetime.combine(date.min, self.end_time)  # -> datetime(1, 1, 1, 10, 0)


        # Считаем разницу в секундах и переводим в часы

        return (end - start).total_seconds() / 3600  # -> 1.0







class ShiftSwapRequest(models.Model):

    """
    Заявка на обмен сменами между сотрудниками.

    """
    from_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='swap_requests_sent')

    to_employee = models.ForeignKey(

        Employee,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='swap_requests_received',

    )

    reason = models.TextField(verbose_name="Причина обмена")


    STATUS_CHOICES = [

        ('pending', 'На рассмотрении'),

        ('approved_by_employee', 'Одобрено сотрудником'),

        ('approved_by_manager', 'Одобрено руководителем'),

        ('completed', 'Завершено'),

        ('rejected', 'Отклонено'),

    ]

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Заявка на обмен сменами"

        verbose_name_plural = "Заявки на обмен сменами"


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f"Обмен: {self.from_employee} -> {self.to_employee or 'кандидат не выбран'}"




class SwapShift(models.Model):

    """
    Смена, участвующая в обмене.

    """
    swap_request = models.ForeignKey(ShiftSwapRequest, on_delete=models.CASCADE, related_name='shifts')

    shift_assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, verbose_name="Смена для обмена")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Смена в обмене"

        verbose_name_plural = "Смены в обмене"


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f"{self.shift_assignment} in {self.swap_request}"





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

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Правило оптимизации"

        verbose_name_plural = "Правила оптимизации"

        ordering = ['priority', 'rule_type']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f"{self.name} ({self.get_rule_type_display()})"




class DistributionRule(models.Model):

    """
    Модель правил распределения для автозаполнения графика.

    """
    RULE_TYPE_CHOICES = [

        ('weekly_limit', 'Лимит в неделю'),

        ('calm_consecutive', 'Ограничение спокойных подряд'),

        ('alternation', 'Чередование категорий'),

        ('daily_duplicate_limit', 'Запрет дублей в день'),

    ]


    SEVERITY_CHOICES = [

        ('hard', 'Жесткое'),

        ('soft', 'Мягкое'),

    ]


    # ── Основные поля ────────────────────────────────────────────

    name = models.CharField(max_length=200, verbose_name='Название правила')

    # �?сходный текст, который ввёл пользователь (сохраняется для истории и перепроверки)

    source_text = models.TextField(verbose_name='Текст правила')

    # Тип: weekly_limit / calm_consecutive / alternation / daily_duplicate_limit

    rule_type = models.CharField(max_length=32, choices=RULE_TYPE_CHOICES, verbose_name='Тип правила')

    # Жёсткость: hard (нельзя нарушать) / soft (желательно не нарушать)

    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='hard', verbose_name='Жесткость')

    # Структурированные параметры — JSON-словарь. Содержит всё, что нужно JS-алгоритму:

    #   для weekly_limit: target_mode, workout_name/category, period, buckets/max_total

    #   для calm_consecutive: weekdays, max_consecutive, category

    #   для alternation: weekdays, categories, mode

    #   для daily_duplicate_limit: scope, max_per_bucket_per_day, buckets, weekdays

    params_json = models.JSONField(default=dict, blank=True, verbose_name='Параметры (JSON)')

    # Активно ли правило сейчас. Выключенные правила не участвуют в автозаполнении.

    is_active = models.BooleanField(default=True, verbose_name='Активно')

    # Приоритет: чем меньше число, тем важнее правило. При конфликте побеждает меньший priority.

    priority = models.PositiveIntegerField(default=100, verbose_name='Приоритет')

    # Кто создал правило (менеджер). Может быть null, если пользователь удалён.

    created_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='distribution_rules_created',

        verbose_name='Создатель',

    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = 'Правило распределения'

        verbose_name_plural = 'Правила распределения'

        # Сортировка по умолчанию: сначала важные (priority=1), затем по ID создания

        ordering = ['priority', 'id']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return self.name




class Availability(models.Model):

    """Модель Django описывает таблицу базы данных и связанные с ней правила поведения."""
    employee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name="Сотрудник")

    date = models.DateField(verbose_name="Дата")

    start_time = models.TimeField(verbose_name="Начало слота")

    end_time = models.TimeField(verbose_name="Окончание слота")

    is_available = models.BooleanField(default=True, verbose_name="Доступен")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Последнее обновление")


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = "Доступность"

        verbose_name_plural = "Доступность"

        unique_together = ('employee', 'date', 'start_time')


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        name = ' '.join(p for p in (self.employee.user.last_name, self.employee.user.first_name) if p) or self.employee.user.username

        return f"{name} — {self.date} {self.start_time}–{self.end_time}"





#согласование графика: модель отзыва

class ScheduleApproval(models.Model):

    """Модель Django описывает таблицу базы данных и связанные с ней правила поведения."""
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='approvals')

    employee = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    approved = models.BooleanField(null=True)  # True/False/None

    comment = models.TextField(blank=True)

    rejection_slots_json = models.JSONField(default=list, blank=True)

    responded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        unique_together = ('schedule', 'employee')




class ChatConversation(models.Model):

    """
    Личный диалог между двумя пользователями.

    participant_a и participant_b всегда хранятся в стабильном порядке (по id),

    чтобы не создавать дубликаты диалогов для одной пары пользователей.

    """
    participant_a = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name='chat_conversations_as_a',

        verbose_name='Участник A',

        null=True,

        blank=True,

    )

    participant_b = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name='chat_conversations_as_b',

        verbose_name='Участник B',

        null=True,

        blank=True,

    )

    is_group = models.BooleanField(default=False, verbose_name='Групповой чат')

    title = models.CharField(max_length=200, blank=True, verbose_name='Название группы')

    participants = models.ManyToManyField(

        User,

        related_name='chat_conversations',

        blank=True,

        verbose_name='Участники',

    )

    created_by = models.ForeignKey(

        User,

        on_delete=models.SET_NULL,

        null=True,

        blank=True,

        related_name='chat_groups_created',

        verbose_name='Создатель группы',

    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = 'Диалог'

        verbose_name_plural = 'Диалоги'

        constraints = [

            models.UniqueConstraint(

                fields=['participant_a', 'participant_b'],

                condition=Q(participant_a__isnull=False, participant_b__isnull=False, is_group=False),

                name='unique_chat_conversation_pair',

            ),

        ]

        ordering = ['-updated_at']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        if self.is_group:

            return self.title or f'Группа #{self.id}'

        if self.participant_a and self.participant_b:

            return f'Диалог: {self.participant_a.username} <-> {self.participant_b.username}'

        return f'Диалог #{self.id}'


    def get_other_user(self, current_user):

        """Возвращает второго участника личного диалога относительно текущего пользователя."""
        return self.participant_b if self.participant_a_id == current_user.id else self.participant_a




class ChatConversationPin(models.Model):

    """
    Закрепление диалога конкретным пользователем.

    """
    user = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name='chat_pins',

        verbose_name='Пользователь',

    )

    conversation = models.ForeignKey(

        ChatConversation,

        on_delete=models.CASCADE,

        related_name='pins',

        verbose_name='Диалог',

    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Закреплено в')


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = 'Закрепленный диалог'

        verbose_name_plural = 'Закрепленные диалоги'

        constraints = [

            models.UniqueConstraint(fields=['user', 'conversation'], name='unique_chat_conversation_pin'),

        ]

        ordering = ['-created_at']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f'{self.user.username} pinned #{self.conversation_id}'




class ChatMessage(models.Model):

    """
    Сообщение в личном диалоге.

    """
    conversation = models.ForeignKey(

        ChatConversation,

        on_delete=models.CASCADE,

        related_name='messages',

        verbose_name='Диалог',

    )

    sender = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name='chat_messages_sent',

        verbose_name='Отправитель',

    )

    text = models.TextField(verbose_name='Текст сообщения', blank=True, default='')

    is_read = models.BooleanField(default=False, verbose_name='Прочитано')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Отправлено')


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = 'Сообщение чата'

        verbose_name_plural = 'Сообщения чата'

        ordering = ['created_at']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        preview = (self.text or '').strip()

        if not preview:

            preview = '[вложение]'

        return f'[{self.created_at:%d.%m.%Y %H:%M}] {self.sender.username}: {preview[:30]}'




class ChatMessageAttachment(models.Model):

    """Модель Django описывает таблицу базы данных и связанные с ней правила поведения."""
    message = models.ForeignKey(

        ChatMessage,

        on_delete=models.CASCADE,

        related_name='attachments',

        verbose_name='Сообщение',

    )

    file = models.FileField(upload_to='chat_files/%Y/%m/%d/', verbose_name='Файл')

    original_name = models.CharField(max_length=255, verbose_name='�?мя файла')

    size = models.PositiveIntegerField(default=0, verbose_name='Размер (байт)')

    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name='Загружен')


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = 'Вложение сообщения'

        verbose_name_plural = 'Вложения сообщений'

        ordering = ['id']


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f'Файл {self.original_name} к сообщению #{self.message_id}'




class ChatMessageRead(models.Model):

    """
    Персональный статус прочтения сообщения конкретным пользователем.

    """
    message = models.ForeignKey(

        ChatMessage,

        on_delete=models.CASCADE,

        related_name='read_states',

        verbose_name='Сообщение',

    )

    user = models.ForeignKey(

        User,

        on_delete=models.CASCADE,

        related_name='chat_message_read_states',

        verbose_name='Пользователь',

    )

    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Прочитано в')


    class Meta:

        """Внутренние настройки модели Django: название, сортировка, ограничения или отображение."""
        verbose_name = 'Статус прочтения сообщения'

        verbose_name_plural = 'Статусы прочтения сообщений'

        constraints = [

            models.UniqueConstraint(fields=['message', 'user'], name='unique_message_read_state'),

        ]


    def __str__(self):

        """Возвращает короткое читаемое представление объекта для админки, логов и списков."""
        return f'Чтение сообщения #{self.message_id} пользователем {self.user.username}'

