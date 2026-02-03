### 1) Обзор

#### Цель

Сделать Telegram‑бота, который продаёт доступ в приватный Telegram‑канал по подписке на **90 дней**. Оплата поддерживается через **Robokassa** и **TON (через CryptoBot)**. После успешной оплаты бот автоматически выдаёт доступ (одноразовая персональная инвайт‑ссылка) и по окончании срока подписки автоматически удаляет пользователя из канала.

#### Скоуп

- Telegram‑бот: `/start`, покупка 90 дней, “Моя подписка”, “Поддержка”, админ‑команды.
- Платежи:
  - Robokassa: генерация платёжной ссылки + приём и валидация `Result URL` callback.
  - TON через CryptoBot: создание счёта/инвойса + подтверждение оплаты.
- Доступ в канал:
  - генерация одноразовой инвайт‑ссылки (member_limit=1, expire_date 5–10 минут),
  - автокик пользователей с истёкшей подпиской.
- Хранилище: Postgres, новые таблицы `subscriptions`, `payments` (и вспомогательные сущности для идемпотентности/аудита).
- Web‑админка (Flask‑Admin): управление пользователями/подписками/платежами/настройками, ручная выдача/продление, статистика.
- Интеграция между сервисами через NATS + фоновые задачи Taskiq (проверка подписок, автокик, “reconcile” платежей).

#### Вне скоупа

- Мульти‑тарифы (кроме одного тарифа 90 дней).
- Возвраты/чарджбеки, сложная бухгалтерия, интеграция с CRM.
- Полноценный “пользовательский веб‑кабинет” (кроме админки).
- Продвинутая антифрод‑логика и KYC.

#### Глоссарий

- **Подписка**: право доступа пользователя в приватный Telegram‑канал на период 90 дней.
- **Платёж**: попытка оплаты подписки (Robokassa или CryptoBot).
- **Result URL**: серверный callback Robokassa о результате платежа.
- **Invoice**: счёт/инвойс в CryptoBot для оплаты в TON.
- **Инвайт‑ссылка**: ссылка `createChatInviteLink` с `member_limit=1` и TTL 5–10 минут.
- **Автокик**: удаление пользователя из канала при истечении подписки.
- **Идемпотентность**: защита от повторной обработки одного и того же callback/события.

#### Предположения (явные)

- **Канал**: это приватный Telegram‑канал (или супергруппа) с известным `CHANNEL_ID`, бот добавлен администратором и имеет права “приглашать” и “банить/удалять”.
  - Последствие: без админ‑прав в канале бот не сможет создавать инвайты и кикать.
- **Robokassa**: используется официальный механизм подписи (CRC/Signature) и фиксированная сумма на тариф 90 дней.
  - Последствие: для корректной работы требуется точно определённая схема формирования/проверки подписи и список разрешённых IP/доп. мер (опционально).
- **TON через CryptoBot**: используем **API CryptoBot** (создание инвойса) и подтверждение оплаты через webhook или периодическую проверку статуса инвойса.
  - Последствие: если webhook недоступен, потребуется cron‑задача “reconcile”.
- **HTTP‑входящие callbacks** (Robokassa Result URL, CryptoBot webhook) принимаются в сервисе `web` (Flask), потому что он уже предназначен для HTTP‑эндпойнтов и доступен через `nginx` в prod.
  - Последствие: `bot` остаётся чисто Telegram‑процессом (long polling), а `web` становится “edge” для внешних платёжных провайдеров.
- **Миграции**: сейчас в проекте есть `create_all()`/`drop_all()` утилиты, но для продакшена нужна Alembic‑схема миграций в репозитории.
  - Последствие: добавление новых таблиц под подписки/платежи должно сопровождаться миграциями, а не пересозданием БД.

---

### 2) Архитектура системы (на уровне сервисов)

#### Схема сервисов (dev/prod)

