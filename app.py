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

def obtener_checkbox(prop):
    try:
        if prop["type"] == "checkbox":
            return prop["checkbox"]
    except:
        return False
    return False

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
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔮 Mismo género", use_container_width=True):
            g_ref = set(ref["generos"])
            a_ref = set(ref["autores_ids"])
            
            if not g_ref:
                st.warning("El libro que has seleccionado no tiene géneros asignados para poder comparar.")
            else:
                # Quitamos los que son del mismo autor (la idea es variar la pluma)
                cands = [p for p in candidatos if not set(p["autores_ids"]).intersection(a_ref)]
                
                # Nivel 1: Igualdad total
                opciones_exactas = [p for p in cands if set(p["generos"]) == g_ref]
                # Nivel 2: Tiene todo lo tuyo + algún género extra
                opciones_expandidas = [p for p in cands if g_ref.issubset(set(p["generos"])) and set(p["generos"]) != g_ref]
                # Nivel 3: Tiene algunos de tus géneros, pero NO tiene géneros "intrusos"
                opciones_concentradas = [p for p in cands if set(p["generos"]).issubset(g_ref) and len(set(p["generos"])) > 0 and set(p["generos"]) != g_ref]
                
                if opciones_exactas:
                    st.success(f"🔥 **Match Exacto (100% pureza):**\n\n{formato_mensaje(random.choice(opciones_exactas))}")
                elif opciones_expandidas:
                    st.success(f"✨ **Match Expandido (Tus géneros + un toque extra):**\n\n{formato_mensaje(random.choice(opciones_expandidas))}")
                elif opciones_concentradas:
                    st.success(f"🎯 **Match Concentrado (Esencia pura):**\n\n{formato_mensaje(random.choice(opciones_concentradas))}")
                else:
                    st.warning("No hay libros pendientes que igualen la pureza de estos géneros. ¡Prueba a cambiar radicalmente!")

    with col2:
        if st.button("✍️ Mismo autor", use_container_width=True):
            a_ref = set(ref["autores_ids"])
            opciones = [p for p in candidatos if set(p["autores_ids"]).intersection(a_ref)]
            if opciones: st.success(f"Siguiendo con su pluma:\n\n{formato_mensaje(random.choice(opciones))}")
            else: st.warning("No te quedan libros pendientes de este autor.")

    with col3:
        if st.button("🔄 Cambio radical", use_container_width=True):
            opciones = [p for p in candidatos if not any(g in p["generos"] for g in ref["generos"])]
            if opciones: st.success(f"Rompe con todo:\n\n{formato_mensaje(random.choice(opciones))}")
            else: st.warning("¡Añade más variedad a tus pendientes!")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🔍 Opciones Avanzadas")
    col4, col5, col6, col7 = st.columns(4)
    
    with col4:
        if st.button("🔗 Continuar Saga", use_container_width=True):
            saga_actual = ref.get("saga_texto")
            if not saga_actual:
                st.warning("El libro seleccionado no pertenece a ninguna saga conocida.")
            else:
                opciones = [p for p in candidatos if p.get("saga_texto") == saga_actual and p.get("numero_saga") is not None]
                if opciones:
                    siguiente = min(opciones, key=lambda x: safe_float(x["numero_saga"]))
                    st.success(f"El viaje continúa:\n\n{formato_mensaje(siguiente)}")
                else:
                    st.warning("¡Felicidades! Estás al día con esta saga (o no tienes las continuaciones en pendientes).")
                    
    with col5:
        if st.button("📚 Saga Similar", use_container_width=True):
            g_ref = set(ref["generos"])
            candidatos_saga = [p for p in candidatos if p.get("saga_texto") and p.get("saga_texto") != ref.get("saga_texto") and len(g_ref.intersection(set(p["generos"]))) >= 1]
            opciones_inicio = primeras_de_saga(candidatos_saga)
            if opciones_inicio:
                st.success(f"Empieza una nueva aventura:\n\n{formato_mensaje(random.choice(opciones_inicio))}")
            else:
                st.warning("No hay nuevas sagas de este género listas para empezar.")

    with col6:
        if st.button("🎨 Buscar por Color", use_container_width=True):
            c_ref = set(ref.get("colores", []))
            opciones = [p for p in candidatos if set(p.get("colores", [])).intersection(c_ref)]
            if opciones: st.success(f"Estética compartida:\n\n{formato_mensaje(random.choice(opciones))}")
            else: st.warning("No hay libros con esta paleta.")

    with col7:
        if st.button("🇬🇧 En Inglés", use_container_width=True):
            opciones = [p for p in candidatos if p.get("es_ingles", False)]
            if opciones: st.success(f"Para tu reto de lectura:\n\n{formato_mensaje(random.choice(opciones))}")
            else: st.warning("No tienes libros pendientes marcados en inglés.")

except Exception as e:
    st.error("❌ Ups, error al cargar.")
    st.write(e)