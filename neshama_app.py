import streamlit as st
import requests
import json
from datetime import datetime, date # Se usa 'date' para comparar fechas del caché
import pandas as pd
import time # Aunque no se usa activamente para retrasos aquí, es bueno tenerlo si se necesita

# --- CONFIGURACIÓN ---
# El API_TICKET ya no es usado directamente por esta app para las búsquedas principales,
# pero se mantiene por si el bloque try-except original lo necesita como fallback o para otras funciones futuras.
try:
    API_TICKET = st.secrets["API_TICKET_MERCADOPUBLICO"]
except KeyError:
    API_TICKET = "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL" 
    if API_TICKET == "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL":
        # Ya no es un error crítico si no lo encuentra, porque leemos del Gist
        st.sidebar.warning("API_TICKET no configurado en los secrets. Se leerá del caché Gist.")

# --- URL DEL GIST DE CACHÉ ---
GIST_CACHE_URL = "https://gist.githubusercontent.com/Neshamalic/7683372d7c8374cbd8bc67d81eec5fe9/raw/7705bf1ca22a60fb3e8683f7394cf1c756cde759/oportunidades_cache.json"

# --- TU CATÁLOGO DE PRODUCTOS (se mantiene por si la app hace algún filtrado local) ---
CATALOGO_PRODUCTOS_RAW = """
AMLODIPINO	amlodipino
AMOXICILINA	amoxi
APIXABAN	APIXABAN,apixaban
ARIPIPRAZOL	ARIPIPRAZOL,aripiprazol
ATORVASTATINA	ATORVASTATINA,atorvastatina
AZITROMICINA	AZITROMICINA,azitromicina
BETAHISTINA	BETAHISTINA,betahistina
BISOPROLOL	BISOPROLOL,bisoprolol,bisopro
CARBAMAZEPINA	CARBAMAZEPINA,carbamazepina
CARVEDILOL	CARVEDILOL,carvedilol
CEFTRIAXONA	CEFTRIAZONA,ceftriaozona,CEFTRIAXONA,ceftriaxona,ceftri
CIPROFLOXACINO	CIPROFLOXACIN,CIPROFLOXACINO,ciprofloxacino
CLOBAZAM	CLOBAZAM,clobazam
CLOPIDOGREL	CLOPIDOGREL,clopidogrel
DAPAGLIFLOZINA	DAPAGLIFLOZINA,dapagliflozina
DOMPERIDONA	DOMPERIDONA,domperidona,dompe
ESCITALOPRAM	ESCITALOPRAM,escitalopram
ESOMEPRAZOL	ESOMEPRAZOL,esomeprazol
FAMOTIDINA	FAMOTIDINA,famotidina
FEXOFENADINA	FEXOFENADINA,fexofenadina
FUROSEMIDA	FUROSEMID,furosemid
IBUPROFENO	IBUPROFENO,ibuprof
LORATADINA	loratad
LOSARTAN	LOSARTAN,losartan
MEROPENEM	MEROPENEM,meropenem
METFORMINA	METFORMIN,metformin
METRONIDAZOL	METRONIDAZOL
NEBIVOLOL	NEBIVOLOL,nebivolol
OMEPRAZOL	OMEPRAZOL
OXCARBAZEPINA	OXCAR,oxcar
PARACETAMOL	PARACETAMOL,paracetamol
PREGABALINA	PREGABALINA,pregabalina
QUETIAPINA	QUETIAPIN,quetiapin
RIVAROXABAN	RIVAROXABAN,rivaroxaban
ROSUVASTATINA	ROSUVAS,rosuvastatina
SERTRALINA	SERTRALINA,sertralina
SILDENAFIL	SILDENAFIL,SILDENAFILO,sildenafil
SITAGLIPTINA	SITAGLIPTINA,sitagliptina
SOLIFENACINA	SOLIFENACINA,solifenacina
TRAMADOL	TRAMADOL,tramadol
TRANEXAMICO	TRANEXAMICO,tranexamico
TRAZODONA	TRAZODONA,trazodona
"""

# No necesitamos parsear el catálogo aquí si el filtrado ya se hizo en updater.py
# Pero lo dejamos por si en el futuro se quiere añadir filtrado en la UI
def parsear_catalogo(raw_data):
    # ... (código de parsear_catalogo como lo tenías)
    catalogo_procesado = {}
    for line in raw_data.strip().splitlines():
        line = line.strip();
        if not line: continue
        parts = line.split('\t')
        producto_principal_original_casing = parts[0].strip()
        if not producto_principal_original_casing: continue
        palabras_clave_para_este_producto = {producto_principal_original_casing.lower()}
        if len(parts) > 1 and parts[1].strip():
            secundarias_raw = parts[1].strip()
            palabras_secundarias_lista = [kw.strip().lower() for kw in secundarias_raw.split(',') if kw.strip()]
            palabras_clave_para_este_producto.update(palabras_secundarias_lista)
        catalogo_procesado[producto_principal_original_casing] = palabras_clave_para_este_producto
    return catalogo_procesado

MI_CATALOGO_ESTRUCTURADO = parsear_catalogo(CATALOGO_PRODUCTOS_RAW) # Se mantiene por si acaso


def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime('%H:%M:%S')
    if 'log_messages_streamlit' not in st.session_state: # Usar un nombre diferente para el log de esta app
        st.session_state.log_messages_streamlit = []
    st.session_state.log_messages_streamlit.append(f"{timestamp} - {level.upper()}: {message}")
    print(f"STREAMLIT_APP_LOG - {timestamp} - {level.upper()}: {message}") # Para logs del servidor de Streamlit Cloud