- **`bot`** (`services/bot`): Telegram‑бот (python-telegram-bot), бизнес‑логика подписок/доступа, выдача инвайтов, админ‑команды, потребитель событий.
- **`web`** (`services/web`): Flask + Flask‑Admin, HTTP‑точка входа для внешних callbacks (Robokassa/CryptoBot), админ‑панель управления, публикация событий.
- **`db`**: Postgres (источник истины данных).
- **`nats`**: NATS JetStream (шина событий).
- **`taskiq-worker`**: worker фоновых задач (через NATS JetStream).
- **`taskiq-scheduler`**: планировщик периодических задач (cron).
- **`traefik`** (только prod): edge‑reverse‑proxy, HTTPS (Let's Encrypt), маршрутизация по домену.
- **`nginx`** (только prod): внутренний прокси для `web`, статик/медиа (за `traefik`).
- **`nats-nui`**: UI для NATS (наблюдаемость/отладка).

#### Потоки данных

- **Bot → DB**:
  - чтение/запись пользователей (`users`),
  - выдача инвайта и активация подписки (`subscriptions`),
  - изменения статусов (например, `expired`, `revoked`),
  - логирование попыток доступа/ошибок (аудит).
- **Web(Admin) → DB**:
  - управление сущностями (пользователи/подписки/платежи/настройки),
  - ручная выдача/продление подписок,
  - просмотр статистики и истории платежей.
- **Web ↔ внешние платежи (HTTP)**:
  - Robokassa `Result URL` (server‑to‑server callback),
  - CryptoBot webhook (или периодический опрос API CryptoBot).
- **Web → NATS**:
  - публикация событий “платёж подтверждён” / “подписка активирована” (см. раздел 6).
- **Bot ← NATS**:
  - обработка события успешной оплаты → выдача инвайта/активация подписки.
- **Taskiq ↔ DB/Telegram/NATS**:
  - cron‑проверка истёкших подписок и автокик,
  - reconcile “зависших” платежей (опционально),
  - публикация событий по итогам выполнения задач (опционально).

#### Границы ответственности

- **`db`**: единственный источник истины по подпискам/платежам/статусам.
- **`web`**:
  - принимает внешние callback’и платежных систем,
  - валидирует подписи/параметры,
  - записывает `payments` и триггерит доменные события в NATS,
  - предоставляет админ‑интерфейс управления.
- **`bot`**:
  - пользовательские сценарии в Telegram,
  - выдаёт доступ (создание инвайт‑ссылки),
  - выполняет Telegram‑действия (invite/kick),
  - админ‑команды Telegram (whitelist user_id).
- **`nats`**: интеграционная шина для слабой связности `web` ↔ `bot` ↔ `workers`.
- **`taskiq-*`**: планирование и выполнение фоновых операций, которые нельзя “впихнуть” в обработку Telegram‑апдейта/HTTP‑запроса.

---

### 3) Модель данных (Postgres через SQLAlchemy модели)

> Ниже описаны таблицы, которые требуются ТЗ. Отдельно отмечено соответствие текущим моделям в `services/common/models/*` и изменения, которые нужно внести.

#### 3.1. Существующие таблицы (уже есть в проекте)

##### `users` (уже есть: `services/common/models/users_models.py`)

- **Поля (факт по модели)**
  - `user_id` → bigint → not null → PK (это и есть `telegram_user_id`)
  - `first_name` → text → not null
  - `last_name` → text → null
  - `username` → text → null
  - `phone` → text → null
  - `lang` → text → not null → default `ru`
  - `timezone` → text → not null → default `Europe/Moscow`
  - `created_at` → timestamptz → not null → default now()
  - `source` → text → null
- **Индексы/уникальности**
  - PK по `user_id`
- **Комментарий по ТЗ**
  - В ТЗ таблица `users` описана как `id`, `telegram_user_id`, `username`, “дата регистрации”.
  - В проекте уже используется модель `User` с PK `user_id`. В `SPEC` считаем это каноничным и не заводим отдельный `id`.

##### `messages`, `kb_menu`, `buttons`, `settings` (уже есть)

- `messages`, `kb_menu`, `buttons` уже используются для UI/сообщений бота и админки.
- `settings` (`services/common/models/models.py`): ключ‑значение для конфигурации.

#### 3.2. Новые таблицы под ТЗ (нужно добавить)

##### `subscriptions` (нужно добавить)

Назначение: хранение подписок пользователя на канал на 90 дней и их статусов.

- **Поля**
  - `id` → int → not null → PK
  - `user_id` → bigint → not null → FK → `users.user_id`
  - `channel_id` → bigint → not null (куда выдан доступ; 1 канал по ТЗ, но поле оставляем для расширяемости)
  - `start_at` → timestamptz → not null (момент подтверждения оплаты/ручной выдачи)
  - `end_at` → timestamptz → not null ( \(start\_at + 90\) дней или ручное продление)
  - `status` → text/enum → not null (`active`, `expired`, `revoked`)
  - `created_at` → timestamptz → not null → default now()
  - `updated_at` → timestamptz → not null → default now() (обновляется при изменениях)
  - `revoked_at` → timestamptz → null
  - `revoked_reason` → text → null
  - `activated_by_payment_id` → int → null → FK → `payments.id` (если активировано платежом)
  - `activated_by_admin_id` → int → null → FK → `admin_model.id` (если выдано из админки)
- **Индексы**
  - индекс `subscriptions(user_id, channel_id)`
  - индекс `subscriptions(status, end_at)`
  - уникальность (инвариант) “не более 1 активной подписки на канал”:
    - логически: `UNIQUE(user_id, channel_id) WHERE status='active'`
- **Каскады**
  - `subscriptions.user_id` → `users.user_id`: `ON DELETE RESTRICT` (не удаляем пользователя, если есть история подписок).

##### `payments` (нужно добавить)

Назначение: единый журнал платежей (Robokassa/CryptoBot), статусы и идемпотентность callback’ов.

- **Поля**
  - `id` → int → not null → PK
  - `user_id` → bigint → not null → FK → `users.user_id`
  - `provider` → text → not null (`robokassa`, `cryptobot`)
  - `amount` → numeric(12,2) → not null
  - `currency` → text → not null (например `KZT` для Robokassa и CryptoBot; ранее использовались `RUB`/`TON`)
  - `status` → text/enum → not null (`pending`, `success`, `failed`, `canceled`)
  - `provider_payment_id` → text → null (ID платежа у провайдера; для Robokassa/ CryptoBot)
  - `provider_invoice_id` → text → null (если провайдер разделяет invoice/payment)
  - `provider_payload` → text → null (уникальный комментарий/пейлоад для сопоставления)
  - `signature_verified` → bool → not null → default false (для Robokassa)
  - `raw_callback` → jsonb → null (сырые параметры callback/webhook для аудита/разборов)
  - `created_at` → timestamptz → not null → default now()
  - `paid_at` → timestamptz → null
  - `failed_at` → timestamptz → null
- **Индексы/уникальности**
  - индекс `payments(user_id, created_at)`
  - `UNIQUE(provider, provider_payment_id)` (если `provider_payment_id` есть)
  - `UNIQUE(provider, provider_invoice_id)` (если используется)
  - `UNIQUE(provider, provider_payload)` (если payload является ключом идемпотентности/сопоставления)

##### `subscription_access` (опционально, но рекомендуется)

Назначение: хранить факты выдачи инвайт‑ссылок и обеспечить идемпотентность/аудит (особенно если пользователь запросил ссылку повторно).

- **Поля**
  - `id` → int → PK
  - `subscription_id` → int → FK → `subscriptions.id`
  - `invite_link` → text → not null (что отдал Telegram)
  - `expire_at` → timestamptz → not null
  - `member_limit` → int → not null → default 1
  - `created_at` → timestamptz → not null → default now()
  - `used_at` → timestamptz → null (если сможем определить/отметить)

##### `audit_log` (опционально, но рекомендуется)

Назначение: фиксировать критичные действия (админ выдал/продлил/отозвал, платеж прошёл/упал, кик выполнен/ошибка).

- **Поля**
  - `id` → int → PK
  - `actor_type` → text (`admin`, `bot`, `system`)
  - `actor_id` → text/int (например `admin_model.id` или telegram `user_id`)
  - `action` → text (например `subscription.activate`, `subscription.expire`, `payment.webhook_received`)
  - `entity_type` → text (`user`, `subscription`, `payment`)
  - `entity_id` → text/int
  - `payload` → jsonb → null
  - `created_at` → timestamptz → not null → default now()

#### 3.3. Сопоставление с кодом (что уже есть / что менять)

- **Уже есть**
  - `services/common/models/users_models.py`: `User`, `SendMessageCampaign` (кампании рассылки — не относятся к ТЗ подписок напрямую).
  - `services/common/models/admin_models.py`: `AdminModel` для входа в админку.
  - `services/common/models/interface_models.py`: `Message`, `Menu`, `Button` для контента/интерфейса.
  - `services/common/models/models.py`: `Settings` (key/value), можно хранить цену/валюту/TTL инвайта и т.п.
- **Нужно добавить**
  - новые модели для `subscriptions`, `payments` (и опционально `subscription_access`, `audit_log`) — логично разместить в `services/common/models/subscriptions_models.py` или `payments_models.py` и экспортировать через `services/common/models/__init__.py`.
- **Нужно поправить/уточнить**
  - в модели `User` есть `is_admin`, который ссылается на `self.role`, но поля `role` в таблице нет (по текущему коду). Для проекта подписок это не критично, но в целом требует приведения в соответствие (либо убрать, либо добавить роль).

#### 3.4. Миграции

- **Сейчас в проекте** встречаются утилиты `create_all()`/`drop_all()` (например `services/bot/create_db.py`, `services/web/manage.py`), а Alembic указан в зависимостях и папка `alembic/` игнорируется.
- **Требование для продакшена**: перейти на Alembic‑миграции, добавить `alembic/` в репозиторий и вызывать миграции из `entrypoint*.sh` сервисов `bot/web` (и/или отдельного migrator).

---

### 4) Контракт Telegram бота (не HTTP)

#### 4.1. Команды

- **`/start`**
  - **Триггер**: пользователь пишет `/start`.
  - **Ответ**: приветствие + описание сервиса + кнопки:
    - “Оформить подписку (90 дней)”
    - “Моя подписка”
    - “Поддержка”
  - **Побочные эффекты**: upsert пользователя в `users` (если нет).

- **`/help`** (рекомендуется)
  - краткая справка, контакты поддержки, повтор кнопок.

- **Админ‑команды (whitelist по user_id)**
  - `/users`: список активных подписчиков (постранично/ограничение вывода).
  - `/add <user_id>`: выдать подписку на 90 дней вручную.
  - `/extend <user_id> <days>`: продлить активную подписку на N дней (или создать новую, если expired).
  - `/remove <user_id>`: отозвать подписку и удалить пользователя из канала.
  - `/stats`: статистика по платежам/подпискам.

#### 4.2. Кнопки и callback_data

Минимальная схема callback’ов (пример; финальные строки должны укладываться в лимит `callback_data` Telegram):

- `buy_90d` — начать покупку 90 дней.
- `my_sub` — показать статус подписки.
- `support` — показать поддержку.
- `pay_robokassa` — выбрать оплату Robokassa.
- `pay_ton` — выбрать оплату TON (CryptoBot).
- `get_invite` — запросить новую инвайт‑ссылку (только при активной подписке; защита от спама).

Маршрутизация callback’ов должна быть детерминированной и идемпотентной (повторный клик/повторный апдейт не должен создавать дубликаты платежей/подписок).

#### 4.3. Состояния диалога

Допускается без сложного FSM (простые шаги через inline‑кнопки). Если нужен FSM:

- `idle` → `choose_payment_method` → `await_payment`
- переход в `active` после получения события об успешной оплате (из NATS).

#### 4.4. Сообщения

Ключевые тексты (можно хранить в таблице `messages` и управлять из админки, как это уже предусмотрено проектом):

- `msg-start`: приветствие + объяснение.
- `msg-choose-payment`: “Выберите способ оплаты…”.
- `msg-payment-created`: ссылка/инструкция оплаты.
- `msg-payment-success`: подтверждение оплаты + дата окончания + инвайт‑ссылка.
- `msg-my-subscription`: статус + дата окончания (или “подписка отсутствует/истекла”).
- `msg-support`: контакты/инструкция.
- `msg-admin-*`: ответы админ‑команд.

Переменные шаблонов:

- `{end_at}`: дата окончания подписки.
- `{amount}` / `{currency}`: сумма и валюта.
- `{invite_link}`: одноразовая ссылка.

#### 4.5. Ошибки и edge cases

- **Idempotency**: повторный callback Robokassa/CryptoBot не должен повторно активировать подписку/создавать вторую.
- **Race conditions**: пользователь нажал “Получить инвайт” до того, как платеж подтверждён — показываем “ожидаем подтверждение”.
- **Bot blocked**: если пользователь заблокировал бота, мы всё равно фиксируем платеж/подписку в БД; отправку сообщения логируем как ошибку.
- **Rate limits**: ограничить частоту генерации инвайт‑ссылок (например, не чаще 1 раза в минуту на пользователя).
- **Telegram API ошибки**: если не удалось создать инвайт/кикнуть — задача ретраится (Taskiq), событие/ошибка пишется в `audit_log`.

---

### 5) Контракт веб‑админки (Flask + Flask‑Admin)

#### 5.1. Аутентификация/авторизация

- **Уже есть**: вход через `AdminModel` (Flask‑Login), пароль хранится хешем, доступ к админ‑вьюхам по `current_user.is_authenticated`.
- **Нужно расширить** (рекомендуется):
  - роли/права (например `admin`, `operator`, `viewer`) либо хотя бы audit действий;
  - принудительная смена дефолтного пароля, отключение слабых паролей.

#### 5.2. Admin Views (Flask‑Admin)

Нужно добавить/расширить следующие разделы:

- **Users (`users`)**
  - Назначение: просмотр пользователей, фильтр по наличию активной подписки.
  - Поля в списке: `user_id`, `first_name`, `username`, `created_at`.
  - Действия: “Открыть в Telegram”, “Выдать подписку”, “Продлить”, “Отозвать”.

- **Subscriptions (`subscriptions`)** (нужно добавить)
  - Поля в списке: `id`, `user_id`, `channel_id`, `status`, `start_at`, `end_at`.
  - Фильтры: `status`, диапазон дат, `channel_id`.
  - Действия:
    - “Продлить на N дней”
    - “Отозвать”
    - “Сгенерировать инвайт” (опционально; фактически лучше делать через бота/задачу, чтобы не хранить токены в UI).

- **Payments (`payments`)** (нужно добавить)
  - Поля: `id`, `user_id`, `provider`, `amount`, `currency`, `status`, `provider_payment_id`, `created_at`, `paid_at`.
  - Фильтры: provider, status, диапазоны дат.
  - Просмотр `raw_callback` для расследований.

- **Settings (`settings`)** (уже есть)
  - Использовать для:
    - цена тарифа,
    - валюта,
    - TTL инвайта (5–10 минут),
    - частота проверок автокика (5–15 минут),
    - идентификатор канала/чата (если не через ENV).

#### 5.3. Пользовательские страницы/эндпойнты (кроме Flask‑Admin)

Нужно добавить HTTP‑эндпойнты (не админ‑UI):

- **Robokassa Result URL**
  - `POST /payments/robokassa/result`
  - Валидирует подпись, сумму, статус, сопоставляет с `payments`.
  - Переводит `payments.status` → `success` и публикует событие в NATS.

- **CryptoBot webhook** (или poll‑эндпойнт)
  - `POST /payments/cryptobot/webhook`
  - Проверяет подпись/секрет (если поддерживается), сопоставляет invoice, отмечает `payments.success`, публикует событие.

---

### 6) Контракт событий и фоновых задач (NATS + Taskiq)

> В проекте уже есть пример NATS события для рассылки: subject **`campaign.send`** и Pydantic‑модель `SendCampaignEvent`. Подписки/платежи добавляются отдельными subject’ами.

#### 6.1. События (NATS subjects)

##### `payment.succeeded`

- **Публикует**: `web` (после успешной валидации callback/webhook).
- **Потребляет**: `bot` (и опционально `taskiq-worker` для побочных процессов).
- **Payload (JSON)**
  - `payment_id` (int)
  - `user_id` (int, telegram user id)
  - `provider` (`robokassa` | `cryptobot`)
  - `amount` (string/number)
  - `currency` (string)
  - `paid_at` (ISO datetime)
  - `idempotency_key` (string; например `provider:provider_payment_id`)
- **Гарантии/дубликаты**
  - JetStream work‑queue, возможно повторение доставки.
  - Идемпотентность на стороне consumer: обработка должна быть “exactly‑once” логически (проверка по `payments.status==success` и/или `idempotency_key`).

##### `subscription.activated` (опционально)

- **Публикует**: `bot` после успешной выдачи инвайта и записи `subscriptions.active`.
- **Потребляет**: `web` для обновления UI/аудита/уведомлений (опционально).
- **Payload**
  - `subscription_id`, `user_id`, `channel_id`, `start_at`, `end_at`.

##### `subscription.expired` / `subscription.revoked` (опционально)

- **Публикует**: `taskiq-worker` (после автокика) или `bot` (по админ‑команде `/remove`).
- **Потребляет**: `web` (статистика/аудит).

#### 6.2. Фоновые задачи (Taskiq)

##### `subscriptions.expire_and_kick`

- **Триггер**: cron каждые 5–15 минут (по ТЗ).
- **Вход**: нет (или `now`).
- **Действия**
  - выбрать `subscriptions` где `status='active'` и `end_at < now()`,
  - попытаться удалить пользователя из канала через Telegram API,
  - выставить `subscriptions.status='expired'`,
  - записать `audit_log`.
- **Ретраи/таймауты**
  - ретраи на ошибки Telegram API,
  - идемпотентность: если пользователь уже не в канале — считать успехом и всё равно пометить подписку expired.

##### `payments.reconcile_pending` (рекомендуется)

- **Триггер**: cron, например каждые 5 минут.
- **Назначение**: если callback/webhook потерян, проверять статус “pending” платежей через API провайдера и доводить до `success/failed`.

---

### 7) Docker Compose и окружение

#### 7.1. Сервисы и роли (факт по репозиторию)

- **dev** (`docker-compose.yml`):
  - `web` публикуется наружу на `:5000`.
  - `nats` публикуется `4222/8222`, есть `nats-nui` на `31311`.
  - NATS JetStream включён через конфиг‑файл в репозитории: `infra/nats/server.conf` (монтируется в контейнер как `/etc/nats/server.conf:ro`). Хранилище в `/data` на томе `nats_data`, лимиты: mem `1G`, file `5G`, `http_port=8222`.
  - `taskiq-worker`/`taskiq-scheduler` используют образ `bot` и подключены к NATS.
  - `db` — Postgres 13.
- **prod** (`docker-compose.prod.yml`):
  - добавлен `nginx` (публикуется наружу на `:1337`, проксирует `web`).
  - `web` доступен только внутри сети (`expose: 5000`).

#### 7.2. Сети/тома

- Postgres: `postgres_data` (dev) / `postgres_data_prod` (prod).
- Статика: `static_volume` (используют `web` и `nginx`, а также подключён в `bot` по compose).
- Медиа (prod): `media_volume`.
- NATS: `nats_data`, `nui_db`.

#### 7.3. Переменные окружения (ключевые, без значений)

> Источники: `.env.dev`, `.env.prod`, `.env.prod.db` (по compose).

**Bot (`services/bot`)**

- `BOT_TOKEN`
- `CHANNEL_ID` (int/bigint)
- `ADMIN_USER_IDS` (список user_id, например через запятую)
- `DATABASE_URL` (или компоненты: `DB_HOST=db`, `DB_PORT=5432`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`)
- `NATS_URL` (по умолчанию `nats://nats:4222`)
- `INVITE_TTL_SECONDS` (например 600)
- `SUBSCRIPTION_DAYS` (фиксировано 90)

**Web (`services/web`)**

- `SECRET_KEY` (Flask session)
- `DATABASE_URL` / DB‑параметры
- `NATS_URL`
- `ROBO_MERCHANT_LOGIN`
- `ROBO_PASSWORD_1` / `ROBO_PASSWORD_2` (в зависимости от схемы подписи)
- `ROBO_ALLOWED_IPS` (опционально)
- `TARIFF_AMOUNT_KZT` (единая цена подписки в тенге; хранится в таблице `settings`, инициализируется в `create_db`, ENV — фоллбэк)
- `CRYPTOBOT_TOKEN`
- `CRYPTOBOT_DESCRIPTION` (описание инвойса/подписки; хранится в `settings`, ENV — фоллбэк)
- `CRYPTOBOT_WEBHOOK_SECRET` (если доступно)
- `PUBLIC_BASE_URL` (нужен, чтобы формировать callback URLs и возвращаемые ссылки)

**DB**

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (prod берётся из `.env.prod.db`).

#### 7.4. Хосты (внутри Docker‑сети)

- Postgres: `db:5432`
- NATS: `nats:4222`
- Web: `web:5000`

---

### 8) Безопасность, наблюдаемость, эксплуатация

#### 8.1. Секреты

- токен Telegram‑бота (`BOT_TOKEN`)
- Robokassa пароли/секреты подписи
- CryptoBot токен/секрет вебхука
- `SECRET_KEY` Flask
- креды БД

Хранить только в `.env.*` (не коммитить), а в логах не печатать секреты/полные payload’ы без маскирования.

#### 8.2. Аудит

Логировать (в `audit_log` и/или в структурные логи):

- все входящие callback’и платежей (с привязкой к `payment_id`)
- активацию/продление/отзыв подписки (кто инициировал)
- генерацию инвайтов (сколько раз, TTL)
- автокик и ошибки Telegram API

#### 8.3. Логи/метрики

- структурные логи JSON (желательно) с полями:
  - `service`, `event_id`/`correlation_id`, `user_id`, `payment_id`, `subscription_id`
- минимальные метрики:
  - число успешных/неуспешных платежей,
  - число активных подписок,
  - ошибки Telegram API,
  - длительность задач Taskiq.

#### 8.4. Бэкапы

- регулярный backup Postgres (как минимум daily) + хранение 7–30 дней.
- тест восстановления (restore drill).

---

### 9) План реализации (пошагово)

#### 9.1. БД / модель данных → миграции

- **Уже есть**: общие модели и подключение Postgres.
- **Нужно добавить**:
  - модели `payments`, `subscriptions` (и опционально `subscription_access`, `audit_log`) в `services/common/models`.
  - Alembic‑миграции и процесс применения миграций в контейнерах.

#### 9.2. Контракты событий / задачи (NATS + Taskiq)

- **Уже есть**: NATS JetStream, subject `campaign.send`, Taskiq broker/scheduler.
- **Нужно добавить**:
  - subject `payment.succeeded` (и при необходимости `subscription.*`),
  - задачи `subscriptions.expire_and_kick`, `payments.reconcile_pending`.

#### 9.3. Платежи

- **Robokassa**
  - **Нужно добавить** в `web`: генерацию платежной ссылки (по запросу от бота/админки) и `Result URL` обработчик.
  - Валидация: подпись, сумма, статус, идемпотентность.
- **CryptoBot (TON)**
  - **Нужно добавить**: создание invoice (из бота или из web) и обработку webhook/проверку статуса.

#### 9.4. Bot‑фичи

- **Уже есть**: каркас бота, интерфейс кнопок/меню/сообщений, репозитории/UoW.
- **Нужно добавить/изменить**:
  - сценарий покупки (кнопки, выбор метода оплаты),
  - вывод “Моя подписка”,
  - обработка событий `payment.succeeded` → активация подписки и выдача инвайта,
  - админ‑команды `/users /add /extend /remove /stats`,
  - анти‑спам на “получить инвайт”.

#### 9.5. Web‑админка

- **Уже есть**: Flask‑Admin и вход.
- **Нужно добавить**:
  - Admin Views для `subscriptions`, `payments`,
  - экраны/действия для ручной выдачи/продления/отзыва,
  - HTTP эндпойнты callbacks Robokassa/CryptoBot.

#### 9.6. Инфраструктура / деплой

- **Уже есть**: dev/prod compose, nginx в prod.
- **Нужно уточнить/добавить**:
  - внешний `PUBLIC_BASE_URL` и маршрутизация nginx для callback URLs,
  - healthchecks (опционально),
  - политика логов и бэкапов Postgres.

