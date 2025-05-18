import streamlit as st
import requests
import json
from datetime import datetime, date
import pandas as pd
import time
import os # No se usa directamente, pero es buena práctica importarlo si se manejan paths

# --- CONFIGURACIÓN ---
try:
    API_TICKET = st.secrets["API_TICKET_MERCADOPUBLICO"]
except KeyError:
    API_TICKET = "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL" 
    if API_TICKET == "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL" and not os.path.exists(".streamlit/secrets.toml"):
        # st.sidebar.warning("API_TICKET no configurado. Se leerá del caché Gist.")
        pass

# --- URL DEL GIST DE CACHÉ ---
GIST_CACHE_URL = "https://gist.githubusercontent.com/Neshamalic/7683372d7c8374cbd8bc67d81eec5fe9/raw/7705bf1ca22a60fb3e8683f7394cf1c756cde759/oportunidades_cache.json" # Asegúrate que esta sea tu URL Raw correcta

# --- TU CATÁLOGO DE PRODUCTOS (se mantiene por si la app hace algún filtrado local futuro) ---
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

def parsear_catalogo(raw_data):
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

MI_CATALOGO_ESTRUCTURADO = parsear_catalogo(CATALOGO_PRODUCTOS_RAW)

def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime('%H:%M:%S')
    if 'log_messages_streamlit' not in st.session_state:
        st.session_state.log_messages_streamlit = []
    st.session_state.log_messages_streamlit.append(f"{timestamp} - {level.upper()}: {message}")
    print(f"STREAMLIT_APP_LOG - {timestamp} - {level.upper()}: {message}")

@st.cache_data(ttl=300) # Cachear los datos del Gist por 5 minutos
def cargar_datos_desde_gist():
    log_message(f"Intentando cargar datos desde Gist: {GIST_CACHE_URL}", "INFO")
    oportunidades = []
    fecha_cache_obtenida = "No disponible"
    response_text_for_debug = "N/A"
    try:
        cache_buster_url = f"{GIST_CACHE_URL}?v={int(time.time())}"
        response = requests.get(cache_buster_url, timeout=20)
        response_text_for_debug = response.text
        response.raise_for_status()
        datos_gist = response.json()
        fecha_cache_obtenida = datos_gist.get("fecha_cache", "Desconocida (sin fecha en Gist)")
        oportunidades = datos_gist.get("oportunidades", [])
        if oportunidades:
            log_message(f"Datos ({len(oportunidades)} oportunidades) cargados desde Gist. Fecha del caché Gist: {fecha_cache_obtenida}.", "INFO")
        else:
            log_message(f"Gist cargado pero no contiene oportunidades o la lista está vacía. Fecha del caché Gist: {fecha_cache_obtenida}.", "ADVERTENCIA")
    except Exception as e:
        log_message(f"Error al cargar datos desde Gist: {e}. Respuesta (si existe): {response_text_for_debug[:500]}", "ERROR")
    return oportunidades, fecha_cache_obtenida

# --- Streamlit UI ---
st.set_page_config(page_title="PINNACLE - Licitaciones", page_icon=":briefcase:", layout="wide")
st.title("PINNACLE :briefcase: - Oportunidades en Licitaciones CENABAST")
st.markdown("Resultados de licitaciones de CENABAST (actualizados diariamente por un proceso automático).")

if 'log_messages_streamlit' not in st.session_state:
    st.session_state.log_messages_streamlit = []

if st.button("Refrescar Vista (desde caché diario)", type="primary"):
    cargar_datos_desde_gist.clear() 
    st.rerun()

oportunidades_a_mostrar, fecha_del_cache = cargar_datos_desde_gist()
st.caption(f"Datos mostrados corresponden a la actualización automática del: {fecha_del_cache}")

if oportunidades_a_mostrar:
    st.header(f"Resultados de la Búsqueda ({len(oportunidades_a_mostrar)} oportunidades encontradas):")
    
    df_oportunidades = pd.DataFrame(oportunidades_a_mostrar)
    
    df_para_mostrar_ui = df_oportunidades.copy()

    # Columnas que esperamos que vengan del Gist y que queremos mostrar
    columnas_del_gist_a_mostrar = [
        "Tender_id", 
        "Nombre_Producto Licitación", 
        "Descripcion", 
        "Fecha Cierre",
        "Quantity", 
        "Vencimiento"
        # "Producto de mi Catálogo", # Opcional, puedes descomentar si quieres mostrarla
        # "Nombre Licitación General" # Opcional
    ]
    
    # Crear el DataFrame final, asegurando que todas las columnas esperadas existan
    df_display_final = pd.DataFrame()
    for col_esperada in columnas_del_gist_a_mostrar:
        if col_esperada in df_para_mostrar_ui.columns:
            # Renombrar "Nombre_Producto Licitación" para la UI
            col_para_ui = "Nombre_Producto" if col_esperada == "Nombre_Producto Licitación" else col_esperada
            df_display_final[col_para_ui] = df_para_mostrar_ui[col_esperada]
        else:
            col_para_ui = "Nombre_Producto" if col_esperada == "Nombre_Producto Licitación" else col_esperada
            log_message(f"Columna '{col_esperada}' (mostrada como '{col_para_ui}') no encontrada. Se usará N/D.", "ADVERTENCIA")
            df_display_final[col_para_ui] = "N/D"
    
    # Asegurar el orden final de las columnas para la UI
    final_column_order_display = [
        "Tender_id", "Nombre_Producto", "Descripcion", 
        "Fecha Cierre", "Quantity", "Vencimiento"
    ]
    # Reordenar si es necesario, manteniendo solo las columnas que realmente existen en df_display_final
    df_display_final = df_display_final[[col for col in final_column_order_display if col in df_display_final.columns]]

    st.dataframe(
        df_display_final,
        height=600,
        use_container_width=True,
        hide_index=True
        # No se usa column_config para links aquí
    )
    
    # Para el CSV, podemos usar df_para_mostrar_ui que tiene más columnas si queremos
    # o construir uno específico. Vamos a usar df_oportunidades (los datos crudos del Gist)
    # para tener la mayor flexibilidad.
    @st.cache_data
    def convert_df_to_csv(df_crudo_oportunidades):
        df_para_csv = df_crudo_oportunidades.copy()
        # Añadir la URL completa al CSV para conveniencia
        if 'Tender_id' in df_para_csv.columns:
            df_para_csv['URL_Licitacion'] = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=" + df_para_csv['Tender_id'].astype(str)
        
        # Renombrar "Nombre_Producto Licitación" si existe
        if "Nombre_Producto Licitación" in df_para_csv.columns:
            df_para_csv = df_para_csv.rename(columns={"Nombre_Producto Licitación": "Nombre_Producto"})
            
        return df_para_csv.to_csv(index=False).encode('utf-8-sig')

    csv = convert_df_to_csv(df_oportunidades) # Pasar los datos originales del Gist
    st.download_button(
        label="Descargar resultados como CSV",
        data=csv,
        file_name='oportunidades_pinnacle.csv',
        mime='text/csv',
    )
else:
    st.info("No hay oportunidades para mostrar en este momento. El caché podría estar vacío o hubo un error al cargarlo. Revisa el log.")

with st.expander("Ver registro de actividad de esta sesión (App Streamlit)", expanded=False):
    if 'log_messages_streamlit' in st.session_state and st.session_state.log_messages_streamlit:
        log_text = "\n".join(reversed(st.session_state.log_messages_streamlit))
        st.text_area("Registro:", value=log_text, height=300, disabled=True, key="log_area_streamlit_pinnacle_simple")
    else:
        st.caption("El registro de actividad de esta sesión está vacío.")