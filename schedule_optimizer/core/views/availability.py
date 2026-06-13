"""Страницы доступности сотрудников и ручной отправки напоминаний."""

from .auth import *
from .distribution_rules import _generate_studio_slots

@login_required
def my_availability(request):
    """Позволяет сотруднику указать доступность по слотам на выбранную неделю."""
    user_profile = request.user.profile
    if user_profile.role != 'employee':
        messages.error(request, "Доступно только для сотрудников.")
        return redirect('dashboard')

    # === POST handling: save data ===
    if request.method == "POST":
        week_str = request.POST.get('selected_week')
        if week_str:
            try:
                week_start = datetime.strptime(week_str, '%Y-%m-%d').date()
                if week_start.weekday() != 0:
                    week_start = week_start - timedelta(days=week_start.weekday())
            except (ValueError, TypeError):
                messages.error(request, "Неверный формат даты.")
                return redirect('my_availability')
        else:
            today = datetime.today()
            days_ahead = (7 - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            week_start = today + timedelta(days=days_ahead)

        # Генерация дней
        current_days = [week_start + timedelta(days=i) for i in range(7)]
        date_strings = [d.strftime('%Y-%m-%d') for d in current_days]

        # Слоты (с учетом обеда 14:00-16:00)
        slots = _generate_studio_slots()

        print("=== POST KEYS ===")
        print(list(request.POST.keys()))
        print("=== EXPECTED SAMPLE ===")
        print(f"Sample key: {date_strings[0]}_{slots[0][0]}")

        # Удаление старых записей
        Availability.objects.filter(
            employee=user_profile,
            date__in=current_days
        ).delete()

        # Сохранение новых
        new_records = []
        for day_str in date_strings:
            for slot_start, slot_end in slots:
                key = f"{day_str}_{slot_start}"
                if request.POST.get(key) == 'on':  # <- enabled
                    date_obj = datetime.strptime(day_str, '%Y-%m-%d').date()
                    start_time = datetime.strptime(slot_start, '%H:%M').time()
                    end_time = datetime.strptime(slot_end, '%H:%M').time()
                    new_records.append(Availability(
                        employee=user_profile,
                        date=date_obj,
                        start_time=start_time,
                        end_time=end_time,
                        is_available=True
                    ))

        if new_records:
            Availability.objects.bulk_create(new_records)
            messages.success(request, "Доступность успешно сохранена!")
        else:
            messages.info(request, "Доступность не указана.")

        return redirect(f"{request.path}?week={week_start.strftime('%Y-%m-%d')}")

    # === GET handling: render form ===
    today = datetime.today()
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    default_week_start = today + timedelta(days=days_ahead)

    week_start = default_week_start
    week_param = request.GET.get('week')
    if week_param:
        try:
            parsed_date = datetime.strptime(week_param, '%Y-%m-%d').date()
            week_start = parsed_date - timedelta(days=parsed_date.weekday())
        except (ValueError, TypeError):
            pass

    # Генерация дней (без спискового включения — через цикл)
    current_days = []
    for i in range(7):
        current_days.append(week_start + timedelta(days=i))
    date_strings = [d.strftime('%Y-%m-%d') for d in current_days]

    # Слоты (с учетом обеда 14:00-16:00)
    slots = _generate_studio_slots()

    # Загрузка данных
    availabilities = Availability.objects.filter(
        employee=user_profile,
        date__in=current_days
    )
    checked_keys = set()
    for a in availabilities:
        key = f"{a.date.strftime('%Y-%m-%d')}_{a.start_time.strftime('%H:%M')}"
        checked_keys.add(key)

    last_updated = availabilities.order_by('-updated_at').first()

    # === Previous-week data for JS ===
    prev_week_start = week_start - timedelta(weeks=1)
    prev_avail = Availability.objects.filter(
        employee=user_profile,
        date__gte=prev_week_start,
        date__lt=week_start
    )
    prev_avail_list = []
    for a in prev_avail:
        # Сдвигаем дату на неделю вперёд
        new_date = a.date + timedelta(weeks=1)
        prev_avail_list.append({
            'date': new_date.strftime('%Y-%m-%d'),
            'time': a.start_time.strftime('%H:%M')
        })

    prev_week = (week_start - timedelta(weeks=1)).strftime('%Y-%m-%d')
    next_week = (week_start + timedelta(weeks=1)).strftime('%Y-%m-%d')

    context = {
        'days': current_days,
        'date_strings': date_strings,
        'slots': slots,
        'checked_keys': checked_keys,
        'last_updated': last_updated,
        'week_start': week_start,
        'week_end': week_start + timedelta(days=6),
        'prev_week': prev_week,
        'next_week': next_week,
        'prev_avail_json': json.dumps(prev_avail_list),
    }
    return render(request, 'core/availability/my_availability.html', context)


#для отправки напоминаний о доступности
@login_required
@user_passes_test(lambda u: u.profile.role == 'manager')
def send_availability_reminder_manual(request):
    """Отправляет сотрудникам email-напоминание о заполнении доступности."""
    if request.method == "POST":
        employees = UserProfile.objects.filter(role='employee')
        emails = [emp.user.email for emp in employees if emp.user.email]
        if emails:
            ok = send_mail_with_fallback(
                subject="Напоминание: укажите ваши рабочие часы",
                message="Пожалуйста, зайдите в личный кабинет и укажите, когда вы можете работать на следующей неделе.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=emails,
            )
            if ok:
                messages.success(request, f"Напоминание отправлено {len(emails)} сотрудникам.")
            else:
                messages.error(
                    request,
                    "Письма не отправлены: почтовый сервер недоступен или отклоняет подключение. "
                    "Проверьте настройки SMTP и пароль приложения."
                )
        else:
            messages.warning(request, "Нет сотрудников с email.")
    return redirect('schedule_view')
