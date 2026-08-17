import streamlit as st
import requests
import random

st.set_page_config(page_title="Mi Recomendador", page_icon="📚", layout="wide")

# Cargamos las claves de forma segura desde Streamlit
NOTION_TOKEN = st.secrets["notion_token"]
DATABASE_ID = st.secrets["database_id"]

def obtener_titulo(prop):
    try:
        return prop["title"][0]["plain_text"]
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
            if next_cursor:
                payload["start_cursor"] = next_cursor
                
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
        # (Aquí hemos quitado el mensaje verde de éxito como querías)
        
        nombres_libros = []
        diccionario_libros = {}
        pendientes = []
        
        for libro in libros:
            props = libro["properties"]
            titulo = obtener_titulo(props.get("Título", {}))
            estado = obtener_estado(props.get("Estado", {}))
            generos = obtener_ids(props.get("Género", {}))
            autores = obtener_ids(props.get("Autor", {}))
            
            diccionario_libros[titulo] = {
                "titulo": titulo,
                "estado": estado,
                "generos": generos,
                "autores": autores
            }
            nombres_libros.append(titulo)
            
            if estado.lower() in ["por leer", "to read", "pendiente"]:
                pendientes.append(diccionario_libros[titulo])

        nombres_libros.sort()

        st.markdown("---")
        st.subheader("🎯 Tu punto de partida")
        libro_elegido = st.selectbox(
            "Selecciona un libro que hayas leído para basar las recomendaciones:", 
            nombres_libros,
            index=nombres_libros.index("La isla de la mujer dormida") if "La isla de la mujer dormida" in nombres_libros else 0
        )
        
        ref = diccionario_libros[libro_elegido]
        st.write(f"Has elegido **{libro_elegido}**. ¡Vamos a ver qué hay en tu lista de pendientes!")
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔮 Mismo género, distinto autor", use_container_width=True):
                opciones = [
                    p for p in pendientes 
                    if any(g in p["generos"] for g in ref["generos"]) 
                    and not any(a in p["autores"] for a in ref["autores"])
                ]
                if opciones:
                    recomendado = random.choice(opciones)
                    st.success(f"¡Prueba con **{recomendado['titulo']}**!")
                else:
                    st.warning("No tienes libros pendientes con este género exacto de otros autores.")
                    
        with col2:
            if st.button("🔄 Cambio radical", use_container_width=True):
                opciones = [
                    p for p in pendientes 
                    if not any(g in p["generos"] for g in ref["generos"]) 
                    and not any(a in p["autores"] for a in ref["autores"])
                ]
                if opciones:
                    recomendado = random.choice(opciones)
                    st.success(f"Rompe con todo: **{recomendado['titulo']}**")
                else:
                    st.warning("¡Añade más variedad a tu lista de pendientes!")
                    
        with col3:
            if st.button("🎨 Buscar por Color", use_container_width=True):
                st.info("Próximamente: filtrado automático por portadas.")

except Exception as e:
    st.error("❌ Ups, hubo un problema interno.")
    st.write(e)