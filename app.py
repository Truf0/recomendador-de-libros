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

# Nueva función para leer la paleta de 3 colores (Multi-select)
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
        nombres_para_selector = []
        diccionario_libros = {}
        pendientes = []
        
        for libro in libros:
            props = libro["properties"]
            titulo = obtener_titulo(props.get("Título", {}))
            
            if titulo == "Sin título":
                continue
                
            estado = obtener_estado(props.get("Estado", {}))
            generos = obtener_ids(props.get("Género", {}))
            autores_ids = obtener_ids(props.get("Autor", {}))
            
            autor_texto = obtener_texto_formula(props.get("Texto Autor", {}))
            saga_texto = obtener_texto_formula(props.get("Texto Saga", {}))
            colores_portada = obtener_colores_multiselect(props.get("Color", {}))
            
            nombre_desplegable = f"{titulo}, de {autor_texto}" if autor_texto else titulo
            
            diccionario_libros[nombre_desplegable] = {
                "titulo": titulo,
                "autor_texto": autor_texto,
                "saga_texto": saga_texto,
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
        
        indice_defecto = 0
        for i, nombre in enumerate(nombres_para_selector):
            if "La isla de la mujer dormida" in nombre:
                indice_defecto = i
                break

        libro_elegido = st.selectbox(
            "Selecciona un libro que hayas leído para basar las recomendaciones:", 
            nombres_para_selector,
            index=indice_defecto
        )
        
        ref = diccionario_libros[libro_elegido]
        st.write(f"Has elegido **{libro_elegido}**. ¡Vamos a ver qué hay en tu lista de pendientes!")
        st.markdown("---")
        
        col1, col2, col3 = st.columns(3)
        
        # --- EL BOTÓN DE GÉNEROS MEJORADO (MATCH DE ALTA PUREZA) ---
        with col1:
            if st.button("🔮 Mismo género, distinto autor", use_container_width=True):
                generos_ref = set(ref["generos"])
                autores_ref = set(ref["autores_ids"])
                
                # Buscamos coincidencias
                opciones_puras = []
                opciones_suaves = []
                
                for p in pendientes:
                    # Que no sea del mismo autor
                    if not set(p["autores_ids"]).intersection(autores_ref):
                        generos_p = set(p["generos"])
                        comunes = generos_ref.intersection(generos_p)
                        
                        if len(comunes) >= 2:
                            opciones_puras.append(p)
                        elif len(comunes) == 1:
                            opciones_suaves.append(p)
                
                if opciones_puras:
                    rec = random.choice(opciones_puras)
                    mensaje = f"🔥 **¡Match de Alta Pureza!** (Coinciden varios géneros).\n\nPrueba con **{rec['titulo']}**, de {rec['autor_texto']}."
                    if rec['saga_texto']:
                        mensaje += f" \n*(Pertenece a la saga: {rec['saga_texto']})*"
                    st.success(mensaje)
                elif opciones_suaves:
                    rec = random.choice(opciones_suaves)
                    mensaje = f"✨ **Match Suave** (Coincide 1 género).\n\nPrueba con **{rec['titulo']}**, de {rec['autor_texto']}."
                    if rec['saga_texto']:
                        mensaje += f" \n*(Pertenece a la saga: {rec['saga_texto']})*"
                    st.success(mensaje)
                else:
                    st.warning("No tienes libros pendientes que compartan géneros con este y sean de otros autores.")
                    
        with col2:
            if st.button("🔄 Cambio radical", use_container_width=True):
                opciones = [
                    p for p in pendientes 
                    if not any(g in p["generos"] for g in ref["generos"]) 
                    and not any(a in p["autores_ids"] for a in ref["autores_ids"])
                ]
                if opciones:
                    rec = random.choice(opciones)
                    mensaje = f"Rompe con todo leyendo **{rec['titulo']}**, de {rec['autor_texto']}."
                    if rec['saga_texto']:
                        mensaje += f" \n*(Pertenece a la saga: {rec['saga_texto']})*"
                    st.success(mensaje)
                else:
                    st.warning("¡Añade más variedad a tu lista de pendientes!")
                    
        # --- EL BOTÓN DE COLORES CON PALETAS (COMPARTEN VIBRA VISUAL) ---
        with col3:
            if st.button("🎨 Buscar por Color", use_container_width=True):
                colores_ref = set(ref.get("colores", []))
                
                if not colores_ref:
                    st.warning("Este libro todavía no ha sido analizado por el robot de colores.")
                else:
                    # Buscamos libros pendientes que compartan AL MENOS 1 color de la paleta
                    opciones = [
                        p for p in pendientes 
                        if set(p.get("colores", [])).intersection(colores_ref)
                    ]
                    
                    if opciones:
                        rec = random.choice(opciones)
                        # Averiguamos qué color o colores coinciden exactamente para decírselo al usuario
                        colores_comunes = list(set(rec['colores']).intersection(colores_ref))
                        texto_colores = " y ".join(colores_comunes)
                        
                        mensaje = f"Comparten tonos de **{texto_colores}**.\n\nSigue la misma estética leyendo **{rec['titulo']}**, de {rec['autor_texto']}."
                        if rec['saga_texto']:
                            mensaje += f" \n*(Pertenece a la saga: {rec['saga_texto']})*"
                        st.success(mensaje)
                    else:
                        st.warning("No tienes libros pendientes con portadas que compartan esta paleta.")

except Exception as e:
    st.error("❌ Ups, hubo un problema interno.")
    st.write(e)