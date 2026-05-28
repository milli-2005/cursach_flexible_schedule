# GitHub Push: быстрый фикс (Windows + PowerShell)

Этот файл для частых ошибок при `git push` в твоем проекте.
Рабочая папка: `...\cursach_flexible_schedule\schedule_optimizer`.

---

## 1) Ошибка: `Can't push refs to remote. Try running Pull first`

```powershell
git status
git pull --rebase origin master
git push origin master
```

Если после `pull --rebase` есть конфликты:

```powershell
git status
# исправить конфликтные файлы

git add .
git rebase --continue
git push origin master
```

---

## 2) Ошибка GH001: большие `.tar` файлы

Пример: `schedule_web.tar`, `postgres16.tar`.

### 2.1 Добавь игнор
В `schedule_optimizer/.gitignore` должна быть строка:

```gitignore
*.tar
```

### 2.2 Убери `.tar` из индекса (не удаляя с диска)

```powershell
git rm --cached schedule_web.tar postgres16.tar
```

Если не сработало (`pathspec did not match`), найди точные пути:

```powershell
git ls-files | findstr /i ".tar"
```

И повтори `git rm --cached` с правильными путями.

### 2.3 Обнови последний коммит и пуш

```powershell
git add .gitignore
git commit --amend --no-edit
git pull --rebase origin master
git push origin master
```

---

## 3) Ошибка GH013: Push protection (секреты в `.env`)

GitHub блокирует push, если в коммите найден ключ (например `OPENAI_API_KEY`).

### 3.1 Убедись, что env-файлы игнорируются
В корневом `.gitignore` (в `cursach_flexible_schedule/.gitignore`) должно быть:

```gitignore
.env
.env.*
*.env
!.env.example
!.env.postgres.example
```

### 3.2 Убери env из индекса

```powershell
git rm --cached .env .env.docker
```

Если запускаешь из `schedule_optimizer`, пути такие же (без префикса).

### 3.3 Перепиши последний коммит и пуш

```powershell
git add ..\.gitignore
git commit --amend --no-edit
git pull --rebase origin master
git push origin master
```

---

## 4) Быстрая проверка перед push

```powershell
git status
git ls-files | findstr /i ".tar"
git ls-files | findstr /i ".env"
```

Если `.tar` и `.env` не отслеживаются (или видишь только `*.example`) — можно пушить.

---

## 5) Если нужно задать вопрос в новом чате (шаблон)

Скопируй и вставь:

```text
Помоги с git push в проекте Django (Windows, PowerShell).
Ошибка: <вставь текст ошибки полностью>
Я в папке: ...\cursach_flexible_schedule\schedule_optimizer
Команды, которые уже пробовала:
1) ...
2) ...
`git status` сейчас:
<вставь вывод>
```

