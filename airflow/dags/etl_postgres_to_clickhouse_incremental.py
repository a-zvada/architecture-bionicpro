from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

#from clickhouse_driver import Client
#from airflow.hooks.base import BaseHook

#from airflow.providers.clickhouse.hooks.clickhouse import ClickHouseHook
from airflow_clickhouse_plugin.hooks.clickhouse import ClickHouseHook
import pandas as pd

# Default args
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'retries': 0,
}

# DAG definition
with DAG(
    dag_id='etl_postgres_to_clickhouse_incremental',
    default_args=default_args,
    description='Incremental ETL from CRM/Telemetry Postgres to ClickHouse',
    schedule_interval='@hourly',  # Ежечасно
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['etl', 'clickhouse', 'postgres'],
    max_active_runs=1,
) as dag:

    def get_max_telemetry_id(**context):
        ch_hook = ClickHouseHook(clickhouse_conn_id='olap_db')
        
        max_id_query = """
        SELECT max(telemetry_id) AS max_id
        FROM telemetry_analytics
        """
        result = ch_hook.execute(max_id_query, with_column_types=True)
        max_id = result[0][0][0] if result and result[0] else 0
        
        context['task_instance'].xcom_push(key='max_telemetry_id', value=max_id)
        return max_id

    get_max_id_task = PythonOperator(
        task_id='get_max_telemetry_id_from_clickhouse',
        python_callable=get_max_telemetry_id,
        provide_context=True,
    )

    def extract_new_telemetry(**context):
        max_id = context['task_instance'].xcom_pull(key='max_telemetry_id')
        
        # Подключение к telemetry_db
        tele_hook = PostgresHook(postgres_conn_id='tele_db')
        
        new_telemetry_query = f"""
        SELECT 
            telemetry_id,
            sensor_id,
            recorded_at,
            value
        FROM telemetry
        WHERE telemetry_id > {max_id}
        ORDER BY telemetry_id
        """
        
        df_telemetry = tele_hook.get_pandas_df(new_telemetry_query)
        
        if df_telemetry.empty:
            raise ValueError("No new data to process")
        
        df_telemetry['recorded_at'] = df_telemetry['recorded_at'].dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        context['task_instance'].xcom_push(key='new_telemetry_df', value=df_telemetry.to_dict('records'))
        
        # Сохраняем уникальные sensor_id для следующего шага
        sensor_ids = df_telemetry['sensor_id'].unique().tolist()
        context['task_instance'].xcom_push(key='sensor_ids', value=sensor_ids)

    extract_telemetry_task = PythonOperator(
        task_id='extract_new_telemetry',
        python_callable=extract_new_telemetry,
        provide_context=True,
    )

    def extract_related_crm_data(**context):
        sensor_ids = context['task_instance'].xcom_pull(key='sensor_ids')
        
        if not sensor_ids:
            raise ValueError("No sensor_ids to extract CRM data")
        
        # Подключение к crm_db
        crm_hook = PostgresHook(postgres_conn_id='crm_db')
        
        # Джойним Sensors, Prostheses, Users по sensor_ids
        sensor_ids_str = ','.join(map(str, sensor_ids))
        crm_query = f"""
        SELECT 
            s.sensor_id,
            s.sensor_type,
            s.location,
            s.serial_number AS sensor_serial_number,
            s.installed_at,
            s.is_active,
            p.prosthesis_id,
            p.model,
            p.serial_number AS prosthesis_serial_number,
            p.purchase_date,
            u.user_id,
            u.name,
            u.email,
            u.date_of_birth,
            u.registration_date
        FROM Sensors s
        JOIN Prostheses p ON s.prosthesis_id = p.prosthesis_id
        JOIN Users u ON p.user_id = u.user_id
        WHERE s.sensor_id IN ({sensor_ids_str})
        """
        
        df_crm = crm_hook.get_pandas_df(crm_query)
        
        context['task_instance'].xcom_push(key='crm_df', value=df_crm.to_dict('records'))

    extract_crm_task = PythonOperator(
        task_id='extract_related_crm_data',
        python_callable=extract_related_crm_data,
        provide_context=True,
    )

    def transform_and_join(**context):
        tele_records = context['task_instance'].xcom_pull(key='new_telemetry_df')
        crm_records = context['task_instance'].xcom_pull(key='crm_df')
        
        df_tele = pd.DataFrame(tele_records)
        df_crm = pd.DataFrame(crm_records)
        
        # Джойним по sensor_id
        df_joined = pd.merge(df_tele, df_crm, on='sensor_id', how='left')
        
        # Преобразуем типы для ClickHouse
        df_joined['telemetry_id'] = df_joined['telemetry_id'].astype('uint64')
        df_joined['sensor_id'] = df_joined['sensor_id'].astype('uint32')
        df_joined['prosthesis_id'] = df_joined['prosthesis_id'].astype('uint32')
        df_joined['user_id'] = df_joined['user_id'].astype('uint32')
        df_joined['value'] = df_joined['value'].astype('float64')
        df_joined['is_active'] = df_joined['is_active'].astype('uint8')
        df_joined['recorded_at'] = pd.to_datetime(df_joined['recorded_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        df_joined['installed_at'] = pd.to_datetime(df_joined['installed_at']).dt.date
        df_joined['purchase_date'] = pd.to_datetime(df_joined['purchase_date']).dt.date
        df_joined['date_of_birth'] = pd.to_datetime(df_joined['date_of_birth']).dt.date
        df_joined['registration_date'] = pd.to_datetime(df_joined['registration_date']).dt.date
        
        # Заполняем Nullable поля
        df_joined['sensor_serial_number'] = df_joined['sensor_serial_number'].fillna('')
        df_joined['prosthesis_serial_number'] = df_joined['prosthesis_serial_number'].fillna('')
        
        context['task_instance'].xcom_push(key='joined_data', value=df_joined.to_dict('records'))

    transform_task = PythonOperator(
        task_id='transform_and_join_data',
        python_callable=transform_and_join,
        provide_context=True,
    )

    def load_to_clickhouse(**context):
        rows = context['task_instance'].xcom_pull(key='joined_data')
        
        if not rows:
            return "Нет данных для загрузки"
        
        joined_df = pd.DataFrame(rows)
        joined_df['recorded_at'] = pd.to_datetime(joined_df['recorded_at'])



        records = [tuple(row) for row in joined_df.to_numpy()]
        columns = ', '.join(joined_df.columns)

        ch_hook = ClickHouseHook(clickhouse_conn_id='olap_db')
        
        #values = [(r['telemetry_id'], r['recorded_at'], r['value'], ... ) for r in records]  # соберите список кортежей
        ch_hook.execute(f"INSERT INTO telemetry_analytics ({columns}) VALUES", params=records)
        

    load_task = PythonOperator(
        task_id='load_to_clickhouse',
        python_callable=load_to_clickhouse,
        provide_context=True,
    )

    # Зависимости
    get_max_id_task >> extract_telemetry_task >> extract_crm_task >> transform_task >> load_task