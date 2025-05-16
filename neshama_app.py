import streamlit as st # Debe estar al principio para st.secrets
import requests
import json
from datetime import datetime, timedelta
import pandas as pd
import time

# --- CONFIGURACIÓN ---
try:
    API_TICKET = st.secrets["API_TICKET_MERCADOPUBLICO"]
except KeyError:
    API_TICKET = "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL" 
    if API_TICKET == "TU_TICKET_POR_DEFECTO_O_DE_PRUEBA_LOCAL":
        st.error("API_TICKET no configurado en los secrets. La aplicación podría no funcionar correctamente. "
                 "Para despliegue, configura el secret 'API_TICKET_MERCADOPUBLICO'. "
                 "Para pruebas locales, crea '.streamlit/secrets.toml'.")
        # Considera st.stop() si el ticket es absolutamente esencial y no se puede proceder sin él.

CODIGO_CENABAST = "6957"
BASE_URL_LICITACIONES = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"

# --- TU CATÁLOGO DE PRODUCTOS ---
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
        line = line.strip()
        if not line:
            continue
        parts = line.split('\t')
        producto_principal_original_casing = parts[0].strip()
        if not producto_principal_original_casing:
            continue
        palabras_clave_para_este_producto = {producto_principal_original_casing.lower()}
        if len(parts) > 1 and parts[1].strip():
            secundarias_raw = parts[1].strip()
            palabras_secundarias_lista = [kw.strip().lower() for kw in secundarias_raw.split(',') if kw.strip()]
            palabras_clave_para_este_producto.update(palabras_secundarias_lista)
        catalogo_procesado[producto_principal_original_casing] = palabras_clave_para_este_producto
    return catalogo_procesado

MI_CATALOGO_ESTRUCTURADO = parsear_catalogo(CATALOGO_PRODUCTOS_RAW)

LICITACIONES_DEBUG_IMPRESAS = 0
MAX_LICITACIONES_DEBUG = 3

def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime('%H:%M:%S')
    if 'log_messages' not in st.session_state:
        st.session_state.log_messages = []
    st.session_state.log_messages.append(f"{timestamp} - {level.upper()}: {message}")
    print(f"{timestamp} - {level.upper()}: {message}")

def obtener_licitaciones_cenabast_activas():
    params = {
        "ticket": API_TICKET,
        "CodigoOrganismo": CODIGO_CENABAST,
        "estado": "activas"
    }
    try:
        response = requests.get(BASE_URL_LICITACIONES, params=params, timeout=45)
        response.raise_for_status()
        data = response.json()
        if data.get("Cantidad") is not None and data.get("Cantidad") > 0 and data.get("Listado"):
            return data["Listado"]
        else:
            log_message(f"No se encontraron licitaciones activas o respuesta inesperada. Respuesta API: {data}", "ADVERTENCIA")
            return []
    except requests.exceptions.Timeout:
        log_message("Timeout al obtener listado de licitaciones activas.", "ERROR")
        return []
    except requests.exceptions.RequestException as e:
        log_message(f"Al obtener listado de licitaciones: {e}", "ERROR")
        if 'response' in locals() and response is not None:
            log_message(f"Respuesta del servidor: {response.text}", "ERROR")
    except json.JSONDecodeError as je:
        log_message(f"Error al decodificar JSON del listado: {je}. Respuesta: {response.text if 'response' in locals() and response is not None else 'No response object'}", "ERROR")
    return []

