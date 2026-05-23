import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time
import psycopg2
import warnings
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
st.set_page_config(
    page_title="Dashboard IoT - Prototipo Físico", 
    page_icon="🔬", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 📦 CREDENCIALES SUPABASE
DB_CONFIG = {
    'host': 'aws-1-us-west-2.pooler.supabase.com',
    'database': 'postgres',
    'user': 'postgres.qllzcapdrsymxklmxuau',
    'password': '9-Ji/G!Vie@vZ2S',
    'port': 6543
}

# ==========================================
# 📊 CARGA DE DATOS
# ==========================================
@st.cache_data(ttl=2)
def cargar_datos():
    """Carga los últimos datos de los sensores (últimas 2 horas)"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cutoff = datetime.now() - timedelta(hours=2)
        
        query = """
            SELECT sensor_id, valor, es_alerta, desc_alerta, timestamp_utc
            FROM medicion
            WHERE sensor_id IN (2, 3, 4, 5, 6) 
            AND timestamp_utc >= %s
            ORDER BY timestamp_utc DESC
        """
        df = pd.read_sql_query(query, conn, params=[cutoff])
        conn.close()
        return df
    except Exception as e:
        st.error(f"❌ Error conectando a la base de datos: {e}")
        return pd.DataFrame()

# ==========================================
# 🎨 CONFIGURACIÓN VISUAL
# ==========================================
SENSOR_NAMES = {
    2: '🌡️ Temperatura', 
    3: '💧 Humedad Suelo', 
    4: '❤️ BPM', 
    5: '⚖️ Peso', 
    6: '🌧️ Lluvia'
}

THRESHOLDS = {2: 25, 3: 30, 4: 100, 5: 600, 6: 15}
UNITS = {2: '°C', 3: '%', 4: 'BPM', 5: 'kg', 6: 'mm'}

COLOR_PALETTE = {
    '🌡️ Temperatura': '#FFB347',
    '💧 Humedad Suelo': '#77DD77',
    '❤️ BPM': '#FF6961',
    '⚖️ Peso': '#AEC6CF',
    '🌧️ Lluvia': '#C3B1E1'
}

# ==========================================
# 📈 INTERFAZ PRINCIPAL
# ==========================================
st.title("🔬 Dashboard IoT - Prototipo Físico")
st.caption(f"🕐 Última actualización: {datetime.now().strftime('%H:%M:%S')}")
st.markdown("---")

# Cargar datos
df = cargar_datos()

if df.empty:
    st.warning("⏳ Esperando datos del Arduino...")
    st.info("💡 Asegúrate de que `recibir_arduino.py` esté corriendo y enviando datos a Supabase")
    time.sleep(2)
    st.rerun()
    st.stop()

# ==========================================
# 🔹 KPIs EN VIVO
# ==========================================
st.subheader("📊 Métricas en Tiempo Real")
kpi_cols = st.columns(5)

# Obtener último valor de cada sensor
latest = df.groupby('sensor_id').first().reset_index()

for i, col in enumerate(kpi_cols):
    sid = i + 2  # Sensores 2, 3, 4, 5, 6
    row = latest[latest['sensor_id'] == sid]
    
    with col:
        if not row.empty:
            val = row.iloc[0]['valor']
            # Determinar si es alerta
            if sid in [2, 4, 5, 6]:  # Mayor que umbral
                es_alerta = val > THRESHOLDS[sid]
            else:  # Menor que umbral (humedad)
                es_alerta = val < THRESHOLDS[sid]
            
            icon = "🔴" if es_alerta else "🟢"
            delta_color = "inverse" if es_alerta else "normal"
            
            st.metric(
                label=SENSOR_NAMES[sid],
                value=f"{val:.1f}{UNITS[sid]}",
                delta=f"{icon} Umbral: {THRESHOLDS[sid]}{UNITS[sid]}",
                delta_color=delta_color
            )
        else:
            st.metric(SENSOR_NAMES[sid], "N/A", "⏳")

st.markdown("---")

# ==========================================
# 🔹 ESTADÍSTICAS DEL PERÍODO
# ==========================================
st.subheader("📈 Estadísticas (Últimas 2 horas)")
stats_cols = st.columns(5)

for i, col in enumerate(stats_cols):
    sid = i + 2
    sensor_data = df[df['sensor_id'] == sid]['valor']
    
    with col:
        st.markdown(f"**{SENSOR_NAMES[sid]}**")
        if not sensor_data.empty:
            st.metric("Promedio", f"{sensor_data.mean():.1f}{UNITS[sid]}")
            st.caption(f"Mín: {sensor_data.min():.1f} | Máx: {sensor_data.max():.1f}")
        else:
            st.caption("Sin datos")

st.markdown("---")

# ==========================================
# 🔹 GRÁFICO DE TENDENCIAS
# ==========================================
st.subheader("📉 Comportamiento de Sensores")

df_plot = df.copy()
df_plot['timestamp_utc'] = pd.to_datetime(df_plot['timestamp_utc'])
df_plot = df_plot.sort_values('timestamp_utc')
df_plot['sensor'] = df_plot['sensor_id'].map(SENSOR_NAMES)

fig = px.line(
    df_plot,
    x='timestamp_utc',
    y='valor',
    color='sensor',
    color_discrete_map=COLOR_PALETTE,
    title='Registro en Tiempo Real',
    height=400,
    markers=True
)

fig.update_traces(mode='lines+markers', line=dict(width=2))
fig.update_layout(
    xaxis_title="Hora",
    yaxis_title="Valor",
    legend_title="Sensor",
    template="simple_white",
    hovermode='x unified'
)

st.plotly_chart(fig, width="stretch")

# ==========================================
# 🔹 ALERTAS ACTIVAS
# ==========================================
st.subheader("🚨 Alertas Detectadas")

alerts = df[df['es_alerta'] == True] if 'es_alerta' in df.columns else pd.DataFrame()

if not alerts.empty:
    alerts['timestamp_utc'] = pd.to_datetime(alerts['timestamp_utc'])
    alerts['hora'] = alerts['timestamp_utc'].dt.strftime('%H:%M:%S')
    
    for _, row in alerts.head(5).iterrows():
        sensor_name = SENSOR_NAMES.get(row['sensor_id'], f"Sensor {row['sensor_id']}")
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 3, 1])
            with c1:
                st.markdown(f"**{sensor_name}**")
            with c2:
                desc = row['desc_alerta'] if pd.notna(row['desc_alerta']) else "Alerta detectada"
                st.markdown(f"⚠️ {desc} — Valor: {row['valor']:.2f}{UNITS.get(row['sensor_id'], '')}")
            with c3:
                st.caption(f"🕐 {row['hora']}")
else:
    st.success("✅ Todos los sensores operan en rangos normales")

# ==========================================
# 🔹 TABLA DE DATOS CRUDOS
# ==========================================
with st.expander("📋 Ver Últimas 20 Mediciones"):
    df_table = df.head(20).copy()
    df_table['timestamp_utc'] = pd.to_datetime(df_table['timestamp_utc'])
    df_table['sensor'] = df_table['sensor_id'].map(SENSOR_NAMES)
    df_table['estado'] = df_table['es_alerta'].map({True: '🔴 Alerta', False: '✅ Normal'}) if 'es_alerta' in df_table.columns else 'N/A'
    
    st.dataframe(
        df_table[['timestamp_utc', 'sensor', 'valor', 'estado']].head(20),
        hide_index=True,
        width="stretch"  # ← Nuevo formato sin warnings
    )

# ==========================================
# 🔄 AUTO-REFRESCO
# ==========================================
time.sleep(2)
st.rerun()