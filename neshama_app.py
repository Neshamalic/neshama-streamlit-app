import streamlit as st
import requests
import json
from datetime import datetime, date
import pandas as pd
import time
import os # No se usa directamente, pero es buena práctica importarlo si se manejan paths

# --- CONFIGURACIÓN ---
# El API_TICKET no es esencial para la lógica principal de esta app ahora,
# pero se mantiene por si el bloque try-except o futuras funciones lo usan.
try:
    API_TICKET = st.secrets["API_TICKET_MERCADOPUBLICO"]
except KeyError:
    API_TICKET = "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL" # Este valor no se usará si el Gist funciona
    if API_TICKET == "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL" and not os.path.exists(".streamlit/secrets.toml"):
        # Solo mostrar advertencia si no hay secrets locales y tampoco se pudo cargar el secret de la nube
        # (Aunque st.secrets ya daría un error más directo si se intenta acceder y no existe en la nube)
        # st.sidebar.warning("API_TICKET no configurado. Se leerá del caché Gist.")
        pass # No es crítico si solo leemos del Gist


# --- URL DEL GIST DE CACHÉ (¡ASEGÚRATE QUE ESTA SEA TU URL RAW CORRECTA!) ---
GIST_CACHE_URL = "https://gist.githubusercontent.com/Neshamalic/7683372d7c8374cbd8bc67d81eec5fe9/raw/7705bf1ca22a60fb3e8683f7394cf1c756cde759/oportunidades_cache.json"

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

MI_CATALOGO_ESTRUCTURADO = parsear_catalogo(CATALOGO_PRODUCTOS_RAW) # Se mantiene por si acaso

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
    response_text_for_debug = "N/A" # Para guardar el texto de la respuesta en caso de error JSON
    try:
        cache_buster_url = f"{GIST_CACHE_URL}?v={int(time.time())}"
        response = requests.get(cache_buster_url, timeout=20)
        response_text_for_debug = response.text # Guardar antes de response.raise_for_status()
        response.raise_for_status() # Lanza un error para respuestas HTTP 4xx/5xx
        datos_gist = response.json()
        
        fecha_cache_obtenida = datos_gist.get("fecha_cache", "Desconocida (sin fecha en Gist)")
        oportunidades = datos_gist.get("oportunidades", [])
        
        if oportunidades:
            log_message(f"Datos ({len(oportunidades)} oportunidades) cargados desde Gist. Fecha del caché Gist: {fecha_cache_obtenida}.", "INFO")
        else:
            log_message(f"Gist cargado pero no contiene oportunidades o la lista está vacía. Fecha del caché Gist: {fecha_cache_obtenida}.", "ADVERTENCIA")
            
    except requests.exceptions.Timeout:
        log_message("Timeout al cargar datos desde Gist.", "ERROR")
    except requests.exceptions.RequestException as e: # Captura errores HTTP y otros de red
        log_message(f"Error de red/HTTP al cargar datos desde Gist: {e}. Respuesta (si existe): {response_text_for_debug[:500]}", "ERROR")
    except json.JSONDecodeError as e:
        log_message(f"Error al decodificar JSON desde Gist: {e}. Contenido recibido: {response_text_for_debug[:500]}", "ERROR")
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

if st.button("Refrescar Vista (desde caché diario)", type="primary"):
    cargar_datos_desde_gist.clear() 
    st.rerun()

oportunidades_a_mostrar, fecha_del_cache = cargar_datos_desde_gist()

st.caption(f"Datos mostrados corresponden a la actualización automática del: {fecha_del_cache}")