def obtener_detalle_licitacion(codigo_licitacion):
    global LICITACIONES_DEBUG_IMPRESAS
    params = {
        "ticket": API_TICKET,
        "codigo": codigo_licitacion
    }
    intentos = 0
    max_intentos = 2 
    retraso_base_reintento = 5 # Segundos para el primer reintento por error 10500

    while intentos < max_intentos:
        try:
            response = requests.get(BASE_URL_LICITACIONES, params=params, timeout=45)
            response.raise_for_status()
            detalle_completo_json = response.json()

            if detalle_completo_json and detalle_completo_json.get("Cantidad", 0) > 0 and detalle_completo_json.get("Listado"):
                detalle_lic_obj = detalle_completo_json["Listado"][0]
                if LICITACIONES_DEBUG_IMPRESAS < MAX_LICITACIONES_DEBUG:
                    # Descomentar para depuración intensiva si es necesario
                    # log_message(f"JSON OBTENIDO para {codigo_licitacion}:\n{json.dumps(detalle_lic_obj, indent=2, ensure_ascii=False)}", "DEBUG")
                    LICITACIONES_DEBUG_IMPRESAS += 1
                return detalle_lic_obj
            elif detalle_completo_json and detalle_completo_json.get("Codigo") == 10500:
                retraso_actual = retraso_base_reintento * (2**intentos)
                log_message(f"Codigo 10500 para {codigo_licitacion}. Intento {intentos + 1}/{max_intentos}. Reintentando en {retraso_actual}s...", "ADVERTENCIA")
                time.sleep(retraso_actual)
                intentos += 1
                continue
            else:
                log_message(f"Respuesta inesperada para {codigo_licitacion}. Detalle: {detalle_completo_json}. Intento {intentos + 1}/{max_intentos}.", "ADVERTENCIA")
                retraso_actual = retraso_base_reintento * (2**intentos)
                time.sleep(retraso_actual)
                intentos +=1
                continue
        except requests.exceptions.HTTPError as http_err:
            error_msg = f"HTTP {http_err.response.status_code} para {codigo_licitacion}"
            retraso_actual = retraso_base_reintento * (2**intentos)
            try:
                error_json = http_err.response.json()
                error_msg += f" - Detalle API: {error_json}"
                if error_json.get("Codigo") == 10500:
                     log_message(f"Error 10500 (vía HTTPError) para {codigo_licitacion}. Intento {intentos + 1}/{max_intentos}. Reintentando en {retraso_actual}s...", "ADVERTENCIA")
                else:
                    log_message(error_msg + f". Intento {intentos + 1}/{max_intentos}. Reintentando en {retraso_actual}s...", "ERROR")
            except json.JSONDecodeError:
                log_message(error_msg + f" (Cuerpo no JSON: {http_err.response.text}). Intento {intentos + 1}/{max_intentos}. Reintentando en {retraso_actual}s...", "ERROR")
            intentos += 1
            if intentos < max_intentos:
                time.sleep(retraso_actual)
            continue
        except requests.exceptions.Timeout:
            retraso_actual = retraso_base_reintento * (2**intentos)
            log_message(f"Timeout para {codigo_licitacion}. Intento {intentos + 1}/{max_intentos}. Reintentando en {retraso_actual}s...", "ERROR")
            intentos +=1
            if intentos < max_intentos:
                time.sleep(retraso_actual)
            continue
        except requests.exceptions.RequestException as e:
            retraso_actual = retraso_base_reintento * (2**intentos)
            log_message(f"Error de red para {codigo_licitacion}: {e}. Intento {intentos + 1}/{max_intentos}. Reintentando en {retraso_actual}s...", "ERROR")
            intentos +=1
            if intentos < max_intentos:
                time.sleep(retraso_actual)
            continue
        except json.JSONDecodeError as je:
            log_message(f"Error al decodificar JSON para {codigo_licitacion} (respuesta OK): {je}. Respuesta: {response.text if 'response' in locals() and response is not None else 'No response object'}", "ERROR")
            return None
    
    log_message(f"Se superaron los {max_intentos} intentos para obtener detalle de {codigo_licitacion}.", "ERROR")
    return None

def producto_coincide_con_catalogo(nombre_item_licitacion, descripcion_item_licitacion, catalogo_estructurado):
    texto_busqueda_licitacion = ( (nombre_item_licitacion.lower() if nombre_item_licitacion else "") + " " +
                                  (descripcion_item_licitacion.lower() if descripcion_item_licitacion else "") ).strip()
    if not texto_busqueda_licitacion:
        return None
    for producto_principal_catalogo, conjunto_palabras_clave in catalogo_estructurado.items():
        for palabra_clave_individual in conjunto_palabras_clave:
            if palabra_clave_individual in texto_busqueda_licitacion:
                return producto_principal_catalogo
    return None

# --- Streamlit UI ---
# --- CAMBIO DE TÍTULO DE PÁGINA/PESTAÑA ---
st.set_page_config(page_title="PINNACLE - Licitaciones", page_icon=":briefcase:", layout="wide")

# --- CAMBIO DE TÍTULO PRINCIPAL DE LA APP ---
st.title("PINNACLE :briefcase: - Oportunidades en Licitaciones CENABAST") # Cambiado emoji también
st.markdown("Buscando licitaciones vigentes de CENABAST que coincidan con tu catálogo de productos.")

if 'oportunidades_encontradas' not in st.session_state:
    st.session_state.oportunidades_encontradas = []
if 'log_messages' not in st.session_state:
    st.session_state.log_messages = []
if 'busqueda_realizada' not in st.session_state:
    st.session_state.busqueda_realizada = False

