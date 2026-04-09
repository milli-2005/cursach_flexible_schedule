# core/models.py
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone  #Р”Р»СЏ СЂР°СЃСЃС‡РµС‚Р° РІСЂРµРјРµРЅРё СЃРјРµРЅС‹ РїР°СЂРѕР»СЏ

class UserProfile(models.Model):
    """
    Р Р°СЃС€РёСЂРµРЅРЅС‹Р№ РїСЂРѕС„РёР»СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ.
    РЎРІСЏР·С‹РІР°РµС‚СЃСЏ СЃРѕ СЃС‚Р°РЅРґР°СЂС‚РЅРѕР№ РјРѕРґРµР»СЊСЋ User С‡РµСЂРµР· OneToOne.
    """
    # Р РѕР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№
    ROLE_CHOICES = [
        ('employee', 'Сотрудник'),
        ('manager', 'Руководитель'),
    ]
    # Р”РѕР»Р¶РЅРѕСЃС‚Рё (РґР»СЏ Р±РёР·РЅРµСЃ-Р»РѕРіРёРєРё)
    # POSITION_CHOICES = [
    #     ('trainer', 'РўСЂРµРЅРµСЂ'),
    #     ('administrator', 'РђРґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂ'),
    # ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    phone = models.CharField(max_length=20, blank=True, verbose_name="РўРµР»РµС„РѕРЅ")
    # position = models.CharField(
    #     max_length=20,
    #     choices=POSITION_CHOICES,
    #     default='trainer',
    #     verbose_name="Р”РѕР»Р¶РЅРѕСЃС‚СЊ"
    # )

    patronymic = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="РћС‚С‡РµСЃС‚РІРѕ"
    )

    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Аватар')

    # РџРѕР»Рµ РґР»СЏ С…СЂР°РЅРµРЅРёСЏ РІСЂРµРјРµРЅРё РїСЂРёРіР»Р°С€РµРЅРёСЏ/СЃР±СЂРѕСЃР° РїР°СЂРѕР»СЏ
    invitation_timestamp = models.DateTimeField(null=True, blank=True, verbose_name="Р’СЂРµРјСЏ РїСЂРёРіР»Р°С€РµРЅРёСЏ/СЃР±СЂРѕСЃР° РїР°СЂРѕР»СЏ")

    class Meta:
        verbose_name = "РџСЂРѕС„РёР»СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ"
        verbose_name_plural = "РџСЂРѕС„РёР»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№"

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


    def is_temporary_password_expired(self, timeout_minutes=5):
        """
        РџСЂРѕРІРµСЂСЏРµС‚, РёСЃС‚С‘Рє Р»Рё СЃСЂРѕРє РґРµР№СЃС‚РІРёСЏ РІСЂРµРјРµРЅРЅРѕРіРѕ РїР°СЂРѕР»СЏ.
        :param timeout_minutes: Р’СЂРµРјСЏ РІ РјРёРЅСѓС‚Р°С…, РїРѕСЃР»Рµ РєРѕС‚РѕСЂРѕРіРѕ РїР°СЂРѕР»СЊ СЃС‚Р°РЅРѕРІРёС‚СЃСЏ РЅРµРґРµР№СЃС‚РІРёС‚РµР»СЊРЅС‹Рј.
        :return: True, РµСЃР»Рё СЃСЂРѕРє РґРµР№СЃС‚РІРёСЏ РёСЃС‚С‘Рє, False РІ РїСЂРѕС‚РёРІРЅРѕРј СЃР»СѓС‡Р°Рµ.
        """
        if not self.invitation_timestamp:
            # Р•СЃР»Рё РІСЂРµРјРµРЅРЅР°СЏ РјРµС‚РєР° РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅР°, СЃС‡РёС‚Р°РµРј, С‡С‚Рѕ РїР°СЂРѕР»СЊ РЅРµ РІСЂРµРјРµРЅРЅС‹Р№ РёР»Рё СЃСЂРѕРє РЅРµ РѕРіСЂР°РЅРёС‡РµРЅ
            return False
        expiration_time = self.invitation_timestamp + timezone.timedelta(minutes=timeout_minutes)
        return timezone.now() > expiration_time


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()



