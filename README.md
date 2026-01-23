# Sprint 9. Объединение сервисов через SSO и работа с данными для аналитики

## Задание 1. Повышение безопасности системы

[./diagrams/BionicPRO\_C4\_model\_task1.drawio](./diagrams/BionicPRO_C4_model_task1.drawio)  
![обновленная схема](/diagrams/BionicPRO_C4_model_task1.drawio.png)

## Задание 2. Разработка сервиса отчётов

### Схема

[./diagrams/BionicPRO\_C4\_model\_task2.drawio](./diagrams/BionicPRO_C4_model_task2.drawio)  
![обновленная схема](/diagrams/BionicPRO_C4_model_task2.drawio.png)

### Реализация

Все поднимается по команде `docker compose up -d`:

*   исходный KeyCloak
*   postgres-базы `crm_db` и `telemetry_db` на разных серверах и заполняются рандомными данными
*   ClickHouse
*   Apache Airflow с DAG `etl_postgres_to_clickhouse_incremental`.  
    Расписание запуска — каждые две минуты, поэтому надо немного подождать, пока данные из `crm_db` и `telemetry_db` сольются в `ClickHouse`
*   бэкенд и фронтенд.  
    Если залогиниться под пользователями `prothetic[1-3]@example.com`, то получим PDF с данными телеметрии.