st.sidebar.header("Tu Catálogo de Productos Procesado")
if MI_CATALOGO_ESTRUCTURADO:
    for prod_principal, kws in MI_CATALOGO_ESTRUCTURADO.items():
        st.sidebar.markdown(f"**{prod_principal}**: {', '.join(kws)}")
else:
    st.sidebar.warning("El catálogo de productos está vacío o no se pudo procesar.")

# --- CAMBIO DE RETRASO ---
RETRASO_ENTRE_LLAMADAS_DETALLE = 1.0  # Cambiado a 1 segundo
# ¡PRECAUCIÓN! Un retraso menor puede causar errores de "peticiones simultáneas".
# Si ocurren, aumenta este valor (ej. 1.5, 2.0, 2.5).

def run_neshama_logic():
    global LICITACIONES_DEBUG_IMPRESAS
    LICITACIONES_DEBUG_IMPRESAS = 0 

    st.session_state.log_messages = [] 
    st.session_state.oportunidades_encontradas = []
    st.session_state.busqueda_realizada = True

    log_message("PINNACLE: Iniciando búsqueda de licitaciones activas de CENABAST...") # Nombre cambiado
    licitaciones_activas_cenabast = obtener_licitaciones_cenabast_activas()

    if licitaciones_activas_cenabast:
        log_message(f"Se encontraron {len(licitaciones_activas_cenabast)} licitaciones activas (resumen). Obteniendo detalles...")
        
        progress_text_detalle = "Obteniendo detalles de licitaciones. Por favor espere..."
        progress_bar_placeholder = st.empty()
        total_licitaciones_activas = len(licitaciones_activas_cenabast)

        for i, licitacion_resumen in enumerate(licitaciones_activas_cenabast):
            codigo_externo = licitacion_resumen.get("CodigoExterno")
            # nombre_licitacion_resumen = licitacion_resumen.get('Nombre', 'Sin Nombre Asignado') # No usado directamente
            
            progress_fraction = (i + 1) / total_licitaciones_activas
            progress_bar_placeholder.progress(progress_fraction, text=f"{progress_text_detalle} ({i+1}/{total_licitaciones_activas}) - {codigo_externo}")

            if not codigo_externo:
                log_message(f"Licitación sin CodigoExterno en el resumen: {licitacion_resumen}", "ADVERTENCIA")
                continue
            
            time.sleep(RETRASO_ENTRE_LLAMADAS_DETALLE)
            detalle_lic = obtener_detalle_licitacion(codigo_externo)

            if detalle_lic:
                fecha_cierre_str = None
                fecha_cierre_str_nivel_superior = detalle_lic.get("FechaCierre")
                if fecha_cierre_str_nivel_superior and isinstance(fecha_cierre_str_nivel_superior, str) and fecha_cierre_str_nivel_superior.strip():
                    fecha_cierre_str = fecha_cierre_str_nivel_superior
                else:
                    fechas_obj = detalle_lic.get("Fechas")
                    if fechas_obj and isinstance(fechas_obj, dict):
                        fecha_cierre_str_anidada = fechas_obj.get("FechaCierre")
                        if fecha_cierre_str_anidada and isinstance(fecha_cierre_str_anidada, str) and fecha_cierre_str_anidada.strip():
                            fecha_cierre_str = fecha_cierre_str_anidada

                fecha_cierre_dt = None
                dias_para_cierre = "N/A"
                fecha_cierre_display = "N/A"

                if fecha_cierre_str:
                    try:
                        ts = fecha_cierre_str.replace('Z', '')
                        if '+' in ts: ts = ts.split('+')[0]
                        
                        date_format_to_try = '%Y-%m-%dT%H:%M:%S'
                        ts_corregido = ts
                        if '.' in ts:
                            partes_ts = ts.split('.')
                            ts_parte_entera = partes_ts[0]
                            ts_microsegundos = partes_ts[1][:6]
                            ts_corregido = f"{ts_parte_entera}.{ts_microsegundos}"
                            date_format_to_try = '%Y-%m-%dT%H:%M:%S.%f'

                        fecha_cierre_dt = datetime.strptime(ts_corregido, date_format_to_try)
                        fecha_cierre_display = fecha_cierre_dt.strftime('%d/%m/%Y %H:%M')
                        hoy = datetime.now()
                        if fecha_cierre_dt > hoy:
                            delta = fecha_cierre_dt - hoy
                            dias_para_cierre = delta.days
                        else:
                            dias_para_cierre = 0 
                    except ValueError as ve:
                        log_message(f"Error parseando FechaCierre '{fecha_cierre_str}' (corregido a '{ts_corregido if 'ts_corregido' in locals() else 'N/A'}') para {codigo_externo}: {ve}. Se usará N/A.", "ADVERTENCIA")
                else:
                    log_message(f"No se encontró un valor válido para FechaCierre para {codigo_externo}.", "ADVERTENCIA")
                
                items_licitacion = detalle_lic.get("Items", {}).get("Listado", [])
                if not items_licitacion:
                     log_message(f"Licitación {codigo_externo} no tiene items detallados.", "ADVERTENCIA")

                for item in items_licitacion:
                    nombre_producto_licitacion = item.get("NombreProducto", "No especificado")
                    descripcion_item_licitacion = item.get("Descripcion", "No especificado")
                    cantidad_licitacion = item.get("Cantidad", "No especificado")

                    producto_de_mi_catalogo_coincidente = producto_coincide_con_catalogo(
                        nombre_producto_licitacion,
                        descripcion_item_licitacion,
                        MI_CATALOGO_ESTRUCTURADO
                    )

                    if producto_de_mi_catalogo_coincidente:
                        oportunidad = {
                            "Tender_id": codigo_externo,
                            "Producto de mi Catálogo": producto_de_mi_catalogo_coincidente,
                            "Nombre_Producto Licitación": nombre_producto_licitacion,
                            "Descripcion": descripcion_item_licitacion,
                            "Quantity": cantidad_licitacion,
                            "Fecha Cierre": fecha_cierre_display,
                            "Vencimiento": dias_para_cierre,
                            "Nombre Licitación General": detalle_lic.get("Nombre", "Sin Nombre General"),
                        }
                        st.session_state.oportunidades_encontradas.append(oportunidad)
        
        progress_bar_placeholder.empty()
        log_message(f"Procesamiento de detalles completado. {len(st.session_state.oportunidades_encontradas)} oportunidades encontradas.")
    else:
        log_message("No se encontraron licitaciones activas de CENABAST para procesar hoy.")
    log_message("Fin de la búsqueda.")