# Р“Р»РѕР±Р°Р»СЊРЅС‹Рµ РєРѕРЅСЃС‚Р°РЅС‚С‹ РґР»СЏ РІСЃРµР№ СЃС‚СѓРґРёРё
WORKOUT_DURATION_MINUTES = 50
TRAINER_RATE_PER_SESSION = 400.00
ADMIN_RATE_PER_DAY = 1500.00


class WorkoutType(models.Model):
    """
    РўРёРї РіСЂСѓРїРїРѕРІРѕРіРѕ Р·Р°РЅСЏС‚РёСЏ (С‚СЂРµРЅРёСЂРѕРІРєРё).
    РќР°РїСЂРёРјРµСЂ: Stretch Basic, Deep Stretch, Yoga.
    Р’СЃРµ Р·Р°РЅСЏС‚РёСЏ РґР»СЏС‚СЃСЏ 50 РјРёРЅСѓС‚ Рё РѕРїР»Р°С‡РёРІР°СЋС‚СЃСЏ РїРѕ С„РёРєСЃРёСЂРѕРІР°РЅРЅРѕР№ СЃС‚Р°РІРєРµ.
    """
    name = models.CharField(max_length=100, verbose_name="РќР°Р·РІР°РЅРёРµ Р·Р°РЅСЏС‚РёСЏ")
    description = models.TextField(blank=True, verbose_name="РћРїРёСЃР°РЅРёРµ")

    class Meta:
        verbose_name = "РўРёРї Р·Р°РЅСЏС‚РёСЏ"
        verbose_name_plural = "РўРёРїС‹ Р·Р°РЅСЏС‚РёР№"

    def __str__(self):
        return self.name

    @property
    def duration_minutes(self):
        """Р’РѕР·РІСЂР°С‰Р°РµС‚ РґР»РёС‚РµР»СЊРЅРѕСЃС‚СЊ Р·Р°РЅСЏС‚РёСЏ РєР°Рє РєРѕРЅСЃС‚Р°РЅС‚Сѓ."""
        return WORKOUT_DURATION_MINUTES

    @property
    def rate_per_session(self):
        """Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃС‚Р°РІРєСѓ Р·Р° Р·Р°РЅСЏС‚РёРµ РєР°Рє РєРѕРЅСЃС‚Р°РЅС‚Сѓ."""
        return TRAINER_RATE_PER_SESSION



class Employee(models.Model):
    """
    РњРѕРґРµР»СЊ СЃРѕС‚СЂСѓРґРЅРёРєР° СЃ РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹РјРё Р°С‚СЂРёР±СѓС‚Р°РјРё РґР»СЏ РїР»Р°РЅРёСЂРѕРІР°РЅРёСЏ.
    """
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='employee_profile')

    # Р Р°Р±РѕС‡РёРµ РїР°СЂР°РјРµС‚СЂС‹
    max_hours_per_week = models.IntegerField(default=40, verbose_name="РњР°РєСЃ. С‡Р°СЃРѕРІ РІ РЅРµРґРµР»СЋ")
    min_hours_per_week = models.IntegerField(default=20, verbose_name="РњРёРЅ. С‡Р°СЃРѕРІ РІ РЅРµРґРµР»СЋ")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Р§Р°СЃРѕРІР°СЏ СЃС‚Р°РІРєР°")

    # РљРІР°Р»РёС„РёРєР°С†РёСЏ
    qualifications = models.TextField(blank=True, verbose_name="РљРІР°Р»РёС„РёРєР°С†РёРё")

    # РџСЂРµРґРїРѕС‡С‚РµРЅРёСЏ
    preferred_shifts = models.TextField(blank=True, verbose_name="РџСЂРµРґРїРѕС‡РёС‚Р°РµРјС‹Рµ СЃРјРµРЅС‹")
    unavailable_days = models.TextField(blank=True, verbose_name="РќРµРІРѕР·РјРѕР¶РЅС‹Рµ РґРЅРё")
    is_substitute = models.BooleanField(
        default=False,
        verbose_name="Р’ РїСѓР»Рµ РїРѕРґРјРµРЅРЅС‹С… С‚СЂРµРЅРµСЂРѕРІ"
    )
    substitute_priority = models.PositiveSmallIntegerField(
        default=50,
        verbose_name="РџСЂРёРѕСЂРёС‚РµС‚ РїРѕРґРјРµРЅС‹"
    )

    # РЅР°РїСЂР°РІР»РµРЅРёСЏ:
    workout_types = models.ManyToManyField(
        'WorkoutType',
        blank=True,
        verbose_name="РќР°РїСЂР°РІР»РµРЅРёСЏ, РєРѕС‚РѕСЂС‹Рµ РІРµРґС‘С‚"
    )

    def __str__(self):
        return f"{self.user_profile.user.get_full_name()}"


    class Meta:
        verbose_name = "РЎРѕС‚СЂСѓРґРЅРёРє"
        verbose_name_plural = "РЎРѕС‚СЂСѓРґРЅРёРєРё"

    def __str__(self):
        return f"{self.user_profile.user.get_full_name() or self.user_profile.user.username}"



