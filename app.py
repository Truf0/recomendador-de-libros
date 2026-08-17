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
        if prop["type"] == "status": return prop["status"]["name"]
        if prop["type"] == "select": return prop["select"]["name"]
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

# Función que lee el número sea del tipo que sea
def obtener_numero(prop):
    if not prop: return None
    try:
        tipo = prop.get("type")
        if tipo == "number":
            return prop.get("number")
        if tipo == "formula":
            # Si la fórmula da un número o un texto con el número
            return prop.get("formula", {}).get("number") or prop.get("formula", {}).get("string")
        if tipo == "rich_text" and prop.get("rich_text"):
            return prop["rich_text"][0]["plain_text"]
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
    
    libros = []
    has_more = True
    next_cursor = None
    
    with st.spinner('Cargando estantería...'):
        while has_more:
            payload = {"page_size": 100}
            if next_cursor: payload["start_cursor"] = next_cursor
            respuesta = requests.post(url, headers=headers, json=payload)
            
            if respuesta.status_code == 200:
                datos = respuesta.json()
                libros.extend(datos.get("results", []))
                has_more = datos.get("has_more", False)
                next_cursor = datos.get("next_cursor", None)
            else:
                has_more = False
                break
                
    if len(libros) > 0:
        nombres_para_selector = []
        diccionario_libros = {}
        pendientes = []
        
        for libro in libros:
            props = libro["properties"]
            titulo = obtener_titulo(props.get("Título", {}))
            if titulo == "Sin título": continue
                
            estado = obtener_estado(props.get("Estado", {}))
            generos = obtener_ids(props.get("Género", {}))
            autores_ids = obtener_ids(props.get("Autor", {}))
            
            autor_texto = obtener_texto_formula(props.get("Texto Autor", {}))
            saga_texto = obtener_texto_formula(props.get("Texto Saga", {}))
            
            # Busca la columna aunque se llame Nº Saga, Numero Saga u Orden
            prop_num = props.get("Nº Saga") or props.get("Numero Saga") or props.get("Orden") or {}
            numero_saga = obtener_numero(prop_num)
            
            colores_portada = obtener_colores_multiselect(props.get("Color", {}))
            
            nombre_desplegable = f"{titulo}, de {autor_texto}" if autor_texto else titulo
            
            diccionario_libros[nombre_desplegable] = {
                "titulo": titulo,
                "autor_texto": autor_texto,
                "saga_texto": saga_texto,
                "numero_saga": numero_saga,
                "colores": colores_portada,
                "estado": estado,
                "generos": generos,
                "autores_ids": autores_ids
            }
            nombres_para_selector.append(nombre_desplegable)
            
            if estado.lower() in ["por leer", "to read", "pendiente"]:
                pendientes.append(diccionario_libros[nombre_desplegable])

        nombres_para_selector.sort()

        st.markdown("---")
        st.subheader("🎯 Tu punto de partida")
        
        libro_elegido = st.selectbox("Selecciona un libro que hayas leído:", nombres_para_selector)
        ref = diccionario_libros[libro_elegido]
        st.write(f"Has elegido **{libro_elegido}**.")
        st.markdown("---")
        
        def formato_mensaje(rec):
            mensaje = f"Prueba con **{rec['titulo']}**, de {rec['autor_texto']}."
            if rec['saga_texto']:
                num = rec['numero_saga']
                if num is not None and str(num).strip() != "":
                    # Si viene como float (ej: 1.0), lo convertimos a entero
                    try:
                        num = int(float(num))
                    except:
                        pass
                    num_texto = f" (Libro {num})"
                else:
                    num_texto = ""
                mensaje += f" \n*Pertenece a {rec['saga_texto']}{num_texto}*"
            return mensaje

        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔮 Mismo género, distinto autor", use_container_width=True):
                generos_ref = set(ref["generos"])
                autores_ref = set(ref["autores_ids"])
                opciones_puras = [p for p in pendientes if not set(p["autores_ids"]).intersection(autores_ref) and len(generos_ref.intersection(set(p["generos"]))) >= 2]
                opciones_suaves = [p for p in pendientes if not set(p["autores_ids"]).intersection(autores_ref) and len(generos_ref.intersection(set(p["generos"]))) == 1]
                
                if opciones_puras:
                    rec = random.choice(opciones_puras)
                    st.success(f"🔥 **¡Match de Alta Pureza!**\n\n{formato_mensaje(rec)}")
                elif opciones_suaves:
                    rec = random.choice(opciones_suaves)
                    st.success(f"✨ **Match Suave**\n\n{formato_mensaje(rec)}")
                else:
                    st.warning("No tienes pendientes de otros autores con estos géneros.")
                    
        with col2:
            if st.button("🔄 Cambio radical", use_container_width=True):
                opciones = [p for p in pendientes if not any(g in p["generos"] for g in ref["generos"]) and not any(a in p["autores_ids"] for a in ref["autores_ids"])]
                if opciones:
                    rec = random.choice(opciones)
                    st.success(f"Rompe con todo leyendo:\n\n{formato_mensaje(rec)}")
                else:
                    st.warning("¡Añade más variedad a tu lista de pendientes!")
                    
        with col3:
            if st.button("🎨 Buscar por Color", use_container_width=True):
                colores_ref = set(ref.get("colores", []))
                if not colores_ref:
                    st.warning("Este libro todavía no ha sido analizado por el robot de colores.")
                else:
                    opciones = [p for p in pendientes if set(p.get("colores", [])).intersection(colores_ref)]
                    if opciones:
                        rec = random.choice(opciones)
                        colores_comunes = list(set(rec['colores']).intersection(colores_ref))
                        st.success(f"Comparten tonos de **{' y '.join(colores_comunes)}**.\n\nSigue la estética leyendo:\n\n{formato_mensaje(rec)}")
                    else:
                        st.warning("No tienes pendientes con portadas que compartan esta paleta.")

except Exception as e:
    st.error("❌ Ups, hubo un problema interno.")
    st.write(e)