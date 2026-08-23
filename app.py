import streamlit as st
import requests
import random
import json
import google.generativeai as genai

st.set_page_config(page_title="Mi Recomendador", page_icon="📚", layout="wide")

NOTION_TOKEN = st.secrets["notion_token"]
DATABASE_ID = st.secrets["database_id"]

def obtener_titulo(prop):
    try:
        titulo_real = prop["title"][0]["plain_text"]
        return titulo_real if titulo_real.strip() else "Sin título"
    except:
        return "Sin título"

def obtener_estado(prop):
    try:
        if prop["type"] == "status": return prop["status"]["name"].lower()
        if prop["type"] == "select": return prop["select"]["name"].lower()
    except:
        return ""
    return ""

def obtener_ids(prop):
    if not prop: return []
    try:
        if prop["type"] == "relation": return [r["id"] for r in prop["relation"]]
        if prop["type"] == "multi_select": return [m["id"] for m in prop["multi_select"]]
        if prop["type"] == "select" and prop["select"]: return [prop["select"]["id"]]
    except:
        pass
    return []

def obtener_texto_formula(prop):
    try:
        if prop["type"] == "formula":
            return prop["formula"].get("string", "")
    except:
        return ""
    return ""

def obtener_numero(prop):
    if not prop: return None
    try:
        tipo = prop.get("type")
        if tipo == "number": return prop.get("number")
        if tipo == "formula": return prop.get("formula", {}).get("number") or prop.get("formula", {}).get("string")
        if tipo == "rich_text" and prop.get("rich_text"): return prop["rich_text"][0]["plain_text"]
    except:
        return None
    return None

def obtener_colores_multiselect(prop):
    try:
        if prop["type"] == "multi_select":
            return [c["name"] for c in prop["multi_select"]]
    except:
        return []
    return []

def obtener_checkbox(prop):
    try:
        if prop["type"] == "checkbox":
            return prop["checkbox"]
    except:
        return False
    return False

def obtener_descripcion(prop):
    try:
        if prop["type"] == "rich_text" and prop["rich_text"]:
            return "".join([t["plain_text"] for t in prop["rich_text"]])
    except:
        return ""
    return ""

def safe_float(val):
    try:
        return float(val)
    except:
        return 9999.0

def primeras_de_saga(lista_candidatos):
    sagas = {}
    for libro in lista_candidatos:
        saga = libro.get("saga_texto")
        num = libro.get("numero_saga")
        if saga and num is not None:
            n = safe_float(num)
            if saga not in sagas or n < sagas[saga]["n"]:
                sagas[saga] = {"n": n, "libro": libro}
    return [v["libro"] for v in sagas.values()]

st.title("📚 Mi Recomendador de Lectura")

# --- INICIO DEL MODO DETECTIVE ---
try:
    genai.configure(api_key=st.secrets["gemini_api_key"])
    modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    st.error(f"🔍 MIS MODELOS DISPONIBLES SON: {modelos}")
    st.info("Copia el texto del cuadro rojo de arriba y pégamelo en el chat. Cuando sepamos el modelo, te daré el código final.")
    st.stop() # Esto pausa la app aquí para que no cargue lo demás por ahora
except Exception as e:
    st.error(f"Error al conectar con la API: {e}")
    st.stop()
# --- FIN DEL MODO DETECTIVE ---

try:
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    leidos = []
    por_terminar = []
    pendientes = []
    diccionario_libros = {}
    
    with st.spinner('Cargando estantería completa...'):
        has_more = True
        next_cursor = None
        while has_more:
            payload = {"page_size": 100}
            if next_cursor: payload["start_cursor"] = next_cursor
            
            try:
                respuesta = requests.post(url, headers=headers, json=payload, timeout=15)
            except requests.exceptions.Timeout:
                st.error("⚠️ La conexión con Notion está tardando demasiado. Vuelve a recargar.")
                st.stop()
                
            if respuesta.status_code == 200:
                datos = respuesta.json()
                for libro in datos.get("results", []):
                    props = libro["properties"]
                    titulo = obtener_titulo(props.get("Título", {}))
                    if titulo == "Sin título": continue
                    
                    estado = obtener_estado(props.get("Estado", {}))
                    info_libro = {
                        "titulo": titulo,
                        "autor_texto": obtener_texto_formula(props.get("Texto Autor", {})),
                        "saga_texto": obtener_texto_formula(props.get("Texto Saga", {})),
                        "numero_saga": obtener_numero(props.get("Nº Saga", {})),
                        "colores": obtener_colores_multiselect(props.get("Color", {})),
                        "generos": obtener_ids(props.get("Género", {})),
                        "autores_ids": obtener_ids(props.get("Autor", {})),
                        "descripcion": obtener_descripcion(props.get("Descripción", {})),
                        "es_por_terminar": False,
                        "es_ingles": obtener_checkbox(props.get("Inglés", {}))
                    }
                    
                    nombre_visual = f"{info_libro['titulo']}, de {info_libro['autor_texto']}" if info_libro['autor_texto'] else info_libro['titulo']
                    diccionario_libros[nombre_visual] = info_libro
                    
                    if any(k in estado for k in ["leído", "terminado", "finished", "leídos"]):
                        leidos.append(nombre_visual)
                    elif "por terminar" in estado:
                        info_libro["es_por_terminar"] = True
                        por_terminar.append(info_libro)
                    elif any(k in estado for k in ["leyendo", "en curso", "reading"]):
                        pass 
                    else:
                        pendientes.append(info_libro)
                
                has_more = datos.get("has_more", False)
                next_cursor = datos.get("next_cursor", None)
            else:
                break

    leidos.sort()
    candidatos = pendientes + por_terminar
    
    st.subheader("🎯 Tu punto de partida")
    libro_elegido = st.selectbox("Último título leído", leidos)
    ref = diccionario_libros[libro_elegido]
    
    st.markdown("---")
    
    def formato_mensaje(rec):
        if rec.get("es_por_terminar", False):
            mensaje = f"¿Y si retomas este libro?\n\n**{rec['titulo']}**, de {rec['autor_texto']}."
        else:
            mensaje = f"Prueba con **{rec['titulo']}**, de {rec['autor_texto']}."
            
        if rec['saga_texto']:
            num = rec['numero_saga']
            num_texto = f" (Libro {int(float(num))})" if (num and str(num).replace('.','',1).isdigit()) else ""
            mensaje += f" \n*Pertenece a {rec['saga_texto']}{num_texto}*"
        return mensaje

    st.markdown("#### 🎲 Opciones Rápidas")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔮 Mismo género", use_container_width=True):
            pass # (código original recortado aquí solo de prueba visual)

except Exception as e:
    st.error(f"❌ Ups, error al cargar: {e}")