@receiver(post_save, sender=UserProfile)
def create_employee_for_user_profile(sender, instance, created, **kwargs):
    if created:
        Employee.objects.get_or_create(user_profile=instance)


class Schedule(models.Model):
    """
    РњРѕРґРµР»СЊ РіСЂР°С„РёРєР° СЂР°Р±РѕС‚С‹ РЅР° РѕРїСЂРµРґРµР»РµРЅРЅС‹Р№ РїРµСЂРёРѕРґ.
    """
    name = models.CharField(max_length=200, verbose_name="РќР°Р·РІР°РЅРёРµ РіСЂР°С„РёРєР°")
    start_date = models.DateField(verbose_name="Р”Р°С‚Р° РЅР°С‡Р°Р»Р°")
    end_date = models.DateField(verbose_name="Р”Р°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ")


    # РЎС‚Р°С‚СѓСЃ РіСЂР°С„РёРєР°
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('pending', 'На согласовании'),
        ('approved', 'Утвержден')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="РЎРѕР·РґР°С‚РµР»СЊ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ")

    class Meta:
        verbose_name = "Р“СЂР°С„РёРє СЂР°Р±РѕС‚С‹"
        verbose_name_plural = "Р“СЂР°С„РёРєРё СЂР°Р±РѕС‚С‹"

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"



