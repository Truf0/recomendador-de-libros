import streamlit as st
import requests
import random

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

st.title("📚 Mi Recomendador de Lectura")

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
            
            respuesta = requests.post(url, headers=headers, json=payload)
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
                        "es_por_terminar": False
                    }
                    
                    nombre_visual = f"{info_libro['titulo']}, de {info_libro['autor_texto']}" if info_libro['autor_texto'] else info_libro['titulo']
                    diccionario_libros[nombre_visual] = info_libro
                    
                    # Clasificación estricta según tus reglas
                    if any(k in estado for k in ["leído", "terminado", "finished", "leídos"]):
                        leidos.append(nombre_visual)
                    elif any(k in estado for k in ["por terminar", "leyendo", "en curso", "reading", "retomar"]):
                        info_libro["es_por_terminar"] = True
                        por_terminar.append(info_libro)
                    else:
                        pendientes.append(info_libro)
                
                has_more = datos.get("has_more", False)
                next_cursor = datos.get("next_cursor", None)
            else:
                break

    # El desplegable solo tiene los leídos
    leidos.sort()
    
    # Las recomendaciones miran en Por leer (pendientes) + Por terminar
    candidatos = pendientes + por_terminar
    
    st.subheader("🎯 Tu punto de partida")
    libro_elegido = st.selectbox("Último título leído", leidos)
    ref = diccionario_libros[libro_elegido]
    
    st.markdown("---")
    
    def formato_mensaje(rec):
        # Si es un libro de "por terminar", usamos la frase especial
        if rec.get("es_por_terminar", False):
            mensaje = f"¿Y si retomas este libro?\n\n**{rec['titulo']}**, de {rec['autor_texto']}."
        else:
            mensaje = f"Prueba con **{rec['titulo']}**, de {rec['autor_texto']}."
            
        if rec['saga_texto']:
            num = rec['numero_saga']
            num_texto = f" (Libro {int(float(num))})" if (num and str(num).replace('.','',1).isdigit()) else ""
            mensaje += f" \n*Pertenece a {rec['saga_texto']}{num_texto}*"
        return mensaje

    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔮 Mismo género", use_container_width=True):
            g_ref = set(ref["generos"])
            a_ref = set(ref["autores_ids"])
            opciones = [p for p in candidatos if not set(p["autores_ids"]).intersection(a_ref) and len(g_ref.intersection(set(p["generos"]))) >= 1]
            if opciones: st.success(formato_mensaje(random.choice(opciones)))
            else: st.warning("No hay coincidencias de género.")

    with col2:
        if st.button("🔄 Cambio radical", use_container_width=True):
            opciones = [p for p in candidatos if not any(g in p["generos"] for g in ref["generos"])]
            if opciones: st.success(f"Rompe con todo:\n\n{formato_mensaje(random.choice(opciones))}")
            else: st.warning("¡Añade más variedad!")

    with col3:
        if st.button("🎨 Buscar por Color", use_container_width=True):
            c_ref = set(ref.get("colores", []))
            opciones = [p for p in candidatos if set(p.get("colores", [])).intersection(c_ref)]
            if opciones: st.success(f"Estética compartida:\n\n{formato_mensaje(random.choice(opciones))}")
            else: st.warning("No hay libros con esta paleta.")

except Exception as e:
    st.error("❌ Ups, error al cargar.")
    st.write(e)