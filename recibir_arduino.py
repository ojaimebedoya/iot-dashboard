import serial
import psycopg2
import pyodbc
import time
from datetime import datetime

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
PORT = 'COM9'
BAUD_RATE = 9600

# 1. SQL SERVER LOCAL (Backup)
LOCAL_DB_ON = True
SERVER = r'OSCAR'
DATABASE = 'SabanaIoT_DB'
LOCAL_CONN_STR = (
    r'DRIVER={ODBC Driver 17 for SQL Server};'
    r'SERVER=' + SERVER + ';'
    r'DATABASE=' + DATABASE + ';'
    r'Trusted_Connection=yes;'
)

# 2. SUPABASE (PostgreSQL) - Usa POOLER
DB_CONFIG = {
    'host': 'aws-1-us-west-2.pooler.supabase.com',  # ← Verifica que este sea el host EXACTO del pooler
    'database': 'postgres',
    'user': 'postgres.qllzcapdrsymxklmxuau',  # ← Verifica usuario del pooler
    'password': '9-Ji/G!Vie@vZ2S',
    'port': 6543  # ← Pooler usa puerto 6543
}

# ==========================================
# 🚀 FUNCIONES
# ==========================================

def guardar_en_nube(sensor_id, valor, es_alerta_bool, desc_alerta):
    """Guarda en Supabase (PostgreSQL) - usa booleanos True/False"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        query = """
        INSERT INTO medicion 
        (sensor_id, dispositivo_id, animal_id, usuario_id, 
         valor, lat_medicion, lng_medicion, altitud_msnm,
         calidad_senal, valor_raw, es_alerta, desc_alerta, procesada, timestamp_utc)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        # ⚠️ PostgreSQL usa True/False (boolean), no 1/0 (integer)
        cursor.execute(query, (
            sensor_id, 1, 1, 3,
            valor, 4.1420, -73.6266, 2600,
            85, valor, 
            es_alerta_bool,      # ← True o False (boolean)
            desc_alerta, 
            False,               # ← procesada = False (boolean)
        ))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error Nube: {e}")
        return False

def guardar_en_local(sensor_id, valor, es_alerta_int, desc_alerta):
    """Guarda en SQL Server Local - usa 1/0 (bit)"""
    if not LOCAL_DB_ON: return False
    try:
        conn = pyodbc.connect(LOCAL_CONN_STR)
        cursor = conn.cursor()
        
        query = """
        INSERT INTO dbo.Medicion 
        (sensor_id, dispositivo_id, animal_id, usuario_id, valor,
         lat_medicion, lng_medicion, altitud_msnm, calidad_senal, valor_raw,
         es_alerta, desc_alerta, procesada, timestamp_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
        """
        
        # SQL Server usa 1/0 (bit)
        cursor.execute(query, (
            sensor_id, 1, 1, 3, valor, 4.1420, -73.6266, 2600, 85, valor,
            es_alerta_int,  # ← 1 o 0 (integer)
            desc_alerta, 0
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

# ==========================================
# 🔄 BUCLE PRINCIPAL
# ==========================================
print("🚀 Iniciando receptor IoT (Dual)...")
try:
    arduino = serial.Serial(PORT, BAUD_RATE, timeout=1)
    time.sleep(2); print("✅ Arduino conectado.")
except Exception as e:
    print(f"❌ Error serial: {e}"); exit()

print("📥 Esperando datos...")

while True:
    try:
        if arduino.in_waiting > 0:
            linea = arduino.readline().decode('utf-8', errors='ignore').strip()
            
            if linea.startswith("DATA_"):
                valor = float(linea.split(',')[1])
                sensor_id = int(linea.split('_')[1].split(',')[0])
                
                # Calcular alerta (lógica igual para ambos)
                es_alerta = False  # ← Booleano para PostgreSQL
                desc_alerta = None
                
                if sensor_id == 2 and valor > 25.0:
                    es_alerta, desc_alerta = True, "Temp. Alta"
                elif sensor_id == 3 and valor < 30.0:
                    es_alerta, desc_alerta = True, "Sequía"
                elif sensor_id == 4 and (valor > 100 or valor < 50):
                    es_alerta, desc_alerta = True, "Ritmo Anormal"
                elif sensor_id == 6 and valor > 15.0:
                    es_alerta, desc_alerta = True, "Lluvia Intensa"
                
                estado = "🔴 ALERTA" if es_alerta else "✅ OK"
                print(f"📦 Sensor {sensor_id}: {valor} | {estado}")
                
                # Guardar en Nube (usa booleanos)
                ok_nube = guardar_en_nube(sensor_id, valor, es_alerta, desc_alerta)
                
                # Guardar en Local (convierte booleano a integer: True→1, False→0)
                ok_local = guardar_en_local(sensor_id, valor, int(es_alerta), desc_alerta)
                
                if ok_nube and ok_local:
                    print("   ✅ Guardado en Local + Nube")
                elif ok_local:
                    print("   ⚠️ Guardado solo en Local")
                elif ok_nube:
                    print("   ☁️ Guardado solo en Nube")

    except KeyboardInterrupt:
        print("\n🛑 Detenido."); break
    except Exception as e:
        print(f"⚠️ Error: {e}")
    
    time.sleep(0.1)