class ShiftAssignment(models.Model):
    """
    РќР°Р·РЅР°С‡РµРЅРёРµ СЃРѕС‚СЂСѓРґРЅРёРєР° РЅР° РєРѕРЅРєСЂРµС‚РЅРѕРµ Р·Р°РЅСЏС‚РёРµ РІ РєРѕРЅРєСЂРµС‚РЅС‹Р№ РґРµРЅСЊ Рё РІСЂРµРјСЏ.
    """
    # РЎРІСЏР·СЊ СЃ РіСЂР°С„РёРєРѕРј
    schedule = models.ForeignKey('Schedule', on_delete=models.CASCADE, related_name='assignments')

    # РЎРѕС‚СЂСѓРґРЅРёРє, РєРѕС‚РѕСЂРѕРіРѕ РЅР°Р·РЅР°С‡Р°СЋС‚
    employee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name="РЎРѕС‚СЂСѓРґРЅРёРє")

    # РўРёРї Р·Р°РЅСЏС‚РёСЏ (РґР»СЏ С‚СЂРµРЅРµСЂРѕРІ) РёР»Рё РїСЂРѕСЃС‚Рѕ "Р Р°Р±РѕС‚Р°" (РґР»СЏ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРІ)
    workout_type = models.ForeignKey(
        WorkoutType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="РўРёРї Р·Р°РЅСЏС‚РёСЏ"
    )
    
    

    # Р’СЂРµРјРµРЅРЅС‹Рµ СЂР°РјРєРё
    date = models.DateField(verbose_name="Р”Р°С‚Р°")
    start_time = models.TimeField(verbose_name="Р’СЂРµРјСЏ РЅР°С‡Р°Р»Р°")
    end_time = models.TimeField(verbose_name="Р’СЂРµРјСЏ РѕРєРѕРЅС‡Р°РЅРёСЏ", null=True, blank=True)

    # РЎС‚Р°С‚СѓСЃ РЅР°Р·РЅР°С‡РµРЅРёСЏ
    STATUS_CHOICES = [
        ('scheduled', 'Запланировано'),
        ('confirmed', 'Подтверждено'),
        ('completed', 'Выполнено'),
        ('cancelled', 'Отменено'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Р¤Р°РєС‚РёС‡РµСЃРєРё РѕС‚СЂР°Р±РѕС‚Р°РЅРЅС‹Рµ С‡Р°СЃС‹ (Р·Р°РїРѕР»РЅСЏРµС‚СЃСЏ РїРѕСЃС‚С„Р°РєС‚СѓРј)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Р¤Р°РєС‚. С‡Р°СЃС‹")

    class Meta:
        verbose_name = "РќР°Р·РЅР°С‡РµРЅРёРµ РЅР° Р·Р°РЅСЏС‚РёРµ"
        verbose_name_plural = "РќР°Р·РЅР°С‡РµРЅРёСЏ РЅР° Р·Р°РЅСЏС‚РёСЏ"
        unique_together = ['employee', 'date', 'start_time']  # РЎРѕС‚СЂСѓРґРЅРёРє РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РІ РґРІСѓС… РјРµСЃС‚Р°С… РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ

    def __str__(self):
        # Р•РґРёРЅСЃС‚РІРµРЅРЅС‹Р№, РїСЂР°РІРёР»СЊРЅС‹Р№ РјРµС‚РѕРґ __str__
        end_time_str = self.end_time.strftime('%H:%M') if self.end_time else '??:??'
        return f"{self.employee.user.username} - {self.workout_type or 'Работа'} ({self.date} {self.start_time.strftime('%H:%M')}-{end_time_str})"

    # def get_payment_amount(self):
    #     """
    #     Р Р°СЃСЃС‡РёС‚С‹РІР°РµС‚ СЃСѓРјРјСѓ Рє РІС‹РїР»Р°С‚Рµ Р·Р° СЌС‚Рѕ РЅР°Р·РЅР°С‡РµРЅРёРµ.
    #     """
    #     if self.employee.position == 'trainer':
    #         # Р”Р»СЏ С‚СЂРµРЅРµСЂР°: СЃС‚Р°РІРєР° Р·Р° Р·Р°РЅСЏС‚РёРµ
    #         return self.workout_type.rate_per_session if self.workout_type else 0
    #     elif self.employee.position == 'administrator':
    #         # Р”Р»СЏ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂР°: СЃС‚Р°РІРєР° Р·Р° РґРµРЅСЊ
    #         return ADMIN_RATE_PER_DAY
    #     return 0


    #РІС‹С‡РёСЃР»СЏРµС‚ РїСЂРѕРґРѕР»Р¶РёС‚РµР»СЊРЅРѕСЃС‚СЊ СЃРјРµРЅС‹ РІ С‡Р°СЃР°С…
    def get_duration(self):
        from datetime import datetime, date
        # РЎРѕР·РґР°С‘Рј "С„РёРєС‚РёРІРЅСѓСЋ" РґР°С‚Сѓ (01.01.0001), С‡С‚РѕР±С‹ РїСЂРµРІСЂР°С‚РёС‚СЊ РІСЂРµРјСЏ РІ РїРѕР»РЅРѕС†РµРЅРЅС‹Р№ datetime
        start = datetime.combine(date.min, self.start_time)  # в†’ datetime(1, 1, 1, 9, 0)
        end = datetime.combine(date.min, self.end_time)  # в†’ datetime(1, 1, 1, 10, 0)

        # РЎС‡РёС‚Р°РµРј СЂР°Р·РЅРёС†Сѓ РІ СЃРµРєСѓРЅРґР°С… Рё РїРµСЂРµРІРѕРґРёРј РІ С‡Р°СЃС‹
        return (end - start).total_seconds() / 3600  # в†’ 1.0




class TimeOffRequest(models.Model):
    """
    Р—Р°СЏРІРєР° РЅР° РѕС‚РіСѓР»/РѕС‚РїСѓСЃРє.
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

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, verbose_name="РЎРѕС‚СЂСѓРґРЅРёРє")
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES, default='personal')
    start_date = models.DateField(verbose_name="Р”Р°С‚Р° РЅР°С‡Р°Р»Р°")
    end_date = models.DateField(verbose_name="Р”Р°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ")
    reason = models.TextField(verbose_name="РџСЂРёС‡РёРЅР°")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Р”Р°С‚Р° РѕР±РЅРѕРІР»РµРЅРёСЏ")

    class Meta:
        verbose_name = "Р—Р°СЏРІРєР° РЅР° РѕС‚РіСѓР»"
        verbose_name_plural = "Р—Р°СЏРІРєРё РЅР° РѕС‚РіСѓР»"

    def __str__(self):
        return f"{self.employee} - {self.get_request_type_display()} ({self.start_date} - {self.end_date})"



class ShiftSwapRequest(models.Model):
    """
    Р—Р°СЏРІРєР° РЅР° РѕР±РјРµРЅ СЃРјРµРЅР°РјРё РјРµР¶РґСѓ СЃРѕС‚СЂСѓРґРЅРёРєР°РјРё.
    """
    from_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='swap_requests_sent')
    to_employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='swap_requests_received')
    reason = models.TextField(verbose_name="РџСЂРёС‡РёРЅР° РѕР±РјРµРЅР°")

    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved_by_employee', 'Одобрено сотрудником'),
        ('approved_by_manager', 'Одобрено руководителем'),
        ('completed', 'Завершено'),
        ('rejected', 'Отклонено'),
    ]
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Р”Р°С‚Р° СЃРѕР·РґР°РЅРёСЏ")

    class Meta:
        verbose_name = "Р—Р°СЏРІРєР° РЅР° РѕР±РјРµРЅ СЃРјРµРЅР°РјРё"
        verbose_name_plural = "Р—Р°СЏРІРєРё РЅР° РѕР±РјРµРЅ СЃРјРµРЅР°РјРё"

    def __str__(self):
        return f"Обмен: {self.from_employee} -> {self.to_employee}"


class SwapShift(models.Model):
    """
    РЎРјРµРЅР°, СѓС‡Р°СЃС‚РІСѓСЋС‰Р°СЏ РІ РѕР±РјРµРЅРµ.
    """
    swap_request = models.ForeignKey(ShiftSwapRequest, on_delete=models.CASCADE, related_name='shifts')
    shift_assignment = models.ForeignKey(ShiftAssignment, on_delete=models.CASCADE, verbose_name="РЎРјРµРЅР° РґР»СЏ РѕР±РјРµРЅР°")

    class Meta:
        verbose_name = "РЎРјРµРЅР° РІ РѕР±РјРµРЅРµ"
        verbose_name_plural = "РЎРјРµРЅС‹ РІ РѕР±РјРµРЅРµ"

    def __str__(self):
        return f"{self.shift_assignment} in {self.swap_request}"



class OptimizationRule(models.Model):
    """
    РџСЂР°РІРёР»Рѕ РґР»СЏ Р°Р»РіРѕСЂРёС‚РјР° РѕРїС‚РёРјРёР·Р°С†РёРё.
    """
    RULE_TYPES = [
        ('legal', 'Законодательное'),
        ('business', 'Бизнес-правило'),
        ('preference', 'Предпочтение'),
    ]

    name = models.CharField(max_length=200, verbose_name="РќР°Р·РІР°РЅРёРµ РїСЂР°РІРёР»Р°")
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, default='business')
    description = models.TextField(verbose_name="РћРїРёСЃР°РЅРёРµ РїСЂР°РІРёР»Р°")

    # РџР°СЂР°РјРµС‚СЂС‹ РїСЂР°РІРёР»Р°
    min_employees_per_shift = models.IntegerField(null=True, blank=True, verbose_name="РњРёРЅ. СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ РІ СЃРјРµРЅСѓ")
    max_employees_per_shift = models.IntegerField(null=True, blank=True, verbose_name="РњР°РєСЃ. СЃРѕС‚СЂСѓРґРЅРёРєРѕРІ РІ СЃРјРµРЅСѓ")
    max_consecutive_shifts = models.IntegerField(null=True, blank=True, verbose_name="РњР°РєСЃ. СЃРјРµРЅ РїРѕРґСЂСЏРґ")
    min_rest_hours = models.IntegerField(null=True, blank=True, verbose_name="РњРёРЅ. С‡Р°СЃРѕРІ РѕС‚РґС‹С…Р° РјРµР¶РґСѓ СЃРјРµРЅР°РјРё")

    is_active = models.BooleanField(default=True, verbose_name="РђРєС‚РёРІРЅРѕ")
    priority = models.IntegerField(default=1, verbose_name="РџСЂРёРѕСЂРёС‚РµС‚")

    class Meta:
        verbose_name = "РџСЂР°РІРёР»Рѕ РѕРїС‚РёРјРёР·Р°С†РёРё"
        verbose_name_plural = "РџСЂР°РІРёР»Р° РѕРїС‚РёРјРёР·Р°С†РёРё"
        ordering = ['priority', 'rule_type']

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"



class Availability(models.Model):
    employee = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name="РЎРѕС‚СЂСѓРґРЅРёРє")
    date = models.DateField(verbose_name="Р”Р°С‚Р°")
    start_time = models.TimeField(verbose_name="РќР°С‡Р°Р»Рѕ СЃР»РѕС‚Р°")
    end_time = models.TimeField(verbose_name="РћРєРѕРЅС‡Р°РЅРёРµ СЃР»РѕС‚Р°")
    is_available = models.BooleanField(default=True, verbose_name="Р”РѕСЃС‚СѓРїРµРЅ")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="РџРѕСЃР»РµРґРЅРµРµ РѕР±РЅРѕРІР»РµРЅРёРµ")

    class Meta:
        verbose_name = "Р”РѕСЃС‚СѓРїРЅРѕСЃС‚СЊ"
        verbose_name_plural = "Р”РѕСЃС‚СѓРїРЅРѕСЃС‚СЊ"
        unique_together = ('employee', 'date', 'start_time')

    def __str__(self):
        return f"{self.employee.user.username} вЂ” {self.date} {self.start_time}вЂ“{self.end_time}"



#СЃРѕРіР»Р°СЃРѕРІР°РЅРёРµ РіСЂР°С„РёРєР°: РјРѕРґРµР»СЊ РѕС‚Р·С‹РІР°
class ScheduleApproval(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='approvals')
    employee = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    approved = models.BooleanField(null=True)  # True/False/None
    comment = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('schedule', 'employee')


class ChatConversation(models.Model):
    """
    Р›РёС‡РЅС‹Р№ РґРёР°Р»РѕРі РјРµР¶РґСѓ РґРІСѓРјСЏ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРјРё.
    participant_a Рё participant_b РІСЃРµРіРґР° С…СЂР°РЅСЏС‚СЃСЏ РІ СЃС‚Р°Р±РёР»СЊРЅРѕРј РїРѕСЂСЏРґРєРµ (РїРѕ id),
    С‡С‚РѕР±С‹ РЅРµ СЃРѕР·РґР°РІР°С‚СЊ РґСѓР±Р»РёРєР°С‚С‹ РґРёР°Р»РѕРіРѕРІ РґР»СЏ РѕРґРЅРѕР№ РїР°СЂС‹ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№.
    """
    participant_a = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_conversations_as_a',
        verbose_name='РЈС‡Р°СЃС‚РЅРёРє A',
        null=True,
        blank=True,
    )
    participant_b = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_conversations_as_b',
        verbose_name='РЈС‡Р°СЃС‚РЅРёРє B',
        null=True,
        blank=True,
    )
    is_group = models.BooleanField(default=False, verbose_name='Р“СЂСѓРїРїРѕРІРѕР№ С‡Р°С‚')
    title = models.CharField(max_length=200, blank=True, verbose_name='РќР°Р·РІР°РЅРёРµ РіСЂСѓРїРїС‹')
    participants = models.ManyToManyField(
        User,
        related_name='chat_conversations',
        blank=True,
        verbose_name='РЈС‡Р°СЃС‚РЅРёРєРё',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='РЎРѕР·РґР°РЅ')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='РћР±РЅРѕРІР»РµРЅ')

    class Meta:
        verbose_name = 'Р”РёР°Р»РѕРі'
        verbose_name_plural = 'Р”РёР°Р»РѕРіРё'
        constraints = [
            models.UniqueConstraint(
                fields=['participant_a', 'participant_b'],
                condition=Q(participant_a__isnull=False, participant_b__isnull=False, is_group=False),
                name='unique_chat_conversation_pair',
            ),
        ]
        ordering = ['-updated_at']

    def __str__(self):
        if self.is_group:
            return self.title or f'Р“СЂСѓРїРїР° #{self.id}'
        if self.participant_a and self.participant_b:
            return f'Р”РёР°Р»РѕРі: {self.participant_a.username} в†” {self.participant_b.username}'
        return f'Р”РёР°Р»РѕРі #{self.id}'

    def get_other_user(self, current_user):
        return self.participant_b if self.participant_a_id == current_user.id else self.participant_a


class ChatConversationPin(models.Model):
    """
    Р—Р°РєСЂРµРїР»РµРЅРёРµ РґРёР°Р»РѕРіР° РєРѕРЅРєСЂРµС‚РЅС‹Рј РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_pins',
        verbose_name='РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ',
    )
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='pins',
        verbose_name='Р”РёР°Р»РѕРі',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Р—Р°РєСЂРµРїР»РµРЅРѕ РІ')

    class Meta:
        verbose_name = 'Р—Р°РєСЂРµРїР»РµРЅРЅС‹Р№ РґРёР°Р»РѕРі'
        verbose_name_plural = 'Р—Р°РєСЂРµРїР»РµРЅРЅС‹Рµ РґРёР°Р»РѕРіРё'
        constraints = [
            models.UniqueConstraint(fields=['user', 'conversation'], name='unique_chat_conversation_pin'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} pinned #{self.conversation_id}'


class ChatMessage(models.Model):
    """
    РЎРѕРѕР±С‰РµРЅРёРµ РІ Р»РёС‡РЅРѕРј РґРёР°Р»РѕРіРµ.
    """
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Р”РёР°Р»РѕРі',
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_messages_sent',
        verbose_name='РћС‚РїСЂР°РІРёС‚РµР»СЊ',
    )
    text = models.TextField(verbose_name='РўРµРєСЃС‚ СЃРѕРѕР±С‰РµРЅРёСЏ')
    is_read = models.BooleanField(default=False, verbose_name='РџСЂРѕС‡РёС‚Р°РЅРѕ')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='РћС‚РїСЂР°РІР»РµРЅРѕ')

    class Meta:
        verbose_name = 'РЎРѕРѕР±С‰РµРЅРёРµ С‡Р°С‚Р°'
        verbose_name_plural = 'РЎРѕРѕР±С‰РµРЅРёСЏ С‡Р°С‚Р°'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.created_at:%d.%m.%Y %H:%M}] {self.sender.username}: {self.text[:30]}'