@st.cache_data(ttl=300) # Cachear los datos del Gist por 5 minutos (300 segundos) para reducir llamadas
def cargar_datos_desde_gist():
    log_message(f"Intentando cargar datos desde Gist: {GIST_CACHE_URL}", "INFO")
    oportunidades = []
    fecha_cache_obtenida = "No disponible"
    try:
        # Añadir un timestamp al final de la URL para intentar evitar el caché del navegador/CDN agresivo
        cache_buster_url = f"{GIST_CACHE_URL}?v={int(time.time())}"
        response = requests.get(cache_buster_url, timeout=20) # Timeout más corto, es solo leer un archivo
        response.raise_for_status()
        datos_gist = response.json()
        
        fecha_cache_obtenida = datos_gist.get("fecha_cache", "Desconocida (sin fecha en Gist)")
        oportunidades = datos_gist.get("oportunidades", [])
        
        if oportunidades:
            log_message(f"Datos ({len(oportunidades)} oportunidades) cargados desde Gist. Fecha del caché Gist: {fecha_cache_obtenida}.", "INFO")
        else:
            log_message(f"Gist cargado pero no contiene oportunidades. Fecha del caché Gist: {fecha_cache_obtenida}.", "ADVERTENCIA")
            
    except requests.exceptions.Timeout:
        log_message("Timeout al cargar datos desde Gist.", "ERROR")
    except requests.exceptions.RequestException as e:
        log_message(f"Error de red al cargar datos desde Gist: {e}", "ERROR")
    except json.JSONDecodeError as e:
        log_message(f"Error al decodificar JSON desde Gist: {e}. Contenido recibido: {response.text[:500] if 'response' in locals() else 'N/A'}", "ERROR")
    except Exception as e:
        log_message(f"Error inesperado al cargar datos desde Gist: {e}", "ERROR")
    
    return oportunidades, fecha_cache_obtenida

# --- Streamlit UI ---
st.set_page_config(page_title="PINNACLE - Licitaciones", page_icon=":briefcase:", layout="wide")
st.title("PINNACLE :briefcase: - Oportunidades en Licitaciones CENABAST")
st.markdown("Resultados de licitaciones de CENABAST (actualizados diariamente por un proceso automático).")

# Inicializar session_state para los logs de esta app
if 'log_messages_streamlit' not in st.session_state:
    st.session_state.log_messages_streamlit = []

# Botón para refrescar la vista (vuelve a cargar del Gist)
if st.button("Refrescar Vista (desde caché diario)", type="primary"):
    # Limpiar el caché de la función para forzar una nueva descarga del Gist
    cargar_datos_desde_gist.clear() 
    st.rerun()

# Cargar los datos
oportunidades_a_mostrar, fecha_del_cache = cargar_datos_desde_gist()

st.caption(f"Datos mostrados corresponden a la actualización automática del: {fecha_del_cache}")

if oportunidades_a_mostrar:
    st.header(f"Resultados de la Búsqueda ({len(oportunidades_a_mostrar)} oportunidades encontradas):")
    
    # Crear DataFrame a partir de los datos cargados
    df_oportunidades = pd.DataFrame(oportunidades_a_mostrar)
    
    # Columnas esperadas en el JSON del Gist (basado en lo que `updater.py` guarda)
    # y cómo se renombrarán para la visualización
    columnas_originales_esperadas = [
        "Tender_id",
        "Nombre_Producto Licitación", 
        "Descripcion", 
        "Fecha Cierre",
        "Quantity", 
        "Vencimiento",
        "Producto de mi Catálogo", 
        "Nombre Licitación General" 
    ]
    
    # Crear el DataFrame intermedio asegurando que todas las columnas esperadas existan
    df_display_intermediate = pd.DataFrame()
    for col in columnas_originales_esperadas:
        if col in df_oportunidades.columns:
            df_display_intermediate[col] = df_oportunidades[col]
        else:
            # Si una columna esperada no está en el JSON del Gist, llenar con N/D
            # Esto podría pasar si cambias la estructura en updater.py y no en la app
            log_message(f"Columna '{col}' no encontrada en los datos del Gist. Se mostrará N/D.", "ADVERTENCIA")
            df_display_intermediate[col] = "N/D" 
    
    # Renombrar para la visualización
    df_display_intermediate = df_display_intermediate.rename(columns={
        "Nombre_Producto Licitación": "Nombre_Producto" 
    })
    
    # Seleccionar y ordenar las columnas finales para mostrar en la UI
    final_column_order_display = [
        "Tender_id", "Nombre_Producto", "Descripcion", 
        "Fecha Cierre", "Quantity", "Vencimiento"
    ]
    # Asegurar que solo se muestren estas columnas si existen después del renombrado
    df_display_final = df_display_intermediate[[col for col in final_column_order_display if col in df_display_intermediate.columns]]

    st.dataframe(df_display_final, height=600, use_container_width=True)

    @st.cache_data
    def convert_df_to_csv(df_to_convert):
        return df_to_convert.to_csv(index=False).encode('utf-8-sig')

    csv = convert_df_to_csv(df_display_final) 
    st.download_button(
        label="Descargar resultados como CSV",
        data=csv,
        file_name='oportunidades_pinnacle.csv',
        mime='text/csv',
    )
else: # Si oportunidades_a_mostrar está vacía
    st.info("No hay oportunidades para mostrar en este momento. El caché podría estar vacío o hubo un error al cargarlo. Revisa el log.")

# Expansor para el log
with st.expander("Ver registro de actividad de esta sesión (App Streamlit)", expanded=False):
    if st.session_state.log_messages_streamlit:
        log_text = "\n".join(reversed(st.session_state.log_messages_streamlit))
        st.text_area("Registro:", value=log_text, height=300, disabled=True, key="log_area_streamlit_app")
    else:
        st.caption("El registro de actividad de esta sesión está vacío.")