$ErrorActionPreference = 'Stop'

$src = 'C:\Users\miles\Desktop\учеба\4 rehc\преддипломная практика\03_Степанова_отчет_преддипломная_практика.docx'
$dst = 'C:\Users\miles\Desktop\учеба\4 rehc\преддипломная практика\03_Степанова_отчет_преддипломная_практика_новые_внедрения_финал.docx'
$imgDir = 'C:\Users\miles\Desktop\учеба\4 rehc\преддипломная практика'

$imgAvailability = Join-Path $imgDir 'быстрый просмотр доступности.png'
$imgVariants = Join-Path $imgDir 'сравнение 3 вариантов.png'
$imgVersions = Join-Path $imgDir 'версии и откат.png'

Copy-Item -LiteralPath $src -Destination $dst -Force

function Clean-Text([string]$text) {
    if ($null -eq $text) { return '' }
    return $text.Replace("`r", '').Replace([char]7, '').Trim()
}

function Set-ParagraphText($doc, [int]$index, [string]$text) {
    $doc.Paragraphs.Item($index).Range.Text = $text + "`r"
}

function Remove-Range($doc, [int]$startParagraph, [int]$endParagraphExclusive) {
    if ($endParagraphExclusive -le $startParagraph) { return }
    $start = $doc.Paragraphs.Item($startParagraph).Range.Start
    $end = $doc.Paragraphs.Item($endParagraphExclusive).Range.Start
    $doc.Range($start, $end).Delete()
}

function Insert-PlainParagraphsAt($doc, [ref]$pos, [string[]]$paragraphs) {
    foreach ($paragraph in $paragraphs) {
        $range = $doc.Range($pos.Value, $pos.Value)
        $range.Text = $paragraph + "`r"
        $range.Style = -1
        $range.Font.Name = 'Times New Roman'
        $range.Font.Size = 14
        $pos.Value = $range.End
    }
}

function Insert-ImageWithCaptionAt($doc, [ref]$pos, [string]$imagePath, [string]$caption, [int]$width = 430) {
    $imgRange = $doc.Range($pos.Value, $pos.Value)
    $shape = $doc.InlineShapes.AddPicture($imagePath, $false, $true, $imgRange)
    if ($shape.Width -gt $width) {
        $shape.LockAspectRatio = $true
        $shape.Width = $width
    }
    $capRange = $doc.Range($shape.Range.End, $shape.Range.End)
    $capRange.Text = "`r" + $caption + "`r"
    $capRange.Style = -1
    $capRange.ParagraphFormat.Alignment = 1
    $capRange.Font.Name = 'Times New Roman'
    $capRange.Font.Size = 14
    $pos.Value = $capRange.End
}