if oportunidades_a_mostrar: # Solo proceder si hay datos
    st.header(f"Resultados de la Búsqueda ({len(oportunidades_a_mostrar)} oportunidades encontradas):")
    
    df_oportunidades = pd.DataFrame(oportunidades_a_mostrar)
    
    # Crear una copia para el procesamiento y visualización
    df_para_procesar = df_oportunidades.copy()

    # Columnas que esperamos que vengan del Gist (basado en lo que `updater.py` guarda)
    columnas_del_gist_esperadas = [
        "Tender_id", "Nombre_Producto Licitación", "Descripcion", 
        "Fecha Cierre", "Quantity", "Vencimiento",
        "Producto de mi Catálogo", "Nombre Licitación General" 
    ]
    
    # Asegurar que todas las columnas esperadas existan en df_para_procesar, si no, añadir con N/D
    for col in columnas_del_gist_esperadas:
        if col not in df_para_procesar.columns:
            log_message(f"Columna '{col}' no encontrada en los datos del Gist. Se mostrará N/D.", "ADVERTENCIA")
            df_para_procesar[col] = "N/D"
    
    # Crear la columna con la URL completa para cada Tender_id para el link
    if 'Tender_id' in df_para_procesar.columns:
        df_para_procesar['URL_Licitacion_Completa'] = "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=" + df_para_procesar['Tender_id'].astype(str)
    else:
        # Esto no debería pasar si la columna se añadió con N/D arriba
        df_para_procesar['URL_Licitacion_Completa'] = ""

    # Formatear la columna Tender_id para que sea un link Markdown
    def format_tender_id_as_link_direct(row):
        tender_id = row.get('Tender_id', "N/D") # Usar .get para evitar KeyError
        url = row.get('URL_Licitacion_Completa', "")
        if pd.isna(tender_id) or tender_id == "N/D" or pd.isna(url) or url == "":
            return str(tender_id) 
        return f"[{tender_id}]({url})"

    # Aplicar el formateo de Markdown directamente a la columna 'Tender_id'
    # Solo si las columnas base existen
    if 'Tender_id' in df_para_procesar.columns and 'URL_Licitacion_Completa' in df_para_procesar.columns:
        df_para_procesar['Tender_id_Con_Link'] = df_para_procesar.apply(format_tender_id_as_link_direct, axis=1)
    else: # Si falta Tender_id o URL_Licitacion_Completa, usar el Tender_id original o N/D
        df_para_procesar['Tender_id_Con_Link'] = df_para_procesar.get('Tender_id', "N/D")
    
    # Renombrar columnas para la visualización final
    df_para_mostrar_ui = df_para_procesar.rename(columns={
        "Nombre_Producto Licitación": "Nombre_Producto",
        "Tender_id_Con_Link": "ID Licitación (Ver)" # Esta será la columna con el link clicable
    })
    
    # Seleccionar y ordenar las columnas finales para mostrar en la UI
    final_column_order_display = [
        "ID Licitación (Ver)", 
        "Nombre_Producto", 
        "Descripcion", 
        "Fecha Cierre", 
        "Quantity", 
        "Vencimiento"
    ]
    
    df_display_final = pd.DataFrame()
    for col in final_column_order_display:
        if col in df_para_mostrar_ui.columns:
            df_display_final[col] = df_para_mostrar_ui[col]
        else:
            log_message(f"Columna final para UI '{col}' no generada. Se mostrará N/D.", "ADVERTENCIA")
            df_display_final[col] = "N/D" 

    st.dataframe(
        df_display_final,
        height=600,
        use_container_width=True,
        hide_index=True,
        # No se especifica column_config para "ID Licitación (Ver)"
        # para dejar que Streamlit intente renderizar el Markdown por defecto.
    )

    # Para el CSV, es mejor tener el Tender_id original y la URL por separado.
    @st.cache_data
    def convert_df_to_csv(df_source_for_csv):
        df_for_csv_export = pd.DataFrame()
        # Usar la columna Tender_id original (antes de formatearla como Markdown)
        if 'Tender_id' in df_source_for_csv.columns:
             df_for_csv_export['Tender_id'] = df_source_for_csv['Tender_id'] # Este es el ID crudo
        if 'URL_Licitacion_Completa' in df_source_for_csv.columns:
            df_for_csv_export['URL_Licitacion'] = df_source_for_csv['URL_Licitacion_Completa']
        
        # Usar los nombres de columna ya renombrados para la UI (como "Nombre_Producto")
        cols_restantes_renombradas = ["Nombre_Producto", "Descripcion", "Fecha Cierre", "Quantity", "Vencimiento"]
        for col_ui in cols_restantes_renombradas:
            # Encontrar el nombre original de la columna si fue renombrada
            col_original = col_ui 
            if col_ui == "Nombre_Producto" and "Nombre_Producto Licitación" in df_source_for_csv.columns:
                col_original = "Nombre_Producto Licitación"
            
            if col_original in df_source_for_csv.columns:
                 df_for_csv_export[col_ui] = df_source_for_csv[col_original]
            else:
                df_for_csv_export[col_ui] = "N/D"
        return df_for_csv_export.to_csv(index=False).encode('utf-8-sig')

    # Usar df_para_procesar para el CSV ya que tiene Tender_id original y URL_Licitacion_Completa
    csv = convert_df_to_csv(df_para_procesar) 
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
        st.text_area("Registro:", value=log_text, height=300, disabled=True, key="log_area_streamlit_pinnacle_final")
    else:
        st.caption("El registro de actividad de esta sesión está vacío.")