if st.button("Buscar Nuevas Oportunidades Ahora", type="primary", use_container_width=True):
    with st.spinner("Iniciando búsqueda en MercadoPúblico..."): # Mensaje de spinner ajustado
        run_neshama_logic()

if st.session_state.busqueda_realizada:
    if st.session_state.oportunidades_encontradas:
        st.header(f"Resultados de la Búsqueda ({len(st.session_state.oportunidades_encontradas)} oportunidades encontradas):")
        df_oportunidades = pd.DataFrame(st.session_state.oportunidades_encontradas)
        
        column_order_internal = [
            "Tender_id", "Nombre_Producto Licitación", "Descripcion", 
            "Fecha Cierre", "Quantity", "Vencimiento",
            "Producto de mi Catálogo", "Nombre Licitación General" 
        ]
        
        df_display_intermediate = pd.DataFrame()
        for col in column_order_internal:
            if col in df_oportunidades.columns:
                df_display_intermediate[col] = df_oportunidades[col]
            else:
                df_display_intermediate[col] = "N/D"
        
        df_display_intermediate = df_display_intermediate.rename(columns={
            "Nombre_Producto Licitación": "Nombre_Producto"
        })
        
        final_column_order_display = [
            "Tender_id", "Nombre_Producto", "Descripcion", 
            "Fecha Cierre", "Quantity", "Vencimiento"
        ]
        df_display_final = df_display_intermediate[[col for col in final_column_order_display if col in df_display_intermediate.columns]]

        st.dataframe(df_display_final, height=600, use_container_width=True)

        @st.cache_data
        def convert_df_to_csv(df_to_convert):
            return df_to_convert.to_csv(index=False).encode('utf-8-sig')

        csv = convert_df_to_csv(df_display_final) 
        st.download_button(
            label="Descargar resultados como CSV",
            data=csv,
            file_name='oportunidades_pinnacle.csv', # Nombre de archivo cambiado
            mime='text/csv',
        )
    elif st.session_state.log_messages: 
        st.info("No se encontraron oportunidades que coincidan con tu catálogo de productos en esta búsqueda, o hubo problemas al obtener detalles. Revisa el log.")
    
with st.expander("Ver registro de actividad (Log)", expanded=False):
    if st.session_state.log_messages:
        log_text = "\n".join(reversed(st.session_state.log_messages))
        st.text_area("Registro:", value=log_text, height=300, disabled=True, key="log_area_pinnacle")
    else:
        st.caption("El registro de actividad está vacío.")