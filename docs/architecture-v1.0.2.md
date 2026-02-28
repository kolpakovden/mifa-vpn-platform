Архитектурный overview - MIFA Platform v1.0.2
1) Self-hosted VPN платформа на Xray (VLESS+Reality) с Telegram-ботом для управления пользователями и полной наблюдаемостью (Prometheus+Grafana+Loki).

2) Слои архитектуры
A. Traffic Layer (VPN Data Plane)

Xray-core
Протокол: VLESS
Маскировка: Reality (TLS camouflage без сертификатов)
Поддержка multi-port inbounds
Структурированный access logging (для Loki)
Центральный конфиг: /usr/local/etc/xray/config.json
Логи: /var/log/xray/access.log
Роль: единственный источник истины для трафика. Всё управление пользователями в итоге сводится к изменению Xray-конфига/клиентских credential’ов и reload.

B. Control Layer (User & Config Management)
Telegram Bot (python-telegram-bot) как “операторская консоль”:
Команды:
/add <user> — создать пользователя (uuid/key), добавить в конфиг
/del <user> — удалить из конфигурации
/list — список пользователей
/key <user> — выдать клиентский ключ/URI
/restart — безопасный reload/restart сервиса

Сервис:

systemd unit: mifa-xray-bot
секреты/переменные: /etc/mifa/bot.env
состояние/метаданные: /etc/mifa/state.env
Роль: единственная точка входа для управления, но пока (в v1.0.2) это “бот, который правит файлы и рестартит сервис”.

C. Observability Layer (Metrics + Logs)

Docker Compose стек:
Prometheus (метрики)
Grafana (дашборды + explore)
Loki (логи)

Promtail (shippers: читает логи Xray и шлёт в Loki)
node-exporter (системные метрики)
Endpoints:
Grafana: :3000
Prometheus: :9090
Loki: :3100
Node Exporter: :9100

Хранилище Loki: single-node, volume в /var/lib/loki (важно для прав и персистентности).
Роль: наблюдаемость “из коробки”: метрики сервера + логовый трейс активности.

3) Flows v1.0.2
Flow 1: Provisioning пользователя
Админ пишет в Telegram /add alice
Бот генерирует uuid/key → правит config.json
Бот делает reload Xray
/key alice отдаёт VLESS URI/ключ

Flow 2: Отключение пользователя
/del alice
удалить client из конфига
reload Xray

Flow 3: Наблюдаемость
Xray пишет access.log → promtail → loki → grafana explore/дашборды
node-exporter → prometheus → grafana dashboards

4) Что важно как “инварианты”
Xray config остаётся источником правды для клиентов (пока нет внешней БД).
Бот = control plane, но сейчас tightly coupled к файловой конфигурации.
Observability развёрнут отдельно контейнерами → хорошо для воспроизводимости.
“Безопасность доступа” — через firewall/ограничения сервисов, наружу желательно только Grafana (или закрыть по IP).