function Insert-ListingAt($doc, [ref]$pos, [string]$leadText, [string]$caption, [string[]]$codeLines) {
    $lead = $doc.Range($pos.Value, $pos.Value)
    $lead.Text = $leadText + "`r"
    $lead.Style = -1
    $lead.Font.Name = 'Times New Roman'
    $lead.Font.Size = 14
    $pos.Value = $lead.End

    $cap = $doc.Range($pos.Value, $pos.Value)
    $cap.Text = $caption + "`r"
    $cap.Style = -1
    $cap.ParagraphFormat.Alignment = 1
    $cap.Font.Name = 'Times New Roman'
    $cap.Font.Size = 14
    $pos.Value = $cap.End

    $codeText = ($codeLines -join "`r") + "`r"
    $code = $doc.Range($pos.Value, $pos.Value)
    $code.Text = $codeText
    $code.Style = -1
    $code.Font.Name = 'Courier New'
    $code.Font.Size = 10
    $code.ParagraphFormat.Alignment = 0
    $pos.Value = $code.End
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open($dst)

try {
    # Headings in body
    Set-ParagraphText $doc 41 '1. Разработка интерфейса информационной системы'
    Set-ParagraphText $doc 45 '1.1 Страница создания графика: быстрый просмотр доступности'
    Set-ParagraphText $doc 98 '1.2 Страница создания графика: сравнение вариантов'
    Set-ParagraphText $doc 170 '1.3 Страница настройки правил распределения'

    Set-ParagraphText $doc 232 '2. Разработка базы данных информационной системы'
    Set-ParagraphText $doc 238 '2.1 Модели правил распределения'
    Set-ParagraphText $doc 272 '2.2 Модели версионирования графика'

    Set-ParagraphText $doc 397 '3. Разработка функциональной части информационной системы'
    Set-ParagraphText $doc 401 '3.1 Автоматическая проверка и применение правил'
    Set-ParagraphText $doc 451 '3.2 Быстрый просмотр доступности и моделирование вариантов'
    Set-ParagraphText $doc 534 '3.3 Система версий графика, сравнение и откат'

    # Conclusion
    Remove-Range $doc 561 571
    $pos = $doc.Paragraphs.Item(560).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'В ходе преддипломной практики информационная система гибкого планирования смен была доработана только в части нового функционала, расширяющего возможности автоматического формирования и сопровождения графика. Основное внимание было уделено тем механизмам, которые непосредственно упрощают работу руководителя при создании и корректировке расписания.',
        'В системе были реализованы модуль правил распределения направлений занятий, отдельная страница настройки этих правил, автоматическая проверка и применение активных ограничений при формировании графика, быстрый просмотр доступности сотрудников на странице создания расписания, сравнение нескольких вариантов графика с выбором лучшего решения, а также система версий с возможностью сравнения и отката.',
        'В результате преддипломной практики система стала более удобной для повседневной работы, поскольку руководитель получил инструменты не только для составления графика, но и для его оценки, уточнения и безопасного восстановления предыдущих состояний. Поставленные задачи преддипломной практики выполнены в полном объеме.'
    )

    # Section 3.3
    Remove-Range $doc 535 560
    $pos = $doc.Paragraphs.Item(534).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'На странице просмотра графика был добавлен блок версий, позволяющий сохранять промежуточные состояния расписания, сравнивать их между собой и при необходимости возвращаться к ранее зафиксированному варианту. Такой механизм особенно важен при поэтапной доработке графика, когда руководителю нужно оценить последствия изменений и не потерять рабочую версию.'
    )
    Insert-ImageWithCaptionAt $doc ([ref]$pos) $imgVersions 'Рисунок 3.1 - Система версий графика, сравнение версий и откат'
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 3.3 приведен фрагмент серверной логики сохранения версии и отката графика.' 'Листинг 3.3 - Фрагмент серверной логики версионирования графика' @(
        'def _create_schedule_version(schedule, created_by=None, source="", note=""):',
        '    last_number = (',
        '        ScheduleVersion.objects.filter(schedule=schedule)',
        '        .order_by("-version_number")',
        '        .values_list("version_number", flat=True)',
        '        .first() or 0',
        '    )',
        '    version = ScheduleVersion.objects.create(',
        '        schedule=schedule,',
        '        version_number=last_number + 1,',
        '        schedule_name=schedule.name,',
        '        created_by=created_by if getattr(created_by, "is_authenticated", False) else None,',
        '        change_source=(source or "")[:30],',
        '        change_note=(note or "")[:255],',
        '    )',
        '',
        'def api_restore_schedule_version(request, schedule_id, version_id):',
        '    version = get_object_or_404(ScheduleVersion, id=version_id, schedule=schedule)',
        '    ShiftAssignment.objects.filter(schedule=schedule).delete()',
        '    for row in version.assignments.all():',
        '        ShiftAssignment.objects.create(',
        '            schedule=schedule, employee_id=row.employee_id,',
        '            workout_type_id=row.workout_type_id, date=row.date,',
        '            start_time=row.start_time, end_time=row.end_time,',
        '        )',
        '    _create_schedule_version(schedule, created_by=request.user, source="restore",',
        '                             note=f"Откат к версии v{version.version_number}")'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Представленный фрагмент показывает, что при сохранении создается отдельная запись версии и набор снимков по каждой ячейке расписания. При откате текущие назначения удаляются, после чего восстанавливаются данные из выбранной версии и автоматически фиксируется новая версия-откат.'
    )

    # Section 3.2
    Remove-Range $doc 452 534
    $pos = $doc.Paragraphs.Item(451).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'На странице создания графика была расширена клиентская логика, связанная с анализом доступности и выбором наиболее удачного варианта расписания. Руководитель может быстро посмотреть доступность конкретного сотрудника по дням недели, после чего запустить расчет нескольких вариантов заполнения и применить лучший из них непосредственно в таблицу.'
    )
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 3.2 приведен фрагмент клиентской логики моделирования и применения вариантов графика.' 'Листинг 3.2 - Фрагмент клиентской логики сравнения вариантов графика' @(
        'function runThreeVariantSimulation() {',
        '    const baseSeed = Date.now() & 0xffffffff;',
        '    const currentPlan = readCurrentPlanFromTable();',
        '    const variants = [',
        '        { plan: currentPlan, metrics: calculatePlanMetrics(currentPlan), label: "Текущий вариант" },',
        '        buildAutoFillPlan(baseSeed + 9973),',
        '        buildAutoFillPlan(baseSeed + 19946),',
        '    ];',
        '    variants.sort((a, b) => {',
        '        if (a.metrics.empty !== b.metrics.empty) return a.metrics.empty - b.metrics.empty;',
        '        return a.metrics.balance_std - b.metrics.balance_std;',
        '    });',
        '    LAST_SIMULATION_VARIANTS = variants;',
        '    renderSimulationResults(variants);',
        '}',
        '',
        'document.addEventListener("click", function (event) {',
        '    const applyBtn = event.target.closest(".apply-variant-btn");',
        '    if (!applyBtn) return;',
        '    const idx = Number(applyBtn.dataset.variant || -1);',
        '    applyPlanToTable(LAST_SIMULATION_VARIANTS[idx].plan);',
        '});'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Алгоритм формирует несколько вариантов заполнения на основе текущего плана и автоматически рассчитанных комбинаций. После сортировки по числу пустых слотов и балансу нагрузки результаты выводятся на экран, а выбранный вариант может быть сразу применен без повторного ручного ввода.'
    )

    # Section 3.1
    Remove-Range $doc 402 451
    $pos = $doc.Paragraphs.Item(401).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Новый модуль правил распределения влияет на формирование расписания уже на этапе автозаполнения. Перед назначением тренировки в конкретную ячейку система проверяет активные ограничения: недельные лимиты по направлению, запрет повторов в одном окне дня, ограничения по последовательности категорий и другие условия, заданные руководителем.'
    )
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 3.1 приведен фрагмент клиентской логики проверки и применения правил при создании графика.' 'Листинг 3.1 - Фрагмент проверки активных правил распределения' @(
        'function checkRules(dayStr, startTime, workoutObj) {',
        '    const reasons = [];',
        '    for (const rule of ACTIVE_DISTRIBUTION_RULES) {',
        '        const params = rule.params || {};',
        '        if (rule.rule_type === "weekly_limit") {',
        '            const target = normalizeWorkoutNameForRule(params.workout_name || "");',
        '            const workoutNorm = normalizeWorkoutNameForRule(workoutObj.name || "");',
        '            if (target && workoutNorm.includes(target)) {',
        '                const totalKey = `${rule.id}|workout:${target}|total`;',
        '                const usedTotal = state.weeklyWorkoutTotalCount[totalKey] || 0;',
        '                if (params.max_total !== undefined && usedTotal >= Number(params.max_total || 0)) {',
        '                    reasons.push(formatRuleLabel(rule));',
        '                }',
        '            }',
        '        }',
        '    }',
        '    return reasons;',
        '}',
        '',
        'function commitRules(dayStr, startTime, workoutObj) {',
        '    for (const rule of ACTIVE_DISTRIBUTION_RULES) {',
        '        // после выбора тренировки счетчики правила обновляются',
        '    }',
        '}'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Сначала функция определяет, нарушает ли выбранное направление хотя бы одно из активных ограничений, а затем после подтвержденного назначения обновляет счетчики использования. За счет этого правила не только отображаются в интерфейсе, но и реально участвуют в алгоритме автосоздания графика.'
    )

    # Delete old section 2.3 completely
    Remove-Range $doc 368 397

    # Section 2.2
    Remove-Range $doc 273 368
    $pos = $doc.Paragraphs.Item(272).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Для реализации механизма сравнения и отката графиков в структуру базы данных были добавлены отдельные сущности, фиксирующие каждую сохраненную версию расписания и состав назначений, относящихся к этой версии.'
    )
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 2.3 приведена модель хранения версии графика.' 'Листинг 2.3 - Модель «Версия графика»' @(
        'class ScheduleVersion(models.Model):',
        '    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name="versions")',
        '    version_number = models.PositiveIntegerField(verbose_name="Номер версии")',
        '    schedule_name = models.CharField(max_length=200, verbose_name="Название графика в версии")',
        '    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,',
        '                                   related_name="created_schedule_versions")',
        '    change_source = models.CharField(max_length=30, blank=True, verbose_name="Источник изменения")',
        '    change_note = models.CharField(max_length=255, blank=True, verbose_name="Комментарий к версии")',
        '    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания версии")'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Данная сущность хранит номер версии, название графика на момент сохранения, автора изменения и текстовый комментарий. Это позволяет не только видеть историю изменений, но и различать первичное создание, обычное редактирование и откат к прошлому состоянию.'
    )
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 2.4 приведена модель хранения снимков смен внутри версии графика.' 'Листинг 2.4 - Модель «Снимок смены версии»' @(
        'class ScheduleVersionAssignment(models.Model):',
        '    schedule_version = models.ForeignKey(ScheduleVersion, on_delete=models.CASCADE, related_name="assignments")',
        '    employee = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True)',
        '    workout_type = models.ForeignKey(WorkoutType, on_delete=models.SET_NULL, null=True, blank=True)',
        '    date = models.DateField(verbose_name="Дата")',
        '    start_time = models.TimeField(verbose_name="Время начала")',
        '    end_time = models.TimeField(verbose_name="Время окончания")'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Эта таблица содержит снимок каждой заполненной ячейки расписания для конкретной версии. За счет такого подхода система может сравнивать две версии по составу смен и при необходимости полностью восстановить выбранный вариант графика.'
    )

    # Section 2.1
    Remove-Range $doc 239 272
    $pos = $doc.Paragraphs.Item(238).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Новый функционал правил распределения потребовал расширения структуры данных отдельными сущностями, в которых сохраняются параметры ограничений и условия их применения при автоматическом формировании расписания.'
    )
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 2.1 приведена модель общего правила оптимизации.' 'Листинг 2.1 - Модель «Правило оптимизации»' @(
        'class OptimizationRule(models.Model):',
        '    name = models.CharField(max_length=200, verbose_name="Название правила")',
        '    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, default="business")',
        '    description = models.TextField(verbose_name="Описание правила")',
        '    min_employees_per_shift = models.IntegerField(null=True, blank=True)',
        '    max_employees_per_shift = models.IntegerField(null=True, blank=True)',
        '    max_consecutive_shifts = models.IntegerField(null=True, blank=True)',
        '    min_rest_hours = models.IntegerField(null=True, blank=True)',
        '    is_active = models.BooleanField(default=True, verbose_name="Активно")',
        '    priority = models.IntegerField(default=1, verbose_name="Приоритет")'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Модель используется для хранения общих ограничений алгоритма планирования. В ней фиксируются тип правила, приоритет и количественные параметры, которые затем могут использоваться при расчете смен и распределении нагрузки.'
    )
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 2.2 приведена модель настраиваемого правила распределения направлений.' 'Листинг 2.2 - Модель «Правило распределения»' @(
        'class DistributionRule(models.Model):',
        '    name = models.CharField(max_length=200, verbose_name="Название правила")',
        '    source_text = models.TextField(verbose_name="Текст правила")',
        '    rule_type = models.CharField(max_length=32, choices=RULE_TYPE_CHOICES, verbose_name="Тип правила")',
        '    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="hard")',
        '    params_json = models.JSONField(default=dict, blank=True, verbose_name="Параметры (JSON)")',
        '    is_active = models.BooleanField(default=True, verbose_name="Активно")',
        '    priority = models.PositiveIntegerField(default=100, verbose_name="Приоритет")',
        '    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,',
        '                                   related_name="distribution_rules_created")',
        '    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")',
        '    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'В этой сущности сохраняются конкретные правила распределения занятий, которые руководитель задает через интерфейс. Поле JSON позволяет хранить гибкий набор параметров для разных типов ограничений без создания отдельной таблицы под каждый сценарий.'
    )

    # Section 1.3 – preserve old screenshot/listing, remove old extras
    Remove-Range $doc 210 232
    Remove-Range $doc 171 191
    $pos = $doc.Paragraphs.Item(170).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'В ходе преддипломной практики для руководителя была реализована отдельная страница настройки правил распределения. На ней можно задать условия, которые влияют на формирование расписания: лимиты по направлению, чередование категорий занятий и запрет повторов в рамках одного дня.'
    )
    Set-ParagraphText $doc 191 'На рисунке 1.3 представлена страница настройки правил распределения. Интерфейс объединяет режим текстового ввода и конструктор параметров, благодаря чему руководитель может как быстро описать правило, так и вручную задать его структуру.'
    Set-ParagraphText $doc 194 'Рисунок 1.3 - Страница настройки правил распределения'
    Set-ParagraphText $doc 195 'В листинге 1.3 приведен HTML-фрагмент страницы правил распределения.'
    Set-ParagraphText $doc 197 'Листинг 1.3 - HTML-фрагмент страницы правил распределения'

    # Section 1.2
    Remove-Range $doc 99 170
    $pos = $doc.Paragraphs.Item(98).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'На странице создания графика был добавлен отдельный блок сравнения вариантов. После запуска расчета система показывает несколько вариантов заполнения расписания, выводит показатели по каждому из них и позволяет сразу применить лучший вариант в рабочую таблицу.'
    )
    Insert-ImageWithCaptionAt $doc ([ref]$pos) $imgVariants 'Рисунок 1.2 - Блок сравнения трех вариантов графика'
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 1.2 приведен HTML-фрагмент блока сравнения вариантов на странице создания графика.' 'Листинг 1.2 - HTML-фрагмент блока сравнения вариантов графика' @(
        '<div id="simulation-results" class="management-table p-3 mb-3 d-none">',
        '    <div class="d-flex justify-content-between align-items-center mb-2">',
        '        <div class="panel-title-wrap">',
        '            <h5 class="mb-0">Сравнение 3 вариантов</h5>',
        '            <button id="simulation-toggle-btn" type="button" class="panel-arrow-btn">',
        '                <i class="bi bi-chevron-up"></i>',
        '            </button>',
        '        </div>',
        '        <div class="d-flex align-items-center gap-2">',
        '            <small class="text-muted">Выберите лучший и примените в таблицу</small>',
        '        </div>',
        '    </div>',
        '    <div id="simulation-results-body">',
        '        <div id="simulation-results-cards" class="row g-2"></div>',
        '    </div>',
        '</div>'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'В блоке предусмотрены карточки вариантов, кнопка скрытия и показа содержимого, а также область для вывода рассчитанных результатов. Такое решение позволяет не перегружать страницу и при этом быстро переключаться между ручной и автоматической настройкой графика.'
    )

    # Section 1.1
    Remove-Range $doc 46 98
    $pos = $doc.Paragraphs.Item(45).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'При доработке страницы создания графика был добавлен блок быстрого просмотра доступности сотрудников. Руководитель выбирает нужного сотрудника в выпадающем списке и сразу видит отметки доступности по дням недели без перехода на отдельную страницу. Это ускоряет проверку исходных данных перед автоматическим распределением смен.'
    )
    Insert-ImageWithCaptionAt $doc ([ref]$pos) $imgAvailability 'Рисунок 1.1 - Блок быстрого просмотра доступности сотрудника'
    Insert-ListingAt $doc ([ref]$pos) 'В листинге 1.1 приведен HTML-фрагмент блока быстрого просмотра доступности на странице создания графика.' 'Листинг 1.1 - HTML-фрагмент блока просмотра доступности' @(
        '<div id="availability-quick-panel" class="availability-quick-panel">',
        '    <div class="availability-quick-head">',
        '        <div>',
        '            <div class="panel-title-wrap">',
        '                <h6 class="availability-quick-title mb-0">Быстрый просмотр доступности</h6>',
        '                <button id="availability-toggle-btn" type="button" class="panel-arrow-btn">',
        '                    <i class="bi bi-chevron-up"></i>',
        '                </button>',
        '            </div>',
        '            <p class="availability-quick-subtitle">',
        '                Выберите сотрудника и сразу увидите, где у него отмечена доступность.',
        '            </p>',
        '        </div>',
        '        <div class="d-flex gap-2 align-items-center">',
        '            <select id="availability-employee-select" class="form-select form-select-sm"></select>',
        '            <button id="availability-clear-btn" type="button" class="btn btn-sm btn-outline-light">Сбросить</button>',
        '        </div>',
        '    </div>',
        '</div>'
    )
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'В разметке выделены заголовок блока, кнопка сворачивания, поле выбора сотрудника и область визуального отображения доступности. За счет этого функционал встроен прямо в рабочий экран составления расписания и не требует дополнительных действий от пользователя.'
    )

    # Introduction
    Remove-Range $doc 22 41
    $pos = $doc.Paragraphs.Item(21).Range.End
    Insert-PlainParagraphsAt $doc ([ref]$pos) @(
        'Преддипломная практика была посвящена дальнейшему развитию ранее разработанной информационной системы гибкого планирования смен для фитнес-студии. Если в рамках курсового проекта была реализована базовая функциональность управления сотрудниками, доступностью и графиками, то в период практики основное внимание было уделено новым инструментам, повышающим качество автоматического формирования расписания и удобство его корректировки.',
        'В ходе преддипломной практики были внедрены модуль правил распределения направлений занятий, отдельная страница настройки правил для руководителя, автоматическая проверка и применение активных ограничений при создании графика, быстрый просмотр доступности сотрудников на странице формирования расписания, механизм сравнения нескольких вариантов графика, а также система версий с возможностью сравнения и отката.',
        'Целью отчета является описание интерфейсных, структурных и функциональных изменений, реализованных в информационной системе в период прохождения преддипломной практики.'
    )

    # Update TOC and fields
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    foreach ($field in $doc.Fields) { $field.Update() }

    $doc.Save()
}
finally {
    $doc.Close()
    $word.Quit()
}

Write-Output $dst