class ChatMessageRead(models.Model):
    """
    РџРµСЂСЃРѕРЅР°Р»СЊРЅС‹Р№ СЃС‚Р°С‚СѓСЃ РїСЂРѕС‡С‚РµРЅРёСЏ СЃРѕРѕР±С‰РµРЅРёСЏ РєРѕРЅРєСЂРµС‚РЅС‹Рј РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј.
    """
    message = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='read_states',
        verbose_name='РЎРѕРѕР±С‰РµРЅРёРµ',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='chat_message_read_states',
        verbose_name='РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ',
    )
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='РџСЂРѕС‡РёС‚Р°РЅРѕ РІ')

    class Meta:
        verbose_name = 'РЎС‚Р°С‚СѓСЃ РїСЂРѕС‡С‚РµРЅРёСЏ СЃРѕРѕР±С‰РµРЅРёСЏ'
        verbose_name_plural = 'РЎС‚Р°С‚СѓСЃС‹ РїСЂРѕС‡С‚РµРЅРёСЏ СЃРѕРѕР±С‰РµРЅРёР№'
        constraints = [
            models.UniqueConstraint(fields=['message', 'user'], name='unique_message_read_state'),
        ]

    def __str__(self):
        return f'Р§С‚РµРЅРёРµ СЃРѕРѕР±С‰РµРЅРёСЏ #{self.message_id} РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј {self.user.username}'

